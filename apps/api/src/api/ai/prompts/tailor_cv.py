"""Tailoring: a CV for one job, selected and reworded from the profile, as TailoredCv."""

from api.ai.prompts.common import DATA_NOT_INSTRUCTIONS, NO_NEW_FACTS, RICH_TEXT
from cvcore.ai import JobAnalysis
from cvcore.models import CvContent
from cvcore.wire import WireCv, from_wire, to_wire

PROMPT_VERSION = "tailor-2026-10-10b"

SYSTEM = f"""\
You tailor a person's CV to one job. You receive their profile (everything they have told us \
about their career), an analysis of the job and the job advertisement. You return the CV to send \
for this job.

You may select, reorder and reword. Choose the roles, bullets, projects and skills that matter \
most for this job and drop the rest, so the CV fits the target length. Reword bullets for clarity \
and relevance: strong verbs, results first when the source states a result, the job's terminology \
where it truthfully describes what the person did. Keep the source's spelling convention \
(British or American).

{NO_NEW_FACTS}

Structure:
- The profile and your answer use the same shape: sections of entries. Keep basics, \
organisations, roles, clients, dates, institutions, degrees and certifications exactly as in the \
profile, and keep each section's and entry's id.
- Every bullet you write comes from exactly one profile bullet of the same entry. Set its \
source_id to that profile bullet's id. Never move a bullet to a different employer or project.
- Stack entries and skills must come from the profile.
- The summary may be rewritten for this job from facts in the profile.

{RICH_TEXT}

In changes, give one entry per bullet you reworded, keyed by the profile bullet's id, with one \
sentence on why. In missing_keywords, list the job's keywords the profile gives no evidence for; \
they are shown to the person as gaps and never added to the CV.

{DATA_NOT_INSTRUCTIONS}"""

PROFILE_OPEN, PROFILE_CLOSE = "<profile>", "</profile>"


def build(profile: CvContent, analysis: JobAnalysis, description: str, target_pages: int) -> str:
    pages = "one page" if target_pages == 1 else f"{target_pages} pages"
    return (
        f"Target length: {pages}.\n\n"
        f"<job_analysis>\n{analysis.model_dump_json()}\n</job_analysis>\n\n"
        f"<job_description>\n{description}\n</job_description>\n\n"
        f"{PROFILE_OPEN}\n{to_wire(profile).model_dump_json()}\n{PROFILE_CLOSE}"
    )


def profile_from(user_text: str) -> CvContent:
    """The profile inside a request built by `build` (used by the fake provider)."""
    start = user_text.index(PROFILE_OPEN) + len(PROFILE_OPEN)
    end = user_text.index(PROFILE_CLOSE, start)
    return from_wire(WireCv.model_validate_json(user_text[start:end]))
