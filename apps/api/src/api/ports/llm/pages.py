"""PDF pages as PNG images (for providers that read images but not PDFs, and for comparing a
rendered template with the CV it copies) and the text layer of a PDF."""

import io
import threading
from collections.abc import Generator
from contextlib import contextmanager

import pypdfium2

from api.errors import ValidationFailed

# A CV rarely runs past a few pages; later pages are not sent.
MAX_PAGES = 6
# 2x the PDF's 72 dpi: about 1190 x 1684 pixels for an A4 page, sharp enough for small print.
SCALE = 2.0
# pdfium is not thread-safe. Every pypdfium2 call in the API goes through this lock, because
# callers run these functions with asyncio.to_thread.
PDFIUM_LOCK = threading.Lock()


@contextmanager
def open_pdf(data: bytes, unreadable_message: str) -> Generator[pypdfium2.PdfDocument]:
    """Open a PDF under the pdfium lock, closed on exit. Raises ValidationFailed if unreadable."""
    with PDFIUM_LOCK:
        try:
            document = pypdfium2.PdfDocument(data)
        except pypdfium2.PdfiumError as exc:
            raise ValidationFailed(unreadable_message) from exc
        try:
            yield document
        finally:
            document.close()


def pdf_to_pngs(data: bytes, max_pages: int = MAX_PAGES, scale: float = SCALE) -> list[bytes]:
    with open_pdf(
        data,
        "This PDF could not be read. Save it again from your editor, or paste the text.",
    ) as document:
        images = []
        for index in range(min(len(document), max_pages)):
            bitmap = document[index].render(scale=scale)
            buffer = io.BytesIO()
            bitmap.to_pil().save(buffer, format="PNG", optimize=True)
            images.append(buffer.getvalue())
        return images


def pdf_text(data: bytes) -> tuple[str, int]:
    """The text layer of a PDF, page after page, and its page count. Empty text for a scan."""
    with open_pdf(
        data,
        "This PDF could not be read. Save it again from your editor and try again.",
    ) as document:
        pages = [document[index].get_textpage().get_text_range() for index in range(len(document))]
        return "\n".join(pages), len(document)
