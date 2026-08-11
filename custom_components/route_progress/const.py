"""Constants for the Route Progress integration."""

from __future__ import annotations

DOMAIN = "route_progress"
PLATFORMS = ["binary_sensor", "button", "sensor"]

CONF_API_TOKEN = "api_token"
CONF_BASE_URL = "base_url"
CONF_CLOUDFLARE_ACCESS_ENABLED = "cloudflare_access_enabled"
CONF_CLOUDFLARE_CLIENT_ID = "cloudflare_client_id"
CONF_CLOUDFLARE_CLIENT_SECRET = "cloudflare_client_secret"
CONF_UPDATE_INTERVAL = "update_interval"

CONF_DESTINATION_ENTITY = "destination_entity"
CONF_DESTINATION_POSITION_ENTITY = "destination_position_entity"
CONF_VEHICLE_POSITION_ENTITY = "vehicle_position_entity"
CONF_HEADING_ENTITY = "heading_entity"
CONF_SPEED_ENTITY = "speed_entity"
CONF_ETA_ENTITY = "eta_entity"
CONF_DISTANCE_ENTITY = "distance_entity"
CONF_TRAFFIC_DELAY_ENTITY = "traffic_delay_entity"
CONF_CHARGING_MINUTES_ENTITY = "charging_minutes_entity"
CONF_CHARGING_ENTITY = "charging_entity"
CONF_BATTERY_AT_ARRIVAL_ENTITY = "battery_at_arrival_entity"

REQUIRED_ENTITY_KEYS = (
    CONF_DESTINATION_ENTITY,
    CONF_DESTINATION_POSITION_ENTITY,
    CONF_VEHICLE_POSITION_ENTITY,
)

OPTIONAL_ENTITY_KEYS = (
    CONF_HEADING_ENTITY,
    CONF_SPEED_ENTITY,
    CONF_ETA_ENTITY,
    CONF_DISTANCE_ENTITY,
    CONF_TRAFFIC_DELAY_ENTITY,
    CONF_CHARGING_MINUTES_ENTITY,
    CONF_CHARGING_ENTITY,
    CONF_BATTERY_AT_ARRIVAL_ENTITY,
)

DEFAULT_UPDATE_INTERVAL = 30
MIN_UPDATE_INTERVAL = 10
MAX_UPDATE_INTERVAL = 300
STORAGE_VERSION = 1

UNKNOWN_STATES = {"", "none", "unknown", "unavailable"}
