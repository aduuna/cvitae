import pytest
from pydantic import ValidationError

from cvcore.ids import new_id
from cvcore.models import CvContent, Section


def test_minimal_content_fills_defaults() -> None:
    content = CvContent.model_validate({"basics": {"name": ""}, "sections": []})

    assert content.schema_version == 1
    assert content.summary == ""
    assert content.basics.links == []


def test_section_lists_default_empty() -> None:
    section = Section(id="s", kind="skills", title="Skills")

    assert section.experience == section.skills == section.custom == []


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="extra"):
        CvContent.model_validate({"basics": {"name": "A", "nickname": "B"}, "sections": []})


def test_links_must_be_http_urls() -> None:
    with pytest.raises(ValidationError):
        CvContent.model_validate(
            {
                "basics": {"name": "A", "links": [{"label": "x", "url": "javascript:alert(1)"}]},
                "sections": [],
            }
        )


def test_unknown_section_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Section.model_validate({"id": "s", "kind": "hobbies", "title": "Hobbies"})


def test_serialization_schema_marks_defaults_required() -> None:
    schema = CvContent.model_json_schema(mode="serialization")

    assert set(schema["required"]) == {"schema_version", "basics", "summary", "sections"}


def test_new_id_format() -> None:
    ids = {new_id() for _ in range(100)}

    assert len(ids) == 100
    assert all(len(i) == 12 and int(i, 16) >= 0 for i in ids)
