"""Custom templates: a Typst template in the design of a CV the user uploads (docs/BACKEND.md,
Custom templates).

One generation is one AI run however many model calls it takes. A model drafts the template from
the PDF; deterministic checks (cvcore.user_templates) and a test render decide whether it is
good; a failing draft goes back for up to two repairs; a passing one gets one visual refinement
pass against the original. The result is saved as a `draft` the user confirms. A refused or failed
generation saves nothing: the only row it writes is the `ai_runs` record.
"""

import asyncio
import contextlib
import functools
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path

from api.ai import tasks
from api.ai.prompts import template as prompt
from api.billing.plans import Plan
from api.db.models import Document, User, UserTemplate
from api.errors import (
    AppError,
    NotFound,
    ProviderError,
    ProviderTimeout,
    RenderFailed,
    ServiceUnavailable,
    TemplateFailed,
    ValidationFailed,
)
from api.ports.llm.pages import pdf_text, pdf_to_pngs
from api.ports.renderer import RendererClient
from api.ports.storage import Storage
from api.repositories.ai_runs import AiRunRepository
from api.repositories.documents import DocumentRepository
from api.repositories.uploads import UploadRepository
from api.repositories.user_templates import UserTemplateRepository
from api.repositories.users import UserRepository
from api.services.ai_models import ModelChoice
from api.services.quotas import require_ai_runs, require_room
from api.services.templates import CUSTOM_PAPER_SIZES, DEFAULT_TEMPLATE_ID, TemplateCatalog
from api.services.uploads import MAX_UPLOAD_BYTES, PDF, detect_mime_type, get_upload, store_upload
from cvcore.models import CvContent
from cvcore.render import to_render_json
from cvcore.rendering import Paper
from cvcore.user_templates import (
    Reference,
    TemplateIssue,
    check_pages,
    check_render,
    check_template,
    mentions_owner,
    new_template_id,
    reference_from_text,
)

logger = logging.getLogger(__name__)

MAX_REPAIRS = 2
"""Corrections asked for when a draft fails a check or does not compile."""

TIME_BUDGET_SECONDS = 120.0
"""No further model call starts after this long. A call can take 90 seconds and the request has
Cloud Run's 300, so a repair or refinement is skipped rather than risk the request."""

NAME_MAX, DESCRIPTION_MAX = 60, 200
DEFAULT_NAME = "Custom template"

PROVIDER_PROBLEM = (
    "Claude could not finish this template. Wait a minute and try again, or try a PDF with a "
    "simpler layout."
)
"""A template always runs on Claude, so a failed or slow call cannot offer another model."""


@contextlib.asynccontextmanager
async def _template_wording() -> AsyncGenerator[None]:
    """Rewords a failed or slow Claude call for a template; the code and details stay."""
    try:
        yield
    except (ProviderError, ProviderTimeout) as exc:
        raise type(exc)(PROVIDER_PROBLEM, exc.details) from exc


# A failed check that makes a test render pointless: the source is not allowed to run at all.
_BLOCKS_RENDER = frozenset(
    {"too_large", "forbidden_import", "forbidden_call", "missing_import", "missing_data"}
)


@dataclass(frozen=True)
class Kit:
    """What drafting reads from the repository's templates directory."""

    library: prompt.Library
    profiles: tuple[CvContent, ...]
    """Data every draft is test-rendered with: a full CV, then one with most fields empty."""


@functools.cache
def load_kit(templates_dir: Path) -> Kit:
    fixtures = templates_dir / "fixtures"
    return Kit(
        library=prompt.Library(
            helpers=(templates_dir / "_lib" / "cv.typ").read_text(),
            example=(templates_dir / "classic" / "main.typ").read_text(),
        ),
        profiles=tuple(
            CvContent.model_validate_json((fixtures / f"{name}.json").read_text())
            for name in ("profile-sample", "profile-edge")
        ),
    )


@dataclass(frozen=True)
class Generated:
    template: UserTemplate
    choice: ModelChoice
    model: str
    """The model id that answered last."""


@dataclass(frozen=True)
class _Verdict:
    problems: list[TemplateIssue]
    pdf: bytes | None
    """The sample CV rendered with the template, when it compiled."""


async def _verify(
    renderer: RendererClient,
    kit: Kit,
    reference: Reference,
    slug: str,
    source: str,
    paper: Paper,
    target_pages: int,
) -> _Verdict:
    """Static checks, then a test render with each of the kit's CVs: it compiles, shows all the
    data and fits the page target. Problems are worded for the model that repairs them."""
    problems = check_template(source, reference)
    if any(issue.code in _BLOCKS_RENDER for issue in problems):
        return _Verdict(problems, None)
    sample_pdf: bytes | None = None
    for index, profile in enumerate(kit.profiles):
        try:
            pdf = await renderer.render_pdf(slug, to_render_json(profile), paper, source=source)
        except RenderFailed as exc:
            for diagnostic in exc.details.get("diagnostics") or [{"message": exc.message}]:
                line = diagnostic.get("line")
                where = f" at line {line}" if line else ""
                message = f"Typst could not compile the template{where}: {diagnostic['message']}"
                problems.append(TemplateIssue("compile_error", message))
            return _Verdict(problems, None)
        text, pages = await asyncio.to_thread(pdf_text, pdf)
        found = check_render(text, profile)
        if index == 0:
            sample_pdf = pdf
            found += check_pages(pages, target_pages)
        said = {issue.message for issue in problems}
        problems += [issue for issue in found if issue.message not in said]
    return _Verdict(problems, sample_pdf)


def _label(text: str, reference: Reference, limit: int, default: str) -> str:
    """A name or description the model gave, trimmed; the default when it names the owner."""
    text = " ".join(text.split())[:limit].strip()
    return default if not text or mentions_owner(text, reference) else text


async def _pdf_of(
    uploads: UploadRepository,
    storage: Storage,
    file: tuple[str, bytes] | None,
    upload_id: uuid.UUID | None,
) -> bytes:
    """The PDF to copy: the file just sent, or an earlier upload. A DOCX is refused, since its
    look cannot be read from its text."""
    if (file is None) == (upload_id is None):
        raise ValidationFailed("Upload a PDF, or choose an earlier upload.")
    if file is not None:
        data = file[1]
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValidationFailed("This file is larger than 10 MB. Upload a smaller file.")
        mime_type = detect_mime_type(data)
    else:
        assert upload_id is not None  # noqa: S101 - exactly one is given, checked above
        upload = await get_upload(uploads, upload_id)
        mime_type = upload.mime_type
        data = await storage.get(upload.storage_key)
    if mime_type is None:
        raise ValidationFailed("This file is not a PDF. Upload a PDF file.")
    if mime_type != PDF:
        raise ValidationFailed(
            "A template copies how a CV looks, which a DOCX does not keep. Save it as a PDF and "
            "upload that."
        )
    return data


async def generate_template(
    choice: ModelChoice,
    runs: AiRunRepository,
    uploads: UploadRepository,
    storage: Storage,
    templates: UserTemplateRepository,
    renderer: RendererClient,
    *,
    plan: Plan,
    kit: Kit,
    file: tuple[str, bytes] | None = None,
    upload_id: uuid.UUID | None = None,
) -> Generated:
    """Draft a template from a PDF (`file`: its name and bytes, or the `upload_id` of an earlier
    one) and save it as a draft, replacing the user's earlier unconfirmed one. Takes one AI run;
    the plan's room for another template and for the run are checked before any model call."""
    pdf = await _pdf_of(uploads, storage, file, upload_id)
    text, _ = await asyncio.to_thread(pdf_text, pdf)
    reference = reference_from_text(text)
    await require_room("templates", plan, templates)
    await require_ai_runs(runs, plan)

    slug = new_template_id()
    started = time.monotonic()

    def in_time() -> bool:
        return time.monotonic() - started < TIME_BUDGET_SECONDS

    async with _template_wording(), tasks.combined_run(runs) as run:
        drafted = await tasks.draft_template(choice, run, pdf=pdf, library=kit.library)
        meta = drafted.output
        source, model = meta.main_typ, drafted.model
        target_pages = min(max(meta.target_pages, 1), 2)

        async def verify(candidate: str) -> _Verdict:
            return await _verify(
                renderer, kit, reference, slug, candidate, meta.paper, target_pages
            )

        verdict = await verify(source)
        repairs = 0
        while verdict.problems:
            if repairs >= MAX_REPAIRS or not in_time():
                issues = sorted({issue.code for issue in verdict.problems})
                logger.warning(
                    "template failed",
                    extra={
                        "user_id": str(runs.user_id),
                        "template_id": slug,
                        "repairs": repairs,
                        "issues": issues,
                    },
                )
                raise TemplateFailed(
                    "We could not turn this CV into a template that renders correctly. Try a "
                    "PDF with a simpler layout, or a different CV.",
                    {"issues": issues},
                )
            revised = await tasks.repair_template(
                choice,
                run,
                source=source,
                problems=[str(issue) for issue in verdict.problems],
                library=kit.library,
            )
            repairs += 1
            source, model = revised.output.main_typ, revised.model
            verdict = await verify(source)

        refined = False
        if in_time() and verdict.pdf is not None:
            try:
                [page] = await asyncio.to_thread(pdf_to_pngs, verdict.pdf, 1)
                revised = await tasks.refine_template(
                    choice, run, pdf=pdf, page=page, source=source, library=kit.library
                )
                candidate = revised.output.main_typ
                # Kept only when it passes everything the first version did.
                if candidate.strip() != source.strip() and not (await verify(candidate)).problems:
                    source, model, refined = candidate, revised.model, True
            except (ProviderError, ProviderTimeout, ServiceUnavailable):
                # The draft already passed: a refinement that cannot run is not worth losing it.
                logger.info("template refinement skipped", extra={"template_id": slug})

        stored = await store_upload(uploads, storage, *file) if file is not None else None
        await templates.delete_drafts()
        row = await templates.create(
            slug=slug,
            name=_label(meta.name, reference, NAME_MAX, DEFAULT_NAME),
            description=_label(meta.description, reference, DESCRIPTION_MAX, ""),
            main_typ=source,
            paper_sizes=list(CUSTOM_PAPER_SIZES),
            target_pages=target_pages,
            status="draft",
            upload_id=stored.id if stored is not None else upload_id,
            prompt_version=prompt.PROMPT_VERSION,
        )
        logger.info(
            "template generated",
            extra={
                "user_id": str(runs.user_id),
                "template_id": slug,
                "calls": run.calls,
                "repairs": repairs,
                "refined": refined,
                "duration_ms": int((time.monotonic() - started) * 1000),
            },
        )
    return Generated(template=row, choice=choice, model=model)


async def get_custom(templates: UserTemplateRepository, slug: str) -> UserTemplate:
    """One of the user's own templates, draft or ready."""
    row = await templates.get_by_slug(slug)
    if row is None:
        raise NotFound("This template does not exist or was deleted.")
    return row


async def update_custom(
    templates: UserTemplateRepository,
    slug: str,
    *,
    plan: Plan,
    name: str | None = None,
    description: str | None = None,
    confirm: bool = False,
) -> UserTemplate:
    """Rename or describe a template. `confirm` makes a draft usable, which needs room under the
    plan's limit; it changes nothing on a template that is ready."""
    row = await get_custom(templates, slug)
    values: dict[str, object] = {}
    if name is not None:
        values["name"] = name.strip()
    if description is not None:
        values["description"] = description.strip()
    if confirm and row.status != "ready":
        await require_room("templates", plan, templates)
        values["status"] = "ready"
    return await templates.update(row, **values)


async def delete_custom(
    templates: UserTemplateRepository,
    documents: DocumentRepository,
    users: UserRepository,
    catalog: TemplateCatalog,
    user: User,
    slug: str,
) -> None:
    """Delete a template. The user's CVs that use it switch to their default template, or to
    Classic when the default was this one; the default itself resets to Classic."""
    row = await get_custom(templates, slug)
    fallback = DEFAULT_TEMPLATE_ID
    default = user.default_template_id
    if default and default != slug:
        try:
            fallback = (await catalog.require(default)).id
        except AppError:
            fallback = DEFAULT_TEMPLATE_ID
    await documents.update_where(
        Document.template_id == slug, template_id=fallback, page_count=None
    )
    if default == slug:
        await users.update(user, default_template_id=DEFAULT_TEMPLATE_ID)
    await templates.delete(row.id)
    logger.info("template deleted", extra={"user_id": str(user.id), "template_id": slug})
