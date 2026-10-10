import pytest

from api.services.rendering import Pdf, pdf_filename


@pytest.mark.parametrize(
    ("name", "company", "expected"),
    [
        ("Ama Owusu-Mensah", None, "Ama-Owusu-Mensah-CV.pdf"),
        ("Ama Owusu-Mensah", "Harbour Bank", "Ama-Owusu-Mensah-CV-Harbour-Bank.pdf"),
        ("  Zoë   O'Brien ", None, "Zoë-O-Brien-CV.pdf"),
        ("../../etc/passwd", None, "etc-passwd-CV.pdf"),
        ("", None, "CV.pdf"),
    ],
)
def test_pdf_filename(name: str, company: str | None, expected: str) -> None:
    assert pdf_filename(name, company) == expected


def test_content_disposition_has_an_ascii_fallback() -> None:
    pdf = Pdf(content=b"", filename="Zoë-CV.pdf")

    assert pdf.content_disposition == (
        "attachment; filename=\"Zoe-CV.pdf\"; filename*=UTF-8''Zo%C3%AB-CV.pdf"
    )
