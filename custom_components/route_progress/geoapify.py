"""Share bounded, in-memory validation results between config and runtime."""

from hashlib import sha256

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .destination import DestinationLookup


def get_lookup(hass, api_key):
    api_key = str(api_key or "").strip()
    cache = hass.data.setdefault(DOMAIN, {}).setdefault("geoapify_clients", {})
    key = sha256(api_key.encode()).hexdigest()
    if key not in cache:
        while len(cache) >= 4:
            del cache[next(iter(cache))]
        cache[key] = DestinationLookup(async_get_clientsession(hass), api_key)
    return cache[key]
