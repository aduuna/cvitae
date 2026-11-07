# A VPC that exists only to cut a service off from the internet (docs/INFRA.md, GCP resources).
# The renderer's instances join the subnet with Direct VPC egress and all traffic routed into the
# VPC. The network has no Cloud NAT, no router and no default route, and the subnet has no Private
# Google Access, so nothing leaves it.

terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
    }
  }
}

resource "google_compute_network" "this" {
  name                    = var.name
  auto_create_subnetworks = false
  # A custom-mode network starts with a route to the internet gateway; this removes it.
  delete_default_routes_on_create = true
}

resource "google_compute_subnetwork" "this" {
  name                     = var.subnet_name
  region                   = var.region
  network                  = google_compute_network.this.id
  ip_cidr_range            = var.ip_cidr_range
  private_ip_google_access = false
}
