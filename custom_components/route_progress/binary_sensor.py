"""Binary sensor platform for Route Progress."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Set up the Route Progress active-state sensor."""
    async_add_entities([RouteProgressActiveBinarySensor(entry.runtime_data)])


class RouteProgressActiveBinarySensor(RouteProgressEntity, BinarySensorEntity):
    """Show whether a public trip is currently active."""

    _attr_translation_key = "active"
    _attr_icon = "mdi:map-marker-path"

    def __init__(self, manager: RouteProgressManager) -> None:
        """Initialize the active sensor."""
        super().__init__(manager, "active")

    @property
    def is_on(self) -> bool:
        """Return whether a trip ID is currently tracked."""
        return self.manager.active
