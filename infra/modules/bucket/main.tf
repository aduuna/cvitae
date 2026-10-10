# A private bucket: uniform access, public access prevention, no versioning.

terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
    }
  }
}

resource "google_storage_bucket" "this" {
  name                        = var.name
  location                    = var.location
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.force_destroy

  versioning {
    enabled = false
  }
}

resource "google_storage_bucket_iam_member" "object_admins" {
  for_each = toset(var.object_admins)
  bucket   = google_storage_bucket.this.name
  role     = "roles/storage.objectAdmin"
  member   = each.value
}
