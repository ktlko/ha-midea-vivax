"""Entities built from the attributes of a midea-local appliance (see catalog.py)."""

from __future__ import annotations

from enum import Enum
import re
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN
from .catalog import DEVICE_TYPES, ENTITIES
from .coordinator import ApplianceCoordinator

MANUFACTURER = "Midea"


def option_key(value: Any) -> str:
    """Translation key of a select option (same rule as the catalog generator)."""
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_") or "none"


def _plain(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


class ApplianceEntity(CoordinatorEntity[ApplianceCoordinator]):
    """Entity of one attribute of a midea-local appliance."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, spec: dict[str, Any]) -> None:
        """Initialize."""
        super().__init__(entry.runtime_data)
        self.spec = spec
        self.attr: str = spec["a"]
        device_id = entry.data["device_id"]
        type_name = DEVICE_TYPES.get(self.coordinator.device_type, "Midea appliance")
        self._attr_unique_id = f"appliance_{device_id}_{spec['k']}"
        self._attr_translation_key = f"ml_{spec['k']}"
        if icon := spec.get("i"):
            self._attr_icon = icon
        if spec.get("ec") == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        model = entry.data.get("model")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"appliance_{device_id}")},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=f"{type_name} ({model})" if model else type_name,
        )

    @property
    def available(self) -> bool:
        """Connected and the attribute is known."""
        return super().available and self.coordinator.online

    @property
    def value(self) -> Any:
        """Current value of the attribute."""
        return _plain((self.coordinator.data or {}).get(self.attr))


class ApplianceSensor(ApplianceEntity, SensorEntity):
    """Read-only value."""

    def __init__(self, entry: ConfigEntry, spec: dict[str, Any]) -> None:
        """Initialize."""
        super().__init__(entry, spec)
        self._attr_native_unit_of_measurement = spec.get("u")
        if dc := spec.get("dc"):
            self._attr_device_class = SensorDeviceClass(dc)
        if sc := spec.get("sc"):
            self._attr_state_class = SensorStateClass(sc)
        self._options: list[str] | None = None
        if values := spec.get("o"):
            # Known text values (midea-local tables, confirmed by the Midea Lua plug-ins): translated states.
            self._options = list(dict.fromkeys(option_key(v) for v in values))
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = self._options

    @property
    def native_value(self) -> Any:
        """Value (lists and structures are not shown)."""
        value = self.value
        if self._options is not None:
            key = None if value is None else option_key(value)
            return key if key in self._options else None
        if isinstance(value, (list, tuple, dict)):
            return None
        if isinstance(value, bool) and self.spec.get("u") is None:
            return "on" if value else "off"
        if self.spec.get("dc") or self.spec.get("sc"):
            return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
        return value


class ApplianceBinarySensor(ApplianceEntity, BinarySensorEntity):
    """Flag."""

    def __init__(self, entry: ConfigEntry, spec: dict[str, Any]) -> None:
        """Initialize."""
        super().__init__(entry, spec)
        if dc := spec.get("dc"):
            self._attr_device_class = BinarySensorDeviceClass(dc)

    @property
    def is_on(self) -> bool | None:
        """Flag."""
        value = self.value
        return None if value is None else bool(value)


class ApplianceSwitch(ApplianceEntity, SwitchEntity):
    """Writable flag."""

    @property
    def is_on(self) -> bool | None:
        """Flag."""
        value = self.value
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.coordinator.async_set(self.attr, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.coordinator.async_set(self.attr, False)


class ApplianceSelect(ApplianceEntity, SelectEntity):
    """Choice among the values the library knows for this attribute."""

    def __init__(self, entry: ConfigEntry, spec: dict[str, Any]) -> None:
        """Initialize."""
        super().__init__(entry, spec)
        self._values = {option_key(o): o for o in spec["o"]}
        self._attr_options = list(self._values)

    @property
    def current_option(self) -> str | None:
        """Current choice."""
        value = self.value
        key = None if value is None else option_key(value)
        return key if key in self._values else None

    async def async_select_option(self, option: str) -> None:
        """Choose."""
        await self.coordinator.async_set(self.attr, self._values[option])


class ApplianceNumber(ApplianceEntity, NumberEntity):
    """Writable setpoint."""

    _attr_mode = NumberMode.BOX

    def __init__(self, entry: ConfigEntry, spec: dict[str, Any]) -> None:
        """Initialize."""
        super().__init__(entry, spec)
        self._attr_native_unit_of_measurement = spec.get("u")
        self._attr_native_step = float(spec.get("step", 1))
        if spec.get("dc") == "temperature":
            self._attr_device_class = NumberDeviceClass.TEMPERATURE
        elif spec.get("dc") == "humidity":
            self._attr_device_class = NumberDeviceClass.HUMIDITY

    def _bound(self, which: str) -> float:
        dynamic = (self.coordinator.data or {}).get(self.spec.get(f"{which}_attr") or "")
        if isinstance(dynamic, (int, float)) and not isinstance(dynamic, bool):
            return float(dynamic)
        return float(self.spec.get(which, 0 if which == "min" else 100))

    @property
    def native_min_value(self) -> float:
        """Lower limit."""
        return self._bound("min")

    @property
    def native_max_value(self) -> float:
        """Upper limit."""
        return self._bound("max")

    @property
    def native_value(self) -> float | None:
        """Setpoint."""
        value = self.value
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    async def async_set_native_value(self, value: float) -> None:
        """Write the setpoint."""
        step = self._attr_native_step or 1
        out: float | int = int(round(value)) if float(step).is_integer() else value
        await self.coordinator.async_set(self.attr, out)


CLASSES: dict[Platform, type[ApplianceEntity]] = {
    Platform.SENSOR: ApplianceSensor,
    Platform.BINARY_SENSOR: ApplianceBinarySensor,
    Platform.SWITCH: ApplianceSwitch,
    Platform.SELECT: ApplianceSelect,
    Platform.NUMBER: ApplianceNumber,
}


async def async_setup_platform(
    entry: ConfigEntry, async_add_entities: AddEntitiesCallback, platform: Platform
) -> None:
    """Add the catalog entities of one platform for this appliance."""
    coordinator: ApplianceCoordinator = entry.runtime_data
    cls = CLASSES.get(platform)
    if cls is None:
        return
    known = coordinator.device.attributes
    async_add_entities(
        cls(entry, spec)
        for spec in ENTITIES.get(coordinator.device_type, ())
        if spec["p"] == platform.value and spec["a"] in known
    )
