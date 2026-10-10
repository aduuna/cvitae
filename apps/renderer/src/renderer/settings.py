"""Renderer settings. Defaults point into the repository; the container sets the directories."""

from pathlib import Path

from pydantic_settings import BaseSettings

_REPO = Path(__file__).resolve().parents[4]

MB = 1024 * 1024


class Settings(BaseSettings):
    templates_dir: Path = _REPO / "templates"
    fonts_dir: Path = _REPO / "apps" / "renderer" / "fonts"

    # Sandbox limits (docs/BACKEND.md, Sandboxing).
    cpu_seconds: int = 10
    wall_seconds: float = 15
    memory_bytes: int = 768 * MB
    max_source_bytes: int = 256 * 1024
    max_files: int = 20
    max_data_bytes: int = 256 * 1024
    max_pages: int = 10
    max_pdf_bytes: int = 5 * MB
