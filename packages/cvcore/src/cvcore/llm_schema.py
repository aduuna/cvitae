"""Pydantic model -> the JSON schema subset that both Claude and Gemini structured output accept."""

from typing import Any

from pydantic import BaseModel

_SCALARS = {"string", "number", "integer", "boolean"}
_CONST_TYPES: dict[type, str] = {str: "string", bool: "boolean", int: "integer", float: "number"}


def llm_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Inline every `$defs` reference, close every object with `additionalProperties: false`, and
    keep only object, array, string, number, integer, boolean and enum. Optional fields become
    non-required fields of the inner type. Raises ValueError for recursion and real unions."""
    schema = model.model_json_schema()
    defs: dict[str, Any] = schema.pop("$defs", {})
    return _convert(schema, defs, ())


def _convert(node: dict[str, Any], defs: dict[str, Any], seen: tuple[str, ...]) -> dict[str, Any]:
    description = node.get("description")

    if "$ref" in node:
        name = node["$ref"].removeprefix("#/$defs/")
        if name in seen:
            raise ValueError(f"{name} is recursive, which structured output does not support")
        out = _convert(defs[name], defs, (*seen, name))
    elif "anyOf" in node:
        branches = [branch for branch in node["anyOf"] if branch.get("type") != "null"]
        if len(branches) != 1:
            raise ValueError("unions other than Optional are not supported")
        out = _convert(branches[0], defs, seen)
    elif "const" in node:
        out = {"type": _CONST_TYPES[type(node["const"])], "enum": [node["const"]]}
    elif "enum" in node:
        out = {"type": node.get("type", "string"), "enum": list(node["enum"])}
    elif node.get("type") == "object":
        properties: dict[str, Any] = node.get("properties", {})
        required = [name for name in node.get("required", []) if not _nullable(properties[name])]
        out = {
            "type": "object",
            "properties": {name: _convert(prop, defs, seen) for name, prop in properties.items()},
            "required": required,
            "additionalProperties": False,
        }
    elif node.get("type") == "array":
        out = {"type": "array", "items": _convert(node["items"], defs, seen)}
    elif node.get("type") in _SCALARS:
        out = {"type": node["type"]}
    else:
        raise ValueError(f"unsupported schema node: {sorted(node)}")

    if description and "description" not in out:
        out["description"] = description
    return out


def _nullable(node: dict[str, Any]) -> bool:
    return any(branch.get("type") == "null" for branch in node.get("anyOf", []))
