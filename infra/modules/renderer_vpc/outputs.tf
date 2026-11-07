output "network" {
  description = "Network name, for a service's vpc_egress."
  value       = google_compute_network.this.name
}

output "subnetwork" {
  description = "Subnetwork name, for a service's vpc_egress."
  value       = google_compute_subnetwork.this.name
}
