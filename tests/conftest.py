"""
Configuración de pytest: agrega el directorio raíz al sys.path
para que los imports de analyzer_utils, gradle_analyzer, etc. funcionen.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
