"""Sync coordinator: mirror Paprika recipes and photos into a local cache.

* Only recipes whose hash changed are downloaded.
* Cached data keeps being served when Paprika is down or rejects the login.
* Recipes in Paprika's trash are hidden (their hash is remembered).
* A failed photo download leaves the recipe marked for retry on the next sync.
* An empty recipe list from Paprika never wipes a non-empty cache.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import models
from .api import PaprikaApi, PaprikaApiError, PaprikaAuthError
from .cache import RecipeCache, valid_uid
from .const import CONF_SYNC_INTERVAL, DEFAULT_SYNC_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import PaprikaConfigEntry

_LOGGER = logging.getLogger(__name__)

REQUEST_DELAY = 0.05  # be gentle with Paprika's servers


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class PaprikaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch recipes from Paprika into the local cache."""

    config_entry: PaprikaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PaprikaConfigEntry,
        api: PaprikaApi,
        cache: RecipeCache,
    ) -> None:
        minutes = entry.options.get(CONF_SYNC_INTERVAL, DEFAULT_SYNC_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=minutes),
        )
        self.api = api
        self.cache = cache
        self.state: dict[str, Any] = {}
        self.index: list[dict[str, Any]] = []
        self.unmapped_category_refs = 0

    # -- cache ---------------------------------------------------------------
    async def async_load_cache(self) -> None:
        """Load whatever is on disk so recipes show before the first sync."""
        self.state = await self.hass.async_add_executor_job(self.cache.load_state)
        if not self.state.get("full_body_fix"):
            # v0.1.0 could cache truncated photos/recipes; force a full re-download once.
            for entry in self.state["recipes"].values():
                if not entry.get("trashed"):
                    entry["hash"] = None
                    entry["photo_hash"] = None
            self.state["full_body_fix"] = True
        await self._async_rebuild_index()
        self.data = self.status()

    def _rebuild_index_blocking(self) -> tuple[list[dict[str, Any]], int]:
        items: list[dict[str, Any]] = []
        unmapped = 0
        cats = self.state["categories"]
        for uid, entry in self.state["recipes"].items():
            if entry.get("trashed"):
                continue
            raw = self.cache.read_recipe(uid)
            if raw is None:
                continue
            unmapped += sum(1 for c in (raw.get("categories") or []) if c not in cats)
            items.append(models.summary(raw, cats, bool(entry.get("photo_file"))))
        items.sort(key=lambda s: s["name"].casefold())
        return items, unmapped

    async def _async_rebuild_index(self) -> None:
        self.index, self.unmapped_category_refs = await self.hass.async_add_executor_job(
            self._rebuild_index_blocking
        )

    # -- reads used by the websocket/HTTP layers -----------------------------
    async def async_get_recipe(self, uid: str) -> dict[str, Any] | None:
        entry = self.state.get("recipes", {}).get(uid) if valid_uid(uid) else None
        if not entry or entry.get("trashed"):
            return None
        raw = await self.hass.async_add_executor_job(self.cache.read_recipe, uid)
        if raw is None:
            return None
        return models.public_recipe(
            raw, self.state["categories"], bool(entry.get("photo_file"))
        )

    async def async_photo_path(self, uid: str):
        entry = self.state.get("recipes", {}).get(uid) if valid_uid(uid) else None
        if not entry or entry.get("trashed"):
            return None
        return await self.hass.async_add_executor_job(
            self.cache.photo_path, entry.get("photo_file")
        )

    def status(self) -> dict[str, Any]:
        sync = self.state.get("sync", {})
        recipes = [
            e for e in self.state.get("recipes", {}).values() if not e.get("trashed")
        ]
        return {
            "recipes": len(self.index),
            "photos": sum(1 for e in recipes if e.get("photo_file")),
            "pending_retry": sum(1 for e in recipes if not e.get("hash")),
            "categories": len(self.state.get("categories", {})),
            "unmapped_category_refs": self.unmapped_category_refs,
            "last_attempt": sync.get("last_attempt"),
            "last_success": sync.get("last_success"),
            "last_error": sync.get("last_error"),
            "last_result": sync.get("last_result"),
        }

    # -- sync ----------------------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        sync = self.state["sync"]
        sync["last_attempt"] = _now()
        result = {"fetched": 0, "unchanged": 0, "removed": 0, "photos": 0, "errors": 0}
        try:
            await self._async_sync(result)
        except PaprikaAuthError as err:
            sync["last_error"] = "Paprika rejected the login. Cached recipes still served."
            await self._async_finish(result)
            raise ConfigEntryAuthFailed("Paprika rejected the login") from err
        except PaprikaApiError as err:
            sync["last_error"] = f"Could not reach Paprika: {err}. Cached recipes still served."
            await self._async_finish(result)
            raise UpdateFailed(sync["last_error"]) from err
        sync["last_success"] = _now()
        sync["last_error"] = (
            f"{result['errors']} recipe(s) failed and will be retried"
            if result["errors"]
            else None
        )
        await self._async_finish(result)
        return self.status()

    async def _async_finish(self, result: dict[str, int]) -> None:
        self.state["sync"]["last_result"] = result
        await self.hass.async_add_executor_job(self.cache.save_state, self.state)
        await self._async_rebuild_index()

    async def _async_sync(self, result: dict[str, int]) -> None:
        remote: dict[str, str] = {}
        for item in await self.api.list_recipes():
            if isinstance(item, dict):
                uid, digest = item.get("uid"), item.get("hash")
                if valid_uid(uid) and isinstance(digest, str):
                    remote[uid] = digest

        local = self.state["recipes"]
        if not remote and local:
            raise PaprikaApiError("Paprika returned an empty recipe list; keeping cache")

        try:
            cats = await self.api.list_categories()
            self.state["categories"] = {
                c["uid"]: c["name"]
                for c in cats
                if isinstance(c, dict)
                and isinstance(c.get("uid"), str)
                and isinstance(c.get("name"), str)
            }
        except PaprikaAuthError:
            raise
        except PaprikaApiError as err:
            _LOGGER.warning("Could not refresh categories (keeping previous): %s", err)

        for uid in [u for u in local if u not in remote]:
            await self.hass.async_add_executor_job(self._remove_blocking, uid)
            result["removed"] += 1

        for uid, digest in remote.items():
            entry = local.get(uid)
            if (
                entry
                and entry.get("hash") == digest
                and (
                    entry.get("trashed")
                    or await self.hass.async_add_executor_job(self.cache.has_recipe, uid)
                )
            ):
                result["unchanged"] += 1
                continue
            try:
                await self._async_fetch_one(uid, digest, result)
            except PaprikaAuthError:
                raise
            except (PaprikaApiError, ValueError, OSError) as err:
                _LOGGER.warning("Recipe %s failed: %s", uid, err)
                result["errors"] += 1
            await asyncio.sleep(REQUEST_DELAY)

    def _remove_blocking(self, uid: str) -> None:
        self.cache.delete_recipe(uid)
        self.cache.delete_photo(uid)
        self.state["recipes"].pop(uid, None)

    async def _async_fetch_one(self, uid: str, digest: str, result: dict[str, int]) -> None:
        recipe = await self.api.get_recipe(uid)
        recipe["uid"] = uid  # trust the list, not the payload, for the identifier
        if recipe.get("in_trash"):
            await self.hass.async_add_executor_job(self._trash_blocking, uid)
            self.state["recipes"][uid] = {"hash": digest, "trashed": True}
            return
        entry = self.state["recipes"].get(uid) or {}
        entry.pop("trashed", None)
        photo_ok = await self._async_sync_photo(uid, recipe, entry, result)
        await self.hass.async_add_executor_job(self.cache.write_recipe, uid, recipe)
        entry["hash"] = digest if photo_ok else None  # None => retry next sync
        self.state["recipes"][uid] = entry
        result["fetched"] += 1

    def _trash_blocking(self, uid: str) -> None:
        self.cache.delete_recipe(uid)
        self.cache.delete_photo(uid)

    async def _async_sync_photo(
        self, uid: str, recipe: dict[str, Any], entry: dict[str, Any], result: dict[str, int]
    ) -> bool:
        url = recipe.get("photo_url")
        photo_hash = recipe.get("photo_hash")
        if not url:
            await self.hass.async_add_executor_job(self.cache.delete_photo, uid)
            entry["photo_file"] = None
            entry["photo_hash"] = None
            return True
        if (
            photo_hash
            and entry.get("photo_hash") == photo_hash
            and await self.hass.async_add_executor_job(
                self.cache.photo_path, entry.get("photo_file")
            )
        ):
            return True
        try:
            data = await self.api.download_photo(url)
            entry["photo_file"] = await self.hass.async_add_executor_job(
                self.cache.write_photo, uid, data
            )
            entry["photo_hash"] = photo_hash
            result["photos"] += 1
        except (PaprikaApiError, ValueError, OSError) as err:
            _LOGGER.warning("Photo download failed for %s: %s", uid, err)
            return False  # keep any older photo; retry next sync
        return True
