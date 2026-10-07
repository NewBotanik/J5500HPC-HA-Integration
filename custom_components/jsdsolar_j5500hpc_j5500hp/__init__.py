"""The JSDSolar J5500HPC/J5500HP integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .jsdsolar_rs232 import LOG_BASIC, LOG_PROTOCOL
from .coordinator import GobelBatteryUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# number/select/switch/button only create entities for a JSD SOLAR entry with control enabled
PLATFORMS = ["sensor", "binary_sensor", "number", "select", "switch", "button"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the JSDSolar J5500HPC/J5500HP component from YAML."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up JSDSolar J5500HPC/J5500HP from a config entry."""
    coordinator = GobelBatteryUpdateCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})
    _apply_log_level(hass, entry, coordinator.log_depth)
    
    # Run the synchronous driver initialization
    if not await coordinator.async_setup():
        raise ConfigEntryNotReady(f"Failed to connect to BMS for {entry.title}")

    # Fetch initial data so entities have state on startup
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to the sensor and binary_sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload on options change, so control entities appear or disappear
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    return True

def _apply_log_level(hass: HomeAssistant, entry: ConfigEntry, depth: int):
    """Set the integration logger to the deepest debug level any loaded entry asks for."""
    depths = hass.data[DOMAIN].setdefault("_log_depths", {})
    if depth:
        depths[entry.entry_id] = depth
    else:
        depths.pop(entry.entry_id, None)
    deepest = max(depths.values(), default=0)
    level = logging.DEBUG if deepest >= LOG_PROTOCOL else logging.INFO if deepest >= LOG_BASIC else logging.NOTSET
    logging.getLogger(__package__).setLevel(level)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reload the entry after its options changed."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        _apply_log_level(hass, entry, 0)
        # Release socket/serial/background threads
        await hass.async_add_executor_job(coordinator.shutdown)

    return unload_ok
