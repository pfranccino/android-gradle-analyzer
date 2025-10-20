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


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python gradle_analyzer.py <ruta_al_directorio_credit-card>")
        print("\nEjemplo:")
        print("  python gradle_analyzer.py /Users/payalao/Documents/mach/android-mach/credit-card")
        print("\nEl script detectará automáticamente TODOS los módulos en cualquier profundidad.")
        sys.exit(1)
    
    base_path = sys.argv[1]
    
    print("🚀 Analizador de Dependencias via Gradle")
    print("=" * 70)
    
    analyzer = GradleDependencyAnalyzer(base_path)
    analyzer.scan_modules()
    analyzer.analyze_gradle_dependencies()
    
    print("\n📊 Generando archivos...")
    print("=" * 70)
    
    analyzer.save_all()
    
    print("\n" + analyzer.generate_report())
    
    print("\n" + "=" * 70)
    print("✅ ¡Análisis completado!")
    print("=" * 70)
    print("\n💡 Para visualizar:")
    print("  • PlantUML: https://www.plantuml.com/plantuml/uml/")
    print("  • Mermaid: https://mermaid.live/")


if __name__ == "__main__":
    main()