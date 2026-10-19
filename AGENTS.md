# AGENTS.md

Chameleon vitae is a web app that turns a person's career history into polished, job-specific CVs.
Users import an existing CV or enter their experience, paste a job description, and get a tailored CV
rendered with Typst. They can keep many CVs, switch between 5 templates, edit in a form or in raw Typst,
and export PDF. AI runs on MiMo, Claude or Gemini models, chosen by the user.

Read these before writing code. They are the source of truth; if code and docs disagree, ask.

| File | What it defines |
|---|---|
| `docs/PRODUCT.md` | Features, side-nav sections, user flows, acceptance criteria, plans |
| `docs/DESIGN.md` | Design language, tokens, components, layout, copy rules |
| `docs/BACKEND.md` | Architecture, data model, API, AI pipeline, renderer, testing |
| `docs/INFRA.md` | GCP, OpenTofu, containers, CI/CD, environments |
| `docs/ROADMAP.md` | Milestones in build order, with "done when" checks |

Work one milestone at a time from `docs/ROADMAP.md`. Do not start the next milestone until the current
one meets its "done when" list and all checks pass.

## Stack

- Frontend: SvelteKit (Svelte 5 runes, SPA mode via adapter-static), Tailwind CSS v4, `@lucide/svelte`,
  Geist and Geist Mono via `@fontsource-variable/geist` and `@fontsource-variable/geist-mono`,
  CodeMirror 6 for the Typst editor, Firebase Auth (client SDK).
- Browser extension: Manifest V3 for Chrome and Firefox, a Svelte 5 side panel built with Vite that
  reuses `apps/web`'s tokens, components and generated API types (`@web`), plain TypeScript content
  scripts. See `docs/PRODUCT.md`, 8.
- Backend: Python 3.13, FastAPI (`fastapi[standard]`), Pydantic v2, pydantic-settings, SQLAlchemy 2 (async) with psycopg 3,
  Alembic, firebase-admin, anthropic, google-genai, httpx.
- Rendering: Typst through the `typst` Python package, in a separate `renderer` service.
- Data: Neon Postgres, Google Cloud Storage. Payments: Paystack.
- Infra: GCP Cloud Run, Artifact Registry, Secret Manager, OpenTofu, GitHub Actions.

## Hard rules

1. **Package managers: bun and uv only.** Never use npm, npx, pnpm, yarn, pip, pipx or poetry.
   Use `bun add`, `bunx`, `bun run`, `uv add`, `uv run`, `uv sync`.
2. **No emojis or em dashes** anywhere: UI, copy, code, comments, commit messages, docs.
3. **Colors come from semantic tokens only** (`bg-surface`, `text-fg`, `border-line`, ...). Never use raw
   palette utilities (`gray-500`, `black`, hex values) inside components. See `docs/DESIGN.md`.
4. **Icons only through `$lib/components/ui/Icon.svelte`**, which wraps `@lucide/svelte` with the
   standard size and stroke (the extension imports the same file). No other icon sets, no inline SVG
   icons.
5. **Backend layering is strict:** routers call services, services call repositories and ports
   (LLM, storage, renderer, billing, auth). Routers never touch the database. Repositories hold no
   business logic. See `docs/BACKEND.md`.
6. **Every repository query is scoped by `user_id`** through the shared base repository helper.
   No query may return another user's rows.
7. **Never log CV content, profile content, job descriptions, uploaded files or prompts.** Log IDs,
   counts, durations, token usage and error codes only.
8. **The AI must not invent facts.** Tailoring may select, reorder and reword. New numbers or claims
   become placeholders. The deterministic fact guard in `cvcore` enforces this; never bypass it.
9. **No secrets in code or in the repo.** Settings come from environment variables via pydantic-settings;
   in GCP they come from Secret Manager.
10. **DRY:** shared Pydantic models, markup parsing and the fact guard live in `packages/cvcore` and are
    imported by both Python apps. Frontend API types are generated from the OpenAPI schema, never
    hand-written. Typst helpers shared by all templates live in `templates/_lib/cv.typ`.
11. **Tests ship with the code.** New service logic needs unit tests; new endpoints need API tests;
    template changes must pass the golden render tests. No real LLM or Paystack calls in the default
    test run.

## Repository layout

```
AGENTS.md
docs/                   product, design, backend, infra, roadmap
apps/
  web/                  SvelteKit SPA (bun)
  api/                  FastAPI app: REST API + serves the built SPA (uv)
  renderer/             FastAPI app: sandboxed Typst compile service (uv)
  extension/            browser extension for Chrome and Firefox (bun; builds on apps/web)
packages/
  cvcore/               shared Pydantic models, rich-text parser, fact guard (uv)
templates/
  _lib/cv.typ           shared Typst helpers
  classic/ compact/ modern/ minimal/ technical/   one folder per template
  fixtures/             sample data.json files for golden tests
infra/                  OpenTofu (bootstrap, modules, envs)
.github/workflows/      ci.yml, deploy.yml
pyproject.toml          uv workspace root
compose.yaml            local Postgres for development and tests
```

## Commands

Python (from the repo root; uv workspace):

```
uv sync                                   # install all Python packages
uv run ruff check . && uv run ruff format --check .
uv run ty check                           # type check (config in [tool.ty])
uv run pytest                             # all Python tests (needs Postgres: docker compose up -d db)
uv run --package api alembic upgrade head # run migrations (from apps/api)
uv run --package api fastapi dev apps/api/src/api/main.py
uv run --package renderer fastapi dev apps/renderer/src/renderer/main.py --port 8001
```

Frontend (from `apps/web`):

```
bun install
bun run dev            # Vite dev server, proxies /api to localhost:8000
bun run check          # svelte-check
bun run lint           # eslint + prettier --check
bun run test           # vitest
bun run test:e2e       # playwright
bun run gen:api        # regenerate src/lib/api/schema.d.ts from apps/api OpenAPI
bun run build
```

Browser extension (from `apps/extension`; needs `bun install` in `apps/web` too):

```
bun install
bun run build          # dist/chrome and dist/firefox; VITE_APP_URL sets the app (default :5173)
bun run package        # store zips in releases/, for the live app (docs/INFRA.md)
bun run store:assets   # store screenshots and promo tiles in store/
bun run check          # svelte-check
bun run lint           # eslint + prettier --check
bun run lint:firefox   # web-ext lint on dist/firefox
bun run test           # vitest
bun run test:e2e       # playwright with the built extension (bunx playwright install chromium)
```

## Definition of done (every change)

- Ruff, ty, svelte-check, eslint and prettier pass with no new warnings.
- Tests for the change exist and pass; coverage for `apps/api` and `packages/cvcore` stays at or above 85%.
- If an API schema changed, `bun run gen:api` was run and the generated types are committed.
- If a template changed, golden render tests pass and the preview image was regenerated.
- UI changes follow `docs/DESIGN.md` (tokens, components, copy rules) and work at 1280px and 768px widths.
- No TODO comments without a linked issue.

## When unsure

Prefer the simplest thing that satisfies the docs. Do not add services, queues, caches or frameworks
that the docs do not call for; this app has zero customers and runs in two containers. Ask before
changing the data model, the API contract or the infrastructure layout.
