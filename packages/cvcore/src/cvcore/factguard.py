"""The fact guard: tailoring may select, reorder and reword, never add facts (AGENTS.md rule 8).

`check(source, tailored)` compares a tailored CV with the profile it came from and returns the
content with every violation corrected, plus a report of what was corrected:

- `new_claim`: a bullet without a known `source_id`, or one moved to a different employer, becomes a
  placeholder holding its text. Entries (roles, clients, projects, degrees, certifications) that are
  not in the source are removed.
- `new_number`: a number in a bullet that is not in its source bullet becomes
  `[[check this number: <n>]]`. The summary is checked against every number in the source; a
  headline with a new number reverts to the source headline (`changed_fact`).
- `changed_fact`: organisations, roles, clients, dates, locations, institutions, degrees, project
  and certification details, and contact details revert to the source.
- `new_skill`: skills and stack entries that are not in the source are removed. A skill counts as
  in the source when it is a source skill or stack entry, or is mentioned in any source text; a
  stack entry must belong to the same role in the source.

Entries are matched by id, then by name (for example organisation and role), so a model that
rewrites ids still lines up. The guard is deterministic and has no I/O.
"""

import re
from collections.abc import Callable, Iterable
from typing import Literal

from pydantic import BaseModel

from cvcore.ids import new_id
from cvcore.models import (
    Bullet,
    CertificationItem,
    CvContent,
    EducationItem,
    Engagement,
    ExperienceItem,
    ProjectItem,
    SkillGroup,
    Span,
)
from cvcore.richtext import CLOSE, OPEN, parse, plain_text, serialize

IssueKind = Literal["new_claim", "new_number", "changed_fact", "new_skill"]

# A number as a CV states it: 140, 1,200, 1.2, with an optional %, +, k, m, b or x right after it.
# Digits inside words (S3, EC2, v2) are not numbers.
NUMBER = re.compile(
    r"(?<![\w.])(?P<core>\d{1,3}(?:,\d{3})+|\d+)(?P<frac>\.\d+)?"
    r"(?P<suffix>%|\+|[kKmMbBxX](?![A-Za-z0-9]))?(?!\w)"
)


class FactIssue(BaseModel):
    kind: IssueKind
    message: str
    """What was corrected, in words the review screen can show."""
    bullet_id: str | None = None
    """The tailored bullet it is about, when it is about a bullet."""
    value: str | None = None
    """The number, skill or text that was corrected."""


class FactReport(BaseModel):
    content: CvContent
    """The tailored content with every violation corrected."""
    issues: list[FactIssue]


def number_tokens(text: str) -> set[tuple[str, str]]:
    """(value, suffix) for every number: "$4,800" is ("4800", ""), "62%" is ("62", "%")."""
    return {_token(match) for match in NUMBER.finditer(text)}


def _token(match: re.Match[str]) -> tuple[str, str]:
    value = match["core"].replace(",", "") + (match["frac"] or "")
    return value, (match["suffix"] or "").lower()


def _number_allowed(token: tuple[str, str], allowed: set[tuple[str, str]]) -> bool:
    value, suffix = token
    return any(
        value == known and (not suffix or suffix == known_suffix) for known, known_suffix in allowed
    )


def _key(*parts: str) -> tuple[str, ...]:
    return tuple(" ".join(part.split()).casefold() for part in parts)


def _mentioned(term: str, text: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term.casefold())}(?!\w)", text) is not None


def as_placeholder(text: str) -> str:
    """The text, without markers, as one placeholder."""
    plain = plain_text(text).replace(OPEN, "[ [").replace(CLOSE, "] ]").strip()
    return f"{OPEN}{plain}{CLOSE}" if plain else ""


class _Source:
    """Lookups over the profile the tailored CV must stay true to."""

    def __init__(self, content: CvContent) -> None:
        self.content = content
        # Bullet id -> (bullet, owner). Bullets of a role and of its client engagements share the
        # role as owner: moving between them keeps the employer.
        self.bullets: dict[str, tuple[Bullet, str]] = {}
        self.experience: dict[str, ExperienceItem] = {}
        self.projects: dict[str, ProjectItem] = {}
        self.education: dict[str, EducationItem] = {}
        self.certifications: dict[str, CertificationItem] = {}
        self.skills: set[str] = set()
        texts = [content.summary, content.basics.headline]

        for section in content.sections:
            for item in section.experience:
                self.experience[item.id] = item
                self.skills.update(entry.casefold() for entry in item.stack)
                for bullet in item.bullets:
                    self.bullets[bullet.id] = (bullet, f"experience:{item.id}")
                for engagement in item.engagements:
                    for bullet in engagement.bullets:
                        self.bullets[bullet.id] = (bullet, f"experience:{item.id}")
            for project in section.projects:
                self.projects[project.id] = project
                for bullet in project.bullets:
                    self.bullets[bullet.id] = (bullet, f"project:{project.id}")
            for bullet in section.custom:
                self.bullets[bullet.id] = (bullet, "custom")
            for item in section.education:
                self.education[item.id] = item
            for item in section.certifications:
                self.certifications[item.id] = item
            for group in section.skills:
                self.skills.update(entry.casefold() for entry in group.items)

        texts.extend(bullet.text for bullet, _ in self.bullets.values())
        self.text = " ".join(plain_text(text) for text in texts).casefold()
        self.numbers = set().union(*(number_tokens(plain_text(text)) for text in texts))

    def match[T: (ExperienceItem, ProjectItem, EducationItem, CertificationItem)](
        self, items: dict[str, T], item: T, key: Callable[[T], tuple[str, ...]]
    ) -> T | None:
        if item.id in items:
            return items[item.id]
        return next((known for known in items.values() if key(known) == key(item)), None)

    def has_skill(self, skill: str) -> bool:
        return skill.casefold() in self.skills or _mentioned(skill, self.text)


class _Guard:
    def __init__(self, source: CvContent) -> None:
        self.source = _Source(source)
        self.issues: list[FactIssue] = []
        self.bullet_ids: set[str] = set()

    def issue(
        self,
        kind: IssueKind,
        message: str,
        *,
        bullet_id: str | None = None,
        value: str | None = None,
    ) -> None:
        self.issues.append(FactIssue(kind=kind, message=message, bullet_id=bullet_id, value=value))

    def revert(self, label: str, tailored: object, source: object, field: str) -> None:
        """Set `field` back to the source value when the tailored one differs."""
        before, after = getattr(source, field), getattr(tailored, field)
        if before != after:
            setattr(tailored, field, before)
            self.issue("changed_fact", f"Kept the {label} from your profile.", value=str(after))

    # Text

    def numbers(self, text: str, allowed: set[tuple[str, str]], bullet_id: str | None) -> str:
        """The text with every number that is not in `allowed` turned into a placeholder."""
        spans: list[Span] = []
        for span in parse(text):
            if span.p:
                spans.append(span)
                continue
            position = 0
            for match in NUMBER.finditer(span.t):
                if _number_allowed(_token(match), allowed):
                    continue
                if match.start() > position:
                    spans.append(Span(t=span.t[position : match.start()], b=span.b))
                spans.append(Span(t=f"check this number: {match[0]}", b=span.b, p=True))
                self.issue(
                    "new_number",
                    f"The number {match[0]} is not in your profile. Check it before using this CV.",
                    bullet_id=bullet_id,
                    value=match[0],
                )
                position = match.end()
            if position < len(span.t):
                spans.append(Span(t=span.t[position:], b=span.b))
        return serialize(spans)

    def bullets(self, bullets: Iterable[Bullet], owner: str) -> list[Bullet]:
        kept: list[Bullet] = []
        for bullet in bullets:
            if not bullet.id or bullet.id in self.bullet_ids:
                bullet.id = new_id()
            self.bullet_ids.add(bullet.id)
            known = self.source.bullets.get(bullet.source_id or "")
            if known is None or known[1] != owner:
                reason = "is not in your profile" if known is None else "comes from another entry"
                bullet.text = as_placeholder(bullet.text)
                bullet.source_id = None
                self.issue(
                    "new_claim",
                    f"This bullet {reason}. Rewrite it from your own experience or delete it.",
                    bullet_id=bullet.id,
                    value=plain_text(bullet.text),
                )
                if not bullet.text:
                    continue
            else:
                allowed = number_tokens(plain_text(known[0].text))
                bullet.text = self.numbers(bullet.text, allowed, bullet.id)
            kept.append(bullet)
        return kept

    def skills(self, entries: list[str], allowed: Callable[[str], bool]) -> list[str]:
        kept = []
        for entry in entries:
            if allowed(entry):
                kept.append(entry)
            else:
                self.issue("new_skill", f"Removed {entry}: it is not in your profile.", value=entry)
        return kept

    # Entries

    def experience(self, item: ExperienceItem) -> ExperienceItem | None:
        source = self.source.match(self.source.experience, item, lambda it: _key(it.org, it.role))
        if source is None:
            self.issue(
                "new_claim",
                f"Removed {item.role} at {item.org}: it is not in your profile.",
                value=f"{item.role}, {item.org}",
            )
            return None
        item.id = source.id
        for label, field in [("organisation", "org"), ("role", "role"), ("location", "location")]:
            self.revert(label, item, source, field)
        self.revert("dates", item, source, "dates")
        own_stack = {entry.casefold() for entry in source.stack}
        item.stack = self.skills(item.stack, lambda entry: entry.casefold() in own_stack)
        owner = f"experience:{source.id}"
        item.bullets = self.bullets(item.bullets, owner)
        item.engagements = [
            kept
            for e in item.engagements
            if (kept := self.engagement(e, source, owner)) is not None
        ]
        return item

    def engagement(
        self, engagement: Engagement, parent: ExperienceItem, owner: str
    ) -> Engagement | None:
        known = {e.id: e for e in parent.engagements}
        source = known.get(engagement.id) or next(
            (e for e in parent.engagements if _key(e.name) == _key(engagement.name)), None
        )
        if source is None:
            self.issue(
                "new_claim",
                f"Removed {engagement.name}: it is not a client of {parent.org} in your profile.",
                value=engagement.name,
            )
            return None
        engagement.id = source.id
        for label, field in [
            ("client name", "name"),
            ("client label", "label"),
            ("location", "location"),
            ("dates", "dates"),
        ]:
            self.revert(label, engagement, source, field)
        engagement.bullets = self.bullets(engagement.bullets, owner)
        return engagement

    def project(self, item: ProjectItem) -> ProjectItem | None:
        source = self.source.match(self.source.projects, item, lambda it: _key(it.name))
        if source is None:
            self.issue(
                "new_claim", f"Removed {item.name}: it is not in your profile.", value=item.name
            )
            return None
        item.id = source.id
        for label, field in [
            ("project name", "name"),
            ("link", "url"),
            ("status", "status"),
            ("year", "year"),
        ]:
            self.revert(label, item, source, field)
        item.bullets = self.bullets(item.bullets, f"project:{source.id}")
        return item

    def education(self, item: EducationItem) -> EducationItem | None:
        source = self.source.match(
            self.source.education, item, lambda it: _key(it.institution, it.degree)
        )
        if source is None:
            self.issue(
                "new_claim",
                f"Removed {item.degree} at {item.institution}: it is not in your profile.",
                value=f"{item.degree}, {item.institution}",
            )
            return None
        item.id = source.id
        for label, field in [
            ("institution", "institution"),
            ("degree", "degree"),
            ("location", "location"),
            ("dates", "dates"),
        ]:
            self.revert(label, item, source, field)
        return item

    def certification(self, item: CertificationItem) -> CertificationItem | None:
        source = self.source.match(self.source.certifications, item, lambda it: _key(it.name))
        if source is None:
            self.issue(
                "new_claim", f"Removed {item.name}: it is not in your profile.", value=item.name
            )
            return None
        item.id = source.id
        for label, field in [
            ("certification", "name"),
            ("issuer", "issuer"),
            ("date", "date"),
        ]:
            self.revert(label, item, source, field)
        return item

    def skill_group(self, group: SkillGroup) -> SkillGroup | None:
        group.items = self.skills(group.items, self.source.has_skill)
        return group if group.items else None


def check(source: CvContent, tailored: CvContent) -> FactReport:
    guard = _Guard(source)
    content = tailored.model_copy(deep=True)

    for label, field in [
        ("name", "name"),
        ("email", "email"),
        ("phone number", "phone"),
        ("location", "location"),
        ("links", "links"),
    ]:
        guard.revert(label, content.basics, source.basics, field)
    # The headline is plain text, so it cannot hold a placeholder: a new number reverts it.
    numbers = guard.source.numbers
    if not all(_number_allowed(token, numbers) for token in number_tokens(content.basics.headline)):
        guard.revert("headline", content.basics, source.basics, "headline")
    content.summary = guard.numbers(content.summary, numbers, None)

    def keep[T](items: Iterable[T], fix: Callable[[T], T | None]) -> list[T]:
        return [kept for item in items if (kept := fix(item)) is not None]

    for section in content.sections:
        section.experience = keep(section.experience, guard.experience)
        section.projects = keep(section.projects, guard.project)
        section.education = keep(section.education, guard.education)
        section.certifications = keep(section.certifications, guard.certification)
        section.skills = keep(section.skills, guard.skill_group)
        section.custom = guard.bullets(section.custom, "custom")

    return FactReport(content=content, issues=guard.issues)
