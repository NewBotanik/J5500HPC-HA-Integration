# JSD SOLAR Inverter — RS232 Communication Protocol (Developer Reference)

> **Source:** `protocol.JSDSOLAR.docx` (Chinese original, "逆变器通信协议", revision 21, 2024-05-06),
> Ukrainian translation: `protocol.JSDSOLAR.uk.docx`. Ukrainian version of this reference: [protocol.JSDSOLAR.uk.md](protocol.JSDSOLAR.uk.md).
>
> This file restructures the vendor document for implementation work. Everything in the
> command sections is taken from the vendor spec. Text marked **[Impl. note]** is our own
> guidance, not part of the spec. Known errors and contradictions in the vendor
> document are listed in [§14 Known issues](#14-known-issues-in-the-vendor-document). Read that section before you trust any single example.

---

## Contents

1. [Quick facts](#1-quick-facts)
2. [Physical layer](#2-physical-layer)
3. [Framing and general rules](#3-framing-and-general-rules)
4. [Implementation guide](#4-implementation-guide)
5. [Command index](#5-command-index)
6. [Allowed operating modes for settings and actions](#6-allowed-operating-modes-for-settings-and-actions)
7. [Control commands](#7-control-commands)
8. [Query commands](#8-query-commands)
9. [Setting commands](#9-setting-commands)
10. [Calibration commands](#10-calibration-commands)
11. [Extended commands (SNMP / BMS board)](#11-extended-commands-snmp--bms-board)
12. [Custom commands](#12-custom-commands)
13. [Enumerations and bit tables](#13-enumerations-and-bit-tables)
14. [Known issues in the vendor document](#14-known-issues-in-the-vendor-document)
15. [Glossary](#15-glossary)
16. [Vendor revision history](#16-vendor-revision-history)

---

## 1. Quick facts

| Item | Value |
|---|---|
| Interface | RS232C, DB9 female on the inverter |
| Serial settings | **2400 bps, 8 data bits, no parity, 1 stop bit (8N1)** |
| Encoding | ASCII text |
| Request terminator | `\r` (CR, 0x0D) |
| Response terminator | `\r` (CR, 0x0D) |
| Roles | Host (PC / master) sends a request, and the inverter answers. The inverter never sends unsolicited data. The one exception is the SNMP/BMS board handshake in §11. |
| Response timeout | The inverter **must answer within 500 ms** |
| Data response prefix | `(` for most queries. `#` for `F` and `I`. `BL` for `BL`. No prefix for `TCQN`, `DATE` and `TIME`. |
| Write result | `ACK\r` means success. `NAK\r` means rejected (out of range, or not allowed in the current mode). |
| Field separator | One space (0x20) |
| Numbers | Fixed-width decimal with zero padding and a fixed decimal point (`MMM.M`, `QQQ`, …) |

---

## 2. Physical layer

### 2.1 Transmission parameters

| Parameter | Value |
|---|---|
| Baud rate | 2400 bps |
| Data bits | 8 |
| Stop bits | 1 |
| Parity | None |
| Flow control | None (not mentioned in the spec, so assume none) |

### 2.2 Wiring (RS232C, 9-pin female connector on the inverter)

| Host (PC) | Inverter | Inverter pin |
|---|---|---|
| RX (receive) | TX (transmit) | Pin 2 |
| TX (transmit) | RX (receive) | Pin 3 |
| GND | GND | Pin 5 |

---

## 3. Framing and general rules

### 3.1 Request

```
<COMMAND>[<parameter>]\r
```

- Only ASCII characters. The command letters are upper-case.
- The parameter follows the command name directly, with no separator: `CHGC020\r`, `TCCV28.3\r`, `SPON1\r`.
- The parameter must have **exactly the width shown in the template**, zero-padded. For example, `<nnn>` → `020`, `<nn.n>` → `28.3`, `<nnnn>` → `0060`.
- Calibration commands carry a sign: `BUN+10\r`, `VR-.5\r`.
- The extended commands (§11) use `\n` inside the frame: `SNMP\n\r`.

### 3.2 Response types

| Type | Format | Used by |
|---|---|---|
| Acknowledge | `ACK\r` / `NAK\r` | All control, setting and calibration writes |
| Data frame | `(` + space-separated fields + `\r` | Most queries and setting read-backs |
| Hash frame | `#` + fields + `\r` | `F`, `I` |
| Tagged | `BLAAA\r` | `BL` |
| Bare | `AAAA\r`, `AA BB CC\r` | `TCQN`, `DATE`, `TIME` |
| Extended ack | `(ACK\r` | `SNMP`, `SBMS` |

### 3.3 Reading back a setting

Most setting commands can be read back. You send the command name followed by **one `?` per parameter character**, with the dot counted as a character:

```
TCCV????\r   ->  (28.3\r        (template <nn.n>, 4 characters)
CHGC???\r    ->  (020\r         (template <nnn>)
TBAT?\r      ->  (0\r           (template <n>)
UP?????\r    ->  (05000\r       (template <nnnnn>)
```

The exact query string for each command is given in its section. `F` is an exception: its setting is read with the rated-data query `F\r` (§8.1).

### 3.4 Placeholders used in the spec

- Upper-case letter groups (`AAA.A`, `BB.BB`, `KKKKK`) mark positional fields. The number of letters is the number of digits, and a dot is a literal decimal point.
- `b15…b0` and `c15…c0` are 16-character strings of `0`/`1`. The **leftmost character is bit 15**.
- `<n>`, `<nn>`, `<nnn.n>` are request parameters.
- `?` in a request is a literal question mark (see §3.3).

---

## 4. Implementation guide

> Everything in §4 is **[Impl. note]**: our recommendations, derived from the spec.

### 4.1 Transport loop

1. Open the port at 2400 8N1. Clear the receive buffer.
2. Send `<cmd>\r`.
3. Read bytes until `\r`. Use a timeout of **≥ 500 ms**; 1000 ms is recommended because 2400 bps is slow. The longest frames are `GPV` and `GPDAT`, about 150 characters, which take about 0.6 s to transmit at 2400 bps. So measure the timeout **from the last byte received**, not from the moment the request was sent.
4. Remove the trailing `\r` (and any `\n`).
5. Classify the reply: `ACK`, `NAK`, `(…`, `#…`, `BL…`, or bare.
6. Send only one request at a time. Wait for the reply, or the timeout, before sending the next request.

### 4.2 Parsing data frames

- Remove the prefix `(` or `#`, trim the string, then split it on **runs of whitespace**. Some examples in the spec contain double spaces or a space after `(`, for example `( 361.0 360.0 360.0`.
- Map the tokens to fields **by position**, using the field tables below.
- **Be tolerant.** Accept fewer or more tokens than documented. Older firmware returns shorter frames, and several examples in the spec have fewer fields than their templates (see `GLINE` and `FAN` in §14). Fields that are missing should become `null`, not an error.
- Parse numbers with an invariant culture: the decimal point is always `.`.
- Keep bit strings as strings, or convert them with `bit(i) = s[15 - i] == '1'`.

### 4.3 32-bit energy counters

`GLINE`, `GOP` and `GPV` report their lifetime energy counters in two 16-bit decimal fields: an "extension" (high word) field followed by a low-word field. The spec describes them as "binary concatenation, read in decimal":

```
total = ext * 65536 + low          // both fields are decimal numbers 0..65535
energy_Wh = total * 10             // the unit is tens of watt-hours
```

The daily counters are single fields in the same unit (×10 Wh). The command `Q\r` resets all these counters (§7.5).

### 4.4 Writes

- Always check for `ACK`. A `NAK` means the value is out of range **or** the command is not allowed in the current operating mode (§6).
- **[Impl. note]** After a successful write, read the value back with the `?` form (§3.3) to confirm it.
- Some settings depend on other settings. The main dependencies are:
  - `TCCV`, `TCFV`, `EOD` and `TBLV` take effect only when the battery type is user-defined (the spec says to send `TBAT2`; see §14 on the TBAT 2/3 conflict).
  - The CV voltage (`TCCV`) must be greater than the float voltage (`TCFV`).
  - `TCVT` takes effect only when the charge mode is forced 3-stage (`CST02`).
  - `BSOCU`, `BSOCG` and `BSOCB` take effect only while communication with the BMS is working.
  - `TCDV` and `TDOT` need the dual-output auxiliary board.
  - `ED1`, `F` and `SW` are accepted only in Standby or Line mode.

### 4.5 Suggested polling set for monitoring

| Purpose | Commands |
|---|---|
| Mode and faults | `GMOD`, `GWS` |
| Grid | `GLINE` |
| Output and load | `GOP` |
| Battery | `GBAT`, `BL`, `GCHG` (and `GBMS` if a BMS is connected) |
| PV | `GPV` |
| Temperatures | `GTMP` |
| Identity (once) | `I`, `SVFW`, `F` |
| Parallel systems | `GPDAT<n>`, `GPSTS<n><m>`, `GPID<n>`, `GPPV<n>` |

At 2400 bps a full cycle of the commands above takes about 3–5 s. Do not poll faster than the link can carry.

---

## 5. Command index

| Category | Command | Purpose | Section |
|---|---|---|---|
| Control | `SON` | Cancel remote shutdown, i.e. turn the inverter on | [7.1](#71-son) |
| Control | `SOFF` | Remote shutdown | [7.2](#72-soff) |
| Control | `SPON<n>` | Turn on unit n of a parallel system | [7.3](#73-sponn) |
| Control | `SPOFF<n>` | Shut down unit n of a parallel system | [7.4](#74-spoffn) |
| Control | `Q` | Clear the energy counters | [7.5](#75-q) |
| Query | `F` | Rated data | [8.1](#81-f--rated-data) |
| Query | `GMOD` | Operating mode | [8.2](#82-gmod--operating-mode) |
| Query | `SVFW` | Firmware version and date | [8.3](#83-svfw--firmware-version) |
| Query | `GTMP` | Temperatures | [8.4](#84-gtmp--temperatures) |
| Query | `GLINE` | Grid (mains) input | [8.5](#85-gline--grid-input) |
| Query | `GBAT` | Battery | [8.6](#86-gbat--battery) |
| Query | `GBUS` | DC bus | [8.7](#87-gbus--dc-bus) |
| Query | `GCHG` | Charger | [8.8](#88-gchg--charger) |
| Query | `GOP` | Output | [8.9](#89-gop--output) |
| Query | `GINV` | Inverter stage | [8.10](#810-ginv--inverter-stage) |
| Query | `FAN???` | Fans | [8.11](#811-fan--fans) |
| Query | `GWS` | Faults and warnings | [8.12](#812-gws--faults-and-warnings) |
| Query | `BL` | Battery level, % | [8.13](#813-bl--battery-level) |
| Query | `GPV` | PV input | [8.14](#814-gpv--pv-input) |
| Query | `TCQN????` | Time since the last equalization charge | [8.15](#815-tcqn--equalization-interval-counter) |
| Query/Set | `DATE` | Date | [8.16](#816-date--date) |
| Query/Set | `TIME` | Time | [8.17](#817-time--time) |
| Query | `GPDAT<n>` | Data of parallel unit n | [8.18](#818-gpdatn--parallel-unit-data) |
| Query | `GPSTS<n><m>` | Status bits of parallel unit n | [8.19](#819-gpstsnm--parallel-unit-status-bits) |
| Query | `GPID<n>` | ID of parallel unit n | [8.20](#820-gpidn--parallel-unit-id) |
| Query | `GFAIL` | Snapshot taken at the last fault | [8.21](#821-gfail--fault-snapshot) |
| Query | `GBMS` | BMS data | [8.22](#822-gbms--bms-data) |
| Query | `GPPV<n>` | PV of all parallel units | [8.23](#823-gppvn--pv-of-all-parallel-units) |
| Query/Set | `CFG<n>` | Remote configuration mode | [8.24](#824-cfgn--remote-configuration-mode) |
| Query | `I` | Serial number and DSP firmware | [8.25](#825-i--serial-number) |
| Setting | `TE<n>` / `TD<n>` | Enable / disable feature flags | [9.1](#91-ten--enable-feature-flag), [9.2](#92-tdn--disable-feature-flag) |
| Setting | `ED1` | Factory reset | [9.3](#93-ed1--factory-reset) |
| Setting | `V<nnn>` | Output voltage | [9.4](#94-vnnn--output-voltage) |
| Setting | `F<nn>` | System frequency | [9.5](#95-fnn--system-frequency) |
| Setting | `TBAT<n>` | Battery type | [9.6](#96-tbatn--battery-type) |
| Setting | `CHGC<nnn>` | Maximum charge current (PV+AC) | [9.7](#97-chgcnnn--maximum-charge-current) |
| Setting | `TCCV<nn.n>` | CV (bulk/absorption) voltage | [9.8](#98-tccvnnn--cv-charge-voltage) |
| Setting | `TCFV<nn.n>` | Float voltage | [9.9](#99-tcfvnnn--float-voltage) |
| Setting | `TCDV<nn.n>` | Second-output cut-off voltage | [9.10](#910-tcdvnnn--second-output-cut-off-voltage) |
| Setting | `TCQV<nn.n>` | Equalization voltage | [9.11](#911-tcqvnnn--equalization-voltage) |
| Setting | `TCVT<nnnn>` | CV charge time | [9.12](#912-tcvtnnnn--cv-charge-time) |
| Setting | `TDOT<nnnn>` | Second-output run time | [9.13](#913-tdotnnnn--second-output-run-time) |
| Setting | `TCQT<nnnn>` | Equalization time | [9.14](#914-tcqtnnnn--equalization-time) |
| Setting | `TCQO<nnnn>` | Equalization timeout | [9.15](#915-tcqonnnn--equalization-timeout) |
| Setting | `TCQI<nnnn>` | Equalization interval | [9.16](#916-tcqinnnn--equalization-interval) |
| Setting | `EOD<nn.n>` | Battery low-voltage shutdown (end of discharge) | [9.17](#917-eodnnn--battery-cut-off-voltage) |
| Setting | `TBLV<nn.n>` | Battery low-voltage warning | [9.18](#918-tblvnnn--battery-low-voltage-warning) |
| Setting | `LWDT<nnnn>` | Low-power discharge time | [9.19](#919-lwdtnnnn--low-power-discharge-time) |
| Setting | `BSOCU<nnn>` | Low-SOC shutdown (BMS) | [9.20](#920-bsocunnn--low-soc-shutdown) |
| Setting | `BSOCG<nnn>` | Low SOC → switch to grid (BMS) | [9.21](#921-bsocgnnn--low-soc--switch-to-grid) |
| Setting | `BSOCB<nnn>` | High SOC → switch to battery (BMS) | [9.22](#922-bsocbnnn--high-soc--switch-to-battery) |
| Setting | `UP<nnnnn>` | Displayed output power | [9.23](#923-upnnnnn--displayed-output-power) |
| Setting | `LT<nnn>` | Delay before returning from battery to grid | [9.24](#924-ltnnn--battery-to-grid-return-delay) |
| Setting | `FT<n>` | Fan fault detection | [9.25](#925-ftn--fan-fault-detection) |
| Setting | `HV<n>` | Output voltage type (high/low) | [9.26](#926-hvn--output-voltage-type) |
| Setting | `OVP<nnn>` | Grid over-voltage protection | [9.27](#927-ovpnnn--grid-over-voltage-protection) |
| Setting | `LVP<nnn>` | Grid under-voltage protection | [9.28](#928-lvpnnn--grid-under-voltage-protection) |
| Setting | `CI1<nn>` | Maximum constant-current charge time | [9.29](#929-ci1nn--maximum-constant-current-charge-time) |
| Setting | `OPR<nn>` | Output source priority | [9.30](#930-oprnn--output-source-priority) |
| Setting | `OPM<nn>` | Output mode APP/UPS | [9.31](#931-opmnn--output-mode) |
| Setting | `CPR<nn>` | Charger source priority | [9.32](#932-cprnn--charger-source-priority) |
| Setting | `GCC<nnn>` | Maximum grid (AC) charge current | [9.33](#933-gccnnn--maximum-grid-charge-current) |
| Setting | `CST<nn>` | Charge mode: auto / 2-stage / 3-stage | [9.34](#934-cstnn--charge-mode) |
| Setting | `BTG<nn.n>` | Battery voltage for switching back to grid | [9.35](#935-btgnnn--battery-voltage-back-to-grid) |
| Setting | `BTB<nn.n>` | Battery voltage for switching back to battery | [9.36](#936-btbnnn--battery-voltage-back-to-battery) |
| Setting | `BTO<nn.n>` | Battery over-voltage protection | [9.37](#937-btonnn--battery-over-voltage-protection) |
| Setting | `PAR<n>` | Parallel mode | [9.38](#938-parn--parallel-mode) |
| Setting | `SW<nn>` | Button/LCD panel variant | [9.39](#939-swnn--button-panel-variant) |
| Calibration | `BA0`, `B1A`, `B2A` | Battery voltage | [10.1–10.3](#101-ba0--reset-battery-voltage-calibration) |
| Calibration | `PA0`, `PV` | PV voltage | [10.4–10.5](#104-pa0--reset-pv-calibration) |
| Calibration | `BUN LVR VDR OCR VR IR DCR CHI LWT LVA` | Relative trims (±) | [10.6–10.15](#106-relative-trims-) |
| Extended | `SNMP\n`, `SBMS\n` | External monitoring/BMS board | [11](#11-extended-commands-snmp--bms-board) |
| Custom | `GCF` | Detailed fault bit strings | [12.1](#121-gcf--detailed-fault-status) |

---

## 6. Allowed operating modes for settings and actions

√ = allowed. An empty cell = not allowed (the inverter will answer `NAK`). The last
column, "Par. sync", means that the value is propagated to every unit of a
parallel system.

> **Caveat:** the vendor table uses many merged cells, and the alignment of its
> last rows is ambiguous. Treat this table as a guide. The `ACK`/`NAK` reply is the final word.

| Command | Standby | Shutdown | Line | Battery | Test | Fault | Power-on | Par. sync |
|---|---|---|---|---|---|---|---|---|
| `TE` / `TD` | √ | | √ | √ | √ | √ | | per flag (§9.1) |
| `ED1` | √ | | √ | | | | | |
| `V` | √ | | √ | √ | | | | √ |
| `F` | √ | | √ | | | | | √ |
| `TBAT CHGC TCCV TCFV TCQV TCVT TCQT TCQO TCQI EOD TBLV LWDT BSOCU BSOCG BSOCB` | √ | | √ | √ | √ | √ | | √ |
| `UP` | √ | √ | √ | √ | √ | √ | √ | |
| `LT FT OVP LVP CI1 OPR OPM CPR GCC CST BTG BTB BTO SW` | √ | | √ | √ | √ | √ | | √ |
| `HV` | √ | | √ | √ | √ | √ | | |
| `PAR`, `CFG` | √ | √ | √ | √ | √ | √ | √ | √ |
| `SON` (turn on) | √ | | | | | | | |
| `SOFF` (turn off) | | | √ | √ | | √ | | |
| `SPON` → Line or Battery | √ | √ | √ | √ | √ | √ | √ | |
| `SPOFF` → Bypass or Standby | √ | √ | √ | √ | √ | √ | √ | |
| `Q` (clear energy counters) | √ | √ | √ | √ | √ | √ | √ | |

---

## 7. Control commands

All control commands answer `ACK\r`.

### 7.1 SON

| | |
|---|---|
| Request | `SON\r` |
| Response | `ACK\r` |
| Effect | Cancels a remote shutdown. The inverter starts and enters Line or Battery mode. |

### 7.2 SOFF

| | |
|---|---|
| Request | `SOFF\r` |
| Response | `ACK\r` |
| Effect | Remote shutdown. The inverter enters Bypass or Standby mode. |

### 7.3 SPON\<n\>

| | |
|---|---|
| Request | `SPON<n>\r`, where n is the unit number in the parallel system |
| Response | `ACK\r` |
| Effect | Unit n enters Line or Battery mode. |

### 7.4 SPOFF\<n\>

| | |
|---|---|
| Request | `SPOFF<n>\r` |
| Response | `ACK\r` |
| Effect | Unit n enters Bypass or Standby mode. |

### 7.5 Q

| | |
|---|---|
| Request | `Q\r` |
| Response | `ACK\r` |
| Effect | Clears the energy counters listed below. |

Counters cleared by `Q`:

1. AC (grid) energy today
2. AC (grid) energy total
3. AC (grid) energy total, extension (high) word
4. PV energy today
5. PV energy total
6. PV energy total, extension word
7. Output energy today
8. Output energy total
9. Output energy total, extension word

---

## 8. Query commands

### 8.1 F — rated data

| | |
|---|---|
| Request | `F\r` |
| Response | `#MMM.M QQQ SSS.S RR.R\r` |

| # | Field | Meaning | Format / unit |
|---|---|---|---|
| 0 | `#` | Start character | |
| 1 | `MMM.M` | Rated voltage | 000.0–999.9 V |
| 2 | `QQQ` | Rated current | 000–999 A |
| 3 | `SSS.S` | Battery cell count × 120 (sic) | `SS.SS` 00.00–99.99 or `SSS.S` 000.0–999.9 |
| 4 | `RR.R` | Rated frequency | 00.0–99.9 Hz |

This command is also used to read back the `F<nn>` frequency setting.

### 8.2 GMOD — operating mode

| | |
|---|---|
| Request | `GMOD\r` |
| Response | `(M\r` |

| M | Mode |
|---|---|
| `P` | Initial power-on |
| `S` | Standby |
| `L` | Line (grid) |
| `B` | Battery |
| `F` | Fault |
| `D` | Shutdown |
| `X` | Test |

### 8.3 SVFW — firmware version

| | |
|---|---|
| Request | `SVFW\r` |
| Response | `(N.NNN (AAAABBCC\r` |
| Fields | `N.NNN` is the firmware version. `AAAABBCC` is the release date as YYYYMMDD. All characters are digits 0–9. |
| Example | `SVFW\r` → `(4.001 (20211105\r` means firmware 4001, released 2021-11-05. |

**[Impl. note]** The second field starts with its own `(`. Strip it before you parse the date.

### 8.4 GTMP — temperatures

| | |
|---|---|
| Request | `GTMP\r` |
| Response | `(NNN.N MMM.M AAA.A III.I ZZZ.Z\r` |
| Unit | °C |

| # | Field | Meaning |
|---|---|---|
| 1 | `NNN.N` | PV-side temperature |
| 2 | `MMM.M` | Charger-side temperature |
| 3 | `AAA.A` | Ambient temperature |
| 4 | `III.I` | Low-voltage MPPT 1 temperature |
| 5 | `ZZZ.Z` | Low-voltage MPPT 2 temperature |

### 8.5 GLINE — grid input

| | |
|---|---|
| Request | `GLINE\r` |
| Response | `(AAA.A BB.BB CCC.C DDD.D EEE.E FFF.F GG.GG HH.HH IIIII JJJ KKKKK LLLLL MMMMM\r` |

| # | Field | Meaning | Unit |
|---|---|---|---|
| 1 | `AAA.A` | Grid input voltage | V |
| 2 | `BB.BB` | Grid frequency | Hz |
| 3 | `CCC.C` | Grid-loss high-voltage threshold | V |
| 4 | `DDD.D` | Grid-loss low-voltage threshold | V |
| 5 | `EEE.E` | Grid-return high-voltage threshold | V |
| 6 | `FFF.F` | Grid-return low-voltage threshold | V |
| 7 | `GG.GG` | Grid-loss high-frequency threshold | Hz |
| 8 | `HH.HH` | Grid-loss low-frequency threshold | Hz |
| 9 | `IIIII` | Internal data (a counter, "times") | |
| 10 | `JJJ` | Load | % |
| 11 | `KKKKK` | Grid energy today | ×10 Wh (the spec says "tens of watts") |
| 12 | `LLLLL` | Grid energy total, high word | see §4.3 |
| 13 | `MMMMM` | Grid energy total, low word | ×10 Wh |

Example from the spec (older, shorter frame):

```
GLINE\r -> (220.0 50.00 264.0 154.0 255.0 163.0 70.00 40.00 010 \r
```

This reads as 220 V, 50 Hz, loss thresholds 264/154 V, return thresholds 255/163 V, frequency limits 70/40 Hz and a load of 10 %. The example has no internal-data field and no energy fields.

### 8.6 GBAT — battery

| | |
|---|---|
| Request | `GBAT\r` |
| Response | `(AAA.A BBB.BB CC DD.D EE.E\r` |

| # | Field | Meaning | Unit |
|---|---|---|---|
| 1 | `AAA.A` | Battery voltage | V |
| 2 | `BBB.BB` | Battery discharge current | A |
| 3 | `CC` | Configured number of battery cells | |
| 4 | `DD.D` | Configured discharge cut-off voltage | V |
| 5 | `EE.E` | Configured discharge warning voltage | V |

### 8.7 GBUS — DC bus

| | |
|---|---|
| Request | `GBUS\r` |
| Response | `(AAA.A BBB.B CCC.C\r` |

| # | Field | Meaning | Unit |
|---|---|---|---|
| 1 | `AAA.A` | Actual bus voltage | V |
| 2 | `BBB.B` | Initial bus reference setpoint | V |
| 3 | `CCC.C` | Bus reference setpoint | V |

Example: `( 361.0 360.0 360.0` means the bus is at 361 V and both references are 360 V.

### 8.8 GCHG — charger

| | |
|---|---|
| Request | `GCHG\r` |
| Response | `(AAA.A BBB.B CC DDD.D EEE.EE FFF.FF GG.G HH.H II.I JJJ.JJ KKKK LLL MMM NNN O P Q R SSS.SS TTT.TT UUU.UU VVV.V W\r` |

| # | Field | Meaning | Unit / values |
|---|---|---|---|
| 1 | `AAA.A` | Bus voltage | V |
| 2 | `BBB.B` | Charge voltage | V |
| 3 | `CC` | Number of battery cells | |
| 4 | `DDD.D` | Charge current | A |
| 5 | `EEE.EE` | Internal data | A |
| 6 | `FFF.FF` | Internal data | A |
| 7 | `GG.G` | Configured CV voltage | V |
| 8 | `HH.H` | Configured float voltage | V |
| 9 | `II.I` | Configured equalization voltage | V |
| 10 | `JJJ.JJ` | Configured maximum charge current (PV + AC) | A |
| 11 | `KKKK` | Configured CV time | min |
| 12 | `LLL` | Configured equalization time | min |
| 13 | `MMM` | Configured equalization timeout | min |
| 14 | `NNN` | Equalization interval | days |
| 15 | `O` | Equalization mode | 1 = on, 0 = off |
| 16 | `P` | Configured battery type | see `TBAT` |
| 17 | `Q` | Low-power discharge time setting | h |
| 18 | `R` | Charge stage | 0 = stopped, 1 = constant current, 2 = constant voltage (CV), 3 = float |
| 19–23 | `SSS.SS TTT.TT UUU.UU VVV.V W` | Internal data | |

### 8.9 GOP — output

| | |
|---|---|
| Request | `GOP\r` |
| Response | `(AAA.A BB.BB CCC.CC DD.DD EEEEE FFFFF GGGGG HHHHH IIIII JJJ KKKKK LLLLL MMMMM NNNNN OOOOO\r` |

| # | Field | Meaning | Unit |
|---|---|---|---|
| 1 | `AAA.A` | Output voltage | V |
| 2 | `BB.BB` | Output frequency | Hz |
| 3 | `CCC.CC` | Output current | A |
| 4 | `DD.DD` | Output current, small-current channel | A |
| 5 | `EEEEE` | Output active power | W |
| 6 | `FFFFF` | Internal data | |
| 7 | `GGGGG` | Output apparent power | VA |
| 8 | `HHHHH` | Output power, small-current channel | W |
| 9 | `IIIII` | Output apparent power, half-cycle | |
| 10 | `JJJ` | Load | % |
| 11 | `KKKKK` | Internal data | |
| 12 | `LLLLL` | Internal data | |
| 13 | `MMMMM` | Output energy today | ×10 Wh |
| 14 | `NNNNN` | Output energy total, high word | see §4.3 |
| 15 | `OOOOO` | Output energy total, low word | ×10 Wh |

### 8.10 GINV — inverter stage

| | |
|---|---|
| Request | `GINV\r` |
| Response | `(AAA.A BB.BB CCC.C\r` |

| # | Field | Meaning | Unit |
|---|---|---|---|
| 1 | `AAA.A` | Inverter voltage | V |
| 2 | `BB.BB` | Inverter frequency | Hz |
| 3 | `CCC.C` | Inverter current | A |

### 8.11 FAN??? — fans

| | |
|---|---|
| Request | `FAN???\r` |
| Response (template) | `(AAA BBB C\r` |
| Response (example, use this) | `(050 00020 00020 0 1\r` |

| # | Field | Meaning |
|---|---|---|
| 1 | `050` | Fan speed command, % |
| 2 | `00020` | Measured speed of fan 1 |
| 3 | `00020` | Measured speed of fan 2 |
| 4 | `0` | Fan 1 stop flag: 1 = fault, 0 = normal |
| 5 | `1` | Fan 2 stop flag: 1 = fault, 0 = normal |

### 8.12 GWS — faults and warnings

| | |
|---|---|
| Request | `GWS\r` |
| Response | `(NN b15…b0 c15…c0\r` |
| Example | `(00 0000000000000000 0000000000000000\r` |

| # | Field | Meaning |
|---|---|---|
| 1 | `NN` | Fault code, decimal. `00` = no fault. Any non-zero code puts the unit in Fault mode. See [§13.1](#131-fault-codes-gws-nn-gpdat-ee-gfail-aa). |
| 2 | `b15…b0` | Warning word 1. See [§13.2](#132-gws-warning-word-1-b15b0). |
| 3 | `c15…c0` | Warning word 2. See [§13.3](#133-gws-warning-word-2-c15c0). |

### 8.13 BL — battery level

| | |
|---|---|
| Request | `BL\r` |
| Response | `BLAAA\r`, where `AAA` = 000–100 (%) |

### 8.14 GPV — PV input

| | |
|---|---|
| Request | `GPV\r` |
| Response | `(AAA.A BBB.B CC.CC DD.DD EEEEE FF G H III.I JJJ.J KKK.K LLL.L MMM.M NN OOOOO PPPPP QQQQ QQQQ QQQQ QQQQ RRRRR SSSSS TTTTT b15…b0\r` |

| # | Field | Meaning | Unit / values |
|---|---|---|---|
| 1 | `AAA.A` | PV voltage | V |
| 2 | `BBB.B` | Battery voltage | V |
| 3 | `CC.CC` | PV charge current | A |
| 4 | `DD.DD` | PV current | A |
| 5 | `EEEEE` | PV power | W |
| 6 | `FF` | PV tracking state | 00 = standby, 01 = ready, 02 = CV mode, 03 = MPPT |
| 7 | `G` | PV charging possible | 0 = no, 1 = yes |
| 8 | `H` | Internal data | |
| 9–13 | `III.I JJJ.J KKK.K LLL.L MMM.M` | Internal data | |
| 14 | `NN` | Internal data | |
| 15 | `OOOOO` | Internal data | |
| 16 | `PPPPP` | Internal data | |
| 17–20 | `QQQQ` ×4 | Internal data (four tokens) | |
| 21 | `RRRRR` | PV energy today | ×10 Wh |
| 22 | `SSSSS` | PV energy total, high word | see §4.3 |
| 23 | `TTTTT` | PV energy total, low word | ×10 Wh |
| 24 | `b15…b0` | PV warning bits | see [§13.4](#134-gpv-warning-bits-b15b0) |

The vendor revision 21 changed "the GPV units (charge amount)". The field list above follows revision 21.

### 8.15 TCQN???? — equalization interval counter

| | |
|---|---|
| Request | `TCQN????\r` |
| Response | `AAAA\r`, 0000–2160 hours |
| Meaning | Hours since the last equalization charge started |

### 8.16 DATE — date

| | |
|---|---|
| Read | `DATE??????\r` → `AA BB CC\r` (no `(` prefix) |
| Fields | `AA` = year 00–99, counted from 2000. `BB` = month 01–12. `CC` = day 01–31. |
| Write | `DATEyymmdd\r`. For example, `DATE051203\r` sets 2005-12-03. |

### 8.17 TIME — time

| | |
|---|---|
| Read | `TIME??????\r` → `AA BB CC\r` |
| Fields | `AA` = hours 00–23, `BB` = minutes 00–59, `CC` = seconds 00–59 |
| Write | `TIMEhhmmss\r`. For example, `TIME051203\r` sets 05:12:03. The spec example wrongly says `DATE051203`; see §14. |

### 8.18 GPDAT\<n\> — parallel unit data

| | |
|---|---|
| Request | `GPDAT<n>\r`, where n = unit number |
| Response | `(A B CCCC D EE FFF.F GG.GG HHH.H II.II JJJ.J KK.KK LL.LL MM.M NNN.N OOO PPPP QQQQ RRR SSS.S TTT.T UUUU VVV.V\r` |

| # | Field | Meaning | Unit / values |
|---|---|---|---|
| 1 | `A` | Communication OK | 0 = link lost, so **the remaining fields are invalid**; 1 = OK |
| 2 | `B` | Operating state | [§13.5](#135-operating-state-codes) (GPDAT column) |
| 3 | `CCCC` | Firmware version | |
| 4 | `D` | Parallel mode | 0 = single, 1 = single-phase parallel, 2 = phase R, 3 = phase S, 4 = phase T |
| 5 | `EE` | Fault code | 0 = none, otherwise [§13.1](#131-fault-codes-gws-nn-gpdat-ee-gfail-aa) |
| 6 | `FFF.F` | Inverter voltage | V |
| 7 | `GG.GG` | Inverter frequency | Hz |
| 8 | `HHH.H` | Grid voltage | V |
| 9 | `II.II` | Grid frequency | Hz |
| 10 | `JJJ.J` | Output voltage | V |
| 11 | `KK.KK` | Output frequency | Hz |
| 12 | `LL.LL` | Output current | A |
| 13 | `MM.M` | Battery voltage | V |
| 14 | `NNN.N` | Battery current | A |
| 15 | `OOO` | Load | % |
| 16 | `PPPP` | Load apparent power | VA |
| 17 | `QQQQ` | Load active power | W |
| 18 | `RRR` | Battery capacity | % |
| 19 | `SSS.S` | PV voltage | V |
| 20 | `TTT.T` | PV charge current | A |
| 21 | `UUUU` | PV power | W |
| 22 | `VVV.V` | Main board temperature | °C |

### 8.19 GPSTS\<n\>\<m\> — parallel unit status bits

| | |
|---|---|
| Request | `GPSTS<n><m>\r`, where n = unit number and m = page (0 or 1) |
| Response | `(A b15…b0 c15…c0\r` |

`A` is the communication-OK flag, as in `GPDAT`. If `A` = 0, the bit fields are invalid.

| m | `b15…b0` | `c15…c0` |
|---|---|---|
| 0 | PFC warnings ([§13.6](#136-gpsts-m0-pfc-warnings-b15b0)) | INV warnings ([§13.7](#137-gpsts-m0-inv-warnings-c15c0)) |
| 1 | Grid status ([§13.8](#138-gpsts-m1-grid-status-b15b0)) | Charger status ([§13.9](#139-gpsts-m1-charger-status-c15c0)) |

### 8.20 GPID\<n\> — parallel unit ID

| | |
|---|---|
| Request | `GPID<n>\r` |
| Response | `(A BBBBB CCCCC DDDDD\r` |
| Fields | `A` = communication OK. `BBBBB`, `CCCCC`, `DDDDD` = ID words 1, 2, 3. |

### 8.21 GFAIL — fault snapshot

| | |
|---|---|
| Request | `GFAIL\r` |
| Response | `(AA BB CCCCC DDDD EEEE FFFF GG.GG HHHH IIII JJJJ KKKK LLLL MMMM NNN OOOOO PPPPP QQQQQ R SSSSS TTTTT UUUUU\r` |

These values were recorded at the moment of the last fault.

| # | Field | Meaning | Unit |
|---|---|---|---|
| 1 | `AA` | Fault code | [§13.1](#131-fault-codes-gws-nn-gpdat-ee-gfail-aa) |
| 2 | `BB` | Mode at the time of the fault | [§13.5](#135-operating-state-codes) (GFAIL column) |
| 3 | `CCCCC` | R-phase active power | W |
| 4 | `DDDD` | R-phase grid voltage | V (scaling not specified) |
| 5 | `EEEE` | Grid frequency | Hz (scaling not specified) |
| 6 | `FFFF` | R-phase inverter output voltage | V |
| 7 | `GG.GG` | **Not described in the spec** | |
| 8 | `HHHH` | Inverter frequency | Hz |
| 9 | `IIII` | R-phase inverter current | A |
| 10 | `JJJJ` | Bus voltage | V |
| 11 | `KKKK` | Battery voltage | V |
| 12 | `LLLL` | Charge current | A |
| 13 | `MMMM` | INV 1 temperature | °C |
| 14 | `NNN` | Calibration reset bits | |
| 15 | `OOOOO` | Battery PFC state | |
| 16 | `PPPPP` | Grid PFC state | |
| 17 | `QQQQQ` | Inverter protection (INV state) | |
| 18 | `R` | DC/DC mode | |
| 19 | `SSSSS` | ADC state | |
| 20 | `TTTTT` | Inverter DC-component sample | |
| 21 | `UUUUU` | Ambient temperature | |

**[Impl. note]** The spec gives no scale factors for the 4- and 5-digit integer fields.
Show them raw, or confirm the scaling on a real device first.

### 8.22 GBMS — BMS data

| | |
|---|---|
| Request | `GBMS\r` |
| Response | `(AAAAA BBBBB CCCCC DDDDD EEEEE FFFFF HHHHH IIIII JJJJJ KKKKK LLLLL MMMMM NNNNN PPPPP QQQQQ RRRRR SSSSS\r` |

The letters `G` and `O` are skipped in the template. There are 17 fields.

| # | Field | Meaning | Unit |
|---|---|---|---|
| 1 | `AAAAA` | BMS communication state | see `SBMS` `XXXXX` (§11.2) |
| 2 | `BBBBB` | BMS state | see `SBMS` `AAAAA` |
| 3 | `CCCCC` | BMS voltage | 0.1 V |
| 4 | `DDDDD` | BMS current | 0.01 A (signed) |
| 5 | `EEEEE` | BMS temperature | 0.1 °C (signed) |
| 6 | `FFFFF` | SOC | the spec says 0.1 Ah; this is most likely 0.1 % (see §14) |
| 7 | `HHHHH` | Remaining capacity | 0.1 Ah |
| 8 | `IIIII` | Rated capacity | 0.1 Ah |
| 9 | `JJJJJ` | BMS fault code | |
| 10 | `KKKKK` | BMS warning code | |
| 11 | `LLLLL` | BMS maximum charge current | 0.01 A |
| 12 | `MMMMM` | BMS CV voltage | 0.1 V |
| 13–17 | `NNNNN PPPPP QQQQQ RRRRR SSSSS` | Reserved 0–4 | |

### 8.23 GPPV\<n\> — PV of all parallel units

| | |
|---|---|
| Request | `GPPV<n>\r` |
| Response | `(A BBB.B CCC.C DDD.D EEE.E … RRR.R SSS.S\r` |

| # | Field | Meaning |
|---|---|---|
| 1 | `A` | Confirmed number of parallel units, 2–9 |
| 2k, 2k+1 (k = 1…9) | pairs of `xxx.x xxx.x` | PV voltage (V) and PV charge current (A) of unit k |

The units are ordered by device ID in ascending order: the smallest ID is unit 1.

### 8.24 CFG\<n\> — remote configuration mode

| | |
|---|---|
| Set | `CFG<n>\r`, n = 0 or 1 → `ACK\r` |
| Default | 0 |
| Read | `CFG?\r` → `(0\r` |
| Note | `CFG0` example: "remote configuration mode, parallel synchronisation". The spec does not define the meaning of 0 and 1 any further. |

### 8.25 I — serial number

| | |
|---|---|
| Request | `I\r` |
| Response | `#AAAAAAAAAAAAAAAAAAAAAAAAAAAR1.B.BBB  \r` |

| Part | Meaning |
|---|---|
| `#` | Start character |
| `A…A` (27 characters) | Serial number |
| `R`, `1`, `.` | Literal characters |
| `B.BBB` | DSP firmware version |
| 2 spaces | Padding |

**[Impl. note]** Parse this frame by fixed offsets, not by spaces: SN = `[1..27]`, then `R1.`, then the version.

---

## 9. Setting commands

Common behaviour for every command in this section:

- The inverter answers `ACK\r` on success and `NAK\r` on failure.
- The read-back form uses `?` characters (§3.3) and returns `(value\r`.
- The battery-voltage ranges depend on the nominal battery voltage (12 / 24 / 48 V).

### 9.1 TE\<n\> — enable feature flag

| | |
|---|---|
| Set | `TE<n>\r` → `ACK`/`NAK`, where `<n>` is one letter from the table below |
| Read | `TE?\r` → `(nnnn\r` |

**[Impl. note]** The read-back most likely returns the list of letters that are currently enabled. Verify this on a device.

| n | Feature | Default | Par. sync |
|---|---|---|---|
| A | Return to the default LCD page after an idle timeout | Enabled | √ |
| B | Fast grid over-voltage protection: high grid voltage during one mains cycle counts as grid loss | Disabled | √ |
| C | Automatic restart (3 attempts) after an overload fault | Enabled | √ |
| D | Automatic restart (3 attempts) after an over-temperature fault | Enabled | √ |
| E | Buzzer alarm on PV/grid loss | Enabled | √ |
| F | BMS interface disabled | Disabled | √ |
| G | Switch to grid after an overload in Battery mode, if the grid is OK | Disabled | √ |
| H | Automatic frequency adaptation | Enabled | √ |
| I | Battery power-saving mode | Disabled | √ |
| J | Start auto-adaptation | Enabled | |
| K | Charger allowed | Disabled | √ |
| L | "Battery not connected" warning | Disabled | |
| M | Phase lock at the zero crossing | Disabled | |
| N | Immediate equalization, after the next entry into Float | Disabled | √ |
| O | Mute the buzzer | Disabled | √ |
| P | Feed energy into the grid | Disabled | √ |
| Q | Battery equalization (EQ) mode | Disabled | √ |
| R | Invert the screen buttons | Disabled | |
| S | BMS communication | Disabled | √ |
| T | Combined display of three-phase data | Disabled | |
| U | Low-power discharge flag | Disabled | |
| V | Charge at maximum current | Disabled | |
| X | Automatic LCD switch-off | Enabled | √ |
| Y | Close the relay during inverter soft start | Disabled | √ |
| Z | Fast closing of the N relay | Disabled | |

`W` is not defined. Revision 18 also mentions the flags `a`, `b` and `c`, but they are not in the table.

### 9.2 TD\<n\> — disable feature flag

| | |
|---|---|
| Set | `TD<n>\r` → `ACK`/`NAK`. The letters are the same as for `TE`. |
| Read | `TD?\r` → `(nnnn\r`, most likely the list of disabled letters |

### 9.3 ED1 — factory reset

| | |
|---|---|
| Set | `ED1\r` → `ACK`/`NAK` |
| Effect | Restores all settings to their factory defaults |
| Allowed modes | Standby or Line mode only |

### 9.4 V\<nnn\> — output voltage

| | |
|---|---|
| Values | 100, 110, 115, 120, 127, 208, 220, 230, 240 V. The values 100–127 only change the **displayed** voltage, i.e. the voltage after an external step-down transformer; they require `HV1`. |
| Default | 220 |
| Examples | `V120\r` → `ACK`: displayed output after the transformer = 120 V. `V220\r` → `ACK`: actual inverter output = 220 V. |
| Read | `V???\r` → `(220 120\r` = actual output voltage and displayed output voltage |

### 9.5 F\<nn\> — system frequency

| | |
|---|---|
| Values | 50 or 60 Hz |
| Default | 50 |
| Example | `F50\r` → `ACK` |
| Allowed modes | Standby or Line mode only |
| Read | Use `F\r` (§8.1), field `RR.R` |

### 9.6 TBAT\<n\> — battery type

| n | Type |
|---|---|
| 0 | Lead-acid (sealed). CV fixed at 14.1 V per 12 V block, float fixed at 13.5 V. |
| 1 | Flooded (serviceable). CV fixed at 14.6 V per 12 V block, float fixed at 13.5 V. |
| 2 | Lithium |
| 3 | User-defined. The charge voltages are set with `TCCV` / `TCFV`. |

| | |
|---|---|
| Default | 0 |
| Example | `TBAT0\r` → `ACK` (lead-acid) |
| Read | `TBAT?\r` → `(0\r` |

### 9.7 CHGC\<nnn\> — maximum charge current

| | |
|---|---|
| Range | 010–120 A. For a PWM-type PV charge controller the range is 010–110 A. |
| Default | Given as "1" in the spec (sic) |
| Example | `CHGC020\r` → `ACK`: 20 A |
| Read | `CHGC???\r` → `(020\r` |

### 9.8 TCCV\<nn.n\> — CV charge voltage

| Battery | Range | Default |
|---|---|---|
| 12 V | 12.0–15.5 V | 14.1 V |
| 24 V | 28.0–29.0 V | 28.2 V |
| 48 V | 48.0–62.0 V | 56.4 V |

| | |
|---|---|
| Condition | The battery type must be user-defined. The CV voltage must be greater than the float voltage. |
| Example | `TCCV28.3\r` → `ACK` |
| Read | `TCCV????\r` → `(28.3\r` |

### 9.9 TCFV\<nn.n\> — float voltage

| Battery | Range | Default |
|---|---|---|
| 12 V | 12.0–15.5 V | 13.5 V |
| 24 V | 26.6–27.8 V | 27.0 V |
| 48 V | 48.0–62.0 V | 54.0 V |

| | |
|---|---|
| Condition | The battery type must be user-defined. The float voltage must be less than the CV voltage. |
| Example | `TCFV27.2\r` → `ACK` |
| Read | `TCFV????\r` → `(27.2\r` |

### 9.10 TCDV\<nn.n\> — second-output cut-off voltage

Requires the dual-output auxiliary board. In Battery mode, the second output is switched off when the battery voltage falls to this value.

| Battery | Range | Default |
|---|---|---|
| 12 V | 11.0–15.0 V | 12.0 V |
| 24 V | 22.0–32.0 V | 24.0 V |
| 48 V | 44.0–60.0 V | 48.0 V |

| | |
|---|---|
| Example | `TCDV46.0\r` → `ACK` |
| Read | `TCDV????\r` → `(46.0\r` |

### 9.11 TCQV\<nn.n\> — equalization voltage

When EQ mode is enabled, the battery is charged at this voltage for a set time at regular intervals.

| Battery | Range | Default |
|---|---|---|
| 12 V | 12.0–15.0 V | 14.6 V |
| 24 V | 24.0–30.0 V | 29.2 V |
| 48 V | 48.0–60.0 V | 58.4 V |

| | |
|---|---|
| Example | `TCQV25.0\r` → `ACK` |
| Read | `TCQV????\r` → `(25.0\r` |

### 9.12 TCVT\<nnnn\> — CV charge time

| | |
|---|---|
| Range | 0001–0720 min. Takes effect only with a forced 3-stage charge (`CST02`). |
| Default | 0000 |
| Example | `TCVT0720\r` → `ACK` |
| Read | `TCVT????\r` → `(0720\r` |

### 9.13 TDOT\<nnnn\> — second-output run time

Requires the dual-output auxiliary board.

| | |
|---|---|
| Range | 0000–0890 min, or 895. `0` = dual output off. `895` = no time limit. Any other value keeps the second output on for that many minutes in Battery mode. |
| Default | 0000 |
| Example | `TDOT0060\r` → `ACK` (60 min) |
| Read | `TDOT????\r` → `(0120\r` |

### 9.14 TCQT\<nnnn\> — equalization time

| | |
|---|---|
| Range | 0005–0900 min |
| Default | 0030 |
| Example | `TCQT0060\r` → `ACK` |
| Read | `TCQT????\r` → `(0030\r` |

### 9.15 TCQO\<nnnn\> — equalization timeout

| | |
|---|---|
| Range | 0005–0900 min |
| Default | 0060 |
| Example | `TCQO0120\r` → `ACK` |
| Read | `TCQO????\r` → `(0060\r` |

### 9.16 TCQI\<nnnn\> — equalization interval

| | |
|---|---|
| Range | 0024–2160 h |
| Default | 0720 (30 days) |
| Example | `TCQI1440\r` → `ACK` (60 days) |
| Read | `TCQI????\r` → `(0720\r` |

### 9.17 EOD\<nn.n\> — battery cut-off voltage

The inverter shuts down when the battery voltage falls to this value.

| Battery | Range | Default |
|---|---|---|
| 12 V | 10.0–12.0 V | 10.5 V |
| 24 V | 20.0–22.0 V | 21.0 V |
| 48 V | 40.0–48.0 V | 42.0 V |

| | |
|---|---|
| Condition | The battery type must be user-defined |
| Example | `EOD21.0\r` → `ACK` |
| Read | `EOD????\r` → `(21.0\r` |

### 9.18 TBLV\<nn.n\> — battery low-voltage warning

| Battery | Range | Default |
|---|---|---|
| 12 V | 10.5–13.5 V | 11.0 V |
| 24 V | 20.6–22.6 V | 22.0 V |
| 48 V | 42.0–54.0 V | 44.0 V |

| | |
|---|---|
| Condition | The battery type must be user-defined |
| Example | `TBLV21.0\r` → `ACK` |
| Read | `TBLV????\r` → `(21.0\r` |

### 9.19 LWDT\<nnnn\> — low-power discharge time

| | |
|---|---|
| Range | 60–480 min. Takes effect immediately, and only in APP mode. |
| Default | 480 |
| Example | `LWDT0240\r` → `ACK` (4 h) |
| Read | `LWDT????\r` → `(0480\r` |

### 9.20 BSOCU\<nnn\> — low-SOC shutdown

Takes effect only while communication with the BMS works.

| | |
|---|---|
| Range | 5–50 %, or 0. `0` disables the function: there is no low-SOC warning and no SOC limit for start-up. |
| Behaviour | The inverter shuts down when SOC < setpoint. The low-SOC warning is raised at setpoint + 5 % and cleared at setpoint + 10 %. From Standby, the inverter may start in Battery mode only when SOC ≥ setpoint + 10 %. |
| Default | 20 |
| Example | `BSOCU030\r` → `ACK` |
| Read | `BSOCU???\r` → `(030\r` |

### 9.21 BSOCG\<nnn\> — low SOC → switch to grid

Takes effect only while communication with the BMS works.

| | |
|---|---|
| Range | 10–90 %, or 0 (off) |
| Behaviour | When the output priority is PBG and SOC < setpoint, the inverter switches from Battery to Line mode. |
| Default | 50 |
| Example | `BSOCG075\r` → `ACK` |
| Read | `BSOCG???\r` → `(075\r` |

### 9.22 BSOCB\<nnn\> — high SOC → switch to battery

Takes effect only while communication with the BMS works.

| | |
|---|---|
| Range | 10–100 %, or 0 (off) |
| Behaviour | When the output priority is PBG and SOC > setpoint, the inverter switches from Line to Battery mode. |
| Default | 90 |
| Example | `BSOCB075\r` → `ACK` |
| Read | `BSOCB???\r` → `(075\r` |

### 9.23 UP\<nnnnn\> — displayed output power

| | |
|---|---|
| Range | 1–05000 VA. This is the virtual rating shown on the display. |
| Default | 0 |
| Example | `UP05000\r` → `ACK` (5 kVA) |
| Read | `UP?????\r` → `(05000\r` |

### 9.24 LT\<nnn\> — battery-to-grid return delay

| | |
|---|---|
| Range | 1–300 s. This is the delay before the inverter returns from Battery mode to Line mode. |
| Default | 5 |
| Example | `LT010\r` → `ACK` (10 s) |
| Read | `LT???\r` → `(010\r` |

### 9.25 FT\<n\> — fan fault detection

| | |
|---|---|
| Values | 0 = fan fault detection on, 1 = off |
| Default | 0 |
| Example | `FT1\r` → `ACK` |
| Read | `FT?\r` → `(1\r` |

### 9.26 HV\<n\> — output voltage type

| | |
|---|---|
| Values | 0 = high output voltage, 1 = low output voltage (output through a step-down transformer) |
| Default | 0 |
| Example | `HV1\r` → `ACK` |
| Read | `HV?\r` → `(1\r` |

### 9.27 OVP\<nnn\> — grid over-voltage protection

| | |
|---|---|
| Range | 264–280 V. This is the fast trip point, evaluated over one mains cycle. |
| Default | 264 |
| Example | `OVP280\r` → `ACK` |
| Read | `OVP???\r` → `(280\r` |

### 9.28 LVP\<nnn\> — grid under-voltage protection

| | |
|---|---|
| Range | 090–154 V in APP mode, 170–200 V in UPS mode |
| Default | 154 (APP), 185 (UPS) |
| Example | `LVP090\r` → `ACK` |
| Read | `LVP???\r` → `(154\r` |

### 9.29 CI1\<nn\> — maximum constant-current charge time

| | |
|---|---|
| Range | 01–99 h |
| Default | 12 |
| Example | `CI110\r` → `ACK` (10 h). Note that the parameter directly follows the digit `1` of the command name. |
| Read | `CI1??\r` → `(10\r` |

### 9.30 OPR\<nn\> — output source priority

| nn | Priority |
|---|---|
| 00 | Grid first |
| 01 | PV first |
| 02 | PV → battery → grid (PBG) |

| | |
|---|---|
| Default | 00 |
| Example | `OPR01\r` → `ACK` |
| Read | `OPR??\r` → `(01\r` |

### 9.31 OPM\<nn\> — output mode

| nn | Mode |
|---|---|
| 00 | APP (appliance). Typical grid↔battery transfer time 10 ms. |
| 01 | UPS. Typical transfer time 10 ms. |

| | |
|---|---|
| Default | 00 |
| Example | `OPM01\r` → `ACK` |
| Read | `OPM??\r` → `(01\r` |

### 9.32 CPR\<nn\> — charger source priority

| nn | Priority |
|---|---|
| 00 | Grid first |
| 01 | PV first |
| 02 | Grid and PV at the same time |
| 03 | PV only |

| | |
|---|---|
| Default | 02 |
| Example | `CPR01\r` → `ACK` |
| Read | `CPR??\r` → `(01\r` |

### 9.33 GCC\<nnn\> — maximum grid charge current

| | |
|---|---|
| Range | 1–120 A, sent as a 3-digit value. The heading of the spec says `<nn>`, but the range and the example use 3 digits. |
| Default | 030 |
| Example | `GCC050\r` → `ACK` |
| Read | `GCC???\r` → `(050\r` |

### 9.34 CST\<nn\> — charge mode

| nn | Mode |
|---|---|
| 00 | Automatic: 3-stage if the battery is below 12.5 V per 12 V block when charging starts, otherwise 2-stage. Also sets the maximum CV time to 8 h. |
| 01 | Forced 2-stage |
| 02 | Forced 3-stage |

| | |
|---|---|
| Default | 00 |
| Example | `CST01\r` → `ACK` |
| Read | `CST??\r` → `(01\r` |

### 9.35 BTG\<nn.n\> — battery voltage back to grid

This setting applies when `OPR` is not "grid first". If PV is insufficient, the battery
keeps discharging. When the battery falls to this voltage, the inverter returns to Line mode, so that some charge is kept in the battery.

| Battery | Range | Default |
|---|---|---|
| 12 V | 11.0–13.0 V | 11.5 V |
| 24 V | 22.0–26.0 V | 23.0 V |
| 48 V | 44.0–52.0 V | 46.0 V |

| | |
|---|---|
| Example | `BTG23.0\r` → `ACK` |
| Read | `BTG????\r` → `(23.0\r` |

### 9.36 BTB\<nn.n\> — battery voltage back to battery

This setting applies when `OPR` is not "grid first". When the battery has been recharged, from PV or from the grid, to this voltage, the inverter returns to Battery mode. `00.0` means "when the battery reaches Float".

| Battery | Range | Default |
|---|---|---|
| 12 V | 12.0–14.5 V or 00.0 | 13.5 V |
| 24 V | 24.0–29.0 V or 00.0 | 26.0 V |
| 48 V | 44.0–52.0 V or 00.0 | 54.0 V (sic: this is outside the stated range) |

| | |
|---|---|
| Example | `BTB26.0\r` → `ACK` |
| Read | `BTB????\r` → `(26.0\r` |

### 9.37 BTO\<nn.n\> — battery over-voltage protection

| Battery | Range | Default |
|---|---|---|
| 12 V | 14.0–16.0 V | 16.0 V |
| 24 V | 28.0–32.0 V | 32.0 V |
| 48 V | 56.0–61.0 V | 61.0 V |

| | |
|---|---|
| Example | `BTO30.0\r` → `ACK` |
| Read | `BTO????\r` → `(30.0\r` |

### 9.38 PAR\<n\> — parallel mode

| n | Mode |
|---|---|
| 0 | Standalone (single unit) |
| 1 | Single-phase parallel |
| 2 | Three-phase parallel, phase R |
| 3 | Three-phase parallel, phase S |
| 4 | Three-phase parallel, phase T |

| | |
|---|---|
| Default | 0 |
| Example | `PAR1\r` → `ACK` |
| Read | `PAR?\r` → `(0\r` |

### 9.39 SW\<nn\> — button panel variant

| | |
|---|---|
| Range | nn ≤ 99. `SW00` = generic version (the 4-button LCD). `SW01` = 3-button LCD. |
| Default | 00 (for the 5k model) |
| Example | `SW01\r` → `ACK` |
| Read | `SW??\r` → `(01\r` |
| Allowed modes | Standby and Line mode |

---

## 10. Calibration commands

> ⚠️ Calibration changes the measurement coefficients of the device. Use these commands only in service tools, never
> in routine monitoring code.

### 10.1 BA0 — reset battery voltage calibration

`BA0\r` → `ACK\r`. Restores the default battery-voltage calibration. The example in the spec says `BT0`; see §14.

### 10.2 B1A\<nn.n\> — battery calibration, high point

`B1A<nn.n>\r`, where nn.n is the actual battery voltage measured with a multimeter, in V.
Example: `B1A21.0\r` → `ACK`.

### 10.3 B2A\<nn.n\> — battery calibration, low point

`B2A<nn.n>\r`. Example: `B2A27.0\r` → `ACK`.

The battery calibration uses **two points**. Send both `B1A` and `B2A` to complete it.

### 10.4 PA0 — reset PV calibration

`PA0\r` → `ACK\r`. Restores the default PV-voltage calibration.

### 10.5 PV\<nnn.n\> — PV voltage calibration

`PV<nnn.n>\r`, where nnn.n is the actual PV voltage measured with a multimeter. Example: `PV150.0\r` → `ACK`.

### 10.6 Relative trims (±)

Format: `<CMD>+<nn>\r` or `<CMD>-<nn>\r`, where nn = 00–99 raw steps. `+` increases the measured
or displayed value, and `-` decreases it. Read the current trim with `<CMD>???\r`, which returns
`(2048\r`. The trim is a raw register, and 2048 is probably the neutral midpoint.

| Command | Calibrates | Parameter |
|---|---|---|
| `BUN±nn` | Bus voltage (displayed) | 00–99 |
| `LVR±nn` | Grid voltage | 00–99 |
| `VDR±nn` | Output voltage | Fine: `+.x` / `-.x`, x = 1–9 → 0.1–0.9 V. Coarse: `+0x` / `-0x` → 1–9 V. |
| `OCR±nn` | Output current (displayed) | 00–99 |
| `VR±nn` | Inverter voltage | Fine and coarse, as for `VDR`. Examples: `VR+02` = +2 V, `VR+.2` = +0.2 V. |
| `IR±nn` | Inverter current | 00–99 |
| `DCR±nn` | DC component of the output | 00–99 |
| `CHI±nn` | Charge current | 00–99 |
| `LWT±nn` | Output active power (W) | 00–99 |
| `LVA±nn` | Output apparent power (VA) | 00–99 |

---

## 11. Extended commands (SNMP / BMS board)

These commands are exchanged between the inverter and an external centralised monitoring or BMS board.
Here the **inverter** starts the exchange.

### 11.1 SNMP\n — presence handshake

- Every 10 s the inverter sends `GSNMP`.
- The board must reply `SNMP\n\r` within 10 s. The inverter answers `(ACK\r`.
- If 3 replies in a row are missing, the inverter treats the board as disconnected. It then clears the BMS data and blocks the BMS communication function.

### 11.2 SBMS\n — BMS data push

The board sends the following frame. The fields follow each other with no separator (the `+` signs in the spec only mark the boundaries):

```
SBMS\n XXXXX AAAAA BBBBB CCCCC DDDDD EEEEE FFFFF GGGGG HHHHH IIIII JJJJJ KKKKK LLLLLLLLLLLLLLLLLLLLLLLLL \r
```

The inverter answers `(ACK\r`. The presence rules of §11.1 also apply.

| Field | Meaning | Unit / values |
|---|---|---|
| `XXXXX` | BMS protocol state | `0x0000` = initialisation, `0x0001` = Growatt protocol, `0x0002` = China Tower protocol, `0x8000` = BMS link lost |
| `AAAAA` | Battery pack state | `0x0000` = single pack, `0x0100` = series-parallel pack, `0x0200` = series-parallel pack being formed |
| `BBBBB` | Battery voltage | 100 mV |
| `CCCCC` | Battery current | 10 mA, signed |
| `DDDDD` | Battery temperature | 0.1 °C, signed |
| `EEEEE` | Pack SOC | 0.1 % |
| `FFFFF` | Remaining capacity | 0.1 Ah |
| `GGGGG` | Rated capacity | 0.1 Ah |
| `HHHHH` | Pack fault information | |
| `IIIII` | Pack warning information | |
| `JJJJJ` | Maximum charge current | 10 mA |
| `KKKKK` | CV voltage | 100 mV |
| `L`×25 | Reserved | |

- Reserved fields, and BMS values that are not defined, are sent as **32767**.
- The inverter reads the other fields only when it has received a valid protocol state. If it receives no valid BMS protocol for 10 s in a row, or receives "link lost", it raises **warning 56**.
- **[Impl. note]** The spec does not say whether `XXXXX` is sent as decimal or as hex text. Confirm this on a device.

---

## 12. Custom commands

### 12.1 GCF — detailed fault status

| | |
|---|---|
| Request | `GCF\r` |
| Response | `( BT<16 bits> RL<16 bits> P1<17 bits> I1<16 bits> I2<16 bits> \r` |

| Tag | Bits | Meaning |
|---|---|---|
| `BT` | 16 | Battery status bits |
| `RL` | 16 | Grid status bits |
| `P1` | 17 (sic) | PFC status bits |
| `I1` | 16 | Inverter 1 status bits |
| `I2` | 16 | Inverter 2 status bits |

In every group, 1 = fault and 0 = normal. The meaning of the individual bits is not documented.
**[Impl. note]** Parse each group by its two-letter tag, not by its position.

---

## 13. Enumerations and bit tables

### 13.1 Fault codes (GWS `NN`, GPDAT `EE`, GFAIL `AA`)

| Code | Fault |
|---|---|
| 0 | No fault |
| 1 | Bus soft-start failure |
| 2 | Bus over-voltage |
| 3 | Bus under-voltage |
| 4 | DC/DC circuit fault |
| 5 | Over-temperature |
| 6 | Battery over-voltage |
| 7 | Bus boost (input) failure |
| 8 | Bus short circuit |
| 9 | Inverter soft-start failure |
| 10 | Inverter over-voltage |
| 11 | Inverter under-voltage |
| 12 | Inverter short circuit |
| 13 | Inverter reverse-power protection |
| 14 | Overload fault |
| 15 | Model mismatch fault |
| 16 | Bootloader missing |
| 17 | Firmware error |
| 18 | PV over-current |
| 19 | Duplicate serial number [parallel] |
| 20 | CAN communication failure [parallel] |
| 21 | Battery voltage difference too large [parallel] |
| 22 | Grid voltage difference too large [parallel] |
| 23 | Grid frequency difference too large [parallel] |
| 24 | Parallel output setting error [parallel] |
| 25 | Synchronisation lost [parallel] |
| 26 | Battery BMS fault |

### 13.2 GWS warning word 1 (`b15…b0`)

| Bit | Warning |
|---|---|
| 15 | Abnormal generator waveform |
| 14 | Shutdown due to low battery voltage |
| 13 | EEPROM failure |
| 12 | Low-power discharge |
| 11 | Fan fault |
| 10 | Reserved |
| 9 | Over-temperature |
| 8 | Reserved |
| 7 | Charge voltage too high |
| 6 | BMS lost |
| 5 | Battery cold-start failure (low SOC) |
| 4 | Battery low-SOC warning |
| 3 | Shutdown due to low battery SOC |
| 2 | Charger short circuit |
| 1 | Battery not connected |
| 0 | Low battery voltage |

### 13.3 GWS warning word 2 (`c15…c0`)

| Bit | Warning |
|---|---|
| 15 | Parallel settings inconsistent |
| 14 | Synchronisation lost |
| 13 | Parallel communication fault |
| 12 | Parallel firmware versions inconsistent |
| 11–9 | Reserved |
| 8 | Grid mismatch in parallel operation |
| 7 | Reserved |
| 6 | Weak PV energy |
| 5 | Reserved |
| 4 | Overload |
| 3–0 | Reserved |

### 13.4 GPV warning bits (`b15…b0`)

| Bit | Warning |
|---|---|
| 15–12 | Reserved |
| 11 | PV under-voltage |
| 10 | Charge current imbalance |
| 9 | Reverse charge current |
| 8 | Communication lost |
| 7 | Charge over-current |
| 6 | Charge channel 1 over-current |
| 5 | Charge channel 2 over-current |
| 4 | Channel 1 over-temperature warning |
| 3 | Channel 2 over-temperature warning |
| 2 | Battery over-voltage |
| 1 | Battery under-voltage |
| 0 | PV over-voltage |

### 13.5 Operating state codes

> ⚠️ The numeric codes **differ** between `GPDAT` and `GFAIL`. `GMOD` uses letters.

| State | `GMOD` | `GPDAT` field `B` | `GFAIL` field `BB` |
|---|---|---|---|
| Power-on (initial) | `P` | 0 | 0 |
| Shutdown | `D` | 1 | 5 |
| Fault | `F` | 2 | 4 |
| Standby | `S` | 3 | 1 |
| Line (grid) | `L` | 4 | 2 |
| Battery | `B` | 5 | 3 |
| Test | `X` | 6 | 6 |

### 13.6 GPSTS m=0: PFC warnings (`b15…b0`)

| Bit | Warning |
|---|---|
| 15 | Reserved |
| 14 | Battery under-voltage |
| 13 | Memory fault |
| 12 | Low-power discharge |
| 11 | Fan fault |
| 10 | Reserved |
| 9 | Over-temperature |
| 8 | Reserved |
| 7 | Charge over-current |
| 6 | BMS communication lost |
| 5 | Reserved |
| 4 | Phase sequence error |
| 3–2 | Reserved |
| 1 | Battery circuit open |
| 0 | Low battery voltage |

### 13.7 GPSTS m=0: INV warnings (`c15…c0`)

| Bit | Warning |
|---|---|
| 15 | Parallel setting error |
| 14 | Parallel synchronisation fault |
| 13 | Parallel communication fault |
| 12 | Parallel firmware versions inconsistent |
| 11–9 | Reserved |
| 8 | Wrong grid phase in parallel operation |
| 7 | Reserved |
| 6 | Insufficient PV power |
| 5 | Reserved |
| 4 | Overload |
| 3–2 | Reserved |
| 1 | Grid frequency lost |
| 0 | Grid voltage lost |

### 13.8 GPSTS m=1: grid status (`b15…b0`)

| Bit | Meaning |
|---|---|
| 15–12 | Reserved |
| 11–9 | Internal data |
| 8 | Grid lost (generator) |
| 7–4 | Internal data |
| 3 | Grid OK |
| 2 | Grid waveform lost |
| 1 | Grid frequency lost |
| 0 | Grid voltage lost |

### 13.9 GPSTS m=1: charger status (`c15…c0`)

| Bit | Meaning |
|---|---|
| 15–7 | Reserved |
| 6–4 | Internal data |
| 3–1 | DC/DC state, a 3-bit value: 0 = idle, 1 = charging, 2 = discharging |
| 0 | PV charging allowed |

---

## 14. Known issues in the vendor document

These are errors and contradictions found in the original. Handle them defensively in your code.

| # | Where | Issue | Suggested handling |
|---|---|---|---|
| 1 | `GLINE` example | The example has 9 fields; the template has 13. | Tolerant positional parsing (§4.2) |
| 2 | `FAN???` | The template `(AAA BBB C` has 3 fields; the example has 5. | Use the 5-field layout from the example |
| 3 | `TIME` | The write example uses `DATE051203` to set the time. | Use `TIMEhhmmss` |
| 4 | `BA0` | The example says `BT0`. | Send `BA0` |
| 5 | `VDR` / `VR` | The coarse-trim syntax shows `Vn-0x`. | Read it as `<CMD>-0x` |
| 6 | `GCC` | The heading says `<nn>`, but the range and the example use 3 digits. | Send 3 digits (`GCC050`) |
| 7 | `CHGC` | The default is given as "1". | Read the actual value back |
| 8 | `TCQV` | The example text was copied from `BTG` ("return to grid 25 V"). | Ignore that wording |
| 9 | `V` | Refers to "the HV command, see 6.18"; the correct reference is §9.26. | — |
| 10 | `TBAT` vs `TCCV/TCFV/EOD/TBLV` | `TBAT` defines 3 = user-defined, but the dependent commands say "send `TBAT2`" (2 = lithium). | Verify on a device. Probably user-defined = 3. |
| 11 | `GFAIL` | Field `GG.GG` is not described. The description says `CCCC` while the template has `CCCCC`. The header says "for unit `<n>`", but the command has no parameter. | Map by position (§8.21) |
| 12 | `GBMS` | The SOC unit is given as "0.1 Ah". | Treat SOC as 0.1 % |
| 13 | `GLINE` energy | The unit is "tens of watts" (not Wh). | Treat as ×10 Wh, like `GOP`/`GPV` |
| 14 | `SVFW` | The template ends with `\r\r`. | Accept one or two CRs |
| 15 | §6 table | The "Bypass or Standby" action row lists `SOFF` a second time. | It means `SPOFF` |
| 16 | `TE` | There is no flag `W`. Revision 18 mentions `a b c`, which are not listed. | Handle unknown letters |
| 17 | `BTB` 48 V | The default 54.0 V is outside the stated range 44.0–52.0 V. | Read the actual value back |
| 18 | `GCF` | The `P1` group has 17 bits; the other groups have 16. | Parse by tag, not by length |
| 19 | `F` | The cell-count field is described as "×120", with two different formats. | Parse as a float |
| 20 | Command table | Counts per category ("24 queries", "40 settings") do not match the sections exactly. `CFG` appears under both Settings and Queries. | — |

---

## 15. Glossary

| Term | Meaning |
|---|---|
| Host | The PC or controller that sends commands (上位机) |
| Line mode | The load is supplied from the grid (mains) |
| Battery mode | The load is supplied by the inverter from the battery or PV |
| Bypass | The output is connected directly to the grid |
| CV | Constant voltage charge stage (absorption) |
| Float | Maintenance charge stage (floating charge) |
| EQ | Equalization charge |
| PBG | Output priority PV → Battery → Grid (`OPR02`) |
| APP / UPS | Output modes: appliance or UPS (`OPM`) |
| PFC | Power-factor-correction stage, the grid-side converter |
| INV | Inverter stage, the DC→AC converter |
| DC/DC | Battery charger/discharger converter |
| MPPT | Maximum power point tracking of the PV input |
| BMS | Battery management system (for lithium packs) |
| SOC | State of charge, % |
| Parallel system | Several inverters sharing a load. Units are addressed by `<n>`. |

---

## 16. Vendor revision history

| Rev. | Date | Change |
|---|---|---|
| 01 | 2021-05-11 | First draft (Edward) |
| 02 | 2022-04-13 | Added battery equalization (EQ) mode settings and status |
| 03 | 2022-05-27 | Updated GOP, GCHG, GPV, GLINE |
| 04 | 2022-06-06 | Updated the TCQ series, LBDT, LVP, TE, PAR. Removed BEQ. |
| 05 | 2022-06-15 | Updated FAN |
| 06 | 2022-06-21 | Updated TEZ |
| 07 | 2022-07-05 | Updated TER, TET |
| 08 | 2022-07-16 | Energy statistics in GOP, GPV, GLINE. Updated TIME, DATE, GTMP. |
| 09 | 2022-08-05 | GCHG field widths, support for charge current > 100 A |
| 10 | 2022-08-09 | GCC field widths, support for charge current > 100 A |
| 11 | 2022-09-14 | Fixed the LWDT description |
| 12 | 2022-10-08 | Updated SPON, SPOFF, GPDAT, GPSTS, GPID, SBAUD |
| 13 | 2022-10-10 | GCHG field widths |
| 14 | 2022-10-10 | Fixed the SVFW description |
| 15 | 2022-10-17 | Fixed the calibration ranges |
| 16 | 2022-11-09 | BMS communication on/off (TES/TDS), SOC management (BSOC) |
| 17 | 2022-11-14 | Updated TDOT, TCDV. Removed Q1. |
| 18 | 2023-08-09 | Added GCF; I, CFG, GPPV, GBMS, GFAIL; SW; TE flags (F J P U V W X a b c); Q. Removed SBAUD. |
| 19 | 2023-12-07 | Extended GWS. Added PA0. |
| 20 | 2024-04-15 | BTO: upper limit for a 48 V battery changed to 61.0 V |
| 21 | 2024-05-06 | Changed the GPV units (charge amount) |
