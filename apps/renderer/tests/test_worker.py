from renderer.worker import parse_diagnostics


def test_parses_location_and_message() -> None:
    rendered = "error: unknown variable: foo\n  ┌─ main.typ:3:2\n  │\n3 │ #foo\n  │  ^^^\n\n"

    assert parse_diagnostics(rendered, "unknown variable: foo") == [
        {"message": "unknown variable: foo", "file": "main.typ", "line": 3, "column": 2}
    ]


def test_parses_every_error() -> None:
    rendered = (
        "error: unclosed delimiter\n  ┌─ _lib/cv.typ:9:1\n\n"
        "error: expected expression\n  ┌─ main.typ:1:5\n\n"
    )

    assert [(d["file"], d["line"]) for d in parse_diagnostics(rendered, "x")] == [
        ("_lib/cv.typ", 9),
        ("main.typ", 1),
    ]


def test_errors_without_a_location() -> None:
    assert parse_diagnostics("error: file not found\n", "file not found") == [
        {"message": "file not found", "file": None, "line": None, "column": None}
    ]


def test_falls_back_to_the_message() -> None:
    assert parse_diagnostics("", "something broke") == [{"message": "something broke"}]
