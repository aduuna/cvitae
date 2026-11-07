# The billing account id is not committed: set TF_VAR_billing_account when applying.
variable "billing_account" {
  description = "Billing account id, like 012345-6789AB-CDEF01."
  type        = string
}

variable "project_ids" {
  description = "Projects the budget covers (dev and prod). The first one also hosts the Billing Budgets API."
  type        = list(string)

  validation {
    condition     = length(var.project_ids) > 0
    error_message = "List at least one project."
  }
}

variable "currency" {
  description = "Must match the billing account's currency."
  type        = string
  default     = "USD"
}

variable "alert_amounts" {
  description = "Monthly spend, in the currency, at which to send an alert."
  type        = list(number)
  default     = [10, 25, 50]

  validation {
    condition     = length(var.alert_amounts) > 0 && alltrue([for amount in var.alert_amounts : amount > 0 && amount == floor(amount)])
    error_message = "alert_amounts are positive whole numbers."
  }
}
