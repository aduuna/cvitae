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
- SvelteKit app in `apps/web` with bun: Svelte 5, adapter-static SPA (`fallback: "spa.html"`,
  `ssr = false` in the root layout; only the landing page at `/` is prerendered), Tailwind v4 via `@tailwindcss/vite`, Geist fonts, `@lucide/svelte`,
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

## M6: Browser extension

Built ahead of M5 on a branch, as an exploration (`docs/PRODUCT.md`, 8).

- `cvcore`: `application.py` and `places.py` with tests.
- `extension_tokens` table and migration; connection routes for the web app and token routes for the
  extension, with API tests for scoping, revocation and the token working on extension routes only.
- Web app: the Extension page (`/app/extension`, in the side nav), the privacy policy (`/privacy`),
  `?job=` on Tailor, return to the page after sign-in, the `Checkbox` primitive.
- `apps/extension`: Manifest V3 for Chrome and Firefox; background script, connect script, content
  script (field detection, filling, the fill offer, job ad reading), side panel; unit tests on form
  fixtures from the main job platforms, Playwright tests with the built extension; CI job.

Done when: the checks in `docs/PRODUCT.md`, 8 pass in Chrome and Firefox against `dev`, `web-ext lint`
reports no errors, and both store listings are drafted (privacy text: what is read, when, and that
nothing is stored or sent elsewhere).

## M7: ATS score

Built on a branch after M6, like it (`docs/PRODUCT.md`, 9).

- `cvcore/ats.py` with tests: term matching, short forms, abbreviations, title, score, bands, checks.
- `services/ats.py`; `GET /documents/{id}/ats`, `POST /jobs/{id}/analyze`, `job_id` on
  `PATCH /documents/{id}`; tailoring returns `ats` and the model no longer lists missing keywords.
- Web app: the ATS report in Next steps; the editor's ATS button and dialog.

Done when: the checks in `docs/PRODUCT.md`, 9 pass, with API, unit and Playwright tests at 1280px
and 768px.

## M8: Drafted answers in the extension

Built after M7 on top of M6, also ahead of M5 (`docs/PRODUCT.md`, 8, Answer questions;
`docs/BACKEND.md`, Drafted answers).

- Docs: the CV rule and the drafts' rule stated apart (`AGENTS.md` rule 8, `docs/PRODUCT.md`
  principles 1 and 4, `docs/BACKEND.md` prompt rules).
- `cvcore`: `DraftAnswers` output models in `ai.py` (through `llm_schema`); `answers.py` (number
  placeholders, word and character limits, the skills hint); the fact guard's number pattern and
  mention test exported for it, the guard itself unchanged.
- api: migration `0008` (`answers` in `ai_runs.task`); `ai/prompts/draft_answers.py` with
  `ANSWER_RULES`; `tasks.draft_answers`; `services/answers.py`; `POST /extension/answers` with the
  token user's plan, AI runs and models; a `FakeLLMProvider` responder. Service tests with the fake
  provider, API tests for the route.
- Web app: `bun run gen:api`; the privacy policy and the Extension page describe drafted answers.
- `apps/extension`: open question detection, limits and the AI notice in the content script; undo
  kept per fill (fields, answers); the Answer questions card; the mock api; vitest and Playwright
  tests; the store listing, manifest description and store screenshots; version 0.2.0 and
  `bun run package`.

Done when:

- `uv run pytest` passes, with tests that one request takes one AI run, the quota is checked before
  any model call, a refused or failed request saves nothing, a number not in the material becomes a
  placeholder, answers fit their limits, the hint lists only skills the material does not mention,
  and another user's profile, CV or job is a 404; Firebase tokens are refused on the route.
- The fact guard's tests pass unchanged, and no code path puts a draft into a CV or a profile.
- The extension's vitest covers question detection on the Greenhouse, Lever, Ashby and careers
  fixtures (open questions found; excluded, hidden and already classified fields not), limits from
  `maxlength` and labels, the AI notice, and the card from finding questions to Undo.
- The extension's Playwright test finds questions, drafts them against the mock api, edits one,
  fills, checks the page, and undoes.
- Every check in `AGENTS.md`'s definition of done and `bun run lint:firefox` pass, and coverage for
  `apps/api` and `packages/cvcore` stays at or above 85%.
- `apps/extension` is at 0.2.0 and `bun run package` has written the three zips; `listing.md` (with no
  job platform names in its description), the privacy policy and the manifest describe the feature,
  and the Chrome data usage answers and Firefox `data_collection_permissions` match it with no new
  browser permission.

---

## Later (not scheduled)

Cover letters from the same profile and job, DOCX export, in-browser Typst preview via WASM to cut
renderer calls, bring-your-own API key, shareable read-only CV links, OpenAI models as a fourth
provider. For the extension: filling custom list widgets (Workday's, react-select), drafting cover
letters once the app has them, and remembering per site which fields the user corrected.
