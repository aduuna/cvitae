"""What job application forms ask for, read from CV content. The browser extension fills forms
with it.

Text is plain: bold markers are dropped, and placeholders keep their brackets so a gap the user
has not filled yet stays visible in the form instead of reading as a real phrase. Nothing is
added: every value is the CV's own text, split or reformatted (a name into parts, a location into
city and country, a date into year and month)."""

import re
from collections.abc import Iterable
from typing import Literal
from urllib.parse import urlsplit

from cvcore.models import Bullet, CvContent, CvModel, EducationItem, ExperienceItem
from cvcore.places import parse_place
from cvcore.richtext import parse

DegreeLevel = Literal["", "high_school", "associate", "bachelor", "master", "doctorate"]


class NameParts(CvModel):
    full: str
    first: str
    middle: str
    """Every word between the first and the last."""
    last: str


class Place(CvModel):
    full: str
    """As written in the CV."""
    city: str
    region: str
    region_names: list[str]
    """Spellings of the region a list might use: as written, and the code and name of a US state."""
    country: str
    """The country's English name when recognised, else empty."""
    country_code: str
    """ISO 3166-1 alpha-2, empty when not recognised."""
    country_names: list[str]
    """Spellings of the country a list might use: name, code and common aliases."""


class YearMonth(CvModel):
    year: int
    month: int | None = None
    """1 to 12; None when the CV gives only the year."""


class Links(CvModel):
    linkedin: str = ""
    github: str = ""
    gitlab: str = ""
    twitter: str = ""
    stackoverflow: str = ""
    website: str = ""
    """The first link that is none of the above: a portfolio, blog or personal site."""
    other: list[str]
    """Every other link, in CV order."""


class Role(CvModel):
    id: str
    company: str
    title: str
    location: str
    start: YearMonth | None
    end: YearMonth | None
    """None while the role is current (see `current`), or when the CV's date cannot be read."""
    current: bool
    description: str
    """The role's bullets, one per line, then each client engagement under its own heading."""
    stack: list[str]


class Education(CvModel):
    id: str
    institution: str
    degree: str
    """As written, for example "BSc Computer Science"."""
    level: DegreeLevel
    field: str
    """The subject when the degree names one, for example "Computer Science"."""
    location: str
    start: YearMonth | None
    end: YearMonth | None


class Certification(CvModel):
    name: str
    issuer: str
    date: str


class ApplicationData(CvModel):
    name: NameParts
    headline: str
    email: str
    phone: str
    location: Place
    links: Links
    summary: str
    current_company: str
    """The organisation of the first current role, else empty."""
    current_title: str
    experience: list[Role]
    """Every role, in CV order (usually most recent first)."""
    education: list[Education]
    skills: list[str]
    """Skill group entries, then stack entries, without repeats."""
    certifications: list[Certification]
    placeholders: int
    """Placeholders left in the text above; the user should fill them before applying."""


def to_application_data(content: CvContent) -> ApplicationData:
    counter = _PlaceholderCounter()
    experience = [_role(item, counter) for item in _experience(content)]
    current = next((role for role in experience if role.current), None)
    return ApplicationData(
        name=split_name(content.basics.name),
        headline=content.basics.headline.strip(),
        email=content.basics.email.strip(),
        phone=content.basics.phone.strip(),
        location=_place(content.basics.location),
        links=classify_links(str(link.url) for link in content.basics.links),
        summary=counter.text(content.summary),
        current_company=current.company if current else "",
        current_title=current.title if current else "",
        experience=experience,
        education=[_education(item) for section in content.sections for item in section.education],
        skills=_skills(content),
        certifications=[
            Certification(name=item.name, issuer=item.issuer, date=item.date)
            for section in content.sections
            for item in section.certifications
        ],
        placeholders=counter.count,
    )


class _PlaceholderCounter:
    def __init__(self) -> None:
        self.count = 0

    def text(self, text: str) -> str:
        """Plain text: bold dropped, placeholders kept in their brackets and counted."""
        out: list[str] = []
        for span in parse(text):
            if span.p:
                self.count += 1
                out.append(f"[[{span.t}]]")
            else:
                out.append(span.t)
        return "".join(out).strip()

    def lines(self, bullets: Iterable[Bullet]) -> list[str]:
        return [f"- {line}" for bullet in bullets if (line := self.text(bullet.text))]


def split_name(name: str) -> NameParts:
    """First word, last word and the words between. People who use one name get only `first`."""
    words = name.split()
    if not words:
        return NameParts(full="", first="", middle="", last="")
    return NameParts(
        full=" ".join(words),
        first=words[0],
        middle=" ".join(words[1:-1]),
        last=words[-1] if len(words) > 1 else "",
    )


def _place(location: str) -> Place:
    place = parse_place(location)
    country = place.country
    return Place(
        full=place.full,
        city=place.city,
        region=place.region,
        region_names=list(place.region_names),
        country=country.name if country else "",
        country_code=country.code if country else "",
        country_names=country.spellings if country else [],
    )


_LINK_HOSTS: dict[str, str] = {
    "linkedin.com": "linkedin",
    "github.com": "github",
    "gitlab.com": "gitlab",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "stackoverflow.com": "stackoverflow",
}


def _link_kind(host: str) -> str | None:
    """The site a host belongs to, subdomains included ("uk.linkedin.com")."""
    for site, kind in _LINK_HOSTS.items():
        if host == site or host.endswith(f".{site}"):
            return kind
    return None


def classify_links(urls: Iterable[str]) -> Links:
    """Each link by its site; the first unrecognised one is the website."""
    found: dict[str, str] = {}
    other: list[str] = []
    for url in urls:
        kind = _link_kind(urlsplit(url).hostname or "")
        if kind and kind not in found:
            found[kind] = url
        elif kind is None and "website" not in found:
            found["website"] = url
        else:
            other.append(url)
    return Links(**found, other=other)


def parse_date(text: str | None) -> YearMonth | None:
    """ "2024-01" or "2024" as the CV stores them; anything else is None."""
    match = re.fullmatch(r"\s*(\d{4})(?:-(\d{1,2}))?\s*", text or "")
    if not match:
        return None
    month = int(match[2]) if match[2] else None
    return YearMonth(year=int(match[1]), month=month if month and 1 <= month <= 12 else None)


def _experience(content: CvContent) -> Iterable[ExperienceItem]:
    for section in content.sections:
        yield from section.experience


def _role(item: ExperienceItem, counter: _PlaceholderCounter) -> Role:
    lines = counter.lines(item.bullets)
    for engagement in item.engagements:
        heading = f"{engagement.label}: {engagement.name}".strip(": ")
        if engagement.location:
            heading = f"{heading}, {engagement.location}"
        lines += ["", heading, *counter.lines(engagement.bullets)]
    return Role(
        id=item.id,
        company=item.org.strip(),
        title=item.role.strip(),
        location=item.location.strip(),
        start=parse_date(item.dates.start),
        end=parse_date(item.dates.end),
        current=item.dates.end is None,
        description="\n".join(lines).strip(),
        stack=list(item.stack),
    )


def _education(item: EducationItem) -> Education:
    return Education(
        id=item.id,
        institution=item.institution.strip(),
        degree=item.degree.strip(),
        level=degree_level(item.degree),
        field=degree_field(item.degree),
        location=item.location.strip(),
        start=parse_date(item.dates.start),
        end=parse_date(item.dates.end),
    )


# Degree abbreviations, matched as whole words with optional dots ("B.Sc.", "BSc").
_LEVELS: list[tuple[DegreeLevel, str]] = [
    ("doctorate", r"ph\.?\s?d|d\.?phil|doctor(?:ate)?|d\.?sc|ed\.?d|eng\.?d"),
    (
        "master",
        r"master'?s?|m\.?sc|m\.?s|m\.?a|mba|m\.?eng|m\.?phil|m\.?res|ll\.?m|m\.?tech|m\.?ed",
    ),
    (
        "bachelor",
        r"bachelor'?s?|b\.?sc|b\.?s|b\.?a|b\.?eng|b\.?tech|ll\.?b|b\.?com|bba|b\.?ed|ba\s?\(hons\)",
    ),
    ("associate", r"associate'?s?|a\.?a\.?s|a\.?a"),
    ("high_school", r"high\s+school|secondary\s+school|a[\s-]levels?|wassce|ssce|gcses?|ib"),
]


def degree_level(degree: str) -> DegreeLevel:
    for level, pattern in _LEVELS:
        if re.search(rf"(?<![\w.])(?:{pattern})\.?(?![\w])", degree, re.IGNORECASE):
            return level
    return ""


_ABBREVIATION = re.compile(
    r"^\s*(?:[a-z]{1,4}\.?){1,3}\s*(?:\((?:hons?|honou?rs)\))?\s*,?\s*", re.IGNORECASE
)


def degree_field(degree: str) -> str:
    """The subject of a degree: after "in" ("Bachelor of Science in Physics"), or after a leading
    abbreviation ("BSc (Hons) Physics"). Empty when there is none ("Bachelor of Arts")."""
    text = degree.strip()
    if match := re.search(r"\bin\s+(.+)$", text, re.IGNORECASE):
        return match[1].strip(" ,")
    if degree_level(text) not in ("", "high_school") and (match := _ABBREVIATION.match(text)):
        rest = text[match.end() :]
        if re.match(r"[^\W\d_]", rest) and not re.match(r"(?:of|degree)\b", rest, re.I):
            return rest.strip(" ,")
    return ""


def _skills(content: CvContent) -> list[str]:
    seen: dict[str, str] = {}
    entries = [
        entry for section in content.sections for group in section.skills for entry in group.items
    ]
    entries += [entry for item in _experience(content) for entry in item.stack]
    for entry in entries:
        entry = entry.strip()
        if entry:
            seen.setdefault(entry.casefold(), entry)
    return list(seen.values())
