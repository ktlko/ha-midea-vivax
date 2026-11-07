"""Midea/Vivax devices on the local network.

Heat pump over Modbus TCP (e.g. Elfin EW11 on the wired controller H1/H2) and air
conditioners over their Wi-Fi modules (LAN protocol V3, see ac/protocol.py).
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .ac.coordinator import AcCoordinator
from .appliance.coordinator import ApplianceCoordinator
from .const import (
    CONF_KIND,
    CONF_OUTDOOR_UNIT,
    DEFAULT_DEVICE_ID,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    KIND_AC,
    KIND_APPLIANCE,
)
from .coordinator import HeatPumpCoordinator

CONF_DEVICE_ID = "device_id"
CONF_AIR_CONDITIONERS = "air_conditioners"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): cv.positive_int,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                # Air conditioners paired by Midea AC LAN (token/key are taken from its storage).
                vol.Optional(CONF_AIR_CONDITIONERS, default=[]): [
                    vol.Schema(
                        {
                            vol.Required(CONF_DEVICE_ID): cv.positive_int,
                            vol.Required(CONF_NAME): cv.string,
                            vol.Optional(CONF_OUTDOOR_UNIT, default=""): cv.string,
                        }
                    )
                ],
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Turn a ``midea_modbus_hp:`` YAML block into config entries (shown in the UI)."""
    if DOMAIN in config:
        conf = dict(config[DOMAIN])
        for unit in conf.pop(CONF_AIR_CONDITIONERS):
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_KIND: KIND_AC, **unit}
                )
            )
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    if entry.data.get(CONF_KIND) == KIND_APPLIANCE:
        appliance = ApplianceCoordinator(hass, entry)
        try:
            await appliance.async_config_entry_first_refresh()
        except Exception:
            await appliance.async_close()
            raise
        entry.runtime_data = appliance
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True
    if entry.data.get(CONF_KIND) == KIND_AC:
        ac = AcCoordinator(hass, entry)
        await ac.async_config_entry_first_refresh()
        entry.runtime_data = ac
        entry.async_on_unload(entry.add_update_listener(_async_reload))
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True
    coordinator = HeatPumpCoordinator(
        hass, entry, entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_DEVICE_ID]
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    # The circulation pump switch became a button (the bit is only a start pulse).
    registry = er.async_get(hass)
    if old := registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{entry.unique_id or entry.entry_id}_pump_d_on"
    ):
        registry.async_remove(old)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and isinstance(entry.runtime_data, HeatPumpCoordinator):
        await entry.runtime_data.async_close()
    if unloaded and isinstance(entry.runtime_data, ApplianceCoordinator):
        await entry.runtime_data.async_close()
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Options changed (outdoor unit, address): rebuild the entities."""
    await hass.config_entries.async_reload(entry.entry_id)
