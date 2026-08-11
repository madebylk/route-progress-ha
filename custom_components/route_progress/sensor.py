"""Sensor platform for Route Progress."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
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
    async_add_entities([RouteProgressShareURLSensor(entry.runtime_data)])


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
            "last_error": self.manager.last_error,
        }
