"""
Tests para load_project_config en analyzer_utils.py.
Cubre: carga exitosa desde fixture, ausencia de archivo, pyyaml no instalado.
"""

import sys
from pathlib import Path

from analyzer_utils import load_project_config

FIXTURES = Path(__file__).parent / "fixtures"


class TestLoadProjectConfig:

    def test_returns_empty_when_no_yml(self, tmp_path):
        result = load_project_config(tmp_path)
        assert result == {}

    def test_returns_empty_when_nonexistent_dir(self, tmp_path):
        result = load_project_config(tmp_path / "no_existe")
        assert result == {}

    def test_graceful_when_pyyaml_missing(self, tmp_path, monkeypatch):
        yml = tmp_path / "analyzer.yml"
        yml.write_text("sanity:\n  fail_on_cycle: true\n", encoding="utf-8")
        monkeypatch.setitem(sys.modules, "yaml", None)
        result = load_project_config(tmp_path)
        assert result == {}

    def test_loads_sanity_section(self):
        pytest_importorskip_yaml()
        result = load_project_config(FIXTURES / "with_analyzer_yml")
        sanity = result.get("sanity", {})
        assert sanity.get("fail_on_cycle") is True
        assert sanity.get("fail_on_score_below") == 70
        assert sanity.get("output_dir") == "reports/sanity"

    def test_loads_impact_section(self):
        pytest_importorskip_yaml()
        result = load_project_config(FIXTURES / "with_analyzer_yml")
        impact = result.get("impact", {})
        assert impact.get("default_module") == "app"
        assert impact.get("output_dir") == "reports/impact"

    def test_loads_analyzer_section(self):
        pytest_importorskip_yaml()
        result = load_project_config(FIXTURES / "with_analyzer_yml")
        analyzer = result.get("analyzer", {})
        assert analyzer.get("format") == "mermaid"
        assert analyzer.get("output_dir") == "reports/diagrams"

    def test_returns_empty_on_malformed_yml(self, tmp_path, capsys):
        pytest_importorskip_yaml()
        yml = tmp_path / "analyzer.yml"
        yml.write_text("sanity: [\ninvalid yaml", encoding="utf-8")
        result = load_project_config(tmp_path)
        assert result == {}
        captured = capsys.readouterr()
        assert "analyzer.yml" in captured.out


def pytest_importorskip_yaml():
    import importlib
    try:
        importlib.import_module("yaml")
    except ImportError:
        import pytest
        pytest.skip("pyyaml no instalado")
