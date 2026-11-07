"""Finishing drafted answers to application questions (docs/BACKEND.md, Drafted answers).

Drafts follow their own rule, not the CV rule: the fact guard never runs on them, and nothing here
judges a claim or removes a skill. This module turns numbers the material does not give into
placeholders, fits a draft to its limits, and works out which skills a draft names that the
material does not mention, for the hint under it. It shares the guard's number pattern and mention
test, nothing else.
"""

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from cvcore.ai import SkillMention
from cvcore.factguard import NUMBER, mentioned, number_allowed, number_tokens
from cvcore.models import CvContent, CvModel
from cvcore.richtext import CLOSE, OPEN, parse, plain_text

MAX_INFERRED = 5
"""Skills named in the hint under one answer."""
MAX_BASIS = 3
"""What one inferred skill is said to rest on."""


class InferredSkill(CvModel):
    skill: str
    """A skill the answer names that the material does not mention."""
    based_on: list[str]
    """What in the material it rests on; every item is in the material."""


class FinishedAnswer(CvModel):
    id: str
    text: str
    """Plain text; gaps stay as [[placeholders]]."""
    inferred: list[InferredSkill]
    placeholders: int
    shortened: bool
    """The draft was cut to the question's word or character limit."""


@dataclass(frozen=True)
class Limits:
    multiline: bool = True
    """False for a single-line field: the answer gets one line."""
    max_words: int | None = None
    max_chars: int | None = None


def for_drafting(content: CvContent) -> CvContent:
    """What the AI provider reads: the CV without email, phone and links, which no answer needs."""
    copy = content.model_copy(deep=True)
    copy.basics.email = ""
    copy.basics.phone = ""
    copy.basics.links = []
    return copy


def _texts(content: CvContent) -> Iterator[str]:
    basics = content.basics
    yield from (basics.name, basics.headline, basics.location, content.summary)
    for section in content.sections:
        yield section.title
        for item in section.experience:
            yield from (item.org, item.role, item.location, item.dates.start, item.dates.end or "")
            yield from item.stack
            yield from (bullet.text for bullet in item.bullets)
            for engagement in item.engagements:
                yield from (engagement.name, engagement.label, engagement.location)
                if engagement.dates:
                    yield from (engagement.dates.start, engagement.dates.end or "")
                yield from (bullet.text for bullet in engagement.bullets)
        for project in section.projects:
            yield from (project.name, project.status, project.year)
            yield from (bullet.text for bullet in project.bullets)
        for school in section.education:
            yield from (school.institution, school.degree, school.location)
            yield from (school.dates.start, school.dates.end or "")
        for group in section.skills:
            yield group.label
            yield from group.items
        for cert in section.certifications:
            yield from (cert.name, cert.issuer, cert.date)
        yield from (bullet.text for bullet in section.custom)


class Material:
    """What drafts may draw on: everything the profile or CV says. The job ad counts for numbers
    only; a skill the ad asks for is not one the applicant has."""

    def __init__(self, content: CvContent, ad: str = "") -> None:
        plain = " ".join(plain_text(text) for text in _texts(content) if text)
        self.text = plain.casefold()
        self.skills = {
            entry.casefold()
            for section in content.sections
            for entry in [
                *(item for group in section.skills for item in group.items),
                *(entry for item in section.experience for entry in item.stack),
            ]
        }
        self.numbers = number_tokens(plain) | number_tokens(ad)

    def mentions(self, term: str) -> bool:
        term = term.strip()
        return bool(term) and (term.casefold() in self.skills or mentioned(term, self.text))


def tidy(text: str, *, multiline: bool = True) -> str:
    """Plain text: no bold markers or em dashes (a comma takes the dash's place), single spaces, at
    most one blank line between paragraphs; a single-line answer is joined into one line."""
    text = re.sub(r"\s*\u2014\s*", ", ", text.replace("**", ""))
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    if not multiline:
        return " ".join(line for line in lines if line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _check_number(match: re.Match[str], allowed: set[tuple[str, str]]) -> str:
    tokens = number_tokens(match[0])
    if all(number_allowed(token, allowed) for token in tokens):
        return match[0]
    return f"{OPEN}check this number: {match[0]}{CLOSE}"


def guard_numbers(text: str, allowed: set[tuple[str, str]]) -> str:
    """Each number outside a placeholder that `allowed` does not hold becomes one to check."""
    parts = []
    for span in parse(text):
        if span.p:
            parts.append(f"{OPEN}{span.t}{CLOSE}")
        else:
            parts.append(NUMBER.sub(lambda match: _check_number(match, allowed), span.t))
    return "".join(parts)


def word_count(text: str) -> int:
    return len(text.split())


def _over(text: str, limits: Limits) -> bool:
    return bool(
        (limits.max_words and word_count(text) > limits.max_words)
        or (limits.max_chars and len(text) > limits.max_chars)
    )


def _cut(text: str, limits: Limits) -> str:
    """One sentence too long for the limits, cut at a word."""
    if limits.max_words:
        words = re.match(rf"(?:\S+\s*){{1,{limits.max_words}}}", text)
        text = words[0] if words else text
    if limits.max_chars and len(text) > limits.max_chars:
        cut = text[: limits.max_chars]
        space = cut.rfind(" ")
        at_word_end = text[limits.max_chars].isspace()
        text = cut if at_word_end or space <= limits.max_chars // 2 else cut[:space]
    # A placeholder cut in half would show its opening brackets as text.
    if text.rfind(OPEN) > text.rfind(CLOSE):
        text = text[: text.rfind(OPEN)]
    return text.rstrip(" ,;:-\n")


def fit(text: str, limits: Limits) -> tuple[str, bool]:
    """The text within its limits, dropping whole sentences from the end; True when it was cut."""
    if not _over(text, limits):
        return text, False
    sentences = re.split(r"(?<=[.!?])(?=\s)", text)
    while len(sentences) > 1 and _over("".join(sentences).rstrip(), limits):
        sentences.pop()
    fitted = "".join(sentences).rstrip()
    return (_cut(fitted, limits) if _over(fitted, limits) else fitted), True


def _unique(items: Iterator[str]) -> list[str]:
    seen: dict[str, str] = {}
    for item in items:
        item = item.strip()
        if item and item.casefold() not in seen:
            seen[item.casefold()] = item
    return list(seen.values())


def inferred_skills(
    text: str,
    skills: Sequence[SkillMention],
    material: Material,
    keywords: Sequence[str] = (),
) -> list[InferredSkill]:
    """The skills the answer names that the material does not mention: those the model says it
    names, and the job's keywords found in it. Each keeps the basis the material does mention."""
    answer = plain_text(text).casefold()
    basis = {mention.skill.strip().casefold(): mention.based_on for mention in skills}
    named = _unique(
        term
        for term in [*(mention.skill for mention in skills), *keywords]
        if term.strip() and mentioned(term.strip(), answer)
    )
    found = []
    for skill in named:
        if material.mentions(skill):
            continue
        rests_on = _unique(
            item for item in basis.get(skill.casefold(), []) if material.mentions(item)
        )
        found.append(InferredSkill(skill=skill, based_on=rests_on[:MAX_BASIS]))
    return found[:MAX_INFERRED]


def finish(
    question_id: str,
    draft: str,
    skills: Sequence[SkillMention],
    *,
    question: str,
    limits: Limits,
    material: Material,
    keywords: Sequence[str] = (),
) -> FinishedAnswer:
    """The answer the user sees for one question, from the model's draft (empty when it gave
    none). Numbers neither the material, the job ad nor the question gives become placeholders."""
    text = tidy(draft, multiline=limits.multiline)
    text = guard_numbers(text, material.numbers | number_tokens(question))
    text, shortened = fit(text, limits)
    return FinishedAnswer(
        id=question_id,
        text=text,
        inferred=inferred_skills(text, skills, material, keywords) if text else [],
        placeholders=sum(1 for span in parse(text) if span.p),
        shortened=shortened,
    )
