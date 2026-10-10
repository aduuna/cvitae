# Infrastructure

Goal: near-zero cost at zero customers, two containers, no clusters, everything reproducible with
OpenTofu and deployed by GitHub Actions.

## Environments

| Env | GCP project | Neon | Deploys |
|---|---|---|---|
| `local` | none | Postgres in `compose.yaml` (or a personal Neon branch) | `fastapi dev`, `bun run dev` |
| `dev` | `cvitae-511214` | Neon database `neondb` (pooled and direct endpoints) | every push to `main` that passes CI |
| `prod` | a second project, created in M5 | Neon, separate branch or project | tags `v*`, behind a GitHub environment approval |

Region: `europe-west1` for Cloud Run, Artifact Registry and GCS (supports Cloud Run domain mappings and
is close to both Europe and Africa). Neon region: AWS `eu-central-1` (Frankfurt) is the closest to
Cloud Run. The dev database was created in `us-east-2`; every query crosses the Atlantic until it
moves (create a Frankfurt project, then replace the two `database-url*` secret versions).

Domain: `cvitae.aduuna.dev` (a CNAME to `ghs.googlehosted.com` at the DNS host) is mapped to the dev
`api` service. `aduuna.dev` is verified in Google Search Console by the project owner.

## GCP resources (per project)

| Resource | Name | Settings |
|---|---|---|
| Artifact Registry (Docker) | `cvitae` | Cleanup policy: keep the 10 most recent images per package. Created by `bootstrap/`, because images are pushed before the services exist. |
| Cloud Run service | `api` | Public (`allUsers` invoker; auth is Firebase at app level). Min 0, max 3 instances, 1 vCPU, 512 MiB, concurrency 40, request timeout 300 s, CPU only during requests. Service account `api-sa`. |
| Cloud Run service | `renderer` | Ingress `all`, but IAM invoker granted only to `api-sa`, so Google rejects any request without a valid OIDC token for that account before it reaches the container. Min 0, max 3, 1 vCPU, 1 GiB, concurrency 4, timeout 30 s. Service account `renderer-sa` with no roles. Direct VPC egress with `ALL_TRAFFIC` into a subnet that has no Cloud NAT, so it has no internet access. (Internal-only ingress would force the api's traffic through the VPC and require Cloud NAT for its calls to Neon, the AI providers and Paystack; not worth it at this stage.) |
| VPC (M5) | `cvitae-vpc` with subnet `renderer-egress` (`10.10.0.0/26`) | No Cloud NAT, no routes to the internet. Exists only to cut the renderer off. |
| GCS bucket | `<project>-uploads` | Uniform access, public access prevention enforced, versioning off, lifecycle: none (user deletes remove objects). `api-sa` has `roles/storage.objectAdmin` on this bucket only. |
| Secret Manager | `anthropic-api-key`, `gemini-api-key`, `mimo-api-key`, `paystack-secret-key`, `database-url`, `database-url-direct` | `api-sa` can access all except `database-url-direct`; the CI deployer can access `database-url-direct` for migrations. |
| Cloud Scheduler | `prune-versions` (daily 03:00 UTC) | Calls `POST /api/v1/internal/prune-versions` on `api` with an OIDC token from `scheduler-sa`. |
| Firebase Auth | project-level | Firebase was added and the Google provider enabled in the console (its OAuth client secret stays out of OpenTofu state). OpenTofu owns the web app (`google_firebase_web_app`, whose config the api serves to the SPA) and the Auth config, adopted with an `import` block: email sign-in without a password (email link), and authorized domains `localhost`, the Firebase domains, the Cloud Run URL and the custom domain. |
| Domain mapping | `app.<domain>` -> `api` | Cloud Run domain mapping (free). Move to a load balancer only if needed later. |
| Budget alert | billing account | Alerts at $10, $25, $50 per month. |

APIs to enable: run, artifactregistry, secretmanager, iam, iamcredentials, sts, cloudscheduler, compute
(for the VPC), firebase, identitytoolkit, logging, monitoring.

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
ENV PATH="/srv/.venv/bin:$PATH" STATIC_DIR=/srv/static SAMPLE_PROFILE_PATH=/srv/sample-profile.json
USER app
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
```

`--no-editable` installs `api` and `cvcore` into the venv as regular packages, so the runtime image needs
only the venv and the static files. The renderer's `pyproject.toml` is copied because uv resolves the
whole workspace lockfile.

`apps/renderer/Dockerfile`: same uv pattern without the web stage; copies `templates/` to `/templates`
and `apps/renderer/fonts/` to `/fonts`; runs as a non-root user; `CMD` runs uvicorn on port 8080.

Images are tagged with the git SHA and deployed by digest.

## OpenTofu layout

```
infra/
  bootstrap/                 applied once by hand per project, with local credentials
    main.tf                  APIs, state bucket, registry, Workload Identity pool + GitHub provider, deployer SA
  modules/
    cloud_run_service/       one module used for both api and renderer (image, sa, scaling, env, secrets, ingress, vpc egress)
    secret/                  secret + IAM accessor bindings
    bucket/
  envs/
    dev/  main.tf  auth.tf  versions.tf  variables.tf  outputs.tf  terraform.tfvars  backend.tf
    prod/ (M5)
  github/                    repository environments and their branch policies
```

- `bootstrap/` also enables the project's APIs, creates the Artifact Registry repository and the
  deployer service account with the roles `envs/*` need. Its own state started local and was moved to
  the state bucket (`tofu init -migrate-state`). People who may impersonate the deployer come from
  `TF_VAR_admin_members` (for example `'["user:you@example.com"]'`), never from a committed file, because
  the repository is public.
- `github/` holds repository settings that deploys rely on: the `dev` environment may only be used
  from `main`. Apply it by hand with `GITHUB_TOKEN=$(gh auth token) tofu apply`.
- State: GCS backend bucket `<project>-tofu-state` with versioning, created by `bootstrap/`, one prefix
  per stack (`bootstrap`, `envs/dev`, `github`).
- Providers: `google` and `google-beta` (Firebase and Identity Platform resources), versions pinned.
- `envs/*/main.tf` only composes modules; no inline resources except one-offs (VPC, scheduler).
- Image digests are input variables (`api_image`, `renderer_image`) set by CI, so OpenTofu owns the
  full service definition and there is no drift from `gcloud run deploy`.
- Secret values are never in OpenTofu. Tofu creates the secrets; values are added once with
  `gcloud secrets versions add`.
- The AI keys reach the api only for the secrets listed in `ai_keys` in `envs/dev/terraform.tfvars`.
  Add a key with `printf '%s' "$KEY" | gcloud secrets versions add anthropic-api-key --data-file=-`,
  then list `anthropic-api-key` there and push: Cloud Run refuses a secret that has no version.
- Neon is managed in the Neon console (project, branches, roles). Its connection strings go into Secret
  Manager. Managing Neon from OpenTofu is optional later.

## CI/CD (GitHub Actions)

Authentication to GCP uses Workload Identity Federation (`google-github-actions/auth` with the pool and
deployer service account from `bootstrap/`). No service-account JSON keys anywhere. The pool accepts
only this repository (by numeric repository and owner id), and the deployer trusts only jobs that run
in a listed GitHub environment (OIDC subject `repo:aduuna/cvitae:environment:dev`).

### `ci.yml` (pull requests and pushes)

Jobs run in parallel:

1. **python**: `astral-sh/setup-uv`, `uv sync --frozen`, `uv run ruff check .`, `uv run ruff format --check .`,
   `uv run ty check`, `uv run pytest --cov` with a `postgres:17` service container.
2. **web**: `oven-sh/setup-bun` and `astral-sh/setup-uv`, `bun install --frozen-lockfile`, `bun run check`,
   `bun run lint`, `bun run test`, `bun run build`. Then `bun run gen:api` and `git diff --exit-code` so the
   job fails if the committed API types are stale.
3. **templates**: renderer golden tests (every template x every fixture), uploads preview PNGs as artifacts.
4. **e2e**: Playwright against the built SPA and a mocked API.
5. **infra**: `opentofu/setup-opentofu`, `tofu fmt -check -recursive`, and `tofu validate` for every
   stack. (A `tofu plan` for `dev` posted on pull requests, with a read-only WIF role, is still to come.)

### `deploy.yml`

- Trigger: CI completing successfully for a push to `main` deploys `dev` (`workflow_run`), so a failing
  build never deploys; it can also be started by hand. Tag `v*` deploys `prod` (GitHub environment
  `prod` requires approval; M5).
- The project id, registry, WIF provider and deployer email are written in the workflow: they are ids,
  not secrets, and keeping them there means no repository variables to set by hand.
- Steps:
  1. Authenticate with WIF.
  2. Build and push `api` and `renderer` images to Artifact Registry (Docker Buildx with GitHub cache).
  3. Run migrations: `uv run --package api alembic upgrade head` with `DATABASE_URL_DIRECT` read from
     Secret Manager. Migrations must be backward compatible with the previous release (expand, then
     contract in a later release).
  4. `tofu apply -auto-approve -var api_image=<digest> -var renderer_image=<digest>` in `infra/envs/<env>`.
  5. Smoke test (`apps/api/scripts/smoke.py`): `GET /healthz`; `GET /me` without a token is refused;
     a test user (`smoke-test`, created with the Firebase Admin SDK) signs in with a custom token
     signed by the deployer, then `GET /me` and a template preview succeed, which proves Firebase
     verification and the api's OIDC call to the renderer; a direct call to the renderer is refused.

## Local development

`compose.yaml` runs Postgres 17 for development and tests:

```yaml
services:
  db:
    image: postgres:17
    environment: { POSTGRES_USER: vitae, POSTGRES_PASSWORD: vitae, POSTGRES_DB: vitae }
    ports: ["5432:5432"]
```

Run the api with `AUTH_MODE=dev`, `STORAGE_MODE=local`, `RENDERER_AUTH=none` and
`RENDERER_URL=http://localhost:8001`. The Vite dev server proxies `/api` to `localhost:8000`.
Provider keys can be set locally to try real AI calls; tests never need them.

## Cost at zero customers (rough)

Cloud Run, Artifact Registry, Secret Manager, Cloud Scheduler and GCS stay within or close to free tiers
at this scale, and Neon's free plan scales compute to zero. Expect a few dollars a month, mostly AI usage
during your own testing. The budget alert catches surprises.

## Security checklist

- Renderer: IAM invoker restricted to `api-sa` (no unauthenticated access), no internet egress, no
  secrets, resource limits (see `docs/BACKEND.md`).
- Least-privilege service accounts; no default compute service account in use.
- Secrets only in Secret Manager; mounted as environment variables at deploy.
- HTTPS only; HSTS and a strict Content Security Policy set by the api for the SPA (allow Firebase Auth
  domains and Paystack checkout redirect).
- Paystack webhook signature verified; Firebase tokens verified on every request.
- Uploads limited to 10 MB, PDF and DOCX by magic-byte check, stored under `uploads/<user_id>/`.
- Account deletion removes database rows (cascade) and the user's GCS prefix; a test covers both.
