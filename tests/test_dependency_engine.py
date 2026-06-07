"""
Tests para dependency_engine.py:
  - StaticEngine:  paridad con el comportamiento histórico (parse por archivo).
  - DynamicEngine: normalización del JSON de Gradle, filtrado a known/self,
                   detección del wrapper y error claro sin gradlew.
  - AutoEngine:    fallback a static (sin wrapper o ante EngineError).
  - get_engine:    factory y validación de nombre.
"""

import pytest
from pathlib import Path

from dependency_engine import (
    StaticEngine,
    DynamicEngine,
    AutoEngine,
    EngineError,
    get_engine,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ── StaticEngine ──────────────────────────────────────────────────────────────

class TestStaticEngine:

    def test_resolve_external_ambiguous(self):
        """caller declara project(':common') y project(':target:common');
        con known=internos solo cuenta target:common (paridad con el flujo real)."""
        engine = StaticEngine()
        result = engine.resolve(
            FIXTURES / "external_ambiguous",
            modules=["caller", "caller-using-accessor"],
            known_modules=["target", "target:common"],
        )
        assert result["caller"]["implementation"] == {"target:common"}
        assert result["caller-using-accessor"]["implementation"] == {"target:common"}

    def test_resolve_excludes_self_and_unknown(self):
        """Un módulo sin gradle o sin deps internas no aparece como fila."""
        engine = StaticEngine()
        result = engine.resolve(
            FIXTURES / "external_ambiguous",
            modules=["common"],            # :common raíz, sin deps a known
            known_modules=["target", "target:common"],
        )
        assert "common" not in result

    def test_on_progress_called(self):
        seen = []
        StaticEngine().resolve(
            FIXTURES / "external_ambiguous",
            modules=["caller", "caller-using-accessor"],
            known_modules=["target:common"],
            on_progress=lambda done, total: seen.append((done, total)),
        )
        assert seen[-1] == (2, 2)


# ── DynamicEngine: normalización y filtrado del JSON ──────────────────────────

class TestDynamicEngineMapping:

    @pytest.fixture
    def raw(self):
        # Lo que devolvería el init script de Gradle (paths con ':' inicial).
        return {
            ":app": {
                "implementation": [":payments:gateway", ":legacy"],  # legacy no está en known
                "testImplementation": [":app"],                      # auto-referencia
            },
            ":payments:gateway": {"api": [":core"]},
            ":": {"implementation": [":app"]},                       # root → se descarta
        }

    def _engine_with(self, raw):
        eng = DynamicEngine()
        eng._run_gradle = lambda project_root: raw   # evita ejecutar Gradle
        return eng

    def test_normalizes_strips_leading_colon(self, raw):
        result = self._engine_with(raw).resolve(
            ".", modules=["app", "payments:gateway"],
            known_modules=["app", "payments:gateway", "core"],
        )
        assert result["payments:gateway"]["api"] == {"core"}

    def test_filters_unknown_targets(self, raw):
        result = self._engine_with(raw).resolve(
            ".", modules=["app"],
            known_modules=["app", "payments:gateway", "core"],
        )
        # legacy no está en known → se filtra
        assert result["app"]["implementation"] == {"payments:gateway"}

    def test_excludes_self_reference(self, raw):
        result = self._engine_with(raw).resolve(
            ".", modules=["app"],
            known_modules=["app", "payments:gateway", "core"],
        )
        # testImplementation(:app) sobre el módulo app → excluido (queda sin ese scope)
        assert "testImplementation" not in result.get("app", {})

    def test_root_project_skipped(self, raw):
        result = self._engine_with(raw).resolve(
            ".", modules=["app", "payments:gateway"],
            known_modules=["app", "payments:gateway", "core"],
        )
        assert "" not in result


# ── DynamicEngine: wrapper y errores ──────────────────────────────────────────

class TestDynamicEngineWrapper:

    def test_find_wrapper_present(self, tmp_path):
        (tmp_path / "settings.gradle").write_text("rootProject.name='x'")
        (tmp_path / "gradlew").write_text("#!/bin/sh\n")
        assert DynamicEngine.find_wrapper(tmp_path) is not None

    def test_find_wrapper_absent(self, tmp_path):
        assert DynamicEngine.find_wrapper(tmp_path) is None

    def test_resolve_without_wrapper_raises(self):
        """Sin gradlew, el motor dinámico falla con EngineError (no crash)."""
        engine = DynamicEngine()
        with pytest.raises(EngineError):
            engine.resolve(
                FIXTURES / "external_ambiguous",
                modules=["caller"],
                known_modules=["target:common"],
            )


# ── AutoEngine: fallback ──────────────────────────────────────────────────────

class TestAutoEngine:

    def test_fallback_to_static_without_wrapper(self):
        """Sin wrapper de Gradle, auto usa el motor estático y reporta used='static'."""
        engine = AutoEngine(verbose=False)
        result = engine.resolve(
            FIXTURES / "external_ambiguous",
            modules=["caller"],
            known_modules=["target", "target:common"],
        )
        assert engine.used == "static"
        assert result["caller"]["implementation"] == {"target:common"}

    def test_fallback_on_engine_error(self, monkeypatch):
        """Si el motor dinámico está disponible pero falla, auto cae a estático."""
        engine = AutoEngine(verbose=False)
        monkeypatch.setattr(engine._dynamic, "available", lambda pr: True)

        def _boom(*a, **k):
            raise EngineError("build no configura")
        monkeypatch.setattr(engine._dynamic, "resolve", _boom)

        result = engine.resolve(
            FIXTURES / "external_ambiguous",
            modules=["caller"],
            known_modules=["target", "target:common"],
        )
        assert engine.used == "static"
        assert result["caller"]["implementation"] == {"target:common"}


# ── Factory ───────────────────────────────────────────────────────────────────

class TestGetEngine:

    @pytest.mark.parametrize("name,cls", [
        ("static",  StaticEngine),
        ("dynamic", DynamicEngine),
        ("auto",    AutoEngine),
        ("STATIC",  StaticEngine),   # case-insensitive
    ])
    def test_known_engines(self, name, cls):
        assert isinstance(get_engine(name), cls)

    def test_default_is_static(self):
        assert isinstance(get_engine(), StaticEngine)

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            get_engine("turbo")
