"""Integration tests: sync behaviour, websocket API, photos, flows."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.components.diagnostics import REDACTED
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator, WebSocketGenerator

from custom_components.paprika_recipes.const import DOMAIN
from custom_components.paprika_recipes.diagnostics import async_get_config_entry_diagnostics

from .conftest import JPEG, make_recipe, setup_entry


async def test_first_sync_hides_trash_and_maps_categories(hass, patch_api, entry):
    coord = await setup_entry(hass, entry)
    names = [r["name"] for r in coord.index]
    assert names == ["apple pie", "Zucchini Bread"]  # case-insensitive sort, trash hidden
    assert coord.index[1]["categories"] == ["Dinner"]
    assert coord.status()["photos"] == 1
    assert "R3-CCC" in patch_api.fetched  # fetched once to learn it is trashed
    assert entry.state is ConfigEntryState.LOADED


async def test_incremental_sync_only_fetches_changes(hass, patch_api, entry):
    coord = await setup_entry(hass, entry)
    patch_api.fetched.clear()
    patch_api.photo_downloads.clear()
    patch_api.recipes["R2-BBB"] = make_recipe("R2-BBB", "Apple Pie v2", "h2b")
    await coord.async_refresh()
    assert patch_api.fetched == ["R2-BBB"]
    assert patch_api.photo_downloads == []
    assert "Apple Pie v2" in [r["name"] for r in coord.index]


async def test_remote_delete_removes_recipe(hass, patch_api, entry):
    coord = await setup_entry(hass, entry)
    del patch_api.recipes["R1-AAA"]
    await coord.async_refresh()
    assert [r["uid"] for r in coord.index] == ["R2-BBB"]
    assert await coord.async_photo_path("R1-AAA") is None


async def test_empty_remote_list_keeps_cache(hass, patch_api, entry):
    coord = await setup_entry(hass, entry)
    patch_api.recipes.clear()
    await coord.async_refresh()
    assert len(coord.index) == 2
    assert "empty recipe list" in coord.status()["last_error"]


async def test_outage_serves_cache(hass, patch_api, entry):
    coord = await setup_entry(hass, entry)
    patch_api.down = True
    await coord.async_refresh()
    assert len(coord.index) == 2
    assert "Could not reach Paprika" in coord.status()["last_error"]
    assert entry.state is ConfigEntryState.LOADED


async def test_failed_photo_retried_next_sync(hass, patch_api, entry):
    patch_api.photo_fail = {"r1"}
    coord = await setup_entry(hass, entry)
    assert coord.status()["pending_retry"] == 1
    patch_api.photo_fail = set()
    patch_api.fetched.clear()
    await coord.async_refresh()
    assert coord.status()["pending_retry"] == 0
    assert coord.status()["photos"] == 1
    assert patch_api.fetched == ["R1-AAA"]


async def test_auth_failure_starts_reauth_and_keeps_cache(hass, patch_api, entry):
    coord = await setup_entry(hass, entry)
    patch_api.auth_fail = True
    await coord.async_refresh()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f["context"]["source"] for f in flows] == ["reauth"]
    assert len(coord.index) == 2


async def test_reauth_flow_updates_password(hass, patch_api, entry):
    await setup_entry(hass, entry)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    patch_api.auth_fail = True
    bad = await hass.config_entries.flow.async_configure(result["flow_id"], {"password": "x"})
    assert bad["errors"] == {"base": "invalid_auth"}
    patch_api.auth_fail = False
    ok = await hass.config_entries.flow.async_configure(result["flow_id"], {"password": "new"})
    assert ok["type"] is FlowResultType.ABORT and ok["reason"] == "reauth_successful"
    assert entry.data["password"] == "new"
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_config_flow_success_and_errors(hass, patch_api):
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    patch_api.auth_fail = True
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"email": "a@b.c", "password": "p"})
    assert r["errors"] == {"base": "invalid_auth"}
    patch_api.auth_fail, patch_api.down = False, True
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"email": "a@b.c", "password": "p"})
    assert r["errors"] == {"base": "cannot_connect"}
    patch_api.down = False
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"email": "a@b.c", "password": "p"})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["data"] == {"email": "a@b.c", "password": "p"}
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_single_entry_only(hass, patch_api, entry):
    await setup_entry(hass, entry)
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert r["type"] is FlowResultType.ABORT


async def test_options_flow_changes_interval(hass, patch_api, entry):
    await setup_entry(hass, entry)
    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"sync_interval": 60})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.runtime_data.update_interval.total_seconds() == 3600


async def test_websocket_list_get_and_photo(hass, patch_api, entry, hass_ws_client: WebSocketGenerator, hass_client: ClientSessionGenerator):
    await setup_entry(hass, entry)
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "paprika_recipes/list"})
    msg = await ws.receive_json()
    recipes = {r["uid"]: r for r in msg["result"]["recipes"]}
    assert set(recipes) == {"R1-AAA", "R2-BBB"}
    assert recipes["R2-BBB"]["photo"] is None
    assert "authSig=" in recipes["R1-AAA"]["photo"]

    await ws.send_json({"id": 2, "type": "paprika_recipes/get", "uid": "R1-AAA"})
    got = (await ws.receive_json())["result"]
    assert got["source_url"] is None  # javascript: URLs are dropped
    assert got["ingredients"].startswith("2 cups")

    await ws.send_json({"id": 3, "type": "paprika_recipes/get", "uid": "R3-CCC"})
    assert (await ws.receive_json())["error"]["code"] == "not_found"
    await ws.send_json({"id": 4, "type": "paprika_recipes/get", "uid": "../../etc/passwd"})
    assert (await ws.receive_json())["error"]["code"] == "not_found"

    client = await hass_client()
    resp = await client.get(recipes["R1-AAA"]["photo"])
    assert resp.status == 200
    assert resp.headers["Content-Type"] == "image/jpeg"
    assert await resp.read() == JPEG


async def test_photo_requires_auth(hass, patch_api, entry, hass_client_no_auth):
    await setup_entry(hass, entry)
    client = await hass_client_no_auth()
    assert (await client.get("/api/paprika_recipes/photo/R1-AAA")).status == 401


async def test_photo_unknown_uid_404(hass, patch_api, entry, hass_client):
    await setup_entry(hass, entry)
    client = await hass_client()
    assert (await client.get("/api/paprika_recipes/photo/NOPE")).status == 404
    assert (await client.get("/api/paprika_recipes/photo/R3-CCC")).status == 404


async def test_sensors_and_sync_button(hass, patch_api, entry):
    coord = await setup_entry(hass, entry)
    ent = er.async_get(hass)
    count = ent.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_recipes")
    assert hass.states.get(count).state == "2"
    patch_api.recipes["R9-ZZZ"] = make_recipe("R9-ZZZ", "New", "h9")
    button = ent.async_get_entity_id("button", DOMAIN, f"{entry.entry_id}_sync_now")
    await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(coord.index) == 3


async def test_diagnostics_redacts_credentials(hass, patch_api, entry):
    await setup_entry(hass, entry)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"] == {"email": REDACTED, "password": REDACTED}
    assert "hunter2" not in str(diag)


async def test_unload_and_remove_deletes_cache(hass, patch_api, entry):
    await setup_entry(hass, entry)
    cache_root = entry.runtime_data.cache.root
    assert cache_root.exists()
    assert "paprika-recipes" in hass.data["frontend_panels"]
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert "paprika-recipes" not in hass.data["frontend_panels"]
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert not cache_root.exists()


async def test_cache_survives_restart(hass, patch_api, entry):
    await setup_entry(hass, entry)
    assert await hass.config_entries.async_unload(entry.entry_id)
    patch_api.down = True
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(entry.runtime_data.index) == 2
