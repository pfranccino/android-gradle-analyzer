#!/usr/bin/env python3
"""
Utilidades compartidas para el Android Gradle Dependency Analyzer.
"""

import re
import json
from pathlib import Path
from collections import defaultdict


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

                    # Buscar coincidencia en módulos conocidos
                    for known_module in known_modules:
                        if (
                            project_path.endswith(known_module) or
                            known_module.endswith(project_path) or
                            project_path.replace(':', '/') == known_module.replace(':', '/')
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


def load_config(config_path=None) -> dict:
    """
    Carga configuración desde un archivo JSON.

    Busca en orden:
    1. config_path explícito (via --config)
    2. analyzer_config.json en el directorio de trabajo actual
    3. analyzer_config.json junto al script
    4. Defaults internos (genéricos para cualquier proyecto Android)
    """
    candidates = []

    if config_path:
        candidates.append(Path(config_path))

    candidates.extend([
        Path.cwd() / "analyzer_config.json",
        Path(__file__).parent / "analyzer_config.json",
    ])

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

    color = {node: _WHITE for node in all_nodes}
    parent: dict = {}
    cycles: list = []

    def dfs(u: str) -> None:
        color[u] = _GRAY
        for v in sorted(flat_deps.get(u, set())):
            if color.get(v, _WHITE) == _GRAY:
                cycles.append(_reconstruct_cycle(parent, u, v))
            elif color.get(v, _WHITE) == _WHITE:
                parent[v] = u
                dfs(v)
        color[u] = _BLACK

    for node in sorted(all_nodes):
        if color[node] == _WHITE:
            dfs(node)

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
