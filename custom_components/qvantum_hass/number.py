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
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import QvantumDataUpdateCoordinator
from .api import QvantumApiError
from .const import (
    COMMONLY_USED_NUMBER_SETTINGS,
    DOMAIN,
    SKIP_NUMBER_SETTINGS,
)
from .entity import QvantumEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qvantum number entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    devices = data["devices"]

    entities = []

    for device in devices:
        device_id = device["id"]
        coordinator = coordinators[device_id]

        # Add number entities for numeric settings
        if coordinator.data and "settings_inventory" in coordinator.data:
            settings_inventory = coordinator.data["settings_inventory"]
            if settings_inventory and "settings" in settings_inventory:
                # Get list of settings that are actually returned by the API
                available_setting_names = QvantumEntity.get_available_setting_names(
                    coordinator.data
                )

                for setting in settings_inventory["settings"]:
                    # Skip settings that are handled as select entities
                    if setting.get("name") in SKIP_NUMBER_SETTINGS:
                        continue

                    # Only create entities for settings that are actually available in API response
                    if setting.get("name") not in available_setting_names:
                        _LOGGER.debug(
                            "Skipping number entity for %s - not available in settings response",
                            setting.get("name"),
                        )
                        continue

                    if setting.get("data_type") == "number" and not setting.get(
                        "read_only", False
                    ):
                        entities.append(
                            QvantumNumberEntity(
                                coordinator,
                                device,
                                setting,
                            )
                        )

    async_add_entities(entities)


class QvantumNumberEntity(QvantumEntity, NumberEntity):
    """Number entity for Qvantum settings."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        setting: dict[str, Any],
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, device, None)
        self._setting = setting
        self._setting_name = setting["name"]
        self._attr_name = setting.get("display_name", setting["name"])
        self._attr_unique_id = f"qvantum_{device['id']}_{self._setting_name}"
        self._attr_entity_category = EntityCategory.CONFIG
        self._optimistic_value: float | None = None  # Store optimistic value

        # Commonly-used settings enabled by default, advanced settings disabled
        # Note: tap_water_start/stop are disabled because they're managed
        # automatically by select.tap_water_capacity_target
        # Note: room_comp_factor is now a select entity
        self._attr_entity_registry_enabled_default = (
            self._setting_name in COMMONLY_USED_NUMBER_SETTINGS
        )

        # Set min, max, and step based on setting name
        self._attr_native_min_value = self._get_min()
        self._attr_native_max_value = self._get_max()
        self._attr_native_step = self._get_step()

        # Get unit from metrics inventory
        if coordinator.data and "metrics_inventory" in coordinator.data:
            metrics_inventory = coordinator.data["metrics_inventory"]
            if metrics_inventory and "metrics" in metrics_inventory:
                for metric in metrics_inventory["metrics"]:
                    if metric["name"] == self._setting_name:
                        self._attr_native_unit_of_measurement = metric.get("unit")
                        break

    def _get_min(self) -> float:
        """Get minimum value for setting."""
        name = self._setting_name
        if name == "tap_water_capacity_target":
            return 0
        if name == "tap_water_start":
            return 40
        if name == "tap_water_stop":
            return 40
        if name == "indoor_temperature_target":
            return 15
        return 0

    def _get_max(self) -> float:
        """Get maximum value for setting."""
        name = self._setting_name
        if name == "tap_water_capacity_target":
            return 5
        if name == "tap_water_start":
            return 70
        if name == "tap_water_stop":
            return 99
        if name == "indoor_temperature_target":
            return 25
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
            await self.hass.async_add_executor_job(
                self.coordinator.api.set_setting,
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
