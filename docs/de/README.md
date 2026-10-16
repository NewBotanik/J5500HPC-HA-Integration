# JSDSolar J5500HPC/J5500HP Home Assistant Integration

**JSD SOLAR Wechselrichter** · aktiver Balancer JK-DZ11-B2A24S · Batterie-BMS Pace / JK / TDT

[English](../../README.md) | [Українська](../uk/README.md)

> **Hinweis**: Dies ist ein Fork von [fancyui/Gobel-Battery-HA-Integration](https://github.com/fancyui/Gobel-Battery-HA-Integration) mit zusätzlicher Unterstützung für JSD SOLAR J5500HPC/J5500HP Wechselrichter und den Balancer JK-DZ11-B2A24S.

Eine native benutzerdefinierte Home Assistant-Integration für **JSD SOLAR J5500HPC/J5500HP Wechselrichter**. Sie kommuniziert mit dem Wechselrichter über RS232 (direkt oder über eine WiFi/Ethernet-Bridge), stellt alle Werte des Wechselrichters als Home Assistant-Entitäten bereit und kann auf Wunsch seine Einstellungen ändern, auch aus Automatisierungen. Dieselbe Integration unterstützt außerdem den aktiven Balancer JK-DZ11-B2A24S und LiFePO4-Batteriebänke mit Pace-, JK- oder TDT-BMS.

Sie **benötigt keinen MQTT-Broker**: Geräte und Entitäten werden direkt in Home Assistant angelegt und über die Benutzeroberfläche eingerichtet. Mehrere Geräte (zum Beispiel ein Wechselrichter, ein Balancer und eine Batteriebank) werden als separate Einträge hinzugefügt.

---

## Hauptmerkmale & Funktionen:

### JSD SOLAR Wechselrichter (J5500HPC/J5500HP)
* **Überwachung:** Netz, Ausgang, Wechselrichterstufe, DC-Bus, Batterie, PV, Temperaturen, Lüfter, Energiezähler, vom Wechselrichter empfangene BMS-Daten, Fehler und Warnungen, Momentaufnahme des letzten Fehlers, Parallelgeräte.
* **Steuerung (optional):** jede Einstellung als `number`/`select`-Entität (Batteriespannungen als Schieberegler in 0,1-V-Schritten), Funktionsflags als Schalter, Tasten für Ein/Aus, Zurücksetzen der Energiezähler und Uhrzeitabgleich. Jeder Schreibvorgang wird auf den zulässigen Bereich geprüft, vom Wechselrichter bestätigt (`ACK`, bei `NAK` wiederholt) und zurückgelesen.
* **Automatisierungen:** Aktionen, um beliebige Befehle zu senden und die Antwort zu erhalten, und um ausgewählte Entitäten sofort neu zu lesen, statt auf den Abfragezyklus zu warten.
* **Uhrzeitabgleich (optional):** hält Datum und Uhrzeit des Wechselrichters gleich mit Home Assistant.
* **Diagnose:** Debug-Protokollierung in drei Tiefen, bis hin zu jedem Frame auf der Leitung mit seiner Antwortzeit.

### Aktiver Balancer JK-DZ11-B2A24S
* Zellspannungen, Balancing-Strom und -Zustand, Temperatur, Alarme über RS485; optionale Steuerung von Zellenanzahl, Auslösedifferenz, maximalem Strom und Balancing ein/aus.

### Batterie-BMS
* **Pace BMS** (RS232/RS485/WiFi), **JK BMS** (55AA-Passivprotokoll) und **TDT BMS** (RS232): Zellspannungen, Kapazität, Strom, Temperaturen, Fehler.
* **Gruppierung mehrerer Packs:** Gesamtwerte (Gesamt-SOC, Spannung, Strom) auf einem übergeordneten Gerät und ein untergeordnetes Gerät für jedes parallel geschaltete Slave-Pack.

### Allgemein
* **Anbindung:** RS232-USB, RS485-USB oder eine RS232/RS485-zu-Ethernet/WiFi-Bridge.
* **Einrichtung über die Benutzeroberfläche (Config Flow):** alles wird unter **Geräte & Dienste** hinzugefügt und konfiguriert, ohne YAML.

---

## Anschlussanleitung für den JSD SOLAR Wechselrichter (z. B. J5500HPC):

<img src="../../img/J5500HPC.avif" alt="JSD SOLAR J5500HPC Wechselrichter" width="360">
<img src="../../img/J5500HPC_02.png" alt="JSD SOLAR J5500HPC Wechselrichter" width="360">

- **RS232-USB-Kabel oder eine RS232-zu-WiFi/Ethernet-Bridge** (zum Beispiel ein ESP8266 mit ESPHome `stream_server` oder ein USR/Elfin-Modul im transparenten TCP-Modus).
- **Anschlussport**: der **RS232**-DB9-Port des Wechselrichters: Pin 2 = TX des Wechselrichters, Pin 3 = RX des Wechselrichters, Pin 5 = GND.
- **Serielle Einstellungen**: **2400 Baud, 8N1**. Wählen Sie `JSD_SOLAR` als Gerätetyp; der Schritt für die serielle Verbindung schlägt dann 2400 Baud vor. Eine Bridge muss ebenfalls auf 2400 8N1 eingestellt sein.
- **Abfrageintervall**: Ein Zyklus liest etwa 15 ASCII-Frames, was bei 2400 Baud etwa 5 s dauert. Empfohlen wird ein Abfrageintervall von **10 s oder mehr**; es lässt sich später unter **Configure** ändern, ebenso der serielle Port, die Baudrate oder IP/Port der Bridge.
- Der Wechselrichter spricht sein eigenes JSD-ASCII-Protokoll ([docs/protocols/protocol.JSDSOLAR.en.md](../protocols/protocol.JSDSOLAR.en.md)), nicht PI30/PI18 (Voltronic), daher funktionieren Integrationen im Stil von `pipsolar` mit ihm nicht.
- **Steuerung (optional)**: Standardmäßig liest die Integration nur. Um Einstellungen zu ändern, öffnen Sie die Integration, klicken auf **Configure** und aktivieren **Enable inverter control**. Dadurch kommen `number`/`select`-Entitäten für alle Einstellungen, Schalter für die Funktionsflags sowie Tasten für Ein/Aus, Zurücksetzen der Energiezähler, Werksreset und Uhrzeitabgleich hinzu. Jeder Schreibvorgang wird auf den zulässigen Bereich geprüft, muss vom Wechselrichter bestätigt werden (`ACK`; bei `NAK` oder ohne Antwort bis zu 5 Wiederholungen im Abstand von 1 s) und wird zurückgelesen. Einstellungen der Batteriespannung sind Schieberegler in 0,1-V-Schritten. Die Tasten **Power Off**, **Reset Energy Counters** und **Factory Reset** sind anfangs deaktiviert: Aktivieren Sie sie bei Bedarf in den Entitätseinstellungen. Manche Einstellungen nimmt der Wechselrichter nur in bestimmten Betriebsarten an; ein abgelehnter Schreibvorgang wird in Home Assistant als Fehler angezeigt.
- **Debug-Protokollierung**: Aktivieren Sie unter **Configure** die Option **Enable debug logging** und wählen Sie eine **Logging depth**: *Basic* (Zykluszusammenfassung, Identität, Schreibvorgänge), *Protocol* (+ jeder an den Wechselrichter gesendete und von ihm empfangene Frame mit Antwortzeit) oder *Protocol + parsing* (+ die ausgewerteten Werte jedes Befehls). Die Einträge erscheinen unter **Einstellungen → System → Protokolle**. Schalten Sie sie danach wieder aus: Die tiefen Stufen schreiben viel.
- **Uhrzeitabgleich (optional)**: Bei aktivierter Steuerung vergleicht **Configure → Sync inverter date and time** nach jedem Lesen von Datum/Uhrzeit die Uhr des Wechselrichters mit Home Assistant und korrigiert eine Abweichung von mehr als 30 s (höchstens einmal pro Stunde).
- **Aktionen für Automatisierungen**: rohe Befehle senden und Entitäten bei Bedarf aktualisieren, siehe [JSD SOLAR: Befehle und Aktualisierung in Automatisierungen](#jsd-solar-befehle-und-aktualisierung-in-automatisierungen).
- Kalibrierbefehle werden nicht unterstützt.

---

## JSD SOLAR: Befehle und Aktualisierung in Automatisierungen

Die Integration stellt für den Wechselrichter zwei Aktionen bereit. Beide erscheinen unter **Entwicklerwerkzeuge → Aktionen** und im Automatisierungseditor (**Aktion hinzufügen → JSDSolar J5500HPC/J5500HP**), sodass Sie sie ausprobieren können, bevor Sie sie in eine Automatisierung übernehmen.

### Bevor Sie beginnen

- Lesen (Abfragen) funktioniert ohne zusätzliche Optionen.
- Zum Senden eines Schreibbefehls ist **Configure → Enable inverter control** nötig.
- Um die Frames auf der Leitung zu sehen, aktivieren Sie **Enable debug logging** mit der Tiefe *Protocol* (siehe oben).
- Die Befehlssyntax steht in [docs/protocols/protocol.JSDSOLAR.en.md](../protocols/protocol.JSDSOLAR.en.md). Senden Sie den Befehl ohne abschließendes CR.

### Befehl senden: `jsdsolar_j5500hpc_j5500hp.send_command`

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `command` | ja | Befehlstext, z. B. `GBAT`, `CPR??`, `CPR03` |
| `attempts` | nein, Standard 1 | Bis zu so oft erneut senden (1–10), solange der Wechselrichter `NAK` oder nichts antwortet |
| `device_id` | nur bei mehreren Wechselrichtern | Das Wechselrichtergerät |

Probieren Sie es unter **Entwicklerwerkzeuge → Aktionen** aus: Wählen Sie *Send inverter command*, wechseln Sie in den YAML-Modus, fügen Sie

```yaml
action: jsdsolar_j5500hpc_j5500hp.send_command
data:
  command: GBAT
```

ein und klicken Sie auf **Aktion ausführen**. Die Antwort erscheint darunter:

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

| `status` | Bedeutung |
|---|---|
| `ok` | Der Wechselrichter hat Daten gesendet (Antwort auf eine Abfrage) |
| `ack` | Der Wechselrichter hat einen Schreibvorgang angenommen |
| `nak` | Der Wechselrichter hat den Befehl abgelehnt: außerhalb des Bereichs, in der aktuellen Betriebsart nicht erlaubt oder unbekannt |
| `no_answer` | Keine Antwort innerhalb von 3 s pro Versuch |

`parsed` gibt es nur für Abfragen, die die Integration kennt (der schnelle Satz, `I`/`SVFW`/`F`, das Zurücklesen von Einstellungen wie `CPR??`, `TE?`, `DATE??????`, `TIME??????`, `TCQN????`, `GFAIL`, `GCF`).

Was gesendet werden darf:

- **Abfragen** sind immer erlaubt: alles, was `?` enthält (`CPR??`, `GCC???`, `BTB????`, `TE?`), und die Abfragebefehle des Protokolls (`GMOD`, `GBAT`, `GPV`, `GOP`, `GLINE`, `BL`, `GWS`, `I`, `F`, `GPDAT1` …).
- **Alles andere ist ein Schreibvorgang** (`CPR03`, `OPR01`, `GCC030`, `TEO`, `TDO`, `SON` …) und erfordert die Wechselrichtersteuerung. Ein Schreibvorgang wird auf INFO-Ebene protokolliert.
- **Kalibrierbefehle** (§10: `BA0`, `B1A…`, `B2A…`, `PA0`, `PV<nnn.n>`, `BUN±`, `VR±` …) werden immer abgelehnt.

`send_command` aktualisiert die Entitäten nicht. Rufen Sie danach `refresh` auf (siehe unten).

Typische Befehle:

| Zweck | Abfrage | Schreiben |
|---|---|---|
| Ladepriorität (0 Netz zuerst, 1 PV zuerst, 2 Netz und PV, 3 nur PV) | `CPR??` | `CPR00` … `CPR03` |
| Ausgangspriorität (0 Netz zuerst, 1 PV zuerst, 2 PV-Batterie-Netz) | `OPR??` | `OPR00` … `OPR02` |
| Max. Ladestrom aus dem Netz, A | `GCC???` | `GCC030` (3 Stellen) |
| Batteriespannung für Rückkehr ins Netz | `BTG????` | `BTG47.5` (`nn.n`) |
| Funktionsflags | `TE?` (aktivierte Buchstaben) | `TE<Buchstabe>` ein, `TD<Buchstabe>` aus |
| Datum / Uhrzeit | `DATE??????`, `TIME??????` | `DATE251203`, `TIME051203` |

Für Einstellungen, die eine Entität haben, sind `select.select_option` und `number.set_value` einfacher: Sie prüfen den Bereich, wiederholen bis zu 5 Mal und lesen den Wert selbst zurück.

### Entitäten sofort aktualisieren: `jsdsolar_j5500hpc_j5500hp.refresh`

Die Messwerte fragt die Integration etwa alle 5 s ab, Einstellungen, Funktionsflags, Uhrzeit und Fehler-Momentaufnahme laufen jedoch über eine langsame Warteschlange (3 Befehle pro Zyklus), sodass eine Einstellung Minuten bis zur Aktualisierung brauchen kann. `refresh` liest sofort nur die Befehle neu, aus denen die gewählten Entitäten stammen (`battery_voltage` → `GBAT`, `setting_charger_priority` → `CPR??`, ein Funktionsschalter → `TE?`), aktualisiert diese Entitäten und gibt die neuen Werte zurück:

```yaml
action: jsdsolar_j5500hpc_j5500hp.refresh
target:
  entity_id:
    - select.j5500hpc_setting_charger_priority
    - sensor.j5500hpc_battery_voltage
```

Antwort:

```yaml
values:
  select.j5500hpc_setting_charger_priority: PV only
  sensor.j5500hpc_battery_voltage: 52.4
```

Entitäten aus demselben Befehl kosten eine einzige Anfrage. Eine Entität, die die Integration noch nicht gelesen hat (direkt nach einem Neustart), führt zu einem Fehler; warten Sie die ersten Abfragezyklen ab.

Die Standardaktion **`homeassistant.update_entity`** führt für eine Wechselrichterentität dasselbe gezielte Neulesen aus, jedoch ohne Antwort.

### Beispiele

Ladepriorität mit einem rohen Befehl umschalten, die Antwort prüfen und die Entität aktualisieren:

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
          message: "Wechselrichter hat CPR03 abgelehnt: {{ reply.status }} nach {{ reply.attempts }} Versuchen"
      - stop: "CPR03 nicht angenommen"
  - action: jsdsolar_j5500hpc_j5500hp.refresh
    target:
      entity_id: select.j5500hpc_setting_charger_priority
```

Einen frischen Wert direkt vor einer Entscheidung lesen:

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

Den Wert einer Abfrage verwenden, für die es keine Entität gibt:

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

### Fehler

Die Aktion schlägt fehl (und die Automatisierung stoppt, sofern der Schritt nicht `continue_on_error: true` hat), wenn der Befehl ein Schreibvorgang ist und die Wechselrichtersteuerung ausgeschaltet ist, wenn es ein Kalibrierbefehl ist, wenn das Ziel keine Entität eines JSD SOLAR Wechselrichters ist oder wenn eine zu aktualisierende Entität noch nicht gelesen wurde. Eine Antwort `nak` oder `no_answer` ist kein Fehler: Prüfen Sie `status`.

---

## Anschlussanleitung für den aktiven Balancer JK-DZ11-B2A24S (RS485):

<img src="../../img/JK-DZ11-B2A24S-RS485.avif" alt="Aktiver Balancer JK-DZ11-B2A24S mit RS485" width="360">

- **RS485-USB-Kabel oder RS485-zu-Ethernet/WiFi-Bridge**, angeschlossen am RS485-Port des Balancers (A an A, B an B). Die Beschriftung A/B unterscheidet sich je nach Hersteller: Wenn der Balancer nicht antwortet oder ein Debug-Protokoll nur eine kurze Antwort `55 95 01 FF 01` zeigt, vertauschen Sie A und B.
- **Gerätetyp**: `JK_BALANCER`. Das ist ein anderes Protokoll als `JK_PB`: Der Balancer antwortet nur auf Anfragen und sendet nie von selbst, daher bleibt ein `JK_PB`-Eintrag mit ihm nicht verfügbar.
- **Serielle Einstellungen**: **9600 Baud, 8N1** (der Schritt für die serielle Verbindung schlägt 9600 vor). Eine Bridge muss genauso eingestellt sein.
- **Adresse**: die RS485-Slave-Adresse des Balancers, standardmäßig 1; bei Bedarf unter **Configure** ändern.
- **Steuerung (optional)**: Aktivieren Sie unter **Configure** die Option **Enable balancer control**, um die Zellenanzahl (2–24), die Auslösedifferenz für das Balancing (2–1000 mV) und den maximalen Balancing-Strom (30–2000 mA beim 2-A-Modell) zu ändern sowie das Balancing ein- oder auszuschalten.
- **Über RS485 nicht verfügbar**: Widerstände der Zellanschlüsse (Balancerkabel) und die „Balancing-Startspannung“; diese liefert der Balancer nur über Bluetooth in der JK-App.
- Protokoll: [docs/protocols/JK-DZ11B2A224S_RS485_V1.3_en.md](../protocols/JK-DZ11B2A224S_RS485_V1.3_en.md).

---

## Anschlussanleitung für Pace BMS:
- **RS232-WIFI/Ethernet-Modul oder RS232-USB-Kabel erforderlich**
- **Anschlussport**: Verbinden Sie Home Assistant mit der **RS232**- oder **WIFI**-Schnittstelle des Pace BMS.
- **Master-BMS**: Die Verbindung muss mit dem **Master-BMS** hergestellt werden.
- **DIP-Schalter-Einstellungen**: Stellen Sie sicher, dass die DIP-Schalter (Wahlschalter) des Master-BMS auf **1000** eingestellt sind.
- **Stromauflösung**: Die meisten PACE-BMS melden den Strom in 0,01 A. Wenn Strom und Leistung 10-mal zu klein erscheinen, stellen Sie **Configure → PACE current resolution** auf 0,1 A.

## Anschlussanleitung für JK BMS:
- **RS485-WIFI/Ethernet-Modul oder RS485-USB-Kabel erforderlich**
- **Anschlussport**: Verbinden Sie Home Assistant mit der **RS485B**- oder **RS485C**-Schnittstelle des JK BMS.
- **Master-BMS**: Die Verbindung muss mit dem **Master-BMS** hergestellt werden.
- **DIP-Schalter-Einstellungen**: Stellen Sie sicher, dass die DIP-Schalter (Wahlschalter) des Master-BMS auf **0000** eingestellt sind.

---

## Installation:

### Option 1: Über HACS (empfohlen)
1. Stellen Sie sicher, dass [HACS (Home Assistant Community Store)](https://hacs.xyz/) installiert ist.
2. Gehen Sie in Home Assistant auf **HACS -> Integrationen**.
3. Klicken Sie auf die drei Punkte in der oberen rechten Ecke und wählen Sie **Benutzerdefinierte Repositories**.
4. Fügen Sie die URL dieses Repositories ein: `https://github.com/NewBotanik/J5500HPC-HA-Integration`
5. Wählen Sie **Integration** als Kategorie aus und klicken Sie auf **Hinzufügen**.
6. Suchen Sie nach der Integration **JSDSolar J5500HPC/J5500HP** in HACS und klicken Sie auf **Herunterladen**.
7. Starten Sie Home Assistant neu.

### Option 2: Manuelle Installation
1. Laden Sie die neueste Version herunter oder klonen Sie das Repository.
2. Kopieren Sie das Verzeichnis `custom_components/jsdsolar_j5500hpc_j5500hp` in das Verzeichnis `/config/custom_components/` Ihres Home Assistant.
3. Starten Sie Home Assistant neu.

---

## Konfiguration:
1. Gehen Sie in Home Assistant auf **Einstellungen -> Geräte & Dienste**.
2. Klicken Sie unten rechts auf **Integration hinzufügen**.
3. Suchen Sie nach **JSDSolar J5500HPC/J5500HP** und klicken Sie darauf.
4. Wählen Sie den Gerätetyp (JSD SOLAR Wechselrichter, JK-Balancer oder ein BMS) und die Verbindung (Netzwerk oder seriell). Der nächste Schritt fragt nur ab, was dieser Typ braucht: für Wechselrichter und Balancer nur Gerätename und Abfrageintervall; für ein BMS zusätzlich Porttyp, maximale Anzahl paralleler Packs und die JK-Pack-Nummerierung. Geben Sie anschließend IP/Port der Bridge oder den seriellen Port und die Baudrate ein.
5. Für weitere Geräte (zum Beispiel einen Wechselrichter und einen Balancer oder mehrere Batteriebänke mit unterschiedlichen IPs/Ports) klicken Sie für jedes erneut auf **Integration hinzufügen**.
