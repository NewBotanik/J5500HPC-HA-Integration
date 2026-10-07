# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
Ukrainian version: [CLAUDE.uk.md](CLAUDE.uk.md). Keep both files in sync.

## Project overview

Native Home Assistant custom integration (HACS, domain `jsdsolar_j5500hpc_j5500hp`). It polls devices over serial (RS232/RS485) or TCP (Ethernet/WiFi bridge) and creates HA entities directly. No MQTT. Supported devices:

- Battery BMS: **PACE** (RS232, RS485, WiFi module), **JK (JKBMS)**, **TDT**
- Inverter: **JSD SOLAR** (e.g. J5500HPC), RS232 ASCII protocol at 2400 baud; monitoring, optional control

Forked from `fancyui/Gobel-Battery-HA-Integration`. The sibling repo `../J5500HPC-HA-Addon` is the old MQTT Add-on version of the same drivers.

## Commands

- No linter, no HA test harness. Offline driver test (no HA needed): `python tests/test_jsdsolar.py`
- Syntax check: `python -m py_compile custom_components/jsdsolar_j5500hpc_j5500hp/*.py`
- CI: `.github/workflows/hacs.yml` (HACS validation) and `hassfest.yaml`.
- Version lives in `custom_components/jsdsolar_j5500hpc_j5500hp/manifest.json` (`version`). Every version change needs a `CHANGELOG.md` entry.

## Architecture

```text
__init__.py → coordinator.py (DataUpdateCoordinator, runs drivers in the executor)
                → bms_comm.py           transport: serial (pySerial) or TCP socket
                → pacebms_rs232.py      PACE over RS232, command/response
                → pacebms_rs485.py      PACE over RS485, multi-pack
                → pacebms_wifi.py       PACE over WiFi module (PACE_LV_WIFI)
                → jkbms_rs485.py        JK over RS485, passive listener thread
                → tdtbms_rs232.py       TDT over RS232, command/response
                → jsdsolar_rs232.py     JSD SOLAR inverter, ASCII command/response
            → sensor.py / binary_sensor.py   entities built from coordinator.data
            → number.py / select.py / switch.py / button.py   JSD SOLAR control (option)
            → jsdsolar_entity.py   shared JSD entity base, device card, write helper
config_flow.py   UI setup: user step (type, connection, port) → network or serial step
const.py         config keys, BMS_TYPES, defaults
```

- **`coordinator.py`**: `_setup_bms_sync()` picks the driver by `bms_type` + `battery_port`. `_fetch_data_sync()` returns `{"analog": [...], "warning": [...]}`, one dict per pack, keyed by `pack_id`. Packs keep cached data for up to 3 failed polls. The BMS drivers come from the old Add-on and still expect an MQTT publisher; `DummyHAComm` stands in for it.
- **BMS drivers** expose `get_analog_data(pack)` / `get_warning_data(pack)`. JK reads frame caches filled by its background thread (`stop()` on unload).
- **JSD SOLAR** uses a separate data path. `JSDSOLAR232.get_data()` returns `(sensor values, binary flags)`, and the coordinator returns `{"analog": [], "warning": [], "inverter": {...}, "inverter_flags": {...}}`. `sensor.py` / `binary_sensor.py` branch early for `BMS_TYPE_JSD_SOLAR` and create one inverter device. Entities are created when a key first appears, using metadata from `jsdsolar_rs232.SENSORS`. Unique ID: `{entry_id}_inverter_{key}`.
- **`bms_comm.py`**: `receive_data()` reads up to `\r` (serial `read_until`, TCP buffered). On read errors it disconnects; the next `send_data()` reconnects. JK-only helpers: `receive_jkbms_passive()`, `receive_jkbms_raw()`, `flush_jkbms_buffer()`.

## Key conventions

- **Isolation rule**: a change to one driver (`pacebms_*.py`, `jkbms_rs485.py`, `tdtbms_rs232.py`, `jsdsolar_rs232.py`) must not affect the others. In shared files (`coordinator.py`, `sensor.py`, `binary_sensor.py`, `config_flow.py`), add device-specific code as a separate `bms_type` branch. See also `.agents/rules/ha-addon.md`.
- **Do not change `bms_comm.py` behaviour** for one device. All drivers share it.
- **JSD SOLAR writes**: polling (`get_data()`) sends queries only; `tests/test_jsdsolar.py` asserts this. Settings (§9) and control (§7) commands are sent only from `set_setting` / `set_feature` / `run_action`, called by number/select/switch/button entities on a user action, and only when the entry option `jsd_enable_control` is on (`allow_writes`). Every write: range check → `<cmd><value>` → must get `ACK` → read back. Never send calibration (§10). `SOFF`, `Q`, `ED1` buttons are disabled by default in the entity registry.
- **JSD SOLAR polling**: parsers are pure functions; missing fields become `None` and are not exposed. Link budget: 2400 baud, about 5 s per cycle, 3 s per unanswered command. So the fast set (§4.5) runs every cycle, everything else (settings, `TE?`, `TCQN`, `DATE`/`TIME`, `GFAIL`, `GCF`, parallel units) goes through a slow queue, 3 per cycle; failing commands back off; the coordinator timeout for JSD is 60 s. A driver lock keeps writes and polling from interleaving on the wire.
- **JSD SOLAR settings** are described once in `jsdsolar_rs232.SETTINGS` (command, width, type, options, range); keys shared with GCHG/GBAT fields (e.g. `setting_cv_voltage`) hold the same value from both sources. With control on, settings are number/select entities instead of sensors, and feature flags are switches instead of binary sensors.
- **Options flow** (Configure, every device type): `poll_interval` (overrides the setup value), `debug_logging` + `log_depth` (`basic` / `protocol` / `parsing`), and `jsd_enable_control` for JSD SOLAR. Saving reloads the entry. `__init__._apply_log_level()` sets the package logger to the deepest level any loaded entry asks for (`protocol`/`parsing` → DEBUG, `basic` → INFO, none → NOTSET). The JSD driver gates its own records by `log_depth` (`LOG_BASIC` cycle summary, `LOG_PROTOCOL` TX/RX with response time, `LOG_PARSING` parsed values); BMS drivers only get the logger level.
- **Pack ID**: use the pack id from the ACK data to tell packs apart.
- **Entity naming**: BMS `"{device_name} Pack NN {metric}"`, unique ID `{entry_id}_pack_{id}_{metric}`; overall `{entry_id}_total_{key}`.
- **Commit format**: conventional commits: `feat:`, `fix:`, `chore:`, `docs:`.
- **Version bump**: `manifest.json` `version` + `CHANGELOG.md` entry.
- `translations/*.yaml` at the repo root are leftovers from the Add-on and are not used by the integration.

## Protocol documentation

- `docs/protocols/JK-BMS-55AA-Protocol_EN.md` / `_ZH.md`: JK BMS 55AA frame protocol
- `docs/protocols/pc-bms-RS232-Protocol_en.md`: PACE BMS RS232 protocol
- `docs/protocols/protocol.JSDSOLAR.en.md` / `.uk.md`: JSD SOLAR inverter RS232 protocol. Read §14 (errors in the vendor document) before trusting an example.
- The J5500HPC does not answer Voltronic PI30/PI18/PI17/PI16 commands (`QPIGS`, `^P005GS`, …). An ESPHome UART probe confirmed this, so the JSD protocol is the only option.
