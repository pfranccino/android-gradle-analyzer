#!/usr/bin/env python3
"""
Analizador de dependencias entre módulos Android
Lee los archivos build.gradle / build.gradle.kts para detectar dependencias REALES
"""

import argparse
from pathlib import Path
from collections import defaultdict

from analyzer_utils import (
    parse_gradle_file_scoped,
    load_config,
    get_icon,
    get_style,
    detect_cycles,
)

# Agrupación visual de scopes en los diagramas
_COMPILE_SCOPES = {'api', 'implementation', 'compileOnly'}
_BUILD_SCOPES   = {'kapt', 'annotationProcessor'}
_TEST_SCOPES    = {
    'testImplementation', 'androidTestImplementation',
    'debugImplementation', 'releaseImplementation',
    'runtimeOnly', 'testRuntimeOnly',
}


class GradleDependencyAnalyzer:
    def __init__(self, base_path, config_path=None, exclude=None):
        self.base_path = Path(base_path)
        self.config    = load_config(config_path)
        self.exclude   = set(exclude or [])
        self.modules   = []
        self.dependencies = defaultdict(lambda: defaultdict(set))
        # estructura: {module: {scope: {modules}}}
        self.module_paths = {}

    def scan_modules(self):
        """Escanea TODOS los módulos del proyecto recursivamente"""
        print(f"📁 Escaneando TODOS los módulos en: {self.base_path}\n")

        if not self.base_path.exists():
            print("❌ Error: La ruta no existe")
            return self

        gradle_files = list(self.base_path.rglob("build.gradle*"))

        for gradle_file in sorted(gradle_files):
            module_dir = gradle_file.parent
            try:
                rel_path    = module_dir.relative_to(self.base_path)
                module_name = str(rel_path).replace('/', ':').replace('\\', ':')

                if module_name == '.':
                    continue

                if module_name in self.exclude:
                    print(f"  ⊘ {module_name} (excluido)")
                    continue

                self.modules.append(module_name)
                self.module_paths[module_name] = rel_path
                print(f"  • {module_name}")

            except ValueError:
                continue

        print(f"\n✓ {len(self.modules)} módulos encontrados\n")
        return self

    def analyze_gradle_dependencies(self):
        """Analiza las dependencias desde los archivos gradle"""
        print("🔍 Analizando archivos Gradle...")

        for module in self.modules:
            module_path = self.base_path / module.replace(':', '/')

            gradle_file = module_path / "build.gradle.kts"
            if not gradle_file.exists():
                gradle_file = module_path / "build.gradle"

            if gradle_file.exists():
                scoped = parse_gradle_file_scoped(gradle_file, self.modules, module)
                if scoped:
                    self.dependencies[module] = scoped
                    total = sum(len(v) for v in scoped.values())
                    print(f"  ✓ {module}: {total} dependencia(s)")
                else:
                    print(f"  ○ {module}: sin dependencias internas")
            else:
                print(f"  ⚠️  No se encontró gradle para: {module}")

        total_deps = sum(
            len(mods)
            for scopes in self.dependencies.values()
            for mods in scopes.values()
        )
        print(f"\n✓ Análisis completado: {total_deps} dependencias detectadas\n")
        return self

    def detect_dependency_cycles(self):
        """Detecta ciclos en el grafo de dependencias"""
        return detect_cycles(self.dependencies)

    # ── Generadores ──────────────────────────────────────────────────────────

    def generate_plantuml(self):
        """Genera el código PlantUML"""
        package_name = self.base_path.name
        cycles       = self.detect_dependency_cycles()
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
            "' Espaciado",
            "skinparam nodesep 150",
            "skinparam ranksep 150",
            "skinparam padding 30",
            "",
            f'package "{package_name}" <<package>> {{',
            "",
        ]

        for module in sorted(self.modules):
            module_id = module.replace('-', '_').replace(':', '_')
            style     = ' <<cycle>>' if module in cycle_modules else get_style(module, self.config)
            lines.append(f'  class "{module}" as {module_id}{style}')

        lines.append("")
        lines.append("  ' Dependencias detectadas desde Gradle")

        for from_module in sorted(self.dependencies.keys()):
            from_id = from_module.replace('-', '_').replace(':', '_')
            scoped  = self.dependencies[from_module]

            compile_deps = set()
            for s in _COMPILE_SCOPES:
                compile_deps |= scoped.get(s, set())
            for to_module in sorted(compile_deps):
                to_id = to_module.replace('-', '_').replace(':', '_')
                lines.append(f"  {from_id} --> {to_id} : use")

            build_deps = set()
            for s in _BUILD_SCOPES:
                build_deps |= scoped.get(s, set())
            for to_module in sorted(build_deps - compile_deps):
                to_id = to_module.replace('-', '_').replace(':', '_')
                lines.append(f"  {from_id} ..> {to_id} : build")

            test_deps = set()
            for s in _TEST_SCOPES:
                test_deps |= scoped.get(s, set())
            for to_module in sorted(test_deps - compile_deps - build_deps):
                to_id = to_module.replace('-', '_').replace(':', '_')
                lines.append(f"  {from_id} ..> {to_id} : test")

        lines.extend(["", "}", "", "@enduml"])
        return "\n".join(lines)

    def generate_mermaid(self):
        """Genera el código Mermaid"""
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

        for module in sorted(self.modules):
            module_id = module.replace('-', '_').replace(':', '_')
            icon      = get_icon(module, self.config)
            lines.append(f'    {module_id}["{icon} {module}"]')

        lines.append("")
        lines.append("    %% Dependencias desde Gradle")

        for from_module in sorted(self.dependencies.keys()):
            from_id = from_module.replace('-', '_').replace(':', '_')
            scoped  = self.dependencies[from_module]

            compile_deps = set()
            for s in _COMPILE_SCOPES:
                compile_deps |= scoped.get(s, set())
            for to_module in sorted(compile_deps):
                to_id = to_module.replace('-', '_').replace(':', '_')
                lines.append(f"    {from_id} -->|use| {to_id}")

            build_deps = set()
            for s in _BUILD_SCOPES:
                build_deps |= scoped.get(s, set())
            for to_module in sorted(build_deps - compile_deps):
                to_id = to_module.replace('-', '_').replace(':', '_')
                lines.append(f"    {from_id} -.->|build| {to_id}")

            test_deps = set()
            for s in _TEST_SCOPES:
                test_deps |= scoped.get(s, set())
            for to_module in sorted(test_deps - compile_deps - build_deps):
                to_id = to_module.replace('-', '_').replace(':', '_')
                lines.append(f"    {from_id} -.->|test| {to_id}")

        lines.append("  end")
        lines.append("")

        # Estilos
        lines.append(f'  classDef commonStyle  fill:{colors.get("common",  "#FFF9C4")},stroke:#F57F17,stroke-width:2px')
        lines.append(f'  classDef gatewayStyle fill:{colors.get("gateway", "#E1F5FE")},stroke:#0277BD,stroke-width:2px')
        lines.append(f'  classDef hubStyle     fill:{colors.get("hub",     "#E8F5E9")},stroke:#2E7D32,stroke-width:2px')
        lines.append(f'  classDef cycleStyle   fill:{colors.get("cycle",   "#FFCDD2")},stroke:#C62828,stroke-width:2px')
        lines.append("")

        def _ids(mods):
            return [m.replace('-', '_').replace(':', '_') for m in mods]

        commons  = _ids(m for m in self.modules if any(k in m.lower() for k in ('common', 'core', 'shared')))
        gateways = _ids(m for m in self.modules if any(k in m.lower() for k in ('gateway', 'network', 'remote')) or m.endswith(':api'))
        hubs     = _ids(m for m in self.modules if any(k in m.lower() for k in ('home', 'main', 'hub')))
        cycle_ids = _ids(m for m in cycle_modules if m in self.modules)

        if commons:
            lines.append(f"  class {','.join(commons)} commonStyle")
        if gateways:
            lines.append(f"  class {','.join(gateways)} gatewayStyle")
        if hubs:
            lines.append(f"  class {','.join(hubs)} hubStyle")
        if cycle_ids:
            lines.append(f"  class {','.join(cycle_ids)} cycleStyle")

        return "\n".join(lines)

    def generate_report(self):
        """Genera un reporte detallado en texto"""
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

    def save_all(self, output_dir="diagrams", fmt="all"):
        """Guarda los archivos generados según el formato solicitado"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        if fmt in ('plantuml', 'all'):
            plantuml_file = output_path / "gradle-dependencies.puml"
            with open(plantuml_file, 'w', encoding='utf-8') as f:
                f.write(self.generate_plantuml())
            print(f"✓ PlantUML: {plantuml_file}")

        if fmt in ('mermaid', 'all'):
            mermaid_file = output_path / "gradle-dependencies.mmd"
            with open(mermaid_file, 'w', encoding='utf-8') as f:
                f.write(self.generate_mermaid())
            print(f"✓ Mermaid: {mermaid_file}")

        # El reporte siempre se genera
        report_file = output_path / "gradle-report.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_report())
        print(f"✓ Reporte: {report_file}")


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Analiza dependencias internas de módulos Android'
    )
    parser.add_argument(
        'path',
        help='Ruta al directorio del módulo a analizar (ej: /ruta/a/tu/proyecto/payments)'
    )
    parser.add_argument(
        '--format',
        choices=['plantuml', 'mermaid', 'all'],
        default='all',
        dest='fmt',
        metavar='FORMAT',
        help='Formato de salida: plantuml, mermaid, all (default: all)'
    )
    parser.add_argument(
        '--output-dir',
        default='diagrams',
        dest='output_dir',
        metavar='DIR',
        help='Directorio de salida (default: diagrams)'
    )
    parser.add_argument(
        '--exclude',
        action='append',
        default=[],
        metavar='MODULE',
        help='Excluir un módulo del análisis (puede repetirse)'
    )
    parser.add_argument(
        '--config',
        default=None,
        metavar='PATH',
        help='Ruta a archivo analyzer_config.json personalizado'
    )

    args = parser.parse_args()

    print("🚀 Analizador de Dependencias via Gradle")
    print("=" * 70)

    analyzer = GradleDependencyAnalyzer(
        base_path=args.path,
        config_path=args.config,
        exclude=args.exclude,
    )
    analyzer.scan_modules()
    analyzer.analyze_gradle_dependencies()

    print("\n📊 Generando archivos...")
    print("=" * 70)

    analyzer.save_all(output_dir=args.output_dir, fmt=args.fmt)

    print("\n" + analyzer.generate_report())

    print("\n" + "=" * 70)
    print("✅ ¡Análisis completado!")
    print("=" * 70)
    print("\n💡 Para visualizar:")
    print("  • PlantUML: https://www.plantuml.com/plantuml/uml/")
    print("  • Mermaid:  https://mermaid.live/")


if __name__ == "__main__":
    main()
