# A Cloud Scheduler job that calls an HTTP endpoint with an OIDC token for a service account.
# The endpoint checks the token itself (the api allows any caller at the Cloud Run level).

terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
    }
  }
}

resource "google_cloud_scheduler_job" "this" {
  name             = var.name
  region           = var.region
  schedule         = var.schedule
  time_zone        = "Etc/UTC"
  attempt_deadline = "${var.attempt_deadline_seconds}s"

  retry_config {
    retry_count          = var.retry_count
    min_backoff_duration = "30s"
  }

  http_target {
    http_method = "POST"
    uri         = var.uri

    oidc_token {
      service_account_email = var.service_account_email
      audience              = var.audience
    }
  }
}
