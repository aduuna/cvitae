# Chameleon vitae

[![CI](https://github.com/aduuna/cvitae/actions/workflows/ci.yml/badge.svg)](https://github.com/aduuna/cvitae/actions/workflows/ci.yml)

Paste a job description, get a CV tailored to it, typeset properly, without the AI inventing anything.

Chameleon vitae turns a person's career history into job-specific CVs. Users import an existing CV
or enter their experience, paste a job description, and get a tailored CV rendered with Typst. AI runs
on MiMo, Claude or Gemini models, chosen by the user, and may only select, reorder and reword facts
the user gave.

**Status:** milestone M4 (plans, quotas and Paystack) is built. Users sign in with Google or an
email link, import a CV (PDF, DOCX or pasted text) into a profile, paste a job description and get a
tailored CV checked by the fact guard, edit it with a live Typst preview in one of five templates,
and export PDFs. Free and Pro plans limit CVs, profiles and monthly AI usage, and users upgrade to Pro
through Paystack. Every push to `main` that passes CI deploys to dev at https://cvitae.aduuna.dev.
Advanced editing and hardening come next. See [docs/ROADMAP.md](docs/ROADMAP.md).

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

Locally the api runs with `AUTH_MODE=dev` and trusts an `X-Dev-User: <email>` header instead of a
Firebase token. The web app asks the api how to sign in (`GET /api/v1/client-config`) and, in dev
mode, sends that header for you (`VITE_DEV_USER`, default `dev@localhost`). The api refuses to start
in dev auth mode when `ENV` is `dev` or `prod`. Uploaded files go to `.data/uploads/`
(`STORAGE_MODE=local`).

## Run locally

Each command runs in its own terminal, from the repository root unless noted.

```sh
docker compose up -d db                                                          # Postgres
uv run --package api fastapi dev apps/api/src/api/main.py                        # api on :8000
uv run --package renderer fastapi dev apps/renderer/src/renderer/main.py --port 8001
cd apps/web && bun run dev                                                       # app on :5173
```

Open http://localhost:5173. The Vite dev server proxies `/api` to the api on port 8000.

### With mise

If you use [mise](https://mise.jdx.dev/), `mise.toml` wraps the steps above in tasks, so one terminal
is enough. Docker must be running.

```sh
mise install        # bun and uv, at the versions in mise.toml
mise run setup      # first run: uv sync, bun install, .env from .env.example
mise run dev        # Postgres, migrations, api, renderer and web app; Ctrl+C stops them
```

`mise run dev` starts Postgres, waits for it, applies migrations, then runs the api, renderer and
web app in parallel with prefixed logs. Ctrl+C leaves the Postgres container running; stop it with
`docker compose stop db`. Each part also runs alone: `mise run db`, `mise run migrate`,
`mise run dev:api`, `mise run dev:renderer` and `mise run dev:web`. `mise tasks` lists them all.

### In a dev container or Codespaces

`.devcontainer/` sets up the same environment in a container: open the repository in GitHub
Codespaces, or in VS Code with "Dev Containers: Reopen in Container". On first start it installs
mise, the tools in `mise.toml`, the dependencies and the Playwright browser, and creates `.env`.
Postgres runs inside the container through Docker in Docker. When it is ready:

```sh
mise run dev
```

Ports 5173 (web), 8000 (api) and 8001 (renderer) are forwarded, and the web app opens in the
browser. The container keeps its own `.venv` and `apps/web/node_modules` in volumes, so it never
overwrites the ones on your machine.

### AI providers

Import and Tailor call MiMo, Claude or Gemini. Set any of `MIMO_API_KEY`, `ANTHROPIC_API_KEY` and
`GEMINI_API_KEY` in `.env` to use them locally; a provider without a key is not offered. Tests never call them: the default run uses
a deterministic fake. The real calls have their own tests, run by hand because they cost money:

```sh
uv run pytest -m live apps/api/tests/test_llm_live.py -s   # prints tokens and cost per run
```

Pro models need the Pro plan. To try them locally without Paystack, set `ENFORCE_AI_PLANS=false`.

### Billing

Upgrades go through Paystack and are offered only when `PAYSTACK_SECRET_KEY` (a test key, `sk_test_...`),
`PAYSTACK_PRO_PLAN_CODE` and `PAYSTACK_CALLBACK_URL` are set. Paystack sends the user back to the
callback URL, where the SPA verifies the payment. Webhooks need a public URL: point the Paystack
dashboard at a tunnel to `/api/v1/webhooks/paystack`, or rely on the verify call alone while
developing. Tests use a fake Paystack and signed sample events; they never call Paystack.

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

The renderer bundles its fonts in `apps/renderer/fonts/` (Libertinus Serif, Geist and Geist Mono,
all under the SIL Open Font License; see the `OFL.txt` in each folder) and uses no system fonts, so
output is the same on every machine.

## Deployment

Infrastructure is OpenTofu in `infra/` (see [docs/INFRA.md](docs/INFRA.md)). `infra/bootstrap` was
applied once by hand; after that, `.github/workflows/deploy.yml` builds both images, runs migrations,
applies `infra/envs/dev` with the new image digests and runs a smoke test, every time CI passes on
`main`. Nothing is deployed with `gcloud run deploy`.

## Repository layout

```
apps/
  web/            SvelteKit SPA
  api/            REST API; serves the built SPA in production
  renderer/       sandboxed Typst compile service
packages/
  cvcore/         code shared by api and renderer
templates/        Typst templates, shared helpers, fixtures and goldens
infra/            OpenTofu: bootstrap, modules, envs/dev, github
docs/             product, design, backend, infrastructure and roadmap specs
compose.yaml      local Postgres
mise.toml         optional local tasks (mise run dev)
.devcontainer/    dev container for Codespaces and VS Code
```

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
