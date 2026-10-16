"""JSD SOLAR actions for automations: raw command with reply, and an immediate re-read of entities."""
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_extract_entity_ids

from .const import DOMAIN, BMS_TYPE_JSD_SOLAR

SERVICE_SEND_COMMAND = "send_command"
SERVICE_REFRESH = "refresh"

SEND_COMMAND_SCHEMA = vol.Schema({
    vol.Optional("device_id"): cv.string,
    vol.Required("command"): cv.string,
    vol.Optional("attempts", default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
})
REFRESH_SCHEMA = vol.Schema(cv.TARGET_SERVICE_FIELDS)


def _inverters(hass):
    """entry_id -> coordinator of every loaded JSD SOLAR entry."""
    return {entry_id: c for entry_id, c in hass.data.get(DOMAIN, {}).items()
            if getattr(c, "bms_type", None) == BMS_TYPE_JSD_SOLAR}


def _inverter_for_device(hass, device_id):
    inverters = _inverters(hass)
    if not device_id:
        if len(inverters) != 1:
            raise HomeAssistantError(f"{len(inverters)} JSD SOLAR inverters loaded: choose the device")
        return next(iter(inverters.values()))
    device = dr.async_get(hass).async_get(device_id)
    if device is not None:
        for entry_id in device.config_entries:
            if entry_id in inverters:
                return inverters[entry_id]
    raise HomeAssistantError("The device is not a loaded JSD SOLAR inverter")


async def _async_send_command(hass, call: ServiceCall):
    coordinator = _inverter_for_device(hass, call.data.get("device_id"))
    try:
        return await hass.async_add_executor_job(
            coordinator.bms.send_command, call.data["command"], call.data["attempts"])
    except (ValueError, PermissionError) as err:
        raise HomeAssistantError(str(err)) from err


async def _async_refresh(hass, call: ServiceCall):
    inverters = _inverters(hass)
    registry = er.async_get(hass)
    # coordinator -> [(entity_id, key)]
    wanted = {}
    for entity_id in sorted(await async_extract_entity_ids(hass, call)):
        entry = registry.async_get(entity_id)
        coordinator = inverters.get(entry.config_entry_id) if entry else None
        prefix = f"{entry.config_entry_id}_inverter_" if entry else ""
        if coordinator is None or not entry.unique_id.startswith(prefix):
            raise HomeAssistantError(f"{entity_id} is not a JSD SOLAR inverter entity")
        wanted.setdefault(coordinator, []).append((entity_id, entry.unique_id[len(prefix):]))
    if not wanted:
        raise HomeAssistantError("No entities given")
    values = {}
    for coordinator, items in wanted.items():
        try:
            fresh = await coordinator.async_refresh_keys([key for _entity_id, key in items])
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        values.update({entity_id: fresh.get(key) for entity_id, key in items})
    return {"values": values}


def async_register(hass: HomeAssistant):
    """Register the actions once for the domain; each call picks its inverter entry."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):
        return

    async def send_command(call):
        return await _async_send_command(hass, call)

    async def refresh(call):
        return await _async_refresh(hass, call)

    hass.services.async_register(DOMAIN, SERVICE_SEND_COMMAND, send_command,
                                 schema=SEND_COMMAND_SCHEMA, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH, refresh,
                                 schema=REFRESH_SCHEMA, supports_response=SupportsResponse.OPTIONAL)
