"""
Tests para menu.actions: el orquestador del menú.
Regresión: el resumen en pantalla debe respetar el foco (no mostrar todo el grafo).
"""

from menu import actions


def _project(root):
    (root / "settings.gradle").write_text(
        "include ':app'\ninclude ':a'\ninclude ':b'\ninclude ':noise'\n", encoding="utf-8")

    def mod(path, body):
        d = root / path
        d.mkdir(parents=True, exist_ok=True)
        (d / "build.gradle").write_text(body, encoding="utf-8")

    mod("app",   "dependencies { implementation project(':a'); implementation project(':noise') }")
    mod("a",     "dependencies { implementation project(':b') }")
    mod("b",     "dependencies {}")
    mod("noise", "dependencies {}")


def test_run_internal_summary_respects_focus(tmp_path):
    """El summary devuelto (lo que se muestra en pantalla y se exporta) debe estar
    centrado en el foco, igual que los archivos — no volcar el grafo completo."""
    _project(tmp_path)
    result = actions.run_internal(
        path=str(tmp_path), fmt="ascii",
        output_dir=str(tmp_path / "out"), focus="a",
    )
    assert result["ok"]
    summary = result["summary"]
    assert "📦 a  ◀ foco" in summary    # el foco
    assert "📦 b" in summary            # su downstream
    assert "noise" not in summary       # ajeno al foco
    assert "📦 app" not in summary      # llamador, no es fila del reporte enfocado
