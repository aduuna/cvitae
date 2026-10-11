project_id    = "cvitae-511214"
region        = "europe-west1"
custom_domain = "cvitae.aduuna.dev"

# Add each AI key's secret id here after giving the secret a value.
ai_keys = ["anthropic-api-key", "gemini-api-key", "mimo-api-key"]

# The Pro plan's code from the Paystack dashboard, once paystack-secret-key has a value. Empty: no
# upgrades. Set the dashboard's webhook URL to https://<custom_domain>/api/v1/webhooks/paystack.
paystack_pro_plan_code = "PLN_yoffbuwnj2uxs10"
