"""Buttons: one-shot commands (reg 5 start pulses)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import KIND_APPLIANCE
from .ac import extras as ac_extras
from .const import CONF_KIND, KIND_AC, FUNCTION_PUMP_D, REG_FUNCTION
from .entity import HeatPumpEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up buttons."""
    if entry.data.get(CONF_KIND) == KIND_APPLIANCE:
        return  # no such entities
    if entry.data.get(CONF_KIND) == KIND_AC:
        await ac_extras.async_setup_button(hass, entry, async_add_entities)
        return
    async_add_entities([PumpDStartButton(entry)])


class PumpDStartButton(HeatPumpEntity, ButtonEntity):
    """Start the DHW circulation pump (pump_D).

    The bit is a start pulse: the unit runs pump_D for PUMP_D RUNNING TIME (reg 209)
    and clears the bit itself; clearing it earlier does not stop the pump.
    """

    _attr_icon = "mdi:pump"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "pump_d_start", "Spustiť cirkuláciu TÚV")

    async def async_press(self) -> None:
        """Set the start bit."""
        mask = 1 << FUNCTION_PUMP_D
        await self.coordinator.async_write_bits(REG_FUNCTION, mask, mask)
