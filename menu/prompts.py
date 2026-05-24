"""
Wrappers de questionary para todos los prompts del menú interactivo.
"""

import questionary
from questionary import Style

from menu.state import get_last_project, get_last_module

# Estilo coherente para todos los prompts
_STYLE = Style([
    ("qmark",        "fg:#5f87ff bold"),
    ("question",     "bold"),
    ("answer",       "fg:#5fff87 bold"),
    ("pointer",      "fg:#5f87ff bold"),
    ("highlighted",  "fg:#5f87ff bold"),
    ("selected",     "fg:#5fff87"),
    ("separator",    "fg:#5f5f5f"),
    ("instruction",  "fg:#5f5f5f"),
])

# ── Opciones del menú principal ───────────────────────────────────────────────

MENU_CHOICES = [
    questionary.Choice("📦  Dependencias internas",         value="internal"),
    questionary.Choice("🔗  Llamadas externas al módulo",   value="external"),
    questionary.Choice("📊  Sanidad de dependencias",       value="sanity"),
    questionary.Separator(),
    questionary.Choice("📤  Exportar último análisis",       value="export"),
    questionary.Choice("📋  Ver historial",                  value="history"),
    questionary.Separator(),
    questionary.Choice("❌  Salir",                          value="quit"),
]


def main_menu() -> str | None:
    """Muestra el menú principal y devuelve la acción elegida."""
    answer = questionary.select(
        "¿Qué querés hacer?",
        choices=MENU_CHOICES,
        style=_STYLE,
        use_shortcuts=False,
    ).ask()
    return answer


# ── Pedir ruta al proyecto ────────────────────────────────────────────────────

def ask_project_path(prompt: str = "Ruta al proyecto Android") -> str | None:
    """Solicita la ruta del proyecto con el último usado como default."""
    default = get_last_project() or ""
    answer = questionary.path(
        f"{prompt}:",
        default=default,
        only_directories=True,
        style=_STYLE,
    ).ask()
    return answer or None


# ── Pedir módulo target ───────────────────────────────────────────────────────

def ask_module(modules: list[str], prompt: str = "Módulo a analizar") -> str | None:
    """
    Muestra la lista de módulos detectados.
    Usa autocomplete si hay más de 15 módulos, select si hay 15 o menos.
    """
    if not modules:
        return questionary.text(f"{prompt} (nombre del módulo):", style=_STYLE).ask() or None

    last = get_last_module()
    default = last if last in modules else (modules[0] if modules else None)

    if len(modules) > 15:
        answer = questionary.autocomplete(
            f"{prompt}:",
            choices=modules,
            default=default or "",
            style=_STYLE,
        ).ask()
    else:
        choices = modules[:]
        answer = questionary.select(
            f"{prompt}:",
            choices=choices,
            default=default,
            style=_STYLE,
        ).ask()

    return answer or None


# ── Pedir formato de salida ───────────────────────────────────────────────────

def ask_format() -> str | None:
    """Solicita el formato de salida para diagramas."""
    return questionary.select(
        "Formato de salida:",
        choices=[
            questionary.Choice("Todos (PlantUML + Mermaid + TXT)", value="all"),
            questionary.Choice("PlantUML (.puml)",                  value="plantuml"),
            questionary.Choice("Mermaid (.mmd)",                    value="mermaid"),
        ],
        style=_STYLE,
    ).ask()


# ── Pedir formatos de export ──────────────────────────────────────────────────

def ask_export_formats(pdf_available: bool = True) -> list[str] | None:
    """Checkbox para elegir qué formatos exportar."""
    choices = [
        questionary.Choice("HTML  (colores, standalone)",   value="html",     checked=True),
        questionary.Choice("Markdown  (con bloque mermaid)", value="markdown", checked=True),
        questionary.Choice("ZIP  (todos los archivos)",      value="zip",      checked=False),
    ]
    if pdf_available:
        choices.insert(2, questionary.Choice("PDF  (requiere weasyprint)", value="pdf", checked=False))

    return questionary.checkbox(
        "¿En qué formatos querés exportar?",
        choices=choices,
        style=_STYLE,
    ).ask()


# ── Confirmación simple ───────────────────────────────────────────────────────

def ask_confirm(msg: str, default: bool = True) -> bool:
    answer = questionary.confirm(msg, default=default, style=_STYLE).ask()
    return bool(answer)


# ── Pedir string (fallback) ───────────────────────────────────────────────────

def ask_text(prompt: str, default: str = "") -> str | None:
    return questionary.text(f"{prompt}:", default=default, style=_STYLE).ask() or None


# ── Historial: elegir entrada ─────────────────────────────────────────────────

def ask_history_entry(history: list[dict]) -> dict | None:
    """Muestra el historial y permite elegir una entrada."""
    if not history:
        return None

    choices = [
        questionary.Choice(
            f"{e.get('timestamp','')[:16]}  [{e.get('action','')}]  {e.get('path','')}",
            value=e,
        )
        for e in history
    ]
    choices.append(questionary.Choice("← Volver", value=None))

    return questionary.select(
        "Seleccioná un análisis del historial:",
        choices=choices,
        style=_STYLE,
    ).ask()
