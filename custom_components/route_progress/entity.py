"""Shared entity base for Route Progress."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .manager import RouteProgressManager


class RouteProgressEntity(Entity):
    """Base class backed by the in-memory lifecycle manager."""

    _attr_has_entity_name = True

    def __init__(self, manager: RouteProgressManager, suffix: str) -> None:
        """Initialize a Route Progress entity."""
        self.manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.entry.entry_id)},
            name="Route Progress",
            manufacturer="Route Progress",
            model="Route sharing service",
            configuration_url=manager.api.base_url,
        )
        self._remove_listener = None

    @property
    def available(self) -> bool:
        """Return API connection availability."""
        return self.manager.available

    async def async_added_to_hass(self) -> None:
        """Subscribe to lifecycle updates."""
        await super().async_added_to_hass()
        self._remove_listener = self.manager.async_add_listener(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from lifecycle updates."""
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self) -> None:
        """Write manager data to HA state."""
        self.async_write_ha_state()
