"""Ids for items inside CV content (bullets, entries, sections)."""

import secrets


def new_id() -> str:
    """A random 12-character hex id. The frontend generates ids in the same format."""
    return secrets.token_hex(6)
