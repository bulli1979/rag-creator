from __future__ import annotations

from pathlib import Path

_SKIP_DIR_NAMES = {
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".idea",
    ".vs",
}


def iter_files_recursive(root_dir: str) -> list[tuple[str, str]]:
    """
    Gibt Dateien unter root rekursiv zurueck:
    (absoluter_pfad, relativer_pfad_mit_slash).
    """
    root = Path(root_dir).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Ordner nicht gefunden: {root_dir}")

    result: list[tuple[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        result.append((str(path), rel))
    return result
