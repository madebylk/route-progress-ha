"""Sensor platform for Route Progress."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import RouteProgressEntity
from .manager import RouteProgressManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Route Progress share URL sensor."""
    manager = entry.runtime_data
    entities = [
        RouteProgressShareURLSensor(manager),
        RouteProgressStatusSensor(manager),
    ]
    if manager.manual_mode:
        entities.append(RouteProgressDestinationSensor(manager))
    async_add_entities(entities)


class RouteProgressDestinationSensor(RouteProgressEntity, SensorEntity):
    """The selected target, also suitable for the standard HA map card."""

    _attr_translation_key = "selected_destination"
    _attr_icon = "mdi:map-marker-check-outline"
    _attr_should_poll = False

    def __init__(self, manager):
        super().__init__(manager, "selected_destination")

    @property
    def available(self):
        return self.manager.manual_mode

    @property
    def native_value(self):
        return (self.manager.manual_destination or {}).get("name", "")[:255] or None

    @property
    def extra_state_attributes(self):
        target = dict(self.manager.manual_destination or {})
        if target.get("source") == "geoapify":
            target["attribution"] = "Powered by Geoapify | © OpenStreetMap contributors"
        return target


class RouteProgressShareURLSensor(RouteProgressEntity, SensorEntity):
    """Expose the most recently created public share URL."""

    _attr_translation_key = "share_url"
    _attr_icon = "mdi:share-variant"

    def __init__(self, manager: RouteProgressManager) -> None:
        """Initialize the share URL sensor."""
        super().__init__(manager, "share_url")

    @property
    def native_value(self) -> str | None:
        """Return the current or most recent share URL."""
        return self.manager.share_url

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return useful lifecycle metadata."""
        return {
            "active": self.manager.active,
            "trip_id": self.manager.trip_id,
            "destination": self.manager.destination_name,
            "expires_at": self.manager.expires_at,
            "arrived_at": self.manager.arrived_at,
            "arrival_detection": self.manager.arrival_detection,
            "arrival_followup_until": self.manager.arrival_followup_until,
            "finished_at": self.manager.finished_at,
            "last_error": self.manager.last_error,
        }


class RouteProgressStatusSensor(RouteProgressEntity, SensorEntity):
    """Expose the lifecycle state decided by the backend."""

    _attr_translation_key = "share_status"
    _attr_icon = "mdi:map-clock-outline"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        "idle",
        "waiting_for_destination",
        "confirming_destination",
        "en_route",
        "navigation_uncertain",
        "destination_changed",
        "arrived_followup",
        "arrived",
        "manually_finished",
        "expired",
    ]

    def __init__(self, manager: RouteProgressManager) -> None:
        """Initialize the status sensor."""
        super().__init__(manager, "share_status")

    @property
    def native_value(self) -> str:
        """Return the backend-owned lifecycle state."""
        return self.manager.status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the shared destination and terminal timestamps."""
        return {
            "destination": self.manager.destination_name,
            "expires_at": self.manager.expires_at,
            "arrived_at": self.manager.arrived_at,
            "arrival_detection": self.manager.arrival_detection,
            "arrival_followup_until": self.manager.arrival_followup_until,
            "finished_at": self.manager.finished_at,
        }
