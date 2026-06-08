from pathlib import Path
from gradle_sanity import GradleSanityAnalyzer

FIXTURES = Path(__file__).parent / "fixtures"


class TestSanityFocusInContext:
    """Sanidad enfocada en un subárbol/módulo: Ca/Ce/I se miden en el contexto
    del proyecto COMPLETO (no aislando el subárbol). El reporte y el score se
    centran en el foco, pero las métricas son las reales del proyecto."""

    def _project(self, root: Path):
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

    def test_ca_counts_external_callers_when_focused(self, tmp_path):
        """grp:sub-a tiene Ca=2 (app + grp:sub-b) tanto en la raíz como enfocando
        en grp/ — el llamador externo `app` NO se pierde al enfocar el subárbol."""
        self._project(tmp_path)

        full = GradleSanityAnalyzer(base_path=str(tmp_path), verbose=False)
        full.analyze()

        sub = GradleSanityAnalyzer(base_path=str(tmp_path / "grp"), verbose=False)
        sub.analyze()

        assert sub.ca["grp:sub-a"] == full.ca["grp:sub-a"] == 2
        assert round(sub.instability["grp:sub-a"], 2) == 0.5
        # El reporte se centra en el subárbol
        assert set(sub.focus_modules) == {"grp:sub-a", "grp:sub-b"}
        assert sub.is_focused

    def test_explicit_focus_param(self, tmp_path):
        self._project(tmp_path)
        a = GradleSanityAnalyzer(base_path=str(tmp_path), focus=["grp:sub-a"], verbose=False)
        a.analyze()
        assert set(a.focus_modules) == {"grp:sub-a"}
        assert a.ca["grp:sub-a"] == 2          # contexto completo

    def test_report_focused_shows_only_focus_rows(self, tmp_path):
        self._project(tmp_path)
        a = GradleSanityAnalyzer(base_path=str(tmp_path / "grp"), verbose=False)
        a.analyze()
        report = a.generate_report()
        assert "grp:sub-a" in report
        assert "Foco" in report
        # 'app' está en el contexto pero NO debe ser una fila del reporte enfocado
        assert "\n  app " not in report


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
