"""Register map for Midea M-Thermal heat pumps (wired controller Modbus RTU).

Source: Midea/Hyundai "Modbus registry" document (wired controller is the slave,
H1-/H2+, 9600 8N1). Registers 0-13 are read/write; 100-146 are read-only.
On the Vivax 171H120F controller registers 14-20 return unrelated data, so the
"recommended" duplicates there are not used.
"""

from __future__ import annotations

DOMAIN = "midea_modbus_hp"
# Config entries are either the Modbus heat pump (no kind, older entries) or a Wi-Fi air conditioner.
CONF_KIND = "kind"
KIND_AC = "air_conditioner"
# Any other Midea appliance driven by midea-local (dehumidifier, water heater, ...).
KIND_APPLIANCE = "appliance"
CONF_OUTDOOR_UNIT = "outdoor_unit"
DEFAULT_PORT = 502
DEFAULT_DEVICE_ID = 1
DEFAULT_NAME = "Heat pump (Modbus)"
SCAN_SECONDS = 30

# (start, count) blocks read on every poll.
READ_BLOCKS = ((0, 14), (100, 25), (125, 22))
# Installer parameters, read every SLOW_EVERY polls. Gaps are registers the
# 171H120F controller (HMI software 34) does not answer: 236, 239, 253, 254, 263.
# 148-199 and 600+ are not implemented by this controller at all.
SLOW_BLOCKS = ((200, 36), (237, 2), (240, 13), (255, 8), (264, 9))
SLOW_EVERY = 20

# Writable registers.
REG_POWER = 0  # bit0 zone1/2 room control, bit1 zone1, bit2 DHW, bit3 zone2
REG_MODE = 1  # 1 auto, 2 cool, 3 heat
REG_ROOM_SET = 3  # room setpoint, value = degC * 2
REG_DHW_SET = 4
REG_FUNCTION = 5  # see FUNCTION_* bits
REG_CURVE = 6  # low byte zone1 curve 1-9, high byte zone2 curve 1-9
REG_FORCED_DHW = 7  # 0 none, 1 forced on, 2 forced off
REG_FORCED_TBH = 8
REG_FORCED_IBH = 9
REG_SG_MAX = 10  # smart grid: max hours at high price
REG_ZONE1_SET = 11
REG_ZONE2_SET = 12

FUNCTION_DISINFECT = 4
FUNCTION_HOLIDAY_AWAY = 5  # read only
FUNCTION_SILENT = 6
FUNCTION_SILENT_LEVEL2 = 7
FUNCTION_HOLIDAY_HOME = 8  # read only
FUNCTION_ECO = 10
FUNCTION_PUMP_D = 11
FUNCTION_CURVE_Z1 = 12
FUNCTION_CURVE_Z2 = 13

REG_STATUS = 128
REG_LOADS = 129
REG_ENERGY_IN = 143  # uint32, kWh (plain kWh on R32 units)
REG_ENERGY_OUT = 145

NOT_PRESENT = 255  # sentinel for absent probes / inactive curve

REG_PARAM1 = 210
REG_PARAM2 = 211

# Error code table 1 (state keys; descriptions live in the translations) (Midea Modbus documentation, register 124 and 125-127 history).
ERROR_CODES: dict[int, str] = {
    0: "none",
    1: "e0",
    2: "e1",
    3: "e2",
    4: "e3",
    5: "e4",
    6: "e5",
    7: "e6",
    8: "e7",
    9: "e8",
    10: "e9",
    11: "ea",
    12: "eb",
    13: "ec",
    14: "ed",
    15: "ee",
    20: "p0",
    21: "p1",
    23: "p3",
    24: "p4",
    25: "p5",
    26: "p6",
    31: "pb",
    33: "pd",
    38: "pp",
    39: "h0",
    40: "h1",
    41: "h2",
    42: "h3",
    43: "h4",
    44: "h5",
    45: "h6",
    46: "h7",
    47: "h8",
    48: "h9",
    49: "ha",
    50: "hb",
    52: "hd",
    53: "he",
    54: "hf",
    55: "hh",
    57: "hp",
    65: "c7",
    112: "bh",
    116: "f1",
    134: "l0",
    135: "l1",
    136: "l2",
    138: "l4",
    139: "l5",
    141: "l7",
    142: "l8",
    143: "l9",
}
