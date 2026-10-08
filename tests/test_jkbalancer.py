#!/usr/bin/env python3
# Offline check of the JK-DZ11-B2A24S balancer driver against the example frames from
# docs/protocols/JK-DZ11B2A224S_RS485_V1.3_en.md. Needs no Home Assistant.
# Run: python tests/test_jkbalancer.py

import os
import sys

# Import the module directly: the package __init__ pulls in homeassistant
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'jsdsolar_j5500hpc_j5500hp'))
import jkbalancer_rs485 as jk  # noqa: E402


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


def frame(text):
    return bytes.fromhex(text)


# Vendor example frames (§4.1–4.5)
STATUS = frame(
    "EB 90 01 FF 1E D3 0F 69 14 13 02 00 00 00 07 00 00 00 05 03 E8 01 14 0F 69 0F 69"
    "0F 69 0F 69 0F 69 0F 69 0F 69 0F 69 0F 69 0F 69 0F 69 0F 69 0F 69 0F 69 0F 69 0F"
    "69 0F 69 0F 69 0F 69 0F 69 0F 69 0F 69 0F 69 0F 69 00 16 6F")


def set_reply(command, value):
    body = bytes([0xEB, 0x90, 0x01, command, value >> 8, value & 0xFF]) + bytes(67)
    return body + bytes([jk.checksum(body)])


class FakeComm:
    """Serves queued replies; records every request."""

    def __init__(self, replies):
        self.replies = dict(replies)
        self.sent = []
        self._pending = b''

    def flush(self):
        self._pending = b''

    def send_data(self, data):
        self.sent.append(bytes(data))
        reply = self.replies.get(bytes(data)[3])
        self._pending = reply(bytes(data)) if callable(reply) else (reply or b'')
        return True

    def read_bytes(self, size, timeout=1.0):
        data, self._pending = self._pending[:size], self._pending[size:]
        return data


results = []

# Requests and checksums
results.append(check("Read request", jk.build_request(1, jk.CMD_READ).hex(' ').upper(), "55 AA 01 FF 00 00 FF"))
results.append(check("Set cells 16", jk.build_request(1, jk.CMD_CELL_COUNT, 16).hex(' ').upper(), "55 AA 01 F0 00 10 00"))
results.append(check("Set trigger 10 mV", jk.build_request(1, jk.CMD_TRIGGER_DELTA, 10).hex(' ').upper(), "55 AA 01 F2 00 0A FC"))
results.append(check("Set max current 500 mA", jk.build_request(1, jk.CMD_MAX_BALANCE_CURRENT, 500).hex(' ').upper(), "55 AA 01 F4 01 F4 E9"))
results.append(check("Balancing on", jk.build_request(1, jk.CMD_BALANCING_SWITCH, 1).hex(' ').upper(), "55 AA 01 F6 00 01 F7"))
results.append(check("Example status frame valid", jk.validate_response(STATUS, 1, jk.CMD_READ), None))
for command, value, chk in ((0xF0, 16, 0x7C), (0xF2, 10, 0x78), (0xF4, 500, 0x65), (0xF6, 1, 0x73)):
    results.append(check(f"Example {command:02X} reply checksum", set_reply(command, value)[-1], chk))
broken = STATUS[:-1] + bytes([0x00])
results.append(check("Bad checksum rejected", jk.validate_response(broken, 1, jk.CMD_READ) is not None, True))
results.append(check("Wrong address rejected", jk.validate_response(STATUS, 2, jk.CMD_READ) is not None, True))

# Status parsing (Table 5)
data, flags = jk.parse_status(STATUS)
results.append(check("Total voltage", data['voltage'], 78.91))
results.append(check("Average cell", data['cell_voltage_avg'], 3945))
results.append(check("Cells detected / configured", (data['cell_count_detected'], data['cell_count']), (20, 20)))
results.append(check("Highest / lowest cell", (data['cell_voltage_max_number'], data['cell_voltage_min_number']), (19, 2)))
results.append(check("Delta, trigger, max current", (data['cell_voltage_delta'], data['balance_trigger_voltage'], data['max_balance_current']), (7, 5, 1000)))
results.append(check("Temperature", data['temperature'], 22))
results.append(check("Only configured cells exposed", (jk.cell_key(20) in data, jk.cell_key(21) in data), (True, False)))
results.append(check("Cell 01", data['cell_01_voltage'], 3945))
results.append(check("Balancing idle", (data['balancing_state'], flags['balancing_charging'], flags['balancing_discharging']), ('Idle', False, False)))
results.append(check("Balancing switch on", flags['balancing_enabled'], True))
results.append(check("No alarms", [k for k in flags if k.startswith('alarm_') and flags[k]], []))
results.append(check("Every key has metadata", [k for k in data if jk.sensor_meta(k) is None], []))
negative = bytearray(STATUS)
negative[71:73] = (-5).to_bytes(2, 'big', signed=True)
negative[-1] = jk.checksum(negative[:-1])
results.append(check("Negative temperature (INT16)", jk.parse_status(bytes(negative))[0]['temperature'], -5))

# Driver: polling, resync, silence
comm = FakeComm({jk.CMD_READ: STATUS})
balancer = jk.JKBalancer485(comm, address=1)
data, flags = balancer.get_data()
results.append(check("Poll returns data", data['voltage'], 78.91))
results.append(check("Polling sends only the read command", {f[3] for f in comm.sent}, {jk.CMD_READ}))
comm = FakeComm({jk.CMD_READ: b'\x00\x13' + STATUS})
results.append(check("Resync after noise", jk.JKBalancer485(comm).get_data()[0].get('voltage'), 78.91))
silent = jk.JKBalancer485(FakeComm({}))
results.append(check("Silent balancer", silent.get_data(), ({}, {})))
comm = FakeComm({jk.CMD_READ: STATUS})
balancer = jk.JKBalancer485(comm)
balancer.get_data()
comm.replies.clear()
for _ in range(jk.JKBalancer485.MAX_FAILURES):
    data, _flags = balancer.get_data()
results.append(check("Cached during short outage", data.get('voltage'), 78.91))
results.append(check("Dropped after too many failures", balancer.get_data(), ({}, {})))

# Writes
locked = jk.JKBalancer485(FakeComm({}))
results.append(raises("Write refused without option", PermissionError, locked.set_setting, 'max_balance_current', 500))
echo = lambda request: set_reply(request[3], int.from_bytes(request[4:6], 'big'))  # noqa: E731
comm = FakeComm({jk.CMD_READ: STATUS, 0xF0: echo, 0xF2: echo, 0xF4: echo, 0xF6: echo})
balancer = jk.JKBalancer485(comm, allow_writes=True)
balancer.get_data()
results.append(check("Set max current", balancer.set_setting('max_balance_current', 500), 500))
results.append(check("Set trigger", balancer.set_setting('balance_trigger_voltage', 10), 10))
results.append(check("Switch off", balancer.set_switch('balancing_enabled', False), False))
results.append(check("Cached value updated", balancer._last[0]['max_balance_current'], 500))
results.append(raises("Out of range not sent", ValueError, balancer.set_setting, 'balance_trigger_voltage', 5000))
results.append(check("Out-of-range frame not sent", any(f[3] == 0xF2 and f[4:6] == (5000).to_bytes(2, 'big') for f in comm.sent), False))
comm.replies[0xF4] = lambda request: set_reply(0xF4, 1000)
results.append(raises("Balancer keeping old value raises", ValueError, balancer.set_setting, 'max_balance_current', 600))
del comm.replies[0xF6]
results.append(raises("Silent write raises", TimeoutError, balancer.set_switch, 'balancing_enabled', True))

print(f"\n{sum(results)}/{len(results)} checks passed")
raise SystemExit(0 if all(results) else 1)
