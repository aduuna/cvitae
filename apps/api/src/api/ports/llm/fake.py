"""A deterministic provider for tests and local work without API keys."""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from api.ai.prompts import draft_answers as answers_prompt
from api.ai.prompts import edit_cv as edit_prompt
from api.ai.prompts import tailor_cv as tailor_prompt
from api.ports.llm.base import LLMRequest, LLMResult, ProviderName
from cvcore.ai import (
    DraftAnswer,
    DraftAnswers,
    GeneratedTemplate,
    JobAnalysis,
    RevisedTemplate,
    SkillMention,
)
from cvcore.models import CvContent
from cvcore.render import iter_bullets
from cvcore.wire import WireCvEdit, WireImportedCv, WireTailoredCv, to_wire

type Responder = Callable[[LLMRequest[Any]], BaseModel]


class FakeLLMProvider:
    """Answers each task with its responder; records every request. Set `fail_with` to make the
    next calls raise."""

    def __init__(self, name: ProviderName, responders: dict[str, Responder]) -> None:
        self.name = name
        self.responders = responders
        self.requests: list[LLMRequest[Any]] = []
        self.fail_with: Exception | None = None

    async def generate[T: BaseModel](self, request: LLMRequest[T]) -> LLMResult[T]:
        self.requests.append(request)
        if self.fail_with is not None:
            raise self.fail_with
        output = request.output_model.model_validate(
            self.responders[request.task](request).model_dump()
        )
        return LLMResult(
            output=output,
            provider=self.name,
            model=request.model,
            input_tokens=len(request.user_text) // 4,
            output_tokens=len(output.model_dump_json()) // 4,
            duration_ms=1,
        )


# The template the fake model drafts: a compact Geist design. A copy of
# templates/fixtures/user-template.typ, which a test keeps in step and the renderer's tests compile.
FAKE_TEMPLATE = """\
// A template as a user's own CV would produce one: Geist, a teal rule under the header.
// It is the fake model's answer in the api tests (apps/api/src/api/ports/llm/fake.py keeps a
// copy) and a renderer test checks that it compiles through the sandbox as a `files` template.
#import "/_lib/cv.typ": *
#let cv = json("data.json")

#let teal = rgb("#0f766e")
#let muted = rgb("#5f6670")

#set document(title: cv.basics.name + " CV", author: cv.basics.name)
#set page(paper: paper-size(), margin: (x: 1.8cm, y: 1.5cm))
#set text(font: "Geist", size: 9.5pt, lang: "en", hyphenate: false)
#set par(leading: 0.55em, spacing: 0.7em)
#set list(marker: text(fill: teal)[•], indent: 0.1em, body-indent: 0.5em, spacing: 0.45em)

#let meta(body) = text(fill: muted, body)

#let section-heading(title) = block(above: 1.1em, below: 0.6em, sticky: true)[
  #text(size: 10pt, weight: "semibold", fill: teal, upper(title))
  #v(-0.55em)
  #line(length: 100%, stroke: 0.6pt + teal)
]

#let engagement(item) = pad(left: 0.8em, top: 0.1em)[
  #split-row(
    text(weight: "medium", item.name),
    meta(join-items((item.location, fmt-range(item.dates)), [ · ])),
  )
  #bullets(item.bullets)
]

#let experience(item) = block(below: 0.9em)[
  #split-row([*#item.role*, #item.org], meta(fmt-range(item.dates)))
  #if item.location.trim() != "" or item.stack.len() > 0 {
    v(-0.4em)
    meta(join-items((item.location, item.stack.join(", ")), [ · ]))
  }
  #bullets(item.bullets)
  #for engagement-item in item.engagements { src(engagement-item, engagement(engagement-item)) }
]

#let project(item) = block(below: 0.8em)[
  #split-row([*#item.name*], meta(item.year))
  #bullets(item.bullets)
]

#let education(item) = block(below: 0.7em)[
  #split-row([*#item.degree*, #item.institution], meta(fmt-range(item.dates)))
]

#let skills(groups) = grid(
  columns: (auto, 1fr),
  column-gutter: 0.9em,
  row-gutter: 0.55em,
  ..groups
    .map(group => (src(group, [*#group.label*]), src(group, group.items.join(", "))))
    .flatten(),
)

#let certification(item) = block(below: 0.5em)[
  #split-row([*#item.name*, #item.issuer], meta(fmt-date(item.date)))
]

#src("basics", [
  #text(size: 21pt, weight: "semibold", fill: teal, cv.basics.name)
  #if cv.basics.headline.trim() != "" {
    v(-0.5em)
    text(size: 11pt, cv.basics.headline)
  }
  #v(-0.3em)
  #meta(join-items(contact-items(cv.basics), [#h(0.4em)·#h(0.4em)]))
])

#if cv.summary.len() > 0 {
  src("summary", block(above: 0.9em, rich(cv.summary)))
}

#sections(
  cv,
  section-heading: section-heading,
  experience: experience,
  project: project,
  education: education,
  skills: skills,
  certification: certification,
)
"""

# Terms the fake job analysis looks for; enough to make keyword gaps visible in tests.
KNOWN_TERMS = [
    "Python",
    "SQL",
    "Spark",
    "Kafka",
    "Airflow",
    "dbt",
    "AWS",
    "Snowflake",
    "Kubernetes",
]


def default_responders(sample_profile: CvContent) -> dict[str, Responder]:
    """Plausible, deterministic answers in the providers' wire shape: import returns the sample
    profile (the content of templates/fixtures/sample-cv.pdf), job analysis reads the ad's first
    lines and known terms, tailoring returns the profile it was given with every bullet traced
    to its source, an edit returns the CV it was given unchanged, each question gets an answer
    set in the first role that names a skill the profile does not (Databricks) and has a gap to
    fill, and a template request returns a small valid template."""

    def extract(_: LLMRequest[Any]) -> BaseModel:
        return WireImportedCv(content=to_wire(sample_profile), profile_name="Data engineering")

    def analyze(request: LLMRequest[Any]) -> BaseModel:
        description = request.user_text.split("<job_description>", 1)[-1]
        lines = [line.strip() for line in description.splitlines() if line.strip()]
        terms = [term for term in KNOWN_TERMS if term.casefold() in description.casefold()]
        return JobAnalysis(
            title=lines[0] if lines else "",
            company=lines[1] if len(lines) > 1 and "</job_description>" not in lines[1] else "",
            seniority="senior" if "senior" in description.casefold() else "",
            must_have=terms[:3],
            nice_to_have=terms[3:],
            keywords=terms,
            summary="A role building data pipelines.",
        )

    def tailor(request: LLMRequest[Any]) -> BaseModel:
        profile = tailor_prompt.profile_from(request.user_text)
        for bullet in iter_bullets(profile):
            bullet.source_id = bullet.id
        return WireTailoredCv(content=to_wire(profile), changes=[])

    def edit(request: LLMRequest[Any]) -> BaseModel:
        cv = edit_prompt.cv_from(request.user_text)
        return WireCvEdit(reply="I made no change.", content=to_wire(cv))

    def answers(request: LLMRequest[Any]) -> BaseModel:
        profile = answers_prompt.profile_from(request.user_text)
        roles = [item for section in profile.sections for item in section.experience]
        drafts = []
        for question in answers_prompt.questions_from(request.user_text):
            if not roles:
                drafts.append(DraftAnswer(id=question.id, text="", skills=[]))
                continue
            role, tools = roles[0], roles[0].stack[:2]
            opening = "In my time at" if question.previous else "At"
            text = (
                f"{opening} {role.org} I worked as {role.role.lower()} with "
                f"{' and '.join(tools) or 'the team'}, and moved [[how many]] jobs to Databricks."
            )
            mention = SkillMention(skill="Databricks", based_on=tools)
            drafts.append(DraftAnswer(id=question.id, text=text, skills=[mention]))
        return DraftAnswers(answers=drafts)

    def template(request: LLMRequest[Any]) -> BaseModel:
        # The first call drafts; a repair or a refinement only returns the source.
        if request.output_model is GeneratedTemplate:
            return GeneratedTemplate(
                name="Teal rule",
                description="Sans serif type with teal section rules and a compact header.",
                paper="a4",
                target_pages=1,
                main_typ=FAKE_TEMPLATE,
            )
        return RevisedTemplate(main_typ=FAKE_TEMPLATE)

    return {
        "import": extract,
        "analyze_job": analyze,
        "tailor": tailor,
        "edit": edit,
        "answers": answers,
        "template": template,
    }
