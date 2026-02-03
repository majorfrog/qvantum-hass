"""Constants for the Qvantum Heat Pump integration.

This module contains all constants used throughout the integration,
including:
- Domain and configuration constants
- API endpoints and authentication servers
- Entity mappings and configurations
- Sensor lists and categories
- Metric definitions

Organization:
    1. Domain and basic configuration
    2. API endpoints and authentication
    3. Device information
    4. State mappings for sensors
    5. Sensor configuration (disabled by default, writable, etc.)
    6. Metric information for internal sensors
"""

from typing import Final

# Domain and basic configuration constants
DOMAIN: Final = "qvantum_hass"

# Configuration keys
CONF_API_KEY: Final = "api_key"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_FAST_SCAN_INTERVAL: Final = "fast_scan_interval"

# Default values
DEFAULT_SCAN_INTERVAL: Final = 30  # seconds
DEFAULT_FAST_SCAN_INTERVAL: Final = 5  # seconds for power/current sensors

# API Endpoints and authentication
DEFAULT_API_ENDPOINT: Final = "https://api.qvantum.com"
DEFAULT_INTERNAL_API_ENDPOINT: Final = "https://api.qvantum.com"
DEFAULT_AUTH_SERVER: Final = "https://identitytoolkit.googleapis.com"
DEFAULT_TOKEN_SERVER: Final = "https://securetoken.googleapis.com"

# Firebase API key
DEFAULT_API_KEY: Final = "AIzaSyCLQ22XHjH8LmId-PB1DY8FBsN53rWTpFw"

# Device information
MANUFACTURER: Final = "Qvantum"
MODEL: Final = "Qvantum Heat Pump"

# State mappings for select and sensor entities
HP_STATUS_MAP: Final = {
    0: "idle",
    1: "defrosting",
    2: "hot_water",
    3: "heating",
}

OP_MODE_MAP: Final = {
    0: "auto",
    1: "manual",
    2: "additional_heat_only",
}

HOT_WATER_TEMP_MAP: Final = {
    52: "normal_52c",
    55: "hot_55c",
    58: "very_hot_58c",
}

HOT_WATER_PRIORITY_MAP: Final = {
    30: "normal_30min",
    60: "plus_1h",
    120: "plus_plus_2h",
}

# Sensor configuration and categorization
# These sets define which sensors should be created, enabled, or skipped
# based on their use case and access requirements.

# Settings handled by other entity platforms
# These settings are writable through number, select, or switch entities
# and should NOT have read-only sensor entities created for them.
WRITABLE_SETTINGS: Final = {
    "guide_he",  # Number entity
    "guide_des_temp",  # Number entity
    "op_man_dhw",  # Switch entity
    "op_man_addition",  # Switch entity
    "op_man_cooling",  # Switch entity
    "op_mode",  # Select entity (using OP_MODE_MAP)
    "dhw_prioritytime",  # Select entity (DHW Priority)
    "dhw_outl_temp_5",  # Select entity (DHW Out Temp)
    "tap_water_cap",  # Select entity (Tap Water Capacity)
    "smart_dhw_mode",  # Switch entity (Smart Control DHW)
    "smart_sh_mode",  # Switch entity (Smart Control Heating)
    # The DHW start/stop shown in sensors are READ-ONLY actual limits.
    # The writable versions are tap_water_start/stop (number entities).
}

# Advanced/diagnostic sensors disabled by default
# These are technical metrics that most users don't need in their
# default dashboard. Advanced users can enable them in the UI.
DISABLED_BY_DEFAULT_SENSORS: Final = {
    "bt2",  # Indoor temp (often not mounted)
    "bt4",  # BT4 (often not mounted)
    "btx",  # BTX (often not mounted)
    "bt12",  # BT12
    "bp1_temp_20min_filter",  # BP1 temp filter
    "max_bp2_env",  # Max BP2 environment
    "fan0_10v",  # Fan speed voltage
    "qn8position",  # Shunt valve position
    "calc_suppy_cpr",  # Calculated supply CPR
    "dhw_outl_temp_15",  # DHW outlet temp 15
    "dhw_outl_temp_max",  # DHW outlet temp max
    "filtered60sec_outdoortemp",  # Filtered outdoor temp
    "max_freq_env",  # Max frequency environment
    "dhw_set",  # DHW set (calculated value)
    "picpin_mask",  # PIC pin mask
    "switch_state",  # Switch state (raw value)
    "dhwdemand",  # DHW demand (raw value)
    "price_region",  # Price region - not commonly used
    "heatingdemand",  # Heating demand (raw value)
    "coolingdemand",  # Cooling demand (raw value)
    "heatingreleased",  # Heating released (raw value)
    "coolingreleased",  # Cooling released (raw value)
    "compressorreleased",  # Compressor released (raw value)
    "additionreleased",  # Addition released (raw value)
    "dhw_prioritytimeleft",  # DHW priority time left (also a select)
    "heating_prioritytimeleft",  # Heating priority time left
    "cooling_priotitytimeleft",  # Cooling priority time left
    "dhwstop_temp",  # DHW stop temp (read-only, show actual limit)
    "dhwstart_temp",  # DHW start temp (read-only, show actual limit)
    "room_temp_ext",  # Room temp external - most don't have it
    "cooling_enabled",  # Cooling enabled - most don't use cooling
    # Note: dhw_normal_start and dhw_normal_stop are kept enabled
    # as they show the actual operating limits
}

# Settings that should NOT be created as number entities
# (they're handled as select entities instead)
SKIP_NUMBER_SETTINGS: Final = [
    "tap_water_capacity_target",
    "dhw_mode",
    "op_mode",
    "room_comp_factor",
    "indoor_temperature_offset",  # Handled as select entity
    "sensor_mode",  # Handled as select entity
    "indoor_temperature_target",  # Handled as select entity
]

# Commonly-used number settings that should be enabled by default
# All other number settings are disabled by default
COMMONLY_USED_NUMBER_SETTINGS: Final = set()

# Commonly-used switch settings that should be enabled by default
# All other switch settings are disabled by default
COMMONLY_USED_SWITCH_SETTINGS: Final = {
    "vacation_mode",
}

# Commonly-used select settings that should be enabled by default
# All other select settings are disabled by default
COMMONLY_USED_SELECT_SETTINGS: Final = {
    "indoor_temperature_target",
    "smart_control_mode",
    # "dhw_mode",
    "op_mode",
    "tap_water_capacity_target",
    "dhw_priority_time",
    "dhw_out_temp",
    "room_comp_factor",
    "heating_curve_shift",
}

ROOM_COMP_MAP: Final = {
    0: "none",
    0.5: "minimum",
    1: "normal",
    2: "maximum",
}

CURVE_SHIFT_MAP: Final = {
    -9: "minus_9",
    -8: "minus_8",
    -7: "minus_7",
    -6: "minus_6",
    -5: "minus_5",
    -4: "minus_4",
    -3: "minus_3",
    -2: "minus_2",
    -1: "minus_1",
    0: "zero",
    1: "plus_1",
    2: "plus_2",
    3: "plus_3",
    4: "plus_4",
    5: "plus_5",
    6: "plus_6",
    7: "plus_7",
    8: "plus_8",
    9: "plus_9",
}

# Operation mode sensor mapping (which temp sensor controls the heat pump)
OP_MODE_SENSOR_MAP: Final = {
    0: "off",
    1: "bt2",
    2: "bt3",
    3: "btx",
}

# Sensor mode mapping for sensor_mode setting (writable version)
SENSOR_MODE_OPTIONS: Final = {
    "off": "off",
    "bt2": "bt2",
    "bt3": "bt3",
    "btx": "btx",
}

# Indoor temperature target options (15-25°C)
INDOOR_TEMP_TARGET_MAP: Final = {
    15: "temp_15c",
    16: "temp_16c",
    17: "temp_17c",
    18: "temp_18c",
    19: "temp_19c",
    20: "temp_20c",
    21: "temp_21c",
    22: "temp_22c",
    23: "temp_23c",
    24: "temp_24c",
    25: "temp_25c",
}

# Metric information: (name, unit, entity_type)
# Inline comments describe what each metric represents for documentation purposes.
METRIC_INFO: Final = [
    ("bf1_l_min", "l/m", "sensor"),  # Flow sensor DHW
    ("bp1_pressure", "bar", "sensor"),  # Low pressure bar
    ("bp1_temp", "°C", "sensor"),  # Low pressure temperature
    ("bp2_pressure", "bar", "sensor"),  # High pressure bar
    ("bp2_temp", "°C", "sensor"),  # High pressure temperature
    ("bt1", "°C", "sensor"),  # Outdoor
    ("bt2", "°C", "sensor"),  # Indoor
    ("bt10", "°C", "sensor"),  # Condenser outlet
    ("bt11", "°C", "sensor"),  # Heating medium flow
    ("bt13", "°C", "sensor"),  # Condenser inlet
    ("bt14", "°C", "sensor"),  # Exhaust air temperature
    ("bt15", "°C", "sensor"),  # Extract air temperature
    ("bt20", "°C", "sensor"),  # Discharge line
    ("bt21", "°C", "sensor"),  # Liquid line
    ("bt22", "°C", "sensor"),  # Evaporator inlet
    ("bt23", "°C", "sensor"),  # Suction line
    ("bt30", "°C", "sensor"),  # Accumulator tank
    ("bt31", "°C", "sensor"),  # DHW primary charge inlet
    ("bt33", "°C", "sensor"),  # DHW cold water inlet
    ("bt34", "°C", "sensor"),  # DHW hot water outlet
    ("cal_heat_temp", "°C", "sensor"),  # Heating medium flow target
    ("compressormeasuredspeed", "rpm", "sensor"),  # Compressor speed
    ("dhw_normal_start", "°C", "sensor"),  # Accumulator tank lower limit
    ("dhw_normal_stop", "°C", "sensor"),  # Accumulator tank upper limit
    ("fan0_10v", "%", "sensor"),  # Fan speed
    ("gp1_speed", "%", "sensor"),  # Circulation pump
    ("gp2_speed", "%", "sensor"),  # DHW charge pump
    ("picpin_relay_heat_l1", "bool", "binary_sensor"),  # Additional power L1
    ("picpin_relay_heat_l2", "bool", "binary_sensor"),  # Additional power L2
    ("picpin_relay_heat_l3", "bool", "binary_sensor"),  # Additional power L3
    (
        "picpin_relay_qm10",
        "bool",
        "binary_sensor",
    ),  # Diverting valve DHW/heating (QM10)
    ("qn8position", "%", "sensor"),  # Shuntvalve, addition (QN8)
    ("powertotal", "W", "sensor"),  # Total Power
    ("compressorenergy", "kWh", "sensor"),  # Compressor Energy
    ("additionalenergy", "kWh", "sensor"),  # Additional Energy
    ("inputcurrent1", "A", "sensor"),  # Input Current L1
    ("inputcurrent2", "A", "sensor"),  # Input Current L2
    ("inputcurrent3", "A", "sensor"),  # Input Current L3
    (
        "dhw_outl_temp_5",
        "°C",
        "sensor",
    ),  # DHW outlet temperature (setting for hot water out temperature)
    ("dhw_outl_temp_15", "°C", "sensor"),  # DHW outlet temperature 15
    ("dhw_outl_temp_max", "°C", "sensor"),  # DHW outlet temperature max
    ("dhw_prioritytime", "minutes", "sensor"),  # DHW priority time
    ("fanrpm", "rpm", "sensor"),  # Fan speed
    ("hp_status", None, "sensor"),  # Heat pump status
    ("tap_water_cap", "L", "sensor"),  # Hot water capacity
    ("op_mode", None, "sensor"),  # Operation mode
    ("op_mode_sensor", None, "sensor"),  # Operation mode sensor
    ("enable_sc_dhw", "bool", "binary_sensor"),  # SmartControl: DHW
    ("enable_sc_sh", "bool", "binary_sensor"),  # SmartControl: Heating
    ("use_adaptive", "bool", "binary_sensor"),  # SmartControl
    ("smart_sh_mode", None, "sensor"),  # Smart SH mode
    ("smart_dhw_mode", None, "sensor"),  # Smart DHW mode
    ("calc_suppy_cpr", "°C", "sensor"),  # Calculated Supply CPR
    ("btx", "°C", "sensor"),  # BTX
    ("bt4", "°C", "sensor"),  # BT4
    ("bt12", "°C", "sensor"),  # External heating flow
    ("dhwpower", "kW", "sensor"),  # DHW Power
    ("heatingpower", "kW", "sensor"),  # Heating Power
    ("cooling_enabled", "bool", "binary_sensor"),  # Cooling enabled
    ("guide_des_temp", "°C", "sensor"),  # Guide desired temperature
    ("guide_he", "°C", "sensor"),  # Guide heating
    ("price_region", None, "sensor"),  # Price region
    ("room_temp_ext", "°C", "sensor"),  # External room temperature
    ("dhwdemand", None, "sensor"),  # DHW demand
    ("heatingdemand", None, "sensor"),  # Heating demand
    ("coolingdemand", None, "sensor"),  # Cooling demand
    ("heatingreleased", None, "sensor"),  # Heating released
    ("coolingreleased", None, "sensor"),  # Cooling released
    ("compressorreleased", None, "sensor"),  # Compressor released
    ("additionreleased", None, "sensor"),  # Additional heat released
    ("dhw_prioritytimeleft", "minutes", "sensor"),  # DHW priority time remaining
    (
        "heating_prioritytimeleft",
        "minutes",
        "sensor",
    ),  # Heating priority time remaining
    (
        "cooling_priotitytimeleft",
        "minutes",
        "sensor",
    ),  # Cooling priority time remaining
    ("switch_state", None, "sensor"),  # Switch State
    ("dhwstop_temp", "°C", "sensor"),  # Accumulator tank stop temperature
    ("dhwstart_temp", "°C", "sensor"),  # Accumulator tank start temperature
    ("filtered60sec_outdoortemp", "°C", "sensor"),  # Outdoor temperature (60s filtered)
    ("max_freq_env", "Hz", "sensor"),  # Max Frequency Environment
    ("dhw_set", "°C", "sensor"),  # DHW Set
    ("bp1_temp_20min_filter", "°C", "sensor"),  # BP1 Temp 20min Filter
    ("max_bp2_env", "bar", "sensor"),  # Max BP2 Environment
    ("picpin_mask", None, "sensor"),  # PIC Pin Mask
]

# List of metric names for API requests
# Manual Operation Mode metrics are fetched but not created as sensors
# (only used by switch entities - they were removed from METRIC_INFO)
METRIC_NAMES: Final = [metric[0] for metric in METRIC_INFO] + [
    "man_mode",
    "op_man_dhw",
    "op_man_addition",
    "op_man_cooling",
]

# Fast polling metrics - power and current sensors that benefit from frequent updates
# These metrics change rapidly and provide real-time monitoring of energy usage
FAST_POLLING_METRICS: Final = [
    "powertotal",  # Total power consumption (W) - changes rapidly
    "heatingpower",  # Heating power (kW) - real-time heating load
    "dhwpower",  # DHW power (kW) - real-time hot water power
    "inputcurrent1",  # Input current L1 (A) - rapid electrical monitoring
    "inputcurrent2",  # Input current L2 (A) - rapid electrical monitoring
    "inputcurrent3",  # Input current L3 (A) - rapid electrical monitoring
    "bf1_l_min",  # Flow sensor DHW (l/m) - rapid flow changes
]
