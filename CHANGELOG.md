# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
