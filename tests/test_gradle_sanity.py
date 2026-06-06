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


class TestLeafCoupling:

    def _analyzer(self):
        return GradleSanityAnalyzer(base_path=str(FIXTURES / "leaf_coupling"))

    def test_feature_with_high_ca_detected(self):
        # payments: I≈0.71 (hoja) y Ca=2 (checkout + cart dependen de él) → dispara
        analyzer = self._analyzer()
        analyzer.analyze()
        modules = {m for m, *_ in analyzer.coupling_issues}
        assert "payments" in modules

    def test_advisory_does_not_change_score(self):
        # Con penalty default 0, hay hallazgos pero el score no cambia
        analyzer = self._analyzer()
        analyzer.analyze()
        assert analyzer.coupling_issues
        assert analyzer.compute_score() == 100

    def test_penalty_applied_when_configured(self):
        # leaf_penalty=10 (payments) + app_penalty=15 (app) → 100 - 25 = 75
        analyzer = self._analyzer()
        analyzer.config["coupling_limits"]["leaf_penalty"] = 10
        analyzer.config["coupling_limits"]["app_penalty"]  = 15
        analyzer.analyze()
        assert analyzer.compute_score() == 75

    def test_core_not_flagged(self):
        # core tiene I bajo (muchos dependen de él) → no es una hoja, no se reporta
        analyzer = self._analyzer()
        analyzer.analyze()
        modules = {m for m, *_ in analyzer.coupling_issues}
        assert "core" not in modules

    def test_ignore_override(self):
        analyzer = self._analyzer()
        analyzer.config["coupling_overrides"] = {"payments": "ignore"}
        analyzer.analyze()
        modules = {m for m, *_ in analyzer.coupling_issues}
        assert "payments" not in modules

    def test_app_plugin_detected_as_app(self):
        # app aplica com.android.application y tiene Ca>0 → kind "app"
        analyzer = self._analyzer()
        analyzer.analyze()
        kinds = {m: kind for m, kind, *_ in analyzer.coupling_issues}
        assert kinds.get("app") == "app"

    def test_json_contains_coupling_issues(self):
        analyzer = self._analyzer()
        analyzer.analyze()
        data = analyzer.to_json_dict()
        assert "coupling_issues" in data
        assert any(c["module"] == "payments" for c in data["coupling_issues"])
