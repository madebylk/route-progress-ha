"""Native selectors for search results and HA zones."""

import time

from homeassistant.components.select import SelectEntity
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .destination import DestinationError, point_result
from .entity import RouteProgressEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.runtime_data.manual_mode:
        async_add_entities(
            [
                RouteProgressDestinationSelect(entry.runtime_data),
                RouteProgressDestinationSelect(entry.runtime_data, zones=True),
            ]
        )


class RouteProgressDestinationSelect(RouteProgressEntity, SelectEntity):
    _attr_should_poll = False
    _attr_icon = "mdi:map-marker-check-outline"

    def __init__(self, manager, zones=False):
        self.zones = zones
        self._attr_translation_key = (
            "destination_zone" if zones else "destination_result"
        )
        super().__init__(manager, self._attr_translation_key)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if self.zones:

            @callback
            def changed(event):
                if event.data.get("entity_id", "").startswith("zone."):
                    self.async_write_ha_state()

            self.async_on_remove(self.hass.bus.async_listen("state_changed", changed))

    def _targets(self):
        if not self.zones:
            return self.manager.destination_results
        targets = {}
        for state in self.manager.hass.states.async_all("zone"):
            try:
                target = point_result(
                    state.name,
                    state.attributes.get("latitude"),
                    state.attributes.get("longitude"),
                )
            except DestinationError:
                continue
            targets[f"{state.name[:180]} ({state.entity_id})"[:255]] = {
                **target,
                "source": "zone",
                "address": "",
                "id": state.entity_id,
            }
        return targets

    @property
    def available(self):
        return self.manager.manual_mode and bool(self.options)

    @property
    def options(self):
        return list(self._targets())

    @property
    def extra_state_attributes(self):
        if any(
            target.get("source") == "geoapify" for target in self._targets().values()
        ):
            return {"attribution": "Powered by Geoapify | © OpenStreetMap contributors"}
        return {}

    @property
    def current_option(self):
        selected = self.manager.manual_destination or {}
        return next(
            (
                label
                for label, target in self._targets().items()
                if all(
                    selected.get(key) == target.get(key)
                    for key in ("name", "latitude", "longitude")
                )
            ),
            None,
        )

    async def async_select_option(self, option):
        target = self._targets().get(option)
        if target is None or (
            not self.zones
            and time.monotonic() >= self.manager.destination_results_until
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="result_expired"
            )
        if self.zones and getattr(self._context, "user_id", None):
            user = await self.hass.auth.async_get_user(self._context.user_id)
            if user is None or not user.permissions.check_entity(target["id"], "read"):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="zone_not_allowed"
                )
        await self.manager.async_select_destination(target)
