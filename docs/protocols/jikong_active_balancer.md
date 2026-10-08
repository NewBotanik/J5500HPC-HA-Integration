# Jikong (JK) Active Balancer JK-DZ11-B2A24S

Notes on the stand-alone Jikong active balancer board `JK-DZ11-B2A24S`
(2–24 cells in series). The device has two independent interfaces that speak
**different protocols**:

| Interface | Protocol | Used by aiobmsble |
|---|---|---|
| Bluetooth LE | JK02 (the JK BMS app protocol, `55 AA EB 90` frames, JK02_32S layout) | Yes, via `aiobmsble/bms/jikong_bms.py` (balancer variant) |
| RS485 | Vendor balancer protocol V1.3 (`55 AA` request / `EB 90` 74-byte response) | No |

There is **no separate plugin** for this device. Over BLE it behaves like a JK
BMS, and its advertisement cannot be told apart from one (see
[BLE identification](#ble-identification)). `jikong_bms.py` detects the
balancer from the model string of the `0x03` device-info frame and switches to
a reduced field set (see [aiobmsble support](#aiobmsble-support)).

Ukrainian version: [jikong_active_balancer_uk.md](jikong_active_balancer_uk.md).

## Sources

| Source | Content |
|---|---|
| [BMS_BLE-HA #636](https://github.com/patman15/BMS_BLE-HA/issues/636), HA debug logs 2026-02-24 … 2026-03-04 (aiobmsble 0.18.1) | Advertisement, GATT table, recorded BLE frames: `0x03` device info, `0x01` settings, ~17 800 valid `0x02` cell-info frames over 2 h 45 min |
| Vendor document [JK-DZ11B2A224S_RS485_V1.3.pdf](JK-DZ11B2A224S_RS485_V1.3.pdf) (Chinese), translations [EN](JK-DZ11B2A224S_RS485_V1.3_en.md) / [UK](JK-DZ11B2A224S_RS485_V1.3_uk.md) | RS485 protocol only |
| [mpp-solar `jk485.py`](https://github.com/jblance/mpp-solar/blob/master/mppsolar/protocols/jk485.py) | Independent RS485 implementation of the `0xFF` read command; field map, scaling and checksum (`sum & 0xFF`) match the vendor document. Implements reading only, no BLE. Decodes the temperature as unsigned, while the vendor document specifies `INT16` (signed is used below). |

The debug logs contain the device passcodes in clear text and are therefore
not part of the repository. All passcode values below are `<REDACTED>`; the
test frame has these bytes zeroed and its checksum recalculated.

## BLE identification

Recorded advertisement (stored in `aiobmsble/test_data/jikong_bms.json`):

| Item | Value |
|---|---|
| Local name | `50301130603` (user-configurable device name, equals the serial number by default) |
| MAC address | `C8:47:80:31:F6:43` |
| Manufacturer ID | `0x0B65` (2917), data `88 a0 c8 47 80 31 f6 43` = `88 a0` + MAC |
| Service UUIDs | `0xFFE0`, `0xFEE7` |

This is the same pattern as JK BMS devices, and `jikong_bms.py` matches it
(`service_uuid=0xFFE0`, `manufacturer_id=0x0B65`). Nothing in the
advertisement identifies the balancer: the local name is user-defined and the
manufacturer data is just the MAC address. A separate balancer plugin would
therefore violate the matcher-uniqueness rule (`tests/test_plugins.py::
test_advertisements_unique`).

## GATT table (recorded)

| Service | Characteristic | Handle | Properties |
|---|---|---|---|
| `0xFFE0` | `0xFFE2` | 15 | write-without-response |
| `0xFFE0` | `0xFFE1` | 17 | write-without-response, write, notify |
| `0x180A` Device Information | `0x2A24` Model Number, `0x2A25` Serial Number, `0x2A26` Firmware, `0x2A27` Hardware, `0x2A28` Software, `0x2A29` Manufacturer, `0x2A23` System ID, `0x2A2A` Regulatory, `0x2A50` PnP ID | 21–37 | read |

`jikong_bms.py` uses handle 17 (`0xFFE1`) for both notify and write.

## BLE protocol (JK02)

Frame format, checksum and commands are those of the JK BMS protocol
implemented in `jikong_bms.py`:

- Command: `aa 55 90 eb` + command byte + length + 13 data bytes + 8-bit sum
  (20 bytes).
- Response: `55 aa eb 90` + frame type (offset 4) + frame counter (offset 5) +
  payload, 300 bytes, last byte = 8-bit sum of bytes 0…298. Responses arrive
  as 4 notifications (128 + 22 + 128 + 22 bytes).
- Firmware `11.55` → JK02_32S layout (`jikong_bms.py` protocol offset 0).

### Recorded exchange

```text
TX  aa 55 90 eb 97 00 … 00 11     # device info request
RX  55 aa eb 90 03 …  (300 B)     # 0x03 device info
RX  aa 55 90 eb c8 01 01 00 … 44  # 0xC8 "ready", separate notification
TX  aa 55 90 eb 96 00 … 00 10     # cell info request
RX  55 aa eb 90 01 …  (300 B)     # 0x01 settings
RX  55 aa eb 90 03 …  (300 B)     # 0x03 device info (repeated)
RX  aa 55 90 eb c8 …              # 0xC8 (repeated)
RX  55 aa eb 90 02 …  (300 B)     # 0x02 cell info, then streamed about every 0.55 s
```

After `0x96` the device answers with `0x01` and `0x03` first, then streams
`0x02` frames continuously while connected. `jikong_bms.py` ignores the
unexpected types and uses the latest `0x02` frame. Incomplete frames caused by
lost notifications (150/172/278 bytes in the logs) fail the checksum and are
discarded.

### `0x03` device-info frame

Offsets are absolute frame offsets; strings are NUL-terminated ASCII.

| Offset | Size | Field | Recorded value | Used by `jikong_bms.py` |
|---|---|---|---|---|
| 0 | 4 | Header | `55 aa eb 90` | |
| 4 | 1 | Frame type | `0x03` | |
| 5 | 1 | Frame counter | varies | |
| 6 | 16 | Model | `JK_DZ11B2A24S` | `model`, balancer detection (`JK_DZ` prefix) |
| 22 | 8 | Hardware version | `11U` | `hw_version` |
| 30 | 8 | Software version | `11.55` | `sw_version` → protocol offset 0 |
| 38 | 4 | Uptime, u32 LE [s] | e.g. 4 268 100 s | |
| 42 | 4 | Power-on count, u32 LE | `8` | |
| 46 | 16 | Device name | `50301130603` | `name` |
| 62 | 16 | Device passcode | `<REDACTED>` | |
| 78 | 8 | Manufacturing date | `260107` | |
| 86 | 11 | Serial number | `50301130603` | `serial_number` (bytes 86–93 only: `50301130`) |
| 97 | 5 | Passcode | `<REDACTED>` | |
| 102 | 16 | User data | `Input Userdata` | |
| 118 | 16 | Setup passcode | `<REDACTED>` | |
| 299 | 1 | Checksum | | |

### `0x02` cell-info frame

Recorded values are from the test frame (16 cells, balancer idle). All values
little-endian. "Key" is the `BMSSample` key produced for the balancer.

| Offset | Size | Type | Field | Recorded | Key |
|---|---|---|---|---|---|
| 6 + 2·i | 2 | u16 | Cell voltage *i* [mV], 32 slots | 3323 … 3325 | `cell_voltages` |
| 70 | 4 | u32 | Enabled-cell bit mask | `ff ff 00 00` | `cell_count` (bit count = 16) |
| 74 | 2 | u16 | Average cell voltage [mV] | 3323 | |
| 76 | 2 | u16 | Max. cell voltage difference [mV] | 2 | `delta_voltage` |
| 78 | 1 | u8 | Index of highest cell, 0-based | 11 | |
| 79 | 1 | u8 | Index of lowest cell, 0-based | 0 | |
| 80 + 2·i | 2 | u16 | Cell connection (balance lead) resistance *i* [mΩ] | 65 … 141 | `cell_resistances` [Ω] |
| 144 | 2 | s16 | MOSFET temperature [0.1 °C] | 0 (no sensor) | |
| 150 | 4 | u32 | Pack voltage [mV] | 53 175 | `voltage` |
| 154 | 4 | u32 | Power [mW] | 0 (no shunt) | |
| 158 | 4 | s32 | Current [mA] | 0 (no shunt) | |
| 162 | 2 | s16 | Temperature [0.1 °C] | 116 → 11.6 °C | `temp_values` (only sensor) |
| 164 | 2 | s16 | Temperature 2 [0.1 °C] | 0 (no sensor) | |
| 166 | 4 | u32 | Alarm bit field (lower 16 bits used) | 0 | `problem_code` |
| 170 | 2 | s16 | Balancing current [mA] | 0 | `balance_current` |
| 172 | 1 | u8 | Balancing state (0 = idle) | 0 | `balancer` (bool) |
| 173 | 1 | u8 | SoC [%] | 0 (not estimated) | |
| 174 | 4 | u32 | Remaining capacity [mAh] | 0 | |
| 178 | 4 | u32 | Capacity setting [mAh] | 40 000 | |
| 182 | 4 | u32 | Cycle count | 0 | |
| 190 | 1 | u8 | SoH [%] | 0 | |
| 194 | 4 | u32 | Uptime [s] | ≈ 4.83 · 10⁶ (counts up) | |
| 198 | 1 | u8 | Charge MOSFET | 0 (none) | |
| 199 | 1 | u8 | Discharge MOSFET | 0 (none) | |
| 214 | 2 | u16 | Temperature sensor mask | `0x00ff` (claims all; wrong) | |
| 299 | 1 | u8 | Checksum | | |

Balancing was never active in the recorded sessions: the maximum cell
difference was 3 mV, below the 7 mV trigger from the settings. The meaning of
offsets 170/172 is taken from the JK BMS layout; `test_balancer_active` covers
it with a modified copy of the recorded frame.

### `0x01` settings frame (recorded, partly decoded)

| Offset | Size | Field | Recorded |
|---|---|---|---|
| 26 | 4 | Balancing trigger voltage difference [mV] | 7 |
| 78 | 4 | Max. balancing current [mA] | 2000 |
| 114 | 4 | Cell count | 16 |
| 126 | 4 | Balancing switch | 1 (on) |
| 130 | 4 | Battery capacity [mAh] | 40 000 |
| 138 | 4 | Balancing start voltage [mV] | 2000 |

Positions follow the JK02_32S settings layout; the recorded values are
plausible for a 16-cell pack. The settings frame is not decoded by aiobmsble.

## aiobmsble support

`jikong_bms.py` sets `_balancer` when the model starts with `JK_DZ`
(`_BALANCER_MODELS`). For a balancer it:

- decodes only `voltage`, `problem_code`, `balance_current` and `balancer`
  (`_FIELDS_BALANCER`) besides the cell data, so the always-zero `current`,
  `battery_level`, `cycle_charge`, `cycles`, `battery_health`, MOSFET states
  and the capacity setting are not reported;
- reads the temperature only from offset 162 (`_TEMP_POS_BALANCER`) and
  ignores the wrong sensor mask at offset 214.

For all JK devices (BMS and balancer) the per-cell connection resistances are
reported as `cell_resistances` (in Ω, one value per enabled cell, read from
offset 80, or 64 for the JK02_24S layout). This is the resistance of the
balance lead and its terminals as measured by the device, not the internal
resistance of the cell. These are most likely the per-cell resistances shown
in the vendor app (not yet compared value by value).

Before this change the logs showed `problem: True` (because
`cycle_charge = 0`), three spurious 0 °C sensors and an averaged temperature of
2.9 °C. The balancer variant now yields, for the test frame:

```python
{
    "voltage": 53.175,
    "problem_code": 0,
    "balance_current": 0.0,
    "balancer": False,
    "cell_count": 16,
    "delta_voltage": 0.002,
    "cell_voltages": [3.323] * 11 + [3.325] + [3.323] * 4,
    "cell_resistances": [0.065, 0.072, 0.071, 0.068, 0.075, 0.071, 0.073, 0.071,
                         0.065, 0.141, 0.127, 0.073, 0.071, 0.072, 0.069, 0.065],
    "temp_values": [TempSensor(11.6)],
    "temperature": 11.6,
    "problem": False,
}
```

Tests: `tests/bms/test_jikong_bms.py::test_balancer_update`,
`test_balancer_device_info`, `test_balancer_active`.

### Remaining limitations

- No frame with active balancing has been recorded; sign and scaling of
  `balance_current` while balancing should be confirmed with a log taken while
  the cell difference exceeds the trigger.
- The connection problems in the issue (`BleakOutOfConnectionSlotsError`)
  are caused by the Home Assistant Bluetooth setup, not by the protocol.

## RS485 protocol (reference)

Summary of the vendor document, for wired use (e.g. RS485 adapters). It is
**not** used over BLE. Details and the original example frames are in the
translations linked above; all example checksums were verified.

### Communication model

- Master/slave, request-response, the balancer never sends unsolicited data.
- 9600 baud (framing not stated; 8N1 is assumed).
- Reply within 1 s; the next request only after a reply or the timeout.
- Requests are 7 bytes, every response is 74 bytes.
- Multi-byte values are unsigned big-endian unless noted.

### Frames

```text
request:  [55 AA] [ADDR] [CMD] [DATA_HI DATA_LO] [CHK]          7 bytes
response: [EB 90] [ADDR] [CMD] [DATA × 69]       [CHK]         74 bytes
CHK = sum(all preceding bytes, header included) & 0xFF
```

### Commands

| Cmd | Purpose | Request data (u16) | Range | Response |
|---|---|---|---|---|
| `0xFF` | Read status and cell voltages | `0x0000` | – | See table below |
| `0xF0` | Set number of cells | cells | 2–24 | Active value at offset 4, rest `00` |
| `0xF2` | Set balancing trigger delta | mV | 2–1000 | Active value at offset 4, rest `00` |
| `0xF4` | Set max. balancing current | mA | 30–1000 | Active value at offset 4, rest `00` |
| `0xF6` | Balancing on/off | 0/1 | 0–1 | Active value at offset 4, rest `00` |

Out-of-range values are ignored and the response carries the currently active
value.

### `0xFF` response

| Offset | Size | Type | Field | Unit |
|---|---|---|---|---|
| 0 | 2 | – | Header `EB 90` | |
| 2 | 1 | u8 | Address | |
| 3 | 1 | u8 | Command `0xFF` | |
| 4 | 2 | u16 | Total voltage | 10 mV |
| 6 | 2 | u16 | Average cell voltage | mV |
| 8 | 1 | u8 | Detected cell count | |
| 9 | 1 | u8 | Highest cell index | |
| 10 | 1 | u8 | Lowest cell index | |
| 11 | 1 | u8 | Balancing status: bit 0 charging a cell, bit 1 discharging a cell | |
| 12 | 1 | u8 | Alarms: bit 0 cell-count setting error, bit 1 wire resistance too high, bit 2 battery overvoltage | |
| 13 | 2 | u16 | Max. cell voltage difference | mV |
| 15 | 2 | u16 | Balancing current | mA |
| 17 | 2 | u16 | Balancing trigger delta | mV |
| 19 | 2 | u16 | Max. balancing current | mA |
| 21 | 1 | u8 | Balancing switch (0 off, 1 on) | |
| 22 | 1 | u8 | Configured cell count | |
| 23 + 2·i | 2 | u16 | Cell voltage i, i = 0…23 | mV |
| 71 | 2 | s16 | Temperature | °C |
| 73 | 1 | u8 | Checksum | |

Example: `55 AA 01 FF 00 00 FF` → `EB 90 01 FF 1E D3 …` (78.91 V, 20 cells,
22 °C; full frame in the translations).
