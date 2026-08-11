"""Binary sensor platform for Route Progress."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import RouteProgressEntity
from .manager import RouteProgressManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Route Progress status sensors."""
    manager = entry.runtime_data
    async_add_entities(
        [
            RouteProgressActiveBinarySensor(manager),
            RouteProgressCloudConnectionBinarySensor(manager),
        ]
    )


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


class RouteProgressCloudConnectionBinarySensor(
    RouteProgressEntity, BinarySensorEntity
):
    """Show whether the Route Progress API is reachable."""

    _attr_translation_key = "cloud_connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager: RouteProgressManager) -> None:
        """Initialize the cloud connection sensor."""
        super().__init__(manager, "cloud_connection")

    @property
    def available(self) -> bool:
        """Keep the diagnostic entity available while disconnected."""
        return True

    @property
    def is_on(self) -> bool:
        """Return the latest known API connectivity state."""
        return self.manager.available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return connection diagnostics."""
        return {
            "last_successful_connection": self.manager.last_successful_connection,
            "last_error": self.manager.last_error,
        }
