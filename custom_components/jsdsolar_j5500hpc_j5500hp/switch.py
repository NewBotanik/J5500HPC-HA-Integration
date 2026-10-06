"""Switch platform: JSD SOLAR feature flags TE/TD (§9.1), when control is enabled."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .jsdsolar_rs232 import FEATURE_KEYS
from .jsdsolar_entity import JSDSolarEntity, add_entities_for_new_keys, control_enabled


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up feature-flag switches once TE? has been read; nothing for BMS entries or with control off."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if not control_enabled(coordinator):
        return

    def factory(key):
        return JSDSolarFeatureSwitch(coordinator, key) if key in FEATURE_KEYS else None

    add_entities_for_new_keys(coordinator, entry, async_add_entities, "inverter_flags", factory)


class JSDSolarFeatureSwitch(JSDSolarEntity, SwitchEntity):
    """One feature flag: on sends TE<letter>, off sends TD<letter>, then TE? is read back."""

    section = "inverter_flags"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:toggle-switch-outline"

    @property
    def is_on(self):
        return self._value

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_write(self.coordinator.bms.set_feature, self.key, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_write(self.coordinator.bms.set_feature, self.key, False)
