# The first apply ran with local state; `tofu init -migrate-state` then moved it here.
terraform {
  backend "gcs" {
    bucket = "cvitae-511214-tofu-state"
    prefix = "bootstrap"
  }
}
