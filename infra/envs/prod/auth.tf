# Firebase Authentication: the web app the SPA signs in with, and the sign-in configuration.
# As in dev, Firebase is added to the project and the Google provider enabled in the console first
# (its OAuth client secret stays out of OpenTofu state); that creates the Auth configuration,
# which the first apply adopts.

resource "google_firebase_web_app" "web" {
  provider        = google-beta
  display_name    = "Chameleon vitae"
  deletion_policy = "ABANDON"
}

data "google_firebase_web_app_config" "web" {
  provider   = google-beta
  web_app_id = google_firebase_web_app.web.app_id
}

import {
  to = google_identity_platform_config.auth
  id = "projects/${var.project_id}/config"
}

resource "google_identity_platform_config" "auth" {
  # No localhost in prod.
  authorized_domains = [
    "${var.project_id}.firebaseapp.com",
    "${var.project_id}.web.app",
    trimprefix(module.api.uri, "https://"),
    local.app_host,
  ]

  sign_in {
    # Email link (passwordless) sign-in; Google is the other provider. password_required = false
    # also accepts passwords, used only by the store review account (apps/api/scripts/review_account.py).
    email {
      enabled           = true
      password_required = false
    }

    phone_number {
      enabled = false
    }
  }
}
