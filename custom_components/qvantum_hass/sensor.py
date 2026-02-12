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

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import QvantumDataUpdateCoordinator
from .const import (
    BT4_CONFIG_MAP,
    BTX_CONFIG_MAP,
    DISABLED_BY_DEFAULT_SENSORS,
    DOMAIN,
    FAST_POLLING_METRICS,
    GUIDE_HE_MAP,
    HP_STATUS_MAP,
    METRIC_INFO,
    OP_MODE_MAP,
    OP_MODE_SENSOR_MAP,
    WRITABLE_SETTINGS,
)
from .entity import QvantumEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qvantum sensor entities from a config entry.

    Creates sensor entities for all available metrics from the device,
    excluding those that are writable settings (handled by other platforms).
    Sensors are automatically categorized and some are disabled by default.

    Fast-polling metrics (power/current) use a separate coordinator with
    5-second updates, while other sensors use normal 30-second updates.

    Args:
        hass: Home Assistant instance
        entry: Config entry for this integration instance
        async_add_entities: Callback to add entities to HA
    """
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    fast_coordinators = data["fast_coordinators"]
    devices = data["devices"]

    entities = []

    for device in devices:
        device_id = device["id"]
        coordinator = coordinators[device_id]
        fast_coordinator = fast_coordinators[device_id]

        # Keep track of which metrics we've added to avoid duplicates
        added_metrics = set()

        # Add metrics sensors from inventory (standard public API metrics)
        if coordinator.data and "metrics_inventory" in coordinator.data:
            metrics_inventory = coordinator.data["metrics_inventory"]
            if metrics_inventory and "metrics" in metrics_inventory:
                # ALL public API metrics should be skipped - internal metrics are more comprehensive
                # and have better naming. Public API metrics often have very long auto-generated
                # descriptions as names.
                _LOGGER.debug(
                    "Skipping ALL public API metrics - using internal metrics only for device %s",
                    device_id,
                )

        # Add internal metrics sensors (skip if already added from public API)
        # Map internal metric names to their public API equivalents
        internal_to_public_map = {
            "bt1": "outdoor_temperature",
            "bt2": "indoor_temperature",
        }

        for metric_name, unit, entity_type in METRIC_INFO:
            if entity_type == "sensor":
                # Skip if this internal metric has a public API equivalent that was already added
                public_equivalent = internal_to_public_map.get(metric_name)
                if public_equivalent and public_equivalent in added_metrics:
                    continue

                # Skip if this metric is actually a writable setting handled by another platform
                if metric_name in WRITABLE_SETTINGS:
                    continue

                # Use fast coordinator for power/current metrics, normal coordinator for others
                selected_coordinator = (
                    fast_coordinator
                    if metric_name in FAST_POLLING_METRICS
                    else coordinator
                )

                entities.append(
                    QvantumInternalMetricSensor(
                        selected_coordinator,
                        device,
                        metric_name,
                        unit,
                    )
                )

        # Add device metadata sensors
        entities.extend(
            [
                QvantumMetadataSensor(coordinator, device, "uptime_hours", "uptime"),
                QvantumMetadataSensor(
                    coordinator,
                    device,
                    "display_fw_version",
                    "display_fw_version",
                ),
                QvantumMetadataSensor(
                    coordinator, device, "cc_fw_version", "cc_fw_version"
                ),
                QvantumMetadataSensor(
                    coordinator, device, "inv_fw_version", "inv_fw_version"
                ),
            ]
        )

        # Add alarm sensors
        entities.extend(
            [
                QvantumAlarmCountSensor(coordinator, device),
                QvantumActiveAlarmsSensor(coordinator, device),
            ]
        )

        # Add service access sensor
        entities.append(QvantumServiceAccessUntilSensor(coordinator, device))

        # Add access level sensors
        entities.extend(
            [
                QvantumAccessLevelSensor(coordinator, device),
                QvantumAccessExpireSensor(coordinator, device),
            ]
        )

        # Add settings-based read-only sensors
        entities.extend(
            [
                QvantumSettingsEnumSensor(
                    coordinator, device, "btxconfig", BTX_CONFIG_MAP
                ),
                QvantumSettingsEnumSensor(
                    coordinator, device, "bt4config", BT4_CONFIG_MAP
                ),
                QvantumSettingsTimestampSensor(coordinator, device, "vacation_start"),
                QvantumSettingsTimestampSensor(coordinator, device, "vacation_stop"),
                QvantumSettingsTextSensor(coordinator, device, "wifi_ssid"),
            ]
        )

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
        self._attr_unique_id = f"qvantum_{device['id']}_{sensor_type}"


class QvantumInternalMetricSensor(QvantumSensorBase):
    """Sensor for Qvantum internal metrics."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        metric_name: str,
        unit: str,
    ) -> None:
        """Initialize the sensor."""
        # Use metric_name as translation_key
        super().__init__(coordinator, device, f"internal_{metric_name}", metric_name)
        self._metric_name = metric_name

        # Disable technical sensors by default (list from const.py)
        if metric_name in DISABLED_BY_DEFAULT_SENSORS:
            self._attr_entity_registry_enabled_default = False

        # Configure enum sensors (sensors with fixed state values)
        if metric_name == "hp_status":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(HP_STATUS_MAP.values())
        elif metric_name == "op_mode":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(OP_MODE_MAP.values())
        elif metric_name == "op_mode_sensor":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(OP_MODE_SENSOR_MAP.values())
        elif metric_name == "guide_he":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(GUIDE_HE_MAP.values())
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        # Only set state_class for numeric sensors (those with a unit)
        # Non-numeric sensors (like price_region with unit=None) should not have state_class
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
        elif unit == "kWh":
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif unit == "A":
            self._attr_device_class = SensorDeviceClass.CURRENT
            self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit is not None:
            # For other units (like "int", "minutes", "RPM", "L"), set the unit but keep MEASUREMENT state_class
            self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data and "internal_metrics" in self.coordinator.data:
            values = self.coordinator.data["internal_metrics"]
            raw_value = values.get(self._metric_name)

            # Map status values to human-readable strings
            if self._metric_name == "hp_status" and raw_value is not None:
                return HP_STATUS_MAP.get(int(raw_value), raw_value)
            elif self._metric_name == "op_mode" and raw_value is not None:
                return OP_MODE_MAP.get(int(raw_value), raw_value)
            elif self._metric_name == "op_mode_sensor" and raw_value is not None:
                return OP_MODE_SENSOR_MAP.get(int(raw_value), raw_value)
            elif self._metric_name == "guide_he" and raw_value is not None:
                return GUIDE_HE_MAP.get(int(raw_value), raw_value)

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
    def native_value(self):
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
    def native_value(self):
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
                    return datetime.fromisoformat(until.replace("Z", "+00:00"))
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
    def native_value(self):
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
    def native_value(self):
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

            parts = []
            for severity in ["CRITICAL", "SEVERE", "WARNING", "INFO"]:
                if severity in severities:
                    parts.append(f"{severities[severity]} {severity}")

            return ", ".join(parts) if parts else f"{len(active_alarms)} active"
        return "Unknown"

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
        self._attr_unique_id = f"qvantum_{device['id']}_access_level"
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
        self._attr_unique_id = f"qvantum_{device['id']}_access_expires_at"
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
                    return datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
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
    """Read-only enum sensor for settings like btxconfig, bt4config."""

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
        self._attr_unique_id = f"qvantum_{device['id']}_{setting_name}"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = list(value_map.values())
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        """Return the current value mapped to a human-readable string."""
        if (
            self.coordinator.data
            and "settings" in self.coordinator.data
            and "settings" in self.coordinator.data["settings"]
        ):
            for setting in self.coordinator.data["settings"]["settings"]:
                if setting["name"] == self._setting_name:
                    value = setting.get("value")
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
    """Read-only timestamp sensor for settings like vacation_start/stop."""

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
        self._attr_unique_id = f"qvantum_{device['id']}_{setting_name}"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp value."""
        if (
            self.coordinator.data
            and "settings" in self.coordinator.data
            and "settings" in self.coordinator.data["settings"]
        ):
            for setting in self.coordinator.data["settings"]["settings"]:
                if setting["name"] == self._setting_name:
                    value = setting.get("value")
                    if value is not None and value != "":
                        try:
                            return datetime.fromisoformat(
                                str(value).replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            _LOGGER.debug(
                                "Could not parse %s timestamp: %s",
                                self._setting_name,
                                value,
                            )
        return None


class QvantumSettingsTextSensor(QvantumEntity, SensorEntity):
    """Read-only text sensor for settings like wifi_ssid."""

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
        self._attr_unique_id = f"qvantum_{device['id']}_{setting_name}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        """Return the text value."""
        if (
            self.coordinator.data
            and "settings" in self.coordinator.data
            and "settings" in self.coordinator.data["settings"]
        ):
            for setting in self.coordinator.data["settings"]["settings"]:
                if setting["name"] == self._setting_name:
                    value = setting.get("value")
                    if value is not None:
                        return str(value)
        return None
