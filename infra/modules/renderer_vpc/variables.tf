variable "region" {
  type = string
}

variable "name" {
  type    = string
  default = "cvitae-vpc"
}

variable "subnet_name" {
  type    = string
  default = "renderer-egress"
}

variable "ip_cidr_range" {
  description = "Direct VPC egress needs at least a /26."
  type        = string
  default     = "10.10.0.0/26"
}
