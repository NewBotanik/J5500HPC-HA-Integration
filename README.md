---
description: Native Home Assistant Integration for JSD SOLAR J5500HPC/J5500HP inverters and Gobel Power battery BMS
---

# JSDSolar J5500HPC/J5500HP Home Assistant Integration (JSD SOLAR inverter, JK BMS, Pace BMS, TDT BMS)

[Deutsch](docs/de/README.md) | [Українська](docs/uk/README.md)

> **Note**: This is a fork of [fancyui/Gobel-Battery-HA-Integration](https://github.com/fancyui/Gobel-Battery-HA-Integration) with added support for JSD SOLAR J5500HPC/J5500HP inverters.

The ultimate Home Assistant custom integration for smart energy storage monitoring. This integration communicates directly with your LiFePO4 battery banks running Pace BMS, JK BMS, or TDT BMS hardware, registering them as native entities in Home Assistant.

Unlike the previous Add-on version, this integration **does not require an MQTT broker**. It sets up device and sensor entities directly inside Home Assistant, supporting multi-device setups (e.g. multiple battery banks with different IPs/serial ports) via the visual configuration UI.

---

## Key Features & Capabilities:
* **Multi-BMS Compatibility:** Native support for Pace BMS (RS232/RS485/WiFi), JK BMS (55AA passive protocol), and TDT BMS (RS232).
* **JSD SOLAR Inverters:** Monitoring and optional control of JSD SOLAR inverters such as the J5500HPC over RS232 (grid, output, battery, PV, temperatures, energy counters, faults and warnings, all settings, parallel units).
* **Versatile Connectivity Options:** Connect directly via RS232-USB, RS232-to-Ethernet, RS232-to-WiFi, RS485-to-Ethernet, or RS485-to-WiFi.
* **Direct Integration (No MQTT Required):** Create native Home Assistant sensors and binary sensors directly for cell voltages, capacity, current, and faults.
* **Dynamic Multi-Device & Grouping:** Group overall metrics (Total SOC, Total Voltage, Total Current, etc.) under an aggregate Device, and create child Devices for each physical parallel-connected slave battery pack (fully compatible with Master-Slave dial structures).
* **Config Flow GUI Setup:** Easy setup via the HA "Devices & Services" menu. No YAML editing, command-line arguments, or manual configuration file creation required.

---

## Pace BMS Connection Instructions:
- **RS232-WIFI/Ethernet module or RS232-USB cable needed**
- **Connection Port**: Connect Home Assistant to the **RS232** or **WIFI** interface of the Pace BMS.
- **Master BMS**: The connection must be made to the **Master BMS**.
- **DIP Switch Settings**: Ensure the DIP switch (Dial) of the master BMS is set to **1000**.

## JK BMS Connection Instructions:
- **RS485-WIFI/Ethernet module or RS485-USB cable needed**
- **Connection Port**: Connect Home Assistant to the **RS485B** or **RS485C** interface of the JK BMS.
- **Master BMS**: The connection must be made to the **Master BMS**.
- **DIP Switch Settings**: Ensure the DIP switch (Dial) of the master BMS is set to **0000**.

## JSD SOLAR Inverter (e.g. J5500HPC) Connection Instructions:
- **RS232-USB cable, or an RS232-to-WiFi/Ethernet bridge** (for example an ESP8266 running ESPHome `stream_server`, or a USR/Elfin module in transparent TCP mode).
- **Connection Port**: the inverter's **RS232** DB9 port: pin 2 = inverter TX, pin 3 = inverter RX, pin 5 = GND.
- **Serial settings**: **2400 baud, 8N1**. Select `JSD_SOLAR` as the BMS type; the serial step then proposes 2400 baud. A bridge must also be set to 2400 8N1.
- **Poll interval**: one cycle reads about 15 ASCII frames, which takes about 5 s at 2400 baud. A poll interval of **10 s or more** is recommended.
- The inverter speaks its own JSD ASCII protocol ([docs/protocols/protocol.JSDSOLAR.en.md](docs/protocols/protocol.JSDSOLAR.en.md)), not PI30/PI18 (Voltronic), so `pipsolar`-style integrations do not work with it.
- **Control (optional)**: by default the integration only reads. To change settings, open the integration, click **Configure** and turn on **jsd_enable_control**. This adds `number`/`select` entities for all settings, switches for the feature flags, and buttons for power on/off, energy counter reset, factory reset and clock sync. Every write is checked against the allowed range, must be confirmed by the inverter (`ACK`) and is read back. The **Power Off**, **Reset Energy Counters** and **Factory Reset** buttons start disabled: enable them in the entity settings if you need them. Some settings are accepted only in certain operating modes; a refused write shows an error in Home Assistant.
- Calibration commands are not supported.

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
4. Follow the configuration steps on-screen to choose your BMS type, connection method (Network vs. Serial), and input connection parameters.
5. If you have multiple battery banks with different IPs/ports, simply click **Add Integration** again to configure additional instances.