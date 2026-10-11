# Roadmap

Build in this order. Each milestone ends with a working, tested app. Finish a milestone's "done when"
list before starting the next. Within a milestone, keep each change small: one feature or layer per
commit, with its tests.

How to work through a milestone with Claude Code:

1. Read the milestone and the doc sections it links to.
2. Write a short plan (files to add or change, tests to write) and confirm it before coding.
3. Implement with tests; run the checks from `AGENTS.md`.
4. Tick the "done when" items explicitly in the final message, with the command output that proves each.

---

## M0: Foundations

Scaffold the repository and the design system, with nothing user-facing beyond the shell.

- uv workspace (`apps/api`, `apps/renderer`, `packages/cvcore`) with ruff, ty and pytest configured
  (`docs/BACKEND.md`, "uv workspace").
- SvelteKit app in `apps/web` with bun: Svelte 5, adapter-static SPA (`fallback: "index.html"`,
  `ssr = false` in the root layout), Tailwind v4 via `@tailwindcss/vite`, Geist fonts, `@lucide/svelte`,
  eslint, prettier, svelte-check, vitest, Playwright.
- `app.css` with the full token set and the token enforcement test (`docs/DESIGN.md`).
- UI primitives: Button, IconButton, Icon, Input, Textarea, Select, SegmentedControl, Tabs, Dialog,
  ConfirmDialog, Menu, Toast, Tooltip, Badge, Card, EmptyState, Skeleton, Kbd, Splitter, Dropzone,
  each with tests.
- App shell: side nav with the six items, collapsible to an icon rail, top bar, empty pages for each route.
- `compose.yaml` with Postgres; `ci.yml` running python, web and infra-format jobs.

Done when: `uv run pytest`, `bun run check`, `bun run lint` and `bun run test` pass in CI; the shell
renders at 1280px and 768px; the token test fails if a raw color is added to a component.

## M1: Profiles, CVs and rendering (no AI, dev auth)

- `cvcore`: models, rich-text parser with property tests, `llm_schema` (used later).
- Database models and first Alembic migration for `users`, `profiles`, `documents`, `document_versions`.
- `AUTH_MODE=dev` auth dependency; `UserScopedRepository` with the cross-user isolation test.
- Profiles: CRUD API and the section editor UI (drag and keyboard reorder, engagements, autosave).
- Renderer service: `/render` with the sandbox (child process, limits, `@` import rejection), `classic`
  and `compact` templates, `_lib/cv.typ`, fixtures, golden tests.
- Documents: create from a profile, list, rename, duplicate, delete; editor with form mode and live SVG
  preview; template switch; versions (manual and restore); PDF export with the placeholder check.
- Generate frontend API types from OpenAPI (`bun run gen:api`) and use `openapi-fetch`.

Done when: a user (dev auth) can build a profile by hand, create three CVs from it, edit one with live
preview, switch between `classic` and `compact`, restore a version and download a PDF; renderer tests
prove a 20-second infinite loop is killed at the time limit and an `@preview` import is rejected.

## M2: Auth, storage and first deploy

- Firebase Auth on the frontend (Google and email link) and `FirebaseVerifier` on the backend.
- `Storage` port with `GcsStorage` and `LocalStorage`; `uploads` table.
- OpenTofu: `bootstrap/`, modules, `envs/dev` (`docs/INFRA.md`).
- Dockerfiles for `api` and `renderer`; `deploy.yml` for `dev` with migrations and smoke test.
- Remaining templates: `modern`, `minimal`, `technical`; Templates page with previews and default template.

Done when: pushing to `main` deploys to `dev`; a real Google sign-in works on the Cloud Run URL; the
renderer rejects requests without the api's OIDC token; all five templates pass golden tests.

## M3: AI with Claude and Gemini

- `LLMProvider` protocol, Claude and Gemini adapters, `FakeLLMProvider`, provider registry,
  `ai_runs` table, pricing table (`docs/BACKEND.md`, "AI pipeline").
- Fact guard with its full test suite.
- Import: upload or paste, provider choice, draft review, accept into a profile.
- Jobs and Tailor: job form, job analysis, tailoring, review screen (Preview, Changes, Gaps),
  regenerate with the other provider.
- Provider preference in Settings; provider segmented control on Import and Tailor.
- Live tests (`-m live`) for both providers, run manually with real keys.

Done when: with the fake provider, the tailoring flow test passes end to end; with real keys (manual run),
both Claude and Gemini import `templates/fixtures/sample-cv.pdf` and tailor the fixture profile against
the fixture job with zero fact-guard violations left unflagged; each run records tokens and cost.

## M4: Plans, quotas and Paystack

- `billing/plans.py`, quota checks on every AI task and on CV and profile creation, `GET /usage`,
  usage display in the side nav.
- Paystack checkout, verify, webhooks with signature check and idempotency, manage link.
- `subscriptions` and `webhook_events` tables.

Done when: in Paystack test mode a user upgrades to Pro, the webhook flips the plan, limits change in the
UI, cancelling via the manage link leads to `subscription.disable` and a downgrade, and replaying a webhook
changes nothing.

## M5: Advanced editing and hardening

- Eject to Typst: CodeMirror 6 editor for `main.typ` and `data.json`, diagnostics inline, one-way
  confirmation.
- Renderer egress lock (Direct VPC egress, no NAT) applied in OpenTofu and verified.
- Account export and deletion (database and GCS), with tests.
- Cloud Scheduler version pruning; budget alerts; CSP and security headers.
- `envs/prod`, prod deploy on tags with approval, custom domain mapping.
- Accessibility pass against `docs/DESIGN.md`; Playwright coverage for the main flows.

Done when: a production deploy is live on the custom domain, an ejected CV compiles and exports, account
deletion leaves no rows or objects behind, and Lighthouse accessibility scores 95 or higher on Documents,
the editor and Settings.

---

## Later (not scheduled)

Cover letters from the same profile and job, DOCX export, in-browser Typst preview via WASM to cut
renderer calls, bring-your-own API key, shareable read-only CV links, OpenAI models as a fourth
provider.
