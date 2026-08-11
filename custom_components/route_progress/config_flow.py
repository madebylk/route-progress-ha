"""Config flow for Route Progress."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
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
    CONF_UPDATE_INTERVAL,
    CONF_VEHICLE_POSITION_ENTITY,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    OPTIONAL_ENTITY_KEYS,
    REQUIRED_ENTITY_KEYS,
)


class RouteProgressConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Route Progress configuration through the UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the single Route Progress config entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate(user_input)
            if not errors:
                await self.async_set_unique_id("route-progress")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Route Progress", data=_clean_input(user_input)
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update URL, credentials, source entities, and interval."""
        entry = self._get_reconfigure_entry()
        current = {**entry.data, **entry.options}
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await self._async_validate(user_input)
            if not errors:
                return self.async_update_and_abort(
                    entry,
                    data=_clean_input(user_input),
                    options={},
                    reason="reconfigure_successful",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(user_input or current),
            errors=errors,
        )

    async def _async_validate(self, data: dict[str, Any]) -> dict[str, str]:
        """Validate URL and bearer token using a side-effect-free API call."""
        missing_entities = [key for key in REQUIRED_ENTITY_KEYS if not data.get(key)]
        if missing_entities:
            return {key: "required_entity" for key in missing_entities}

        parsed = urlparse(str(data[CONF_BASE_URL]))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return {CONF_BASE_URL: "invalid_url"}

        if data.get(CONF_CLOUDFLARE_ACCESS_ENABLED) and (
            not data.get(CONF_CLOUDFLARE_CLIENT_ID)
            or not data.get(CONF_CLOUDFLARE_CLIENT_SECRET)
        ):
            return {"base": "cloudflare_credentials_required"}

        api = RouteProgressAPI(
            async_get_clientsession(self.hass),
            str(data[CONF_BASE_URL]),
            str(data[CONF_API_TOKEN]),
            str(data.get(CONF_CLOUDFLARE_CLIENT_ID, ""))
            if data.get(CONF_CLOUDFLARE_ACCESS_ENABLED)
            else None,
            str(data.get(CONF_CLOUDFLARE_CLIENT_SECRET, ""))
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

    @staticmethod
    @callback
    def async_get_options_flow(
        _config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """The integration uses the native reconfigure flow instead."""
        return RouteProgressOptionsFlow()


class RouteProgressOptionsFlow(config_entries.OptionsFlow):
    """Redirect legacy Configure actions to the reconfigure flow values."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the same fields for HA versions exposing Options."""
        current = {**self.config_entry.data, **self.config_entry.options}
        errors: dict[str, str] = {}
        if user_input is not None:
            missing_entities = [
                key for key in REQUIRED_ENTITY_KEYS if not user_input.get(key)
            ]
            errors.update({key: "required_entity" for key in missing_entities})
            if user_input.get(CONF_CLOUDFLARE_ACCESS_ENABLED) and (
                not user_input.get(CONF_CLOUDFLARE_CLIENT_ID)
                or not user_input.get(CONF_CLOUDFLARE_CLIENT_SECRET)
            ):
                errors["base"] = "cloudflare_credentials_required"
            if not errors:
                parsed = urlparse(str(user_input[CONF_BASE_URL]))
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    errors[CONF_BASE_URL] = "invalid_url"
                else:
                    api = RouteProgressAPI(
                        async_get_clientsession(self.hass),
                        str(user_input[CONF_BASE_URL]),
                        str(user_input[CONF_API_TOKEN]),
                        str(user_input.get(CONF_CLOUDFLARE_CLIENT_ID, ""))
                        if user_input.get(CONF_CLOUDFLARE_ACCESS_ENABLED)
                        else None,
                        str(user_input.get(CONF_CLOUDFLARE_CLIENT_SECRET, ""))
                        if user_input.get(CONF_CLOUDFLARE_ACCESS_ENABLED)
                        else None,
                    )
                    try:
                        await api.async_check_auth()
                    except RouteProgressAuthError:
                        errors["base"] = "invalid_auth"
                    except RouteProgressAPIError:
                        errors["base"] = "cannot_connect"
            if not errors:
                return self.async_create_entry(data=_clean_input(user_input))

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(user_input or current),
            errors=errors,
        )


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the UI form schema with current values as defaults."""
    entity = selector.EntitySelector(selector.EntitySelectorConfig())
    optional_entity = selector.EntitySelector(selector.EntitySelectorConfig())
    destination_marker = (
        vol.Required(
            CONF_DESTINATION_ENTITY,
            default=defaults[CONF_DESTINATION_ENTITY],
        )
        if defaults.get(CONF_DESTINATION_ENTITY)
        else vol.Required(CONF_DESTINATION_ENTITY)
    )
    destination_position_marker = (
        vol.Required(
            CONF_DESTINATION_POSITION_ENTITY,
            default=defaults[CONF_DESTINATION_POSITION_ENTITY],
        )
        if defaults.get(CONF_DESTINATION_POSITION_ENTITY)
        else vol.Required(CONF_DESTINATION_POSITION_ENTITY)
    )
    vehicle_position_marker = (
        vol.Required(
            CONF_VEHICLE_POSITION_ENTITY,
            default=defaults[CONF_VEHICLE_POSITION_ENTITY],
        )
        if defaults.get(CONF_VEHICLE_POSITION_ENTITY)
        else vol.Required(CONF_VEHICLE_POSITION_ENTITY)
    )
    fields: dict[Any, Any] = {
            vol.Required(
                CONF_BASE_URL, default=defaults.get(CONF_BASE_URL, "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
            ),
            vol.Required(
                CONF_API_TOKEN, default=defaults.get(CONF_API_TOKEN, "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Required(
                CONF_CLOUDFLARE_ACCESS_ENABLED,
                default=defaults.get(CONF_CLOUDFLARE_ACCESS_ENABLED, False),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_CLOUDFLARE_CLIENT_ID,
                default=defaults.get(CONF_CLOUDFLARE_CLIENT_ID, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional(
                CONF_CLOUDFLARE_CLIENT_SECRET,
                default=defaults.get(CONF_CLOUDFLARE_CLIENT_SECRET, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            destination_marker: entity,
            destination_position_marker: entity,
            vehicle_position_marker: entity,
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
    }
    for key in OPTIONAL_ENTITY_KEYS:
        marker = (
            vol.Optional(key, default=defaults[key])
            if defaults.get(key)
            else vol.Optional(key)
        )
        fields[marker] = optional_entity
    return vol.Schema(fields)


def _clean_input(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize URL and remove blank optional entity selectors."""
    cleaned = dict(data)
    cleaned[CONF_BASE_URL] = str(cleaned[CONF_BASE_URL]).rstrip("/")
    cleaned[CONF_UPDATE_INTERVAL] = int(cleaned[CONF_UPDATE_INTERVAL])
    cleaned[CONF_CLOUDFLARE_ACCESS_ENABLED] = bool(
        cleaned.get(CONF_CLOUDFLARE_ACCESS_ENABLED)
    )
    if not cleaned[CONF_CLOUDFLARE_ACCESS_ENABLED]:
        cleaned.pop(CONF_CLOUDFLARE_CLIENT_ID, None)
        cleaned.pop(CONF_CLOUDFLARE_CLIENT_SECRET, None)
    for key in OPTIONAL_ENTITY_KEYS:
        if not cleaned.get(key):
            cleaned.pop(key, None)
    return cleaned
