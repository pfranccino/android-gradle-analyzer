"""
Tests para analyzer_utils.py:
  - parse_gradle_file_scoped: verifica que no haya falsos positivos por endswith (bug 1)
  - detect_cycles: verifica detección correcta de ciclos directos e indirectos (bug 3)
"""

import pytest
from pathlib import Path

from analyzer_utils import parse_gradle_file_scoped, detect_cycles

FIXTURES = Path(__file__).parent / "fixtures"


# ── parse_gradle_file_scoped ──────────────────────────────────────────────────

class TestParseGradleFileScoped:

    def test_detects_simple_dependency(self):
        """app depende de core — debe matchear correctamente."""
        gradle_file  = FIXTURES / "simple" / "app" / "build.gradle"
        known        = ["app", "core"]
        result       = parse_gradle_file_scoped(gradle_file, known, "app")
        assert "core" in result.get("implementation", set())

    def test_no_self_reference(self):
        """No debe incluir el propio módulo como dependencia."""
        gradle_file = FIXTURES / "simple" / "app" / "build.gradle"
        known       = ["app", "core"]
        result      = parse_gradle_file_scoped(gradle_file, known, "app")
        for deps in result.values():
            assert "app" not in deps

    def test_no_false_positive_with_prefix_match(self):
        """
        Bug 1: project(":payments") no debe matchear 'quick-payments'.
        El fixture ambiguous/payments/build.gradle referencia :payments:common.
        quick-payments no debe aparecer en ninguna dependencia.
        """
        gradle_file   = FIXTURES / "ambiguous" / "payments" / "build.gradle"
        known_modules = ["payments", "payments:common", "quick-payments"]
        result        = parse_gradle_file_scoped(gradle_file, known_modules, "payments")

        all_deps = {dep for deps in result.values() for dep in deps}
        assert "quick-payments" not in all_deps, (
            "quick-payments no debe matchear la dependencia project(':payments:common')"
        )

    def test_nested_module_matched(self):
        """payments:common debe encontrarse al referenciar project(':payments:common')."""
        gradle_file   = FIXTURES / "ambiguous" / "payments" / "build.gradle"
        known_modules = ["payments", "payments:common", "quick-payments"]
        result        = parse_gradle_file_scoped(gradle_file, known_modules, "payments")

        all_deps = {dep for deps in result.values() for dep in deps}
        assert "payments:common" in all_deps

    def test_empty_gradle_returns_empty(self):
        """Un gradle sin dependencias internas devuelve dict vacío."""
        gradle_file = FIXTURES / "simple" / "core" / "build.gradle"
        known       = ["app", "core"]
        result      = parse_gradle_file_scoped(gradle_file, known, "core")
        assert all(len(v) == 0 for v in result.values())


# ── detect_cycles ──────────────────────────────────────────────────────────────

class TestDetectCycles:

    def test_detects_direct_cycle(self):
        """a → b → a debe detectarse como ciclo."""
        deps = {
            "a": {"implementation": {"b"}},
            "b": {"implementation": {"a"}},
        }
        cycles = detect_cycles(deps)
        assert len(cycles) >= 1, "Debe detectar al menos un ciclo directo"

        # Al menos un ciclo debe contener tanto 'a' como 'b'
        nodes_in_cycles = {node for cycle in cycles for node in cycle}
        assert "a" in nodes_in_cycles
        assert "b" in nodes_in_cycles

    def test_detects_indirect_cycle(self):
        """a → b → c → a debe detectarse como ciclo."""
        deps = {
            "a": {"implementation": {"b"}},
            "b": {"implementation": {"c"}},
            "c": {"implementation": {"a"}},
        }
        cycles = detect_cycles(deps)
        assert len(cycles) >= 1

    def test_no_cycle_in_linear_chain(self):
        """a → b → c sin vuelta no debe producir ciclos."""
        deps = {
            "a": {"implementation": {"b"}},
            "b": {"implementation": {"c"}},
            "c": {},
        }
        cycles = detect_cycles(deps)
        assert cycles == []

    def test_no_cycle_in_empty_deps(self):
        """Sin dependencias no hay ciclos."""
        assert detect_cycles({}) == []

    def test_fixture_cycle(self):
        """Usa los fixtures de ciclo reales (a/build.gradle, b/build.gradle)."""
        from gradle_analyzer import GradleDependencyAnalyzer

        analyzer = GradleDependencyAnalyzer(base_path=str(FIXTURES / "cycle"))
        analyzer.scan_modules()
        analyzer.analyze_gradle_dependencies()

        cycles = analyzer.detect_dependency_cycles()
        assert len(cycles) >= 1
