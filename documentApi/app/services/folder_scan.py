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

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".html", ".htm", ".md", ".txt"}


def iter_files_recursive(root_dir: str) -> list[tuple[str, str]]:
    """
    Gibt Dateien unter root rekursiv zurueck:
    (absoluter_pfad, relativer_pfad_mit_slash).
    Filtert auf die Dateiformate, die der Dokument-Parser unterstützt.
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
        if path.suffix.lower() not in _ALLOWED_EXTENSIONS:
            continue
        rel = path.relative_to(root).as_posix()
        result.append((str(path), rel))
    return result
