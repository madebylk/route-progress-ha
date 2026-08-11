"""Route Progress custom integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RouteProgressAPI, RouteProgressAPIError, RouteProgressAuthError
from .const import (
    CONF_API_TOKEN,
    CONF_BASE_URL,
    CONF_CLOUDFLARE_ACCESS_ENABLED,
    CONF_CLOUDFLARE_CLIENT_ID,
    CONF_CLOUDFLARE_CLIENT_SECRET,
    PLATFORMS,
)
from .manager import RouteProgressManager


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Route Progress from a config entry."""
    config: dict[str, Any] = {**entry.data, **entry.options}
    api = RouteProgressAPI(
        async_get_clientsession(hass),
        config[CONF_BASE_URL],
        config[CONF_API_TOKEN],
        config.get(CONF_CLOUDFLARE_CLIENT_ID)
        if config.get(CONF_CLOUDFLARE_ACCESS_ENABLED)
        else None,
        config.get(CONF_CLOUDFLARE_CLIENT_SECRET)
        if config.get(CONF_CLOUDFLARE_ACCESS_ENABLED)
        else None,
    )
    manager = RouteProgressManager(hass, entry, api, config)
    try:
        await api.async_check_auth()
    except RouteProgressAuthError as err:
        raise ConfigEntryAuthFailed from err
    except RouteProgressAPIError as err:
        manager.record_connection_error(err)

    await manager.async_load()
    entry.runtime_data = manager
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await manager.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Route Progress without finishing an active shared trip."""
    manager: RouteProgressManager = entry.runtime_data
    await manager.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration after its configuration changes."""
    await hass.config_entries.async_reload(entry.entry_id)
