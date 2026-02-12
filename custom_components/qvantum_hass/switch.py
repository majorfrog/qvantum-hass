"""Switch platform for Qvantum Heat Pump integration.

This module provides switch entities for boolean (on/off) settings:
- Extra hot water boost mode
- SmartControl enable switches (heating and DHW)
- Manual operation mode controls
- Vacation mode
- Auto-elevate access control
- Various system boolean settings

Switches provide simple on/off control for heat pump features and modes.
Many are disabled by default to reduce clutter for typical users.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import QvantumDataUpdateCoordinator
from .api import QvantumApiError
from .const import COMMONLY_USED_SWITCH_SETTINGS, DOMAIN
from .entity import QvantumEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qvantum switch entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    devices = data["devices"]
    api = data["api"]

    entities = []

    for device in devices:
        device_id = device["id"]
        coordinator = coordinators[device_id]

        # Add extra hot water switch (uses command API)
        entities.append(
            QvantumExtraHotWaterSwitch(
                coordinator,
                device,
                api,
            )
        )

        # Add SmartControl enable switches
        entities.append(
            QvantumSmartControlSwitch(
                coordinator,
                device,
                api,
                "enable_sc_sh",
            )
        )
        entities.append(
            QvantumSmartControlSwitch(
                coordinator,
                device,
                api,
                "enable_sc_dhw",
            )
        )

        # Add Manual Operation Mode sub-switches (only available when operation mode is Manual)
        # Note: Operation mode itself is controlled by select.operation_mode
        # Note: man_mode is now a select entity (off/heating/cooling)
        entities.append(
            QvantumManualOperationSwitch(
                coordinator,
                device,
                api,
                "op_man_dhw",
                "mdi:water-outline",
            )
        )
        entities.append(
            QvantumManualOperationSwitch(
                coordinator,
                device,
                api,
                "op_man_addition",
                "mdi:transmission-tower-import",
            )
        )

        # Add switch entities for boolean settings
        if coordinator.data and "settings_inventory" in coordinator.data:
            settings_inventory = coordinator.data["settings_inventory"]
            if settings_inventory and "settings" in settings_inventory:
                # Get list of settings that are actually returned by the API
                available_setting_names = QvantumEntity.get_available_setting_names(
                    coordinator.data
                )

                for setting in settings_inventory["settings"]:
                    # Skip extra_tap_water as we handle it separately
                    if setting.get("name") == "extra_tap_water":
                        continue
                    # Skip settings already handled as binary sensors from METRIC_INFO
                    if setting.get("name") == "cooling_enabled":
                        continue
                    # Skip SmartControl settings as we handle them separately
                    if setting.get("name") in (
                        "enable_sc_sh",
                        "enable_sc_dhw",
                        "use_adaptive",
                    ):
                        continue
                    # Skip manual operation mode settings as we handle them separately
                    # Note: op_mode is now only controlled via select.operation_mode
                    if setting.get("name") in (
                        "op_mode",
                        "man_mode",
                        "op_man_dhw",
                        "op_man_addition",
                        "op_man_cooling",
                    ):
                        continue

                    # Only create entities for settings that are actually available in API response
                    if setting.get("name") not in available_setting_names:
                        _LOGGER.debug(
                            "Skipping switch entity for %s - not available in settings response",
                            setting.get("name"),
                        )
                        continue

                    if setting.get("data_type") == "boolean" and not setting.get(
                        "read_only", False
                    ):
                        entities.append(
                            QvantumSwitchEntity(
                                coordinator,
                                device,
                                setting,
                            )
                        )

        # Add auto-elevate access switch
        entities.append(
            QvantumAutoElevateAccessSwitch(
                coordinator,
                device,
                api,
            )
        )

    async_add_entities(entities)


class QvantumSwitchEntity(QvantumEntity, SwitchEntity):
    """Switch entity for Qvantum settings."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        setting: dict[str, Any],
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, device, None)
        self._setting = setting
        self._setting_name = setting["name"]
        self._attr_translation_key = self._setting_name
        self._attr_unique_id = f"qvantum_{device['id']}_{self._setting_name}"
        # Keep vacation_mode in main controls, move others to config
        if self._setting_name != "vacation_mode":
            self._attr_entity_category = EntityCategory.CONFIG

        # Commonly-used settings enabled by default, advanced settings disabled
        self._attr_entity_registry_enabled_default = (
            self._setting_name in COMMONLY_USED_SWITCH_SETTINGS
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if (
            self.coordinator.data
            and "settings" in self.coordinator.data
            and "settings" in self.coordinator.data["settings"]
        ):
            for setting in self.coordinator.data["settings"]["settings"]:
                if setting["name"] == self._setting_name:
                    value = setting.get("value")
                    if value is not None:
                        # Handle different value representations
                        if isinstance(value, bool):
                            return value
                        if isinstance(value, str):
                            return value.lower() in ("on", "true", "1", "yes")
                        if isinstance(value, (int, float)):
                            return bool(value)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.api.set_setting,
                self._device["id"],
                self._setting_name,
                "on",
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to turn on %s: %s",
                self._setting_name,
                err,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.api.set_setting,
                self._device["id"],
                self._setting_name,
                "off",
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to turn off %s: %s",
                self._setting_name,
                err,
            )


class QvantumExtraHotWaterSwitch(QvantumEntity, SwitchEntity):
    """Switch entity for extra hot water control."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: Any,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, device, api)
        self._attr_translation_key = "extra_hot_water"
        self._attr_unique_id = f"qvantum_{device['id']}_extra_hot_water"
        self._attr_icon = "mdi:water-boiler"

    @property
    def is_on(self) -> bool | None:
        """Return true if extra hot water is active."""
        if (
            self.coordinator.data
            and "settings" in self.coordinator.data
            and "settings" in self.coordinator.data["settings"]
        ):
            for setting in self.coordinator.data["settings"]["settings"]:
                if setting["name"] == "extra_tap_water":
                    value = setting.get("value")
                    if value is not None:
                        if isinstance(value, bool):
                            return value
                        if isinstance(value, str):
                            return value.lower() in ("on", "true", "1", "yes")
                        if isinstance(value, (int, float)):
                            return bool(value)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on extra hot water indefinitely."""
        try:
            await self.hass.async_add_executor_job(
                self._api.set_extra_hot_water,
                self._device["id"],
                0,  # Hours parameter (ignored when indefinite=True)
                True,  # Enable indefinitely
            )
            _LOGGER.info(
                "Activated extra hot water indefinitely on device %s",
                self._device["id"],
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to activate extra hot water: %s",
                err,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off extra hot water."""
        try:
            await self.hass.async_add_executor_job(
                self._api.set_extra_hot_water,
                self._device["id"],
                0,  # Cancel
            )
            _LOGGER.info(
                "Cancelled extra hot water on device %s",
                self._device["id"],
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to cancel extra hot water: %s",
                err,
            )


class QvantumSmartControlSwitch(QvantumEntity, SwitchEntity):
    """Switch entity for SmartControl enable/disable."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: Any,
        setting_name: str,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, device, api)
        self._setting_name = setting_name
        # Map setting names to translation keys
        translation_key_map = {
            "enable_sc_sh": "smart_control_heating",
            "enable_sc_dhw": "smart_control_dhw",
        }
        self._attr_translation_key = translation_key_map.get(setting_name, setting_name)
        self._attr_unique_id = f"qvantum_{device['id']}_{setting_name}"
        self._attr_icon = "mdi:leaf"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if not self.coordinator.data:
            return False

        # Try internal_metrics first (data is already extracted from 'values')
        internal_metrics = self.coordinator.data.get("internal_metrics", {})
        value = internal_metrics.get(self._setting_name)
        if value is not None:
            return bool(value)

        # Fall back to settings
        if (
            "settings" in self.coordinator.data
            and "settings" in self.coordinator.data["settings"]
        ):
            for setting in self.coordinator.data["settings"]["settings"]:
                if setting["name"] == self._setting_name:
                    value = setting.get("value")
                    if value is not None:
                        # Handle different value representations
                        if isinstance(value, bool):
                            return value
                        if isinstance(value, str):
                            return value.lower() in ("on", "true", "1", "yes")
                        if isinstance(value, (int, float)):
                            return bool(value)
        # Return False instead of None to avoid "unknown" state
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.hass.async_add_executor_job(
                self._api.set_setting,
                self._device["id"],
                self._setting_name,
                True,
            )
            _LOGGER.info(
                "Turned on %s for device %s",
                self._setting_name,
                self._device["id"],
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to turn on %s: %s",
                self._setting_name,
                err,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.hass.async_add_executor_job(
                self._api.set_setting,
                self._device["id"],
                self._setting_name,
                False,
            )
            _LOGGER.info(
                "Turned off %s for device %s",
                self._setting_name,
                self._device["id"],
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to turn off %s: %s",
                self._setting_name,
                err,
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        if not self.coordinator.data:
            return False

        # Only available when use_adaptive (SmartControl) is enabled
        use_adaptive = None

        # Check internal_metrics first
        internal_metrics = self.coordinator.data.get("internal_metrics", {})
        if internal_metrics:
            use_adaptive = internal_metrics.get("use_adaptive")

        # Fall back to settings if not found
        if use_adaptive is None:
            settings = self.coordinator.data.get("settings", {})
            if "settings" in settings:
                for setting in settings["settings"]:
                    if setting.get("name") == "use_adaptive":
                        use_adaptive = setting.get("value")
                        break

        # Convert to boolean if needed
        if isinstance(use_adaptive, str):
            use_adaptive = use_adaptive.lower() in ("on", "true", "1", "yes")
        elif isinstance(use_adaptive, (int, float)):
            use_adaptive = bool(use_adaptive)

        # Only available when use_adaptive is explicitly True
        # (i.e., when select.smartcontrol is not "Off")
        if use_adaptive is not True:
            return False

        # Also check connectivity status
        if (
            "status" in self.coordinator.data
            and "connectivity" in self.coordinator.data["status"]
        ):
            connectivity = self.coordinator.data["status"]["connectivity"]
            return connectivity.get("connected", False)

        return True


class QvantumManualOperationSwitch(QvantumEntity, SwitchEntity):
    """Switch entity for Manual Operation Mode controls."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: Any,
        setting_name: str,
        icon: str,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, device, api)
        self._setting_name = setting_name
        # Map setting names to translation keys
        translation_key_map = {
            "op_man_dhw": "manual_dhw",
            "op_man_addition": "manual_additional_heat",
            "op_man_cooling": "manual_cooling",
        }
        self._attr_translation_key = translation_key_map.get(setting_name, setting_name)
        self._attr_unique_id = f"qvantum_{device['id']}_{setting_name}"
        self._attr_icon = icon
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if not self.coordinator.data:
            return False

        # Try internal_metrics first (data is already extracted from 'values')
        internal_metrics = self.coordinator.data.get("internal_metrics", {})
        value = internal_metrics.get(self._setting_name)
        if value is not None:
            # Manual operation mode values are 0/1 integers
            return value == 1 or value is True

        # Fall back to settings
        if (
            "settings" in self.coordinator.data
            and "settings" in self.coordinator.data["settings"]
        ):
            for setting in self.coordinator.data["settings"]["settings"]:
                if setting["name"] == self._setting_name:
                    value = setting.get("value")
                    if value is not None:
                        # Handle different value representations
                        if isinstance(value, bool):
                            return value
                        if isinstance(value, str):
                            return value.lower() in ("on", "true", "1", "yes")
                        if isinstance(value, (int, float)):
                            return value == 1 or bool(value)
        # Return False instead of None to avoid "unknown" state
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.hass.async_add_executor_job(
                self._api.set_setting,
                self._device["id"],
                self._setting_name,
                1,
            )
            _LOGGER.info(
                "Turned on %s for device %s",
                self._setting_name,
                self._device["id"],
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to turn on %s: %s",
                self._setting_name,
                err,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.hass.async_add_executor_job(
                self._api.set_setting,
                self._device["id"],
                self._setting_name,
                0,
            )
            _LOGGER.info(
                "Turned off %s for device %s",
                self._setting_name,
                self._device["id"],
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to turn off %s: %s",
                self._setting_name,
                err,
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        # Check connectivity status
        if (
            self.coordinator.data
            and "status" in self.coordinator.data
            and "connectivity" in self.coordinator.data["status"]
        ):
            connectivity = self.coordinator.data["status"]["connectivity"]
            if not connectivity.get("connected", False):
                return False

            # For manual operation sub-switches, only available when operation mode is Manual (value 1)
            if self._setting_name in (
                "op_man_dhw",
                "op_man_addition",
                "man_mode",
                "op_man_cooling",
            ):
                op_mode_value = None

                # Check internal_metrics first
                internal_metrics = self.coordinator.data.get("internal_metrics", {})
                if internal_metrics:
                    op_mode_value = internal_metrics.get("op_mode")

                # Fall back to settings if not found
                if op_mode_value is None:
                    settings = self.coordinator.data.get("settings", {})
                    if "settings" in settings:
                        for setting in settings["settings"]:
                            if setting.get("name") == "op_mode":
                                op_mode_value = setting.get("value")
                                break

                # Convert to integer if needed
                if isinstance(op_mode_value, str):
                    try:
                        op_mode_value = int(op_mode_value)
                    except (ValueError, TypeError):
                        op_mode_value = (
                            1
                            if op_mode_value.lower() in ("on", "true", "1", "yes")
                            else 0
                        )
                elif isinstance(op_mode_value, bool):
                    op_mode_value = 1 if op_mode_value else 0

                # Only available when op_mode is 1 (enabled)
                if op_mode_value != 1:
                    return False

            return True

        return True


class QvantumAutoElevateAccessSwitch(QvantumEntity, SwitchEntity):
    """Switch to control automatic access elevation renewal."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: Any,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, device, api)
        self._attr_translation_key = "auto_elevate_access"
        self._attr_unique_id = f"qvantum_{device['id']}_auto_elevate_access"
        self._attr_icon = "mdi:shield-refresh"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return true if auto-elevation is enabled."""
        # Get state from coordinator's auto_elevate flag
        return getattr(self.coordinator, "auto_elevate_enabled", False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable automatic access elevation renewal."""
        await self.coordinator.async_set_auto_elevate(True)
        _LOGGER.info("Auto-elevate access enabled for device %s", self._device["id"])
        # Immediately elevate access when enabled
        try:
            await self.hass.async_add_executor_job(
                self._api.elevate_access,
                self._device["id"],
            )
            _LOGGER.info("Access elevated successfully")
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.warning("Failed to elevate access: %s", err)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable automatic access elevation renewal."""
        await self.coordinator.async_set_auto_elevate(False)
        _LOGGER.info("Auto-elevate access disabled for device %s", self._device["id"])
        self.async_write_ha_state()
