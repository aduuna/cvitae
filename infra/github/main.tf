# Repository settings that deployments rely on. Applied by hand with a token that can administer
# the repository: GITHUB_TOKEN=$(gh auth token) tofu apply
#
# Only `main` may deploy to dev. The deployer trusts jobs in these environments (infra/bootstrap),
# so this policy is what stops a feature branch from deploying.

terraform {
  required_version = ">= 1.9"
  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.13"
    }
  }
}

provider "github" {
  owner = var.owner
}

resource "github_repository_environment" "dev" {
  repository  = var.repository
  environment = "dev"

  deployment_branch_policy {
    protected_branches     = false
    custom_branch_policies = true
  }
}

resource "github_repository_environment_deployment_policy" "dev_main" {
  repository     = var.repository
  environment    = github_repository_environment.dev.environment
  branch_pattern = "main"
}
