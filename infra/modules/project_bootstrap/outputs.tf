output "state_bucket" {
  value = google_storage_bucket.tofu_state.name
}

output "registry" {
  description = "Image path prefix: <registry>/<image>:<tag>."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "deployer_email" {
  value = google_service_account.deployer.email
}

output "workload_identity_provider" {
  description = "For google-github-actions/auth."
  value       = google_iam_workload_identity_pool_provider.github.name
}
