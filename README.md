# Chameleon vitae

[![CI](https://github.com/aduuna/cvitae/actions/workflows/ci.yml/badge.svg)](https://github.com/aduuna/cvitae/actions/workflows/ci.yml)

Paste a job description, get a CV tailored to it, typeset properly, without the AI inventing anything.

Chameleon vitae turns a person's career history into job-specific CVs. Users import an existing CV
or enter their experience, paste a job description, and get a tailored CV rendered with Typst. AI runs
on Claude or Gemini, chosen by the user, and may only select, reorder and reword facts the user gave.

**Status:** milestone M1 (profiles, CVs and rendering) is done. With dev sign-in, you can build
profiles by hand, make CVs from them, edit with a live Typst preview, switch between the `classic`
and `compact` templates, keep versions and export PDFs. AI, Firebase sign-in and deployment come
next. See [docs/ROADMAP.md](docs/ROADMAP.md).

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
- Docker, for the local Postgres
- [OpenTofu](https://opentofu.org/), only for infrastructure work

Use bun and uv only. Do not use npm, npx, pnpm, yarn, pip or poetry.

## Setup

```sh
git clone https://github.com/aduuna/cvitae.git
cd cvitae
uv sync                                  # Python workspace into .venv
cp .env.example .env                     # local settings (git-ignored)
docker compose up -d db                  # Postgres on :5432
cd apps/api && uv run --package api alembic upgrade head && cd ../..
cd apps/web
bun install
bunx playwright install chromium         # once, for the end-to-end tests
```

Until Firebase sign-in arrives (M2), the api runs with `AUTH_MODE=dev` and trusts an
`X-Dev-User: <email>` header, which the web app sends for you (`VITE_DEV_USER`, default
`dev@localhost`). The api refuses to start in dev auth mode when `ENV` is `dev` or `prod`.

## Run locally

Each command runs in its own terminal, from the repository root unless noted.

```sh
docker compose up -d db                                                          # Postgres
uv run --package api fastapi dev apps/api/src/api/main.py                        # api on :8000
uv run --package renderer fastapi dev apps/renderer/src/renderer/main.py --port 8001
cd apps/web && bun run dev                                                       # app on :5173
```

Open http://localhost:5173. The Vite dev server proxies `/api` to the api on port 8000.

## Checks

These are the same checks CI runs (`.github/workflows/ci.yml`).

```sh
# Python, from the repository root (Postgres must be running; tests use the vitae_test database)
uv run ruff check . && uv run ruff format --check .
uv run ty check
uv run pytest --cov

# Web, from apps/web
bun run check          # svelte-check
bun run lint           # prettier and eslint
bun run test           # vitest, including the design token test
bun run test:e2e       # Playwright against a mocked api, builds and serves the app
bun run gen:api        # after an api schema change: regenerate src/lib/api types, commit them
```

### Templates

Typst templates live in `templates/` (`_lib/cv.typ` holds the shared helpers). The golden tests
render every template with every fixture in `templates/fixtures/` and compare the SVG output with
`templates/golden.json`. After an intended template change, regenerate the goldens and the
`preview.png` images, then review the previews before committing:

```sh
UPDATE_GOLDENS=1 uv run pytest apps/renderer/tests/test_templates.py
```

The renderer bundles its fonts in `apps/renderer/fonts/` (Libertinus Serif, SIL Open Font License,
see `apps/renderer/fonts/libertinus/OFL.txt`) and uses no system fonts, so output is the same on
every machine.

## Repository layout

```
apps/
  web/            SvelteKit SPA
  api/            REST API; serves the built SPA in production
  renderer/       sandboxed Typst compile service
packages/
  cvcore/         code shared by api and renderer
templates/        Typst templates, shared helpers, fixtures and goldens
docs/             product, design, backend, infrastructure and roadmap specs
compose.yaml      local Postgres
```

`infra/` arrives in M2.

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
