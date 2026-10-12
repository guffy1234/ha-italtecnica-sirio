"""Constants for the Sirio pump controller integration."""

DOMAIN = "sirio"
MANUFACTURER = "Italtecnica"

DEFAULT_PORT = 8080
DEFAULT_NAME = "Sirio"
DEFAULT_SCAN_INTERVAL = 10  # seconds; the controller's own web page polls every 200 ms
MIN_SCAN_INTERVAL = 1
MAX_SCAN_INTERVAL = 300
PARAM_SCAN_INTERVAL = 300  # seconds; parameters rarely change, so read them slowly
PARAM_RETRY_INTERVAL = 30  # seconds; sooner while some parameter has never been read
REQUEST_TIMEOUT = 10  # seconds

# Option: parameters are read-only unless the user explicitly allows changes.
CONF_ALLOW_WRITE = "allow_parameter_changes"

# Error codes reported by the controller (counters e0..e13 in the status JSON)
ERRORS: dict[int, str] = {
    0: "E0 - Low voltage",
    1: "E1 - High voltage",
    2: "E2 - Short circuit",
    3: "E3 - Dry running",
    4: "E4 - Ambient temperature",
    5: "E5 - Module temperature",
    6: "E6 - Overload",
    7: "E7 - Out of curve",
    8: "E8 - Serial error",
    9: "E9 - Pressure limit",
    10: "E10 - External error",
    11: "E11 - Max starts per hour",
    12: "E12 - 12V error",
    13: "E13 - Pressure sensor error",
}
