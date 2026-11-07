# The dev project's bootstrap, applied once by hand with local credentials (docs/INFRA.md,
# OpenTofu layout). The project, its state bucket and its variables live in this folder, so a bare
# `tofu apply` here can only ever touch the dev project and its own state.

terraform {
  required_version = ">= 1.9"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.6"
    }
  }
}

locals {
  project_id = "cvitae-511214"
  region     = "europe-west1"
}

provider "google" {
  project               = local.project_id
  region                = local.region
  billing_project       = local.project_id
  user_project_override = true
}

module "bootstrap" {
  source               = "../../modules/project_bootstrap"
  project_id           = local.project_id
  region               = local.region
  github_repository    = "aduuna/cvitae"
  github_repository_id = "1413058337"
  github_owner_id      = "29348646"
  github_environments  = ["dev"]
  admin_members        = var.admin_members
}

# This state was created when the stack was one root folder. These moves put its resources under
# the module without recreating anything: `tofu plan` must show only "has moved" lines (plus any
# new APIs and roles), never a create or destroy of an existing resource. Delete them once applied.
moved {
  from = google_project_service.apis
  to   = module.bootstrap.google_project_service.apis
}

moved {
  from = google_storage_bucket.tofu_state
  to   = module.bootstrap.google_storage_bucket.tofu_state
}

moved {
  from = google_artifact_registry_repository.images
  to   = module.bootstrap.google_artifact_registry_repository.images
}

moved {
  from = google_service_account.deployer
  to   = module.bootstrap.google_service_account.deployer
}

moved {
  from = google_project_iam_member.deployer
  to   = module.bootstrap.google_project_iam_member.deployer
}

moved {
  from = google_service_account_iam_member.deployer_signs_as_itself
  to   = module.bootstrap.google_service_account_iam_member.deployer_signs_as_itself
}

moved {
  from = google_service_account_iam_member.admins_impersonate_deployer
  to   = module.bootstrap.google_service_account_iam_member.admins_impersonate_deployer
}

moved {
  from = google_iam_workload_identity_pool.github
  to   = module.bootstrap.google_iam_workload_identity_pool.github
}

moved {
  from = google_iam_workload_identity_pool_provider.github
  to   = module.bootstrap.google_iam_workload_identity_pool_provider.github
}

moved {
  from = google_service_account_iam_member.github_deploys
  to   = module.bootstrap.google_service_account_iam_member.github_deploys
}
