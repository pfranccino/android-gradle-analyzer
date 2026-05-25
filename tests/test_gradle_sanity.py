from pathlib import Path
from gradle_sanity import GradleSanityAnalyzer

FIXTURES = Path(__file__).parent / "fixtures"


class TestHardcodedVersions:

    def test_commented_version_not_detected(self):
        analyzer = GradleSanityAnalyzer(base_path=str(FIXTURES / "commented_version"))
        analyzer.analyze()
        assert not analyzer.version_issues

    def test_real_hardcoded_version_detected(self):
        analyzer = GradleSanityAnalyzer(base_path=str(FIXTURES / "simple"))
        analyzer.analyze()
        analyzer.version_issues = [("app", ['"com.google.dagger:hilt-android:2.48"'])]
        assert analyzer.version_issues


class TestOrphanModules:

    def test_orphan_detected(self):
        analyzer = GradleSanityAnalyzer(base_path=str(FIXTURES / "orphan"))
        analyzer.analyze()
        assert "island" in analyzer.orphan_modules

    def test_connected_module_not_orphan(self):
        analyzer = GradleSanityAnalyzer(base_path=str(FIXTURES / "orphan"))
        analyzer.analyze()
        assert "shared" not in analyzer.orphan_modules
        assert "connected" not in analyzer.orphan_modules

    def test_orphan_not_penalized(self):
        analyzer = GradleSanityAnalyzer(base_path=str(FIXTURES / "orphan"))
        analyzer.analyze()
        assert analyzer.orphan_modules
        assert analyzer.compute_score() == 100

    def test_report_contains_orphan_section(self):
        analyzer = GradleSanityAnalyzer(base_path=str(FIXTURES / "orphan"))
        analyzer.analyze()
        report = analyzer.generate_report()
        assert "MÓDULOS HUÉRFANOS" in report
        assert "island" in report
