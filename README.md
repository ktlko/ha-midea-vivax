# Midea / Vivax heat pump & air conditioners for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![GitHub release](https://img.shields.io/github/v/release/ktlko/ha-midea-vivax)](https://github.com/ktlko/ha-midea-vivax/releases)
[![Validate](https://github.com/ktlko/ha-midea-vivax/actions/workflows/validate.yml/badge.svg)](https://github.com/ktlko/ha-midea-vivax/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Local control of **Midea M-Thermal (Vivax, Hyundai, …) air-to-water heat pumps** over Modbus and of **Midea / Vivax Wi-Fi air conditioners** over their LAN protocol – no cloud needed for operation.

[![Buy me a coffee](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=&slug=kotelino&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff)](https://www.buymeacoffee.com/kotelino)

**Languages:** English, Slovenčina, Čeština, Deutsch, Polski, Español, Italiano

## Features

**Heat pump (Modbus TCP)** – about 200 entities read from the wired controller:

- climate entity for zone 1, switches for zone 1/2, hot water, ECO, silent mode, disinfection, weather curves
- water setpoints, hot water setpoint, weather curve number, all installer parameters (hysteresis, limits, TBH/IBH/AHS,
  custom curves, holiday …) as number entities
- temperatures T1–T5, Tw_in/out, Tp, Th, T2/T2B, Ta, pressures, compressor frequency, fan, current, voltage,
  water flow, output power, consumed electricity, produced heat and lifetime **COP**
- running loads (compressor, pumps, 3-way valves, heaters, defrost, anti-freeze …) as binary sensors
- error code with its description and the last three errors
- forced hot water / TBH / IBH, operating mode, silent level as selects; start DHW circulation button

**Air conditioners (Wi-Fi, LAN protocol V3)**

- climate entity with modes, fan speeds (including silent) and swing
- louvre positions, display, beep, ionizer, coil drying, 8 °C frost protection, "airflow away from people"
- room temperature and humidity, indoor/outdoor coil, compressor, fan speeds, energy
- self-cleaning start, filter reminder
- **multi-split**: indoor units can share one outdoor unit device with one "units mode" select

## Requirements

**Heat pump:** a Modbus RTU → TCP gateway (e.g. **Elfin EW11**) wired to the H1/H2 terminals of the wired
controller: **A+ → H2, B- → H1**, 9600 baud, 8N1. Set the Modbus address on the controller
(*HMI ADDRESS FOR BMS*, default 1) and use the gateway in *Modbus TCP ↔ RTU* mode, port 502.

**Air conditioners:** the unit must be on your LAN and registered in a Midea app
(**MSmartHome**, NetHome Plus, Midea Air …). The integration downloads the unit's token and key from that cloud
**once** during setup; afterwards everything runs locally. The password is not stored.

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ktlko&repository=ha-midea-vivax&category=integration)

1. In Home Assistant open **HACS → ⋮ → Custom repositories**.
2. Add `https://github.com/ktlko/ha-midea-vivax` with the type **Integration**.
3. Search for **Midea / Vivax (Modbus + Wi-Fi)**, open it and click **Download**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and pick **Midea / Vivax (Modbus + Wi-Fi)**.

[![Open your Home Assistant instance and start setting up the integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=midea_modbus_hp)

### Manual

Copy `custom_components/midea_modbus_hp` into the `custom_components` folder of your Home Assistant
configuration (the folder that contains `configuration.yaml`) and restart Home Assistant.

## Configuration

The setup dialog offers two choices:

### Heat pump (Modbus via EW11)

| Field | Meaning |
| --- | --- |
| Gateway IP address | IP of the EW11 (or other Modbus TCP gateway) |
| Port | Modbus TCP port, usually `502` |
| Modbus address | *HMI ADDRESS FOR BMS* from the controller menu, usually `1` |
| Name | device name in Home Assistant |

The integration reads register 1 before it creates the entry, so wrong wiring is reported right away.

### Air conditioner (Wi-Fi)

1. **Sign in to the Midea cloud** – choose the app the unit is registered in (MSmartHome = *SmartHome*)
   and enter its e-mail and password. Without your own account tick *Use the default account*; you then type the
   unit ID (appliance ID from the app) yourself.
2. **Choose the air conditioner** – units of your account are listed. Their IP address is filled in when the unit
   answers network discovery; many units don't, then look the IP up in your router. Indoor units that share one
   outdoor unit (multi-split) get the same *shared outdoor unit* name.
3. The token is fetched, the unit is tested and added.

If you already use **Midea AC LAN**, units paired there can be added directly without signing in.

The IP address and the outdoor unit can be changed later in the integration options.

## Tips

- Give the air conditioners a fixed IP address (DHCP reservation) in your router.
- The installer parameters are entity category *configuration* – keep them hidden from normal dashboards.
- Values with a state such as *mode* or *error* are stored as keys (`heat`, `e0` …) and shown translated, so they
  work the same in every language in automations.

## Troubleshooting

Add this to `configuration.yaml` to get debug logs, then reproduce the problem and attach the log to an issue:

```yaml
logger:
  logs:
    custom_components.midea_modbus_hp: debug
```

**Settings → Devices & services → (integration) → ⋮ → Download diagnostics** creates a file without passwords or tokens –
attach it to bug reports.

## Support

Found a bug or have an idea? [Open an issue](https://github.com/ktlko/ha-midea-vivax/issues).

If this integration saves you time, you can support the development:

[![Buy me a coffee](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=&slug=kotelino&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff)](https://www.buymeacoffee.com/kotelino)

## License

[MIT](LICENSE) – this project is not affiliated with or endorsed by the device manufacturers.
