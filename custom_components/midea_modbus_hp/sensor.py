"""Read-only measurements (registers 100-146)."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ac import sensor as ac_sensor
from .const import CONF_KIND, KIND_AC, ERROR_CODES, NOT_PRESENT, REG_ENERGY_IN, REG_ENERGY_OUT
from .entity import HeatPumpEntity, signed

T = SensorDeviceClass.TEMPERATURE
C = UnitOfTemperature.CELSIUS
M = SensorStateClass.MEASUREMENT
DIAG = EntityCategory.DIAGNOSTIC


@dataclass(frozen=True)
class Reg:
    """One register-backed sensor."""

    address: int
    key: str
    name: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = M
    scale: float = 1
    is_signed: bool = True
    absent_255: bool = False  # 255 means "probe not installed / inactive"
    enabled: bool = True
    category: EntityCategory | None = None
    options: dict[int, str] | None = None
    mask: int = 0xFFFF  # for values packed into part of a register
    shift: int = 0


REGS: tuple[Reg, ...] = (
    Reg(100, "comp_freq", "Frekvencia kompresora", UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY),
    Reg(101, "unit_mode", "Aktuálny režim jednotky", state_class=None,
        options={0: "off", 2: "cool", 3: "heat"}),
    Reg(102, "fan_speed", "Otáčky ventilátora", "rpm"),
    Reg(103, "exv", "Expanzný ventil (otvorenie)", "P", enabled=False),
    Reg(104, "tw_in", "Vstup vody (Tw_in)", C, T),
    Reg(105, "tw_out", "Výstup vody (Tw_out)", C, T),
    Reg(106, "t3", "Kondenzátor (T3)", C, T),
    Reg(107, "t4", "Vonkajšia teplota (T4)", C, T),
    Reg(108, "tp", "Výtlak kompresora (Tp)", C, T),
    Reg(109, "th", "Sanie kompresora (Th)", C, T),
    Reg(110, "t1", "Celková výstupná voda (T1)", C, T),
    Reg(111, "t1b", "Voda zóna 2 (T1B)", C, T, absent_255=True, enabled=False),
    Reg(112, "t2", "Chladivo kvapalina (T2)", C, T),
    Reg(113, "t2b", "Chladivo plyn (T2B)", C, T),
    Reg(114, "ta", "Izbová teplota (Ta)", C, T),
    Reg(115, "t5", "Bojler (T5)", C, T),
    Reg(116, "p_high", "Vysoký tlak", UnitOfPressure.KPA, SensorDeviceClass.PRESSURE),
    Reg(117, "p_low", "Nízky tlak", UnitOfPressure.KPA, SensorDeviceClass.PRESSURE),
    Reg(118, "odu_current", "Prúd vonkajšej jednotky", UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT),
    Reg(119, "odu_voltage", "Napätie vonkajšej jednotky", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE),
    Reg(120, "tbt1", "Akumulačka hore (Tbt1)", C, T, absent_255=True, enabled=False),
    Reg(121, "tbt2", "Akumulačka dole (Tbt2)", C, T, absent_255=True, enabled=False),
    Reg(122, "comp_hours", "Prevádzka kompresora", UnitOfTime.HOURS, SensorDeviceClass.DURATION,
        SensorStateClass.TOTAL_INCREASING, is_signed=False),
    Reg(123, "unit_capacity", "Výkonová trieda jednotky", UnitOfPower.KILO_WATT, state_class=None,
        is_signed=False, category=DIAG),
    Reg(130, "idu_sw", "Softvér hydromodulu", state_class=None, is_signed=False, category=DIAG),
    Reg(131, "hmi_sw", "Softvér ovládača", state_class=None, is_signed=False, category=DIAG),
    Reg(132, "target_freq", "Cieľová frekvencia", UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY),
    Reg(133, "dc_current", "DC prúd", UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT,
        scale=0.1, enabled=False),
    Reg(134, "dc_voltage", "DC napätie", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE,
        scale=10, enabled=False),
    Reg(135, "tf", "Teplota modulu (TF)", C, T, enabled=False),
    Reg(136, "curve_t1s_z1", "Ekvitermický cieľ zóna 1", C, T, absent_255=True),
    Reg(137, "curve_t1s_z2", "Ekvitermický cieľ zóna 2", C, T, absent_255=True, enabled=False),
    Reg(138, "water_flow", "Prietok vody", UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        SensorDeviceClass.VOLUME_FLOW_RATE, scale=0.01),
    Reg(139, "odu_limit", "Obmedzenie prúdu (kód)", state_class=None, enabled=False, category=DIAG),
    Reg(140, "capacity", "Výkon hydromodulu", UnitOfPower.KILO_WATT, SensorDeviceClass.POWER, scale=0.01),
    Reg(141, "tsolar", "Solárny panel (Tsolar)", C, T, absent_255=True, enabled=False),
    # Installer limits and parameters (read every 10 minutes).
    Reg(201, "lim_cool_max", "Limit chladenie – max. voda zóna 1", C, T, None, mask=0x00FF, category=DIAG),
    Reg(202, "lim_cool_min", "Limit chladenie – min. voda zóna 1", C, T, None, mask=0x00FF, category=DIAG),
    Reg(203, "lim_heat_max", "Limit kúrenie – max. voda zóna 1", C, T, None, mask=0x00FF, category=DIAG),
    Reg(204, "lim_heat_min", "Limit kúrenie – min. voda zóna 1", C, T, None, mask=0x00FF, category=DIAG),
    Reg(205, "lim_room_max", "Limit izba – max.", C, T, None, scale=0.5, category=DIAG),
    Reg(206, "lim_room_min", "Limit izba – min.", C, T, None, scale=0.5, category=DIAG),
    Reg(207, "lim_dhw_max", "Limit teplá voda – max.", C, T, None, category=DIAG),
    Reg(208, "lim_dhw_min", "Limit teplá voda – min.", C, T, None, category=DIAG),
    Reg(255, "dry_up", "Sušenie podlahy – dni nábehu", UnitOfTime.DAYS, state_class=None, category=DIAG),
    Reg(256, "dry_peak_days", "Sušenie podlahy – dni na vrchole", UnitOfTime.DAYS, state_class=None, category=DIAG),
    Reg(257, "dry_down", "Sušenie podlahy – dni dobehu", UnitOfTime.DAYS, state_class=None, category=DIAG),
    Reg(258, "dry_peak", "Sušenie podlahy – vrcholová teplota", C, T, None, category=DIAG),
    Reg(259, "t_arsth", "Predohrev podlahy – trvanie", UnitOfTime.HOURS, state_class=None, category=DIAG),
    Reg(260, "preheat_t1s", "Predohrev podlahy – teplota vody", C, T, None, category=DIAG),
    *(
        Reg(272, f"emission_{key}", f"Typ vykurovacích telies – {label}", state_class=None,
            category=DIAG, mask=0xF << shift, shift=shift,
            options={0: "fan_coil", 1: "radiators", 2: "underfloor"})
        for key, label, shift in (
            ("z1_heat", "zóna 1 kúrenie", 0), ("z2_heat", "zóna 2 kúrenie", 4),
            ("z1_cool", "zóna 1 chladenie", 8), ("z2_cool", "zóna 2 chladenie", 12),
        )
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors."""
    if entry.data.get(CONF_KIND) == KIND_AC:
        await ac_sensor.async_setup_entry(hass, entry, async_add_entities)
        return
    entities: list[SensorEntity] = [RegisterSensor(entry, r) for r in REGS]
    entities += [
        ErrorSensor(entry, 124, "error", "Aktuálna porucha", True),
        ErrorSensor(entry, 125, "error_hist1", "Porucha – história 1", False),
        ErrorSensor(entry, 126, "error_hist2", "Porucha – história 2", False),
        ErrorSensor(entry, 127, "error_hist3", "Porucha – história 3", False),
    ]
    entities += [
        EnergySensor(entry, REG_ENERGY_IN, "energy_in", "Spotrebovaná elektrina"),
        EnergySensor(entry, REG_ENERGY_OUT, "energy_out", "Vyrobené teplo"),
        CopSensor(entry),
    ]
    async_add_entities(entities)


class RegisterSensor(HeatPumpEntity, SensorEntity):
    """Sensor for one 16-bit register."""

    def __init__(self, entry: ConfigEntry, spec: Reg) -> None:
        """Initialize."""
        super().__init__(entry, spec.key, spec.name, enabled=spec.enabled)
        self._spec = spec
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_device_class = SensorDeviceClass.ENUM if spec.options else spec.device_class
        self._attr_state_class = None if spec.options else spec.state_class
        self._attr_entity_category = spec.category
        if spec.options:
            self._attr_options = [*spec.options.values(), "other"]
        if spec.scale != 1:
            self._attr_suggested_display_precision = 2 if spec.scale < 1 else 0

    @property
    def native_value(self) -> float | int | str | None:
        """Scaled register value."""
        raw = self.reg(self._spec.address)
        if raw is None or (self._spec.absent_255 and raw == NOT_PRESENT):
            return None
        raw = (raw & self._spec.mask) >> self._spec.shift
        if self._spec.options:
            return self._spec.options.get(raw, "other")
        if self._spec.mask != 0xFFFF:
            value = raw - 0x100 if self._spec.is_signed and raw & 0x80 else raw  # int8
        else:
            value = signed(raw) if self._spec.is_signed else raw
        return round(value * self._spec.scale, 2) if self._spec.scale != 1 else value


class ErrorSensor(HeatPumpEntity, SensorEntity):
    """Error code with its description; raw code kept as an attribute."""

    _attr_icon = "mdi:alert-circle-outline"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [*ERROR_CODES.values(), "unknown"]

    def __init__(
        self, entry: ConfigEntry, address: int, key: str, name: str, current: bool
    ) -> None:
        """Initialize."""
        super().__init__(entry, key, name)
        self._address = address
        if not current:
            self._attr_entity_category = DIAG

    @property
    def native_value(self) -> str | None:
        """Description of the code."""
        raw = self.reg(self._address)
        if raw is None:
            return None
        return ERROR_CODES.get(raw, "unknown")

    @property
    def extra_state_attributes(self) -> dict[str, int | None]:
        """Raw code for automations."""
        return {"code": self.reg(self._address)}


class EnergySensor(HeatPumpEntity, SensorEntity):
    """32-bit energy counter across two registers (high word first)."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, entry: ConfigEntry, address: int, key: str, name: str) -> None:
        """Initialize."""
        super().__init__(entry, key, name)
        self._address = address

    @property
    def native_value(self) -> int | None:
        """Combined counter."""
        high, low = self.reg(self._address), self.reg(self._address + 1)
        return None if high is None or low is None else (high << 16) | low


class CopSensor(HeatPumpEntity, SensorEntity):
    """Lifetime COP from the two energy counters."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "cop_total", "COP celkový")

    @property
    def native_value(self) -> float | None:
        """Produced heat / consumed electricity."""
        regs = [self.reg(a) for a in range(REG_ENERGY_IN, REG_ENERGY_OUT + 2)]
        if None in regs:
            return None
        used = (regs[0] << 16) | regs[1]
        made = (regs[2] << 16) | regs[3]
        return round(made / used, 2) if used else None
