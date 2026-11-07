# Budget alerts on the billing account (docs/INFRA.md, GCP resources). Applied by hand with the
# owner's own credentials, never by CI: the deployer holds no billing roles, and a budget belongs
# to the billing account, not to one environment.
#
#   TF_VAR_billing_account=XXXXXX-XXXXXX tofu apply
#
# The caller needs Billing Account Costs Manager (or Administrator) on the billing account.
# Alerts email the billing account's administrators and users (the default recipients).

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
  # Where the Billing Budgets API is enabled and the calls are billed to.
  quota_project = var.project_ids[0]

  # One budget whose size is the largest alert; the others are fractions of it.
  budget_amount = max(var.alert_amounts...)
}

provider "google" {
  project               = local.quota_project
  billing_project       = local.quota_project
  user_project_override = true
}

resource "google_project_service" "billingbudgets" {
  project            = local.quota_project
  service            = "billingbudgets.googleapis.com"
  disable_on_destroy = false
}

data "google_project" "this" {
  for_each   = toset(var.project_ids)
  project_id = each.value
}

resource "google_billing_budget" "monthly" {
  billing_account = var.billing_account
  display_name    = "cvitae monthly spend"

  # Only the cvitae projects, so other projects on the same billing account do not trigger it.
  budget_filter {
    projects        = [for project in data.google_project.this : "projects/${project.number}"]
    calendar_period = "MONTH"
  }

  amount {
    specified_amount {
      currency_code = var.currency
      units         = tostring(local.budget_amount)
    }
  }

  dynamic "threshold_rules" {
    for_each = var.alert_amounts
    content {
      threshold_percent = threshold_rules.value / local.budget_amount
      spend_basis       = "CURRENT_SPEND"
    }
  }

  depends_on = [google_project_service.billingbudgets]
}
