"""Helpers for keeping personal data out of places it does not belong.

Our users are children, and logs have no retention policy - an e-mail address
written to a log file outlives the account it belonged to. Everything that has
to identify a user in a log line goes through here first.

The masking format matches what app/groups.py has always used ("abc***@***"),
so existing log greps keep working; it lives here now so there is one
implementation instead of the pattern being retyped at every call site.
"""

from typing import Optional


def mask_email(email: Optional[str]) -> str:
    """Mask an e-mail for logging: "jan.kowalski@example.com" -> "jan***@***".

    Keeps the first three characters, which is enough to correlate lines in one
    incident, and drops everything that would identify the person or their
    provider.
    """
    if not email:
        return "<none>"
    return f"{email[:3]}***@***"


def mask_user_id(user_id: Optional[str]) -> str:
    """Mask a Google sub for logging: keeps a short, non-identifying prefix.

    Matches the `user_id[:8]}...` convention already used in submission logs.
    """
    if not user_id:
        return "<none>"
    return f"{user_id[:8]}..."
