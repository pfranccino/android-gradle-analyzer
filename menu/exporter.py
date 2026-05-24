"""
Exporta reportes a formatos compartibles.
Los archivos originales (.puml, .mmd, .txt) NO se tocan.
Este módulo sólo AGREGA nuevos formatos encima de los existentes.
"""

import zipfile
import webbrowser
from pathlib import Path
from datetime import datetime

from rich.console import Console

from menu.branding import EXPORT_FOOTER

# PDF es opcional — weasyprint puede no estar instalado o faltar deps nativas.
# En Windows requiere GTK/Pango (libgobject), que no vienen por defecto.
# Usamos import lazy (solo al llamar to_pdf) para no imprimir nada al cargar el módulo.
import importlib as _importlib

def _try_import_weasyprint():
    """Intenta importar weasyprint en tiempo de ejecución. Devuelve el módulo o None."""
    try:
        return _importlib.import_module("weasyprint")
    except Exception:
        return None

def _pdf_available() -> bool:
    """Comprueba si weasyprint está disponible SIN imprimir nada."""
    import subprocess, sys
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import weasyprint"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False

PDF_AVAILABLE = _pdf_available()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ── HTML ──────────────────────────────────────────────────────────────────────

def to_html(summary: str, dest: str | None = None, project_name: str = "analysis") -> str:
    """
    Genera un HTML rico con el contenido del dashboard capturado.

    Args:
        summary: texto del reporte (str)
        dest:    ruta destino del archivo HTML (auto si None)
        project_name: nombre base para el archivo

    Returns:
        Ruta del archivo generado
    """
    if dest is None:
        dest = f"{project_name}-{_timestamp()}.html"

    # Capturar el summary como HTML usando Rich
    capture_console = Console(record=True, width=100)
    capture_console.print(summary)
    html_body = capture_console.export_html(inline_styles=True)

    # Inyectar footer del autor
    footer_html = f'<p style="color:#888;font-size:0.85em;text-align:center;margin-top:2em;">{EXPORT_FOOTER}</p>'
    html_body = html_body.replace("</body>", f"{footer_html}</body>")

    Path(dest).write_text(html_body, encoding="utf-8")
    return dest


# ── PDF ───────────────────────────────────────────────────────────────────────

def to_pdf(summary: str, dest: str | None = None, project_name: str = "analysis") -> str:
    """
    Genera PDF desde HTML usando weasyprint.
    Requiere: pip install weasyprint

    Returns:
        Ruta del archivo generado
    """
    if not PDF_AVAILABLE:
        raise RuntimeError(
            "weasyprint no está disponible. "
            "En macOS/Linux: pip install weasyprint. "
            "En Windows requiere GTK: ver https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
        )

    wp = _try_import_weasyprint()
    if wp is None:
        raise RuntimeError("No se pudo importar weasyprint.")

    if dest is None:
        dest = f"{project_name}-{_timestamp()}.pdf"

    html_path = to_html(summary, dest=dest + ".tmp.html", project_name=project_name)
    wp.HTML(filename=html_path).write_pdf(dest)
    Path(html_path).unlink(missing_ok=True)
    return dest


# ── Markdown ──────────────────────────────────────────────────────────────────

def to_markdown(
    summary: str,
    mermaid_content: str | None = None,
    dest: str | None = None,
    project_name: str = "analysis",
) -> str:
    """
    Genera un archivo Markdown con el reporte y, si se provee,
    el diagrama Mermaid embebido (GitHub lo renderiza nativamente).

    Returns:
        Ruta del archivo generado
    """
    if dest is None:
        dest = f"{project_name}-{_timestamp()}.md"

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Android Gradle Analyzer — {project_name}",
        f"",
        f"_Generado el {ts}_",
        f"",
        "## Reporte",
        "",
        "```",
        summary,
        "```",
        "",
    ]

    if mermaid_content:
        lines += [
            "## Diagrama de dependencias",
            "",
            "```mermaid",
            mermaid_content,
            "```",
            "",
        ]

    lines += [
        "---",
        f"_{EXPORT_FOOTER}_",
    ]

    Path(dest).write_text("\n".join(lines), encoding="utf-8")
    return dest


# ── ZIP ───────────────────────────────────────────────────────────────────────

def to_zip(
    dirs_to_pack: list[str],
    dest: str | None = None,
    project_name: str = "analysis",
) -> str:
    """
    Empaqueta los directorios de salida (diagrams/, external-calls/, sanity/)
    más cualquier export previo en un único ZIP.

    Args:
        dirs_to_pack: lista de carpetas a incluir
        dest:         ruta destino del ZIP
        project_name: nombre base del archivo

    Returns:
        Ruta del archivo generado
    """
    if dest is None:
        dest = f"analysis-{project_name}-{_timestamp()}.zip"

    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for dir_str in dirs_to_pack:
            dir_path = Path(dir_str)
            if not dir_path.exists():
                continue
            for file_path in dir_path.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, arcname=file_path.relative_to(dir_path.parent))

    return dest


# ── PlantUML online ───────────────────────────────────────────────────────────

def open_plantuml_online(puml_path: str) -> bool:
    """
    Abre el diagram PlantUML en plantuml.com/plantuml usando el contenido
    codificado en hex.
    Devuelve True si se abrió el browser, False si hubo error.
    """
    try:
        content = Path(puml_path).read_text(encoding="utf-8")
        hex_content = content.encode("utf-8").hex()
        url = f"https://www.plantuml.com/plantuml/uml/~h{hex_content}"
        webbrowser.open(url)
        return True
    except Exception:
        return False


# ── PlantUML local ────────────────────────────────────────────────────────────

def render_plantuml_local(puml_path: str) -> tuple[bool, str]:
    """
    Intenta renderizar el .puml a PNG usando plantuml en el PATH.
    Devuelve (éxito, mensaje).
    """
    import shutil
    import subprocess

    if not shutil.which("plantuml"):
        return False, "plantuml no encontrado en el PATH"

    try:
        result = subprocess.run(
            ["plantuml", puml_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            png = Path(puml_path).with_suffix(".png")
            return True, f"PNG generado: {png}"
        return False, result.stderr.strip()
    except Exception as exc:
        return False, str(exc)
