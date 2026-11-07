"""The renderer's HTTP contract, shared by the renderer service and the api's client."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

Paper = Literal["a4", "us-letter"]
OutputFormat = Literal["pdf", "svg"]
RenderErrorCode = Literal["compile_error", "timeout", "limit_exceeded", "forbidden_import"]


class RenderRequest(BaseModel):
    """Either `template_id` with `files` holding only data.json (structured CVs), or a full `files`
    map with main.typ (ejected CVs). The renderer always adds `_lib/`."""

    files: dict[str, str]
    template_id: str | None = None
    format: OutputFormat = "svg"
    paper: Paper = "a4"
    source_links: bool = False
    """SVG previews only: link each part of the CV to its form field (`cv:<id>`), so a click on
    the preview can open it. Ignored for PDF."""

    @model_validator(mode="after")
    def _template_or_main(self) -> Self:
        if self.template_id is None and "main.typ" not in self.files:
            raise ValueError("give template_id, or files with main.typ")
        if self.template_id is not None and set(self.files) - {"data.json"}:
            raise ValueError("with template_id, files may hold only data.json")
        return self


class SvgPages(BaseModel):
    pages: list[str]
    page_count: int


class Diagnostic(BaseModel):
    message: str
    line: int | None = None
    column: int | None = None
    file: str | None = None


class RenderError(BaseModel):
    code: RenderErrorCode
    diagnostics: list[Diagnostic]


class TemplateMeta(BaseModel):
    # Defaults are required in the serialization schema, so generated API types mark `custom` as
    # always present.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    id: str
    name: str
    description: str
    paper_sizes: list[Paper]
    target_pages: int
    custom: bool = False
    """False for the templates in the repository; true for one the user made from their own CV
    (docs/PRODUCT.md, 6, Custom templates)."""
