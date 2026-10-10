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
