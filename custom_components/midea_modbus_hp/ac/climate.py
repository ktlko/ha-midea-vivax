"""Climate entity of an air conditioner."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SLEEP,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import protocol as p
from .coordinator import CAP_ECO, CAP_TURBO, AcCoordinator
from .entity import AcEntity, group_coordinators, outdoor_unit

_LOGGER = logging.getLogger(__name__)

HVAC_TO_MODE = {
    HVACMode.AUTO: p.MODE_AUTO,
    HVACMode.COOL: p.MODE_COOL,
    HVACMode.DRY: p.MODE_DRY,
    HVACMode.HEAT: p.MODE_HEAT,
    HVACMode.FAN_ONLY: p.MODE_FAN,
}
MODE_TO_HVAC = {v: k for k, v in HVAC_TO_MODE.items()}
FAN_SILENT = "silent"
FAN_SPEEDS = {FAN_SILENT: 20, FAN_LOW: 40, FAN_MEDIUM: 60, FAN_HIGH: 80, FAN_AUTO: p.FAN_AUTO}
# The outdoor unit cannot heat and cool at once.
_HEATING = {p.MODE_HEAT}
_COOLING = {p.MODE_COOL, p.MODE_DRY}


async def async_align_group(hass: HomeAssistant, entry: ConfigEntry, mode: int) -> None:
    """Switch running indoor units on the same outdoor unit away from a conflicting mode."""
    unit = outdoor_unit(entry)
    if not unit or mode not in _HEATING | _COOLING:
        return
    for other in group_coordinators(hass, unit):
        data = other.data or {}
        if other is entry.runtime_data or not data.get("power"):
            continue
        current = data.get("mode")
        conflict = current == p.MODE_AUTO or (mode in _HEATING) != (current in _HEATING)
        if current in _HEATING | _COOLING | {p.MODE_AUTO} and conflict:
            target = mode if mode in _HEATING else p.MODE_COOL
            _LOGGER.info("%s: mode %s -> %s to match the shared outdoor unit", other.name, current, target)
            await other.async_set(mode=target)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the climate entity."""
    async_add_entities([AcClimate(entry)])


class AcClimate(AcEntity, ClimateEntity):
    """Indoor unit."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_precision = 0.1
    _attr_hvac_modes = [HVACMode.OFF, *HVAC_TO_MODE]
    _attr_swing_modes = [SWING_OFF, SWING_VERTICAL, SWING_HORIZONTAL, SWING_BOTH]

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "climate", None)
        self._entry = entry
        c: AcCoordinator = entry.runtime_data
        self._attr_min_temp, self._attr_max_temp = c.temperature_range
        self._attr_fan_modes = list(FAN_SPEEDS)
        # Offer only the louvre directions the unit reports (B5 0x0215).
        vertical, horizontal = c.swing_directions
        self._attr_swing_modes = [SWING_OFF]
        if vertical:
            self._attr_swing_modes.append(SWING_VERTICAL)
        if horizontal:
            self._attr_swing_modes.append(SWING_HORIZONTAL)
        if vertical and horizontal:
            self._attr_swing_modes.append(SWING_BOTH)
        self._attr_preset_modes = [PRESET_NONE, PRESET_SLEEP]
        if c.has(CAP_ECO, 1, 2):
            self._attr_preset_modes.append(PRESET_ECO)
        if c.has(CAP_TURBO):
            self._attr_preset_modes.append(PRESET_BOOST)
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        )

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Current mode."""
        if self.field("power") is None:
            return None
        return MODE_TO_HVAC.get(self.field("mode"), HVACMode.AUTO) if self.field("power") else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Running state (compressor frequency is only reported by some units)."""
        if not self.field("power"):
            return HVACAction.OFF
        mode = self.field("mode")
        if mode == p.MODE_FAN:
            return HVACAction.FAN
        if mode == p.MODE_DRY:
            return HVACAction.DRYING
        if self.field("compressor_frequency") == 0:
            return HVACAction.IDLE
        return HVACAction.HEATING if mode == p.MODE_HEAT else HVACAction.COOLING

    @property
    def native_current_temperature(self) -> float | None:
        """Indoor temperature."""
        return self.field("indoor_temperature")

    @property
    def current_humidity(self) -> float | None:
        """Indoor humidity (units with a humidity sensor)."""
        return self.field("humidity")

    @property
    def native_target_temperature(self) -> float | None:
        """Setpoint."""
        return self.field("target_temperature")

    @property
    def fan_mode(self) -> str | None:
        """Nearest named fan speed."""
        speed = self.field("fan_speed")
        if speed is None:
            return None
        if speed > 100:
            return FAN_AUTO
        return min((k for k in FAN_SPEEDS if k != FAN_AUTO), key=lambda k: abs(FAN_SPEEDS[k] - speed))

    @property
    def swing_mode(self) -> str | None:
        """Louvre swing."""
        vertical, horizontal = self.field("swing_vertical"), self.field("swing_horizontal")
        if vertical and horizontal:
            return SWING_BOTH
        return SWING_VERTICAL if vertical else SWING_HORIZONTAL if horizontal else SWING_OFF

    @property
    def preset_mode(self) -> str | None:
        """Active preset."""
        if self.field("turbo"):
            return PRESET_BOOST
        if self.field("eco"):
            return PRESET_ECO
        if self.field("sleep"):
            return PRESET_SLEEP
        return PRESET_NONE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn off or run in a mode."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_set(power=False)
            return
        mode = HVAC_TO_MODE[hvac_mode]
        await async_align_group(self.hass, self._entry, mode)
        await self.coordinator.async_set(power=True, mode=mode)

    async def async_turn_on(self) -> None:
        """Turn on in the last mode."""
        await async_align_group(self.hass, self._entry, self.field("mode"))
        await self.coordinator.async_set(power=True)

    async def async_turn_off(self) -> None:
        """Turn off."""
        await self.coordinator.async_set(power=False)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Setpoint, optionally with a mode."""
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(hvac_mode)
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            temperature = min(max(round(float(temperature) * 2) / 2, self.min_temp), self.max_temp)
            await self.coordinator.async_set(target_temperature=temperature)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Fan speed."""
        await self.coordinator.async_set(fan_speed=FAN_SPEEDS[fan_mode])

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Louvre swing."""
        await self.coordinator.async_set(
            swing_vertical=swing_mode in (SWING_VERTICAL, SWING_BOTH),
            swing_horizontal=swing_mode in (SWING_HORIZONTAL, SWING_BOTH),
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """ECO, turbo or sleep (mutually exclusive)."""
        await self.coordinator.async_set(
            eco=preset_mode == PRESET_ECO,
            turbo=preset_mode == PRESET_BOOST,
            sleep=preset_mode == PRESET_SLEEP,
        )
