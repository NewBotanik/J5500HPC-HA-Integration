"""Select platform: JSD SOLAR inverter settings with fixed choices (§9), when control is enabled."""
from homeassistant.components.select import SelectEntity
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
    """Set up inverter setting selects; nothing for BMS entries or with control off."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if not control_enabled(coordinator):
        return

    def factory(key):
        setting = SETTINGS.get(key)
        if setting is None or not setting.options:
            return None
        return JSDSolarSettingSelect(coordinator, key)

    add_entities_for_new_keys(coordinator, entry, async_add_entities, "inverter", factory)


class JSDSolarSettingSelect(JSDSolarEntity, SelectEntity):
    """One enumerated setting, e.g. output or charger source priority."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        setting = SETTINGS[key]
        self._attr_options = list(setting.options.values())
        self._attr_icon = setting.icon

    @property
    def current_option(self):
        value = self._value
        return value if value in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        await self._async_write(self.coordinator.bms.set_setting, self.key, option)
