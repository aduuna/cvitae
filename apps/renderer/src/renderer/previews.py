"""Regenerate templates/<id>/preview.png from the sample fixture.

uv run --package renderer python -m renderer.previews

Runs trusted templates and fixtures in-process, without the sandbox. The golden render tests call
this when UPDATE_GOLDENS=1.
"""

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import typst

from cvcore.models import CvContent
from cvcore.render import to_render_json
from renderer.settings import Settings
from renderer.templates import LIB_DIR, load_templates

SAMPLE_FIXTURE = "profile-sample"
PREVIEW_PPI = 72


def fixture_data(settings: Settings, name: str) -> dict[str, Any]:
    path = settings.templates_dir / "fixtures" / f"{name}.json"
    return to_render_json(CvContent.model_validate_json(path.read_text()))


def compile_template(
    settings: Settings, template_id: str, data: dict[str, Any], ppi: float = PREVIEW_PPI
) -> tuple[list[bytes], list[str]]:
    """PNG pages and Typst warning messages for a template rendered with `data`."""
    with tempfile.TemporaryDirectory(prefix="preview-") as tmp:
        root = Path(tmp)
        shutil.copytree(settings.templates_dir / LIB_DIR, root / LIB_DIR)
        shutil.copy(settings.templates_dir / template_id / "main.typ", root / "main.typ")
        (root / "data.json").write_text(json.dumps(data))
        compiler = typst.Compiler(
            root=str(root),
            font_paths=typst.Fonts(
                include_system_fonts=False,
                include_embedded_fonts=False,
                font_paths=[str(settings.fonts_dir)],
            ),
            sys_inputs={"paper": "a4"},
        )
        pages, warnings = compiler.compile_with_warnings(
            input=str(root / "main.typ"), format="png", ppi=ppi
        )
    pages = pages if isinstance(pages, list) else [pages]
    return [page for page in pages if isinstance(page, bytes)], [w.message for w in warnings]


def write_previews(settings: Settings) -> list[Path]:
    data = fixture_data(settings, SAMPLE_FIXTURE)
    written = []
    for template_id in load_templates(settings.templates_dir):
        pages, _ = compile_template(settings, template_id, data)
        path = settings.templates_dir / template_id / "preview.png"
        path.write_bytes(pages[0])
        written.append(path)
    return written


if __name__ == "__main__":
    for path in write_previews(Settings()):
        print(f"wrote {path}")
