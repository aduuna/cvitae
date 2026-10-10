"""Template metadata from templates/<id>/meta.toml."""

import tomllib
from pathlib import Path

from cvcore.rendering import TemplateMeta

LIB_DIR = "_lib"


def load_templates(templates_dir: Path) -> dict[str, TemplateMeta]:
    """Every folder with a meta.toml and a main.typ, keyed by folder name."""
    found: dict[str, TemplateMeta] = {}
    for folder in sorted(templates_dir.iterdir()):
        meta = folder / "meta.toml"
        if folder.name.startswith("_") or not meta.is_file() or not (folder / "main.typ").is_file():
            continue
        found[folder.name] = TemplateMeta(id=folder.name, **tomllib.loads(meta.read_text()))
    return found
