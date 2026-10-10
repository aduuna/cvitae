# Infrastructure

Goal: near-zero cost at zero customers, two containers, no clusters, everything reproducible with
OpenTofu and deployed by GitHub Actions.

## Environments

| Env | GCP project | Neon | Deploys |
|---|---|---|---|
| `local` | none | Postgres in `compose.yaml` (or a personal Neon branch) | `fastapi dev`, `bun run dev` |
| `dev` | `vitae-dev` | Neon project `vitae`, branch `dev` | every push to `main` |
| `prod` | `vitae-prod` | Neon project `vitae`, branch `main` | tags `v*`, behind a GitHub environment approval |

Region: `europe-west1` for Cloud Run, Artifact Registry and GCS (supports Cloud Run domain mappings and
is close to both Europe and Africa). Neon region: AWS `eu-central-1` (Frankfurt), the closest Neon region.

## GCP resources (per project)

| Resource | Name | Settings |
|---|---|---|
| Artifact Registry (Docker) | `vitae` | Cleanup policy: keep the 10 most recent images per package |
| Cloud Run service | `api` | Public (`allUsers` invoker; auth is Firebase at app level). Min 0, max 3 instances, 1 vCPU, 512 MiB, concurrency 40, request timeout 300 s, CPU only during requests. Service account `api-sa`. |
| Cloud Run service | `renderer` | Ingress `all`, but IAM invoker granted only to `api-sa`, so Google rejects any request without a valid OIDC token for that account before it reaches the container. Min 0, max 3, 1 vCPU, 1 GiB, concurrency 4, timeout 30 s. Service account `renderer-sa` with no roles. Direct VPC egress with `ALL_TRAFFIC` into a subnet that has no Cloud NAT, so it has no internet access. (Internal-only ingress would force the api's traffic through the VPC and require Cloud NAT for its calls to Neon, the AI providers and Paystack; not worth it at this stage.) |
| VPC | `vitae-vpc` with subnet `renderer-egress` (`10.10.0.0/26`) | No Cloud NAT, no routes to the internet. Exists only to cut the renderer off. |
| GCS bucket | `<project>-uploads` | Uniform access, public access prevention enforced, versioning off, lifecycle: none (user deletes remove objects). `api-sa` has `roles/storage.objectAdmin` on this bucket only. |
| Secret Manager | `anthropic-api-key`, `gemini-api-key`, `paystack-secret-key`, `database-url`, `database-url-direct` | `api-sa` can access all except `database-url-direct`; the CI deployer can access `database-url-direct` for migrations. |
| Cloud Scheduler | `prune-versions` (daily 03:00 UTC) | Calls `POST /api/v1/internal/prune-versions` on `api` with an OIDC token from `scheduler-sa`. |
| Firebase / Identity Platform | project-level | Providers: Google, Email link. Authorized domains: the Cloud Run URL and the custom domain. |
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
# 1. Build the SPA with bun
FROM oven/bun:1 AS web
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
ENV PATH="/srv/.venv/bin:$PATH" STATIC_DIR=/srv/static
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
    main.tf                  state bucket, Workload Identity pool + GitHub provider, deployer SA
  modules/
    cloud_run_service/       one module used for both api and renderer (image, sa, scaling, env, secrets, ingress, vpc egress)
    secret/                  secret + IAM accessor bindings
    bucket/
  envs/
    dev/  main.tf  variables.tf  terraform.tfvars  backend.tf
    prod/ main.tf  variables.tf  terraform.tfvars  backend.tf
```

- State: GCS backend bucket `<project>-tofu-state` with versioning, created by `bootstrap/`.
- Providers: `google` and `google-beta` (Firebase and Identity Platform resources), versions pinned.
- `envs/*/main.tf` only composes modules; no inline resources except one-offs (VPC, scheduler).
- Image digests are input variables (`api_image`, `renderer_image`) set by CI, so OpenTofu owns the
  full service definition and there is no drift from `gcloud run deploy`.
- Secret values are never in OpenTofu. Tofu creates the secrets; values are added once with
  `gcloud secrets versions add`.
- Neon is managed in the Neon console (project, branches, roles). Its connection strings go into Secret
  Manager. Managing Neon from OpenTofu is optional later.

## CI/CD (GitHub Actions)

Authentication to GCP uses Workload Identity Federation (`google-github-actions/auth` with the pool and
deployer service account from `bootstrap/`). No service-account JSON keys anywhere.

### `ci.yml` (pull requests and pushes)

Jobs run in parallel:

1. **python**: `astral-sh/setup-uv`, `uv sync --frozen`, `uv run ruff check .`, `uv run ruff format --check .`,
   `uv run ty check`, `uv run pytest --cov` with a `postgres:17` service container.
2. **web**: `oven-sh/setup-bun` and `astral-sh/setup-uv`, `bun install --frozen-lockfile`, `bun run check`,
   `bun run lint`, `bun run test`, `bun run build`. Then `bun run gen:api` and `git diff --exit-code` so the
   job fails if the committed API types are stale.
3. **templates**: renderer golden tests (every template x every fixture), uploads preview PNGs as artifacts.
4. **e2e**: Playwright against the built SPA and a mocked API.
5. **infra**: `opentofu/setup-opentofu`, `tofu fmt -check -recursive`, `tofu validate`, and `tofu plan` for
   `dev` (read-only WIF role), posted as a PR comment.

### `deploy.yml`

- Trigger: push to `main` deploys `dev`; tag `v*` deploys `prod` (GitHub environment `prod` requires approval).
- Steps:
  1. Authenticate with WIF.
  2. Build and push `api` and `renderer` images to Artifact Registry (Docker Buildx with GitHub cache).
  3. Run migrations: `uv run --package api alembic upgrade head` with `DATABASE_URL_DIRECT` read from
     Secret Manager. Migrations must be backward compatible with the previous release (expand, then
     contract in a later release).
  4. `tofu apply -auto-approve -var api_image=<digest> -var renderer_image=<digest>` in `infra/envs/<env>`.
  5. Smoke test: `GET /healthz` on the api URL and one authenticated preview call with a test user
     (dev only).

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
