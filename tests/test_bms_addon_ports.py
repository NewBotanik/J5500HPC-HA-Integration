#!/usr/bin/env python3
# Offline checks of the BMS fixes ported from Gobel-Battery-HA-Addon 1.9.87 / dev:
# PACE RS485 short ACK for the pack number, PACE current scale, JK BMS power sign.
# Needs no Home Assistant. Run: python tests/test_bms_addon_ports.py

import logging
import os
import struct
import sys

# Import the modules directly: the package __init__ pulls in homeassistant
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'jsdsolar_j5500hpc_j5500hp'))
import pacebms_rs485  # noqa: E402
import jkbms_rs485  # noqa: E402


def check(name, actual, expected):
    status = "OK  " if actual == expected else "FAIL"
    print(f"{status} {name}: {actual}" + ("" if actual == expected else f" (expected {expected})"))
    return actual == expected


def raises(name, error, func, *args):
    try:
        func(*args)
    except error:
        return check(name, error.__name__, error.__name__)
    return check(name, 'no error', error.__name__)


results = []

# PACE RS485 pack number (CID2 90): echo DATAINFO, short ACK, error RTN
pace = pacebms_rs485.PACEBMS485(bms_comm=None, ha_comm=None, data_refresh_interval=5, debug=0, if_random=0)
results.append(check("Pack number, echo DATAINFO (LENID 002)", pace.parse_pack_number_data("~25034600E00203FD8D"), 3))
results.append(check("Pack number, short ACK (LENID 000)", pace.parse_pack_number_data("~250546000000FDAF"), 5))
results.append(raises("Pack number, RTN error", ValueError, pace.parse_pack_number_data, "~250546040000FDAB"))
results.append(raises("Pack number, unknown LENID", ValueError, pace.parse_pack_number_data, "~25054600F00404FDAF"))

# PACE current scale: -1000 raw is -10 A at 0.01 A, -100 A at 0.1 A
frame = ("250146000000" "00" "01"          # header, INFOFLAG, packs
         "02" "0CE4" "0CE5"                # 2 cells
         "01" "0BA4"                       # 1 temperature
         "FC18"                            # current, raw -1000
         "D0AC"                            # total voltage 53.42 V
         "2710" "03" "2710"                # remaining 100 Ah, P, full 100 Ah
         "0010" "2710")                    # cycles, design 100 Ah


def current(scale):
    driver = pacebms_rs485.PACEBMS485(bms_comm=None, ha_comm=None, data_refresh_interval=5, debug=0, if_random=0,
                                      current_scale=scale)
    try:
        parsed = driver.parse_analog_data(frame)
    except Exception as err:
        return f"error: {err}"
    pack = parsed[0] if isinstance(parsed, list) else parsed
    return pack.get('view_current')


results.append(check("PACE current, default scale 100", current(100), -10.0))
results.append(check("PACE current, scale 10", current(10), -100.0))
results.append(check("PACE invalid scale falls back to 100", current(0), -10.0))

# JK BMS: power is unsigned in the frame and takes the sign of the current
jk = jkbms_rs485.JKBMS485.__new__(jkbms_rs485.JKBMS485)
jk.logger = logging.getLogger("test")


def jk_power(power_mw, current_ma):
    data = bytearray(300)
    data[0:2] = b"\x55\xaa"
    struct.pack_into("<I", data, 154, power_mw)
    struct.pack_into("<i", data, 158, current_ma)
    return jk.parse_jkbms_55aa_frame(bytes(data)).get("power_kw")


results.append(check("JK power while charging", jk_power(1_500_000, 30_000), 1.5))
results.append(check("JK power while discharging", jk_power(1_500_000, -30_000), -1.5))
results.append(check("JK power at zero current", jk_power(0, 0), 0.0))

print()
print(f"{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
