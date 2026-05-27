<div align="center">

# 📊 Android Gradle Dependency Analyzer

Herramientas para **analizar, visualizar y medir la salud** de las dependencias entre módulos en proyectos Android multi-módulo.

[![Python](https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/github/actions/workflow/status/pfranccino/android-gradle-analyzer/release.yml?branch=main&label=tests)](https://github.com/pfranccino/android-gradle-analyzer/actions/workflows/release.yml)
[![Release](https://img.shields.io/github/v/release/pfranccino/android-gradle-analyzer?label=release)](https://github.com/pfranccino/android-gradle-analyzer/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PlantUML](https://img.shields.io/badge/diagrams-PlantUML%20%C2%B7%20Mermaid-orange)](https://plantuml.com)

<img src="docs/preview.svg" alt="Vista previa del analizador en consola" width="780"/>

</div>

---

## ⚡ Quick start

```bash
# Recomendado · instalación global con pipx (última versión)
pipx install git+https://github.com/pfranccino/android-gradle-analyzer.git

# Versión específica
pipx install git+https://github.com/pfranccino/android-gradle-analyzer.git@v1.0.0
pipx install git+https://github.com/pfranccino/android-gradle-analyzer.git@v0.1.0

# Ver versión instalada
gradle-analyzer-menu --version

# 1 · Dependencias internas de un módulo
gradle-analyzer /ruta/a/tu/proyecto/payments

# También podés usar . si ya estás parado en el módulo
cd /ruta/a/tu/proyecto/payments
gradle-analyzer .

# 2 · Quién llama a un módulo desde fuera
gradle-externals /ruta/a/tu/proyecto payments

# 3 · Score de sanidad (Ca/Ce/I, ciclos, anti-patrones)
gradle-sanity /ruta/a/tu/proyecto/payments
gradle-sanity .   # equivalente si ya estás en el módulo

# 4 · Impacto de cambios — qué se rompe si cambio X
gradle-impact /ruta/a/tu/proyecto payments:common
```

<details>
<summary><b>Alternativa · clonar el repo</b> (para desarrollo o contribuir)</summary>

```bash
git clone https://github.com/pfranccino/android-gradle-analyzer.git
cd android-gradle-analyzer
pip install -r requirements.txt
python3 gradle_analyzer.py /ruta/a/tu/proyecto/payments
```

</details>

---

## 🎛️ Modo interactivo

Un único comando con dashboard, autodetección de módulos, navegación con teclado y export a HTML / Markdown / ZIP.

```bash
gradle-analyzer-menu
```

<div align="center">
<img src="docs/preview-menu.svg" alt="Vista previa del menú interactivo" width="780"/>
</div>

**Modo no-interactivo (CI/scripts):**
```bash
gradle-analyzer-menu --quick sanity /ruta/proyecto
gradle-analyzer-menu --version
```

---

## ✨ Qué hace

<table>
<tr>
<td width="25%" valign="top">

### 🔍 Dependencias internas
Lee `build.gradle` / `build.gradle.kts` recursivamente y dibuja cómo dependen los módulos entre sí.

**Salida** · PlantUML · Mermaid · reporte de texto

</td>
<td width="25%" valign="top">

### 🌐 Llamadas externas
Detecta qué módulos de **fuera** de tu feature lo están consumiendo. Útil para refactors seguros.

**Salida** · PlantUML · Mermaid · reporte de texto

</td>
<td width="25%" valign="top">

### 🏥 Sanidad arquitectónica
Métricas Ca/Ce/I, detección de ciclos, violaciones SDP y score 0–100 con explicación.

**Salida** · reporte detallado · JSON

</td>
<td width="25%" valign="top">

### 💥 Impacto de cambios
Dado un módulo, muestra qué otros módulos se romperían si cambia (BFS sobre el grafo invertido de dependencias).

**Salida** · PlantUML · Mermaid · reporte de texto

</td>
</tr>
</table>

### Características destacadas

- ✅ **Detección recursiva** sin importar la profundidad de los módulos
- 📋 **`settings.gradle.kts` / `settings.gradle`** — si existe, se usa como fuente de verdad para los módulos
- 🎨 **Colores por tipo** (common, gateway, features)
- ⚠️ **Detección automática de ciclos**
- 🔭 **Scopes soportados:** `implementation`, `api`, `kapt`, `compileOnly`, `testImplementation`, y más
- ⚙️ **Configuración personalizable** via `analyzer_config.json`
- 🤫 **`--quiet`** en todos los CLIs para suprimir output de progreso
- 📄 **`--json`** en todos los CLIs para salida JSON (ideal para CI/CD)
- 🚦 **`--fail-on-cycle` / `--fail-on-score-below N`** en `gradle-sanity` para integración con CI

---

## 📖 Uso

<details>
<summary><b>1. Analizar dependencias internas</b></summary>

```bash
gradle-analyzer <ruta_al_modulo>
```

| Flag | Descripción | Default |
|---|---|---|
| `--format plantuml\|mermaid\|all` | Formato de salida | `all` |
| `--output-dir <dir>` | Directorio de salida | `diagrams` |
| `--exclude <module>` | Excluir un módulo (puede repetirse) | — |
| `--config <path>` | Ruta a `analyzer_config.json` personalizado | auto-detect |
| `--quiet` | Suprime output de progreso | off |
| `--json` | Salida JSON a stdout | off |

**Ejemplos:**

```bash
# Solo Mermaid
gradle-analyzer /ruta/proyecto/payments --format mermaid

# Excluir módulos de test
gradle-analyzer /ruta/proyecto/payments --exclude test-utils --exclude mocks

# Output personalizado
gradle-analyzer /ruta/proyecto/payments --output-dir docs/diagrams
```

**Genera:**
- `diagrams/gradle-dependencies.puml`
- `diagrams/gradle-dependencies.mmd`
- `diagrams/gradle-report.txt`

</details>

<details>
<summary><b>2. Analizar llamadas externas</b></summary>

```bash
gradle-externals <ruta_proyecto> <nombre_modulo>
```

| Flag | Descripción | Default |
|---|---|---|
| `--format plantuml\|mermaid\|all` | Formato de salida | `all` |
| `--output-dir <dir>` | Directorio de salida | `external-calls` |
| `--config <path>` | Config personalizado | auto-detect |
| `--quiet` | Suprime output de progreso | off |
| `--json` | Salida JSON a stdout | off |

**Genera:**
- `external-calls/<modulo>-external-calls.puml`
- `external-calls/<modulo>-external-calls.mmd`
- `external-calls/<modulo>-external-report.txt`

</details>

<details>
<summary><b>3. Analizar sanidad arquitectónica</b></summary>

```bash
gradle-sanity <ruta_al_modulo>
```

| Flag | Descripción | Default |
|---|---|---|
| `--output-dir <dir>` | Directorio de salida | `sanity` |
| `--config <path>` | Config personalizado | auto-detect |
| `--quiet` | Suprime output de progreso | off |
| `--json` | Salida JSON a stdout | off |
| `--fail-on-cycle` | `exit 1` si se detecta algún ciclo | off |
| `--fail-on-score-below N` | `exit 1` si el score es menor a N | off |

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
| **Ca** | Cuántos módulos dependen de éste (fan-in). Alto en `common`, `core`. |
| **Ce** | De cuántos depende éste (fan-out). Alto en `app` o features de alto nivel. |
| **I** | `Ce / (Ce + Ca)`. 0 = muy estable, 1 = muy inestable. |

**¿Qué detecta?**

| Problema | Penalización default | Descripción |
|---|---|---|
| Ciclo | −20 pts | A depende de B y B depende de A |
| Violación SDP | −10 pts | Estable depende de inestable |
| `api` innecesario | −5 pts | Usa `api` pero `Ca=0` |
| Fan-out excesivo | −3 pts | `Ce` supera el umbral (default: 5) |
| Versión hardcodeada | −2 pts | `"lib:x:1.2.3"` en vez de Version Catalog |

Los pesos son configurables en `analyzer_config.json` bajo `sanity_weights`.

</details>

<details>
<summary><b>4. Analizar impacto de cambios</b></summary>

```bash
gradle-impact <ruta_proyecto> <modulo>
```

Responde: **"¿qué módulos se rompen si cambio este módulo?"**

Construye el grafo invertido de dependencias y hace BFS desde el módulo target, asignando un nivel a cada módulo impactado (1 = directo, 2 = transitivo, etc.).

| Flag | Descripción | Default |
|---|---|---|
| `--format plantuml\|mermaid\|all` | Formato de salida | `all` |
| `--output-dir <dir>` | Directorio de salida | `impact` |
| `--config <path>` | Config personalizado | auto-detect |
| `--quiet` | Suprime output de progreso | off |
| `--json` | Salida JSON a stdout | off |

**Ejemplo de reporte:**

```
IMPACTO DE CAMBIOS EN: PAYMENTS:COMMON

Proyecto      : /ruta/proyecto
Módulo        : payments:common
Total módulos : 12

  Nivel 1 — dependientes directos (2):
    • payments:home
    • payments:checkout

  Nivel 2 — dependientes transitivos (2):
    • payments:summary
    • app

  🔥 Impacto total: 4 módulos (33% del proyecto)
     Cambiar payments:common requiere verificar 4 módulo(s).
```

**Genera:**
- `impact/<modulo>-impact.puml`
- `impact/<modulo>-impact.mmd`
- `impact/<modulo>-impact-report.txt`

</details>

<details>
<summary><b>5. Generar imágenes desde PlantUML</b></summary>

```bash
# PNG
plantuml diagrams/gradle-dependencies.puml
plantuml diagrams/*.puml external-calls/*.puml

# SVG (escalable)
plantuml -tsvg diagrams/gradle-dependencies.puml
```

**Instalar PlantUML:**

```bash
brew install plantuml          # macOS
sudo apt install plantuml      # Ubuntu/Debian
choco install plantuml         # Windows
```

</details>

---

## 🎨 Configuración personalizada

Sin config, el analizador usa defaults genéricos para cualquier proyecto Android. La configuración es **opt-in**: la herramienta funciona sin ningún archivo de config.

Si querés personalizar colores, íconos y estilos, creá un `analyzer_config.json` en el directorio desde donde corrés el comando:

**Instalado con pipx:**
```bash
# macOS / Linux
curl -o analyzer_config.json \
  https://raw.githubusercontent.com/pfranccino/android-gradle-analyzer/main/analyzer_config.example.json

# Windows (PowerShell)
Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/pfranccino/android-gradle-analyzer/main/analyzer_config.example.json" `
  -OutFile "analyzer_config.json"
```

**Con el repo clonado:**
```bash
cp analyzer_config.example.json analyzer_config.json
```

<details>
<summary><b>Ejemplo de configuración</b></summary>

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

Solo incluí los campos que querés cambiar — el resto usa defaults.

**Orden de búsqueda:**
1. `--config <path>` explícito
2. `analyzer_config.json` en el directorio actual (donde corrés el comando)
3. Defaults internos

> **Tip:** si siempre analizás el mismo proyecto, poné el `analyzer_config.json` en la raíz de ese proyecto y corré el comando desde ahí. Si analizás varios proyectos, usá `--config ~/mi-config.json`.

</details>

---

## ⚙️ Configuración por proyecto (`analyzer.yml`)

Si creás un archivo `analyzer.yml` en la **raíz del proyecto Android analizado**, las herramientas lo leerán automáticamente y usarán sus valores como defaults. Los flags de CLI siempre tienen prioridad sobre el yml.

```yaml
sanity:
  fail_on_cycle: true
  fail_on_score_below: 70
  output_dir: reports/sanity

impact:
  default_module: app
  output_dir: reports/impact

analyzer:
  output_dir: reports/diagrams
  format: mermaid

externals:
  output_dir: reports/external-calls
```

**Campos por sección:**

| Sección | Campo | CLI equivalente |
|---|---|---|
| `sanity` | `fail_on_cycle` | `--fail-on-cycle` |
| `sanity` | `fail_on_score_below` | `--fail-on-score-below N` |
| `sanity` | `output_dir` | `--output-dir` |
| `impact` | `default_module` | segundo argumento posicional |
| `impact` | `output_dir` | `--output-dir` |
| `analyzer` | `output_dir` | `--output-dir` |
| `analyzer` | `format` | `--format` |
| `externals` | `output_dir` | `--output-dir` |

**Reglas:**
- El yml se busca en la ruta que pasás como primer argumento, no en el CWD.
- Los flags de CLI **siempre** ganan sobre el yml.
- Requiere `pyyaml` (instalación opcional: `pip install android-gradle-analyzer[yaml]`). Si no está instalado, el yml se ignora sin error.

---

## 🚦 Integración CI/CD

`gradle-sanity` tiene flags para fallar la build si se detectan problemas:

```bash
# Falla si hay ciclos
gradle-sanity /ruta/proyecto --fail-on-cycle --quiet

# Falla si el score cae por debajo de 70
gradle-sanity /ruta/proyecto --fail-on-score-below 70 --quiet

# Salida JSON para parsear en el pipeline
gradle-sanity /ruta/proyecto --json > sanity-report.json
```

Ver el ejemplo completo en [`examples/github-actions-dependency-health.yml`](examples/github-actions-dependency-health.yml).

---

## 🔭 Scopes soportados

| Scope | Categoría visual |
|---|---|
| `api`, `implementation`, `compileOnly` | Flecha sólida (compile) |
| `kapt`, `annotationProcessor` | Flecha punteada (build) |
| `testImplementation`, `androidTestImplementation`, `debugImplementation`, `releaseImplementation`, `runtimeOnly`, `testRuntimeOnly` | Flecha punteada con label (test/debug) |

---

## 📋 Más info

<details>
<summary><b>Estructura del proyecto</b></summary>

```
android-gradle-analyzer/
├── README.md
├── CHANGELOG.md
├── LICENSE
├── CONTRIBUTING.md
├── pyproject.toml               ← instalación via pipx
├── requirements.txt             ← uso directo (git clone)
├── menu.py                      ← wrapper: python3 menu.py
├── menu/                        ← paquete del menú interactivo
│   ├── actions.py
│   ├── branding.py
│   ├── exporter.py
│   ├── prompts.py
│   ├── state.py
│   └── ui.py
├── analyzer_utils.py            ← utilidades compartidas
├── analyzer_config.example.json ← config de ejemplo
├── gradle_analyzer.py           ← script 1: dependencias internas
├── external_callers.py          ← script 2: llamadas externas
├── gradle_sanity.py             ← script 3: sanidad + score
├── gradle_impact.py             ← script 4: impacto de cambios
├── examples/
│   └── github-actions-dependency-health.yml
└── scripts/
    └── bump_version.py          ← sincroniza versión y guía el release
```

</details>

<details>
<summary><b>Cómo funciona internamente</b></summary>

**Detección de módulos**
1. Si existe `settings.gradle.kts` o `settings.gradle` en la raíz, se usa como fuente de verdad (extrae los `include(":module")`).
2. Sino, `rglob()` busca todos los `build.gradle*` como fallback.
3. Paths → nombres: `payments/home` → `payments:home`.

**Extracción de dependencias**
1. Lee cada `build.gradle`.
2. Regex sobre cada scope: `implementation project(":...")`, `api(project(":..."))`, `kapt project(':...')`, etc.
3. Normaliza y guarda las relaciones por scope.

**Generación de diagramas**
1. Clasifica módulos por tipo (common, gateway, features).
2. Aplica colores según clasificación.
3. Genera PlantUML/Mermaid agrupados por categoría visual.
4. Marca en rojo los módulos involucrados en ciclos.

</details>

<details>
<summary><b>Ajustar espaciado de diagramas</b></summary>

En `gradle_analyzer.py`, función `generate_plantuml()`:

```python
"skinparam nodesep 150",    # Horizontal
"skinparam ranksep 150",    # Vertical
"skinparam padding 30",     # Interno
```

| Estilo | nodesep / ranksep / padding |
|---|---|
| Compacto | 60 / 60 / 10 |
| Balanceado | 100 / 100 / 20 |
| Espacioso | 150 / 150 / 30 |

</details>

<details>
<summary><b>Troubleshooting</b></summary>

**"No se encontró gradle para: [módulo]"**
El módulo no tiene `build.gradle` ni `build.gradle.kts`. Verificá el path.

**Diagrama apretado**
Subí los valores de espaciado (ver sección anterior).

**No detecta algunas dependencias**
El formato del gradle puede ser distinto al estándar. Revisá los patrones en `analyzer_utils.py` (constante `DEPENDENCY_SCOPES`).

**El menú no arranca tras clonar**
Instalá las dependencias: `pip install -r requirements.txt`

</details>

<details>
<summary><b>Referencias del análisis de sanidad</b></summary>

Las métricas de `gradle_sanity.py` están basadas en fuentes verificadas:

- **Low coupling / High cohesion en Android** — [Guide to Android app modularization](https://developer.android.com/topic/modularization) · [Common modularization patterns](https://developer.android.com/topic/modularization/patterns)
- **Métricas Ca, Ce, I y principios de acoplamiento de paquetes** — formulados por **Robert C. Martin (Uncle Bob)** en *Agile Software Development: Principles, Patterns, and Practices* (2002), capítulo sobre Package Design Principles. Los tres principios de acoplamiento son:
  - **ADP** (Acyclic Dependencies Principle) — el grafo de dependencias entre módulos no debe tener ciclos.
  - **SDP** (Stable Dependencies Principle) — un módulo solo debe depender de módulos más estables que él mismo.
  - **SAP** (Stable Abstractions Principle) — los módulos más estables deben ser los más abstractos.
  - La fórmula `I = Ce / (Ce + Ca)` cuantifica estabilidad: `0` = imposible de desestabilizar, `1` = completamente inestable.
  - Ver también: [Efferent coupling — Wikipedia](https://en.wikipedia.org/wiki/Efferent_coupling) · [Software Coupling Metrics — entrofi.net](https://www.entrofi.net/coupling-metrics-afferent-and-efferent-coupling/)
- **Aplicación a módulos Android** — Martin definió estas métricas para *packages* en Java/C++. En proyectos Android multi-módulo, cada módulo Gradle cumple el mismo rol que un package en su modelo (unidad de compilación y encapsulamiento), por lo que la semántica es directamente trasladable.
- **DAGP** — [dependency-analysis-gradle-plugin](https://github.com/autonomousapps/dependency-analysis-gradle-plugin). Inspiró la detección de scopes mal declarados.
- **Detección de ciclos** — DFS con coloreo de nodos (blanco/gris/negro).

> El **score 0–100 no es un estándar externo.** Es orientativo con pesos razonables como punto de partida, ajustables en `analyzer_config.json` bajo `sanity_weights`. El umbral SDP de 0.3 tampoco es parte del principio original — es un parámetro configurable.

</details>

---

## 🤝 Contribuir

Las contribuciones son bienvenidas. Forkeá, creá una rama, commiteá y abrí un PR. Ver [CONTRIBUTING.md](CONTRIBUTING.md) para detalles.

## 📄 Licencia

MIT — ver [LICENSE](LICENSE).

---

<div align="center">

made with care · [pfranccino.dev](https://pfranccino.dev)

</div>
