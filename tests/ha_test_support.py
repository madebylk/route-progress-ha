"""Small HA boundary doubles; integration code and aiohttp remain real."""

import importlib
import sys
import types
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch


class Store:
    def __init__(self, *args):
        self.data = None

    def __class_getitem__(cls, _item):
        return cls

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.data = dict(data)


class Flow:
    def __init_subclass__(cls, **kwargs):
        pass

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    def async_update_and_abort(self, entry, **kwargs):
        return {"type": "abort", **kwargs}

    def _async_current_entries(self):
        return []

    async def async_set_unique_id(self, _value):
        pass

    def _abort_if_unique_id_configured(self):
        pass


class Selector:
    def __init__(self, config=None):
        self.config = config

    def __call__(self, value):
        return value


class HAError(Exception):
    pass


def load_modules():
    modules = {}

    def module(name, **attrs):
        obj = types.ModuleType(name)
        obj.__dict__.update(attrs)
        modules[name] = obj
        return obj

    ha = module("homeassistant")
    ha.config_entries = module(
        "homeassistant.config_entries",
        ConfigEntry=object,
        ConfigFlow=Flow,
        OptionsFlow=Flow,
    )
    module(
        "homeassistant.core",
        HomeAssistant=object,
        State=object,
        Event=object,
        callback=lambda f: f,
    )
    module("homeassistant.const", STATE_ON="on")
    module(
        "homeassistant.exceptions",
        HomeAssistantError=HAError,
        ConfigEntryAuthFailed=HAError,
    )
    helpers = module("homeassistant.helpers")
    helpers.selector = module("homeassistant.helpers.selector")
    for name in [
        "TextSelector",
        "EntitySelector",
        "SelectSelector",
        "NumberSelector",
        "BooleanSelector",
    ]:
        setattr(helpers.selector, name, Selector)
        setattr(helpers.selector, name + "Config", lambda **kw: kw)
    helpers.selector.TextSelectorType = types.SimpleNamespace(
        PASSWORD="password", URL="url"
    )
    helpers.selector.SelectSelectorMode = types.SimpleNamespace(DROPDOWN="dropdown")
    helpers.selector.NumberSelectorMode = types.SimpleNamespace(BOX="box")
    module(
        "homeassistant.helpers.aiohttp_client",
        async_get_clientsession=lambda hass: None,
    )
    module(
        "homeassistant.helpers.event",
        **{
            name: lambda *a: lambda: None
            for name in [
                "async_call_later",
                "async_track_state_change_event",
                "async_track_time_interval",
            ]
        },
    )
    module("homeassistant.helpers.storage", Store=Store)
    util = module("homeassistant.util")
    util.dt = module(
        "homeassistant.util.dt",
        utcnow=lambda: datetime.now(UTC),
        parse_datetime=lambda value: datetime.fromisoformat(value) if value else None,
        as_utc=lambda value: value.astimezone(UTC),
    )
    components = module("homeassistant.components")
    components.frontend = module(
        "homeassistant.components.frontend",
        add_extra_js_url=lambda *a: None,
        remove_extra_js_url=lambda *a: None,
    )
    components.websocket_api = module(
        "homeassistant.components.websocket_api",
        websocket_command=lambda schema: lambda f: f,
        async_response=lambda f: f,
        async_register_command=lambda *a: None,
    )
    module("homeassistant.components.http", StaticPathConfig=lambda *a: a)
    helpers.entity_registry = module(
        "homeassistant.helpers.entity_registry", async_get=lambda hass: hass.registry
    )
    module("homeassistant.auth")
    module("homeassistant.auth.permissions")
    module(
        "homeassistant.auth.permissions.const",
        POLICY_CONTROL="control",
        POLICY_READ="read",
    )
    package = module("route_progress_boundary_tests")
    package.__path__ = [
        str(Path(__file__).parents[1] / "custom_components/route_progress")
    ]
    with patch.dict(sys.modules, modules):
        manager = importlib.import_module(package.__name__ + ".manager")
        config = importlib.import_module(package.__name__ + ".config_flow")
        dashboard = importlib.import_module(package.__name__ + ".dashboard")
    return manager, config, dashboard


manager_module, config_module, dashboard_module = load_modules()


def make_manager(manual=True):
    position = types.SimpleNamespace(
        state="not_home",
        attributes={"latitude": 53.5, "longitude": 10.2},
        last_updated=datetime(2026, 10, 9, 10, tzinfo=UTC),
    )
    states = {"device_tracker.phone": position}
    hass = types.SimpleNamespace(
        states=types.SimpleNamespace(get=states.get, async_all=lambda domain: []),
        data={},
    )
    entry = types.SimpleNamespace(entry_id="test", data={}, options={})
    api = types.SimpleNamespace(
        async_create_trip=AsyncMock(
            return_value={
                "trip_id": "trip",
                "share_url": "https://example.com/t/test",
                "expires_at": "later",
                "status": "waiting_for_destination",
                "accepts_updates": True,
            }
        ),
        async_update_trip=AsyncMock(
            return_value={"status": "confirming_destination", "accepts_updates": True}
        ),
        async_check_auth=AsyncMock(),
    )
    config = {"vehicle_position_entity": "device_tracker.phone"}
    if manual:
        config["destination_source"] = "manual"
    manager = manager_module.RouteProgressManager(hass, entry, api, config)
    entry.runtime_data = manager
    return manager, states
