"""
Tests para menu.ui.
Regresión del "timer congelado": el spinner/barra fijan su Console al stdout real,
así que cuando el análisis redirige sys.stdout a un buffer (menu.actions._capture),
los frames del timer siguen yendo a la terminal y no se congelan.
"""

import sys
import io

from menu import ui


def test_spinner_console_survives_stdout_swap():
    real = sys.stdout
    with ui.analysis_spinner("analizando") as progress:
        sys.stdout = io.StringIO()      # simula el swap de _capture durante el análisis
        try:
            assert progress.console.file is real
        finally:
            sys.stdout = real


def test_progress_console_survives_stdout_swap():
    real = sys.stdout
    # total > 10 → barra determinada (la que se "congelaba" con el motor dinámico)
    with ui.analysis_progress("analizando", total=50) as on_progress:
        sys.stdout = io.StringIO()
        try:
            on_progress(1, 50)          # no debe romperse con el stdout intercambiado
        finally:
            sys.stdout = real
