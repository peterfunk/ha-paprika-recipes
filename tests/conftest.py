"""Shared fixtures: a fake Paprika API and a config entry."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.paprika_recipes.api import PaprikaApiError, PaprikaAuthError
from custom_components.paprika_recipes.const import DOMAIN

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 32


def make_recipe(uid: str, name: str, digest: str, photo: str | None = None, **kw) -> dict:
    recipe = {
        "uid": uid, "name": name, "hash": digest,
        "ingredients": "2 cups flour\n1 tsp salt", "directions": "Mix.\nBake.",
        "photo_url": f"https://photos.example/{photo}" if photo else None,
        "photo_hash": f"ph-{photo}" if photo else None,
        "categories": ["CAT-1"], "servings": "4", "rating": 4,
        "in_trash": False, "on_favorites": True,
        "source_url": "javascript:alert(1)", "notes": "<script>x</script>",
    }
    recipe.update(kw)
    return recipe


class FakePaprika:
    """Stand-in for PaprikaApi that records calls and can be told to fail."""

    def __init__(self) -> None:
        self.recipes: dict[str, dict] = {
            "R1-AAA": make_recipe("R1-AAA", "Zucchini Bread", "h1", "r1"),
            "R2-BBB": make_recipe("R2-BBB", "apple pie", "h2"),
            "R3-CCC": make_recipe("R3-CCC", "Deleted Thing", "h3", in_trash=True),
        }
        self.categories = [{"uid": "CAT-1", "name": "Dinner"}]
        self.auth_fail = False
        self.down = False
        self.photo_fail: set[str] = set()
        self.fetched: list[str] = []
        self.photo_downloads: list[str] = []

    def _check(self) -> None:
        if self.auth_fail:
            raise PaprikaAuthError("HTTP 401")
        if self.down:
            raise PaprikaApiError("network error")

    async def list_recipes(self):
        self._check()
        return [{"uid": u, "hash": r["hash"]} for u, r in self.recipes.items()]

    async def get_recipe(self, uid):
        self._check()
        self.fetched.append(uid)
        return dict(self.recipes[uid])

    async def list_categories(self):
        self._check()
        return self.categories

    async def download_photo(self, url):
        self.photo_downloads.append(url)
        if any(p in url for p in self.photo_fail):
            raise PaprikaApiError("photo failed")
        return JPEG


@pytest.fixture(autouse=True)
def _auto_enable(enable_custom_integrations):
    return


@pytest.fixture(autouse=True)
def _clean_cache(hass):
    """The test config dir is shared between tests; start each with an empty cache."""
    import shutil

    shutil.rmtree(hass.config.path("paprika_recipes"), ignore_errors=True)
    yield
    shutil.rmtree(hass.config.path("paprika_recipes"), ignore_errors=True)


@pytest.fixture
def fake() -> FakePaprika:
    return FakePaprika()


@pytest.fixture
def patch_api(fake):
    with patch("custom_components.paprika_recipes.PaprikaApi", return_value=fake), patch(
        "custom_components.paprika_recipes.config_flow.PaprikaApi", return_value=fake
    ):
        yield fake


@pytest.fixture
def entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN, unique_id="me@example.com", title="me@example.com",
        data={"email": "me@example.com", "password": "hunter2"},
    )


async def setup_entry(hass, entry) -> Any:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry.runtime_data
