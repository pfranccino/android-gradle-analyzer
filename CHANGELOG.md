# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [1.2.1] - 2026-05-26

### Changed
- `pyproject.toml`: `requires-python` actualizado de `>=3.8` a `>=3.10`. El código usa sintaxis PEP 604 (`str | None`, `list[str]`) que requiere Python 3.10 o superior. Antes el paquete se instalaba en 3.8/3.9 pero crashaba al primer import — ahora pip se niega antes con un mensaje claro
- README: badge de Python actualizado a `3.10+` (antes mentía con `3.7+`)

### Added
- README: badges de **Tests** (estado del último workflow) y **Release** (última versión publicada) vía shields.io

## [1.2.0] - 2026-05-26

### Added
- Soporte para **type-safe project accessors** (`projects.foo.barBaz`, Gradle 7+) en los 4 analizadores. El parser construye un mapa accessor → módulo a partir de `settings.gradle(.kts)` y resuelve referencias en Kotlin DSL (`implementation(projects.feature.paymentsCommon)`) y Groovy (`implementation projects.feature.paymentsCommon`). Análisis 100% estático, sin compilar
- `module_to_accessor()` y `build_accessor_map()` expuestos en `analyzer_utils` para uso externo o testing
- Detección de colisiones de accessor (raro en proyectos reales): si dos módulos mapean al mismo accessor, se emite un warning y gana el primero

### Fixed
- **Falsos positivos en `external_callers` y `gradle_analyzer`**: el matcher anterior usaba `endswith(':' + path)` bidireccional, lo que hacía que `project(":common")` matchera erróneamente cualquier submódulo `:foo:common`. Ahora el matcheo es exacto sobre el listado de módulos conocidos. Caso real afectado: cualquier proyecto con módulos raíz que comparten leaf-name con submódulos del target

## [1.1.1] - 2026-05-26

### Fixed
- `generate_ascii`: usaba `module_set` (solo los módulos del scope analizado) como filtro de dependencias, mostrando "(sin dependencias internas)" cuando las deps apuntan a módulos del proyecto raíz fuera del subdirectorio. Ahora usa `known_modules`
- `generate_report`: la sección "Módulos no utilizados por otros" se oculta cuando se analiza un subconjunto del proyecto (el Ca no puede calcularse sin analizar todos los módulos). En su lugar muestra una nota que apunta a "Llamadas externas"

## [1.1.0] - 2026-05-26

### Added
- Auto-detección de raíz del proyecto: `find_project_root()` sube directorios desde el path analizado hasta encontrar `settings.gradle(.kts)`, permitiendo resolver dependencias `implementation(project(":..."))` a módulos fuera del subdirectorio analizado (ej. analizar `customer/` y ver dependencias a `view`, `mach-foundation:util`, etc.)
- `known_modules` separado de `modules` en `GradleDependencyAnalyzer`: el registry completo del proyecto raíz se usa para el matching de dependencias, mientras `modules` sigue controlando qué módulos se analizan
- Barra de progreso con porcentaje en el menú interactivo para proyectos con más de 10 módulos (`BarColumn` + `MofNCompleteColumn`); proyectos pequeños mantienen el spinner simple
- `analyze_gradle_dependencies` acepta callback `on_progress(done, total)` para actualizar la UI; usa `as_completed` para progreso fluido conforme terminan los workers paralelos

## [1.0.9] - 2026-05-25

### Fixed
- Mermaid: grafos grandes (>500 edges) fallaban silenciosamente por el límite default del parser. Se agrega header `%%{init}%%` con `maxEdges: 10000`, `maxTextSize: 200000`, `htmlLabels: true`, `curve: basis` y `wrappingWidth: 200`

## [1.0.8] - 2026-05-25

### Fixed
- Mermaid: edge label `use` renombrado a `uses` — `use` es keyword reservado en Mermaid v11+ y causaba error de parsing
- Mermaid: `base_path` resuelto con `.resolve()` para que el ID del subgraph no quede vacío al invocar el analyzer con ruta relativa (`.`)
- Consola: `VERSION` en `menu/branding.py` desincronizado con `pyproject.toml` — ahora ambos se actualizan juntos en el bump

## [1.0.7] - 2026-05-25

### Fixed
- `parse_settings_modules`: detección de módulos con sintaxis `include("modulo")` sin `:` inicial (común en proyectos Android Groovy DSL que adoptan convenciones tipo Kotlin). Antes devolvía 0 módulos silenciosamente. `includeBuild` ya no se cuenta como módulo del proyecto.

## [1.0.6] - 2026-05-24

### Added
- Soporte para `analyzer.yml` en la raíz del proyecto analizado — configura defaults de CLI sin pasar flags manualmente

## [1.0.5] - 2026-05-24

### Fixed
- Colones en nombres de archivo en Windows (`external_callers`) — módulos como `core:analytics:tracker` generaban `[Errno 22]`

## [1.0.4] - 2026-05-24

### Fixed
- UnicodeEncodeError en Windows: todos los CLIs ahora fuerzan UTF-8 en stdout/stderr al arrancar (fix para terminales con encoding cp1252)

## [1.0.3] - 2026-05-24

### Fixed
- Menú: al cancelar la selección de módulo focal ya no procede el análisis — vuelve correctamente al menú principal
- Menú: selector de módulo focal muestra los nombres directamente en la lista (sin paso intermedio)

## [1.0.2] - 2026-05-24

### Added
- Menú interactivo: formato DOT y ASCII disponibles en el selector de formato
- Menú interactivo: prompt de zoom (`--focus`) en análisis de dependencias internas
- Menú interactivo: ASCII se muestra inline en el panel del terminal
- Menú interactivo: offer post-análisis para renderizar DOT a PNG/SVG con Graphviz local

## [1.0.1] - 2026-05-24

### Added
- Graphviz DOT format (`--format dot` / `gradle-dot`) con colores por tipo de módulo
- ASCII format (`--format ascii` / `gradle-ascii`) para visualización en terminal
- `--focus <module[,module]>`: zoom al subgrafo de un módulo en todos los formatos
- Entry points independientes `gradle-dot` y `gradle-ascii`
- Parsing paralelo con `ThreadPoolExecutor` en los 3 analizadores (gradle-analyzer, gradle-externals, gradle-impact)

### Fixed
- Build files con nombre custom (ej. `chat.gradle.kts`) ahora se detectan correctamente — fix para proyectos como MEGA Android que no usan `build.gradle.kts` estándar

## [1.0.0] - 2026-05-24

### Added
- `gradle-impact`: nuevo analizador de impacto de cambios — dado un módulo, muestra qué otros módulos se ven afectados (BFS sobre grafo invertido, niveles directos y transitivos)
- `--quiet` en todos los CLIs para suprimir output de progreso (ideal para CI)
- `--json` en todos los CLIs para salida estructurada a stdout
- `--fail-on-cycle` en `gradle-sanity`: `exit 1` si se detecta algún ciclo (CI gate)
- `--fail-on-score-below N` en `gradle-sanity`: `exit 1` si el score cae por debajo de N
- Sección de módulos huérfanos en reporte de sanidad (Ca=0 y Ce=0, sin penalización)
- Parsing de `settings.gradle.kts` / `settings.gradle` como fuente de verdad para módulos
- HTML export con Mermaid embebido (renderizado inline via CDN)
- `examples/github-actions-dependency-health.yml`: ejemplo de integración GitHub Actions
- `scripts/bump_version.py`: script de versionado semántico
- `CHANGELOG.md` con formato Keep a Changelog

### Fixed
- Falsos positivos en detección de versiones hardcodeadas: las versiones dentro de comentarios (`// "lib:x:1.2.3"`) ya no se reportan

## [0.1.0] - 2026-05-24

### Added
- `gradle-analyzer`: análisis de dependencias internas con salida PlantUML, Mermaid y texto
- `gradle-externals`: detección de callers externos a un módulo
- `gradle-sanity`: métricas Ca/Ce/I, detección de ciclos, violaciones SDP y score 0–100
- `gradle-analyzer-menu`: menú interactivo con Rich + questionary, historial y export
- Export a HTML, Markdown, ZIP y PDF (opcional via weasyprint)
- Configuración personalizable via `analyzer_config.json`
- Detección automática de ciclos con DFS y coloreo de nodos
- Soporte para Groovy DSL y Kotlin DSL (`build.gradle` y `build.gradle.kts`)
- Scopes soportados: `implementation`, `api`, `kapt`, `compileOnly`, `testImplementation` y más
