"""Sensor platform for Qvantum Heat Pump integration.

This module provides sensor entities for monitoring Qvantum heat pumps.
It creates sensors for:
- Temperature measurements (outdoor, indoor, flow, tank, etc.)
- Energy consumption (total, compressor, additional)
- Performance metrics (speeds, flow rates, pressures)
- System status (heat pump status, operation mode)
- Device information (firmware versions, uptime)
- Access control (access level, expiry)
- Alarms (count, active alarms)

Sensors are automatically categorized as diagnostic or configuration
entities where appropriate, and advanced sensors are disabled by default
to provide a clean initial user experience.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import logging
from typing import Any, Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import QvantumDataUpdateCoordinator
from .entity import QvantumEntity
from .models import EntitySource, QvantumEntityDef

PARALLEL_UPDATES = 0

# =============================================================================
# State mappings for sensor entities
#
# These dicts map internal numeric values to human-readable state strings
# used by sensor entities for display. Co-located here with the sensor
# classes that consume them.
# =============================================================================

HP_STATUS_MAP: Final = {
    0: "idle",
    1: "defrosting",
    2: "hot_water",
    3: "heating",
}

OP_MODE_SENSOR_MAP: Final = {
    0: "off",
    1: "bt2",
    2: "bt3",
    3: "btx",
}

GUIDE_HE_MAP: Final = {
    0: "underfloor_heating",
    1: "radiators",
}

BTX_CONFIG_MAP: Final = {
    0: "undef_ntc_10k",
    1: "pool_ntc_10k",
    2: "sg_ready_a",
}

BT4_CONFIG_MAP: Final = {
    0: "undef_ntc_10k",
    1: "sg_ready_b",
}


# =============================================================================
# Entity definitions for this platform
#
# Each entity is declared once here. definitions.py imports these to
# build the full cross-platform collection used by the coordinator.
# =============================================================================

ENTITY_DEFS: Final[list[QvantumEntityDef]] = [
    # =========================================================================
    # TEMPERATURE SENSORS (source: internal_metrics)
    # Thermocouple and NTC temperature readings from heat pump circuits.
    # =========================================================================
    QvantumEntityDef(
        "bt1",
        "Outdoor temperature sensor",
        unit="°C",
    ),
    QvantumEntityDef(
        "bt2",
        "Indoor temperature sensor (often not mounted)",
        unit="°C",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "bt4",
        "BT4 auxiliary temperature sensor (often not mounted)",
        unit="°C",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "bt10",
        "Condenser outlet temperature",
        unit="°C",
    ),
    QvantumEntityDef(
        "bt11",
        "Heating medium flow temperature (to radiators/underfloor)",
        unit="°C",
    ),
    QvantumEntityDef(
        "bt12",
        "External heating flow temperature",
        unit="°C",
    ),
    QvantumEntityDef(
        "bt13",
        "Condenser inlet (return) temperature",
        unit="°C",
    ),
    QvantumEntityDef(
        "bt14",
        "Exhaust air temperature (air leaving the building)",
        unit="°C",
    ),
    QvantumEntityDef(
        "bt15",
        "Extract air temperature (air from rooms)",
        unit="°C",
    ),
    QvantumEntityDef(
        "bt20",
        "Discharge line temperature (compressor outlet)",
        unit="°C",
    ),
    QvantumEntityDef(
        "bt21",
        "Liquid line temperature (after condenser)",
        unit="°C",
    ),
    QvantumEntityDef(
        "bt22",
        "Evaporator inlet temperature",
        unit="°C",
    ),
    QvantumEntityDef(
        "bt23",
        "Suction line temperature (compressor inlet)",
        unit="°C",
    ),
    QvantumEntityDef(
        "bt30",
        "Accumulator (hot water) tank temperature",
        unit="°C",
    ),
    QvantumEntityDef(
        "bt31",
        "DHW primary charge inlet temperature",
        unit="°C",
    ),
    QvantumEntityDef(
        "bt33",
        "DHW cold water inlet temperature",
        unit="°C",
    ),
    QvantumEntityDef(
        "bt34",
        "DHW hot water outlet temperature",
        unit="°C",
    ),
    QvantumEntityDef(
        "btx",
        "BTX external temperature sensor (often not mounted)",
        unit="°C",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "cal_heat_temp",
        "Calculated heating medium flow target temperature",
        unit="°C",
    ),
    QvantumEntityDef(
        "dhw_normal_start",
        "Accumulator tank lower limit (heating starts)",
        unit="°C",
    ),
    QvantumEntityDef(
        "dhw_normal_stop",
        "Accumulator tank upper limit (heating stops)",
        unit="°C",
    ),
    QvantumEntityDef(
        "dhw_outl_temp_15",
        "DHW outlet temperature 15-minute average",
        unit="°C",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "dhw_outl_temp_max",
        "DHW outlet temperature maximum recorded",
        unit="°C",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "dhwstop_temp",
        "Accumulator tank stop temperature (actual limit)",
        unit="°C",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "dhwstart_temp",
        "Accumulator tank start temperature (actual limit)",
        unit="°C",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "filtered60sec_outdoortemp",
        "Outdoor temperature (60-second filtered)",
        unit="°C",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "calc_suppy_cpr",
        "Calculated supply temperature for compressor",
        unit="°C",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "bp1_temp",
        "Low pressure (evaporator) temperature",
        unit="°C",
    ),
    QvantumEntityDef(
        "bp2_temp",
        "High pressure (condenser) temperature",
        unit="°C",
    ),
    QvantumEntityDef(
        "bp1_temp_20min_filter",
        "Low pressure temperature (20 min filter)",
        unit="°C",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "dhw_set",
        "DHW target temperature (calculated by heat pump)",
        unit="°C",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "room_temp_ext",
        "External room temperature sensor reading",
        unit="°C",
        enabled_by_default=False,
    ),
    # =========================================================================
    # PRESSURE SENSORS (source: internal_metrics)
    # Refrigerant circuit pressure measurements.
    # =========================================================================
    QvantumEntityDef(
        "bp1_pressure",
        "Low pressure (evaporator side)",
        unit="bar",
    ),
    QvantumEntityDef(
        "bp2_pressure",
        "High pressure (condenser side)",
        unit="bar",
    ),
    QvantumEntityDef(
        "max_bp2_env",
        "Maximum allowed high pressure (envelope limit)",
        unit="bar",
        enabled_by_default=False,
    ),
    # =========================================================================
    # FLOW & SPEED SENSORS (source: internal_metrics)
    # Pump speeds, fan speeds, valve positions, and flow rates.
    # =========================================================================
    QvantumEntityDef(
        "bf1_l_min",
        "DHW flow sensor (domestic hot water flow rate)",
        unit="L/min",
        fast_polling=True,
    ),
    QvantumEntityDef(
        "compressormeasuredspeed",
        "Compressor measured speed",
        unit="rpm",
    ),
    QvantumEntityDef(
        "fanrpm",
        "Ventilation fan speed",
        unit="rpm",
    ),
    QvantumEntityDef(
        "fan0_10v",
        "Fan speed as 0-10V signal percentage",
        unit="%",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "gp1_speed",
        "Circulation pump speed (heating circuit)",
        unit="%",
    ),
    QvantumEntityDef(
        "gp2_speed",
        "DHW charge pump speed (hot water circuit)",
        unit="%",
    ),
    QvantumEntityDef(
        "qn8position",
        "Shunt valve position QN8 (additional heat mixing)",
        unit="%",
        enabled_by_default=True,
    ),
    # =========================================================================
    # POWER & ENERGY SENSORS (source: internal_metrics)
    # Real-time power consumption and cumulative energy usage.
    # =========================================================================
    QvantumEntityDef(
        "powertotal",
        "Total power consumption (all circuits)",
        unit="W",
        fast_polling=True,
    ),
    QvantumEntityDef(
        "heatingpower",
        "Heating circuit power output",
        unit="kW",
        fast_polling=True,
    ),
    QvantumEntityDef(
        "dhwpower",
        "Domestic hot water power output",
        unit="kW",
        fast_polling=True,
    ),
    QvantumEntityDef(
        "compressorenergy",
        "Compressor cumulative energy",
        unit="kWh",
    ),
    QvantumEntityDef(
        "additionalenergy",
        "Additional heater cumulative energy",
        unit="kWh",
    ),
    # =========================================================================
    # CURRENT SENSORS (source: internal_metrics)
    # Per-phase electrical current measurements.
    # =========================================================================
    QvantumEntityDef(
        "inputcurrent1",
        "Input current phase L1",
        unit="A",
        fast_polling=True,
    ),
    QvantumEntityDef(
        "inputcurrent2",
        "Input current phase L2",
        unit="A",
        fast_polling=True,
    ),
    QvantumEntityDef(
        "inputcurrent3",
        "Input current phase L3",
        unit="A",
        fast_polling=True,
    ),
    # =========================================================================
    # FREQUENCY SENSOR (source: internal_metrics)
    # =========================================================================
    QvantumEntityDef(
        "max_freq_env",
        "Maximum compressor frequency (envelope limit)",
        unit="Hz",
        enabled_by_default=False,
    ),
    # =========================================================================
    # HOT WATER CAPACITY SENSOR (source: internal_metrics)
    # =========================================================================
    QvantumEntityDef(
        "tap_water_cap",
        "Hot water capacity (current level in litres)",
        unit="L",
    ),
    # =========================================================================
    # STATUS & MODE SENSORS (source: internal_metrics, enum type)
    # These sensors display mapped string values from numeric codes.
    # =========================================================================
    QvantumEntityDef(
        "hp_status",
        "Heat pump operational status (idle/defrost/hot water/heating)",
    ),
    QvantumEntityDef(
        "op_mode_sensor",
        "Active temperature sensor for heat pump control",
    ),
    QvantumEntityDef(
        "guide_he",
        "Heat emitter type configured in setup guide",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # =========================================================================
    # TIMER SENSORS (source: internal_metrics)
    # Priority mode time remaining counters.
    # =========================================================================
    QvantumEntityDef(
        "dhw_prioritytimeleft",
        "DHW priority time remaining",
        unit="minutes",
        enabled_by_default=True,
    ),
    QvantumEntityDef(
        "heating_prioritytimeleft",
        "Heating priority time remaining",
        unit="minutes",
        enabled_by_default=True,
    ),
    QvantumEntityDef(
        "cooling_priotitytimeleft",
        "Cooling priority time remaining",
        unit="minutes",
        enabled_by_default=True,
    ),
    # =========================================================================
    # MISCELLANEOUS SENSORS (source: internal_metrics)
    # Raw internal values — disabled by default.
    # =========================================================================
    QvantumEntityDef(
        "price_region",
        "Electricity price region code",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "switch_state",
        "Internal relay switch state bitmask",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "picpin_mask",
        "PIC microcontroller pin bitmask",
        enabled_by_default=False,
    ),
    # =========================================================================
    # SMART CONTROL MODE SENSORS (source: internal_metrics)
    # Raw SmartControl mode values. The SmartControl select entity provides
    # a friendlier interface, but these show the raw numeric values.
    # NOTE: Previously these were in WRITABLE_SETTINGS and skipped from sensor
    # setup entirely. They now appear as new disabled diagnostic sensors.
    # =========================================================================
    QvantumEntityDef(
        "smart_sh_mode",
        "SmartControl space heating mode value (raw)",
        enabled_by_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    QvantumEntityDef(
        "smart_dhw_mode",
        "SmartControl DHW mode value (raw)",
        enabled_by_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # =========================================================================
    # READ-ONLY CONFIGURATION SENSORS (source: internal_metrics)
    # Settings that are read as internal metrics but displayed as sensors.
    # These use special sensor classes (enum, timestamp, text).
    # =========================================================================
    QvantumEntityDef(
        "btxconfig",
        "BTX sensor configuration (undefined/pool/SG Ready)",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="settings_enum",
    ),
    QvantumEntityDef(
        "bt4config",
        "BT4 sensor configuration (undefined/SG Ready)",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="settings_enum",
    ),
    QvantumEntityDef(
        "vacation_start",
        "Vacation mode start date/time",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="settings_timestamp",
    ),
    QvantumEntityDef(
        "vacation_stop",
        "Vacation mode end date/time",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="settings_timestamp",
    ),
    QvantumEntityDef(
        "wifi_ssid",
        "Connected WiFi network name",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="settings_text",
    ),
    # =========================================================================
    # DEVICE METADATA SENSORS (source: status)
    # Information from the device status endpoint (firmware, uptime).
    # =========================================================================
    QvantumEntityDef(
        "uptime",
        "Device uptime in hours",
        source=EntitySource.STATUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        api_key="uptime_hours",
        entity_type="metadata",
    ),
    QvantumEntityDef(
        "display_fw_version",
        "Display board firmware version",
        source=EntitySource.STATUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="metadata",
    ),
    QvantumEntityDef(
        "cc_fw_version",
        "Communication controller firmware version",
        source=EntitySource.STATUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="metadata",
    ),
    QvantumEntityDef(
        "inv_fw_version",
        "Inverter firmware version",
        source=EntitySource.STATUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="metadata",
    ),
    # =========================================================================
    # ALARM SENSORS (source: alarms)
    # Alarm monitoring from the device alarms endpoint.
    # =========================================================================
    QvantumEntityDef(
        "alarm_count",
        "Number of currently active alarms",
        source=EntitySource.ALARMS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="alarm_count",
    ),
    QvantumEntityDef(
        "active_alarms",
        "Active alarm summary with severity breakdown",
        source=EntitySource.ALARMS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="active_alarms",
    ),
    # =========================================================================
    # SERVICE & ACCESS SENSORS (source: status, access_level)
    # Service technician access monitoring.
    # =========================================================================
    QvantumEntityDef(
        "service_access_until",
        "Service access expiration timestamp",
        source=EntitySource.STATUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="service_access_until",
    ),
    QvantumEntityDef(
        "access_level",
        "Current API write access level (10=user, 20=service)",
        source=EntitySource.ACCESS_LEVEL,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="access_level",
    ),
    QvantumEntityDef(
        "access_expires_at",
        "Elevated access expiration timestamp",
        source=EntitySource.ACCESS_LEVEL,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="access_expires",
    ),
]

_LOGGER = logging.getLogger(__name__)

# =============================================================================
# Value maps for settings_enum sensor types, keyed by entity key.
# =============================================================================
_ENUM_VALUE_MAPS: dict[str, dict[int, str]] = {
    "btxconfig": BTX_CONFIG_MAP,
    "bt4config": BT4_CONFIG_MAP,
}


def _create_internal_metric(
    coordinator: QvantumDataUpdateCoordinator,
    device: dict[str, Any],
    entity_def: QvantumEntityDef,
) -> QvantumInternalMetricSensor:
    """Create a generic internal metric sensor."""
    return QvantumInternalMetricSensor(coordinator, device, entity_def)


def _create_settings_enum(
    coordinator: QvantumDataUpdateCoordinator,
    device: dict[str, Any],
    entity_def: QvantumEntityDef,
) -> QvantumSettingsEnumSensor:
    """Create a settings enum sensor (e.g., btxconfig, bt4config)."""
    value_map = _ENUM_VALUE_MAPS[entity_def.key]
    return QvantumSettingsEnumSensor(coordinator, device, entity_def.key, value_map)


def _create_settings_timestamp(
    coordinator: QvantumDataUpdateCoordinator,
    device: dict[str, Any],
    entity_def: QvantumEntityDef,
) -> QvantumSettingsTimestampSensor:
    """Create a settings timestamp sensor (e.g., vacation_start/stop)."""
    return QvantumSettingsTimestampSensor(coordinator, device, entity_def.key)


def _create_settings_text(
    coordinator: QvantumDataUpdateCoordinator,
    device: dict[str, Any],
    entity_def: QvantumEntityDef,
) -> QvantumSettingsTextSensor:
    """Create a settings text sensor (e.g., wifi_ssid)."""
    return QvantumSettingsTextSensor(coordinator, device, entity_def.key)


def _create_metadata(
    coordinator: QvantumDataUpdateCoordinator,
    device: dict[str, Any],
    entity_def: QvantumEntityDef,
) -> QvantumMetadataSensor:
    """Create a device metadata sensor (e.g., uptime, firmware versions)."""
    return QvantumMetadataSensor(
        coordinator, device, entity_def.api_key or entity_def.key, entity_def.key
    )


def _create_alarm_count(
    coordinator: QvantumDataUpdateCoordinator,
    device: dict[str, Any],
    _entity_def: QvantumEntityDef,
) -> QvantumAlarmCountSensor:
    """Create the alarm count sensor."""
    return QvantumAlarmCountSensor(coordinator, device)


def _create_active_alarms(
    coordinator: QvantumDataUpdateCoordinator,
    device: dict[str, Any],
    _entity_def: QvantumEntityDef,
) -> QvantumActiveAlarmsSensor:
    """Create the active alarms sensor."""
    return QvantumActiveAlarmsSensor(coordinator, device)


def _create_service_access_until(
    coordinator: QvantumDataUpdateCoordinator,
    device: dict[str, Any],
    _entity_def: QvantumEntityDef,
) -> QvantumServiceAccessUntilSensor:
    """Create the service access expiration sensor."""
    return QvantumServiceAccessUntilSensor(coordinator, device)


def _create_access_level(
    coordinator: QvantumDataUpdateCoordinator,
    device: dict[str, Any],
    _entity_def: QvantumEntityDef,
) -> QvantumAccessLevelSensor:
    """Create the access level sensor."""
    return QvantumAccessLevelSensor(coordinator, device)


def _create_access_expires(
    coordinator: QvantumDataUpdateCoordinator,
    device: dict[str, Any],
    _entity_def: QvantumEntityDef,
) -> QvantumAccessExpireSensor:
    """Create the access expiration sensor."""
    return QvantumAccessExpireSensor(coordinator, device)


def get_entity_def(key: str) -> QvantumEntityDef | None:
    """Look up an entity definition by key within this platform's entity definitions."""
    return next((e for e in ENTITY_DEFS if e.key == key), None)


# Factory registry: entity_type -> constructor callable.
# None means "use the default generic class" (QvantumInternalMetricSensor).
# To add a new sensor type: add a factory here and set entity_type in
# ENTITY_DEFS above. No other dispatch code needed.
_SENSOR_FACTORIES: dict[
    str | None,
    Callable[
        [QvantumDataUpdateCoordinator, dict[str, Any], QvantumEntityDef],
        SensorEntity,
    ],
] = {
    None: _create_internal_metric,
    "settings_enum": _create_settings_enum,
    "settings_timestamp": _create_settings_timestamp,
    "settings_text": _create_settings_text,
    "metadata": _create_metadata,
    "alarm_count": _create_alarm_count,
    "active_alarms": _create_active_alarms,
    "service_access_until": _create_service_access_until,
    "access_level": _create_access_level,
    "access_expires": _create_access_expires,
}


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qvantum sensor entities from a config entry.

    Iterates all sensor entity definitions and uses the factory registry
    to create the appropriate sensor class for each. Fast-polling metrics
    use a separate coordinator with 5-second updates.

    Args:
        hass: Home Assistant instance
        entry: Config entry for this integration instance
        async_add_entities: Callback to add entities to HA
    """
    data = entry.runtime_data
    coordinators = data["coordinators"]
    fast_coordinators = data["fast_coordinators"]
    devices = data["devices"]

    entities: list[SensorEntity] = []

    for device in devices:
        device_id = device["id"]
        coordinator = coordinators[device_id]
        fast_coordinator = fast_coordinators[device_id]

        for entity_def in ENTITY_DEFS:
            selected_coordinator = (
                fast_coordinator if entity_def.fast_polling else coordinator
            )
            factory = _SENSOR_FACTORIES[entity_def.entity_type]
            entities.append(factory(selected_coordinator, device, entity_def))

    async_add_entities(entities)


class QvantumSensorBase(QvantumEntity, SensorEntity):
    """Base class for Qvantum sensors."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        sensor_type: str,
        translation_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device, None)  # API not needed for sensors
        self._sensor_type = sensor_type
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{device['id']}_{sensor_type}"


class QvantumInternalMetricSensor(QvantumSensorBase):
    """Sensor for Qvantum internal metrics."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        entity_def: QvantumEntityDef,
    ) -> None:
        """Initialize the sensor from an entity definition."""
        super().__init__(
            coordinator, device, f"internal_{entity_def.key}", entity_def.key
        )
        self._metric_name = entity_def.key

        # Set enabled/disabled from entity definition
        if not entity_def.enabled_by_default:
            self._attr_entity_registry_enabled_default = False

        # Set entity category from entity definition
        self._attr_entity_category = entity_def.entity_category

        # Configure enum sensors (sensors with fixed state values)
        if entity_def.key == "hp_status":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(HP_STATUS_MAP.values())
        elif entity_def.key == "op_mode_sensor":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(OP_MODE_SENSOR_MAP.values())
        elif entity_def.key == "guide_he":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(GUIDE_HE_MAP.values())

        # Only set state_class for numeric sensors (those with a unit)
        unit = entity_def.unit
        if unit is not None:
            self._attr_state_class = SensorStateClass.MEASUREMENT

        # Set unit and device class based on unit string
        if unit == "°C":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        elif unit == "%":
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif unit == "bar":
            self._attr_device_class = SensorDeviceClass.PRESSURE
            self._attr_native_unit_of_measurement = UnitOfPressure.BAR
        elif unit == "Hz":
            self._attr_device_class = SensorDeviceClass.FREQUENCY
            self._attr_native_unit_of_measurement = UnitOfFrequency.HERTZ
        elif unit == "L/min":
            self._attr_native_unit_of_measurement = (
                UnitOfVolumeFlowRate.LITERS_PER_MINUTE
            )
        elif unit == "W":
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_native_unit_of_measurement = UnitOfPower.WATT
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "kW":
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "kWh":
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif unit == "A":
            self._attr_device_class = SensorDeviceClass.CURRENT
            self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit is not None:
            # Custom units (rpm, minutes, L) — keep MEASUREMENT state_class
            self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "internal_metrics" in self.coordinator.data:
            values = self.coordinator.data["internal_metrics"]
            raw_value = values.get(self._metric_name)

            # Map status values to human-readable strings
            if self._metric_name == "hp_status" and raw_value is not None:
                try:
                    return HP_STATUS_MAP.get(int(raw_value), raw_value)
                except (ValueError, TypeError):
                    return raw_value
            if self._metric_name == "op_mode_sensor" and raw_value is not None:
                try:
                    return OP_MODE_SENSOR_MAP.get(int(raw_value), raw_value)
                except (ValueError, TypeError):
                    return raw_value
            if self._metric_name == "guide_he" and raw_value is not None:
                try:
                    return GUIDE_HE_MAP.get(int(raw_value), raw_value)
                except (ValueError, TypeError):
                    return raw_value

            return raw_value
        return None


class QvantumMetadataSensor(QvantumSensorBase):
    """Sensor for device metadata."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        metadata_key: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device, f"metadata_{metadata_key}", name)
        self._metadata_key = metadata_key
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if (
            self.coordinator.data
            and "status" in self.coordinator.data
            and "device_metadata" in self.coordinator.data["status"]
        ):
            metadata = self.coordinator.data["status"]["device_metadata"]
            return metadata.get(self._metadata_key)
        return None


class QvantumServiceAccessUntilSensor(QvantumSensorBase):
    """Sensor for service access expiration time."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, device, "service_access_until", "service_access_until"
        )
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> datetime | None:
        """Return the state of the sensor."""
        if (
            self.coordinator.data
            and "status" in self.coordinator.data
            and "service_access" in self.coordinator.data["status"]
        ):
            service_access = self.coordinator.data["status"]["service_access"]
            until = service_access.get("until")
            if until:
                try:
                    # Parse ISO format timestamp to datetime
                    return datetime.fromisoformat(until)
                except (ValueError, AttributeError):
                    return None
        return None


class QvantumAlarmCountSensor(QvantumSensorBase):
    """Sensor for total alarm count."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device, "alarm_count", "alarm_count")
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_native_unit_of_measurement = "alarms"
        self._attr_state_class = None

    @property
    def native_value(self) -> int:
        """Return the number of active alarms."""
        if (
            self.coordinator.data
            and "alarms" in self.coordinator.data
            and "alarms" in self.coordinator.data["alarms"]
        ):
            alarms = self.coordinator.data["alarms"]["alarms"]
            active_alarms = [a for a in alarms if a.get("is_active", False)]
            return len(active_alarms)
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if (
            self.coordinator.data
            and "alarms" in self.coordinator.data
            and "alarms" in self.coordinator.data["alarms"]
        ):
            alarms = self.coordinator.data["alarms"]["alarms"]
            total = len(alarms)
            active = [a for a in alarms if a.get("is_active", False)]

            return {
                "total_alarms": total,
                "active_alarms": len(active),
                "acknowledged_alarms": len(
                    [a for a in alarms if a.get("is_acknowledged", False)]
                ),
            }
        return {}


class QvantumActiveAlarmsSensor(QvantumSensorBase):
    """Sensor for active alarm details."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device, "active_alarms", "active_alarms")
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return a summary of active alarms."""
        if (
            self.coordinator.data
            and "alarms" in self.coordinator.data
            and "alarms" in self.coordinator.data["alarms"]
        ):
            alarms = self.coordinator.data["alarms"]["alarms"]
            active_alarms = [a for a in alarms if a.get("is_active", False)]

            if not active_alarms:
                return "none"

            # Return summary of active alarms
            severities = {}
            for alarm in active_alarms:
                severity = alarm.get("severity", "UNKNOWN")
                severities[severity] = severities.get(severity, 0) + 1

            parts = [
                f"{severities[severity]} {severity}"
                for severity in ["CRITICAL", "SEVERE", "WARNING", "INFO"]
                if severity in severities
            ]

            return ", ".join(parts) if parts else f"{len(active_alarms)} active"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed alarm information."""
        if (
            self.coordinator.data
            and "alarms" in self.coordinator.data
            and "alarms" in self.coordinator.data["alarms"]
        ):
            alarms = self.coordinator.data["alarms"]["alarms"]
            active_alarms = [a for a in alarms if a.get("is_active", False)]

            attrs = {"alarm_list": []}

            for alarm in active_alarms:
                alarm_info = {
                    "code": alarm.get("code"),
                    "description": alarm.get("description"),
                    "severity": alarm.get("severity"),
                    "category": alarm.get("type"),
                    "triggered": alarm.get("triggered_timestamp"),
                    "acknowledged": alarm.get("is_acknowledged", False),
                }
                attrs["alarm_list"].append(alarm_info)

            return attrs
        return {}


class QvantumAccessLevelSensor(QvantumEntity, SensorEntity):
    """Sensor showing the current access level for the device."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the access level sensor."""
        super().__init__(coordinator, device, None)
        self._attr_translation_key = "access_level"
        self._attr_unique_id = f"{device['id']}_access_level"
        self._attr_icon = "mdi:security"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> int | None:
        """Return the current write access level."""
        if self.coordinator.data and "access_level" in self.coordinator.data:
            return self.coordinator.data["access_level"].get("writeAccessLevel")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional access level information."""
        if self.coordinator.data and "access_level" in self.coordinator.data:
            access_data = self.coordinator.data["access_level"]
            return {
                "read_access_level": access_data.get("readAccessLevel"),
                "has_service_access": access_data.get("writeAccessLevel", 0) >= 20,
            }
        return {}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "access_level" in self.coordinator.data
        )


class QvantumAccessExpireSensor(QvantumEntity, SensorEntity):
    """Sensor showing when the elevated access expires."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the access expiration sensor."""
        super().__init__(coordinator, device, None)
        self._attr_translation_key = "access_expires_at"
        self._attr_unique_id = f"{device['id']}_access_expires_at"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:clock-alert"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> datetime | None:
        """Return the access expiration timestamp."""
        if self.coordinator.data and "access_level" in self.coordinator.data:
            expires_at_str = self.coordinator.data["access_level"].get("expiresAt")
            if expires_at_str:
                try:
                    # Parse ISO format timestamp
                    return datetime.fromisoformat(expires_at_str)
                except (ValueError, AttributeError):
                    return None
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "access_level" in self.coordinator.data
            and self.coordinator.data["access_level"].get("expiresAt") is not None
        )


class QvantumSettingsEnumSensor(QvantumEntity, SensorEntity):
    """Read-only enum sensor that reads from internal_metrics (e.g. btxconfig, bt4config).

    Despite the "Settings" prefix these values are returned by the internal-metrics
    API endpoint, not the settings endpoint.
    """

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        setting_name: str,
        value_map: dict[int, str],
    ) -> None:
        """Initialize the settings enum sensor."""
        super().__init__(coordinator, device, None)
        self._setting_name = setting_name
        self._value_map = value_map
        self._attr_translation_key = setting_name
        self._attr_unique_id = f"{device['id']}_{setting_name}"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = list(value_map.values())
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        """Return the current value mapped to a human-readable string."""
        if self.coordinator.data and "internal_metrics" in self.coordinator.data:
            value = self.coordinator.data["internal_metrics"].get(self._setting_name)
            if value is not None:
                try:
                    return self._value_map.get(int(value))
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Could not convert %s value %s to int",
                        self._setting_name,
                        value,
                    )
        return None


class QvantumSettingsTimestampSensor(QvantumEntity, SensorEntity):
    """Read-only timestamp sensor that reads from internal_metrics (e.g. vacation_start/stop).

    Despite the "Settings" prefix these values are returned by the internal-metrics
    API endpoint, not the settings endpoint.
    """

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        setting_name: str,
    ) -> None:
        """Initialize the settings timestamp sensor."""
        super().__init__(coordinator, device, None)
        self._setting_name = setting_name
        self._attr_translation_key = setting_name
        self._attr_unique_id = f"{device['id']}_{setting_name}"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        """Return False when value is 0 or empty string (no date set)."""
        if self.coordinator.data and "internal_metrics" in self.coordinator.data:
            value = self.coordinator.data["internal_metrics"].get(self._setting_name)
            if value in {0, ""}:
                return False
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp value."""
        if self.coordinator.data and "internal_metrics" in self.coordinator.data:
            value = self.coordinator.data["internal_metrics"].get(self._setting_name)
            if value is not None and value not in {"", 0}:
                try:
                    if isinstance(value, (int, float)):
                        # API returns Unix epoch seconds
                        return datetime.fromtimestamp(value, tz=UTC)
                    return datetime.fromisoformat(str(value))
                except (ValueError, AttributeError, OSError):
                    _LOGGER.warning(
                        "Could not parse %s timestamp: %s",
                        self._setting_name,
                        value,
                    )
        return None


class QvantumSettingsTextSensor(QvantumEntity, SensorEntity):
    """Read-only text sensor that reads from internal_metrics (e.g. wifi_ssid).

    Despite the "Settings" prefix this value is returned by the internal-metrics
    API endpoint, not the settings endpoint.
    """

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        setting_name: str,
    ) -> None:
        """Initialize the settings text sensor."""
        super().__init__(coordinator, device, None)
        self._setting_name = setting_name
        self._attr_translation_key = setting_name
        self._attr_unique_id = f"{device['id']}_{setting_name}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        """Return the text value."""
        if self.coordinator.data and "internal_metrics" in self.coordinator.data:
            value = self.coordinator.data["internal_metrics"].get(self._setting_name)
            if value is not None:
                return str(value)
        return None
