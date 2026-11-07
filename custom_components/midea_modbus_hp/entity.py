"""Base entity and register helpers."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HeatPumpCoordinator


def signed(value: int) -> int:
    """Interpret a uint16 register as int16."""
    return value - 0x10000 if value & 0x8000 else value


class HeatPumpEntity(CoordinatorEntity[HeatPumpCoordinator]):
    """Entity on the single heat pump device."""

    _attr_has_entity_name = True

    def __init__(
        self, entry: ConfigEntry, key: str, name: str, *, enabled: bool = True
    ) -> None:
        """Initialize."""
        super().__init__(entry.runtime_data)
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_entity_registry_enabled_default = enabled
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            name=entry.title,
            manufacturer="Midea (Vivax)",
            model="M-Thermal, Modbus via wired controller",
        )

    def reg(self, address: int) -> int | None:
        """Raw register value from the last poll."""
        return self.coordinator.data.get(address) if self.coordinator.data else None

    def bit(self, address: int, bit: int) -> bool | None:
        """One bit of a register."""
        value = self.reg(address)
        return None if value is None else bool(value >> bit & 1)
