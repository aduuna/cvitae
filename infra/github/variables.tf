variable "owner" {
  type    = string
  default = "aduuna"
}

variable "repository" {
  type    = string
  default = "cvitae"
}

variable "prod_reviewers" {
  description = "GitHub logins that approve a prod deploy (up to 6)."
  type        = list(string)
  default     = ["aduuna"]
}
