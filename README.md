---
description: Native Home Assistant integration for JSD SOLAR J5500HPC/J5500HP inverters, the JK-DZ11-B2A24S active balancer and Pace/JK/TDT battery BMS
---

# JSDSolar J5500HPC/J5500HP Home Assistant Integration

**JSD SOLAR inverter** · JK-DZ11-B2A24S active balancer · Pace / JK / TDT battery BMS

[Deutsch](docs/de/README.md) | [Українська](docs/uk/README.md)

> **Note**: This is a fork of [fancyui/Gobel-Battery-HA-Integration](https://github.com/fancyui/Gobel-Battery-HA-Integration) with added support for JSD SOLAR J5500HPC/J5500HP inverters and the JK-DZ11-B2A24S balancer.

A native Home Assistant custom integration for **JSD SOLAR J5500HPC/J5500HP inverters**. It talks to the inverter over RS232 (directly or through a WiFi/Ethernet bridge), shows everything the inverter reports as Home Assistant entities, and can optionally change its settings, also from automations. The same integration also supports the JK-DZ11-B2A24S active balancer and LiFePO4 battery banks with Pace, JK or TDT BMS.

It **does not need an MQTT broker**: devices and entities are created directly in Home Assistant and set up in the UI. Several devices (for example an inverter, a balancer and a battery bank) are added as separate entries.

---

## Key Features & Capabilities:

### JSD SOLAR inverter (J5500HPC/J5500HP)
* **Monitoring:** grid, output, inverter stage, DC bus, battery, PV, temperatures, fans, energy counters, BMS data seen by the inverter, faults and warnings, the last fault snapshot, parallel units.
* **Control (optional):** every setting as a `number`/`select` entity (battery voltages as 0.1 V sliders), feature flags as switches, buttons for power on/off, energy counter reset and clock sync. Every write is range-checked, confirmed by the inverter (`ACK`, retried on `NAK`) and read back.
* **Automations:** actions to send any command and get the reply, and to re-read chosen entities at once instead of waiting for the poll cycle.
* **Clock sync (optional):** keeps the inverter date and time equal to Home Assistant.
* **Diagnostics:** debug logging in three depths, down to every frame on the wire with its response time.

### JK-DZ11-B2A24S active balancer
* Cell voltages, balancing current and state, temperature, alarms over RS485; optional control of cell count, trigger delta, maximum current and balancing on/off.

### Battery BMS
* **Pace BMS** (RS232/RS485/WiFi), **JK BMS** (55AA passive protocol) and **TDT BMS** (RS232): cell voltages, capacity, current, temperatures, faults.
* **Multi-pack grouping:** overall metrics (total SOC, voltage, current) on an aggregate device, and a child device for each parallel-connected slave pack.

### General
* **Connectivity:** RS232-USB, RS485-USB, or an RS232/RS485-to-Ethernet/WiFi bridge.
* **Config Flow GUI setup:** add and configure everything under **Devices & Services**, no YAML.

---

## JSD SOLAR Inverter (e.g. J5500HPC) Connection Instructions:


<p><img src="img/J5500HPC.avif" alt="JSD SOLAR J5500HPC inverter" width="48%"> <img src="img/J5500HPC_02.png" alt="JSD SOLAR J5500HPC inverter" width="48%"></p>

- **RS232-USB cable, or an RS232-to-WiFi/Ethernet bridge** (for example an ESP8266 running ESPHome `stream_server`, or a USR/Elfin module in transparent TCP mode).
- **Connection Port**: the inverter's **RS232** DB9 port: pin 2 = inverter TX, pin 3 = inverter RX, pin 5 = GND.
- **Serial settings**: **2400 baud, 8N1**. Select `JSD_SOLAR` as the BMS type; the serial step then proposes 2400 baud. A bridge must also be set to 2400 8N1.
- **Poll interval**: one cycle reads about 15 ASCII frames, which takes about 5 s at 2400 baud. A poll interval of **10 s or more** is recommended; it can be changed later under **Configure**, together with the serial port, baud rate or bridge IP/port.
- The inverter speaks its own JSD ASCII protocol ([docs/protocols/protocol.JSDSOLAR.en.md](docs/protocols/protocol.JSDSOLAR.en.md)), not PI30/PI18 (Voltronic), so `pipsolar`-style integrations do not work with it.
- **Control (optional)**: by default the integration only reads. To change settings, open the integration, click **Configure** and turn on **Enable inverter control**. This adds `number`/`select` entities for all settings, switches for the feature flags, and buttons for power on/off, energy counter reset, factory reset and clock sync. Every write is checked against the allowed range, must be confirmed by the inverter (`ACK`; a `NAK` or no answer is retried up to 5 times, 1 s apart) and is read back. Battery-voltage settings are sliders in 0.1 V steps. The **Power Off**, **Reset Energy Counters** and **Factory Reset** buttons start disabled: enable them in the entity settings if you need them. Some settings are accepted only in certain operating modes; a refused write shows an error in Home Assistant.
- **Debug logging**: under **Configure**, turn on **Enable debug logging** and pick a **Logging depth**: *Basic* (cycle summary, identity, writes), *Protocol* (+ every frame sent to and received from the inverter, with response time) or *Protocol + parsing* (+ the parsed values of every command). The records go to **Settings → System → Logs**. Turn it off when done: the deep levels write a lot.
- **Clock sync (optional)**: with control on, **Configure → Sync inverter date and time** compares the inverter clock with Home Assistant after every date/time read-back and corrects a drift over 30 s (at most once an hour).
- **Actions for automations**: send raw commands and refresh entities on demand, see [JSD SOLAR: commands and refresh in automations](#jsd-solar-commands-and-refresh-in-automations).
- Calibration commands are not supported.

---

## JSD SOLAR: commands and refresh in automations

The integration adds two actions for the inverter. Both appear in **Developer Tools → Actions** and in the automation editor (**Add action → JSDSolar J5500HPC/J5500HP**), so you can try them before you put them into an automation.

### Before you start

- Reading (queries) works without any options.
- Sending a write command needs **Configure → Enable inverter control**.
- To see the frames on the wire, turn on **Enable debug logging** with depth *Protocol* (see above).
- Command syntax is in [docs/protocols/protocol.JSDSOLAR.en.md](docs/protocols/protocol.JSDSOLAR.en.md). Send the command without the trailing CR.

### Send a command: `jsdsolar_j5500hpc_j5500hp.send_command`

| Field | Required | Meaning |
|---|---|---|
| `command` | yes | Command text, e.g. `GBAT`, `CPR??`, `CPR03` |
| `attempts` | no, default 1 | Resend up to this many times (1–10) while the inverter answers `NAK` or nothing |
| `device_id` | only with several inverters | The inverter device |

Try it in **Developer Tools → Actions**: choose *Send inverter command*, switch to YAML mode, paste

```yaml
action: jsdsolar_j5500hpc_j5500hp.send_command
data:
  command: GBAT
```

and press **Perform action**. The response appears below:

```yaml
command: GBAT
response: (052.4 031.50 16 42.0 44.0
status: ok
attempts: 1
elapsed_ms: 412
parsed:
  battery_voltage: 52.4
  battery_discharge_current: 31.5
  setting_battery_cells: 16
  setting_battery_cutoff_voltage: 42
  setting_battery_warning_voltage: 44
```

| `status` | Meaning |
|---|---|
| `ok` | The inverter sent data (a query reply) |
| `ack` | The inverter accepted a write |
| `nak` | The inverter refused the command: out of range, not allowed in the current mode, or unknown |
| `no_answer` | No reply within 3 s per attempt |

`parsed` is present only for queries the integration knows (the fast set, `I`/`SVFW`/`F`, setting read-backs such as `CPR??`, `TE?`, `DATE??????`, `TIME??????`, `TCQN????`, `GFAIL`, `GCF`).

What may be sent:

- **Queries** are always allowed: anything that contains `?` (`CPR??`, `GCC???`, `BTB????`, `TE?`) and the query commands of the protocol (`GMOD`, `GBAT`, `GPV`, `GOP`, `GLINE`, `BL`, `GWS`, `I`, `F`, `GPDAT1` …).
- **Everything else is a write** (`CPR03`, `OPR01`, `GCC030`, `TEO`, `TDO`, `SON` …) and needs inverter control. A write is logged at INFO level.
- **Calibration commands** (§10: `BA0`, `B1A…`, `B2A…`, `PA0`, `PV<nnn.n>`, `BUN±`, `VR±` …) are always refused.

`send_command` does not update the entities. Call `refresh` afterwards (below).

Typical commands:

| Purpose | Query | Write |
|---|---|---|
| Charger priority (0 grid first, 1 PV first, 2 grid and PV, 3 PV only) | `CPR??` | `CPR00` … `CPR03` |
| Output priority (0 grid first, 1 PV first, 2 PV-battery-grid) | `OPR??` | `OPR00` … `OPR02` |
| Max grid charge current, A | `GCC???` | `GCC030` (3 digits) |
| Battery back-to-grid voltage | `BTG????` | `BTG47.5` (`nn.n`) |
| Feature flags | `TE?` (enabled letters) | `TE<letter>` on, `TD<letter>` off |
| Date / time | `DATE??????`, `TIME??????` | `DATE251203`, `TIME051203` |

For settings that have an entity, `select.select_option` and `number.set_value` are simpler: they check the range, retry up to 5 times and read the value back by themselves.

### Refresh entities now: `jsdsolar_j5500hpc_j5500hp.refresh`

The integration polls the measurements about every 5 s, but the settings, feature flags, clock and fault snapshot go through a slow queue (3 commands per cycle), so a setting can take minutes to update. `refresh` re-reads at once only the commands behind the chosen entities (`battery_voltage` → `GBAT`, `setting_charger_priority` → `CPR??`, a feature switch → `TE?`), updates those entities and returns the fresh values:

```yaml
action: jsdsolar_j5500hpc_j5500hp.refresh
target:
  entity_id:
    - select.j5500hpc_setting_charger_priority
    - sensor.j5500hpc_battery_voltage
```

Response:

```yaml
values:
  select.j5500hpc_setting_charger_priority: PV only
  sensor.j5500hpc_battery_voltage: 52.4
```

Entities read from the same command cost one request. An entity that the integration has not read yet (right after a restart) gives an error; wait for the first poll cycles.

The standard **`homeassistant.update_entity`** action on an inverter entity does the same targeted re-read, without a response.

### Examples

Switch the charger priority with a raw command, check the answer, and refresh the entity:

```yaml
actions:
  - action: jsdsolar_j5500hpc_j5500hp.send_command
    data:
      command: CPR03
      attempts: 5
    response_variable: reply
  - if:
      - condition: template
        value_template: "{{ reply.status != 'ack' }}"
    then:
      - action: persistent_notification.create
        data:
          message: "Inverter refused CPR03: {{ reply.status }} after {{ reply.attempts }} attempts"
      - stop: "CPR03 not accepted"
  - action: jsdsolar_j5500hpc_j5500hp.refresh
    target:
      entity_id: select.j5500hpc_setting_charger_priority
```

Read a fresh value right before a decision:

```yaml
actions:
  - action: jsdsolar_j5500hpc_j5500hp.refresh
    target:
      entity_id: sensor.j5500hpc_battery_voltage
    response_variable: fresh
  - if:
      - condition: template
        value_template: "{{ fresh['values']['sensor.j5500hpc_battery_voltage'] | float(0) < 48 }}"
    then:
      - action: select.select_option
        target:
          entity_id: select.j5500hpc_setting_output_priority
        data:
          option: Grid first
```

Use the value of a query that has no entity:

```yaml
actions:
  - action: jsdsolar_j5500hpc_j5500hp.send_command
    data:
      command: GCF
    response_variable: gcf
  - action: persistent_notification.create
    data:
      message: "GCF: {{ gcf.response }}"
```

### Errors

The action fails (and the automation stops, unless the step has `continue_on_error: true`) when the command is a write and inverter control is off, the command is a calibration command, the target is not a JSD SOLAR inverter entity, or a refreshed entity has not been read yet. A `nak` or `no_answer` reply is not an error: check `status`.

---

## JK-DZ11-B2A24S Active Balancer (RS485) Connection Instructions:


<img src="img/JK-DZ11-B2A24S-RS485.avif" alt="JK-DZ11-B2A24S active balancer with RS485" width="360">

- **RS485-USB cable or RS485-to-Ethernet/WiFi bridge** connected to the balancer's RS485 port (A to A, B to B). A/B labels differ between vendors: if the balancer does not answer, or a debug log shows only a short `55 95 01 FF 01` reply, swap A and B.
- **Device type**: `JK_BALANCER`. This is a different protocol from `JK_PB`: the balancer only answers requests and never streams data, so a `JK_PB` entry stays unavailable with it.
- **Serial settings**: **9600 baud, 8N1** (the serial step proposes 9600). A bridge must be set the same way.
- **Address**: the RS485 slave address of the balancer, 1 by default; change it under **Configure** if needed.
- **Control (optional)**: under **Configure**, turn on **Enable balancer control** to change the cell count (2–24), balancing trigger delta (2–1000 mV), maximum balancing current (30–2000 mA on the 2 A model) and switch balancing on or off.
- **Not available over RS485**: cell connection (balance lead) resistances and the "balancing start voltage"; the balancer provides them only over Bluetooth in the JK app.
- Protocol: [docs/protocols/JK-DZ11B2A224S_RS485_V1.3_en.md](docs/protocols/JK-DZ11B2A224S_RS485_V1.3_en.md).

---

## Pace BMS Connection Instructions:
- **RS232-WIFI/Ethernet module or RS232-USB cable needed**
- **Connection Port**: Connect Home Assistant to the **RS232** or **WIFI** interface of the Pace BMS.
- **Master BMS**: The connection must be made to the **Master BMS**.
- **DIP Switch Settings**: Ensure the DIP switch (Dial) of the master BMS is set to **1000**.
- **Current resolution**: most PACE BMS report current in 0.01 A. If current and power look 10 times too small, set **Configure → PACE current resolution** to 0.1 A.

## JK BMS Connection Instructions:
- **RS485-WIFI/Ethernet module or RS485-USB cable needed**
- **Connection Port**: Connect Home Assistant to the **RS485B** or **RS485C** interface of the JK BMS.
- **Master BMS**: The connection must be made to the **Master BMS**.
- **DIP Switch Settings**: Ensure the DIP switch (Dial) of the master BMS is set to **0000**.

---

## Installation:

### Option 1: Via HACS (Recommended)
1. Ensure [HACS (Home Assistant Community Store)](https://hacs.xyz/) is installed.
2. Go to **HACS -> Integrations** in Home Assistant.
3. Click the three dots in the top-right corner and select **Custom repositories**.
4. Paste the URL of this repository: `https://github.com/NewBotanik/J5500HPC-HA-Integration`
5. Select **Integration** as the Category and click **Add**.
6. Find the **JSDSolar J5500HPC/J5500HP** integration in HACS and click **Download**.
7. Restart Home Assistant.

### Option 2: Manual Installation
1. Download the latest release or clone the repository.
2. Copy the `custom_components/jsdsolar_j5500hpc_j5500hp` directory into your Home Assistant `/config/custom_components/` folder.
3. Restart Home Assistant.

---

## Configuration:
1. In Home Assistant, go to **Settings -> Devices & Services**.
2. Click **Add Integration** in the bottom-right corner.
3. Search for **JSDSolar J5500HPC/J5500HP** and click to set it up.
4. Choose the device type (JSD SOLAR inverter, JK balancer or a BMS) and the connection (network or serial). The next step asks only what that type needs: for the inverter and the balancer just the device name and poll interval; for a BMS also the port type, max parallel packs and JK pack numbering. Then enter the bridge IP/port or the serial port and baud rate.
5. For more devices (for example an inverter and a balancer, or several battery banks with different IPs/ports), click **Add Integration** again for each of them.