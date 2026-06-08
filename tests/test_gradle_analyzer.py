"""
Tests para GradleDependencyAnalyzer:
  - scan_modules: detecta módulos correctamente
  - analyze_gradle_dependencies: resuelve dependencias entre módulos
"""

from pathlib import Path

from gradle_analyzer import GradleDependencyAnalyzer
from analyzer_utils import find_gradle_file

FIXTURES = Path(__file__).parent / "fixtures"


class TestGradleDependencyAnalyzer:

    def test_scan_simple_modules(self):
        """Detecta exactamente los módulos del fixture simple."""
        analyzer = GradleDependencyAnalyzer(base_path=str(FIXTURES / "simple"))
        analyzer.scan_modules()

        assert "app" in analyzer.modules
        assert "core" in analyzer.modules
        assert len(analyzer.modules) == 2

    def test_analyze_simple_dependency(self):
        """app depende de core via implementation."""
        analyzer = GradleDependencyAnalyzer(base_path=str(FIXTURES / "simple"))
        analyzer.scan_modules()
        analyzer.analyze_gradle_dependencies()

        assert "core" in analyzer.dependencies["app"].get("implementation", set())

    def test_analyze_ambiguous_no_false_positive(self):
        """
        Bug 1 (integración): payments depende de payments:common,
        quick-payments NO debe aparecer como dependencia de nadie.
        """
        analyzer = GradleDependencyAnalyzer(base_path=str(FIXTURES / "ambiguous"))
        analyzer.scan_modules()
        analyzer.analyze_gradle_dependencies()

        all_deps = {
            dep
            for scopes in analyzer.dependencies.values()
            for deps in scopes.values()
            for dep in deps
        }
        assert "quick-payments" not in all_deps

    def test_generate_report_returns_string(self):
        analyzer = GradleDependencyAnalyzer(base_path=str(FIXTURES / "simple"))
        analyzer.scan_modules()
        analyzer.analyze_gradle_dependencies()

        report = analyzer.generate_report()
        assert isinstance(report, str)
        assert "app" in report
        assert "core" in report

    def test_generate_dot_returns_digraph(self):
        analyzer = GradleDependencyAnalyzer(base_path=str(FIXTURES / "simple"))
        analyzer.scan_modules()
        analyzer.analyze_gradle_dependencies()

        dot = analyzer.generate_dot()
        assert dot.startswith("digraph")
        assert "app" in dot
        assert "core" in dot

    def test_generate_ascii_returns_text(self):
        analyzer = GradleDependencyAnalyzer(base_path=str(FIXTURES / "simple"))
        analyzer.scan_modules()
        analyzer.analyze_gradle_dependencies()

        ascii_out = analyzer.generate_ascii()
        assert "app" in ascii_out
        assert "core" in ascii_out

    def test_focus_filters_modules(self):
        analyzer = GradleDependencyAnalyzer(base_path=str(FIXTURES / "simple"))
        analyzer.scan_modules()
        analyzer.analyze_gradle_dependencies()

        focused = analyzer._focused_modules(["app"])
        assert "app" in focused
        assert "core" in focused

    def test_focus_excludes_unrelated(self):
        analyzer = GradleDependencyAnalyzer(base_path=str(FIXTURES / "simple"))
        analyzer.scan_modules()
        analyzer.analyze_gradle_dependencies()

        focused = analyzer._focused_modules(["core"])
        assert "core" in focused
        assert "app" not in focused

    def test_resolves_type_safe_accessors_end_to_end(self):
        """
        Integración: el analizador completo sobre un proyecto con type-safe
        accessors (projects.foo.barBaz) debe resolver las dependencias igual
        que con el formato clásico project(":foo:bar").
        """
        analyzer = GradleDependencyAnalyzer(base_path=str(FIXTURES / "accessors"))
        analyzer.scan_modules()
        analyzer.analyze_gradle_dependencies()

        app_deps = analyzer.dependencies.get("app", {})
        assert "feature:payments-common" in app_deps.get("implementation", set())
        assert "core:network_api"        in app_deps.get("api", set())
        # Mezcla con sintaxis clásica en el mismo archivo
        assert "legacy:plain-lib"        in app_deps.get("implementation", set())


class TestSubtreeAnalysis:
    """Analizar un SUBÁRBOL (no la raíz) debe usar los nombres CANÓNICOS de los
    módulos (relativos a la raíz, con prefijo de grupo), no relativos a la carpeta
    apuntada. Si no, ':grupo:hijo' se vería como 'hijo' y los edges internos del
    subárbol se perderían (síntoma: "no detecta nada")."""

    def _make_project(self, root: Path):
        (root / "settings.gradle.kts").write_text(
            'include("app")\ninclude("view")\ninclude("pin")\n'
            'include("grp:sub-a")\ninclude("grp:sub-b")\n', encoding="utf-8")

        def mod(path, body):
            d = root / path
            d.mkdir(parents=True, exist_ok=True)
            (d / "build.gradle.kts").write_text(body, encoding="utf-8")

        mod("app",       'dependencies {\n  implementation(project(":grp:sub-a"))\n  implementation(project(":view"))\n}')
        mod("view",      'dependencies {}')
        mod("pin",       'dependencies {}')
        mod("grp/sub-a", 'dependencies {\n  implementation(project(":view"))\n  implementation(project(":pin"))\n}')
        mod("grp/sub-b", 'dependencies {\n  implementation(project(":grp:sub-a"))\n}')

    def test_subtree_uses_canonical_names(self, tmp_path):
        self._make_project(tmp_path)
        a = GradleDependencyAnalyzer(base_path=str(tmp_path / "grp"), verbose=False)
        a.scan_modules()
        # Nombres completos con prefijo de grupo, NO 'sub-a' / 'sub-b'
        assert set(a.modules) == {"grp:sub-a", "grp:sub-b"}
        # El registry completo (known_modules) sigue siendo el de la raíz
        assert "app" in a.known_modules

    def test_subtree_preserves_internal_edge(self, tmp_path):
        self._make_project(tmp_path)
        a = GradleDependencyAnalyzer(base_path=str(tmp_path / "grp"), verbose=False)
        a.scan_modules()
        a.analyze_gradle_dependencies()
        # El edge interno del subárbol (sub-b -> grp:sub-a) se conserva
        assert "grp:sub-a" in a.dependencies["grp:sub-b"].get("implementation", set())
        # Y las deps hacia afuera del subárbol también se detectan (nombres canónicos)
        assert "view" in a.dependencies["grp:sub-a"].get("implementation", set())

    def test_root_analysis_unchanged(self, tmp_path):
        """Analizar la raíz completa sigue detectando todos los módulos."""
        self._make_project(tmp_path)
        a = GradleDependencyAnalyzer(base_path=str(tmp_path), verbose=False)
        a.scan_modules()
        assert set(a.modules) == {"app", "view", "pin", "grp:sub-a", "grp:sub-b"}


class TestFindGradleFile:

    def test_finds_standard_build_gradle(self):
        p = find_gradle_file(FIXTURES / "simple" / "app")
        assert p is not None
        assert p.name == "build.gradle"

    def test_returns_none_when_no_file(self):
        p = find_gradle_file(FIXTURES / "simple")
        assert p is None

    def test_finds_custom_named_file(self, tmp_path):
        (tmp_path / "chat.gradle.kts").write_text('dependencies {}')
        p = find_gradle_file(tmp_path)
        assert p is not None
        assert p.name == "chat.gradle.kts"
