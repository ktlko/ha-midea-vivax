"""Switches of an air conditioner."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import protocol as p
from .coordinator import CAP_ANION, CAP_FROST, CAP_PREVENT_STRAIGHT_WIND
from .entity import AcEntity

# Prevent straight wind (B0/B1 0x0042): 1 = off, 2 = on.
STRAIGHT_WIND_OFF, STRAIGHT_WIND_ON = 1, 2


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up switches."""
    c = entry.runtime_data
    entities: list[SwitchEntity] = [
        StateSwitch(entry, "dry", "Vysušenie výmenníka po vypnutí", "mdi:water-off"),
        DisplaySwitch(entry),
        BeepSwitch(entry),
    ]
    if c.has(CAP_FROST, 1):
        entities.append(StateSwitch(entry, "frost_protect", "Temperovanie 8 °C", "mdi:snowflake-thermometer"))
    if c.has(CAP_ANION, 1):
        entities.append(StateSwitch(entry, "anion", "Ionizátor", "mdi:atom"))
    if c.has(CAP_PREVENT_STRAIGHT_WIND):
        entities.append(PreventStraightWindSwitch(entry))
    async_add_entities(entities)


class StateSwitch(AcEntity, SwitchEntity):
    """Flag of the classic state (written with the whole 0x40 set)."""

    def __init__(self, entry: ConfigEntry, key: str, name: str, icon: str) -> None:
        """Initialize."""
        super().__init__(entry, key, name)
        self._key = key
        self._attr_icon = icon

    @property
    def is_on(self) -> bool | None:
        """Flag."""
        return self.field(self._key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set."""
        await self.coordinator.async_set(**{self._key: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Clear."""
        await self.coordinator.async_set(**{self._key: False})


class DisplaySwitch(AcEntity, SwitchEntity):
    """Indoor display (the unit only knows a toggle command)."""

    _attr_icon = "mdi:television-ambient-light"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "display", "Displej")

    @property
    def is_on(self) -> bool | None:
        """Display lit."""
        return self.field("display")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Light up."""
        if not self.is_on:
            await self.coordinator.async_toggle_display()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Darken."""
        if self.is_on:
            await self.coordinator.async_toggle_display()


class BeepSwitch(AcEntity, SwitchEntity, RestoreEntity):
    """Confirmation beep for commands from Home Assistant (kept in HA, sent with each command)."""

    _attr_icon = "mdi:volume-high"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "beep", "Pípnutie pri ovládaní")

    async def async_added_to_hass(self) -> None:
        """Restore the choice."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self.coordinator.beep = last.state != "off"

    @property
    def is_on(self) -> bool:
        """Beep enabled."""
        return self.coordinator.beep

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable."""
        self.coordinator.beep = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable."""
        self.coordinator.beep = False
        self.async_write_ha_state()


class PreventStraightWindSwitch(AcEntity, SwitchEntity):
    """Keep the airflow off people (new-protocol property 0x0042)."""

    _attr_icon = "mdi:weather-windy-variant"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "prevent_straight_wind", "Vzduch mimo ľudí")

    @property
    def is_on(self) -> bool | None:
        """Active."""
        value = self.field("prevent_straight_wind")
        return None if value is None else value == STRAIGHT_WIND_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable."""
        await self.coordinator.async_set_property(p.TAG_PREVENT_STRAIGHT_WIND, STRAIGHT_WIND_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable."""
        await self.coordinator.async_set_property(p.TAG_PREVENT_STRAIGHT_WIND, STRAIGHT_WIND_OFF)
