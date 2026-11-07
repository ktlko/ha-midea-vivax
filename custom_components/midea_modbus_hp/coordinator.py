"""Modbus TCP polling and writes for the heat pump."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, READ_BLOCKS, SCAN_SECONDS, SLOW_BLOCKS, SLOW_EVERY

_LOGGER = logging.getLogger(__name__)


class HeatPumpCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Reads all register blocks; data maps register address -> raw uint16."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, host: str, port: int, device_id: int
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_SECONDS),
        )
        self.host, self.port, self.device_id = host, port, device_id
        self._client = AsyncModbusTcpClient(host, port=port, timeout=5, retries=2)
        self._lock = asyncio.Lock()
        self._polls = 0

    async def _ensure_connected(self) -> None:
        if not self._client.connected and not await self._client.connect():
            raise UpdateFailed(f"Cannot connect to {self.host}:{self.port}")

    async def _read(self, start: int, count: int) -> list[int]:
        result = await self._client.read_holding_registers(
            start, count=count, device_id=self.device_id
        )
        if result.isError():
            raise UpdateFailed(f"Read {start}+{count} failed: {result}")
        return list(result.registers)

    async def _async_update_data(self) -> dict[int, int]:
        async with self._lock:
            try:
                await self._ensure_connected()
                blocks = list(READ_BLOCKS)
                if self._polls % SLOW_EVERY == 0:
                    blocks += SLOW_BLOCKS
                self._polls += 1
                data = dict(self.data or {})  # keep slow registers between their reads
                for start, count in blocks:
                    for offset, value in enumerate(await self._read(start, count)):
                        data[start + offset] = value
                return data
            except ModbusException as err:
                self._client.close()
                raise UpdateFailed(str(err)) from err

    async def async_write(self, address: int, value: int) -> None:
        """Write one holding register, then refresh."""
        await self._write(address, lambda _old: value)

    async def async_write_bits(self, address: int, mask: int, value: int) -> None:
        """Read-modify-write: replace the bits in ``mask`` with ``value``."""
        await self._write(address, lambda old: (old & ~mask & 0xFFFF) | (value & mask))

    async def _write(self, address: int, build) -> None:
        async with self._lock:
            try:
                await self._ensure_connected()
                (old,) = await self._read(address, 1)  # fresh value, not the cache
                new = build(old)
                _LOGGER.debug("Write reg %s: %s -> %s", address, old, new)
                result = await self._client.write_register(
                    address, new, device_id=self.device_id
                )
                if result.isError():
                    raise UpdateFailed(f"Write {address}={new} failed: {result}")
                if self.data is not None:
                    self.data[address] = new  # slow registers are not re-read right away
                    self.async_update_listeners()
            except ModbusException as err:
                self._client.close()
                raise UpdateFailed(str(err)) from err
        await asyncio.sleep(1)
        await self.async_request_refresh()

    async def async_close(self) -> None:
        """Close the TCP connection."""
        self._client.close()
