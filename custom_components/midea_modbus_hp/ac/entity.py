"""Base entities for air conditioners and their shared outdoor unit (multi-split)."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import CONF_KIND, CONF_OUTDOOR_UNIT, DOMAIN, KIND_AC
from .coordinator import AcCoordinator

MANUFACTURER = "Midea (Vivax)"


def outdoor_unit(entry: ConfigEntry) -> str:
    """Name of the outdoor unit shared with other indoor units ('' = own unit)."""
    return (entry.options.get(CONF_OUTDOOR_UNIT) or entry.data.get(CONF_OUTDOOR_UNIT) or "").strip()


def group_entries(hass: HomeAssistant, unit: str) -> list[ConfigEntry]:
    """AC entries sharing one outdoor unit, ordered by device id."""
    entries = [
        e for e in hass.config_entries.async_entries(DOMAIN)
        if e.data.get(CONF_KIND) == KIND_AC and outdoor_unit(e) == unit
    ]
    return sorted(entries, key=lambda e: e.data["device_id"])


def group_coordinators(hass: HomeAssistant, unit: str) -> list[AcCoordinator]:
    """Loaded coordinators of the indoor units on one outdoor unit."""
    return [
        coordinator for e in group_entries(hass, unit)
        if isinstance(coordinator := getattr(e, "runtime_data", None), AcCoordinator)
    ]


def is_group_primary(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """The member with the lowest device id owns the outdoor-unit entities."""
    unit = outdoor_unit(entry)
    return bool(unit) and group_entries(hass, unit)[0].entry_id == entry.entry_id


def outdoor_device(unit: str) -> DeviceInfo:
    """Device of a shared outdoor unit."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"outdoor_{unit}")},
        translation_key="outdoor_unit",
        translation_placeholders={"unit": unit},
        manufacturer=MANUFACTURER,
        model="Multi-split",
    )


class AcEntity(CoordinatorEntity[AcCoordinator]):
    """Entity of one indoor unit."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, key: str, name: str | None, *, enabled: bool = True) -> None:
        """Initialize."""
        super().__init__(entry.runtime_data)
        device_id = entry.data["device_id"]
        self._attr_unique_id = f"ac_{device_id}_{key}"
        if name is None:
            self._attr_name = None  # main feature of the device
        self._attr_translation_key = f"ac_{key}"
        self._attr_entity_registry_enabled_default = enabled
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"ac_{device_id}")},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=entry.data.get("model") or "Air conditioner",
        )

    def field(self, key: str) -> Any:
        """Last polled value."""
        return (self.coordinator.data or {}).get(key)


class OutdoorEntity(AcEntity):
    """Entity of a shared outdoor unit, fed by the group's primary indoor unit."""

    def __init__(self, entry: ConfigEntry, key: str, name: str, *, enabled: bool = True) -> None:
        """Initialize."""
        super().__init__(entry, key, name, enabled=enabled)
        self.unit = outdoor_unit(entry)
        self._attr_unique_id = f"outdoor_{self.unit}_{key}"
        self._attr_device_info = outdoor_device(self.unit)
