"""Config flow for JSDSolar J5500HPC/J5500HP integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_BMS_TYPE,
    CONF_CONNECTION_TYPE,
    CONF_BATTERY_PORT,
    CONF_IP_ADDRESS,
    CONF_IP_PORT,
    CONF_USB_PORT,
    CONF_BAUD_RATE,
    CONF_POLL_INTERVAL,
    CONF_JK_DISPLAY_INDEX_START,
    CONF_MAX_PARALLEL,
    CONF_JSD_ENABLE_CONTROL,
    CONF_JSD_AUTO_CLOCK_SYNC,
    CONF_DEBUG_LOGGING,
    CONF_LOG_DEPTH,
    LOG_DEPTHS,
    DEFAULT_LOG_DEPTH,
    BMS_TYPES,
    BMS_TYPE_JSD_SOLAR,
    BMS_TYPE_JK_BALANCER,
    BMS_TYPE_PACE_LV,
    BMS_TYPE_PACE_LV_WIFI,
    CONF_PACE_CURRENT_SCALE,
    PACE_CURRENT_SCALES,
    DEFAULT_PACE_CURRENT_SCALE,
    CONNECTION_TYPES,
    BATTERY_PORTS,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_MAX_PARALLEL,
    DEFAULT_BAUD_RATE,
    DEFAULT_JSD_SOLAR_BAUD_RATE,
    DEFAULT_JK_BALANCER_BAUD_RATE,
    DEFAULT_JK_BALANCER_ADDRESS,
    CONF_JK_BALANCER_ADDRESS,
    CONF_JK_BALANCER_ENABLE_CONTROL,
    DEFAULT_IP_PORT,
    CONN_TYPE_SERIAL,
    DEFAULT_JK_DISPLAY_INDEX_START,
)

_LOGGER = logging.getLogger(__name__)

# Device type -> (default device name, default poll interval in s); BMS types use "Gobel Battery", 5 s
DEVICE_DEFAULTS = {
    # One inverter cycle takes about 5 s at 2400 baud
    BMS_TYPE_JSD_SOLAR: ("J5500HPC", 10),
    BMS_TYPE_JK_BALANCER: ("JK Balancer", DEFAULT_POLL_INTERVAL),
}


def _default_baud(bms_type):
    if bms_type == BMS_TYPE_JSD_SOLAR:
        return DEFAULT_JSD_SOLAR_BAUD_RATE
    if bms_type == BMS_TYPE_JK_BALANCER:
        return DEFAULT_JK_BALANCER_BAUD_RATE
    return DEFAULT_BAUD_RATE

class GobelBatteryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gobel Battery."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Options (Configure button) of an existing entry."""
        return GobelBatteryOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """First step: device type and connection; the next step asks only what that type needs."""
        if user_input is not None:
            # The list uses lower-case values (translation keys must be [a-z0-9-_]); entries store BMS_TYPES
            self.config_data = {**user_input, CONF_BMS_TYPE: user_input[CONF_BMS_TYPE].upper()}
            return await self.async_step_device()

        data_schema = vol.Schema(
            {
                # Labelled list: JK_PB (JK BMS) and JK_BALANCER are easy to mix up by code alone
                vol.Required(CONF_BMS_TYPE, default=BMS_TYPE_JSD_SOLAR.lower()): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[bms_type.lower() for bms_type in BMS_TYPES], translation_key="bms_type",
                        mode=selector.SelectSelectorMode.LIST
                    )
                ),
                vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_TYPES[0]): vol.In(CONNECTION_TYPES),
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_device(self, user_input=None):
        """Device name, poll interval and the type-specific fields (BMS port and pack numbering only for BMS)."""
        bms_type = self.config_data[CONF_BMS_TYPE]
        if user_input is not None:
            self.config_data.update(user_input)
            if self.config_data[CONF_CONNECTION_TYPE] in ["ethernet", "wifi"]:
                return await self.async_step_network()
            return await self.async_step_serial()

        default_name, default_poll = DEVICE_DEFAULTS.get(bms_type, ("Gobel Battery", DEFAULT_POLL_INTERVAL))
        fields = {
            vol.Required("device_name", default=default_name): str,
            vol.Optional(CONF_POLL_INTERVAL, default=default_poll): vol.All(vol.Coerce(int), vol.Range(min=1)),
        }
        # The inverter and the balancer have one fixed protocol each: no BMS port, packs or numbering
        if bms_type not in (BMS_TYPE_JSD_SOLAR, BMS_TYPE_JK_BALANCER):
            fields.update({
                vol.Required(CONF_BATTERY_PORT, default=BATTERY_PORTS[0]): vol.In(BATTERY_PORTS),
                vol.Optional(CONF_MAX_PARALLEL, default=DEFAULT_MAX_PARALLEL): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(CONF_JK_DISPLAY_INDEX_START, default=DEFAULT_JK_DISPLAY_INDEX_START): vol.In(["00", "01"]),
            })
        return self.async_show_form(step_id="device", data_schema=vol.Schema(fields))

    async def async_step_network(self, user_input=None):
        """Handle network configuration parameters (IP and port)."""
        errors = {}
        if user_input is not None:
            user_data = {**self.config_data, **user_input}
            unique_id = f"{user_data[CONF_IP_ADDRESS]}_{user_data[CONF_IP_PORT]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(title=user_data["device_name"], data=user_data)

        network_schema = vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS): str,
                vol.Required(CONF_IP_PORT, default=DEFAULT_IP_PORT): int,
            }
        )

        return self.async_show_form(
            step_id="network", data_schema=network_schema, errors=errors
        )

    async def async_step_serial(self, user_input=None):
        """Handle serial configuration parameters (Port and Baud rate)."""
        errors = {}
        if user_input is not None:
            user_data = {**self.config_data, **user_input}
            unique_id = user_data[CONF_USB_PORT]
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(title=user_data["device_name"], data=user_data)

        # JSD SOLAR inverters talk at a fixed 2400 baud, the JK balancer at 9600
        default_baud = _default_baud(self.config_data[CONF_BMS_TYPE])
        serial_schema = vol.Schema(
            {
                vol.Required(CONF_USB_PORT, default="/dev/ttyUSB0"): str,
                vol.Required(CONF_BAUD_RATE, default=default_baud): int,
            }
        )

        return self.async_show_form(
            step_id="serial", data_schema=serial_schema, errors=errors
        )


class GobelBatteryOptionsFlow(config_entries.OptionsFlow):
    """Options of an entry: poll interval, debug logging and, for JSD SOLAR, inverter control."""

    def __init__(self, config_entry):
        # Stored under a private name: HA 2024.12+ provides self.config_entry itself
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._entry.options
        data = self._entry.data

        def current(key, default=None):
            return options.get(key, data.get(key, default))

        poll_interval = current(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        fields = {}
        # Connection of this entry: serial port and baud rate, or bridge IP and TCP port
        if data.get(CONF_CONNECTION_TYPE) == CONN_TYPE_SERIAL:
            default_baud = _default_baud(data.get(CONF_BMS_TYPE))
            fields[vol.Required(CONF_USB_PORT, default=current(CONF_USB_PORT, "/dev/ttyUSB0"))] = str
            fields[vol.Required(CONF_BAUD_RATE, default=current(CONF_BAUD_RATE, default_baud))] = selector.NumberSelector(
                selector.NumberSelectorConfig(min=300, max=921600, step=1, mode=selector.NumberSelectorMode.BOX)
            )
        else:
            fields[vol.Required(CONF_IP_ADDRESS, default=current(CONF_IP_ADDRESS, ""))] = str
            fields[vol.Required(CONF_IP_PORT, default=current(CONF_IP_PORT, DEFAULT_IP_PORT))] = selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=65535, step=1, mode=selector.NumberSelectorMode.BOX)
            )
        fields.update({
            vol.Required(CONF_POLL_INTERVAL, default=poll_interval): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=3600, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s"
                )
            ),
            vol.Required(CONF_DEBUG_LOGGING, default=options.get(CONF_DEBUG_LOGGING, False)): bool,
            vol.Required(CONF_LOG_DEPTH, default=options.get(CONF_LOG_DEPTH, DEFAULT_LOG_DEPTH)): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=LOG_DEPTHS, translation_key="log_depth", mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
        })
        if self._entry.data.get(CONF_BMS_TYPE) == BMS_TYPE_JSD_SOLAR:
            fields[vol.Required(
                CONF_JSD_ENABLE_CONTROL, default=options.get(CONF_JSD_ENABLE_CONTROL, False)
            )] = bool
            fields[vol.Required(
                CONF_JSD_AUTO_CLOCK_SYNC, default=options.get(CONF_JSD_AUTO_CLOCK_SYNC, False)
            )] = bool
        if self._entry.data.get(CONF_BMS_TYPE) == BMS_TYPE_JK_BALANCER:
            fields[vol.Required(
                CONF_JK_BALANCER_ADDRESS, default=options.get(CONF_JK_BALANCER_ADDRESS, DEFAULT_JK_BALANCER_ADDRESS)
            )] = selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=255, step=1, mode=selector.NumberSelectorMode.BOX)
            )
            fields[vol.Required(
                CONF_JK_BALANCER_ENABLE_CONTROL, default=options.get(CONF_JK_BALANCER_ENABLE_CONTROL, False)
            )] = bool
        if self._entry.data.get(CONF_BMS_TYPE) in (BMS_TYPE_PACE_LV, BMS_TYPE_PACE_LV_WIFI):
            fields[vol.Required(
                CONF_PACE_CURRENT_SCALE, default=options.get(CONF_PACE_CURRENT_SCALE, DEFAULT_PACE_CURRENT_SCALE)
            )] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=PACE_CURRENT_SCALES, translation_key="pace_current_scale",
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields))
