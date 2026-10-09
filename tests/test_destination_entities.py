"""Native entity workflow uses the same confirmed destination as the card."""

import asyncio
import time
import types
import unittest
from unittest.mock import AsyncMock

from ha_test_support import HAError, dashboard_module, make_manager

TARGET = {
    "name": "Hamburg",
    "latitude": 53.55,
    "longitude": 10.01,
    "address": "Hamburg, Germany",
    "source": "geoapify",
}


class EntityTests(unittest.IsolatedAsyncioTestCase):
    def setup_entities(self):
        manager, _ = make_manager()
        manager.hass.config = types.SimpleNamespace(language="de")
        lookup = types.SimpleNamespace(
            search=AsyncMock(return_value=[TARGET, {**TARGET, "longitude": 10.02}])
        )
        manager.hass.data["route_progress"] = {"lookup": lookup}
        text = dashboard_module.test_text.RouteProgressDestinationQuery(manager)
        text.hass = manager.hass
        select = dashboard_module.test_select.RouteProgressDestinationSelect(manager)
        sensor = dashboard_module.test_sensor.RouteProgressDestinationSensor(manager)
        return manager, lookup, text, select, sensor

    async def test_search_requires_selection_then_updates_sensor_without_start(self):
        manager, lookup, text, select, sensor = self.setup_entities()
        manager.available = False
        self.assertTrue(text.available)
        await text.async_set_value("Hamburg")
        self.assertIsNone(manager.manual_destination)
        self.assertEqual(len(set(select.options)), 2)
        await select.async_select_option(select.options[1])
        self.assertEqual(sensor.native_value, "Hamburg")
        self.assertEqual(sensor.extra_state_attributes["longitude"], 10.02)
        self.assertIn("Geoapify", sensor.extra_state_attributes["attribution"])
        self.assertEqual(select.current_option, select.options[1])
        manager.api.async_create_trip.assert_not_called()
        lookup.search.assert_awaited_once_with("Hamburg", "de")
        manager.destination_results_until = time.monotonic() - 1
        with self.assertRaisesRegex(HAError, "result_expired"):
            await select.async_select_option(select.options[0])

    async def test_zones_need_no_lookup_and_read_current_coordinates(self):
        manager, lookup, _, _, sensor = self.setup_entities()
        zone = types.SimpleNamespace(
            name="Home",
            entity_id="zone.home",
            attributes={"latitude": 53.6, "longitude": 10.3},
        )
        manager.hass.states.async_all = lambda _: [zone]
        select = dashboard_module.test_select.RouteProgressDestinationSelect(
            manager, zones=True
        )
        select._context = types.SimpleNamespace(user_id=None)
        await select.async_select_option(select.options[0])
        lookup.search.assert_not_called()
        self.assertEqual(sensor.extra_state_attributes["latitude"], 53.6)
        zone.attributes["latitude"] = 53.7
        self.assertIsNone(select.current_option)
        self.assertEqual(sensor.extra_state_attributes["latitude"], 53.6)

    async def test_slow_search_cannot_replace_newer_results(self):
        manager, lookup, text, select, _ = self.setup_entities()
        gate = asyncio.Event()

        async def search(value, language):
            if value == "Old":
                await gate.wait()
            return [{**TARGET, "address": value}]

        lookup.search.side_effect = search
        old = asyncio.create_task(text.async_set_value("Old"))
        await asyncio.sleep(0)
        await text.async_set_value("New")
        gate.set()
        await old
        self.assertEqual(select.options, ["1. New"])
        await text.async_set_value("")
        self.assertEqual(select.options, [])

    async def test_initial_confirmation_preserves_real_observation(self):
        manager, _ = make_manager()
        await manager.async_select_destination(TARGET)
        manager.api.async_confirm_initial_destination.return_value = {
            "status": "en_route",
            "accepts_updates": True,
        }
        manager.api.async_update_trip.side_effect = [
            {"status": "confirming_destination", "accepts_updates": True},
            {"status": "en_route", "accepts_updates": True},
        ]
        await manager.async_manual_start()
        self.assertEqual(manager.status, "en_route")
        calls = manager.api.async_update_trip.call_args_list
        self.assertEqual(calls[0].args[1], calls[1].args[1])
        manager.api.async_confirm_initial_destination.assert_awaited_once()

    async def test_older_server_fallback_is_only_probed_once(self):
        manager, _ = make_manager()
        await manager.async_select_destination(TARGET)
        await manager.async_manual_start()
        await manager.async_sync()
        manager.api.async_confirm_initial_destination.assert_awaited_once()
        self.assertTrue(manager.available)
