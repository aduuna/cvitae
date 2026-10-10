variable "name" {
  type = string
}

variable "accessors" {
  description = "IAM members allowed to read the secret's versions."
  type        = list(string)
  default     = []
}
