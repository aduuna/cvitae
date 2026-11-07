# The prod project. Use it with -var-file=prod.tfvars and the prod backend (docs/INFRA.md,
# Production). It sets every value terraform.tfvars (dev) sets, because terraform.tfvars is
# always loaded first and this file overrides it.
project_id           = "cvitae-prod"
github_repository    = "aduuna/cvitae"
github_repository_id = "1413058337"
github_owner_id      = "29348646"
github_environments  = ["prod"]
