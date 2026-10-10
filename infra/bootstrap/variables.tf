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
  default     = ["dev"]
}

# Personal emails stay out of this public repository: set it in the environment when applying,
# for example TF_VAR_admin_members='["user:you@example.com"]' tofu apply. No default, so an apply
# without it fails instead of silently removing the binding.
variable "admin_members" {
  description = "IAM members (user:...) who may impersonate the deployer."
  type        = list(string)
}
