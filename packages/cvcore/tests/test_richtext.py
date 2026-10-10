import pytest
from hypothesis import given
from hypothesis import strategies as st

from cvcore.models import Span
from cvcore.richtext import parse, plain_text, serialize


def spans(*items: tuple[str, str]) -> list[Span]:
    """("text", "") literal, ("text", "b") bold, ("text", "p") placeholder, ("text", "bp") both."""
    return [Span(t=t, b="b" in flags, p="p" in flags) for t, flags in items]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", []),
        ("Plain text", spans(("Plain text", ""))),
        ("Cut costs by **40%**", spans(("Cut costs by ", ""), ("40%", "b"))),
        (
            "Served [[number of users]] users",
            spans(("Served ", ""), ("number of users", "p"), (" users", "")),
        ),
        ("**[[check this number: 40%]]**", spans(("check this number: 40%", "bp"))),
        (
            "**up [[n]] times** faster",
            spans(("up ", "b"), ("n", "bp"), (" times", "b"), (" faster", "")),
        ),
        ("[[**literal** inside]]", spans(("**literal** inside", "p"))),
        ("a ** b", spans(("a ** b", ""))),
        ("****", spans(("****", ""))),
        ("[[]]", spans(("[[]]", ""))),
        ("**a**b**", spans(("a", "b"), ("b**", ""))),
        ("**a****b**", spans(("a", "b"), ("**b**", ""))),
        ("**a*****b**", spans(("a", "b"), ("*", ""), ("b", "b"))),
        ("***a**", spans(("*a", "b"))),
        ("**a [[b** c]]", spans(("a [[b", "b"), (" c]]", ""))),
        ("[[a **b]] c**", spans(("a **b", "p"), (" c**", ""))),
        ("[[a]][[b]]", spans(("a", "p"), ("b", "p"))),
        ('#import "x" $math$ <label>', spans(('#import "x" $math$ <label>', ""))),
    ],
)
def test_parse(text: str, expected: list[Span]) -> None:
    assert parse(text) == expected
    assert serialize(expected) == text


def test_plain_text_drops_markers() -> None:
    assert (
        plain_text("Cut **40%** for [[number of teams]] teams")
        == "Cut 40% for number of teams teams"
    )


marker_heavy = st.text(alphabet="*[]ab ", max_size=40)


@given(st.one_of(st.text(), marker_heavy))
def test_serialize_inverts_parse_for_every_string(text: str) -> None:
    assert serialize(parse(text)) == text


@given(st.one_of(st.text(), marker_heavy))
def test_parse_produces_no_empty_spans(text: str) -> None:
    assert all(span.t for span in parse(text))


def canonical(raw: list[Span]) -> list[Span]:
    """Merge neighbours that parse would merge: literal text, and bold text inside one block."""
    out: list[Span] = []
    for span in raw:
        prev = out[-1] if out else None
        if prev and not prev.p and not span.p and prev.b == span.b:
            out[-1] = Span(t=prev.t + span.t, b=span.b)
        else:
            out.append(span)
    return out


span_lists = st.lists(
    st.builds(
        Span,
        t=st.text(alphabet=st.characters(exclude_characters="*[]"), min_size=1, max_size=8),
        b=st.booleans(),
        p=st.booleans(),
    ),
    max_size=8,
).map(canonical)


@given(span_lists)
def test_parse_inverts_serialize_for_canonical_spans(value: list[Span]) -> None:
    assert parse(serialize(value)) == value
