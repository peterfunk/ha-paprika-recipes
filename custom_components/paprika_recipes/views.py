"""HTTP view serving cached recipe photos (signed URLs only)."""

from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .cache import MEDIA_TYPES
from .const import DOMAIN, PHOTO_URL


class PaprikaPhotoView(HomeAssistantView):
    """Serve a cached photo. Requires auth (or a valid signed path)."""

    url = PHOTO_URL + "/{uid}"
    name = "api:paprika_recipes:photo"
    requires_auth = True

    async def get(self, request: web.Request, uid: str) -> web.StreamResponse:
        hass = request.app["hass"]
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise web.HTTPNotFound
        path = await entries[0].runtime_data.async_photo_path(uid)
        if path is None:
            raise web.HTTPNotFound
        ext = path.suffix.lstrip(".").lower()
        return web.FileResponse(
            path,
            headers={
                "Content-Type": MEDIA_TYPES.get(ext, "application/octet-stream"),
                "Cache-Control": "private, max-age=3600",
                "X-Content-Type-Options": "nosniff",
            },
        )
