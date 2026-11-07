# The first apply runs with local state, because this bucket does not exist yet (docs/INFRA.md,
# Production): move this file aside, apply, move it back and run
# `tofu init -migrate-state -force-copy`.
terraform {
  backend "gcs" {
    bucket = "cvitae-prod-tofu-state"
    prefix = "bootstrap"
  }
}
