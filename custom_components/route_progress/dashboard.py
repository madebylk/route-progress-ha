"""Authenticated Home Assistant dashboard card and its WebSocket API."""

from __future__ import annotations

import secrets
import time
from pathlib import Path

import voluptuous as vol
from homeassistant.auth.permissions.const import POLICY_CONTROL, POLICY_READ
from homeassistant.components import frontend, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry

from .const import CONF_GEOAPIFY_API_KEY, CONF_VEHICLE_POSITION_ENTITY, DOMAIN
from .destination import DestinationError, point_result
from .geoapify import get_lookup

STATIC_URL = "/route_progress_static/route-progress-card.js"


async def async_setup_dashboard(hass, manager):
    """Register static code once; rebind runtime state on each reload."""
    data = hass.data.setdefault(DOMAIN, {})
    if not data.get("card_registered"):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    STATIC_URL,
                    str(Path(__file__).parent / "frontend" / "route-progress-card.js"),
                    False,
                )
            ]
        )
        websocket_api.async_register_command(hass, websocket_destination)
        data["card_registered"] = True
    data["manager"] = manager
    data["lookup"] = get_lookup(hass, manager.config.get(CONF_GEOAPIFY_API_KEY, ""))
    if manager.manual_mode and manager.config.get(CONF_GEOAPIFY_API_KEY):
        manager.geoapify = data["lookup"]
        manager._unsubscribers.append(
            manager.geoapify.add_listener(manager._notify_listeners)
        )
        try:
            await manager.geoapify.check_api()
        except DestinationError:
            # A search outage must not disable server sharing or HA zones.
            pass
    data["results"] = {}
    frontend.add_extra_js_url(hass, STATIC_URL + "?v=0.14.0")


def async_unload_dashboard(hass):
    frontend.remove_extra_js_url(hass, STATIC_URL + "?v=0.14.0")
    data = hass.data.get(DOMAIN, {})
    data.pop("manager", None)
    data.pop("lookup", None)
    data.pop("results", None)


def _state(hass, manager, user):
    zones = []
    for state in hass.states.async_all("zone"):
        if not user.permissions.check_entity(state.entity_id, POLICY_READ):
            continue
        try:
            target = point_result(
                state.name,
                state.attributes.get("latitude"),
                state.attributes.get("longitude"),
            )
        except DestinationError:
            continue
        zones.append({**target, "id": state.entity_id, "source": "zone", "address": ""})
    return {
        "manual": manager.manual_mode,
        "destination": manager.manual_destination,
        "status": manager.status,
        "active": manager.active,
        "available": manager.available,
        "can_start": manager.can_start,
        "can_accept": manager.can_accept_destination,
        "share_url": manager.share_url,
        "zones": zones,
        "search_enabled": bool(manager.config.get(CONF_GEOAPIFY_API_KEY)),
    }


@websocket_api.websocket_command(
    {
        vol.Required("type"): "route_progress/destination",
        vol.Required("action"): vol.In(
            ["state", "search", "select", "start", "finish", "accept"]
        ),
        vol.Optional("query"): vol.All(str, vol.Length(min=3, max=4096)),
        vol.Optional("language", default="en"): vol.In(["de", "en"]),
        vol.Optional("target_id"): vol.All(str, vol.Length(max=200)),
    }
)
@websocket_api.async_response
async def websocket_destination(hass, connection, msg):
    """Never accept arbitrary URLs for fetching or client-supplied coordinates."""
    data = hass.data.get(DOMAIN, {})
    manager = data.get("manager")
    if manager is None or not manager.manual_mode:
        connection.send_error(
            msg["id"], "manual_disabled", "Manual destination mode is not enabled."
        )
        return
    registry = entity_registry.async_get(hass)
    start_entity = registry.async_get_entity_id(
        "button", DOMAIN, f"{manager.entry.entry_id}_start"
    )
    if (
        not start_entity
        or not connection.user.permissions.check_entity(start_entity, POLICY_CONTROL)
        or not connection.user.permissions.check_entity(
            manager.config[CONF_VEHICLE_POSITION_ENTITY], POLICY_READ
        )
    ):
        connection.send_error(
            msg["id"], "unauthorized", "No permission to control this trip."
        )
        return
    try:
        action = msg["action"]
        if action == "search":
            if "query" not in msg:
                raise DestinationError("invalid_query")
            results = await data["lookup"].search(msg["query"], msg["language"])
            cache = data["results"]
            now = time.monotonic()
            for key in list(cache):
                if cache[key][0] < now:
                    del cache[key]
            while len(cache) > 95:
                del cache[next(iter(cache))]
            for result in results:
                result["id"] = secrets.token_urlsafe(18)
                cache[result["id"]] = (now + 600, connection.user.id, result)
            connection.send_result(msg["id"], {"results": results})
            return
        if action == "select":
            target_id = msg.get("target_id", "")
            if target_id.startswith("zone."):
                target = next(
                    (
                        zone
                        for zone in _state(hass, manager, connection.user)["zones"]
                        if zone["id"] == target_id
                    ),
                    None,
                )
            else:
                cached = data["results"].get(target_id)
                target = (
                    cached[2]
                    if cached
                    and cached[0] > time.monotonic()
                    and cached[1] == connection.user.id
                    else None
                )
            if target is None:
                raise DestinationError("result_expired")
            await manager.async_select_destination(target)
        elif action == "start":
            await manager.async_manual_start()
        elif action == "finish":
            await manager.async_manual_stop()
        elif action == "accept":
            await manager.async_accept_destination()
        if action != "state" and not manager.available:
            raise DestinationError("server_unavailable")
        connection.send_result(msg["id"], _state(hass, manager, connection.user))
    except DestinationError as err:
        connection.send_error(msg["id"], str(err), str(err))
    except HomeAssistantError:
        connection.send_error(
            msg["id"], "destination_required", "Select a destination first."
        )
