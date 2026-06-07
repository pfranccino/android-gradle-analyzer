#!/usr/bin/env python3
"""
Motores de extracción de dependencias entre módulos.

Dos implementaciones detrás de una misma interfaz (`resolve`):

  - StaticEngine  · lee los `build.gradle(.kts)` con regex/tree-sitter
    (`parse_gradle_file_scoped`). Funciona sobre cualquier carpeta, al instante,
    sin toolchain, y es seguro (solo lee texto). Es el comportamiento histórico.

  - DynamicEngine · ejecuta `gradlew -I <init script>` y lee la verdad que Gradle
    resuelve del modelo de proyecto. Precisión total: soporta Version Catalogs,
    variables, accessors type-safe y convention plugins sin parsear texto. A
    cambio requiere un build que configure y **ejecuta código del proyecto**.

  - AutoEngine    · usa dynamic si hay wrapper de Gradle y la corrida tiene éxito;
    si no (o si falla), cae a static con una advertencia. Mismo patrón que el
    fallback tree-sitter↔regex que ya existe en analyzer_utils.

Contrato común:

    engine.resolve(project_root, modules, known_modules, on_progress=None)
        -> dict[str, dict[str, set[str]]]   # {módulo: {scope: {targets}}}

    - modules:       qué módulos incluir como filas del resultado.
    - known_modules: qué targets son válidos; se filtra a este conjunto y se
                     excluyen auto-referencias, igual que el motor estático.
    - on_progress:   callback opcional on_progress(hechos, total).

El DynamicEngine extrae **dependencias declaradas directas** por configuración
(no el grafo transitivo resuelto): es el equivalente fiel de lo que extrae el
parser estático, y evita el costo de resolver (red/compilación).
"""

from __future__ import annotations

import os
import json
import subprocess
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from analyzer_utils import (
    parse_gradle_file_scoped,
    find_gradle_file,
    find_project_root,
    normalize_module_name,
)


class EngineError(RuntimeError):
    """Falla del motor dinámico (Gradle ausente, build que no configura, etc.)."""


def _norm(path: str) -> str:
    """':payments:gateway' -> 'payments:gateway'; ':' / '' -> ''."""
    return normalize_module_name(path.lstrip(':'))


# ─── Motor estático ────────────────────────────────────────────────────────

class StaticEngine:
    name = "static"

    def resolve(self, project_root, modules, known_modules, on_progress=None):
        project_root = Path(project_root)
        known   = list(known_modules)
        modules = list(modules)
        total   = len(modules)

        def _parse_one(module):
            module_path = project_root / module.replace(':', '/')
            gradle_file = find_gradle_file(module_path)
            if gradle_file is None:
                return module, {}
            return module, parse_gradle_file_scoped(gradle_file, known, module)

        out: dict = {}
        done = 0
        with ThreadPoolExecutor() as executor:
            for module, scoped in executor.map(_parse_one, modules):
                done += 1
                if on_progress:
                    on_progress(done, total)
                if scoped:
                    cleaned = {scope: set(deps) for scope, deps in scoped.items() if deps}
                    if cleaned:
                        out[module] = cleaned
        return out


# ─── Motor dinámico (Gradle init script) ───────────────────────────────────

# Init script en Groovy (máxima compatibilidad entre versiones de Gradle).
# Recorre todos los proyectos y, por cada configuración, extrae las
# dependencias declaradas de tipo `project(...)` agrupadas por scope.
# Lee `.dependencies` (declaradas) — NO resuelve la configuración.
_INIT_SCRIPT = r"""
import org.gradle.api.artifacts.ProjectDependency
import groovy.json.JsonOutput

gradle.projectsEvaluated {
    def result = [:]
    rootProject.allprojects.each { project ->
        def byScope = [:]
        project.configurations.each { cfg ->
            try {
                cfg.dependencies.withType(ProjectDependency).each { dep ->
                    String path
                    try {
                        path = dep.path                       // Gradle 8.11+
                    } catch (Throwable ignored) {
                        path = dep.dependencyProject.path     // versiones previas
                    }
                    byScope.computeIfAbsent(cfg.name, { new LinkedHashSet() }).add(path)
                }
            } catch (Throwable ignored) {
                // configuración no inspeccionable: se ignora
            }
        }
        if (!byScope.isEmpty()) {
            def asLists = [:]
            byScope.each { scope, paths -> asLists[scope] = paths as List }
            result[project.path] = asLists
        }
    }
    def target = gradle.startParameter.projectProperties.get('analyzerOut')
    def jsonText = JsonOutput.toJson(result)
    if (target) {
        new File(target).text = jsonText
    } else {
        println jsonText
    }
}
"""


class DynamicEngine:
    name = "dynamic"

    def __init__(self, timeout=300, extra_args=None):
        self.timeout    = timeout
        self.extra_args = list(extra_args or [])

    @staticmethod
    def find_wrapper(root) -> Path | None:
        """Devuelve el path al wrapper de Gradle en `root`, o None si no existe."""
        root  = Path(root)
        names = ("gradlew.bat", "gradlew") if os.name == "nt" else ("gradlew",)
        for name in names:
            candidate = root / name
            if candidate.exists():
                return candidate
        return None

    def available(self, project_root) -> bool:
        return self.find_wrapper(find_project_root(project_root)) is not None

    def resolve(self, project_root, modules, known_modules, on_progress=None):
        raw       = self._run_gradle(project_root)
        norm      = self._normalize_raw(raw)
        known_set = {_norm(m) for m in known_modules}
        known_set.discard('')
        modules   = list(modules)
        total     = len(modules)

        out: dict = {}
        for i, module in enumerate(modules, 1):
            if on_progress:
                on_progress(i, total)
            by_scope = norm.get(module)
            if not by_scope:
                continue
            filtered: dict = {}
            for scope, targets in by_scope.items():
                keep = {t for t in targets if t in known_set and t != module}
                if keep:
                    filtered[scope] = keep
            if filtered:
                out[module] = filtered
        return out

    @staticmethod
    def _normalize_raw(raw: dict) -> dict:
        """Pasa los paths de Gradle (':a:b') a la convención interna ('a:b')."""
        norm: dict = {}
        for gpath, scopes in raw.items():
            module = _norm(gpath)
            if not module:
                continue
            by_scope: dict = {}
            for scope, targets in scopes.items():
                deps = {_norm(t) for t in targets}
                deps.discard('')
                if deps:
                    by_scope[scope] = deps
            norm[module] = by_scope
        return norm

    def _run_gradle(self, project_root) -> dict:
        root    = find_project_root(project_root)
        wrapper = self.find_wrapper(root)
        if wrapper is None:
            raise EngineError(
                f"No se encontró el wrapper de Gradle (gradlew) en {root}. "
                f"El motor dinámico requiere el wrapper en la raíz del proyecto."
            )

        with tempfile.TemporaryDirectory(prefix="aga-dyn-") as tmp:
            init_script = Path(tmp) / "analyzer-init.gradle"
            out_file    = Path(tmp) / "deps.json"
            init_script.write_text(_INIT_SCRIPT, encoding="utf-8")

            cmd = [
                str(wrapper),
                "-I", str(init_script),
                f"-PanalyzerOut={out_file}",
                "--console=plain",
                "-q",
                *self.extra_args,
                "help",
            ]

            try:
                proc = subprocess.run(
                    cmd, cwd=str(root),
                    capture_output=True, text=True, timeout=self.timeout,
                )
            except subprocess.TimeoutExpired as exc:
                raise EngineError(f"Gradle excedió el timeout de {self.timeout}s") from exc
            except OSError as exc:
                raise EngineError(f"No se pudo ejecutar Gradle: {exc}") from exc

            if proc.returncode != 0:
                tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-15:]
                raise EngineError(
                    f"Gradle falló (exit {proc.returncode}):\n" + "\n".join(tail)
                )

            if not out_file.exists():
                raise EngineError(
                    "El init script no generó salida (¿proyecto sin subproyectos "
                    "o Gradle no llegó a projectsEvaluated?)."
                )

            try:
                return json.loads(out_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise EngineError(f"La salida de Gradle no es JSON válido: {exc}") from exc


# ─── Motor auto (dynamic con fallback) ─────────────────────────────────────

class AutoEngine:
    name = "auto"

    def __init__(self, timeout=300, extra_args=None, verbose=True):
        self._dynamic = DynamicEngine(timeout=timeout, extra_args=extra_args)
        self._static  = StaticEngine()
        self._vprint  = print if verbose else (lambda *a, **k: None)
        self.used     = None

    def resolve(self, project_root, modules, known_modules, on_progress=None):
        if self._dynamic.available(project_root):
            try:
                result = self._dynamic.resolve(project_root, modules, known_modules, on_progress)
                self.used = "dynamic"
                return result
            except EngineError as exc:
                self._vprint(f"  ⚠️  Motor dinámico falló, usando estático: {exc}")
        else:
            self._vprint("  ℹ️  Sin wrapper de Gradle; usando motor estático.")
        self.used = "static"
        return self._static.resolve(project_root, modules, known_modules, on_progress)


# ─── Factory ────────────────────────────────────────────────────────────────

def get_engine(name="static", *, timeout=300, extra_args=None, verbose=True):
    """Construye un motor por nombre: 'static' | 'dynamic' | 'auto'."""
    key = (name or "static").lower()
    if key == "static":
        return StaticEngine()
    if key == "dynamic":
        return DynamicEngine(timeout=timeout, extra_args=extra_args)
    if key == "auto":
        return AutoEngine(timeout=timeout, extra_args=extra_args, verbose=verbose)
    raise ValueError(f"Motor desconocido: {name!r} (usa 'static', 'dynamic' o 'auto')")


ENGINE_CHOICES = ("static", "dynamic", "auto")
