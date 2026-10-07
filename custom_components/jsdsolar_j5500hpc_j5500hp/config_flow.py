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
    CONF_DEBUG_LOGGING,
    CONF_LOG_DEPTH,
    LOG_DEPTHS,
    DEFAULT_LOG_DEPTH,
    BMS_TYPES,
    BMS_TYPE_JSD_SOLAR,
    CONNECTION_TYPES,
    BATTERY_PORTS,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_MAX_PARALLEL,
    DEFAULT_BAUD_RATE,
    DEFAULT_JSD_SOLAR_BAUD_RATE,
    DEFAULT_IP_PORT,
    CONN_TYPE_SERIAL,
    DEFAULT_JK_DISPLAY_INDEX_START,
)

_LOGGER = logging.getLogger(__name__)

class GobelBatteryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gobel Battery."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Options (Configure button) of an existing entry."""
        return GobelBatteryOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step."""
        errors = {}
        if user_input is not None:
            self.config_data = user_input
            if user_input[CONF_CONNECTION_TYPE] in ["ethernet", "wifi"]:
                return await self.async_step_network()
            else:
                return await self.async_step_serial()

        data_schema = vol.Schema(
            {
                vol.Required("device_name", default="Gobel Battery"): str,
                vol.Required(CONF_BMS_TYPE, default=BMS_TYPES[0]): vol.In(BMS_TYPES),
                vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_TYPES[0]): vol.In(CONNECTION_TYPES),
                vol.Required(CONF_BATTERY_PORT, default=BATTERY_PORTS[0]): vol.In(BATTERY_PORTS),
                vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(CONF_MAX_PARALLEL, default=DEFAULT_MAX_PARALLEL): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(CONF_JK_DISPLAY_INDEX_START, default=DEFAULT_JK_DISPLAY_INDEX_START): vol.In(["00", "01"]),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

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

        # JSD SOLAR inverters talk at a fixed 2400 baud
        default_baud = DEFAULT_JSD_SOLAR_BAUD_RATE if self.config_data[CONF_BMS_TYPE] == BMS_TYPE_JSD_SOLAR else DEFAULT_BAUD_RATE
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
            default_baud = DEFAULT_JSD_SOLAR_BAUD_RATE if data.get(CONF_BMS_TYPE) == BMS_TYPE_JSD_SOLAR else DEFAULT_BAUD_RATE
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
        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields))
