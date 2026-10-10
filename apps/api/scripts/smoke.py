"""Smoke test for a deployed environment (deploy.yml runs it after `tofu apply`).

uv run --package api python apps/api/scripts/smoke.py --api-url ... --renderer-url ... \\
    --firebase-api-key ... --project-id ... --service-account deployer@<project>.iam...

Signs in a dedicated test user with a Firebase custom token signed by the service account, then
checks: the api is up, Firebase tokens are verified, the api can reach the renderer with its OIDC
token, and the renderer refuses callers without one.
"""

import argparse
import sys

import firebase_admin
import httpx
from firebase_admin import auth

SMOKE_UID = "smoke-test"
SMOKE_EMAIL = "smoke-test@cvitae.invalid"
SIGN_IN_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken"


def check(condition: bool, message: str) -> None:
    if not condition:
        sys.exit(f"FAILED: {message}")
    print(f"ok: {message}")


def id_token(project_id: str, service_account: str, api_key: str) -> str:
    app = firebase_admin.initialize_app(
        options={"projectId": project_id, "serviceAccountId": service_account}, name="smoke"
    )
    try:
        auth.update_user(SMOKE_UID, email=SMOKE_EMAIL, email_verified=True, app=app)
    except auth.UserNotFoundError:
        auth.create_user(uid=SMOKE_UID, email=SMOKE_EMAIL, email_verified=True, app=app)
    custom = auth.create_custom_token(SMOKE_UID, app=app).decode()
    response = httpx.post(
        SIGN_IN_URL,
        params={"key": api_key},
        json={"token": custom, "returnSecureToken": True},
        timeout=30,
    )
    response.raise_for_status()
    return str(response.json()["idToken"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--renderer-url", required=True)
    parser.add_argument("--firebase-api-key", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--service-account", required=True)
    args = parser.parse_args()

    with httpx.Client(base_url=args.api_url, timeout=60) as api:
        health = api.get("/api/v1/healthz")
        check(health.status_code == 200, "api /healthz answers")

        config = api.get("/api/v1/client-config").json()
        check(config["auth_mode"] == "firebase", "api uses Firebase sign-in")

        check(api.get("/api/v1/me").status_code == 401, "api refuses requests without a token")

        token = id_token(args.project_id, args.service_account, args.firebase_api_key)
        headers = {"Authorization": f"Bearer {token}"}
        me = api.get("/api/v1/me", headers=headers)
        check(me.status_code == 200, "api accepts a Firebase ID token")
        check(me.json()["email"] == SMOKE_EMAIL, "api knows the signed-in user")

        preview = api.get("/api/v1/templates/classic/preview", headers=headers)
        check(preview.status_code == 200, "api renders a preview through the renderer")
        check(preview.json()["page_count"] >= 1, "the preview has pages")

    # Not /healthz: Cloud Run reserves root paths ending in "z" at its front end.
    renderer = httpx.get(f"{args.renderer_url}/templates", timeout=30)
    check(renderer.status_code in (401, 403), "renderer refuses callers without an OIDC token")


if __name__ == "__main__":
    main()
