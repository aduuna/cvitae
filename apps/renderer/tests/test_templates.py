"""Golden render tests: every template renders every fixture to exactly the recorded SVG pages.

SVG output is byte-identical on macOS and Linux for the pinned Typst and bundled fonts, so any
visual change shows up here. After an intended template change, regenerate goldens and previews:
UPDATE_GOLDENS=1 uv run pytest apps/renderer/tests/test_templates.py
"""

import asyncio
import hashlib
import json
import os
import re
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from cvcore.models import CvContent
from cvcore.render import find_placeholders, iter_bullets
from cvcore.rendering import RenderRequest
from renderer.compile import check_imports, render
from renderer.previews import compile_template, fixture_data, write_previews
from renderer.settings import Settings
from renderer.templates import load_templates

SETTINGS = Settings()
TEMPLATES_DIR = SETTINGS.templates_dir
GOLDEN_PATH = TEMPLATES_DIR / "golden.json"
TEMPLATE_IDS = sorted(load_templates(TEMPLATES_DIR))
FIXTURE_NAMES = sorted(path.stem for path in (TEMPLATES_DIR / "fixtures").glob("profile-*.json"))
CASES = list(product(TEMPLATE_IDS, FIXTURE_NAMES))


Golden = dict[str, dict[str, dict[str, Any]]]


async def svg_pages(template_id: str, fixture: str, *, source_links: bool = False) -> list[str]:
    """The pages through the real sandboxed renderer."""
    request = RenderRequest(
        files={"data.json": json.dumps(fixture_data(SETTINGS, fixture))},
        template_id=template_id,
        format="svg",
        source_links=source_links,
    )
    return (await render(request, SETTINGS)).svg_pages


SOURCE_LINK = re.compile(r'<a [^>]*href="cv:([^"]*)"[^>]*>.*?</a>', re.S)
EMPTY_GROUP = re.compile(r"<g([^>]*)>\s*</g>")


def without_source_links(page: str) -> str:
    """The page with its source links removed; a group that held only a link closes itself."""
    return EMPTY_GROUP.sub(r"<g\1/>", SOURCE_LINK.sub("", page))


def fixture_content(fixture: str) -> CvContent:
    return CvContent.model_validate_json(
        (TEMPLATES_DIR / "fixtures" / f"{fixture}.json").read_text()
    )


def digest(pages: list[str]) -> list[str]:
    return [hashlib.sha256(page.encode()).hexdigest() for page in pages]


@pytest.fixture(scope="module")
def golden() -> Golden:
    if os.environ.get("UPDATE_GOLDENS") == "1":
        cases: Golden = {}
        for template_id, fixture in CASES:
            pages = asyncio.run(svg_pages(template_id, fixture))
            cases.setdefault(template_id, {})[fixture] = {
                "page_count": len(pages),
                "svg_sha256": digest(pages),
            }
        GOLDEN_PATH.write_text(json.dumps(cases, indent=2, sort_keys=True) + "\n")
        write_previews(SETTINGS)
    return json.loads(GOLDEN_PATH.read_text())


def test_there_are_templates_and_fixtures() -> None:
    assert TEMPLATE_IDS == ["classic", "compact", "minimal", "modern", "technical"]
    assert {"profile-sample", "profile-long", "profile-edge"} <= set(FIXTURE_NAMES)


def test_goldens_cover_every_case(golden: Golden) -> None:
    assert sorted((t, f) for t, fixtures in golden.items() for f in fixtures) == sorted(CASES)


@pytest.mark.parametrize(("template_id", "fixture"), CASES)
async def test_template_renders_fixture(golden: Golden, template_id: str, fixture: str) -> None:
    pages = await svg_pages(template_id, fixture)

    expected = golden[template_id][fixture]
    assert len(pages) == expected["page_count"]
    assert digest(pages) == expected["svg_sha256"], (
        "Rendered pages changed. If intended, run with UPDATE_GOLDENS=1 and review the previews."
    )
    assert ("#ffe58a" in "".join(pages)) == bool(find_placeholders(fixture_content(fixture)))


@pytest.mark.parametrize(("template_id", "fixture"), CASES)
async def test_source_links_change_nothing_on_the_page(template_id: str, fixture: str) -> None:
    plain = await svg_pages(template_id, fixture)
    linked = await svg_pages(template_id, fixture, source_links=True)

    assert [without_source_links(page) for page in linked] == [
        without_source_links(page) for page in plain
    ]


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
async def test_previews_link_every_part_to_its_field(template_id: str) -> None:
    content = fixture_content("profile-sample")
    expected = {"basics", "summary"}
    for section in content.sections:
        expected.add(section.id)
        for items in (section.experience, section.projects, section.education):
            expected |= {item.id for item in items}
        expected |= {item.id for item in [*section.skills, *section.certifications]}
        expected |= {e.id for role in section.experience for e in role.engagements}
    expected |= {bullet.id for bullet in iter_bullets(content) if bullet.text.strip()}

    pages = await svg_pages(template_id, "profile-sample", source_links=True)

    assert expected <= {target for page in pages for target in SOURCE_LINK.findall(page)}


async def test_a_pdf_never_carries_source_links() -> None:
    request = RenderRequest(
        files={"data.json": json.dumps(fixture_data(SETTINGS, "profile-sample"))},
        template_id="classic",
        format="pdf",
        source_links=True,
    )

    pdf = (await render(request, SETTINGS)).pdf

    assert pdf is not None and b"cv:" not in pdf


@pytest.mark.parametrize(("template_id", "fixture"), CASES)
def test_template_has_no_warnings(template_id: str, fixture: str) -> None:
    """A missing font or bad data access shows up as a Typst warning."""
    _, warnings = compile_template(SETTINGS, template_id, fixture_data(SETTINGS, fixture), ppi=10)

    assert warnings == []


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
async def test_sample_fits_one_page(template_id: str) -> None:
    assert len(await svg_pages(template_id, "profile-sample")) == 1


def test_templates_use_no_packages() -> None:
    sources = {
        str(path.relative_to(TEMPLATES_DIR)): path.read_text()
        for path in Path(TEMPLATES_DIR).rglob("*.typ")
    }

    check_imports(sources)
    assert not any("@preview" in source for source in sources.values())


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_template_has_metadata_and_preview(template_id: str) -> None:
    meta = load_templates(TEMPLATES_DIR)[template_id]

    assert meta.name and meta.description
    assert meta.paper_sizes == ["a4", "us-letter"]
    assert (TEMPLATES_DIR / template_id / "preview.png").read_bytes().startswith(b"\x89PNG")
