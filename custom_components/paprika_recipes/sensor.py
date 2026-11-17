"""Sensors for Paprika Recipes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import PaprikaConfigEntry
from .const import DOMAIN
from .coordinator import PaprikaCoordinator


def device_info(entry: PaprikaConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Paprika Recipes",
        entry_type=DeviceEntryType.SERVICE,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PaprikaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        [PaprikaRecipeCountSensor(entry.runtime_data, entry), PaprikaLastSyncSensor(entry.runtime_data, entry)]
    )


class _Base(CoordinatorEntity[PaprikaCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: PaprikaCoordinator, entry: PaprikaConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = device_info(entry)


class PaprikaRecipeCountSensor(_Base):
    _attr_translation_key = "recipes"
    _attr_icon = "mdi:book-open-page-variant"
    _attr_native_unit_of_measurement = "recipes"

    def __init__(self, coordinator: PaprikaCoordinator, entry: PaprikaConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_recipes"

    @property
    def native_value(self) -> int:
        return self.coordinator.status()["recipes"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self.coordinator.status()
        return {k: s[k] for k in ("photos", "categories", "pending_retry", "last_error")}


class PaprikaLastSyncSensor(_Base):
    _attr_translation_key = "last_sync"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: PaprikaCoordinator, entry: PaprikaConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_sync"

    @property
    def native_value(self) -> datetime | None:
        value = self.coordinator.status()["last_success"]
        return dt_util.parse_datetime(value) if value else None
