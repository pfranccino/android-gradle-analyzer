#!/usr/bin/env python3
import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from analyzer_utils import (
    parse_gradle_file_scoped,
    parse_settings_modules,
    load_config,
    load_project_config,
    get_icon,
    get_style,
    detect_cycles,
    find_gradle_file,
    normalize_module_name,
    setup_utf8,
)

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
    def __init__(self, base_path, config_path=None, exclude=None, verbose=True):
        self.base_path    = Path(base_path).resolve()
        self.config       = load_config(config_path)
        self.exclude      = set(exclude or [])
        self.modules      = []
        self.dependencies = defaultdict(lambda: defaultdict(set))
        self.module_paths = {}
        self._vprint      = print if verbose else (lambda *a, **k: None)

    def scan_modules(self):
        self._vprint(f"📁 Escaneando módulos en: {self.base_path}\n")

        if not self.base_path.exists():
            print("❌ Error: La ruta no existe")
            return self

        from_settings = parse_settings_modules(self.base_path)

        if from_settings is not None:
            for module_name in sorted(from_settings):
                if module_name in self.exclude:
                    self._vprint(f"  ⊘ {module_name} (excluido)")
                    continue
                self.modules.append(module_name)
                self.module_paths[module_name] = Path(module_name.replace(':', '/'))
                self._vprint(f"  • {module_name}")
        else:
            for gradle_file in sorted(self.base_path.rglob("build.gradle*")):
                module_dir = gradle_file.parent
                try:
                    rel_path    = module_dir.relative_to(self.base_path)
                    module_name = str(rel_path).replace('/', ':').replace('\\', ':')
                    if module_name == '.':
                        continue
                    if module_name in self.exclude:
                        self._vprint(f"  ⊘ {module_name} (excluido)")
                        continue
                    self.modules.append(module_name)
                    self.module_paths[module_name] = rel_path
                    self._vprint(f"  • {module_name}")
                except ValueError:
                    continue

        self._vprint(f"\n✓ {len(self.modules)} módulos encontrados\n")
        return self

    def analyze_gradle_dependencies(self):
        self._vprint("🔍 Analizando archivos Gradle...")

        modules   = self.modules
        base_path = self.base_path

        def _parse_one(module):
            module_path = base_path / module.replace(':', '/')
            gradle_file = find_gradle_file(module_path)
            if gradle_file is None:
                return module, None
            return module, parse_gradle_file_scoped(gradle_file, modules, module)

        with ThreadPoolExecutor() as executor:
            for module, scoped in executor.map(_parse_one, modules):
                if scoped is None:
                    self._vprint(f"  ⚠️  No se encontró gradle para: {module}")
                elif scoped:
                    self.dependencies[module] = scoped
                    total = sum(len(v) for v in scoped.values())
                    self._vprint(f"  ✓ {module}: {total} dependencia(s)")
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
        visited = set()
        queue   = [m for m in focus_list if m in self.modules]
        while queue:
            m = queue.pop()
            if m in visited:
                continue
            visited.add(m)
            for scope_deps in self.dependencies.get(m, {}).values():
                for dep in scope_deps:
                    if dep not in visited:
                        queue.append(dep)
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
        modules       = self._focused_modules(focus) if focus else self.modules
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
                lines.append(f"  {from_id} --> {to_module.replace('-','_').replace(':','_')} : uses")
            for to_module in sorted(build_deps - compile_deps):
                lines.append(f"  {from_id} ..> {to_module.replace('-','_').replace(':','_')} : build")
            for to_module in sorted(test_deps - compile_deps - build_deps):
                lines.append(f"  {from_id} ..> {to_module.replace('-','_').replace(':','_')} : test")

        lines.extend(["", "}", "", "@enduml"])
        return "\n".join(lines)

    def generate_mermaid(self, focus=None):
        modules       = self._focused_modules(focus) if focus else self.modules
        package_name  = self.base_path.name
        pkg_id        = package_name.replace('-', '_')
        cycles        = self.detect_dependency_cycles()
        cycle_modules = {m for cycle in cycles for m in cycle}
        colors        = self.config.get("colors", {})

        lines = [
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
                lines.append(f"    {from_id} -->|uses| {to_module.replace('-','_').replace(':','_')}")
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
        modules       = self._focused_modules(focus) if focus else self.modules
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
        modules    = self._focused_modules(focus) if focus else self.modules
        module_set = set(modules)
        name       = self.base_path.name
        width      = 70

        lines = [
            "━" * width,
            f"DEPENDENCIAS — {name.upper()}",
            "━" * width,
            "",
        ]

        for module in sorted(modules):
            scoped = self.dependencies.get(module, {})
            all_deps = [
                (dep, scope)
                for scope, deps in sorted(scoped.items())
                for dep in sorted(deps)
                if dep in module_set
            ]

            icon = get_icon(module, self.config)
            lines.append(f"{icon} {module}")

            if not all_deps:
                lines.append("  (sin dependencias internas)")
            else:
                for i, (dep, scope) in enumerate(all_deps):
                    connector = "└──" if i == len(all_deps) - 1 else "├──"
                    dep_icon  = get_icon(dep, self.config)
                    lines.append(f"  {connector} {dep_icon} {dep}  [{scope}]")

            lines.append("")

        return "\n".join(lines)

    def generate_report(self):
        cycles = self.detect_dependency_cycles()
        total_deps = sum(
            len(mods)
            for scopes in self.dependencies.values()
            for mods in scopes.values()
        )

        lines = [
            "=" * 70,
            "REPORTE DE DEPENDENCIAS - ANÁLISIS DESDE GRADLE",
            "=" * 70,
            f"\nRuta: {self.base_path}",
            f"Total de módulos: {len(self.modules)}",
            f"Total de dependencias: {total_deps}",
        ]

        if cycles:
            lines.append("\n" + "=" * 70)
            lines.append(f"⚠️  CICLOS DETECTADOS ({len(cycles)})")
            lines.append("=" * 70)
            for i, cycle in enumerate(cycles, 1):
                lines.append(f"  Ciclo {i}: {' → '.join(cycle)}")

        lines.append("\n" + "=" * 70)
        lines.append("DEPENDENCIAS POR MÓDULO")
        lines.append("=" * 70)

        for module in sorted(self.modules):
            scoped = self.dependencies.get(module, {})
            lines.append(f"\n📦 {module}")
            if scoped:
                for scope in sorted(scoped.keys()):
                    for dep in sorted(scoped[scope]):
                        lines.append(f"  → {dep}  [{scope}]")
            else:
                lines.append("  (sin dependencias internas)")

        lines.append("\n" + "=" * 70)
        lines.append("ESTADÍSTICAS")
        lines.append("=" * 70)

        usage_count: dict = defaultdict(int)
        for scopes in self.dependencies.values():
            for deps in scopes.values():
                for dep in deps:
                    usage_count[dep] += 1

        if usage_count:
            lines.append("\nMódulos más utilizados:")
            for module, count in sorted(usage_count.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"  • {module}: usado por {count} módulo(s)")

        no_deps = [m for m in self.modules if not self.dependencies.get(m)]
        if no_deps:
            lines.append(f"\nMódulos sin dependencias internas ({len(no_deps)}):")
            for module in sorted(no_deps):
                lines.append(f"  • {module}")

        unused = [m for m in self.modules if m not in usage_count]
        if unused:
            lines.append(f"\nMódulos no utilizados por otros ({len(unused)}):")
            for module in sorted(unused):
                lines.append(f"  • {module}")

        return "\n".join(lines)

    def to_json_dict(self) -> dict:
        return {
            "path":    str(self.base_path),
            "modules": self.modules,
            "dependencies": {
                m: {scope: list(deps) for scope, deps in scopes.items()}
                for m, scopes in self.dependencies.items()
            },
            "cycles": self.detect_dependency_cycles(),
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

        p = output_path / "gradle-report.txt"
        p.write_text(self.generate_report(), encoding='utf-8')
        self._vprint(f"✓ Reporte: {p}")


def _build_analyzer(args):
    focus = [m.strip() for m in args.focus.split(',')] if getattr(args, 'focus', None) else None
    analyzer = GradleDependencyAnalyzer(
        base_path=args.path,
        config_path=args.config,
        exclude=args.exclude,
        verbose=not args.quiet,
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
    parser.add_argument('--format', choices=['plantuml', 'mermaid', 'dot', 'ascii', 'all'],
                        default=None, dest='fmt', metavar='FORMAT')
    parser.add_argument('--output-dir', default=None, dest='output_dir', metavar='DIR')
    parser.add_argument('--exclude', action='append', default=[], metavar='MODULE')
    parser.add_argument('--focus',   default=None, metavar='MODULE[,MODULE]')
    parser.add_argument('--config',  default=None, metavar='PATH')
    parser.add_argument('--quiet',   action='store_true')
    parser.add_argument('--json',    action='store_true')

    args = parser.parse_args()

    proj_cfg = load_project_config(args.path).get('analyzer', {})
    if args.output_dir is None:
        args.output_dir = proj_cfg.get('output_dir', 'diagrams')
    if args.fmt is None:
        args.fmt = proj_cfg.get('format', 'all')

    if not args.quiet:
        print("🚀 Analizador de Dependencias via Gradle")
        print("=" * 70)

    analyzer, focus = _build_analyzer(args)

    if not args.quiet:
        print("\n📊 Generando archivos...")
        print("=" * 70)

    analyzer.save_all(output_dir=args.output_dir, fmt=args.fmt, focus=focus)

    if args.json:
        print(json.dumps(analyzer.to_json_dict(), indent=2, ensure_ascii=False))
    else:
        print("\n" + analyzer.generate_report())
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
