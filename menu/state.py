"""
Persistencia de estado entre sesiones.
Guarda el último proyecto usado y un historial de los últimos 5 análisis.
Ruta: ~/.gradle-analyzer/state.json
"""

import json
from pathlib import Path
from datetime import datetime

STATE_DIR  = Path.home() / ".gradle-analyzer"
STATE_FILE = STATE_DIR / "state.json"

_EMPTY: dict = {
    "last_project": None,
    "last_module":  None,
    "history": [],          # lista de {path, module, action, timestamp, outputs}
}


def _load() -> dict:
    """Carga el estado desde disco; devuelve dict vacío si no existe."""
    if not STATE_FILE.exists():
        return dict(_EMPTY)
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # garantizar claves mínimas
        for key, val in _EMPTY.items():
            data.setdefault(key, val)
        return data
    except Exception:
        return dict(_EMPTY)


def _save(state: dict) -> None:
    """Persiste el estado en disco."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ── API pública ──────────────────────────────────────────────────────────────

def get_last_project() -> str | None:
    return _load().get("last_project")


def get_last_module() -> str | None:
    return _load().get("last_module")


def set_last_project(path: str) -> None:
    state = _load()
    state["last_project"] = path
    _save(state)


def set_last_module(module: str) -> None:
    state = _load()
    state["last_module"] = module
    _save(state)


def add_history_entry(path: str, module: str | None, action: str, outputs: list[str]) -> None:
    """Agrega una entrada al historial (máx 5)."""
    state = _load()
    entry = {
        "path":      path,
        "module":    module,
        "action":    action,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "outputs":   outputs,
    }
    history: list = state.get("history", [])
    history.insert(0, entry)
    state["history"] = history[:5]   # mantener solo los últimos 5
    _save(state)


def get_history() -> list[dict]:
    return _load().get("history", [])
