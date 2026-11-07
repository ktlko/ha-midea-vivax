"""Sensors of an air conditioner and of a shared outdoor unit."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import CAP_ENERGY, CAP_HUMIDITY
from .entity import AcEntity, OutdoorEntity, is_group_primary, outdoor_unit


@dataclass(frozen=True)
class Spec:
    """One value from the coordinator data."""

    key: str
    name: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT
    enabled: bool = True
    diagnostic: bool = False


TEMP = UnitOfTemperature.CELSIUS
INDOOR = (
    Spec("indoor_temperature", "Teplota v miestnosti", TEMP, SensorDeviceClass.TEMPERATURE),
    Spec("pmv", "Tepelný komfort (PMV)", None, None, enabled=False, diagnostic=True),
    Spec("indoor_fan_speed", "Otáčky vnútorného ventilátora", REVOLUTIONS_PER_MINUTE, None, diagnostic=True),
    Spec("indoor_coil_temperature", "Teplota vnútorného výmenníka", TEMP, SensorDeviceClass.TEMPERATURE,
         enabled=False, diagnostic=True),
)
HUMIDITY = Spec("humidity", "Vlhkosť v miestnosti", PERCENTAGE, SensorDeviceClass.HUMIDITY)
# On a multi-split these describe the shared outdoor unit; otherwise they belong to the unit itself.
OUTDOOR = (
    Spec("outdoor_temperature", "Vonkajšia teplota", TEMP, SensorDeviceClass.TEMPERATURE),
    Spec("compressor_frequency", "Frekvencia kompresora", UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY,
         diagnostic=True),
    Spec("compressor_current", "Prúd kompresora", UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT,
         enabled=False, diagnostic=True),
    Spec("outdoor_coil_temperature", "Teplota vonkajšieho výmenníka", TEMP, SensorDeviceClass.TEMPERATURE,
         enabled=False, diagnostic=True),
    Spec("discharge_temperature", "Teplota na výtlaku kompresora", TEMP, SensorDeviceClass.TEMPERATURE,
         enabled=False, diagnostic=True),
    Spec("outdoor_fan_speed", "Otáčky vonkajšieho ventilátora", REVOLUTIONS_PER_MINUTE, None, diagnostic=True),
)
ENERGY = Spec("energy_total", "Spotrebovaná elektrina", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY,
              SensorStateClass.TOTAL_INCREASING)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up sensors."""
    c = entry.runtime_data
    entities: list[SensorEntity] = [AcSensor(entry, spec) for spec in INDOOR]
    if c.has(CAP_HUMIDITY):
        entities.append(AcSensor(entry, HUMIDITY))
    shared = list(OUTDOOR) + ([ENERGY] if c.has(CAP_ENERGY) else [])
    if not outdoor_unit(entry):
        entities += [AcSensor(entry, spec) for spec in shared]
    elif is_group_primary(hass, entry):
        entities += [OutdoorSensor(entry, spec) for spec in shared]
    async_add_entities(entities)


def _apply(entity: SensorEntity, spec: Spec) -> None:
    entity._attr_native_unit_of_measurement = spec.unit  # noqa: SLF001
    entity._attr_device_class = spec.device_class  # noqa: SLF001
    entity._attr_state_class = spec.state_class  # noqa: SLF001
    if spec.diagnostic:
        entity._attr_entity_category = EntityCategory.DIAGNOSTIC  # noqa: SLF001


class AcSensor(AcEntity, SensorEntity):
    """Value of an indoor unit."""

    def __init__(self, entry: ConfigEntry, spec: Spec) -> None:
        """Initialize."""
        super().__init__(entry, spec.key, spec.name, enabled=spec.enabled)
        self._key = spec.key
        _apply(self, spec)

    @property
    def native_value(self) -> float | None:
        """Value."""
        return self.field(self._key)


class OutdoorSensor(OutdoorEntity, SensorEntity):
    """Value of a shared outdoor unit, read through the group's primary indoor unit."""

    def __init__(self, entry: ConfigEntry, spec: Spec) -> None:
        """Initialize."""
        super().__init__(entry, spec.key, spec.name, enabled=spec.enabled)
        self._key = spec.key
        _apply(self, spec)

    @property
    def native_value(self) -> float | None:
        """Value."""
        return self.field(self._key)
