"""Binary sensors: load outputs (reg 129), status (reg 128), holiday flags (reg 5)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.const import Platform
from .const import KIND_APPLIANCE
from .appliance.entities import async_setup_platform as async_setup_appliance
from .ac import extras as ac_extras
from .const import (
    CONF_KIND,
    KIND_AC,
    FUNCTION_HOLIDAY_AWAY,
    FUNCTION_HOLIDAY_HOME,
    REG_FUNCTION,
    REG_LOADS,
    REG_PARAM1,
    REG_PARAM2,
    REG_STATUS,
)
from .entity import HeatPumpEntity

RUN = BinarySensorDeviceClass.RUNNING
HEAT = BinarySensorDeviceClass.HEAT
PROBLEM = BinarySensorDeviceClass.PROBLEM

# (register, bit, key, name, device_class, enabled by default)
BITS = (
    (REG_LOADS, 0, "ibh1", "Elektrický ohrievač IBH1", RUN, True),
    (REG_LOADS, 1, "ibh2", "Elektrický ohrievač IBH2", RUN, False),
    (REG_LOADS, 2, "tbh", "Ohrievač bojlera TBH", RUN, True),
    (REG_LOADS, 3, "pump_i", "Vnútorné obehové čerpadlo", RUN, True),
    (REG_LOADS, 4, "sv1", "3-cestný ventil SV1 (bojler)", None, True),
    (REG_LOADS, 5, "sv2", "3-cestný ventil SV2", None, False),
    (REG_LOADS, 6, "pump_o", "Vonkajšie obehové čerpadlo", RUN, False),
    (REG_LOADS, 7, "pump_d", "Cirkulácia TÚV (pump_D)", RUN, False),
    (REG_LOADS, 8, "pump_c", "Čerpadlo zóny 2 (pump_C)", RUN, False),
    (REG_LOADS, 9, "sv3", "3-cestný ventil SV3", None, False),
    (REG_LOADS, 10, "crankcase", "Ohrev kľukovej skrine", HEAT, True),
    (REG_LOADS, 11, "pump_s", "Solárne čerpadlo (pump_S)", RUN, False),
    (REG_LOADS, 12, "alarm", "Alarm", PROBLEM, True),
    (REG_LOADS, 14, "ahs", "Externý zdroj tepla (AHS)", RUN, False),
    # Status bit 1 (register 128), Midea Modbus document page 2.
    (REG_STATUS, 1, "defrost", "Odmrazovanie", RUN, True),
    (REG_STATUS, 2, "anti_freeze", "Ochrana proti zamrznutiu", RUN, True),
    (REG_STATUS, 3, "oil_return", "Návrat oleja", RUN, True),
    (REG_STATUS, 4, "remote_onoff", "Diaľkové zap/vyp aktívne", None, False),
    (REG_STATUS, 6, "thermostat_heat", "Termostat – požiadavka kúrenia (HT)", RUN, True),
    (REG_STATUS, 7, "thermostat_cool", "Termostat – požiadavka chladenia (CL)", RUN, True),
    (REG_STATUS, 8, "solar_input", "Solárny vstup", None, False),
    (REG_STATUS, 9, "dhw_anti_freeze", "Ochrana bojlera proti zamrznutiu", RUN, True),
    (REG_STATUS, 10, "sg_signal", "Smart grid signál (SG)", None, True),
    (REG_STATUS, 11, "euv_signal", "Lacná elektrina (EUV)", None, True),
    (REG_FUNCTION, FUNCTION_HOLIDAY_AWAY, "holiday_away", "Dovolenka – preč", None, True),
    (REG_FUNCTION, FUNCTION_HOLIDAY_HOME, "holiday_home", "Dovolenka – doma", None, False),
    # Installer "parameter setting 1/2" (registers 210/211), read every 10 minutes.
    *(
        (REG_PARAM1, bit, f"p1_{key}", f"Funkcia: {label}", None, True)
        for bit, key, label in (
            (15, "dhw", "teplá voda"), (14, "tbh", "ohrievač bojlera TBH"),
            (13, "disinfect", "dezinfekcia"), (12, "pump_d", "cirkulačné čerpadlo TÚV"),
            (11, "dhw_priority_fn", "priorita TÚV"), (10, "pump_d_disinfect", "cirkulácia pri dezinfekcii"),
            (9, "cooling", "chladenie"), (7, "heating", "kúrenie"),
            (5, "pump_i_silent", "tiché obehové čerpadlo"), (4, "room_temp", "riadenie podľa izbovej teploty"),
            (3, "room_thermostat", "izbový termostat"), (2, "thermostat_mode", "termostat prepína režim"),
            (1, "thermostat_double", "termostat 2 zóny"), (0, "dhw_priority", "priorita TÚV zapnutá"),
        )
    ),
    *(
        (REG_PARAM2, bit, f"p2_{key}", f"Funkcia: {label}", None, True)
        for bit, key, label in (
            (14, "m1m2", "M1M2 / AHS zap-vyp"), (12, "tbt1", "snímač akumulačky Tbt1"),
            (11, "fpipe", "potrubie ≥ 10 m"), (7, "smart_grid", "smart grid"),
            (3, "double_zone", "dve zóny"), (1, "tbt", "akumulačná nádrž"),
        )
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up binary sensors."""
    if entry.data.get(CONF_KIND) == KIND_APPLIANCE:
        await async_setup_appliance(entry, async_add_entities, Platform.BINARY_SENSOR)
        return
    if entry.data.get(CONF_KIND) == KIND_AC:
        await ac_extras.async_setup_binary_sensor(hass, entry, async_add_entities)
        return
    async_add_entities([*(BitSensor(entry, *spec) for spec in BITS), CompressorRunning(entry)])


class CompressorRunning(HeatPumpEntity, BinarySensorEntity):
    """On while the compressor frequency (register 100) is above zero."""

    _attr_device_class = RUN

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "compressor_running", "Kompresor beží")

    @property
    def is_on(self) -> bool | None:
        """Compressor running."""
        freq = self.reg(100)
        return None if freq is None else freq > 0


class BitSensor(HeatPumpEntity, BinarySensorEntity):
    """One bit of a status register."""

    def __init__(
        self, entry: ConfigEntry, address: int, bit: int, key: str, name: str,
        device_class: BinarySensorDeviceClass | None, enabled: bool,
    ) -> None:
        """Initialize."""
        super().__init__(entry, key, name, enabled=enabled)
        self._address, self._bit = address, bit
        self._attr_device_class = device_class
        if address in (REG_PARAM1, REG_PARAM2):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool | None:
        """Bit state."""
        return self.bit(self._address, self._bit)
