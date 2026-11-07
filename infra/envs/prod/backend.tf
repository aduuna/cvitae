terraform {
  # The prod project's own state bucket, created by infra/bootstrap applied to that project.
  backend "gcs" {
    bucket = "cvitae-prod-tofu-state"
    prefix = "envs/prod"
  }
}
