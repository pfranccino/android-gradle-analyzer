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
    is_submodule_of,
    setup_utf8,
)
from dependency_engine import get_engine, EngineError


class ExternalCallersAnalyzer:
    def __init__(self, project_root, target_module, config_path=None, verbose=True,
                 engine="static"):
        self.project_root   = Path(project_root)
        self.root           = self.project_root
        self.target_module  = target_module
        self.config         = load_config(config_path)
        self.internal_modules = []
        self.all_modules      = []
        self.external_callers = defaultdict(lambda: defaultdict(set))
        self._vprint          = print if verbose else (lambda *a, **k: None)
        self.engine_name      = engine
        self.engine           = get_engine(engine, verbose=verbose)

    def scan_all_modules(self):
        self._vprint(f"📁 Escaneando proyecto completo: {self.project_root}\n")

        # Siempre escaneamos desde la RAÍZ del proyecto (aunque se pase una
        # subcarpeta), con nombres canónicos: si no, los llamadores externos
        # (ej. ':app') quedarían fuera del scope y no se detectarían.
        self.root, known, _focus = compute_scope(self.project_root)
        for module_name in known:
            self.all_modules.append(module_name)
            if is_submodule_of(module_name, self.target_module):
                self.internal_modules.append(module_name)
                self._vprint(f"  ✓ [INTERNO] {module_name}")
            else:
                self._vprint(f"  ○ [EXTERNO] {module_name}")

        self._vprint(f"\n✓ Total módulos: {len(self.all_modules)}")
        self._vprint(f"✓ Módulos internos de {self.target_module}: {len(self.internal_modules)}")
        self._vprint(f"✓ Módulos externos: {len(self.all_modules) - len(self.internal_modules)}\n")
        return self

    def analyze_external_calls(self):
        self._vprint(f"🔍 Buscando quién llama a '{self.target_module}' (motor: {self.engine_name})...\n")

        external_modules = [m for m in self.all_modules if not is_submodule_of(m, self.target_module)]

        resolved = self.engine.resolve(
            self.root, external_modules, self.internal_modules,
        )
        for module, scoped_deps in resolved.items():
            for scope, targets in scoped_deps.items():
                for target_submodule in targets:
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
        slug = self.target_module.replace(":", "-")

        if fmt in ('plantuml', 'all'):
            p = output_path / f"{slug}-external-calls.puml"
            p.write_text(self.generate_plantuml(), encoding='utf-8')
            self._vprint(f"✓ PlantUML: {p}")

        if fmt in ('mermaid', 'all'):
            p = output_path / f"{slug}-external-calls.mmd"
            p.write_text(self.generate_mermaid(), encoding='utf-8')
            self._vprint(f"✓ Mermaid: {p}")

        p = output_path / f"{slug}-external-report.txt"
        p.write_text(self.generate_report(), encoding='utf-8')
        self._vprint(f"✓ Reporte: {p}")


def main():
    setup_utf8()
    parser = argparse.ArgumentParser(
        description='Detecta qué módulos externos llaman a tu módulo Android'
    )
    parser.add_argument('project_root')
    parser.add_argument('target_module')
    parser.add_argument('--format', choices=['plantuml', 'mermaid', 'all'], default='all',
                        dest='fmt', metavar='FORMAT')
    parser.add_argument('--output-dir', default=None, dest='output_dir', metavar='DIR')
    parser.add_argument('--config', default=None, metavar='PATH')
    parser.add_argument('--engine', choices=['static', 'dynamic', 'auto'], default=None,
                        help='Motor de extracción de dependencias (default: static)')
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--json',  action='store_true')

    args = parser.parse_args()

    proj_cfg = load_project_config(args.project_root).get('externals', {})
    if args.output_dir is None:
        args.output_dir = proj_cfg.get('output_dir', 'external-calls')
    if args.engine is None:
        args.engine = proj_cfg.get('engine', 'static')

    if not args.quiet:
        print("🚀 Analizador de Llamadas Externas")
        print("=" * 70)

    analyzer = ExternalCallersAnalyzer(
        project_root=args.project_root,
        target_module=args.target_module,
        config_path=args.config,
        verbose=not args.quiet,
        engine=args.engine,
    )
    try:
        analyzer.scan_all_modules()
        analyzer.analyze_external_calls()
    except EngineError as exc:
        print(f"\n❌ Motor '{args.engine}' falló: {exc}")
        sys.exit(1)

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
