"""Selects: louvre angles and the shared-outdoor-unit mode."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import protocol as p
from .coordinator import CAP_LR_ANGLE, CAP_UD_ANGLE
from .entity import AcEntity, OutdoorEntity, group_coordinators, is_group_primary

ANGLES = {"free": 0, "1": 1, "2": 25, "3": 50, "4": 75, "5": 100}
GROUP_MODES = {"heat": p.MODE_HEAT, "cool": p.MODE_COOL, "dry": p.MODE_DRY, "fan_only": p.MODE_FAN}
GROUP_OFF = "off"
GROUP_MIXED = "mixed"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up selects."""
    c = entry.runtime_data
    entities: list[SelectEntity] = []
    if c.has(CAP_UD_ANGLE):
        entities.append(AngleSelect(entry, "ud_angle", p.TAG_UD_ANGLE, "Lamela hore–dole", "mdi:arrow-up-down"))
    if c.has(CAP_LR_ANGLE):
        entities.append(AngleSelect(entry, "lr_angle", p.TAG_LR_ANGLE, "Lamela vľavo–vpravo", "mdi:arrow-left-right"))
    if is_group_primary(hass, entry):
        entities.append(GroupModeSelect(entry))
    async_add_entities(entities)


class AngleSelect(AcEntity, SelectEntity):
    """Fixed louvre position (new-protocol property)."""

    _attr_options = list(ANGLES)

    def __init__(self, entry: ConfigEntry, key: str, tag: int, name: str, icon: str) -> None:
        """Initialize."""
        super().__init__(entry, key, name)
        self._key, self._tag = key, tag
        self._attr_icon = icon

    @property
    def current_option(self) -> str | None:
        """Nearest position."""
        value = self.field(self._key)
        if value is None:
            return None
        return min(ANGLES, key=lambda k: abs(ANGLES[k] - value))

    async def async_select_option(self, option: str) -> None:
        """Move the louvre."""
        await self.coordinator.async_set_property(self._tag, ANGLES[option])


class GroupModeSelect(OutdoorEntity, SelectEntity):
    """One mode for all running indoor units of a multi-split (the outdoor unit heats or cools)."""

    _attr_icon = "mdi:hvac"
    _attr_options = [GROUP_OFF, *GROUP_MODES, GROUP_MIXED]

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "mode", "Režim jednotiek")

    @property
    def current_option(self) -> str:
        """Mode of the running units."""
        modes = {
            (c.data or {}).get("mode") for c in group_coordinators(self.hass, self.unit) if (c.data or {}).get("power")
        }
        if not modes:
            return GROUP_OFF
        if len(modes) > 1:
            return GROUP_MIXED
        mode = modes.pop()
        return next((k for k, v in GROUP_MODES.items() if v == mode), GROUP_MIXED)

    async def async_added_to_hass(self) -> None:
        """Follow every member, not only the primary."""
        await super().async_added_to_hass()
        for c in group_coordinators(self.hass, self.unit):
            if c is not self.coordinator:
                self.async_on_remove(c.async_add_listener(self.async_write_ha_state))

    async def async_select_option(self, option: str) -> None:
        """Turn all running units off, or switch them to one mode."""
        for c in group_coordinators(self.hass, self.unit):
            if not (c.data or {}).get("power"):
                continue
            if option == GROUP_OFF:
                await c.async_set(power=False)
            elif option in GROUP_MODES:
                await c.async_set(mode=GROUP_MODES[option])
