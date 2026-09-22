"""Shared test data helpers.

Domain-specific factories (create_user, create_event, ...) are added here as
each module's models land (M1+). Use these instead of copied setup blocks —
see CLAUDE.md's Testing section.
"""

import secrets


def unique_suffix() -> str:
    return secrets.token_hex(4)


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}+{unique_suffix()}@example.com"
