#!/usr/bin/env python3
"""
Android Gradle Analyzer — Menú interactivo
Uso: python3 menu.py            ← modo interactivo (recomendado)
     python3 menu.py --quick <accion> <ruta>   ← modo no-interactivo (CI/scripts)
     python3 menu.py --version
"""

import argparse
import sys
import os

# ── Windows: forzar UTF-8 para emojis ────────────────────────────────────────
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except AttributeError:
        pass

from rich.console import Console
from rich.text import Text

from menu.branding import VERSION_STRING, EXIT_LINE
from menu.state   import (
    get_last_project, get_last_module,
    set_last_project, set_last_module,
    add_history_entry, get_history,
)
import menu.prompts  as prompts
import menu.actions  as actions
import menu.ui       as ui
from menu.exporter   import (
    to_html, to_markdown, to_zip, PDF_AVAILABLE,
    open_plantuml_online, render_plantuml_local,
)

from analyzer_utils import list_modules

console = Console()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_project_and_modules() -> tuple[str | None, list[str]]:
    """Pide la ruta al proyecto y devuelve (path, modules)."""
    path = prompts.ask_project_path()
    if not path:
        return None, []
    modules = list_modules(path)
    return path, modules


def _handle_export(last_result: dict | None) -> None:
    """Flujo de exportación de un análisis previo."""
    if not last_result:
        ui.print_error("No hay ningún análisis reciente. Ejecutá primero un análisis.")
        return

    formats = prompts.ask_export_formats(pdf_available=PDF_AVAILABLE)
    if not formats:
        return

    project_name = last_result.get("project_name", "analysis")
    summary      = last_result.get("summary", "")
    mermaid_path = last_result.get("mermaid_path")

    mermaid_content = None
    if mermaid_path:
        from pathlib import Path as _Path
        p = _Path(mermaid_path)
        if p.exists():
            mermaid_content = p.read_text(encoding="utf-8")

    generated = []

    if "html" in formats:
        path = to_html(summary, project_name=project_name)
        generated.append(path)
        console.print(f"  [green]✓[/green] HTML: [cyan]{path}[/cyan]")

    if "pdf" in formats:
        try:
            path = to_pdf(summary, project_name=project_name)
            generated.append(path)
            console.print(f"  [green]✓[/green] PDF: [cyan]{path}[/cyan]")
        except RuntimeError as exc:
            console.print(f"  [yellow]⚠[/yellow] PDF: {exc}")

    if "markdown" in formats:
        path = to_markdown(summary, mermaid_content=mermaid_content, project_name=project_name)
        generated.append(path)
        console.print(f"  [green]✓[/green] Markdown: [cyan]{path}[/cyan]")

    if "zip" in formats:
        dirs = ["diagrams", "external-calls", "sanity"]
        path = to_zip(dirs_to_pack=dirs, project_name=project_name)
        generated.append(path)
        console.print(f"  [green]✓[/green] ZIP: [cyan]{path}[/cyan]")

    if generated:
        ui.print_outputs_panel(generated, title="📤 Exports generados")


def _offer_plantuml_open(outputs: list[str]) -> None:
    """Ofrece abrir el .puml online o renderizarlo localmente."""
    import questionary

    puml_files = [f for f in outputs if f.endswith(".puml")]
    if not puml_files:
        return

    puml = puml_files[0]
    answer = questionary.select(
        "¿Qué hacemos con el diagrama PlantUML?",
        choices=[
            questionary.Choice("Abrir en plantuml.com (browser)", value="online"),
            questionary.Choice("Renderizar localmente (plantuml en PATH)", value="local"),
            questionary.Choice("← Nada, continuar", value=None),
        ],
        instruction="(↑↓  ↵ elegir  Esc omitir)",
    ).ask()

    if answer == "online":
        ok = open_plantuml_online(puml)
        console.print("  [green]✓[/green] Browser abierto." if ok else "  [yellow]⚠[/yellow] No se pudo abrir el browser.")
    elif answer == "local":
        ok, msg = render_plantuml_local(puml)
        console.print(f"  [green]✓[/green] {msg}" if ok else f"  [yellow]⚠[/yellow] {msg}")


def _post_analysis(result: dict, action: str, project: str, module: str | None) -> dict:
    """
    Acciones comunes después de cada análisis:
    muestra outputs, agrega al historial, ofrece export/PlantUML.
    Devuelve un dict con contexto para exportación posterior.
    """
    if not result["ok"]:
        ui.print_error(result["summary"])
        return {}

    outputs = result.get("outputs", [])
    ui.print_outputs_panel(outputs)
    ui.print_summary(result.get("summary", ""))

    # Métricas de sanidad si están disponibles
    metrics = result.get("metrics")
    score   = result.get("score")
    if metrics and isinstance(metrics, dict) and metrics and "ca" in next(iter(metrics.values()), {}):
        ui.print_metrics_table(metrics, score=score)

    add_history_entry(project, module, action, outputs)
    set_last_project(project)
    if module:
        set_last_module(module)

    _offer_plantuml_open(outputs)

    # Ofrecer export inmediato
    if prompts.ask_confirm("¿Querés exportar este análisis ahora?", default=False):
        mermaid_files = [f for f in outputs if f.endswith(".mmd")]
        last_result = {
            "summary":      result.get("summary", ""),
            "project_name": (module or "analysis"),
            "mermaid_path": mermaid_files[0] if mermaid_files else None,
        }
        _handle_export(last_result)
        return last_result

    mermaid_files = [f for f in outputs if f.endswith(".mmd")]
    return {
        "summary":      result.get("summary", ""),
        "project_name": (module or "analysis"),
        "mermaid_path": mermaid_files[0] if mermaid_files else None,
    }


# ── Acciones del menú ──────────────────────────────────────────────────────────

def action_internal(last_result: dict) -> dict:
    path, modules = _get_project_and_modules()
    if not path:
        return last_result

    fmt = prompts.ask_format()
    if not fmt:
        return last_result

    with ui.analysis_spinner("Analizando dependencias internas..."):
        result = actions.run_internal(path=path, fmt=fmt, output_dir="diagrams")

    new_ctx = _post_analysis(result, "internal", path, None)
    return new_ctx or last_result


def action_external(last_result: dict) -> dict:
    path, modules = _get_project_and_modules()
    if not path:
        return last_result

    module = prompts.ask_module(modules, "Módulo target (quién recibe las llamadas)")
    if not module:
        return last_result

    fmt = prompts.ask_format()
    if not fmt:
        return last_result

    with ui.analysis_spinner(f"Buscando llamadas externas a '{module}'..."):
        result = actions.run_external(project=path, module=module, fmt=fmt, output_dir="external-calls")

    new_ctx = _post_analysis(result, "external", path, module)
    return new_ctx or last_result


def action_sanity(last_result: dict) -> dict:
    path, modules = _get_project_and_modules()
    if not path:
        return last_result

    with ui.analysis_spinner("Calculando métricas de sanidad..."):
        result = actions.run_sanity(path=path, output_dir="sanity")

    # Para sanidad mostramos la tabla de métricas inmediatamente
    if result["ok"]:
        outputs = result.get("outputs", [])
        ui.print_outputs_panel(outputs)
        ui.print_metrics_table(result.get("metrics", {}), score=result.get("score"))
        ui.print_summary(result.get("summary", ""))

        add_history_entry(path, None, "sanity", outputs)
        set_last_project(path)

        if prompts.ask_confirm("¿Querés exportar el reporte ahora?", default=False):
            last_result_ctx = {
                "summary":      result.get("summary", ""),
                "project_name": "sanity",
                "mermaid_path": None,
            }
            _handle_export(last_result_ctx)
            return last_result_ctx

        return {
            "summary":      result.get("summary", ""),
            "project_name": "sanity",
            "mermaid_path": None,
        }
    else:
        ui.print_error(result["summary"])
        return last_result


def action_history() -> None:
    history = get_history()
    ui.print_history_table(history)

    entry = prompts.ask_history_entry(history)
    if entry:
        console.print(f"\n[dim]Path:[/dim] [cyan]{entry.get('path')}[/cyan]")
        if entry.get("module"):
            console.print(f"[dim]Módulo:[/dim] [cyan]{entry.get('module')}[/cyan]")
        console.print(f"[dim]Acción:[/dim] {entry.get('action')}")
        outputs = entry.get("outputs", [])
        if outputs:
            ui.print_outputs_panel(outputs, title="📂 Archivos de ese análisis")


# ── Quick mode (no-interactivo) ────────────────────────────────────────────────

def quick_mode(action: str, path: str) -> None:
    """
    Modo no-interactivo: python3 menu.py --quick <accion> <ruta>
    Acciones: internal, external <modulo>, sanity
    """
    import shlex

    console.print(f"[dim]⚡ Quick mode: {action} · {path}[/dim]")

    if action == "internal":
        result = actions.run_internal(path=path)
    elif action.startswith("external "):
        parts  = shlex.split(action)
        module = parts[1] if len(parts) > 1 else ""
        result = actions.run_external(project=path, module=module)
    elif action == "sanity":
        result = actions.run_sanity(path=path)
    else:
        console.print(f"[red]Acción desconocida: {action}[/red]")
        sys.exit(1)

    if result["ok"]:
        console.print(result["summary"])
        sys.exit(0)
    else:
        console.print(f"[red]{result['summary']}[/red]")
        sys.exit(1)


# ── Loop principal ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Android Gradle Analyzer — Menú interactivo (v{VERSION_STRING})"
    )
    parser.add_argument(
        "--version", action="version",
        version=VERSION_STRING,
    )
    parser.add_argument(
        "--quick",
        nargs="+",
        metavar=("ACCION", "RUTA"),
        help='Modo no-interactivo: --quick sanity /ruta/proyecto',
    )

    args = parser.parse_args()

    if args.quick:
        if len(args.quick) < 2:
            console.print("[red]--quick requiere: <accion> <ruta>[/red]")
            sys.exit(1)
        quick_mode(action=" ".join(args.quick[:-1]), path=args.quick[-1])
        return

    # ── Modo interactivo ──────────────────────────────────────────────────────
    last_project = get_last_project()
    last_modules_count = 0
    if last_project:
        mods = list_modules(last_project)
        last_modules_count = len(mods)

    ui.print_header(project_path=last_project, n_modules=last_modules_count)

    last_result: dict = {}

    while True:
        choice = prompts.main_menu()

        if choice is None or choice == "quit":
            break

        console.print()  # separador visual

        if choice == "internal":
            last_result = action_internal(last_result)

        elif choice == "external":
            last_result = action_external(last_result)

        elif choice == "sanity":
            last_result = action_sanity(last_result)

        elif choice == "export":
            _handle_export(last_result or None)

        elif choice == "history":
            action_history()

        console.print()

    # ── Exit line ─────────────────────────────────────────────────────────────
    console.print(f"\n[dim]{EXIT_LINE}[/dim]\n")


if __name__ == "__main__":
    main()
