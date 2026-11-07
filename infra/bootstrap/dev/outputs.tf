output "state_bucket" {
  value = module.bootstrap.state_bucket
}

output "registry" {
  description = "Image path prefix: <registry>/<image>:<tag>."
  value       = module.bootstrap.registry
}

output "deployer_email" {
  value = module.bootstrap.deployer_email
}

output "workload_identity_provider" {
  description = "For google-github-actions/auth."
  value       = module.bootstrap.workload_identity_provider
}
