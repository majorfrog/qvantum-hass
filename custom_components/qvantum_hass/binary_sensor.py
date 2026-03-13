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

from collections.abc import Callable
import logging
from typing import Any, Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import QvantumDataUpdateCoordinator
from .entity import QvantumEntity
from .models import EntitySource, QvantumEntityDef

PARALLEL_UPDATES = 0

# =============================================================================
# Entity definitions for this platform
#
# Each entity is declared once here. definitions.py imports these to
# build the full cross-platform collection used by the coordinator.
# =============================================================================

ENTITY_DEFS: Final[list[QvantumEntityDef]] = [
    # =========================================================================
    # BINARY SENSORS — INTERNAL METRICS (source: internal_metrics)
    # Boolean state indicators from the heat pump internal metrics.
    # =========================================================================
    QvantumEntityDef(
        "picpin_relay_heat_l1",
        "Additional electric heater relay phase L1",
    ),
    QvantumEntityDef(
        "picpin_relay_heat_l2",
        "Additional electric heater relay phase L2",
    ),
    QvantumEntityDef(
        "picpin_relay_heat_l3",
        "Additional electric heater relay phase L3",
    ),
    QvantumEntityDef(
        "picpin_relay_qm10",
        "Diverting valve DHW/heating (QM10 relay)",
    ),
    QvantumEntityDef(
        "enable_sc_dhw",
        "SmartControl DHW enabled state",
    ),
    QvantumEntityDef(
        "enable_sc_sh",
        "SmartControl space heating enabled state",
    ),
    QvantumEntityDef(
        "use_adaptive",
        "SmartControl (adaptive mode) enabled state",
    ),
    QvantumEntityDef(
        "cooling_enabled",
        "Cooling mode enabled state",
        enabled_by_default=False,
    ),
    # =========================================================================
    # DEMAND & RELEASE STATE SENSORS (source: internal_metrics)
    # Internal control flags showing what the heat pump is requested to do.
    # Technical/diagnostic — disabled by default.
    # =========================================================================
    QvantumEntityDef(
        "dhwdemand",
        "DHW (hot water) demand flag",
    ),
    QvantumEntityDef(
        "heatingdemand",
        "Space heating demand flag",
    ),
    QvantumEntityDef(
        "heatingreleased",
        "Heating released (compressor allowed to heat)",
    ),
    QvantumEntityDef(
        "additionreleased",
        "Additional heater released (allowed to run)",
    ),
    QvantumEntityDef(
        "coolingdemand",
        "Cooling demand flag",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "coolingreleased",
        "Cooling released (compressor allowed to cool)",
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "compressorreleased",
        "Compressor released (allowed to run)",
        enabled_by_default=True,
    ),
    # =========================================================================
    # BINARY SENSORS — SPECIAL (source: status, alarms)
    # Status indicators from other API endpoints.
    # =========================================================================
    QvantumEntityDef(
        "connectivity",
        "Device cloud connectivity status",
        source=EntitySource.STATUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="connectivity",
    ),
    QvantumEntityDef(
        "alarm_state",
        "Active alarm indicator (problem detected)",
        source=EntitySource.ALARMS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="alarm_state",
    ),
    QvantumEntityDef(
        "service_access",
        "Service technician access enabled",
        source=EntitySource.STATUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_type="service_access",
    ),
]

_LOGGER = logging.getLogger(__name__)


# Factory registry: entity_type -> constructor callable.
# None means "use the default generic class" (QvantumInternalBinarySensor).
# To add a new binary sensor type: add a factory here and set entity_type
# in the entity definition in const.py.
_BINARY_SENSOR_FACTORIES: dict[
    str | None,
    Callable[
        [QvantumDataUpdateCoordinator, dict[str, Any], QvantumEntityDef],
        BinarySensorEntity,
    ],
] = {
    None: lambda c, d, e: QvantumInternalBinarySensor(c, d, e),  # pylint: disable=unnecessary-lambda
    "connectivity": lambda c, d, e: QvantumConnectivitySensor(c, d),
    "alarm_state": lambda c, d, e: QvantumAlarmStateSensor(c, d),
    "service_access": lambda c, d, e: QvantumServiceAccessSensor(c, d),
}


def get_entity_def(key: str) -> QvantumEntityDef | None:
    """Look up an entity definition by key within this platform's entity definitions."""
    return next((e for e in ENTITY_DEFS if e.key == key), None)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qvantum binary sensor entities.

    Iterates all binary_sensor entity definitions and uses the factory
    registry to create the appropriate class for each.
    """
    data = entry.runtime_data
    coordinators = data["coordinators"]
    devices = data["devices"]

    entities: list[BinarySensorEntity] = []

    for device in devices:
        device_id = device["id"]
        coordinator = coordinators[device_id]

        for entity_def in ENTITY_DEFS:
            factory = _BINARY_SENSOR_FACTORIES[entity_def.entity_type]
            entities.append(factory(coordinator, device, entity_def))

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
        self._attr_unique_id = f"{device['id']}_{sensor_type}"


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
        entity_def: QvantumEntityDef,
    ) -> None:
        """Initialize the binary sensor from an entity definition."""
        # Map metric names to more user-friendly translation keys where needed
        translation_key_map = {
            "picpin_relay_heat_l1": "additional_power_l1",
            "picpin_relay_heat_l2": "additional_power_l2",
            "picpin_relay_heat_l3": "additional_power_l3",
            "picpin_relay_qm10": "diverting_valve",
        }
        translation_key = translation_key_map.get(entity_def.key, entity_def.key)
        super().__init__(
            coordinator, device, f"internal_{entity_def.key}", translation_key
        )
        self._metric_name = entity_def.key

        if not entity_def.enabled_by_default:
            self._attr_entity_registry_enabled_default = False

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if self.coordinator.data and "internal_metrics" in self.coordinator.data:
            values = self.coordinator.data["internal_metrics"]
            value = values.get(self._metric_name)
            # Convert various representations to boolean
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                return value.lower() in ("1", "true", "on", "yes")
        return False
