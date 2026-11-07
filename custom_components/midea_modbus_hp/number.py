"""Numbers: setpoints, weather curves and installer parameters.

Installer parameter ranges are the ones in the Vivax HPS-HM-AERI manual
("FOR SERVICEMAN" table), so values outside what the unit accepts are refused.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfPower, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.const import Platform
from .const import KIND_APPLIANCE
from .appliance.entities import async_setup_platform as async_setup_appliance
from .ac import extras as ac_extras
from .const import (
    CONF_KIND,
    KIND_AC,
    REG_CURVE,
    REG_DHW_SET,
    REG_ROOM_SET,
    REG_SG_MAX,
    REG_ZONE1_SET,
    REG_ZONE2_SET,
)
from .entity import HeatPumpEntity, signed

C = UnitOfTemperature.CELSIUS
TEMP = NumberDeviceClass.TEMPERATURE
MIN = UnitOfTime.MINUTES
CFG = EntityCategory.CONFIG


@dataclass(frozen=True)
class Num:
    """A number stored in (part of) one holding register."""

    address: int
    key: str
    name: str
    low: float
    high: float
    step: float = 1
    unit: str | None = C
    device_class: NumberDeviceClass | None = TEMP
    scale: float = 1  # register value = number / scale
    mask: int = 0xFFFF
    shift: int = 0
    is_signed: bool = False
    enabled: bool = True
    category: EntityCategory | None = None


NUMBERS: tuple[Num, ...] = (
    Num(REG_ZONE1_SET, "zone1_set", "Zóna 1 – žiadaná teplota vody", 5, 65),
    Num(REG_ZONE2_SET, "zone2_set", "Zóna 2 – žiadaná teplota vody", 5, 65, enabled=False),
    Num(REG_DHW_SET, "dhw_set", "Teplá voda – žiadaná teplota", 20, 60),
    Num(REG_ROOM_SET, "room_set", "Izba – žiadaná teplota", 17, 30, 0.5, scale=0.5),
    Num(REG_CURVE, "curve_z1_no", "Ekvitermická krivka zóna 1 (1–9)", 1, 9, unit=None,
        device_class=None, mask=0x00FF),
    Num(REG_CURVE, "curve_z2_no", "Ekvitermická krivka zóna 2 (1–9)", 1, 9, unit=None,
        device_class=None, mask=0xFF00, shift=8, enabled=False),
    Num(REG_SG_MAX, "sg_max", "Smart grid – max. hodín pri drahej tarife", 0, 24,
        unit=UnitOfTime.HOURS, device_class=None, enabled=False),
    # --- installer parameters (FOR SERVICEMAN) ---
    # Teplá voda
    Num(212, "p_dt5_on", "TÚV – hysterézia štartu (dT5_ON)", 1, 30, category=CFG),
    Num(213, "p_dt1s5", "TÚV – rozdiel voda/bojler (dT1S5)", 5, 40, category=CFG),
    Num(215, "p_t4dhwmax", "TÚV – max. vonkajšia teplota", 35, 43, is_signed=True, category=CFG),
    Num(216, "p_t4dhwmin", "TÚV – min. vonkajšia teplota", -25, 30, is_signed=True, category=CFG),
    Num(241, "p_t_dhwhp_max", "TÚV – max. doba ohrevu tepelným čerpadlom", 10, 600, 5, MIN, None, category=CFG),
    Num(242, "p_t_dhwhp_restrict", "TÚV – doba kúrenia medzi ohrevmi TÚV", 10, 600, 5, MIN, None, category=CFG),
    Num(209, "p_pump_d_time", "Cirkulácia TÚV – doba behu", 5, 120, 1, MIN, None, category=CFG),
    # Ohrievač bojlera TBH
    Num(217, "p_t_tbh_delay", "TBH – oneskorenie zapnutia", 0, 240, 5, MIN, None, category=CFG),
    Num(218, "p_dt5_tbh_off", "TBH – rozdiel vypnutia (dT5_TBH_OFF)", 0, 10, category=CFG),
    Num(219, "p_t4_tbh_on", "TBH – max. vonkajšia teplota", -5, 50, is_signed=True, category=CFG),
    Num(252, "p_tbh_power", "TBH – príkon", 0, 20, 0.5, UnitOfPower.KILO_WATT, None, scale=0.1, category=CFG),
    # Dezinfekcia
    Num(220, "p_t5s_di", "Dezinfekcia – teplota", 60, 70, category=CFG),
    Num(221, "p_t_di_max", "Dezinfekcia – max. trvanie", 90, 300, 5, MIN, None, category=CFG),
    Num(222, "p_t_di_hightemp", "Dezinfekcia – držanie teploty", 5, 60, 5, MIN, None, category=CFG),
    # Chladenie
    Num(224, "p_dt1sc", "Chladenie – hysterézia vody (dT1SC)", 2, 10, category=CFG),
    Num(225, "p_dtsc", "Chladenie – hysterézia izby (dTSC)", 1, 10, category=CFG),
    Num(226, "p_t4cmax", "Chladenie – max. vonkajšia teplota", 35, 52, is_signed=True, category=CFG),
    Num(227, "p_t4cmin", "Chladenie – min. vonkajšia teplota", -5, 25, is_signed=True, category=CFG),
    # Kúrenie
    Num(229, "p_dt1sh", "Kúrenie – hysterézia vody (dT1SH)", 2, 20, category=CFG),
    Num(230, "p_dtsh", "Kúrenie – hysterézia izby (dTSH)", 1, 10, category=CFG),
    Num(231, "p_t4hmax", "Kúrenie – max. vonkajšia teplota", 20, 35, is_signed=True, category=CFG),
    Num(232, "p_t4hmin", "Kúrenie – min. vonkajšia teplota", -25, 30, is_signed=True, category=CFG),
    Num(243, "p_t4autocmin", "Auto – min. vonkajšia pre chladenie", 20, 29, is_signed=True, category=CFG),
    Num(244, "p_t4autohmax", "Auto – max. vonkajšia pre kúrenie", 10, 17, is_signed=True, category=CFG),
    # Vlastná ekvitermická krivka zóna 1 (bod 1 a bod 2)
    Num(265, "p_t1seth1", "Vlastná krivka kúrenie – voda bod 1", 25, 65, category=CFG),
    Num(267, "p_t4h1", "Vlastná krivka kúrenie – vonku bod 1", -25, 35, is_signed=True, category=CFG),
    Num(266, "p_t1seth2", "Vlastná krivka kúrenie – voda bod 2", 25, 65, category=CFG),
    Num(268, "p_t4h2", "Vlastná krivka kúrenie – vonku bod 2", -25, 35, is_signed=True, category=CFG),
    Num(261, "p_t1setc1", "Vlastná krivka chladenie – voda bod 1", 5, 25, category=CFG),
    Num(262, "p_t1setc2", "Vlastná krivka chladenie – voda bod 2", 5, 25, category=CFG),
    Num(264, "p_t4c2", "Vlastná krivka chladenie – vonku bod 2", -5, 46, is_signed=True, category=CFG),
    # Záložný ohrievač IBH a externý zdroj AHS
    Num(233, "p_t4_ibh_on", "IBH – max. vonkajšia teplota zapnutia", -15, 30, is_signed=True, category=CFG),
    Num(234, "p_dt1_ibh_on", "IBH – rozdiel vody pre zapnutie", 2, 10, category=CFG),
    Num(235, "p_t_ibh_delay", "IBH – oneskorenie zapnutia", 15, 120, 5, MIN, None, category=CFG),
    Num(250, "p_ibh1_power", "IBH1 – príkon", 0, 20, 0.5, UnitOfPower.KILO_WATT, None, scale=0.1, category=CFG),
    Num(251, "p_ibh2_power", "IBH2 – príkon", 0, 20, 0.5, UnitOfPower.KILO_WATT, None, scale=0.1,
        enabled=False, category=CFG),
    Num(237, "p_t4_ahs_on", "AHS – max. vonkajšia teplota zapnutia", -15, 30, is_signed=True,
        enabled=False, category=CFG),
    Num(238, "p_dt1_ahs_on", "AHS – rozdiel vody pre zapnutie", 2, 20, enabled=False, category=CFG),
    Num(240, "p_t_ahs_delay", "AHS – oneskorenie zapnutia", 5, 120, 5, MIN, None, enabled=False, category=CFG),
    # Dovolenka a ostatné
    Num(245, "p_holiday_heat", "Dovolenka – teplota vody kúrenia", 20, 25, category=CFG),
    Num(246, "p_holiday_dhw", "Dovolenka – teplota TÚV", 20, 25, category=CFG),
    Num(269, "p_power_limit", "Obmedzenie príkonu (typ 0–8)", 0, 8, unit=None, device_class=None, category=CFG),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up numbers."""
    if entry.data.get(CONF_KIND) == KIND_APPLIANCE:
        await async_setup_appliance(entry, async_add_entities, Platform.NUMBER)
        return
    if entry.data.get(CONF_KIND) == KIND_AC:
        await ac_extras.async_setup_number(hass, entry, async_add_entities)
        return
    async_add_entities(RegisterNumber(entry, spec) for spec in NUMBERS)


class RegisterNumber(HeatPumpEntity, NumberEntity):
    """A setting stored in (part of) one register."""

    _attr_mode = NumberMode.BOX

    def __init__(self, entry: ConfigEntry, spec: Num) -> None:
        """Initialize."""
        super().__init__(entry, spec.key, spec.name, enabled=spec.enabled)
        self._spec = spec
        self._attr_native_min_value = spec.low
        self._attr_native_max_value = spec.high
        self._attr_native_step = spec.step
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_device_class = spec.device_class
        self._attr_entity_category = spec.category

    @property
    def native_value(self) -> float | None:
        """Current value."""
        raw = self.reg(self._spec.address)
        if raw is None:
            return None
        raw = (raw & self._spec.mask) >> self._spec.shift
        if self._spec.is_signed:
            raw = signed(raw)
        value = raw * self._spec.scale
        return round(value, 1) if self._spec.scale != 1 else value

    async def async_set_native_value(self, value: float) -> None:
        """Write the value, keeping other bits of the register."""
        raw = (round(value / self._spec.scale) & 0xFFFF) << self._spec.shift
        await self.coordinator.async_write_bits(self._spec.address, self._spec.mask, raw)
