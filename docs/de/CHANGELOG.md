---
description: 
---

# Änderungsprotokoll

[English](../../CHANGELOG.md) | [Українська](../uk/CHANGELOG.md)

## [3.4.4] - 2026-10-21
### Entfernt
-   `categories` in `manifest.json` wieder entfernt: Die auf GitHub verwendete hassfest-Prüfung akzeptiert den Schlüssel für benutzerdefinierte Integrationen noch nicht (Home Assistant hat ihn am 17.10.2026 im Entwicklungszweig erlaubt). Er wird wieder hinzugefügt, sobald eine veröffentlichte Home-Assistant-Version ihn unterstützt. Ohne ihn zeigt HACS nur eine Warnung.

---------------

## [3.4.3] - 2026-10-21
### Hinzugefügt
-   `manifest.json` nennt die Integrationskategorien `energy.backup_power` und `energy.solar_batteries`, sodass HACS und Home Assistant sie unter Energy anzeigen (die HACS-Warnung „The integration manifest has no categories“ entfällt).
### Geändert
-   `codeowners` in `manifest.json` ist jetzt `@NewBotanik` (bisher `@fancyui`, der Autor des Ursprungsprojekts).

---------------

## [3.4.2] - 2026-10-21
### Behoben
-   Hassfest-Prüfung: Die Gerätetypen im Einrichtungsformular verwenden Optionswerte in Kleinbuchstaben (`jsd_solar`, `jk_balancer`, `pace_lv` …), da Übersetzungsschlüssel in Home Assistant `[a-z0-9-_]` entsprechen müssen. Beim Absenden wird der Wert wieder in den Typ in Großbuchstaben umgewandelt, gespeicherte Einträge (`JSD_SOLAR`, …) bleiben also unverändert.
### Geändert
-   Die GitHub-Workflows verwenden `actions/checkout@v5` (Node.js 24) statt des veralteten, auf Node.js 20 basierenden `@v4`.

---------------

## [3.4.1] - 2026-10-16
### Behoben
-   [JSD SOLAR] Die Aktion `refresh` schlug in aktuellen Home-Assistant-Versionen mit „Unknown error“ fehl: `async_extract_entity_ids()` nimmt `hass` nicht mehr entgegen (es liest es aus dem Dienstaufruf). Beide Signaturen werden jetzt unterstützt, sodass die Aktion ab 2023.7 funktioniert.
-   [JSD SOLAR] Unerwartete Fehler in den Aktionen `send_command` und `refresh` werden mit ihrem Text statt „Unknown error“ angezeigt, und der Traceback landet im Home-Assistant-Log.

---------------

## [3.4.0] - 2026-10-16
### Hinzugefügt
-   [JSD SOLAR] Aktion `send_command`: sendet einen einzelnen Rohbefehl und gibt die Antwort zurück (Status `ok`/`ack`/`nak`/`no_answer`, Versuche, Antwortzeit, geparste Werte bei einer bekannten Abfrage). Abfragen funktionieren immer; andere Befehle sind Schreibvorgänge und erfordern die Wechselrichtersteuerung; Kalibrierbefehle werden abgelehnt; optionales erneutes Senden bei NAK oder ausbleibender Antwort (`attempts`, 1–10).
-   [JSD SOLAR] Aktion `refresh`: liest sofort nur die Befehle hinter den gewählten Entitäten neu, überträgt die Werte an sie und gibt `{entity_id: value}` zurück. `homeassistant.update_entity` auf einer Wechselrichter-Entität führt dasselbe gezielte Neueinlesen statt einer vollständigen Abfrage aus.
-   Die minimale Home-Assistant-Version ist jetzt 2023.7 (Aktionen mit Antwort).
-   [PACE BMS] Option "PACE current resolution" unter **Configure**: 0,01 A (Standard, unverändert) oder 0,1 A, für BMS, deren Strom und Leistung zehnmal zu klein angezeigt wurden. Portiert aus Gobel-Battery-HA-Addon 1.9.87 (`pace_current_scale`).
-   [JSD SOLAR] Option "Sync inverter date and time with Home Assistant when they differ" (erfordert die Wechselrichtersteuerung). Nach jedem Rücklesen von DATE/TIME wird die Uhr des Wechselrichters mit der lokalen HA-Zeit verglichen; eine Abweichung von mehr als 30 s oder ein falsches Datum wird mit DATE/TIME-Schreibvorgängen korrigiert, höchstens einmal pro Stunde. Standardmäßig aus: Die Abfrage sendet keine Schreibvorgänge, solange diese Option nicht aktiviert ist.
### Geändert
-   Einrichtungsformular in zwei Schritten: zuerst Gerätetyp und Verbindung, dann nur die Felder, die dieser Typ benötigt. Der JSD-SOLAR-Wechselrichter und der JK-Balancer fragen nicht mehr nach BMS-Porttyp, maximaler Anzahl paralleler Packs oder JK-Pack-Nummerierung. Standard-Gerätename und Abfrageintervall richten sich nach dem Typ (Wechselrichter: „J5500HPC“, 10 s; Balancer: „JK Balancer“, 5 s). Die Liste der Gerätetypen beginnt mit dem JSD-SOLAR-Wechselrichter, beschriftet mit „(J5500HPC/J5500HP, possibly others)“; der Balancer ist mit „(JK-B2A24S-RS485, possibly others)“ beschriftet. Bestehende Einträge sind nicht betroffen.
-   [JSD SOLAR] Einstellungen der Batteriespannung (CV, Erhaltungsladung, EQ, Abschaltung des zweiten Ausgangs, Abschaltung, Warnung, Rückkehr zum Netz, Rückkehr zur Batterie, Überspannung) sind Schieberegler in 0,1-V-Schritten über den Bereich des erkannten 12/24/48-V-Systems.
### Behoben
-   [JSD SOLAR] Eine Einstellung, die außerhalb ihres angegebenen Bereichs zurückgelesen wird (z. B. BTB 54,4 V bei einem 48-V-System, Bereich bis 54,0 V), wird unverändert angezeigt: Der Zahlenbereich wird so erweitert, dass er den Wert einschließt.
-   [JSD SOLAR] Schreibvorgänge werden bis zu 5-mal im Abstand von 1 s wiederholt, wenn der Wechselrichter mit NAK oder gar nicht antwortet: Er beantwortet eine gültige Änderung der Ladepriorität, der Ausgangspriorität oder des maximalen Netzladestroms beim ersten Versuch manchmal mit NAK, was Automatisierungen unterbrach. Für jeden fehlgeschlagenen Versuch wird eine Warnung protokolliert. Schlagen alle Versuche fehl, liest die Einstellung aber bereits den gewünschten Wert, gilt der Schreibvorgang als erledigt.
-   [JSD SOLAR] Batteriestrom beim Laden und im Ruhezustand. GBAT-Feld 2 („discharge current“ im Herstellerdokument) ist der Batteriestrom in beide Richtungen, daher zeigte "Battery Discharge Current" beim Laden den Ladestrom (38 A). Im Ruhezustand zeigten sowohl dieser Sensor als auch "Charge Current" 0,1–0,3 A, während das BMS 0,00 A meldete: ein Nullpunktversatz des Stromsensors im Wechselrichter, kein echter Leckstrom. Jetzt ergibt sich die Richtung aus dem Vorzeichen des BMS-Stroms (oder, ohne BMS-Verbindung, aus Ladephase und Betriebsmodus): "Battery Discharge Current" ist 0, außer wenn die Batterie entladen wird, "Charge Current" ist 0, solange das Ladegerät steht, und der neue Sensor "Battery Current" ist vorzeichenbehaftet (+ Laden, − Entladen). Die unkorrigierten Messwerte bleiben als Diagnosesensoren "Battery Current Raw" und "Charge Current Raw" erhalten. Siehe Protokoll §14 #21.
-   [PACE BMS RS485] Packs, die die Anfrage nach der Pack-Nummer (CID2 90) mit einem kurzen ACK (`LENID 000`, ohne DATAINFO) beantworten, werden wieder gefunden; zuvor wurde nur Pack 0 abgefragt, und jeder Zyklus protokollierte „Invalid LENID value“. Portiert aus Gobel-Battery-HA-Addon 1.9.87.
-   [JK BMS] Pack-Leistung und Gesamtleistung haben das Vorzeichen des Stroms (negativ beim Entladen); der Frame überträgt die Leistung ohne Vorzeichen, daher war sie immer positiv. Portiert aus Gobel-Battery-HA-Addon `dev` (1.9.88).
-   [JSD SOLAR] Dezimale Einstellungswerte werden vor der Bereichsprüfung auf 0,1 gerundet, sodass ein Wert an der Bereichsgrenze mit Gleitkomma-Rauschen nicht abgelehnt wird.

---------------

## [3.3.3] - 2026-10-09
### Behoben
-   [JK-Balancer] Die Temperatur wird in 0,1 °C übertragen (das Gerät meldet 190, während die JK-App 18,9 °C anzeigt); sie wurde als 189 °C angezeigt.
-   [JK-Balancer] Der Binärsensor "Alarm Cell Count Error" wurde entfernt: Alarmbit 0 ist bei einem intakten Balancer gesetzt, dessen App keinen Alarm meldet, seine Bedeutung weicht also vom Herstellerdokument ab. Das rohe Alarmbyte ist als Diagnosesensor "Alarm Code" verfügbar.

---------------

## [3.3.2] - 2026-10-09
### Geändert
-   Der Gerätetyp im Einrichtungsformular ist eine beschriftete Liste (z. B. „JK BMS (55AA stream, 115200 baud)“ vs. „JK-DZ11-B2A24S active balancer (RS485, 9600 baud)“), sodass JK BMS und JK-Balancer nicht mehr versehentlich verwechselt werden.

---------------

## [3.3.1] - 2026-10-09
### Behoben
-   [JK-Balancer] Höchste/niedrigste Zelle werden vom Gerät 0-basiert übertragen (ein echter 16-Zellen-Frame liefert 0 und 15); sie werden jetzt 1-basiert angezeigt.
-   [JK-Balancer] Der maximale Balancing-Strom akzeptiert bis zu 2000 mA: Das 2-A-Modell (JK-DZ11-B2A24S) meldet 2000 mA, mehr als der Bereich von 30–1000 mA im Herstellerdokument.
### Hinzugefügt
-   Node-RED-Testflows in `docs/node-red/` (Auslesen von V1.3 mit Dekodierung sowie eine Sonde für V1.3-/JK02-Anfragen) und ein Test mit einem echten Balancer-Frame.

---------------

## [3.3.0] - 2026-10-08
### Hinzugefügt
-   [JK-Balancer] Neuer Gerätetyp `JK_BALANCER` für den eigenständigen Aktiv-Balancer JK-DZ11-B2A24S über RS485 (Herstellerprotokoll V1.3: 9600 Baud, Anfrage `55 AA` / 74-Byte-Antwort `EB 90`, additive Prüfsumme). Liest Gesamt- und Einzelzellspannungen, Durchschnitt/Maximum/Minimum/Differenz, höchste/niedrigste Zelle, Balancing-Zustand und -Strom, Auslösedifferenz, maximalen Balancing-Strom, Balancing-Schalter, konfigurierte und erkannte Zellenanzahl, Temperatur und die drei Alarmbits.
-   [JK-Balancer] Optionale Steuerung (Configure → **Enable balancer control**): Zellenanzahl (2–24), Balancing-Auslösedifferenz (2–1000 mV), maximaler Balancing-Strom (30–1000 mA) und Balancing ein/aus. Der Balancer sendet den aktiven Wert zurück; ein Schreibvorgang, den er nicht übernimmt, löst einen Fehler aus. Die RS485-Slave-Adresse wird unter Configure festgelegt (Standard 1).
-   `bms_comm.read_bytes()` für binäre Antworten fester Länge; die bestehenden Transportmethoden bleiben unverändert.
-   Offline-Test `python tests/test_jkbalancer.py` mit den Beispiel-Frames des Herstellers.

---------------

## [3.2.1] - 2026-10-07
### Geändert
-   Neue Integrationssymbole in den Home-Assistant-Brand-Größen (`icon.png` 256×256, `icon@2x.png` 512×512), neu erzeugt aus dem `J5500HPC.png` in voller Auflösung mit schärferer Verkleinerung, damit der Schriftzug „jsdsolar“ lesbar bleibt.
-   Neues `logo.png` (347×512) und `logo@2x.png` (695×1024), in `brand/` und im Stammverzeichnis des Repositorys.

---------------

## [3.2.0] - 2026-10-07
### Hinzugefügt
-   Verbindungsparameter im Optionsformular (**Configure**): serieller Port und Baudrate für eine serielle Verbindung, IP-Adresse der Bridge und TCP-Port für eine Netzwerkverbindung. Sie lassen sich ändern, ohne das Gerät neu hinzuzufügen.

---------------

## [3.1.0] - 2026-10-07
### Hinzugefügt
-   Optionsformular (**Configure**) für jeden Gerätetyp: **poll interval** (änderbar, ohne das Gerät neu hinzuzufügen), **Enable debug logging** und **Logging depth**. Die Wechselrichtersteuerung bleibt für JSD SOLAR im selben Formular.
-   [JSD SOLAR] Stufen der Protokollierungstiefe: *Basic* (Zykluszusammenfassung, Identität, Schreibvorgänge), *Protocol* (+ jeder gesendete und empfangene Frame mit Antwortzeit), *Protocol + parsing* (+ geparste Werte jedes Befehls). Der Logger der Integration wird auf die tiefste Stufe gesetzt, die irgendein Eintrag anfordert, und zurückgesetzt, wenn das Debugging ausgeschaltet wird.

---------------

## [3.0.1] - 2026-10-06
### Hinzugefügt
-   Übersetzungen (Englisch, Ukrainisch) für die Einrichtungs- und Optionsformulare. Das Formular **Configure** erklärt jetzt die Option **Enable inverter control**, die die schreibgeschützten Wechselrichtereinstellungen in bearbeitbare Entitäten umwandelt.
### Behoben
-   [JSD SOLAR] `GFAIL` mit Fehlercode 0 stellt die bedeutungslosen Snapshot-Felder nicht mehr bereit (z. B. „Last Fault Mode: Unknown (35)“).

---------------

## [3.0.0] - 2026-10-02
### Geändert
-   **Inkompatible Änderung:** Die Integration heißt jetzt **JSDSolar J5500HPC/J5500HP**, Domain `jsdsolar_j5500hpc_j5500hp` (bisher `gobel_battery`, „Gobel Battery Monitor“). Home Assistant behandelt sie als neue Integration: Entfernen Sie die alten Einträge und `custom_components/gobel_battery`, installieren Sie den neuen Ordner und fügen Sie die Geräte anschließend erneut hinzu. Entitäts-IDs und Verlauf der alten Einträge werden nicht übernommen.

---------------

## [2.2.0] - 2026-10-01
### Hinzugefügt
-   [JSD SOLAR] Alle Abfragebefehle: Rücklesen jeder §9-Einstellung (37), Funktionsflags `TE?`, Zeit seit dem Ausgleichsladen `TCQN`, Uhr des Wechselrichters `DATE`/`TIME`, Snapshot des letzten Fehlers `GFAIL` (Rohfelder, standardmäßig deaktiviert), detaillierte Fehlerbits `GCF` sowie im Parallelbetrieb die Daten pro Einheit `GPDAT`, Statusbits `GPSTS`, ID `GPID` und PV `GPPV`. Sie werden in einer langsamen Warteschlange zu je 3 pro Abfragezyklus gelesen; Abfragen, die die Firmware nie beantwortet, werden nur alle 10 Runden wiederholt.
-   [JSD SOLAR] Wechselrichtersteuerung, standardmäßig aus und in den Integrationsoptionen aktivierbar (**Configure → Enable inverter control**): `number`- und `select`-Entitäten für alle §9-Einstellungen, `switch`-Entitäten für die TE/TD-Funktionsflags und Schaltflächen für `SON`, `SOFF`, `Q`, `ED1`, `SPON<n>`/`SPOFF<n>` und die Uhrensynchronisierung (`DATE`/`TIME` aus Home Assistant). Jeder Schreibvorgang muss mit `ACK` beantwortet werden und wird zurückgelesen; die Werte werden vorher auf ihren Bereich geprüft (die Grenzen der Batteriespannung richten sich nach dem erkannten 12/24/48-V-System). Die Schaltflächen `SOFF`, `Q` und `ED1` sind in der Entitätsregistrierung standardmäßig deaktiviert.
-   Kalibrierbefehle (§10) werden absichtlich nicht unterstützt.

---------------

## [2.1.0] - 2026-10-01
### Hinzugefügt
-   [JSD SOLAR] Überwachung von JSD-SOLAR-Wechselrichtern (z. B. J5500HPC) über RS232, direkt oder über eine Seriell-zu-TCP-Bridge (`bms_type: JSD_SOLAR`, 2400 Baud). Der Wechselrichter erscheint als ein Gerät mit Sensoren für Betriebsmodus, Fehler, Netz, Ausgang, Wechselrichterstufe, DC-Bus, Batterie, Ladegerät, PV, Temperaturen, Lüfter, vom Wechselrichter empfangene BMS-Daten, Energiezähler, Identität und zurückgelesene Einstellungen sowie Binärsensoren für jedes Warnbit. Nur Lesezugriff: Es werden keine Einstellungs-, Steuer- oder Kalibrierbefehle gesendet.
-   [JSD SOLAR] Einstellungen werden zu je einer pro Abfragezyklus gelesen, der letzte gültige Frame eines Befehls wird für 3 fehlgeschlagene Zyklen beibehalten, und Befehle, die die Firmware nicht beantwortet, werden nur alle 30 Zyklen wiederholt, sodass ein vollständiger Zyklus in die langsame 2400-Baud-Verbindung passt.
-   Offline-Treibertest: `python tests/test_jsdsolar.py`.

---------------

## [2.0.12] - 2026-07-25
### Behoben
-   [JKBMS] Das Parsen der Spannungsregister im Setup-Frame für `VolInverterMaxCharge` (maximale Ladespannung des Wechselrichters) an Offset 38 und `VolFloatCharge` (Erhaltungsladespannung) an Offset 42 wurde korrigiert (zuvor fälschlich als Unter-/Überspannungsschutz der Batterie erkannt).

---------------

## [2.0.11] - 2026-07-13
### Behoben
-   [Pace BMS] Falsch-positive strukturelle Treffer bei der dynamischen Berechnung der U/W-Bytes (z. B. wenn die Batterie voll geladen ist und der Strom 0 A beträgt) wurden behoben, indem auf von null verschiedene Zellen- und Temperaturanzahlen geprüft und eine hybride Divisionsberechnung mit Fallback verwendet wird.

---------------

## [2.0.10] - 2026-06-24
### Behoben
-   [BMS] Abgeschnittene Socket-Puffer und eine Desynchronisierung des Telemetrieprotokolls über Ethernet-/WiFi-Verbindungen wurden behoben, indem TCP-Stream-Pufferung und das Lesen bis zum Wagenrücklauf als Trennzeichen implementiert wurden.

---------------

## [2.0.9] - 2026-06-22
### Behoben
-   [Integration] Ein Problem wurde behoben, bei dem sich die Integration nach einer Unterbrechung der seriellen oder Netzwerkverbindung nicht automatisch neu verband.
-   [JKBMS] Ein Watchdog-Timer wurde hinzugefügt, der die Verbindung zurücksetzt, wenn 15 Sekunden lang keine gültigen Telemetrie-Frames empfangen werden.
-   [PACE/TDT] Der zugrunde liegende Kommunikations-Handler wurde verbessert, sodass er tote Verbindungen bei Lesefehlern sofort verwirft und sich im nächsten Abfragezyklus neu verbindet.

---------------

## [2.0.8] - 2026-06-22
### Behoben
- `AttributeError: 'BMSCommunication' object has no attribute 'close'` beim Entladen der Integration wurde behoben.



## 2.0.7

-   [Integration] Robuster Mechanismus für Leseversuche und Daten-Caching für Batteriepacks implementiert, um sporadische Timeouts oder CRC-Fehler der RS485-/seriellen Kommunikation auszugleichen.
-   [Integration] Behoben, dass Entitäten in den Zustand `unknown` fielen: Sie wechseln jetzt korrekt in den Standardzustand `unavailable`, wenn die Kommunikation mit einem Batteriepack vollständig abbricht oder das Wiederholungslimit überschreitet.

---------------


## 2.0.6

-   [PACE/TDT] Fehlerhaftes Parsen des aktiven Balancing-Status behoben, das wegen verschobener Byte-Offsets in den RS232- und RS485-Protokollen falsche Werte meldete.

---------------


## 2.0.1

-   [JKBMS] Erkennung mehrerer Packs und Registrierung der Entitäten korrigiert.
-   [JKBMS] Dynamische Registrierung der Entitäten und eindeutige Zuordnung der physischen `pack_id` implementiert, um vertauschte Packs zu verhindern und neu online gekommene Packs im laufenden Betrieb zu registrieren.
-   [JKBMS] Wartefenster für das passive Mithören beim Start optimiert, damit sich alle parallelen Packs melden, bevor die erste Abfrage abgeschlossen wird.

---------------


## 2.0.0

-   Home-Assistant-Add-on zu einer nativen benutzerdefinierten Integration migriert.

---------------


## 1.9.79

-   [JKBMS] Unterstützung für die Veröffentlichung der durchschnittlichen Zellspannung (`cell_voltage_avg`), des Index der Zelle mit maximaler Spannung (`cell_voltage_max_index`) und des Index der Zelle mit minimaler Spannung (`cell_voltage_min_index`) an Home Assistant über MQTT hinzugefügt.
-   [JKBMS] Rohe, 0-basierte Zellindex-Telemetriewerte aus dem JK-Protokoll werden in 1-basierte Indexsensoren umgerechnet, passend zur üblichen Zellbenennung.

---------------


## 1.9.78

-   [JKBMS] AttributeError „'Serial' object has no attribute 'gettimeout'“ beim Anschluss des BMS über einen seriellen Port im passiven Mithörmodus behoben.

---------------


## 1.9.77

-   [PACE232] Robuste strukturelle Validierung für die Klassifizierung der Pakettypen implementiert. Analog- und Warnpakete werden unterschieden, indem ihre Schemastruktur für die gemeldete Anzahl paralleler Packs validiert wird; dabei wird automatisch an unterschiedliche Datenlängen der Firmware angepasst (Größe der benutzerdefinierten Felder U und Warnstatus-Bytes W). Dies behebt Protokoll-Desynchronisierung sowie verfälschte Telemetrie von Zellspannung, Temperatur und SOC in Konfigurationen mit mehreren Packs.
-   [PACE/TDT] Abstürze durch IndexError beim Parsen bei Firmware-Versionen ohne Unterstützung für aktives Balancing behoben, indem sichere Grenzprüfungen implementiert wurden.
-   [PACE/TDT] Byte-Offsets des aktiven Balancing-Status in den Protokollen PACE RS232, RS485 und TDT RS232 korrigiert.
-   [Dashboard] Sensoren für den aktiven und passiven Balancing-Status zum Raster der PACE/TDT-BMS-Pack-Details im HA-Dashboard hinzugefügt. Abweichende Groß-/Kleinschreibung der Entitäten korrigiert (von großgeschriebenem SOC/SOH zu kleingeschriebenem soc/soh), passend zu den automatisch registrierten, kleingeschriebenen MQTT-Entitäts-IDs von Home Assistant.

---------------


## 1.9.74

-   [PACE/TDT] Passiver und aktiver Balancing-Status in getrennte Sensoren aufgeteilt:
    *   **Passiver Balancing-Status**:
        *   Schlüssel: `balancing_status_passive_1`, `balancing_status_passive_2`
        *   Name in der HA-Discovery: `Pack 0x Balancing Status Passive 1 / 2`
        *   Wert: Rohe Bitmasken-Bytewerte der aktiven Bypass-Widerstände (mehrere Bits können 1 sein).
    *   **Aktiver Balancing-Status**:
        *   Schlüssel: `balancing_status_active_1`, `balancing_status_active_2`
        *   Name in der HA-Discovery: `Pack 0x Balancing Status Active 1 / 2`
        *   Wert: Dekodierter Zellindex (1-8, 9-16). Gibt 0 zurück, wenn das aktive Balancing inaktiv ist.
-   [TDT] Absturz durch ValueError behoben, wenn die Werte des Balance-Zustands größer als 1 sind.

---------------


## 1.9.73

-   [PACE/TDT] Protokollierung der Pakete als Roh-ASCII und hexadezimal für alle Sende- und Empfangsvorgänge der Telemetrie hinzugefügt, wenn die Konfiguration `debug` aktiviert ist.
-   [PACE/TDT] Methodensignaturen für die Methoden zu Kapazität und Produktinformationen korrigiert.

---------------


## 1.9.72

-   [PACE/TDT] Sensoren für den aktiven Balancing-Status (`balance_state_1` und `balance_state_2`) für die BMS-Protokolle PACE (RS232, RS485, WiFi) und TDT bereitgestellt.
-   [BMS] Format der Debug-Protokollierung für geparste Analog- und Warntelemetrie in den BMS-Treibern für JK, PACE und TDT vereinheitlicht.

---------------


## 1.9.71

-   [PACE485] Einheit der Zelltemperatursensoren korrigiert (von '℃' zum Standard '°C'), damit Home Assistant die Sensoren akzeptiert.

---------------


## 1.9.70

-   [PACE232] Die Parsing-Längen der benutzerdefinierten Felder und der Warnstatus-Bytes werden dynamisch bestimmt, um unterschiedliche Firmware-Versionen der Batteriepacks zu unterstützen.
-   [PACE232] Eine ratiometrische Methode zur Paketklassifizierung implementiert, um Antwortpakete für Analog- und Warndaten zu unterscheiden. Verspätete oder in falscher Reihenfolge eintreffende Pakete werden gerettet, geparst und zwischengespeichert, um verfälschte Sensorzustände in Home Assistant zu verhindern.

---------------


## 1.9.66

-   [Addon] Mehrsprachige Übersetzungen (Englisch, Deutsch und Chinesisch) für die Konfigurationsoptionen hinzugefügt, damit auf der Einstellungsseite des Home-Assistant-Add-ons benutzerfreundliche Namen und Beschreibungen angezeigt werden.

---------------


## 1.9.61

-   [JKBMS] Konfigurationseinstellung `jk_display_index_start` mit den Auswahlmöglichkeiten "00" oder "01" (Standard) hinzugefügt, damit die Bezeichnungen von Home-Assistant-Entitäten und Packs der physisch per DIP-Schalter eingestellten Adresse des Batteriepacks entsprechen können.

---------------


## 1.9.60

-   [JKBMS] Den seriellen Leser des JK BMS in einen asynchronen Hintergrund-Listener-Thread umgebaut, um ein Blockieren des seriellen Ports in der Hauptschleife vollständig zu verhindern. Frames, die nicht 55AA sind (etwa Modbus-Master-Abfragen), werden automatisch gefiltert und verworfen. Die Hauptlogik für die Veröffentlichung holt die Telemetrie mit 0,0 s Latenz aus threadsicheren Caches, was schwankende HA-Entitäten und Pack-Anzahlen behebt.

---------------


## 1.9.59

-   [JKBMS] Die Ablaufzeit des Caches für dynamische Telemetrie passt sich jetzt an das Aktualisierungsintervall an (`max(30s, refresh_interval * 3)`), um größere Aktualisierungsintervalle (z. B. 20 s) ohne falsche Offline-Meldungen zu unterstützen.

---------------


## 1.9.58

-   [JKBMS] Schleife für passives Lesen optimiert: Das Lese-Timeout wurde auf 8,0 s erhöht (deckt die beobachtete Zykluszeit von 7,0 s für 16 Packs vollständig ab), und ein 5-Sekunden-Frische-Cache wurde hinzugefügt, damit doppeltes Lesen den seriellen Port nicht blockiert.

---------------


## 1.9.57

-   [JKBMS] Zeitfenster für passives Lesen weiter von 2,0 s auf 4,0 s erhöht, damit ein vollständiger sequenzieller Abfragezyklus von 3,2 Sekunden für 16 Packs sicher erfasst wird.

---------------


## 1.9.56

-   [JKBMS] Zeitfenster für passives Lesen von 1,0 s auf 2,0 s erhöht, um Telemetrie-Frames von bis zu 16 parallelen Batteriepacks zuverlässig zu erfassen.

---------------


## 1.9.55

-   [JKBMS] Dynamische Telemetrie-Frames werden bis zu 30 Sekunden zwischengespeichert, damit Pack-Anzahl (total_packs_num) und Batterie-Entitäten nicht durch vorübergehende Paketverluste oder Lese-Timeouts am seriellen Port schwanken.

---------------


## 1.9.54

-   [JKBMS] Modbus-Slave-ID wird direkt als Pack-ID zugeordnet, um 0-basierte Kommunikationsadressen (Adressen 0, 1, 2, 3 …) zu unterstützen und Konflikte bei der Pack-Zuordnung in Home Assistant zu beheben.

---------------


## 1.9.53

-   [JKBMS] 1-basierte Modbus-Slave-ID im nachfolgenden ACK wird auf eine 0-basierte Pack-ID abgebildet, um das fehlende Pack 01 zu beheben und doppelte bzw. falsch zugeordnete Pack-Geräte in HA zu verhindern.

---------------


## 1.9.52

-   [PACEWIFI] Unterstützung für den bms_type PACE_LV_WIFI hinzugefügt, um aktiv über WiFi gesendete Telemetriedaten passiv zu parsen.

---------------


## 1.9.50

-   [JKBMS] Das Modbus-ACK am Ende der Frames wird dynamisch geparst, sodass das Parsen der Daten unabhängig von bestimmten Paketlängen ist.

---------------


## 1.9.48

-   [JKBMS] Logik zur Pack-Identifizierung korrigiert, um Datenkollisionen zwischen verschiedenen Packs zu verhindern.
-   [JKBMS] Die Sensordaten jedes Packs werden an ein eigenes, separates Home-Assistant-Gerät gesendet.

---------------


## 1.9.46

-   [JKBMS] Ausführliche Logmeldungen zum Frame-Parsing von WARNING auf DEBUG geändert, um das Log zu entlasten.

---------------


## 1.9.45

-   [JKBMS] Integration mehrerer Packs und Konfigurationsparameter des Setups verfeinert (Reg=0x161E).
-   [PACE232] Status der Heizfolie (status_heating) zu instruction_state hinzugefügt.

---------------

## 1.9.21

-   build.yaml hinzugefügt, um einen fehlgeschlagenen Docker-Build zu beheben (fehlendes Argument BUILD_FROM).


---------------

## 1.9.20

-   Unterstützung für JK BMS über RS485 hinzugefügt.
-   Fehler bei Energy Discharged/Charged behoben.


---------------

## 1.9.0

-   Automatische Wiederverbindung nach Verbindungsverlust.
-   Index der Zelle mit maximaler/minimaler Spannung hinzugefügt.
-   Anleitung für Protoss PW10 / Waveshare geändert: 'Flow Control Settings' in 'Flow Control' und 'Software Flow Control' in 'OFF' geändert.


---------------

## 1.8.2

-   Fehler bei der Temperatureinheit behoben.
-   Fehler bei der Einheit der maximalen/minimalen Spannung behoben.
-   Wert der Spannungsdifferenz hinzugefügt.
-   Timeout für das Lesen der Daten auf 3 Sekunden geändert.

---------------


## 1.8.0

-   Die Wertgenauigkeit von geladener/entladener Energie wurde auf 5 geändert.

---------------


## 1.7.8

-   Fehlerbehebung für TDT BMS.

---------------


## 1.7

-   Fehler bei mehreren Packs über RS232 behoben.
    Für Pace BMS wird standardmäßig PACE_LV (Protokoll der neuesten Version) verwendet; falls das nicht funktioniert, versuchen Sie PACE_LV_V1.
-   Maximale/minimale Zellspannung für das Gesamtsystem und jedes Pack hinzugefügt.
-   Unterstützung für TDT BMS hinzugefügt.

---------------
