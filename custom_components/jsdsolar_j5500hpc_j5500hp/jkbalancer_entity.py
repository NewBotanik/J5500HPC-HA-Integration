"""Entities of the JK-DZ11-B2A24S active balancer (RS485)."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.components.number import NumberEntity, NumberMode, NumberDeviceClass
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, BMS_TYPE_JK_BALANCER
from .jkbalancer_rs485 import SETTINGS, SWITCHES, sensor_meta
from .jsdsolar_entity import add_entities_for_new_keys

DATA = "balancer"
FLAGS = "balancer_flags"
# Configuration values, shown under Diagnostic when read-only
DIAGNOSTIC_KEYS = {"cell_count", "cell_count_detected", "balance_trigger_voltage", "max_balance_current"}


def is_balancer(coordinator):
    return coordinator.bms_type == BMS_TYPE_JK_BALANCER


def balancer_control_enabled(coordinator):
    return is_balancer(coordinator) and coordinator.jk_balancer_control


def entity_name(key):
    """'cell_voltage_max_number' -> 'Cell Voltage Max Number'."""
    return key.replace("_", " ").title()


class JKBalancerEntity(CoordinatorEntity):
    """Base: one key of coordinator.data[section], all on one balancer device."""

    section = DATA

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = f"{coordinator.device_name} {entity_name(key)}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_balancer_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.entry.entry_id}_balancer")},
            "name": coordinator.device_name,
            "manufacturer": "Jikong (JK)",
            "model": "JK-DZ11-B2A24S",
        }

    @property
    def _value(self):
        return (self.coordinator.data or {}).get(self.section, {}).get(self.key)

    @property
    def available(self) -> bool:
        return super().available and self.key in (self.coordinator.data or {}).get(self.section, {})

    async def _async_write(self, func, *args):
        """Run a driver write in the executor, then show the value the balancer confirmed."""
        try:
            await self.hass.async_add_executor_job(func, *args)
        except (ValueError, TimeoutError, PermissionError) as err:
            raise HomeAssistantError(str(err)) from err
        last = self.coordinator.bms._last
        if self.coordinator.data is not None and last:
            self.coordinator.data[DATA] = dict(last[0])
            self.coordinator.data[FLAGS] = dict(last[1])
            self.coordinator.async_update_listeners()


class JKBalancerSensor(JKBalancerEntity, SensorEntity):
    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        unit, icon, device_class, state_class, precision = sensor_meta(key)
        self._attr_native_unit_of_measurement = unit or None
        self._attr_device_class = SensorDeviceClass(device_class) if device_class else None
        self._attr_state_class = SensorStateClass(state_class) if state_class else None
        self._attr_suggested_display_precision = precision
        self._attr_icon = icon
        if key in DIAGNOSTIC_KEYS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        return self._value


class JKBalancerBinarySensor(JKBalancerEntity, BinarySensorEntity):
    section = FLAGS

    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        if key.startswith("alarm_"):
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        elif key in ("balancing_charging", "balancing_discharging"):
            self._attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self):
        return self._value


class JKBalancerNumber(JKBalancerEntity, NumberEntity):
    """Cell count, trigger delta or max balance current; the shown value is the one the balancer confirmed."""

    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_step = 1

    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        _command, minimum, maximum, unit, icon = SETTINGS[key]
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        if unit == "mV":
            self._attr_device_class = NumberDeviceClass.VOLTAGE
        elif unit == "mA":
            self._attr_device_class = NumberDeviceClass.CURRENT

    @property
    def native_value(self):
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        await self._async_write(self.coordinator.bms.set_setting, self.key, value)


class JKBalancerSwitch(JKBalancerEntity, SwitchEntity):
    """Balancing on/off (command 0xF6)."""

    section = FLAGS
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:scale-balance"

    @property
    def is_on(self):
        return self._value

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_write(self.coordinator.bms.set_switch, self.key, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_write(self.coordinator.bms.set_switch, self.key, False)


def setup_sensors(coordinator, entry, async_add_entities):
    # With control on, settings are number entities instead of sensors
    writable = set(SETTINGS) if balancer_control_enabled(coordinator) else set()

    def factory(key):
        if key in writable or sensor_meta(key) is None:
            return None
        return JKBalancerSensor(coordinator, key)

    add_entities_for_new_keys(coordinator, entry, async_add_entities, DATA, factory)


def setup_binary_sensors(coordinator, entry, async_add_entities):
    writable = set(SWITCHES) if balancer_control_enabled(coordinator) else set()

    def factory(key):
        return None if key in writable else JKBalancerBinarySensor(coordinator, key)

    add_entities_for_new_keys(coordinator, entry, async_add_entities, FLAGS, factory)


def setup_numbers(coordinator, entry, async_add_entities):
    if not balancer_control_enabled(coordinator):
        return

    def factory(key):
        return JKBalancerNumber(coordinator, key) if key in SETTINGS else None

    add_entities_for_new_keys(coordinator, entry, async_add_entities, DATA, factory)


def setup_switches(coordinator, entry, async_add_entities):
    if not balancer_control_enabled(coordinator):
        return

    def factory(key):
        return JKBalancerSwitch(coordinator, key) if key in SWITCHES else None

    add_entities_for_new_keys(coordinator, entry, async_add_entities, FLAGS, factory)
