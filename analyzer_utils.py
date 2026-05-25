#!/usr/bin/env python3
"""
Utilidades compartidas para el Android Gradle Dependency Analyzer.
"""

import re
import sys
import json
from pathlib import Path
from collections import defaultdict


def setup_utf8() -> None:
    if sys.platform == "win32":
        import os
        os.environ.setdefault("PYTHONUTF8", "1")
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except AttributeError:
            pass


# ─── Detección de módulos ──────────────────────────────────────────────────

_INCLUDE_RE = re.compile(r'["\'](:[\w:/-]+)["\']')


def _extract_includes(settings_path) -> list:
    content = Path(settings_path).read_text(encoding='utf-8')
    modules = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith(('//', '*', '/*')) or 'include' not in stripped:
            continue
        for match in _INCLUDE_RE.finditer(stripped):
            normalized = normalize_module_name(match.group(1).lstrip(':'))
            if normalized and normalized not in modules:
                modules.append(normalized)
    return modules


def parse_settings_modules(base_path) -> list | None:
    base = Path(base_path)
    for filename in ("settings.gradle.kts", "settings.gradle"):
        settings = base / filename
        if settings.exists():
            return _extract_includes(settings)
    return None


def list_modules(base_path) -> list:
    base = Path(base_path)

    from_settings = parse_settings_modules(base)
    if from_settings is not None:
        return from_settings

    modules = []
    for gradle_file in sorted(base.rglob("build.gradle*")):
        module_dir = gradle_file.parent
        try:
            rel_path    = module_dir.relative_to(base)
            module_name = normalize_module_name(str(rel_path))
            if module_name == ".":
                continue
            if module_name not in modules:
                modules.append(module_name)
        except ValueError:
            continue
    return modules


def normalize_module_name(path: str) -> str:
    return path.replace('/', ':').replace('\\', ':')


def find_gradle_file(module_path: Path) -> Path | None:
    for name in ("build.gradle.kts", "build.gradle"):
        p = module_path / name
        if p.exists():
            return p
    for pattern in ("*.gradle.kts", "*.gradle"):
        candidates = sorted(module_path.glob(pattern))
        if candidates:
            return candidates[0]
    return None


def is_submodule_of(module: str, parent: str) -> bool:
    """True si module es parent o un submódulo directo/anidado de parent."""
    return module == parent or module.startswith(parent + ':')


# ─── Patrones de dependencias ──────────────────────────────────────────────

def _build_patterns(scope: str) -> list:
    """Genera los tres patrones regex para un scope de dependencia dado."""
    return [
        # scope(project(":module"))  — Kotlin DSL
        rf'{scope}\s*\(\s*project\s*\(\s*["\']([^"\']+)["\']\s*\)\s*\)',
        # scope project(":module")  — Groovy
        rf'{scope}\s+project\s*\(\s*["\']([^"\']+)["\']\s*\)',
        # scope project(path: ':module')  — Groovy named param
        rf'{scope}\s+project\s*\(\s*path\s*:\s*["\']([^"\']+)["\']\s*\)',
    ]


DEPENDENCY_SCOPES = {
    scope: _build_patterns(scope)
    for scope in [
        'implementation',
        'api',
        'testImplementation',
        'androidTestImplementation',
        'kapt',
        'compileOnly',
        'runtimeOnly',
        'debugImplementation',
        'releaseImplementation',
        'annotationProcessor',
        'testRuntimeOnly',
    ]
}


# ─── Parsing de Gradle ─────────────────────────────────────────────────────

def parse_gradle_file_scoped(gradle_file, known_modules, self_module):
    """
    Parsea un archivo gradle y devuelve dependencias agrupadas por scope.

    Args:
        gradle_file: Path al archivo build.gradle / build.gradle.kts
        known_modules: lista de módulos válidos del proyecto
        self_module: nombre del módulo actual (para excluir auto-referencias)

    Returns:
        dict[str, set[str]]: {scope: {modulos_dependidos}}
    """
    result = defaultdict(set)

    try:
        with open(gradle_file, 'r', encoding='utf-8') as f:
            content = f.read()

        for scope, patterns in DEPENDENCY_SCOPES.items():
            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    project_path = match.group(1)

                    # Quitar el primer ":" si existe
                    if project_path.startswith(':'):
                        project_path = project_path[1:]

                    normalized_path = normalize_module_name(project_path)
                    for known_module in known_modules:
                        normalized_module = normalize_module_name(known_module)
                        if (
                            normalized_path == normalized_module or
                            normalized_module.endswith(':' + normalized_path) or
                            normalized_path.endswith(':' + normalized_module)
                        ):
                            if known_module != self_module:
                                result[scope].add(known_module)
                            break

    except Exception as e:
        print(f"  ⚠️  Error leyendo {gradle_file.name}: {e}")

    return result


# ─── Configuración JSON ────────────────────────────────────────────────────

_DEFAULTS = {
    "icons": {
        "common": "🔧",
        "shared": "🔧",
        "core": "🔧",
        "gateway": "🌐",
        "api": "🌐",
        "network": "🌐",
        "remote": "🌐",
        "home": "🏠",
        "main": "🏠",
        "hub": "🏠",
        "ui": "🎨",
        "presentation": "🎨",
        "view": "🎨",
        "screen": "🎨",
        "domain": "🧩",
        "usecase": "🧩",
        "data": "💾",
        "repository": "💾",
        "repo": "💾",
        "database": "🗄️",
        "db": "🗄️",
        "local": "🗄️",
        "test": "🧪",
    },
    "styles": {},
    "colors": {
        "common": "#FFF9C4",
        "gateway": "#E1F5FE",
        "hub": "#E8F5E9",
        "cycle": "#FFCDD2",
    },
    "scope_weights": {
        "api": "high",
        "implementation": "normal",
        "compileOnly": "build",
        "kapt": "build",
        "annotationProcessor": "build",
        "testImplementation": "test",
        "androidTestImplementation": "test",
        "testRuntimeOnly": "test",
        "debugImplementation": "debug",
        "releaseImplementation": "release",
        "runtimeOnly": "runtime",
    },
    "sanity_weights": {
        # Penalizaciones al score (base 100). Configurables por el usuario.
        # No son un estándar externo — son defaults razonables que puedes ajustar.
        "cycle": 20,                  # -20 por cada ciclo detectado
        "sdp_violation": 10,          # -10 por cada violación SDP (estable → inestable)
        "unnecessary_api": 5,         # -5 por cada módulo con `api` pero Ca=0
        "high_fan_out_threshold": 5,  # Ce > este valor se considera fan-out excesivo
        "high_fan_out_penalty": 3,    # -3 por cada módulo con fan-out excesivo
        "hardcoded_version": 2,       # -2 por cada versión hardcodeada encontrada
        "sdp_threshold": 0.3,         # diferencia mínima de I para considerar violación SDP
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge recursivo: override sobreescribe base key a key."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_project_config(project_root) -> dict:
    """
    Carga el archivo analyzer.yml desde la raíz del proyecto analizado.

    Requiere pyyaml (opcional). Si no está instalado o el archivo no existe,
    devuelve un dict vacío sin emitir errores fatales.

    Args:
        project_root: ruta a la raíz del proyecto Android analizado

    Returns:
        dict con las secciones del yml (sanity, impact, analyzer, …) o {} si no aplica
    """
    config_file = Path(project_root) / "analyzer.yml"
    if not config_file.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(config_file.read_text(encoding='utf-8')) or {}
    except ImportError:
        return {}
    except Exception as e:
        print(f"  ⚠️  Error leyendo analyzer.yml: {e}")
        return {}


def load_config(config_path=None) -> dict:
    """
    Carga configuración desde un archivo JSON.

    Busca en orden:
    1. config_path explícito (via --config)
    2. analyzer_config.json en el directorio de trabajo actual (CWD)
    3. Defaults internos (genéricos para cualquier proyecto Android)

    No se auto-carga desde el directorio del script para que el archivo
    de ejemplo versionado (analyzer_config.example.json) sea realmente
    opt-in: el usuario debe copiarlo y renombrarlo para activarlo.
    """
    candidates = []

    if config_path:
        candidates.append(Path(config_path))

    candidates.append(Path.cwd() / "analyzer_config.json")

    for candidate in candidates:
        if candidate.exists():
            try:
                with open(candidate, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                return _deep_merge(_DEFAULTS, user_config)
            except Exception as e:
                print(f"  ⚠️  Error leyendo config {candidate}: {e}")

    return _deep_merge(_DEFAULTS, {})


# ─── Iconos y estilos ──────────────────────────────────────────────────────

def get_icon(module: str, config: dict) -> str:
    """Devuelve el emoji para un módulo según la configuración y heurísticas genéricas."""
    module_lower = module.split(':')[-1].lower()  # usar solo la última parte del path
    icons = config.get("icons", _DEFAULTS["icons"])

    for keyword, icon in icons.items():
        if keyword.lower() in module_lower:
            return icon

    return "📦"


def get_style(module: str, config: dict) -> str:
    """Devuelve el stereotype PlantUML para un módulo."""
    module_lower = module.split(':')[-1].lower()
    styles = config.get("styles", {})

    # Config del usuario primero
    for keyword, style in styles.items():
        if keyword.lower() in module_lower:
            return f' {style}'

    # Heurísticas genéricas
    if any(k in module_lower for k in ('common', 'core', 'shared')):
        return ' <<common>>'
    if any(k in module_lower for k in ('gateway', 'api', 'network', 'remote')):
        return ' <<gateway>>'
    if any(k in module_lower for k in ('home', 'main', 'hub')):
        return ' <<hub>>'

    return ''


# ─── Detección de ciclos ───────────────────────────────────────────────────

_WHITE = 0  # No visitado
_GRAY  = 1  # En el stack actual (back-edge si se encuentra)
_BLACK = 2  # Completamente procesado


def detect_cycles(dependencies: dict) -> list:
    """
    Detecta ciclos en el grafo de dependencias usando DFS con coloreo de nodos.

    Args:
        dependencies: dict[str, set[str]] o dict[str, dict[str, set[str]]]

    Returns:
        list[list[str]]: ciclos como caminos, ej. [['home', 'common', 'home']]
    """
    # Normalizar estructura anidada {scope: {modules}} → {module: set}
    flat_deps: dict = {}
    for module, deps in dependencies.items():
        if isinstance(deps, dict):
            all_deps: set = set()
            for scope_deps in deps.values():
                all_deps.update(scope_deps)
            flat_deps[module] = all_deps
        else:
            flat_deps[module] = set(deps)

    all_nodes: set = set(flat_deps.keys())
    for deps in flat_deps.values():
        all_nodes.update(deps)

    color  = {node: _WHITE for node in all_nodes}
    parent: dict = {}
    cycles: list = []

    for start in sorted(all_nodes):
        if color[start] != _WHITE:
            continue
        stack = [(start, False)]
        while stack:
            u, returning = stack.pop()
            if returning:
                color[u] = _BLACK
                continue
            if color[u] == _GRAY:
                continue
            color[u] = _GRAY
            stack.append((u, True))
            for v in sorted(flat_deps.get(u, ())):
                cv = color[v]
                if cv == _GRAY:
                    cycles.append(_reconstruct_cycle(parent, u, v))
                elif cv == _WHITE:
                    parent[v] = u
                    stack.append((v, False))

    return cycles


def _reconstruct_cycle(parent: dict, from_node: str, to_node: str) -> list:
    """
    Reconstruye el camino de un ciclo.

    from_node: nodo donde se detectó el back-edge (u)
    to_node:   nodo ancestro al que apunta el back-edge (v)
    Resultado: [to_node, ..., from_node, to_node]
    """
    cycle = [from_node]
    current = from_node
    seen = {from_node}

    while current != to_node:
        if current not in parent:
            break  # seguridad
        current = parent[current]
        if current in seen:
            break  # seguridad contra bucle infinito
        seen.add(current)
        cycle.append(current)

    cycle.reverse()
    cycle.append(to_node)
    return cycle
