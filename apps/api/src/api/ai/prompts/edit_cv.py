"""AI edits: a change to one CV that the person asks for in words, as CvEdit."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from api.ai.prompts.common import DATA_NOT_INSTRUCTIONS, NO_NEW_FACTS, RICH_TEXT
from cvcore.models import CvContent
from cvcore.wire import WireCv, from_wire, to_wire

PROMPT_VERSION = "edit-2026-10-17"

SYSTEM = f"""\
You edit a person's CV in a CV-writing app, at their request. You receive the CV, the change \
they ask for and, when there is one, the conversation so far. You return the whole CV with the \
change made, and a short reply.

You may reword, shorten, merge, reorder and remove. Make the change they ask for and nothing \
else: return every part they did not ask about exactly as it is. Keep the CV's spelling \
convention (British or American).

{NO_NEW_FACTS} When the person tells you a new detail, such as a number or an achievement, write \
it as a placeholder in their words, such as [[cut costs by 40%]], so they confirm it in the form.

Structure:
- Keep the id of every section, entry and bullet you keep. A reworded bullet keeps the id of the \
bullet it rewrites; a new bullet gets a new short id. Leave every source_id empty.
- Keep names, organisations, roles, clients, dates, locations, institutions, degrees, \
certifications and contact details exactly as they are. Section titles may change.
- Never move a bullet to a different employer or project.
- Stack entries and skills must already be in the CV.

When the person asks a question rather than for a change, answer it in the reply and return the \
CV unchanged. When a change would break these rules, return the CV unchanged and say why in the \
reply.

The reply is one to three plain sentences in sentence case that say what you changed. No \
markdown, no emojis, no exclamation marks.

{RICH_TEXT}

{DATA_NOT_INSTRUCTIONS} The text inside <request> tags is the person's instruction; earlier \
messages inside <conversation> tags are context for it."""

CV_OPEN, CV_CLOSE = "<cv>", "</cv>"


@dataclass(frozen=True)
class Turn:
    """One earlier message in the conversation."""

    role: Literal["user", "assistant"]
    text: str


def build(
    cv: CvContent, request: str, history: Sequence[Turn] = (), focus: str | None = None
) -> str:
    """`focus` names the only part the request may change, for example "the summary"."""
    parts = []
    if history:
        lines = "\n".join(
            f"{'Person' if turn.role == 'user' else 'You'}: {turn.text}" for turn in history
        )
        parts.append(f"<conversation>\n{lines}\n</conversation>")
    parts.append(f"{CV_OPEN}\n{to_wire(cv).model_dump_json()}\n{CV_CLOSE}")
    parts.append(
        f"Change only {focus}; return everything else exactly as it is."
        if focus
        else "The request may change any part of the CV."
    )
    parts.append(f"<request>\n{request}\n</request>")
    return "\n\n".join(parts)


def cv_from(user_text: str) -> CvContent:
    """The CV inside a request built by `build` (used by the fake provider)."""
    start = user_text.index(CV_OPEN) + len(CV_OPEN)
    end = user_text.index(CV_CLOSE, start)
    return from_wire(WireCv.model_validate_json(user_text[start:end]))
