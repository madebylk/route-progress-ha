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
DestinationObservation = models.DestinationObservation
DestinationObservationState = models.DestinationObservationState
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

    def test_incomplete_navigation_omits_only_navigation_zero_sentinels(self) -> None:
        payload = _snapshot(
            # The cached destination can truthfully restore `present` while
            # Tessie's raw navigation metrics are still incomplete.
            navigation_presence="present",
            navigation_data_complete=False,
            eta_minutes=0,
            distance_km=0,
            battery_at_arrival=0,
            traffic_delay_minutes=0,
            charging_minutes=0,
            is_charging=False,
        ).update_payload()

        self.assertNotIn("eta_minutes", payload)
        self.assertNotIn("distance_km", payload)
        self.assertNotIn("battery_at_arrival", payload)
        self.assertEqual(payload["traffic_delay_minutes"], 0)
        self.assertEqual(payload["charging_minutes"], 0)
        self.assertIs(payload["is_charging"], False)

    def test_complete_navigation_preserves_legitimate_arrival_zeros(self) -> None:
        payload = _snapshot(
            eta_minutes=0,
            distance_km=0,
            battery_at_arrival=0,
        ).update_payload()

        self.assertEqual(payload["eta_minutes"], 0)
        self.assertEqual(payload["distance_km"], 0)
        self.assertEqual(payload["battery_at_arrival"], 0)


class DestinationObservationStateTest(unittest.TestCase):
    """Verify coherent snapshots across split Tessie destination entities."""

    def setUp(self) -> None:
        self.state = DestinationObservationState()
        self.first = datetime(2026, 8, 20, 6, 28, tzinfo=UTC)

    def observe(
        self,
        source: str,
        position: str,
        name: str,
        latitude: float | None,
        longitude: float | None,
        *,
        name_time: datetime | None = None,
        position_time: datetime | None = None,
    ) -> DestinationObservation:
        return self.state.observe(
            source,
            position,
            name,
            latitude,
            longitude,
            name_time or self.first,
            position_time or self.first,
        )

    def test_same_destination_recovers_from_explicit_absence(self) -> None:
        complete = self.observe("Arbeit", "home", "Arbeit", 53.67, 10.10)
        self.assertEqual(complete.navigation_presence, "present")
        self.assertTrue(complete.navigation_data_complete)

        absent = self.observe("none", "unavailable", "", None, None)
        self.assertEqual(absent.navigation_presence, "absent")
        self.assertIsNone(absent.latitude)

        recovered = self.observe("Arbeit", "unavailable", "Arbeit", None, None)
        self.assertEqual(recovered.navigation_presence, "present")
        self.assertFalse(recovered.navigation_data_complete)
        self.assertEqual((recovered.latitude, recovered.longitude), (53.67, 10.10))

    def test_explicit_absence_wins_even_if_position_still_has_coordinates(self) -> None:
        self.observe("Arbeit", "home", "Arbeit", 53.67, 10.10)

        absent = self.observe("none", "home", "", 53.67, 10.10)
        self.assertEqual(absent.navigation_presence, "absent")
        self.assertEqual(absent.name, "")
        self.assertIsNone(absent.latitude)

    def test_same_destination_recovers_after_unknown_outage(self) -> None:
        self.observe("Arbeit", "home", "Arbeit", 53.67, 10.10)
        outage = self.observe("unavailable", "unavailable", "", None, None)
        self.assertEqual(outage.navigation_presence, "unknown")

        recovered = self.observe(" Arbeit ", "unavailable", "Arbeit", None, None)
        self.assertEqual(recovered.navigation_presence, "present")
        self.assertEqual((recovered.latitude, recovered.longitude), (53.67, 10.10))

    def test_different_destination_never_reuses_cached_coordinates(self) -> None:
        self.observe("Arbeit", "home", "Arbeit", 53.67, 10.10)
        self.observe("none", "unavailable", "", None, None)

        other = self.observe("Juka Dojo", "unavailable", "Juka Dojo", None, None)
        self.assertEqual(other.navigation_presence, "unknown")
        self.assertIsNone(other.latitude)

    def test_different_destination_waits_for_fresh_position(self) -> None:
        self.observe("Arbeit", "home", "Arbeit", 53.67, 10.10)
        changed = self.first + timedelta(minutes=1)

        stale = self.observe(
            "Juka Dojo",
            "home",
            "Juka Dojo",
            53.67,
            10.10,
            name_time=changed,
            position_time=self.first,
        )
        self.assertEqual(stale.navigation_presence, "unknown")

        fresh = self.observe(
            "Juka Dojo",
            "home",
            "Juka Dojo",
            53.61,
            10.15,
            name_time=changed,
            # A changed valid point itself proves the position refreshed, even
            # if HA delivered the split position entity first.
            position_time=self.first,
        )
        self.assertEqual(fresh.navigation_presence, "present")
        self.assertEqual((fresh.latitude, fresh.longitude), (53.61, 10.15))

    def test_new_name_at_same_coordinates_requires_refreshed_position(self) -> None:
        self.observe("Arbeit", "home", "Arbeit", 53.67, 10.10)
        changed = self.first + timedelta(minutes=1)

        refreshed = self.observe(
            "Firmenparkplatz",
            "home",
            "Firmenparkplatz",
            53.67,
            10.10,
            name_time=changed,
            position_time=changed,
        )
        self.assertEqual(refreshed.navigation_presence, "present")

    def test_other_then_original_requires_original_coordinates_again(self) -> None:
        self.observe("Arbeit", "home", "Arbeit", 53.67, 10.10)
        other_time = self.first + timedelta(minutes=1)
        self.observe(
            "Juka Dojo",
            "home",
            "Juka Dojo",
            53.61,
            10.15,
            name_time=other_time,
            position_time=other_time,
        )

        work_again = self.observe(
            "Arbeit",
            "unavailable",
            "Arbeit",
            None,
            None,
            name_time=other_time + timedelta(minutes=1),
        )
        self.assertEqual(work_again.navigation_presence, "unknown")
        self.assertIsNone(work_again.latitude)

        work_time = other_time + timedelta(minutes=1)
        refreshed_work = self.observe(
            "Arbeit",
            "home",
            "Arbeit",
            53.67,
            10.10,
            name_time=work_time,
            position_time=work_time + timedelta(seconds=1),
        )
        self.assertEqual(refreshed_work.navigation_presence, "present")
        self.assertEqual(
            (refreshed_work.latitude, refreshed_work.longitude), (53.67, 10.10)
        )

    def test_initial_snapshot_allows_different_entity_timestamps(self) -> None:
        observation = self.observe(
            "Arbeit",
            "home",
            "Arbeit",
            53.67,
            10.10,
            name_time=self.first + timedelta(minutes=1),
            position_time=self.first,
        )
        self.assertEqual(observation.navigation_presence, "present")


if __name__ == "__main__":
    unittest.main()
