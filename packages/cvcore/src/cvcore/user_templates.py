"""Templates users make from their own CV: ids, and the deterministic checks every generated
template passes before it is saved (docs/BACKEND.md, Custom templates).

A model writes the Typst, so nothing it returns is trusted: the source must follow the template
contract, use only what the renderer provides, and hold none of the uploaded CV's personal details
or text. Pure Python, no I/O: the api extracts the PDF's text and renders the template.
"""

import re
import secrets
from dataclasses import dataclass
from typing import Literal

from cvcore.models import CvContent
from cvcore.render import iter_bullets
from cvcore.richtext import plain_text

ID_ALPHABET = "abcdefghijklmnopqrstuvwxyz234567"
CUSTOM_ID = re.compile(r"^u-[a-z2-7]{10}$")

MAX_SOURCE_BYTES = 64 * 1024
"""A template's main.typ. The renderer's limit is 256 KB for every file together, data.json
included, so this leaves room for a long CV; the built-in templates are under 5 KB."""

LIB_IMPORT = "/_lib/cv.typ"
BUNDLED_FONTS = ("Geist", "Geist Mono", "Libertinus Serif")
"""The fonts the renderer has (apps/renderer/fonts); any other family falls back silently."""

MAX_LITERAL_CHARS = 40
"""Longest string a template may hold. Labels and colours are short; a sentence is copied text."""

PROSE_WORDS = 7
"""Plain words in a row, in markup, that read as a sentence rather than code."""

HEADING_WORDS = frozenset(
    {
        "about",
        "achievements",
        "awards",
        "certifications",
        "contact",
        "education",
        "employment",
        "experience",
        "history",
        "interests",
        "languages",
        "links",
        "me",
        "professional",
        "profile",
        "projects",
        "publications",
        "references",
        "skills",
        "summary",
        "technical",
        "work",
    }
)
"""Words a template may write itself, as a heading that is not in the data."""

# Calls that read files or load code. A template reads data.json and nothing else.
_FORBIDDEN_CALLS = ("read", "image", "plugin", "eval", "csv", "yaml", "toml", "xml", "cbor")
_FORBIDDEN_CALL = re.compile(rf"(?<![\w.-])({'|'.join(_FORBIDDEN_CALLS)}|bibliography)\s*\(")
_JSON_CALL = re.compile(r'(?<![\w.-])json\s*\(\s*"((?:[^"\\]|\\.)*)"')
_IMPORT = re.compile(r'\b(?:import|include)\s+"((?:[^"\\]|\\.)*)"')
_DATA_LINE = re.compile(r'#let\s+cv\s*=\s*json\(\s*"data\.json"\s*\)')
_LIB_LINE = re.compile(r'#import\s+"/_lib/cv\.typ"\s*:\s*\*')
_PAPER = re.compile(r"paper-size\s*\(\s*\)")
_SECTIONS = re.compile(r"(?<![\w.-])sections\s*\(")
_FONT_ARG = re.compile(r'\bfont\s*:\s*(\([^)]*\)|"(?:[^"\\]|\\.)*")')
_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
_PROSE = re.compile(
    rf"(?<![\w#.@-])(?:[A-Za-z][A-Za-z'-]*[ \t]+){{{PROSE_WORDS - 1}}}[A-Za-z][A-Za-z'-]*"
)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"\+?\(?\d[\d\s().-]{5,}\d")
_URL = re.compile(r"(?:https?://|www\.)[^\s)>\]\"']+", re.IGNORECASE)
_BARE_URL = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}/[^\s)>\]\"']+", re.IGNORECASE)

IssueCode = Literal[
    "compile_error",
    "too_large",
    "missing_import",
    "missing_data",
    "missing_paper",
    "missing_sections",
    "forbidden_import",
    "forbidden_call",
    "unknown_font",
    "copied_name",
    "copied_email",
    "copied_phone",
    "copied_url",
    "copied_text",
    "long_literal",
    "prose",
    "missing_content",
    "too_many_pages",
]


@dataclass(frozen=True)
class TemplateIssue:
    """One thing wrong with a template. `message` is for the model that repairs it, so it says
    what to change; it never repeats the uploaded CV's own text."""

    code: IssueCode
    message: str
    line: int | None = None

    def __str__(self) -> str:
        return f"line {self.line}: {self.message}" if self.line else self.message


def new_template_id() -> str:
    """A template id for a user's own template: `u-` and 10 random base32 characters. It is a
    valid renderer template id (`^[a-z][a-z0-9-]*$`) and cannot clash with a built-in one."""
    return "u-" + "".join(secrets.choice(ID_ALPHABET) for _ in range(10))


def is_custom_id(template_id: str) -> bool:
    return CUSTOM_ID.fullmatch(template_id) is not None


@dataclass(frozen=True)
class Reference:
    """What an uploaded CV says about its owner and in its own words, from its text layer."""

    name: str | None = None
    emails: frozenset[str] = frozenset()
    phones: frozenset[str] = frozenset()
    """Digits only."""
    urls: frozenset[str] = frozenset()
    """Without scheme, `www.` and trailing slash, in lower case."""
    text: str = ""
    """Normalised: lower case, single spaces."""


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _squash(text: str) -> str:
    return "".join(text.split()).casefold()


def _normal_url(url: str) -> str:
    url = re.sub(r"^(?:https?://)?(?:www\.)?", "", url.strip().lower())
    return url.rstrip("/.,;")


def _phone_digits(candidate: str) -> str | None:
    """The digits of something that looks like a phone number; None for a date range or a short
    number."""
    groups = re.findall(r"\d+", candidate)
    digits = "".join(groups)
    if not 7 <= len(digits) <= 15:
        return None
    if all(len(g) == 4 and 1950 <= int(g) <= 2100 for g in groups):
        return None
    return digits


def _owner_name(lines: list[str]) -> str | None:
    """The first line when it reads as a person's name: two to five words, no digits or symbols."""
    if not lines:
        return None
    first = lines[0]
    words = first.split()
    if 2 <= len(words) <= 5 and len(first) <= 50 and not re.search(r"[\d@/:|]", first):
        return first
    return None


def reference_from_text(text: str) -> Reference:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    emails = frozenset(email.lower() for email in _EMAIL.findall(text))
    without_emails = _EMAIL.sub(" ", text)
    urls = {_normal_url(url) for url in _URL.findall(without_emails)}
    urls |= {_normal_url(url) for url in _BARE_URL.findall(without_emails)}
    phones = {digits for c in _PHONE.findall(text) if (digits := _phone_digits(c)) is not None}
    return Reference(
        name=_owner_name(lines),
        emails=emails,
        phones=frozenset(phones),
        urls=frozenset(url for url in urls if url),
        text=_norm(text),
    )


@dataclass(frozen=True)
class _Scan:
    code: str
    """Comments and the inside of strings blanked; offsets and line breaks kept."""
    uncommented: str
    """Comments blanked, strings kept."""
    literals: list[tuple[str, int]]
    """Each string's content and its line."""


def _blank(text: str) -> str:
    return "".join(c if c == "\n" else " " for c in text)


def _scan(source: str) -> _Scan:
    code: list[str] = []
    uncommented: list[str] = []
    literals: list[tuple[str, int]] = []
    i, n = 0, len(source)
    while i < n:
        if source.startswith("//", i):
            end = source.find("\n", i)
            end = n if end == -1 else end
            code.append(_blank(source[i:end]))
            uncommented.append(_blank(source[i:end]))
            i = end
        elif source.startswith("/*", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if source.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif source.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            code.append(_blank(source[i:j]))
            uncommented.append(_blank(source[i:j]))
            i = j
        elif source[i] == '"':
            j = i + 1
            while j < n and source[j] != '"':
                j += 2 if source[j] == "\\" else 1
            if j >= n:
                # No closing quote: an apostrophe-like character in markup, not a string.
                code.append('"')
                uncommented.append('"')
                i += 1
                continue
            literals.append((source[i + 1 : j], source.count("\n", 0, i) + 1))
            code.append('"' + _blank(source[i + 1 : j]) + '"')
            uncommented.append(source[i : j + 1])
            i = j + 1
        else:
            code.append(source[i])
            uncommented.append(source[i])
            i += 1
    return _Scan("".join(code), "".join(uncommented), literals)


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _structure_issues(source: str, scan: _Scan) -> list[TemplateIssue]:
    issues: list[TemplateIssue] = []
    if len(source.encode()) > MAX_SOURCE_BYTES:
        issues.append(
            TemplateIssue("too_large", f"The source is larger than {MAX_SOURCE_BYTES // 1024} KB.")
        )
    if not _LIB_LINE.search(scan.uncommented):
        issues.append(
            TemplateIssue(
                "missing_import", f'The source must start with #import "{LIB_IMPORT}": *.'
            )
        )
    if not _DATA_LINE.search(scan.uncommented):
        issues.append(
            TemplateIssue(
                "missing_data", '#let cv = json("data.json") is missing; it must be there.'
            )
        )
    if not _PAPER.search(scan.code):
        issues.append(
            TemplateIssue("missing_paper", "The page must use paper: paper-size() for its size.")
        )
    if not _SECTIONS.search(scan.code):
        issues.append(
            TemplateIssue(
                "missing_sections",
                "The sections must be drawn with sections(cv, ...) from the helper library.",
            )
        )
    return issues


def _access_issues(scan: _Scan) -> list[TemplateIssue]:
    issues: list[TemplateIssue] = []
    for match in _IMPORT.finditer(scan.uncommented):
        if match.group(1) != LIB_IMPORT:
            issues.append(
                TemplateIssue(
                    "forbidden_import",
                    f'Only #import "{LIB_IMPORT}": * is allowed; packages and other files are not.',
                    _line(scan.uncommented, match.start()),
                )
            )
    for match in _FORBIDDEN_CALL.finditer(scan.code):
        issues.append(
            TemplateIssue(
                "forbidden_call",
                f"{match.group(1)}() is not allowed: a template reads data.json and nothing "
                "else, and draws without images.",
                _line(scan.code, match.start()),
            )
        )
    for match in _JSON_CALL.finditer(scan.uncommented):
        if match.group(1) != "data.json":
            issues.append(
                TemplateIssue(
                    "forbidden_call",
                    'json() may only read "data.json".',
                    _line(scan.uncommented, match.start()),
                )
            )
    bundled = {font.casefold() for font in BUNDLED_FONTS}
    for match in _FONT_ARG.finditer(scan.uncommented):
        for name in _STRING.findall(match.group(1)):
            if name.casefold() not in bundled:
                issues.append(
                    TemplateIssue(
                        "unknown_font",
                        f"The font {name!r} is not available. Use only {', '.join(BUNDLED_FONTS)}.",
                        _line(scan.uncommented, match.start()),
                    )
                )
    return issues


def _copy_issues(source: str, scan: _Scan, reference: Reference) -> list[TemplateIssue]:
    issues: list[TemplateIssue] = []
    lowered = _norm(source)
    stripped = re.sub(r"https?://|www\.", "", lowered)
    if reference.name and reference.name.casefold() in lowered:
        issues.append(
            TemplateIssue(
                "copied_name",
                "The source holds the person's name from the attached CV. Use cv.basics.name.",
            )
        )
    if any(email in lowered for email in reference.emails):
        issues.append(
            TemplateIssue(
                "copied_email",
                "The source holds an email address from the attached CV. Use the data.",
            )
        )
    candidates = {_phone_digits(c) for c in _PHONE.findall(source)} - {None}
    if any(
        phone in candidate for phone in reference.phones for candidate in candidates if candidate
    ):
        issues.append(
            TemplateIssue(
                "copied_phone",
                "The source holds a phone number from the attached CV. Use the data.",
            )
        )
    if any(url in stripped for url in reference.urls):
        issues.append(
            TemplateIssue(
                "copied_url", "The source holds a link from the attached CV. Use the data."
            )
        )
    for text, line in scan.literals:
        if len(text) > MAX_LITERAL_CHARS:
            issues.append(
                TemplateIssue(
                    "long_literal",
                    f"A string longer than {MAX_LITERAL_CHARS} characters is copied text, not a "
                    "label. Take text from the data.",
                    line,
                )
            )
            continue
        words = _norm(text).split()
        if (
            len(_norm(text)) >= 12
            and len(words) >= 2
            and _norm(text) in reference.text
            and not all(re.sub(r"\W", "", word) in HEADING_WORDS for word in words)
        ):
            issues.append(
                TemplateIssue(
                    "copied_text",
                    "A string repeats text of the attached CV. Take text from the data.",
                    line,
                )
            )
    for match in _PROSE.finditer(scan.code):
        issues.append(
            TemplateIssue(
                "prose",
                "The source holds a run of plain words that reads as a sentence. Take text from "
                "the data.",
                _line(scan.code, match.start()),
            )
        )
    return issues


def mentions_owner(text: str, reference: Reference) -> bool:
    """Whether `text` holds the uploaded CV's owner: their name, an email address or a link. For
    the name and description a model gives a template."""
    lowered = _norm(text)
    stripped = re.sub(r"https?://|www\.", "", lowered)
    return bool(
        (reference.name and reference.name.casefold() in lowered)
        or any(email in lowered for email in reference.emails)
        or any(url in stripped for url in reference.urls)
    )


def check_template(source: str, reference: Reference | None = None) -> list[TemplateIssue]:
    """Everything wrong with `source` that can be seen without rendering it, in source order
    within each group. `reference` (from the uploaded CV) adds the copy checks. Empty means
    passed."""
    scan = _scan(source)
    return [
        *_structure_issues(source, scan),
        *_access_issues(scan),
        *_copy_issues(source, scan, reference or Reference()),
    ]


def check_pages(pages: int, target_pages: int) -> list[TemplateIssue]:
    """The sample CV fits the template's page target."""
    if pages <= target_pages:
        return []
    noun = "page" if target_pages == 1 else "pages"
    return [
        TemplateIssue(
            "too_many_pages",
            f"The sample CV takes {pages} pages but must fit {target_pages} {noun}. Reduce type "
            "size, spacing or margins.",
        )
    ]


def _expected_text(content: CvContent) -> dict[str, list[str]]:
    """What a template must show of a CV, by kind, each as the text a render must contain. A skills
    group with a label and no skills holds nothing to show, so a template may leave it out."""
    basics = content.basics
    found: dict[str, list[str]] = {
        "name": [basics.name],
        "headline": [basics.headline],
        "contact details": [basics.email, basics.phone, basics.location],
        "summary": [plain_text(content.summary)[:20]],
        "section titles": [],
        "entries": [],
        "bullets": [],
    }
    for section in content.sections:
        entries = (
            [(item.org, item.role) for item in section.experience]
            + [(item.name,) for item in section.projects]
            + [(item.institution, item.degree) for item in section.education]
            + [(item.label,) for item in section.skills if item.items]
            + [(item.name,) for item in section.certifications]
        )
        has_items = bool(entries or section.custom)
        if has_items:
            found["section titles"].append(section.title)
        for entry in entries:
            found["entries"].extend(entry)
    found["bullets"] = [plain_text(b.text)[:20] for b in iter_bullets(content)]
    return {kind: [t for t in texts if t.strip()] for kind, texts in found.items()}


MIN_BULLET_SHARE = 0.5


def check_render(text: str, content: CvContent) -> list[TemplateIssue]:
    """The text of a template's PDF, rendered from `content`, shows what the data holds: the
    name, headline, contact details, summary, every section title and entry, and at least half
    the bullets. A template that drops data would silently drop a user's CV."""
    haystack = _squash(text)
    issues: list[TemplateIssue] = []
    for kind, texts in _expected_text(content).items():
        if not texts:
            continue
        missing = [t for t in texts if _squash(t) not in haystack]
        allowed = len(texts) * (1 - MIN_BULLET_SHARE) if kind == "bullets" else 0
        if len(missing) > allowed:
            issues.append(
                TemplateIssue(
                    "missing_content",
                    f"The rendered sample CV does not show its {kind}. The template must draw "
                    "every part of the data.",
                )
            )
    return issues
