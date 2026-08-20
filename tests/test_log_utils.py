"""Unit tests for safe diagnostic logging."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def _load_log_utils_module():
    path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "route_progress"
        / "log_utils.py"
    )
    spec = importlib.util.spec_from_file_location("route_progress_log_utils_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


redact_secrets = _load_log_utils_module().redact_secrets


class RedactSecretsTest(unittest.TestCase):
    """Verify share credentials never reach formatted debug data."""

    def test_redacts_create_response_without_mutating_runtime_data(self) -> None:
        response = {
            "trip_id": "trip-1",
            "share_url": "https://route.example/t/super-secret-token",
            "status": "waiting_for_destination",
        }

        safe = redact_secrets(response)

        self.assertEqual(safe["share_url"], "<redacted>")
        self.assertEqual(safe["trip_id"], "trip-1")
        self.assertIn("super-secret-token", response["share_url"])

    def test_redacts_nested_secrets_case_insensitively(self) -> None:
        safe = redact_secrets(
            {
                "result": [
                    {"SHARE_URL": "secret"},
                    {"api_token": "secret", "destination": "Arbeit"},
                ]
            }
        )

        self.assertEqual(safe["result"][0]["SHARE_URL"], "<redacted>")
        self.assertEqual(safe["result"][1]["api_token"], "<redacted>")
        self.assertEqual(safe["result"][1]["destination"], "Arbeit")


if __name__ == "__main__":
    unittest.main()
