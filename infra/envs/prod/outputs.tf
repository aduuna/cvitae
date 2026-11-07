output "api_url" {
  value = module.api.uri
}

output "renderer_url" {
  value = module.renderer.uri
}

output "app_url" {
  description = "Where users open the app."
  value       = local.public_base_url
}

output "firebase_api_key" {
  description = "The web API key (public; used by the smoke test to exchange a custom token)."
  value       = data.google_firebase_web_app_config.web.api_key
}

output "dns_records" {
  description = "Records to create at the DNS host for app.<domain> (Cloud Run domain mapping)."
  value       = try(google_cloud_run_domain_mapping.api.status[0].resource_records, [])
}
