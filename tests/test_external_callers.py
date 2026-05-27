"""
Tests para ExternalCallersAnalyzer:
  - scan_all_modules: clasifica correctamente internos vs externos (bug 2)
  - analyze_external_calls: detecta las llamadas externas reales
"""

import pytest
from pathlib import Path

from external_callers import ExternalCallersAnalyzer

FIXTURES = Path(__file__).parent / "fixtures"


class TestExternalCallersAnalyzer:

    @pytest.fixture
    def scanned(self):
        """Analyzer con scan_all_modules() ya ejecutado."""
        analyzer = ExternalCallersAnalyzer(
            project_root=str(FIXTURES / "external"),
            target_module="payments",
        )
        analyzer.scan_all_modules()
        return analyzer

    def test_internal_modules_exact_match(self, scanned):
        """
        Bug 2: solo 'payments' y 'payments:gateway' son internos.
        'payments-extra' NO debe clasificarse como interno.
        """
        assert "payments" in scanned.internal_modules
        assert "payments:gateway" in scanned.internal_modules

    def test_no_false_internal_from_prefix(self, scanned):
        """
        Bug 2: 'payments-extra' tiene nombre que empieza con 'payments'
        pero NO es un submódulo — debe quedar como externo.
        """
        assert "payments-extra" not in scanned.internal_modules

    def test_app_is_external(self, scanned):
        """'app' es un módulo externo — no debe estar en internal_modules."""
        assert "app" not in scanned.internal_modules

    def test_detects_external_call(self, scanned):
        """app llama a payments:gateway — debe aparecer en external_callers."""
        scanned.analyze_external_calls()

        assert "app" in scanned.external_callers
        assert "payments:gateway" in scanned.external_callers["app"]

    def test_payments_extra_generates_no_call(self, scanned):
        """payments-extra no tiene deps a payments — no debe aparecer en external_callers."""
        scanned.analyze_external_calls()

        assert "payments-extra" not in scanned.external_callers


class TestExternalCallersAmbiguousLeaf:
    """
    Cubre el bug del endswith: un módulo raíz :common que coexiste con
    un submódulo :target:common confunde al matcher heurístico anterior.
    """

    @pytest.fixture
    def analyzer(self):
        a = ExternalCallersAnalyzer(
            project_root=str(FIXTURES / "external_ambiguous"),
            target_module="target",
        )
        a.scan_all_modules()
        a.analyze_external_calls()
        return a

    def test_root_common_not_a_caller_of_target_common(self, analyzer):
        """
        caller declara project(':common') (raíz) y project(':target:common').
        SOLO la segunda debe contar como llamada externa.
        """
        callers = analyzer.external_callers.get("caller", {})
        assert "target:common" in callers
        # El bug previo agregaba target:common doble vía endswith desde :common.
        # Verificamos que el scope tenga exactamente el match correcto.
        assert callers["target:common"] == {"implementation"}

    def test_accessor_caller_detected(self, analyzer):
        """caller-using-accessor usa projects.target.common — debe verse igual."""
        callers = analyzer.external_callers.get("caller-using-accessor", {})
        assert "target:common" in callers

    def test_common_root_is_external_not_internal(self, analyzer):
        """:common (raíz) no es submódulo de target — debe ser externo."""
        assert "common" not in analyzer.internal_modules
