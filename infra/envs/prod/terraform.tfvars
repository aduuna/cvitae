project_id = "cvitae-prod"
region     = "europe-west1"

# The production domain; the api is served at app.<domain> (docs/INFRA.md, Production). Required:
# set it before the first deploy.
# domain = "example.com"

# Add each AI key's secret id here after giving the secret a value.
ai_keys = []

# The live Pro plan's code from the Paystack dashboard, once paystack-secret-key has a live key.
# Empty: no upgrades. Set the dashboard's webhook URL to https://app.<domain>/api/v1/webhooks/paystack.
paystack_pro_plan_code = ""
