"""Concurrent PDF text extraction and page rendering: pdfium calls are serialised by one lock."""

import asyncio
from pathlib import Path

from api.ports.llm.pages import pdf_text, pdf_to_pngs

SAMPLE_PDF = (
    Path(__file__).resolve().parents[3] / "templates" / "fixtures" / "sample-cv.pdf"
).read_bytes()
CALLS = 8


async def test_concurrent_text_extraction_and_rendering_all_succeed() -> None:
    texts = asyncio.gather(*[asyncio.to_thread(pdf_text, SAMPLE_PDF) for _ in range(CALLS)])
    renders = asyncio.gather(*[asyncio.to_thread(pdf_to_pngs, SAMPLE_PDF, 1) for _ in range(CALLS)])
    text_results, render_results = await asyncio.gather(texts, renders)

    assert all(text.strip() and pages == 1 for text, pages in text_results)
    assert all(len(images) == 1 and images[0].startswith(b"\x89PNG") for images in render_results)
