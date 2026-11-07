"""Smaller platforms of an air conditioner: fan percentage, self-clean button, filter sensor."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import protocol as p
from .coordinator import CAP_SELF_CLEAN
from .entity import AcEntity


async def async_setup_number(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Fan percentage on units with free fan speed."""
    if entry.runtime_data.fan_percent:
        async_add_entities([FanPercent(entry)])


async def async_setup_button(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Self-clean on units that support it."""
    if entry.runtime_data.has(CAP_SELF_CLEAN):
        async_add_entities([SelfCleanButton(entry)])


async def async_setup_binary_sensor(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Filter and self-clean state."""
    entities = [FilterSensor(entry)]
    if entry.runtime_data.has(CAP_SELF_CLEAN):
        entities.append(SelfCleanRunning(entry))
    async_add_entities(entities)


class FanPercent(AcEntity, NumberEntity):
    """Fan speed 1-100 % (auto is set in the climate entity)."""

    _attr_icon = "mdi:fan"
    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "fan_percent", "Ventilátor")

    @property
    def native_value(self) -> float | None:
        """Speed, None while on auto."""
        speed = self.field("fan_speed")
        return speed if speed is not None and speed <= 100 else None

    async def async_set_native_value(self, value: float) -> None:
        """Set speed."""
        await self.coordinator.async_set(fan_speed=int(value))


class SelfCleanButton(AcEntity, ButtonEntity):
    """Start evaporator self-cleaning (unit must be off)."""

    _attr_icon = "mdi:spray-bottle"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "self_clean_start", "Spustiť samočistenie")

    async def async_press(self) -> None:
        """Start."""
        await self.coordinator.async_set_property(p.TAG_SELF_CLEAN, 1)


class SelfCleanRunning(AcEntity, BinarySensorEntity):
    """Self-cleaning in progress."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "self_clean", "Samočistenie")

    @property
    def is_on(self) -> bool | None:
        """Running."""
        value = self.field("self_clean")
        return None if value is None else value > 0


class FilterSensor(AcEntity, BinarySensorEntity):
    """Filter needs cleaning."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:air-filter"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "filter_full", "Vyčistiť filter")

    @property
    def is_on(self) -> bool | None:
        """Dirty filter."""
        return self.field("filter_full")
