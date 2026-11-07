"""Selects: operating mode, silent level, forced DHW/TBH/IBH."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.const import Platform
from .const import KIND_APPLIANCE
from .appliance.entities import async_setup_platform as async_setup_appliance
from .ac import select as ac_select
from .const import (
    CONF_KIND,
    KIND_AC,
    FUNCTION_SILENT_LEVEL2,
    REG_FORCED_DHW,
    REG_FORCED_IBH,
    REG_FORCED_TBH,
    REG_FUNCTION,
    REG_MODE,
)
from .entity import HeatPumpEntity

FORCED = {"none": 0, "force_on": 1, "force_off": 2}

# (register, mask, key, name, options name->value, icon, enabled by default)
SELECTS = (
    (REG_MODE, 0xFFFF, "mode", "Režim", {"auto": 1, "cool": 2, "heat": 3},
     "mdi:sun-snowflake-variant", True),
    (REG_FUNCTION, 1 << FUNCTION_SILENT_LEVEL2, "silent_level", "Úroveň tichého režimu",
     {"level_1": 0, "level_2": 1 << FUNCTION_SILENT_LEVEL2}, "mdi:volume-low", True),
    (REG_FORCED_DHW, 0xFFFF, "forced_dhw", "Vynútený ohrev TÚV", FORCED, "mdi:water-boiler-alert", True),
    (REG_FORCED_TBH, 0xFFFF, "forced_tbh", "Vynútený ohrievač bojlera (TBH)", FORCED, "mdi:heating-coil", False),
    (REG_FORCED_IBH, 0xFFFF, "forced_ibh", "Vynútený záložný ohrievač (IBH)", FORCED, "mdi:heating-coil", False),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up selects."""
    if entry.data.get(CONF_KIND) == KIND_APPLIANCE:
        await async_setup_appliance(entry, async_add_entities, Platform.SELECT)
        return
    if entry.data.get(CONF_KIND) == KIND_AC:
        await ac_select.async_setup_entry(hass, entry, async_add_entities)
        return
    async_add_entities(RegisterSelect(entry, *spec) for spec in SELECTS)


class RegisterSelect(HeatPumpEntity, SelectEntity):
    """Maps option names to register values (bits under ``mask`` only)."""

    def __init__(
        self, entry: ConfigEntry, address: int, mask: int, key: str, name: str,
        options: dict[str, int], icon: str, enabled: bool,
    ) -> None:
        """Initialize."""
        super().__init__(entry, key, name, enabled=enabled)
        self._address, self._mask, self._map = address, mask, options
        self._attr_options = list(options)
        self._attr_icon = icon

    @property
    def current_option(self) -> str | None:
        """Option matching the register."""
        value = self.reg(self._address)
        if value is None:
            return None
        value &= self._mask
        return next((name for name, v in self._map.items() if v == value), None)

    async def async_select_option(self, option: str) -> None:
        """Write the option's value."""
        await self.coordinator.async_write_bits(self._address, self._mask, self._map[option])
