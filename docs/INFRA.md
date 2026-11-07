# Infrastructure

Goal: near-zero cost at zero customers, two containers, no clusters, everything reproducible with
OpenTofu and deployed by GitHub Actions.

## Environments

| Env | GCP project | Neon | Deploys |
|---|---|---|---|
| `local` | none | Postgres in `compose.yaml` (or a personal Neon branch) | `fastapi dev`, `bun run dev` |
| `dev` | `cvitae-511214` | Neon database `neondb` (pooled and direct endpoints) | every push to `main` that passes CI |
| `prod` | `cvitae-prod` (a second project, with its own state bucket) | Neon, separate branch or project | tags `v*`, behind a GitHub environment approval |

Region: `europe-west1` for Cloud Run, Artifact Registry and GCS (supports Cloud Run domain mappings and
is close to both Europe and Africa). Neon region: AWS `eu-central-1` (Frankfurt) is the closest to
Cloud Run. The dev database was created in `us-east-2`; every query crosses the Atlantic until it
moves (create a Frankfurt project, then replace the two `database-url*` secret versions).

Domain: `cvitae.aduuna.dev` (a CNAME to `ghs.googlehosted.com` at the DNS host) is mapped to the dev
`api` service. `aduuna.dev` is verified in Google Search Console by the project owner. Prod is served
at `app.<domain>`, with `domain` set in `infra/envs/prod/terraform.tfvars` (see Production).

## GCP resources (per project)

| Resource | Name | Settings |
|---|---|---|
| Artifact Registry (Docker) | `cvitae` | Cleanup policy: keep the 3 most recent images per package (the deployed one and two to roll back to), so storage stays near the free 0.5 GB. Created by `bootstrap/`, because images are pushed before the services exist. |
| Cloud Run service | `api` | Public (`allUsers` invoker; auth is Firebase at app level). Min 0, max 3 instances, 1 vCPU, 512 MiB, concurrency 40, request timeout 300 s, CPU only during requests. Service account `api-sa`. |
| Cloud Run service | `renderer` | Ingress `all`, but IAM invoker granted only to `api-sa`, so Google rejects any request without a valid OIDC token for that account before it reaches the container. Min 0, max 3, 1 vCPU, 1 GiB, concurrency 4, timeout 30 s. Service account `renderer-sa` with no roles. Direct VPC egress with `ALL_TRAFFIC` into a subnet that has no Cloud NAT, so it has no internet access. (Internal-only ingress would force the api's traffic through the VPC and require Cloud NAT for its calls to Neon, the AI providers and Paystack; not worth it at this stage.) |
| VPC | `cvitae-vpc` with subnet `renderer-egress` (`10.10.0.0/26`) | No Cloud NAT, no router, no default route, no Private Google Access. Exists only to cut the renderer off. `infra/scripts/check-renderer-egress.sh` verifies it (see Renderer egress lock). |
| GCS bucket | `<project>-uploads` | Uniform access, public access prevention enforced, versioning off, lifecycle: none (user deletes remove objects). `api-sa` has `roles/storage.objectAdmin` on this bucket only. |
| Secret Manager | `anthropic-api-key`, `gemini-api-key`, `mimo-api-key`, `paystack-secret-key`, `database-url`, `database-url-direct` | `api-sa` can access all except `database-url-direct`; the CI deployer can access `database-url-direct` for migrations. |
| Cloud Scheduler | `prune-versions` (daily 03:00 UTC) | Calls `POST /api/v1/internal/prune-versions` on `api` with an OIDC token from `scheduler-sa` (no roles; the api verifies the token). The audience is the api's public URL, the custom domain's, because the service's own URL is not known before it exists. The api gets it as `PUBLIC_BASE_URL`, and `scheduler-sa`'s address as `SCHEDULER_SA_EMAIL`. |
| Firebase Auth | project-level | Firebase was added and the Google provider enabled in the console (its OAuth client secret stays out of OpenTofu state). OpenTofu owns the web app (`google_firebase_web_app`, whose config the api serves to the SPA) and the Auth config, adopted with an `import` block: email sign-in (email link; Firebase also accepts a password for an account made with one, which only the store review account is), and authorized domains `localhost`, the Firebase domains, the Cloud Run URL and the custom domain. |
| Domain mapping | `app.<domain>` -> `api` | Cloud Run domain mapping (free). Move to a load balancer only if needed later. |
| Budget alert | billing account | Alerts at $10, $25, $50 per month, for the dev and prod projects only. One budget in `infra/billing/`, applied by hand: the deployer holds no billing roles. |

APIs to enable: run, artifactregistry, secretmanager, iam, iamcredentials, sts, cloudscheduler, compute
(for the VPC), firebase, identitytoolkit, logging, monitoring; `infra/billing/` enables billingbudgets.

What is deliberately absent: GKE, load balancers, Pub/Sub, Redis, Cloud SQL, Cloud Tasks. Add them only
when a measured need appears.

## Containers

Both images build from the repository root so the uv workspace and `cvcore` are available.

`apps/api/Dockerfile` (multi-stage):

```dockerfile
# 1. Build the SPA with bun. Vite runs under Node, as in CI: SvelteKit's build does not finish
# under the Bun runtime that the oven/bun image would use.
FROM oven/bun:1.3.9 AS bun
FROM node:24-bookworm-slim AS web
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
WORKDIR /src/apps/web
COPY apps/web/package.json apps/web/bun.lock ./
RUN bun install --frozen-lockfile
COPY apps/web ./
RUN bun run build                    # outputs apps/web/build

# 2. Build the Python environment with uv (same /srv path as runtime so the venv is not relocated)
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS py
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
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
COPY templates/_lib /srv/templates/_lib
COPY templates/classic/main.typ /srv/templates/classic/main.typ
COPY templates/fixtures/profile-sample.json templates/fixtures/profile-edge.json /srv/templates/fixtures/
ENV PATH="/srv/.venv/bin:$PATH" STATIC_DIR=/srv/static SAMPLE_PROFILE_PATH=/srv/sample-profile.json \
    TEMPLATES_DIR=/srv/templates
USER app
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
```

`--no-editable` installs `api` and `cvcore` into the venv as regular packages, so the runtime image needs
only the venv, the static files and the few template files that drafting a custom template reads
(`TEMPLATES_DIR`). The renderer's `pyproject.toml` is copied because uv resolves the whole workspace
lockfile.

`apps/renderer/Dockerfile`: same uv pattern without the web stage; copies `templates/` to `/templates`
and `apps/renderer/fonts/` to `/fonts`; runs as a non-root user; `CMD` runs uvicorn on port 8080.

Images are tagged with the git SHA and deployed by digest.

## OpenTofu layout

```
infra/
  bootstrap/                 applied once by hand per project, with local credentials
    dev/   main.tf  backend.tf  variables.tf  outputs.tf    the dev project and its state
    prod/  main.tf  backend.tf  variables.tf  outputs.tf    the prod project and its state
  modules/
    project_bootstrap/       APIs, state bucket, registry, Workload Identity pool + GitHub provider, deployer SA
    cloud_run_service/       one module used for both api and renderer (image, sa, scaling, env, secrets, ingress, vpc egress)
    renderer_vpc/            cvitae-vpc and the renderer-egress subnet, no way out
    scheduler_job/           Cloud Scheduler job that POSTs with an OIDC token
    secret/                  secret + IAM accessor bindings
    bucket/
  envs/
    dev/   main.tf  auth.tf  versions.tf  variables.tf  outputs.tf  terraform.tfvars  backend.tf
    prod/  the same files, the same modules, production settings
  billing/                   budget alerts on the billing account, applied by hand
  scripts/                   check-renderer-egress.sh
  github/                    repository environments and their branch policies
```

- `bootstrap/` also enables the project's APIs, creates the Artifact Registry repository and the
  deployer service account with the roles `envs/*` need. Each project has its own root folder with
  its own backend and project values (the module `project_bootstrap` holds the resources), so there
  is nothing to switch between dev and prod and a bare `tofu apply` cannot pair one project's
  values with the other's state. Each state started local and was moved to the state bucket
  (`tofu init -migrate-state`). People who may impersonate the deployer come from
  `TF_VAR_admin_members` (for example `'["user:you@example.com"]'`), never from a committed file, because
  the repository is public. `bootstrap/dev` keeps the state path it had when it was one folder
  (bucket `cvitae-511214-tofu-state`, prefix `bootstrap`); `moved` blocks in its `main.tf` map the
  old resource addresses into the module. After pulling that change run `tofu init` and `tofu plan`
  there: the plan must show only moves (and any new APIs or roles), never a create or destroy of an
  existing resource. Apply it, then delete the `moved` blocks.
- `github/` holds repository settings that deploys rely on: the `dev` environment may only be used
  from `main`, and `prod` only from tags `v*`, with required reviewers (`prod_reviewers`, default the
  owner) and no administrator bypass; and a tag ruleset that lets only repository admins create,
  move or delete `v*` tags. Apply it by hand with `GITHUB_TOKEN=$(gh auth token) tofu apply`.
- `billing/` holds the budget (`TF_VAR_billing_account=<id> tofu apply`, with credentials that have
  Billing Account Costs Manager). It is not in CI: the deployer must not hold billing roles.
- State: GCS backend bucket `<project>-tofu-state` with versioning, created by `bootstrap/`, one prefix
  per stack (`bootstrap`, `envs/dev`, `github`, `billing`; `bootstrap` and `envs/prod` in the prod
  project's bucket).
- Providers: `google` and `google-beta` (Firebase and Identity Platform resources), versions pinned.
- `envs/*/main.tf` only composes modules; its inline resources are the service accounts, the domain
  mapping and the Firebase Auth setup. Anything else both environments need (VPC, scheduler job) is a
  module.
- Image digests are input variables (`api_image`, `renderer_image`) set by CI, so OpenTofu owns the
  full service definition and there is no drift from `gcloud run deploy`.
- Secret values are never in OpenTofu. Tofu creates the secrets; values are added once with
  `gcloud secrets versions add`.
- The AI keys reach the api only for the secrets listed in `ai_keys` in `envs/dev/terraform.tfvars`.
  Add a key with `printf '%s' "$KEY" | gcloud secrets versions add anthropic-api-key --data-file=-`,
  then list `anthropic-api-key` there and push: Cloud Run refuses a secret that has no version.
- Neon is managed in the Neon console (project, branches, roles). Its connection strings go into Secret
  Manager. Managing Neon from OpenTofu is optional later.
- Billing stays off until it is configured, the same way. Use Paystack test mode keys in `dev`:
  1. In the Paystack dashboard, create the monthly Pro plan and note its code (`PLN_...`).
  2. `printf '%s' "$SK" | gcloud secrets versions add paystack-secret-key --data-file=-`.
  3. Set `paystack_pro_plan_code` in `envs/dev/terraform.tfvars` and push. The api then gets
     `PAYSTACK_SECRET_KEY`, `PAYSTACK_PRO_PLAN_CODE` and `PAYSTACK_CALLBACK_URL`
     (`https://<custom_domain>/app/settings?tab=billing`).
  4. In the dashboard's API settings, set the webhook URL to
     `https://<custom_domain>/api/v1/webhooks/paystack`.

### Renderer egress lock

`infra/scripts/check-renderer-egress.sh <project-id>` runs at the end of every deploy and by hand with
the deployer's credentials (`GOOGLE_IMPERSONATE_SERVICE_ACCOUNT`). It checks that the `renderer` service
routes all traffic into a subnet (the network and subnet are read from the service's
`network-interfaces` annotation), that the subnet's network has no router (so no Cloud NAT) and no
default route, and then runs a throwaway Cloud Run job with the renderer's image, service account and
network settings that tries to connect to public addresses; every attempt must fail. The job is
deleted afterwards. It needs `gcloud` and `jq`. If it ever reports a leak, remove the router or route
it names before anything else.

The check runs after the apply, so a broken lock is found once the new revision is live, and the
probe job runs on every deploy even when the network has not changed. That is accepted at this
scale: the configuration checks are cheap, the probe takes about a minute, and a failed check is a
red deploy to fix at once rather than a rollback. Move the configuration checks before the apply if
that ever stops being enough.

### Production

Stand-up order for `prod`; the project id is `cvitae-prod` (change it in `bootstrap/prod/main.tf`,
`bootstrap/prod/backend.tf`, `envs/prod/backend.tf`, `envs/prod/terraform.tfvars`,
`billing/terraform.tfvars` and the `prod` job in `deploy.yml` if the id is taken).

1. Create the project and link billing. Create the Neon database for prod (Frankfurt).
2. `infra/github`: `GITHUB_TOKEN=$(gh auth token) tofu apply` creates the protected `prod`
   environment (required reviewers, tag policy) and the `release-tags` ruleset. Do this before
   anything that lets a tag deploy (steps 3 and 4). GitHub creates a missing environment the first
   time a job names it, with no reviewers and no branch or tag policy, and the workflow cannot
   check that the protection exists, so a tag pushed before this step could deploy with no approval.
3. Bootstrap prod, with your credentials and `TF_VAR_admin_members` set. The state bucket does not
   exist yet, so the first apply uses local state, then moves it:
   ```sh
   cd infra/bootstrap/prod
   mv backend.tf backend.tf.off && tofu init
   tofu apply
   mv backend.tf.off backend.tf
   tofu init -migrate-state -force-copy
   ```
   Delete the local `terraform.tfstate*` files afterwards. This folder holds the prod project, its
   backend and its state only, so nothing needs switching and a bare `tofu apply` here can only
   touch prod. The same apply lets the prod deployer read dev's registry, which prod deploys
   promote images from.
4. `gh variable set PROD_WIF_PROVIDER --body "$(tofu output -raw workload_identity_provider)"`
   (still in `infra/bootstrap/prod`): the `prod` deploy reads the provider from this repository
   variable, because it is known only now.
5. In the Firebase console, add Firebase to the project and enable Authentication with the Google
   provider, as in dev (the first apply adopts the Auth configuration this creates).
6. Set `domain` in `envs/prod/terraform.tfvars`. At the DNS host add a CNAME `app` to
   `ghs.googlehosted.com`. Cloud Run maps only a domain the caller has verified: make
   `deployer@cvitae-prod.iam.gserviceaccount.com` an owner of the domain in Google Search Console.
7. Create the secrets, so migrations can read `database-url-direct` before the first apply, then
   give them values (the AI keys and, later, the live Paystack key too):
   ```sh
   export GOOGLE_IMPERSONATE_SERVICE_ACCOUNT=deployer@cvitae-prod.iam.gserviceaccount.com
   cd infra/envs/prod && tofu init
   tofu apply -target=module.secrets -var api_image=unused -var renderer_image=unused
   printf '%s' "$URL" | gcloud secrets versions add database-url --project cvitae-prod --data-file=-
   ```
   Repeat the last command for `database-url-direct` and the AI keys, then list the AI keys in
   `ai_keys` in `envs/prod/terraform.tfvars` and commit.
8. Release: an admin pushes a tag `v*` (the ruleset stops anyone else) on a commit that passed CI on
   main and that dev built and deployed; prod promotes dev's images for that commit, which dev's
   registry keeps only for its last three builds. Then approve the run in Actions. Before approving,
   check that the tagged commit is on `main` and ran in dev: the `verify-tag` job runs from the
   tagged commit's own workflow files, so it catches mistakes but cannot be trusted alone, and the
   approval is the last gate.
9. Apply `infra/billing` (the budget) now that the project exists.

## CI/CD (GitHub Actions)

Authentication to GCP uses Workload Identity Federation (`google-github-actions/auth` with the pool and
deployer service account from `bootstrap/`). No service-account JSON keys anywhere. The pool accepts
only this repository (by numeric repository and owner id), and the deployer trusts only jobs that run
in a listed GitHub environment. The repository uses GitHub's immutable OIDC subject, which carries
the numeric owner and repository ids: `repo:aduuna@29348646/cvitae@1413058337:environment:dev`.

### `ci.yml` (pull requests and pushes)

Jobs run in parallel:

1. **python**: `astral-sh/setup-uv`, `uv sync --frozen`, `uv run ruff check .`, `uv run ruff format --check .`,
   `uv run ty check`, `uv run pytest --cov` with a `postgres:17` service container.
2. **web**: `oven-sh/setup-bun` and `astral-sh/setup-uv`, `bun install --frozen-lockfile`, `bun run check`,
   `bun run lint`, `bun run test`, `bun run build`. Then `bun run gen:api` and `git diff --exit-code` so the
   job fails if the committed API types are stale.
3. **templates**: renderer golden tests (every template x every fixture), uploads preview PNGs as artifacts.
4. **e2e**: Playwright against the built SPA and a mocked API.
5. **extension**: `bun install --frozen-lockfile` in `apps/web` (the extension builds on its tokens,
   components and generated API types) and `apps/extension`, then `bun run check`, `bun run lint`,
   `bun run test`, `bun run build`, `bun run lint:firefox` (Mozilla's `web-ext lint`), and
   `bun run test:e2e` with full Chromium (`bunx playwright install --with-deps chromium`; extensions
   do not load in the headless shell).
6. **infra**: `opentofu/setup-opentofu`, `tofu fmt -check -recursive`, and `tofu validate` for every
   stack. (A `tofu plan` for `dev` posted on pull requests, with a read-only WIF role, is still to come.)

### Browser extension

The extension needs no cloud resources: it calls the api on the app's own origin. Builds are per
browser and per environment, because the app's address is part of the manifest (host permission,
connect page) and of the code. For the stores:

```sh
cd apps/extension
bun run package    # releases/cvitae-{chrome,firefox,source}-<version>.zip
```

It builds both browsers for `VITE_APP_URL` (default `https://cvitae.aduuna.dev`; local addresses
are refused) and zips each with `manifest.json` at the root. The source zip (`apps/extension` and
`apps/web` as they are, without ignored files) is what Mozilla asks for with bundled code; to
rebuild from it: `bun install` in both folders, then `bun run build` in `apps/extension`. Nothing
is minified. Bump `version` in `apps/extension/package.json` for each upload.

Publishing is by hand: upload the Chrome zip in the Chrome Web Store Developer Dashboard and the
Firefox zip (with the source zip) on addons.mozilla.org. The listing's text and answers are in
`apps/extension/store/listing.md`; its screenshots and promo tiles come from
`bun run store:assets` (the real extension against a mock account), which rewrites
`apps/extension/store/*.jpg`. The Firefox add-on id is
`extension@cvitae.aduuna.dev`. Once a listing is live, set its address in
`apps/web/src/lib/extension/stores.ts` so the Extension page links to it. The privacy policy for
the listings is `https://cvitae.aduuna.dev/privacy`.

Store reviewers sign in with a password account, `cvitae-review` (`cvitae-review@aduuna.dev`), at
`/login?password`. `apps/api/scripts/review_account.py` creates it in Firebase with a verified
email, or gives it a new password, and prints the password:

```sh
gcloud auth application-default login
gcloud auth application-default set-quota-project cvitae-511214
uv run --package api python apps/api/scripts/review_account.py --project-id cvitae-511214
```

It needs a project owner's Google credentials, not the database: the account's `users` row is
created at its first sign-in. Sign in as it once to add a profile, a CV and a tailored CV, then
give the email and password to the stores (see `listing.md`).

### `deploy.yml`

- Trigger: CI completing successfully for a push to `main` deploys `dev` (`workflow_run`), so a failing
  build never deploys; it can also be started by hand. A tag `v*` deploys `prod`: tags do not run CI,
  so a `verify-tag` job first requires the tagged commit to be on `main` and to have a successful CI
  push run there, then the `prod` job waits for a reviewer's approval (GitHub environment `prod`).
  Tag only after CI has finished; the run can be started again from the tag if it was too early.
  `verify-tag` runs from the tagged commit's own workflow files, so it guards against mistakes, not
  against someone who can push tags: the `release-tags` ruleset (admins only) and the approver
  checking the commit are the gates.
- `deploy.yml` only routes; `deploy-env.yml` (a reusable workflow) holds the steps, so dev and prod
  run the same ones.
- The project id, registry, WIF provider and deployer email are written in the workflow: they are ids,
  not secrets, and keeping them there means no repository variables to set by hand. The one exception
  is prod's WIF provider, which contains the project number and so exists only after bootstrap: the
  repository variable `PROD_WIF_PROVIDER`.
- Steps:
  1. Authenticate with WIF.
  2. Build and push `api` and `renderer` images to Artifact Registry (Docker Buildx with GitHub cache).
     Prod builds nothing: it looks up the digest of `<image>:<sha>` in dev's registry (failing if the
     tag is gone), copies the image into its own registry by digest, checks the digest is unchanged,
     and deploys that. What runs in prod is what ran in dev, with no second build and no base image
     that could have moved in between.
  3. Run migrations: `uv run --package api alembic upgrade head` with `DATABASE_URL_DIRECT` read from
     Secret Manager. Migrations must be backward compatible with the previous release (expand, then
     contract in a later release).
  4. `tofu apply -auto-approve -var api_image=<digest> -var renderer_image=<digest>` in `infra/envs/<env>`.
  5. Smoke test (`apps/api/scripts/smoke.py`): `GET /healthz`; `GET /me` without a token is refused;
     a test user (`smoke-test`, created with the Firebase Admin SDK) signs in with a custom token
     signed by the deployer, then `GET /me` and a template preview succeed, which proves Firebase
     verification and the api's OIDC call to the renderer; a direct call to the renderer is refused.
  6. Renderer egress check (`infra/scripts/check-renderer-egress.sh`, see Renderer egress lock).

## Local development

`compose.yaml` runs Postgres 17 for development and tests:

```yaml
services:
  db:
    image: postgres:17
    environment: { POSTGRES_USER: vitae, POSTGRES_PASSWORD: vitae, POSTGRES_DB: vitae }
    ports: ["5432:5432"]
    volumes: [db-data:/var/lib/postgresql/data]

volumes:
  db-data:
```

The named volume keeps local data across `docker compose down`; `docker compose down -v` deletes it.

Run the api with `AUTH_MODE=dev`, `STORAGE_MODE=local`, `RENDERER_AUTH=none` and
`RENDERER_URL=http://localhost:8001`. The Vite dev server proxies `/api` to `localhost:8000`.
Provider keys can be set locally to try real AI calls; tests never need them.

## Cost at zero customers (rough)

Cloud Run, Artifact Registry, Secret Manager, Cloud Scheduler and GCS stay within or close to free tiers
at this scale, and Neon's free plan scales compute to zero. Expect a few dollars a month, mostly AI usage
during your own testing. The budget alert catches surprises.

## Security checklist

- Renderer: IAM invoker restricted to `api-sa` (no unauthenticated access), no internet egress
  (checked after every deploy), no secrets, resource limits (see `docs/BACKEND.md`).
- Least-privilege service accounts; no default compute service account in use.
- Secrets only in Secret Manager; mounted as environment variables at deploy.
- HTTPS only; HSTS and a strict Content Security Policy set by the api for the SPA (allow Firebase Auth
  domains and Paystack checkout redirect).
- Paystack webhook signature verified; Firebase tokens verified on every request.
- Uploads limited to 10 MB, PDF and DOCX by magic-byte check, stored under `uploads/<user_id>/`.
- Account deletion removes database rows (cascade) and the user's GCS prefix; a test covers both.
