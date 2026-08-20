"""Data models used by Route Progress."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


def classify_navigation_presence(
    destination_source_state: str | None,
    destination_position_state: str | None,
    destination_name: str,
    latitude: float | None,
    longitude: float | None,
) -> str:
    """Describe only what the configured entities currently prove."""
    destination_state = (destination_source_state or "unavailable").strip().lower()
    position_state = (destination_position_state or "unavailable").strip().lower()
    if destination_state in {"unknown", "unavailable"}:
        return "unknown"
    if destination_state in {"", "none"}:
        return "absent"
    if position_state in {"unknown", "unavailable"} or not destination_name:
        return "unknown"
    return "present" if _valid_point(latitude, longitude) else "unknown"


def _destination_key(name: str) -> str:
    """Normalize a destination name for identity comparisons only."""
    return " ".join(name.split()).casefold()


@dataclass(frozen=True, slots=True)
class DestinationObservation:
    """One coherent observation of the configured destination entities."""

    name: str
    latitude: float | None
    longitude: float | None
    navigation_presence: str
    navigation_data_complete: bool


@dataclass(slots=True)
class DestinationObservationState:
    """Stabilize split destination-name and destination-position entities.

    Some providers briefly make the position entity unavailable when a
    destination disappears and then restore the same destination name without
    refreshing that position entity. A complete observation may bridge that
    gap, but only while no different destination name was observed.
    """

    complete_name: str = ""
    complete_latitude: float | None = None
    complete_longitude: float | None = None
    observed_name_key: str | None = None

    def observe(
        self,
        destination_source_state: str | None,
        destination_position_state: str | None,
        destination_name: str,
        latitude: float | None,
        longitude: float | None,
        destination_updated_at: datetime | None = None,
        position_updated_at: datetime | None = None,
    ) -> DestinationObservation:
        """Return a coherent destination without inferring driver intent."""
        source_state = (destination_source_state or "unavailable").strip().lower()
        position_state = (
            destination_position_state or "unavailable"
        ).strip().lower()
        name = destination_name.strip()

        if source_state in {"unknown", "unavailable"}:
            return DestinationObservation("", None, None, "unknown", False)
        if source_state in {"", "none"}:
            self.observed_name_key = None
            return DestinationObservation("", None, None, "absent", False)
        if not name:
            return DestinationObservation("", None, None, "unknown", False)

        name_key = _destination_key(name)
        complete_key = _destination_key(self.complete_name)
        same_as_complete = bool(complete_key) and name_key == complete_key
        different_name = (
            (self.observed_name_key is not None and name_key != self.observed_name_key)
            or (bool(complete_key) and name_key != complete_key)
        )

        position_available = position_state not in {"unknown", "unavailable"}
        point_valid = _valid_point(latitude, longitude)
        if not position_available or not point_valid:
            self.observed_name_key = name_key
            if same_as_complete and not different_name:
                return DestinationObservation(
                    name,
                    self.complete_latitude,
                    self.complete_longitude,
                    "present",
                    False,
                )
            return DestinationObservation(name, None, None, "unknown", False)

        # A different name must not be paired with coordinates left behind by
        # the previous destination. Changed coordinates prove a new complete
        # position even when the provider updates its split entities in either
        # order. If the coordinates happen to be identical, HA State timestamps
        # must prove that the position entity refreshed with the new name.
        same_as_complete_point = (
            latitude == self.complete_latitude
            and longitude == self.complete_longitude
        )
        position_refreshed_with_name = (
            destination_updated_at is not None
            and position_updated_at is not None
            and position_updated_at >= destination_updated_at
        )
        if (
            different_name
            and same_as_complete_point
            and not position_refreshed_with_name
        ):
            self.observed_name_key = name_key
            return DestinationObservation(name, None, None, "unknown", False)

        self.complete_name = name
        self.complete_latitude = latitude
        self.complete_longitude = longitude
        self.observed_name_key = name_key
        return DestinationObservation(name, latitude, longitude, "present", True)


@dataclass(slots=True)
class TripSnapshot:
    """Values collected from the configured Home Assistant entities."""

    destination_name: str
    destination_latitude: float | None
    destination_longitude: float | None
    navigation_presence: str
    latitude: float | None
    longitude: float | None
    navigation_data_complete: bool = True
    position_observed_at: datetime | None = None
    source_observed_at: datetime | None = None
    heading: float | None = None
    speed_kmh: float | None = None
    eta_minutes: float | None = None
    distance_km: float | None = None
    traffic_delay_minutes: float | None = None
    charging_minutes: float | None = None
    is_charging: bool | None = None
    battery_at_arrival: float | None = None

    @property
    def destination_valid(self) -> bool:
        """Return whether the destination can be sent to the API."""
        return bool(self.destination_name) and _valid_point(
            self.destination_latitude, self.destination_longitude
        )

    @property
    def position_valid(self) -> bool:
        """Return whether the current vehicle position is valid."""
        return _valid_point(self.latitude, self.longitude)

    @property
    def position_key(self) -> tuple[float, float] | None:
        """Return the source-independent position used for change detection."""
        if not self.position_valid:
            return None
        return (float(self.latitude), float(self.longitude))

    def create_payload(self) -> dict[str, Any]:
        """Build the API payload used to create a trip."""
        payload = self.update_payload()
        payload["destination"] = {
            "name": self.destination_name,
            "latitude": self.destination_latitude,
            "longitude": self.destination_longitude,
        }
        return payload

    def update_payload(self) -> dict[str, Any]:
        """Build an update payload, omitting unavailable optional values."""
        payload: dict[str, Any] = {}
        payload["navigation_presence"] = self.navigation_presence
        if self.source_observed_at is not None:
            payload["source_observed_at"] = self.source_observed_at.isoformat()
        if self.navigation_presence == "present" and self.destination_valid:
            payload["destination"] = {
                "name": self.destination_name,
                "latitude": self.destination_latitude,
                "longitude": self.destination_longitude,
            }
        if self.position_valid:
            payload["position"] = {
                "latitude": self.latitude,
                "longitude": self.longitude,
            }
            if self.position_observed_at is not None:
                payload["observed_at"] = self.position_observed_at.isoformat()
        # Keep an unavailable speed explicit so the backend can select its
        # location-only arrival fallback without treating it as 0 km/h.
        payload["speed_kmh"] = self.speed_kmh
        optional = {
            "heading": self.heading,
            "eta_minutes": self.eta_minutes,
            "distance_km": self.distance_km,
            "traffic_delay_minutes": self.traffic_delay_minutes,
            "charging_minutes": self.charging_minutes,
            "is_charging": self.is_charging,
            "battery_at_arrival": self.battery_at_arrival,
        }
        if not self.navigation_data_complete:
            # Tessie uses numeric zero as an unavailable sentinel for these
            # navigation-derived values while its destination snapshot is
            # incomplete. Preserve zero once navigation is complete, and do
            # not suppress legitimate zero values for unrelated metrics.
            for key in ("eta_minutes", "distance_km", "battery_at_arrival"):
                if optional[key] == 0:
                    optional[key] = None
        payload.update(
            {key: value for key, value in optional.items() if value is not None}
        )
        return payload

def _valid_point(latitude: float | None, longitude: float | None) -> bool:
    """Validate a geographic point the same way as the Go API."""
    if latitude is None or longitude is None:
        return False
    return (
        -90 <= latitude <= 90
        and -180 <= longitude <= 180
        and not (latitude == 0 and longitude == 0)
    )


@dataclass(slots=True)
class PositionObservationState:
    """Track the source time of the latest distinct vehicle position."""

    observed_position: tuple[float, float] | None = None
    position_observed_at: datetime | None = None

    def observe_position(
        self,
        position: tuple[float, float] | None,
        source_updated_at: datetime | None,
    ) -> datetime | None:
        """Keep the timestamp at which coordinates actually changed."""
        if position is None:
            self.observed_position = None
            self.position_observed_at = None
            return None
        if position != self.observed_position:
            self.observed_position = position
            self.position_observed_at = source_updated_at
        return self.position_observed_at
