"""What a PDF measures for the template prompts: exact values, none of the CV's words."""

from pathlib import Path

import typst

from api.ports.llm.design import describe_design
from api.ports.renderer import fake_pdf

FIXTURES = Path(__file__).resolve().parents[3] / "templates" / "fixtures"

BANNER = """\
#set page(paper: "a4", margin: (x: 2cm, y: 1.5cm), fill: none)
#set text(size: 10pt)
#place(top + left, dx: -2cm, dy: -1.5cm, rect(width: 21cm, height: 4cm, fill: rgb("#0b5d5b")))
#text(size: 24pt, fill: white, weight: "bold")[Quiet banner]
#v(3cm)
#text(size: 9pt, fill: rgb("#5f6f6e"), tracking: 0.1em)[#upper[Experience]]
#line(length: 100%, stroke: 1.5pt + rgb("#0b5d5b"))
First paragraph of body text that wraps over more than one line, so the lines have a pitch to
measure. It goes on for a while, in a few sentences, to fill the measure of the page.
#box(fill: rgb("#d9eeec"), inset: 4pt)[A tag]
#place(top + left, dx: 5cm, dy: 12cm, rect(width: 1cm, height: 1cm, fill: rgb("#ffe58a")))
"""


def test_the_sample_cv_measures_as_the_classic_design() -> None:
    design = describe_design((FIXTURES / "sample-cv.pdf").read_bytes())

    assert "Paper: A4 (21.0 x 29.7 cm), 1 page." in design
    assert "LibertinusSerif-Semibold 22pt" in design
    assert "#1f3a5f" in design, "the navy of the headings and rules, exactly"
    assert "horizontal 0.6pt #1f3a5f" in design
    assert "all capitals" in design
    assert "Gaps between consecutive text lines" in design
    assert "Filled areas" not in design, "the placeholder highlight is not part of a design"


def test_it_holds_no_words_of_the_cv() -> None:
    design = describe_design((FIXTURES / "sample-cv.pdf").read_bytes()).casefold()

    for word in ("ama", "owusu", "northwind", "engineer", "ledgerline", "example.com"):
        assert word not in design


def test_a_band_a_rule_and_a_tag_are_measured() -> None:
    pdf = typst.compile(BANNER.encode())

    design = describe_design(pdf)

    assert "#0b5d5b: 21.0 x 4.0 cm, 0.0 to 21.0 cm from the left, 0.0 to 4.0 cm from the top" in (
        design
    )
    assert "#d9eeec" in design
    assert "horizontal 1.5pt #0b5d5b" in design
    assert "#5f6f6e" in design and "all capitals" in design
    assert "#ffe58a" not in design


def test_a_pdf_with_no_text_still_gives_its_paper() -> None:
    pdf = typst.compile(b'#set page(paper: "us-letter")\n#rect(width: 4cm, height: 4cm, fill: red)')

    design = describe_design(pdf)

    assert design.startswith("- Paper: US Letter (21.6 x 27.9 cm), 1 page.")
    assert "Type styles" not in design
    assert "#ff4136" in design.casefold()


def test_a_fake_renderers_pdf_is_measured() -> None:
    design = describe_design(
        fake_pdf({"basics": {"name": "Zoe", "links": []}, "summary": [], "sections": []})
    )

    assert "Helvetica 6pt #000000" in design


def test_a_pdf_that_cannot_be_read_gives_nothing() -> None:
    assert describe_design(b"%PDF-1.7 truncated") == ""
    assert describe_design(b"") == ""
