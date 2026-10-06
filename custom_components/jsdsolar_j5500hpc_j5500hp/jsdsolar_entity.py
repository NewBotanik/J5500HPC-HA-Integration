"""Shared helpers for the JSD SOLAR inverter entities."""
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, BMS_TYPE_JSD_SOLAR

# Words that title() would spell wrong in inverter entity names
INVERTER_NAME_FIXES = {
    "Pv": "PV", "Bms": "BMS", "Soc": "SOC", "Cv": "CV", "Eq": "EQ", "Mppt": "MPPT", "Dsp": "DSP",
    "Eeprom": "EEPROM", "Lcd": "LCD", "Pfc": "PFC", "Inv": "INV", "Inv1": "INV1", "Dcdc": "DC/DC",
    "Cc": "CC", "Adc": "ADC", "Dc": "DC", "Id": "ID",
}


def inverter_entity_name(key):
    """'pv_energy_today' -> 'PV Energy Today'."""
    return " ".join(INVERTER_NAME_FIXES.get(w, w) for w in key.replace("_", " ").title().split())


def inverter_device_info(coordinator):
    """Device card of the JSD SOLAR inverter, shared by all its entities."""
    identity = getattr(coordinator.bms, "identity", None) or {}
    info = {
        "identifiers": {(DOMAIN, f"{coordinator.entry.entry_id}_inverter")},
        "name": coordinator.device_name,
        "manufacturer": "JSD SOLAR",
        "model": "Inverter",
    }
    if identity.get("firmware_version"):
        info["sw_version"] = identity["firmware_version"]
    if identity.get("serial_number"):
        info["serial_number"] = identity["serial_number"]
    return info


def control_enabled(coordinator):
    """Writable entities exist only for a JSD SOLAR entry with control turned on in its options."""
    return coordinator.bms_type == BMS_TYPE_JSD_SOLAR and coordinator.jsd_control


def add_entities_for_new_keys(coordinator, entry, async_add_entities, section, factory):
    """Create entities for a key the moment it first shows up in coordinator.data[section].

    factory(key) returns an entity, a list of entities, or None to skip the key.
    """
    registered = set()

    def add_new():
        values = (coordinator.data or {}).get(section, {})
        new_entities = []
        for key in values:
            if key in registered:
                continue
            created = factory(key)
            registered.add(key)
            if isinstance(created, list):
                new_entities.extend(created)
            elif created is not None:
                new_entities.append(created)
        if new_entities:
            async_add_entities(new_entities)

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))


class JSDSolarEntity(CoordinatorEntity):
    """Base for inverter entities bound to one key of coordinator.data[section]."""

    section = "inverter"

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = f"{coordinator.device_name} {inverter_entity_name(key)}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_inverter_{key}"
        self._attr_device_info = inverter_device_info(coordinator)

    @property
    def _value(self):
        return (self.coordinator.data or {}).get(self.section, {}).get(self.key)

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return self.key in (self.coordinator.data or {}).get(self.section, {})

    async def _async_write(self, func, *args):
        """Run a driver write in the executor, then show the read-back value without a full poll."""
        try:
            result = await self.hass.async_add_executor_job(func, *args)
        except (ValueError, TimeoutError, PermissionError) as err:
            raise HomeAssistantError(str(err)) from err
        data = self.coordinator.data
        if data is not None:
            bms = self.coordinator.bms
            data.setdefault("inverter", {}).update(
                {k: v for k, v in {**bms.settings, **bms.slow_data}.items() if v is not None})
            data.setdefault("inverter_flags", {}).update(bms.slow_flags)
            self.coordinator.async_update_listeners()
        return result
