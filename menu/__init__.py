"""
menu/ — Módulo de menú interactivo para android-gradle-analyzer.

Entry points:
  python3 menu.py               ← uso directo (repo clonado)
  gradle-analyzer-menu          ← instalado via pipx
"""

import argparse
import sys
import os

# ── Windows: forzar UTF-8 para emojis ────────────────────────────────────────
def _setup_utf8():
    if sys.platform == "win32":
        os.environ.setdefault("PYTHONUTF8", "1")
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
            sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except AttributeError:
            pass


# ── Imports lazy para acelerar el arranque ────────────────────────────────────
def _get_deps():
    from rich.console import Console
    from menu.branding import VERSION_STRING, EXIT_LINE
    from menu.state import (
        get_last_project, set_last_project, set_last_module,
        add_history_entry, get_history,
    )
    import menu.prompts as prompts
    import menu.actions as actions
    import menu.ui as ui
    from menu.exporter import (
        to_html, to_pdf, to_markdown, to_zip, PDF_AVAILABLE,
        open_plantuml_online, render_plantuml_local,
    )
    from analyzer_utils import list_modules
    return (
        Console(), VERSION_STRING, EXIT_LINE,
        get_last_project, set_last_project, set_last_module,
        add_history_entry, get_history,
        prompts, actions, ui,
        to_html, to_pdf, to_markdown, to_zip, PDF_AVAILABLE,
        open_plantuml_online, render_plantuml_local,
        list_modules,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_project_and_modules(prompts, list_modules):
    path = prompts.ask_project_path()
    if not path:
        return None, []
    return path, list_modules(path)


def _handle_export(last_result, prompts, ui, console,
                   to_html, to_pdf, to_markdown, to_zip, PDF_AVAILABLE):
    if not last_result:
        ui.print_error("No hay ningún análisis reciente. Ejecutá primero un análisis.")
        return

    formats = prompts.ask_export_formats(pdf_available=PDF_AVAILABLE)
    if not formats:
        return

    project_name  = last_result.get("project_name", "analysis")
    summary       = last_result.get("summary", "")
    mermaid_path  = last_result.get("mermaid_path")

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
        path = to_zip(dirs_to_pack=["diagrams", "external-calls", "sanity"],
                      project_name=project_name)
        generated.append(path)
        console.print(f"  [green]✓[/green] ZIP: [cyan]{path}[/cyan]")

    if generated:
        ui.print_outputs_panel(generated, title="📤 Exports generados")


def _offer_plantuml_open(outputs, console, open_plantuml_online, render_plantuml_local):
    import questionary
    puml_files = [f for f in outputs if f.endswith(".puml")]
    if not puml_files:
        return
    puml   = puml_files[0]
    answer = questionary.select(
        "¿Qué hacemos con el diagrama PlantUML?",
        choices=[
            questionary.Choice("Abrir en plantuml.com (browser)",      value="online"),
            questionary.Choice("Renderizar localmente (plantuml en PATH)", value="local"),
            questionary.Choice("← Nada, continuar",                    value=None),
        ],
        instruction="(↑↓  ↵ elegir  Esc omitir)",
    ).ask()
    if answer == "online":
        ok = open_plantuml_online(puml)
        console.print("  [green]✓[/green] Browser abierto." if ok else
                      "  [yellow]⚠[/yellow] No se pudo abrir el browser.")
    elif answer == "local":
        ok, msg = render_plantuml_local(puml)
        console.print(f"  [green]✓[/green] {msg}" if ok else f"  [yellow]⚠[/yellow] {msg}")


def _post_analysis(result, action, project, module,
                   ui, prompts, console,
                   add_history_entry, set_last_project, set_last_module,
                   open_plantuml_online, render_plantuml_local,
                   to_html, to_pdf, to_markdown, to_zip, PDF_AVAILABLE):
    if not result["ok"]:
        ui.print_error(result["summary"])
        return {}

    outputs = result.get("outputs", [])
    ui.print_outputs_panel(outputs)
    ui.print_summary(result.get("summary", ""))

    metrics = result.get("metrics")
    score   = result.get("score")
    if metrics and isinstance(metrics, dict) and metrics and \
            "ca" in next(iter(metrics.values()), {}):
        ui.print_metrics_table(metrics, score=score)

    add_history_entry(project, module, action, outputs)
    set_last_project(project)
    if module:
        set_last_module(module)

    _offer_plantuml_open(outputs, console, open_plantuml_online, render_plantuml_local)

    if prompts.ask_confirm("¿Querés exportar este análisis ahora?", default=False):
        mermaid_files = [f for f in outputs if f.endswith(".mmd")]
        ctx = {
            "summary":      result.get("summary", ""),
            "project_name": (module or "analysis"),
            "mermaid_path": mermaid_files[0] if mermaid_files else None,
        }
        _handle_export(ctx, prompts, ui, console,
                       to_html, to_pdf, to_markdown, to_zip, PDF_AVAILABLE)
        return ctx

    mermaid_files = [f for f in outputs if f.endswith(".mmd")]
    return {
        "summary":      result.get("summary", ""),
        "project_name": (module or "analysis"),
        "mermaid_path": mermaid_files[0] if mermaid_files else None,
    }


# ── Acciones ──────────────────────────────────────────────────────────────────

def _action_internal(last_result, deps):
    (console, _, _, _, set_last_project, set_last_module, add_history_entry, _,
     prompts, actions, ui, to_html, to_pdf, to_markdown, to_zip, PDF_AVAILABLE,
     open_plantuml_online, render_plantuml_local, list_modules) = deps

    path, _ = _get_project_and_modules(prompts, list_modules)
    if not path:
        return last_result
    fmt = prompts.ask_format()
    if not fmt:
        return last_result
    with ui.analysis_spinner("Analizando dependencias internas..."):
        result = actions.run_internal(path=path, fmt=fmt, output_dir="diagrams")
    ctx = _post_analysis(result, "internal", path, None,
                         ui, prompts, console, add_history_entry,
                         set_last_project, set_last_module,
                         open_plantuml_online, render_plantuml_local,
                         to_html, to_pdf, to_markdown, to_zip, PDF_AVAILABLE)
    return ctx or last_result


def _action_external(last_result, deps):
    (console, _, _, _, set_last_project, set_last_module, add_history_entry, _,
     prompts, actions, ui, to_html, to_pdf, to_markdown, to_zip, PDF_AVAILABLE,
     open_plantuml_online, render_plantuml_local, list_modules) = deps

    path, modules = _get_project_and_modules(prompts, list_modules)
    if not path:
        return last_result
    module = prompts.ask_module(modules, "Módulo target (quién recibe las llamadas)")
    if not module:
        return last_result
    fmt = prompts.ask_format()
    if not fmt:
        return last_result
    with ui.analysis_spinner(f"Buscando llamadas externas a '{module}'..."):
        result = actions.run_external(project=path, module=module, fmt=fmt,
                                      output_dir="external-calls")
    ctx = _post_analysis(result, "external", path, module,
                         ui, prompts, console, add_history_entry,
                         set_last_project, set_last_module,
                         open_plantuml_online, render_plantuml_local,
                         to_html, to_pdf, to_markdown, to_zip, PDF_AVAILABLE)
    return ctx or last_result


def _action_sanity(last_result, deps):
    (console, _, _, get_last_project, set_last_project, _, add_history_entry, _,
     prompts, actions, ui, to_html, to_pdf, to_markdown, to_zip, PDF_AVAILABLE,
     open_plantuml_online, render_plantuml_local, list_modules) = deps

    path, _ = _get_project_and_modules(prompts, list_modules)
    if not path:
        return last_result
    with ui.analysis_spinner("Calculando métricas de sanidad..."):
        result = actions.run_sanity(path=path, output_dir="sanity")
    if result["ok"]:
        outputs = result.get("outputs", [])
        ui.print_outputs_panel(outputs)
        ui.print_metrics_table(result.get("metrics", {}), score=result.get("score"))
        ui.print_summary(result.get("summary", ""))
        add_history_entry(path, None, "sanity", outputs)
        set_last_project(path)
        ctx = {"summary": result.get("summary", ""),
               "project_name": "sanity", "mermaid_path": None}
        if prompts.ask_confirm("¿Querés exportar el reporte ahora?", default=False):
            _handle_export(ctx, prompts, ui, console,
                           to_html, to_pdf, to_markdown, to_zip, PDF_AVAILABLE)
        return ctx
    else:
        ui.print_error(result["summary"])
        return last_result


def _action_impact(last_result, deps):
    (console, _, _, _, set_last_project, set_last_module, add_history_entry, _,
     prompts, actions, ui, to_html, to_pdf, to_markdown, to_zip, PDF_AVAILABLE,
     open_plantuml_online, render_plantuml_local, list_modules) = deps

    path, modules = _get_project_and_modules(prompts, list_modules)
    if not path:
        return last_result
    module = prompts.ask_module(modules, "Módulo a analizar (qué pasa si cambia)")
    if not module:
        return last_result
    fmt = prompts.ask_format()
    if not fmt:
        return last_result
    with ui.analysis_spinner(f"Calculando impacto de '{module}'..."):
        result = actions.run_impact(project=path, module=module, fmt=fmt,
                                    output_dir="impact")
    ctx = _post_analysis(result, "impact", path, module,
                         ui, prompts, console, add_history_entry,
                         set_last_project, set_last_module,
                         open_plantuml_online, render_plantuml_local,
                         to_html, to_pdf, to_markdown, to_zip, PDF_AVAILABLE)
    return ctx or last_result


def _action_history(deps):
    (console, _, _, _, _, _, _, get_history,
     prompts, _, ui, *_) = deps

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


# ── Quick mode ────────────────────────────────────────────────────────────────

def _quick_mode(action: str, path: str, actions, console) -> None:
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
    elif action.startswith("impact "):
        parts  = shlex.split(action)
        module = parts[1] if len(parts) > 1 else ""
        result = actions.run_impact(project=path, module=module)
    else:
        console.print(f"[red]Acción desconocida: {action}[/red]")
        sys.exit(1)

    if result["ok"]:
        console.print(result["summary"])
        sys.exit(0)
    else:
        console.print(f"[red]{result['summary']}[/red]")
        sys.exit(1)


# ── Entrada principal ─────────────────────────────────────────────────────────

def main() -> None:
    """
    Entry point para:
      - python3 menu.py               (via wrapper menu.py)
      - gradle-analyzer-menu          (via pipx / pyproject.toml entry point)
    """
    _setup_utf8()
    deps = _get_deps()
    (console, VERSION_STRING, EXIT_LINE,
     get_last_project, set_last_project, set_last_module,
     add_history_entry, get_history,
     prompts, actions, ui,
     to_html, to_pdf, to_markdown, to_zip, PDF_AVAILABLE,
     open_plantuml_online, render_plantuml_local,
     list_modules) = deps

    parser = argparse.ArgumentParser(
        description=f"Android Gradle Analyzer — Menú interactivo ({VERSION_STRING})"
    )
    parser.add_argument("--version", action="version", version=VERSION_STRING)
    parser.add_argument(
        "--quick", nargs="+", metavar=("ACCION", "RUTA"),
        help="Modo no-interactivo: --quick sanity /ruta/proyecto",
    )
    args = parser.parse_args()

    if args.quick:
        if len(args.quick) < 2:
            console.print("[red]--quick requiere: <accion> <ruta>[/red]")
            sys.exit(1)
        _quick_mode(" ".join(args.quick[:-1]), args.quick[-1], actions, console)
        return

    # ── Modo interactivo ──────────────────────────────────────────────────────
    last_project = get_last_project()
    last_n = len(list_modules(last_project)) if last_project else 0
    ui.print_header(project_path=last_project, n_modules=last_n)

    last_result: dict = {}

    while True:
        choice = prompts.main_menu()
        if choice is None or choice == "quit":
            break

        console.print()

        if choice == "internal":
            last_result = _action_internal(last_result, deps)
        elif choice == "external":
            last_result = _action_external(last_result, deps)
        elif choice == "sanity":
            last_result = _action_sanity(last_result, deps)
        elif choice == "impact":
            last_result = _action_impact(last_result, deps)
        elif choice == "export":
            _handle_export(last_result or None, prompts, ui, console,
                           to_html, to_pdf, to_markdown, to_zip, PDF_AVAILABLE)
        elif choice == "history":
            _action_history(deps)

        console.print()

    console.print(f"\n[dim]{EXIT_LINE}[/dim]\n")
