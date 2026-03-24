# 📊 Android Gradle Dependency Analyzer

Herramientas para analizar y visualizar dependencias entre módulos en proyectos Android multi-módulo.

## 🎯 Características

- ✅ **Análisis automático** de dependencias leyendo archivos `build.gradle` / `build.gradle.kts`
- 🔍 **Detección recursiva** de todos los módulos sin importar la profundidad
- 📈 **Visualización clara** con diagramas PlantUML y Mermaid
- 🎨 **Colores por tipo** de módulo (common, gateway, features)
- 📊 **Dos perspectivas**: dependencias internas y llamadas externas
- 📝 **Reportes detallados** en texto plano
- 🗂️ **Matriz de dependencias (DSM)** para detectar acoplamiento de un vistazo
- 🔴 **Detección de ciclos** con diagrama Mermaid que los resalta en rojo
- 🎯 **Análisis de impacto transitivo** para saber qué módulos afecta un cambio
- 🏗️ **Diagrama de capas arquitectónicas** basado en topological sort

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

**Salida generada automáticamente:**

| Archivo | Descripción |
|---------|-------------|
| `diagrams/gradle-dependencies.puml` | Diagrama PlantUML de dependencias |
| `diagrams/gradle-dependencies.mmd` | Diagrama Mermaid de dependencias |
| `diagrams/gradle-report.txt` | Reporte detallado en texto |
| `diagrams/dependency-matrix.txt` | Matriz de dependencias (DSM) |
| `diagrams/cycle-diagram.mmd` | Diagrama de ciclos (rojo = problema) |
| `diagrams/layers-diagram.mmd` | Diagrama de capas arquitectónicas |

**Análisis de impacto (opcional):**

```bash
python3 gradle_analyzer.py /ruta/proyecto --impact-module common
python3 gradle_analyzer.py /ruta/proyecto --impact-module feature:payment
```

Genera `diagrams/impact-<modulo>.mmd` con todos los módulos afectados si ese módulo cambia.

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

### Matriz de Dependencias (DSM)

Tabla cruzada donde `X` indica que la fila depende de la columna. Útil para detectar acoplamiento excesivo de un vistazo:

```
MATRIZ DE DEPENDENCIAS (DSM)
----------------------------------------------------
                   app  common  core  network  payment
----------------------------------------------------
app             |   ·                           X
common          |           ·
core            |                   ·
feature:payment |           X       X       ·
network         |                   X       ·
----------------------------------------------------
```

> Un módulo que tiene muchas `X` en su fila depende de muchos otros — candidato a simplificarse.

### Diagrama de Ciclos

Detecta dependencias circulares y las resalta en rojo. Los nodos en ciclo aparecen marcados con `⚠️` y los arcos del ciclo se dibujan en rojo:

```
graph TD
  ⚠️ ModuloA --> ⚠️ ModuloB --> ⚠️ ModuloC --> ⚠️ ModuloA  (🔴 ciclo)
  ModuloD -.-> ModuloA
```

> Un ciclo en rojo es una deuda técnica que impide compilación incremental y dificulta el testing aislado.

### Diagrama de Impacto Transitivo

Dado un módulo objetivo, muestra todos los módulos que serían afectados si ese módulo cambia. Los nodos afectados se colorean en naranja y muestran su distancia (`d=1` directo, `d=2` indirecto, etc.):

```bash
python3 gradle_analyzer.py /ruta/proyecto --impact-module common
```

```
graph TD
  🎯 common
  📦 feature:payment (d=1)
  📦 feature:home (d=1)
  📦 app (d=2)
```

> Antes de refactorizar un módulo, genera su diagrama de impacto para dimensionar el alcance del cambio.

### Diagrama de Capas Arquitectónicas

Organiza los módulos en capas calculadas por **topological sort**: los módulos sin dependencias (Foundation) quedan en Layer 0 y los que dependen de todo quedan en la capa más alta (App). Las etiquetas `Foundation` y `App` se asignan automáticamente solo a módulos con nombres universales (`core`, `common`, `base`, `util`, `shared`, `app`):

```
graph TD
  subgraph "Layer 0 · Foundation"
    🏗️ core
    🏗️ common
  end
  subgraph "Layer 1"
    📦 network
    🏗️ feature:core
  end
  subgraph "Layer 2"
    📦 feature:payment
    📦 feature:home
  end
  subgraph "Layer 3 · App"
    📱 app
  end
```

> Si ves flechas que van hacia capas superiores (dependencias inversas), es una señal de acoplamiento incorrecto en la arquitectura.

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
