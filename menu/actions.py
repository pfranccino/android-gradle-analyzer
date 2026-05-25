"""
Orquesta los tres scripts existentes importando sus clases directamente.
No usa subprocess — import directo para reutilizar lógica sin overhead.
"""

import sys
import io
from pathlib import Path


# ── helpers ──────────────────────────────────────────────────────────────────

def _capture(fn):
    """Ejecuta fn() capturando stdout; devuelve (result, captured_text)."""
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        result = fn()
    finally:
        sys.stdout = old_stdout
    return result, buf.getvalue()


# ── acciones públicas ─────────────────────────────────────────────────────────

def run_internal(
    path: str,
    fmt: str = "all",
    exclude: list[str] | None = None,
    output_dir: str = "diagrams",
    config: str | None = None,
) -> dict:
    """
    Analiza dependencias internas de un módulo Android.

    Returns:
        dict con ok (bool), outputs (list[str]), summary (str)
    """
    from gradle_analyzer import GradleDependencyAnalyzer

    try:
        analyzer = GradleDependencyAnalyzer(
            base_path=path,
            config_path=config,
            exclude=exclude or [],
        )

        def _run():
            analyzer.scan_modules()
            analyzer.analyze_gradle_dependencies()
            analyzer.save_all(output_dir=output_dir, fmt=fmt)

        _, log = _capture(_run)

        output_path = Path(output_dir)
        outputs = [str(f) for f in output_path.iterdir() if f.is_file()] if output_path.exists() else []

        summary = analyzer.generate_report()
        cycles  = analyzer.detect_dependency_cycles()

        return {
            "ok":      True,
            "outputs": outputs,
            "summary": summary,
            "cycles":  cycles,
            "modules": analyzer.modules,
            "log":     log,
        }
    except Exception as exc:
        return {"ok": False, "outputs": [], "summary": str(exc), "cycles": [], "modules": [], "log": ""}


def run_external(
    project: str,
    module: str,
    fmt: str = "all",
    output_dir: str = "external-calls",
    config: str | None = None,
) -> dict:
    """
    Detecta qué módulos externos llaman al módulo dado.

    Returns:
        dict con ok (bool), outputs (list[str]), summary (str)
    """
    from external_callers import ExternalCallersAnalyzer

    try:
        analyzer = ExternalCallersAnalyzer(
            project_root=project,
            target_module=module,
            config_path=config,
        )

        def _run():
            analyzer.scan_all_modules()
            analyzer.analyze_external_calls()
            analyzer.save_all(output_dir=output_dir, fmt=fmt)

        _, log = _capture(_run)

        output_path = Path(output_dir)
        outputs = [str(f) for f in output_path.iterdir() if f.is_file()] if output_path.exists() else []

        summary = analyzer.generate_report()

        return {
            "ok":      True,
            "outputs": outputs,
            "summary": summary,
            "callers": dict(analyzer.external_callers),
            "log":     log,
        }
    except Exception as exc:
        return {"ok": False, "outputs": [], "summary": str(exc), "callers": {}, "log": ""}


def run_impact(
    project: str,
    module: str,
    fmt: str = "all",
    output_dir: str = "impact",
    config: str | None = None,
) -> dict:
    from gradle_impact import ImpactAnalyzer

    try:
        analyzer = ImpactAnalyzer(
            project_root=project,
            target_module=module,
            config_path=config,
        )

        def _run():
            analyzer.scan_and_build_graph()
            analyzer.compute_impact()
            analyzer.save_all(output_dir=output_dir, fmt=fmt)

        _, log = _capture(_run)

        output_path = Path(output_dir)
        outputs = [str(f) for f in output_path.iterdir() if f.is_file()] if output_path.exists() else []

        return {
            "ok":      True,
            "outputs": outputs,
            "summary": analyzer.generate_report(),
            "impacted": dict(analyzer.impacted),
            "log":     log,
        }
    except Exception as exc:
        return {"ok": False, "outputs": [], "summary": str(exc), "impacted": {}, "log": ""}


def run_sanity(
    path: str,
    output_dir: str = "sanity",
    config: str | None = None,
) -> dict:
    """
    Calcula métricas de sanidad (Ca/Ce/I, SDP, score 0-100).

    Returns:
        dict con ok (bool), outputs (list[str]), summary (str), score (int)
    """
    from gradle_sanity import GradleSanityAnalyzer

    try:
        analyzer = GradleSanityAnalyzer(base_path=path, config_path=config)

        def _run():
            analyzer.analyze()
            analyzer.save_report(output_dir=output_dir)

        _, log = _capture(_run)

        output_path = Path(output_dir)
        outputs = [str(f) for f in output_path.iterdir() if f.is_file()] if output_path.exists() else []

        summary = analyzer.generate_report()
        score   = analyzer.compute_score()

        # métricas por módulo: {module: {ca, ce, instability}}
        metrics = {
            m: {
                "ca": analyzer.ca.get(m, 0),
                "ce": analyzer.ce.get(m, 0),
                "I":  round(analyzer.instability.get(m, 0.0), 2),
            }
            for m in analyzer._dep.modules
        }

        return {
            "ok":      True,
            "outputs": outputs,
            "summary": summary,
            "score":   score,
            "metrics": metrics,
            "modules": analyzer._dep.modules,
            "log":     log,
        }
    except Exception as exc:
        return {"ok": False, "outputs": [], "summary": str(exc), "score": None, "metrics": {}, "modules": [], "log": ""}
