# A Secret Manager secret and who may read it. Values are never in OpenTofu: add them with
# `gcloud secrets versions add <name> --data-file=-`.

terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
    }
  }
}

resource "google_secret_manager_secret" "this" {
  secret_id = var.name

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "accessors" {
  for_each  = toset(var.accessors)
  secret_id = google_secret_manager_secret.this.id
  role      = "roles/secretmanager.secretAccessor"
  member    = each.value
}
