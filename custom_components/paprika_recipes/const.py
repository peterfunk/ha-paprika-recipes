"""Constants for the Paprika Recipes integration."""

from __future__ import annotations

DOMAIN = "paprika_recipes"

DEFAULT_BASE_URL = "https://www.paprikaapp.com/api/v1/sync"
USER_AGENT = "ha-paprika-recipes (read-only; https://github.com/peterfunk/ha-paprika-recipes)"

CONF_SYNC_INTERVAL = "sync_interval"
DEFAULT_SYNC_INTERVAL = 30  # minutes
MIN_SYNC_INTERVAL = 5
MAX_SYNC_INTERVAL = 1440

CACHE_DIR = "paprika_recipes"
PANEL_URL_PATH = "paprika-recipes"
PANEL_ELEMENT = "paprika-recipes-panel"
STATIC_URL = "/paprika_recipes_static"
PHOTO_URL = "/api/paprika_recipes/photo"
PHOTO_SIGN_EXPIRY_HOURS = 24

MAX_JSON_BYTES = 20 * 1024 * 1024
MAX_PHOTO_BYTES = 15 * 1024 * 1024
