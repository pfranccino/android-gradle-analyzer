from pathlib import Path
from gradle_impact import ImpactAnalyzer

FIXTURES = Path(__file__).parent / "fixtures"


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
