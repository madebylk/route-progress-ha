"""Exercise actual config steps, manual state and dashboard authorization."""

import types
import unittest
from unittest.mock import AsyncMock, patch

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

    async def test_provider_attribution_survives_restart(self):
        manager, _ = make_manager()
        target = {**TARGET, "source": "geoapify", "address": "Home, Hamburg"}
        await manager.async_select_destination(target)
        restored, _ = make_manager()
        restored._store.data = manager._store.data
        await restored.async_load()
        self.assertEqual(restored.manual_destination, target)
        self.assertEqual(restored._snapshot().create_payload()["destination"], TARGET)

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
        flow.hass = types.SimpleNamespace(data={})
        with patch.object(
            config_module,
            "get_lookup",
            return_value=types.SimpleNamespace(check_api=AsyncMock()),
        ):
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


class GeoapifyFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_key_stays_in_form_and_does_not_save(self):
        for flow_class in [
            config_module.RouteProgressConfigFlow,
            config_module.RouteProgressOptionsFlow,
        ]:
            flow = flow_class()
            flow.hass = types.SimpleNamespace(data={})
            flow._pending = dict(COMMON)
            check = AsyncMock(
                side_effect=config_module.DestinationError("invalid_api_key")
            )
            with patch.object(
                config_module,
                "get_lookup",
                return_value=types.SimpleNamespace(check_api=check),
            ):
                result = await flow.async_step_destination(
                    {"geoapify_api_key": "wrong"}
                )
            self.assertEqual(result["type"], "form")
            self.assertEqual(
                result["errors"], {"geoapify_api_key": "geoapify_invalid_key"}
            )
            check.assert_awaited_once()

    async def test_errors_mapped_without_sensitive_provider_details(self):
        for code, expected in [
            ("rate_limited", "geoapify_rate_limited"),
            ("lookup_failed", "geoapify_unavailable"),
        ]:
            flow = config_module.RouteProgressConfigFlow()
            flow.hass = types.SimpleNamespace(data={})
            flow._pending = dict(COMMON)
            with patch.object(
                config_module,
                "get_lookup",
                return_value=types.SimpleNamespace(
                    check_api=AsyncMock(
                        side_effect=config_module.DestinationError(code)
                    )
                ),
            ):
                result = await flow.async_step_destination(
                    {"geoapify_api_key": "secret"}
                )
            self.assertEqual(result["errors"]["geoapify_api_key"], expected)

    async def test_blank_key_and_entity_mode_skip_check(self):
        for mode, values in [
            ("manual", {"geoapify_api_key": "  "}),
            (
                "entities",
                {
                    "destination_entity": "sensor.name",
                    "destination_position_entity": "sensor.point",
                },
            ),
        ]:
            flow = config_module.RouteProgressConfigFlow()
            flow._pending = {**COMMON, "destination_source": mode}
            with patch.object(config_module, "get_lookup") as lookup:
                result = await flow.async_step_destination(values)
            lookup.assert_not_called()
            self.assertEqual(result["type"], "create_entry")
            self.assertNotIn("geoapify_api_key", result["data"])

    async def test_lookup_cache_is_scoped_to_key(self):
        hass = types.SimpleNamespace(data={})
        first = config_module.get_lookup(hass, "one")
        self.assertIs(first, config_module.get_lookup(hass, " one "))
        other = config_module.get_lookup(hass, "two")
        self.assertIsNot(first, other)
        self.assertIsNone(other.connected)
        self.assertNotIn("one", hass.data["route_progress"]["geoapify_clients"])

    async def test_diagnostic_is_independent_of_cloud_and_makes_no_requests(self):
        manager, _ = make_manager()
        manager.api.base_url = "https://example.com"
        manager.available = False
        manager.geoapify = config_module.get_lookup(manager.hass, "secret")
        sensor = dashboard_module.test_binary_sensor.RouteProgressGeoapifyConnectionBinarySensor(
            manager
        )
        self.assertTrue(sensor.available)
        self.assertIsNone(sensor.is_on)
        manager.geoapify._record_status()
        self.assertTrue(sensor.is_on)
        manager.geoapify._record_status("rate_limited")
        self.assertFalse(sensor.is_on)
        self.assertEqual(sensor.extra_state_attributes["last_error"], "rate_limited")
        self.assertNotIn("secret", str(sensor.extra_state_attributes))

    async def test_setup_reuses_config_check_and_unsubscribes_on_unload(self):
        from test_destination import Response, Session

        manager, _ = make_manager()
        manager.config["geoapify_api_key"] = "shared-key"
        lookup = config_module.get_lookup(manager.hass, "shared-key")
        lookup.session = Session(Response(payload={"features": []}))
        await lookup.check_api()
        manager.hass.data["route_progress"]["card_registered"] = True
        await dashboard_module.async_setup_dashboard(manager.hass, manager)
        self.assertIs(manager.geoapify, lookup)
        self.assertEqual(len(lookup.session.requests), 1)
        self.assertEqual(len(lookup._listeners), 1)
        await manager.async_stop()
        self.assertEqual(len(lookup._listeners), 0)
