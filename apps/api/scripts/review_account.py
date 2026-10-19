"""Creates the account store reviewers sign in with, or gives it a new password.

gcloud auth application-default login
gcloud auth application-default set-quota-project <project>
uv run --package api python apps/api/scripts/review_account.py --project-id <project>

The account is the Firebase user `cvitae-review` (cvitae-review@aduuna.dev by default), with a
password and a verified email, which the api requires. Each run prints a new random password; the
old one stops working. Reviewers sign in at <app>/login?password, the only page with a password
form. The account's users row is created at its first sign-in, as anyone's is, so the script needs
Google credentials that may manage the project's Firebase users (a project owner's), not the
database.
"""

import argparse
import secrets

import firebase_admin
from firebase_admin import auth

REVIEW_UID = "cvitae-review"
REVIEW_EMAIL = "cvitae-review@aduuna.dev"


def new_password() -> str:
    return secrets.token_urlsafe(18)


def set_up(app: firebase_admin.App, email: str, password: str) -> bool:
    """Creates the review user, or resets it to this email and password. True when created."""
    try:
        auth.update_user(
            REVIEW_UID,
            email=email,
            password=password,
            email_verified=True,
            disabled=False,
            app=app,
        )
    except auth.UserNotFoundError:
        auth.create_user(
            uid=REVIEW_UID, email=email, password=password, email_verified=True, app=app
        )
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--email", default=REVIEW_EMAIL)
    args = parser.parse_args()

    app = firebase_admin.initialize_app(options={"projectId": args.project_id}, name="review")
    password = new_password()
    created = set_up(app, args.email, password)
    print(f"{'Created' if created else 'Reset'} {REVIEW_UID}")
    print(f"email:    {args.email}")
    print(f"password: {password}")


if __name__ == "__main__":
    main()
