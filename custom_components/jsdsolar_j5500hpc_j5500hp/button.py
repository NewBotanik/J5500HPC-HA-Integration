"""Button platform: JSD SOLAR control commands (§7, §9.3) and clock sync, when control is enabled."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .jsdsolar_entity import JSDSolarEntity, add_entities_for_new_keys, control_enabled

# action -> (icon, enabled by default). Commands that cut the output or erase data start disabled.
BUTTONS = {
    "power_on": ("mdi:power-on", True),
    "power_off": ("mdi:power-off", False),
    "reset_energy_counters": ("mdi:counter", False),
    "factory_reset": ("mdi:restore-alert", False),
    "sync_clock": ("mdi:clock-check-outline", True),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up control buttons; per-unit SPON/SPOFF buttons appear when parallel units are found."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if not control_enabled(coordinator):
        return

    async_add_entities(JSDSolarActionButton(coordinator, action) for action in BUTTONS)

    def factory(key):
        # 'parallel_<n>_communication_ok' marks a discovered parallel unit
        if not (key.startswith("parallel_") and key.endswith("_communication_ok")):
            return None
        unit = int(key.split("_")[1])
        return [JSDSolarParallelButton(coordinator, unit, action) for action in ("power_on", "power_off")]

    add_entities_for_new_keys(coordinator, entry, async_add_entities, "inverter_flags", factory)


class JSDSolarActionButton(JSDSolarEntity, ButtonEntity):
    """SON / SOFF / Q / ED1, or DATE+TIME sync from the Home Assistant clock."""

    def __init__(self, coordinator, action):
        super().__init__(coordinator, action)
        self._action = action
        self._attr_icon, self._attr_entity_registry_enabled_default = BUTTONS[action]
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def available(self) -> bool:
        # Buttons have no state of their own; they work while the inverter answers
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        await self._async_write(self.coordinator.bms.run_action, self._action, None, dt_util.now())


class JSDSolarParallelButton(JSDSolarEntity, ButtonEntity):
    """SPON<n> / SPOFF<n> for one unit of a parallel system."""

    def __init__(self, coordinator, unit, action):
        super().__init__(coordinator, f"parallel_{unit}_{action}")
        self._unit = unit
        self._action = action
        self._attr_icon = BUTTONS[action][0]
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_entity_registry_enabled_default = action == "power_on"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        await self._async_write(self.coordinator.bms.run_action, self._action, self._unit)
