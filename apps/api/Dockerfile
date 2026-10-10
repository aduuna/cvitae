# Build from the repository root: docker build -f apps/api/Dockerfile .

# 1. Build the SPA with bun. Vite runs under Node, as in CI: SvelteKit's build does not finish
# under the Bun runtime that the oven/bun image would use.
FROM oven/bun:1.3.9 AS bun
FROM node:24-bookworm-slim AS web
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
WORKDIR /src/apps/web
COPY apps/web/package.json apps/web/bun.lock ./
RUN bun install --frozen-lockfile
COPY apps/web ./
RUN bun run build

# 2. Build the Python environment with uv (same /srv path as runtime so the venv is not relocated)
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS py
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /srv
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps/api ./apps/api
COPY apps/renderer/pyproject.toml ./apps/renderer/pyproject.toml
RUN uv sync --frozen --no-dev --package api --no-editable

# 3. Runtime (same base Python as the uv image)
FROM python:3.13-slim-bookworm
RUN useradd --create-home app
WORKDIR /srv
COPY --from=py /srv/.venv /srv/.venv
COPY --from=py /srv/apps/api/alembic.ini /srv/apps/api/alembic.ini
COPY --from=web /src/apps/web/build /srv/static
COPY templates/fixtures/profile-sample.json /srv/sample-profile.json
ENV PATH="/srv/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    STATIC_DIR=/srv/static \
    SAMPLE_PROFILE_PATH=/srv/sample-profile.json
USER app
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
