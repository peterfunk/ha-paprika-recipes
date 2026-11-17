"""Sync-now button."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PaprikaConfigEntry
from .sensor import device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PaprikaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([PaprikaSyncButton(entry)])


class PaprikaSyncButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "sync_now"
    _attr_icon = "mdi:sync"

    def __init__(self, entry: PaprikaConfigEntry) -> None:
        self._coordinator = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_sync_now"
        self._attr_device_info = device_info(entry)

    async def async_press(self) -> None:
        await self._coordinator.async_request_refresh()
