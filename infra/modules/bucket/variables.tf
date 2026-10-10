variable "name" {
  type = string
}

variable "location" {
  type = string
}

variable "object_admins" {
  type    = list(string)
  default = []
}

variable "force_destroy" {
  type    = bool
  default = false
}
