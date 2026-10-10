output "api_url" {
  value = module.api.uri
}

output "renderer_url" {
  value = module.renderer.uri
}

output "app_url" {
  description = "Where users open the app."
  value       = var.custom_domain == "" ? module.api.uri : "https://${var.custom_domain}"
}

output "firebase_api_key" {
  description = "The web API key (public; used by the smoke test to exchange a custom token)."
  value       = data.google_firebase_web_app_config.web.api_key
}
