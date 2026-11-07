# Lives in the dev project's state bucket, like the stack that manages the repository settings.
terraform {
  backend "gcs" {
    bucket = "cvitae-511214-tofu-state"
    prefix = "billing"
  }
}
