"""The CV as the AI providers read and write it: a flat shape both can produce reliably.

CvContent has one list per section kind, nullable dates and URLs, and many optional fields. Claude's
structured output rejects that (too many optional parameters, then a grammar too large to compile),
and Gemini leaves optional lists out. The wire shape has one entry type for every kind, no nullable
fields and every field required; empty strings stand for "not given". Fields are named for what they
hold (organisation, role, institution...), because some models ignore schema descriptions and read a
generic "title" as a job title.

`to_wire` and `from_wire` convert between the two; `from_wire(to_wire(c)) == c` for every valid CV,
except that an empty end date comes back as None (both mean "present").
"""

from pydantic import Field, HttpUrl, TypeAdapter, ValidationError

from cvcore.models import (
    Basics,
    Bullet,
    CertificationItem,
    CvContent,
    CvModel,
    DateRange,
    EducationItem,
    Engagement,
    ExperienceItem,
    Link,
    ProjectItem,
    Section,
    SectionKind,
    SkillGroup,
)

_url = TypeAdapter(HttpUrl)


class WireBullet(CvModel):
    id: str = Field(description="A short unique id.")
    text: str = Field(description="The bullet; may use **bold** and [[placeholder]] only.")
    source_id: str = Field(
        description="When tailoring: the id of the profile bullet this comes from. Else empty."
    )


class WireEngagement(CvModel):
    """A client or contingent-worker placement inside a role."""

    id: str
    label: str = Field(description='For example "Client" or "Contingent worker".')
    name: str = Field(description="The client's name.")
    location: str
    start: str = Field(description='"YYYY-MM" or "YYYY"; empty when not given.')
    end: str = Field(description="Empty when ongoing or not given.")
    bullets: list[WireBullet]


class WireEntry(CvModel):
    """One entry of a section. Fields named for another kind stay empty: experience uses
    organisation, role, location, start, end, items (the stack), bullets and engagements; projects
    use name, status, start (the year), url and bullets; education uses institution, degree,
    location, start and end; skills use name (the group label) and items; certifications use name,
    issuer and start (the date); custom uses bullets."""

    id: str
    organisation: str = Field(description="experience: the employer.")
    role: str = Field(description="experience: the job title.")
    institution: str = Field(description="education: the school or university.")
    degree: str = Field(description="education: the degree or qualification.")
    name: str = Field(
        description="projects: project name; skills: group label; certifications: name."
    )
    status: str = Field(description='projects: for example "in development"; else empty.')
    issuer: str = Field(description="certifications: who issued it.")
    location: str = Field(description="experience and education.")
    start: str = Field(
        description='"YYYY-MM" or "YYYY"; for projects the year, for certifications the date.'
    )
    end: str = Field(description="Empty when ongoing or not given.")
    url: str = Field(description="projects: a full URL, or empty.")
    items: list[str] = Field(description="experience: the tech stack; skills: the skills.")
    bullets: list[WireBullet] = Field(description="experience, projects and custom.")
    engagements: list[WireEngagement] = Field(description="experience: client placements.")


class WireSection(CvModel):
    id: str
    kind: SectionKind
    title: str
    entries: list[WireEntry]


class WireLink(CvModel):
    label: str
    url: str = Field(description="A full URL starting with https://.")


class WireBasics(CvModel):
    name: str
    headline: str
    email: str
    phone: str
    location: str
    links: list[WireLink]


class WireCv(CvModel):
    basics: WireBasics
    summary: str = Field(description="May use **bold** and [[placeholder]] only.")
    sections: list[WireSection]


class WireImportedCv(CvModel):
    content: WireCv = Field(description="The career data, copied from the CV.")
    profile_name: str = Field(
        description="The kind of work this profile is for, in 1 to 4 words, for example "
        '"Data engineering". Never the person\'s name or an employer.'
    )


class WireChange(CvModel):
    source_id: str = Field(description="Id of the profile bullet this change is about.")
    rationale: str = Field(description="One sentence on why it was reworded.")


class WireTailoredCv(CvModel):
    content: WireCv = Field(description="The tailored CV.")
    changes: list[WireChange] = Field(description="One entry per bullet that was reworded.")
    missing_keywords: list[str] = Field(
        description="Job keywords the profile does not cover. Never added to the CV."
    )


class WireCvEdit(CvModel):
    reply: str = Field(
        description="One to three plain sentences to the person: what you changed, the answer "
        "to their question, or why you made no change."
    )
    content: WireCv = Field(description="The whole CV after the change.")


# CvContent to wire


def _bullets(bullets: list[Bullet]) -> list[WireBullet]:
    return [WireBullet(id=b.id, text=b.text, source_id=b.source_id or "") for b in bullets]


def _dates(dates: DateRange | None) -> tuple[str, str]:
    return ("", "") if dates is None else (dates.start, dates.end or "")


def _entry(
    id: str,
    *,
    organisation: str = "",
    role: str = "",
    institution: str = "",
    degree: str = "",
    name: str = "",
    status: str = "",
    issuer: str = "",
    location: str = "",
    start: str = "",
    end: str = "",
    url: str = "",
    items: list[str] | None = None,
    bullets: list[WireBullet] | None = None,
    engagements: list[WireEngagement] | None = None,
) -> WireEntry:
    return WireEntry(
        id=id,
        organisation=organisation,
        role=role,
        institution=institution,
        degree=degree,
        name=name,
        status=status,
        issuer=issuer,
        location=location,
        start=start,
        end=end,
        url=url,
        items=items or [],
        bullets=bullets or [],
        engagements=engagements or [],
    )


def _wire_entries(section: Section) -> list[WireEntry]:
    match section.kind:
        case "experience":
            return [
                _entry(
                    item.id,
                    organisation=item.org,
                    role=item.role,
                    location=item.location,
                    start=item.dates.start,
                    end=item.dates.end or "",
                    items=list(item.stack),
                    bullets=_bullets(item.bullets),
                    engagements=[
                        WireEngagement(
                            id=e.id,
                            label=e.label,
                            name=e.name,
                            location=e.location,
                            start=_dates(e.dates)[0],
                            end=_dates(e.dates)[1],
                            bullets=_bullets(e.bullets),
                        )
                        for e in item.engagements
                    ],
                )
                for item in section.experience
            ]
        case "projects":
            return [
                _entry(
                    item.id,
                    name=item.name,
                    status=item.status,
                    start=item.year,
                    url=str(item.url) if item.url else "",
                    bullets=_bullets(item.bullets),
                )
                for item in section.projects
            ]
        case "education":
            return [
                _entry(
                    item.id,
                    institution=item.institution,
                    degree=item.degree,
                    location=item.location,
                    start=item.dates.start,
                    end=item.dates.end or "",
                )
                for item in section.education
            ]
        case "skills":
            return [
                _entry(group.id, name=group.label, items=list(group.items))
                for group in section.skills
            ]
        case "certifications":
            return [
                _entry(item.id, name=item.name, issuer=item.issuer, start=item.date)
                for item in section.certifications
            ]
        case "custom":
            if not section.custom:
                return []
            return [_entry(f"{section.id}-items", bullets=_bullets(section.custom))]


def to_wire(content: CvContent) -> WireCv:
    basics = content.basics
    return WireCv(
        basics=WireBasics(
            name=basics.name,
            headline=basics.headline,
            email=basics.email,
            phone=basics.phone,
            location=basics.location,
            links=[WireLink(label=link.label, url=str(link.url)) for link in basics.links],
        ),
        summary=content.summary,
        sections=[
            WireSection(
                id=section.id,
                kind=section.kind,
                title=section.title,
                entries=_wire_entries(section),
            )
            for section in content.sections
        ],
    )


# Wire to CvContent


def parse_url(value: str) -> HttpUrl | None:
    """A URL, with https:// added when the scheme is missing; None when it is not a URL."""
    value = value.strip()
    if not value:
        return None
    for candidate in (value, f"https://{value}"):
        try:
            return _url.validate_python(candidate)
        except ValidationError:
            continue
    return None


def _from_bullets(bullets: list[WireBullet]) -> list[Bullet]:
    return [Bullet(id=b.id, text=b.text, source_id=b.source_id or None) for b in bullets]


def _range(start: str, end: str) -> DateRange:
    return DateRange(start=start, end=end or None)


def _experience(entry: WireEntry) -> ExperienceItem:
    return ExperienceItem(
        id=entry.id,
        org=entry.organisation,
        role=entry.role,
        location=entry.location,
        dates=_range(entry.start, entry.end),
        stack=entry.items,
        bullets=_from_bullets(entry.bullets),
        engagements=[
            Engagement(
                id=g.id,
                name=g.name,
                label=g.label,
                location=g.location,
                dates=_range(g.start, g.end) if g.start or g.end else None,
                bullets=_from_bullets(g.bullets),
            )
            for g in entry.engagements
        ],
    )


def _section(section: WireSection) -> Section:
    """Entries go to the list for the section's kind; the other lists stay empty."""
    entries = section.entries
    kind = section.kind
    return Section(
        id=section.id,
        kind=kind,
        title=section.title,
        experience=[_experience(e) for e in entries] if kind == "experience" else [],
        projects=[
            ProjectItem(
                id=e.id,
                name=e.name,
                url=parse_url(e.url),
                status=e.status,
                year=e.start,
                bullets=_from_bullets(e.bullets),
            )
            for e in entries
        ]
        if kind == "projects"
        else [],
        education=[
            EducationItem(
                id=e.id,
                institution=e.institution,
                degree=e.degree,
                location=e.location,
                dates=_range(e.start, e.end),
            )
            for e in entries
        ]
        if kind == "education"
        else [],
        skills=[SkillGroup(id=e.id, label=e.name, items=e.items) for e in entries]
        if kind == "skills"
        else [],
        certifications=[
            CertificationItem(id=e.id, name=e.name, issuer=e.issuer, date=e.start) for e in entries
        ]
        if kind == "certifications"
        else [],
        custom=[b for e in entries for b in _from_bullets(e.bullets)] if kind == "custom" else [],
    )


def from_wire(wire: WireCv) -> CvContent:
    links = [
        Link(label=link.label, url=url)
        for link in wire.basics.links
        if (url := parse_url(link.url)) is not None
    ]
    basics = wire.basics
    return CvContent(
        basics=Basics(
            name=basics.name,
            headline=basics.headline,
            email=basics.email,
            phone=basics.phone,
            location=basics.location,
            links=links,
        ),
        summary=wire.summary,
        sections=[_section(section) for section in wire.sections],
    )
