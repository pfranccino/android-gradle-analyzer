"""
Wrappers de questionary para todos los prompts del menú interactivo.

Principio de navegación:
  - Cada questionary.select incluye '← Volver' como última opción.
  - Si el usuario presiona Esc, questionary devuelve None → volver al menú principal.
  - El valor sentinel BACK indica "volver un nivel".
"""

import questionary
from questionary import Style

from menu.state import get_last_project, get_last_module

# Valor centinela para "volver atrás"
BACK = "__back__"

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
    """
    Muestra el menú principal y devuelve la acción elegida.
    Devuelve None si el usuario presiona Esc (→ volver = salir del loop).
    """
    answer = questionary.select(
        "¿Qué querés hacer?",
        choices=MENU_CHOICES,
        style=_STYLE,
        use_shortcuts=False,
        instruction="(↑↓ navegar  ↵ elegir  Esc salir)",
    ).ask()
    return answer


# ── Pedir ruta al proyecto ────────────────────────────────────────────────────

def ask_project_path(prompt: str = "Ruta al proyecto Android") -> str | None:
    """
    Solicita la ruta del proyecto con el último usado como default.
    Devuelve None si el usuario cancela (Esc o string vacío).
    """
    default = get_last_project() or ""
    answer = questionary.path(
        f"{prompt}:",
        default=default,
        only_directories=True,
        style=_STYLE,
    ).ask()
    # questionary.path devuelve None con Esc, o "" si borra y confirma
    if not answer:
        return None
    return answer


# ── Pedir módulo target ───────────────────────────────────────────────────────

def ask_module(modules: list[str], prompt: str = "Módulo a analizar") -> str | None:
    """
    Muestra la lista de módulos detectados con opción ← Volver.
    Devuelve None si el usuario cancela o elige Volver.
    """
    if not modules:
        answer = questionary.text(
            f"{prompt} (nombre del módulo):",
            style=_STYLE,
        ).ask()
        return answer or None

    last = get_last_module()
    default = last if last in modules else (modules[0] if modules else None)

    back_choice = questionary.Choice("← Volver", value=BACK)

    if len(modules) > 15:
        answer = questionary.autocomplete(
            f"{prompt}:",
            choices=modules,
            default=default or "",
            style=_STYLE,
        ).ask()
        return answer if answer and answer != BACK else None
    else:
        choices = modules + [questionary.Separator(), back_choice]
        answer = questionary.select(
            f"{prompt}:",
            choices=choices,
            default=default,
            style=_STYLE,
            use_shortcuts=False,
            instruction="(↑↓  ↵ elegir  Esc cancelar)",
        ).ask()
        if answer is None or answer == BACK:
            return None
        return answer


# ── Pedir formato de salida ───────────────────────────────────────────────────

def ask_format() -> str | None:
    """
    Solicita el formato de salida para diagramas.
    Devuelve None si el usuario cancela o elige Volver.
    """
    answer = questionary.select(
        "Formato de salida:",
        choices=[
            questionary.Choice("Todos (PlantUML + Mermaid + TXT)", value="all"),
            questionary.Choice("PlantUML (.puml)",                  value="plantuml"),
            questionary.Choice("Mermaid (.mmd)",                    value="mermaid"),
            questionary.Separator(),
            questionary.Choice("← Volver",                          value=BACK),
        ],
        style=_STYLE,
        use_shortcuts=False,
        instruction="(↑↓  ↵ elegir  Esc cancelar)",
    ).ask()
    if answer is None or answer == BACK:
        return None
    return answer


# ── Pedir formatos de export ──────────────────────────────────────────────────

def ask_export_formats(pdf_available: bool = True) -> list[str] | None:
    """
    Checkbox para elegir qué formatos exportar.
    Devuelve None si el usuario cancela.
    """
    choices = [
        questionary.Choice("HTML  (colores, standalone)",    value="html",     checked=True),
        questionary.Choice("Markdown  (con bloque mermaid)", value="markdown", checked=True),
        questionary.Choice("ZIP  (todos los archivos)",      value="zip",      checked=False),
    ]
    if pdf_available:
        choices.insert(2, questionary.Choice("PDF  (requiere weasyprint)", value="pdf", checked=False))

    answer = questionary.checkbox(
        "¿En qué formatos querés exportar?",
        choices=choices,
        style=_STYLE,
        instruction="(espacio marcar  ↵ confirmar  Esc cancelar)",
    ).ask()
    return answer if answer is not None else None


# ── Confirmación simple ───────────────────────────────────────────────────────

def ask_confirm(msg: str, default: bool = True) -> bool:
    answer = questionary.confirm(
        msg,
        default=default,
        style=_STYLE,
    ).ask()
    return bool(answer)


# ── Historial: elegir entrada ─────────────────────────────────────────────────

def ask_history_entry(history: list[dict]) -> dict | None:
    """
    Muestra el historial y permite elegir una entrada.
    Incluye opción ← Volver.
    """
    if not history:
        return None

    choices = [
        questionary.Choice(
            f"{e.get('timestamp','')[:16]}  [{e.get('action','')}]  {e.get('path','')}",
            value=e,
        )
        for e in history
    ]
    choices.append(questionary.Separator())
    choices.append(questionary.Choice("← Volver", value=None))

    return questionary.select(
        "Seleccioná un análisis del historial:",
        choices=choices,
        style=_STYLE,
        use_shortcuts=False,
        instruction="(↑↓  ↵ elegir  Esc cancelar)",
    ).ask()
