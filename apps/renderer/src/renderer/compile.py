"""Compile a render request in a sandbox: checked inputs, a fresh temp root, a limited child."""

import asyncio
import json
import logging
import os
import posixpath
import re
import shutil
import signal
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from cvcore.rendering import Diagnostic, RenderError, RenderErrorCode, RenderRequest
from renderer.settings import Settings
from renderer.templates import LIB_DIR

logger = logging.getLogger("renderer")

_IMPORT = re.compile(r'\b(?:import|include)\s+"((?:[^"\\]|\\.)*)"')
_FILE_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.-]*)*$")
_TEMPLATE_ID = re.compile(r"^[a-z][a-z0-9-]*$")
_ALLOWED_SUFFIXES = (".typ", ".json")
# Any package download attempt goes to a closed local port and fails at once.
_BLACKHOLE_PROXY = "http://127.0.0.1:9"


class RenderFailure(Exception):
    def __init__(
        self, code: RenderErrorCode, message: str, diagnostics: list[Diagnostic] | None = None
    ) -> None:
        super().__init__(message)
        self.error = RenderError(
            code=code, diagnostics=diagnostics or [Diagnostic(message=message)]
        )


@dataclass(frozen=True)
class RenderOutput:
    page_count: int
    svg_pages: list[str]
    pdf: bytes | None


def check_limits(files: dict[str, str], settings: Settings) -> None:
    if len(files) > settings.max_files:
        raise RenderFailure("limit_exceeded", f"A CV can have at most {settings.max_files} files.")
    total = sum(len(source.encode()) for source in files.values())
    if total > settings.max_source_bytes:
        raise RenderFailure(
            "limit_exceeded",
            f"The CV source is larger than {settings.max_source_bytes // 1024} KB.",
        )
    data = files.get("data.json", "")
    if len(data.encode()) > settings.max_data_bytes:
        raise RenderFailure(
            "limit_exceeded", f"data.json is larger than {settings.max_data_bytes // 1024} KB."
        )
    for name in files:
        if (
            not _FILE_NAME.match(name)
            or ".." in name.split("/")
            or name.split("/")[0] == LIB_DIR
            or not name.endswith(_ALLOWED_SUFFIXES)
        ):
            raise RenderFailure(
                "forbidden_import",
                f"{name!r} is not an allowed file name. Use .typ or .json files in the project.",
            )


def check_imports(files: dict[str, str]) -> None:
    """Reject `#import`/`#include` of packages (`@...`) and of paths that leave the root."""
    for name, source in files.items():
        if not name.endswith(".typ"):
            continue
        for match in _IMPORT.finditer(source):
            path = match.group(1)
            line = source.count("\n", 0, match.start()) + 1
            column = match.start() - (source.rfind("\n", 0, match.start()) + 1) + 1
            if path.startswith("@"):
                message = f"Packages cannot be imported ({path}). Copy the code into the project."
            elif _escapes_root(name, path):
                message = f"Imports must stay inside the project ({path})."
            else:
                continue
            diagnostic = Diagnostic(message=message, file=name, line=line, column=column)
            raise RenderFailure("forbidden_import", message, [diagnostic])


def _escapes_root(importer: str, path: str) -> bool:
    if path.startswith("/"):
        target = posixpath.normpath(path.lstrip("/"))
    else:
        target = posixpath.normpath(posixpath.join(posixpath.dirname(importer), path))
    return target == ".." or target.startswith("../")


def template_main(template_id: str, settings: Settings) -> str:
    path = settings.templates_dir / template_id / "main.typ"
    if not _TEMPLATE_ID.match(template_id) or not path.is_file():
        raise RenderFailure("compile_error", f"There is no template called {template_id!r}.")
    return path.read_text()


async def render(request: RenderRequest, settings: Settings) -> RenderOutput:
    check_limits(request.files, settings)
    check_imports(request.files)
    sources = dict(request.files)
    if request.template_id is not None:
        sources["main.typ"] = template_main(request.template_id, settings)

    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="render-") as tmp:
            output = await _compile_in_child(Path(tmp), sources, request, settings)
    except RenderFailure as failure:
        logger.info(
            "render failed",
            extra={"template_id": request.template_id, "code": failure.error.code},
        )
        raise
    logger.info(
        "render ok",
        extra={
            "template_id": request.template_id,
            "format": request.format,
            "page_count": output.page_count,
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    )
    return output


async def _compile_in_child(
    tmp: Path, sources: dict[str, str], request: RenderRequest, settings: Settings
) -> RenderOutput:
    root, out_dir = tmp / "root", tmp / "out"
    for directory in (root, out_dir, tmp / "packages"):
        directory.mkdir()
    for name, source in sources.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)
    shutil.copytree(settings.templates_dir / LIB_DIR, root / LIB_DIR)

    args = [str(root), str(out_dir), request.format, request.paper, str(settings.fonts_dir)]
    args += [str(settings.cpu_seconds), str(settings.memory_bytes), str(settings.max_pages)]
    # Few malloc arenas keep reserved address space well under RLIMIT_AS on many-core hosts.
    env = {"PATH": os.defpath, "HOME": str(tmp), "NO_PROXY": "", "MALLOC_ARENA_MAX": "2"}
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        env[key] = env[key.lower()] = _BLACKHOLE_PROXY

    # -I: no environment-driven imports, and the project root is not on sys.path.
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-m",
        "renderer.worker",
        *args,
        cwd=root,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=settings.wall_seconds)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise _timeout(settings) from None

    if process.returncode in (-signal.SIGXCPU, -signal.SIGKILL):
        raise _timeout(settings)
    try:
        result = json.loads(stdout.decode().strip().splitlines()[-1])
    except (IndexError, ValueError):
        if process.returncode in (-signal.SIGABRT, -signal.SIGSEGV):
            raise RenderFailure(
                "limit_exceeded", "The CV needed more memory than allowed."
            ) from None
        raise RenderFailure("compile_error", "The renderer stopped unexpectedly.") from None

    if not result["ok"]:
        diagnostics = [Diagnostic.model_validate(d) for d in result["diagnostics"]]
        raise RenderFailure(result["code"], diagnostics[0].message, diagnostics)

    if request.format == "pdf":
        pdf = (out_dir / "document.pdf").read_bytes()
        if len(pdf) > settings.max_pdf_bytes:
            raise RenderFailure(
                "limit_exceeded",
                f"The PDF is larger than {settings.max_pdf_bytes // (1024 * 1024)} MB.",
            )
        return RenderOutput(page_count=result["page_count"], svg_pages=[], pdf=pdf)
    pages = [
        (out_dir / f"page-{number}.svg").read_text()
        for number in range(1, result["page_count"] + 1)
    ]
    return RenderOutput(page_count=len(pages), svg_pages=pages, pdf=None)


def _timeout(settings: Settings) -> RenderFailure:
    return RenderFailure(
        "timeout",
        f"Rendering took longer than {settings.cpu_seconds} seconds and was stopped. "
        "Check for loops that never end.",
    )
