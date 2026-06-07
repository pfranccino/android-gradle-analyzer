# 📚 Ejemplos de uso

Recetas end-to-end con los CLIs actuales. La referencia de cada comando (flags, archivos generados) está en el [Wiki → Comandos](https://github.com/pfranccino/android-gradle-analyzer/wiki/Comandos).

> Todos los ejemplos se pueden **reproducir** clonando el repo: usan los fixtures de `tests/fixtures/leaf_coupling` (10 módulos). La salida que se muestra es real.
>
> El proyecto de ejemplo tiene este grafo: `app → cart, checkout, core`; `cart, checkout → payments`; `payments → core, database, model, network, util`; el resto → `core`; y `legacy → app`.

---

## Receta 1 · Entender un módulo nuevo (onboarding)

¿Acabas de entrar a un proyecto y quieres ver cómo se relacionan sus módulos?

```bash
gradle-analyzer tests/fixtures/leaf_coupling --format mermaid
```

```console
🔍 Analizando dependencias (motor: static)...
  ✓ app: 3 dependencia(s)
  ✓ payments: 5 dependencia(s)
  ○ core: sin dependencias internas
  ...
✓ Análisis completado: 15 dependencias detectadas
✓ Mermaid: diagrams/gradle-dependencies.mmd
```

El `.mmd` lo pegas en un README (GitHub lo renderiza) o en [mermaid.live](https://mermaid.live/). Para una imagen PNG/SVG usa PlantUML:

```bash
gradle-analyzer tests/fixtures/leaf_coupling --format plantuml
plantuml -tsvg diagrams/gradle-dependencies.puml
```

---

## Receta 2 · Refactor seguro de un módulo

Antes de tocar `payments`, dos preguntas: **¿quién lo usa desde fuera?** y **¿qué se rompe si lo cambio?**

**a) ¿Quién consume `payments`?**

```bash
gradle-externals tests/fixtures/leaf_coupling payments
```

```console
======================================================================
MÓDULOS EXTERNOS QUE LLAMAN
======================================================================

📦 cart
  └─→ payments  [implementation]

📦 checkout
  └─→ payments  [implementation]
```

**b) ¿Qué se rompe si cambio `core`?**

```bash
gradle-impact tests/fixtures/leaf_coupling core
```

```console
  Nivel 1 — dependientes directos (6):
    • app   • database   • model   • network   • payments   • util

  Nivel 2 — dependientes transitivos (3):
    • cart   • checkout   • legacy

  🔥 Impacto total: 9 módulos (90% del proyecto)
     Cambiar core requiere verificar 9 módulo(s).
```

→ Tocar `core` impacta al 90% del proyecto: PR pequeño, tests amplios y revisión cuidadosa.

---

## Receta 3 · Auditoría de arquitectura

```bash
gradle-sanity tests/fixtures/leaf_coupling
```

Tabla de métricas (recortada) y score:

```console
  Módulo      Ca    Ce       I  Estado
  ────────   ────  ────  ──────  ──────────────────────────────
  core         6     0    0.00  🟢 Estable
  payments     2     5    0.71  🟠 Moderadamente inestable
  legacy       0     1    1.00  🔴 Inestable (módulo hoja)

  PUNTUACIÓN FINAL:  100 / 100
  Resultado: 🟢 Excelente — arquitectura de dependencias muy sana
```

`core` con `Ca=6, I=0.00` es el módulo base sano (todos dependen de él, él de nadie). Qué significa cada métrica: [Wiki → Métricas de sanidad](https://github.com/pfranccino/android-gradle-analyzer/wiki/Metricas-de-sanidad).

---

## Receta 4 · Gate de arquitectura en CI

Falla la build si aparece un ciclo o el score baja del umbral:

```bash
gradle-sanity tests/fixtures/leaf_coupling \
  --fail-on-cycle \
  --fail-on-score-below 70 \
  --quiet
```

Para parsear en el pipeline, usa JSON:

```bash
gradle-sanity tests/fixtures/leaf_coupling --json --quiet > sanity-report.json
```

Workflow completo de GitHub Actions: [Wiki → Integración CI](https://github.com/pfranccino/android-gradle-analyzer/wiki/Integracion-CI) y [`examples/github-actions-dependency-health.yml`](examples/github-actions-dependency-health.yml).

---

## Receta 5 · Snapshot antes/después de un refactor

```bash
# Antes
gradle-analyzer ./payments --format plantuml
cp diagrams/gradle-dependencies.puml diagrams/before-refactor.puml

# ... refactorizas ...

# Después — comparar visualmente
gradle-analyzer ./payments --format plantuml
plantuml diagrams/before-refactor.puml diagrams/gradle-dependencies.puml
```

---

## Receta 6 · Auditar varios features en lote

```bash
#!/usr/bin/env bash
set -euo pipefail

for feature in payments transfers wallet; do
  echo "📦 $feature"
  gradle-sanity "./features/$feature" --quiet --json \
    | python -c "import sys,json; d=json.load(sys.stdin); print('  score:', d['score'])"
done
```

---

¿Tienes otro caso de uso? [Compártelo](https://github.com/pfranccino/android-gradle-analyzer/issues).
