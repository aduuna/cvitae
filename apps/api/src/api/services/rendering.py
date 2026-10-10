"""Preview and PDF export of a CV through the renderer."""

import re
import unicodedata
import uuid
from dataclasses import dataclass
from urllib.parse import quote

from api.errors import Conflict
from api.ports.renderer import RendererClient
from api.repositories.documents import DocumentRepository
from api.services.documents import get_document
from cvcore.models import CvContent
from cvcore.render import find_placeholders, to_render_json
from cvcore.rendering import Paper, SvgPages

DEFAULT_PAPER: Paper = "a4"


@dataclass(frozen=True)
class Pdf:
    content: bytes
    filename: str

    @property
    def content_disposition(self) -> str:
        """Attachment header with an ASCII fallback and the exact UTF-8 name (RFC 6266)."""
        ascii_name = (
            unicodedata.normalize("NFKD", self.filename).encode("ascii", "ignore").decode()
        ) or "CV.pdf"
        return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(self.filename)}"


async def preview(
    documents: DocumentRepository, renderer: RendererClient, document_id: uuid.UUID
) -> SvgPages:
    """SVG pages of the saved CV. Keeps the stored page count current."""
    document = await get_document(documents, document_id)
    content = CvContent.model_validate(document.content)
    pages = await renderer.render_svg(document.template_id, to_render_json(content), DEFAULT_PAPER)
    if document.page_count != pages.page_count:
        await documents.update(document, page_count=pages.page_count)
    return pages


async def export_pdf(
    documents: DocumentRepository,
    renderer: RendererClient,
    document_id: uuid.UUID,
    *,
    force: bool = False,
) -> Pdf:
    """The CV as a PDF. Refused while placeholders remain, unless `force`."""
    document = await get_document(documents, document_id)
    content = CvContent.model_validate(document.content)
    placeholders = find_placeholders(content)
    if placeholders and not force:
        count = len(placeholders)
        noun = "placeholder" if count == 1 else "placeholders"
        raise Conflict(
            f"This CV still has {count} {noun}. Fill them in, or export anyway.",
            {"placeholders": [ref.model_dump() for ref in placeholders]},
        )
    pdf = await renderer.render_pdf(document.template_id, to_render_json(content), DEFAULT_PAPER)
    return Pdf(content=pdf, filename=pdf_filename(content.basics.name))


def pdf_filename(name: str, company: str | None = None) -> str:
    """`<Name>-CV-<Company>.pdf` when a job is linked, else `<Name>-CV.pdf`."""
    parts = [_slug(name), "CV", _slug(company or "")]
    return "-".join(part for part in parts if part) + ".pdf"


def _slug(text: str) -> str:
    return re.sub(r"[^\w]+", "-", text).strip("-_")
