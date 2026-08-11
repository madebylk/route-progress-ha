"""Button platform for Route Progress."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Set up the manual finish button."""
    async_add_entities([RouteProgressFinishButton(entry.runtime_data)])


class RouteProgressFinishButton(RouteProgressEntity, ButtonEntity):
    """Finish the current public trip manually."""

    _attr_translation_key = "finish"
    _attr_icon = "mdi:stop-circle-outline"

    def __init__(self, manager: RouteProgressManager) -> None:
        """Initialize the finish button."""
        super().__init__(manager, "finish")

    @property
    def available(self) -> bool:
        """Only enable the button while a reachable trip is active."""
        return self.manager.available and self.manager.active

    async def async_press(self) -> None:
        """Finish the current trip."""
        await self.manager.async_manual_stop()
