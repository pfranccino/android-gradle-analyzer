#!/usr/bin/env python3
"""
Extrae las notas de release del CHANGELOG.md para una versión dada.

Uso:
    python scripts/extract_changelog.py 1.2.0

Imprime a stdout la sección entre `## [1.2.0]` y la siguiente cabecera `## [...]`.
Si no encuentra la versión, sale con código 1.
"""
import re
import sys
from pathlib import Path

ROOT      = Path(__file__).parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"


def extract(version: str, text: str) -> str | None:
    pattern = rf'^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)'
    m = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else None


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: extract_changelog.py <version>", file=sys.stderr)
        return 2

    version = sys.argv[1].lstrip("v")
    if not CHANGELOG.exists():
        print(f"CHANGELOG no encontrado: {CHANGELOG}", file=sys.stderr)
        return 1

    section = extract(version, CHANGELOG.read_text(encoding="utf-8"))
    if section is None:
        print(f"Versión {version} no encontrada en CHANGELOG", file=sys.stderr)
        return 1

    print(section)
    return 0


if __name__ == "__main__":
    sys.exit(main())
