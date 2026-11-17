"""Websocket API used by the Recipes panel."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant, callback
import voluptuous as vol

from .const import DOMAIN, PHOTO_SIGN_EXPIRY_HOURS, PHOTO_URL


def _coordinator(hass: HomeAssistant):
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


def _with_photo(hass: HomeAssistant, item: dict[str, Any]) -> dict[str, Any]:
    out = dict(item)
    if item.get("photo"):
        out["photo"] = async_sign_path(
            hass,
            f"{PHOTO_URL}/{item['uid']}",
            timedelta(hours=PHOTO_SIGN_EXPIRY_HOURS),
        )
    else:
        out["photo"] = None
    return out


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_get)
    websocket_api.async_register_command(hass, ws_sync)


@websocket_api.websocket_command({vol.Required("type"): "paprika_recipes/list"})
@websocket_api.async_response
async def ws_list(hass: HomeAssistant, connection, msg) -> None:
    coordinator = _coordinator(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "Paprika Recipes is not loaded")
        return
    connection.send_result(
        msg["id"],
        {
            "recipes": [_with_photo(hass, i) for i in coordinator.index],
            "status": coordinator.status(),
        },
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "paprika_recipes/get", vol.Required("uid"): str}
)
@websocket_api.async_response
async def ws_get(hass: HomeAssistant, connection, msg) -> None:
    coordinator = _coordinator(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "Paprika Recipes is not loaded")
        return
    recipe = await coordinator.async_get_recipe(msg["uid"])
    if recipe is None:
        connection.send_error(msg["id"], "not_found", "Recipe not found")
        return
    connection.send_result(msg["id"], _with_photo(hass, recipe))


@websocket_api.websocket_command({vol.Required("type"): "paprika_recipes/sync"})
@websocket_api.async_response
async def ws_sync(hass: HomeAssistant, connection, msg) -> None:
    coordinator = _coordinator(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "Paprika Recipes is not loaded")
        return
    await coordinator.async_request_refresh()
    connection.send_result(msg["id"], coordinator.status())
