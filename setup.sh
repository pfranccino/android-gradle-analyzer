#!/bin/bash

# Script de configuración para Android Gradle Analyzer

echo "🚀 Configurando Android Gradle Analyzer..."
echo ""

# Verificar Python
echo "📋 Verificando requisitos..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 no está instalado"
    echo "   Instálalo desde: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "✅ $PYTHON_VERSION encontrado"

# Instalar dependencias Python
echo ""
echo "📦 Instalando dependencias Python..."
if python3 -m pip install -r requirements.txt --quiet; then
    echo "✅ Dependencias instaladas (questionary, rich)"
else
    echo "⚠️  Error instalando dependencias. Intentá manualmente:"
    echo "   pip install questionary>=2.0 rich>=13.7"
fi

# Verificar PlantUML (opcional)
if command -v plantuml &> /dev/null; then
    PLANTUML_VERSION=$(plantuml -version 2>&1 | head -n 1)
    echo "✅ PlantUML encontrado: $PLANTUML_VERSION"
else
    echo "⚠️  PlantUML no encontrado (opcional)"
    echo "   Para generar imágenes, instala PlantUML:"
    echo "   • macOS: brew install plantuml"
    echo "   • Ubuntu: sudo apt install plantuml"
    echo ""
fi

# Crear directorios de salida
echo ""
echo "📁 Creando directorios de salida..."
mkdir -p diagrams
mkdir -p external-calls
echo "✅ Directorios creados"

# Hacer scripts ejecutables
echo ""
echo "🔧 Configurando permisos..."
chmod +x gradle_analyzer.py
chmod +x external_callers.py
chmod +x gradle_sanity.py
chmod +x menu.py
echo "✅ Scripts configurados"

echo ""
echo "✅ ¡Configuración completada!"
echo ""
echo "📖 Uso rápido:"
echo "   python3 menu.py                              ← menú interactivo (recomendado)"
echo "   python3 gradle_analyzer.py /ruta/a/tu/modulo"
echo "   python3 external_callers.py /ruta/proyecto nombre-modulo"
echo "   python3 gradle_sanity.py /ruta/a/tu/modulo"
echo ""
echo "📚 Ver README.md para documentación completa"