"""A deterministic provider for tests and local work without API keys."""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from api.ai.prompts import tailor_cv as tailor_prompt
from api.ports.llm.base import LLMRequest, LLMResult, ProviderName
from cvcore.ai import JobAnalysis
from cvcore.models import CvContent
from cvcore.render import iter_bullets
from cvcore.richtext import plain_text
from cvcore.wire import WireImportedCv, WireTailoredCv, to_wire

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
    lines and known terms, and tailoring returns the profile it was given with every bullet traced
    to its source."""

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
        text = " ".join(plain_text(b.text) for b in iter_bullets(profile)).casefold()
        skills = {item.casefold() for s in profile.sections for g in s.skills for item in g.items}
        missing = [
            term
            for term in KNOWN_TERMS
            if term.casefold() in request.user_text.casefold()
            and term.casefold() not in skills
            and term.casefold() not in text
        ]
        return WireTailoredCv(content=to_wire(profile), changes=[], missing_keywords=missing)

    return {"import": extract, "analyze_job": analyze, "tailor": tailor}
