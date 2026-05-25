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
    get_icon,
    normalize_module_name,
    is_submodule_of,
    find_gradle_file,
)


class ExternalCallersAnalyzer:
    def __init__(self, project_root, target_module, config_path=None, verbose=True):
        self.project_root   = Path(project_root)
        self.target_module  = target_module
        self.config         = load_config(config_path)
        self.internal_modules = []
        self.all_modules      = []
        self.external_callers = defaultdict(lambda: defaultdict(set))
        self._vprint          = print if verbose else (lambda *a, **k: None)

    def scan_all_modules(self):
        self._vprint(f"📁 Escaneando proyecto completo: {self.project_root}\n")

        from_settings = parse_settings_modules(self.project_root)

        if from_settings is not None:
            for module_name in from_settings:
                self.all_modules.append(module_name)
                if is_submodule_of(module_name, self.target_module):
                    self.internal_modules.append(module_name)
                    self._vprint(f"  ✓ [INTERNO] {module_name}")
                else:
                    self._vprint(f"  ○ [EXTERNO] {module_name}")
        else:
            for gradle_file in sorted(self.project_root.rglob("build.gradle*")):
                module_dir = gradle_file.parent
                try:
                    rel_path    = module_dir.relative_to(self.project_root)
                    module_name = normalize_module_name(str(rel_path))
                    if module_name == '.':
                        continue
                    self.all_modules.append(module_name)
                    if is_submodule_of(module_name, self.target_module):
                        self.internal_modules.append(module_name)
                        self._vprint(f"  ✓ [INTERNO] {module_name}")
                    else:
                        self._vprint(f"  ○ [EXTERNO] {module_name}")
                except ValueError:
                    continue

        self._vprint(f"\n✓ Total módulos: {len(self.all_modules)}")
        self._vprint(f"✓ Módulos internos de {self.target_module}: {len(self.internal_modules)}")
        self._vprint(f"✓ Módulos externos: {len(self.all_modules) - len(self.internal_modules)}\n")
        return self

    def analyze_external_calls(self):
        self._vprint(f"🔍 Buscando quién llama a '{self.target_module}'...\n")

        external_modules  = [m for m in self.all_modules if not is_submodule_of(m, self.target_module)]
        internal_modules  = self.internal_modules
        project_root      = self.project_root

        def _parse_one(module):
            module_path = project_root / module.replace(':', '/')
            gradle_file = find_gradle_file(module_path)
            if gradle_file is None:
                return module, {}
            return module, parse_gradle_file_scoped(gradle_file, internal_modules, module)

        with ThreadPoolExecutor() as executor:
            for module, scoped_deps in executor.map(_parse_one, external_modules):
                for scope, modules in scoped_deps.items():
                    for target_submodule in modules:
                        self.external_callers[module][target_submodule].add(scope)
                        self._vprint(f"  🔗 {module} → {target_submodule} [{scope}]")

        total_calls = sum(len(targets) for targets in self.external_callers.values())
        self._vprint(f"\n✓ Análisis completado")
        self._vprint(f"✓ {len(self.external_callers)} módulos externos llaman a {self.target_module}")
        self._vprint(f"✓ {total_calls} conexiones externas detectadas\n")
        return self

    def generate_plantuml(self):
        colors = self.config.get("colors", {})
        lines = [
            "@startuml",
            "",
            "skinparam packageStyle rectangle",
            "skinparam linetype ortho",
            "skinparam backgroundColor white",
            "",
            f'skinparam classBackgroundColor<<internal>> {colors.get("hub", "#E8F5E9")}',
            "skinparam classBackgroundColor<<external>> #FFE0B2",
            "skinparam classBorderColor #757575",
            "",
            "skinparam nodesep 120",
            "skinparam ranksep 120",
            "skinparam padding 20",
            "",
            f'package "{self.target_module}" <<internal>> {{',
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
        colors       = self.config.get("colors", {})
        pkg_id       = self.target_module.replace('-', '_')

        lines = [
            "graph LR",
            f'  subgraph {pkg_id}["{self.target_module} 📦"]',
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

        internal_ids = [m.replace(':', '_').replace('-', '_') for m in sorted(called_modules)]
        external_ids = [c.replace(':', '_').replace('-', '_') for c in sorted(self.external_callers.keys())]
        if internal_ids:
            lines.append(f"  class {','.join(internal_ids)} internal")
        if external_ids:
            lines.append(f"  class {','.join(external_ids)} external")

        return "\n".join(lines)

    def generate_report(self):
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

    def to_json_dict(self) -> dict:
        return {
            "project": str(self.project_root),
            "target":  self.target_module,
            "external_callers": {
                caller: {
                    target: list(scopes)
                    for target, scopes in targets.items()
                }
                for caller, targets in self.external_callers.items()
            },
        }

    def save_all(self, output_dir="external-calls", fmt="all"):
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if fmt in ('plantuml', 'all'):
            plantuml_file = output_path / f"{self.target_module}-external-calls.puml"
            with open(plantuml_file, 'w', encoding='utf-8') as f:
                f.write(self.generate_plantuml())
            self._vprint(f"✓ PlantUML: {plantuml_file}")

        if fmt in ('mermaid', 'all'):
            mermaid_file = output_path / f"{self.target_module}-external-calls.mmd"
            with open(mermaid_file, 'w', encoding='utf-8') as f:
                f.write(self.generate_mermaid())
            self._vprint(f"✓ Mermaid: {mermaid_file}")

        report_file = output_path / f"{self.target_module}-external-report.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_report())
        self._vprint(f"✓ Reporte: {report_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Detecta qué módulos externos llaman a tu módulo Android'
    )
    parser.add_argument('project_root')
    parser.add_argument('target_module')
    parser.add_argument('--format', choices=['plantuml', 'mermaid', 'all'], default='all',
                        dest='fmt', metavar='FORMAT')
    parser.add_argument('--output-dir', default='external-calls', dest='output_dir', metavar='DIR')
    parser.add_argument('--config', default=None, metavar='PATH')
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--json',  action='store_true')

    args = parser.parse_args()

    if not args.quiet:
        print("🚀 Analizador de Llamadas Externas")
        print("=" * 70)

    analyzer = ExternalCallersAnalyzer(
        project_root=args.project_root,
        target_module=args.target_module,
        config_path=args.config,
        verbose=not args.quiet,
    )
    analyzer.scan_all_modules()
    analyzer.analyze_external_calls()

    if not args.quiet:
        print("\n📊 Generando archivos...")
        print("=" * 70)

    analyzer.save_all(output_dir=args.output_dir, fmt=args.fmt)

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


if __name__ == "__main__":
    main()
