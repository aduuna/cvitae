# Chameleon vitae

[![CI](https://github.com/aduuna/cvitae/actions/workflows/ci.yml/badge.svg)](https://github.com/aduuna/cvitae/actions/workflows/ci.yml)

Paste a job description, get a CV tailored to it, typeset properly, without the AI inventing anything.

Chameleon vitae turns a person's career history into job-specific CVs. Users import an existing CV
or enter their experience, paste a job description, and get a tailored CV rendered with Typst. AI runs
on Claude or Gemini, chosen by the user, and may only select, reorder and reword facts the user gave.

**Status:** milestone M0 (foundations) is done: the workspace, design system, UI primitives and app
shell. Nothing user-facing works yet beyond navigation. See [docs/ROADMAP.md](docs/ROADMAP.md).

## Stack

| Part | Technology |
|---|---|
| Frontend (`apps/web`) | SvelteKit 3 SPA (Svelte 5), Tailwind CSS v4, bun |
| API (`apps/api`) | Python 3.13, FastAPI, Pydantic v2, uv |
| Renderer (`apps/renderer`) | FastAPI service that compiles Typst in a sandbox |
| Shared (`packages/cvcore`) | CV models, rich-text parser, fact guard |
| Data and infra | Neon Postgres, Google Cloud Storage, Cloud Run, OpenTofu |

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (installs Python 3.13 for you)
- [bun](https://bun.sh/) 1.3 or later
- Docker, for the local Postgres (needed from M1)
- [OpenTofu](https://opentofu.org/), only for infrastructure work

Use bun and uv only. Do not use npm, npx, pnpm, yarn, pip or poetry.

## Setup

```sh
git clone https://github.com/aduuna/cvitae.git
cd cvitae
uv sync                                  # Python workspace into .venv
cd apps/web
bun install
bunx playwright install chromium         # once, for the end-to-end tests
```

## Run locally

Each command runs in its own terminal, from the repository root unless noted.

```sh
uv run --package api fastapi dev apps/api/src/api/main.py                        # api on :8000
uv run --package renderer fastapi dev apps/renderer/src/renderer/main.py --port 8001
cd apps/web && bun run dev                                                       # app on :5173
docker compose up -d db                                                          # Postgres (from M1)
```

Open http://localhost:5173. The Vite dev server proxies `/api` to the api on port 8000.

## Checks

These are the same checks CI runs (`.github/workflows/ci.yml`).

```sh
# Python, from the repository root
uv run ruff check . && uv run ruff format --check .
uv run ty check
uv run pytest --cov

# Web, from apps/web
bun run check          # svelte-check
bun run lint           # prettier and eslint
bun run test           # vitest, including the design token test
bun run test:e2e       # Playwright, builds and serves the app
```

## Repository layout

```
apps/
  web/            SvelteKit SPA
  api/            REST API; serves the built SPA in production
  renderer/       sandboxed Typst compile service
packages/
  cvcore/         code shared by api and renderer
docs/             product, design, backend, infrastructure and roadmap specs
compose.yaml      local Postgres
```

`templates/` and `infra/` arrive in later milestones.

## Documentation

The docs are the source of truth. If code and docs disagree, ask before changing either.

| File | Covers |
|---|---|
| [AGENTS.md](AGENTS.md) | Working rules, commands and the definition of done. Read it before contributing. |
| [docs/PRODUCT.md](docs/PRODUCT.md) | Features, navigation, user flows, plans |
| [docs/DESIGN.md](docs/DESIGN.md) | Design language, tokens, components, copy rules |
| [docs/BACKEND.md](docs/BACKEND.md) | Architecture, data model, API, AI pipeline, renderer |
| [docs/INFRA.md](docs/INFRA.md) | GCP, OpenTofu, containers, CI/CD |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Milestones in build order |
