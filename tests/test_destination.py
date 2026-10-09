"""Lookup contract tests with deterministic HTTP responses (no API key/network)."""

import importlib.util
import json
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "route_destination_test",
    Path(__file__).parents[1] / "custom_components/route_progress/destination.py",
)
destination = importlib.util.module_from_spec(spec)
spec.loader.exec_module(destination)


class Response:
    def __init__(self, status=200, payload=None, headers=None, raw=None):
        self.status = status
        self.headers = headers or {}
        self.raw = raw if raw is not None else json.dumps(payload).encode()
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def iter_chunked(self, _size):
        # Exercise responses split across arbitrary network chunks.
        for start in range(0, len(self.raw), 11):
            yield self.raw[start : start + 11]


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.responses.pop(0)


class MapsParserTests(unittest.TestCase):
    def test_target_not_viewport(self):
        result = destination.parse_maps_target(
            "https://www.google.com/maps/place/Hotel/@40,5,10z/data=!3d53.5!4d10.2"
        )
        self.assertEqual(result["latitude"], 53.5)
        self.assertEqual(result["name"], "Hotel")
        with self.assertRaisesRegex(destination.DestinationError, "unsupported_link"):
            destination.parse_maps_target("https://www.google.com/maps/@40,5,10z")

    def test_query_coordinates_and_address(self):
        self.assertEqual(
            destination.parse_maps_target(
                "https://www.google.com/maps/search/?api=1&query=53.5%2C10.2"
            )["longitude"],
            10.2,
        )
        self.assertEqual(
            destination.parse_maps_target(
                "https://www.google.com/maps/search/?api=1&query=Hamburg+Hbf"
            ),
            "Hamburg Hbf",
        )

    def test_single_explicit_route_destination(self):
        self.assertEqual(
            destination.parse_maps_target(
                "https://www.google.com/maps/dir/?api=1&destination=Hamburg"
            ),
            "Hamburg",
        )
        for url in [
            "https://www.google.com/maps/dir/Berlin/Hamburg/",
            "https://www.google.com/maps/dir/?destination=Hamburg&waypoints=Luebeck",
        ]:
            with (
                self.subTest(url=url),
                self.assertRaisesRegex(destination.DestinationError, "ambiguous_link"),
            ):
                destination.parse_maps_target(url)

    def test_ssrf_and_credential_urls_rejected(self):
        for url in [
            "https://127.0.0.1/maps",
            "http://maps.app.goo.gl/x",
            "https://maps.app.goo.gl.evil.test/x",
            "https://user:password@maps.app.goo.gl/x",
            "https://www.google.com:8443/maps",
            "https://www.google.com/url?q=https://localhost",
            "https://goo.gl/notmaps",
            "https://www.google.com/maps\\@evil.test",
        ]:
            with self.subTest(url=url), self.assertRaises(destination.DestinationError):
                destination.validate_maps_url(url)

    def test_opaque_place_and_multiple_targets_rejected(self):
        for url in [
            "https://www.google.com/maps/search/?query=place_id:abc",
            "https://www.google.com/maps/place/Hotel/data=!3d53!4d10!3d54!4d11",
        ]:
            with self.subTest(url=url), self.assertRaises(destination.DestinationError):
                destination.parse_maps_target(url)

    def test_invalid_coordinates_rejected(self):
        for lat, lon in [
            (91, 0),
            (0, 181),
            (float("nan"), 10),
            (53, float("inf")),
            (0, 0),
            (None, 10),
        ]:
            with self.subTest(lat=lat), self.assertRaises(destination.DestinationError):
                destination.point_result("Target", lat, lon)


class LookupTests(unittest.IsolatedAsyncioTestCase):
    async def test_geoapify_request_and_normalization(self):
        session = Session(
            Response(
                payload={
                    "features": [
                        {
                            "properties": {
                                "name": "Hotel",
                                "formatted": "Hotel, Hamburg",
                                "lat": 53.5,
                                "lon": 10.2,
                            }
                        },
                        {"properties": {"lat": 999, "lon": 10}},
                    ]
                }
            )
        )
        result = await destination.DestinationLookup(session, "private-key").search(
            "Hotel Hamburg", "de"
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Hotel")
        self.assertEqual(session.requests[0][1]["params"]["apiKey"], "private-key")
        self.assertFalse(session.requests[0][1]["allow_redirects"])
        self.assertNotIn("private-key", str(result))

    async def test_keyless_coordinate_link_does_not_call_geoapify(self):
        session = Session()
        results = await destination.DestinationLookup(session, "").search(
            "https://www.google.com/maps/search/?query=53,10"
        )
        self.assertEqual(results[0]["latitude"], 53)
        self.assertEqual(session.requests, [])

    async def test_shortlink_redirect_and_ssrf_rejection(self):
        session = Session(
            Response(
                302,
                headers={"Location": "https://www.google.com/maps/search/?query=53,10"},
            )
        )
        results = await destination.DestinationLookup(session, "").search(
            "https://maps.app.goo.gl/abc"
        )
        self.assertEqual(results[0]["source"], "google_maps")
        session = Session(
            Response(302, headers={"Location": "http://127.0.0.1/private"})
        )
        with self.assertRaisesRegex(destination.DestinationError, "unsupported_link"):
            await destination.DestinationLookup(session, "").search(
                "https://maps.app.goo.gl/abc"
            )
        self.assertEqual(len(session.requests), 1)

    async def test_timeout_and_provider_errors_are_safe(self):
        for status, code in [
            (401, "invalid_api_key"),
            (403, "invalid_api_key"),
            (429, "rate_limited"),
            (500, "lookup_failed"),
        ]:
            lookup = destination.DestinationLookup(Session(Response(status)), "secret")
            with (
                self.subTest(status=status),
                self.assertRaisesRegex(destination.DestinationError, code),
            ):
                await lookup.search("Hamburg")

    async def test_malformed_and_oversize_payload(self):
        for raw in [b"broken", b"[]", b'{"features":null}', b" " * 256001]:
            with (
                self.subTest(size=len(raw)),
                self.assertRaisesRegex(destination.DestinationError, "lookup_failed"),
            ):
                await destination.DestinationLookup(
                    Session(Response(raw=raw)), "secret"
                ).search("Hamburg")

    async def test_missing_key_and_empty_query(self):
        lookup = destination.DestinationLookup(Session(), "")
        for text, code in [("Hamburg", "api_key_required"), ("a", "invalid_query")]:
            with (
                self.subTest(text=text),
                self.assertRaisesRegex(destination.DestinationError, code),
            ):
                await lookup.search(text)

    async def test_rate_limiter(self):
        lookup = destination.DestinationLookup(
            Session(Response(payload={"features": []})), "secret"
        )
        self.assertEqual(await lookup.search("Hamburg"), [])
        with self.assertRaisesRegex(destination.DestinationError, "rate_limited"):
            await lookup.search("Hannover")
        await lookup._lock.acquire()
        with self.assertRaisesRegex(destination.DestinationError, "rate_limited"):
            await lookup.search("Berlin")
        lookup._lock.release()
