"""
Tests para analyzer_utils.py:
  - parse_gradle_file_scoped: verifica que no haya falsos positivos por endswith (bug 1)
  - detect_cycles: verifica detección correcta de ciclos directos e indirectos (bug 3)
"""

from pathlib import Path

from analyzer_utils import (
    parse_gradle_file_scoped,
    detect_cycles,
    parse_settings_modules,
    list_modules,
    module_to_accessor,
    build_accessor_map,
)

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

    def test_root_module_not_confused_with_nested(self):
        """
        Bug del endswith: project(':common') NO debe matchear el módulo
        anidado payments:common cuando ambos coexisten en known_modules.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            g = Path(tmp) / "build.gradle"
            g.write_text('dependencies { implementation project(":common") }')
            known  = ["common", "payments", "payments:common"]
            result = parse_gradle_file_scoped(g, known, "caller")
            deps   = {d for v in result.values() for d in v}
            assert "common" in deps
            assert "payments:common" not in deps

    def test_dep_unknown_to_known_modules_is_dropped(self):
        """
        Si el gradle refiere project(':foo') y 'foo' no está en known_modules,
        no se inventa una coincidencia heurística.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            g = Path(tmp) / "build.gradle"
            g.write_text('dependencies { implementation project(":foo") }')
            result = parse_gradle_file_scoped(g, ["app", "core"], "caller")
            deps   = {d for v in result.values() for d in v}
            assert deps == set()


# ── module_to_accessor ─────────────────────────────────────────────────────────

class TestModuleToAccessor:

    def test_simple_module(self):
        assert module_to_accessor(":app") == "app"
        assert module_to_accessor("app") == "app"

    def test_nested_module(self):
        assert module_to_accessor(":payments:common") == "payments.common"

    def test_kebab_case_becomes_camel(self):
        assert module_to_accessor(":feature:payments-common") == "feature.paymentsCommon"

    def test_snake_case_becomes_camel(self):
        assert module_to_accessor(":core:network_api") == "core.networkApi"

    def test_dot_separator_becomes_camel(self):
        assert module_to_accessor(":legacy:my.lib") == "legacy.myLib"

    def test_multiple_separators(self):
        assert module_to_accessor(":foo-bar-baz") == "fooBarBaz"

    def test_digits_preserved(self):
        assert module_to_accessor(":lib-1") == "lib1"

    def test_already_camel_unchanged(self):
        assert module_to_accessor(":fooBar") == "fooBar"


# ── build_accessor_map ─────────────────────────────────────────────────────────

class TestBuildAccessorMap:

    def test_round_trips_modules(self):
        modules = ["app", "feature:payments-common", "core:network_api"]
        m = build_accessor_map(modules)
        assert m["app"] == "app"
        assert m["feature.paymentsCommon"] == "feature:payments-common"
        assert m["core.networkApi"] == "core:network_api"

    def test_idempotent_on_same_module(self):
        """Listar el mismo módulo dos veces no es colisión real."""
        m = build_accessor_map(["app", "app"])
        assert m == {"app": "app"}

    def test_collision_logs_warning_and_first_wins(self, capsys):
        """:foo-bar y :fooBar mapean al mismo accessor; el segundo se descarta."""
        m = build_accessor_map(["foo-bar", "fooBar"])
        assert m["fooBar"] == "foo-bar"
        captured = capsys.readouterr()
        assert "colisiona" in captured.out


# ── parse_gradle_file_scoped: type-safe accessors ─────────────────────────────

class TestParseAccessors:

    def test_kotlin_dsl_accessor_resolved(self):
        """implementation(projects.feature.paymentsCommon) → feature:payments-common"""
        gradle_file = FIXTURES / "accessors" / "app" / "build.gradle.kts"
        known       = ["app", "feature:payments-common", "core:network_api", "legacy:plain-lib"]
        result      = parse_gradle_file_scoped(gradle_file, known, "app")

        assert "feature:payments-common" in result.get("implementation", set())
        assert "core:network_api"        in result.get("api", set())

    def test_classic_and_accessor_coexist_in_same_file(self):
        """El mismo archivo mezcla projects.foo.bar y project(':foo:bar') — ambos deben verse."""
        gradle_file = FIXTURES / "accessors" / "app" / "build.gradle.kts"
        known       = ["app", "feature:payments-common", "core:network_api", "legacy:plain-lib"]
        result      = parse_gradle_file_scoped(gradle_file, known, "app")

        deps = {d for v in result.values() for d in v}
        assert "legacy:plain-lib"        in deps   # formato clásico
        assert "feature:payments-common" in deps   # accessor

    def test_groovy_unparenthesized_accessor(self):
        """`implementation projects.foo.bar` (sin parens, sintaxis Groovy) también funciona."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            g = Path(tmp) / "build.gradle"
            g.write_text('dependencies {\n    implementation projects.feature.paymentsCommon\n}')
            known  = ["app", "feature:payments-common"]
            result = parse_gradle_file_scoped(g, known, "app")
            assert "feature:payments-common" in result.get("implementation", set())

    def test_accessor_to_unknown_module_is_dropped(self):
        """projects.foo.barBaz que no mapea a ningún módulo conocido se ignora."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            g = Path(tmp) / "build.gradle.kts"
            g.write_text('dependencies { implementation(projects.unknown.module) }')
            result = parse_gradle_file_scoped(g, ["app", "core"], "app")
            deps   = {d for v in result.values() for d in v}
            assert deps == set()


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


# ── parse_settings_modules ────────────────────────────────────────────────────

class TestParseSettingsModules:

    def test_returns_modules_from_settings(self):
        """Lee settings.gradle.kts y devuelve los módulos incluidos."""
        modules = parse_settings_modules(FIXTURES / "with_settings")
        assert modules is not None
        assert "app" in modules
        assert "core" in modules

    def test_returns_none_when_no_settings(self):
        """Sin settings.gradle* devuelve None para indicar fallback."""
        modules = parse_settings_modules(FIXTURES / "simple")
        assert modules is None

    def test_list_modules_uses_settings_when_present(self):
        """list_modules usa settings.gradle.kts si existe (no rglob)."""
        modules = list_modules(FIXTURES / "with_settings")
        assert set(modules) == {"app", "core"}

    def test_settings_excludes_root(self):
        """El módulo raíz '.' nunca debe aparecer en la lista."""
        modules = parse_settings_modules(FIXTURES / "with_settings")
        assert "." not in (modules or [])
        assert "" not in (modules or [])

    def test_detects_modules_without_leading_colon(self):
        """include("app") sin ':' inicial debe detectarse igual que include(":app")."""
        modules = parse_settings_modules(FIXTURES / "with_settings_no_colon")
        assert modules is not None
        assert "app" in modules
        assert "core" in modules
        assert "feature:home" in modules

    def test_includeBuild_not_counted_as_module(self):
        """includeBuild('build-logic') no debe contarse como módulo del proyecto."""
        modules = parse_settings_modules(FIXTURES / "with_settings_no_colon")
        assert modules is not None
        assert "build-logic" not in modules

    def test_classic_groovy_syntax_still_works(self):
        """Sintaxis Groovy clásica include ':app' sigue funcionando."""
        modules = parse_settings_modules(FIXTURES / "with_settings")
        assert modules is not None
        assert "app" in modules
