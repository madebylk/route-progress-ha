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
    """Set up the manual trip lifecycle buttons."""
    manager = entry.runtime_data
    async_add_entities(
        [
            RouteProgressStartButton(manager),
            RouteProgressAcceptDestinationButton(manager),
            RouteProgressFinishButton(manager),
        ]
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
        return self.manager.available and not self.manager.active

    async def async_press(self) -> None:
        """Create a share which waits for a stable navigation destination."""
        await self.manager.async_manual_start()


class RouteProgressAcceptDestinationButton(RouteProgressEntity, ButtonEntity):
    """Explicitly adopt a changed navigation destination."""

    _attr_translation_key = "accept_destination"
    _attr_icon = "mdi:map-marker-check-outline"

    def __init__(self, manager: RouteProgressManager) -> None:
        """Initialize the destination confirmation button."""
        super().__init__(manager, "accept_destination")

    @property
    def available(self) -> bool:
        """Enable only while the server reports a destination change."""
        return self.manager.available and self.manager.can_accept_destination

    async def async_press(self) -> None:
        """Accept the currently observed navigation destination."""
        await self.manager.async_accept_destination()


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
