"""The wire shape the AI providers read and write, and its conversion to and from CvContent."""

from pathlib import Path
from typing import Any

import pytest

from cvcore.llm_schema import llm_schema
from cvcore.models import CvContent
from cvcore.wire import WireCv, WireImportedCv, WireTailoredCv, from_wire, parse_url, to_wire

FIXTURES = Path(__file__).resolve().parents[3] / "templates" / "fixtures"


def normalised(content: CvContent) -> CvContent:
    """An empty end date and None both mean "present"; the wire returns None."""
    copy = content.model_copy(deep=True)
    for section in copy.sections:
        for item in [*section.experience, *section.education]:
            if item.dates.end == "":
                item.dates.end = None
    return copy


@pytest.mark.parametrize("fixture", sorted(p.name for p in FIXTURES.glob("profile-*.json")))
def test_fixtures_survive_the_round_trip(fixture: str) -> None:
    content = CvContent.model_validate_json((FIXTURES / fixture).read_text())

    assert from_wire(to_wire(content)) == normalised(content)


def optional_fields(node: dict[str, Any]) -> int:
    count = 0
    if node.get("type") == "object":
        count += len(set(node["properties"]) - set(node["required"]))
        count += sum(optional_fields(prop) for prop in node["properties"].values())
    if "items" in node:
        count += optional_fields(node["items"])
    return count


@pytest.mark.parametrize("model", [WireCv, WireImportedCv, WireTailoredCv])
def test_the_wire_schema_has_no_optional_fields(model: type[WireCv]) -> None:
    # Claude's structured output allows few optional fields, and Gemini skips optional lists.
    assert optional_fields(llm_schema(model)) == 0


def wire(sections: list[dict[str, Any]], links: list[dict[str, str]] | None = None) -> WireCv:
    return WireCv.model_validate(
        {
            "basics": {
                "name": "Ada",
                "headline": "",
                "email": "",
                "phone": "",
                "location": "",
                "links": links or [],
            },
            "summary": "",
            "sections": sections,
        }
    )


def entry(**fields: Any) -> dict[str, Any]:
    names = ["organisation", "role", "institution", "degree", "name", "status", "issuer"]
    values = dict.fromkeys([*names, "location", "start", "end", "url"], "")
    return {"id": "e", **values, "items": [], "bullets": [], "engagements": [], **fields}


def test_entries_land_in_the_list_for_their_kind() -> None:
    bullet = {"id": "b", "text": "Did it", "source_id": ""}
    content = from_wire(
        wire(
            [
                {
                    "id": "s1",
                    "kind": "projects",
                    "title": "Projects",
                    "entries": [
                        entry(
                            name="Ledger",
                            status="beta",
                            start="2024",
                            url="github.com/x/y",
                            bullets=[bullet],
                            items=["ignored"],
                        ),
                    ],
                },
                {
                    "id": "s2",
                    "kind": "custom",
                    "title": "Awards",
                    "entries": [
                        entry(bullets=[bullet]),
                        entry(id="f", bullets=[{**bullet, "id": "c"}]),
                    ],
                },
                {
                    "id": "s3",
                    "kind": "certifications",
                    "title": "Certs",
                    "entries": [
                        entry(name="CKA", issuer="CNCF", start="2023-04"),
                    ],
                },
            ],
            links=[
                {"label": "GitHub", "url": "github.com/ada"},
                {"label": "Broken", "url": "not a url at all"},
            ],
        )
    )

    projects, awards, certs = content.sections
    [project] = projects.projects
    assert (project.name, project.status, project.year) == ("Ledger", "beta", "2024")
    assert str(project.url) == "https://github.com/x/y"
    assert projects.experience == [] and projects.skills == []
    assert [b.id for b in awards.custom] == ["b", "c"]
    assert (certs.certifications[0].issuer, certs.certifications[0].date) == ("CNCF", "2023-04")
    assert [(link.label, str(link.url)) for link in content.basics.links] == [
        ("GitHub", "https://github.com/ada")
    ]


def test_clients_without_dates_have_no_dates() -> None:
    engagement = {
        "id": "g",
        "label": "Client",
        "name": "Harbour Bank",
        "location": "",
        "start": "",
        "end": "",
        "bullets": [],
    }
    content = from_wire(
        wire(
            [
                {
                    "id": "s",
                    "kind": "experience",
                    "title": "Experience",
                    "entries": [
                        entry(
                            organisation="Northwind",
                            role="Engineer",
                            start="2021",
                            end="",
                            engagements=[engagement],
                        ),
                    ],
                }
            ]
        )
    )

    [item] = content.sections[0].experience
    assert item.dates.end is None
    assert item.engagements[0].dates is None


def test_source_ids_round_trip() -> None:
    content = CvContent.model_validate_json((FIXTURES / "profile-sample.json").read_text())
    content.sections[0].experience[0].bullets[0].source_id = "src-1"

    wired = to_wire(content)

    assert wired.sections[0].entries[0].bullets[0].source_id == "src-1"
    assert from_wire(wired).sections[0].experience[0].bullets[0].source_id == "src-1"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://example.com/a", "https://example.com/a"),
        ("example.com", "https://example.com/"),
        ("  ", None),
        ("not a url", None),
    ],
)
def test_parse_url(value: str, expected: str | None) -> None:
    url = parse_url(value)
    assert (str(url) if url else None) == expected
