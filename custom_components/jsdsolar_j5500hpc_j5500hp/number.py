"""Number platform: numeric JSD SOLAR inverter settings (§9), when control is enabled."""
from homeassistant.components.number import NumberEntity, NumberMode, NumberDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .jsdsolar_rs232 import SETTINGS
from .jsdsolar_entity import JSDSolarEntity, add_entities_for_new_keys, control_enabled


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up inverter setting numbers; nothing for BMS entries or with control off."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if not control_enabled(coordinator):
        return

    def factory(key):
        setting = SETTINGS.get(key)
        if setting is None or setting.options:
            return None
        return JSDSolarSettingNumber(coordinator, key)

    add_entities_for_new_keys(coordinator, entry, async_add_entities, "inverter", factory)


class JSDSolarSettingNumber(JSDSolarEntity, NumberEntity):
    """One numeric setting; the value shown is always the one read back from the inverter."""

    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self._setting = SETTINGS[key]
        self._attr_native_unit_of_measurement = self._setting.unit or None
        self._attr_native_step = 0.1 if self._setting.cast is float else 1
        self._attr_icon = self._setting.icon
        if self._setting.device_class:
            self._attr_device_class = NumberDeviceClass(self._setting.device_class)

    @property
    def native_min_value(self):
        # Battery-voltage limits follow the detected 12/24/48 V system
        low, _high = self.coordinator.bms.setting_range(self.key)
        return low if low is not None else 0

    @property
    def native_max_value(self):
        _low, high = self.coordinator.bms.setting_range(self.key)
        return high if high is not None else 99999

    @property
    def native_value(self):
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        await self._async_write(self.coordinator.bms.set_setting, self.key, value)
