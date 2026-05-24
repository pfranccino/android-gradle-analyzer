#!/usr/bin/env python3
"""
Analizador de llamadas externas a módulos
Detecta qué módulos externos (app, otros features) llaman a tus módulos
"""

import argparse
from pathlib import Path
from collections import defaultdict

from analyzer_utils import (
    parse_gradle_file_scoped,
    load_config,
    get_icon,
    normalize_module_name,
    is_submodule_of,
)


class ExternalCallersAnalyzer:
    def __init__(self, project_root, target_module, config_path=None):
        """
        Args:
            project_root:  Ruta raíz del proyecto (ej: /ruta/a/tu/android-project)
            target_module: Módulo a analizar (ej: payments)
            config_path:   Ruta opcional a analyzer_config.json
        """
        self.project_root  = Path(project_root)
        self.target_module = target_module
        self.config        = load_config(config_path)

        self.internal_modules = []
        self.all_modules      = []

        # {caller_module: {target_submodule: set(scopes)}}
        self.external_callers = defaultdict(lambda: defaultdict(set))

    def scan_all_modules(self):
        """Escanea TODOS los módulos del proyecto"""
        print(f"📁 Escaneando proyecto completo: {self.project_root}\n")

        gradle_files = list(self.project_root.rglob("build.gradle*"))

        for gradle_file in sorted(gradle_files):
            module_dir = gradle_file.parent
            try:
                rel_path    = module_dir.relative_to(self.project_root)
                module_name = normalize_module_name(str(rel_path))

                if module_name == '.':
                    continue

                self.all_modules.append(module_name)

                if is_submodule_of(module_name, self.target_module):
                    self.internal_modules.append(module_name)
                    print(f"  ✓ [INTERNO] {module_name}")
                else:
                    print(f"  ○ [EXTERNO] {module_name}")

            except ValueError:
                continue

        print(f"\n✓ Total módulos: {len(self.all_modules)}")
        print(f"✓ Módulos internos de {self.target_module}: {len(self.internal_modules)}")
        print(f"✓ Módulos externos: {len(self.all_modules) - len(self.internal_modules)}\n")
        return self

    def analyze_external_calls(self):
        """Analiza qué módulos externos llaman a los módulos del target"""
        print(f"🔍 Buscando quién llama a '{self.target_module}'...\n")

        for module in self.all_modules:
            if is_submodule_of(module, self.target_module):
                continue

            module_path = self.project_root / module.replace(':', '/')
            gradle_file = module_path / "build.gradle.kts"
            if not gradle_file.exists():
                gradle_file = module_path / "build.gradle"

            if gradle_file.exists():
                self._check_gradle_for_calls(module, gradle_file)

        total_calls = sum(len(targets) for targets in self.external_callers.values())

        print(f"\n✓ Análisis completado")
        print(f"✓ {len(self.external_callers)} módulos externos llaman a {self.target_module}")
        print(f"✓ {total_calls} conexiones externas detectadas\n")
        return self

    def _check_gradle_for_calls(self, caller_module, gradle_file):
        """Revisa si un módulo externo llama a algún módulo interno"""
        scoped_deps = parse_gradle_file_scoped(
            gradle_file, self.internal_modules, caller_module
        )
        for scope, modules in scoped_deps.items():
            for target_submodule in modules:
                self.external_callers[caller_module][target_submodule].add(scope)
                print(f"  🔗 {caller_module} → {target_submodule} [{scope}]")

    # ── Generadores ──────────────────────────────────────────────────────────

    def generate_plantuml(self):
        """Genera diagrama PlantUML de llamadas externas"""
        package_name = self.target_module
        colors       = self.config.get("colors", {})

        lines = [
            "@startuml",
            "",
            "skinparam packageStyle rectangle",
            "skinparam linetype ortho",
            "skinparam backgroundColor white",
            "",
            "' Colores",
            f'skinparam classBackgroundColor<<internal>> {colors.get("hub", "#E8F5E9")}',
            "skinparam classBackgroundColor<<external>> #FFE0B2",
            "skinparam classBorderColor #757575",
            "",
            "' Espaciado",
            "skinparam nodesep 120",
            "skinparam ranksep 120",
            "skinparam padding 20",
            "",
            f'package "{package_name}" <<internal>> {{',
        ]

        called_modules = {t for targets in self.external_callers.values() for t in targets}

        for module in sorted(called_modules):
            display_name = module.split(':', 1)[1] if ':' in module else module
            module_id    = module.replace(':', '_').replace('-', '_')
            lines.append(f'  class "{display_name}" as {module_id} <<internal>>')

        lines.append("}")
        lines.append("")
        lines.append("' Módulos externos que llaman")

        for caller in sorted(self.external_callers.keys()):
            caller_id = caller.replace(':', '_').replace('-', '_')
            lines.append(f'class "{caller}" as {caller_id} <<external>>')

        lines.append("")
        lines.append("' Llamadas externas")

        for caller in sorted(self.external_callers.keys()):
            caller_id = caller.replace(':', '_').replace('-', '_')
            for target in sorted(self.external_callers[caller].keys()):
                target_id = target.replace(':', '_').replace('-', '_')
                lines.append(f"{caller_id} ..> {target_id} : uses")

        lines.extend(["", "@enduml"])
        return "\n".join(lines)

    def generate_mermaid(self):
        """Genera diagrama Mermaid de llamadas externas"""
        package_name = self.target_module
        pkg_id       = package_name.replace('-', '_')
        colors       = self.config.get("colors", {})

        lines = [
            "graph LR",
            f'  subgraph {pkg_id}["{package_name} 📦"]',
        ]

        called_modules = {t for targets in self.external_callers.values() for t in targets}

        for module in sorted(called_modules):
            display_name = module.split(':', 1)[1] if ':' in module else module
            module_id    = module.replace(':', '_').replace('-', '_')
            icon         = get_icon(display_name, self.config)
            lines.append(f'    {module_id}["{icon} {display_name}"]')

        lines.append("  end")
        lines.append("")

        for caller in sorted(self.external_callers.keys()):
            caller_id = caller.replace(':', '_').replace('-', '_')
            lines.append(f'  {caller_id}["🟠 {caller}"]')

        lines.append("")

        for caller in sorted(self.external_callers.keys()):
            caller_id = caller.replace(':', '_').replace('-', '_')
            for target in sorted(self.external_callers[caller].keys()):
                target_id = target.replace(':', '_').replace('-', '_')
                lines.append(f"  {caller_id} -.->|uses| {target_id}")

        lines.append("")
        lines.append(f'  classDef internal fill:{colors.get("hub", "#E8F5E9")},stroke:#2E7D32')
        lines.append("  classDef external fill:#FFE0B2,stroke:#E65100")

        # Aplicar estilos a los nodos
        internal_ids = [m.replace(':', '_').replace('-', '_') for m in sorted(called_modules)]
        external_ids = [c.replace(':', '_').replace('-', '_') for c in sorted(self.external_callers.keys())]
        if internal_ids:
            lines.append(f"  class {','.join(internal_ids)} internal")
        if external_ids:
            lines.append(f"  class {','.join(external_ids)} external")

        return "\n".join(lines)

    def generate_report(self):
        """Genera reporte de texto"""
        lines = [
            "=" * 70,
            f"ANÁLISIS DE LLAMADAS EXTERNAS A {self.target_module.upper()}",
            "=" * 70,
            f"\nProyecto: {self.project_root}",
            f"Módulo analizado: {self.target_module}",
            "\n" + "=" * 70,
            "MÓDULOS EXTERNOS QUE LLAMAN",
            "=" * 70,
        ]

        if not self.external_callers:
            lines.append("\n❌ No se encontraron llamadas externas")
        else:
            for caller in sorted(self.external_callers.keys()):
                lines.append(f"\n📦 {caller}")
                for target in sorted(self.external_callers[caller].keys()):
                    scopes = ', '.join(sorted(self.external_callers[caller][target]))
                    lines.append(f"  └─→ {target}  [{scopes}]")

        lines.append("\n" + "=" * 70)
        lines.append("ESTADÍSTICAS")
        lines.append("=" * 70)

        call_count: dict = defaultdict(int)
        for targets in self.external_callers.values():
            for target in targets:
                call_count[target] += 1

        if call_count:
            lines.append("\nMódulos más llamados desde fuera:")
            for module, count in sorted(call_count.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"  • {module}: {count} llamada(s)")

        uncalled = set(self.internal_modules) - set(call_count.keys())
        if uncalled:
            lines.append(f"\nMódulos NO llamados externamente ({len(uncalled)}):")
            for module in sorted(uncalled)[:10]:
                lines.append(f"  • {module}")
            if len(uncalled) > 10:
                lines.append(f"  ... y {len(uncalled) - 10} más")

        return "\n".join(lines)

    def save_all(self, output_dir="external-calls", fmt="all"):
        """Guarda los archivos generados según el formato solicitado"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if fmt in ('plantuml', 'all'):
            plantuml_file = output_path / f"{self.target_module}-external-calls.puml"
            with open(plantuml_file, 'w', encoding='utf-8') as f:
                f.write(self.generate_plantuml())
            print(f"✓ PlantUML: {plantuml_file}")

        if fmt in ('mermaid', 'all'):
            mermaid_file = output_path / f"{self.target_module}-external-calls.mmd"
            with open(mermaid_file, 'w', encoding='utf-8') as f:
                f.write(self.generate_mermaid())
            print(f"✓ Mermaid: {mermaid_file}")

        # El reporte siempre se genera
        report_file = output_path / f"{self.target_module}-external-report.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_report())
        print(f"✓ Reporte: {report_file}")


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Detecta qué módulos externos llaman a tu módulo Android'
    )
    parser.add_argument(
        'project_root',
        help='Ruta raíz del proyecto Android (ej: /ruta/a/tu/android-project)'
    )
    parser.add_argument(
        'target_module',
        help='Nombre del módulo a analizar (ej: payments)'
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
        default='external-calls',
        dest='output_dir',
        metavar='DIR',
        help='Directorio de salida (default: external-calls)'
    )
    parser.add_argument(
        '--config',
        default=None,
        metavar='PATH',
        help='Ruta a archivo analyzer_config.json personalizado'
    )

    args = parser.parse_args()

    print("🚀 Analizador de Llamadas Externas")
    print("=" * 70)

    analyzer = ExternalCallersAnalyzer(
        project_root=args.project_root,
        target_module=args.target_module,
        config_path=args.config,
    )
    analyzer.scan_all_modules()
    analyzer.analyze_external_calls()

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
