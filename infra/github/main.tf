# Repository settings that deployments rely on. Applied by hand with a token that can administer
# the repository: GITHUB_TOKEN=$(gh auth token) tofu apply
#
# Only `main` may deploy to dev, and only a version tag to prod. The deployers trust jobs in these
# environments (infra/bootstrap), so these policies are what stop a feature branch from deploying.

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

# Prod deploys only from a version tag, and only after a reviewer approves the run. Administrators
# cannot skip the approval. deploy.yml also requires the tagged commit to be on main and to have
# passed CI. Reviewers may approve their own tag: with one maintainer, blocking self-review would
# block every release.
data "github_user" "prod_reviewers" {
  for_each = toset(var.prod_reviewers)
  username = each.value
}

resource "github_repository_environment" "prod" {
  repository        = var.repository
  environment       = "prod"
  can_admins_bypass = false

  reviewers {
    users = [for reviewer in data.github_user.prod_reviewers : reviewer.id]
  }

  deployment_branch_policy {
    protected_branches     = false
    custom_branch_policies = true
  }
}

resource "github_repository_environment_deployment_policy" "prod_tags" {
  repository  = var.repository
  environment = github_repository_environment.prod.environment
  tag_pattern = "v*"
}

# Only repository admins may create, move or delete a release tag. The environment's tag policy
# and deploy.yml's verify-tag job both run from the tagged commit's own workflow files, so a writer
# could tag an unmerged commit that weakens them; this rule is enforced outside the tagged code.
# The approver of a prod run still checks that the commit is on main (docs/INFRA.md, Production).
resource "github_repository_ruleset" "release_tags" {
  name        = "release-tags"
  repository  = var.repository
  target      = "tag"
  enforcement = "active"

  conditions {
    ref_name {
      include = ["refs/tags/v*"]
      exclude = []
    }
  }

  # The repository admin role (a personal repository's owner).
  bypass_actors {
    actor_id    = 5
    actor_type  = "RepositoryRole"
    bypass_mode = "always"
  }

  rules {
    creation = true
    update   = true
    deletion = true
  }
}
