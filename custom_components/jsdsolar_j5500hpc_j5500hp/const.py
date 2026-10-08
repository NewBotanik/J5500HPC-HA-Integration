"""Constants for the JSDSolar J5500HPC/J5500HP integration."""

DOMAIN = "jsdsolar_j5500hpc_j5500hp"

CONF_BMS_TYPE = "bms_type"
CONF_CONNECTION_TYPE = "connection_type"
CONF_BATTERY_PORT = "battery_port"
CONF_IP_ADDRESS = "ip_address"
CONF_IP_PORT = "ip_port"
CONF_USB_PORT = "usb_port"
CONF_BAUD_RATE = "baud_rate"
CONF_POLL_INTERVAL = "poll_interval"
CONF_JK_DISPLAY_INDEX_START = "jk_display_index_start"
CONF_MAX_PARALLEL = "max_parallel_allowed"
# Options flow: allow JSD SOLAR settings/control writes (off by default)
CONF_JSD_ENABLE_CONTROL = "jsd_enable_control"
# Options flow, JK balancer: RS485 slave address and settings writes (off by default)
CONF_JK_BALANCER_ADDRESS = "jk_balancer_address"
CONF_JK_BALANCER_ENABLE_CONTROL = "jk_balancer_enable_control"
# Options flow: debug logging of this entry and how deep it goes
CONF_DEBUG_LOGGING = "debug_logging"
CONF_LOG_DEPTH = "log_depth"
LOG_DEPTH_BASIC = "basic"
LOG_DEPTH_PROTOCOL = "protocol"
LOG_DEPTH_PARSING = "parsing"
LOG_DEPTHS = [LOG_DEPTH_BASIC, LOG_DEPTH_PROTOCOL, LOG_DEPTH_PARSING]
DEFAULT_LOG_DEPTH = LOG_DEPTH_PROTOCOL

# Option Choices
BMS_TYPE_PACE_LV = "PACE_LV"
BMS_TYPE_PACE_LV_WIFI = "PACE_LV_WIFI"
BMS_TYPE_JK_PB = "JK_PB"
BMS_TYPE_TDT = "TDT"
# JSD SOLAR inverter (e.g. J5500HPC), not a BMS; kept in the same selector for one config flow
BMS_TYPE_JSD_SOLAR = "JSD_SOLAR"

# JK-DZ11-B2A24S stand-alone active balancer over RS485 (request/response, not the JK BMS 55AA stream)
BMS_TYPE_JK_BALANCER = "JK_BALANCER"

BMS_TYPES = [BMS_TYPE_PACE_LV, BMS_TYPE_PACE_LV_WIFI, BMS_TYPE_JK_PB, BMS_TYPE_TDT, BMS_TYPE_JSD_SOLAR, BMS_TYPE_JK_BALANCER]

CONN_TYPE_ETHERNET = "ethernet"
CONN_TYPE_WIFI = "wifi"
CONN_TYPE_SERIAL = "serial"

CONNECTION_TYPES = [CONN_TYPE_ETHERNET, CONN_TYPE_WIFI, CONN_TYPE_SERIAL]

PORT_RS232 = "rs232"
PORT_RS485 = "rs485"

BATTERY_PORTS = [PORT_RS232, PORT_RS485]

DEFAULT_POLL_INTERVAL = 5
DEFAULT_MAX_PARALLEL = 16
DEFAULT_BAUD_RATE = 115200
DEFAULT_JSD_SOLAR_BAUD_RATE = 2400
DEFAULT_JK_BALANCER_BAUD_RATE = 9600
DEFAULT_JK_BALANCER_ADDRESS = 1
DEFAULT_IP_PORT = 8899
DEFAULT_JK_DISPLAY_INDEX_START = "01"
