from typing import Any, Literal

import pytest
from pydantic import BaseModel, Field

from cvcore.ai import JobAnalysis, TailoredCv
from cvcore.llm_schema import llm_schema
from cvcore.models import CvContent

ALLOWED_KEYS = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "enum",
    "description",
}
ALLOWED_TYPES = {"object", "array", "string", "number", "integer", "boolean"}


def walk(node: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = [node]
    for prop in node.get("properties", {}).values():
        nodes.extend(walk(prop))
    if "items" in node:
        nodes.extend(walk(node["items"]))
    return nodes


@pytest.mark.parametrize("model", [CvContent, JobAnalysis, TailoredCv])
def test_output_models_use_only_the_shared_subset(model: type[BaseModel]) -> None:
    schema = llm_schema(model)

    for node in walk(schema):
        assert set(node) <= ALLOWED_KEYS, node
        assert node["type"] in ALLOWED_TYPES, node
        if node["type"] == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) <= set(node["properties"])


def test_cv_content_shape() -> None:
    schema = llm_schema(CvContent)

    assert schema["required"] == ["basics", "sections"]
    assert schema["properties"]["schema_version"] == {"type": "integer", "enum": [1]}
    section = schema["properties"]["sections"]["items"]
    assert section["properties"]["kind"]["enum"] == [
        "experience",
        "projects",
        "education",
        "skills",
        "certifications",
        "custom",
    ]
    bullet = section["properties"]["custom"]["items"]
    assert bullet["required"] == ["id", "text"]
    assert bullet["properties"]["source_id"] == {"type": "string"}
    link = schema["properties"]["basics"]["properties"]["links"]["items"]
    assert link["properties"]["url"] == {"type": "string"}


class Tagged(BaseModel):
    mode: Literal["a", "b"] = Field(description="Which mode")
    note: str | None
    count: int = 0
    ratio: float
    on: bool


def test_nullable_required_fields_become_optional_and_descriptions_stay() -> None:
    schema = llm_schema(Tagged)

    assert schema["required"] == ["mode", "ratio", "on"]
    assert schema["properties"]["mode"] == {
        "type": "string",
        "enum": ["a", "b"],
        "description": "Which mode",
    }
    assert schema["properties"]["note"] == {"type": "string"}
    assert schema["properties"]["ratio"] == {"type": "number"}


class Node(BaseModel):
    name: str
    children: list["Node"] = []


def test_recursion_is_rejected() -> None:
    with pytest.raises(ValueError, match="recursive"):
        llm_schema(Node)


class Either(BaseModel):
    value: int | str


def test_real_unions_are_rejected() -> None:
    with pytest.raises(ValueError, match="unions"):
        llm_schema(Either)


class Loose(BaseModel):
    data: dict[str, Any]


def test_free_form_objects_are_closed() -> None:
    schema = llm_schema(Loose)

    assert schema["properties"]["data"] == {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }


class Anything(BaseModel):
    value: Any


def test_untyped_values_are_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        llm_schema(Anything)
