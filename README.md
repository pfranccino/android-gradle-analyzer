# 📊 Android Gradle Dependency Analyzer

Herramientas para analizar y visualizar dependencias entre módulos en proyectos Android multi-módulo.

## 🎯 Características

- ✅ **Análisis automático** de dependencias leyendo archivos `build.gradle` / `build.gradle.kts`
- 🔍 **Detección recursiva** de todos los módulos sin importar la profundidad
- 📈 **Visualización clara** con diagramas PlantUML y Mermaid
- 🎨 **Colores por tipo** de módulo (common, gateway, features)
- 📊 **Dos perspectivas**: dependencias internas y llamadas externas
- 📝 **Reportes detallados** en texto plano

## 🚀 Instalación

### Requisitos

- Python 3.7+
- PlantUML (opcional, para generar imágenes)

### Clonar el repositorio

```bash
git clone https://github.com/pfranccino/android-gradle-analyzer.git
cd android-gradle-analyzer
```

### Instalar PlantUML (opcional)

```bash
# macOS
brew install plantuml

# Ubuntu/Debian
sudo apt install plantuml

# Windows (con Chocolatey)
choco install plantuml
```

## 📖 Uso

### 1. Analizar Dependencias Internas

Analiza las dependencias **dentro** de un módulo específico.

```bash
python3 gradle_analyzer.py <ruta_al_modulo>
```

**Ejemplo:**

```bash
python3 gradle_analyzer.py /Users/tu-usuario/proyecto/payments
```

**Salida:**

- `diagrams/gradle-dependencies.puml` - Diagrama PlantUML
- `diagrams/gradle-dependencies.mmd` - Diagrama Mermaid
- `diagrams/gradle-report.txt` - Reporte detallado

### 2. Analizar Llamadas Externas

Detecta qué módulos externos llaman a tu módulo target.

```bash
python3 external_callers.py <ruta_proyecto> <nombre_modulo>
```

**Ejemplo:**

```bash
python3 external_callers.py /Users/tu-usuario/proyecto payments
```

**Salida:**

- `external-calls/payments-external-calls.puml`
- `external-calls/payments-external-calls.mmd`
- `external-calls/payments-external-report.txt`

### 3. Generar Imágenes

```bash
# Convertir .puml a PNG
plantuml diagrams/gradle-dependencies.puml

# Convertir todos los archivos .puml
plantuml diagrams/*.puml
plantuml external-calls/*.puml

# Generar SVG (escalable)
plantuml -tsvg diagrams/gradle-dependencies.puml
```

## 📊 Ejemplos de Salida

### Diagrama de Dependencias Internas

Muestra cómo los módulos dentro de tu feature dependen unos de otros:

```
┌─────────────┐         ┌─────────────┐
│    home     │ ───────→│   common    │
└─────────────┘         └─────────────┘
       │
       ↓
┌─────────────┐
│  dashboard  │
└─────────────┘
```

### Diagrama de Llamadas Externas

Muestra qué módulos externos (app, otros features) usan tu feature:

```
┌─────────────┐
│     app     │ 🟠
└─────────────┘
       │
       ↓
┌─────────────────────┐
│   my-feature        │
│  ┌──────────┐       │
│  │  home    │ 🟢    │
│  └──────────┘       │
└─────────────────────┘
```

## 🎨 Personalización

### Ajustar Espaciado

Edita `gradle_analyzer.py`, líneas ~195-197:

```python
"skinparam nodesep 100",    # Espacio horizontal (default: 60)
"skinparam ranksep 100",    # Espacio vertical (default: 60)
"skinparam padding 20",     # Espacio interno (default: 10)
```

**Valores sugeridos:**

- **Compacto**: 60, 60, 10
- **Balanceado**: 100, 100, 20
- **Espacioso**: 150, 150, 30

### Agregar Nuevos Tipos de Módulos

Edita la función `get_style()` en `gradle_analyzer.py`:

```python
def get_style(module):
    if module == 'common':
        return ' <<common>>'
    elif 'payment' in module:
        return ' <<payment>>'  # Nuevo tipo
    # ...
```

Luego agrega el color:

```python
"skinparam classBackgroundColor<<payment>> #FFCDD2",
```

## 📋 Estructura del Proyecto

```
android-gradle-analyzer/
├── README.md                  ← Documentación principal
├── LICENSE                    ← Licencia MIT
├── .gitignore                 ← Archivos a ignorar
├── CONTRIBUTING.md            ← Guía para contribuir
├── EXAMPLES.md                ← Ejemplos de uso
├── setup.sh                   ← Script de configuración
├── gradle_analyzer.py         ← Script principal 1
└── external_callers.py        ← Script principal 2
```

## 🔧 Cómo Funciona

### Detección de Módulos

1. Usa `rglob()` para buscar **recursivamente** todos los archivos `build.gradle*`
2. Convierte paths a nombres de módulos: `payments/home` → `payments:home`
3. Mapea cada módulo encontrado

### Extracción de Dependencias

1. Lee el contenido completo de cada `build.gradle`
2. Aplica **regex** para encontrar patrones como:
   ```kotlin
   implementation project(path: ':my-feature:common')
   api(project(":my-feature:gateway"))
   ```
3. Normaliza los paths y almacena las relaciones

### Generación de Diagramas

1. Clasifica módulos por tipo (common, gateway, features)
2. Aplica colores según la clasificación
3. Genera código PlantUML/Mermaid con las dependencias

## 🤝 Contribuir

Las contribuciones son bienvenidas! Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -m 'Agrega nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## 📝 Casos de Uso

- ✅ Documentar arquitectura de proyectos multi-módulo
- ✅ Detectar dependencias circulares
- ✅ Identificar módulos altamente acoplados
- ✅ Auditar dependencias antes de refactorizar
- ✅ Onboarding de nuevos desarrolladores
- ✅ Revisiones de arquitectura

## 🐛 Troubleshooting

### Error: "No se encontró gradle para: [módulo]"

**Causa**: El módulo no tiene archivo `build.gradle` o `build.gradle.kts`

**Solución**: Verifica que el path sea correcto y que el módulo tenga un archivo gradle.

### Diagrama se ve muy apretado

**Solución**: Aumenta los valores de espaciado:

```python
"skinparam nodesep 150",
"skinparam ranksep 150",
"skinparam padding 30",
```

### No detecta algunas dependencias

**Causa**: El formato del gradle puede ser diferente

**Solución**: Verifica los patrones regex en `_parse_gradle_file()` y agrega el formato que usa tu proyecto.

## 📄 Licencia

MIT License - ver [LICENSE](LICENSE) para más detalles.

## 🙏 Agradecimientos

- [PlantUML](https://plantuml.com/) - Generación de diagramas UML
- [Mermaid](https://mermaid.js.org/) - Diagramas en Markdown

## 📧 Contacto

¿Preguntas o sugerencias? Abre un [issue](https://github.com/pfranccino/android-gradle-analyzer/issues)

---

⭐ Si este proyecto te fue útil, considera darle una estrella!
