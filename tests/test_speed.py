"""Check speed selection and JSON delivery through the real HA API client."""

import types
import unittest

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer

from ha_test_support import make_manager, manager_module


class SpeedDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_speed_sources_reach_http_without_defaulting_missing_to_zero(self):
        received = []

        async def receive(request):
            received.append(await request.json())
            return web.json_response({"status": "en_route", "accepts_updates": True})

        app = web.Application()
        app.router.add_post("/api/v1/trips/trip/updates", receive)
        cases = [
            ("no source", None, None, None),
            ("entity zero overrides attribute", "0", 42, 0),
            ("entity takes priority", "83.5", 42, 83.5),
            ("attribute without entity", None, 42, 42),
            ("attribute zero", None, 0, 0),
            ("unavailable entity falls back", "unavailable", 42, 42),
            ("unknown entity", "unknown", None, None),
            ("invalid entity", "invalid", None, None),
            ("negative entity", "-1", None, None),
            ("invalid attribute", None, "unavailable", None),
            ("nonfinite attribute", None, "nan", None),
            ("speed returns", "30", None, 30),
            ("speed disappears", "unavailable", None, None),
        ]
        async with TestServer(app) as server, ClientSession() as session:
            for manual in (False, True):
                manager, states = make_manager(manual)
                manager.trip_id, manager.accepts_updates = "trip", True
                manager.api = manager_module.RouteProgressAPI(
                    session, str(server.make_url("")), "test-token"
                )
                for name, entity, attribute, expected in cases:
                    with self.subTest(mode=manual, case=name):
                        manager.config.pop("speed_entity", None)
                        if entity is not None:
                            manager.config["speed_entity"] = "sensor.speed"
                            states["sensor.speed"] = types.SimpleNamespace(
                                state=entity, attributes={}
                            )
                        attributes = states["device_tracker.phone"].attributes
                        attributes.pop("speed", None)
                        if attribute is not None:
                            attributes["speed"] = attribute
                        await manager.async_sync()
                        self.assertIn("speed_kmh", received[-1])
                        self.assertEqual(received[-1]["speed_kmh"], expected)
                        self.assertIn("position", received[-1])
