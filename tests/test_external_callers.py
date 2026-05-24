"""
Tests para ExternalCallersAnalyzer:
  - scan_all_modules: clasifica correctamente internos vs externos (bug 2)
  - analyze_external_calls: detecta las llamadas externas reales
"""

from pathlib import Path

from external_callers import ExternalCallersAnalyzer

FIXTURES = Path(__file__).parent / "fixtures"


class TestExternalCallersAnalyzer:

    def _build_analyzer(self):
        return ExternalCallersAnalyzer(
            project_root=str(FIXTURES / "external"),
            target_module="payments",
        )

    def test_internal_modules_exact_match(self):
        """
        Bug 2: solo 'payments' y 'payments:gateway' son internos.
        'payments-extra' NO debe clasificarse como interno.
        """
        analyzer = self._build_analyzer()
        analyzer.scan_all_modules()

        assert "payments" in analyzer.internal_modules
        assert "payments:gateway" in analyzer.internal_modules

    def test_no_false_internal_from_prefix(self):
        """
        Bug 2: 'payments-extra' tiene nombre que empieza con 'payments'
        pero NO es un submódulo — debe quedar como externo.
        """
        analyzer = self._build_analyzer()
        analyzer.scan_all_modules()

        assert "payments-extra" not in analyzer.internal_modules

    def test_app_is_external(self):
        """'app' es un módulo externo — no debe estar en internal_modules."""
        analyzer = self._build_analyzer()
        analyzer.scan_all_modules()

        assert "app" not in analyzer.internal_modules

    def test_detects_external_call(self):
        """app llama a payments:gateway — debe aparecer en external_callers."""
        analyzer = self._build_analyzer()
        analyzer.scan_all_modules()
        analyzer.analyze_external_calls()

        assert "app" in analyzer.external_callers
        assert "payments:gateway" in analyzer.external_callers["app"]

    def test_payments_extra_generates_no_call(self):
        """payments-extra no tiene deps a payments — no debe aparecer en external_callers."""
        analyzer = self._build_analyzer()
        analyzer.scan_all_modules()
        analyzer.analyze_external_calls()

        assert "payments-extra" not in analyzer.external_callers
