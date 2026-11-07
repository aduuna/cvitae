# The dev environment: composes modules. Image digests come from CI (deploy.yml).

locals {
  # AI provider keys the api can receive, by secret id.
  ai_key_env = {
    "anthropic-api-key" = "ANTHROPIC_API_KEY"
    "gemini-api-key"    = "GEMINI_API_KEY"
    "mimo-api-key"      = "MIMO_API_KEY"
  }

  # Billing turns on once the Pro plan code is set (and paystack-secret-key has a value).
  billing = var.paystack_pro_plan_code != "" && var.custom_domain != ""
  billing_env = local.billing ? {
    PAYSTACK_PRO_PLAN_CODE = var.paystack_pro_plan_code
    PAYSTACK_CALLBACK_URL  = "https://${var.custom_domain}/app/settings?tab=billing"
  } : {}

  # The api checks the scheduler's OIDC token against its own public URL (PUBLIC_BASE_URL). The
  # scheduler needs that URL before the service exists, so it is the custom domain's.
  public_base_url = var.custom_domain == "" ? "" : "https://${var.custom_domain}"
  scheduler_env = local.public_base_url == "" ? {} : {
    PUBLIC_BASE_URL    = local.public_base_url
    SCHEDULER_SA_EMAIL = google_service_account.scheduler.email
  }

  api_sa      = "serviceAccount:${google_service_account.api.email}"
  renderer_sa = "serviceAccount:${google_service_account.renderer.email}"
  deployer_sa = "serviceAccount:deployer@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_service_account" "api" {
  account_id   = "api-sa"
  display_name = "api service"
}

# No roles: the renderer reads nothing and calls nothing.
resource "google_service_account" "renderer" {
  account_id   = "renderer-sa"
  display_name = "renderer service"
}

# No roles: its OIDC token only tells the api who is calling.
resource "google_service_account" "scheduler" {
  account_id   = "scheduler-sa"
  display_name = "Cloud Scheduler jobs"
}

module "uploads" {
  source        = "../../modules/bucket"
  name          = "${var.project_id}-uploads"
  location      = var.region
  object_admins = [local.api_sa]
  force_destroy = true
}

module "secrets" {
  source = "../../modules/secret"
  for_each = {
    "anthropic-api-key"   = [local.api_sa]
    "gemini-api-key"      = [local.api_sa]
    "mimo-api-key"        = [local.api_sa]
    "paystack-secret-key" = [local.api_sa]
    "database-url"        = [local.api_sa]
    # Migrations run in CI with the direct (unpooled) endpoint.
    "database-url-direct" = [local.deployer_sa]
  }
  name      = each.key
  accessors = each.value
}

# The renderer compiles user-supplied Typst, so it gets no internet: Direct VPC egress into a
# subnet with no NAT and no internet route.
module "renderer_vpc" {
  source = "../../modules/renderer_vpc"
  region = var.region
}

module "renderer" {
  source          = "../../modules/cloud_run_service"
  name            = "renderer"
  region          = var.region
  image           = var.renderer_image
  service_account = google_service_account.renderer.email
  # Ingress stays open, but Google rejects any request without an OIDC token for api-sa.
  invokers            = [local.api_sa]
  memory              = "1Gi"
  concurrency         = 4
  timeout_seconds     = 30
  health_path         = "/healthz"
  deletion_protection = false
  vpc_egress = {
    network    = module.renderer_vpc.network
    subnetwork = module.renderer_vpc.subnetwork
  }
}

module "api" {
  source          = "../../modules/cloud_run_service"
  name            = "api"
  region          = var.region
  image           = var.api_image
  service_account = google_service_account.api.email
  # Public: authentication is Firebase, at the application level.
  invokers            = ["allUsers"]
  memory              = "512Mi"
  concurrency         = 40
  timeout_seconds     = 300
  health_path         = "/api/v1/healthz"
  deletion_protection = false

  env = merge({
    ENV                  = "dev"
    AUTH_MODE            = "firebase"
    FIREBASE_PROJECT_ID  = var.project_id
    FIREBASE_API_KEY     = data.google_firebase_web_app_config.web.api_key
    FIREBASE_AUTH_DOMAIN = data.google_firebase_web_app_config.web.auth_domain
    FIREBASE_APP_ID      = google_firebase_web_app.web.app_id
    STORAGE_MODE         = "gcs"
    GCS_BUCKET           = module.uploads.name
    RENDERER_URL         = module.renderer.uri
    RENDERER_AUTH        = "oidc"
  }, local.billing_env, local.scheduler_env)
  secret_env = merge(
    { DATABASE_URL = module.secrets["database-url"].id },
    { for id in var.ai_keys : local.ai_key_env[id] => module.secrets[id].id },
    local.billing ? { PAYSTACK_SECRET_KEY = module.secrets["paystack-secret-key"].id } : {},
  )

  depends_on = [module.secrets]
}

# Deletes autosave versions older than 7 days (docs/BACKEND.md, API).
module "prune_versions" {
  count                 = local.public_base_url == "" ? 0 : 1
  source                = "../../modules/scheduler_job"
  name                  = "prune-versions"
  region                = var.region
  schedule              = "0 3 * * *"
  uri                   = "${local.public_base_url}/api/v1/internal/prune-versions"
  audience              = local.public_base_url
  service_account_email = google_service_account.scheduler.email
}

resource "google_cloud_run_domain_mapping" "api" {
  count    = var.custom_domain == "" ? 0 : 1
  name     = var.custom_domain
  location = var.region

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = module.api.name
  }
}
