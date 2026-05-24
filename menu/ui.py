"""
Helpers de Rich: paneles, tablas, spinners y formateo de resultados.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.text import Text
from rich.align import Align
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from contextlib import contextmanager

from menu.branding import AUTHOR, AUTHOR_URL, VERSION, TOOL_NAME, HEADER_CREDIT

console = Console()


# ── Header ────────────────────────────────────────────────────────────────────

def print_header(project_path: str | None = None, n_modules: int = 0) -> None:
    """Muestra el panel de bienvenida con crédito discreto al autor."""
    title = f"[bold cyan]🤖 {TOOL_NAME}[/bold cyan]  [dim]v{VERSION}[/dim]"
    credit = f"[dim]{HEADER_CREDIT}[/dim]"

    lines = [Text.from_markup(title)]
    if project_path:
        lines.append(Text.from_markup(f"[dim]📁 {project_path}[/dim]"))
    if n_modules:
        lines.append(Text.from_markup(f"[dim]📦 {n_modules} módulos detectados[/dim]"))

    # Combinar líneas de contenido + crédito alineado a la derecha
    content_text = Text()
    for t in lines:
        content_text.append_text(t)
        content_text.append("\n")
    content_text.append_text(Text.from_markup(f"\n{credit}"))

    console.print(Panel(content_text, border_style="cyan", padding=(0, 1)))


# ── Spinner durante análisis ──────────────────────────────────────────────────

@contextmanager
def analysis_spinner(label: str):
    """Context manager que muestra un spinner Rich mientras corre el análisis."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(f"[cyan]{label}[/cyan]")
        yield progress


# ── Tabla de módulos con métricas ─────────────────────────────────────────────

def print_metrics_table(metrics: dict, score: int | None = None) -> None:
    """
    Muestra una tabla con Ca/Ce/I por módulo.
    metrics: {module: {ca, ce, I}}
    """
    if not metrics:
        console.print("[dim]  Sin métricas disponibles.[/dim]")
        return

    table = Table(
        title=f"📊 Métricas de módulos" + (f"  •  Score: {_score_badge(score)}" if score is not None else ""),
        box=box.ROUNDED,
        border_style="dim",
        show_footer=False,
    )
    table.add_column("Módulo",   style="cyan",    no_wrap=True)
    table.add_column("Ca",       justify="center", style="green")
    table.add_column("Ce",       justify="center", style="yellow")
    table.add_column("I",        justify="center")
    table.add_column("Estado",   justify="center")

    for module in sorted(metrics):
        m   = metrics[module]
        ca  = m.get("ca", 0)
        ce  = m.get("ce", 0)
        ins = m.get("I",  0.0)

        # Semáforo de instabilidad
        if ins <= 0.3:
            status = "[green]● estable[/green]"
        elif ins <= 0.7:
            status = "[yellow]● moderado[/yellow]"
        else:
            status = "[red]● inestable[/red]"

        table.add_row(module, str(ca), str(ce), f"{ins:.2f}", status)

    console.print(table)


def _score_badge(score: int | None) -> str:
    if score is None:
        return "?"
    if score >= 80:
        return f"[green]{score}/100[/green]"
    if score >= 60:
        return f"[yellow]{score}/100[/yellow]"
    return f"[red]{score}/100[/red]"


# ── Panel de outputs generados ────────────────────────────────────────────────

def print_outputs_panel(outputs: list[str], title: str = "✅ Archivos generados") -> None:
    """Muestra los archivos generados en un panel."""
    if not outputs:
        console.print(Panel("[dim]No se generaron archivos.[/dim]", title=title, border_style="dim"))
        return

    lines = "\n".join(f"  [dim]•[/dim] [cyan]{p}[/cyan]" for p in sorted(outputs))
    console.print(Panel(lines, title=title, border_style="green", padding=(0, 1)))


# ── Panel de errores ──────────────────────────────────────────────────────────

def print_error(msg: str) -> None:
    console.print(Panel(f"[red]{msg}[/red]", title="❌ Error", border_style="red"))


# ── Tabla de historial ────────────────────────────────────────────────────────

def print_history_table(history: list[dict]) -> None:
    if not history:
        console.print("[dim]  Sin historial disponible.[/dim]")
        return

    table = Table(title="📋 Últimos análisis", box=box.SIMPLE, border_style="dim")
    table.add_column("#",         justify="right",  style="dim")
    table.add_column("Acción",    style="cyan")
    table.add_column("Proyecto",  style="white", no_wrap=False)
    table.add_column("Módulo",    style="dim")
    table.add_column("Fecha",     style="dim")

    for i, entry in enumerate(history, 1):
        table.add_row(
            str(i),
            entry.get("action", ""),
            entry.get("path", ""),
            entry.get("module") or "—",
            entry.get("timestamp", "")[:16],
        )

    console.print(table)


# ── Print summary text ────────────────────────────────────────────────────────

def print_summary(summary: str, max_lines: int = 30) -> None:
    """Muestra el resumen del análisis, truncado a max_lines."""
    lines = summary.splitlines()
    shown = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        shown += f"\n[dim]... ({len(lines) - max_lines} líneas más en el archivo generado)[/dim]"
    console.print(Panel(shown, title="📄 Resumen", border_style="dim", padding=(0, 1)))
