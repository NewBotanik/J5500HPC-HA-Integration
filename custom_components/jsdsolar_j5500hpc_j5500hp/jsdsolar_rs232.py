import logging
import random
import re
import threading
import time

# JSD SOLAR inverter (e.g. J5500HPC) over RS232: ASCII command/response, 2400 8N1, CR-terminated.
# Protocol reference: docs/protocols/protocol.JSDSOLAR.en.md. Polling sends queries only; settings and control commands
# are sent only on an explicit user action (HA number/select/switch/button). Calibration (§10) is never sent.


FAULT_CODES = {
    0: "No fault",
    1: "Bus soft-start failure",
    2: "Bus over-voltage",
    3: "Bus under-voltage",
    4: "DC/DC circuit fault",
    5: "Over-temperature",
    6: "Battery over-voltage",
    7: "Bus boost failure",
    8: "Bus short circuit",
    9: "Inverter soft-start failure",
    10: "Inverter over-voltage",
    11: "Inverter under-voltage",
    12: "Inverter short circuit",
    13: "Inverter reverse-power protection",
    14: "Overload fault",
    15: "Model mismatch fault",
    16: "Bootloader missing",
    17: "Firmware error",
    18: "PV over-current",
    19: "Duplicate serial number",
    20: "CAN communication failure",
    21: "Battery voltage difference too large",
    22: "Grid voltage difference too large",
    23: "Grid frequency difference too large",
    24: "Parallel output setting error",
    25: "Synchronisation lost",
    26: "Battery BMS fault",
}

OPERATING_MODES = {
    'P': "Power-on",
    'S': "Standby",
    'L': "Line",
    'B': "Battery",
    'F': "Fault",
    'D': "Shutdown",
    'X': "Test",
}

# GWS warning word 1 (b15..b0), reserved bits omitted
GWS_WARNINGS_1 = {
    15: "warning_generator_waveform_abnormal",
    14: "warning_low_battery_voltage_shutdown",
    13: "warning_eeprom_failure",
    12: "warning_low_power_discharge",
    11: "warning_fan_fault",
    9: "warning_over_temperature",
    7: "warning_charge_voltage_too_high",
    6: "warning_bms_lost",
    5: "warning_battery_cold_start_failure",
    4: "warning_battery_low_soc",
    3: "warning_low_soc_shutdown",
    2: "warning_charger_short_circuit",
    1: "warning_battery_not_connected",
    0: "warning_low_battery_voltage",
}

# GWS warning word 2 (c15..c0), reserved bits omitted
GWS_WARNINGS_2 = {
    15: "warning_parallel_settings_inconsistent",
    14: "warning_parallel_sync_lost",
    13: "warning_parallel_communication_fault",
    12: "warning_parallel_firmware_inconsistent",
    8: "warning_parallel_grid_mismatch",
    6: "warning_weak_pv_energy",
    4: "warning_overload",
}

# GPV warning bits (b15..b0), reserved bits omitted
GPV_WARNINGS = {
    11: "pv_warning_under_voltage",
    10: "pv_warning_charge_current_imbalance",
    9: "pv_warning_reverse_charge_current",
    8: "pv_warning_communication_lost",
    7: "pv_warning_charge_over_current",
    6: "pv_warning_channel_1_over_current",
    5: "pv_warning_channel_2_over_current",
    4: "pv_warning_channel_1_over_temperature",
    3: "pv_warning_channel_2_over_temperature",
    2: "pv_warning_battery_over_voltage",
    1: "pv_warning_battery_under_voltage",
    0: "pv_warning_over_voltage",
}

CHARGE_STAGES = {0: "Stopped", 1: "Constant current", 2: "Constant voltage", 3: "Float"}
PV_TRACKING_STATES = {0: "Standby", 1: "Ready", 2: "CV mode", 3: "MPPT"}
BATTERY_TYPES = {0: "Lead-acid (sealed)", 1: "Flooded", 2: "Lithium", 3: "User-defined"}
OUTPUT_PRIORITIES = {0: "Grid first", 1: "PV first", 2: "PV-Battery-Grid"}
OUTPUT_MODES = {0: "APP", 1: "UPS"}
CHARGER_PRIORITIES = {0: "Grid first", 1: "PV first", 2: "Grid and PV", 3: "PV only"}
CHARGE_MODES = {0: "Auto", 1: "Forced 2-stage", 2: "Forced 3-stage"}
PARALLEL_MODES = {0: "Standalone", 1: "Single-phase parallel", 2: "Three-phase R", 3: "Three-phase S", 4: "Three-phase T"}

FAN_FAULT_DETECTION = {0: "On", 1: "Off"}
OUTPUT_VOLTAGE_TYPES = {0: "High", 1: "Low (step-down transformer)"}
OUTPUT_VOLTAGES = {v: f"{v} V" for v in (100, 110, 115, 120, 127, 208, 220, 230, 240)}
FREQUENCIES = {50: "50 Hz", 60: "60 Hz"}
PANEL_VARIANTS = {0: "4-button LCD", 1: "3-button LCD"}
REMOTE_CONFIG_MODES = {0: "0", 1: "1"}


class Setting:
    """One §9 setting: write `<cmd><value>`, read back `<cmd>` + '?' × width (§3.3)."""

    def __init__(self, cmd, width, cast=int, options=None, unit='', icon='mdi:cog', device_class=None,
                 minimum=None, maximum=None, ranges=None, precision=None):
        self.cmd = cmd
        self.width = width
        self.cast = cast
        self.options = options
        self.unit = unit
        self.icon = icon
        self.device_class = device_class
        self.minimum = minimum
        self.maximum = maximum
        # Battery-voltage settings: {nominal battery voltage: (min, max)}
        self.ranges = ranges
        self.precision = precision if precision is not None else (1 if cast is float else 0)

    @property
    def read_command(self):
        return self.cmd + '?' * self.width

    def format(self, value):
        """Fixed-width, zero-padded parameter (§3.1)."""
        if self.cast is float:
            return f"{float(value):0{self.width}.1f}"
        return f"{int(value):0{self.width}d}"


def _v(cmd, ranges, icon='mdi:battery'):
    """Battery-voltage setting <nn.n> whose range depends on the 12/24/48 V system."""
    return Setting(cmd, 4, float, unit='V', icon=icon, device_class='voltage', ranges=ranges)


# entity key -> Setting. Keys shared with GCHG/GBAT fields hold the same value from both sources.
SETTINGS = {
    'setting_output_voltage': Setting('V', 3, options=OUTPUT_VOLTAGES, icon='mdi:power-socket-eu'),
    'setting_frequency': Setting('F', 2, options=FREQUENCIES, icon='mdi:sine-wave'),
    'setting_battery_type': Setting('TBAT', 1, options=BATTERY_TYPES, icon='mdi:battery-unknown'),
    'setting_max_charge_current': Setting('CHGC', 3, unit='A', icon='mdi:current-dc', device_class='current', minimum=10, maximum=120),
    'setting_cv_voltage': _v('TCCV', {12: (12.0, 15.5), 24: (28.0, 29.0), 48: (48.0, 62.0)}, 'mdi:battery-charging-high'),
    'setting_float_voltage': _v('TCFV', {12: (12.0, 15.5), 24: (26.6, 27.8), 48: (48.0, 62.0)}, 'mdi:battery-charging-medium'),
    'setting_second_output_cutoff_voltage': _v('TCDV', {12: (11.0, 15.0), 24: (22.0, 32.0), 48: (44.0, 60.0)}, 'mdi:power-plug-off'),
    'setting_eq_voltage': _v('TCQV', {12: (12.0, 15.0), 24: (24.0, 30.0), 48: (48.0, 60.0)}, 'mdi:battery-sync'),
    'setting_cv_time': Setting('TCVT', 4, unit='min', icon='mdi:timer-outline', device_class='duration', minimum=0, maximum=720),
    'setting_second_output_time': Setting('TDOT', 4, unit='min', icon='mdi:timer-outline', device_class='duration', minimum=0, maximum=895),
    'setting_eq_time': Setting('TCQT', 4, unit='min', icon='mdi:timer-outline', device_class='duration', minimum=5, maximum=900),
    'setting_eq_timeout': Setting('TCQO', 4, unit='min', icon='mdi:timer-outline', device_class='duration', minimum=5, maximum=900),
    'setting_eq_interval_hours': Setting('TCQI', 4, unit='h', icon='mdi:calendar-sync', device_class='duration', minimum=24, maximum=2160),
    'setting_battery_cutoff_voltage': _v('EOD', {12: (10.0, 12.0), 24: (20.0, 22.0), 48: (40.0, 48.0)}, 'mdi:battery-off'),
    'setting_battery_warning_voltage': _v('TBLV', {12: (10.5, 13.5), 24: (20.6, 22.6), 48: (42.0, 54.0)}, 'mdi:battery-alert'),
    'setting_low_power_discharge_minutes': Setting('LWDT', 4, unit='min', icon='mdi:timer-outline', device_class='duration', minimum=60, maximum=480),
    'setting_low_soc_shutdown': Setting('BSOCU', 3, unit='%', icon='mdi:battery-10', minimum=0, maximum=50),
    'setting_low_soc_to_grid': Setting('BSOCG', 3, unit='%', icon='mdi:battery-30', minimum=0, maximum=90),
    'setting_high_soc_to_battery': Setting('BSOCB', 3, unit='%', icon='mdi:battery-90', minimum=0, maximum=100),
    'setting_displayed_output_power': Setting('UP', 5, unit='VA', icon='mdi:monitor', device_class='apparent_power', minimum=0, maximum=5000),
    'setting_battery_to_grid_delay': Setting('LT', 3, unit='s', icon='mdi:timer-outline', device_class='duration', minimum=1, maximum=300),
    'setting_fan_fault_detection': Setting('FT', 1, options=FAN_FAULT_DETECTION, icon='mdi:fan-alert'),
    'setting_output_voltage_type': Setting('HV', 1, options=OUTPUT_VOLTAGE_TYPES, icon='mdi:transmission-tower'),
    'setting_grid_over_voltage_protection': Setting('OVP', 3, unit='V', icon='mdi:transmission-tower', device_class='voltage', minimum=264, maximum=280),
    # 90–154 V in APP mode, 170–200 V in UPS mode: the inverter NAKs the wrong half
    'setting_grid_under_voltage_protection': Setting('LVP', 3, unit='V', icon='mdi:transmission-tower', device_class='voltage', minimum=90, maximum=200),
    'setting_max_cc_charge_time': Setting('CI1', 2, unit='h', icon='mdi:timer-outline', device_class='duration', minimum=1, maximum=99),
    'setting_output_priority': Setting('OPR', 2, options=OUTPUT_PRIORITIES, icon='mdi:priority-high'),
    'setting_output_mode': Setting('OPM', 2, options=OUTPUT_MODES, icon='mdi:power-plug'),
    'setting_charger_priority': Setting('CPR', 2, options=CHARGER_PRIORITIES, icon='mdi:priority-high'),
    'setting_max_grid_charge_current': Setting('GCC', 3, unit='A', icon='mdi:current-ac', device_class='current', minimum=1, maximum=120),
    'setting_charge_mode': Setting('CST', 2, options=CHARGE_MODES, icon='mdi:battery-charging'),
    'setting_battery_back_to_grid_voltage': _v('BTG', {12: (11.0, 13.0), 24: (22.0, 26.0), 48: (44.0, 52.0)}, 'mdi:battery-arrow-down-outline'),
    # 00.0 = "at Float"; the 48 V default 54.0 is outside the stated range (§14 #17)
    'setting_battery_back_to_battery_voltage': _v('BTB', {12: (0.0, 14.5), 24: (0.0, 29.0), 48: (0.0, 54.0)}, 'mdi:battery-arrow-up-outline'),
    'setting_battery_over_voltage': _v('BTO', {12: (14.0, 16.0), 24: (28.0, 32.0), 48: (56.0, 61.0)}, 'mdi:battery-alert'),
    'setting_parallel_mode': Setting('PAR', 1, options=PARALLEL_MODES, icon='mdi:vector-link'),
    'setting_panel_variant': Setting('SW', 2, options=PANEL_VARIANTS, icon='mdi:gesture-tap-button'),
    'setting_remote_config_mode': Setting('CFG', 1, options=REMOTE_CONFIG_MODES, icon='mdi:remote'),
}
# Feature flags (§9.1): letter -> entity key suffix. 'W' is not defined.
FEATURE_FLAGS = {
    'A': 'lcd_return_to_default_page',
    'B': 'fast_grid_over_voltage_protection',
    'C': 'overload_auto_restart',
    'D': 'over_temperature_auto_restart',
    'E': 'buzzer_on_source_loss',
    'F': 'bms_interface_disabled',
    'G': 'overload_switch_to_grid',
    'H': 'auto_frequency_adaptation',
    'I': 'battery_power_saving',
    'J': 'start_auto_adaptation',
    'K': 'charger_allowed',
    'L': 'battery_not_connected_warning',
    'M': 'zero_crossing_phase_lock',
    'N': 'immediate_equalization',
    'O': 'buzzer_mute',
    'P': 'grid_feed_in',
    'Q': 'battery_equalization',
    'R': 'invert_screen_buttons',
    'S': 'bms_communication',
    'T': 'three_phase_combined_display',
    'U': 'low_power_discharge',
    'V': 'max_current_charge',
    'X': 'lcd_auto_off',
    'Y': 'relay_close_on_soft_start',
    'Z': 'fast_n_relay_close',
}
FEATURE_KEYS = {f"feature_{slug}": letter for letter, slug in FEATURE_FLAGS.items()}

# Operating state codes (§13.5): GPDAT and GFAIL use different numbers
GPDAT_STATES = {0: "Power-on", 1: "Shutdown", 2: "Fault", 3: "Standby", 4: "Line", 5: "Battery", 6: "Test"}
GFAIL_MODES = {0: "Power-on", 1: "Standby", 2: "Line", 3: "Battery", 4: "Fault", 5: "Shutdown", 6: "Test"}
DCDC_STATES = {0: "Idle", 1: "Charging", 2: "Discharging"}

# GPSTS status bits (§13.6–13.9), reserved and internal bits omitted
GPSTS_PFC = {14: "pfc_battery_under_voltage", 13: "pfc_memory_fault", 12: "pfc_low_power_discharge",
             11: "pfc_fan_fault", 9: "pfc_over_temperature", 7: "pfc_charge_over_current",
             6: "pfc_bms_communication_lost", 4: "pfc_phase_sequence_error", 1: "pfc_battery_circuit_open",
             0: "pfc_low_battery_voltage"}
GPSTS_INV = {15: "inv_parallel_setting_error", 14: "inv_parallel_sync_fault", 13: "inv_parallel_communication_fault",
             12: "inv_parallel_firmware_inconsistent", 8: "inv_wrong_grid_phase", 6: "inv_insufficient_pv_power",
             4: "inv_overload", 1: "inv_grid_frequency_lost", 0: "inv_grid_voltage_lost"}
GPSTS_GRID = {8: "grid_lost_generator", 3: "grid_ok", 2: "grid_waveform_lost", 1: "grid_frequency_lost",
              0: "grid_voltage_lost"}

PARALLEL_MAX_UNITS = 9


# entity_id -> (unit, icon, device_class, state_class, precision)
SENSORS = {
    # Mode and faults
    'operating_mode': ('', 'mdi:state-machine', None, None, None),
    'fault_code': ('', 'mdi:alert-circle', None, None, 0),
    'fault': ('', 'mdi:alert-circle', None, None, None),
    # Grid
    'grid_voltage': ('V', 'mdi:transmission-tower', 'voltage', 'measurement', 1),
    'grid_frequency': ('Hz', 'mdi:sine-wave', 'frequency', 'measurement', 2),
    'grid_energy_today': ('kWh', 'mdi:transmission-tower-import', 'energy', 'total_increasing', 2),
    'grid_energy_total': ('kWh', 'mdi:transmission-tower-import', 'energy', 'total_increasing', 2),
    'setting_grid_loss_high_voltage': ('V', 'mdi:transmission-tower', 'voltage', None, 1),
    'setting_grid_loss_low_voltage': ('V', 'mdi:transmission-tower', 'voltage', None, 1),
    'setting_grid_return_high_voltage': ('V', 'mdi:transmission-tower', 'voltage', None, 1),
    'setting_grid_return_low_voltage': ('V', 'mdi:transmission-tower', 'voltage', None, 1),
    'setting_grid_loss_high_frequency': ('Hz', 'mdi:sine-wave', 'frequency', None, 2),
    'setting_grid_loss_low_frequency': ('Hz', 'mdi:sine-wave', 'frequency', None, 2),
    # Output
    'output_voltage': ('V', 'mdi:power-socket-eu', 'voltage', 'measurement', 1),
    'output_frequency': ('Hz', 'mdi:sine-wave', 'frequency', 'measurement', 2),
    'output_current': ('A', 'mdi:current-ac', 'current', 'measurement', 2),
    'output_active_power': ('W', 'mdi:home-lightning-bolt', 'power', 'measurement', 0),
    'output_apparent_power': ('VA', 'mdi:home-lightning-bolt-outline', 'apparent_power', 'measurement', 0),
    'output_load': ('%', 'mdi:gauge', None, 'measurement', 0),
    'output_energy_today': ('kWh', 'mdi:home-export-outline', 'energy', 'total_increasing', 2),
    'output_energy_total': ('kWh', 'mdi:home-export-outline', 'energy', 'total_increasing', 2),
    # Inverter stage and bus
    'inverter_voltage': ('V', 'mdi:sine-wave', 'voltage', 'measurement', 1),
    'inverter_frequency': ('Hz', 'mdi:sine-wave', 'frequency', 'measurement', 2),
    'inverter_current': ('A', 'mdi:current-ac', 'current', 'measurement', 1),
    'bus_voltage': ('V', 'mdi:flash', 'voltage', 'measurement', 1),
    # Battery
    'battery_voltage': ('V', 'mdi:car-battery', 'voltage', 'measurement', 1),
    'battery_discharge_current': ('A', 'mdi:battery-arrow-down', 'current', 'measurement', 2),
    'battery_level': ('%', 'mdi:battery-70', 'battery', 'measurement', 0),
    'setting_battery_cells': ('', 'mdi:battery', None, None, 0),
    'setting_battery_cutoff_voltage': ('V', 'mdi:battery-off', 'voltage', None, 1),
    'setting_battery_warning_voltage': ('V', 'mdi:battery-alert', 'voltage', None, 1),
    # Charger
    'charge_voltage': ('V', 'mdi:battery-charging', 'voltage', 'measurement', 1),
    'charge_current': ('A', 'mdi:battery-arrow-up', 'current', 'measurement', 1),
    'charge_stage': ('', 'mdi:battery-charging-wireless', None, None, None),
    'setting_cv_voltage': ('V', 'mdi:battery-charging-high', 'voltage', None, 1),
    'setting_float_voltage': ('V', 'mdi:battery-charging-medium', 'voltage', None, 1),
    'setting_eq_voltage': ('V', 'mdi:battery-sync', 'voltage', None, 1),
    'setting_max_charge_current': ('A', 'mdi:current-dc', 'current', None, 0),
    'setting_cv_time': ('min', 'mdi:timer-outline', 'duration', None, 0),
    'setting_eq_time': ('min', 'mdi:timer-outline', 'duration', None, 0),
    'setting_eq_timeout': ('min', 'mdi:timer-outline', 'duration', None, 0),
    'setting_eq_interval': ('d', 'mdi:calendar-sync', 'duration', None, 0),
    'setting_eq_mode': ('', 'mdi:battery-sync', None, None, None),
    'setting_battery_type': ('', 'mdi:battery-unknown', None, None, None),
    'setting_low_power_discharge_time': ('h', 'mdi:timer-outline', 'duration', None, 0),
    # PV
    'pv_voltage': ('V', 'mdi:solar-panel', 'voltage', 'measurement', 1),
    'pv_current': ('A', 'mdi:solar-panel', 'current', 'measurement', 2),
    'pv_charge_current': ('A', 'mdi:solar-power', 'current', 'measurement', 2),
    'pv_power': ('W', 'mdi:solar-power-variant', 'power', 'measurement', 0),
    'pv_tracking_state': ('', 'mdi:solar-panel', None, None, None),
    'pv_energy_today': ('kWh', 'mdi:solar-power', 'energy', 'total_increasing', 2),
    'pv_energy_total': ('kWh', 'mdi:solar-power', 'energy', 'total_increasing', 2),
    # Temperatures
    'temperature_pv': ('°C', 'mdi:thermometer', 'temperature', 'measurement', 1),
    'temperature_charger': ('°C', 'mdi:thermometer', 'temperature', 'measurement', 1),
    'temperature_ambient': ('°C', 'mdi:thermometer', 'temperature', 'measurement', 1),
    'temperature_mppt_1': ('°C', 'mdi:thermometer', 'temperature', 'measurement', 1),
    'temperature_mppt_2': ('°C', 'mdi:thermometer', 'temperature', 'measurement', 1),
    # Fans
    'fan_speed_command': ('%', 'mdi:fan', None, 'measurement', 0),
    'fan_1_speed': ('', 'mdi:fan', None, 'measurement', 0),
    'fan_2_speed': ('', 'mdi:fan', None, 'measurement', 0),
    # BMS (via inverter)
    'bms_comm_state': ('', 'mdi:lan-connect', None, None, 0),
    'bms_state': ('', 'mdi:battery-check', None, None, 0),
    'bms_voltage': ('V', 'mdi:car-battery', 'voltage', 'measurement', 1),
    'bms_current': ('A', 'mdi:current-dc', 'current', 'measurement', 2),
    'bms_temperature': ('°C', 'mdi:thermometer', 'temperature', 'measurement', 1),
    'bms_soc': ('%', 'mdi:battery-70', 'battery', 'measurement', 1),
    'bms_remaining_capacity': ('Ah', 'mdi:battery-clock', None, 'measurement', 1),
    'bms_rated_capacity': ('Ah', 'mdi:battery-high', None, None, 1),
    'bms_fault_code': ('', 'mdi:alert', None, None, 0),
    'bms_warning_code': ('', 'mdi:alert-outline', None, None, 0),
    'bms_max_charge_current': ('A', 'mdi:current-dc', 'current', 'measurement', 2),
    'bms_cv_voltage': ('V', 'mdi:battery-charging-high', 'voltage', 'measurement', 1),
    # Identity
    'serial_number': ('', 'mdi:identifier', None, None, None),
    'firmware_version': ('', 'mdi:chip', None, None, None),
    'firmware_date': ('', 'mdi:calendar', None, None, None),
    'dsp_firmware_version': ('', 'mdi:chip', None, None, None),
    'rated_voltage': ('V', 'mdi:information-outline', 'voltage', None, 1),
    'rated_current': ('A', 'mdi:information-outline', 'current', None, 0),
    'rated_frequency': ('Hz', 'mdi:information-outline', 'frequency', None, 1),
    # Settings read back with '?' queries
    'setting_output_priority': ('', 'mdi:priority-high', None, None, None),
    'setting_output_mode': ('', 'mdi:power-plug', None, None, None),
    'setting_charger_priority': ('', 'mdi:priority-high', None, None, None),
    'setting_charge_mode': ('', 'mdi:battery-charging', None, None, None),
    'setting_parallel_mode': ('', 'mdi:vector-link', None, None, None),
    'setting_max_grid_charge_current': ('A', 'mdi:current-ac', 'current', None, 0),
    'setting_battery_back_to_grid_voltage': ('V', 'mdi:battery-arrow-down-outline', 'voltage', None, 1),
    'setting_battery_back_to_battery_voltage': ('V', 'mdi:battery-arrow-up-outline', 'voltage', None, 1),
    'setting_battery_over_voltage': ('V', 'mdi:battery-alert', 'voltage', None, 1),
    'setting_low_soc_shutdown': ('%', 'mdi:battery-10', None, None, 0),
    'setting_low_soc_to_grid': ('%', 'mdi:battery-30', None, None, 0),
    'setting_high_soc_to_battery': ('%', 'mdi:battery-90', None, None, 0),
    'setting_battery_to_grid_delay': ('s', 'mdi:timer-outline', 'duration', None, 0),
}

# Values from the slow query set
SENSORS.update({
    'setting_displayed_output_voltage': ('V', 'mdi:monitor', 'voltage', None, 0),
    'hours_since_equalization': ('h', 'mdi:calendar-clock', 'duration', 'measurement', 0),
    'inverter_date': ('', 'mdi:calendar', None, None, None),
    'inverter_time': ('', 'mdi:clock-outline', None, None, None),
    'last_fault_code': ('', 'mdi:alert-circle-outline', None, None, 0),
    'last_fault': ('', 'mdi:alert-circle-outline', None, None, None),
    'last_fault_mode': ('', 'mdi:state-machine', None, None, None),
    'parallel_unit_count': ('', 'mdi:vector-link', None, 'measurement', 0),
})
SENSORS.update({key: ('', 'mdi:alert-circle-outline', None, None, None) for key in (
    'last_fault_active_power_raw', 'last_fault_grid_voltage_raw', 'last_fault_grid_frequency_raw',
    'last_fault_inverter_voltage_raw', 'last_fault_field_7_raw', 'last_fault_inverter_frequency_raw',
    'last_fault_inverter_current_raw', 'last_fault_bus_voltage_raw', 'last_fault_battery_voltage_raw',
    'last_fault_charge_current_raw', 'last_fault_inv1_temperature_raw', 'last_fault_calibration_reset_bits',
    'last_fault_battery_pfc_state', 'last_fault_grid_pfc_state', 'last_fault_inv_state',
    'last_fault_dcdc_mode', 'last_fault_adc_state', 'last_fault_inverter_dc_sample',
    'last_fault_ambient_temperature_raw',
    'fault_bits_battery', 'fault_bits_grid', 'fault_bits_pfc', 'fault_bits_inverter_1', 'fault_bits_inverter_2',
)})
# Every §9 setting gets sensor metadata for read-only mode
for _key, _setting in SETTINGS.items():
    SENSORS.setdefault(_key, (_setting.unit, _setting.icon, _setting.device_class, None,
                              None if _setting.options else _setting.precision))

# Per-unit values of a parallel system: key 'parallel_<n>_<field>'
PARALLEL_SENSORS = {
    'state': ('', 'mdi:state-machine', None, None, None),
    'firmware_version': ('', 'mdi:chip', None, None, None),
    'parallel_mode': ('', 'mdi:vector-link', None, None, None),
    'fault_code': ('', 'mdi:alert-circle', None, None, 0),
    'fault': ('', 'mdi:alert-circle', None, None, None),
    'inverter_voltage': ('V', 'mdi:sine-wave', 'voltage', 'measurement', 1),
    'inverter_frequency': ('Hz', 'mdi:sine-wave', 'frequency', 'measurement', 2),
    'grid_voltage': ('V', 'mdi:transmission-tower', 'voltage', 'measurement', 1),
    'grid_frequency': ('Hz', 'mdi:sine-wave', 'frequency', 'measurement', 2),
    'output_voltage': ('V', 'mdi:power-socket-eu', 'voltage', 'measurement', 1),
    'output_frequency': ('Hz', 'mdi:sine-wave', 'frequency', 'measurement', 2),
    'output_current': ('A', 'mdi:current-ac', 'current', 'measurement', 2),
    'battery_voltage': ('V', 'mdi:car-battery', 'voltage', 'measurement', 1),
    'battery_current': ('A', 'mdi:current-dc', 'current', 'measurement', 1),
    'output_load': ('%', 'mdi:gauge', None, 'measurement', 0),
    'output_apparent_power': ('VA', 'mdi:home-lightning-bolt-outline', 'apparent_power', 'measurement', 0),
    'output_active_power': ('W', 'mdi:home-lightning-bolt', 'power', 'measurement', 0),
    'battery_capacity': ('%', 'mdi:battery-70', 'battery', 'measurement', 0),
    'pv_voltage': ('V', 'mdi:solar-panel', 'voltage', 'measurement', 1),
    'pv_charge_current': ('A', 'mdi:solar-power', 'current', 'measurement', 1),
    'pv_power': ('W', 'mdi:solar-power-variant', 'power', 'measurement', 0),
    'temperature': ('°C', 'mdi:thermometer', 'temperature', 'measurement', 1),
    'dcdc_state': ('', 'mdi:battery-sync', None, None, None),
    'id': ('', 'mdi:identifier', None, None, None),
}
_PARALLEL_KEY = re.compile(r'parallel_(\d)_(.+)')


def sensor_meta(key):
    """(unit, icon, device_class, state_class, precision) for a value key, or None if unknown."""
    if key in SENSORS:
        return SENSORS[key]
    match = _PARALLEL_KEY.fullmatch(key)
    return PARALLEL_SENSORS.get(match.group(2)) if match else None


# BMS values that are not defined are sent as 32767 (§11.2)
BMS_UNDEFINED = 32767
BMS_LINK_LOST = (0x8000, 8000)

# Sample frames used when if_random is enabled (no inverter attached)
SAMPLE_RESPONSES = {
    'GMOD': '(B',
    'GWS': '(00 0000000000000000 0000000000000000',
    'GLINE': '(229.8 50.01 264.0 154.0 255.0 163.0 70.00 40.00 00012 034 00125 00001 04321',
    'GOP': '(230.1 50.00 007.85 00.00 01650 00000 01805 00000 00000 034 00000 00000 00410 00002 01234',
    'GINV': '(230.0 50.00 007.9',
    'GBUS': '( 361.0 360.0 360.0',
    'GBAT': '(052.4 031.50 16 42.0 44.0',
    'BL': 'BL078',
    'GCHG': '(361.0 053.2 16 000.0 000.00 000.00 56.4 54.0 58.4 060.00 0120 030 060 030 0 2 8 1 000.00 000.00 000.00 000.0 0',
    'GPV': '(310.5 052.4 18.20 03.10 00960 03 1 0 000.0 000.0 000.0 000.0 000.0 00 00000 00000 0000 0000 0000 0000 00340 00000 21987 0000000000000000',
    'GTMP': '(041.5 038.0 029.5 040.0 039.5',
    'FAN???': '(050 00020 00020 0 0',
    'GBMS': '(00001 00000 00524 -1250 00255 00780 00780 01000 00000 00000 06000 00560 32767 32767 32767 32767 32767',
    'I': '#J5500HPC2024010100000000001R1.4.001  ',
    'SVFW': '(4.001 (20211105',
    'F': '#230.0 024 048.0 50.0',
    'OPR??': '(02',
    'OPM??': '(00',
    'CPR??': '(01',
    'CST??': '(00',
    'PAR?': '(0',
    'GCC???': '(030',
    'BTG????': '(46.0',
    'BTB????': '(54.0',
    'BTO????': '(61.0',
    'BSOCU???': '(020',
    'BSOCG???': '(050',
    'BSOCB???': '(090',
    'LT???': '(005',
    'V???': '(230 230',
    'TBAT?': '(2',
    'CHGC???': '(060',
    'TCCV????': '(56.4',
    'TCFV????': '(54.0',
    'TCDV????': '(48.0',
    'TCQV????': '(58.4',
    'TCVT????': '(0120',
    'TDOT????': '(0000',
    'TCQT????': '(0030',
    'TCQO????': '(0060',
    'TCQI????': '(0720',
    'EOD????': '(42.0',
    'TBLV????': '(44.0',
    'LWDT????': '(0480',
    'UP?????': '(05000',
    'FT?': '(0',
    'HV?': '(0',
    'OVP???': '(264',
    'LVP???': '(154',
    'CI1??': '(12',
    'SW??': '(00',
    'CFG?': '(0',
    'TE?': '(ACDEHJX',
    'TCQN????': '0123',
    'DATE??????': '25 12 03',
    'TIME??????': '05 12 03',
    'GFAIL': '(14 03 01650 2300 5000 2300 00.00 5000 0078 3610 0524 0000 0415 000 00000 00000 00000 0 00000 00000 00295',
    'GCF': '( BT0000000000000000 RL0000000000000000 P100000000000000000 I10000000000000000 I20000000000000000 ',
}


def _tokens(response, prefix='('):
    """Strip the frame prefix and split on runs of whitespace (§4.2)."""
    if response is None:
        return None
    text = response.strip()
    if prefix and text.startswith(prefix):
        text = text[len(prefix):]
    return text.split()


def _num(tokens, index, cast=float):
    """Positional field as a number, or None when missing or malformed."""
    try:
        return cast(tokens[index])
    except (IndexError, ValueError, TypeError):
        return None


def _bits(tokens, index):
    """16-character 0/1 string -> {bit: bool}; the leftmost character is bit 15."""
    try:
        word = tokens[index]
    except (IndexError, TypeError):
        return None
    if len(word) != 16 or set(word) - {'0', '1'}:
        return None
    return {bit: word[15 - bit] == '1' for bit in range(16)}


def _energy_kwh(ext, low):
    """32-bit counter split in two decimal words, unit 10 Wh (§4.3)."""
    if ext is None or low is None:
        return None
    return round((ext * 65536 + low) * 10 / 1000, 2)


def _daily_kwh(value):
    return None if value is None else round(value * 10 / 1000, 2)


def _enum(mapping, value):
    if value is None:
        return None
    return mapping.get(value, f"Unknown ({value})")


def _bms_value(tokens, index, scale, signed=False):
    raw = _num(tokens, index, int)
    if raw is None or raw == BMS_UNDEFINED:
        return None
    if signed and raw > BMS_UNDEFINED:
        raw -= 65536
    return round(raw * scale, 3)


def parse_gmod(response):
    tokens = _tokens(response)
    if not tokens:
        return None
    code = tokens[0][0]
    return {'operating_mode': OPERATING_MODES.get(code, f"Unknown ({code})")}


def parse_gws(response):
    tokens = _tokens(response)
    code = _num(tokens, 0, int) if tokens else None
    if code is None:
        return None
    data = {'fault_code': code, 'fault': FAULT_CODES.get(code, f"Unknown fault ({code})")}
    warnings = {}
    for index, names in ((1, GWS_WARNINGS_1), (2, GWS_WARNINGS_2)):
        bits = _bits(tokens, index)
        if bits is not None:
            for bit, name in names.items():
                warnings[name] = bits[bit]
    return data, warnings


def parse_gline(response):
    t = _tokens(response)
    if not t:
        return None
    return {
        'grid_voltage': _num(t, 0),
        'grid_frequency': _num(t, 1),
        'setting_grid_loss_high_voltage': _num(t, 2),
        'setting_grid_loss_low_voltage': _num(t, 3),
        'setting_grid_return_high_voltage': _num(t, 4),
        'setting_grid_return_low_voltage': _num(t, 5),
        'setting_grid_loss_high_frequency': _num(t, 6),
        'setting_grid_loss_low_frequency': _num(t, 7),
        'grid_energy_today': _daily_kwh(_num(t, 10, int)),
        'grid_energy_total': _energy_kwh(_num(t, 11, int), _num(t, 12, int)),
    }


def parse_gop(response):
    t = _tokens(response)
    if not t:
        return None
    return {
        'output_voltage': _num(t, 0),
        'output_frequency': _num(t, 1),
        'output_current': _num(t, 2),
        'output_active_power': _num(t, 4, int),
        'output_apparent_power': _num(t, 6, int),
        'output_load': _num(t, 9, int),
        'output_energy_today': _daily_kwh(_num(t, 12, int)),
        'output_energy_total': _energy_kwh(_num(t, 13, int), _num(t, 14, int)),
    }


def parse_ginv(response):
    t = _tokens(response)
    if not t:
        return None
    return {
        'inverter_voltage': _num(t, 0),
        'inverter_frequency': _num(t, 1),
        'inverter_current': _num(t, 2),
    }


def parse_gbus(response):
    t = _tokens(response)
    if not t:
        return None
    return {'bus_voltage': _num(t, 0)}


def parse_gbat(response):
    t = _tokens(response)
    if not t:
        return None
    return {
        'battery_voltage': _num(t, 0),
        'battery_discharge_current': _num(t, 1),
        'setting_battery_cells': _num(t, 2, int),
        'setting_battery_cutoff_voltage': _num(t, 3),
        'setting_battery_warning_voltage': _num(t, 4),
    }


def parse_bl(response):
    if response is None or not response.startswith('BL'):
        return None
    level = _num([response[2:].strip()], 0, int)
    if level is None:
        return None
    return {'battery_level': level}


def parse_gchg(response):
    t = _tokens(response)
    if not t:
        return None
    eq_mode = _num(t, 14, int)
    return {
        'charge_voltage': _num(t, 1),
        'charge_current': _num(t, 3),
        'setting_cv_voltage': _num(t, 6),
        'setting_float_voltage': _num(t, 7),
        'setting_eq_voltage': _num(t, 8),
        'setting_max_charge_current': _num(t, 9),
        'setting_cv_time': _num(t, 10, int),
        'setting_eq_time': _num(t, 11, int),
        'setting_eq_timeout': _num(t, 12, int),
        'setting_eq_interval': _num(t, 13, int),
        'setting_eq_mode': None if eq_mode is None else ("On" if eq_mode == 1 else "Off"),
        'setting_battery_type': _enum(BATTERY_TYPES, _num(t, 15, int)),
        'setting_low_power_discharge_time': _num(t, 16, int),
        'charge_stage': _enum(CHARGE_STAGES, _num(t, 17, int)),
    }


def parse_gpv(response):
    t = _tokens(response)
    if not t:
        return None
    charging_possible = _num(t, 6, int)
    data = {
        'pv_voltage': _num(t, 0),
        'pv_charge_current': _num(t, 2),
        'pv_current': _num(t, 3),
        'pv_power': _num(t, 4, int),
        'pv_tracking_state': _enum(PV_TRACKING_STATES, _num(t, 5, int)),
        'pv_energy_today': _daily_kwh(_num(t, 20, int)),
        'pv_energy_total': _energy_kwh(_num(t, 21, int), _num(t, 22, int)),
    }
    flags = {}
    if charging_possible is not None:
        flags['pv_charging_possible'] = charging_possible == 1
    bits = _bits(t, 23)
    if bits is not None:
        for bit, name in GPV_WARNINGS.items():
            flags[name] = bits[bit]
    return data, flags


def parse_gtmp(response):
    t = _tokens(response)
    if not t:
        return None
    return {
        'temperature_pv': _num(t, 0),
        'temperature_charger': _num(t, 1),
        'temperature_ambient': _num(t, 2),
        'temperature_mppt_1': _num(t, 3),
        'temperature_mppt_2': _num(t, 4),
    }


def parse_fan(response):
    # The template has 3 fields, the example 5; the 5-field layout is used (§14 #2)
    t = _tokens(response)
    if not t:
        return None
    data = {
        'fan_speed_command': _num(t, 0, int),
        'fan_1_speed': _num(t, 1, int),
        'fan_2_speed': _num(t, 2, int),
    }
    flags = {}
    for index, name in ((3, 'fan_1_fault'), (4, 'fan_2_fault')):
        value = _num(t, index, int)
        if value is not None:
            flags[name] = value == 1
    return data, flags


def parse_gbms(response):
    t = _tokens(response)
    comm_state = _num(t, 0, int) if t else None
    if comm_state is None:
        return None
    data = {'bms_comm_state': comm_state, 'bms_state': _num(t, 1, int)}
    if comm_state == 0 or comm_state in BMS_LINK_LOST:
        # Initialisation or link lost: the remaining fields are not valid
        return data
    data.update({
        'bms_voltage': _bms_value(t, 2, 0.1),
        'bms_current': _bms_value(t, 3, 0.01, signed=True),
        'bms_temperature': _bms_value(t, 4, 0.1, signed=True),
        'bms_soc': _bms_value(t, 5, 0.1),  # spec says 0.1 Ah, treated as 0.1 % (§14 #12)
        'bms_remaining_capacity': _bms_value(t, 6, 0.1),
        'bms_rated_capacity': _bms_value(t, 7, 0.1),
        'bms_fault_code': _bms_value(t, 8, 1),
        'bms_warning_code': _bms_value(t, 9, 1),
        'bms_max_charge_current': _bms_value(t, 10, 0.01),
        'bms_cv_voltage': _bms_value(t, 11, 0.1),
    })
    return data


def parse_i(response):
    # '#' + 27-character serial number + 'R1.' + DSP version; parsed by offsets (§8.25)
    if response is None or not response.startswith('#'):
        return None
    body = response[1:]
    serial_number = body[:27].strip()
    if not serial_number:
        return None
    data = {'serial_number': serial_number}
    rest = body[27:].strip()
    if rest.startswith('R1.'):
        rest = rest[3:]
    if rest:
        data['dsp_firmware_version'] = rest
    return data


def parse_svfw(response):
    t = _tokens(response)
    if not t:
        return None
    data = {'firmware_version': t[0]}
    if len(t) > 1:
        date = t[1].lstrip('(')
        if len(date) == 8 and date.isdigit():
            data['firmware_date'] = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    return data


def parse_f(response):
    t = _tokens(response, prefix='#')
    if not t:
        return None
    return {
        'rated_voltage': _num(t, 0),
        'rated_current': _num(t, 1, int),
        'rated_frequency': _num(t, 3),
    }


def parse_setting(key, response):
    """Read-back of one §9 setting -> {key: value}; select-type settings return their label."""
    setting = SETTINGS[key]
    t = _tokens(response)
    value = _num(t, 0, setting.cast) if t else None
    if value is None:
        return None
    data = {key: _enum(setting.options, value) if setting.options else value}
    if key == 'setting_output_voltage':
        # V??? -> (actual displayed), e.g. (220 120 (§9.4)
        data['setting_displayed_output_voltage'] = _num(t, 1, int)
    return data


def parse_features(response):
    """TE? -> letters of the enabled feature flags (§9.1); None if the reply is not a letter list."""
    t = _tokens(response)
    if t is None:
        return None
    text = ''.join(t)
    if not all(c.isalpha() for c in text):
        return None
    enabled = set(text.upper())
    return {f"feature_{slug}": letter in enabled for letter, slug in FEATURE_FLAGS.items()}


def _bare_numbers(response, count):
    """Bare frame without '(' (TCQN, DATE, TIME): `count` integer tokens."""
    t = _tokens(response)
    if not t or len(t) < count:
        return None
    values = [_num(t, i, int) for i in range(count)]
    return None if None in values else values


def parse_tcqn(response):
    values = _bare_numbers(response, 1)
    return {'hours_since_equalization': values[0]} if values else None


def parse_date(response):
    values = _bare_numbers(response, 3)
    return {'inverter_date': f"20{values[0]:02d}-{values[1]:02d}-{values[2]:02d}"} if values else None


def parse_time(response):
    values = _bare_numbers(response, 3)
    return {'inverter_time': f"{values[0]:02d}:{values[1]:02d}:{values[2]:02d}"} if values else None


# GFAIL fields from index 2 on; the spec gives no scale factors, so they stay raw (§8.21)
GFAIL_RAW_FIELDS = (
    'last_fault_active_power_raw', 'last_fault_grid_voltage_raw', 'last_fault_grid_frequency_raw',
    'last_fault_inverter_voltage_raw', 'last_fault_field_7_raw', 'last_fault_inverter_frequency_raw',
    'last_fault_inverter_current_raw', 'last_fault_bus_voltage_raw', 'last_fault_battery_voltage_raw',
    'last_fault_charge_current_raw', 'last_fault_inv1_temperature_raw', 'last_fault_calibration_reset_bits',
    'last_fault_battery_pfc_state', 'last_fault_grid_pfc_state', 'last_fault_inv_state',
    'last_fault_dcdc_mode', 'last_fault_adc_state', 'last_fault_inverter_dc_sample',
    'last_fault_ambient_temperature_raw',
)


def parse_gfail(response):
    t = _tokens(response)
    code = _num(t, 0, int) if t else None
    if code is None:
        return None
    data = {
        'last_fault_code': code,
        'last_fault': FAULT_CODES.get(code, f"Unknown fault ({code})"),
    }
    if code == 0:
        # No fault recorded: the snapshot fields hold no meaningful values
        return data
    data['last_fault_mode'] = _enum(GFAIL_MODES, _num(t, 1, int))
    for offset, key in enumerate(GFAIL_RAW_FIELDS, start=2):
        data[key] = _num(t, offset, float if key == 'last_fault_field_7_raw' else int)
    return data


GCF_TAGS = {'BT': 'fault_bits_battery', 'RL': 'fault_bits_grid', 'P1': 'fault_bits_pfc',
            'I1': 'fault_bits_inverter_1', 'I2': 'fault_bits_inverter_2'}


def parse_gcf(response):
    """GCF -> raw bit strings per tag; parsed by tag, not length (P1 has 17 bits, §14 #18)."""
    t = _tokens(response)
    if not t:
        return None
    data = {}
    for token in t:
        key = GCF_TAGS.get(token[:2])
        bits = token[2:]
        if key and bits and not set(bits) - {'0', '1'}:
            data[key] = bits
    return data or None


def parse_gpdat(unit, response):
    """GPDAT<n> -> (data, flags); with the link lost the other fields are invalid (§8.18)."""
    t = _tokens(response)
    ok = _num(t, 0, int) if t else None
    if ok is None:
        return None
    p = f"parallel_{unit}_"
    flags = {p + 'communication_ok': ok == 1}
    if ok != 1:
        return {}, flags
    fault_code = _num(t, 4, int)
    data = {
        p + 'state': _enum(GPDAT_STATES, _num(t, 1, int)),
        p + 'firmware_version': t[2] if len(t) > 2 else None,
        p + 'parallel_mode': _enum(PARALLEL_MODES, _num(t, 3, int)),
        p + 'fault_code': fault_code,
        p + 'fault': None if fault_code is None else FAULT_CODES.get(fault_code, f"Unknown fault ({fault_code})"),
        p + 'inverter_voltage': _num(t, 5),
        p + 'inverter_frequency': _num(t, 6),
        p + 'grid_voltage': _num(t, 7),
        p + 'grid_frequency': _num(t, 8),
        p + 'output_voltage': _num(t, 9),
        p + 'output_frequency': _num(t, 10),
        p + 'output_current': _num(t, 11),
        p + 'battery_voltage': _num(t, 12),
        p + 'battery_current': _num(t, 13),
        p + 'output_load': _num(t, 14, int),
        p + 'output_apparent_power': _num(t, 15, int),
        p + 'output_active_power': _num(t, 16, int),
        p + 'battery_capacity': _num(t, 17, int),
        p + 'pv_voltage': _num(t, 18),
        p + 'pv_charge_current': _num(t, 19),
        p + 'pv_power': _num(t, 20, int),
        p + 'temperature': _num(t, 21),
    }
    return data, flags


def parse_gpsts(unit, page, response):
    """GPSTS<n><m> -> (data, flags) for status page m = 0 or 1 (§8.19)."""
    t = _tokens(response)
    ok = _num(t, 0, int) if t else None
    if ok is None:
        return None
    if ok != 1:
        return {}, {}
    p = f"parallel_{unit}_"
    data, flags = {}, {}
    first, second = _bits(t, 1), _bits(t, 2)
    if page == 0:
        for bits, names in ((first, GPSTS_PFC), (second, GPSTS_INV)):
            if bits is not None:
                flags.update({p + name: bits[bit] for bit, name in names.items()})
    else:
        if first is not None:
            flags.update({p + name: first[bit] for bit, name in GPSTS_GRID.items()})
        if second is not None:
            dcdc = (second[3] << 2) | (second[2] << 1) | int(second[1])
            data[p + 'dcdc_state'] = _enum(DCDC_STATES, dcdc)
            flags[p + 'pv_charging_allowed'] = second[0]
    return data, flags


def parse_gpid(unit, response):
    t = _tokens(response)
    if not t or _num(t, 0, int) != 1 or len(t) < 4:
        return None
    return {f"parallel_{unit}_id": '-'.join(t[1:4])}


def parse_gppv(response):
    """GPPV<n> -> unit count and PV voltage/charge current per unit, ordered by device ID (§8.23)."""
    t = _tokens(response)
    count = _num(t, 0, int) if t else None
    if count is None:
        return None
    data = {'parallel_unit_count': count}
    for unit in range(1, count + 1):
        data[f"parallel_{unit}_pv_voltage"] = _num(t, 2 * unit - 1)
        data[f"parallel_{unit}_pv_charge_current"] = _num(t, 2 * unit)
    return data


# Fast poll set (§4.5): command -> parser. Parsers marked as split return (data, flags).
FAST_QUERIES = (
    ('GMOD', parse_gmod, False),
    ('GWS', parse_gws, True),
    ('GLINE', parse_gline, False),
    ('GOP', parse_gop, False),
    ('GINV', parse_ginv, False),
    ('GBUS', parse_gbus, False),
    ('GBAT', parse_gbat, False),
    ('BL', parse_bl, False),
    ('GCHG', parse_gchg, False),
    ('GTMP', parse_gtmp, False),
    ('GBMS', parse_gbms, False),
    ('GPV', parse_gpv, True),
    ('FAN???', parse_fan, True),
)

IDENTITY_QUERIES = (('I', parse_i), ('SVFW', parse_svfw), ('F', parse_f))

# Control commands (§7, §9.3) behind buttons; SPON/SPOFF take the parallel unit number
ACTIONS = {
    'power_on': 'SON',
    'power_off': 'SOFF',
    'reset_energy_counters': 'Q',
    'factory_reset': 'ED1',
}
PARALLEL_ACTIONS = {'power_on': 'SPON', 'power_off': 'SPOFF'}

# Binary sensors that report a problem when on; the rest are plain states
PROBLEM_FLAGS_PREFIXES = ('warning_', 'pv_warning_')
PROBLEM_FLAGS = ('fan_1_fault', 'fan_2_fault')
PROBLEM_FLAG_MARKERS = ('_pfc_', '_inv_', '_lost')


def is_problem_flag(key):
    return key.startswith(PROBLEM_FLAGS_PREFIXES) or key in PROBLEM_FLAGS or any(m in key for m in PROBLEM_FLAG_MARKERS)


# Debug log depth (options flow): what the driver writes to the HA log
LOG_OFF = 0
LOG_BASIC = 1      # cycle summary, identity, writes
LOG_PROTOCOL = 2   # + every frame sent and received, with response time
LOG_PARSING = 3    # + parsed values of every command


class JSDSOLAR232:
    """JSD SOLAR inverter driver for the HA coordinator.

    Polling only sends queries. Writes happen only through set_setting / set_feature / run_action,
    which the HA entities call on a user action, and only when allow_writes is set.
    Calibration commands (§10) are never sent.
    """

    # Keep the last good frame of a command for this many failed cycles
    MAX_FAILURES = 3
    # A fast command that keeps failing is retried only once per this many cycles
    BACKOFF_CYCLES = 30
    # Slow queries (settings, flags, clock, fault snapshot, parallel units) read per cycle
    SLOW_PER_CYCLE = 3
    # A slow query that keeps failing is retried only once per this many rounds of the slow queue
    SLOW_BACKOFF_ROUNDS = 10

    def __init__(self, bms_comm, data_refresh_interval, debug=0, if_random=0, allow_writes=False,
                 log_depth=LOG_OFF):
        self.bms_comm = bms_comm
        self.log_depth = log_depth
        self.data_refresh_interval = data_refresh_interval
        self.if_random = if_random
        self.allow_writes = allow_writes
        self.cycle = 0
        self.identity = {}
        self.settings = {}
        self.slow_data = {}
        self.slow_flags = {}
        self.parallel_units = set()
        self._battery_voltage = None
        self._last = {}
        self._failures = {}
        self._slow_failures = {}
        self._slow_queue = []
        self._slow_round = 0
        # One request on the wire at a time: polling and writes run in different executor threads
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

    # --- Transport ---------------------------------------------------------------------------

    def _exchange(self, command):
        """Send one command, return the raw reply line ('' or None when silent)."""
        with self._lock:
            started = time.monotonic()
            if self.log_depth >= LOG_PROTOCOL:
                self.logger.debug("TX %r", f"{command}\r")
            if self.if_random:
                response = self._sample_response(command)
            else:
                # Drop stale bytes, e.g. the second CR that SVFW may send (§14 #14)
                self.bms_comm.flush()
                if not self.bms_comm.send_data(f"{command}\r"):
                    if self.log_depth >= LOG_PROTOCOL:
                        self.logger.debug("TX %s failed: link down", command)
                    return None
                response = self.bms_comm.receive_data()
            if self.log_depth >= LOG_PROTOCOL:
                elapsed_ms = (time.monotonic() - started) * 1000
                if response:
                    self.logger.debug("RX %r (%.0f ms)", response, elapsed_ms)
                else:
                    self.logger.debug("RX nothing for %s (%.0f ms)", command, elapsed_ms)
            return response

    def query(self, command):
        """Send one query and return the response line, or None on timeout/NAK."""
        response = self._exchange(command)
        if not response:
            self.logger.debug("%s: no response", command)
            return None
        if response == 'NAK':
            self.logger.debug("%s: NAK", command)
            return None
        self.logger.debug("%s: %s", command, response)
        return response

    def _parse(self, command, parser, response):
        """Run a parser on a reply; at LOG_PARSING depth log what came out."""
        parsed = parser(response)
        if self.log_depth >= LOG_PARSING:
            if parsed:
                self.logger.debug("Parsed %s: %s", command, parsed)
            elif response:
                self.logger.debug("Parsed %s: nothing usable in %r", command, response)
        return parsed

    def _sample_response(self, command):
        response = SAMPLE_RESPONSES.get(command)
        if command == 'GPV' and response:
            # Vary the PV power so that the HA history is not flat
            response = response.replace('00960', f"{random.randint(500, 3500):05d}")
        return response

    # --- Polling -----------------------------------------------------------------------------

    def _due(self, command):
        """Skip commands that keep failing, except for an occasional retry."""
        failures = self._failures.get(command, 0)
        return failures <= self.MAX_FAILURES or self.cycle % self.BACKOFF_CYCLES == 0

    def _poll(self, command, parser):
        """Parsed result of one command, or the cached one while failures are few."""
        if not self._due(command):
            return None
        parsed = self._parse(command, parser, self.query(command))
        if parsed:
            self._failures[command] = 0
            self._last[command] = parsed
            return parsed
        failures = self._failures.get(command, 0) + 1
        self._failures[command] = failures
        if failures == self.MAX_FAILURES + 1:
            self.logger.warning("Inverter does not answer %s, polling it less often", command)
        if failures <= self.MAX_FAILURES:
            return self._last.get(command)
        self._last.pop(command, None)
        return None

    def update_identity(self):
        """Serial number, firmware and rated data; retried until the inverter answers."""
        for command, parser in IDENTITY_QUERIES:
            parsed = self._parse(command, parser, self.query(command))
            if parsed:
                self.identity.update(parsed)
                if command == 'F':
                    self._store_frequency(parsed)
        if self.identity:
            self.logger.info("Inverter identity: %s", self.identity)
        else:
            self.logger.warning("Could not read inverter identity (I/SVFW/F)")

    def _store_frequency(self, parsed):
        # The F<nn> setting is read back through the rated-data query F (§9.5)
        frequency = parsed.get('rated_frequency')
        if frequency is not None:
            self.settings['setting_frequency'] = _enum(FREQUENCIES, int(round(frequency)))

    def _read_setting(self, key):
        if key == 'setting_frequency':
            parsed = self._parse('F', parse_f, self.query('F'))
            if parsed:
                self._store_frequency(parsed)
            return bool(parsed)
        command = SETTINGS[key].read_command
        parsed = self._parse(command, lambda r: parse_setting(key, r), self.query(command))
        if parsed:
            self.settings.update({k: v for k, v in parsed.items() if v is not None})
        return bool(parsed)

    def _read_features(self):
        parsed = self._parse('TE?', parse_features, self.query('TE?'))
        if parsed:
            self.slow_flags.update(parsed)
        return bool(parsed)

    def _read_into_slow_data(self, command, parser):
        parsed = self._parse(command, parser, self.query(command))
        if not parsed:
            return False
        data, flags = parsed if isinstance(parsed, tuple) else (parsed, {})
        self.slow_data.update({k: v for k, v in data.items() if v is not None})
        self.slow_flags.update(flags)
        return True

    def _read_gfail(self):
        parsed = self._parse('GFAIL', parse_gfail, self.query('GFAIL'))
        if not parsed:
            return False
        # Drop the previous snapshot: with fault code 0 its fields are not sent again
        for key in ('last_fault_mode',) + GFAIL_RAW_FIELDS:
            self.slow_data.pop(key, None)
        self.slow_data.update({k: v for k, v in parsed.items() if v is not None})
        return True

    def _read_parallel_unit(self, unit):
        found = self._read_into_slow_data(f"GPDAT{unit}", lambda r: parse_gpdat(unit, r))
        if self.slow_flags.get(f"parallel_{unit}_communication_ok"):
            self.parallel_units.add(unit)
        return found

    def _parallel_mode(self):
        mode = self.settings.get('setting_parallel_mode')
        return mode is not None and mode != PARALLEL_MODES[0]

    def _build_slow_queue(self):
        items = [(f"setting:{key}", lambda k=key: self._read_setting(k)) for key in SETTINGS]
        items += [
            ('TE?', self._read_features),
            ('TCQN????', lambda: self._read_into_slow_data('TCQN????', parse_tcqn)),
            ('DATE??????', lambda: self._read_into_slow_data('DATE??????', parse_date)),
            ('TIME??????', lambda: self._read_into_slow_data('TIME??????', parse_time)),
            ('GFAIL', self._read_gfail),
            ('GCF', lambda: self._read_into_slow_data('GCF', parse_gcf)),
        ]
        if self._parallel_mode():
            for unit in range(1, PARALLEL_MAX_UNITS + 1):
                items.append((f"GPDAT{unit}", lambda u=unit: self._read_parallel_unit(u)))
            for unit in sorted(self.parallel_units):
                for page in (0, 1):
                    items.append((f"GPSTS{unit}{page}", lambda u=unit, m=page: self._read_into_slow_data(
                        f"GPSTS{u}{m}", lambda r: parse_gpsts(u, m, r))))
                items.append((f"GPID{unit}", lambda u=unit: self._read_into_slow_data(
                    f"GPID{u}", lambda r: parse_gpid(u, r))))
            count = max(1, len(self.parallel_units))
            items.append(('GPPV', lambda: self._read_into_slow_data(f"GPPV{count}", parse_gppv)))

        # Queries the firmware never answered are retried once per SLOW_BACKOFF_ROUNDS rounds
        retry_all = self._slow_round % self.SLOW_BACKOFF_ROUNDS == 0
        return [item for item in items
                if retry_all or self._slow_failures.get(item[0], 0) <= self.MAX_FAILURES]

    def _poll_slow(self):
        for _ in range(self.SLOW_PER_CYCLE):
            if not self._slow_queue:
                self._slow_queue = self._build_slow_queue()
                self._slow_round += 1
                if not self._slow_queue:
                    return
            name, read = self._slow_queue.pop(0)
            if read():
                self._slow_failures[name] = 0
            else:
                self._slow_failures[name] = self._slow_failures.get(name, 0) + 1

    def get_data(self):
        """Poll one cycle. Returns (sensor values, binary flags); empty dicts if the inverter is silent."""
        started = time.monotonic()
        if not self.identity and self.cycle % self.BACKOFF_CYCLES == 0:
            self.update_identity()

        fast_data = {}
        fast_flags = {}
        any_answer = False
        for command, parser, split in FAST_QUERIES:
            parsed = self._poll(command, parser)
            if not parsed:
                continue
            any_answer = True
            if split:
                fast_data.update(parsed[0])
                fast_flags.update(parsed[1])
            else:
                fast_data.update(parsed)

        if any_answer:
            self._poll_slow()

        self.cycle += 1
        if not any_answer:
            self.logger.error("No data received from inverter. Check the cable, port and baud rate (2400).")
            return {}, {}

        if fast_data.get('battery_voltage') is not None:
            self._battery_voltage = fast_data['battery_voltage']
        data = {**self.settings, **self.slow_data, **fast_data, **self.identity}
        flags = {**self.slow_flags, **fast_flags}
        data = {k: v for k, v in data.items() if v is not None}
        if self.log_depth >= LOG_BASIC:
            self.logger.info("Cycle %d: %d values, %d flags, %.1f s, slow queue %d left",
                             self.cycle, len(data), len(flags), time.monotonic() - started, len(self._slow_queue))
        return data, flags

    # --- Writes (user actions only) ----------------------------------------------------------

    def nominal_battery_voltage(self):
        """12, 24 or 48 V system, from the configured cut-off voltage or the measured voltage."""
        voltage = self.settings.get('setting_battery_cutoff_voltage') or self._battery_voltage
        if not voltage:
            return None
        if voltage < 18:
            return 12
        if voltage < 36:
            return 24
        return 48

    def setting_range(self, key):
        setting = SETTINGS[key]
        if setting.ranges:
            nominal = self.nominal_battery_voltage()
            if nominal in setting.ranges:
                return setting.ranges[nominal]
            return (min(r[0] for r in setting.ranges.values()), max(r[1] for r in setting.ranges.values()))
        return setting.minimum, setting.maximum

    def _write(self, command):
        """Send one write command; raises unless the inverter answers ACK."""
        if not self.allow_writes:
            raise PermissionError("Inverter control is disabled in the integration options")
        self.logger.info("Inverter write: %s", command)
        if self.if_random:
            return
        response = self._exchange(command)
        if response == 'ACK':
            return
        if response == 'NAK':
            raise ValueError(f"Inverter rejected {command} (NAK): out of range or not allowed in the current mode")
        raise TimeoutError(f"No answer from inverter to {command}")

    def set_setting(self, key, value):
        """Write one §9 setting and return the value read back from the inverter."""
        setting = SETTINGS[key]
        if setting.options:
            code = value if isinstance(value, int) else next(
                (c for c, label in setting.options.items() if label == value), None)
            if code not in setting.options:
                raise ValueError(f"Invalid option for {key}: {value}")
            parameter = setting.format(code)
        else:
            low, high = self.setting_range(key)
            number = setting.cast(value)
            if (low is not None and number < low) or (high is not None and number > high):
                raise ValueError(f"{key}: {value} is outside {low}–{high}")
            parameter = setting.format(number)
        self._write(f"{setting.cmd}{parameter}")
        if self.if_random:
            self.settings[key] = setting.options[code] if setting.options else number
        else:
            self._read_setting(key)
        return self.settings.get(key)

    def set_feature(self, key, enabled):
        """Enable (TE) or disable (TD) one feature flag and return the state read back."""
        letter = FEATURE_KEYS[key]
        self._write(f"{'TE' if enabled else 'TD'}{letter}")
        if self.if_random:
            self.slow_flags[key] = enabled
        else:
            self._read_features()
        return self.slow_flags.get(key)

    def run_action(self, action, unit=None, now=None):
        """Control command behind a button: SON/SOFF/Q/ED1, SPON/SPOFF<n>, or clock sync."""
        if action == 'sync_clock':
            self._write(now.strftime('DATE%y%m%d'))
            self._write(now.strftime('TIME%H%M%S'))
            self._read_into_slow_data('DATE??????', parse_date)
            self._read_into_slow_data('TIME??????', parse_time)
        elif unit is not None:
            self._write(f"{PARALLEL_ACTIONS[action]}{unit}")
        else:
            self._write(ACTIONS[action])
            if action == 'factory_reset':
                # Every setting changed: re-read them all from the next cycle on
                self.settings.clear()
                self._slow_queue = []
