"""Data models used by Route Progress."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class TripSnapshot:
    """Values collected from the configured Home Assistant entities."""

    destination_name: str
    destination_latitude: float | None
    destination_longitude: float | None
    latitude: float | None
    longitude: float | None
    position_observed_at: datetime | None = None
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

    @property
    def destination_key(self) -> str:
        """Return a stable key which detects name or coordinate changes."""
        latitude = round(self.destination_latitude or 0, 6)
        longitude = round(self.destination_longitude or 0, 6)
        return f"{self.destination_name}|{latitude:.6f}|{longitude:.6f}"

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
        if self.destination_valid:
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
        payload.update(
            {key: value for key, value in optional.items() if value is not None}
        )
        return payload

    def arrival_observation_payload(self) -> dict[str, Any]:
        """Build a private arrival observation without publishing telemetry."""
        payload: dict[str, Any] = {
            "arrival_observation": True,
            "speed_kmh": self.speed_kmh,
        }
        if self.destination_valid:
            payload["destination"] = {
                "name": self.destination_name,
                "latitude": self.destination_latitude,
                "longitude": self.destination_longitude,
            }
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
