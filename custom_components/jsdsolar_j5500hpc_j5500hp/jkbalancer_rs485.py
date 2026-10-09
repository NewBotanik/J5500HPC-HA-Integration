import logging
import threading
import time

# JK-DZ11-B2A24S active balancer over RS485: binary request/response, 9600 baud.
# Protocol reference: docs/protocols/JK-DZ11B2A224S_RS485_V1.3_en.md.
# Request 7 bytes: 55 AA <addr> <cmd> <data u16 BE> <sum>; reply 74 bytes: EB 90 <addr> <cmd> <69 data> <sum>.
# Polling sends only the 0xFF read; set commands (0xF0/F2/F4/F6) only on a user action when writes are allowed.

REQUEST_HEADER = b'\x55\xAA'
RESPONSE_HEADER = b'\xEB\x90'
RESPONSE_LENGTH = 74
MAX_CELLS = 24
RESPONSE_TIMEOUT = 1.5  # the balancer must answer within 1 s (§3)

CMD_READ = 0xFF
CMD_CELL_COUNT = 0xF0
CMD_TRIGGER_DELTA = 0xF2
CMD_MAX_BALANCE_CURRENT = 0xF4
CMD_BALANCING_SWITCH = 0xF6

# Debug log depth, same levels as the JSD driver
LOG_OFF = 0
LOG_BASIC = 1
LOG_PROTOCOL = 2
LOG_PARSING = 3

# Writable settings: key -> (command, minimum, maximum, unit, icon)
SETTINGS = {
    'cell_count': (CMD_CELL_COUNT, 2, MAX_CELLS, None, 'mdi:counter'),
    'balance_trigger_voltage': (CMD_TRIGGER_DELTA, 2, 1000, 'mV', 'mdi:scale-balance'),
    # The document says 30–1000 mA; the 2 A model (B2A) reports and accepts 2000 mA
    'max_balance_current': (CMD_MAX_BALANCE_CURRENT, 30, 2000, 'mA', 'mdi:current-dc'),
}
SWITCHES = {'balancing_enabled': CMD_BALANCING_SWITCH}

# key -> (unit, icon, device_class, state_class, precision)
SENSORS = {
    'voltage': ('V', 'mdi:sine-wave', 'voltage', 'measurement', 2),
    'cell_voltage_avg': ('mV', 'mdi:align-vertical-center', 'voltage', 'measurement', 0),
    'cell_voltage_max': ('mV', 'mdi:align-vertical-top', 'voltage', 'measurement', 0),
    'cell_voltage_min': ('mV', 'mdi:align-vertical-bottom', 'voltage', 'measurement', 0),
    'cell_voltage_delta': ('mV', 'mdi:format-align-middle', 'voltage', 'measurement', 0),
    'cell_voltage_max_number': ('', 'mdi:arrow-up-bold', None, None, 0),
    'cell_voltage_min_number': ('', 'mdi:arrow-down-bold', None, None, 0),
    'cell_count_detected': ('', 'mdi:counter', None, None, 0),
    'cell_count': ('', 'mdi:counter', None, None, 0),
    'balance_current': ('mA', 'mdi:scale-balance', 'current', 'measurement', 0),
    'balance_trigger_voltage': ('mV', 'mdi:scale-balance', 'voltage', None, 0),
    'max_balance_current': ('mA', 'mdi:current-dc', 'current', None, 0),
    'balancing_state': ('', 'mdi:scale-balance', None, None, None),
    'temperature': ('°C', 'mdi:thermometer', 'temperature', 'measurement', 1),
    'alarm_code': ('', 'mdi:alert-circle-outline', None, None, 0),
}
CELL_SENSOR = ('mV', 'mdi:battery-outline', 'voltage', 'measurement', 0)

# Binary flags; the alarm_* ones are problems. Alarm bit 0 ("cell-count setting error" in the
# document) is set on a healthy device whose app shows no alarm, so it is only in alarm_code.
FLAG_KEYS = (
    'balancing_charging', 'balancing_discharging', 'balancing_enabled',
    'alarm_wire_resistance_high', 'alarm_battery_overvoltage',
)


def cell_key(index):
    """1-based cell number -> 'cell_01_voltage'."""
    return f"cell_{index:02d}_voltage"


def sensor_meta(key):
    if key in SENSORS:
        return SENSORS[key]
    if key.startswith('cell_') and key.endswith('_voltage') and key[5:7].isdigit():
        return CELL_SENSOR
    return None


def checksum(data):
    """Additive checksum: low 8 bits of the sum of all preceding bytes (§4.3)."""
    return sum(data) & 0xFF


def build_request(address, command, value=0):
    frame = REQUEST_HEADER + bytes([address & 0xFF, command & 0xFF, (value >> 8) & 0xFF, value & 0xFF])
    return frame + bytes([checksum(frame)])


def _u16(frame, offset):
    return int.from_bytes(frame[offset:offset + 2], 'big')


def _s16(frame, offset):
    return int.from_bytes(frame[offset:offset + 2], 'big', signed=True)


def validate_response(frame, address, command):
    """Return None if the 74-byte reply is valid for this request, otherwise the reason."""
    if len(frame) != RESPONSE_LENGTH:
        return f"length {len(frame)} instead of {RESPONSE_LENGTH}"
    if frame[:2] != RESPONSE_HEADER:
        return f"header {frame[:2].hex(' ')}"
    if checksum(frame[:-1]) != frame[-1]:
        return f"checksum {frame[-1]:02x}, expected {checksum(frame[:-1]):02x}"
    if frame[2] != address:
        return f"address {frame[2]}, expected {address}"
    if frame[3] != command:
        return f"command {frame[3]:02x}, expected {command:02x}"
    return None


def parse_status(frame):
    """0xFF reply (Table 5) -> (sensor values, binary flags)."""
    status = frame[11]
    alarms = frame[12]
    detected = frame[8]
    configured = frame[22]
    count = configured if 1 <= configured <= MAX_CELLS else min(max(detected, 1), MAX_CELLS)
    cells = [_u16(frame, 23 + 2 * i) for i in range(count)]
    data = {
        'voltage': round(_u16(frame, 4) * 0.01, 2),
        'cell_voltage_avg': _u16(frame, 6),
        'cell_count_detected': detected,
        # The balancer sends 0-based cell indices (a real 16-cell frame gives 0 and 15); shown 1-based
        'cell_voltage_max_number': frame[9] + 1,
        'cell_voltage_min_number': frame[10] + 1,
        'cell_voltage_delta': _u16(frame, 13),
        'balance_current': _u16(frame, 15),
        'balance_trigger_voltage': _u16(frame, 17),
        'max_balance_current': _u16(frame, 19),
        'cell_count': configured,
        # INT16 in 0.1 °C: the device sends 190 while its app shows 18.9 °C (the document says °C)
        'temperature': round(_s16(frame, 71) * 0.1, 1),
        'alarm_code': alarms,
        'balancing_state': 'Charging cell' if status & 0x01 else 'Discharging cell' if status & 0x02 else 'Idle',
    }
    if cells:
        data['cell_voltage_max'] = max(cells)
        data['cell_voltage_min'] = min(cells)
    for index, millivolts in enumerate(cells, start=1):
        data[cell_key(index)] = millivolts
    flags = {
        'balancing_charging': bool(status & 0x01),
        'balancing_discharging': bool(status & 0x02),
        'balancing_enabled': frame[21] == 1,
        'alarm_wire_resistance_high': bool(alarms & 0x02),
        'alarm_battery_overvoltage': bool(alarms & 0x04),
    }
    return data, flags


class JKBalancer485:
    """JK-DZ11-B2A24S balancer driver for the HA coordinator."""

    MAX_FAILURES = 3

    def __init__(self, bms_comm, address=1, allow_writes=False, log_depth=LOG_OFF):
        self.bms_comm = bms_comm
        self.address = address
        self.allow_writes = allow_writes
        self.log_depth = log_depth
        self.cycle = 0
        self._last = None
        self._failures = 0
        # One frame on the wire at a time: polling and writes run in different executor threads
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

    def _transact(self, command, value=0):
        """Send one request and return the validated 74-byte reply, or None."""
        request = build_request(self.address, command, value)
        with self._lock:
            started = time.monotonic()
            self.bms_comm.flush()
            if self.log_depth >= LOG_PROTOCOL:
                self.logger.debug("TX %s", request.hex(' '))
            if not self.bms_comm.send_data(request):
                self.logger.debug("TX %02x failed: link down", command)
                return None
            frame = self.bms_comm.read_bytes(RESPONSE_LENGTH, RESPONSE_TIMEOUT)
            # Resync if noise precedes the header
            start = frame.find(RESPONSE_HEADER)
            if start > 0:
                frame = frame[start:]
                frame += self.bms_comm.read_bytes(RESPONSE_LENGTH - len(frame), RESPONSE_TIMEOUT)
            if self.log_depth >= LOG_PROTOCOL:
                elapsed_ms = (time.monotonic() - started) * 1000
                self.logger.debug("RX %s (%d bytes, %.0f ms)", frame.hex(' ') or 'nothing', len(frame), elapsed_ms)
        problem = validate_response(frame, self.address, command)
        if problem:
            self.logger.debug("Invalid reply to %02x: %s", command, problem)
            return None
        return frame

    def get_data(self):
        """Poll once. Returns (sensor values, binary flags); empty dicts when the balancer is silent."""
        started = time.monotonic()
        self.cycle += 1
        frame = self._transact(CMD_READ)
        if frame is not None:
            self._failures = 0
            self._last = parse_status(frame)
            if self.log_depth >= LOG_PARSING:
                self.logger.debug("Parsed status: %s, flags: %s", *self._last)
        else:
            self._failures += 1
            if self._failures == self.MAX_FAILURES + 1:
                self.logger.warning(
                    "JK balancer at address %d does not answer. Check wiring (A/B), address and baud rate (9600).",
                    self.address)
            if self._failures > self.MAX_FAILURES:
                self._last = None
        if self._last is None:
            return {}, {}
        data, flags = self._last
        if self.log_depth >= LOG_BASIC:
            self.logger.info("Cycle %d: %d values, %d flags, %.2f s", self.cycle, len(data), len(flags),
                             time.monotonic() - started)
        return dict(data), dict(flags)

    def _write(self, command, value):
        """Send a set command; the reply carries the value that is now active (§4.2–4.5)."""
        if not self.allow_writes:
            raise PermissionError("Balancer control is disabled in the integration options")
        self.logger.info("Balancer write: command %02x value %d", command, value)
        frame = self._transact(command, value)
        if frame is None:
            raise TimeoutError(f"No valid answer from balancer to command {command:02x}")
        active = _u16(frame, 4)
        if active != value:
            raise ValueError(f"Balancer kept {active} instead of {value} (out of range)")
        return active

    def set_setting(self, key, value):
        command, minimum, maximum, _unit, _icon = SETTINGS[key]
        value = int(round(value))
        if not minimum <= value <= maximum:
            raise ValueError(f"{key}: {value} is outside {minimum}–{maximum}")
        active = self._write(command, value)
        if self._last:
            self._last[0][key] = active
        return active

    def set_switch(self, key, enabled):
        active = self._write(SWITCHES[key], 1 if enabled else 0)
        if self._last:
            self._last[1][key] = active == 1
        return active == 1
