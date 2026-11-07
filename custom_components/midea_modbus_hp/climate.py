"""Climate card for zone 1: mode, setpoint, water temperature and what the unit is doing.

With the room thermostat in MODE SET (installer setting), the thermostat inputs
H/C decide whether the unit heats or cools; switching the zone here is then
overridden by the unit about 30 s later.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import KIND_APPLIANCE
from .ac import climate as ac_climate
from .const import CONF_KIND, KIND_AC, REG_LOADS, REG_MODE, REG_POWER, REG_ZONE1_SET
from .entity import HeatPumpEntity, signed

ZONE1_BIT = 1 << 1
MODE_TO_HVAC = {1: HVACMode.AUTO, 2: HVACMode.COOL, 3: HVACMode.HEAT}
HVAC_TO_MODE = {v: k for k, v in MODE_TO_HVAC.items()}
REG_COMP_FREQ = 100
REG_UNIT_MODE = 101
REG_T1 = 110
PUMP_I_BIT = 1 << 3


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the zone 1 climate entity."""
    if entry.data.get(CONF_KIND) == KIND_APPLIANCE:
        return  # no such entities
    if entry.data.get(CONF_KIND) == KIND_AC:
        await ac_climate.async_setup_entry(hass, entry, async_add_entities)
        return
    async_add_entities([Zone1Climate(entry)])


class Zone1Climate(HeatPumpEntity, ClimateEntity):
    """Zone 1 water-temperature control."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "zone1_climate", "Zóna 1")

    @property
    def _heating_side(self) -> bool:
        return self.reg(REG_MODE) != 2

    @property
    def min_temp(self) -> float:
        """Lower limit from the installer settings (registers 202/204, zone 1 byte)."""
        raw = self.reg(204 if self._heating_side else 202)
        return float(raw & 0xFF) if raw else 5.0

    @property
    def max_temp(self) -> float:
        """Upper limit from the installer settings (registers 201/203, zone 1 byte)."""
        raw = self.reg(203 if self._heating_side else 201)
        return float(raw & 0xFF) if raw else 65.0

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Off when zone 1 is not powered, otherwise the unit mode."""
        power = self.reg(REG_POWER)
        if power is None:
            return None
        if not power & ZONE1_BIT:
            return HVACMode.OFF
        return MODE_TO_HVAC.get(self.reg(REG_MODE) or 0)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Heating/cooling while the compressor runs in that mode, else idle."""
        if self.hvac_mode in (None, HVACMode.OFF):
            return HVACAction.OFF
        if (self.reg(REG_COMP_FREQ) or 0) > 0:
            unit_mode = self.reg(REG_UNIT_MODE)
            if unit_mode == 3:
                return HVACAction.HEATING
            if unit_mode == 2:
                return HVACAction.COOLING
        if (self.reg(REG_LOADS) or 0) & PUMP_I_BIT:
            return HVACAction.FAN  # circulation pump only, compressor not running
        return HVACAction.IDLE

    @property
    def native_current_temperature(self) -> float | None:
        """Total outlet water temperature T1."""
        raw = self.reg(REG_T1)
        return None if raw is None else float(signed(raw))

    @property
    def native_target_temperature(self) -> float | None:
        """Zone 1 water setpoint."""
        raw = self.reg(REG_ZONE1_SET)
        return None if raw is None else float(raw)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Write the zone 1 water setpoint."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.async_write(REG_ZONE1_SET, round(temp))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Switch zone 1 off, or set the unit mode and switch zone 1 on."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_write_bits(REG_POWER, ZONE1_BIT, 0)
            return
        await self.coordinator.async_write(REG_MODE, HVAC_TO_MODE[hvac_mode])
        await self.coordinator.async_write_bits(REG_POWER, ZONE1_BIT, ZONE1_BIT)

    async def async_turn_on(self) -> None:
        """Switch zone 1 on in the current mode."""
        await self.coordinator.async_write_bits(REG_POWER, ZONE1_BIT, ZONE1_BIT)

    async def async_turn_off(self) -> None:
        """Switch zone 1 off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
