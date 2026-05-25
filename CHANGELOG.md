# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
