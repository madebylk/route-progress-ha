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
SnapshotDeliveryState = models.SnapshotDeliveryState
TripSnapshot = models.TripSnapshot


def _snapshot(**changes):
    values = {
        "destination_name": "Work",
        "destination_latitude": 53.67,
        "destination_longitude": 10.10,
        "latitude": 53.60,
        "longitude": 10.05,
        "speed_kmh": 30.0,
    }
    values.update(changes)
    return TripSnapshot(**values)


class SnapshotDeliveryStateTest(unittest.TestCase):
    """Verify deduplication and truthful observation timestamps."""

    def test_observation_time_only_advances_with_coordinates(self) -> None:
        state = SnapshotDeliveryState()
        first = datetime(2026, 8, 14, 6, 0, tzinfo=UTC)
        later = first + timedelta(minutes=10)

        self.assertEqual(state.observe_position((53.60, 10.05), first), first)
        self.assertEqual(state.observe_position((53.60, 10.05), later), first)
        self.assertEqual(state.observe_position((53.61, 10.06), later), later)

    def test_position_returning_after_unavailable_is_a_new_observation(self) -> None:
        state = SnapshotDeliveryState()
        first = datetime(2026, 8, 14, 6, 0, tzinfo=UTC)
        later = first + timedelta(minutes=10)

        state.observe_position((53.60, 10.05), first)
        self.assertIsNone(state.observe_position(None, later))
        self.assertEqual(state.observe_position((53.60, 10.05), later), later)

    def test_delivery_key_ignores_timestamp_but_includes_telemetry(self) -> None:
        state = SnapshotDeliveryState()
        first = _snapshot(position_observed_at=datetime(2026, 8, 14, 6, 0, tzinfo=UTC))
        state.mark_sent(first)

        refreshed = _snapshot(
            position_observed_at=datetime(2026, 8, 14, 7, 0, tzinfo=UTC)
        )
        self.assertFalse(state.has_changes(refreshed))
        self.assertTrue(state.has_changes(_snapshot(speed_kmh=0.0)))
        self.assertTrue(state.has_changes(_snapshot(destination_name="Home")))

    def test_reset_forces_delivery_for_a_new_trip(self) -> None:
        state = SnapshotDeliveryState()
        snapshot = _snapshot()
        state.mark_sent(snapshot)
        self.assertFalse(state.has_changes(snapshot))

        state.reset_delivery()
        self.assertTrue(state.has_changes(snapshot))


if __name__ == "__main__":
    unittest.main()
