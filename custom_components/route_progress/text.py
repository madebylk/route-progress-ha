"""Destination input for standard HA dashboards and automations."""

import time

from homeassistant.components.text import TextEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .destination import DestinationError
from .entity import RouteProgressEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.runtime_data.manual_mode:
        async_add_entities([RouteProgressDestinationQuery(entry.runtime_data)])


class RouteProgressDestinationQuery(RouteProgressEntity, TextEntity):
    _attr_translation_key = "destination_query"
    _attr_icon = "mdi:map-search-outline"
    _attr_should_poll = False
    _attr_native_min = 0
    _attr_native_max = 255

    def __init__(self, manager):
        super().__init__(manager, "destination_query")
        self._sequence = 0

    @property
    def available(self):
        return self.manager.manual_mode

    @property
    def native_value(self):
        return self.manager.destination_query

    async def async_set_value(self, value):
        """One search per submitted value; never select an ambiguous first hit."""
        value = value.strip()
        if value and not 3 <= len(value) <= 255:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="invalid_query"
            )
        self._sequence += 1
        sequence = self._sequence
        self.manager.destination_query = value
        self.manager.destination_results = {}
        self.manager._notify_listeners()
        if not value:
            return
        try:
            results = await self.hass.data[DOMAIN]["lookup"].search(
                value, "de" if self.hass.config.language.startswith("de") else "en"
            )
        except DestinationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="destination_lookup_failed",
                translation_placeholders={"error": str(err)},
            ) from None
        if sequence != self._sequence:
            return
        self.manager.destination_results = {
            f"{i + 1}. {target.get('address') or target['name']}"[:255]: target
            for i, target in enumerate(results)
        }
        self.manager.destination_results_until = time.monotonic() + 600
        self.manager._notify_listeners()
        if not results:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="no_results"
            )
