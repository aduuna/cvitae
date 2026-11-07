from pathlib import Path

import pytest

from cvcore.models import CvContent
from cvcore.user_templates import (
    MAX_SOURCE_BYTES,
    Reference,
    TemplateIssue,
    check_pages,
    check_render,
    check_template,
    is_custom_id,
    mentions_owner,
    new_template_id,
    reference_from_text,
)

TEMPLATES = Path(__file__).resolve().parents[3] / "templates"
VALID = (TEMPLATES / "fixtures" / "user-template.typ").read_text()

UPLOAD_TEXT = """Grace Hopper
Rear admiral and compiler pioneer
grace@navy.example  +1 (555) 010-4477
linkedin.com/in/grace-hopper  https://www.gracehopper.dev/
Led a team that built the first compiler for a business language
Work experience
2019 - 2021 Senior engineer, Navy Labs
"""


def codes(source: str, reference: Reference | None = None) -> list[str]:
    return [issue.code for issue in check_template(source, reference)]


def test_ids_follow_the_renderer_rule_and_are_told_apart() -> None:
    ids = {new_template_id() for _ in range(50)}

    assert len(ids) == 50
    assert all(is_custom_id(i) for i in ids)
    assert all(len(i) == 12 and i.startswith("u-") for i in ids)
    for built_in in ("classic", "compact", "modern", "minimal", "technical"):
        assert not is_custom_id(built_in)
    assert not is_custom_id("u-ABCDEFGHIJ")
    assert not is_custom_id("u-abcdefghi")
    assert not is_custom_id("u-abcdefghij1")
    assert not is_custom_id("x-abcdefghij")


def test_the_built_in_templates_pass_the_checks() -> None:
    sources = sorted(TEMPLATES.glob("*/main.typ"))

    assert len(sources) == 5
    for path in sources:
        assert check_template(path.read_text()) == [], path


def test_a_template_that_follows_the_contract_passes() -> None:
    assert check_template(VALID) == []
    assert check_template(VALID, reference_from_text(UPLOAD_TEXT)) == []


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ('#import "/_lib/cv.typ": *\n', "", "missing_import"),
        ('#let cv = json("data.json")\n', "", "missing_data"),
        ("paper: paper-size()", 'paper: "a4"', "missing_paper"),
        ("#sections(", "#draw(", "missing_sections"),
        (
            '#import "/_lib/cv.typ": *',
            '#import "@preview/cetz:0.3.4": *\n#import "/_lib/cv.typ": *',
            "forbidden_import",
        ),
        (
            '#import "/_lib/cv.typ": *',
            '#import "/other.typ": *\n#import "/_lib/cv.typ": *',
            "forbidden_import",
        ),
        ("#set par(", '#let data = read("data.json")\n#set par(', "forbidden_call"),
        ("#set par(", '#image("photo.png")\n#set par(', "forbidden_call"),
        ("#set par(", '#let p = plugin("x.wasm")\n#set par(', "forbidden_call"),
        ("#set par(", '#let p = eval("1 + 1")\n#set par(', "forbidden_call"),
        ("#set par(", '#let rows = csv("rows.csv")\n#set par(', "forbidden_call"),
        ("#set par(", '#let other = json("other.json")\n#set par(', "forbidden_call"),
        ('font: "Geist"', 'font: "Helvetica"', "unknown_font"),
        ('font: "Geist"', 'font: ("Geist", "Arial")', "unknown_font"),
    ],
)
def test_each_rule_of_the_contract_is_checked(old: str, new: str, expected: str) -> None:
    assert old in VALID

    assert expected in codes(VALID.replace(old, new, 1))


def test_bundled_fonts_pass_in_any_case_and_in_lists() -> None:
    source = VALID.replace('font: "Geist"', 'font: ("geist", "Libertinus Serif", "Geist Mono")')

    assert check_template(source) == []


def test_an_oversized_source_fails() -> None:
    source = VALID + "\n// " + "x" * MAX_SOURCE_BYTES

    assert "too_large" in codes(source)


def test_issues_say_where_they_are() -> None:
    source = VALID.replace("#set par(", '#let data = read("data.json")\n#set par(', 1)

    [issue] = [i for i in check_template(source) if i.code == "forbidden_call"]

    assert issue.line == source[: source.index("read(")].count("\n") + 1
    assert str(issue).startswith(f"line {issue.line}: read() is not allowed")
    assert str(TemplateIssue("too_large", "Too big.")) == "Too big."


def test_comments_and_strings_do_not_trip_the_call_checks() -> None:
    source = VALID + (
        '\n// image("x.png") and read("y") are not used\n'
        '/* nested /* plugin("z") */ still a comment */\n'
        '#let note = "call image( and read( in prose"\n'
        "#let read-more(x) = x\n"
        "#let thread(x) = x\n"
    )

    assert check_template(source) == []


def test_an_unclosed_quote_in_markup_is_not_a_string() -> None:
    assert check_template(VALID + '\n#let dash = [5" wide]\n#let x = [it"s]\n') == []


def test_personal_details_of_the_upload_are_refused() -> None:
    reference = reference_from_text(UPLOAD_TEXT)
    leaks = {
        "copied_name": "// Made for grace   hopper\n",
        "copied_email": '#let mail = "GRACE@navy.example"\n',
        "copied_phone": '#let tel = "+1 555 010 4477"\n',
        "copied_url": '#let site = "https://gracehopper.dev"\n',
    }
    for code, extra in leaks.items():
        assert code in codes(VALID + extra, reference), code
    assert "copied_url" in codes(VALID + '#let li = "linkedin.com/in/grace-hopper"\n', reference)
    # The same lines are fine when the upload does not say them.
    assert codes(VALID + "".join(leaks.values())) == []


def test_issues_never_repeat_the_uploads_text() -> None:
    reference = reference_from_text(UPLOAD_TEXT)
    source = VALID + "".join(
        [
            "// Grace Hopper\n",
            '#let a = "grace@navy.example"\n',
            '#let b = "gracehopper.dev"\n',
            '#let c = "Led a team that built the first compiler for a business language"\n',
        ]
    )

    messages = " ".join(i.message.casefold() for i in check_template(source, reference))

    for secret in ("hopper", "navy", "+1", "compiler"):
        assert secret not in messages


def test_copied_sentences_are_refused_but_labels_and_headings_are_not() -> None:
    reference = reference_from_text(UPLOAD_TEXT)
    long_text = "Led a team that built the first compiler for a business language"

    assert "long_literal" in codes(VALID + f'#let a = "{long_text}"\n', reference)
    assert "copied_text" in codes(VALID + '#let b = "Senior engineer, Navy Labs"\n', reference)
    assert "copied_text" in codes(VALID + '#let c = "Rear admiral"\n', reference)
    # A heading the CV also has is not copied content, and short labels are fine.
    assert codes(VALID + '#let d = "Work experience"\n#let e = "Present"\n', reference) == []


def test_prose_in_markup_is_refused() -> None:
    sentence = "[Passionate engineer who builds reliable systems for banks and retailers]"

    assert "prose" in codes(VALID + f"#let about = {sentence}\n")
    assert "long_literal" not in codes(VALID + f"#let about = {sentence}\n")
    # Six plain words in a row are not enough, and code is not prose.
    assert codes(VALID + "#let short = [Builds reliable systems for banks]\n") == []


def test_a_year_range_is_not_a_phone_number() -> None:
    reference = reference_from_text(UPLOAD_TEXT)

    assert reference.phones == frozenset({"15550104477"})
    assert codes(VALID + '#let years = "2019 2021 2022"\n', reference) == []


def test_the_reference_reads_name_contact_details_and_links() -> None:
    reference = reference_from_text(UPLOAD_TEXT)

    assert reference.name == "Grace Hopper"
    assert reference.emails == frozenset({"grace@navy.example"})
    assert reference.urls == frozenset({"linkedin.com/in/grace-hopper", "gracehopper.dev"})
    assert "work experience" in reference.text


def test_a_first_line_that_is_not_a_name_is_not_taken_for_one() -> None:
    # A two-word title cannot be told from a name; it only adds a harmless check.
    assert reference_from_text("Curriculum vitae\nPage 1").name == "Curriculum vitae"
    assert reference_from_text("Resume\n").name is None
    assert reference_from_text("Contact: ada@x.com\n").name is None
    assert reference_from_text("").name is None
    assert reference_from_text("") == Reference(text="")


def test_the_page_target_is_checked() -> None:
    assert check_pages(1, 1) == []
    assert check_pages(2, 2) == []
    [issue] = check_pages(3, 1)
    assert issue.code == "too_many_pages"
    assert "3 pages but must fit 1 page" in issue.message
    assert "2 pages" in check_pages(3, 2)[0].message


def test_a_render_must_show_what_the_data_holds(content: CvContent) -> None:
    shown = (
        "Ada Lovelace Data engineer Engineer with 9 years of experience and main domain "
        "Experience Acme Engineer Cut costs by 40% Served number of users users Barclays "
        "Built what Projects Vitae Typst Awards Best paper"
    )

    assert check_render(shown, content) == []
    # Spacing, case and line breaks in the PDF's text do not matter.
    assert check_render(shown.upper().replace(" ", "\n"), content) == []


@pytest.mark.parametrize(
    ("drop", "kind"),
    [
        ("Ada Lovelace", "name"),
        ("Data engineer", "headline"),
        ("Engineer with 9 years", "summary"),
        ("Awards", "section titles"),
        ("Acme", "entries"),
    ],
)
def test_a_render_that_drops_data_fails(content: CvContent, drop: str, kind: str) -> None:
    shown = (
        "Ada Lovelace Data engineer Engineer with 9 years of experience Experience Acme "
        "Engineer Cut costs by 40% Served number of users Built what Projects Vitae Typst "
        "Awards Best paper"
    )

    [issue] = check_render(shown.replace(drop, ""), content)

    assert issue.code == "missing_content"
    assert kind in issue.message


def test_a_render_may_miss_half_the_bullets_but_not_more(content: CvContent) -> None:
    without_two = (
        "Ada Lovelace Data engineer Engineer with 9 years Experience Acme Engineer "
        "Built what Projects Vitae Typst Awards Best paper"
    )
    without_all = (
        without_two.replace("Built what", "").replace("Typst", "").replace("Best paper", "")
    )

    assert check_render(without_two, content) == []
    assert [i.code for i in check_render(without_all, content)] == ["missing_content"]


def test_empty_parts_of_the_data_are_not_expected() -> None:
    content = CvContent.model_validate(
        {"basics": {"name": "Zoe"}, "sections": [{"id": "s", "kind": "skills", "title": "Skills"}]}
    )

    assert check_render("Zoe", content) == []


def test_a_label_that_names_the_owner_is_spotted() -> None:
    reference = reference_from_text(UPLOAD_TEXT)

    assert mentions_owner("Grace   Hopper's CV", reference)
    assert mentions_owner("see GRACE@navy.example", reference)
    assert mentions_owner("my page: www.gracehopper.dev/", reference)
    assert not mentions_owner("Teal banner", reference)
    assert not mentions_owner("Grace Hopper", Reference())
