"""The CV data model, shared by profiles, CVs, the LLM output schema and the renderer."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, HttpUrl


class CvModel(BaseModel):
    # Unknown fields are a client bug, not data to keep. Defaults are required in the serialization
    # schema so generated API types mark fields the server always returns as present.
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class Span(CvModel):
    """A rendered text run."""

    t: str
    b: bool = False
    p: bool = False


class Bullet(CvModel):
    id: str
    text: str
    """Authoring form: may contain **bold** and [[placeholder]]."""
    source_id: str | None = None
    """Id of the profile bullet it came from (tailored CVs)."""


class Link(CvModel):
    label: str
    url: HttpUrl


class Basics(CvModel):
    name: str
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[Link] = []


class DateRange(CvModel):
    start: str
    """"2024-01" or "2024"."""
    end: str | None = None
    """None means present."""


class Engagement(CvModel):
    """A client or contingent-worker placement inside a role."""

    id: str
    name: str
    label: str = "Client"
    location: str = ""
    dates: DateRange | None = None
    bullets: list[Bullet] = []


class ExperienceItem(CvModel):
    id: str
    org: str
    role: str
    location: str = ""
    dates: DateRange
    stack: list[str] = []
    bullets: list[Bullet] = []
    engagements: list[Engagement] = []


class ProjectItem(CvModel):
    id: str
    name: str
    url: HttpUrl | None = None
    status: str = ""
    year: str = ""
    bullets: list[Bullet] = []


class EducationItem(CvModel):
    id: str
    institution: str
    degree: str
    location: str = ""
    dates: DateRange


class SkillGroup(CvModel):
    id: str
    label: str
    items: list[str]


class CertificationItem(CvModel):
    id: str
    name: str
    issuer: str
    date: str = ""


SectionKind = Literal["experience", "projects", "education", "skills", "certifications", "custom"]


class Section(CvModel):
    """One list per kind; only the list matching `kind` is filled."""

    id: str
    kind: SectionKind
    title: str
    experience: list[ExperienceItem] = []
    projects: list[ProjectItem] = []
    education: list[EducationItem] = []
    skills: list[SkillGroup] = []
    certifications: list[CertificationItem] = []
    custom: list[Bullet] = []


class CvContent(CvModel):
    schema_version: Literal[1] = 1
    basics: Basics
    summary: str = ""
    sections: list[Section]
