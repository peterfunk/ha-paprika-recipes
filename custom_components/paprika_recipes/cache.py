"""On-disk cache: recipe JSON, photos and a state file. Blocking; call from an executor."""

from __future__ import annotations
import json
import logging
import os
import re
import tempfile
from pathlib import Path

log = logging.getLogger("paprika_recipes.cache")

UID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$")

MEDIA_TYPES = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
}


def valid_uid(uid) -> bool:
    return isinstance(uid, str) and bool(UID_RE.match(uid))


def sniff_image_ext(data: bytes):
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return None


def _fresh_state():
    return {"version": 1, "recipes": {}, "categories": {}, "sync": {}}


class RecipeCache:
    def __init__(self, data_dir):
        self.root = Path(data_dir)
        self.recipes_dir = self.root / "recipes"
        self.photos_dir = self.root / "photos"
        self.state_path = self.root / "state.json"
        self.recipes_dir.mkdir(parents=True, exist_ok=True)
        self.photos_dir.mkdir(parents=True, exist_ok=True)

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _atomic_write(path: Path, data: bytes):
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # -- state ---------------------------------------------------------------
    def load_state(self):
        try:
            state = json.loads(self.state_path.read_text("utf-8"))
        except FileNotFoundError:
            return _fresh_state()
        except (OSError, ValueError):
            log.warning("state.json unreadable; starting with an empty state")
            return _fresh_state()
        base = _fresh_state()
        if isinstance(state, dict):
            for key in base:
                if isinstance(state.get(key), type(base[key])):
                    base[key] = state[key]
        if isinstance(state, dict) and state.get("full_body_fix"):
            base["full_body_fix"] = True
        return base

    def save_state(self, state):
        self._atomic_write(self.state_path, json.dumps(state, indent=1).encode("utf-8"))

    # -- recipes -------------------------------------------------------------
    def _recipe_path(self, uid):
        if not valid_uid(uid):
            raise ValueError("invalid uid")
        return self.recipes_dir / f"{uid}.json"

    def has_recipe(self, uid) -> bool:
        return self._recipe_path(uid).is_file()

    def read_recipe(self, uid):
        try:
            return json.loads(self._recipe_path(uid).read_text("utf-8"))
        except (FileNotFoundError, ValueError, OSError):
            return None

    def write_recipe(self, uid, recipe):
        self._atomic_write(self._recipe_path(uid), json.dumps(recipe).encode("utf-8"))

    def delete_recipe(self, uid):
        try:
            self._recipe_path(uid).unlink()
        except FileNotFoundError:
            pass

    # -- photos --------------------------------------------------------------
    def write_photo(self, uid, data: bytes) -> str:
        if not valid_uid(uid):
            raise ValueError("invalid uid")
        ext = sniff_image_ext(data)
        if ext is None:
            raise ValueError("downloaded photo is not a recognised image")
        name = f"{uid}.{ext}"
        self._atomic_write(self.photos_dir / name, data)
        for old in self.photos_dir.glob(f"{uid}.*"):  # remove other-extension leftovers
            if old.name != name:
                old.unlink(missing_ok=True)
        return name

    def delete_photo(self, uid):
        if valid_uid(uid):
            for old in self.photos_dir.glob(f"{uid}.*"):
                old.unlink(missing_ok=True)

    def photo_path(self, name):
        """Resolve a stored photo filename; None if it isn't a plain file name."""
        if not name or Path(name).name != name:
            return None
        path = self.photos_dir / name
        return path if path.is_file() else None

    # -- housekeeping --------------------------------------------------------
    def list_recipe_uids(self):
        return [p.stem for p in self.recipes_dir.glob("*.json") if valid_uid(p.stem)]

    def remove_all(self):
        import shutil

        shutil.rmtree(self.root, ignore_errors=True)
