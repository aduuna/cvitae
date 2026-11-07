variable "name" {
  type = string
}

variable "region" {
  type = string
}

variable "schedule" {
  description = "Cron expression, in UTC."
  type        = string
}

variable "uri" {
  description = "Full URL to POST to."
  type        = string
}

variable "audience" {
  description = "The OIDC token's audience; the endpoint compares it with its own public URL."
  type        = string
}

variable "service_account_email" {
  description = "Service account the OIDC token is issued for."
  type        = string
}

variable "attempt_deadline_seconds" {
  type    = number
  default = 180
}

variable "retry_count" {
  type    = number
  default = 2
}
