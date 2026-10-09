"""Two-step setup and reconfiguration with mode-specific destination settings."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RouteProgressAPI, RouteProgressAPIError, RouteProgressAuthError
from .const import (
    CONF_API_TOKEN,
    CONF_BASE_URL,
    CONF_CLOUDFLARE_ACCESS_ENABLED,
    CONF_CLOUDFLARE_CLIENT_ID,
    CONF_CLOUDFLARE_CLIENT_SECRET,
    CONF_DESTINATION_ENTITY,
    CONF_DESTINATION_POSITION_ENTITY,
    CONF_DESTINATION_SOURCE,
    CONF_GEOAPIFY_API_KEY,
    CONF_UPDATE_INTERVAL,
    CONF_VEHICLE_POSITION_ENTITY,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    OPTIONAL_ENTITY_KEYS,
    SOURCE_ENTITIES,
    SOURCE_MANUAL,
)


def _marker(key, defaults, required=True):
    marker = vol.Required if required else vol.Optional
    return marker(key, default=defaults[key]) if key in defaults else marker(key)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    """Common connection and source settings; no destination credentials here."""
    text = selector.TextSelector
    password = text(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    )
    fields = {
        _marker(CONF_BASE_URL, defaults): text(
            selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
        ),
        _marker(CONF_API_TOKEN, defaults): password,
        vol.Required(
            CONF_DESTINATION_SOURCE,
            default=defaults.get(CONF_DESTINATION_SOURCE, SOURCE_ENTITIES),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[SOURCE_ENTITIES, SOURCE_MANUAL],
                translation_key="destination_source",
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        _marker(CONF_VEHICLE_POSITION_ENTITY, defaults): selector.EntitySelector(),
        vol.Required(
            CONF_UPDATE_INTERVAL,
            default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=MIN_UPDATE_INTERVAL,
                max=MAX_UPDATE_INTERVAL,
                step=5,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="s",
            )
        ),
        vol.Required(
            CONF_CLOUDFLARE_ACCESS_ENABLED,
            default=defaults.get(CONF_CLOUDFLARE_ACCESS_ENABLED, False),
        ): selector.BooleanSelector(),
        _marker(CONF_CLOUDFLARE_CLIENT_ID, defaults, False): password,
        _marker(CONF_CLOUDFLARE_CLIENT_SECRET, defaults, False): password,
    }
    for key in OPTIONAL_ENTITY_KEYS:
        fields[_marker(key, defaults, False)] = selector.EntitySelector()
    return vol.Schema(fields)


def _destination_schema(data):
    if data.get(CONF_DESTINATION_SOURCE) == SOURCE_MANUAL:
        return vol.Schema(
            {
                _marker(CONF_GEOAPIFY_API_KEY, data, False): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }
        )
    return vol.Schema(
        {
            _marker(key, data): selector.EntitySelector()
            for key in (CONF_DESTINATION_ENTITY, CONF_DESTINATION_POSITION_ENTITY)
        }
    )


def _clean_input(data):
    cleaned = {k: v for k, v in data.items() if v != ""}
    cleaned[CONF_BASE_URL] = str(cleaned[CONF_BASE_URL]).rstrip("/")
    cleaned[CONF_UPDATE_INTERVAL] = int(cleaned[CONF_UPDATE_INTERVAL])
    if not cleaned.get(CONF_CLOUDFLARE_ACCESS_ENABLED):
        cleaned.pop(CONF_CLOUDFLARE_CLIENT_ID, None)
        cleaned.pop(CONF_CLOUDFLARE_CLIENT_SECRET, None)
    if cleaned.get(CONF_DESTINATION_SOURCE, SOURCE_ENTITIES) == SOURCE_ENTITIES:
        cleaned.pop(CONF_GEOAPIFY_API_KEY, None)
    else:
        cleaned.pop(CONF_DESTINATION_ENTITY, None)
        cleaned.pop(CONF_DESTINATION_POSITION_ENTITY, None)
    return cleaned


class DestinationFlowMixin:
    """Share validation and steps across setup, reconfigure and legacy options."""

    _pending: dict[str, Any]
    _entry = None
    _is_options = False

    async def _common_step(self, step_id, user_input, current):
        errors = {}
        if user_input is not None:
            data = {**current, **user_input}
            for key in (
                *OPTIONAL_ENTITY_KEYS,
                CONF_CLOUDFLARE_CLIENT_ID,
                CONF_CLOUDFLARE_CLIENT_SECRET,
            ):
                if key not in user_input:
                    data.pop(key, None)
            errors = await self._validate(data)
            if not errors:
                self._pending = data
                return await self.async_step_destination()
        return self.async_show_form(
            step_id=step_id, data_schema=_schema(user_input or current), errors=errors
        )

    async def _validate(self, data):
        parsed = urlparse(str(data[CONF_BASE_URL]))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return {CONF_BASE_URL: "invalid_url"}
        if self._entry is not None:
            old = {**self._entry.data, **self._entry.options}
            manager = getattr(self._entry, "runtime_data", None)
            if (
                manager
                and manager.active
                and old.get(CONF_DESTINATION_SOURCE, SOURCE_ENTITIES)
                != data[CONF_DESTINATION_SOURCE]
            ):
                return {"base": "active_trip"}
        if data.get(CONF_CLOUDFLARE_ACCESS_ENABLED) and not (
            data.get(CONF_CLOUDFLARE_CLIENT_ID)
            and data.get(CONF_CLOUDFLARE_CLIENT_SECRET)
        ):
            return {"base": "cloudflare_credentials_required"}
        api = RouteProgressAPI(
            async_get_clientsession(self.hass),
            str(data[CONF_BASE_URL]),
            str(data[CONF_API_TOKEN]),
            data.get(CONF_CLOUDFLARE_CLIENT_ID)
            if data.get(CONF_CLOUDFLARE_ACCESS_ENABLED)
            else None,
            data.get(CONF_CLOUDFLARE_CLIENT_SECRET)
            if data.get(CONF_CLOUDFLARE_ACCESS_ENABLED)
            else None,
        )
        try:
            await api.async_check_auth()
        except RouteProgressAuthError:
            return {"base": "invalid_auth"}
        except RouteProgressAPIError:
            return {"base": "cannot_connect"}
        return {}

    async def async_step_destination(self, user_input=None):
        if user_input is not None:
            if self._entry is not None:
                old = {**self._entry.data, **self._entry.options}
                manager = getattr(self._entry, "runtime_data", None)
                if (
                    manager
                    and manager.active
                    and old.get(CONF_DESTINATION_SOURCE, SOURCE_ENTITIES)
                    != self._pending[CONF_DESTINATION_SOURCE]
                ):
                    return self.async_show_form(
                        step_id="destination",
                        data_schema=_destination_schema(
                            {**self._pending, **user_input}
                        ),
                        errors={"base": "active_trip"},
                    )
            data = dict(self._pending)
            data.pop(CONF_GEOAPIFY_API_KEY, None)
            data.update(user_input)
            data = _clean_input(data)
            if self._is_options:
                self.hass.config_entries.async_update_entry(
                    self._entry, data=data, options={}
                )
                return self.async_create_entry(data={})
            if self._entry is not None:
                return self.async_update_and_abort(
                    self._entry, data=data, options={}, reason="reconfigure_successful"
                )
            await self.async_set_unique_id("route-progress")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Route Progress", data=data)
        return self.async_show_form(
            step_id="destination", data_schema=_destination_schema(self._pending)
        )


class RouteProgressConfigFlow(
    DestinationFlowMixin, config_entries.ConfigFlow, domain=DOMAIN
):
    """Existing entries without a source retain entity mode."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return await self._common_step("user", user_input, {})

    async def async_step_reconfigure(self, user_input=None):
        self._entry = self._get_reconfigure_entry()
        return await self._common_step(
            "reconfigure", user_input, {**self._entry.data, **self._entry.options}
        )

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry):
        return RouteProgressOptionsFlow()


class RouteProgressOptionsFlow(DestinationFlowMixin, config_entries.OptionsFlow):
    """Expose the same two steps on installations using the options dialog."""

    _is_options = True

    async def async_step_init(self, user_input=None):
        self._entry = self.config_entry
        return await self._common_step(
            "init", user_input, {**self._entry.data, **self._entry.options}
        )
