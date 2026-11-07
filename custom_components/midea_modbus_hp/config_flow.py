"""Config flow: Modbus heat pump gateway, or a Wi-Fi air conditioner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import voluptuous as vol
from pymodbus.client import AsyncModbusTcpClient

import logging

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .ac import protocol as ac_protocol
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
from .appliance.catalog import DEVICE_TYPES
from .appliance.coordinator import DEFAULT_PORT as APPLIANCE_PORT, build_device

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE_ID = "device_id"
CONF_UNIT = "unit"
CONF_CLOUD = "cloud"
CONF_DEFAULT_ACCOUNT = "default_account"
CONF_TYPE = "type"
# Cloud names understood by midea-local (the app the unit is registered in).
CLOUDS = ("SmartHome", "NetHome Plus", "Midea Air", "Ariston Clima", "OS Comfort")
DEFAULT_CLOUD = "SmartHome"
# Token/key of units already paired by the Midea AC LAN integration (no cloud login needed here).
MIDEA_AC_LAN_STORAGE = ".storage/midea_ac_lan"


async def _can_read(host: str, port: int, device_id: int) -> bool:
    client = AsyncModbusTcpClient(host, port=port, timeout=5)
    try:
        if not await client.connect():
            return False
        result = await client.read_holding_registers(1, count=1, device_id=device_id)
        return not result.isError()
    except Exception:  # noqa: BLE001 - any failure means "cannot connect"
        return False
    finally:
        client.close()


def _paired_units(config_dir: str) -> dict[str, dict[str, Any]]:
    """Air conditioners (type 0xAC) known to Midea AC LAN, keyed by device id."""
    units = {}
    for path in sorted(Path(config_dir, MIDEA_AC_LAN_STORAGE).glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("type") == ac_protocol.DEVICE_TYPE and data.get("token") and data.get("key"):
            units[str(data["device_id"])] = data
    return units


class MideaModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._units: dict[str, dict[str, Any]] = {}
        self._found: dict[str, dict[str, Any]] = {}
        self._ips: dict[str, str] = {}
        self._cloud: Any = None
        self._located: dict[str, dict[str, Any]] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options (air conditioners only)."""
        return AcOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose what to add."""
        return self.async_show_menu(step_id="user", menu_options=["heat_pump", "air_conditioner", "appliance"])

    async def async_step_heat_pump(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the gateway address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input[CONF_DEVICE_ID]}"
            )
            self._abort_if_unique_id_configured()
            if await _can_read(
                user_input[CONF_HOST], user_input[CONF_PORT], user_input[CONF_DEVICE_ID]
            ):
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
            errors["base"] = "cannot_connect"
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): int,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            }
        )
        return self.async_show_form(step_id="heat_pump", data_schema=schema, errors=errors)

    def _configured_ac(self) -> set[str]:
        return {e.unique_id for e in self._async_current_entries() if e.unique_id}

    async def async_step_air_conditioner(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pair through the Midea cloud, or reuse a unit already paired by Midea AC LAN."""
        paired = await self.hass.async_add_executor_job(_paired_units, self.hass.config.config_dir)
        configured = self._configured_ac()
        self._units = {k: v for k, v in paired.items() if f"ac_{k}" not in configured}
        if self._units:
            return self.async_show_menu(step_id="air_conditioner", menu_options=["ac_cloud", "ac_lan"])
        return await self.async_step_ac_cloud()

    async def async_step_ac_cloud(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Sign in to the cloud of the app the unit is registered in."""
        errors: dict[str, str] = {}
        if user_input is not None:
            use_default, ok, appliances, cloud = await self._async_cloud_login(user_input, errors)
            if not errors:
                if not ok:
                    errors["base"] = "cloud_login_failed"
                else:
                    self._cloud = cloud
                    configured = self._configured_ac()
                    self._found = {
                        str(dev_id): dev
                        for dev_id, dev in appliances.items()
                        if dev.get("type") == ac_protocol.DEVICE_TYPE and f"ac_{dev_id}" not in configured
                    }
                    if not use_default and not self._found:
                        errors["base"] = "no_devices_found" if not appliances else "all_configured"
                    else:
                        await self._async_locate()
                        return await self.async_step_ac_select()
        return self.async_show_form(step_id="ac_cloud", data_schema=self._cloud_schema(), errors=errors)

    async def _async_cloud_login(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> tuple[bool, bool, dict[int, dict[str, Any]], Any]:
        """Sign in; returns (default account, signed in, appliances, cloud)."""
        from midealocal.cloud import get_midea_cloud, get_preset_account_cloud  # noqa: PLC0415

        use_default = bool(user_input.get(CONF_DEFAULT_ACCOUNT))
        if use_default:
            preset = get_preset_account_cloud()
            cloud_name, account, password = preset["cloud_name"], preset["username"], preset["password"]
        else:
            cloud_name = user_input[CONF_CLOUD]
            account = (user_input.get(CONF_USERNAME) or "").strip()
            password = user_input.get(CONF_PASSWORD) or ""
        if not use_default and not (account and password):
            errors["base"] = "missing_credentials"
            return use_default, False, {}, None
        cloud = None
        try:
            cloud = get_midea_cloud(cloud_name, async_get_clientsession(self.hass), account, password)
            ok = await cloud.login()
            appliances = {} if use_default or not ok else (await cloud.list_appliances(None) or {})
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Midea cloud login failed")
            ok, appliances = False, {}
        return use_default, ok, appliances, cloud

    @staticmethod
    def _cloud_schema() -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(CONF_CLOUD, default=DEFAULT_CLOUD): SelectSelector(
                    SelectSelectorConfig(options=list(CLOUDS))
                ),
                vol.Optional(CONF_USERNAME, default=""): str,
                vol.Optional(CONF_PASSWORD, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_DEFAULT_ACCOUNT, default=False): bool,
            }
        )

    # ---- other Midea appliances (midea-local)
    async def async_step_appliance(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Sign in to the cloud to list appliances and download their token/key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            use_default, ok, appliances, cloud = await self._async_cloud_login(user_input, errors)
            if not errors and not ok:
                errors["base"] = "cloud_login_failed"
            elif not errors:
                self._cloud = cloud
                configured = self._configured_ac()
                self._found = {
                    str(dev_id): dev
                    for dev_id, dev in appliances.items()
                    if dev.get("type") in DEVICE_TYPES and f"appliance_{dev_id}" not in configured
                }
                if not use_default and not self._found:
                    errors["base"] = "no_appliances_found" if not appliances else "all_configured"
                else:
                    from midealocal.discover import discover  # noqa: PLC0415

                    try:
                        found = await discover(list(DEVICE_TYPES))
                    except Exception:  # noqa: BLE001
                        found = {}
                    self._located = {str(k): v for k, v in found.items()}
                    return await self.async_step_appliance_select()
        return self.async_show_form(step_id="appliance", data_schema=self._cloud_schema(), errors=errors)

    async def async_step_appliance_select(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick the appliance (or type its id and type), its IP address and name; test the connection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = str(user_input.get(CONF_UNIT) or user_input.get(CONF_DEVICE_ID) or "").strip()
            host = (user_input.get(CONF_HOST) or "").strip()
            info = self._found.get(device_id, {})
            located = self._located.get(device_id, {})
            dev_type = info.get("type") or located.get("type") or int(user_input.get(CONF_TYPE) or "0", 16)
            if not device_id.isdigit() or not host or dev_type not in DEVICE_TYPES:
                errors["base"] = "missing_unit"
            else:
                await self.async_set_unique_id(f"appliance_{device_id}")
                self._abort_if_unique_id_configured()
                if data := await self._async_test_appliance(int(device_id), dev_type, host, info, located):
                    return self.async_create_entry(title=user_input[CONF_NAME], data=data)
                errors["base"] = "cannot_connect_appliance"
        fields: dict[Any, Any] = {}
        if self._found:
            options = [
                SelectOptionDict(
                    value=k,
                    label=f"{v.get('name') or k} ({DEVICE_TYPES[v['type']]}, 0x{v['type']:02X})",
                )
                for k, v in self._found.items()
            ]
            first = next(iter(self._found))
            fields[vol.Required(CONF_UNIT, default=first)] = SelectSelector(SelectSelectorConfig(options=options))
            default_host = self._located.get(first, {}).get("ip_address", "")
            default_name = self._found[first].get("name") or DEVICE_TYPES[self._found[first]["type"]]
        else:
            fields[vol.Required(CONF_DEVICE_ID)] = str
            fields[vol.Required(CONF_TYPE)] = SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=f"{t:02X}", label=f"0x{t:02X} {name}")
                        for t, name in DEVICE_TYPES.items()
                    ]
                )
            )
            default_host, default_name = "", "Midea"
        fields[vol.Required(CONF_HOST, default=default_host)] = str
        fields[vol.Required(CONF_NAME, default=default_name)] = str
        return self.async_show_form(
            step_id="appliance_select",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders={
                "found": ", ".join(
                    f"{k} → {v.get('ip_address')} (0x{v.get('type', 0):02X})" for k, v in self._located.items()
                ) or "–"
            },
        )

    async def _async_test_appliance(
        self, device_id: int, dev_type: int, host: str, info: dict[str, Any], located: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Try the token/key pairs from the cloud; return the entry data of the first that works."""
        protocol = int(located.get("protocol") or 3)
        methods: list[dict[str, str]] = [{"token": "", "key": ""}] if protocol != 3 else []
        if protocol == 3:
            try:
                methods = list((await self._cloud.get_cloud_keys(device_id)).values())
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Getting the token from the Midea cloud failed")
        subtype = info.get("model_number") or located.get("subtype") or 0
        model = info.get("model") or located.get("model") or ""
        for method in methods:
            data = {
                CONF_KIND: KIND_APPLIANCE,
                CONF_HOST: host,
                CONF_PORT: int(located.get("port") or APPLIANCE_PORT),
                "device_id": device_id,
                "type": dev_type,
                "protocol": protocol,
                "token": method.get("token", ""),
                "key": method.get("key", ""),
                "model": str(model or ""),
                "subtype": int(subtype) if str(subtype).isdigit() else 0,
            }
            device = build_device("test", data)
            try:
                if await device.connect(check_protocol=True):
                    return data
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Appliance %s did not accept the key", device_id, exc_info=True)
            finally:
                await device.close_socket()
        return None

    async def _async_locate(self) -> None:
        """Best effort: learn IP addresses by UDP discovery (many units do not answer it)."""
        from midealocal.discover import discover  # noqa: PLC0415

        try:
            found = await discover([ac_protocol.DEVICE_TYPE])
        except Exception:  # noqa: BLE001
            found = {}
        self._ips = {str(k): v["ip_address"] for k, v in found.items()}

    async def async_step_ac_select(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick the unit (or type its id), its IP address and name; then fetch and test the key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = str(user_input.get(CONF_UNIT) or user_input.get(CONF_DEVICE_ID) or "").strip()
            host = (user_input.get(CONF_HOST) or "").strip()
            if not device_id.isdigit() or not host:
                errors["base"] = "missing_unit"
            else:
                await self.async_set_unique_id(f"ac_{device_id}")
                self._abort_if_unique_id_configured()
                try:
                    keys = await self._cloud.get_cloud_keys(int(device_id))
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Getting the token from the Midea cloud failed")
                    keys = {}
                if not keys:
                    errors["base"] = "no_token"
                for method in keys.values():
                    client = ac_protocol.AcLanClient(host, int(device_id), method["token"], method["key"])
                    try:
                        replies = await client.request([ac_protocol.query_status()])
                    except ac_protocol.MideaLanError:
                        replies = []
                    if replies:
                        return self.async_create_entry(
                            title=user_input[CONF_NAME],
                            data={
                                CONF_KIND: KIND_AC,
                                CONF_HOST: host,
                                "device_id": int(device_id),
                                "token": method["token"],
                                "key": method["key"],
                                "model": self._found.get(device_id, {}).get("model", ""),
                                CONF_OUTDOOR_UNIT: user_input.get(CONF_OUTDOOR_UNIT, "").strip(),
                            },
                        )
                if keys:
                    errors["base"] = "cannot_connect_ac"
        fields: dict[Any, Any] = {}
        if self._found:
            options = [
                SelectOptionDict(value=k, label=f"{v.get('name') or k} ({v.get('model') or k})")
                for k, v in self._found.items()
            ]
            first = next(iter(self._found))
            fields[vol.Required(CONF_UNIT, default=first)] = SelectSelector(SelectSelectorConfig(options=options))
            default_host = self._ips.get(first, "")
            default_name = self._found[first].get("name") or "Air conditioner"
        else:
            fields[vol.Required(CONF_DEVICE_ID)] = str
            default_host, default_name = "", "Air conditioner"
        fields[vol.Required(CONF_HOST, default=default_host)] = str
        fields[vol.Required(CONF_NAME, default=default_name)] = str
        fields[vol.Optional(CONF_OUTDOOR_UNIT, default="")] = str
        return self.async_show_form(
            step_id="ac_select",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders={
                "found": ", ".join(f"{k} → {v}" for k, v in self._ips.items()) or "–"
            },
        )

    async def async_step_ac_lan(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick a unit paired by Midea AC LAN and name its outdoor unit."""
        errors: dict[str, str] = {}
        if not self._units:
            return self.async_abort(reason="no_air_conditioners")
        if user_input is not None:
            unit = self._units[user_input[CONF_UNIT]]
            await self.async_set_unique_id(f"ac_{unit['device_id']}")
            self._abort_if_unique_id_configured()
            client = ac_protocol.AcLanClient(unit["ip_address"], unit["device_id"], unit["token"], unit["key"])
            try:
                replies = await client.request([ac_protocol.query_status()])
            except ac_protocol.MideaLanError:
                replies = []
            if replies:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_KIND: KIND_AC,
                        CONF_HOST: unit["ip_address"],
                        "device_id": unit["device_id"],
                        "token": unit["token"],
                        "key": unit["key"],
                        "model": unit.get("model", ""),
                        CONF_OUTDOOR_UNIT: user_input.get(CONF_OUTDOOR_UNIT, "").strip(),
                    },
                )
            errors["base"] = "cannot_connect_ac"
        options = [
            SelectOptionDict(value=k, label=f"{v.get('name', k)} ({v['ip_address']}, {v.get('model', '')})")
            for k, v in self._units.items()
        ]
        first = next(iter(self._units.values()))
        schema = vol.Schema(
            {
                vol.Required(CONF_UNIT, default=next(iter(self._units))): SelectSelector(
                    SelectSelectorConfig(options=options)
                ),
                vol.Required(CONF_NAME, default=first.get("name", "Air conditioner")): str,
                vol.Optional(CONF_OUTDOOR_UNIT, default=""): str,
            }
        )
        return self.async_show_form(step_id="ac_lan", data_schema=schema, errors=errors)

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Create the heat pump or an air conditioner entry from configuration.yaml without asking."""
        if import_data.get(CONF_KIND) == KIND_AC:
            device_id = import_data[CONF_DEVICE_ID]
            await self.async_set_unique_id(f"ac_{device_id}")
            self._abort_if_unique_id_configured()
            paired = await self.hass.async_add_executor_job(_paired_units, self.hass.config.config_dir)
            if (unit := paired.get(str(device_id))) is None:
                return self.async_abort(reason="no_air_conditioners")
            return self.async_create_entry(
                title=import_data[CONF_NAME],
                data={
                    CONF_KIND: KIND_AC,
                    CONF_HOST: unit["ip_address"],
                    "device_id": device_id,
                    "token": unit["token"],
                    "key": unit["key"],
                    "model": unit.get("model", ""),
                    CONF_OUTDOOR_UNIT: import_data.get(CONF_OUTDOOR_UNIT, ""),
                },
            )
        await self.async_set_unique_id(
            f"{import_data[CONF_HOST]}:{import_data[CONF_PORT]}:{import_data[CONF_DEVICE_ID]}"
        )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=import_data[CONF_NAME], data=import_data)


class AcOptionsFlow(OptionsFlow):
    """Address and shared outdoor unit of an air conditioner."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Edit options."""
        entry = self.config_entry
        if entry.data.get(CONF_KIND) != KIND_AC:
            return self.async_abort(reason="not_supported")
        if user_input is not None:
            if user_input[CONF_HOST] != entry.data[CONF_HOST]:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_HOST: user_input[CONF_HOST]}
                )
            return self.async_create_entry(data={CONF_OUTDOOR_UNIT: user_input.get(CONF_OUTDOOR_UNIT, "").strip()})
        unit = entry.options.get(CONF_OUTDOOR_UNIT, entry.data.get(CONF_OUTDOOR_UNIT, ""))
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
                vol.Optional(CONF_OUTDOOR_UNIT, default=unit): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
