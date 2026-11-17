"""Paprika Recipes: show your Paprika 3 recipes natively in Home Assistant."""

from __future__ import annotations

import json
from functools import partial
from pathlib import Path
import shutil

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import PaprikaApi
from .cache import RecipeCache
from .const import (
    CACHE_DIR,
    DEFAULT_BASE_URL,
    DOMAIN,
    PANEL_ELEMENT,
    PANEL_URL_PATH,
    STATIC_URL,
)
from .coordinator import PaprikaCoordinator
from .views import PaprikaPhotoView
from .websocket_api import async_register_websocket_commands

PLATFORMS = [Platform.SENSOR, Platform.BUTTON]

type PaprikaConfigEntry = ConfigEntry[PaprikaCoordinator]

FRONTEND_DIR = Path(__file__).parent / "frontend"


def _version() -> str:
    try:
        return json.loads((Path(__file__).parent / "manifest.json").read_text("utf-8"))[
            "version"
        ]
    except (OSError, ValueError, KeyError):
        return "0"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the static files, photo view and websocket API once."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False)]
    )
    hass.http.register_view(PaprikaPhotoView)
    async_register_websocket_commands(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PaprikaConfigEntry) -> bool:
    """Set up Paprika Recipes from a config entry."""
    api = PaprikaApi(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        DEFAULT_BASE_URL,
    )
    cache = await hass.async_add_executor_job(RecipeCache, hass.config.path(CACHE_DIR))
    coordinator = PaprikaCoordinator(hass, entry, api, cache)
    await coordinator.async_load_cache()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_ELEMENT,
        sidebar_title="Recipes",
        sidebar_icon="mdi:chef-hat",
        module_url=f"{STATIC_URL}/panel.js?v={_version()}",
        embed_iframe=False,
        require_admin=False,
    )

    # First sync runs in the background so a slow or unreachable Paprika never
    # blocks Home Assistant startup; cached recipes are already available.
    entry.async_create_background_task(
        hass, coordinator.async_refresh(), f"{DOMAIN}_first_sync"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PaprikaConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: PaprikaConfigEntry) -> None:
    """Delete the local recipe cache when the integration is removed."""
    await hass.async_add_executor_job(
        partial(shutil.rmtree, hass.config.path(CACHE_DIR), ignore_errors=True)
    )
