# CLAUDE.md (українською)

Цей файл містить вказівки для Claude Code (claude.ai/code) щодо роботи з кодом у цьому репозиторії.
Основна версія: [CLAUDE.md](CLAUDE.md). Обидва файли треба тримати синхронізованими.

## Огляд проєкту

Нативна custom integration для Home Assistant (HACS, домен `jsdsolar_j5500hpc_j5500hp`). Опитує пристрої через serial (RS232/RS485) або TCP (міст Ethernet/WiFi) і створює entities у HA напряму, без MQTT. Підтримувані пристрої:

- BMS батарей: **PACE** (RS232, RS485, WiFi-модуль), **JK (JKBMS)**, **TDT**
- Інвертор: **JSD SOLAR** (наприклад, J5500HPC), ASCII-протокол RS232 на 2400 бод; моніторинг і опційне керування

Форк `fancyui/Gobel-Battery-HA-Integration`. Сусідній репозиторій `../J5500HPC-HA-Addon` — стара MQTT-версія (Add-on) тих самих драйверів.

## Команди

- Лінтера і тестового оточення HA немає. Офлайн-тест драйвера (HA не потрібен): `python tests/test_jsdsolar.py`
- Перевірка синтаксису: `python -m py_compile custom_components/jsdsolar_j5500hpc_j5500hp/*.py`
- CI: `.github/workflows/hacs.yml` (валідація HACS) і `hassfest.yaml`.
- Версія записана в `custom_components/jsdsolar_j5500hpc_j5500hp/manifest.json` (`version`). Кожна зміна версії потребує запису в `CHANGELOG.md`.

## Архітектура

```text
__init__.py → coordinator.py (DataUpdateCoordinator, запускає драйвери в executor)
                → bms_comm.py           транспорт: serial (pySerial) або TCP-сокет
                → pacebms_rs232.py      PACE через RS232, запит/відповідь
                → pacebms_rs485.py      PACE через RS485, кілька паків
                → pacebms_wifi.py       PACE через WiFi-модуль (PACE_LV_WIFI)
                → jkbms_rs485.py        JK через RS485, пасивний слухач у фоновому потоці
                → tdtbms_rs232.py       TDT через RS232, запит/відповідь
                → jsdsolar_rs232.py     інвертор JSD SOLAR, ASCII запит/відповідь
            → sensor.py / binary_sensor.py   entities будуються з coordinator.data
            → number.py / select.py / switch.py / button.py   керування JSD SOLAR (опція)
            → jsdsolar_entity.py   спільна база entities JSD, картка пристрою, helper запису
config_flow.py   налаштування в UI: крок user (тип, підключення, порт) → крок network або serial
const.py         ключі конфігурації, BMS_TYPES, значення за замовчуванням
```

- **`coordinator.py`**: `_setup_bms_sync()` вибирає драйвер за `bms_type` + `battery_port`. `_fetch_data_sync()` повертає `{"analog": [...], "warning": [...]}`, по одному dict на пак із ключем `pack_id`. Дані паків кешуються на час до 3 невдалих опитувань. Драйвери BMS перенесені зі старого Add-on і досі очікують MQTT-публікатор; замість нього підставляється `DummyHAComm`.
- **Драйвери BMS** надають `get_analog_data(pack)` / `get_warning_data(pack)`. JK читає кеш кадрів, який наповнює його фоновий потік (`stop()` під час unload).
- **JSD SOLAR** має окремий шлях даних. `JSDSOLAR232.get_data()` повертає `(значення сенсорів, бінарні прапорці)`, а coordinator повертає `{"analog": [], "warning": [], "inverter": {...}, "inverter_flags": {...}}`. `sensor.py` / `binary_sensor.py` на самому початку відгалужуються для `BMS_TYPE_JSD_SOLAR` і створюють один device інвертора. Entity створюється, коли ключ з'являється вперше; метадані беруться з `jsdsolar_rs232.SENSORS`. Unique ID: `{entry_id}_inverter_{key}`.
- **`bms_comm.py`**: `receive_data()` читає до `\r` (serial `read_until`, TCP із буферизацією). При помилці читання з'єднання закривається; наступний `send_data()` підключається знову. Методи лише для JK: `receive_jkbms_passive()`, `receive_jkbms_raw()`, `flush_jkbms_buffer()`.

## Ключові домовленості

- **Правило ізоляції**: зміна одного драйвера (`pacebms_*.py`, `jkbms_rs485.py`, `tdtbms_rs232.py`, `jsdsolar_rs232.py`) не повинна впливати на інші. У спільних файлах (`coordinator.py`, `sensor.py`, `binary_sensor.py`, `config_flow.py`) код для конкретного пристрою додається окремою гілкою за `bms_type`. Див. також `.agents/rules/ha-addon.md`.
- **Не змінювати поведінку `bms_comm.py`** заради одного пристрою: ним користуються всі драйвери.
- **Запис у JSD SOLAR**: опитування (`get_data()`) надсилає лише запити; це перевіряє `tests/test_jsdsolar.py`. Команди налаштувань (§9) і керування (§7) надсилаються тільки з `set_setting` / `set_feature` / `run_action`, які викликають entities number/select/switch/button за дією користувача, і лише коли в опціях entry увімкнено `jsd_enable_control` (`allow_writes`). Кожен запис: перевірка діапазону → `<cmd><value>` → обов'язкова відповідь `ACK` → зворотне читання. Калібрування (§10) не надсилати ніколи. Кнопки `SOFF`, `Q`, `ED1` за замовчуванням вимкнені в реєстрі entities.
- **Опитування JSD SOLAR**: парсери — чисті функції; поля, яких немає, стають `None` і не відображаються. Обмеження каналу: 2400 бод, близько 5 с на цикл, 3 с на кожну команду без відповіді. Тому швидкий набір (§4.5) опитується щоциклу, а все інше (налаштування, `TE?`, `TCQN`, `DATE`/`TIME`, `GFAIL`, `GCF`, паралельні юніти) йде через повільну чергу, по 3 за цикл; команди зі збоями опитуються рідше; timeout coordinator для JSD — 60 с. Блокування в драйвері не дає запису й опитуванню перемішатися в лінії.
- **Налаштування JSD SOLAR** описані один раз у `jsdsolar_rs232.SETTINGS` (команда, ширина, тип, варіанти, діапазон); ключі, спільні з полями GCHG/GBAT (наприклад, `setting_cv_voltage`), містять одне значення з обох джерел. Коли керування увімкнене, налаштування стають entities number/select замість сенсорів, а функціональні прапорці — перемикачами замість бінарних сенсорів.
- **Pack ID**: використовувати pack id з ACK-даних, щоб розрізняти паки.
- **Іменування entities**: BMS `"{device_name} Pack NN {metric}"`, unique ID `{entry_id}_pack_{id}_{metric}`; загальні `{entry_id}_total_{key}`.
- **Формат комітів**: conventional commits: `feat:`, `fix:`, `chore:`, `docs:`.
- **Зміна версії**: `version` у `manifest.json` + запис у `CHANGELOG.md`.
- `translations/*.yaml` у корені репозиторію залишилися від Add-on; інтеграція їх не використовує.

## Документація протоколів

- `docs/protocols/JK-BMS-55AA-Protocol_EN.md` / `_ZH.md`: протокол кадрів 55AA для JK BMS
- `docs/protocols/pc-bms-RS232-Protocol_en.md`: протокол RS232 для PACE BMS
- `docs/protocols/protocol.JSDSOLAR.en.md` / `.uk.md`: протокол RS232 інвертора JSD SOLAR. Перш ніж довіряти прикладу, прочитайте §14 (помилки у документі виробника).
- J5500HPC не відповідає на команди Voltronic PI30/PI18/PI17/PI16 (`QPIGS`, `^P005GS`, …). Це підтвердила перевірка через UART в ESPHome, тому протокол JSD — єдиний варіант.
