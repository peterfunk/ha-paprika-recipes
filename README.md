# Paprika Recipes for Home Assistant

Browse your [Paprika Recipe Manager 3](https://www.paprikaapp.com/) recipes in a native Home Assistant panel — built for a kitchen wall display. Keep using the Paprika app on your phone; this integration only **reads** from your account.

> **Unofficial.** Not affiliated with or endorsed by Paprika's maker (Hindsight Labs). It uses Paprika's undocumented cloud-sync API, which could change or break without notice.

## Features
- Sidebar **Recipes** panel: photo grid / compact list, search, category filters with counts, favourites, ratings
- Recipe view with **ingredient scaling** (fractions, ranges, "2 (14 oz) cans" package sizes left alone)
- Incremental hash-based sync; works from the local cache when Paprika is unreachable
- Sensors (recipe count, last sync) and a **Sync now** button
- Read-only: only `GET` requests are ever sent; trashed recipes are hidden
- Recipe text is rendered as plain text (never as HTML)

## Install
**HACS (custom repository):** HACS → ⋮ → *Custom repositories* → add this repo as category *Integration* → install **Paprika Recipes** → restart Home Assistant.
**Manual:** copy `custom_components/paprika_recipes` into your config's `custom_components/` folder and restart.

Then *Settings → Devices & services → Add integration → Paprika Recipes* and enter your Paprika email and password.

## Options
*Sync interval* (5–1440 minutes, default 30). If Paprika rejects your password Home Assistant starts a re-authentication flow; cached recipes keep showing meanwhile.

## Privacy & security
- Your Paprika password is stored in Home Assistant's config-entry storage (`.storage/`), **not encrypted** — the same as other integrations that use passwords. Protect your backups.
- Credentials are sent only to Paprika's API host; authenticated requests never follow redirects. Photos are downloaded without credentials.
- Recipes and photos are cached in `<config>/paprika_recipes/` and deleted when you remove the integration.
- Photos are served through Home Assistant's signed-URL mechanism; recipe data goes over the authenticated websocket, so only logged-in users can see it.

## Kitchen-display tip
Open `/paprika-recipes` directly in your kiosk browser, or add the panel to a dashboard as a *Panel (single card)* view.

## Development
```
uv venv --python 3.14 && uv pip install -r requirements_test.txt
uv run python -m pytest -q          # integration tests (no network needed)
node --test tests/scale.test.mjs    # ingredient scaler
```
Tests use only sample data; please keep real recipes out of issues and PRs.

## Credits
Inspired by [rbrunt/paprika-ha](https://github.com/rbrunt/paprika-ha). MIT licensed.
