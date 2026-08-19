"""Unit tests for source snapshot delivery semantics."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _load_models_module():
    path = (
        Path(__file__).parents[1] / "custom_components" / "route_progress" / "models.py"
    )
    spec = importlib.util.spec_from_file_location("route_progress_models_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


models = _load_models_module()
PositionObservationState = models.PositionObservationState
TripSnapshot = models.TripSnapshot
classify_navigation_presence = models.classify_navigation_presence


def _snapshot(**changes):
    values = {
        "destination_name": "Work",
        "destination_latitude": 53.67,
        "destination_longitude": 10.10,
        "navigation_presence": "present",
        "latitude": 53.60,
        "longitude": 10.05,
        "speed_kmh": 30.0,
        "eta_minutes": 12.0,
    }
    values.update(changes)
    return TripSnapshot(**values)


class PositionObservationStateTest(unittest.TestCase):
    """Verify deduplication and truthful observation timestamps."""

    def test_observation_time_only_advances_with_coordinates(self) -> None:
        state = PositionObservationState()
        first = datetime(2026, 8, 14, 6, 0, tzinfo=UTC)
        later = first + timedelta(minutes=10)

        self.assertEqual(state.observe_position((53.60, 10.05), first), first)
        self.assertEqual(state.observe_position((53.60, 10.05), later), first)
        self.assertEqual(state.observe_position((53.61, 10.06), later), later)

    def test_position_returning_after_unavailable_is_a_new_observation(self) -> None:
        state = PositionObservationState()
        first = datetime(2026, 8, 14, 6, 0, tzinfo=UTC)
        later = first + timedelta(minutes=10)

        state.observe_position((53.60, 10.05), first)
        self.assertIsNone(state.observe_position(None, later))
        self.assertEqual(state.observe_position((53.60, 10.05), later), later)

    def test_payload_explicitly_distinguishes_navigation_presence(self) -> None:
        active = _snapshot().update_payload()
        self.assertEqual(active["navigation_presence"], "present")
        self.assertIn("destination", active)

        cleared = _snapshot(
            navigation_presence="absent",
            destination_name="",
            destination_latitude=None,
            destination_longitude=None,
        ).update_payload()
        self.assertEqual(cleared["navigation_presence"], "absent")
        self.assertNotIn("destination", cleared)

    def test_navigation_source_outage_is_not_a_cleared_route(self) -> None:
        self.assertEqual(
            classify_navigation_presence("unavailable", "home", "Work", 53.67, 10.10),
            "unknown",
        )
        self.assertEqual(
            classify_navigation_presence("none", "home", "", 53.67, 10.10),
            "absent",
        )
        self.assertEqual(
            classify_navigation_presence("Work", "home", "Work", 53.67, 10.10),
            "present",
        )

    def test_payload_includes_source_observation_time(self) -> None:
        observed = datetime(2026, 8, 18, 16, 7, tzinfo=UTC)
        payload = _snapshot(source_observed_at=observed).update_payload()
        self.assertEqual(payload["source_observed_at"], observed.isoformat())


if __name__ == "__main__":
    unittest.main()
