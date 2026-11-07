# Midea appliance protocol – derived from the MSmartHome Lua plug-ins

This document was produced for **midea_modbus_hp 1.2.0**. It describes what the official Midea device plug-ins (Lua, `T_0000_<type>_<…>.lua`) do with the bytes of the LAN/cloud protocol. The plug-ins themselves are Midea's code and are **not** part of this repository; only the observed behaviour is documented here.

## How the plug-ins were obtained

- The MSmartHome 3.20.0 APK does not contain the plug-ins (its code is packed; the app downloads them per device). They come from the cloud endpoint `POST /v2/luaEncryption/luaGet` of the MSmartHome (SmartHome, EU: `mp-eu-prod.appsmb.com`) cloud, called with the default account built into midea-local (`cloud.download_lua`). The request carries `applianceType`, the AES-encrypted serial number and the manufacturer code; the plug-in is chosen by the **SN8 model code** (serial characters 9–16).
- SN8 codes were taken from the scene templates bundled in the APK (e.g. `510003X9` water heater, `7300016F` range hood, `20200009` humidifier, `510VR0W0` robot vacuum, `560000AG` fan). With the generic code `00000000` the cloud returns a default plug-in for some types.
- The response contains a download URL; the file is AES-encrypted with a fixed key and decrypted by midea-local. The NetHome Plus cloud (`/v1/appliance/protocol/lua/luaGet`) only had 0xA1, 0xAC and 0xED.

## How they were simulated

Every plug-in was run in LuaJIT (lupa) in a sandbox: only `string`, `table`, `math`, `bit`, a JSON shim and `os.time` were available – no files, no network. The plug-in API is:

- `jsonToData(json)` – `{"deviceinfo":{…}, "query":{…}}` or `{"control":{…}, "status":{…}}` → frame as a hex string.
- `dataToJson(json)` – `{"deviceinfo":{…}, "msg":{"data":"<hex frame>"}}` → `{"status":{…}}`.

Frames: `AA len type 00 00 00 00 00 00 msgtype body… checksum`, `len` = frame length without `AA`, checksum = two's complement of the sum of bytes 1…n. Some types add a CRC-8/854 byte at the end of the body (`+crc`). Message types: `0x02` control, `0x03` query, `0x04`/`0x05` notifications.

Status maps were found by feeding synthetic responses and setting one body byte at a time to 0x01, 0x02 … 0x80, 0x19 and 0xFF. *Body byte 0* is the message header (`body` column of the frame table). Control maps compare `jsonToData` output with and without one changed property.

## Overview

| Type | Device | Plug-in | Query frame | Status response | Properties | Controls |
| --- | --- | --- | --- | --- | --- | --- |
| `0xA1` | Dehumidifier | `T_0000_A1_00000Q10_2023112201.lua` | `aa20a100000000000003418100ff000000000000000000000000000000005170ba` | msg 0x03 body 0x01 +crc | 19 | 20 |
| `0xAC` | Air Conditioner | `T_0000_AC_00000Q10_2024013001.lua` | `aa20ac00000000000003418100ff00000000000000000000000000000000b4a616` | msg 0x03 body 0xC0 | 35 | 38 |
| `0xB6` | Range Hood | `T_0000_B6_1.lua` | `aa0bb600000000000003310b` | msg 0x03 body 0x31 | 18 | 13 |
| `0xB8` | Robot Vacuum | `T_0000_B8_510VR0W0_2023050601.lua` | `aa0cb800000000000003320106` | msg 0x02 body 0x01 +crc | 65 | 0 |
| `0xCA` | Refrigerator | `T_0000_CA_21.lua` | `aa0bcac10000000000030067` | msg 0x03 body 0x00 | 132 | 52 |
| `0xCD` | Heat Pump Water Heater | `T_0000_CD_10.lua` | `aa0ccd00000000000003010122` | msg 0x03 body 0x02 | 97 | 42 |
| `0xDB` | Front Load Washer | `T_0000_DB_41.lua` | `aa0bdb000000000000030314` | msg 0x03 body 0x03 | 52 | 30 |
| `0xE1` | Dishwasher | `T_0000_E1_5.lua` | `aa0be1000000000000030011` | msg 0x03 body 0x00 | 45 | 38 |
| `0xE2` | Electric Water Heater | `T_0000_E2_24.lua` | `aa0ce20000000000000301010d` | msg 0x03 body 0x01 | 105 | 101 |
| `0xE3` | Gas Water Heater | `T_0000_E3_1.lua` | `aa1ee3000000000000030101000000000000000000000000000000000000fa` | msg 0x03 body 0x01 | 18 | 16 |
| `0xE6` | Gas Boilers | `T_0000_E6_9.lua` | `aa1ee6000000000000030101000000000000000000000000000000000000f7` | msg 0x03 body 0x01 | 68 | 53 |
| `0xED` | Water Drinking Appliance | `T_0000_ED_28.lua` | `aa0ced00000000000003010102` | msg 0x03 body 0x01 | 53 | 16 |
| `0xFA` | Fan | `T_0000_FA_560000AG_2022022802.lua` | `aa0afa00000000000003f9` | msg 0x03 body 0x01 | 51 | 19 |
| `0xFC` | Air Purifier | `T_0000_FC_20.lua` | `aa20fc00000000000003410000ff03000002000000000000000000000000466cea` | msg 0x03 body 0x01 | 33 | 26 |
| `0xFD` | Humidifier | `T_0000_FD_20200009_2023051801.lua` | `aa1ffd00000000000003418100ff03000002000000000000000000000000e13a` | msg 0x03 body 0xA0 | 27 | 19 |

No plug-in could be downloaded (the cloud needs a real SN8 of such a device) for: `0x13` Light, `0x26` Bathroom Master, `0x34` Sink Dishwasher, `0x40` Integrated Ceiling Fan, `0xAD` Air Detector, `0xB0` Microwave Oven, `0xB1` Electric Oven, `0xB3` Dish Sterilizer, `0xB4` Toaster, `0xBF` Microwave Steam Oven, `0xC2` Toilet, `0xC3` Heat Pump Wi-Fi Controller, `0xCC` MDV Wi-Fi Controller, `0xCE` Fresh Air Appliance, `0xCF` Heat Pump, `0xDA` Top Load Washer, `0xDC` Clothes Dryer, `0xE8` Electric Slow Cooker, `0xEA` Electric Rice Cooker, `0xEC` Electric Pressure Cooker, `0xFB` Electric Heater.

## 0xA1 Dehumidifier

Plug-in `T_0000_A1_00000Q10_2023112201.lua`. Query (`0x03`): `aa20a100000000000003418100ff000000000000000000000000000000005170ba`.

### Status – msg 0x03 body 0x01 +crc

| Property | Body byte → value | Default | In integration |
| --- | --- | --- | --- |
| `power` | 1.bit0 → "on" | "off" | yes |
| `mode` | 2: 0x01→"set", 0x02→"continuity", 0x04→"dry_clothes", 0x08→"fan" | null |  |
| `wind_speed` | 3: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `power_on_timer` | 4.bit7 → "on" | "off" |  |
| `power_on_time_value` | 4.bit7 → 15 | 0 |  |
| `power_off_timer` | 5.bit7 → "on" | "off" |  |
| `power_off_time_value` | 5.bit7 → 15 | 0 |  |
| `humidity` | 7.bit6/7 → 64 | 35 |  |
| `water_pump` | 9.bit3 → 1 | 0 |  |
| `water_pump_enable` | 9.bit4 → 1 | 0 |  |
| `anion` | 9.bit6 → "on" | "off" | yes |
| `filter_value` | 9.bit7 → "on" | "off" |  |
| `tank_status` | 10: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `water_full_time` | 13: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 14: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `water_full_level` | 15: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `cur_humidity` | 16: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `wind_swing_ud` | 19.bit5 → "on" | "off" |  |
| `error_code` | 21: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `purifier` | 23.bit0 → "on" | "off" |  |

Also reported (not driven by a single byte): `sub_type`, `version`

### Control

Base control frame: `aa21a100000000000002484200817f7f0023000000000000000000000000001c1ed6`

| Property | Test value | Changed body bytes (index: before→after) |
| --- | --- | --- |
| `humidity` | 36 | 7:23->24, 21:1c->03, 22:1e->69 |
| `tank_status` | 1 | 21:1c->07, 22:1e->a3 |
| `error_code` | 1 | 21:1c->19, 22:1e->21 |
| `cur_humidity` | 1 | 21:1c->41, 22:1e->38 |
| `wind_swing_ud` | "on" | 10:00->08, 21:1c->5d, 22:1e->6d |
| `power_on_timer` | "on" | 4:7f->80, 6:00->f0, 21:1c->0d, 22:1e->69 |
| `power_off_timer` | "on" | 5:7f->80, 6:00->0f, 21:1c->07, 22:1e->be |
| `power_off_time_value` | 1 | 21:1c->3d, 22:1e->63 |
| `power_on_time_value` | 1 | 21:1c->4e, 22:1e->79 |
| `water_full_level` | 1 | 13:00->01, 21:1c->5b, 22:1e->7f |
| `water_full_time` | 1 | 21:1c->24, 22:1e->62 |
| `anion` | "on" | 9:00->40, 21:1c->3e, 22:1e->9b |
| `filter_value` | "on" | 9:00->80, 21:1c->23, 22:1e->d5 |
| `water_pump` | 1 | 21:1c->05, 22:1e->1f |
| `water_pump_enable` | 1 | 21:1c->54, 22:1e->9a |
| `power` | "on" | 1:42->43, 21:1c->28, 22:1e->2b |
| `purifier` | "on" | 14:00->01, 21:1c->60, 22:1e->06 |
| `sub_type` | 3 | 21:1c->4d, 22:1e->9b |
| `version` | 19 | 21:1c->49, 22:1e->fa |
| `wind_speed` | 1 | 21:1c->57, 22:1e->78 |

## 0xAC Air Conditioner

Plug-in `T_0000_AC_00000Q10_2024013001.lua`. Query (`0x03`): `aa20ac00000000000003418100ff00000000000000000000000000000000b4a616`.

### Status – msg 0x03 body 0xC0

| Property | Body byte → value | Default | In integration |
| --- | --- | --- | --- |
| `power` | 1.bit0 → "on" | "off" |  |
| `temperature` | 2: 0x01→17, 0x02→18, 0x04→20, 0x08→24; 10.bit2 → 60; 13: 0x01→13, 0x02→14, 0x08→20, 0x10→28 | 16 |  |
| `small_temperature` | 2.bit4 → 0.5 | 0 |  |
| `mode` | 2.bit5/6/7 → "auto" | null |  |
| `wind_speed` | 3: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `power_on_timer` | 4.bit7 → "on" | "off" |  |
| `power_on_time_value` | 4.bit7 → 15 | 0 |  |
| `power_off_timer` | 5.bit7 → "on" | "off" |  |
| `power_off_time_value` | 5.bit7 → 15 | 0 |  |
| `wind_swing_lr` | 7: 0xFF→"on" | "off" |  |
| `wind_swing_ud` | 7: 0xFF→"on" | "off" |  |
| `wind_swing_lr_under` | 7: 0xFF→"on" | "off" |  |
| `power_saving` | 8.bit3 → "on" | "off" |  |
| `strong_wind` | 8.bit5 → "on" | "off" |  |
| `independent_ptc` | 8.bit6 → "on" | "off" |  |
| `natural_wind` | 9.bit1 → "on" | "off" |  |
| `dry` | 9.bit2 → "on" | "off" |  |
| `eco` | 9.bit4 → "on" | "off" |  |
| `purifier` | 9.bit5 → "on" | "off" |  |
| `sleep_status` | 10.bit0 → 1 | 0 |  |
| `tubro` | 10.bit1 → "on" | "off" |  |
| `temperature_unit` | 10.bit2 → 1 | 0 |  |
| `prevent_cold` | 10.bit5 → "on" | "off" |  |
| `indoor_temperature` | 11: 0x01→-24.5, 0x02→-24, 0x04→-23, 0x08→-21; 15: 0x01→-24.9, 0x02→-24.8, 0x04→-24.6, 0x08→-24.2 | -25 |  |
| `outdoor_temperature` | 12: 0x01→-24.5, 0x02→-24, 0x04→-23, 0x08→-21; 15: 0x10→-24.9, 0x20→-24.8, 0x40→-24.6, 0x80→-24.2 | -25 |  |
| `fresh_filter_timeout_ae2` | 13.bit5 → 1 | 0 |  |
| `fresh_filter_timeout` | 13.bit6 → 1 | 0 |  |
| `pmv` | 14: 0x01→-3, 0x02→-2.5, 0x04→-1.5, 0x08→0.5 | -3.5 |  |
| `screen_display_now` | 14: 0xFF→"off" | "on" |  |
| `error_code` | 16: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `degree8_heat` | 21.bit7 → 1 | 0 |  |
| `comfort_power_save` | 22.bit0 → "on" | "off" |  |
| `fresh_filter_time_total` | 24: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 25: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `fresh_filter_time_use` | 26: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 27: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `b5_next_frame` | 61: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |

Also reported (not driven by a single byte): `protocolType`, `version`, `comfort_sleep`, `ptc`

### Control

Base control frame: `aa24ac00000000000002404200817f7fff30000000000000000000000480000000005575b0`

| Property | Test value | Changed body bytes (index: before→after) |
| --- | --- | --- |
| `error_code` | 1 | (other frame layout) |
| `prevent_cold` | "on" | 10:00->08, 25:75->11 |
| `power_saving` | "on" | 8:00->08, 25:75->14 |
| `fresh_filter_time_total` | 1 | (other frame layout) |
| `fresh_filter_time_use` | 1 | (other frame layout) |
| `fresh_filter_timeout` | 1 | (other frame layout) |
| `fresh_filter_timeout_ae2` | 1 | (other frame layout) |
| `strong_wind` | "on" | 8:00->20, 25:75->e8 |
| `tubro` | "on" | 10:00->02, 25:75->6c |
| `power` | "on" | 1:42->43, 9:00->08, 25:75->dc |
| `purifier` | "on" | 9:00->20, 25:75->65 |
| `screen_display_now` | "on" | (other frame layout) |
| `sleep_status` | 1 | 10:00->01, 25:75->f5 |
| `comfort_power_save` | "on" | 22:00->01, 25:75->de |
| `temperature` | 17 | 2:00->01, 18:04->00, 25:75->13 |
| `protocolType` | 1 | (other frame layout) |
| `wind_speed` | 1 | (other frame layout) |
| `independent_ptc` | "on" | 22:00->08, 25:75->50 |
| `wind_swing_lr` | "on" | 7:30->33, 25:75->d3 |
| `degree8_heat` | 1 | 21:00->80, 25:75->ac |
| `wind_swing_ud` | "on" | 7:30->3c, 25:75->df |
| `b5_next_frame` | 1 | (other frame layout) |
| `version` | 52 | (other frame layout) |
| `indoor_temperature` | -24 | (other frame layout) |
| `power_on_timer` | "on" | 4:7f->80, 25:75->9d |
| `outdoor_temperature` | -24 | (other frame layout) |
| `power_off_timer` | "on" | 5:7f->80, 25:75->8c |
| `comfort_sleep` | "on" | 8:00->03, 9:00->40, 11:00->10, 12:00->11, 13:00->11, 14:00->11 |
| `power_off_time_value` | 1 | 6:ff->fe, 25:75->ac |
| `small_temperature` | 1 | 2:00->10, 25:75->84 |
| `power_on_time_value` | 1 | 6:ff->ef, 25:75->50 |
| `wind_swing_lr_under` | "on" | 20:00->80, 25:75->be |
| `eco` | "on" | 9:00->80, 25:75->35 |
| `natural_wind` | "on" | 17:00->40, 25:75->3c |
| `dry` | "on" | 9:00->04, 25:75->77 |
| `pmv` | -2.5 | 18:04->44, 25:75->b2 |
| `ptc` | "on" | 9:00->18, 25:75->79 |
| `temperature_unit` | 1 | 10:00->04, 25:75->47 |

## 0xB6 Range Hood

Plug-in `T_0000_B6_1.lua`. Query (`0x03`): `aa0bb600000000000003310b`.

### Status – msg 0x03 body 0x31

| Property | Body byte → value | Default | In integration |
| --- | --- | --- | --- |
| `light` | 1: 0x01→"on", 0x02→"on", 0x04→"on", 0x08→"on" | "off" | yes |
| `lightness` | 1: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | null |  |
| `work_status` | 2: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `work_status_desc` | 2.bit1 → "working" | "power_off" |  |
| `power` | 2.bit1 → "on" | "off" | yes |
| `gear` | 3: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `oilcup_position` | 5.bit1 → "1" | "0" |  |
| `error_type` | 5.bit2/7 → "tips"; 17: 0x01→"error", 0x02→"error", 0x04→"error", 0x08→"error" | "none" |  |
| `error_eq` | 5.bit2/7 → "robam"; 17: 0x01→"robam", 0x02→"robam", 0x04→"robam", 0x08→"robam" | "none" |  |
| `hotclean_tips` | 5.bit2 → "1" | "0" |  |
| `is_error` | 5.bit7 → "1" | "0" |  |
| `ir` | 13.bit0 → "on" | "off" |  |
| `speak` | 13.bit1 → "on" | "off" |  |
| `gesture` | 13.bit2 → "on" | "off" |  |
| `linkage` | 13.bit3 → "on" | "off" |  |
| `smoke_detector` | 13.bit4 → "on" | "off" |  |
| `error_code` | 17: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `volume` | 32: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |

Also reported (not driven by a single byte): `version`, `electronic_control_version`

### Control

Base control frame: `aa14b6000000000000022201ffffffffffffffff19`

| Property | Test value | Changed body bytes (index: before→after) |
| --- | --- | --- |
| `work_status` | 1 | (other frame layout) |
| `version` | 2 | (other frame layout) |
| `volume` | 1 | (other frame layout) |
| `electronic_control_version` | 1 | (other frame layout) |
| `error_code` | 1 | (other frame layout) |
| `light` | "on" | 2:ff->1a |
| `power` | "on" | 3:ff->02, 4:ff->02 |
| `ir` | "on" | 5:ff->03 |
| `speak` | "on" | 5:ff->05 |
| `gesture` | "on" | 5:ff->07 |
| `linkage` | "on" | 5:ff->09 |
| `smoke_detector` | "on" | 5:ff->0b |
| `gear` | 1 | 3:ff->02, 4:ff->01 |

## 0xB8 Robot Vacuum

Plug-in `T_0000_B8_510VR0W0_2023050601.lua`. Query (`0x03`): `aa0cb800000000000003320106`.

### Status – msg 0x02 body 0x01 +crc

| Property | Body byte → value | Default | In integration |
| --- | --- | --- | --- |
| `11` | 1: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `74` | 1: 0x01→141, 0x02→189, 0x04→221, 0x08→29; 2: 0x01→20, 0x02→150, 0x04→139, 0x08→177; 3: 0x01→96, 0x02→126, 0x04→66, 0x08→58 … | 157 |  |
| `75` | 1: 0x01→108, 0x02→59, 0x04→25, 0x08→213; 2: 0x01→229, 0x02→98, 0x04→107, 0x08→65; 3: 0x01→153, 0x02→122, 0x04→180, 0x08→184 … | 93 |  |
| `12` | 2: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `13` | 3: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `14` | 4: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `15` | 5: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `16` | 6: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `17` | 7: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `18` | 8: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `19` | 9: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `20` | 10: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `21` | 11: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `22` | 12: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `23` | 13: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `24` | 14: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `25` | 15: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `26` | 16: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `27` | 17: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `28` | 18: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `29` | 19: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `30` | 20: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `31` | 21: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `32` | 22: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `33` | 23: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `34` | 24: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `35` | 25: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `36` | 26: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `37` | 27: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `38` | 28: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `39` | 29: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `40` | 30: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `41` | 31: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `42` | 32: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `43` | 33: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `44` | 34: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `45` | 35: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `46` | 36: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `47` | 37: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `48` | 38: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `49` | 39: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `50` | 40: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `51` | 41: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `52` | 42: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `53` | 43: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `54` | 44: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `55` | 45: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `56` | 46: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `57` | 47: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `58` | 48: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `59` | 49: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `60` | 50: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `61` | 51: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `62` | 52: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `63` | 53: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `64` | 54: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `65` | 55: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `66` | 56: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `67` | 57: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `68` | 58: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `69` | 59: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `70` | 60: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `71` | 61: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `72` | 62: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `73` | 63: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |

Also reported (not driven by a single byte): `0`, `1`, `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, `10`

## 0xCA Refrigerator

Plug-in `T_0000_CA_21.lua`. Query (`0x03`): `aa0bcac10000000000030067`.

### Status – msg 0x03 body 0x00

| Property | Body byte → value | Default | In integration |
| --- | --- | --- | --- |
| `storage_mode` | 1.bit0 → "on" | "off" |  |
| `freezing_mode` | 1.bit1 → "on" | "off" |  |
| `intelligent_mode` | 1.bit2 → "on" | "off" |  |
| `energy_saving_mode` | 1.bit3 → "on" | "off" |  |
| `holiday_mode` | 1.bit4 → "on" | "off" |  |
| `moisturize_mode` | 1.bit5 → "on" | "off" |  |
| `preservation_mode` | 1.bit6 → "on" | "off" |  |
| `acme_freezing_mode` | 1.bit7 → "on" | "off" |  |
| `storage_temperature` | 2: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `freezing_temperature` | 2: 0x10→"-13", 0x20→"-14", 0x40→"-16", 0x80→"-20" | "-12" |  |
| `left_flexzone_temperature` | 3: 0x01→"-18", 0x02→"-17", 0x04→"-15", 0x08→"-11" | "0" |  |
| `right_flexzone_temperature` | 4: 0x01→"-18", 0x02→"-17", 0x04→"-15", 0x08→"-11" | "-19" |  |
| `variable_mode` | 5: 0x01→"soft_freezing_mode", 0x02→"zero_fresh_mode", 0x04→"fresh_product_mode", 0x08→"freeze_mode" | "none_mode" | yes |
| `storage_power` | 6.bit0 → "off" | "on" |  |
| `left_flexzone_power` | 6.bit2 → "off" | "on" |  |
| `right_flexzone_power` | 6.bit3 → "off" | "on" |  |
| `freezing_power` | 6.bit4 → "off" | "on" |  |
| `cross_peak_electricity_enter` | 6.bit5 → "enter" | "quit" |  |
| `cross_peak_electricity` | 6.bit6 → "on" | "off" |  |
| `all_refrigeration_power` | 6.bit7 → "on" | "off" |  |
| `remove_dew_power` | 7.bit0 → "on" | "off" |  |
| `humidify_power` | 7.bit1 → "on" | "off" |  |
| `unfreeze_power` | 7.bit2 → "on" | "off" |  |
| `temperature_unit` | 7.bit3 → "fahrenheit" | "celsius" |  |
| `floodlight_power` | 7.bit4 → "on" | "off" |  |
| `icea_bar_function_switch` | 7.bit6/7 → "refrigeration" | "default" |  |
| `radar_mode_power` | 8.bit0 → "on" | "off" |  |
| `milk_mode_power` | 8.bit1 → "on" | "off" |  |
| `icea_mode_power` | 8.bit2 → "on" | "off" |  |
| `plasma_aseptic_mode_power` | 8.bit3 → "on" | "off" |  |
| `acquire_icea_mode_power` | 8.bit4 → "on" | "off" |  |
| `brash_icea_mode_power` | 8.bit5 → "on" | "off" |  |
| `acquire_water_mode_power` | 8.bit6 → "on" | "off" |  |
| `freezing_ice_machine_power` | 8.bit7 → "on" | "off" |  |
| `freeze_fahrenheit_level` | 9: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `refrigeration_fahrenheit_level` | 10: 0x04→"4", 0x08→"8", 0x10→"16", 0x20→"32" | "0" |  |
| `leach_expire_day` | 11: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `power_consumption_low` | 12: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `power_consumption_high` | 13: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `freezing_motor_reset_status` | 14.bit0 → "valid" | "invalid" |  |
| `freezing_motor_deicing_status` | 14.bit1 → "valid" | "invalid" |  |
| `freezing_ice_machine_water_status` | 14.bit2 → "valid" | "invalid" |  |
| `freezing_all_ice_status` | 14.bit3 → "valid" | "invalid" |  |
| `human_induction_status` | 14.bit4 → "valid" | "invalid" |  |
| `storage_door_state` | 15.bit0 → "on" | "off" |  |
| `freezer_door_state` | 15.bit1 → "on" | "off" |  |
| `bar_door_state` | 15.bit2 → "on" | "off" |  |
| `ice_mouth_power` | 15.bit3 → "on" | "off" |  |
| `flexzone_door_state` | 15.bit4 → "on" | "off" |  |
| `storage_ice_home_door_state` | 15.bit5 → "on" | "off" |  |
| `is_error` | 16.bit0 → "yes" | "no" |  |
| `interval_room_humidity_level` | 16: 0x02→"2", 0x04→"4", 0x08→"8", 0x10→"16" | "0" |  |
| `refrigeration_real_temperature` | 17: 0x02→"-49", 0x04→"-48", 0x08→"-46", 0x10→"-42" | "-50" |  |
| `freezing_real_temperature` | 18: 0x02→"-49", 0x04→"-48", 0x08→"-46", 0x10→"-42" | "-50" |  |
| `left_variable_real_temperature` | 19: 0x02→"-49", 0x04→"-48", 0x08→"-46", 0x10→"-42" | "-50" |  |
| `right_variable_real_temperature` | 20: 0x02→"-49", 0x04→"-48", 0x08→"-46", 0x10→"-42" | "-50" |  |
| `fast_cold_minute` | 21: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8"; 22: 0x01→"256", 0x02→"512", 0x04→"1024", 0x08→"2048" | "0" |  |
| `fast_freeze_minute` | 23: 0x01→"256", 0x02→"512", 0x04→"1024", 0x08→"2048"; 24: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `food_site` | 25.bit0 → "right_freezing_room" | "left_freezing_room" |  |
| `beef` | 25.bit6 → "exist" | "nonexistence" |  |
| `pork` | 25.bit7 → "exist" | "nonexistence" |  |
| `mutton` | 26.bit0 → "exist" | "nonexistence" |  |
| `chicken` | 26.bit1 → "exist" | "nonexistence" |  |
| `duck_meat` | 26.bit2 → "exist" | "nonexistence" |  |
| `fish` | 26.bit3 → "exist" | "nonexistence" |  |
| `shrimp` | 26.bit4 → "exist" | "nonexistence" |  |
| `dumplings` | 26.bit5 → "exist" | "nonexistence" |  |
| `gluepudding` | 26.bit6 → "exist" | "nonexistence" |  |
| `ice_cream` | 26.bit7 → "exist" | "nonexistence" |  |
| `microcrystal_fresh` | 27.bit0 → "on" | "off" | yes |
| `dry_zone` | 27.bit1 → "on" | "off" |  |
| `electronic_smell` | 27.bit2 → "on" | "off" | yes |
| `eradicate_pesticide_residue` | 27.bit3 → "on" | "off" |  |
| `humidity` | 27.bit4/5 → "high" | null | yes |
| `performance_mode` | 27.bit7 → "on" | "off" |  |
| `normal_zone_level` | 28: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `function_zone_level` | 29: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `humidify_setting` | 30: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `smart_humidify` | 30.bit7 → "on" | "off" |  |
| `storage_left_door_auto` | 31.bit0/1 → "on" | "invalid" |  |
| `storage_right_door_auto` | 31.bit2/3 → "on" | "invalid" |  |
| `freezer_door_auto` | 31.bit4/5 → "on" | "invalid" |  |
| `freezer_door_auto_control` | 31.bit6 → "on" | "off" |  |
| `storage_door_auto_control` | 31.bit7 → "on" | "off" |  |
| `eradicate_pesticide_residue_progress` | 32: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `eradicate_pesticide_residue_completion` | 32.bit7 → "yes" | "no" |  |
| `storage_ice_machine_power` | 33.bit0 → "on" | "off" |  |
| `storage_ice_machine_water_status` | 33.bit3 → "valid" | "invalid" |  |
| `storage_all_ice_status` | 33.bit4 → "valid" | "invalid" |  |
| `filter_expires_mild_warning` | 33.bit5 → "valid" | "invalid" |  |
| `filter_expires_severe_warning` | 33.bit6 → "valid" | "invalid" |  |
| `ice_room_real_temperature` | 34: 0x02→"-49", 0x04→"-48", 0x08→"-46", 0x10→"-42" | "-50" |  |
| `storage_F_temperature` | 35: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `freezing_F_temperature` | 36: 0x01→"10", 0x02→"9", 0x04→"7", 0x08→"3" | "11" |  |
| `left_flexzone_F_temperature` | 37: 0x01→"0", 0x02→"1", 0x04→"3", 0x08→"7" | "-1" |  |
| `electronic_clean_strong` | 38.bit0 → "on" | "off" |  |
| `electronic_clean_timeout` | 38: 0x02→"1", 0x04→"2", 0x08→"4", 0x10→"8" | "0" |  |
| `quick_beverage_time` | 39: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `quick_beverage` | 39.bit7 → "on" | "off" |  |
| `aquatic_product` | 40.bit0 → "on" | "off" |  |
| `blue_ray_mode` | 40.bit1 → "on" | "off" |  |
| `silent_night_mode` | 40.bit2 → "on" | "off" |  |
| `storage_light_level` | 42: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `night_mode` | 42.bit5 → "on" | "off" |  |
| `quick_beverage_completed` | 42.bit6 → "yes" | "no" |  |
| `quick_beverage_continuing` | 42.bit7 → "yes" | "no" |  |
| `voice_door_auto` | 43.bit0 → "on" | "off" |  |
| `touch_door_auto` | 43.bit1 → "on" | "off" |  |
| `help_door_auto` | 43.bit2 → "on" | "off" |  |
| `speed_door_open` | 43.bit3 → "fast" | "slow" |  |
| `angle_door_open` | 43: 0x10→"90", 0x20→"110", 0x19→"90", 0xFF→"135" | null |  |
| `voice_assistant` | 43.bit6 → "on" | "off" |  |
| `no_action_door_close` | 43.bit7 → "on" | "off" |  |
| `filter_natural_time_high` | 45: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `filter_natural_time_low` | 46: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `beverage_vial_number` | 47: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `beverage_mid_number` | 48: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `beverage_big_number` | 49: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `beverage_quick_time` | 50: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `local_time_hour` | 51: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `local_time_minute` | 52: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `local_time_second` | 53: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `time_zone` | 54: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week` | 55: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `day` | 56: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `month` | 57: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `year` | 58: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `e_cleaning_percentage` | 59: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `drink_valve_equal_open_high` | 60: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `drink_valve_equal_open_low` | 61: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `inlet_valve_equal_open_high` | 62: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `inlet_valve_equal_open_low` | 63: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |

Also reported (not driven by a single byte): `storage_motor_reset_status`, `storage_motor_deicing_status`, `filter_element_use_percentage`, `ice_maker_times_high`, `ice_maker_times_low`, `version`

### Control

Base control frame: `aa47ca8d000000000002000000130b0000000000000000000000000000000000000000000000010101000000000a000b00000000000000000000000000000000000000000000002a`

| Property | Test value | Changed body bytes (index: before→after) |
| --- | --- | --- |
| `storage_door_state` | "on" | (other frame layout) |
| `freezer_door_state` | "on" | (other frame layout) |
| `flexzone_door_state` | "on" | (other frame layout) |
| `storage_ice_home_door_state` | "on" | (other frame layout) |
| `bar_door_state` | "on" | (other frame layout) |
| `ice_mouth_power` | "on" | (other frame layout) |
| `blue_ray_mode` | "on" | (other frame layout) |
| `storage_mode` | "on" | 1:00->01 |
| `freezing_mode` | "on" | 1:00->02 |
| `intelligent_mode` | "on" | 1:00->04 |
| `energy_saving_mode` | "on" | 1:00->08 |
| `holiday_mode` | "on" | 1:00->10 |
| `moisturize_mode` | "on" | 1:00->20 |
| `preservation_mode` | "on" | 1:00->40 |
| `acme_freezing_mode` | "on" | 1:00->80 |
| `storage_power` | "on" | (other frame layout) |
| `left_flexzone_power` | "on" | (other frame layout) |
| `right_flexzone_power` | "on" | (other frame layout) |
| `freezing_power` | "on" | (other frame layout) |
| `cross_peak_electricity` | "on" | 6:00->40 |
| `all_refrigeration_power` | "on" | 6:00->80 |
| `remove_dew_power` | "on" | 7:00->01 |
| `humidify_power` | "on" | 7:00->02 |
| `unfreeze_power` | "on" | 7:00->04 |
| `floodlight_power` | "on" | 7:00->10 |
| `radar_mode_power` | "on" | 8:00->01 |
| `milk_mode_power` | "on" | 8:00->02 |
| `icea_mode_power` | "on" | 8:00->04 |
| `acquire_water_mode_power` | "on" | 8:00->40 |
| `freezing_ice_machine_power` | "on" | 8:00->80 |
| `microcrystal_fresh` | "on" | 27:00->01 |
| `dry_zone` | "on" | 27:00->02 |
| `electronic_smell` | "on" | 27:00->04 |
| `eradicate_pesticide_residue` | "on" | 27:00->08 |
| `performance_mode` | "on" | 27:00->80 |
| `smart_humidify` | "on" | 30:01->81 |
| `freezer_door_auto_control` | "on" | 31:00->40 |
| `storage_door_auto_control` | "on" | 31:00->80 |
| `storage_ice_machine_power` | "on" | 33:00->01 |
| `electronic_clean_strong` | "on" | 38:00->01 |
| `quick_beverage` | "on" | 39:00->80 |
| `aquatic_product` | "on" | 40:00->01 |
| `silent_night_mode` | "on" | 40:00->04 |
| `night_mode` | "on" | 42:00->20 |
| `voice_door_auto` | "on" | 43:00->01 |
| `touch_door_auto` | "on" | 43:00->02 |
| `help_door_auto` | "on" | 43:00->04 |
| `voice_assistant` | "on" | 43:00->40 |
| `no_action_door_close` | "on" | 43:00->80 |
| `brash_icea_mode_power` | "on" | 8:00->20 |
| `acquire_icea_mode_power` | "on" | 8:00->10 |
| `plasma_aseptic_mode_power` | "on" | 8:00->08 |

## 0xCD Heat Pump Water Heater

Plug-in `T_0000_CD_10.lua`. Query (`0x03`): `aa0ccd00000000000003010122`.

### Status – msg 0x03 body 0x02

| Property | Body byte → value | Default | In integration |
| --- | --- | --- | --- |
| `week0timer1_effect` | 2.bit0 → "on" | "off" |  |
| `week0timer2_effect` | 2.bit1 → "on" | "off" |  |
| `week0timer3_effect` | 2.bit2 → "on" | "off" |  |
| `week0timer4_effect` | 2.bit3 → "on" | "off" |  |
| `week0timer5_effect` | 2.bit4 → "on" | "off" |  |
| `week0timer6_effect` | 2.bit5 → "on" | "off" |  |
| `week1timer1_effect` | 3.bit0 → "on" | "off" |  |
| `week1timer2_effect` | 3.bit1 → "on" | "off" |  |
| `week1timer3_effect` | 3.bit2 → "on" | "off" |  |
| `week1timer4_effect` | 3.bit3 → "on" | "off" |  |
| `week1timer5_effect` | 3.bit4 → "on" | "off" |  |
| `week1timer6_effect` | 3.bit5 → "on" | "off" |  |
| `week2timer1_effect` | 4.bit0 → "on" | "off" |  |
| `week2timer2_effect` | 4.bit1 → "on" | "off" |  |
| `week2timer3_effect` | 4.bit2 → "on" | "off" |  |
| `week2timer4_effect` | 4.bit3 → "on" | "off" |  |
| `week2timer5_effect` | 4.bit4 → "on" | "off" |  |
| `week2timer6_effect` | 4.bit5 → "on" | "off" |  |
| `week3timer1_effect` | 5.bit0 → "on" | "off" |  |
| `week3timer2_effect` | 5.bit1 → "on" | "off" |  |
| `week3timer3_effect` | 5.bit2 → "on" | "off" |  |
| `week3timer4_effect` | 5.bit3 → "on" | "off" |  |
| `week3timer5_effect` | 5.bit4 → "on" | "off" |  |
| `week3timer6_effect` | 5.bit5 → "on" | "off" |  |
| `week4timer1_effect` | 6.bit0 → "on" | "off" |  |
| `week4timer2_effect` | 6.bit1 → "on" | "off" |  |
| `week4timer3_effect` | 6.bit2 → "on" | "off" |  |
| `week4timer4_effect` | 6.bit3 → "on" | "off" |  |
| `week4timer5_effect` | 6.bit4 → "on" | "off" |  |
| `week4timer6_effect` | 6.bit5 → "on" | "off" |  |
| `week5timer1_effect` | 7.bit0 → "on" | "off" |  |
| `week5timer2_effect` | 7.bit1 → "on" | "off" |  |
| `week5timer3_effect` | 7.bit2 → "on" | "off" |  |
| `week5timer4_effect` | 7.bit3 → "on" | "off" |  |
| `week5timer5_effect` | 7.bit4 → "on" | "off" |  |
| `week5timer6_effect` | 7.bit5 → "on" | "off" |  |
| `week6timer1_effect` | 8.bit0 → "on" | "off" |  |
| `week6timer2_effect` | 8.bit1 → "on" | "off" |  |
| `week6timer3_effect` | 8.bit2 → "on" | "off" |  |
| `week6timer4_effect` | 8.bit3 → "on" | "off" |  |
| `week6timer5_effect` | 8.bit4 → "on" | "off" |  |
| `week6timer6_effect` | 8.bit5 → "on" | "off" |  |
| `week0timer1_opentime` | 9: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer1_closetime` | 10: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer1_set_temperature` | 11: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer1_modevalue` | 12.bit0/1/2 → "energy" | null |  |
| `week0timer2_opentime` | 13: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer2_closetime` | 14: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer2_set_temperature` | 15: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer2_modevalue` | 16.bit0/1/2 → "energy" | null |  |
| `week0timer3_opentime` | 17: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer3_closetime` | 18: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer3_set_temperature` | 19: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer3_modevalue` | 20.bit0/1/2 → "energy" | null |  |
| `week0timer4_opentime` | 21: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer4_closetime` | 22: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer4_set_temperature` | 23: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer4_modevalue` | 24.bit0/1/2 → "energy" | null |  |
| `week0timer5_opentime` | 25: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer5_closetime` | 26: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer5_set_temperature` | 27: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer5_modevalue` | 28.bit0/1/2 → "energy" | null |  |
| `week0timer6_opentime` | 29: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer6_closetime` | 30: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer6_set_temperature` | 31: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week0timer6_modevalue` | 32.bit0/1/2 → "energy" | null |  |
| `week1timer1_opentime` | 33: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer1_closetime` | 34: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer1_set_temperature` | 35: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer1_modevalue` | 36.bit0/1/2 → "energy" | null |  |
| `week1timer2_opentime` | 37: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer2_closetime` | 38: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer2_set_temperature` | 39: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer2_modevalue` | 40.bit0/1/2 → "energy" | null |  |
| `week1timer3_opentime` | 41: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer3_closetime` | 42: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer3_set_temperature` | 43: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer3_modevalue` | 44.bit0/1/2 → "energy" | null |  |
| `week1timer4_opentime` | 45: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer4_closetime` | 46: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer4_set_temperature` | 47: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer4_modevalue` | 48.bit0/1/2 → "energy" | null |  |
| `week1timer5_opentime` | 49: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer5_closetime` | 50: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer5_set_temperature` | 51: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer5_modevalue` | 52.bit0/1/2 → "energy" | null |  |
| `week1timer6_opentime` | 53: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer6_closetime` | 54: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer6_set_temperature` | 55: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week1timer6_modevalue` | 56.bit0/1/2 → "energy" | null |  |
| `week2timer1_opentime` | 57: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week2timer1_closetime` | 58: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week2timer1_set_temperature` | 59: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week2timer1_modevalue` | 60.bit0/1/2 → "energy" | null |  |
| `week2timer2_opentime` | 61: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week2timer2_closetime` | 62: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `week2timer2_set_temperature` | 63: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |

Also reported (not driven by a single byte): `week3timer2_closetime`, `week3timer2_set_temperature`, `week3timer3_opentime`, `week3timer3_closetime`, `week3timer3_set_temperature`, `week3timer4_opentime`, `week3timer4_closetime`, `week3timer4_set_temperature`, `week3timer5_opentime`, `week3timer5_closetime`, `week3timer5_set_temperature`, `week3timer6_opentime`, `week3timer6_closetime`, `week3timer6_set_temperature`, `week4timer1_opentime`, `week4timer1_closetime`, `week4timer1_set_temperature`, `week4timer2_opentime`, `week4timer2_closetime`, `week4timer2_set_temperature`, `week4timer3_opentime`, `week4timer3_closetime`, `week4timer3_set_temperature`, `week4timer4_opentime`, `week4timer4_closetime`, `week4timer4_set_temperature`, `week4timer5_opentime`, `week4timer5_closetime`, `week4timer5_set_temperature`, `week4timer6_opentime`, `week4timer6_closetime`, `week4timer6_set_temperature`, `week5timer1_opentime`, `week5timer1_closetime`, `week5timer1_set_temperature`, `week5timer2_opentime`, `week5timer2_closetime`, `week5timer2_set_temperature`, `week5timer3_opentime`, `week5timer3_closetime` …

### Control

Base control frame: `aa20cd00000000000002010100000000000000000000000000000000000000000f`

| Property | Test value | Changed body bytes (index: before→after) |
| --- | --- | --- |
| `week0timer1_effect` | "on" | (other frame layout) |
| `week0timer2_effect` | "on" | (other frame layout) |
| `week0timer3_effect` | "on" | (other frame layout) |
| `week0timer4_effect` | "on" | (other frame layout) |
| `week0timer5_effect` | "on" | (other frame layout) |
| `week0timer6_effect` | "on" | (other frame layout) |
| `week1timer1_effect` | "on" | (other frame layout) |
| `week1timer2_effect` | "on" | (other frame layout) |
| `week1timer3_effect` | "on" | (other frame layout) |
| `week1timer4_effect` | "on" | (other frame layout) |
| `week1timer5_effect` | "on" | (other frame layout) |
| `week1timer6_effect` | "on" | (other frame layout) |
| `week2timer1_effect` | "on" | (other frame layout) |
| `week2timer2_effect` | "on" | (other frame layout) |
| `week2timer3_effect` | "on" | (other frame layout) |
| `week2timer4_effect` | "on" | (other frame layout) |
| `week2timer5_effect` | "on" | (other frame layout) |
| `week2timer6_effect` | "on" | (other frame layout) |
| `week3timer1_effect` | "on" | (other frame layout) |
| `week3timer2_effect` | "on" | (other frame layout) |
| `week3timer3_effect` | "on" | (other frame layout) |
| `week3timer4_effect` | "on" | (other frame layout) |
| `week3timer5_effect` | "on" | (other frame layout) |
| `week3timer6_effect` | "on" | (other frame layout) |
| `week4timer1_effect` | "on" | (other frame layout) |
| `week4timer2_effect` | "on" | (other frame layout) |
| `week4timer3_effect` | "on" | (other frame layout) |
| `week4timer4_effect` | "on" | (other frame layout) |
| `week4timer5_effect` | "on" | (other frame layout) |
| `week4timer6_effect` | "on" | (other frame layout) |
| `week5timer1_effect` | "on" | (other frame layout) |
| `week5timer2_effect` | "on" | (other frame layout) |
| `week5timer3_effect` | "on" | (other frame layout) |
| `week5timer4_effect` | "on" | (other frame layout) |
| `week5timer5_effect` | "on" | (other frame layout) |
| `week5timer6_effect` | "on" | (other frame layout) |
| `week6timer1_effect` | "on" | (other frame layout) |
| `week6timer2_effect` | "on" | (other frame layout) |
| `week6timer3_effect` | "on" | (other frame layout) |
| `week6timer4_effect` | "on" | (other frame layout) |
| `week6timer5_effect` | "on" | (other frame layout) |
| `week6timer6_effect` | "on" | (other frame layout) |

## 0xDB Front Load Washer

Plug-in `T_0000_DB_41.lua`. Query (`0x03`): `aa0bdb000000000000030314`.

### Status – msg 0x03 body 0x03

| Property | Body byte → value | Default | In integration |
| --- | --- | --- | --- |
| `power` | 1.bit0 → "on" | "off" | yes |
| `running_status` | 2.bit0/1/2 → "standby" | "idle" |  |
| `mode` | 3.bit0/1 → "factory_test" | "normal" | yes |
| `program` | 4: 0x01→"eco", 0x02→"fast_wash", 0x04→"fiber", 0x08→"sport_clothes" | "cotton" | yes |
| `water_level` | 5: 0x01→"low", 0x02→"mid", 0x04→"4", 0x08→"8" | "0" | yes |
| `dryer` | 6: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" |  |
| `soak_count` | 6: 0x10→"1", 0x20→"2", 0x40→"4", 0x19→"1" | "0" |  |
| `temperature` | 7: 0x01→"0", 0x02→"20", 0x04→"40", 0x08→"90" | null | yes |
| `dehydration_speed` | 8: 0x01→"400", 0x02→"600", 0x04→"1000", 0x08→"1300" | "0" | yes |
| `wash_time` | 9: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 | yes |
| `dehydration_time` | 10: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 | yes |
| `detergent` | 11: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" | yes |
| `softener` | 12: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" | yes |
| `memory` | 13.bit0 → "on" | "off" |  |
| `appointment` | 13.bit1 → "on" | "off" |  |
| `spray_wash` | 13.bit2 → "on" | "off" |  |
| `speedy` | 13.bit3 → "on" | "off" |  |
| `old_speedy` | 13.bit3 → "on" | "off" |  |
| `nightly` | 13.bit4 → "on" | "off" |  |
| `lock` | 13.bit5 → "on" | "off" |  |
| `down_light` | 13.bit6 → "on" | "off" |  |
| `easy_ironing` | 13.bit7 → "on" | "off" |  |
| `appointment_time` | 14: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 15: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `progress` | 16: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 | yes |
| `remain_time` | 17: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 18: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `expert_step` | 19: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `project_no` | 21: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 22: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `error_code` | 24: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `beforehand_wash` | 25.bit0 → "on" | "off" |  |
| `super_clean_wash` | 25.bit1 → "on" | "off" |  |
| `intelligent_wash` | 25.bit2 → "on" | "off" |  |
| `strong_wash` | 25.bit3 → "on" | "off" |  |
| `steam_wash` | 25.bit4 → "on" | "off" |  |
| `fast_clean_wash` | 25.bit5 → "on" | "off" |  |
| `disinfectant` | 25.bit6 → "1" | "0" |  |
| `active_oxygen` | 25.bit7 → "1" | "0" |  |
| `stains` | 26: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" | yes |
| `wash_time_value` | 27: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 | yes |
| `dehydration_time_value` | 28: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 | yes |
| `soak` | 29.bit0 → "on" | "off" |  |
| `add_rinse` | 29.bit2 → "1" | "0" |  |
| `ultraviolet_lamp` | 29.bit3 → "1" | "0" |  |
| `eye_wash` | 29.bit4 → "1" | "0" |  |
| `microbubble` | 29.bit5 → "1" | "0" |  |
| `wind_dispel` | 29.bit6 → "1" | "0" |  |
| `hy_pro` | 29.bit7 → "1" | "0" |  |
| `dirty_degree` | 30: 0x01→"1", 0x02→"2", 0x04→"4", 0x08→"8" | "0" | yes |
| `ai_flag` | 31.bit0 → "on" | "off" |  |
| `water_plus` | 31.bit1 → "1" | "0" |  |
| `remote_control_flag` | 31.bit2 → "1" | "0" |  |
| `silent` | 31.bit3 → "1" | "0" |  |
| `favorite_memory` | 35: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |

Also reported (not driven by a single byte): `data_type`, `version`

### Control

Base control frame: `aa20db0000000000000202ffffffffffffffffffffffff00ffff00ffffffff3fd4`

| Property | Test value | Changed body bytes (index: before→after) |
| --- | --- | --- |
| `strong_wash` | "on" | 16:00->08 |
| `steam_wash` | "on" | 16:00->10 |
| `power` | "on" | 1:ff->01, 13:00->ff, 16:00->ff, 21:3f->ff |
| `soak` | "on" | 16:00->40 |
| `wash_time_value` | 1 | (other frame layout) |
| `dehydration_time_value` | 1 | (other frame layout) |
| `memory` | "on" | 13:00->01 |
| `project_no` | 1 | (other frame layout) |
| `remain_time` | 1 | (other frame layout) |
| `error_code` | 1 | (other frame layout) |
| `expert_step` | 1 | (other frame layout) |
| `favorite_memory` | 1 | (other frame layout) |
| `fast_clean_wash` | "on" | 16:00->20 |
| `intelligent_wash` | "on" | 16:00->04 |
| `super_clean_wash` | "on" | 16:00->02 |
| `progress` | 1 | (other frame layout) |
| `ai_flag` | "on" | (other frame layout) |
| `speedy` | "on" | 19:ff->f7 |
| `wash_time` | 1 | 9:ff->01 |
| `dehydration_time` | 1 | 10:ff->01 |
| `appointment` | "on" | 13:00->02, 14:ff->00, 15:ff->00 |
| `spray_wash` | "on" | 13:00->04 |
| `old_speedy` | "on" | 13:00->08 |
| `nightly` | "on" | 13:00->10 |
| `lock` | "on" | 13:00->20 |
| `down_light` | "on" | 13:00->40 |
| `easy_ironing` | "on" | 13:00->80 |
| `beforehand_wash` | "on" | 16:00->01 |
| `version` | 42 | (other frame layout) |
| `appointment_time` | 1 | (other frame layout) |

## 0xE1 Dishwasher

Plug-in `T_0000_E1_5.lua`. Query (`0x03`): `aa0be1000000000000030011`.

### Status – msg 0x03 body 0x00

| Property | Body byte → value | Default | In integration |
| --- | --- | --- | --- |
| `work_status` | 1.bit0/1/2 → "cancel" | "power_off" |  |
| `cmd` | 1: 0x01→"aa4ae10000000000000300010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000d1", 0x02→"aa4ae10000000000000300020000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000d0", 0x04→"aa4ae10000000000000300040000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000ce", 0x08→"aa4ae10000000000000300080000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000ca"; 2: 0x01→"aa4ae10000000000000300000100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000d1", 0x02→"aa4ae10000000000000300000200000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000d0", 0x04→"aa4ae10000000000000300000400000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000ce", 0x08→"aa4ae10000000000000300000800000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000ca"; 3: 0x01→"aa4ae10000000000000300000001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000d1", 0x02→"aa4ae10000000000000300000002000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000d0", 0x04→"aa4ae10000000000000300000004000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000ce", 0x08→"aa4ae10000000000000300000008000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000ca" … | "aa4ae10000000000000300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000d2" |  |
| `order_left_hour` | 1.bit1 → 0 | null |  |
| `order_left_min` | 1.bit1 → 0 | null |  |
| `order_set_hour` | 1.bit1 → 0 | null |  |
| `order_set_min` | 1.bit1 → 0 | null |  |
| `operator` | 1.bit1 → "pause"; 5.bit3 → "start" | "" |  |
| `mode` | 2: 0x01→"auto", 0x02→"intensive", 0x04→"eco", 0x08→"soak" | "null" | yes |
| `additional` | 3: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `dry_step_switch` | 4.bit0 → 0 | 1 |  |
| `uvswitch` | 4.bit1 → 1 | 0 |  |
| `waterswitch` | 4.bit2 → 1 | 0 | yes |
| `diy_flag` | 4.bit3 → 1 | 0 |  |
| `dryswitch` | 4: 0x10→1, 0x20→2, 0x19→1, 0xFF→2 | 0 |  |
| `door_auto_open` | 4.bit6 → 1 | 0 |  |
| `doorswitch` | 5.bit0 → 1 | 0 |  |
| `bright_lack` | 5.bit1 → 1 | 0 |  |
| `softwater_lack` | 5.bit2 → 1 | 0 |  |
| `lock` | 5.bit4 → "on" | "off" |  |
| `airswitch` | 5.bit5 → 1 | 0 |  |
| `air_status` | 5.bit6 → 1 | 0 |  |
| `water_lack` | 5.bit7 → 1 | 0 | yes |
| `left_time` | 6: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 32: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `wash_stage` | 9: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `error_code` | 10: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 | yes |
| `temperature` | 11: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 | yes |
| `softwater` | 13: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 | yes |
| `wrong_operation` | 16: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 | yes |
| `air_set_hour` | 17: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `air_left_hour` | 18: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `diy_times` | 19: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `diy_main_wash` | 21: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `diy_piao_wash` | 23: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `bright` | 24: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 | yes |
| `device_version` | 28: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `water_level` | 30: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `water_strong_level` | 31: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `humidity` | 33: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 | yes |
| `dry_set_min` | 34: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `wash_region` | 35: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `ota_version` | 36: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `ion_level` | 42: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `ion_time_hour` | 43: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `ion_time_min` | 44: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `ion_status` | 45: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |

Also reported (not driven by a single byte): `msg_type`, `version`

### Control

Base control frame: `aa30e1000000000000020800000000000000000000000000000000000000000000000000000000000000000000000000e5`

| Property | Test value | Changed body bytes (index: before→after) |
| --- | --- | --- |
| `bright` | 1 | 0:08->84, 1:00->01 |
| `airswitch` | 1 | 0:08->81, 4:00->01, 5:00->ff, 6:00->ff, 7:00->ff, 8:00->ff |
| `dryswitch` | 1 | 0:08->81, 4:00->ff, 5:00->ff, 6:00->ff, 7:00->ff, 8:00->ff |
| `dry_set_min` | 1 | 0:08->81, 4:00->ff, 5:00->ff, 6:00->ff, 7:00->ff, 8:00->ff |
| `waterswitch` | 1 | 0:08->81, 4:00->ff, 5:00->ff, 6:00->ff, 7:00->ff, 8:00->01 |
| `msg_type` | 4 | (other frame layout) |
| `dry_step_switch` | 2 | 0:08->81, 4:00->ff, 5:00->ff, 6:00->02, 7:00->ff, 8:00->ff |
| `air_set_hour` | 1 | 0:08->86, 1:00->01 |
| `bright_lack` | 1 | (other frame layout) |
| `diy_piao_wash` | 1 | (other frame layout) |
| `softwater_lack` | 1 | (other frame layout) |
| `diy_flag` | 1 | (other frame layout) |
| `left_time` | 1 | (other frame layout) |
| `wash_stage` | 1 | (other frame layout) |
| `error_code` | 1 | (other frame layout) |
| `temperature` | 1 | (other frame layout) |
| `wrong_operation` | 1 | (other frame layout) |
| `air_status` | 1 | (other frame layout) |
| `air_left_hour` | 1 | (other frame layout) |
| `doorswitch` | 1 | (other frame layout) |
| `water_lack` | 1 | (other frame layout) |
| `humidity` | 1 | (other frame layout) |
| `ota_version` | 1 | (other frame layout) |
| `ion_level` | 1 | (other frame layout) |
| `version` | 2 | (other frame layout) |
| `ion_time_min` | 1 | (other frame layout) |
| `ion_status` | 1 | (other frame layout) |
| `ion_time_hour` | 1 | (other frame layout) |
| `diy_main_wash` | 1 | (other frame layout) |
| `uvswitch` | 1 | 0:08->81, 4:00->ff, 5:00->ff, 6:00->ff, 7:00->01, 8:00->ff |
| `softwater` | 1 | 0:08->80, 1:00->01 |
| `device_version` | 1 | (other frame layout) |
| `additional` | 1 | 3:00->01 |
| `wash_region` | 1 | 4:00->01 |
| `door_auto_open` | 1 | 13:00->01 |
| `lock` | "on" | 0:08->83, 1:00->03 |
| `water_level` | 1 | 11:00->01 |
| `water_strong_level` | 1 | 12:00->01 |

## 0xE2 Electric Water Heater

Plug-in `T_0000_E2_24.lua`. Query (`0x03`): `aa0ce20000000000000301010d`.

### Status – msg 0x03 body 0x01

| Property | Body byte → value | Default | In integration |
| --- | --- | --- | --- |
| `power` | 2.bit0 → "on" | "off" | yes |
| `fast_hot_power` | 2.bit1 → "on" | "off" |  |
| `hot_power` | 2.bit2 → "on" | "off" |  |
| `warm_power` | 2.bit3 → "on" | "off" |  |
| `water_flow` | 2.bit4 → "on" | "off" |  |
| `negative_ions` | 2.bit5 → "on" | "off" |  |
| `sterilization` | 2.bit6 → "on" | "off" | yes |
| `mode` | 2.bit6 → "sterilization"; 7: 0x01→"eplus", 0x02→"fast_wash", 0x10→"summer", 0x20→"winter"; 8: 0x01→"one_person", 0x02→"two_person", 0x04→"old_man", 0x20→"cloud" … | "none" |  |
| `frequency_hot` | 2.bit7 → "on" | "off" |  |
| `error_code` | 3: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `cur_temperature` | 4: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `heat_water_level` | 5: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `flow` | 6: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `eplus` | 7.bit0 → "on" | "off" |  |
| `fast_wash` | 7.bit1 → "on" | "off" |  |
| `heat` | 7: 0x04→"half", 0x08→"whole", 0x19→"whole", 0xFF→"whole" | "none" |  |
| `half_heat` | 7.bit2 → "on" | "off" |  |
| `whole_heat` | 7.bit3 → "on" | "off" |  |
| `summer` | 7.bit4 → "on" | "off" |  |
| `winter` | 7.bit5 → "on" | "off" |  |
| `efficient` | 7.bit6 → "on" | "off" |  |
| `night` | 7.bit7 → "on" | "off" |  |
| `bath_person` | 8: 0x01→"one_person", 0x02→"two_person", 0x04→"old_man", 0x19→"one_person" | "off" |  |
| `screen_off` | 8.bit3 → "on" | "off" |  |
| `sleep` | 8.bit4 → "on" | "off" |  |
| `cloud` | 8.bit5 → "on" | "off" |  |
| `appoint_wash` | 8.bit6 → "on" | "off" |  |
| `now_wash` | 8.bit7 → "on" | "off" |  |
| `end_time_hour` | 9: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `end_time_minute` | 10: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `temperature` | 11: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `get_time` | 12.bit0 → "on" | "off" |  |
| `get_temp` | 12.bit1 → "on" | "off" |  |
| `func_select` | 12.bit2 → "middle" | "low" |  |
| `type_select` | 12.bit4 → "valve" | "normal" |  |
| `smart_sterilize` | 12.bit5 → "on" | "off" |  |
| `sterilize_high_temp` | 12.bit6 → "on" | "off" |  |
| `uv_sterilize` | 12.bit7 → "on" | "off" |  |
| `discharge_status` | 13: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `top_temp` | 14: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 | yes |
| `bottom_heat` | 15.bit0 → "on" | "off" |  |
| `top_heat` | 15.bit1 → "on" | "off" |  |
| `show_h` | 15.bit2 → "on" | "off" |  |
| `need_discharge` | 15.bit3 → "on" | "off" |  |
| `machine` | 15.bit4 → "empty_machine" | "real_machine" |  |
| `elec_warning` | 15.bit5 → "on" | "off" |  |
| `bottom_temp` | 15.bit6 → "on" | "off" |  |
| `water_cyclic` | 15.bit7 → "on" | "off" |  |
| `water_system` | 16: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `discharge_left_time` | 17: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `in_temperature` | 18: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `mg_remain` | 19: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `waterday_lowbyte` | 20: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `waterday_highbyte` | 21: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `tech_water` | 22.bit0 → "on" | "off" |  |
| `protect` | 22.bit1 → "on" | "off" |  |
| `safe` | 22.bit2 → "on" | "off" |  |
| `protect_show` | 22.bit3 → "on" | "off" |  |
| `appoint_power` | 22.bit4 → "on" | "off" |  |
| `music` | 22.bit5 → "on" | "off" |  |
| `ti_protect` | 22.bit6 → "on" | "off" |  |
| `scroll_hot` | 22.bit7 → "on" | "off" |  |
| `wash_with_temp` | 23.bit0 → "on" | "off" |  |
| `wash` | 23.bit0 → "on" | "off" |  |
| `shower` | 23.bit1 → "on" | "off" |  |
| `bath` | 23.bit2 → "on" | "off" |  |
| `memory` | 23.bit3 → "on" | "off" | yes |
| `midea_manager` | 23.bit4 → "on" | "off" |  |
| `big_water` | 23.bit5 → "on" | "off" |  |
| `ali_manager` | 23.bit6 → "on" | "off" |  |
| `cloud_appoint` | 23.bit7 → "on" | "off" |  |
| `passwater_lowbyte` | 24: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `passwater_highbyte` | 25: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `water_quality` | 26: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `volume` | 27: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `rate` | 28: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `t_hot` | 29.bit0 → "on" | "off" |  |
| `clean` | 29.bit1 → "on" | "off" |  |
| `scene` | 29.bit2 → "on" | "off" |  |
| `auto_off` | 29.bit3 → "on" | "off" |  |
| `ele_exception` | 29.bit4 → "on" | "off" |  |
| `mom_wash` | 29.bit5 → "on" | "off" |  |
| `dad_wash` | 29.bit6 → "on" | "off" |  |
| `baby_wash` | 29.bit7 → "on" | "off" |  |
| `scene_id` | 30: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `wash_temperature` | 31: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `grea` | 32: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `sensor_error` | 33.bit0 → "on" | "off" |  |
| `limit_error` | 33.bit1 → "on" | "off" |  |
| `single_wash` | 33.bit2 → "on" | "off" |  |
| `people_wash` | 33.bit3 → "on" | "off" |  |
| `one_egg` | 33.bit4 → "on" | "off" |  |
| `two_egg` | 33.bit5 → "on" | "off" |  |
| `always_fell` | 33.bit6 → "on" | "off" |  |
| `communication_error` | 33.bit7 → "on" | "off" |  |
| `cur_rate` | 34: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `sterilize_left_days` | 35: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `sterilize_cycle_index` | 36: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `uv_sterilize_minute` | 37: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `uv_sterilize_second` | 38: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `sound_dad` | 39.bit0 → "on" | "off" |  |
| `screen_light` | 39: 0x02→2, 0x04→4, 0x08→8, 0x10→16 | 0 |  |
| `door_status` | 40.bit0 → "on" | "off" |  |
| `morning_night_bash` | 40.bit1/2 → 1 | 0 |  |
| `tds_value` | 41: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |

Also reported (not driven by a single byte): `version`

### Control

Base control frame: `aa11e20000000000000214000000000000f7`

| Property | Test value | Changed body bytes (index: before→after) |
| --- | --- | --- |
| `whole_heat` | "on" | 1:00->04, 2:00->02 |
| `temperature` | 1 | 1:00->07, 2:00->01 |
| `sterilization` | "on" | 1:00->0d, 2:00->01 |
| `frequency_hot` | "on" | 1:00->10, 2:00->01 |
| `scene` | "on" | 1:00->13, 2:00->01 |
| `scene_id` | 1 | 1:00->13, 3:00->01 |
| `sterilize_high_temp` | "on" | (other frame layout) |
| `discharge_status` | 1 | (other frame layout) |
| `top_temp` | 1 | (other frame layout) |
| `sleep` | "on" | 1:00->0e, 2:00->01 |
| `top_heat` | "on" | (other frame layout) |
| `show_h` | "on" | (other frame layout) |
| `negative_ions` | "on" | 1:00->0c, 2:00->01 |
| `screen_off` | "on" | 1:00->0f, 2:00->01 |
| `t_hot` | "on" | 1:00->12, 2:00->01 |
| `elec_warning` | "on" | (other frame layout) |
| `bottom_temp` | "on" | (other frame layout) |
| `water_cyclic` | "on" | (other frame layout) |
| `wash_with_temp` | "on" | 1:00->18, 2:00->01 |
| `discharge_left_time` | 1 | (other frame layout) |
| `in_temperature` | 1 | (other frame layout) |
| `mg_remain` | 1 | (other frame layout) |
| `waterday_lowbyte` | 1 | (other frame layout) |
| `waterday_highbyte` | 1 | (other frame layout) |
| `tech_water` | "on" | (other frame layout) |
| `protect_show` | "on" | (other frame layout) |
| `appoint_power` | "on" | (other frame layout) |
| `music` | "on" | (other frame layout) |
| `ti_protect` | "on" | (other frame layout) |
| `scroll_hot` | "on" | (other frame layout) |
| `midea_manager` | "on" | (other frame layout) |
| `ali_manager` | "on" | (other frame layout) |
| `cloud_appoint` | "on" | (other frame layout) |
| `passwater_lowbyte` | 1 | (other frame layout) |
| `passwater_highbyte` | 1 | (other frame layout) |
| `water_quality` | 1 | (other frame layout) |
| `volume` | 1 | (other frame layout) |
| `rate` | 1 | (other frame layout) |
| `ele_exception` | "on" | (other frame layout) |
| `sensor_error` | "on" | (other frame layout) |
| `door_status` | "on" | (other frame layout) |
| `tds_value` | 1 | (other frame layout) |
| `version` | 25 | (other frame layout) |
| `bottom_heat` | "on" | (other frame layout) |
| `need_discharge` | "on" | (other frame layout) |
| `uv_sterilize_second` | 1 | (other frame layout) |
| `uv_sterilize_minute` | 1 | (other frame layout) |
| `water_system` | 1 | (other frame layout) |
| `sterilize_left_days` | 1 | (other frame layout) |
| `cur_rate` | 1 | (other frame layout) |
| `communication_error` | "on" | (other frame layout) |
| `shower` | "on" | (other frame layout) |
| `bath` | "on" | (other frame layout) |
| `memory` | "on" | (other frame layout) |
| `people_wash` | "on" | 1:00->18, 2:00->04 |
| `single_wash` | "on" | 1:00->18, 2:00->02 |
| `limit_error` | "on" | (other frame layout) |
| `grea` | 1 | 1:00->10, 3:00->01 |
| `wash_temperature` | 1 | 1:00->16, 2:00->01 |
| `baby_wash` | "on" | 1:00->17, 2:00->01 |
| `dad_wash` | "on" | 1:00->17, 2:00->02 |
| `mom_wash` | "on" | 1:00->17, 2:00->04 |
| `auto_off` | "on" | 1:00->14, 2:00->01 |
| `clean` | "on" | 1:00->0b, 2:00->01 |
| `big_water` | "on" | 1:00->11, 2:00->01 |
| `one_egg` | "on" | 1:00->19, 2:00->01 |
| `two_egg` | "on" | 1:00->19, 2:00->02 |
| `always_fell` | "on" | 1:00->1a, 2:00->01 |
| `smart_sterilize` | "on" | 1:00->1b, 2:00->01 |
| `end_time_minute` | 1 | (other frame layout) |
| `sterilize_cycle_index` | 1 | 1:00->1b, 4:00->01 |
| `protect` | "on" | 1:00->05, 2:00->01 |
| `uv_sterilize` | "on" | 1:00->1d, 2:00->01 |
| `sound_dad` | "on" | 1:00->1e, 2:00->03, 3:00->01 |
| `screen_light` | 1 | 1:00->1f, 2:00->01 |
| `morning_night_bash` | 1 | 1:00->21, 2:00->01 |
| `get_temp` | "on" | (other frame layout) |
| `safe` | "on" | 1:00->06, 2:00->01 |
| `get_time` | "on" | (other frame layout) |
| `power` | "on" | (other frame layout) |
| `cloud` | "on" | (other frame layout) |
| `hot_power` | "on" | (other frame layout) |
| `eplus` | "on" | (other frame layout) |
| `fast_wash` | "on" | (other frame layout) |
| `summer` | "on" | (other frame layout) |
| `winter` | "on" | (other frame layout) |
| `efficient` | "on" | (other frame layout) |
| `night` | "on" | (other frame layout) |
| `bath_person` | "on" | (other frame layout) |
| `fast_hot_power` | "on" | (other frame layout) |
| `wash` | "on" | (other frame layout) |
| `warm_power` | "on" | (other frame layout) |
| `water_flow` | "on" | (other frame layout) |
| `error_code` | 1 | (other frame layout) |
| `cur_temperature` | 1 | (other frame layout) |
| `heat_water_level` | 1 | (other frame layout) |
| `flow` | 1 | (other frame layout) |
| `appoint_wash` | "on" | (other frame layout) |
| `now_wash` | "on" | (other frame layout) |
| `end_time_hour` | 1 | (other frame layout) |
| `half_heat` | "on" | 1:00->04, 2:00->01 |

## 0xE3 Gas Water Heater

Plug-in `T_0000_E3_1.lua`. Query (`0x03`): `aa1ee3000000000000030101000000000000000000000000000000000000fa`.

### Status – msg 0x03 body 0x01

| Property | Body byte → value | Default | In integration |
| --- | --- | --- | --- |
| `power` | 2.bit0 → "on" | "off" | yes |
| `feedback` | 2.bit1 → "on" | "off" |  |
| `fan` | 2.bit2 → "on" | "off" |  |
| `error_code` | 3: 0x01→"E0", 0x02→"E1", 0x04→"E3", 0x08→"E8" | "none" |  |
| `in_water_tem` | 4: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `out_water_tem` | 5: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `environment_tem` | 6: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `temperature` | 7: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `water_volume` | 8: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 9: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `fire_capacity` | 11: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `mode` | 12.bit0/1 → "kitchen" | "shower" |  |
| `person_mode_two` | 12.bit2 → "on" | "off" |  |
| `person_tem_one` | 13: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `person_tem_two` | 14: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `person_tem_three` | 15: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `wind_speed` | 16: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 17: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `lowest_temp` | 18: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `hightest_temp` | 19: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |

Also reported (not driven by a single byte): `cloud_intelligence`, `person_mode_three`, `person_mode_one`, `version`

### Control

Base control frame: `aa1ee3000000000000020400000000000000000000000000000000000000f9`

| Property | Test value | Changed body bytes (index: before→after) |
| --- | --- | --- |
| `wind_speed` | 1 | (other frame layout) |
| `person_tem_two` | 1 | (other frame layout) |
| `hightest_temp` | 1 | (other frame layout) |
| `person_tem_three` | 1 | (other frame layout) |
| `temperature` | 1 | 1:00->02, 2:00->01 |
| `version` | 2 | (other frame layout) |
| `person_tem_one` | 1 | (other frame layout) |
| `power` | "on" | 0:04->01, 1:00->01 |
| `feedback` | "on" | (other frame layout) |
| `fan` | "on" | (other frame layout) |
| `lowest_temp` | 1 | (other frame layout) |
| `in_water_tem` | 1 | (other frame layout) |
| `out_water_tem` | 1 | (other frame layout) |
| `environment_tem` | 1 | (other frame layout) |
| `water_volume` | 1 | (other frame layout) |
| `fire_capacity` | 1 | (other frame layout) |

## 0xE6 Gas Boilers

Plug-in `T_0000_E6_9.lua`. Query (`0x03`): `aa1ee6000000000000030101000000000000000000000000000000000000f7`.

### Status – msg 0x03 body 0x01

| Property | Body byte → value | Default | In integration |
| --- | --- | --- | --- |
| `antifreezing` | 2: 0x01→"first_level_freeze", 0x02→"second_level_freeze", 0x19→"first_level_freeze", 0xFF→"first_level_freeze" | "unfrozen" |  |
| `power` | 2.bit2 → "on" | "off" |  |
| `flame_feedback` | 2.bit3 → "on" | "off" |  |
| `heating_work` | 2.bit4 → "on" | "off" |  |
| `bathing_work` | 2.bit5 → "on" | "off" |  |
| `heat_mode` | 3: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `winter_mode` | 4.bit0 → "on" | "off" |  |
| `summer_mode` | 4.bit1 → "on" | "off" |  |
| `mode` | 4: 0x04→"normal_mode", 0x08→"out_mode", 0x10→"home_mode", 0x20→"sleep_mode" | null |  |
| `bath_mode` | 5: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `temperature_sensation_switch` | 5.bit1 → "on" | "off" |  |
| `error_code` | 6: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `error` | 6: 0x01→"ignition_failure", 0x02→"flameout", 0x04→"ember", 0x08→"solenoid_valve_failure" | "no_error" |  |
| `exclusive_temperature` | 7: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `bath_out_water_temperature` | 8: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `bath_out_water_temperature_small` | 9: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `bath_set_temperature_max` | 10: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `bath_set_temperature_min` | 11: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `current_bath_set_temperature` | 12: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `current_bath_set_temperature_small` | 13: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `heat_out_water_temperature` | 14: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `heat_set_temperature_max` | 15: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `heat_set_temperature_min` | 16: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `current_heat_set_temperature` | 17: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `fan_type` | 18: 0x01→"single_speed", 0x02→"double_speed", 0x19→"single_speed", 0xFF→"single_speed" | "direct" |  |
| `gas_valve_manufacturer` | 18.bit2 → "aike" | "sanguo" |  |
| `heat_appointment_switch` | 18.bit3 → "on" | "off" |  |
| `appointment` | 18: 0x10→"wifi_ap", 0x20→"wifi_ap_rise", 0x40→"wifi_ap_rise_sen", 0x19→"wifi_ap" | "no_wifi" |  |
| `filter_water` | 19: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048; 20: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `proportioner_max_elec` | 21: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `exclusive_temperature_2` | 21: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `proportioner_fire_elec` | 22: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `exclusive_temperature_3` | 22: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `heat_back_water_temp_diff` | 23: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `half_pipe_time` | 24: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `cold_water_single` | 25.bit0 → "on" | "off" | yes |
| `cold_water_dot` | 25.bit1 → "on" | "off" | yes |
| `cold_water_appoint_switch` | 25.bit2 → "on" | "off" |  |
| `cold_water_master` | 25.bit3 → "on" | "off" |  |
| `heat_exchanger` | 25.bit4 → "floor_heating" | "radiator" |  |
| `cold_water_appoint_master` | 25.bit5 → "on" | "off" |  |
| `cold_water_ai` | 25.bit6 → "on" | "off" |  |
| `cold_water_has_enabled_appoint` | 25.bit7 → "on" | "off" |  |
| `rise_number` | 26: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `water_gage` | 27: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `current_bath_water` | 28: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `out_temperature` | 29: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `in_temperature` | 30: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `temperature_sensation` | 31: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `ignitor_output` | 32.bit0 → "output" | "no_output" |  |
| `main_gas_valve_output` | 32.bit1 → "output" | "no_output" |  |
| `tee_valve_output` | 32.bit2 → "bath_side" | "heat_side" |  |
| `fan_output` | 32.bit3 → "output" | "no_output" |  |
| `heat_pump_output` | 32.bit4 → "output" | "no_output" |  |
| `sectioning1_output` | 32.bit5 → "output" | "no_output" |  |
| `sectioning2_output` | 32.bit6 → "output" | "no_output" |  |
| `zero_cool_pump_output` | 32.bit7 → "output" | "no_output" |  |
| `hold_back_43_1` | 33.bit0 → "on" | "off" |  |
| `in_temperature_switch` | 33.bit1 → "off" | "on" |  |
| `buzzing_master_switch` | 33.bit2 → "no_buzzing" | "buzzing" |  |
| `hold_back_43_3` | 33.bit3 → "on" | "off" |  |
| `hold_back_43_4` | 33.bit4 → "on" | "off" |  |
| `hold_back_43_5` | 33.bit5 → "on" | "off" |  |
| `hold_back_43_6` | 33.bit6 → "on" | "off" |  |
| `hold_back_43_7` | 33.bit7 → "on" | "off" |  |
| `sectioning_output_percent` | 34: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `heat_back_water_temp` | 35: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `bath_back_water_temp` | 36: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |

Also reported (not driven by a single byte): `version`

### Control

Base control frame: `aa1ee6000000000000020400000000000000000000000000000000000000f6`

| Property | Test value | Changed body bytes (index: before→after) |
| --- | --- | --- |
| `cold_water_single` | "on" | 1:00->1a, 2:00->01 |
| `cold_water_dot` | "on" | 1:00->1b, 2:00->01 |
| `cold_water_appoint_switch` | "on" | 1:00->1c, 2:00->01 |
| `cold_water_has_enabled_appoint` | "on" | 1:00->1d, 2:00->01 |
| `cold_water_appoint_master` | "on" | 1:00->1e, 2:00->01 |
| `cold_water_master` | "on" | 1:00->1f, 2:00->01 |
| `half_pipe_time` | 1 | 1:00->20, 2:00->01, 3:00->01 |
| `cold_water_ai` | "on" | 1:00->21, 2:00->01 |
| `flame_feedback` | "on" | (other frame layout) |
| `heating_work` | "on" | (other frame layout) |
| `bathing_work` | "on" | (other frame layout) |
| `error_code` | 1 | (other frame layout) |
| `bath_out_water_temperature` | 1 | (other frame layout) |
| `bath_out_water_temperature_small` | 1 | (other frame layout) |
| `bath_set_temperature_max` | 1 | (other frame layout) |
| `bath_set_temperature_min` | 1 | (other frame layout) |
| `current_bath_set_temperature_small` | 1 | (other frame layout) |
| `heat_out_water_temperature` | 1 | (other frame layout) |
| `heat_set_temperature_max` | 1 | (other frame layout) |
| `heat_set_temperature_min` | 1 | (other frame layout) |
| `filter_water` | 1 | (other frame layout) |
| `proportioner_max_elec` | 1 | (other frame layout) |
| `proportioner_fire_elec` | 1 | (other frame layout) |
| `heat_back_water_temp_diff` | 1 | (other frame layout) |
| `rise_number` | 1 | (other frame layout) |
| `water_gage` | 1 | (other frame layout) |
| `current_bath_water` | 1 | (other frame layout) |
| `out_temperature` | 1 | (other frame layout) |
| `in_temperature` | 1 | (other frame layout) |
| `temperature_sensation` | 1 | (other frame layout) |
| `in_temperature_switch` | "on" | (other frame layout) |
| `hold_back_43_1` | "on" | (other frame layout) |
| `hold_back_43_3` | "on" | (other frame layout) |
| `hold_back_43_4` | "on" | (other frame layout) |
| `hold_back_43_5` | "on" | (other frame layout) |
| `hold_back_43_6` | "on" | (other frame layout) |
| `hold_back_43_7` | "on" | (other frame layout) |
| `sectioning_output_percent` | 1 | (other frame layout) |
| `heat_back_water_temp` | 1 | (other frame layout) |
| `bath_back_water_temp` | 1 | (other frame layout) |
| `power` | "on" | 0:04->01, 1:00->01 |
| `winter_mode` | "on" | 1:00->01, 2:00->01 |
| `summer_mode` | "on" | 1:00->01, 2:00->02 |
| `heat_mode` | 1 | 1:00->02, 3:00->01 |
| `current_heat_set_temperature` | 1 | 1:00->13, 2:00->01 |
| `current_bath_set_temperature` | 1 | 1:00->12, 2:00->01 |
| `exclusive_temperature` | 1 | 1:00->16, 2:00->01 |
| `exclusive_temperature_2` | 1 | 1:00->16, 4:00->01 |
| `exclusive_temperature_3` | 1 | 1:00->16, 6:00->01 |
| `temperature_sensation_switch` | "on" | 1:00->15, 2:00->01 |
| `heat_appointment_switch` | "on" | (other frame layout) |
| `bath_mode` | 1 | 1:00->18, 2:00->01 |
| `version` | 10 | (other frame layout) |

## 0xED Water Drinking Appliance

Plug-in `T_0000_ED_28.lua`. Query (`0x03`): `aa0ced00000000000003010102`.

### Status – msg 0x03 body 0x01

| Property | Body byte → value | Default | In integration |
| --- | --- | --- | --- |
| `basic_data` | 1: 0x01→{"0": 1, "1": 1, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0, "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0, "17": 0, "18": 0, "19": 0, "20": 0, "21": 0, "22": 0, "23": 0, "24": 0, "25": 0, "26": 0, "27": 0, "28": 0, "29": 0, "30": 0, "31": 0, "32": 0, "33": 0, "34": 0, "35": 0, "36": 0, "37": 0, "38": 0, "39": 0, "40": 0, "41": 0, "42": 0, "43": 0, "44": 0, "45": 0, "46": 0, "47": 0, "48": 0, "49": 0, "50": 0, "51": 0, "52": 0, "53": 0, "54": 0, "55": 0, "56": 0, "57": 0, "58": 0, "59": 0, "60": 0, "61": 0, "62": 0, "63": 0}, 0x02→{"0": 1, "1": 2, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0, "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0, "17": 0, "18": 0, "19": 0, "20": 0, "21": 0, "22": 0, "23": 0, "24": 0, "25": 0, "26": 0, "27": 0, "28": 0, "29": 0, "30": 0, "31": 0, "32": 0, "33": 0, "34": 0, "35": 0, "36": 0, "37": 0, "38": 0, "39": 0, "40": 0, "41": 0, "42": 0, "43": 0, "44": 0, "45": 0, "46": 0, "47": 0, "48": 0, "49": 0, "50": 0, "51": 0, "52": 0, "53": 0, "54": 0, "55": 0, "56": 0, "57": 0, "58": 0, "59": 0, "60": 0, "61": 0, "62": 0, "63": 0}, 0x04→{"0": 1, "1": 4, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0, "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0, "17": 0, "18": 0, "19": 0, "20": 0, "21": 0, "22": 0, "23": 0, "24": 0, "25": 0, "26": 0, "27": 0, "28": 0, "29": 0, "30": 0, "31": 0, "32": 0, "33": 0, "34": 0, "35": 0, "36": 0, "37": 0, "38": 0, "39": 0, "40": 0, "41": 0, "42": 0, "43": 0, "44": 0, "45": 0, "46": 0, "47": 0, "48": 0, "49": 0, "50": 0, "51": 0, "52": 0, "53": 0, "54": 0, "55": 0, "56": 0, "57": 0, "58": 0, "59": 0, "60": 0, "61": 0, "62": 0, "63": 0}, 0x08→{"0": 1, "1": 8, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0, "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0, "17": 0, "18": 0, "19": 0, "20": 0, "21": 0, "22": 0, "23": 0, "24": 0, "25": 0, "26": 0, "27": 0, "28": 0, "29": 0, "30": 0, "31": 0, "32": 0, "33": 0, "34": 0, "35": 0, "36": 0, "37": 0, "38": 0, "39": 0, "40": 0, "41": 0, "42": 0, "43": 0, "44": 0, "45": 0, "46": 0, "47": 0, "48": 0, "49": 0, "50": 0, "51": 0, "52": 0, "53": 0, "54": 0, "55": 0, "56": 0, "57": 0, "58": 0, "59": 0, "60": 0, "61": 0, "62": 0, "63": 0}; 2: 0x01→{"0": 1, "1": 0, "2": 1, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0, "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0, "17": 0, "18": 0, "19": 0, "20": 0, "21": 0, "22": 0, "23": 0, "24": 0, "25": 0, "26": 0, "27": 0, "28": 0, "29": 0, "30": 0, "31": 0, "32": 0, "33": 0, "34": 0, "35": 0, "36": 0, "37": 0, "38": 0, "39": 0, "40": 0, "41": 0, "42": 0, "43": 0, "44": 0, "45": 0, "46": 0, "47": 0, "48": 0, "49": 0, "50": 0, "51": 0, "52": 0, "53": 0, "54": 0, "55": 0, "56": 0, "57": 0, "58": 0, "59": 0, "60": 0, "61": 0, "62": 0, "63": 0}, 0x02→{"0": 1, "1": 0, "2": 2, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0, "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0, "17": 0, "18": 0, "19": 0, "20": 0, "21": 0, "22": 0, "23": 0, "24": 0, "25": 0, "26": 0, "27": 0, "28": 0, "29": 0, "30": 0, "31": 0, "32": 0, "33": 0, "34": 0, "35": 0, "36": 0, "37": 0, "38": 0, "39": 0, "40": 0, "41": 0, "42": 0, "43": 0, "44": 0, "45": 0, "46": 0, "47": 0, "48": 0, "49": 0, "50": 0, "51": 0, "52": 0, "53": 0, "54": 0, "55": 0, "56": 0, "57": 0, "58": 0, "59": 0, "60": 0, "61": 0, "62": 0, "63": 0}, 0x04→{"0": 1, "1": 0, "2": 4, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0, "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0, "17": 0, "18": 0, "19": 0, "20": 0, "21": 0, "22": 0, "23": 0, "24": 0, "25": 0, "26": 0, "27": 0, "28": 0, "29": 0, "30": 0, "31": 0, "32": 0, "33": 0, "34": 0, "35": 0, "36": 0, "37": 0, "38": 0, "39": 0, "40": 0, "41": 0, "42": 0, "43": 0, "44": 0, "45": 0, "46": 0, "47": 0, "48": 0, "49": 0, "50": 0, "51": 0, "52": 0, "53": 0, "54": 0, "55": 0, "56": 0, "57": 0, "58": 0, "59": 0, "60": 0, "61": 0, "62": 0, "63": 0}, 0x08→{"0": 1, "1": 0, "2": 8, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0, "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0, "17": 0, "18": 0, "19": 0, "20": 0, "21": 0, "22": 0, "23": 0, "24": 0, "25": 0, "26": 0, "27": 0, "28": 0, "29": 0, "30": 0, "31": 0, "32": 0, "33": 0, "34": 0, "35": 0, "36": 0, "37": 0, "38": 0, "39": 0, "40": 0, "41": 0, "42": 0, "43": 0, "44": 0, "45": 0, "46": 0, "47": 0, "48": 0, "49": 0, "50": 0, "51": 0, "52": 0, "53": 0, "54": 0, "55": 0, "56": 0, "57": 0, "58": 0, "59": 0, "60": 0, "61": 0, "62": 0, "63": 0}; 3: 0x01→{"0": 1, "1": 0, "2": 0, "3": 1, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0, "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0, "17": 0, "18": 0, "19": 0, "20": 0, "21": 0, "22": 0, "23": 0, "24": 0, "25": 0, "26": 0, "27": 0, "28": 0, "29": 0, "30": 0, "31": 0, "32": 0, "33": 0, "34": 0, "35": 0, "36": 0, "37": 0, "38": 0, "39": 0, "40": 0, "41": 0, "42": 0, "43": 0, "44": 0, "45": 0, "46": 0, "47": 0, "48": 0, "49": 0, "50": 0, "51": 0, "52": 0, "53": 0, "54": 0, "55": 0, "56": 0, "57": 0, "58": 0, "59": 0, "60": 0, "61": 0, "62": 0, "63": 0}, 0x02→{"0": 1, "1": 0, "2": 0, "3": 2, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0, "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0, "17": 0, "18": 0, "19": 0, "20": 0, "21": 0, "22": 0, "23": 0, "24": 0, "25": 0, "26": 0, "27": 0, "28": 0, "29": 0, "30": 0, "31": 0, "32": 0, "33": 0, "34": 0, "35": 0, "36": 0, "37": 0, "38": 0, "39": 0, "40": 0, "41": 0, "42": 0, "43": 0, "44": 0, "45": 0, "46": 0, "47": 0, "48": 0, "49": 0, "50": 0, "51": 0, "52": 0, "53": 0, "54": 0, "55": 0, "56": 0, "57": 0, "58": 0, "59": 0, "60": 0, "61": 0, "62": 0, "63": 0}, 0x04→{"0": 1, "1": 0, "2": 0, "3": 4, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0, "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0, "17": 0, "18": 0, "19": 0, "20": 0, "21": 0, "22": 0, "23": 0, "24": 0, "25": 0, "26": 0, "27": 0, "28": 0, "29": 0, "30": 0, "31": 0, "32": 0, "33": 0, "34": 0, "35": 0, "36": 0, "37": 0, "38": 0, "39": 0, "40": 0, "41": 0, "42": 0, "43": 0, "44": 0, "45": 0, "46": 0, "47": 0, "48": 0, "49": 0, "50": 0, "51": 0, "52": 0, "53": 0, "54": 0, "55": 0, "56": 0, "57": 0, "58": 0, "59": 0, "60": 0, "61": 0, "62": 0, "63": 0}, 0x08→{"0": 1, "1": 0, "2": 0, "3": 8, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0, "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0, "17": 0, "18": 0, "19": 0, "20": 0, "21": 0, "22": 0, "23": 0, "24": 0, "25": 0, "26": 0, "27": 0, "28": 0, "29": 0, "30": 0, "31": 0, "32": 0, "33": 0, "34": 0, "35": 0, "36": 0, "37": 0, "38": 0, "39": 0, "40": 0, "41": 0, "42": 0, "43": 0, "44": 0, "45": 0, "46": 0, "47": 0, "48": 0, "49": 0, "50": 0, "51": 0, "52": 0, "53": 0, "54": 0, "55": 0, "56": 0, "57": 0, "58": 0, "59": 0, "60": 0, "61": 0, "62": 0, "63": 0} … | {"0": 1, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0, "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0, "17": 0, "18": 0, "19": 0, "20": 0, "21": 0, "22": 0, "23": 0, "24": 0, "25": 0, "26": 0, "27": 0, "28": 0, "29": 0, "30": 0, "31": 0, "32": 0, "33": 0, "34": 0, "35": 0, "36": 0, "37": 0, "38": 0, "39": 0, "40": 0, "41": 0, "42": 0, "43": 0, "44": 0, "45": 0, "46": 0, "47": 0, "48": 0, "49": 0, "50": 0, "51": 0, "52": 0, "53": 0, "54": 0, "55": 0, "56": 0, "57": 0, "58": 0, "59": 0, "60": 0, "61": 0, "62": 0, "63": 0} |  |
| `power` | 2.bit0 → "on" | "off" | yes |
| `heat` | 2.bit1 → "on" | "off" |  |
| `heat_status` | 2.bit2 → "on" | "off" |  |
| `cool` | 2.bit3 → "on" | "off" |  |
| `cool_status` | 2.bit4 → "on" | "off" |  |
| `bubble` | 2.bit5 → "on" | "off" |  |
| `bubble_status` | 2.bit6 → "on" | "off" |  |
| `out_water` | 3.bit4 → "on" | "off" |  |
| `filter` | 3.bit5 → "on" | "off" |  |
| `wash` | 3.bit6 → "on" | "off" |  |
| `rfid_error` | 4.bit4 → "on" | "off" |  |
| `lack_water` | 4.bit5 → "on" | "off" |  |
| `drainage` | 4.bit6 → "on" | "off" |  |
| `uv_sterilize` | 5.bit5 → "on" | "off" |  |
| `water_litre` | 7: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 8: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `heat_temperature` | 10: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `cool_temperature` | 11: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `has_error` | 13.bit0 → "on" | "off" |  |
| `leaking_error` | 13.bit1 → "on" | "off" |  |
| `in_temperature_sensor_error` | 13.bit2 → "on" | "off" |  |
| `heat_sensor_error` | 13.bit3 → "on" | "off" |  |
| `out_temperature_sensor_error` | 13.bit4 → "on" | "off" |  |
| `hotwater_sensor_short_error` | 13.bit5 → "on" | "off" |  |
| `hotwater_sensor_open_error` | 13.bit6 → "on" | "off" |  |
| `coolwater_sensor_short_error` | 13.bit7 → "on" | "off" |  |
| `coolwater_sensor_open_error` | 14.bit0 → "on" | "off" |  |
| `instant_error` | 14.bit3 → "on" | "off" |  |
| `overtime_error` | 14.bit4 → "on" | "off" |  |
| `communicate_error` | 14.bit5 → "on" | "off" |  |
| `standby_status` | 15.bit1 → "on" | "off" |  |
| `lock` | 15.bit2 → "on" | "off" |  |
| `faucet_error` | 15.bit4 → "on" | "off" |  |
| `tds_error` | 15.bit5 → "on" | "off" |  |
| `life_1` | 16: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `life_2` | 17: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `life_3` | 18: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `life_4` | 19: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `life_5` | 20: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `filter_1` | 25: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 26: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `filter_2` | 27: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 28: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `filter_3` | 29: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 30: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `filter_4` | 31: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 32: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `filter_5` | 33: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 34: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `countdown_filter_1` | 35: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `in_tds` | 36: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 37: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 | yes |
| `out_tds` | 38: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 39: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 | yes |
| `countdown_filter_2` | 40: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `countdown_filter_3` | 41: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `countdown_filter_4` | 42: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `countdown_filter_5` | 43: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `vacation` | 48.bit0 → "on" | "off" |  |
| `wash_enable` | 49.bit5 → "on" | "off" |  |

Also reported (not driven by a single byte): `version`

### Control

Base control frame: `None`

| Property | Test value | Changed body bytes (index: before→after) |
| --- | --- | --- |
| `power` | "on" | (other frame layout) |
| `heat` | "on" | (other frame layout) |
| `cool` | "on" | (other frame layout) |
| `bubble` | "on" | (other frame layout) |
| `out_water` | "on" | (other frame layout) |
| `wash` | "on" | (other frame layout) |
| `drainage` | "on" | (other frame layout) |
| `standby_status` | "on" | (other frame layout) |
| `lock` | "on" | (other frame layout) |
| `life_1` | 1 | (other frame layout) |
| `life_2` | 1 | (other frame layout) |
| `life_3` | 1 | (other frame layout) |
| `life_4` | 1 | (other frame layout) |
| `life_5` | 1 | (other frame layout) |
| `vacation` | "on" | (other frame layout) |
| `wash_enable` | "on" | (other frame layout) |

## 0xFA Fan

Plug-in `T_0000_FA_560000AG_2022022802.lua`. Query (`0x03`): `aa0afa00000000000003f9`.

### Status – msg 0x03 body 0x01

| Property | Body byte → value | Default | In integration |
| --- | --- | --- | --- |
| `error_code` | 1: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 | yes |
| `voice` | 2: 0x01→"open_gps", 0x02→"close_gps", 0x04→"open_buzzer", 0x08→"close_buzzer" | null |  |
| `lock` | 3.bit0/1 → "on" | null |  |
| `power` | 4.bit0 → "on" | "off" | yes |
| `mode` | 4: 0x02→"normal", 0x04→"natural", 0x08→"comfort", 0x10→"storm" | null |  |
| `gear` | 5: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | null |  |
| `temperature` | 6: 0x01→-40, 0x02→-39, 0x04→-37, 0x08→-33 | null |  |
| `humidity` | 7: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | null |  |
| `swing` | 8.bit0 → "on" | "off" |  |
| `swing_direction` | 8: 0x02→"lr", 0x04→"ud", 0x08→"8", 0x19→"8" | "unknown" |  |
| `swing_angle` | 8: 0x10→"30", 0x20→"60", 0x40→"120", 0x19→"30" | "unknown" |  |
| `anion` | 9.bit0/1 → "on" | null | yes |
| `anophelifuge` | 9.bit2/3 → "on" | null | yes |
| `humidify` | 9: 0x10→"off", 0x20→"1", 0x40→"2", 0x19→"off" | null | yes |
| `timer_off_hour` | 10: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `timer_off_minute` | 10.bit5/6/7 → 10; 14: 0x10→1, 0x20→2, 0x40→4, 0x80→8 | 0 |  |
| `timer_on_hour` | 11: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `timer_on_minute` | 11.bit5/6/7 → 10; 14: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `humidify_feedback` | 12: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | null | yes |
| `temperature_feedback` | 13: 0x01→-40, 0x02→-39, 0x04→-37, 0x08→-33 | null | yes |
| `body_feeling_scan` | 15.bit0/1 → "on" | null | yes |
| `scene` | 16.bit0/1/2 → "old" | "none" |  |
| `sleep_sensor` | 17.bit0/1 → "sleep" | "none" |  |
| `spin_switch` | 19.bit0/1 → "on" | null |  |
| `air_dry_switch` | 19.bit2/3 → "on" | null |  |
| `temp_wind_switch` | 19.bit4/5 → "on" | null |  |
| `display_on_off` | 19.bit6/7 → "on" | null | yes |
| `water_feedback` | 24.bit0/1 → "shortage" | "invalid" |  |
| `breath_light` | 24.bit2/3 → "on" | null |  |
| `electrolytic_water` | 24.bit4/5 → "on" | null |  |
| `ud_swing_angle` | 25: 0x01→"30", 0x02→"60", 0x04→"120", 0x08→"-60" | "unknown" |  |
| `lr_diy_down_percent` | 26: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `lr_diy_up_percent` | 27: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `ud_diy_down_percent` | 28: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `ud_diy_up_percent` | 29: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `real_gear` | 30: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `back_gear` | 31: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | null |  |
| `dust_life_time` | 32: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `filter_life_time` | 33: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `waterions` | 34.bit0/1 → "on" | null | yes |
| `filter_replace_info` | 34.bit2/3 → "on" | null |  |
| `dust_info` | 34.bit4/5 → "on" | null |  |
| `filter_reset` | 34.bit6 → "on" | "off" |  |
| `dust_reset` | 34.bit7 → "on" | "off" |  |
| `lr_diy_swing` | 35.bit0/1 → "on" | null |  |
| `ud_diy_swing` | 35.bit2/3 → "on" | null |  |
| `charge` | 35.bit4/5 → "on" | null |  |
| `charge_feedback` | 35.bit6/7 → "off" | null |  |
| `battery_status` | 36.bit0/1 → "charging" | "invalid" |  |
| `battery_level` | 36: 0x08→1, 0x10→2, 0x20→4, 0x19→3 | 0 |  |
| `pm25` | 37.bit0/1/2 → 1 | 0 |  |

Also reported (not driven by a single byte): `version`

### Control

Base control frame: `aa1dfa000000000000020000000080000000800000000000ff00000000e8`

| Property | Test value | Changed body bytes (index: before→after) |
| --- | --- | --- |
| `swing` | "on" | 8:80->01 |
| `power` | "on" | 4:80->01 |
| `lr_diy_down_percent` | 1 | (other frame layout) |
| `lr_diy_up_percent` | 1 | (other frame layout) |
| `ud_diy_down_percent` | 1 | (other frame layout) |
| `ud_diy_up_percent` | 1 | (other frame layout) |
| `real_gear` | 1 | (other frame layout) |
| `version` | 21 | (other frame layout) |
| `dust_life_time` | 1 | (other frame layout) |
| `filter_life_time` | 1 | (other frame layout) |
| `filter_reset` | "on" | (other frame layout) |
| `timer_off_hour` | 1 | 10:00->01 |
| `timer_off_minute` | 1 | 14:ff->1f |
| `dust_reset` | "on" | (other frame layout) |
| `timer_on_hour` | 1 | 11:00->01 |
| `timer_on_minute` | 1 | 14:ff->f1 |
| `battery_level` | 1 | (other frame layout) |
| `pm25` | 1 | (other frame layout) |
| `error_code` | 1 | (other frame layout) |

## 0xFC Air Purifier

Plug-in `T_0000_FC_20.lua`. Query (`0x03`): `aa20fc00000000000003410000ff03000002000000000000000000000000466cea`.

### Status – msg 0x03 body 0x01

| Property | Body byte → value | Default | In integration |
| --- | --- | --- | --- |
| `power` | 1.bit0 → "on" | "off" | yes |
| `detect` | 1.bit3 → "on" | "off" |  |
| `mode` | 2: 0x10→"auto", 0x20→"manual", 0x40→"fast", 0x19→"auto" | "none" | yes |
| `wind_speed` | 3: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `time_on` | 4: 0x01→30, 0x02→45, 0x04→75, 0x08→135; 6: 0x10→14, 0x20→13, 0x40→11, 0x80→7 | 15 |  |
| `power_on_timer` | 4.bit7 → "on" | "off" |  |
| `time` | 5: 0x01→30, 0x02→45, 0x04→75, 0x08→135; 6: 0x01→14, 0x02→13, 0x04→11, 0x08→7 | 15 |  |
| `power_off_timer` | 5.bit7 → "on" | "off" |  |
| `humidify_mode` | 8.bit4/5 → "manual" | "none" |  |
| `lock` | 8.bit7 → "on" | "off" |  |
| `bright` | 9: 0x01→1, 0x02→2, 0x04→4, 0x19→1 | 0 |  |
| `anion` | 9.bit6 → "on" | "off" | yes |
| `filter_deep_1_acc_time` | 11: 0x01→4, 0x02→8, 0x04→16, 0x08→32; 12.bit6/7 → 1 | 0 |  |
| `ash_tvoc` | 12: 0x01→1, 0x02→2, 0x04→4, 0x19→1 | 0 |  |
| `smell_tvoc` | 12: 0x08→1, 0x10→2, 0x20→4, 0x19→3 | 0 |  |
| `pm25` | 13: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 14: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 | yes |
| `tvoc` | 15: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 | yes |
| `humidify_feedback` | 16: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | null |  |
| `temperature_feedback` | 17: 0x01→-24.5, 0x02→-24, 0x04→-23, 0x08→-21 | null |  |
| `waterions` | 19.bit6 → "on" | "off" |  |
| `buzzer` | 19.bit7 → "on" | "off" |  |
| `error_code` | 21: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `voice_volume` | 22: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `first_filter_percent` | 23: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `deep_filter_percent` | 24: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `pm25_out` | 25: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 26: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 |  |
| `detect_mode` | 29: 0x01→"hcho", 0x02→"hcho", 0x04→"hcho", 0x08→"hcho" | "pm25" | yes |
| `hosting` | 34.bit2/3 → "on" | null |  |
| `hosting_upper` | 35: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `hosting_lower` | 36: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `hcho` | 37: 0x01→1, 0x02→2, 0x04→4, 0x08→8; 38: 0x01→256, 0x02→512, 0x04→1024, 0x08→2048 | 0 | yes |
| `sterilize_enable` | 40.bit0/1 → "on" | "none" |  |
| `sterilize_minute` | 41: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | null |  |

Also reported (not driven by a single byte): `version`

### Control

Base control frame: `aa21fc00000000000002484200007f7f00000000000000000000000000000077a33f`

| Property | Test value | Changed body bytes (index: before→after) |
| --- | --- | --- |
| `first_filter_percent` | 1 | (other frame layout) |
| `power_off_timer` | "on" | 3:00->80, 5:7f->81, 6:00->0f, 22:a3->a0 |
| `power` | "on" | 1:42->43, 22:a3->49 |
| `power_on_timer` | "on" | 3:00->80, 4:7f->81, 6:00->f0, 22:a3->44 |
| `detect` | "on" | (other frame layout) |
| `time_on` | 16 | (other frame layout) |
| `bright` | 1 | 9:00->01, 21:77->4a, 22:a3->47 |
| `wind_speed` | 1 | 3:00->01, 21:77->4a, 22:a3->39 |
| `lock` | "on" | 8:00->80, 21:77->4a, 22:a3->3f |
| `buzzer` | "on" | 10:00->40, 21:77->4a, 22:a3->93 |
| `waterions` | "on" | 10:00->20, 21:77->4a, 22:a3->55 |
| `pm25` | 1 | 21:77->4a, 22:a3->e0 |
| `deep_filter_percent` | 1 | 21:77->4a, 22:a3->e0 |
| `voice_volume` | 1 | 12:00->01, 21:77->4a, 22:a3->2e |
| `hosting_lower` | 1 | 17:00->01, 21:77->4a, 22:a3->2d |
| `pm25_out` | 1 | 21:77->4a, 22:a3->e0 |
| `hosting_upper` | 1 | 16:00->01, 21:77->4a, 22:a3->d7 |
| `tvoc` | 1 | 21:77->4a, 22:a3->e0 |
| `ash_tvoc` | 1 | 21:77->4a, 22:a3->e0 |
| `filter_deep_1_acc_time` | 1 | 21:77->4a, 22:a3->e0 |
| `smell_tvoc` | 1 | 21:77->4a, 22:a3->e0 |
| `time` | 16 | 21:77->4a, 22:a3->e0 |
| `error_code` | 1 | 21:77->4a, 22:a3->e0 |
| `anion` | "on" | 9:00->40, 21:77->4a, 22:a3->fa |
| `hcho` | 1 | 21:77->4a, 22:a3->e0 |
| `version` | 21 | 21:77->4a, 22:a3->e0 |

## 0xFD Humidifier

Plug-in `T_0000_FD_20200009_2023051801.lua`. Query (`0x03`): `aa1ffd00000000000003418100ff03000002000000000000000000000000e13a`.

### Status – msg 0x03 body 0xA0

| Property | Body byte → value | Default | In integration |
| --- | --- | --- | --- |
| `power` | 1.bit0 → "on" | "off" | yes |
| `wind_speed` | 3: 0xFF→"off" | null |  |
| `time_on` | 4: 0x01→30, 0x02→45, 0x04→75, 0x08→135; 6: 0x10→14, 0x20→13, 0x40→11, 0x80→7 | 15 |  |
| `power_on_timer` | 4.bit7 → "on" | "off" |  |
| `time_off` | 5: 0x01→30, 0x02→45, 0x04→75, 0x08→135; 6: 0x01→14, 0x02→13, 0x04→11, 0x08→7 | 15 |  |
| `power_off_timer` | 5.bit7 → "on" | "off" |  |
| `humidity` | 7: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `humidity_mode` | 10: 0x01→"manual", 0x02→"auto", 0x04→"parlour", 0x19→"manual" | null |  |
| `tank_status` | 10: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `netIons_on_off` | 10.bit5 → "on" | "off" |  |
| `cur_humidity` | 16: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `cur_temperature` | 17: 0x01→-24.5, 0x02→-24, 0x04→-23, 0x08→-21 | -25 |  |
| `error_code` | 21: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `disinfect_on_off` | 27.bit0/1 → "on" | "invalid" |  |
| `running_percent` | 30: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `wind_gear` | 32.bit0 → "lowest" | null |  |
| `airDry_on_off` | 35.bit4/5 → "on" | "invalid" |  |
| `sensorTemperature` | 37: 0x01→0.1, 0x02→0.2, 0x04→0.4, 0x08→0.8; 38: 0x01→25.6, 0x02→51.2, 0x04→102.4, 0x08→204.8 | 0 |  |
| `sensorHumidify` | 39: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |
| `sensorBattery` | 40: 0x01→1, 0x02→2, 0x04→4, 0x08→8 | 0 |  |

Also reported (not driven by a single byte): `water_box_acc_time`, `buzzer`, `bright_led`, `display_on_off`, `fog_cold_warm_on_off`, `atmosphere_on_off`, `water_box_transposing`, `version`, `auto_off`

### Control

Base control frame: `aa24fd00000000000002484200807f7fff010000000000000000000000000000000000666f`

| Property | Test value | Changed body bytes (index: before→after) |
| --- | --- | --- |
| `time_off` | 16 | 6:ff->fe, 25:66->ba |
| `power_on_timer` | "on" | 4:7f->81, 25:66->36 |
| `time_on` | 16 | 6:ff->ef, 25:66->94 |
| `running_percent` | 1 | 25:66->bf |
| `sensorHumidify` | 1 | 25:66->5a |
| `netIons_on_off` | "on" | 10:00->20, 25:66->df |
| `sensorBattery` | 1 | 25:66->3f |
| `sensorTemperature` | 1 | 25:66->b2 |
| `water_box_acc_time` | 1 | 25:66->0c |
| `humidity` | 1 | 25:66->0a |
| `buzzer` | "on" | 10:00->40, 25:66->63 |
| `cur_humidity` | 1 | 25:66->f0 |
| `cur_temperature` | -24 | 25:66->b3 |
| `power` | "on" | 1:42->43, 25:66->d6 |
| `error_code` | 1 | 25:66->56 |
| `water_box_transposing` | True | 25:66->d7 |
| `version` | 42 | 25:66->49 |
| `tank_status` | 1 | 25:66->4e |
| `power_off_timer` | "on" | 5:7f->81, 25:66->34 |

