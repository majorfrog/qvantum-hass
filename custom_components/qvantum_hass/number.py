"""Number platform for Qvantum Heat Pump integration.

This module provides number entities for adjusting numeric settings:
- Indoor temperature target
- DHW (Domestic Hot Water) start/stop temperatures
- DHW capacity targets
- Other numeric configuration parameters

Number entities include proper min/max ranges and step values for
safe operation within manufacturer specifications.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import QvantumApiError
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
    # NUMBER ENTITIES (source: settings)
    # Numeric writable settings with min/max/step constraints.
    # =========================================================================
    QvantumEntityDef(
        "tap_water_start",
        "DHW start temperature (tank heating begins)",
        source=EntitySource.SETTINGS,
        unit="°C",
        entity_category=EntityCategory.CONFIG,
        enabled_by_default=False,
    ),
    QvantumEntityDef(
        "tap_water_stop",
        "DHW stop temperature (tank heating stops)",
        source=EntitySource.SETTINGS,
        unit="°C",
        entity_category=EntityCategory.CONFIG,
        enabled_by_default=False,
    ),
]

_LOGGER = logging.getLogger(__name__)


def get_entity_def(key: str) -> QvantumEntityDef | None:
    """Look up an entity definition by key within this platform's entity definitions."""
    return next((e for e in ENTITY_DEFS if e.key == key), None)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qvantum number entities."""
    data = entry.runtime_data
    coordinators = data["coordinators"]
    devices = data["devices"]

    entities = []

    for device in devices:
        device_id = device["id"]
        coordinator = coordinators[device_id]

        # Add number entities from entity definitions
        # (replaces dynamic creation from settings_inventory)
        entities.extend(
            QvantumNumberEntity(
                coordinator,
                device,
                entity_def,
            )
            for entity_def in ENTITY_DEFS
        )

    async_add_entities(entities)


class QvantumNumberEntity(QvantumEntity, NumberEntity):  # pylint: disable=abstract-method
    """Number entity for Qvantum settings."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        entity_def: QvantumEntityDef,
    ) -> None:
        """Initialize the number entity from an entity definition."""
        super().__init__(coordinator, device, None)
        self._setting_name = entity_def.api_key or entity_def.key
        self._attr_translation_key = entity_def.key
        self._attr_unique_id = f"{device['id']}_{entity_def.key}"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_entity_registry_enabled_default = entity_def.enabled_by_default
        self._optimistic_value: float | None = None

        # Set unit from entity definition
        if entity_def.unit == "°C":
            self._attr_native_unit_of_measurement = "°C"
        elif entity_def.unit:
            self._attr_native_unit_of_measurement = entity_def.unit

        # Set min, max, and step based on setting name
        self._attr_native_min_value = self._get_min()
        self._attr_native_max_value = self._get_max()
        self._attr_native_step = self._get_step()

    def _get_min(self) -> float:
        """Get minimum value for setting."""
        name = self._setting_name
        if name == "tap_water_start":
            return 40
        if name == "tap_water_stop":
            return 40
        return 0

    def _get_max(self) -> float:
        """Get maximum value for setting."""
        name = self._setting_name
        if name == "tap_water_start":
            return 70
        if name == "tap_water_stop":
            return 99
        return 100

    def _get_step(self) -> float:
        """Get step value for setting."""
        return 1

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        # Get actual value from coordinator
        actual_value = None
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
                            actual_value = float(value)
                        except (ValueError, TypeError):
                            _LOGGER.warning(
                                "Could not convert value %s to float for %s",
                                value,
                                self._setting_name,
                            )
                    else:
                        _LOGGER.debug(
                            "Setting %s found but value is None (may require higher access)",
                            self._setting_name,
                        )
                    break
            else:
                # Setting not found in response
                _LOGGER.debug(
                    "Setting %s not found in settings response (total settings: %d, access level: %s)",
                    self._setting_name,
                    len(self.coordinator.data["settings"]["settings"]),
                    self.coordinator.data.get("access_level", {}).get(
                        "writeAccessLevel", "unknown"
                    ),
                )

        # If we have an optimistic value set
        if self._optimistic_value is not None:
            # Clear optimistic value if actual value matches what we set
            if (
                actual_value is not None
                and abs(actual_value - self._optimistic_value) < 0.01
            ):
                self._optimistic_value = None
                return actual_value
            # Otherwise return optimistic value
            return self._optimistic_value

        return actual_value

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        # Set optimistic value immediately
        self._optimistic_value = value
        self.async_write_ha_state()

        try:
            await self.coordinator.api.set_setting(
                self._device["id"],
                self._setting_name,
                int(value),  # Convert to int for API
            )
            # Request immediate update to fetch the new value
            await self.coordinator.async_request_refresh()
            # The optimistic value will be cleared in native_value property
            # when the actual value matches
        except QvantumApiError as err:
            # Clear optimistic value on error to revert to actual state
            self._optimistic_value = None
            self.async_write_ha_state()
            _LOGGER.error(
                "Failed to set %s to %s: %s",
                self._setting_name,
                value,
                err,
            )
            raise HomeAssistantError(
                translation_domain="qvantum_hass",
                translation_key="set_value_failed",
            ) from err
