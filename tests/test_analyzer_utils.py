"""
Tests para analyzer_utils.py:
  - parse_gradle_file_scoped: regex Groovy, tree-sitter KTS y type-safe accessors
  - detect_cycles: detección de ciclos directos e indirectos
  - _preprocess_groovy: strip de comentarios y colapso multilínea
"""

import pytest
from pathlib import Path

from analyzer_utils import (
    parse_gradle_file_scoped,
    detect_cycles,
    parse_settings_modules,
    list_modules,
    module_to_accessor,
    build_accessor_map,
    _preprocess_groovy,
    _strip_comments,
    _extract_includes,
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


# ── _extract_includes: formatos multilínea Kotlin DSL y Groovy ────────────────

class TestExtractIncludesFormats:
    """Cobertura de los formatos reales de settings.gradle(.kts).

    Regresión del bug "no detecta nada": include() multilínea (Kotlin DSL)
    devolvía 0 módulos porque el parser iba línea por línea.
    """

    def _write(self, tmp_path, name, content):
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return p

    def test_kts_include_multilinea_trailing_comma(self, tmp_path):
        p = self._write(tmp_path, "settings.gradle.kts",
            'include(\n    ":app",\n    ":core:network",\n    ":feature:home",\n)\n')
        assert set(_extract_includes(p)) == {"app", "core:network", "feature:home"}

    def test_kts_include_multilinea_sin_trailing_comma(self, tmp_path):
        p = self._write(tmp_path, "settings.gradle.kts",
            'include(\n    ":app",\n    ":core:network"\n)\n')
        assert set(_extract_includes(p)) == {"app", "core:network"}

    def test_kts_varios_modulos_en_un_include(self, tmp_path):
        p = self._write(tmp_path, "settings.gradle.kts",
            'include(":app", ":core:network", ":feature:home")\n')
        assert set(_extract_includes(p)) == {"app", "core:network", "feature:home"}

    def test_kts_foreach_sobre_listof(self, tmp_path):
        p = self._write(tmp_path, "settings.gradle.kts",
            'listOf(\n    ":app",\n    ":core",\n).forEach { include(it) }\n')
        assert set(_extract_includes(p)) == {"app", "core"}

    def test_kts_bloque_comentado_no_cuenta(self, tmp_path):
        p = self._write(tmp_path, "settings.gradle.kts",
            'include(":app")\n/*\ninclude(":legacy")\n*/\ninclude(":core")\n')
        assert set(_extract_includes(p)) == {"app", "core"}

    def test_kts_variable_includedX_no_es_include(self, tmp_path):
        p = self._write(tmp_path, "settings.gradle.kts",
            'val includedFeatures = listOf("feature-a", "feature-b")\ninclude(":app")\n')
        assert set(_extract_includes(p)) == {"app"}

    def test_kts_crlf_y_tabs(self, tmp_path):
        p = self._write(tmp_path, "settings.gradle.kts",
            'include(\r\n\t":app",\r\n\t":core:network",\r\n)\r\n')
        assert set(_extract_includes(p)) == {"app", "core:network"}

    def test_kts_mezcla_single_y_multi(self, tmp_path):
        p = self._write(tmp_path, "settings.gradle.kts",
            'include(":app")\ninclude(\n    ":core:network",\n    ":core:database",\n)\n'
            'include(":feature:home", ":feature:profile")\n')
        assert set(_extract_includes(p)) == {
            "app", "core:network", "core:database", "feature:home", "feature:profile"}

    def test_groovy_lista_multilinea_trailing_comma(self, tmp_path):
        p = self._write(tmp_path, "settings.gradle",
            "include ':app',\n        ':core:network',\n        ':feature:home'\n")
        assert set(_extract_includes(p)) == {"app", "core:network", "feature:home"}

    def test_groovy_bloque_comentado_no_cuenta(self, tmp_path):
        p = self._write(tmp_path, "settings.gradle",
            "include ':app'\n/* include ':legacy'\n   include ':old' */\ninclude ':core'\n")
        assert set(_extract_includes(p)) == {"app", "core"}

    def test_groovy_semicolons_en_una_linea(self, tmp_path):
        p = self._write(tmp_path, "settings.gradle",
            "include ':app'; include ':core'; include ':feature:home'\n")
        assert set(_extract_includes(p)) == {"app", "core", "feature:home"}

    def test_settings_vacio_devuelve_none_para_fallback(self, tmp_path):
        """settings con solo rootProject.name → None para caer a rglob."""
        p = self._write(tmp_path, "settings.gradle.kts", 'rootProject.name = "demo"\n')
        assert parse_settings_modules(tmp_path) is None

    def test_groovy_include_parentesis_sin_colon_a_escala(self, tmp_path):
        """settings Groovy grande: pluginManagement + includeBuild + plugins,
        y decenas de include("modulo") con paréntesis, sin ':' inicial y con
        anidamiento profundo. (Nombres ficticios — estructura típica de monorepo)."""
        content = (
            'pluginManagement {\n'
            '    includeBuild("build-logic")\n'
            '    repositories {\n'
            '        google()\n'
            '        mavenCentral()\n'
            '        gradlePluginPortal()\n'
            '    }\n'
            '}\n'
            'plugins {\n'
            "    id 'org.example.toolchains.resolver' version '0.10.0'\n"
            '}\n'
            '\n'
            'include("app")\n'
            'include("app-shell")\n'
            'include("alpha:home")\n'
            'include("alpha:detail:data")\n'
            'include("alpha:detail:domain")\n'
            'include("alpha:detail:presentation")\n'
            'include("beta:gateway")\n'
            'include("beta:onboarding")\n'
            'include("payments:p2p")\n'
            'include("payments:transfers:domestic")\n'
            'include("platform:analytics:core")\n'
            'include("platform:analytics:firebase")\n'
            'include("platform:logger")\n'
            'include("shared:theme")\n'
            'include("shared:components:list-view")\n'
        )
        p = self._write(tmp_path, "settings.gradle", content)
        mods = _extract_includes(p)
        expected = {
            "app", "app-shell", "alpha:home",
            "alpha:detail:data", "alpha:detail:domain", "alpha:detail:presentation",
            "beta:gateway", "beta:onboarding",
            "payments:p2p", "payments:transfers:domestic",
            "platform:analytics:core", "platform:analytics:firebase", "platform:logger",
            "shared:theme", "shared:components:list-view",
        }
        assert set(mods) == expected
        assert "build-logic" not in mods          # includeBuild no es módulo
        assert "0.10.0" not in mods               # versión de plugin no es módulo
        assert len(mods) == len(set(mods))        # sin duplicados


# ── _preprocess_groovy / _strip_comments ──────────────────────────────────────

class TestPreprocessGroovy:

    def test_strips_line_comments(self):
        """Líneas con // no deben quedar en el output."""
        content   = "// implementation project(':core')\nimplementation project(':shared')"
        processed = _preprocess_groovy(content)
        assert ":core"   not in processed
        assert ":shared" in processed

    def test_strips_block_comments(self):
        """Bloques /* */ no deben quedar en el output."""
        content   = "/* implementation project(':core') */\nimplementation project(':shared')"
        processed = _preprocess_groovy(content)
        assert ":core"   not in processed
        assert ":shared" in processed

    def test_collapses_multiline_parens(self):
        """Dependencia multilínea dentro de () queda en una sola línea."""
        content   = "implementation(\n    project(':core')\n)"
        processed = _preprocess_groovy(content)
        assert "\n" not in processed.strip()
        assert ":core" in processed

    def test_multiline_groovy_dep_detected(self):
        """parse_gradle_file_scoped detecta deps multilínea en Groovy."""
        gradle_file = FIXTURES / "groovy_multiline" / "app" / "build.gradle"
        known  = ["app", "core", "shared", "ignored", "also-ignored"]
        result = parse_gradle_file_scoped(gradle_file, known, "app")

        assert "core"   in result.get("implementation", set())
        assert "shared" in result.get("api", set())

    def test_groovy_commented_deps_ignored(self):
        """Dependencias en comentarios Groovy no aparecen en el resultado."""
        gradle_file = FIXTURES / "groovy_multiline" / "app" / "build.gradle"
        known    = ["app", "core", "shared", "ignored", "also-ignored"]
        result   = parse_gradle_file_scoped(gradle_file, known, "app")
        all_deps = {dep for deps in result.values() for dep in deps}

        assert "ignored"      not in all_deps
        assert "also-ignored" not in all_deps

    def test_strip_comments_removes_block_and_line(self):
        content = "/* block */\ncode // line\nmore"
        out     = _strip_comments(content)
        assert "block" not in out
        assert "line"  not in out
        assert "code"  in out
        assert "more"  in out


# ── Tree-sitter KTS ───────────────────────────────────────────────────────────

class TestKtsTreeSitter:
    """
    Tests para el parser tree-sitter de archivos .gradle.kts.
    Se saltan automáticamente si tree-sitter-kotlin no está instalado.
    """

    def test_multiline_kts_implementation(self):
        """Tree-sitter detecta implementation multilínea en KTS."""
        pytest.importorskip("tree_sitter_kotlin")
        gradle_file = FIXTURES / "kts_multiline" / "app" / "build.gradle.kts"
        known  = ["app", "core", "shared"]
        result = parse_gradle_file_scoped(gradle_file, known, "app")

        assert "core" in result.get("implementation", set())

    def test_multiline_kts_api(self):
        """Tree-sitter detecta api multilínea anidada en KTS."""
        pytest.importorskip("tree_sitter_kotlin")
        gradle_file = FIXTURES / "kts_multiline" / "app" / "build.gradle.kts"
        known  = ["app", "core", "shared"]
        result = parse_gradle_file_scoped(gradle_file, known, "app")

        assert "shared" in result.get("api", set())

    def test_kts_line_comment_ignored(self):
        """Dependencias en // no aparecen con tree-sitter."""
        pytest.importorskip("tree_sitter_kotlin")
        gradle_file = FIXTURES / "kts_commented" / "app" / "build.gradle.kts"
        known    = ["app", "core", "shared", "network"]
        result   = parse_gradle_file_scoped(gradle_file, known, "app")
        all_deps = {dep for deps in result.values() for dep in deps}

        assert "core" not in all_deps

    def test_kts_block_comment_ignored(self):
        """Dependencias en /* */ no aparecen con tree-sitter."""
        pytest.importorskip("tree_sitter_kotlin")
        gradle_file = FIXTURES / "kts_commented" / "app" / "build.gradle.kts"
        known    = ["app", "core", "shared", "network"]
        result   = parse_gradle_file_scoped(gradle_file, known, "app")
        all_deps = {dep for deps in result.values() for dep in deps}

        assert "shared" not in all_deps

    def test_kts_real_dep_detected(self):
        """La única dep real (no comentada) sí aparece."""
        pytest.importorskip("tree_sitter_kotlin")
        gradle_file = FIXTURES / "kts_commented" / "app" / "build.gradle.kts"
        known  = ["app", "core", "shared", "network"]
        result = parse_gradle_file_scoped(gradle_file, known, "app")

        assert "network" in result.get("implementation", set())

    def test_kts_no_self_reference(self):
        """Tree-sitter no incluye el propio módulo como dependencia."""
        pytest.importorskip("tree_sitter_kotlin")
        gradle_file = FIXTURES / "kts_multiline" / "app" / "build.gradle.kts"
        known  = ["app", "core", "shared"]
        result = parse_gradle_file_scoped(gradle_file, known, "app")

        for deps in result.values():
            assert "app" not in deps

    def test_kts_exact_match_only(self):
        """Tree-sitter usa matching exacto — project(':core') no matchea 'payments:core'."""
        pytest.importorskip("tree_sitter_kotlin")
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            g = Path(tmp) / "build.gradle.kts"
            g.write_text('dependencies { implementation(project(":core")) }')
            known  = ["core", "payments:core"]
            result = parse_gradle_file_scoped(g, known, "caller")
            deps   = {d for v in result.values() for d in v}
            assert "core"          in deps
            assert "payments:core" not in deps


# ── KTS fallback regex (sin tree-sitter) ──────────────────────────────────────

class TestKtsRegexFallback:
    """
    Cubre el parsing de .gradle.kts cuando tree-sitter NO está disponible.
    Es el camino por defecto (tree-sitter es un extra opcional), así que estos
    tests fuerzan el fallback parchando _parse_kts_project_calls a None para
    correr siempre, independientemente de si tree-sitter está instalado.
    """

    @pytest.fixture(autouse=True)
    def _force_regex_fallback(self, monkeypatch):
        monkeypatch.setattr(
            "analyzer_utils._parse_kts_project_calls",
            lambda *a, **k: None,
        )

    def test_line_comment_ignored(self):
        """// implementation(project(':core')) no debe contar como dependencia."""
        gradle_file = FIXTURES / "kts_commented" / "app" / "build.gradle.kts"
        known    = ["app", "core", "shared", "network"]
        result   = parse_gradle_file_scoped(gradle_file, known, "app")
        all_deps = {dep for deps in result.values() for dep in deps}

        assert "core" not in all_deps

    def test_block_comment_ignored(self):
        """/* api(project(':shared')) */ no debe contar como dependencia."""
        gradle_file = FIXTURES / "kts_commented" / "app" / "build.gradle.kts"
        known    = ["app", "core", "shared", "network"]
        result   = parse_gradle_file_scoped(gradle_file, known, "app")
        all_deps = {dep for deps in result.values() for dep in deps}

        assert "shared" not in all_deps

    def test_real_dep_detected(self):
        """La única dep real (no comentada) sí aparece vía regex fallback."""
        gradle_file = FIXTURES / "kts_commented" / "app" / "build.gradle.kts"
        known  = ["app", "core", "shared", "network"]
        result = parse_gradle_file_scoped(gradle_file, known, "app")

        assert "network" in result.get("implementation", set())

    def test_commented_accessor_ignored(self):
        """// implementation(projects.target.secret) no debe contar (accessor comentado)."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            g = Path(tmp) / "build.gradle.kts"
            g.write_text(
                "dependencies {\n"
                "    implementation(projects.target.common)\n"
                "    // implementation(projects.target.secret)\n"
                "}\n"
            )
            known  = ["target:common", "target:secret"]
            result = parse_gradle_file_scoped(g, known, "caller")
            deps   = {d for v in result.values() for d in v}
            assert "target:common" in deps
            assert "target:secret" not in deps
