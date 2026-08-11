"""Button platform for Route Progress."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import RouteProgressEntity
from .manager import RouteProgressManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the manual trip lifecycle buttons."""
    manager = entry.runtime_data
    async_add_entities(
        [RouteProgressStartButton(manager), RouteProgressFinishButton(manager)]
    )


class RouteProgressStartButton(RouteProgressEntity, ButtonEntity):
    """Start a new public trip manually."""

    _attr_translation_key = "start"
    _attr_icon = "mdi:play-circle-outline"

    def __init__(self, manager: RouteProgressManager) -> None:
        """Initialize the start button."""
        super().__init__(manager, "start")

    @property
    def available(self) -> bool:
        """Enable the button whenever no trip is active."""
        return not self.manager.active

    async def async_press(self) -> None:
        """Start a new trip with the current route data."""
        if not self.manager.can_start:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="route_data_required",
            )
        await self.manager.async_manual_start()


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
