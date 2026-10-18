"""AI edits: a change to one CV asked for in words, checked by the fact guard against that CV.

Nothing is saved: the editor puts the edited content into its form, and autosave saves it from
there, so the change can be undone like any other. The content before the edit is kept as an
autosave version first, so it can also be restored from version history later.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from api.ai import tasks
from api.ai.prompts.edit_cv import Turn
from api.billing.plans import Plan
from api.errors import Conflict, ValidationFailed
from api.repositories.ai_runs import AiRunRepository
from api.repositories.documents import DocumentRepository, DocumentVersionRepository
from api.services.ai_models import ModelChoice
from api.services.documents import get_document
from api.services.quotas import require_ai_runs
from cvcore import factguard
from cvcore.models import CvContent
from cvcore.render import iter_bullets
from cvcore.wire import from_wire, to_wire

SUMMARY = "summary"
"""The scope for the summary alone; any other scope is a section id."""


@dataclass(frozen=True)
class AiEditResult:
    reply: str
    content: CvContent
    """The whole CV after the edit, or as it was when nothing changed."""
    changed: bool
    issues: list[factguard.FactIssue]
    """What the fact guard corrected."""
    choice: ModelChoice
    model: str
    """The model id that answered."""


def _unlinked(content: CvContent) -> CvContent:
    copy = content.model_copy(deep=True)
    for bullet in iter_bullets(copy):
        bullet.source_id = None
    return copy


def _plain(content: CvContent) -> CvContent:
    """The CV as the model reads it: through the wire shape, so an unchanged answer compares
    equal, and without links to profile bullets, so the guard traces bullets to this CV's own."""
    return _unlinked(from_wire(to_wire(content)))


def _focus(content: CvContent, scope: str | None) -> str | None:
    """The part of the CV the request may change, in words for the model."""
    if scope is None:
        return None
    if scope == SUMMARY:
        return "the summary"
    section = next((section for section in content.sections if section.id == scope), None)
    if section is None:
        raise ValidationFailed(
            "That section is no longer in this CV. Choose another part to change.",
            {"field": "scope"},
        )
    return f'the section titled "{section.title}" (id {section.id})'


def _within(scope: str | None, current: CvContent, edited: CvContent) -> CvContent:
    """`edited`, with everything outside `scope` as it is in `current`. A section left out of the
    answer was removed; one whose kind changed is kept as it was."""
    if scope is None:
        return edited
    merged = current.model_copy(deep=True)
    if scope == SUMMARY:
        merged.summary = edited.summary
        return merged
    kind = next(section.kind for section in merged.sections if section.id == scope)
    replacement = next((section for section in edited.sections if section.id == scope), None)
    if replacement is None:
        merged.sections = [section for section in merged.sections if section.id != scope]
    elif replacement.kind == kind:
        merged.sections = [
            replacement if section.id == scope else section for section in merged.sections
        ]
    return merged


def _traced(edited: CvContent, source: CvContent) -> CvContent:
    """A bullet that kept its id comes from the bullet of the CV with that id; the model is told to
    keep ids and leave source_id empty. The guard checks it against that bullet, and any other
    bullet as one it cannot trace by source_id."""
    ids = {bullet.id for bullet in iter_bullets(source)}
    for bullet in iter_bullets(edited):
        if bullet.source_id not in ids and bullet.id in ids:
            bullet.source_id = bullet.id
    return edited


def _relinked(content: CvContent, current: CvContent) -> CvContent:
    """Bullets point at the profile bullets they came from again. The guard set each source_id
    to the bullet of this CV it traced the bullet to."""
    links = {bullet.id: bullet.source_id for bullet in iter_bullets(current)}
    for bullet in iter_bullets(content):
        bullet.source_id = links.get(bullet.source_id) if bullet.source_id else None
    return content


async def edit_document(
    choice: ModelChoice,
    runs: AiRunRepository,
    documents: DocumentRepository,
    versions: DocumentVersionRepository,
    document_id: uuid.UUID,
    *,
    message: str,
    history: Sequence[Turn] = (),
    scope: str | None = None,
    plan: Plan,
) -> AiEditResult:
    """Ask the model for the change in `message`, limited to `scope` (None for the whole CV,
    "summary", or a section id). Takes one AI run."""
    document = await get_document(documents, document_id)
    if document.mode == "ejected":
        raise Conflict("This CV is edited as Typst, so AI edits do not apply to it.")
    current = CvContent.model_validate(document.content)
    focus = _focus(current, scope)
    await require_ai_runs(runs, plan)

    source = _plain(current)
    result = await tasks.edit_cv(
        choice, runs, cv=source, request=message, history=history, focus=focus
    )
    edited = _traced(_within(scope, source, result.output.content), source)
    report = factguard.check(source, edited, where="your CV")
    changed = _unlinked(report.content) != source
    if changed:
        latest = await versions.latest(document.id)
        if latest is None or latest.content != document.content:
            await versions.create(
                document_id=document.id, reason="autosave", content=dict(document.content)
            )
    return AiEditResult(
        reply=result.output.reply,
        content=_relinked(report.content, current) if changed else current,
        changed=changed,
        issues=report.issues,
        choice=choice,
        model=result.model,
    )
