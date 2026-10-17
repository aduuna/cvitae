import json

from cvcore.models import CvContent
from cvcore.render import PlaceholderRef, find_placeholders, iter_bullets, to_render_json


def test_render_json_replaces_bullet_text_with_spans(content: CvContent) -> None:
    data = to_render_json(content)
    source = content.sections[0].experience[0]

    role = data["sections"][0]["experience"][0]
    # Bullets keep their id, so previews can link each one back to its field.
    assert role["bullets"][0] == {
        "id": source.bullets[0].id,
        "spans": [
            {"t": "Cut costs by ", "b": False, "p": False},
            {"t": "40%", "b": True, "p": False},
        ],
    }
    assert role["engagements"][0]["bullets"] == [
        {
            "id": source.engagements[0].bullets[0].id,
            "spans": [
                {"t": "Built ", "b": False, "p": False},
                {"t": "what", "b": False, "p": True},
            ],
        }
    ]
    assert data["sections"][1]["projects"][0]["bullets"] == [
        {
            "id": content.sections[1].projects[0].bullets[0].id,
            "spans": [{"t": "Typst", "b": False, "p": False}],
        }
    ]
    assert data["sections"][2]["custom"] == [
        {
            "id": content.sections[2].custom[0].id,
            "spans": [{"t": "Best paper", "b": False, "p": False}],
        }
    ]


def test_render_json_converts_the_summary(content: CvContent) -> None:
    summary = to_render_json(content)["summary"]

    assert [span["t"] for span in summary] == [
        "Engineer with ",
        "9 years",
        " of experience and ",
        "main domain",
        " focus.",
    ]
    assert summary[1]["b"] and summary[3]["p"]


def test_render_json_drops_ids_and_raw_text_and_is_serializable(content: CvContent) -> None:
    text = json.dumps(to_render_json(content))

    assert '"text"' not in text
    assert '"source_id"' not in text
    assert "**" not in text
    assert '"url": "https://github.com/ada"' in text


def test_iter_bullets_reads_in_order(content: CvContent) -> None:
    assert [bullet.id for bullet in iter_bullets(content)] == ["b1", "b2", "b3", "b4", "b5"]


def test_find_placeholders(content: CvContent) -> None:
    assert find_placeholders(content) == [
        PlaceholderRef(text="main domain"),
        PlaceholderRef(text="number of users", bullet_id="b2"),
        PlaceholderRef(text="what", bullet_id="b3"),
    ]


def test_find_placeholders_none_left(content: CvContent) -> None:
    clean = content.model_copy(update={"summary": "Engineer", "sections": []})

    assert find_placeholders(clean) == []
