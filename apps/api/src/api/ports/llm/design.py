"""What a PDF's page 1 measures: paper, margins, type styles, line gaps, filled shapes and rules.

A model reading a design off a picture guesses sizes, colours and gaps; pdfium knows them exactly.
`describe_design` turns them into a short text for the template prompts (docs/BACKEND.md, Custom
templates). It holds no words of the CV: only fonts, sizes, colours and geometry, plus whether a
style is all capitals. It never raises: a scan, a broken PDF or an unexpected pdfium answer gives
what could be measured, or an empty string.
"""

import ctypes
import itertools
import re
from collections import Counter
from dataclasses import dataclass

import pypdfium2
import pypdfium2.raw as pdfium_raw

from api.ports.llm.pages import PDFIUM_LOCK

CM_PER_PT = 2.54 / 72
PLACEHOLDER_FILL = (255, 229, 138)
"""The highlight the app's own templates give a placeholder; not part of any design."""

_MAX_STYLES = 10
_MAX_GAPS = 6
_MAX_FILLS = 8
_MAX_RULES = 6
_MAX_OUTLINES = 4
_MIN_GAP_PT = 3.0
_MAX_GAP_PT = 80.0
_RULE_MAX_THICKNESS_PT = 3.0
_RULE_MIN_LENGTH_PT = 20.0
_TINY_SHAPE_PT = 2.0
_FONT_NAME = re.compile(r"[^A-Za-z0-9 ._-]")
_SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")
_PAPERS = (("A4", 595.3, 841.9), ("US Letter", 612.0, 792.0))


@dataclass(frozen=True)
class _Style:
    font: str
    size: float
    color: str
    caps: bool
    chars: int


def _hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _cm(points: float) -> str:
    return f"{points * CM_PER_PT:.1f}"


def _paper(width: float, height: float) -> str:
    for name, w, h in _PAPERS:
        if abs(width - w) < 3 and abs(height - h) < 3:
            return name
    return "custom size"


def _font_name(textpage: pypdfium2.PdfTextPage, index: int) -> str:
    buffer = ctypes.create_string_buffer(128)
    flags = ctypes.c_int()
    pdfium_raw.FPDFText_GetFontInfo(textpage, index, buffer, 128, ctypes.byref(flags))
    name = _SUBSET_PREFIX.sub("", buffer.value.decode("utf-8", "replace"))
    return _FONT_NAME.sub("", name)[:40] or "unnamed font"


def _fill_color(textpage: pypdfium2.PdfTextPage, index: int) -> str:
    red, green, blue, alpha = (ctypes.c_uint() for _ in range(4))
    if not pdfium_raw.FPDFText_GetFillColor(textpage, index, red, green, blue, alpha):
        return "#000000"
    return _hex(red.value, green.value, blue.value)


def _origin_y(textpage: pypdfium2.PdfTextPage, index: int) -> float:
    x, y = ctypes.c_double(), ctypes.c_double()
    pdfium_raw.FPDFText_GetCharOrigin(textpage, index, ctypes.byref(x), ctypes.byref(y))
    return y.value


def _text_lines(page: pypdfium2.PdfPage, height: float) -> list[str]:
    """Margins, type styles and the gaps between lines, as lines of text."""
    textpage = page.get_textpage()
    groups: dict[tuple[str, float, str], list[str]] = {}
    baselines: set[float] = set()
    left, right, top, bottom = float("inf"), 0.0, 0.0, float("inf")
    total = 0
    for index in range(textpage.count_chars()):
        char = textpage.get_text_range(index, 1)
        if not char.strip() or char == "￾":
            continue
        box_left, box_bottom, box_right, box_top = textpage.get_charbox(index)
        left, right = min(left, box_left), max(right, box_right)
        top, bottom = max(top, box_top), min(bottom, box_bottom)
        key = (
            _font_name(textpage, index),
            round(pdfium_raw.FPDFText_GetFontSize(textpage, index), 1),
            _fill_color(textpage, index),
        )
        groups.setdefault(key, []).append(char)
        baselines.add(round(_origin_y(textpage, index), 1))
        total += 1
    if not total:
        return []

    styles = sorted(
        (
            _Style(
                font=font,
                size=size,
                color=color,
                caps=_all_caps("".join(chars)),
                chars=len(chars),
            )
            for (font, size, color), chars in groups.items()
        ),
        key=lambda style: -style.chars,
    )[:_MAX_STYLES]
    lines = [
        f"- Text runs from {_cm(left)} cm to {_cm(right)} cm across the page width, the first "
        f"line's top is {_cm(height - top)} cm from the top edge and the last line's bottom is "
        f"{_cm(bottom)} cm from the bottom edge.",
        "- Type styles (font, size, colour, share of the text), most used first:",
    ]
    for style in styles:
        share = round(100 * style.chars / total)
        caps = ", all capitals" if style.caps else ""
        lines.append(f"  {style.font} {style.size:g}pt {style.color}, {max(share, 1)}%{caps}")
    gaps = _line_gaps(sorted(baselines, reverse=True))
    if gaps:
        lines.append(f"- Gaps between consecutive text lines, baseline to baseline: {gaps}.")
    return lines


def _all_caps(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 4 and all(c.isupper() for c in letters)


def _line_gaps(baselines: list[float]) -> str:
    gaps = Counter(
        round((above - below) * 2) / 2
        for above, below in itertools.pairwise(baselines)
        if _MIN_GAP_PT < above - below <= _MAX_GAP_PT
    )
    common = sorted(value for value, _ in gaps.most_common(_MAX_GAPS))
    return ", ".join(f"{value:g}pt (x{gaps[value]})" for value in common)


def _shape_lines(page: pypdfium2.PdfPage, width: float, height: float) -> list[str]:
    """Filled areas, rules and outlines, grouped by colour so a repeated tag is one line."""
    fills: dict[str, list[tuple[float, str]]] = {}
    rules: dict[tuple[str, float, str], list[tuple[float, float]]] = {}
    outlines: list[str] = []
    for obj in page.get_objects(filter=(pdfium_raw.FPDF_PAGEOBJ_PATH,)):
        left, bottom, right, top = obj.get_bounds()
        w, h = right - left, top - bottom
        mode, stroked = ctypes.c_int(), ctypes.c_int()
        pdfium_raw.FPDFPath_GetDrawMode(obj.raw, mode, stroked)
        place = (
            f"{_cm(left)} to {_cm(right)} cm from the left, {_cm(height - top)} to "
            f"{_cm(height - bottom)} cm from the top"
        )
        red, green, blue, alpha = (ctypes.c_uint() for _ in range(4))
        if mode.value:
            pdfium_raw.FPDFPageObj_GetFillColor(obj.raw, red, green, blue, alpha)
            rgb = (red.value, green.value, blue.value)
            covers_page = w > 0.9 * width and h > 0.9 * height
            if (
                rgb != PLACEHOLDER_FILL
                and min(w, h) >= _TINY_SHAPE_PT
                and not (covers_page and rgb == (255, 255, 255))
            ):
                note = " (the whole page)" if covers_page else ""
                size = f"{_cm(w)} x {_cm(h)} cm, {place}{note}"
                fills.setdefault(_hex(*rgb), []).append((w * h, size))
        elif stroked.value:
            pdfium_raw.FPDFPageObj_GetStrokeColor(obj.raw, red, green, blue, alpha)
            thickness = ctypes.c_float()
            pdfium_raw.FPDFPageObj_GetStrokeWidth(obj.raw, thickness)
            color = _hex(red.value, green.value, blue.value)
            if min(w, h) <= 2.5 * thickness.value + 0.5 and max(w, h) >= _RULE_MIN_LENGTH_PT:
                axis = "horizontal" if w >= h else "vertical"
                key = (axis, round(thickness.value, 1), color)
                rules.setdefault(key, []).append(
                    (left, right) if axis == "horizontal" else (bottom, top)
                )
            elif len(outlines) < _MAX_OUTLINES:
                outlines.append(
                    f"  outline {thickness.value:.1f}pt {color}, {_cm(w)} x {_cm(h)} cm, {place}"
                )
    lines: list[str] = []
    if fills:
        lines.append("- Filled areas, largest first (the repeats are the same colour):")
        ranked = sorted(fills.items(), key=lambda item: -max(item[1])[0])
        for color, shapes in ranked[:_MAX_FILLS]:
            _, where = max(shapes)
            count = f", {len(shapes)} of them, the largest" if len(shapes) > 1 else ""
            lines.append(f"  {color}{count}: {where}")
    if rules:
        lines.append("- Rules:")
        for (axis, thickness, color), spans in list(rules.items())[:_MAX_RULES]:
            low, high = min(a for a, _ in spans), max(b for _, b in spans)
            lines.append(
                f"  {axis} {thickness:g}pt {color}, {len(spans)}, "
                f"spanning {_cm(low)} to {_cm(high)} cm"
            )
    if outlines:
        lines.append("- Outlined shapes:")
        lines += outlines
    return lines


def describe_design(pdf: bytes) -> str:
    """The measurements of page 1 of `pdf` as a few lines of text; empty when nothing could be
    read. Runs pdfium, so call it from a thread (`asyncio.to_thread`)."""
    try:
        with PDFIUM_LOCK:
            document = pypdfium2.PdfDocument(pdf)
            try:
                page = document[0]
                width, height = page.get_size()
                lines = [
                    f"- Paper: {_paper(width, height)} ({_cm(width)} x {_cm(height)} cm), "
                    f"{len(document)} page{'s' if len(document) != 1 else ''}.",
                    *_text_lines(page, height),
                    *_shape_lines(page, width, height),
                ]
            finally:
                document.close()
    except Exception:  # measurements are a hint: never fail a template for them
        return ""
    return "\n".join(lines)
