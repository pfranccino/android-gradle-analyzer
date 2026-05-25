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
