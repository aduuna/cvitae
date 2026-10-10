"""PDF pages as PNG images, for providers that read images but not PDFs (MiMo)."""

import io

import pypdfium2

from api.errors import ValidationFailed

# A CV rarely runs past a few pages; later pages are not sent.
MAX_PAGES = 6
# 2x the PDF's 72 dpi: about 1190 x 1684 pixels for an A4 page, sharp enough for small print.
SCALE = 2.0


def pdf_to_pngs(data: bytes, max_pages: int = MAX_PAGES, scale: float = SCALE) -> list[bytes]:
    try:
        document = pypdfium2.PdfDocument(data)
    except pypdfium2.PdfiumError as exc:
        raise ValidationFailed(
            "This PDF could not be read. Save it again from your editor, or paste the text."
        ) from exc
    try:
        images = []
        for index in range(min(len(document), max_pages)):
            bitmap = document[index].render(scale=scale)
            buffer = io.BytesIO()
            bitmap.to_pil().save(buffer, format="PNG", optimize=True)
            images.append(buffer.getvalue())
        return images
    finally:
        document.close()
