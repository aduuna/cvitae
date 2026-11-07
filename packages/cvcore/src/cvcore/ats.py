"""The ATS score: how a CV reads to an applicant tracking system's search for one job
(docs/BACKEND.md, ATS score).

`score(cv, analysis)` matches the job's keywords and title against the CV the way a recruiter's
keyword search does: literally, on whole words, ignoring case, punctuation, plurals and British or
American spelling, with a few known short forms (JS for JavaScript) and "Full name (ABC)" pairs
read from the ad and the CV. A keyword a must-have requirement names is worth 3 points, one a
nice-to-have names 2, any other 1; the job title is worth 3. The score is the share of points the CV
covers, rounded down, so 100 means everything was found.

Keywords the CV misses are looked up in the profile it came from, so the person knows which they
can put back and which they could only add to the profile, if true. The score never changes the
CV. `checks` are what a parser needs whatever the job. Deterministic, no I/O.
"""

import re
import unicodedata
from collections.abc import Iterable, Iterator
from typing import Literal

from pydantic import BaseModel

from cvcore.ai import JobAnalysis
from cvcore.models import CvContent
from cvcore.render import find_placeholders
from cvcore.richtext import parse

Importance = Literal["required", "preferred", "other"]
Place = Literal[
    "headline",
    "summary",
    "experience",
    "projects",
    "education",
    "skills",
    "certifications",
    "other",
]
Band = Literal["strong", "good", "partial", "limited"]
CheckId = Literal["contact", "headings", "placeholders", "length"]

POINTS: dict[Importance, int] = {"required": 3, "preferred": 2, "other": 1}
TITLE_POINTS = 3

# Lowest score of each band, best first. The names follow the match strengths recruiters see in
# Greenhouse (strong, good, partial, limited).
BANDS: tuple[tuple[int, Band], ...] = (
    (80, "strong"),
    (60, "good"),
    (40, "partial"),
    (0, "limited"),
)

# Short and long forms a search should treat as one, beyond the "Full name (ABC)" pairs the ad and
# the CV spell out themselves. No short form here is also a common English word.
SAME_TERMS: tuple[tuple[str, ...], ...] = (
    ("JavaScript", "JS"),
    ("TypeScript", "TS"),
    ("Kubernetes", "K8s"),
    ("PostgreSQL", "Postgres"),
    ("Amazon Web Services", "AWS"),
    ("Google Cloud Platform", "Google Cloud", "GCP"),
    ("Microsoft Azure", "Azure"),
    ("Amazon S3", "S3"),
    ("Amazon Redshift", "Redshift"),
    ("Google BigQuery", "BigQuery"),
    ("Microsoft Excel", "Excel"),
    ("Power BI", "PowerBI"),
    ("Node.js", "NodeJS"),
    ("React", "React.js", "ReactJS"),
    ("Vue", "Vue.js", "VueJS"),
    ("Next.js", "NextJS"),
    ("C#", "C sharp"),
    (".NET", "dotnet"),
    ("Machine learning", "ML"),
    ("Artificial intelligence", "AI"),
    ("Natural language processing", "NLP"),
    ("Large language models", "LLMs"),
    ("CI/CD", "Continuous integration and continuous delivery", "Continuous integration"),
    ("Extract, transform, load", "ETL"),
    ("Business intelligence", "BI"),
    ("Quality assurance", "QA"),
    ("User experience", "UX"),
    ("User interface", "UI"),
    ("Search engine optimisation", "SEO"),
    ("Test-driven development", "TDD"),
    ("Infrastructure as code", "IaC"),
    ("Site reliability engineering", "SRE"),
    ("Object-oriented programming", "OOP"),
    ("Software development life cycle", "SDLC"),
    ("Customer relationship management", "CRM"),
    ("Enterprise resource planning", "ERP"),
)

# A word as a search index keeps it: letters and digits, with the inner dots and the trailing plus
# and hash signs of tech names (node.js, c++, c#). Other punctuation separates words.
WORD = re.compile(r"[^\W_]+(?:\.[^\W_]+)*[+#]*")

# British endings folded to American ones on both sides, so "optimisation" finds "optimization".
SPELLING = (
    ("isation", "ization"),
    ("ising", "izing"),
    ("ised", "ized"),
    ("ise", "ize"),
    ("ysing", "yzing"),
    ("ysed", "yzed"),
    ("yse", "yze"),
    ("elling", "eling"),
    ("elled", "eled"),
)

# The plural of an abbreviation (APIs, KPIs, LLMs): its "s" goes before case is folded, since "apis"
# alone looks like a word ending in "is".
ABBREVIATION_PLURAL = re.compile(r"[A-Z0-9]*[A-Z][A-Z0-9]*s")

# "(ABC)" after the words it abbreviates.
ABBREVIATION = re.compile(r"\(([^\W\d_][\w.+#/&-]{1,11})\)")
WORDS_BEFORE = re.compile(r"[^\W_]+")

SENIORITY = frozenset(
    {
        "senior",
        "sr",
        "junior",
        "jr",
        "lead",
        "principal",
        "staff",
        "head",
        "chief",
        "associate",
        "intern",
        "graduate",
        "trainee",
        "entry",
        "mid",
        "level",
        "experienced",
        "i",
        "ii",
        "iii",
        "iv",
    }
)
LINKING = frozenset({"of", "and", "the", "for", "to", "in", "a", "an"})
# Where a job title ends and the team, place or employer begins: a comma, a bracket, " at ", or a
# spaced hyphen, slash, bar or en dash.
EN_DASH = "\N{EN DASH}"
TITLE_END = re.compile(rf",|\(|\s[-|/{EN_DASH}]\s|\sat\s", re.IGNORECASE)

# Words a parser knows each kind of section by (a match anywhere in the title, ignoring case).
HEADINGS: dict[str, tuple[str, ...]] = {
    "experience": ("experience", "employment", "work history", "career"),
    "education": ("education", "academic", "qualification", "training"),
    "skills": ("skill", "technolog", "competenc", "expertise", "tool", "stack"),
    "projects": ("project", "portfolio", "open source"),
    "certifications": ("certif", "licen", "accreditation", "credential", "course"),
}
USUAL_HEADING = {
    "experience": "Experience",
    "education": "Education",
    "skills": "Skills",
    "projects": "Projects",
    "certifications": "Certifications",
}

type Phrase = tuple[str, ...]


class AtsKeyword(BaseModel):
    term: str
    """As the job analysis states it."""
    importance: Importance
    """Required when a must-have requirement names it, preferred when a nice-to-have does."""
    found_in: list[Place]
    """Where the CV has it, in reading order; empty when it does not."""
    in_profile: bool | None = None
    """For a keyword the CV misses, whether the profile the CV came from has it. None when it has
    no profile to compare, or when the CV has the keyword."""


class AtsCheck(BaseModel):
    id: CheckId
    ok: bool
    message: str


class AtsReport(BaseModel):
    score: int | None
    """0 to 100, the share of keyword and title points the CV covers, rounded down. None when the
    job gives nothing to match."""
    band: Band | None
    title: str
    """The job title without seniority words ("Data Engineer"); empty when the job has none."""
    title_found: bool
    """Whether the headline or a role title has it."""
    keywords: list[AtsKeyword]
    """Required first, then preferred, then the rest, each in the job's order."""
    checks: list[AtsCheck]


def score(
    cv: CvContent,
    analysis: JobAnalysis,
    *,
    title: str = "",
    description: str = "",
    profile: CvContent | None = None,
    pages: int | None = None,
    target_pages: int | None = None,
) -> AtsReport:
    """The ATS report for `cv` against one job. `title` overrides the analysed title (the user can
    correct it); `description` is the ad, read only for the abbreviations it spells out; `pages`
    and `target_pages` add the length check when both are known."""
    sources = [description, *analysis.keywords, *analysis.must_have, *analysis.nice_to_have]
    for content in (cv, profile):
        if content is not None:
            sources.extend(text for _, text in _fields(content))
    same = _same_terms(sources)
    cv_index = _index(cv)
    profile_index = _index(profile) if profile is not None else None
    required = [_words(text) for text in analysis.must_have]
    preferred = [_words(text) for text in analysis.nice_to_have]

    keywords: list[AtsKeyword] = []
    seen: set[Phrase] = set()
    for term in analysis.keywords:
        phrase = _words(term)
        variants = _variants(phrase, same)
        if not phrase or variants & seen:
            continue
        seen |= variants
        if any(_contains(text, v) for text in required for v in variants):
            importance: Importance = "required"
        elif any(_contains(text, v) for text in preferred for v in variants):
            importance = "preferred"
        else:
            importance = "other"
        found_in = _places(cv_index, variants)
        in_profile = None
        if not found_in and profile_index is not None:
            in_profile = bool(_places(profile_index, variants))
        keywords.append(
            AtsKeyword(
                term=term.strip(), importance=importance, found_in=found_in, in_profile=in_profile
            )
        )
    keywords.sort(key=lambda keyword: list(POINTS).index(keyword.importance))

    core = core_title(title or analysis.title)
    core_words = _words(core)
    title_found = bool(core_words) and any(
        _contains(_words(text), core_words) for text in _titles(cv)
    )

    total = sum(POINTS[k.importance] for k in keywords) + (TITLE_POINTS if core_words else 0)
    got = sum(POINTS[k.importance] for k in keywords if k.found_in)
    got += TITLE_POINTS if title_found else 0
    value = 100 * got // total if total else None
    return AtsReport(
        score=value,
        band=None if value is None else next(band for low, band in BANDS if value >= low),
        title=core,
        title_found=title_found,
        keywords=keywords,
        checks=checks(cv, pages=pages, target_pages=target_pages),
    )


def core_title(title: str) -> str:
    """The job title a search would use: before the team or place, without seniority words.
    "Senior Data Engineer, Payments Platform" is "Data Engineer"."""
    words = TITLE_END.split(title, maxsplit=1)[0].split()
    kept = [word for word in words if _fold(_normal(word).strip(".")) not in SENIORITY]
    while kept and kept[0].casefold() in LINKING:
        kept.pop(0)
    while kept and kept[-1].casefold() in LINKING:
        kept.pop()
    return " ".join(kept or words)


def checks(
    cv: CvContent, *, pages: int | None = None, target_pages: int | None = None
) -> list[AtsCheck]:
    """What a parser needs whatever the job: contact details, section titles it knows, no
    placeholders, and the template's length."""
    basics = cv.basics
    contact = (("email", basics.email), ("phone", basics.phone), ("location", basics.location))
    missing = [name for name, value in contact if not value.strip()]
    result = [
        AtsCheck(
            id="contact",
            ok=not missing,
            message=(
                f"Add your {_join(missing)} to the header, where parsers look for them."
                if missing
                else "Your email, phone and location are in the header."
            ),
        )
    ]

    odd = [
        section
        for section in cv.sections
        if section.kind in HEADINGS
        and not any(word in section.title.casefold() for word in HEADINGS[section.kind])
    ]
    titles = _join([f'"{section.title}"' for section in odd])
    usual = _join(list(dict.fromkeys(f'"{USUAL_HEADING[section.kind]}"' for section in odd)))
    result.append(
        AtsCheck(
            id="headings",
            ok=not odd,
            message=(
                f"Rename {titles} to a title parsers recognise, such as {usual}."
                if odd
                else "Every section has a title parsers recognise."
            ),
        )
    )

    gaps = len(find_placeholders(cv))
    result.append(
        AtsCheck(
            id="placeholders",
            ok=gaps == 0,
            message=(
                f"Fill in {_count(gaps, 'placeholder')}. A parser reads them as they are written."
                if gaps
                else "No placeholders are left."
            ),
        )
    )

    if pages is not None and target_pages is not None:
        result.append(
            AtsCheck(
                id="length",
                ok=pages <= target_pages,
                message=(
                    f"Runs to {_count(pages, 'page')}, over this template's "
                    f"{_count(target_pages, 'page')}."
                    if pages > target_pages
                    else f"Fits on {_count(target_pages, 'page')}."
                ),
            )
        )
    return result


# Matching


def _normal(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def _fold(word: str) -> str:
    """One form for plurals and British or American spelling. Applied to both sides, so an odd
    stem (kubernetes is kubernete) still finds itself."""
    if len(word) > 3 and word.isalpha():
        if word.endswith("ies"):
            word = word[:-3] + "y"
        elif word.endswith("sses"):
            word = word[:-2]
        elif word.endswith("s") and not word.endswith(("ss", "us", "is")):
            word = word[:-1]
        for british, american in SPELLING:
            if word.endswith(british):
                return word[: -len(british)] + american
    return word


def _words(text: str) -> Phrase:
    return tuple(
        _fold(_singular_abbreviation(word).casefold())
        for word in WORD.findall(unicodedata.normalize("NFKC", text))
    )


def _singular_abbreviation(word: str) -> str:
    return word[:-1] if len(word) > 2 and ABBREVIATION_PLURAL.fullmatch(word) else word


def _contains(text: Phrase, phrase: Phrase) -> bool:
    size = len(phrase)
    return size > 0 and any(
        text[start : start + size] == phrase for start in range(len(text) - size + 1)
    )


def _same_terms(texts: Iterable[str]) -> list[set[Phrase]]:
    """Groups of phrases that mean the same: the known ones, and every "Full name (ABC)" whose
    initials spell the abbreviation."""
    groups = [{_words(term) for term in terms} for terms in SAME_TERMS]
    for text in texts:
        for match in ABBREVIATION.finditer(text):
            short = match[1]
            letters = "".join(c for c in _singular_abbreviation(short) if c.isalnum()).casefold()
            near = WORDS_BEFORE.findall(text[max(0, match.start() - 200) : match.start()])
            full = _spelled_out(near, letters)
            if full:
                groups.append({_words(" ".join(full)), _words(short)})
    return groups


def _spelled_out(before: list[str], letters: str) -> list[str] | None:
    """The words just before an abbreviation that it stands for: their initials spell it, with or
    without the linking words among them ("Infrastructure as Code", "Total Cost of Ownership")."""
    size = len(letters)
    for start in range(len(before) - size, max(len(before) - 2 * size, 0) - 1, -1):
        words = before[start:]
        if words[0].casefold() in LINKING:
            continue
        initials = "".join(word[0] for word in words).casefold()
        content = "".join(word[0] for word in words if word.casefold() not in LINKING).casefold()
        if letters in (initials, content):
            return words
    return None


def _variants(phrase: Phrase, same: list[set[Phrase]]) -> set[Phrase]:
    variants = {phrase}
    for group in same:
        if phrase in group:
            variants |= group
    if len(phrase) > 1 and phrase[0] == "apache":
        variants.add(phrase[1:])  # Apache Spark is Spark
    return {variant for variant in variants if variant}


def _visible(text: str) -> str:
    """Rich text as a parser reads it, without placeholders: they are gaps, not content."""
    return " ".join(span.t for span in parse(text) if not span.p)


def _fields(cv: CvContent) -> Iterator[tuple[Place, str]]:
    """The CV's text, field by field, with where each sits."""
    yield "headline", cv.basics.headline
    yield "summary", _visible(cv.summary)
    for section in cv.sections:
        for item in section.experience:
            yield "experience", item.role
            yield "experience", item.org
            for entry in item.stack:
                yield "experience", entry
            for bullet in item.bullets:
                yield "experience", _visible(bullet.text)
            for engagement in item.engagements:
                yield "experience", engagement.name
                for bullet in engagement.bullets:
                    yield "experience", _visible(bullet.text)
        for project in section.projects:
            yield "projects", project.name
            for bullet in project.bullets:
                yield "projects", _visible(bullet.text)
        for degree in section.education:
            yield "education", degree.degree
            yield "education", degree.institution
        for group in section.skills:
            yield "skills", group.label
            for skill in group.items:
                yield "skills", skill
        for certification in section.certifications:
            yield "certifications", certification.name
            yield "certifications", certification.issuer
        for bullet in section.custom:
            yield "other", _visible(bullet.text)


def _index(cv: CvContent) -> list[tuple[Place, Phrase]]:
    return [(place, _words(text)) for place, text in _fields(cv) if text]


def _places(index: list[tuple[Place, Phrase]], variants: set[Phrase]) -> list[Place]:
    found = (place for place, text in index if any(_contains(text, v) for v in variants))
    return list(dict.fromkeys(found))


def _titles(cv: CvContent) -> Iterator[str]:
    """Where parsers take a person's job titles from: the headline and each role."""
    yield cv.basics.headline
    for section in cv.sections:
        for item in section.experience:
            yield item.role


# Words


def _join(items: list[str]) -> str:
    if len(items) < 2:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"
