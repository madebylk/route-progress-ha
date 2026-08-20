"""Helpers for safe Route Progress diagnostics."""

from __future__ import annotations

from typing import Any

_REDACTED = "<redacted>"
_SENSITIVE_KEYS = {
    "api_token",
    "cloudflare_client_secret",
    "share_url",
    "token",
}


def redact_secrets(value: Any) -> Any:
    """Return a log-safe copy of nested API data."""
    if isinstance(value, dict):
        return {
            key: (
                _REDACTED
                if str(key).casefold() in _SENSITIVE_KEYS
                else redact_secrets(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return value
