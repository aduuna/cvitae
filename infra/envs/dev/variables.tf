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

variable "paystack_pro_plan_code" {
  description = <<-EOT
    The monthly Pro plan from the Paystack dashboard (PLN_...); empty leaves billing off. Set it
    only after paystack-secret-key has a value. Needs custom_domain for Paystack's callback URL.
  EOT
  type        = string
  default     = ""

  validation {
    condition     = var.paystack_pro_plan_code == "" || startswith(var.paystack_pro_plan_code, "PLN_")
    error_message = "paystack_pro_plan_code is a Paystack plan code (PLN_...)."
  }
}
