# 📚 Ejemplos de Uso

## Caso 1: Proyecto Simple

### Estructura

```
mi-app/
├── app/
├── core/
│   ├── common/
│   ├── network/
│   └── database/
└── features/
    ├── login/
    ├── home/
    └── profile/
```

### Analizar módulo `features`

```bash
python3 gradle_analyzer.py /Users/tu-usuario/mi-app/features
```

### Salida esperada

```
📁 Escaneando TODOS los módulos en: /Users/tu-usuario/mi-app/features

  • login
  • home
  • profile

✓ 3 módulos encontrados

🔍 Analizando archivos Gradle...
  ✓ home: 2 dependencia(s)
  ✓ login: 1 dependencia(s)
  ○ profile: sin dependencias internas
```

---

## Caso 2: Proyecto Multi-Módulo Complejo

### Estructura

```
mi-proyecto/
├── app/
├── foundation/
├── shared/
│   └── analytics/
└── payments/
    ├── common/
    ├── home/
    ├── onboarding/
    └── gateway/
```

### 1. Analizar dependencias internas de payments

```bash
python3 gradle_analyzer.py /Users/tu-usuario/mi-proyecto/payments
```

**Resultado**: Diagrama mostrando cómo home, onboarding, etc. se relacionan entre sí.

### 2. Ver quién llama a payments desde fuera

```bash
python3 external_callers.py /Users/tu-usuario/mi-proyecto payments
```

**Resultado**: Diagrama mostrando que `app` y `shared` llaman a módulos de payments.

---

## Caso 3: Detectar Módulos Más Usados

### Comando

```bash
python3 gradle_analyzer.py /path/to/module
cat diagrams/gradle-report.txt
```

### Salida

```
=======================================================================
ESTADÍSTICAS
=======================================================================

Módulos más utilizados:
  • common: usado por 15 módulo(s)
  • network: usado por 8 módulo(s)
  • analytics: usado por 5 módulo(s)
```

**Interpretación**: `common` es el módulo más acoplado, considera dividirlo.

---

## Caso 4: Workflow Completo

### 1. Análisis inicial

```bash
# Analizar módulo
python3 gradle_analyzer.py /path/to/payments

# Ver reporte
cat diagrams/gradle-report.txt

# Generar imagen
plantuml diagrams/gradle-dependencies.puml
open diagrams/gradle-dependencies.png
```

### 2. Análisis de impacto

```bash
# Ver quién usa este módulo
python3 external_callers.py /path/to/project payments

# Generar imagen
plantuml external-calls/payments-external-calls.puml
open external-calls/payments-external-calls.png
```

### 3. Compartir con el equipo

```bash
# Generar SVG para documentación
plantuml -tsvg diagrams/gradle-dependencies.puml

# Copiar a carpeta de docs
cp diagrams/gradle-dependencies.svg ../docs/architecture/
```

---

## Caso 5: Auditoría de Arquitectura

### Script de auditoría

```bash
#!/bin/bash

echo "🔍 Auditando arquitectura..."

# Analizar cada feature
for feature in payments transfers wallet; do
    echo ""
    echo "📦 Analizando $feature..."
    python3 gradle_analyzer.py ./features/$feature

    # Extraer módulos más usados
    echo "Módulos críticos en $feature:"
    grep "usado por" diagrams/gradle-report.txt | head -3
done

# Analizar dependencias externas
echo ""
echo "🌐 Analizando llamadas externas..."
python3 external_callers.py ./ payments

# Generar todas las imágenes
plantuml diagrams/*.puml
plantuml external-calls/*.puml

echo ""
echo "✅ Auditoría completada. Ver carpetas diagrams/ y external-calls/"
```

---

## Caso 6: Onboarding de Nuevo Desarrollador

### Guía rápida

```bash
# 1. Ver estructura general del módulo
python3 gradle_analyzer.py ./payments

# 2. Ver el reporte en texto
cat diagrams/gradle-report.txt

# 3. Generar diagrama visual
plantuml diagrams/gradle-dependencies.puml
open diagrams/gradle-dependencies.png
```

**Incluir en documentación de onboarding**:

- Diagrama actualizado de arquitectura
- Reporte de dependencias
- Explicación de cada módulo

---

## Caso 7: Refactoring Guiado

### Antes de refactorizar

```bash
# Generar snapshot del estado actual
python3 gradle_analyzer.py ./payments
cp diagrams/gradle-dependencies.puml diagrams/before-refactor.puml
plantuml diagrams/before-refactor.puml
```

### Después de refactorizar

```bash
# Generar nuevo estado
python3 gradle_analyzer.py ./payments
plantuml diagrams/gradle-dependencies.puml

# Comparar visualmente
open diagrams/before-refactor.png
open diagrams/gradle-dependencies.png
```

---

## Tips y Trucos

### Ver solo módulos con muchas dependencias

```bash
python3 gradle_analyzer.py ./payments
grep "✓" diagrams/gradle-report.txt | grep -E "[5-9]|[0-9]{2}"
```

### Encontrar módulos sin uso

```bash
cat diagrams/gradle-report.txt | grep "sin dependencias"
```

### Generar diagrama compacto

Edita `gradle_analyzer.py` antes de ejecutar:

```python
"skinparam nodesep 60",
"skinparam ranksep 60",
"skinparam padding 10",
```

### Exportar múltiples formatos

```bash
plantuml diagrams/gradle-dependencies.puml
plantuml -tsvg diagrams/gradle-dependencies.puml
plantuml -tpdf diagrams/gradle-dependencies.puml
```

---

## Solución de Problemas Comunes

### Problema: Demasiados módulos en el diagrama

**Solución**: Analiza submódulos por separado

```bash
python3 gradle_analyzer.py ./my-feature/ui
python3 gradle_analyzer.py ./my-feature/domain
```

### Problema: Líneas cruzadas dificultan lectura

**Solución**: Aumenta espaciado

```python
"skinparam nodesep 150",
"skinparam ranksep 150",
```

### Problema: No detecta algunas dependencias

**Solución**: Verifica el formato en tu gradle y agrega el patrón regex correspondiente.

---

¿Tienes otro caso de uso? [Compártelo](https://github.com/pfranccino/android-gradle-analyzer/issues)!
