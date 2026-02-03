"""Select platform for Qvantum Heat Pump integration.

This module provides select entities for choosing from predefined options:
- Indoor temperature target (15-25°C)
- SmartControl mode (Off, Eco, Balanced, Comfort)
- Operation mode (Auto, Manual, Additional Heat Only)
- DHW priority time selection
- DHW outlet temperature selection
- Tap water capacity targets
- Room compensation factor
- Heating curve shift (indoor temperature offset, -9 to +9)
- Sensor mode (which temperature sensor controls heat pump)

Select entities provide user-friendly named options instead of numeric
values, making configuration more intuitive.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import QvantumDataUpdateCoordinator
from .api import QvantumApi, QvantumApiError
from .const import (
    COMMONLY_USED_SELECT_SETTINGS,
    CURVE_SHIFT_MAP,
    DOMAIN,
    HOT_WATER_PRIORITY_MAP,
    HOT_WATER_TEMP_MAP,
    INDOOR_TEMP_TARGET_MAP,
    OP_MODE_MAP,
    ROOM_COMP_MAP,
    SENSOR_MODE_OPTIONS,
)
from .entity import QvantumEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qvantum select entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    devices = data["devices"]
    api = data["api"]

    entities = []

    for device in devices:
        device_id = device["id"]
        coordinator = coordinators[device_id]

        # Add Indoor Temperature Target select entity
        entities.append(
            QvantumIndoorTempTargetSelect(
                coordinator,
                device,
                api,
            )
        )

        # Add SmartControl select entity
        entities.append(
            QvantumSmartControlSelect(
                coordinator,
                device,
                api,
            )
        )

        # Add tap water capacity target select entity
        entities.append(
            QvantumTapWaterCapacitySelect(
                coordinator,
                device,
                api,
            )
        )

        # Add DHW Priority select entity
        entities.append(
            QvantumDHWPrioritySelect(
                coordinator,
                device,
                api,
            )
        )

        # Add DHW Out Temp select entity
        entities.append(
            QvantumDHWOutTempSelect(
                coordinator,
                device,
                api,
            )
        )

        # Add DHW Mode select entity
        entities.append(
            QvantumDHWModeSelect(
                coordinator,
                device,
                api,
            )
        )

        # Add Operation Mode select entity
        entities.append(
            QvantumOperationModeSelect(
                coordinator,
                device,
                api,
            )
        )

        # Add Room Compensation Factor select entity
        entities.append(
            QvantumRoomCompFactorSelect(
                coordinator,
                device,
                api,
            )
        )

        # Add Heating Curve Shift select entity
        entities.append(
            QvantumCurveShiftSelect(
                coordinator,
                device,
                api,
            )
        )

        # Add Sensor Mode select entity
        entities.append(
            QvantumSensorModeSelect(
                coordinator,
                device,
                api,
            )
        )

    async_add_entities(entities)


class QvantumIndoorTempTargetSelect(QvantumEntity, SelectEntity):
    """Select entity for Indoor Temperature Target."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: QvantumApi,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device, api)
        self._attr_translation_key = "indoor_temperature_target"
        self._attr_unique_id = f"qvantum_{device['id']}_indoor_temp_target"
        self._attr_icon = "mdi:home-thermometer"
        self._attr_entity_category = EntityCategory.CONFIG
        # Check if this should be enabled by default
        self._attr_entity_registry_enabled_default = (
            "indoor_temperature_target" in COMMONLY_USED_SELECT_SETTINGS
        )
        self._attr_options = list(INDOOR_TEMP_TARGET_MAP.values())

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if (
            self.coordinator.data
            and "settings" in self.coordinator.data
            and "settings" in self.coordinator.data["settings"]
        ):
            for setting in self.coordinator.data["settings"]["settings"]:
                if setting["name"] == "indoor_temperature_target":
                    value = setting.get("value")
                    if value is not None:
                        try:
                            # Convert value to int for comparison
                            int_value = int(value)
                            return INDOOR_TEMP_TARGET_MAP.get(int_value)
                        except (ValueError, TypeError):
                            _LOGGER.warning(
                                "Could not convert indoor_temperature_target value %s to int",
                                value,
                            )
        return None

    async def async_select_option(self, option: str) -> None:
        """Set the indoor temperature target."""
        # Find the numeric value for the selected option
        value = None
        for val, label in INDOOR_TEMP_TARGET_MAP.items():
            if label == option:
                value = val
                break

        if value is None:
            _LOGGER.error("Invalid indoor temperature target option: %s", option)
            return

        try:
            await self.hass.async_add_executor_job(
                self._api.set_setting,
                self._device["id"],
                "indoor_temperature_target",
                value,
            )
            _LOGGER.info(
                "Set indoor temperature target to %s (%s) on device %s",
                option,
                value,
                self._device["id"],
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to set indoor temperature target: %s",
                err,
            )


class QvantumSmartControlSelect(QvantumEntity, SelectEntity):
    """Select entity for SmartControl mode."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: Any,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device, api)
        self._attr_translation_key = "smartcontrol"
        self._attr_unique_id = f"qvantum_{device['id']}_smartcontrol"
        self._attr_icon = "mdi:leaf"
        self._attr_options = ["off", "eco", "balanced", "comfort"]
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_entity_registry_enabled_default = (
            "smart_control_mode" in COMMONLY_USED_SELECT_SETTINGS
        )

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if not self.coordinator.data:
            return None

        # Get values from internal_metrics (preferred) or settings
        use_adaptive = None
        smart_sh_mode = None

        # Check internal_metrics first
        internal_metrics = self.coordinator.data.get("internal_metrics", {})
        if internal_metrics:
            use_adaptive = internal_metrics.get("use_adaptive")
            smart_sh_mode = internal_metrics.get("smart_sh_mode")

        # Fall back to settings if not found
        if use_adaptive is None or smart_sh_mode is None:
            settings = self.coordinator.data.get("settings", {}).get("settings", [])
            for setting in settings:
                name = setting.get("name")
                if name == "use_adaptive" and use_adaptive is None:
                    use_adaptive = setting.get("value")
                elif name == "smart_sh_mode" and smart_sh_mode is None:
                    smart_sh_mode = setting.get("value")

        # Convert use_adaptive to boolean
        if isinstance(use_adaptive, str):
            use_adaptive = use_adaptive.lower() in ("on", "true", "1", "yes")
        elif isinstance(use_adaptive, (int, float)):
            use_adaptive = bool(use_adaptive)

        # If SmartControl is disabled, return Off
        if use_adaptive is False:
            return "off"

        # Map mode value to option (same as async_select_option)
        mode_map = {-1: "off", 0: "eco", 1: "balanced", 2: "comfort"}

        try:
            mode_value = int(smart_sh_mode) if smart_sh_mode is not None else -1
            return mode_map.get(mode_value, "off")
        except (ValueError, TypeError):
            _LOGGER.debug(
                "Invalid smart_sh_mode value %s for device %s, defaulting to off",
                smart_sh_mode,
                self._device["id"],
            )
            return "off"

    async def async_select_option(self, option: str) -> None:
        """Update the current value."""
        # Map option to smart control modes
        mode_map = {
            "off": -1,
            "eco": 0,
            "balanced": 1,
            "comfort": 2,
        }

        mode_value = mode_map.get(option, -1)
        sh_mode = mode_value
        dhw_mode = mode_value

        try:
            await self.hass.async_add_executor_job(
                self._api.set_smartcontrol,
                self._device["id"],
                sh_mode,
                dhw_mode,
            )
            _LOGGER.info(
                "Set SmartControl to %s on device %s",
                option,
                self._device["id"],
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to set SmartControl: %s",
                err,
            )


class QvantumTapWaterCapacitySelect(QvantumEntity, SelectEntity):
    """Select entity for tap water capacity target (number of people)."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: Any,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device, api)
        self._attr_translation_key = "tap_water_capacity_target"
        self._attr_unique_id = f"qvantum_{device['id']}_tap_water_capacity_target"
        self._attr_icon = "mdi:account-multiple"
        self._attr_options = ["1", "2", "3", "4", "5"]
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_entity_registry_enabled_default = (
            "tap_water_capacity_target" in COMMONLY_USED_SELECT_SETTINGS
        )

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if not self.coordinator.data:
            return None

        # Check in settings
        settings = self.coordinator.data.get("settings", {})
        if "settings" in settings:
            settings = settings["settings"]

            for setting in settings:
                if setting.get("name") == "tap_water_capacity_target":
                    value = setting.get("value")
                    if value is not None:
                        # Convert to string for option matching
                        try:
                            int_value = int(value)
                            if 1 <= int_value <= 5:
                                return str(int_value)
                        except (ValueError, TypeError):
                            _LOGGER.warning(
                                "Invalid tap_water_capacity_target value: %s",
                                value,
                            )

        return None

    async def async_select_option(self, option: str) -> None:
        """Update the current value."""
        try:
            people_count = int(option)
            await self.hass.async_add_executor_job(
                self._api.set_setting,
                self._device["id"],
                "tap_water_capacity_target",
                people_count,
            )
            _LOGGER.info(
                "Set tap water capacity target to %s people on device %s",
                option,
                self._device["id"],
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except (ValueError, QvantumApiError) as err:
            _LOGGER.error(
                "Failed to set tap water capacity target: %s",
                err,
            )


class QvantumDHWPrioritySelect(QvantumEntity, SelectEntity):
    """Select entity for DHW Priority mode."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: Any,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device, api)
        self._attr_translation_key = "dhw_priority"
        self._attr_unique_id = f"qvantum_{device['id']}_dhw_priority"
        self._attr_icon = "mdi:water-thermometer"
        self._current_custom_value = None  # Track custom value
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_entity_registry_enabled_default = (
            "dhw_priority_time" in COMMONLY_USED_SELECT_SETTINGS
        )

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        base_options = list(HOT_WATER_PRIORITY_MAP.values())
        if self._current_custom_value is not None:
            # Add custom option
            base_options.append(f"Custom ({self._current_custom_value} minutes)")
        return base_options

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if not self.coordinator.data:
            return None

        # Try to get value from internal_metrics first, then settings
        value = None

        internal_metrics = self.coordinator.data.get("internal_metrics", {})
        if internal_metrics:
            value = internal_metrics.get("dhw_prioritytime")

        if value is None:
            settings = self.coordinator.data.get("settings", {})
            if "settings" in settings:
                for setting in settings["settings"]:
                    if setting.get("name") == "dhw_prioritytime":
                        value = setting.get("value")
                        break

        # Map value to option using HOT_WATER_PRIORITY_MAP
        if value is not None:
            try:
                value_int = int(value)
                if value_int in HOT_WATER_PRIORITY_MAP:
                    # Clear custom value if we're back to a standard value
                    self._current_custom_value = None
                    return HOT_WATER_PRIORITY_MAP[value_int]
                # Custom value detected
                _LOGGER.warning(
                    "DHW priority time has custom value %s minutes (device %s). "
                    "Expected one of: %s",
                    value_int,
                    self._device["id"],
                    list(HOT_WATER_PRIORITY_MAP.keys()),
                )
                self._current_custom_value = value_int
                return f"Custom ({value_int} minutes)"
            except (TypeError, ValueError):
                pass

        # Clear custom value and return default
        self._current_custom_value = None
        return HOT_WATER_PRIORITY_MAP[30]  # Default to normal_30min

    async def async_select_option(self, option: str) -> None:
        """Update the current value."""
        # Ignore custom option selection (read-only)
        if option.startswith("Custom ("):
            _LOGGER.warning(
                "Cannot set custom DHW priority value. Please select a standard option."
            )
            return

        # Reverse map option to value using HOT_WATER_PRIORITY_MAP
        value = None
        for minutes, label in HOT_WATER_PRIORITY_MAP.items():
            if label == option:
                value = minutes
                break

        if value is None:
            _LOGGER.error("Invalid DHW priority option: %s", option)
            return

        try:
            response = await self.hass.async_add_executor_job(
                self._api.set_setting,
                self._device["id"],
                "dhw_prioritytime",
                value,
            )
            _LOGGER.info(
                "Set DHW priority time to %s (%s minutes) on device %s",
                option,
                value,
                self._device["id"],
            )
            _LOGGER.debug("API response: %s", response)

            # Optimistic update if command was applied
            if response and (
                response.get("status") == "APPLIED"
                or response.get("heatpump_status") == "APPLIED"
            ):
                # Update coordinator data immediately
                if "internal_metrics" in self.coordinator.data:
                    self.coordinator.data["internal_metrics"]["dhw_prioritytime"] = (
                        value
                    )
                    self.coordinator.async_set_updated_data(self.coordinator.data)
                    _LOGGER.debug(
                        "Optimistically updated dhw_prioritytime to %s in coordinator",
                        value,
                    )

            # Clear custom value when setting a standard value
            self._current_custom_value = None
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to set DHW priority time: %s",
                err,
            )


class QvantumDHWModeSelect(QvantumEntity, SelectEntity):
    """Select entity for DHW Mode."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: Any,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device, api)
        self._attr_translation_key = "dhw_mode"
        self._attr_unique_id = f"qvantum_{device['id']}_dhw_mode"
        self._attr_icon = "mdi:water-thermometer"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_entity_registry_enabled_default = (
            "dhw_mode" in COMMONLY_USED_SELECT_SETTINGS
        )

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        return ["eco", "normal", "extra"]

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if not self.coordinator.data:
            return None

        # Try to get value from settings
        value = None
        settings = self.coordinator.data.get("settings", {})
        if "settings" in settings:
            for setting in settings["settings"]:
                if setting.get("name") == "dhw_mode":
                    value = setting.get("value")
                    break

        if value is None:
            return None

        # Map integer value to option
        mode_map = {0: "eco", 1: "normal", 2: "extra"}
        return mode_map.get(int(value), None)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        # Map option to integer value
        option_map = {"eco": 0, "normal": 1, "extra": 2}
        value = option_map.get(option)

        if value is None:
            _LOGGER.error("Invalid DHW mode option: %s", option)
            return

        try:
            await self._api.set_setting(
                self._device["id"],
                "dhw_mode",
                value,
            )
            _LOGGER.info(
                "Set DHW mode to %s on device %s",
                option,
                self._device["id"],
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except (ValueError, QvantumApiError) as err:
            _LOGGER.error(
                "Failed to set DHW mode: %s",
                err,
            )


class QvantumOperationModeSelect(QvantumEntity, SelectEntity):
    """Select entity for Operation Mode."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: Any,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device, api)
        self._attr_translation_key = "operation_mode"
        self._attr_unique_id = f"qvantum_{device['id']}_operation_mode"
        self._attr_icon = "mdi:cog"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_entity_registry_enabled_default = (
            "op_mode" in COMMONLY_USED_SELECT_SETTINGS
        )

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        return list(OP_MODE_MAP.values())

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if not self.coordinator.data:
            return None

        # Try to get value from internal_metrics first, then settings
        value = None
        internal_metrics = self.coordinator.data.get("internal_metrics", {})
        if internal_metrics:
            value = internal_metrics.get("op_mode")

        if value is None:
            settings = self.coordinator.data.get("settings", {})
            if "settings" in settings:
                for setting in settings["settings"]:
                    if setting.get("name") == "op_mode":
                        value = setting.get("value")
                        break

        if value is None:
            return None

        # Map integer value to option
        return OP_MODE_MAP.get(int(value), None)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        # Map option to integer value
        option_map = {v: k for k, v in OP_MODE_MAP.items()}
        value = option_map.get(option)

        if value is None:
            _LOGGER.error("Invalid operation mode option: %s", option)
            return

        try:
            await self._api.set_setting(
                self._device["id"],
                "op_mode",
                value,
            )
            _LOGGER.info(
                "Set operation mode to %s on device %s",
                option,
                self._device["id"],
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except (ValueError, QvantumApiError) as err:
            _LOGGER.error(
                "Failed to set operation mode: %s",
                err,
            )


class QvantumDHWOutTempSelect(QvantumEntity, SelectEntity):
    """Select entity for DHW Out Temperature mode."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: Any,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device, api)
        self._attr_translation_key = "dhw_out_temp"
        self._attr_unique_id = f"qvantum_{device['id']}_dhw_out_temp"
        self._attr_icon = "mdi:thermometer-water"
        self._current_custom_value = None  # Track custom value
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_entity_registry_enabled_default = (
            "dhw_out_temp" in COMMONLY_USED_SELECT_SETTINGS
        )

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        base_options = list(HOT_WATER_TEMP_MAP.values())
        if self._current_custom_value is not None:
            # Add custom option
            base_options.append(f"Custom ({self._current_custom_value}°C)")
        return base_options

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if not self.coordinator.data:
            return None

        # Try to get value from internal_metrics first, then settings
        value = None

        internal_metrics = self.coordinator.data.get("internal_metrics", {})
        if internal_metrics:
            value = internal_metrics.get("dhw_outl_temp_5")

        if value is None:
            settings = self.coordinator.data.get("settings", {})
            if "settings" in settings:
                for setting in settings["settings"]:
                    if setting.get("name") == "dhw_outl_temp_5":
                        value = setting.get("value")
                        break

        # Map value to option using HOT_WATER_TEMP_MAP
        if value is not None:
            try:
                value_int = int(value)
                if value_int in HOT_WATER_TEMP_MAP:
                    # Clear custom value if we're back to a standard value
                    self._current_custom_value = None
                    return HOT_WATER_TEMP_MAP[value_int]
                # Custom value detected
                _LOGGER.warning(
                    "DHW outlet temperature has custom value %s°C (device %s). "
                    "Expected one of: %s",
                    value_int,
                    self._device["id"],
                    list(HOT_WATER_TEMP_MAP.keys()),
                )
                self._current_custom_value = value_int
                return f"Custom ({value_int}°C)"
            except (TypeError, ValueError):
                pass

        # Clear custom value and return default
        self._current_custom_value = None
        return HOT_WATER_TEMP_MAP[52]  # Default to normal_52c

    async def async_select_option(self, option: str) -> None:
        """Update the current value."""
        # Ignore custom option selection (read-only)
        if option.startswith("Custom ("):
            _LOGGER.warning(
                "Cannot set custom DHW outlet temperature. Please select a standard option."
            )
            return

        # Reverse map option to value using HOT_WATER_TEMP_MAP
        value = None
        for temp, label in HOT_WATER_TEMP_MAP.items():
            if label == option:
                value = temp
                break

        if value is None:
            _LOGGER.error("Invalid DHW out temp option: %s", option)
            return

        try:
            response = await self.hass.async_add_executor_job(
                self._api.set_setting,
                self._device["id"],
                "dhw_outl_temp_5",
                value,
            )
            _LOGGER.info(
                "Set DHW outlet temp to %s (%s°C) on device %s",
                option,
                value,
                self._device["id"],
            )
            _LOGGER.debug("API response: %s", response)

            # Optimistic update if command was applied
            if response and (
                response.get("status") == "APPLIED"
                or response.get("heatpump_status") == "APPLIED"
            ):
                # Update coordinator data immediately
                if "internal_metrics" in self.coordinator.data:
                    self.coordinator.data["internal_metrics"]["dhw_outl_temp_5"] = value
                    self.coordinator.async_set_updated_data(self.coordinator.data)
                    _LOGGER.debug(
                        "Optimistically updated dhw_outl_temp_5 to %s in coordinator",
                        value,
                    )

            # Clear custom value when setting a standard value
            self._current_custom_value = None
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to set DHW outlet temp: %s",
                err,
            )


class QvantumRoomCompFactorSelect(QvantumEntity, SelectEntity):
    """Select entity for Room Compensation Factor."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: QvantumApi,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device, api)
        self._attr_translation_key = "room_comp_factor"
        self._attr_unique_id = f"qvantum_{device['id']}_room_comp_factor"
        self._attr_icon = "mdi:thermometer-lines"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_options = list(ROOM_COMP_MAP.values())
        self._attr_entity_registry_enabled_default = (
            "room_comp_factor" in COMMONLY_USED_SELECT_SETTINGS
        )

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if (
            self.coordinator.data
            and "settings" in self.coordinator.data
            and "settings" in self.coordinator.data["settings"]
        ):
            for setting in self.coordinator.data["settings"]["settings"]:
                if setting["name"] == "room_comp_factor":
                    value = setting.get("value")
                    if value is not None:
                        try:
                            # Convert value to float for comparison
                            float_value = float(value)
                            return ROOM_COMP_MAP.get(float_value)
                        except (ValueError, TypeError):
                            _LOGGER.warning(
                                "Could not convert room_comp_factor value %s to float",
                                value,
                            )
        return None

    async def async_select_option(self, option: str) -> None:
        """Set the room compensation factor."""
        # Find the numeric value for the selected option
        value = None
        for val, label in ROOM_COMP_MAP.items():
            if label == option:
                value = val
                break

        if value is None:
            _LOGGER.error("Invalid room compensation factor option: %s", option)
            return

        try:
            await self.hass.async_add_executor_job(
                self._api.set_setting,
                self._device["id"],
                "room_comp_factor",
                value,
            )
            _LOGGER.info(
                "Set room compensation factor to %s (%s) on device %s",
                option,
                value,
                self._device["id"],
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to set room compensation factor: %s",
                err,
            )


class QvantumCurveShiftSelect(QvantumEntity, SelectEntity):
    """Select entity for Heating Curve Shift (indoor temperature offset)."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: QvantumApi,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device, api)
        self._attr_translation_key = "heating_curve_shift"
        self._attr_unique_id = f"qvantum_{device['id']}_curve_shift"
        self._attr_icon = "mdi:chart-bell-curve-cumulative"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_options = list(CURVE_SHIFT_MAP.values())
        self._attr_entity_registry_enabled_default = (
            "heating_curve_shift" in COMMONLY_USED_SELECT_SETTINGS
        )

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if (
            self.coordinator.data
            and "settings" in self.coordinator.data
            and "settings" in self.coordinator.data["settings"]
        ):
            for setting in self.coordinator.data["settings"]["settings"]:
                if setting["name"] == "indoor_temperature_offset":
                    value = setting.get("value")
                    if value is not None:
                        try:
                            # Convert value to int for comparison
                            int_value = int(value)
                            return CURVE_SHIFT_MAP.get(int_value)
                        except (ValueError, TypeError):
                            _LOGGER.warning(
                                "Could not convert curve shift value %s to int",
                                value,
                            )
        return None

    async def async_select_option(self, option: str) -> None:
        """Set the heating curve shift."""
        # Find the numeric value for the selected option
        value = None
        for val, label in CURVE_SHIFT_MAP.items():
            if label == option:
                value = val
                break

        if value is None:
            _LOGGER.error("Invalid curve shift option: %s", option)
            return

        try:
            await self.hass.async_add_executor_job(
                self._api.set_setting,
                self._device["id"],
                "indoor_temperature_offset",
                value,
            )
            _LOGGER.info(
                "Set heating curve shift to %s (%s) on device %s",
                option,
                value,
                self._device["id"],
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to set heating curve shift: %s",
                err,
            )


class QvantumSensorModeSelect(QvantumEntity, SelectEntity):
    """Select entity for Sensor Mode (which sensor controls heat pump operation)."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: QvantumApi,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device, api)
        self._attr_translation_key = "sensor_mode"
        self._attr_unique_id = f"qvantum_{device['id']}_sensor_mode"
        self._attr_icon = "mdi:thermometer-check"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_entity_registry_enabled_default = (
            "sensor_mode" in COMMONLY_USED_SELECT_SETTINGS
        )
        self._attr_options = list(SENSOR_MODE_OPTIONS.values())

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if (
            self.coordinator.data
            and "settings" in self.coordinator.data
            and "settings" in self.coordinator.data["settings"]
        ):
            for setting in self.coordinator.data["settings"]["settings"]:
                if setting["name"] == "sensor_mode":
                    value = setting.get("value")
                    if value is not None:
                        # Value is a string like "off", "bt2", "bt3", "btx"
                        return SENSOR_MODE_OPTIONS.get(value)
        return None

    async def async_select_option(self, option: str) -> None:
        """Set the sensor mode."""
        # Find the string value for the selected option
        value = None
        for val, label in SENSOR_MODE_OPTIONS.items():
            if label == option:
                value = val
                break

        if value is None:
            _LOGGER.error("Invalid sensor mode option: %s", option)
            return

        try:
            await self.hass.async_add_executor_job(
                self._api.set_setting,
                self._device["id"],
                "sensor_mode",
                value,
            )
            _LOGGER.info(
                "Set sensor mode to %s (%s) on device %s",
                option,
                value,
                self._device["id"],
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to set sensor mode: %s",
                err,
            )
