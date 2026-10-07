#!/usr/bin/env python3
# Offline check of the JSD SOLAR driver against the frame examples from docs/protocols/protocol.JSDSOLAR.en.md.
# Needs no Home Assistant. Run: python tests/test_jsdsolar.py

import datetime
import logging
import os
import re
import sys

# Import the module directly: the package __init__ pulls in homeassistant
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'jsdsolar_j5500hpc_j5500hp'))
import jsdsolar_rs232 as jsd  # noqa: E402


def check(name, actual, expected):
    status = "OK  " if actual == expected else "FAIL"
    print(f"{status} {name}: {actual}" + ("" if actual == expected else f" (expected {expected})"))
    return actual == expected


def raises(name, error, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except error:
        return check(name, error.__name__, error.__name__)
    return check(name, 'no error', error.__name__)


class FakeComm:
    """Answers from a dict; a command missing from it gets no response."""

    def __init__(self, responses):
        self.responses = dict(responses)
        self.sent = []
        self._pending = None

    def flush(self):
        self._pending = None

    def send_data(self, data):
        command = data.rstrip('\r')
        self.sent.append(command)
        self._pending = self.responses.get(command)
        return True

    def receive_data(self):
        return self._pending or ''


results = []

# Parsers: spec examples
results.append(check("GMOD", jsd.parse_gmod("(L"), {'operating_mode': 'Line'}))
results.append(check("SVFW", jsd.parse_svfw("(4.001 (20211105"),
                     {'firmware_version': '4.001', 'firmware_date': '2021-11-05'}))
gline = jsd.parse_gline("(220.0 50.00 264.0 154.0 255.0 163.0 70.00 40.00 010 ")
results.append(check("GLINE short frame voltage", gline['grid_voltage'], 220.0))
results.append(check("GLINE short frame energy missing", gline['grid_energy_total'], None))
results.append(check("GBUS leading space", jsd.parse_gbus("( 361.0 360.0 360.0"), {'bus_voltage': 361.0}))
results.append(check("BL", jsd.parse_bl("BL078"), {'battery_level': 78}))
fan_data, fan_flags = jsd.parse_fan("(050 00020 00020 0 1")
results.append(check("FAN flags", fan_flags, {'fan_1_fault': False, 'fan_2_fault': True}))
data, warnings = jsd.parse_gws("(00 0000000000000000 0000000000000000")
results.append(check("GWS no fault", data, {'fault_code': 0, 'fault': 'No fault'}))
results.append(check("GWS warnings all off", any(warnings.values()), False))
data, warnings = jsd.parse_gws("(14 0000100000000001 0000000000010000")
results.append(check("GWS fault 14", data['fault'], 'Overload fault'))
results.append(check("GWS bit 11 fan fault", warnings['warning_fan_fault'], True))
results.append(check("GWS bit 0 low battery", warnings['warning_low_battery_voltage'], True))
results.append(check("GWS word 2 bit 4 overload", warnings['warning_overload'], True))
results.append(check("F", jsd.parse_f("#230.0 024 048.0 50.0"),
                     {'rated_voltage': 230.0, 'rated_current': 24, 'rated_frequency': 50.0}))
results.append(check("I", jsd.parse_i("#ABCDEFGHIJKLMNOPQRSTUVWXYZ0R1.4.001  "),
                     {'serial_number': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0', 'dsp_firmware_version': '4.001'}))
results.append(check("Energy counter", jsd._energy_kwh(1, 4321), round((65536 + 4321) * 10 / 1000, 2)))

bms = jsd.parse_gbms(jsd.SAMPLE_RESPONSES['GBMS'])
results.append(check("GBMS current", bms['bms_current'], -12.5))
results.append(check("GBMS SOC", bms['bms_soc'], 78.0))
results.append(check("GBMS link lost", jsd.parse_gbms("(32768 00000 00524"), {'bms_comm_state': 32768, 'bms_state': 0}))
bms = jsd.parse_gbms("(00001 00000 32767 65286 00255 00780 00780 01000 00000 00000 06000 00560")
results.append(check("GBMS undefined voltage", bms['bms_voltage'], None))
results.append(check("GBMS two's complement current", bms['bms_current'], -2.5))

results.append(check("None response", jsd.parse_gop(None), None))
results.append(check("Garbage GWS", jsd.parse_gws("(xx"), None))
results.append(check("Bad bit string ignored", jsd.parse_gws("(00 0101")[1], {}))

# Settings (§9): read-back and write formats
results.append(check("Setting OPR", jsd.parse_setting('setting_output_priority', "(02"),
                     {'setting_output_priority': 'PV-Battery-Grid'}))
results.append(check("Setting BTG", jsd.parse_setting('setting_battery_back_to_grid_voltage', "(23.0"),
                     {'setting_battery_back_to_grid_voltage': 23.0}))
results.append(check("Setting V two values", jsd.parse_setting('setting_output_voltage', "(220 120"),
                     {'setting_output_voltage': '220 V', 'setting_displayed_output_voltage': 120}))
results.append(check("Read-back command widths", [jsd.SETTINGS[k].read_command for k in (
    'setting_cv_voltage', 'setting_max_charge_current', 'setting_battery_type',
    'setting_displayed_output_power', 'setting_max_cc_charge_time')],
    ['TCCV????', 'CHGC???', 'TBAT?', 'UP?????', 'CI1??']))
results.append(check("Write formats", [
    jsd.SETTINGS['setting_cv_voltage'].format(56.4), jsd.SETTINGS['setting_battery_back_to_battery_voltage'].format(0),
    jsd.SETTINGS['setting_max_charge_current'].format(20), jsd.SETTINGS['setting_cv_time'].format(720)],
    ['56.4', '00.0', '020', '0720']))

# Other queries (§8, §9.1, §12)
results.append(check("TCQN", jsd.parse_tcqn("0123"), {'hours_since_equalization': 123}))
results.append(check("DATE", jsd.parse_date("05 12 03"), {'inverter_date': '2005-12-03'}))
results.append(check("TIME", jsd.parse_time("05 12 03"), {'inverter_time': '05:12:03'}))
features = jsd.parse_features("(ACDEHJX")
results.append(check("TE? enabled letter", features['feature_overload_auto_restart'], True))
results.append(check("TE? disabled letter", features['feature_buzzer_mute'], False))
results.append(check("TE? unknown format", jsd.parse_features("(0123"), None))
gfail = jsd.parse_gfail(jsd.SAMPLE_RESPONSES['GFAIL'])
results.append(check("GFAIL fault and mode", (gfail['last_fault'], gfail['last_fault_mode']), ('Overload fault', 'Battery')))
results.append(check("GFAIL without fault hides snapshot", jsd.parse_gfail("(00 35 00000 0000"),
                     {'last_fault_code': 0, 'last_fault': 'No fault'}))
results.append(check("GCF P1 has 17 bits", len(jsd.parse_gcf(jsd.SAMPLE_RESPONSES['GCF'])['fault_bits_pfc']), 17))
gpdat = jsd.parse_gpdat(2, "(1 5 4001 1 00 230.0 50.00 229.0 50.00 230.0 50.00 007.5 052.0 -10.0 040 "
                           "01800 01600 080 300.0 010.0 3000 041.0")
results.append(check("GPDAT unit fields", (gpdat[0]['parallel_2_state'], gpdat[0]['parallel_2_output_active_power'],
                                           gpdat[1]['parallel_2_communication_ok']), ('Battery', 1600, True)))
results.append(check("GPDAT link lost", jsd.parse_gpdat(3, "(0 0 0000"), ({}, {'parallel_3_communication_ok': False})))
data, flags = jsd.parse_gpsts(1, 1, "(1 0000000000001000 0000000000000011")
results.append(check("GPSTS page 1", (flags['parallel_1_grid_ok'], data['parallel_1_dcdc_state'],
                                      flags['parallel_1_pv_charging_allowed']), (True, 'Charging', True)))
results.append(check("GPPV", jsd.parse_gppv("(2 300.0 010.0 290.0 009.0")['parallel_2_pv_voltage'], 290.0))
results.append(check("Parallel sensor metadata", jsd.sensor_meta('parallel_4_pv_power')[0], 'W'))

# Driver: sample frames, every key has entity metadata
inverter = jsd.JSDSOLAR232(bms_comm=None, data_refresh_interval=5, if_random=1)
data, flags = inverter.get_data()
results.append(check("Mode", data['operating_mode'], 'Battery'))
results.append(check("Output power", data['output_active_power'], 1650))
results.append(check("PV energy total", data['pv_energy_total'], 219.87))
results.append(check("Identity in data", data['serial_number'], 'J5500HPC2024010100000000001'))
results.append(check("Warning flags present", 'warning_overload' in flags, True))
for _ in range(30):
    data, flags = inverter.get_data()
results.append(check("All settings read after one slow round", set(jsd.SETTINGS) - set(data), set()))
results.append(check("Every key has metadata", {k for k in data if jsd.sensor_meta(k) is None}, set()))
results.append(check("No None values", any(v is None for v in data.values()), False))
results.append(check("Feature flags read", flags.get('feature_auto_frequency_adaptation'), True))
results.append(check("Clock read", (data.get('inverter_date'), data.get('inverter_time')), ('2025-12-03', '05:12:03')))

# Driver: cache on short outages, backoff on unsupported commands
responses = {k: v for k, v in jsd.SAMPLE_RESPONSES.items() if k != 'FAN???'}
comm = FakeComm(responses)
inverter = jsd.JSDSOLAR232(bms_comm=comm, data_refresh_interval=5)
inverter.get_data()
del comm.responses['GOP']
for cycle in range(jsd.JSDSOLAR232.MAX_FAILURES):
    data, _flags = inverter.get_data()
results.append(check("GOP cached during short outage", data.get('output_active_power'), 1650))
data, _flags = inverter.get_data()
results.append(check("GOP dropped after too many failures", 'output_active_power' in data, False))
comm.sent.clear()
for _ in range(10):
    inverter.get_data()
results.append(check("Unsupported FAN polled rarely", comm.sent.count('FAN???') <= 1, True))

silent = jsd.JSDSOLAR232(bms_comm=FakeComm({}), data_refresh_interval=5)
results.append(check("Silent inverter", silent.get_data(), ({}, {})))

# Polling sends queries only: every command must be a known read command, even with writes allowed
READ_COMMANDS = ({c for c, _p, _s in jsd.FAST_QUERIES} | {c for c, _p in jsd.IDENTITY_QUERIES}
                 | {s.read_command for s in jsd.SETTINGS.values()}
                 | {'TE?', 'TCQN????', 'DATE??????', 'TIME??????', 'GFAIL', 'GCF'})
PARALLEL_READ = re.compile(r'GPDAT\d|GPSTS\d[01]|GPID\d|GPPV\d')
comm = FakeComm({**jsd.SAMPLE_RESPONSES, 'PAR?': '(1', 'GPDAT1': '(1 5 4001 1 00', 'GPDAT2': '(0'})
inverter = jsd.JSDSOLAR232(bms_comm=comm, data_refresh_interval=5, allow_writes=True)
for _ in range(60):
    inverter.get_data()
writes = [c for c in comm.sent if c not in READ_COMMANDS and not PARALLEL_READ.fullmatch(c)]
results.append(check("Polling never sends a write", writes, []))
results.append(check("Parallel unit 1 discovered", inverter.parallel_units, {1}))
results.append(check("Parallel status polled", 'GPSTS10' in comm.sent and 'GPID1' in comm.sent, True))

# Writes: refused without the option
locked = jsd.JSDSOLAR232(bms_comm=FakeComm(jsd.SAMPLE_RESPONSES), data_refresh_interval=5)
results.append(raises("Write refused without option", PermissionError,
                      locked.set_setting, 'setting_output_priority', 'PV first'))
results.append(raises("Action refused without option", PermissionError, locked.run_action, 'power_off'))

# Writes: ACK + read-back, ranges, NAK, no answer
comm = FakeComm({**jsd.SAMPLE_RESPONSES, 'OPR01': 'ACK', 'TCCV56.0': 'ACK', 'TEO': 'ACK', 'SOFF': 'ACK',
                 'SPON2': 'ACK', 'DATE251203': 'ACK', 'TIME051203': 'ACK', 'CST01': 'NAK'})
inverter = jsd.JSDSOLAR232(bms_comm=comm, data_refresh_interval=5, allow_writes=True)
inverter.get_data()
comm.responses['OPR??'] = '(01'
results.append(check("Select write + read-back", inverter.set_setting('setting_output_priority', 'PV first'), 'PV first'))
results.append(check("Select write command", 'OPR01' in comm.sent, True))
results.append(check("48 V system detected", inverter.nominal_battery_voltage(), 48))
results.append(check("48 V CV range", inverter.setting_range('setting_cv_voltage'), (48.0, 62.0)))
comm.responses['TCCV????'] = '(56.0'
results.append(check("Number write + read-back", inverter.set_setting('setting_cv_voltage', 56.0), 56.0))
results.append(raises("CV voltage out of range", ValueError, inverter.set_setting, 'setting_cv_voltage', 70.0))
results.append(raises("Grid current out of range", ValueError, inverter.set_setting, 'setting_max_grid_charge_current', 200))
results.append(check("Out-of-range values not sent", 'TCCV70.0' in comm.sent or 'GCC200' in comm.sent, False))
results.append(raises("Unknown option", ValueError, inverter.set_setting, 'setting_output_priority', 'Nonsense'))
results.append(raises("NAK raises", ValueError, inverter.set_setting, 'setting_charge_mode', 'Forced 2-stage'))
comm.responses['TE?'] = '(ACDEHJOX'
results.append(check("Feature on + read-back", inverter.set_feature('feature_buzzer_mute', True), True))
results.append(check("Feature command", 'TEO' in comm.sent, True))
inverter.run_action('power_off')
inverter.run_action('power_on', unit=2)
inverter.run_action('sync_clock', now=datetime.datetime(2025, 12, 3, 5, 12, 3))
results.append(check("Control commands", [c for c in ('SOFF', 'SPON2', 'DATE251203', 'TIME051203') if c in comm.sent],
                     ['SOFF', 'SPON2', 'DATE251203', 'TIME051203']))
results.append(raises("Silent write raises", TimeoutError, inverter.run_action, 'reset_energy_counters'))
results.append(check("Calibration never sent", [c for c in comm.sent if c[:3] in ('BA0', 'B1A', 'B2A', 'PA0')], []))

# Debug log depth: each level adds its own records, off writes none of them
class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def log_messages(depth):
    capture = Capture()
    logger = logging.getLogger(jsd.__name__)
    logger.addHandler(capture)
    logger.setLevel(logging.DEBUG)
    try:
        jsd.JSDSOLAR232(bms_comm=FakeComm(jsd.SAMPLE_RESPONSES), data_refresh_interval=5, log_depth=depth).get_data()
    finally:
        logger.removeHandler(capture)
        logger.setLevel(logging.NOTSET)
    return capture.messages


def kinds(messages):
    return {kind for kind, prefix in (('cycle', 'Cycle '), ('tx', 'TX '), ('rx', 'RX '), ('parsed', 'Parsed '))
            if any(m.startswith(prefix) for m in messages)}


results.append(check("Log depth off", kinds(log_messages(jsd.LOG_OFF)), set()))
results.append(check("Log depth basic", kinds(log_messages(jsd.LOG_BASIC)), {'cycle'}))
results.append(check("Log depth protocol", kinds(log_messages(jsd.LOG_PROTOCOL)), {'cycle', 'tx', 'rx'}))
results.append(check("Log depth parsing", kinds(log_messages(jsd.LOG_PARSING)), {'cycle', 'tx', 'rx', 'parsed'}))
protocol_lines = log_messages(jsd.LOG_PROTOCOL)
results.append(check("RX line shows frame and time", any(m.startswith("RX '(B'") and m.endswith(' ms)') for m in protocol_lines), True))

print(f"\n{sum(results)}/{len(results)} checks passed")
raise SystemExit(0 if all(results) else 1)
