"""Binary sensor platform for Qvantum Heat Pump integration.

This module provides binary sensor entities for monitoring Qvantum heat pump
status indicators and binary states. It includes:
- Device connectivity status
- Alarm state indicators
- Service access status
- Relay states (heating, valves)
- SmartControl status indicators

All binary sensors properly reflect device availability and provide
additional attributes for detailed information.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import QvantumDataUpdateCoordinator
from .const import DOMAIN, METRIC_INFO
from .entity import QvantumEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qvantum binary sensor entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    devices = data["devices"]

    entities = []

    for device in devices:
        device_id = device["id"]
        coordinator = coordinators[device_id]

        # Add connectivity sensor
        entities.append(QvantumConnectivitySensor(coordinator, device))

        # Add alarm state sensor
        entities.append(QvantumAlarmStateSensor(coordinator, device))

        # Add service access sensor
        entities.append(QvantumServiceAccessSensor(coordinator, device))

        # Add internal metrics binary sensors
        for metric_name, _unit, entity_type in METRIC_INFO:
            if entity_type == "binary_sensor":
                entities.append(
                    QvantumInternalBinarySensor(
                        coordinator,
                        device,
                        metric_name,
                    )
                )

    async_add_entities(entities)


class QvantumBinarySensorBase(QvantumEntity, BinarySensorEntity):
    """Base class for Qvantum binary sensors."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        sensor_type: str,
        translation_key: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device, None)
        self._sensor_type = sensor_type
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"qvantum_{device['id']}_{sensor_type}"


class QvantumConnectivitySensor(QvantumBinarySensorBase):
    """Binary sensor for device connectivity."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device, "connectivity", "connectivity")
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return true if the device is connected."""
        if (
            self.coordinator.data
            and "status" in self.coordinator.data
            and "connectivity" in self.coordinator.data["status"]
        ):
            connectivity = self.coordinator.data["status"]["connectivity"]
            return connectivity.get("connected", False)
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if (
            self.coordinator.data
            and "status" in self.coordinator.data
            and "connectivity" in self.coordinator.data["status"]
        ):
            connectivity = self.coordinator.data["status"]["connectivity"]
            return {
                "timestamp": connectivity.get("timestamp"),
                "disconnect_reason": connectivity.get("disconnect_reason"),
            }
        return {}


class QvantumServiceAccessSensor(QvantumBinarySensorBase):
    """Binary sensor for service access state."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device, "service_access", "service_access")
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return true if service access is enabled."""
        if (
            self.coordinator.data
            and "status" in self.coordinator.data
            and "service_access" in self.coordinator.data["status"]
        ):
            service_access = self.coordinator.data["status"]["service_access"]
            return service_access.get("enabled", False)
        return False


class QvantumAlarmStateSensor(QvantumBinarySensorBase):
    """Binary sensor for alarm state (has active alarms)."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device, "alarm_state", "alarm_state")
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return true if there are active alarms."""
        if (
            self.coordinator.data
            and "alarms" in self.coordinator.data
            and "alarms" in self.coordinator.data["alarms"]
        ):
            alarms = self.coordinator.data["alarms"]["alarms"]
            # Check for any active alarms
            active_alarms = [a for a in alarms if a.get("is_active", False)]
            return len(active_alarms) > 0
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if (
            self.coordinator.data
            and "alarms" in self.coordinator.data
            and "alarms" in self.coordinator.data["alarms"]
        ):
            alarms = self.coordinator.data["alarms"]["alarms"]
            active_alarms = [a for a in alarms if a.get("is_active", False)]

            # Get most severe active alarm
            severity_order = {"INFO": 0, "WARNING": 1, "SEVERE": 2, "CRITICAL": 3}
            most_severe = None
            max_severity = -1

            for alarm in active_alarms:
                severity = alarm.get("severity", "INFO")
                severity_val = severity_order.get(severity, 0)
                if severity_val > max_severity:
                    max_severity = severity_val
                    most_severe = alarm

            attrs: dict[str, Any] = {
                "active_alarm_count": len(active_alarms),
                "total_alarm_count": len(alarms),
            }

            if most_severe:
                attrs.update(
                    {
                        "most_severe_code": most_severe.get("code"),
                        "most_severe_description": most_severe.get("description"),
                        "most_severe_severity": most_severe.get("severity"),
                        "most_severe_category": most_severe.get("type"),
                        "most_severe_triggered": most_severe.get("triggered_timestamp"),
                    }
                )

            # Add list of active alarm codes
            if active_alarms:
                attrs["active_alarm_codes"] = [a.get("code") for a in active_alarms]

            return attrs
        return {}


class QvantumInternalBinarySensor(QvantumBinarySensorBase):
    """Binary sensor for internal metrics."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        metric_name: str,
    ) -> None:
        """Initialize the sensor."""
        # Map metric names to more user-friendly translation keys where needed
        translation_key_map = {
            "picpin_relay_heat_l1": "additional_power_l1",
            "picpin_relay_heat_l2": "additional_power_l2",
            "picpin_relay_heat_l3": "additional_power_l3",
            "picpin_relay_qm10": "diverting_valve",
        }
        translation_key = translation_key_map.get(metric_name, metric_name)
        super().__init__(
            coordinator, device, f"internal_{metric_name}", translation_key
        )
        self._metric_name = metric_name

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if (
            self.coordinator.data
            and "internal_metrics" in self.coordinator.data
            and "values" in self.coordinator.data["internal_metrics"]
        ):
            values = self.coordinator.data["internal_metrics"]["values"]
            value = values.get(self._metric_name)
            # Convert various representations to boolean
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                return value.lower() in ("1", "true", "on", "yes")
        return False
