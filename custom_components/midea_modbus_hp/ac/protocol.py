"""Midea air conditioner (0xAC) LAN protocol, V3 (8370) transport.

Framing and crypto follow midea-local (MIT, (c) 2021 George Zhao); message layouts are
confirmed against the vendor Lua codec T_0000_AC_24.
Each request opens a short session: TCP connect, handshake, send/receive, close.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from hashlib import md5, sha256
import os

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PORT = 6444
TIMEOUT = 5.0
REPLY_TIMEOUT = 3.0
LATE_REPLY_TIMEOUT = 0.8
SETTLE_DELAY = 1.0
DEVICE_TYPE = 0xAC

# LAN constants of the V2 packet layer (midea-local LocalSecurity).
_V2_KEY = bytes.fromhex(format(141661095494369103254425781617665632877, "x"))
_V2_SALT = bytes.fromhex(
    format(
        233912452794221312800602098970898185176935770387238278451789080441632479840061417076563,
        "x",
    )
)
_HANDSHAKE_REQUEST = 0x0
_HANDSHAKE_RESPONSE = 0x1
_ENCRYPTED_RESPONSE = 0x3
_ENCRYPTED_REQUEST = 0x6

MSG_SET = 0x02
MSG_QUERY = 0x03

# Classic mode values (C0 byte 2 >> 5, 0x40 set).
MODE_AUTO, MODE_COOL, MODE_DRY, MODE_HEAT, MODE_FAN = 1, 2, 3, 4, 5
FAN_AUTO = 102

# New-protocol property tags (B0 set / B1 query).
TAG_UD_ANGLE = 0x0009
TAG_LR_ANGLE = 0x000A
TAG_INDOOR_HUMIDITY = 0x0015
TAG_SELF_CLEAN = 0x0039
TAG_PREVENT_STRAIGHT_WIND = 0x0042


class MideaLanError(Exception):
    """Communication with the unit failed."""


# ---------------------------------------------------------------- checksums / crypto


def crc8(data: bytes) -> int:
    """CRC-8/MAXIM (Dallas), the body checksum of AC messages."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8C if crc & 1 else crc >> 1
    return crc


def _sum_checksum(data: bytes) -> int:
    return (~sum(data) + 1) & 0xFF


def _aes(key: bytes, mode: modes.Mode, data: bytes, *, encrypt: bool) -> bytes:
    cipher = Cipher(algorithms.AES(key), mode)
    op = cipher.encryptor() if encrypt else cipher.decryptor()
    return op.update(data) + op.finalize()


def _ecb_encrypt(data: bytes) -> bytes:
    padder = padding.PKCS7(128).padder()
    return _aes(_V2_KEY, modes.ECB(), padder.update(data) + padder.finalize(), encrypt=True)


def _ecb_decrypt(data: bytes) -> bytes:
    plain = _aes(_V2_KEY, modes.ECB(), data, encrypt=False)
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(plain) + unpadder.finalize()


# ---------------------------------------------------------------- AA frames


def build_frame(message_type: int, body: bytes, protocol: int = 0) -> bytes:
    """AA frame: 10-byte header, body, sum checksum."""
    header = bytes(
        [0xAA, min(10 + len(body), 0xFF), DEVICE_TYPE, 0, 0, 0, 0, 0, protocol, message_type]
    )
    frame = header + body
    return frame + bytes([_sum_checksum(frame[1:])])


class _Serial:
    value = 0

    @classmethod
    def next(cls) -> int:
        cls.value = cls.value % 254 + 1
        return cls.value


def _with_id_crc(body: bytes) -> bytes:
    body = body + bytes([_Serial.next()])
    return body + bytes([crc8(body)])


def query_status(protocol: int = 0) -> bytes:
    """0x41 status query, answered by C0."""
    body = bytearray(20)
    body[0], body[1], body[3] = 0x41, 0x81, 0xFF
    return build_frame(MSG_QUERY, _with_id_crc(bytes(body)), protocol)


def query_capabilities(protocol: int = 0, *, additional: bool = False) -> bytes:
    """B5 capability query (first or additional frame)."""
    body = bytes([0xB5, 0x01, 0x01, 0x01]) if additional else bytes([0xB5, 0x01, 0x00])
    return build_frame(MSG_QUERY, _with_id_crc(body), protocol)


def query_group(group: int, protocol: int = 0) -> bytes:
    """C1 group query: 1 = compressor/coils, 2 = indoor fan, 3 = outdoor fan, 4 = energy."""
    body = bytes([0x41, 0x21, 0x01, 0x40 | group, 0x00, 0x01])
    return build_frame(MSG_QUERY, body + bytes([crc8(body)]), protocol)


def query_properties(tags: list[int], protocol: int = 0) -> bytes:
    """B1 new-protocol property query."""
    body = bytearray([0xB1, len(tags)])
    for tag in tags:
        body += bytes([tag & 0xFF, tag >> 8])
    return build_frame(MSG_QUERY, _with_id_crc(bytes(body)), protocol)


def set_properties(values: dict[int, bytes], protocol: int = 0) -> bytes:
    """B0 new-protocol property set: [tag lo, tag hi, length, value...]."""
    body = bytearray([0xB0, len(values)])
    for tag, value in values.items():
        body += bytes([tag & 0xFF, tag >> 8, len(value)]) + value
    return build_frame(MSG_SET, _with_id_crc(bytes(body)), protocol)


def toggle_display(protocol: int = 0, *, beep: bool = False) -> bytes:
    """Display on/off toggle (there is no absolute display command)."""
    body = bytearray(20)
    body[0], body[1], body[3], body[4], body[6] = 0x41, 0x02 | (0x40 if beep else 0), 0xFF, 0x02, 0x02
    return build_frame(MSG_QUERY, _with_id_crc(bytes(body)), protocol)


def set_general(state: dict, protocol: int = 0, *, beep: bool = True) -> bytes:
    """0x40 set of the complete classic state (every field is written)."""
    temp = float(state["target_temperature"])
    body = bytearray(23)
    body[0] = 0x40
    body[1] = (0x01 if state["power"] else 0) | (0x40 if beep else 0)
    body[2] = ((state["mode"] << 5) & 0xE0) | (int(temp) & 0x0F) | (0x10 if round(temp * 2) % 2 else 0)
    body[3] = int(state["fan_speed"]) & 0x7F
    body[7] = 0x30 | (0x0C if state["swing_vertical"] else 0) | (0x03 if state["swing_horizontal"] else 0)
    body[8] = 0x20 if state["turbo"] else 0
    body[9] = (0x04 if state["dry"] else 0) | (0x80 if state["eco"] else 0) | (0x20 if state["anion"] else 0)
    body[10] = (0x01 if state["sleep"] else 0) | (0x02 if state["turbo"] else 0)
    body[17] = 0x40 if state["natural_wind"] else 0
    body[21] = 0x80 if state["frost_protect"] else 0
    return build_frame(MSG_SET, _with_id_crc(bytes(body)), protocol)


# ---------------------------------------------------------------- response parsing


def _temperature(integer: int, decimal: int) -> float | None:
    if integer == 0xFF:
        return None
    value = (integer - 50) / 2
    if decimal == 0:
        return value
    return int(value) - decimal * 0.1 if value < 0 else int(value) + decimal * 0.1


def parse_c0(body: bytes) -> dict:
    """C0 status (body[0] == 0xC0)."""
    return {
        "power": bool(body[1] & 0x01),
        "mode": (body[2] & 0xE0) >> 5,
        "target_temperature": (body[2] & 0x0F) + 16.0 + (0.5 if body[2] & 0x10 else 0.0),
        "fan_speed": body[3] & 0x7F,
        "swing_vertical": bool(body[7] & 0x0C),
        "swing_horizontal": bool(body[7] & 0x03),
        "turbo": bool(body[8] & 0x20) or bool(body[10] & 0x02),
        "dry": bool(body[9] & 0x04),
        "eco": bool(body[9] & 0x10),
        "anion": bool(body[9] & 0x20),
        "natural_wind": bool(body[9] & 0x02),
        "sleep": bool(body[10] & 0x01),
        "indoor_temperature": _temperature(body[11], body[15] & 0x0F),
        "outdoor_temperature": _temperature(body[12], body[15] >> 4),
        "filter_full": bool(body[13] & 0x20),
        "display": (body[14] & 0x70) != 0x70,
        "pmv": (body[14] & 0x0F) * 0.5 - 3.5,
        "frost_protect": len(body) > 21 and bool(body[21] & 0x80),
    }


def _bcd(data: bytes) -> int:
    value = 0
    for byte in data:
        value = value * 100 + (byte >> 4) * 10 + (byte & 0x0F)
    return value


def parse_c1(body: bytes) -> dict:
    """C1 group data (body[3] = 0x40 | group)."""
    group, d = body[3], body[4:]
    if group == 0x44:
        # BCD in Wh: hourly deltas reach ~1.4 kWh while cooling and 1-3 Wh in standby
        # (midea-local's 0.01 kWh reading gives up to 14 kWh per hour on a 3-room multi-split).
        return {"energy_total": _bcd(d[0:4]) / 1000, "power_watts": int.from_bytes(d[12:15], "big") / 10}
        # (not "power": that key is the on/off flag of the C0 status)
    if group == 0x41:
        return {
            "compressor_frequency": d[0],
            "compressor_target_frequency": d[1],
            "compressor_current": d[3],
            "compressor_voltage": d[4],
            "indoor_coil_temperature": (d[7] - 30) / 2,
            "outdoor_coil_temperature": (d[8] - 50) / 2,
            "outdoor_ambient_temperature": (d[9] - 50) / 2,
            "discharge_temperature": d[10],
        }
    if group == 0x42:
        return {"indoor_fan_speed": d[1] * 8}
    if group == 0x43:
        return {"outdoor_fan_speed": d[6] * 8}
    return {}


def parse_b5(body: bytes) -> dict[int, bytes]:
    """B5 capabilities: [count, (tag lo, tag hi, length, value...)...]."""
    caps: dict[int, bytes] = {}
    pos = 2
    for _ in range(body[1]):
        if pos + 3 > len(body):
            break
        tag, size = body[pos] | body[pos + 1] << 8, body[pos + 2]
        caps[tag] = bytes(body[pos + 3 : pos + 3 + size])
        pos += 3 + size
    return caps


def parse_b1(body: bytes) -> dict[int, bytes]:
    """B1 properties: [count, (tag lo, tag hi, result, length, value...)...]."""
    props: dict[int, bytes] = {}
    pos = 2
    for _ in range(body[1]):
        if pos + 4 > len(body):
            break
        tag, size = body[pos] | body[pos + 1] << 8, body[pos + 3]
        if body[pos + 2] == 0:
            props[tag] = bytes(body[pos + 4 : pos + 4 + size])
        pos += 4 + size
    return props


def body_of(frame: bytes) -> bytes:
    """Body of an AA frame (without header and checksum); body[0] is the body type."""
    return frame[10:-1]


# ---------------------------------------------------------------- V3 session


class AcLanClient:
    """One unit; every call runs in its own short authenticated session."""

    def __init__(self, host: str, device_id: int, token: str, key: str, port: int = PORT) -> None:
        """Initialize."""
        self.host, self.port, self.device_id = host, port, device_id
        self._token, self._key = bytes.fromhex(token), bytes.fromhex(key)
        self._tcp_key = b""
        self._request_count = 0
        self._buffer = b""
        self._lock = asyncio.Lock()
        self.protocol = 0  # message protocol version, learned from replies

    # ---- 8370 layer
    def _encode_8370(self, data: bytes, msgtype: int) -> bytes:
        encrypted = msgtype in (_ENCRYPTED_REQUEST, _ENCRYPTED_RESPONSE)
        size, pad = len(data), 0
        if encrypted:
            if (size + 2) % 16:
                pad = 16 - ((size + 2) & 0xF)
                data += os.urandom(pad)
            size += pad + 32
        header = bytes([0x83, 0x70]) + size.to_bytes(2, "big") + bytes([0x20, pad << 4 | msgtype])
        data = self._request_count.to_bytes(2, "big") + data
        self._request_count = (self._request_count + 1) % 0xFFFF
        if encrypted:
            sign = sha256(header + data).digest()
            data = _aes(self._tcp_key, modes.CBC(bytes(16)), data, encrypt=True) + sign
        return header + data

    def _decode_8370(self, buf: bytes) -> tuple[list[bytes], bytes]:
        packets = []
        while len(buf) >= 6:
            if buf[0:2] != b"\x83\x70":
                raise MideaLanError("not an 8370 packet")
            size = int.from_bytes(buf[2:4], "big") + 8
            if len(buf) < size:
                break
            header, data, buf = buf[:6], buf[6:size], buf[size:]
            pad, msgtype = header[5] >> 4, header[5] & 0xF
            if msgtype in (_ENCRYPTED_REQUEST, _ENCRYPTED_RESPONSE):
                sign = data[-32:]
                data = _aes(self._tcp_key, modes.CBC(bytes(16)), data[:-32], encrypt=False)
                if sha256(header + data).digest() != sign:
                    raise MideaLanError("8370 signature mismatch")
                if pad:
                    data = data[:-pad]
            packets.append(data[2:])
        return packets, buf

    # ---- 5A5A (V2) layer
    def _encode_v2(self, frame: bytes) -> bytes:
        stamp = datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S%f")[:16]
        packet = bytearray(40)
        packet[0:4] = b"\x5a\x5a\x01\x11"
        packet[6] = 0x20
        packet[12:20] = bytes(reversed([int(stamp[i : i + 2]) for i in range(0, 16, 2)]))
        packet[20:28] = self.device_id.to_bytes(8, "little")
        packet += _ecb_encrypt(frame)
        packet[4:6] = (len(packet) + 16).to_bytes(2, "little")
        return bytes(packet) + md5(bytes(packet) + _V2_SALT).digest()

    @staticmethod
    def _decode_v2(packet: bytes) -> bytes | None:
        if packet == b"ERROR" or len(packet) <= 56 or packet[2:4] in (b"\x01\x10", b"\x01\x00"):
            return None
        try:
            return _ecb_decrypt(packet[40:-16])
        except ValueError:
            return None

    # ---- session
    async def request(self, frames: list[bytes]) -> list[bytes]:
        """Send AA frames one by one, return every AA reply received (fewer on silence).

        Replies can lag behind their query, so callers match them by body type, not position.
        """
        async with self._lock:
            try:
                async with asyncio.timeout(TIMEOUT):
                    reader, writer = await asyncio.open_connection(self.host, self.port)
            except (OSError, TimeoutError) as err:
                raise MideaLanError(f"connect {self.host}: {err}") from err
            try:
                await self._handshake(reader, writer)
                replies: list[bytes] = []
                self._buffer = b""
                for frame in frames:
                    writer.write(self._encode_8370(self._encode_v2(frame), _ENCRYPTED_REQUEST))
                    await writer.drain()
                    # Stop waiting as soon as this frame's reply (or any frame) has arrived.
                    replies += await self._receive(reader, lambda got: len(got) >= 1, REPLY_TIMEOUT)
                replies += await self._receive(reader, lambda got: False, LATE_REPLY_TIMEOUT)
                return replies
            except (OSError, TimeoutError, asyncio.IncompleteReadError) as err:
                raise MideaLanError(f"{self.host}: {err!r}") from err
            finally:
                writer.close()

    async def _handshake(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._request_count = 0
        writer.write(self._encode_8370(self._token, _HANDSHAKE_REQUEST))
        await writer.drain()
        async with asyncio.timeout(TIMEOUT):
            header = await reader.readexactly(6)
            payload = await reader.readexactly(int.from_bytes(header[2:4], "big") + 2)
        if header[5] & 0xF != _HANDSHAKE_RESPONSE or len(payload) != 66:
            raise MideaLanError("authentication refused (token/key)")
        response = payload[2:]
        plain = _aes(self._key, modes.CBC(bytes(16)), response[:32], encrypt=False)
        if sha256(plain).digest() != response[32:]:
            raise MideaLanError("authentication signature mismatch (token/key)")
        self._tcp_key = bytes(a ^ b for a, b in zip(plain, self._key, strict=True))
        self._request_count = 0
        # The modules drop a frame that arrives right after the handshake (measured on Q1C/Q1D/Q1E).
        await asyncio.sleep(SETTLE_DELAY)

    async def _receive(self, reader: asyncio.StreamReader, done, timeout: float) -> list[bytes]:
        frames: list[bytes] = []
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while not done(frames):
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                chunk = await asyncio.wait_for(reader.read(1024), remaining)
            except TimeoutError:
                break
            if not chunk:
                break
            packets, self._buffer = self._decode_8370(self._buffer + chunk)
            for packet in packets:
                frame = self._decode_v2(packet)
                if frame and frame[0] == 0xAA and len(frame) > 11:
                    self.protocol = frame[8]
                    frames.append(frame)
        return frames
