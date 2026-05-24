#!/usr/bin/env python3
import sys
import re
from pathlib import Path

ROOT      = Path(__file__).parent.parent
PYPROJECT = ROOT / "pyproject.toml"
BRANDING  = ROOT / "menu" / "branding.py"


def _current_version():
    m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', PYPROJECT.read_text(encoding="utf-8"))
    return m.group(1) if m else "unknown"


def _valid_semver(v):
    return bool(re.match(r"^\d+\.\d+\.\d+$", v))


def _replace(path, pattern, repl):
    path.write_text(re.sub(pattern, repl, path.read_text(encoding="utf-8")), encoding="utf-8")


def main():
    dry_run = "--dry-run" in sys.argv
    args    = [a for a in sys.argv[1:] if not a.startswith("--")]

    if not args:
        print(f"Uso: python scripts/bump_version.py [--dry-run] <nueva_version>")
        print(f"Versión actual: {_current_version()}")
        sys.exit(0)

    new = args[0]
    old = _current_version()

    if not _valid_semver(new):
        print(f"Error: '{new}' no es semver válido (ej: 1.2.3)")
        sys.exit(1)

    print(f"Bump: {old} -> {new}")
    print(f"  pyproject.toml   version = \"{old}\" -> \"{new}\"")
    print(f"  menu/branding.py VERSION = \"{old}\" -> \"{new}\"")

    if dry_run:
        print("\n(dry-run: sin cambios)")
        return

    _replace(PYPROJECT, r'(?m)^(version\s*=\s*)"[^"]+"', f'\\1"{new}"')
    _replace(BRANDING,  r'(?m)^(VERSION\s*=\s*)"[^"]+"', f'\\1"{new}"')

    print(f"\nCambios aplicados. Ejecutá:")
    print(f"  git add pyproject.toml menu/branding.py CHANGELOG.md")
    print(f"  git commit -m \"chore: bump version to v{new}\"")
    print(f"  git tag v{new}")
    print(f"  git push && git push --tags")


if __name__ == "__main__":
    main()
