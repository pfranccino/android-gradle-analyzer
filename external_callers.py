#!/usr/bin/env python3
"""
Analizador de llamadas externas a módulos
Detecta qué módulos externos (app, otros features) llaman a tus módulos
"""

import re
from pathlib import Path
from collections import defaultdict


class ExternalCallersAnalyzer:
    def __init__(self, project_root, target_module):
        """
        Args:
            project_root: Ruta raíz del proyecto (ej: /path/to/android-mach)
            target_module: Módulo a analizar (ej: credit-card)
        """
        self.project_root = Path(project_root)
        self.target_module = target_module
        self.target_path = self.project_root / target_module
        
        # Módulos dentro del target
        self.internal_modules = []
        
        # Módulos externos que llaman al target
        self.external_callers = defaultdict(lambda: defaultdict(set))
        # Estructura: {caller_module: {target_submodule: set()}}
        
        # Todos los módulos del proyecto
        self.all_modules = []
    
    def scan_all_modules(self):
        """Escanea TODOS los módulos del proyecto"""
        print(f"📁 Escaneando proyecto completo: {self.project_root}\n")
        
        # Buscar todos los build.gradle en el proyecto
        gradle_files = list(self.project_root.rglob("build.gradle*"))
        
        for gradle_file in sorted(gradle_files):
            module_dir = gradle_file.parent
            
            try:
                rel_path = module_dir.relative_to(self.project_root)
                
                if str(rel_path) == '.':
                    continue
                
                module_name = str(rel_path).replace('/', ':').replace('\\', ':')
                self.all_modules.append(module_name)
                
                # Clasificar si es interno o externo
                if module_name.startswith(self.target_module):
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
        
        # Para cada módulo externo, revisar sus dependencias
        for module in self.all_modules:
            # Saltar módulos internos
            if module.startswith(self.target_module):
                continue
            
            # Buscar su archivo gradle
            module_path = self.project_root / module.replace(':', '/')
            gradle_file = module_path / "build.gradle.kts"
            if not gradle_file.exists():
                gradle_file = module_path / "build.gradle"
            
            if gradle_file.exists():
                self._check_gradle_for_calls(module, gradle_file)
        
        total_calls = sum(
            len(targets) 
            for targets in self.external_callers.values()
        )
        
        print(f"\n✓ Análisis completado")
        print(f"✓ {len(self.external_callers)} módulos externos llaman a {self.target_module}")
        print(f"✓ {total_calls} conexiones externas detectadas\n")
        
        return self
    
    def _check_gradle_for_calls(self, caller_module, gradle_file):
        """Revisa si un módulo externo llama a algún módulo interno"""
        try:
            with open(gradle_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Patrones para detectar dependencias
            patterns = [
                r'implementation\s*\(\s*project\s*\(\s*["\']([^"\']+)["\']\s*\)\s*\)',
                r'api\s*\(\s*project\s*\(\s*["\']([^"\']+)["\']\s*\)\s*\)',
                r'implementation\s+project\s*\(\s*["\']([^"\']+)["\']\s*\)',
                r'api\s+project\s*\(\s*["\']([^"\']+)["\']\s*\)',
                r'implementation\s+project\s*\(\s*path\s*:\s*["\']([^"\']+)["\']\s*\)',
                r'api\s+project\s*\(\s*path\s*:\s*["\']([^"\']+)["\']\s*\)',
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    project_path = match.group(1)
                    
                    # Verificar si llama a algún módulo del target
                    if self.target_module in project_path:
                        # Normalizar el path
                        if project_path.startswith(':'):
                            project_path = project_path[1:]
                        
                        # Extraer la parte después del target_module
                        parts = project_path.split(':')
                        if self.target_module in parts:
                            idx = parts.index(self.target_module)
                            if idx + 1 < len(parts):
                                target_submodule = ':'.join(parts[idx:])
                            else:
                                target_submodule = self.target_module
                            
                            # Guardar la llamada
                            self.external_callers[caller_module][target_submodule].add(gradle_file.name)
                            print(f"  🔗 {caller_module} → {target_submodule}")
                            
        except Exception as e:
            pass
    
    def generate_plantuml(self):
        """Genera diagrama PlantUML de llamadas externas"""
        package_name = self.target_module
        
        lines = [
            "@startuml",
            "",
            "skinparam packageStyle rectangle",
            "skinparam linetype ortho",
            "skinparam backgroundColor white",
            "",
            "' Colores",
            "skinparam classBackgroundColor<<internal>> #E8F5E9",
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
        
        # Módulos internos que son llamados
        called_modules = set()
        for targets in self.external_callers.values():
            called_modules.update(targets.keys())
        
        for module in sorted(called_modules):
            # Extraer solo la parte después de target_module
            if ':' in module:
                display_name = module.split(':', 1)[1]
            else:
                display_name = module
            
            module_id = module.replace(':', '_').replace('-', '_')
            lines.append(f'  class "{display_name}" as {module_id} <<internal>>')
        
        lines.append("}")
        lines.append("")
        
        # Módulos externos
        lines.append("' Módulos externos que llaman")
        for caller in sorted(self.external_callers.keys()):
            caller_id = caller.replace(':', '_').replace('-', '_')
            lines.append(f'class "{caller}" as {caller_id} <<external>>')
        
        lines.append("")
        lines.append("' Llamadas externas")
        
        # Dependencias
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
        
        lines = [
            "graph LR",
            f'  subgraph {package_name.replace("-", "_")}["{package_name} 📦"]',
        ]
        
        # Módulos internos llamados
        called_modules = set()
        for targets in self.external_callers.values():
            called_modules.update(targets.keys())
        
        for module in sorted(called_modules):
            if ':' in module:
                display_name = module.split(':', 1)[1]
            else:
                display_name = module
            
            module_id = module.replace(':', '_').replace('-', '_')
            lines.append(f'    {module_id}["🟢 {display_name}"]')
        
        lines.append("  end")
        lines.append("")
        
        # Módulos externos
        for caller in sorted(self.external_callers.keys()):
            caller_id = caller.replace(':', '_').replace('-', '_')
            lines.append(f'  {caller_id}["🟠 {caller}"]')
        
        lines.append("")
        
        # Dependencias
        for caller in sorted(self.external_callers.keys()):
            caller_id = caller.replace(':', '_').replace('-', '_')
            for target in sorted(self.external_callers[caller].keys()):
                target_id = target.replace(':', '_').replace('-', '_')
                lines.append(f"  {caller_id} -.->|uses| {target_id}")
        
        lines.append("")
        lines.append("  classDef internal fill:#E8F5E9,stroke:#2E7D32")
        lines.append("  classDef external fill:#FFE0B2,stroke:#E65100")
        
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
                targets = self.external_callers[caller]
                for target in sorted(targets.keys()):
                    lines.append(f"  └─→ {target}")
        
        # Estadísticas
        lines.append("\n" + "=" * 70)
        lines.append("ESTADÍSTICAS")
        lines.append("=" * 70)
        
        # Módulos más llamados
        call_count = defaultdict(int)
        for targets in self.external_callers.values():
            for target in targets.keys():
                call_count[target] += 1
        
        if call_count:
            lines.append("\nMódulos más llamados desde fuera:")
            for module, count in sorted(call_count.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"  • {module}: {count} llamada(s)")
        
        # Módulos que NO son llamados
        uncalled = set(self.internal_modules) - set(call_count.keys())
        if uncalled:
            lines.append(f"\nMódulos NO llamados externamente ({len(uncalled)}):")
            for module in sorted(uncalled)[:10]:  # Mostrar solo primeros 10
                lines.append(f"  • {module}")
            if len(uncalled) > 10:
                lines.append(f"  ... y {len(uncalled) - 10} más")
        
        return "\n".join(lines)
    
    def save_all(self, output_dir="external-calls"):
        """Guarda todos los archivos generados"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # PlantUML
        plantuml_file = output_path / f"{self.target_module}-external-calls.puml"
        with open(plantuml_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_plantuml())
        print(f"✓ PlantUML: {plantuml_file}")
        
        # Mermaid
        mermaid_file = output_path / f"{self.target_module}-external-calls.mmd"
        with open(mermaid_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_mermaid())
        print(f"✓ Mermaid: {mermaid_file}")
        
        # Reporte
        report_file = output_path / f"{self.target_module}-external-report.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_report())
        print(f"✓ Reporte: {report_file}")


def main():
    import sys
    
    if len(sys.argv) < 3:
        print("Uso: python external_callers.py <ruta_proyecto> <modulo_target>")
        print("\nEjemplo:")
        print("  python external_callers.py /Users/payalao/Documents/mach/android-mach credit-card")
        print("\nEsto analizará qué módulos externos (app, otros features) llaman a credit-card")
        sys.exit(1)
    
    project_root = sys.argv[1]
    target_module = sys.argv[2]
    
    print("🚀 Analizador de Llamadas Externas")
    print("=" * 70)
    
    analyzer = ExternalCallersAnalyzer(project_root, target_module)
    analyzer.scan_all_modules()
    analyzer.analyze_external_calls()
    
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