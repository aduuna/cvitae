variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "custom_domain" {
  description = "Hostname mapped to the api (CNAME to ghs.googlehosted.com); empty for none."
  type        = string
  default     = ""
}

variable "api_image" {
  description = "api image by digest; set by CI."
  type        = string
}

variable "renderer_image" {
  description = "renderer image by digest; set by CI."
  type        = string
}

variable "ai_keys" {
  description = <<-EOT
    AI provider keys to pass to the api, by secret id. List a secret only after it has a value
    (gcloud secrets versions add <id> --data-file=-): a secret without one fails the deploy.
  EOT
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for id in var.ai_keys : contains(["anthropic-api-key", "gemini-api-key", "mimo-api-key"], id)])
    error_message = "ai_keys may list anthropic-api-key, gemini-api-key and mimo-api-key only."
  }
}
