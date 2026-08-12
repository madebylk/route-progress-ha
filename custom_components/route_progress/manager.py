"""Trip lifecycle management for Route Progress."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import (
    RouteProgressAPI,
    RouteProgressAPIError,
    RouteProgressGoneError,
)
from .const import (
    CONF_BATTERY_AT_ARRIVAL_ENTITY,
    CONF_CHARGING_ENTITY,
    CONF_CHARGING_MINUTES_ENTITY,
    CONF_DESTINATION_ENTITY,
    CONF_DESTINATION_POSITION_ENTITY,
    CONF_DISTANCE_ENTITY,
    CONF_ETA_ENTITY,
    CONF_HEADING_ENTITY,
    CONF_SPEED_ENTITY,
    CONF_TRAFFIC_DELAY_ENTITY,
    CONF_UPDATE_INTERVAL,
    CONF_VEHICLE_POSITION_ENTITY,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    UNKNOWN_STATES,
)
from .models import TripSnapshot

_LOGGER = logging.getLogger(__name__)

_DESTINATION_CONFIRMATION_STATUSES = {
    "waiting_for_destination",
    "confirming_destination",
}


class RouteProgressManager:
    """Observe HA entities and keep one Route Progress trip in sync."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: RouteProgressAPI,
        config: dict[str, Any],
    ) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.entry = entry
        self.api = api
        self.config = config
        self.trip_id: str | None = None
        self.share_url: str | None = None
        self.expires_at: str | None = None
        self.destination_name: str | None = None
        self.status = "idle"
        self.accepts_updates = False
        self.arrived_at: str | None = None
        self.arrival_detection: str | None = None
        self.arrival_followup_until: str | None = None
        self.finished_at: str | None = None
        self.last_successful_connection: datetime | None = None
        self.last_error: str | None = None
        self.available = True

        self._store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.{entry.entry_id}"
        )
        self._listeners: set[Callable[[], None]] = set()
        self._unsubscribers: list[Callable[[], None]] = []
        self._lock = asyncio.Lock()
        self._last_sent_position: tuple[float, float] | None = None
        self._last_observed_speed: float | None = None

    @property
    def active(self) -> bool:
        """Return whether a trip is currently tracked."""
        return self.trip_id is not None and self.accepts_updates

    @property
    def can_start(self) -> bool:
        """Return whether a waiting share can be created."""
        return self.available and not self.active

    @property
    def can_accept_destination(self) -> bool:
        """Return whether the currently observed destination can be accepted."""
        return (
            self.trip_id is not None
            and self.status == "destination_changed"
            and self._snapshot().destination_valid
        )

    def record_connection_error(self, err: RouteProgressAPIError) -> None:
        """Record an API error detected while setting up the integration."""
        self._mark_error(err)

    async def async_load(self) -> None:
        """Restore the active trip state after a HA restart."""
        data = await self._store.async_load() or {}
        self.trip_id = _optional_string(data.get("trip_id"))
        self.share_url = _optional_string(data.get("share_url"))
        self.expires_at = _optional_string(data.get("expires_at"))
        self.destination_name = _optional_string(data.get("destination_name"))
        self.status = _optional_string(data.get("status")) or (
            "en_route" if self.trip_id else "idle"
        )
        self.accepts_updates = bool(
            data.get("accepts_updates", self.trip_id is not None)
        )
        self.arrived_at = _optional_string(data.get("arrived_at"))
        self.arrival_detection = _optional_string(data.get("arrival_detection"))
        self.arrival_followup_until = _optional_string(
            data.get("arrival_followup_until")
        )
        self.finished_at = _optional_string(data.get("finished_at"))

    async def async_start(self) -> None:
        """Start entity and interval listeners, then update restored state."""
        destination_entities = [
            self.config[CONF_DESTINATION_ENTITY],
            self.config[CONF_DESTINATION_POSITION_ENTITY],
        ]
        self._unsubscribers.append(
            async_track_state_change_event(
                self.hass, destination_entities, self._async_destination_changed
            )
        )
        interval = int(self.config.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
        self._unsubscribers.append(
            async_track_time_interval(
                self.hass, self._async_interval, timedelta(seconds=interval)
            )
        )
        if self.trip_id:
            await self._async_refresh_state()
        await self.async_sync()

    async def async_stop(self) -> None:
        """Unregister listeners without ending a remotely active trip."""
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe an entity to manager state changes."""
        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    async def async_sync(self, *, destination_event: bool = False) -> None:
        """Update an active trip based on the current Home Assistant state."""
        async with self._lock:
            snapshot = self._snapshot()

            if self.trip_id is None:
                await self._async_check_connection()
                return
            if self.accepts_updates:
                has_new_position = self._has_new_position(snapshot)
                if (
                    destination_event
                    or self.status in _DESTINATION_CONFIRMATION_STATUSES
                    or has_new_position
                ):
                    await self._async_update(snapshot)
                    return
                if self.arrival_detection is not None:
                    await self._async_update(snapshot, arrival_observation=True)
                    return
                await self._async_check_connection()
                return
            await self._async_check_connection()

    async def async_manual_start(self) -> None:
        """Create a trip after the Home Assistant start button is pressed."""
        async with self._lock:
            if self.active:
                return
            snapshot = self._snapshot()
            await self._async_create(snapshot)

    async def async_accept_destination(self) -> None:
        """Explicitly replace the server-owned shared destination."""
        async with self._lock:
            if not self.trip_id:
                return
            snapshot = self._snapshot()
            if not snapshot.destination_valid:
                return
            try:
                result = await self.api.async_accept_destination(
                    self.trip_id,
                    snapshot.create_payload()["destination"],
                )
            except RouteProgressGoneError:
                await self._async_clear("expired")
                return
            except RouteProgressAPIError as err:
                self._mark_error(err)
                return
            self._apply_server_state(result)
            self._mark_success()
            await self._async_save_and_notify()

    async def async_manual_stop(self) -> None:
        """Finish the active trip from the HA button entity."""
        async with self._lock:
            if not self.trip_id:
                return
            await self._async_finish()

    async def _async_create(self, snapshot: TripSnapshot) -> None:
        """Create and persist a new trip."""
        try:
            result = await self.api.async_create_trip({})
        except RouteProgressAPIError as err:
            self._mark_error(err)
            return

        self.trip_id = str(result["trip_id"])
        self.share_url = str(result["share_url"])
        self.expires_at = str(result["expires_at"])
        self._last_sent_position = None
        self._last_observed_speed = None
        self._apply_server_state(result)
        self._mark_success()
        await self._async_save_and_notify()
        _LOGGER.info("Created waiting Route Progress share")
        if self.accepts_updates and snapshot.destination_valid:
            await self._async_update(snapshot)

    async def _async_check_connection(self) -> None:
        """Check API connectivity without creating or changing a trip."""
        try:
            await self.api.async_check_auth()
        except RouteProgressAPIError as err:
            self._mark_error(err)
            return
        self._mark_success()
        self._notify_listeners()

    async def _async_refresh_state(self) -> None:
        """Reconcile restored local state with the authoritative backend."""
        if not self.trip_id:
            return
        try:
            result = await self.api.async_get_trip(self.trip_id)
        except RouteProgressGoneError:
            await self._async_clear("expired")
            return
        except RouteProgressAPIError as err:
            self._mark_error(err)
            return
        self._apply_server_state(result)
        self._mark_success()
        await self._async_save_and_notify()

    async def _async_update(
        self, snapshot: TripSnapshot, *, arrival_observation: bool = False
    ) -> None:
        """Send current route values for the active trip."""
        if not self.trip_id:
            return
        payload = (
            snapshot.arrival_observation_payload()
            if arrival_observation
            else snapshot.update_payload()
        )
        try:
            result = await self.api.async_update_trip(self.trip_id, payload)
        except RouteProgressGoneError:
            await self._async_clear("expired")
            return
        except RouteProgressAPIError as err:
            self._mark_error(err)
            return
        self._apply_server_state(result)
        if not arrival_observation:
            self._last_sent_position = snapshot.position_key
        self._mark_success()
        await self._async_save_and_notify()

    async def _async_finish(self) -> None:
        """Finish the active trip."""
        if not self.trip_id:
            return
        try:
            result = await self.api.async_finish_trip(self.trip_id)
        except RouteProgressAPIError as err:
            self._mark_error(err)
            return
        if result:
            self._apply_server_state(result)
        else:
            await self._async_clear("expired")
            return
        self._mark_success()
        _LOGGER.info("Finished Route Progress trip")
        await self._async_save_and_notify()

    async def _async_clear(self, status: str = "idle") -> None:
        """Clear active state while retaining the last share URL."""
        self.trip_id = None
        self.status = status
        self.accepts_updates = False
        self._mark_success()
        await self._async_save_and_notify()

    async def _async_save_and_notify(self) -> None:
        """Persist lifecycle data and update attached entities."""
        await self._store.async_save(
            {
                "trip_id": self.trip_id,
                "share_url": self.share_url,
                "expires_at": self.expires_at,
                "destination_name": self.destination_name,
                "status": self.status,
                "accepts_updates": self.accepts_updates,
                "arrived_at": self.arrived_at,
                "arrival_detection": self.arrival_detection,
                "arrival_followup_until": self.arrival_followup_until,
                "finished_at": self.finished_at,
            }
        )
        self._notify_listeners()

    def _apply_server_state(self, data: dict[str, Any]) -> None:
        """Adopt lifecycle facts decided by the backend."""
        self.status = str(data.get("status") or self.status)
        self.accepts_updates = bool(data.get("accepts_updates", False))
        self.destination_name = _optional_string(data.get("destination_name"))
        self.expires_at = _optional_string(data.get("expires_at")) or self.expires_at
        self.arrived_at = _optional_string(data.get("arrived_at"))
        self.arrival_detection = _optional_string(data.get("arrival_detection"))
        self.arrival_followup_until = _optional_string(
            data.get("arrival_followup_until")
        )
        self.finished_at = _optional_string(data.get("finished_at"))

    def _snapshot(self) -> TripSnapshot:
        """Collect a consistent snapshot from configured HA entities."""
        destination_state = self._state(CONF_DESTINATION_ENTITY)
        destination_position = self._state(CONF_DESTINATION_POSITION_ENTITY)
        vehicle_position = self._state(CONF_VEHICLE_POSITION_ENTITY)

        destination_name = ""
        if destination_state and destination_state.state.lower() not in UNKNOWN_STATES:
            destination_name = destination_state.state.strip()

        heading = self._number_state(CONF_HEADING_ENTITY)
        if heading is None and vehicle_position:
            heading = _as_number(
                vehicle_position.attributes.get(
                    "heading", vehicle_position.attributes.get("course")
                )
            )
        speed = self._number_state(CONF_SPEED_ENTITY)
        if speed is None and vehicle_position:
            speed = _as_number(vehicle_position.attributes.get("speed"))

        return TripSnapshot(
            destination_name=destination_name,
            destination_latitude=_attribute_number(destination_position, "latitude"),
            destination_longitude=_attribute_number(destination_position, "longitude"),
            latitude=_attribute_number(vehicle_position, "latitude"),
            longitude=_attribute_number(vehicle_position, "longitude"),
            position_observed_at=(
                vehicle_position.last_updated if vehicle_position else None
            ),
            heading=heading,
            speed_kmh=speed,
            eta_minutes=self._eta_minutes(),
            distance_km=self._number_state(CONF_DISTANCE_ENTITY),
            traffic_delay_minutes=self._number_state(CONF_TRAFFIC_DELAY_ENTITY),
            charging_minutes=self._number_state(CONF_CHARGING_MINUTES_ENTITY),
            is_charging=self._charging_state(),
            battery_at_arrival=self._number_state(CONF_BATTERY_AT_ARRIVAL_ENTITY),
        )

    def _has_new_position(self, snapshot: TripSnapshot) -> bool:
        """Return whether position changed or the vehicle has just stopped."""
        position = snapshot.position_key
        stopped = (
            snapshot.speed_kmh == 0
            and self._last_observed_speed != 0
            and position is not None
        )
        self._last_observed_speed = snapshot.speed_kmh
        return stopped or (
            position is not None and position != self._last_sent_position
        )

    def _state(self, config_key: str) -> State | None:
        """Return a state for a configured entity key."""
        entity_id = self.config.get(config_key)
        if not entity_id:
            return None
        return self.hass.states.get(entity_id)

    def _number_state(self, config_key: str) -> float | None:
        """Read a non-negative numeric sensor value."""
        state = self._state(config_key)
        if not state or state.state.lower() in UNKNOWN_STATES:
            return None
        value = _as_number(state.state)
        if value is None or value < 0:
            return None
        return value

    def _eta_minutes(self) -> float | None:
        """Convert a timestamp sensor to minutes, or accept numeric minutes."""
        state = self._state(CONF_ETA_ENTITY)
        if not state or state.state.lower() in UNKNOWN_STATES:
            return None
        parsed = dt_util.parse_datetime(state.state)
        if parsed is not None:
            now = dt_util.utcnow()
            minutes = (dt_util.as_utc(parsed) - now).total_seconds() / 60
            return round(max(0, minutes), 1)
        value = _as_number(state.state)
        return max(0, value) if value is not None else None

    def _charging_state(self) -> bool | None:
        """Read an optional binary charging entity."""
        state = self._state(CONF_CHARGING_ENTITY)
        if not state or state.state.lower() in UNKNOWN_STATES:
            return None
        return state.state.lower() in {STATE_ON, "charging", "true", "1"}

    async def _async_destination_changed(self, _event: Event) -> None:
        """React immediately when destination state or attributes change."""
        await self.async_sync(destination_event=True)

    async def _async_interval(self, _now: datetime) -> None:
        """Update an active trip."""
        await self.async_sync()

    def _mark_error(self, err: Exception) -> None:
        """Record an API failure without losing persisted trip data."""
        self.available = False
        self.last_error = str(err)
        _LOGGER.warning("Route Progress request failed: %s", err)
        self._notify_listeners()

    def _mark_success(self) -> None:
        """Clear a prior API error."""
        if not self.available:
            _LOGGER.info("Route Progress connection recovered")
        self.available = True
        self.last_error = None
        self.last_successful_connection = dt_util.utcnow()

    @callback
    def _notify_listeners(self) -> None:
        """Notify all entities using only in-memory data."""
        for listener in list(self._listeners):
            listener()


def _attribute_number(state: State | None, attribute: str) -> float | None:
    """Read a numeric state attribute."""
    if state is None:
        return None
    return _as_number(state.attributes.get(attribute))


def _as_number(value: Any) -> float | None:
    """Convert a value to a finite float."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def _optional_string(value: Any) -> str | None:
    """Normalize a stored optional string."""
    return str(value) if value not in (None, "") else None
