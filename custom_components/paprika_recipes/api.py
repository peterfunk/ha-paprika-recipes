"""Minimal READ-ONLY async client for Paprika's unofficial cloud sync API.

Only GET requests are made. Authenticated requests never follow redirects, so
the credentials cannot be forwarded to another host; photo downloads carry no
credentials at all.
"""

from __future__ import annotations

import json
import urllib.parse
import zlib
from typing import Any

import aiohttp

from .const import MAX_JSON_BYTES, MAX_PHOTO_BYTES, USER_AGENT


class PaprikaApiError(Exception):
    """Any failure talking to Paprika."""


class PaprikaAuthError(PaprikaApiError):
    """Paprika rejected the credentials."""


class PaprikaApi:
    """Read-only Paprika client."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
        base_url: str,
    ) -> None:
        self._session = session
        self._auth = aiohttp.BasicAuth(email, password, encoding="utf-8")
        self._base = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=30)

    def __repr__(self) -> str:
        return "PaprikaApi(<credentials redacted>)"

    async def _fetch(
        self, url: str, *, authenticated: bool, max_bytes: int
    ) -> bytes:
        headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
        try:
            async with self._session.get(
                url,
                headers=headers,
                auth=self._auth if authenticated else None,
                allow_redirects=not authenticated,
                timeout=self._timeout,
            ) as resp:
                if resp.status in (401, 403):
                    raise PaprikaAuthError(f"HTTP {resp.status}")
                if resp.status != 200:
                    host = urllib.parse.urlsplit(url).netloc
                    raise PaprikaApiError(f"HTTP {resp.status} from {host}")
                # StreamReader.read(n) returns only what has arrived so far, so
                # read the whole body in chunks, enforcing the size cap.
                buf = bytearray()
                async for chunk in resp.content.iter_chunked(65536):
                    buf += chunk
                    if len(buf) > max_bytes:
                        raise PaprikaApiError("response too large")
                data = bytes(buf)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise PaprikaApiError(f"network error: {err}") from None
        if len(data) > max_bytes:
            raise PaprikaApiError("response too large")
        if data[:2] == b"\x1f\x8b":
            try:
                out = zlib.decompressobj(wbits=31).decompress(data, max_bytes + 1)
            except zlib.error:
                raise PaprikaApiError("corrupt gzip response") from None
            if len(out) > max_bytes:
                raise PaprikaApiError("response too large")
            data = out
        return data

    async def _get_json(self, path: str) -> Any:
        data = await self._fetch(
            f"{self._base}{path}", authenticated=True, max_bytes=MAX_JSON_BYTES
        )
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise PaprikaApiError("invalid JSON from Paprika") from None
        if isinstance(payload, dict) and "result" in payload:
            payload = payload["result"]
        return payload

    async def list_recipes(self) -> list[dict[str, Any]]:
        """Return [{'uid':..., 'hash':...}, ...]."""
        payload = await self._get_json("/recipes/")
        if not isinstance(payload, list):
            raise PaprikaApiError("unexpected recipe list payload")
        return payload

    async def get_recipe(self, uid: str) -> dict[str, Any]:
        payload = await self._get_json(f"/recipe/{urllib.parse.quote(uid, safe='')}/")
        if not isinstance(payload, dict):
            raise PaprikaApiError("unexpected recipe payload")
        return payload

    async def list_categories(self) -> list[dict[str, Any]]:
        payload = await self._get_json("/categories/")
        if not isinstance(payload, list):
            raise PaprikaApiError("unexpected category payload")
        return payload

    async def download_photo(self, url: str) -> bytes:
        """Download a photo. No credentials are sent."""
        if urllib.parse.urlsplit(url).scheme.lower() not in ("http", "https"):
            raise PaprikaApiError("refusing non-http(s) photo URL")
        return await self._fetch(url, authenticated=False, max_bytes=MAX_PHOTO_BYTES)
