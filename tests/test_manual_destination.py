"""Exercise actual config steps, manual state and dashboard authorization."""

import types
import unittest
from unittest.mock import AsyncMock

from ha_test_support import HAError, config_module, dashboard_module, make_manager

TARGET = {"name": "Home", "latitude": 53.6, "longitude": 10.3}
COMMON = {
    "base_url": "https://example.com",
    "api_token": "server-key",
    "vehicle_position_entity": "device_tracker.phone",
    "destination_source": "manual",
    "update_interval": 30,
}


class ManualManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_selection_does_not_start_share_and_survives_restart(self):
        manager, _ = make_manager()
        self.assertFalse(manager.can_start)
        with self.assertRaises(HAError):
            await manager.async_manual_start()
        await manager.async_select_destination(TARGET)
        manager.api.async_create_trip.assert_not_called()
        self.assertTrue(manager.can_start)
        restored, _ = make_manager()
        restored._store.data = manager._store.data
        await restored.async_load()
        self.assertEqual(restored.manual_destination, TARGET)
        self.assertEqual(
            restored.manual_destination_updated_at,
            manager.manual_destination_updated_at,
        )
        await restored.async_manual_start()
        restored.api.async_create_trip.assert_awaited_once()
        payload = restored.api.async_update_trip.call_args.args[1]
        self.assertEqual(payload["destination"], TARGET)
        self.assertEqual(payload["navigation_presence"], "present")

    async def test_heartbeat_does_not_fabricate_position_or_source_freshness(self):
        manager, states = make_manager()
        await manager.async_select_destination(TARGET)
        first = manager._snapshot(track_position=True)
        second = manager._snapshot(track_position=True)
        self.assertEqual(first.position_observed_at, second.position_observed_at)
        self.assertEqual(first.source_observed_at, second.source_observed_at)
        states["device_tracker.phone"].state = "unavailable"
        snapshot = manager._snapshot(track_position=True)
        self.assertFalse(snapshot.position_valid)
        self.assertEqual(snapshot.navigation_presence, "present")

    async def test_explicit_change_accepts_server_candidate(self):
        manager, _ = make_manager()
        manager.trip_id, manager.accepts_updates = "trip", True
        manager.status = "en_route"
        manager.api.async_update_trip.return_value = {
            "status": "destination_changed",
            "accepts_updates": True,
        }
        manager.api.async_accept_destination = AsyncMock(
            return_value={"status": "en_route", "accepts_updates": True}
        )
        await manager.async_select_destination(TARGET)
        manager.api.async_accept_destination.assert_awaited_once_with("trip", TARGET)
        self.assertEqual(manager.status, "en_route")

    async def test_legacy_entity_mode_is_default(self):
        manager, _ = make_manager(False)
        self.assertFalse(manager.manual_mode)
        self.assertTrue(manager.can_start)
        with self.assertRaises(HAError):
            await manager.async_select_destination(TARGET)
        manager._store.data = {"manual_destination": TARGET}
        await manager.async_load()
        self.assertIsNone(manager.manual_destination)


class ConfigTests(unittest.IsolatedAsyncioTestCase):
    async def test_setup_shows_only_mode_specific_fields(self):
        flow = config_module.RouteProgressConfigFlow()
        flow._validate = AsyncMock(return_value={})
        form = await flow.async_step_user(COMMON)
        self.assertEqual(form["step_id"], "destination")
        self.assertEqual(
            set(str(k) for k in form["data_schema"].schema), {"geoapify_api_key"}
        )
        result = await flow.async_step_destination({"geoapify_api_key": "private"})
        self.assertEqual(result["data"]["geoapify_api_key"], "private")
        form = await flow.async_step_user({**COMMON, "destination_source": "entities"})
        self.assertEqual(
            set(str(k) for k in form["data_schema"].schema),
            {"destination_entity", "destination_position_entity"},
        )

    async def test_reconfigure_cleans_unused_fields(self):
        flow = config_module.RouteProgressConfigFlow()
        flow._validate = AsyncMock(return_value={})
        entry = types.SimpleNamespace(
            data={**COMMON, "geoapify_api_key": "old"}, options={}
        )
        flow._get_reconfigure_entry = lambda: entry
        await flow.async_step_reconfigure({**COMMON, "destination_source": "entities"})
        result = await flow.async_step_destination(
            {
                "destination_entity": "sensor.name",
                "destination_position_entity": "sensor.coordinates",
            }
        )
        self.assertNotIn("geoapify_api_key", result["data"])
        self.assertEqual(result["options"], {})

    async def test_active_trip_blocks_source_change(self):
        manager, _ = make_manager(False)
        manager.trip_id, manager.accepts_updates = "trip", True
        flow = config_module.RouteProgressConfigFlow()
        flow._entry = manager.entry
        result = await flow._validate(COMMON)
        self.assertEqual(result, {"base": "active_trip"})

    async def test_optional_key_can_be_removed(self):
        result = config_module._clean_input(
            {
                **COMMON,
                "geoapify_api_key": "",
                "destination_entity": "old",
                "destination_position_entity": "old",
            }
        )
        self.assertNotIn("geoapify_api_key", result)
        self.assertNotIn("destination_entity", result)


class DashboardTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_control_permission_blocks_lookup(self):
        manager, _ = make_manager()
        hass = manager.hass
        lookup = types.SimpleNamespace(search=AsyncMock())
        hass.data["route_progress"] = {
            "manager": manager,
            "lookup": lookup,
            "results": {},
        }
        hass.registry = types.SimpleNamespace(
            async_get_entity_id=lambda *a: "button.start"
        )
        connection = types.SimpleNamespace(
            user=types.SimpleNamespace(
                id="user",
                permissions=types.SimpleNamespace(check_entity=lambda *a: False),
            ),
            send_error=lambda *args: errors.append(args),
        )
        errors = []
        await dashboard_module.websocket_destination(
            hass,
            connection,
            {"id": 1, "action": "search", "query": "Hamburg", "language": "en"},
        )
        self.assertEqual(errors[0][1], "unauthorized")
        lookup.search.assert_not_awaited()

    async def test_selection_cache_is_bound_to_user_and_expiry(self):
        import time

        manager, _ = make_manager()
        hass = manager.hass
        hass.registry = types.SimpleNamespace(
            async_get_entity_id=lambda *a: "button.start"
        )
        cache = {
            "other": (time.monotonic() + 600, "other-user", TARGET),
            "expired": (0, "user", TARGET),
        }
        hass.data["route_progress"] = {"manager": manager, "results": cache}
        errors = []
        connection = types.SimpleNamespace(
            user=types.SimpleNamespace(
                id="user",
                permissions=types.SimpleNamespace(check_entity=lambda *a: True),
            ),
            send_error=lambda *args: errors.append(args),
        )
        for target in cache:
            await dashboard_module.websocket_destination(
                hass, connection, {"id": 1, "action": "select", "target_id": target}
            )
        self.assertEqual(
            [error[1] for error in errors], ["result_expired", "result_expired"]
        )
        self.assertIsNone(manager.manual_destination)
