#!/usr/bin/env python3
import json
import argparse
from pathlib import Path
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor

from analyzer_utils import (
    parse_gradle_file_scoped,
    parse_settings_modules,
    load_config,
    get_icon,
    normalize_module_name,
    find_gradle_file,
    setup_utf8,
)


class ImpactAnalyzer:
    def __init__(self, project_root, target_module, config_path=None, verbose=True):
        self.project_root  = Path(project_root)
        self.target_module = target_module
        self.config        = load_config(config_path)
        self.all_modules   = []
        self.reverse_graph = defaultdict(set)
        self.impacted      = {}
        self._vprint       = print if verbose else (lambda *a, **k: None)

    def scan_and_build_graph(self):
        self._vprint(f"📁 Escaneando proyecto: {self.project_root}\n")

        from_settings = parse_settings_modules(self.project_root)

        if from_settings is not None:
            self.all_modules = list(from_settings)
        else:
            for gradle_file in sorted(self.project_root.rglob("build.gradle*")):
                module_dir = gradle_file.parent
                try:
                    rel_path    = module_dir.relative_to(self.project_root)
                    module_name = normalize_module_name(str(rel_path))
                    if module_name == "." or module_name in self.all_modules:
                        continue
                    self.all_modules.append(module_name)
                except ValueError:
                    continue

        self._vprint(f"✓ {len(self.all_modules)} módulos encontrados\n")
        self._vprint("🔍 Construyendo grafo invertido de dependencias...")

        all_modules  = self.all_modules
        project_root = self.project_root

        def _parse_one(module):
            module_path = project_root / module.replace(":", "/")
            gradle_file = find_gradle_file(module_path)
            if gradle_file is None:
                return module, {}
            return module, parse_gradle_file_scoped(gradle_file, all_modules, module)

        with ThreadPoolExecutor() as executor:
            for module, scoped in executor.map(_parse_one, all_modules):
                for scope_deps in scoped.values():
                    for dep in scope_deps:
                        self.reverse_graph[dep].add(module)

        return self

    def compute_impact(self):
        self._vprint(f"\n💥 Calculando impacto de '{self.target_module}'...\n")

        queue   = deque([(self.target_module, 0)])
        visited = {self.target_module}

        while queue:
            current, level = queue.popleft()
            for dependent in sorted(self.reverse_graph.get(current, set())):
                if dependent not in visited:
                    visited.add(dependent)
                    self.impacted[dependent] = level + 1
                    queue.append((dependent, level + 1))

        return self

    def generate_report(self):
        total = len(self.all_modules)
        n     = len(self.impacted)
        pct   = round(n / total * 100) if total > 0 else 0

        by_level = defaultdict(list)
        for m, lvl in self.impacted.items():
            by_level[lvl].append(m)

        lines = [
            "=" * 70,
            f"IMPACTO DE CAMBIOS EN: {self.target_module.upper()}",
            "=" * 70,
            f"\nProyecto      : {self.project_root}",
            f"Módulo        : {self.target_module}",
            f"Total módulos : {total}",
            "",
        ]

        if not self.impacted:
            lines.append("✅ Sin impacto — ningún módulo depende de este.")
            return "\n".join(lines)

        for lvl in sorted(by_level.keys()):
            label = "dependientes directos" if lvl == 1 else "dependientes transitivos"
            lines.append(f"  Nivel {lvl} — {label} ({len(by_level[lvl])}):")
            for m in sorted(by_level[lvl]):
                lines.append(f"    • {m}")
            lines.append("")

        lines += [
            f"  🔥 Impacto total: {n} módulos ({pct}% del proyecto)",
            f"     Cambiar {self.target_module} requiere verificar {n} módulo(s).",
            "",
        ]
        return "\n".join(lines)

    def to_json_dict(self) -> dict:
        return {
            "project":           str(self.project_root),
            "target":            self.target_module,
            "total_modules":     len(self.all_modules),
            "impacted":          self.impacted,
            "impact_percentage": round(len(self.impacted) / len(self.all_modules) * 100) if self.all_modules else 0,
        }

    def generate_plantuml(self):
        def _id(m):
            return m.replace("-", "_").replace(":", "_")

        lines = [
            "@startuml",
            "",
            "skinparam packageStyle rectangle",
            "skinparam linetype ortho",
            "skinparam backgroundColor white",
            "skinparam classBackgroundColor<<target>>  #FFCDD2",
            "skinparam classBackgroundColor<<level1>>  #FFE0B2",
            "skinparam classBackgroundColor<<level2>>  #FFF9C4",
            "skinparam classBorderColor #757575",
            "",
            "skinparam nodesep 100",
            "skinparam ranksep 100",
            "skinparam padding 20",
            "",
            f'class "{self.target_module}" as {_id(self.target_module)} <<target>>',
        ]

        for module, level in sorted(self.impacted.items()):
            stereotype = "<<level1>>" if level == 1 else "<<level2>>"
            lines.append(f'class "{module}" as {_id(module)} {stereotype}')

        lines.append("")

        for source in [self.target_module] + sorted(self.impacted.keys()):
            for dep in sorted(self.reverse_graph.get(source, set())):
                if dep in self.impacted:
                    lines.append(f"{_id(dep)} --> {_id(source)} : uses")

        lines.extend(["", "@enduml"])
        return "\n".join(lines)

    def generate_mermaid(self):
        def _id(m):
            return m.replace("-", "_").replace(":", "_")

        lines = ["graph LR", ""]

        lines.append(f'  {_id(self.target_module)}["🎯 {self.target_module}"]')
        for module in sorted(self.impacted.keys()):
            icon = get_icon(module, self.config)
            lines.append(f'  {_id(module)}["{icon} {module}"]')

        lines.append("")

        for source in [self.target_module] + sorted(self.impacted.keys()):
            for dep in sorted(self.reverse_graph.get(source, set())):
                if dep in self.impacted:
                    lines.append(f"  {_id(dep)} -->|uses| {_id(source)}")

        lines += [
            "",
            "  classDef target  fill:#FFCDD2,stroke:#C62828,stroke-width:2px",
            "  classDef level1  fill:#FFE0B2,stroke:#E65100,stroke-width:2px",
            "  classDef level2  fill:#FFF9C4,stroke:#F57F17,stroke-width:2px",
            "",
            f"  class {_id(self.target_module)} target",
        ]

        level1_ids = [_id(m) for m, lvl in self.impacted.items() if lvl == 1]
        level2_ids = [_id(m) for m, lvl in self.impacted.items() if lvl >= 2]
        if level1_ids:
            lines.append(f"  class {','.join(sorted(level1_ids))} level1")
        if level2_ids:
            lines.append(f"  class {','.join(sorted(level2_ids))} level2")

        return "\n".join(lines)

    def save_all(self, output_dir="impact", fmt="all"):
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        slug = self.target_module.replace(":", "-")

        if fmt in ("plantuml", "all"):
            p = output_path / f"{slug}-impact.puml"
            p.write_text(self.generate_plantuml(), encoding="utf-8")
            self._vprint(f"✓ PlantUML: {p}")

        if fmt in ("mermaid", "all"):
            p = output_path / f"{slug}-impact.mmd"
            p.write_text(self.generate_mermaid(), encoding="utf-8")
            self._vprint(f"✓ Mermaid: {p}")

        p = output_path / f"{slug}-impact-report.txt"
        p.write_text(self.generate_report(), encoding="utf-8")
        self._vprint(f"✓ Reporte: {p}")


def main():
    setup_utf8()
    parser = argparse.ArgumentParser(
        description="Calcula el impacto transitivo de cambios en un módulo Android"
    )
    parser.add_argument("project_root")
    parser.add_argument("target_module")
    parser.add_argument("--format", choices=["plantuml", "mermaid", "all"], default="all",
                        dest="fmt", metavar="FORMAT")
    parser.add_argument("--output-dir", default="impact", dest="output_dir", metavar="DIR")
    parser.add_argument("--config",     default=None, metavar="PATH")
    parser.add_argument("--quiet",      action="store_true")
    parser.add_argument("--json",       action="store_true")

    args = parser.parse_args()

    if not args.quiet:
        print("💥 Analizador de Impacto de Cambios")
        print("=" * 70)

    analyzer = ImpactAnalyzer(
        project_root=args.project_root,
        target_module=args.target_module,
        config_path=args.config,
        verbose=not args.quiet,
    )
    analyzer.scan_and_build_graph()
    analyzer.compute_impact()

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
            print("✅ Análisis completado!")
            print("=" * 70)
            print("\n💡 Para visualizar:")
            print("  • PlantUML: https://www.plantuml.com/plantuml/uml/")
            print("  • Mermaid:  https://mermaid.live/")


if __name__ == "__main__":
    main()
