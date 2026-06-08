from pathlib import Path
from gradle_impact import ImpactAnalyzer

FIXTURES = Path(__file__).parent / "fixtures"


class TestImpactFromSubfolder:
    """Pasar una SUBCARPETA como project_root debe escanear desde la raíz y
    alcanzar a los dependientes externos (ej. app) en el grafo invertido."""

    def _project(self, root: Path):
        (root / "settings.gradle.kts").write_text(
            'include("app")\ninclude("view")\ninclude("grp:sub-a")\ninclude("grp:sub-b")\n',
            encoding="utf-8")

        def mod(path, body):
            d = root / path
            d.mkdir(parents=True, exist_ok=True)
            (d / "build.gradle.kts").write_text(body, encoding="utf-8")

        mod("app",       'dependencies {\n  implementation(project(":grp:sub-a"))\n}')
        mod("view",      'dependencies {}')
        mod("grp/sub-a", 'dependencies {\n  implementation(project(":view"))\n}')
        mod("grp/sub-b", 'dependencies {\n  implementation(project(":grp:sub-a"))\n}')

    def test_subfolder_path_reaches_external_dependents(self, tmp_path):
        self._project(tmp_path)
        a = ImpactAnalyzer(
            project_root=str(tmp_path / "grp"), target_module="grp:sub-a", verbose=False)
        a.scan_and_build_graph()
        a.compute_impact()
        assert "app" in a.impacted          # dependiente fuera del subárbol
        assert "grp:sub-b" in a.impacted


class TestImpactAnalyzer:

    def test_direct_impact(self):
        analyzer = ImpactAnalyzer(
            project_root=str(FIXTURES / "simple"),
            target_module="core",
        )
        analyzer.scan_and_build_graph()
        analyzer.compute_impact()

        assert "app" in analyzer.impacted
        assert analyzer.impacted["app"] == 1

    def test_no_impact_for_leaf(self):
        analyzer = ImpactAnalyzer(
            project_root=str(FIXTURES / "simple"),
            target_module="app",
        )
        analyzer.scan_and_build_graph()
        analyzer.compute_impact()

        assert not analyzer.impacted

    def test_report_contains_impacted_module(self):
        analyzer = ImpactAnalyzer(
            project_root=str(FIXTURES / "simple"),
            target_module="core",
        )
        analyzer.scan_and_build_graph()
        analyzer.compute_impact()

        report = analyzer.generate_report()
        assert "app" in report
        assert "core" in report

    def test_report_no_impact_message(self):
        analyzer = ImpactAnalyzer(
            project_root=str(FIXTURES / "simple"),
            target_module="app",
        )
        analyzer.scan_and_build_graph()
        analyzer.compute_impact()

        report = analyzer.generate_report()
        assert "Sin impacto" in report

    def test_transitive_impact(self):
        analyzer = ImpactAnalyzer(
            project_root=str(FIXTURES / "external"),
            target_module="payments:gateway",
        )
        analyzer.scan_and_build_graph()
        analyzer.compute_impact()

        assert "app" in analyzer.impacted
        assert analyzer.impacted["app"] == 1
