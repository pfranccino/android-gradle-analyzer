# 📊 Android Gradle Dependency Analyzer

Herramientas para analizar y visualizar dependencias entre módulos en proyectos Android multi-módulo.

## 🎯 Características

- ✅ **Análisis automático** de dependencias leyendo archivos `build.gradle` / `build.gradle.kts`
- 🔍 **Detección recursiva** de todos los módulos sin importar la profundidad
- 📈 **Visualización clara** con diagramas PlantUML y Mermaid
- 🎨 **Colores por tipo** de módulo (common, gateway, features)
- 📊 **Dos perspectivas**: dependencias internas y llamadas externas
- 📝 **Reportes detallados** en texto plano
- ⚠️ **Detección de ciclos** de dependencia
- 🔭 **Múltiples scopes**: `implementation`, `api`, `kapt`, `compileOnly`, `testImplementation` y más
- 🏥 **Análisis de sanidad** con métricas de acoplamiento y score configurable
- ⚙️ **Configuración personalizable** via `analyzer_config.json`

## 🚀 Instalación

### Requisitos

- Python 3.7+
- PlantUML (opcional, para generar imágenes PNG/SVG)

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
python3 gradle_analyzer.py /ruta/a/tu/proyecto/payments
```

**Flags opcionales:**

| Flag | Descripción | Default |
|---|---|---|
| `--format plantuml\|mermaid\|all` | Formato de salida | `all` |
| `--output-dir <dir>` | Directorio donde guardar los archivos | `diagrams` |
| `--exclude <module>` | Excluir un módulo (puede repetirse) | — |
| `--config <path>` | Ruta a un `analyzer_config.json` personalizado | auto-detect |

**Ejemplos con flags:**

```bash
# Solo generar Mermaid
python3 gradle_analyzer.py /ruta/a/tu/proyecto/payments --format mermaid

# Excluir módulos de test
python3 gradle_analyzer.py /ruta/a/tu/proyecto/payments --exclude test-utils --exclude mocks

# Usar directorio de salida personalizado (se crean los padres automáticamente)
python3 gradle_analyzer.py /ruta/a/tu/proyecto/payments --output-dir docs/diagrams
```

**Salida:**

- `diagrams/gradle-dependencies.puml` — Diagrama PlantUML
- `diagrams/gradle-dependencies.mmd` — Diagrama Mermaid
- `diagrams/gradle-report.txt` — Reporte detallado

---

### 2. Analizar Llamadas Externas

Detecta qué módulos externos llaman a tu módulo target.

```bash
python3 external_callers.py <ruta_proyecto> <nombre_modulo>
```

**Ejemplo:**

```bash
python3 external_callers.py /ruta/a/tu/android-project payments
```

**Flags opcionales:**

| Flag | Descripción | Default |
|---|---|---|
| `--format plantuml\|mermaid\|all` | Formato de salida | `all` |
| `--output-dir <dir>` | Directorio donde guardar los archivos | `external-calls` |
| `--config <path>` | Ruta a un `analyzer_config.json` personalizado | auto-detect |

**Salida:**

- `external-calls/payments-external-calls.puml`
- `external-calls/payments-external-calls.mmd`
- `external-calls/payments-external-report.txt`

---

### 3. Analizar Sanidad de Dependencias

Mide la **salud arquitectónica** del módulo calculando métricas de acoplamiento y detectando anti-patrones. Genera un score de 0 a 100 con explicación de cada problema encontrado.

```bash
python3 gradle_sanity.py <ruta_al_modulo>
```

**Ejemplo:**

```bash
python3 gradle_sanity.py /ruta/a/tu/proyecto/payments
```

**Flags opcionales:**

| Flag | Descripción | Default |
|---|---|---|
| `--output-dir <dir>` | Directorio donde guardar el reporte | `sanity` |
| `--config <path>` | Ruta a un `analyzer_config.json` personalizado | auto-detect |

**Salida:** `sanity/sanity-report.txt`

**Ejemplo de reporte:**

```
MÉTRICAS POR MÓDULO

  Módulo          Ca   Ce     I    Estado
  ──────────────  ───  ───  ────   ──────────────────────────
  common           3    0   0.00   🟢 Estable
  gateway          1    1   0.50   🟡 Moderadamente estable
  home             1    2   0.67   🟠 Moderadamente inestable
  ui               0    2   1.00   🔴 Inestable (módulo hoja)

VIOLACIONES DETECTADAS

🔴 CICLOS (0)            — sin ciclos ✅
🟠 VIOLACIONES SDP (0)   — sin violaciones ✅
🟡 API INNECESARIO (1)   — ui usa api pero Ca=0
🔵 VERSIONES HARD. (2)   — gateway, home

PUNTUACIÓN FINAL: 91 / 100  🟢 Excelente
```

**¿Qué mide cada columna?**

| Columna | Significado |
|---|---|
| **Ca** | Cuántos módulos dependen de este (flechas que llegan). Alto en `common`, `core`. |
| **Ce** | Cuántos módulos usa este (flechas que salen). Alto en `app`, features de alto nivel. |
| **I** | `Ce / (Ce + Ca)`. 0 = muy estable, 1 = muy inestable. Lo importante es la dirección: las dependencias deben ir de I alto → I bajo. |

**¿Qué detecta?**

| Problema | Penalización default | Descripción |
|---|---|---|
| Ciclo | -20 pts | A depende de B y B depende de A |
| Violación SDP | -10 pts | Módulo estable (I bajo) depende de uno inestable (I alto) |
| `api` innecesario | -5 pts | Usa `api` pero Ca=0, nadie consume esas deps transitivas |
| Fan-out excesivo | -3 pts | Ce supera el umbral (default: 5) |
| Versión hardcodeada | -2 pts | `"lib:x:1.2.3"` en lugar de Version Catalog |

Los pesos son **configurables** en `analyzer_config.json` bajo `sanity_weights`.

---

### 4. Generar Imágenes

```bash
# Convertir .puml a PNG
plantuml diagrams/gradle-dependencies.puml

# Convertir todos los archivos .puml
plantuml diagrams/*.puml
plantuml external-calls/*.puml

# Generar SVG (escalable)
plantuml -tsvg diagrams/gradle-dependencies.puml
```

## ⚠️ Detección de Ciclos

Los ciclos de dependencia se detectan automáticamente y se muestran al inicio del reporte:

```
======================================================================
⚠️  CICLOS DETECTADOS (1)
======================================================================
  Ciclo 1: home → common → home
```

Los módulos involucrados en un ciclo también aparecen **marcados en rojo** en los diagramas PlantUML y Mermaid.

## 🔭 Dependency Scopes Soportados

| Scope | Categoría visual |
|---|---|
| `api`, `implementation`, `compileOnly` | Flecha sólida (compile) |
| `kapt`, `annotationProcessor` | Flecha punteada (build/procesadores) |
| `testImplementation`, `androidTestImplementation`, `debugImplementation`, `releaseImplementation`, `runtimeOnly`, `testRuntimeOnly` | Flecha punteada con label (test/debug) |

En el reporte de texto se muestra el scope exacto por cada dependencia:

```
📦 home
  → common   [implementation]
  → common   [kapt]
  → gateway  [testImplementation]
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

## ⚙️ Configuración Personalizada

Puedes personalizar colores, íconos y estilos creando un archivo `analyzer_config.json` en el directorio desde donde ejecutas la herramienta. El archivo es **completamente opcional** — sin él, la herramienta usa defaults genéricos para cualquier proyecto Android.

El repositorio incluye `analyzer_config.example.json` con todos los campos disponibles documentados. Para activarlo:

```bash
cp analyzer_config.example.json analyzer_config.json
```

**Ejemplo de configuración parcial:**

```json
{
  "icons": {
    "payment": "💸",
    "cart":    "🛒",
    "auth":    "🔐"
  },
  "colors": {
    "cycle": "#FF0000"
  }
}
```

Solo necesitas incluir los campos que quieras cambiar — el resto usa los defaults.

**Orden de búsqueda del config:**
1. `--config <path>` explícito
2. `analyzer_config.json` en el directorio de trabajo actual
3. Defaults internos

## 🎨 Personalización del Código

### Ajustar Espaciado

Edita `gradle_analyzer.py`, sección `generate_plantuml()`:

```python
"skinparam nodesep 150",    # Espacio horizontal (default: 150)
"skinparam ranksep 150",    # Espacio vertical  (default: 150)
"skinparam padding 30",     # Espacio interno   (default: 30)
```

**Valores sugeridos:**

- **Compacto**: 60, 60, 10
- **Balanceado**: 100, 100, 20
- **Espacioso**: 150, 150, 30

## 📋 Estructura del Proyecto

```
android-gradle-analyzer/
├── README.md                  ← Documentación principal
├── LICENSE                    ← Licencia MIT
├── .gitignore
├── CONTRIBUTING.md            ← Guía para contribuir
├── EXAMPLES.md                ← Ejemplos de uso
├── setup.sh                   ← Script de configuración
├── analyzer_utils.py          ← Utilidades compartidas
├── analyzer_config.example.json ← Configuración de ejemplo (cp → analyzer_config.json para activar)
├── gradle_analyzer.py           ← Script 1: dependencias internas + diagramas
├── external_callers.py          ← Script 2: qué módulos externos llaman a este
└── gradle_sanity.py             ← Script 3: métricas de acoplamiento y score de sanidad
```

## 🔧 Cómo Funciona

### Detección de Módulos

1. Usa `rglob()` para buscar **recursivamente** todos los archivos `build.gradle*`
2. Convierte paths a nombres de módulos: `payments/home` → `payments:home`
3. Mapea cada módulo encontrado

### Extracción de Dependencias

1. Lee el contenido completo de cada `build.gradle`
2. Aplica **regex** para encontrar todos los scopes:
   ```kotlin
   implementation project(":my-feature:common")
   api(project(":my-feature:gateway"))
   kapt project(':my-feature:common')
   ```
3. Normaliza los paths y almacena las relaciones por scope

### Generación de Diagramas

1. Clasifica módulos por tipo (common, gateway, features)
2. Aplica colores según la clasificación
3. Genera código PlantUML/Mermaid con las dependencias agrupadas por categoría visual
4. Marca en rojo los módulos involucrados en ciclos

## 🤝 Contribuir

Las contribuciones son bienvenidas! Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -m 'Agrega nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## 📝 Casos de Uso

- ✅ Documentar arquitectura de proyectos multi-módulo
- ✅ Detectar dependencias circulares y violaciones SDP
- ✅ Medir y mejorar la salud arquitectónica con score de sanidad
- ✅ Identificar módulos altamente acoplados
- ✅ Auditar dependencias antes de refactorizar
- ✅ Onboarding de nuevos desarrolladores
- ✅ Revisiones de arquitectura

## 🐛 Troubleshooting

### Error: "No se encontró gradle para: [módulo]"

**Causa**: El módulo no tiene archivo `build.gradle` o `build.gradle.kts`

**Solución**: Verifica que el path sea correcto y que el módulo tenga un archivo gradle.

### Diagrama se ve muy apretado

**Solución**: Aumenta los valores de espaciado en `generate_plantuml()`:

```python
"skinparam nodesep 200",
"skinparam ranksep 200",
"skinparam padding 40",
```

### No detecta algunas dependencias

**Causa**: El formato del gradle puede ser diferente al estándar

**Solución**: Verifica los patrones regex en `analyzer_utils.py` (constante `DEPENDENCY_SCOPES`) y agrega el formato que usa tu proyecto.

## 📚 Referencias — Análisis de Sanidad

Las métricas implementadas en `gradle_sanity.py` están basadas en fuentes académicas e industriales consolidadas, no en valores inventados.

### Métricas de acoplamiento (Ca, Ce, I)

Definidas por **Robert C. Martin** en *"Agile Software Development: Principles, Patterns, and Practices"* (2002), capítulo de *Package Design Principles*. Son las mismas métricas que usan herramientas como **SonarQube**, **NDepend** y **Structure101**.

- **Ca** (Afferent Coupling) y **Ce** (Efferent Coupling): métricas clásicas de acoplamiento entre módulos/paquetes.
- **I** (Instability = Ce / Ce+Ca): mide la resistencia al cambio de un módulo.

### SDP — Stable Dependencies Principle

También de Robert C. Martin, parte de los *Package Principles* (junto a SRP, OCP, etc.). Establece que **las dependencias deben apuntar en la dirección de la estabilidad**. Es un principio binario: o se viola o no. El umbral de 0.3 usado para detectarlo es configurable y no forma parte del estándar original.

> Referencia: [codinghelmet.com — How to Measure Module Coupling and Instability](https://codinghelmet.com/articles/how-to-measure-module-coupling-and-instability-using-ndepend)

### Detección de ciclos

Los ciclos de dependencia son universalmente considerados el problema más grave en arquitectura de módulos. La detección usa **DFS con coloreo de nodos** (blanco/gris/negro), algoritmo estándar de teoría de grafos para detección de back-edges en grafos dirigidos.

### DAGP — Dependency Analysis Gradle Plugin

Herramienta de referencia para análisis de dependencias en proyectos Gradle/Android. Inspiró la detección de scopes mal declarados (`api` vs `implementation`).

> Repositorio: [github.com/autonomousapps/dependency-analysis-gradle-plugin](https://github.com/autonomousapps/dependency-analysis-gradle-plugin)

### Sobre el score (0–100)

El sistema de puntuación **no es un estándar externo**. Es un mecanismo orientativo con defaults razonables, diseñado para ser ajustado por cada equipo según su contexto. Los pesos son configurables en `analyzer_config.json` bajo `sanity_weights`. Herramientas como SonarQube utilizan un sistema similar pero expresado en "deuda técnica" (horas de trabajo) en lugar de puntos.

---

## 📄 Licencia

MIT License - ver [LICENSE](LICENSE) para más detalles.

## 🙏 Agradecimientos

- [PlantUML](https://plantuml.com/) - Generación de diagramas UML
- [Mermaid](https://mermaid.js.org/) - Diagramas en Markdown

## 📧 Contacto

¿Preguntas o sugerencias? Abre un [issue](https://github.com/pfranccino/android-gradle-analyzer/issues)

---

⭐ Si este proyecto te fue útil, considera darle una estrella!
