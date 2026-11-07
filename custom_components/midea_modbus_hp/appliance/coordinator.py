"""One Midea appliance handled by midea-local (it keeps the connection and pushes updates)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
DEFAULT_PORT = 6444


def build_device(name: str, data: dict[str, Any]) -> Any:
    """Create the midea-local device object (not connected yet)."""
    from midealocal.const import ProtocolVersion  # noqa: PLC0415
    from midealocal.devices import device_selector  # noqa: PLC0415

    return device_selector(
        name=name,
        device_id=int(data["device_id"]),
        device_type=int(data["type"]),
        ip_address=data["host"],
        port=int(data.get("port") or DEFAULT_PORT),
        token=data.get("token") or "",
        key=data.get("key") or "",
        device_protocol=ProtocolVersion(int(data.get("protocol") or 3)),
        model=data.get("model") or "",
        subtype=int(data.get("subtype") or 0),
    )


class ApplianceCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """State of one appliance; midea-local polls it and calls back on every change."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, config_entry=entry, name=entry.title)
        self.device_type: int = int(entry.data["type"])
        self.device = build_device(entry.title, dict(entry.data))
        if self.device is None:
            raise HomeAssistantError(f"Unsupported Midea device type {self.device_type:#04x}")

    @property
    def online(self) -> bool:
        """The library is connected to the appliance."""
        return bool(getattr(self.device, "available", False))

    async def _async_setup(self) -> None:
        self.device.register_update(self._on_update)
        await self.device.open()

    async def _async_update_data(self) -> dict[str, Any]:
        return dict(self.device.attributes)

    def _on_update(self, status: dict[str, Any]) -> None:
        """Called by midea-local; hop onto the event loop in case it runs elsewhere."""
        self.hass.loop.call_soon_threadsafe(self._push)

    def _push(self) -> None:
        self.async_set_updated_data(dict(self.device.attributes))

    async def async_set(self, attr: str, value: Any) -> None:
        """Write one attribute; the appliance answers with its new state."""
        if not self.online:
            raise HomeAssistantError(f"{self.name}: appliance is offline")
        try:
            self.device.set_attribute(attr, value)
        except Exception as err:  # noqa: BLE001 - socket closed, value rejected by the library
            raise HomeAssistantError(f"{self.name}: cannot set {attr}: {err}") from err

    async def async_close(self) -> None:
        """Stop the library's connection task."""
        self.device.unregister_update(self._on_update)
        await self.device.close()
