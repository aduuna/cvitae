terraform {
  backend "gcs" {
    bucket = "cvitae-511214-tofu-state"
    prefix = "github"
  }
}
