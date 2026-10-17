"""Child process entry: compiles one Typst project under resource limits.

python -I -m renderer.worker ROOT OUT_DIR svg|pdf PAPER FONTS_DIR CPU_S MEMORY_B MAX_PAGES

Runs with the project root as its working directory. Writes page-<n>.svg files or document.pdf to
out_dir and prints one JSON line: {"ok": true, "page_count": n} or
{"ok": false, "code": "...", "diagnostics": [...]}.
"""

import json
import re
import resource
import sys
from pathlib import Path
from typing import Any

_ERROR = re.compile(
    r"error: (?P<message>.+)\n(?:\s*┌─ (?P<file>.+?):(?P<line>\d+):(?P<column>\d+))?"
)


def apply_limits(cpu_seconds: int, memory_bytes: int) -> None:
    """Called before any user content is touched."""
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
    # macOS does not enforce RLIMIT_AS, so the memory limit only applies on Linux (Cloud Run).
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))


def parse_diagnostics(diagnostic: str, fallback: str) -> list[dict[str, Any]]:
    """Typst's rendered diagnostic ("error: ...\\n  ┌─ main.typ:3:4") as structured entries."""
    found = [
        {
            "message": match["message"],
            "file": match["file"],
            "line": int(match["line"]) if match["line"] else None,
            "column": int(match["column"]) if match["column"] else None,
        }
        for match in _ERROR.finditer(diagnostic)
    ]
    return found or [{"message": fallback}]


def compile_project(
    root: Path,
    out_dir: Path,
    fmt: str,
    paper: str,
    fonts_dir: Path,
    max_pages: int,
    source_links: bool = False,
) -> dict[str, Any]:
    import typst  # imported after the limits are in place

    compiler = typst.Compiler(
        root=str(root),
        font_paths=typst.Fonts(
            include_system_fonts=False, include_embedded_fonts=False, font_paths=[str(fonts_dir)]
        ),
        sys_inputs={"paper": paper, "source-links": "true" if source_links else "false"},
        # Empty, so no package can load; downloads are also blocked by the proxy settings.
        package_path=str(root.parent / "packages"),
        package_cache_path=str(root.parent / "packages"),
    )
    try:
        svg = compiler.compile(input="main.typ", format="svg")
        pages = svg if isinstance(svg, list) else [svg]
        if len(pages) > max_pages:
            return _failure(
                "limit_exceeded", f"The CV has {len(pages)} pages; the limit is {max_pages}."
            )
        if fmt == "pdf":
            pdf = compiler.compile(input="main.typ", format="pdf")
            assert isinstance(pdf, bytes)  # noqa: S101 - PDF is always one file
            (out_dir / "document.pdf").write_bytes(pdf)
        else:
            for number, page in enumerate(pages, start=1):
                assert isinstance(page, bytes)  # noqa: S101 - SVG pages are bytes
                (out_dir / f"page-{number}.svg").write_bytes(page)
    except typst.TypstError as error:
        return {
            "ok": False,
            "code": "compile_error",
            "diagnostics": parse_diagnostics(error.diagnostic, error.message),
        }
    return {"ok": True, "page_count": len(pages)}


def _failure(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "code": code, "diagnostics": [{"message": message}]}


def main(argv: list[str]) -> None:
    root, out_dir, fmt, paper, fonts_dir, cpu, memory, max_pages, links = argv[1:10]
    apply_limits(int(cpu), int(memory))
    try:
        result = compile_project(
            Path(root),
            Path(out_dir),
            fmt,
            paper,
            Path(fonts_dir),
            int(max_pages),
            source_links=links == "true",
        )
    except MemoryError:
        result = _failure("limit_exceeded", "The CV needed more memory than allowed.")
    sys.stdout.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main(sys.argv)
