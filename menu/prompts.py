"""
Wrappers de questionary para todos los prompts del menú interactivo.

Principio de navegación:
  - Cada questionary.select incluye '← Volver' como última opción.
  - Si el usuario presiona Esc, questionary devuelve None → volver al menú principal.
  - El valor sentinel BACK indica "volver un nivel".
"""

import sys

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
    questionary.Choice("💥  Impacto de cambios en módulo",  value="impact"),
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
    Solicita la ruta del proyecto.
    - Windows: siempre muestra un select primero (Esc confiable).
    - macOS/Linux sin último proyecto: va directo al prompt de path (Esc funciona).
    - macOS/Linux con último proyecto: muestra el select para reusar o cambiar.
    Devuelve None si el usuario cancela.
    """
    last = get_last_project()
    _NEW = "__new_path__"

    # macOS/Linux sin último proyecto → directo al path prompt (Esc funciona bien)
    if sys.platform != "win32" and not last:
        answer = questionary.path(
            f"{prompt}:",
            only_directories=True,
            style=_STYLE,
        ).ask()
        return answer if answer else None

    # Windows (siempre) o cualquier plataforma con último proyecto → select primero
    choices: list = []
    if last:
        choices.append(questionary.Choice(f"📁  {last}", value=last))
    choices.append(questionary.Choice("📂  Ingresar nueva ruta...", value=_NEW))
    choices.append(questionary.Separator())
    choices.append(questionary.Choice("← Volver", value=BACK))

    sel = questionary.select(
        prompt,
        choices=choices,
        style=_STYLE,
        use_shortcuts=False,
        instruction="(↑↓  ↵ elegir  Esc cancelar)",
    ).ask()

    if sel is None or sel == BACK:
        return None
    if sel != _NEW:
        return sel  # reutilizó el último proyecto

    # Ingreso manual de ruta
    answer = questionary.path(
        "Ruta al proyecto:",
        only_directories=True,
        style=_STYLE,
    ).ask()
    return answer if answer else None


# ── Pedir módulo target ───────────────────────────────────────────────────────

def ask_module(modules: list[str], prompt: str = "Módulo a analizar") -> str | None:
    """
    Muestra la lista de módulos detectados con opción ← Volver.
    Devuelve None si el usuario cancela o elige Volver.
    """
    back_choice = questionary.Choice("← Volver", value=BACK)

    if not modules:
        # Sin módulos detectados: select mínimo con opción libre
        _MANUAL = "__manual__"
        sel = questionary.select(
            f"{prompt}:",
            choices=[
                questionary.Choice("✏️  Ingresar nombre manualmente", value=_MANUAL),
                questionary.Separator(),
                back_choice,
            ],
            style=_STYLE,
            use_shortcuts=False,
            instruction="(↑↓  ↵ elegir  Esc cancelar)",
        ).ask()
        if sel is None or sel == BACK:
            return None
        answer = questionary.text(f"{prompt} (nombre del módulo):", style=_STYLE).ask()
        return answer or None

    last = get_last_module()
    default = last if last in modules else (modules[0] if modules else None)

    if len(modules) > 15:
        # Autocomplete con ← Volver como opción seleccionable
        choices_with_back = modules + ["← Volver"]
        answer = questionary.autocomplete(
            f"{prompt}:",
            choices=choices_with_back,
            default=default or "",
            style=_STYLE,
        ).ask()
        if answer is None or answer == "← Volver":
            return None
        return answer
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
    answer = questionary.select(
        "Formato de salida:",
        choices=[
            questionary.Choice("Todos  (PlantUML + Mermaid + DOT + ASCII)", value="all"),
            questionary.Choice("PlantUML  (.puml)",                          value="plantuml"),
            questionary.Choice("Mermaid   (.mmd)",                           value="mermaid"),
            questionary.Choice("Graphviz  (.dot)",                           value="dot"),
            questionary.Choice("ASCII     (terminal)",                       value="ascii"),
            questionary.Separator(),
            questionary.Choice("← Volver",                                   value=BACK),
        ],
        style=_STYLE,
        use_shortcuts=False,
        instruction="(↑↓  ↵ elegir  Esc cancelar)",
    ).ask()
    if answer is None or answer == BACK:
        return None
    return answer


def ask_focus(modules: list[str]) -> str | None:
    """
    Permite elegir un módulo focal o ver todos.
    Devuelve:
      None  → sin zoom, mostrar todos
      BACK  → cancelar y volver
      str   → módulo elegido
    """
    _ALL = "__all__"

    if len(modules) > 15:
        all_choices = ["📦  Todos los módulos"] + modules + ["← Volver"]
        answer = questionary.autocomplete(
            "Módulo focal (Enter = todos los módulos):",
            choices=all_choices,
            default="📦  Todos los módulos",
            style=_STYLE,
        ).ask()
        if answer is None or answer == "← Volver":
            return BACK
        if answer == "📦  Todos los módulos":
            return None
        return answer if answer in modules else None

    choices = [
        questionary.Choice("📦  Todos los módulos", value=_ALL),
        questionary.Separator(),
    ]
    for m in modules:
        choices.append(questionary.Choice(m, value=m))
    choices += [questionary.Separator(), questionary.Choice("← Volver", value=BACK)]

    answer = questionary.select(
        "¿Hacer zoom en un módulo? (o ver todos):",
        choices=choices,
        style=_STYLE,
        use_shortcuts=False,
        instruction="(↑↓  ↵ elegir  Esc cancelar)",
    ).ask()

    if answer is None or answer == BACK:
        return BACK
    if answer == _ALL:
        return None
    return answer


# ── Pedir formatos de export ──────────────────────────────────────────────────

def ask_export_formats(pdf_available: bool = True) -> list[str] | None:
    """
    Checkbox para elegir qué formatos exportar.
    Devuelve None si el usuario cancela.
    """
    choices = [
        questionary.Choice("HTML  (colores, standalone)",    value="html",     checked=False),
        questionary.Choice("Markdown  (con bloque mermaid)", value="markdown", checked=False),
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
    choices.append(questionary.Choice("← Volver", value=BACK))

    result = questionary.select(
        "Seleccioná un análisis del historial:",
        choices=choices,
        style=_STYLE,
        use_shortcuts=False,
        instruction="(↑↓  ↵ elegir  Esc cancelar)",
    ).ask()
    # BACK (sentinel) y None (Esc) → cancelar
    if result is None or result == BACK:
        return None
    return result
