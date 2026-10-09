"""Destination lookup performed only by Home Assistant, never the share server."""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
from datetime import UTC, datetime
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

import aiohttp


class DestinationError(Exception):
    """A safe, translatable lookup error; never includes request URLs or keys."""


GOOGLE_HOSTS = {
    "maps.app.goo.gl",
    "goo.gl",
    "maps.google.com",
    "www.google.com",
    "google.com",
    "www.google.de",
    "maps.google.de",
    "google.de",
    "www.google.at",
    "www.google.ch",
    "www.google.fr",
    "www.google.nl",
    "www.google.co.uk",
}
SHORT_HOSTS = {"maps.app.goo.gl", "goo.gl"}


def validate_maps_url(value: str) -> str:
    """Allow only HTTPS Google Maps URLs, including every redirect hop."""
    try:
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or url.hostname not in GOOGLE_HOSTS
            or url.username
            or url.password
            or url.port not in (None, 443)
            or "\\" in value
            or len(value) > 4096
        ):
            raise ValueError
        if url.hostname == "goo.gl" and not url.path.startswith("/maps/"):
            raise ValueError
        if (
            url.hostname not in SHORT_HOSTS
            and url.hostname != "maps.google.com"
            and not url.path.startswith("/maps")
        ):
            raise ValueError
    except ValueError:
        raise DestinationError("unsupported_link") from None
    return value


def point_result(name: str, latitude: object, longitude: object) -> dict:
    """Validate a target before exposing or persisting it."""
    try:
        lat, lon = float(latitude), float(longitude)
        if (
            not math.isfinite(lat)
            or not math.isfinite(lon)
            or not -90 <= lat <= 90
            or not -180 <= lon <= 180
            or (lat == 0 and lon == 0)
        ):
            raise ValueError
    except (TypeError, ValueError):
        raise DestinationError("invalid_destination") from None
    return {
        "name": str(name).strip()[:200] or f"{lat:.5f}, {lon:.5f}",
        "latitude": lat,
        "longitude": lon,
    }


def parse_maps_target(value: str) -> dict | str:
    """Extract explicit targets only. An @latitude,longitude viewport is not a target."""
    validate_maps_url(value)
    url = urlsplit(value)
    query = parse_qs(url.query)
    if query.get("waypoints") or ("/dir/" in url.path and not query.get("destination")):
        raise DestinationError("ambiguous_link")
    target = next(
        (query[k][0] for k in ("destination", "daddr", "query", "q") if query.get(k)),
        "",
    )
    path = unquote(url.path)
    name_match = re.search(r"/place/([^/]+)", path)
    name = name_match.group(1).replace("+", " ") if name_match else ""
    if target and not target.startswith("place_id:"):
        match = re.fullmatch(
            r"\s*([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)\s*", target
        )
        if match:
            return point_result(name, *match.groups())
        return target
    points = re.findall(r"!3d([+-]?[\d.]+)!4d([+-]?[\d.]+)", unquote(value))
    if len(set(points)) == 1:
        return point_result(name, *points[0])
    if len(set(points)) > 1:
        raise DestinationError("ambiguous_link")
    if name:
        return name
    raise DestinationError("unsupported_link")


class DestinationLookup:
    """Bounded Geoapify requests and redirect-only Maps short-link resolution."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        self.session = session
        self.api_key = api_key
        self._lock = asyncio.Lock()
        self._last_request = 0.0
        self.connected: bool | None = None
        self.last_checked: datetime | None = None
        self.last_successful_connection: datetime | None = None
        self.last_error: str | None = None
        self._checked_monotonic = 0.0
        self._check_lock = asyncio.Lock()
        self._listeners = set()

    def add_listener(self, listener):
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def _record_status(self, error=None):
        self.connected = error is None
        self.last_checked = datetime.now(UTC)
        self._checked_monotonic = time.monotonic()
        self.last_error = error
        if error is None:
            self.last_successful_connection = self.last_checked
        for listener in tuple(self._listeners):
            listener()

    async def check_api(self):
        """Reuse recent provider responses; serialize concurrent setup checks."""
        if not self.api_key:
            return
        async with self._check_lock:
            ttl = 900 if self.connected else 60
            if self.last_checked and time.monotonic() - self._checked_monotonic < ttl:
                if self.last_error:
                    raise DestinationError(self.last_error)
                return
            # A fixed public place checks the actual autocomplete permission.
            # No private address is needed and no periodic probe is scheduled.
            await self.search("Berlin")

    async def search(self, text: str, language: str = "en") -> list[dict]:
        text = text.strip()
        if not 3 <= len(text) <= 4096:
            raise DestinationError("invalid_query")
        # All users share one limiter. No unlimited queue of keystroke requests.
        if self._lock.locked():
            raise DestinationError("rate_limited")
        async with self._lock:
            loop = asyncio.get_running_loop()
            if loop.time() - self._last_request < 0.4:
                raise DestinationError("rate_limited")
            self._last_request = loop.time()
            if re.match(r"https?://", text, re.I):
                target = parse_maps_target(await self._expand(text))
                if isinstance(target, dict):
                    return [{**target, "address": "", "source": "google_maps"}]
                text = target
            if not self.api_key:
                raise DestinationError("api_key_required")
            if (
                self.last_error in {"invalid_api_key", "rate_limited"}
                and time.monotonic() - self._checked_monotonic < 60
            ):
                # Do not spend requests on a known invalid key or exhausted quota.
                # Coordinate links above still work during this cooldown.
                raise DestinationError(self.last_error)
            try:
                async with self.session.get(
                    "https://api.geoapify.com/v1/geocode/autocomplete",
                    params={
                        "text": text[:500],
                        "limit": 5,
                        "lang": language if language in {"de", "en"} else "en",
                        "apiKey": self.api_key,
                    },
                    timeout=aiohttp.ClientTimeout(total=12),
                    allow_redirects=False,
                ) as response:
                    if response.status in (401, 403):
                        raise DestinationError("invalid_api_key")
                    if response.status == 429:
                        raise DestinationError("rate_limited")
                    if response.status != 200:
                        raise DestinationError("lookup_failed")
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(16384):
                        body.extend(chunk)
                        if len(body) > 256_000:
                            raise DestinationError("lookup_failed")
                    payload = json.loads(body)
            except DestinationError as err:
                self._record_status(str(err))
                raise
            except (aiohttp.ClientError, TimeoutError, ValueError):
                self._record_status("lookup_failed")
                raise DestinationError("lookup_failed") from None
        results = []
        if not isinstance(payload, dict) or not isinstance(
            payload.get("features"), list
        ):
            self._record_status("lookup_failed")
            raise DestinationError("lookup_failed")
        self._record_status()
        for feature in payload.get("features", [])[:5]:
            if not isinstance(feature, dict) or not isinstance(
                feature.get("properties"), dict
            ):
                continue
            props = feature.get("properties", {})
            try:
                result = point_result(
                    props.get("name")
                    or props.get("address_line1")
                    or props.get("formatted", ""),
                    props.get("lat"),
                    props.get("lon"),
                )
            except DestinationError:
                continue
            results.append(
                {
                    **result,
                    "address": str(props.get("formatted", ""))[:500],
                    "source": "geoapify",
                }
            )
        return results

    async def _expand(self, value: str) -> str:
        current = validate_maps_url(value)
        for _ in range(5):
            if urlsplit(current).hostname not in SHORT_HOSTS:
                return current
            try:
                async with self.session.get(
                    current,
                    allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as response:
                    if (
                        response.status not in (301, 302, 303, 307, 308)
                        or "Location" not in response.headers
                    ):
                        raise DestinationError("unsupported_link")
                    current = validate_maps_url(
                        urljoin(current, response.headers["Location"])
                    )
            except (aiohttp.ClientError, TimeoutError):
                raise DestinationError("lookup_failed") from None
        raise DestinationError("unsupported_link")
