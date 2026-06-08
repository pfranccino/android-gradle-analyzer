#!/usr/bin/env python3
import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict

from analyzer_utils import (
    compute_scope,
    load_config,
    load_project_config,
    get_icon,
    get_style,
    detect_cycles,
    setup_utf8,
)
from dependency_engine import get_engine, EngineError

_COMPILE_SCOPES = {'api', 'implementation', 'compileOnly'}
_BUILD_SCOPES   = {'kapt', 'annotationProcessor'}
_TEST_SCOPES    = {
    'testImplementation', 'androidTestImplementation',
    'debugImplementation', 'releaseImplementation',
    'runtimeOnly', 'testRuntimeOnly',
}

_DOT_COLORS = {
    'common':  '#FFF9C4',
    'gateway': '#E1F5FE',
    'hub':     '#E8F5E9',
    'cycle':   '#FFCDD2',
    'default': '#F5F5F5',
}


class GradleDependencyAnalyzer:
    def __init__(self, base_path, config_path=None, exclude=None, verbose=True,
                 engine="static", focus=None, depth=None):
        self.base_path     = Path(base_path).resolve()
        self.root          = self.base_path
        self.config        = load_config(config_path)
        self.exclude       = set(exclude or [])
        self._init_focus   = list(focus) if focus else None
        self.depth         = depth        # profundidad del árbol de internas (None = todas)
        self.modules       = []          # registry COMPLETO (nodos del grafo, contexto)
        self.known_modules = []
        self.focus_modules = []          # subconjunto a enfocar en la salida
        self.dependencies  = defaultdict(lambda: defaultdict(set))
        self.module_paths  = {}
        self._vprint       = print if verbose else (lambda *a, **k: None)
        self.engine_name   = engine
        self.engine        = get_engine(engine, verbose=verbose)

    def scan_modules(self):
        self._vprint(f"📁 Escaneando módulos en: {self.base_path}\n")

        if not self.base_path.exists():
            print("❌ Error: La ruta no existe")
            return self

        # El grafo se construye SIEMPRE sobre el proyecto completo (contexto),
        # con nombres canónicos relativos a la raíz. `focus` solo centra la
        # salida; no altera el cálculo (un módulo conserva su Ca real porque
        # sus llamadores —aunque vivan fuera del subárbol— siguen en el grafo).
        self.root, known, subtree = compute_scope(self.base_path)
        self.known_modules = list(known)
        self.modules       = [m for m in sorted(known) if m not in self.exclude]

        # Foco efectivo: explícito (param) si se pasó, si no el subárbol bajo base_path.
        focus_src = self._init_focus if self._init_focus is not None else subtree
        focus_set = set(focus_src)
        self.focus_modules = [m for m in self.modules if m in focus_set]

        for module_name in self.modules:
            self.module_paths[module_name] = Path(module_name.replace(':', '/'))
            self._vprint(f"  • {module_name}")

        if self.focus_modules and set(self.focus_modules) != set(self.modules):
            self._vprint(
                f"\n📡 Contexto: {len(self.modules)} módulos del proyecto"
                f" (raíz {self.root}) · foco: {len(self.focus_modules)}"
            )

        self._vprint(f"\n✓ {len(self.modules)} módulos encontrados\n")
        return self

    def _effective_focus(self, focus=None):
        """Devuelve la lista de módulos foco a usar en la salida, o None (=todos).

        Prioridad: foco explícito del llamador > foco por subárbol/param de la
        instancia. Si el foco abarca todo el proyecto, devuelve None (sin zoom)."""
        if focus:
            return list(focus) if isinstance(focus, (list, tuple, set)) else [focus]
        if self.focus_modules and set(self.focus_modules) != set(self.modules):
            return list(self.focus_modules)
        return None

    def analyze_gradle_dependencies(self, on_progress=None):
        self._vprint(f"🔍 Analizando dependencias (motor: {self.engine_name})...")

        resolved = self.engine.resolve(
            self.root, self.modules, self.known_modules, on_progress=on_progress,
        )

        for module in self.modules:
            scoped = resolved.get(module)
            if scoped:
                self.dependencies[module] = scoped
                n = sum(len(v) for v in scoped.values())
                self._vprint(f"  ✓ {module}: {n} dependencia(s)")
            else:
                self._vprint(f"  ○ {module}: sin dependencias internas")

        total_deps = sum(
            len(mods)
            for scopes in self.dependencies.values()
            for mods in scopes.values()
        )
        self._vprint(f"\n✓ Análisis completado: {total_deps} dependencias detectadas\n")
        return self

    def detect_dependency_cycles(self):
        return detect_cycles(self.dependencies)

    def _focused_modules(self, focus_list):
        """Clausura hacia abajo desde el foco: el módulo y lo que usa, recursivo,
        hasta `self.depth` saltos (None = sin límite). El módulo elegido es la raíz
        del árbol de dependencias internas.

        NO incluye llamadores: "quién me llama" es la función de Llamadas externas.
        Como el conjunto es cerrado bajo "depende de" (toda arista de un nodo de la
        vista cae dentro de la vista), la salida nunca arrastra módulos ajenos al foco
        (ej. enfocar un módulo no vuelca toda la lista de dependencias de `app`)."""
        roots    = [m for m in focus_list if m in self.modules]
        visited  = set(roots)
        frontier = list(roots)
        level    = 0
        while frontier and (self.depth is None or level < self.depth):
            nxt = []
            for m in frontier:
                for scope_deps in self.dependencies.get(m, {}).values():
                    for dep in scope_deps:
                        if dep not in visited:
                            visited.add(dep)
                            nxt.append(dep)
            frontier = nxt
            level += 1

        return [m for m in self.modules if m in visited]

    def _compile_deps(self, module):
        scoped = self.dependencies.get(module, {})
        result = set()
        for s in _COMPILE_SCOPES:
            result |= scoped.get(s, set())
        return result

    def _build_deps(self, module):
        scoped = self.dependencies.get(module, {})
        result = set()
        for s in _BUILD_SCOPES:
            result |= scoped.get(s, set())
        return result

    def _test_deps(self, module):
        scoped = self.dependencies.get(module, {})
        result = set()
        for s in _TEST_SCOPES:
            result |= scoped.get(s, set())
        return result

    def generate_plantuml(self, focus=None):
        eff_focus     = self._effective_focus(focus)
        modules       = self._focused_modules(eff_focus) if eff_focus else self.modules
        package_name  = self.base_path.name
        cycles        = self.detect_dependency_cycles()
        cycle_modules = {m for cycle in cycles for m in cycle}
        colors        = self.config.get("colors", {})

        lines = [
            "@startuml",
            "",
            "skinparam packageStyle rectangle",
            "skinparam linetype ortho",
            "skinparam backgroundColor white",
            f'skinparam classBackgroundColor<<common>>  {colors.get("common",  "#FFF9C4")}',
            f'skinparam classBackgroundColor<<gateway>> {colors.get("gateway", "#E1F5FE")}',
            f'skinparam classBackgroundColor<<hub>>     {colors.get("hub",     "#E8F5E9")}',
            f'skinparam classBackgroundColor<<cycle>>   {colors.get("cycle",   "#FFCDD2")}',
            "skinparam classBorderColor #757575",
            "",
            "skinparam nodesep 150",
            "skinparam ranksep 150",
            "skinparam padding 30",
            "",
            f'package "{package_name}" <<package>> {{',
            "",
        ]

        module_set = set(modules)
        for module in sorted(modules):
            module_id = module.replace('-', '_').replace(':', '_')
            style     = ' <<cycle>>' if module in cycle_modules else get_style(module, self.config)
            lines.append(f'  class "{module}" as {module_id}{style}')

        lines.append("")
        for from_module in sorted(modules):
            from_id      = from_module.replace('-', '_').replace(':', '_')
            compile_deps = self._compile_deps(from_module) & module_set
            build_deps   = self._build_deps(from_module) & module_set
            test_deps    = self._test_deps(from_module) & module_set

            for to_module in sorted(compile_deps):
                lines.append(f"  {from_id} --> {to_module.replace('-','_').replace(':','_')} : impl")
            for to_module in sorted(build_deps - compile_deps):
                lines.append(f"  {from_id} ..> {to_module.replace('-','_').replace(':','_')} : build")
            for to_module in sorted(test_deps - compile_deps - build_deps):
                lines.append(f"  {from_id} ..> {to_module.replace('-','_').replace(':','_')} : test")

        lines.extend(["", "}", "", "@enduml"])
        return "\n".join(lines)

    def generate_mermaid(self, focus=None):
        eff_focus     = self._effective_focus(focus)
        modules       = self._focused_modules(eff_focus) if eff_focus else self.modules
        package_name  = self.base_path.name
        pkg_id        = package_name.replace('-', '_')
        cycles        = self.detect_dependency_cycles()
        cycle_modules = {m for cycle in cycles for m in cycle}
        colors        = self.config.get("colors", {})

        lines = [
            "%%{init: {"
            "'flowchart': {"
            "'maxEdges': 10000, "
            "'htmlLabels': true, "
            "'curve': 'basis', "
            "'wrappingWidth': 200"
            "}, "
            "'maxTextSize': 200000"
            "}}%%",
            "graph TD",
            f'  subgraph {pkg_id}["📦 {package_name}"]',
            "",
        ]

        module_set = set(modules)
        for module in sorted(modules):
            module_id = module.replace('-', '_').replace(':', '_')
            icon      = get_icon(module, self.config)
            lines.append(f'    {module_id}["{icon} {module}"]')

        lines.append("")
        for from_module in sorted(modules):
            from_id      = from_module.replace('-', '_').replace(':', '_')
            compile_deps = self._compile_deps(from_module) & module_set
            build_deps   = self._build_deps(from_module) & module_set
            test_deps    = self._test_deps(from_module) & module_set

            for to_module in sorted(compile_deps):
                lines.append(f"    {from_id} --> {to_module.replace('-','_').replace(':','_')}")
            for to_module in sorted(build_deps - compile_deps):
                lines.append(f"    {from_id} -.->|build| {to_module.replace('-','_').replace(':','_')}")
            for to_module in sorted(test_deps - compile_deps - build_deps):
                lines.append(f"    {from_id} -.->|test| {to_module.replace('-','_').replace(':','_')}")

        lines.append("  end")
        lines.append("")

        lines.append(f'  classDef commonStyle  fill:{colors.get("common",  "#FFF9C4")},stroke:#F57F17,stroke-width:2px')
        lines.append(f'  classDef gatewayStyle fill:{colors.get("gateway", "#E1F5FE")},stroke:#0277BD,stroke-width:2px')
        lines.append(f'  classDef hubStyle     fill:{colors.get("hub",     "#E8F5E9")},stroke:#2E7D32,stroke-width:2px')
        lines.append(f'  classDef cycleStyle   fill:{colors.get("cycle",   "#FFCDD2")},stroke:#C62828,stroke-width:2px')
        lines.append("")

        def _ids(mods):
            return [m.replace('-', '_').replace(':', '_') for m in mods]

        commons   = _ids(m for m in modules if any(k in m.lower() for k in ('common', 'core', 'shared')))
        gateways  = _ids(m for m in modules if any(k in m.lower() for k in ('gateway', 'network', 'remote')) or m.endswith(':api'))
        hubs      = _ids(m for m in modules if any(k in m.lower() for k in ('home', 'main', 'hub')))
        cycle_ids = _ids(m for m in cycle_modules if m in module_set)

        if commons:
            lines.append(f"  class {','.join(commons)} commonStyle")
        if gateways:
            lines.append(f"  class {','.join(gateways)} gatewayStyle")
        if hubs:
            lines.append(f"  class {','.join(hubs)} hubStyle")
        if cycle_ids:
            lines.append(f"  class {','.join(cycle_ids)} cycleStyle")

        return "\n".join(lines)

    def generate_dot(self, focus=None):
        eff_focus     = self._effective_focus(focus)
        modules       = self._focused_modules(eff_focus) if eff_focus else self.modules
        package_name  = self.base_path.name
        cycles        = self.detect_dependency_cycles()
        cycle_modules = {m for cycle in cycles for m in cycle}
        colors        = self.config.get("colors", _DOT_COLORS)
        module_set    = set(modules)

        def _color(module):
            if module in cycle_modules:
                return colors.get("cycle", _DOT_COLORS["cycle"])
            ml = module.lower()
            if any(k in ml for k in ('common', 'core', 'shared')):
                return colors.get("common", _DOT_COLORS["common"])
            if any(k in ml for k in ('gateway', 'network', 'remote', 'api')):
                return colors.get("gateway", _DOT_COLORS["gateway"])
            if any(k in ml for k in ('home', 'main', 'hub')):
                return colors.get("hub", _DOT_COLORS["hub"])
            return _DOT_COLORS["default"]

        lines = [
            f'digraph "{package_name}" {{',
            '  rankdir=LR',
            '  bgcolor=white',
            '  node [shape=box fontname="Helvetica" style=filled fontsize=12]',
            '  edge [fontname="Helvetica" fontsize=10]',
            '',
        ]

        for module in sorted(modules):
            node_id = module.replace(':', '_').replace('-', '_')
            color   = _color(module)
            lines.append(f'  {node_id} [label="{module}" fillcolor="{color}"]')

        lines.append('')

        for from_module in sorted(modules):
            from_id      = from_module.replace(':', '_').replace('-', '_')
            compile_deps = self._compile_deps(from_module) & module_set
            build_deps   = self._build_deps(from_module) & module_set
            test_deps    = self._test_deps(from_module) & module_set

            for to in sorted(compile_deps):
                to_id = to.replace(':', '_').replace('-', '_')
                lines.append(f'  {from_id} -> {to_id} [label="impl" color="#555555"]')
            for to in sorted(build_deps - compile_deps):
                to_id = to.replace(':', '_').replace('-', '_')
                lines.append(f'  {from_id} -> {to_id} [label="build" style=dashed color="#888888"]')
            for to in sorted(test_deps - compile_deps - build_deps):
                to_id = to.replace(':', '_').replace('-', '_')
                lines.append(f'  {from_id} -> {to_id} [label="test" style=dashed color="#AAAAAA"]')

        lines.append('}')
        return "\n".join(lines)

    def generate_ascii(self, focus=None):
        """Árbol de dependencias internas enraizado en el foco (o un bosque desde
        los puntos de entrada si no hay foco). Recorre hacia abajo respetando
        `self.depth`. Un módulo ya expandido en otra rama se marca con `↩` y no se
        vuelve a desplegar (evita duplicar subárboles y cortar ciclos)."""
        eff_focus = self._effective_focus(focus)
        if eff_focus:
            view  = set(self._focused_modules(eff_focus))
            roots = [m for m in eff_focus if m in self.modules]
        else:
            view = set(self.modules)
            used = {
                dep
                for m in self.modules
                for deps in self.dependencies.get(m, {}).values()
                for dep in deps
            }
            roots = [m for m in self.modules if m not in used] or list(self.modules)

        known_set = set(self.known_modules) if self.known_modules else view
        name      = self.base_path.name
        width     = 70

        def children(node):
            agg = defaultdict(set)
            for scope, deps in self.dependencies.get(node, {}).items():
                for dep in deps:
                    if dep in view and dep in known_set:
                        agg[dep].add(scope)
            return [(dep, ", ".join(sorted(scopes))) for dep, scopes in sorted(agg.items())]

        lines = [
            "━" * width,
            f"DEPENDENCIAS — {name.upper()}",
            "━" * width,
            "",
        ]
        expanded = set()

        def walk(node, scope_label, prefix, is_last, level):
            connector = "└── " if is_last else "├── "
            icon      = get_icon(node, self.config)
            kids      = children(node)
            repeat    = node in expanded and bool(kids)
            label     = f"{icon} {node}  [{scope_label}]" + ("  ↩" if repeat else "")
            lines.append(f"{prefix}{connector}{label}")
            if not kids or repeat or (self.depth is not None and level >= self.depth):
                return
            expanded.add(node)
            child_prefix = prefix + ("    " if is_last else "│   ")
            for i, (dep, sl) in enumerate(kids):
                walk(dep, sl, child_prefix, i == len(kids) - 1, level + 1)

        for root in sorted(roots):
            icon = get_icon(root, self.config)
            lines.append(f"{icon} {root}")
            expanded.add(root)
            kids = children(root)
            if not kids:
                lines.append("  (sin dependencias internas)")
            elif self.depth is None or self.depth >= 1:
                for i, (dep, sl) in enumerate(kids):
                    walk(dep, sl, "", i == len(kids) - 1, 1)
            lines.append("")

        return "\n".join(lines)

    def generate_report(self, focus=None):
        eff            = self._effective_focus(focus)
        report_modules = self._focused_modules(eff) if eff else self.modules
        report_set     = set(report_modules)
        focus_set      = set(eff) if eff else report_set

        cycles = self.detect_dependency_cycles()
        if eff:
            cycles = [c for c in cycles if report_set.intersection(c)]

        total_deps = sum(
            len(mods)
            for m in report_modules
            for mods in self.dependencies.get(m, {}).values()
        )

        lines = [
            "=" * 70,
            "REPORTE DE DEPENDENCIAS - ANÁLISIS DESDE GRADLE",
            "=" * 70,
            f"\nRuta: {self.base_path}",
        ]
        if eff:
            lines.append(f"Foco: {', '.join(sorted(focus_set))}")
            lines.append(f"Módulos en vista (foco + vecinos): {len(report_modules)}"
                         f"  ·  proyecto completo: {len(self.modules)}")
        else:
            lines.append(f"Total de módulos: {len(self.modules)}")
        lines.append(f"Total de dependencias: {total_deps}")

        if cycles:
            lines.append("\n" + "=" * 70)
            lines.append(f"⚠️  CICLOS DETECTADOS ({len(cycles)})")
            lines.append("=" * 70)
            for i, cycle in enumerate(cycles, 1):
                lines.append(f"  Ciclo {i}: {' → '.join(cycle)}")

        lines.append("\n" + "=" * 70)
        lines.append("DEPENDENCIAS POR MÓDULO")
        lines.append("=" * 70)

        for module in sorted(report_modules):
            scoped = self.dependencies.get(module, {})
            marca  = "  ◀ foco" if (eff and module in focus_set) else ""
            lines.append(f"\n📦 {module}{marca}")
            if scoped:
                for scope in sorted(scoped.keys()):
                    for dep in sorted(scoped[scope]):
                        lines.append(f"  → {dep}  [{scope}]")
            else:
                lines.append("  (sin dependencias internas)")

        lines.append("\n" + "=" * 70)
        lines.append("ESTADÍSTICAS")
        lines.append("=" * 70)

        # Conteo de uso dentro de la vista (foco + vecinos).
        usage_count: dict = defaultdict(int)
        for m in report_modules:
            for deps in self.dependencies.get(m, {}).values():
                for dep in deps:
                    if dep in report_set:
                        usage_count[dep] += 1

        if usage_count:
            lines.append("\nMódulos más utilizados:")
            for module, count in sorted(usage_count.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"  • {module}: usado por {count} módulo(s)")

        no_deps = [m for m in report_modules if not self.dependencies.get(m)]
        if no_deps:
            lines.append(f"\nMódulos sin dependencias internas ({len(no_deps)}):")
            for module in sorted(no_deps):
                lines.append(f"  • {module}")

        unused = [m for m in report_modules if m not in usage_count]
        if unused:
            if eff:
                lines.append(
                    f"\nℹ️  Sin dependencias entrantes dentro de la vista ({len(unused)} módulo(s))."
                    "\n   Para ver quién del proyecto completo depende de estos, usá \"Llamadas externas\"."
                )
            else:
                lines.append(f"\nMódulos no utilizados por otros ({len(unused)}):")
                for module in sorted(unused):
                    lines.append(f"  • {module}")

        return "\n".join(lines)

    def to_json_dict(self, focus=None) -> dict:
        """Salida estructurada para skills/scripts. Respeta el foco y la profundidad:
        con foco, `modules` y `dependencies` son el árbol enraizado (clausura hacia
        abajo), igual que el reporte y el ASCII."""
        eff  = self._effective_focus(focus)
        view = set(self._focused_modules(eff)) if eff else set(self.modules)

        cycles = self.detect_dependency_cycles()
        if eff:
            cycles = [c for c in cycles if view.intersection(c)]

        deps_out: dict = {}
        for m in sorted(view):
            scoped = {}
            for scope, deps in self.dependencies.get(m, {}).items():
                kept = sorted(d for d in deps if d in view)
                if kept:
                    scoped[scope] = kept
            if scoped:
                deps_out[m] = scoped

        return {
            "schema_version": 1,
            "tool":    "internal",
            "path":    str(self.base_path),
            "root":    str(self.root),
            "focus":   list(eff) if eff else [],
            "depth":   self.depth,
            "modules": sorted(view),
            "dependencies": deps_out,
            "cycles":  cycles,
        }

    def save_all(self, output_dir="diagrams", fmt="all", focus=None):
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if fmt in ('plantuml', 'all'):
            p = output_path / "gradle-dependencies.puml"
            p.write_text(self.generate_plantuml(focus), encoding='utf-8')
            self._vprint(f"✓ PlantUML: {p}")

        if fmt in ('mermaid', 'all'):
            p = output_path / "gradle-dependencies.mmd"
            p.write_text(self.generate_mermaid(focus), encoding='utf-8')
            self._vprint(f"✓ Mermaid: {p}")

        if fmt in ('dot', 'all'):
            p = output_path / "gradle-dependencies.dot"
            p.write_text(self.generate_dot(focus), encoding='utf-8')
            self._vprint(f"✓ Graphviz DOT: {p}")

        if fmt in ('ascii', 'all'):
            p = output_path / "gradle-dependencies.txt"
            p.write_text(self.generate_ascii(focus), encoding='utf-8')
            self._vprint(f"✓ ASCII: {p}")

        if fmt in ('json', 'all'):
            p = output_path / "gradle-dependencies.json"
            p.write_text(json.dumps(self.to_json_dict(focus), indent=2, ensure_ascii=False),
                         encoding='utf-8')
            self._vprint(f"✓ JSON: {p}")

        p = output_path / "gradle-report.txt"
        p.write_text(self.generate_report(focus), encoding='utf-8')
        self._vprint(f"✓ Reporte: {p}")


def _depth_type(value):
    """Valida --depth: un entero >= 1 o 'all' (→ None, sin límite)."""
    if value == 'all':
        return None
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("--depth debe ser un entero >= 1 o 'all'")
    if n < 1:
        raise argparse.ArgumentTypeError("--depth debe ser >= 1")
    return n


def _build_analyzer(args):
    focus = [m.strip() for m in args.focus.split(',')] if getattr(args, 'focus', None) else None
    analyzer = GradleDependencyAnalyzer(
        base_path=args.path,
        config_path=args.config,
        exclude=args.exclude,
        verbose=not args.quiet,
        engine=args.engine,
        depth=getattr(args, 'depth', None),
    )
    analyzer.scan_modules()
    analyzer.analyze_gradle_dependencies()
    return analyzer, focus


def main():
    setup_utf8()
    parser = argparse.ArgumentParser(
        description='Analiza dependencias internas de módulos Android'
    )
    parser.add_argument('path')
    parser.add_argument('--format', choices=['plantuml', 'mermaid', 'dot', 'ascii', 'json', 'all'],
                        default=None, dest='fmt', metavar='FORMAT')
    parser.add_argument('--output-dir', default=None, dest='output_dir', metavar='DIR')
    parser.add_argument('--exclude', action='append', default=[], metavar='MODULE')
    parser.add_argument('--focus',   default=None, metavar='MODULE[,MODULE]',
                        help='Módulo(s) raíz del árbol de dependencias internas')
    parser.add_argument('--depth',   type=_depth_type, default=None, metavar='N|all',
                        help="Profundidad del árbol de internas: entero >= 1 o 'all' (default: all)")
    parser.add_argument('--config',  default=None, metavar='PATH')
    parser.add_argument('--engine',  choices=['static', 'dynamic', 'auto'], default=None,
                        help='Motor de extracción de dependencias (default: static)')
    parser.add_argument('--quiet',   action='store_true')
    parser.add_argument('--json',    action='store_true')

    args = parser.parse_args()

    proj_cfg = load_project_config(args.path).get('analyzer', {})
    if args.output_dir is None:
        args.output_dir = proj_cfg.get('output_dir', 'diagrams')
    if args.fmt is None:
        args.fmt = proj_cfg.get('format', 'all')
    if args.engine is None:
        args.engine = proj_cfg.get('engine', 'static')

    if not args.quiet:
        print("🚀 Analizador de Dependencias via Gradle")
        print("=" * 70)

    try:
        analyzer, focus = _build_analyzer(args)
    except EngineError as exc:
        print(f"\n❌ Motor '{args.engine}' falló: {exc}")
        sys.exit(1)

    if not args.quiet:
        print("\n📊 Generando archivos...")
        print("=" * 70)

    analyzer.save_all(output_dir=args.output_dir, fmt=args.fmt, focus=focus)

    if args.json:
        print(json.dumps(analyzer.to_json_dict(focus), indent=2, ensure_ascii=False))
    else:
        print("\n" + analyzer.generate_report(focus))
        if not args.quiet:
            print("\n" + "=" * 70)
            print("✅ ¡Análisis completado!")
            print("=" * 70)
            print("\n💡 Para visualizar:")
            print("  • PlantUML: https://www.plantuml.com/plantuml/uml/")
            print("  • Mermaid:  https://mermaid.live/")
            print("  • DOT:      dot -Tpng gradle-dependencies.dot -o deps.png")


def main_dot():
    sys.argv.insert(1, '--format')
    sys.argv.insert(2, 'dot')
    main()


def main_ascii():
    sys.argv.insert(1, '--format')
    sys.argv.insert(2, 'ascii')
    main()


if __name__ == "__main__":
    main()
