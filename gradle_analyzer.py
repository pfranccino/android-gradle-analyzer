#!/usr/bin/env python3
"""
Analizador de dependencias entre módulos Android
Lee los archivos build.gradle / build.gradle.kts para detectar dependencias REALES
"""

import re
from pathlib import Path
from collections import defaultdict


class GradleDependencyAnalyzer:
    def __init__(self, base_path):
        self.base_path = Path(base_path)
        self.modules = []
        self.dependencies = defaultdict(set)
        self.module_paths = {}  # Mapeo de nombre de módulo a su path completo
        
    def scan_modules(self):
        """Escanea TODOS los módulos del proyecto recursivamente"""
        print(f"📁 Escaneando TODOS los módulos en: {self.base_path}\n")
        
        if not self.base_path.exists():
            print(f"❌ Error: La ruta no existe")
            return self
        
        # Buscar todos los build.gradle recursivamente
        gradle_files = list(self.base_path.rglob("build.gradle*"))
        
        for gradle_file in sorted(gradle_files):
            module_dir = gradle_file.parent
            
            # Calcular el path relativo desde base_path
            try:
                rel_path = module_dir.relative_to(self.base_path)
                
                # Si está en el root, saltar
                if str(rel_path) == '.':
                    continue
                
                # Convertir path a nombre de módulo
                module_name = str(rel_path).replace('/', ':').replace('\\', ':')
                
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
            # Convertir module name a path
            module_path = self.base_path / module.replace(':', '/')
            
            # Intentar leer build.gradle.kts primero, luego build.gradle
            gradle_file = module_path / "build.gradle.kts"
            if not gradle_file.exists():
                gradle_file = module_path / "build.gradle"
            
            if gradle_file.exists():
                self._parse_gradle_file(module, gradle_file)
            else:
                print(f"  ⚠️  No se encontró gradle para: {module}")
        
        total_deps = sum(len(deps) for deps in self.dependencies.values())
        print(f"\n✓ Análisis completado: {total_deps} dependencias detectadas\n")
        
        return self
    
    def _parse_gradle_file(self, module, gradle_file):
        """Parsea un archivo gradle para extraer dependencias"""
        try:
            with open(gradle_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Patrones para detectar dependencias de módulos internos
            patterns = [
                # implementation(project(":credit-card:common"))
                r'implementation\s*\(\s*project\s*\(\s*["\']([^"\']+)["\']\s*\)\s*\)',
                # api(project(":credit-card:common"))
                r'api\s*\(\s*project\s*\(\s*["\']([^"\']+)["\']\s*\)\s*\)',
                # implementation project(":credit-card:common")
                r'implementation\s+project\s*\(\s*["\']([^"\']+)["\']\s*\)',
                # api project(":credit-card:common")
                r'api\s+project\s*\(\s*["\']([^"\']+)["\']\s*\)',
                # implementation project(path: ':credit-card:common')
                r'implementation\s+project\s*\(\s*path\s*:\s*["\']([^"\']+)["\']\s*\)',
                # api project(path: ':credit-card:common')
                r'api\s+project\s*\(\s*path\s*:\s*["\']([^"\']+)["\']\s*\)',
                # testImplementation project(path: ':credit-card:common')
                r'testImplementation\s+project\s*\(\s*path\s*:\s*["\']([^"\']+)["\']\s*\)',
            ]
            
            found_deps = set()
            
            for pattern in patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    project_path = match.group(1)
                    
                    # Normalizar el path del proyecto
                    if project_path.startswith(':'):
                        project_path = project_path[1:]
                    
                    # Extraer solo la parte de credit-card si existe
                    if 'credit-card' in project_path:
                        parts = project_path.split(':')
                        cc_idx = parts.index('credit-card')
                        if cc_idx + 1 < len(parts):
                            # Reconstruir el path después de credit-card
                            normalized_path = ':'.join(parts[cc_idx + 1:])
                        else:
                            continue
                    else:
                        # Si no tiene credit-card en el path, usar el path completo
                        normalized_path = project_path.replace(':', ':')
                    
                    # Buscar coincidencia exacta en los módulos conocidos
                    if normalized_path in self.modules and normalized_path != module:
                        found_deps.add(normalized_path)
            
            if found_deps:
                self.dependencies[module] = found_deps
                print(f"  ✓ {module}: {len(found_deps)} dependencia(s)")
            else:
                print(f"  ○ {module}: sin dependencias internas")
                
        except Exception as e:
            print(f"  ❌ Error leyendo {gradle_file.name} de {module}: {e}")
    
    def _parse_gradle_file(self, module, gradle_file):
        """Parsea un archivo gradle para extraer dependencias"""
        try:
            with open(gradle_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Patrones para detectar dependencias de módulos internos
            patterns = [
                # implementation(project(":credit-card:common"))
                r'implementation\s*\(\s*project\s*\(\s*["\']([^"\']+)["\']\s*\)\s*\)',
                # api(project(":credit-card:common"))
                r'api\s*\(\s*project\s*\(\s*["\']([^"\']+)["\']\s*\)\s*\)',
                # implementation project(":credit-card:common")
                r'implementation\s+project\s*\(\s*["\']([^"\']+)["\']\s*\)',
                # api project(":credit-card:common")
                r'api\s+project\s*\(\s*["\']([^"\']+)["\']\s*\)',
                # implementation project(path: ':credit-card:common')
                r'implementation\s+project\s*\(\s*path\s*:\s*["\']([^"\']+)["\']\s*\)',
                # api project(path: ':credit-card:common')
                r'api\s+project\s*\(\s*path\s*:\s*["\']([^"\']+)["\']\s*\)',
                # testImplementation project(path: ':credit-card:common')
                r'testImplementation\s+project\s*\(\s*path\s*:\s*["\']([^"\']+)["\']\s*\)',
            ]
            
            found_deps = set()
            
            for pattern in patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    project_path = match.group(1)
                    
                    # Normalizar el path del proyecto
                    # Ej: ":credit-card:common" -> "common"
                    # Ej: ":common" -> "common"  
                    # Ej: ":credit-card:ui:common" -> "ui:common"
                    
                    # Quitar el primer ":" si existe
                    if project_path.startswith(':'):
                        project_path = project_path[1:]
                    
                    # Buscar coincidencias en los módulos conocidos
                    for known_module in self.modules:
                        # Verificar si el project_path termina con el known_module
                        # o si known_module termina con project_path
                        if (project_path.endswith(known_module) or 
                            known_module.endswith(project_path) or
                            project_path.replace(':', '/') == known_module.replace(':', '/')):
                            
                            if known_module != module:
                                found_deps.add(known_module)
                            break
            
            if found_deps:
                self.dependencies[module] = found_deps
                print(f"  ✓ {module}: {len(found_deps)} dependencia(s)")
            else:
                print(f"  ○ {module}: sin dependencias internas")
                
        except Exception as e:
            print(f"  ❌ Error leyendo {gradle_file.name} de {module}: {e}")
    
    def generate_plantuml(self):
        """Genera el código PlantUML"""
        # Obtener el nombre del directorio base
        package_name = self.base_path.name
        
        lines = [
            "@startuml",
            "",
            "skinparam packageStyle rectangle",
            "skinparam linetype ortho",
            "skinparam backgroundColor white",
            "skinparam classBackgroundColor<<common>> #FFF9C4",
            "skinparam classBackgroundColor<<gateway>> #E1F5FE",
            "skinparam classBackgroundColor<<hub>> #E8F5E9",
            "skinparam classBorderColor #757575",
            "",
            "' Espaciado mejorado",
            "skinparam nodesep 150",
            "skinparam ranksep 150",
            "skinparam padding 30",
            "",
            f'package "{package_name}" <<package>> {{',
            ""
        ]
        
        # Clasificar módulos
        def get_style(module):
            if module == 'common':
                return ' <<common>>'
            elif 'gateway' in module or 'api' in module:
                return ' <<gateway>>'
            elif module == 'home':
                return ' <<hub>>'
            return ''
        
        # Generar componentes
        for module in sorted(self.modules):
            module_id = module.replace('-', '_').replace(':', '_')
            style = get_style(module)
            lines.append(f'  class "{module}" as {module_id}{style}')
        
        lines.append("")
        lines.append("  ' Dependencies from Gradle files")
        
        # Generar dependencias
        for from_module in sorted(self.dependencies.keys()):
            from_id = from_module.replace('-', '_').replace(':', '_')
            for to_module in sorted(self.dependencies[from_module]):
                to_id = to_module.replace('-', '_').replace(':', '_')
                lines.append(f"  {from_id} ..> {to_id} : use")
        
        lines.extend(["", "}", "", "@enduml"])
        
        return "\n".join(lines)
    
    def generate_mermaid(self):
        """Genera el código Mermaid"""
        lines = [
            "graph TD",
            '  subgraph CC["📦 credit-card"]',
            ""
        ]
        
        # Iconos por tipo de módulo
        def get_icon(module):
            if module == 'common':
                return '🔧'
            elif 'gateway' in module or 'api' in module or 'eligibility' in module:
                return '🌐'
            elif module == 'home':
                return '🏠'
            elif 'payment' in module:
                return '💸'
            elif 'movement' in module:
                return '💰'
            elif 'statement' in module or 'account' in module:
                return '📊'
            elif 'credit' in module:
                return '💵'
            elif 'shipping' in module:
                return '📮'
            elif 'term' in module:
                return '📋'
            elif 'onboarding' in module:
                return '👋'
            elif 'purchase' in module:
                return '✅'
            elif 'overdue' in module or 'portfolio' in module:
                return '⚠️'
            elif 'tracking' in module:
                return '📍'
            elif 'notification' in module:
                return '🔔'
            elif 'card' in module or 'physical' in module:
                return '💳'
            elif 'configuration' in module:
                return '⚙️'
            return '📦'
        
        # Generar nodos
        for module in sorted(self.modules):
            module_id = module.replace('-', '_')
            icon = get_icon(module)
            lines.append(f'    {module_id}["{icon} {module}"]')
        
        lines.append("")
        lines.append("    %% Dependencies from Gradle")
        
        # Generar dependencias
        for from_module in sorted(self.dependencies.keys()):
            from_id = from_module.replace('-', '_')
            for to_module in sorted(self.dependencies[from_module]):
                to_id = to_module.replace('-', '_')
                lines.append(f"    {from_id} -.->|use| {to_id}")
        
        lines.append("  end")
        lines.append("")
        lines.append("  classDef commonStyle fill:#FFF9C4,stroke:#F57F17,stroke-width:2px")
        lines.append("  classDef gatewayStyle fill:#E1F5FE,stroke:#0277BD,stroke-width:2px")
        lines.append("  classDef hubStyle fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px")
        lines.append("")
        lines.append("  class common commonStyle")
        
        # Aplicar estilos a gateways
        gateways = [m.replace('-', '_') for m in self.modules if 'gateway' in m or 'eligibility' in m]
        if gateways:
            lines.append(f"  class {','.join(gateways)} gatewayStyle")
        
        lines.append("  class home hubStyle")
        
        return "\n".join(lines)
    
    def generate_report(self):
        """Genera un reporte detallado"""
        lines = [
            "=" * 70,
            "REPORTE DE DEPENDENCIAS - ANÁLISIS DESDE GRADLE",
            "=" * 70,
            f"\nRuta: {self.base_path}",
            f"Total de módulos: {len(self.modules)}",
            f"Total de dependencias: {sum(len(d) for d in self.dependencies.values())}",
            "\n" + "=" * 70,
            "DEPENDENCIAS POR MÓDULO",
            "=" * 70,
        ]
        
        for module in sorted(self.modules):
            deps = self.dependencies.get(module, set())
            lines.append(f"\n📦 {module}")
            if deps:
                for dep in sorted(deps):
                    lines.append(f"  → {dep}")
            else:
                lines.append("  (sin dependencias internas)")
        
        # Estadísticas
        lines.append("\n" + "=" * 70)
        lines.append("ESTADÍSTICAS")
        lines.append("=" * 70)
        
        # Módulos más usados
        usage_count = defaultdict(int)
        for deps in self.dependencies.values():
            for dep in deps:
                usage_count[dep] += 1
        
        if usage_count:
            lines.append("\nMódulos más utilizados:")
            for module, count in sorted(usage_count.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"  • {module}: usado por {count} módulo(s)")
        
        # Módulos sin dependencias
        no_deps = [m for m in self.modules if not self.dependencies.get(m)]
        if no_deps:
            lines.append(f"\nMódulos sin dependencias internas ({len(no_deps)}):")
            for module in sorted(no_deps):
                lines.append(f"  • {module}")
        
        # Módulos que no son usados por nadie
        unused = [m for m in self.modules if m not in usage_count]
        if unused:
            lines.append(f"\nMódulos no utilizados por otros ({len(unused)}):")
            for module in sorted(unused):
                lines.append(f"  • {module}")
        
        return "\n".join(lines)
    
    def find_cycles(self) -> list:
        """Detecta ciclos en el grafo de dependencias usando DFS (colores WHITE/GRAY/BLACK).
        Retorna una lista de ciclos, cada uno como lista de nombres de módulos."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {m: WHITE for m in self.modules}
        parent = {}
        cycles = []

        def dfs(node, stack):
            color[node] = GRAY
            stack.append(node)
            for neighbor in self.dependencies.get(node, set()):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    # Encontramos un back-edge → ciclo
                    cycle_start = stack.index(neighbor)
                    cycle = stack[cycle_start:]
                    if cycle not in cycles:
                        cycles.append(list(cycle))
                elif color[neighbor] == WHITE:
                    parent[neighbor] = node
                    dfs(neighbor, stack)
            stack.pop()
            color[node] = BLACK

        for module in self.modules:
            if color[module] == WHITE:
                dfs(module, [])

        return cycles

    def generate_cycle_diagram(self) -> str:
        """Genera un diagrama Mermaid resaltando en rojo los módulos involucrados en ciclos."""
        cycles = self.find_cycles()

        lines = ["graph TD", ""]

        if not cycles:
            lines.append('  no_cycles["✅ Sin dependencias circulares"]')
            return "\n".join(lines)

        # Nodos en ciclos
        cycle_nodes = set()
        cycle_edges = set()
        for cycle in cycles:
            for node in cycle:
                cycle_nodes.add(node)
            for i in range(len(cycle)):
                src = cycle[i]
                dst = cycle[(i + 1) % len(cycle)]
                cycle_edges.add((src, dst))

        # Nodos
        for module in sorted(self.modules):
            module_id = module.replace('-', '_').replace(':', '_')
            if module in cycle_nodes:
                lines.append(f'  {module_id}["⚠️ {module}"]')
            else:
                lines.append(f'  {module_id}["{module}"]')

        lines.append("")
        lines.append("  %% Todas las dependencias")
        for from_module in sorted(self.dependencies.keys()):
            from_id = from_module.replace('-', '_').replace(':', '_')
            for to_module in sorted(self.dependencies[from_module]):
                to_id = to_module.replace('-', '_').replace(':', '_')
                if (from_module, to_module) in cycle_edges:
                    lines.append(f"  {from_id} -->|🔴 ciclo| {to_id}")
                else:
                    lines.append(f"  {from_id} -.-> {to_id}")

        lines.append("")
        lines.append("  classDef cycleStyle fill:#FFCDD2,stroke:#C62828,stroke-width:3px,color:#B71C1C")
        cycle_ids = ",".join(
            m.replace('-', '_').replace(':', '_') for m in sorted(cycle_nodes)
        )
        if cycle_ids:
            lines.append(f"  class {cycle_ids} cycleStyle")

        lines.append("")
        lines.append(f"  %% Ciclos detectados: {len(cycles)}")
        for i, cycle in enumerate(cycles, 1):
            lines.append(f"  %% Ciclo {i}: {' → '.join(cycle)} → {cycle[0]}")

        return "\n".join(lines)

    def generate_impact_diagram(self, target: str) -> str:
        """Genera un diagrama Mermaid mostrando todos los módulos afectados
        directa e indirectamente si el módulo objetivo cambia (reverse BFS)."""
        # Construir grafo inverso: quién depende de cada módulo
        reverse_graph = defaultdict(set)
        for module, deps in self.dependencies.items():
            for dep in deps:
                reverse_graph[dep].add(module)

        if target not in self.modules:
            return f"graph TD\n  error[\"❌ Módulo '{target}' no encontrado\"]"

        # BFS desde target en el grafo inverso
        visited = {}  # module -> distancia desde target
        queue = [(target, 0)]
        visited[target] = 0
        while queue:
            current, dist = queue.pop(0)
            for caller in reverse_graph.get(current, set()):
                if caller not in visited:
                    visited[caller] = dist + 1
                    queue.append((caller, dist + 1))

        affected = {m for m in visited if m != target}

        lines = [
            "graph TD",
            f'  %% Impacto de cambios en: {target}',
            f'  %% Módulos afectados: {len(affected)}',
            "",
        ]

        target_id = target.replace('-', '_').replace(':', '_')
        lines.append(f'  {target_id}["🎯 {target}"]')

        for module in sorted(self.modules):
            if module == target:
                continue
            module_id = module.replace('-', '_').replace(':', '_')
            dist = visited.get(module)
            if dist is not None:
                lines.append(f'  {module_id}["📦 {module} (d={dist})"]')
            else:
                lines.append(f'  {module_id}["{module}"]')

        lines.append("")
        lines.append("  %% Dependencias directas e indirectas")
        for from_module in sorted(self.dependencies.keys()):
            from_id = from_module.replace('-', '_').replace(':', '_')
            for to_module in sorted(self.dependencies[from_module]):
                to_id = to_module.replace('-', '_').replace(':', '_')
                lines.append(f"  {from_id} -.-> {to_id}")

        lines.append("")
        lines.append("  classDef targetStyle fill:#FFF9C4,stroke:#F57F17,stroke-width:3px")
        lines.append("  classDef affectedStyle fill:#FFE0B2,stroke:#E65100,stroke-width:2px")
        lines.append(f"  class {target_id} targetStyle")

        affected_ids = ",".join(
            m.replace('-', '_').replace(':', '_') for m in sorted(affected)
        )
        if affected_ids:
            lines.append(f"  class {affected_ids} affectedStyle")

        return "\n".join(lines)

    def generate_matrix(self) -> str:
        """Genera una matriz de dependencias (DSM) en formato ASCII.
        Filas = módulo dependiente, Columnas = módulo del que depende.
        Una 'X' indica que la fila depende de la columna."""
        modules = sorted(self.modules)
        if not modules:
            return "No hay módulos para mostrar."

        # Etiquetas cortas para las columnas (última parte del path)
        short = [m.split(':')[-1] for m in modules]
        col_width = max(len(s) for s in short)
        row_label_width = max(len(m) for m in modules)

        header = " " * (row_label_width + 2)
        for s in short:
            header += s.center(col_width + 1)

        separator = "-" * len(header)

        lines = [
            "MATRIZ DE DEPENDENCIAS (DSM)",
            separator,
            header,
            separator,
        ]

        for i, module in enumerate(modules):
            row = module.ljust(row_label_width) + " |"
            for j, dep in enumerate(modules):
                if dep in self.dependencies.get(module, set()):
                    cell = "X"
                elif i == j:
                    cell = "·"
                else:
                    cell = " "
                row += cell.center(col_width + 1)
            lines.append(row)

        lines.append(separator)
        lines.append(f"\nTotal módulos: {len(modules)}")
        lines.append(f"Total dependencias: {sum(len(d) for d in self.dependencies.values())}")
        return "\n".join(lines)

    def save_all(self, output_dir="diagrams"):
        """Guarda todos los archivos generados"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # PlantUML
        plantuml_file = output_path / "gradle-dependencies.puml"
        with open(plantuml_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_plantuml())
        print(f"✓ PlantUML: {plantuml_file}")
        
        # Mermaid
        mermaid_file = output_path / "gradle-dependencies.mmd"
        with open(mermaid_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_mermaid())
        print(f"✓ Mermaid: {mermaid_file}")
        
        # Reporte
        report_file = output_path / "gradle-report.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_report())
        print(f"✓ Reporte: {report_file}")

        # Matriz de dependencias
        matrix_file = output_path / "dependency-matrix.txt"
        with open(matrix_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_matrix())
        print(f"✓ Matriz: {matrix_file}")

        # Diagrama de ciclos
        cycles_file = output_path / "cycle-diagram.mmd"
        with open(cycles_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_cycle_diagram())
        cycles = self.find_cycles()
        status = f"{len(cycles)} ciclo(s) detectado(s)" if cycles else "sin ciclos"
        print(f"✓ Ciclos: {cycles_file} ({status})")

    def save_impact(self, target: str, output_dir="diagrams"):
        """Guarda el diagrama de impacto transitivo para un módulo específico."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        safe_name = target.replace(':', '_').replace('-', '_')
        impact_file = output_path / f"impact-{safe_name}.mmd"
        with open(impact_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_impact_diagram(target))
        print(f"✓ Impacto: {impact_file}")


def main():
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="Analizador de dependencias entre módulos Android",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Ejemplos:
  python gradle_analyzer.py /ruta/al/proyecto
  python gradle_analyzer.py /ruta/al/proyecto --impact-module common
  python gradle_analyzer.py /ruta/al/proyecto --impact-module feature:payment
"""
    )
    parser.add_argument("path", help="Ruta al directorio raíz del proyecto Android")
    parser.add_argument(
        "--impact-module",
        metavar="MODULE",
        help="Genera diagrama de impacto transitivo para el módulo indicado"
    )
    args = parser.parse_args()

    print("🚀 Analizador de Dependencias via Gradle")
    print("=" * 70)

    analyzer = GradleDependencyAnalyzer(args.path)
    analyzer.scan_modules()
    analyzer.analyze_gradle_dependencies()

    print("\n📊 Generando archivos...")
    print("=" * 70)

    analyzer.save_all()

    if args.impact_module:
        analyzer.save_impact(args.impact_module)

    print("\n" + analyzer.generate_report())

    print("\n" + "=" * 70)
    print("✅ ¡Análisis completado!")
    print("=" * 70)
    print("\n💡 Para visualizar:")
    print("  • PlantUML: https://www.plantuml.com/plantuml/uml/")
    print("  • Mermaid: https://mermaid.live/")


if __name__ == "__main__":
    main()