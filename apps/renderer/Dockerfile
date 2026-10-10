# Build from the repository root: docker build -f apps/renderer/Dockerfile .

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS py
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /srv
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps/renderer ./apps/renderer
COPY apps/api/pyproject.toml ./apps/api/pyproject.toml
RUN uv sync --frozen --no-dev --package renderer --no-editable

FROM python:3.13-slim-bookworm
RUN useradd --create-home app
WORKDIR /srv
COPY --from=py /srv/.venv /srv/.venv
COPY templates /templates
COPY apps/renderer/fonts /fonts
ENV PATH="/srv/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    TEMPLATES_DIR=/templates \
    FONTS_DIR=/fonts
USER app
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "renderer.main:app", "--host", "0.0.0.0", "--port", "8080"]
