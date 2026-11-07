terraform {
  # The prod project's own state bucket, created by infra/bootstrap/prod.
  backend "gcs" {
    bucket = "cvitae-prod-tofu-state"
    prefix = "envs/prod"
  }
}
