# The prod project's bootstrap, applied once by hand with local credentials (docs/INFRA.md,
# Production). The project, its state bucket and its variables live in this folder, so a bare
# `tofu apply` here can only ever touch the prod project and its own state.

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
  project_id = "cvitae-prod"
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
  github_environments  = ["prod"]
  admin_members        = var.admin_members
}
