# Contribuyendo a Android Gradle Analyzer

¡Gracias por tu interés en contribuir! 🎉

## 🚀 Cómo Contribuir

### Reportar Bugs

1. Verifica que el bug no haya sido reportado antes
2. Abre un [issue](https://github.com/pfranccino/android-gradle-analyzer/issues/new)
3. Incluye:
   - Descripción clara del problema
   - Pasos para reproducirlo
   - Comportamiento esperado vs actual
   - Versión de Python
   - Sistema operativo
   - Ejemplo de archivo gradle (si es relevante)

### Sugerir Mejoras

1. Abre un issue con el tag `enhancement`
2. Describe la funcionalidad que te gustaría ver
3. Explica por qué sería útil
4. Proporciona ejemplos de uso si es posible

### Enviar Pull Requests

1. **Fork** el repositorio
2. **Crea una rama** desde `main`:
   ```bash
   git checkout -b feature/mi-nueva-funcionalidad
   ```
3. **Haz tus cambios**:
   - Sigue el estilo de código existente
   - Agrega comentarios donde sea necesario
   - Actualiza documentación si es relevante
4. **Prueba tus cambios**:
   ```bash
   python3 gradle_analyzer.py /ruta/test
   python3 external_callers.py /ruta/test modulo
   ```
5. **Commit** con mensajes descriptivos:
   ```bash
   git commit -m "Agrega soporte para formato Groovy DSL"
   ```
6. **Push** a tu fork:
   ```bash
   git push origin feature/mi-nueva-funcionalidad
   ```
7. **Abre un Pull Request** con:
   - Descripción clara de los cambios
   - Referencias a issues relacionados
   - Screenshots si aplica

## 📝 Guía de Estilo

### Python

- Usa **4 espacios** para indentación
- Nombres de funciones y variables en **snake_case**
- Nombres de clases en **PascalCase**
- Docstrings para funciones públicas
- Líneas máximo 100 caracteres

**Ejemplo:**

```python
def analyze_dependencies(self):
    """
    Analiza las dependencias desde los archivos gradle

    Returns:
        self para encadenamiento
    """
    for module in self.modules:
        self._parse_gradle_file(module)
    return self
```

### Commits

Usa mensajes claros y en presente:

✅ **Bueno:**

- `Agrega soporte para Gradle Kotlin DSL`
- `Corrige detección de dependencias anidadas`
- `Mejora documentación de instalación`

❌ **Malo:**

- `Fix`
- `Changes`
- `Updated stuff`

## 🧪 Testing

Antes de enviar un PR, prueba con:

1. **Proyecto simple** (pocos módulos)
2. **Proyecto complejo** (muchos módulos anidados)
3. **Diferentes formatos** de gradle:
   - `build.gradle` (Groovy)
   - `build.gradle.kts` (Kotlin DSL)

## 🏷️ Proceso de release

`main` está protegida: los cambios entran por **Pull Request** y los tests deben pasar
antes de poder mergear. El release y el publish son automáticos, con un control manual
final antes de subir a PyPI.

1. Actualiza el `CHANGELOG.md` con la sección `## [X.Y.Z]` del release
2. Crea una rama y ejecuta el bump:
   ```bash
   git checkout -b release/vX.Y.Z
   python scripts/bump_version.py X.Y.Z
   ```
3. Revisa el diff en `pyproject.toml` y `menu/branding.py`, commitea y abre el PR:
   ```bash
   git add pyproject.toml menu/branding.py CHANGELOG.md
   git commit -m "chore: bump version to vX.Y.Z"
   git push -u origin release/vX.Y.Z
   gh pr create --fill
   ```
4. Cuando los tests del PR pasen en verde, **mergea el PR**. El CI crea el tag `vX.Y.Z`,
   publica el GitHub Release y deja el job `publish-pypi` **en espera de aprobación**.
5. Ve a la pestaña **Actions** → el run pausado → **Review deployments** → aprueba el
   environment `pypi`. Recién ahí se sube el paquete a PyPI.

> **No crees el tag a mano:** si el tag ya existe, el workflow se salta el release y el
> publish. El tag lo crea el CI tras el merge.

## 💡 Ideas para Contribuir

### Features Buscadas

- [ ] Análisis de performance de build
- [ ] Sugerencias de optimización automáticas
- [ ] Comparación de grafos entre ramas

### Mejoras de Documentación

- [ ] Tutorial en video
- [ ] Más ejemplos de uso
- [ ] Traducción a otros idiomas
- [ ] Guía de arquitectura modular
- [ ] Comparación con otras herramientas

## 🤔 ¿Preguntas?

Si tienes dudas sobre cómo contribuir, abre un issue con el tag `question` o únete a las discusiones.

## 📜 Código de Conducta

- Se respetuoso y constructivo
- Acepta críticas constructivas
- Enfócate en lo mejor para el proyecto
- Sé paciente con otros colaboradores

---

¡Gracias por hacer este proyecto mejor! 🙏
