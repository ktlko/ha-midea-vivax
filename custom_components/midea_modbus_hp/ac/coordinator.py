"""Polling and commands for one Midea air conditioner over Wi-Fi."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import protocol as p

_LOGGER = logging.getLogger(__name__)
SCAN_SECONDS = 30
MAX_MISSED = 3  # polls without a status reply before the entities go unavailable

# B5 capability tags
CAP_FAN = 0x0210
CAP_ECO = 0x0212
CAP_FROST = 0x0213
CAP_ENERGY = 0x0216
CAP_TURBO = 0x021A
CAP_ANION = 0x021E
CAP_HUMIDITY = 0x021F
CAP_TEMPERATURES = 0x0225
CAP_SELF_CLEAN = 0x0039
CAP_PREVENT_STRAIGHT_WIND = 0x0042
CAP_UD_ANGLE = 0x0009
CAP_LR_ANGLE = 0x000A

PROPERTY_TAGS = {
    CAP_HUMIDITY: p.TAG_INDOOR_HUMIDITY,
    CAP_UD_ANGLE: p.TAG_UD_ANGLE,
    CAP_LR_ANGLE: p.TAG_LR_ANGLE,
    CAP_SELF_CLEAN: p.TAG_SELF_CLEAN,
    CAP_PREVENT_STRAIGHT_WIND: p.TAG_PREVENT_STRAIGHT_WIND,
}


class AcCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """State of one unit; capabilities are read once from B5."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=entry.title,
            update_interval=timedelta(seconds=SCAN_SECONDS),
        )
        d = entry.data
        self.client = p.AcLanClient(d["host"], d["device_id"], d["token"], d["key"])
        self.capabilities: dict[int, bytes] = {}
        self.beep = True
        self._missed = 0

    # ---- capabilities
    def has(self, tag: int, *values: int) -> bool:
        """Capability reported (and, if given, with one of the values)."""
        raw = self.capabilities.get(tag)
        if not raw:
            return False
        return raw[0] in values if values else raw[0] != 0

    @property
    def fan_percent(self) -> bool:
        """Free 1-100 % fan speed (B5 0x0210 value 1)."""
        return self.has(CAP_FAN, 1)

    @property
    def temperature_range(self) -> tuple[float, float]:
        """Cool/auto/heat limits from B5 0x0225 (half degrees), else the remote's range."""
        raw = self.capabilities.get(CAP_TEMPERATURES)
        if raw and len(raw) >= 6:
            return min(raw[0], raw[2], raw[4]) / 2, max(raw[1], raw[3], raw[5]) / 2
        return 17.0, 30.0

    def _properties(self) -> list[int]:
        return [tag for cap, tag in PROPERTY_TAGS.items() if self.has(cap)]

    # ---- polling
    async def _async_setup(self) -> None:
        frames = await self._request([p.query_capabilities(), p.query_capabilities(additional=True)])
        for frame in frames:
            body = p.body_of(frame)
            if body[0] == 0xB5:
                self.capabilities.update(p.parse_b5(body))
        _LOGGER.debug("%s capabilities %s", self.name, {f"{k:#06x}": v.hex() for k, v in self.capabilities.items()})

    async def _async_update_data(self) -> dict[str, Any]:
        proto = self.client.protocol
        frames = [p.query_status(proto), p.query_group(1, proto), p.query_group(3, proto)]
        if self.has(CAP_ENERGY):
            frames.append(p.query_group(4, proto))
        if tags := self._properties():
            frames.append(p.query_properties(tags, proto))
        data = dict(self.data or {})
        replies = self._parse(await self._request(frames))
        if "power" not in replies:  # the modules now and then drop a reply; ask once more
            replies.update(self._parse(await self._request([p.query_status(self.client.protocol)])))
        if "power" not in replies:
            self._missed += 1
            if not data or self._missed >= MAX_MISSED:
                raise UpdateFailed(f"{self.name}: no status reply")
        else:
            self._missed = 0
        data.update(replies)
        return data

    async def _request(self, frames: list[bytes]) -> list[bytes]:
        try:
            return await self.client.request(frames)
        except p.MideaLanError as err:
            raise UpdateFailed(str(err)) from err

    @staticmethod
    def _parse(frames: list[bytes]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for frame in frames:
            body = p.body_of(frame)
            if body[0] == 0xC0 and len(body) > 21:
                out.update(p.parse_c0(body))
            elif body[0] == 0xC1 and len(body) > 4:
                group = body[3] if body[3] != 0x03 else 0x43  # some units answer group 3 as 0x03
                out.update(p.parse_c1(body[:3] + bytes([group]) + body[4:]))
            elif body[0] == 0xB1:
                props = p.parse_b1(body)
                if value := props.get(p.TAG_INDOOR_HUMIDITY):
                    out["humidity"] = value[0] if 0 < value[0] <= 100 else None
                for key, tag in (("ud_angle", p.TAG_UD_ANGLE), ("lr_angle", p.TAG_LR_ANGLE),
                                 ("self_clean", p.TAG_SELF_CLEAN),
                                 ("prevent_straight_wind", p.TAG_PREVENT_STRAIGHT_WIND)):
                    if value := props.get(tag):
                        out[key] = value[0]
        return out

    # ---- commands
    async def async_set(self, **changes: Any) -> None:
        """Write the whole classic state with the given changes."""
        if not self.data:
            raise UpdateFailed(f"{self.name}: state unknown, cannot write")
        state = {**self.data, **changes}
        frames = await self._request([p.set_general(state, self.client.protocol, beep=self.beep)])
        self._apply(changes, frames)

    async def async_set_property(self, tag: int, value: int) -> None:
        """Write one new-protocol property (B0)."""
        frames = await self._request([p.set_properties({tag: bytes([value])}, self.client.protocol)])
        self._apply({}, frames)
        await self.async_request_refresh()

    async def async_toggle_display(self) -> None:
        """Flip the indoor display."""
        frames = await self._request([p.toggle_display(self.client.protocol, beep=self.beep)])
        self._apply({"display": not self.data.get("display", True)}, frames)

    def _apply(self, changes: dict[str, Any], frames: list[bytes]) -> None:
        data = {**(self.data or {}), **changes, **self._parse(frames)}
        self.async_set_updated_data(data)
