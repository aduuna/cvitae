variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "domain" {
  description = <<-EOT
    The production domain, without a scheme (for example example.com). The api is served at
    app.<domain>: add a CNAME for app to ghs.googlehosted.com at the DNS host, and verify the
    domain in Google Search Console for the identity that applies this stack. No default: an
    apply without it fails before it changes anything.
  EOT
  type        = string

  validation {
    condition     = can(regex("^([a-z0-9-]+\\.)+[a-z]{2,}$", var.domain))
    error_message = "domain is a bare domain name such as example.com."
  }
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
    only after paystack-secret-key has a value (a live key in prod).
  EOT
  type        = string
  default     = ""

  validation {
    condition     = var.paystack_pro_plan_code == "" || startswith(var.paystack_pro_plan_code, "PLN_")
    error_message = "paystack_pro_plan_code is a Paystack plan code (PLN_...)."
  }
}
