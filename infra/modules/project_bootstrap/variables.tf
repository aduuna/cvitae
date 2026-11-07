variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "europe-west1"
}

variable "registry_name" {
  type    = string
  default = "cvitae"
}

variable "github_repository" {
  description = "owner/name of the repository whose workflows deploy."
  type        = string
}

variable "github_repository_id" {
  description = "Numeric repository id (GitHub API: GET /repos/{owner}/{repo})."
  type        = string
}

variable "github_owner_id" {
  description = "Numeric id of the repository owner."
  type        = string
}

variable "github_environments" {
  description = "GitHub environments whose jobs may act as the deployer."
  type        = list(string)
}

variable "admin_members" {
  description = "IAM members (user:...) who may impersonate the deployer."
  type        = list(string)
}
