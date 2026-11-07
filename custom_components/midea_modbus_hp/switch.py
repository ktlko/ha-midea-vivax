"""Switches: zone/DHW power (reg 0) and functions (reg 5), read-modify-write."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ac import switch as ac_switch
from .const import (
    CONF_KIND,
    KIND_AC,
    FUNCTION_CURVE_Z1,
    FUNCTION_CURVE_Z2,
    FUNCTION_DISINFECT,
    FUNCTION_ECO,
    FUNCTION_SILENT,
    REG_FUNCTION,
    REG_POWER,
)
from .entity import HeatPumpEntity

# (register, bit, key, name, icon, enabled by default)
SWITCHES = (
    (REG_POWER, 1, "zone1_power", "Zóna 1 – kúrenie/chladenie", "mdi:radiator", True),
    (REG_POWER, 3, "zone2_power", "Zóna 2 – kúrenie/chladenie", "mdi:radiator", False),
    (REG_POWER, 2, "dhw_power", "Ohrev teplej vody", "mdi:water-boiler", True),
    (REG_POWER, 0, "room_power", "Zóny podľa izbovej teploty", "mdi:home-thermometer", False),
    (REG_FUNCTION, FUNCTION_ECO, "eco", "ECO režim", "mdi:leaf", True),
    (REG_FUNCTION, FUNCTION_SILENT, "silent", "Tichý režim", "mdi:volume-off", True),
    (REG_FUNCTION, FUNCTION_DISINFECT, "disinfect", "Dezinfekcia (antilegionela)", "mdi:bacteria", True),
    (REG_FUNCTION, FUNCTION_CURVE_Z1, "curve_z1", "Ekvitermická krivka zóna 1", "mdi:chart-bell-curve", True),
    (REG_FUNCTION, FUNCTION_CURVE_Z2, "curve_z2", "Ekvitermická krivka zóna 2", "mdi:chart-bell-curve", False),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switches."""
    if entry.data.get(CONF_KIND) == KIND_AC:
        await ac_switch.async_setup_entry(hass, entry, async_add_entities)
        return
    async_add_entities(BitSwitch(entry, *spec) for spec in SWITCHES)


class BitSwitch(HeatPumpEntity, SwitchEntity):
    """One writable bit; other bits of the register are preserved."""

    def __init__(
        self, entry: ConfigEntry, address: int, bit: int, key: str, name: str,
        icon: str, enabled: bool,
    ) -> None:
        """Initialize."""
        super().__init__(entry, key, name, enabled=enabled)
        self._address, self._mask = address, 1 << bit
        self._attr_icon = icon

    @property
    def is_on(self) -> bool | None:
        """Bit state."""
        value = self.reg(self._address)
        return None if value is None else bool(value & self._mask)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the bit."""
        await self.coordinator.async_write_bits(self._address, self._mask, self._mask)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Clear the bit."""
        await self.coordinator.async_write_bits(self._address, self._mask, 0)
