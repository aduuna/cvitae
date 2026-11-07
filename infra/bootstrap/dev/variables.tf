# Personal emails stay out of this public repository: set it in the environment when applying,
# for example TF_VAR_admin_members='["user:you@example.com"]' tofu apply. No default, so an apply
# without it fails instead of silently removing the binding.
variable "admin_members" {
  description = "IAM members (user:...) who may impersonate the deployer."
  type        = list(string)
}
