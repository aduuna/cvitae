variable "name" {
  type = string
}

variable "region" {
  type = string
}

variable "image" {
  description = "Image reference, by digest."
  type        = string
}

variable "service_account" {
  type = string
}

variable "ingress" {
  type    = string
  default = "INGRESS_TRAFFIC_ALL"
}

variable "invokers" {
  description = "IAM members allowed to call the service: [\"allUsers\"] makes it public."
  type        = list(string)
}

variable "env" {
  type    = map(string)
  default = {}
}

variable "secret_env" {
  description = "Environment variable name to Secret Manager secret id; always the latest version."
  type        = map(string)
  default     = {}
}

variable "cpu" {
  type    = string
  default = "1"
}

variable "memory" {
  type    = string
  default = "512Mi"
}

variable "concurrency" {
  type = number
}

variable "timeout_seconds" {
  type = number
}

variable "min_instances" {
  type    = number
  default = 0
}

variable "max_instances" {
  type    = number
  default = 3
}

variable "health_path" {
  type = string
}

variable "deletion_protection" {
  type    = bool
  default = true
}
