# Firebase Authentication: the web app the SPA signs in with, and the sign-in configuration.
# Firebase was added to the project in the console, and the Google provider was enabled there
# (its OAuth client secret stays out of OpenTofu state).

resource "google_firebase_web_app" "web" {
  provider        = google-beta
  display_name    = "Chameleon vitae"
  deletion_policy = "ABANDON"
}

data "google_firebase_web_app_config" "web" {
  provider   = google-beta
  web_app_id = google_firebase_web_app.web.app_id
}

# The project's Auth configuration existed before OpenTofu; adopt it rather than create it.
import {
  to = google_identity_platform_config.auth
  id = "projects/${var.project_id}/config"
}

resource "google_identity_platform_config" "auth" {
  authorized_domains = concat(
    [
      "localhost",
      "${var.project_id}.firebaseapp.com",
      "${var.project_id}.web.app",
      trimprefix(module.api.uri, "https://"),
    ],
    var.custom_domain == "" ? [] : [var.custom_domain],
  )

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
