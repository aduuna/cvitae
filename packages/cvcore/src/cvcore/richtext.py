"""Rich text in bullets and summaries: `**bold**` and `[[placeholder]]`, everything else literal.

`parse` and `serialize` are exact inverses: `serialize(parse(text)) == text` for every string, and
`parse(serialize(spans)) == spans` for every span list `parse` can produce. The rules that make this
hold:

- A marker pair needs non-empty content; the first closing marker after the content wins.
- Placeholders may sit inside bold (spans with both flags). Placeholder content is always literal.
- A bold block may not open where the previous bold block closed (`**a****b**` is bold "a" followed
  by the literal "**b**"), so consecutive bold spans always come from a single block.
"""

from cvcore.models import Span

BOLD = "**"
OPEN = "[["
CLOSE = "]]"


def parse(text: str) -> list[Span]:
    spans: list[Span] = []
    literal: list[str] = []
    i = 0
    bold_end = -1

    def flush() -> None:
        if literal:
            spans.append(Span(t="".join(literal)))
            literal.clear()

    while i < len(text):
        if text.startswith(BOLD, i) and i != bold_end:
            close = text.find(BOLD, i + len(BOLD) + 1)
            if close != -1:
                flush()
                spans.extend(_parse_placeholders(text[i + len(BOLD) : close], bold=True))
                i = bold_end = close + len(BOLD)
                continue
        if text.startswith(OPEN, i):
            close = text.find(CLOSE, i + len(OPEN) + 1)
            if close != -1:
                flush()
                spans.append(Span(t=text[i + len(OPEN) : close], p=True))
                i = close + len(CLOSE)
                continue
        literal.append(text[i])
        i += 1
    flush()
    return spans


def _parse_placeholders(text: str, *, bold: bool) -> list[Span]:
    spans: list[Span] = []
    start = 0
    i = 0
    while i < len(text):
        if text.startswith(OPEN, i):
            close = text.find(CLOSE, i + len(OPEN) + 1)
            if close != -1:
                if i > start:
                    spans.append(Span(t=text[start:i], b=bold))
                spans.append(Span(t=text[i + len(OPEN) : close], b=bold, p=True))
                i = start = close + len(CLOSE)
                continue
        i += 1
    if start < len(text):
        spans.append(Span(t=text[start:], b=bold))
    return spans


def serialize(spans: list[Span]) -> str:
    out: list[str] = []
    i = 0
    while i < len(spans):
        if not spans[i].b:
            out.append(_wrap(spans[i]))
            i += 1
            continue
        # A run of bold spans is one bold block.
        end = i
        while end < len(spans) and spans[end].b:
            end += 1
        out.append(BOLD + "".join(_wrap(span) for span in spans[i:end]) + BOLD)
        i = end
    return "".join(out)


def _wrap(span: Span) -> str:
    return f"{OPEN}{span.t}{CLOSE}" if span.p else span.t


def plain_text(text: str) -> str:
    """The text without markers, as a reader of the CV sees it."""
    return "".join(span.t for span in parse(text))
