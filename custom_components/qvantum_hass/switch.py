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
from typing import Any, Final

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
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
    # SWITCH ENTITIES (various sources)
    # On/off controls for heat pump features and settings.
    # =========================================================================
    QvantumEntityDef(
        "extra_hot_water",
        "Extra hot water boost (indefinite, via command API)",
        source=EntitySource.SETTINGS,
        api_key="extra_tap_water",
    ),
    QvantumEntityDef(
        "smart_control_heating",
        "SmartControl space heating enable/disable",
        source=EntitySource.INTERNAL_METRICS,
        entity_category=EntityCategory.CONFIG,
        api_key="enable_sc_sh",
    ),
    QvantumEntityDef(
        "smart_control_dhw",
        "SmartControl DHW enable/disable",
        source=EntitySource.INTERNAL_METRICS,
        entity_category=EntityCategory.CONFIG,
        api_key="enable_sc_dhw",
    ),
    QvantumEntityDef(
        "manual_dhw",
        "Manual mode: domestic hot water on/off",
        source=EntitySource.INTERNAL_METRICS,
        entity_category=EntityCategory.CONFIG,
        api_key="op_man_dhw",
    ),
    QvantumEntityDef(
        "manual_additional_heat",
        "Manual mode: additional electric heater on/off",
        source=EntitySource.INTERNAL_METRICS,
        entity_category=EntityCategory.CONFIG,
        api_key="op_man_addition",
    ),
    QvantumEntityDef(
        "manual_cooling",
        "Manual mode: cooling on/off",
        source=EntitySource.INTERNAL_METRICS,
        entity_category=EntityCategory.CONFIG,
        api_key="op_man_cooling",
    ),
    QvantumEntityDef(
        "vacation_mode",
        "Vacation mode (reduces heating while away)",
        source=EntitySource.SETTINGS,
        api_key="vacation_mode",
    ),
    QvantumEntityDef(
        "auto_elevate_access",
        "Auto-renew elevated service access",
        source=EntitySource.COORDINATOR,
        entity_category=EntityCategory.DIAGNOSTIC,
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
    """Set up Qvantum switch entities."""
    data = entry.runtime_data
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

        # Add Manual Operation Mode sub-switches
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
        entities.append(
            QvantumManualOperationSwitch(
                coordinator,
                device,
                api,
                "op_man_cooling",
                "mdi:snowflake",
            )
        )

        # Add settings-based switch entities from entity definitions
        # (replaces dynamic creation from settings_inventory)
        entities.extend(
            QvantumSwitchEntity(
                coordinator,
                device,
                entity_def,
            )
            for entity_def in ENTITY_DEFS
            if (
                entity_def.source == EntitySource.SETTINGS
                and entity_def.key not in ("extra_hot_water",)  # Handled above
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


class QvantumSwitchEntity(QvantumEntity, SwitchEntity):  # pylint: disable=abstract-method
    """Switch entity for Qvantum settings (reads from settings API)."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        entity_def: QvantumEntityDef,
    ) -> None:
        """Initialize the switch entity from an entity definition."""
        super().__init__(coordinator, device, None)
        self._setting_name = entity_def.api_key or entity_def.key
        self._attr_translation_key = entity_def.key
        self._attr_unique_id = f"{device['id']}_{entity_def.key}"
        self._attr_entity_registry_enabled_default = entity_def.enabled_by_default
        self._attr_entity_category = entity_def.entity_category

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
            response = await self.coordinator.api.set_setting(
                self._device["id"],
                self._setting_name,
                True,
            )
            _LOGGER.debug(
                "Turn on %s response for device %s: %s",
                self._setting_name,
                self._device["id"],
                response,
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
            response = await self.coordinator.api.set_setting(
                self._device["id"],
                self._setting_name,
                False,
            )
            _LOGGER.debug(
                "Turn off %s response for device %s: %s",
                self._setting_name,
                self._device["id"],
                response,
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to turn off %s: %s",
                self._setting_name,
                err,
            )


class QvantumExtraHotWaterSwitch(QvantumEntity, SwitchEntity):  # pylint: disable=abstract-method
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
        self._attr_unique_id = f"{device['id']}_extra_hot_water"
        self._attr_icon = "mdi:water-boiler"
        # _pending_state: set immediately after issuing a command to avoid a
        # one-cycle flicker while the coordinator hasn't refreshed yet.  It is
        # cleared on the very next coordinator update so that external changes
        # (e.g. boost cancelled from the app or another HA session) are
        # reflected after at most one polling interval.
        self._pending_state: bool | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Clear pending command state on each coordinator refresh.

        Once the coordinator has fetched fresh data from the API the pending
        state is no longer needed — the real device state is now available.
        """
        self._pending_state = None
        super()._handle_coordinator_update()

    @property
    def is_on(self) -> bool | None:
        """Return true if extra hot water is active.

        Priority order:
        1. ``_pending_state`` — set immediately after a command to cover the
           one coordinator-cycle lag before the API reflects the new state.
           Cleared on the next coordinator refresh.
        2. ``extra_tap_water`` from the settings API — the canonical source.
           Reliably reflects state when using the ``set_additional_hot_water``
           command API (as opposed to the legacy ``update_settings`` path).
        4. ``None`` (unknown) if no source has information yet.
        """
        # Source 1 – transient command state (covers one coordinator cycle)
        if self._pending_state is not None:
            return self._pending_state

        if self.coordinator.data:
            # Source 2 – settings API (reliable with set_additional_hot_water)
            for setting in self.coordinator.data.get("settings", {}).get(
                "settings", []
            ):
                if setting["name"] == "extra_tap_water":
                    value = setting.get("value")
                    if isinstance(value, bool):
                        return value
                    if isinstance(value, str):
                        return value.lower() in ("on", "true", "1", "yes")
                    if isinstance(value, (int, float)):
                        return bool(value)
                    break

        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on extra hot water indefinitely via the command API."""
        try:
            response = await self._api.set_extra_hot_water(
                self._device["id"],
                indefinite=True,
            )
            _LOGGER.debug(
                "Turn on extra hot water (indefinite) response for device %s: %s",
                self._device["id"],
                response,
            )
            _LOGGER.info(
                "Activated extra hot water indefinitely on device %s",
                self._device["id"],
            )
            self._pending_state = True
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to activate extra hot water: %s",
                err,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Cancel extra hot water via the command API."""
        try:
            response = await self._api.set_extra_hot_water(
                self._device["id"],
                hours=0,
            )
            _LOGGER.debug(
                "Cancel extra hot water response for device %s: %s",
                self._device["id"],
                response,
            )
            _LOGGER.info(
                "Cancelled extra hot water on device %s",
                self._device["id"],
            )
            self._pending_state = False
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to cancel extra hot water: %s",
                err,
            )


class QvantumSmartControlSwitch(QvantumEntity, SwitchEntity):  # pylint: disable=abstract-method
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
        translation_key = translation_key_map.get(setting_name, setting_name)
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{device['id']}_{setting_name}"
        self._attr_icon = "mdi:leaf"
        self._attr_entity_category = EntityCategory.CONFIG
        _def = get_entity_def(translation_key)
        self._attr_entity_registry_enabled_default = (
            _def.enabled_by_default if _def else True
        )

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
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self._api.set_setting(
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
            await self._api.set_setting(
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


class QvantumManualOperationSwitch(QvantumEntity, SwitchEntity):  # pylint: disable=abstract-method
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
        translation_key = translation_key_map.get(setting_name, setting_name)
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{device['id']}_{setting_name}"
        self._attr_icon = icon
        self._attr_entity_category = EntityCategory.CONFIG
        _def = get_entity_def(translation_key)
        self._attr_entity_registry_enabled_default = (
            _def.enabled_by_default if _def else True
        )

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
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self._api.set_setting(
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
            await self._api.set_setting(
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


class QvantumAutoElevateAccessSwitch(QvantumEntity, SwitchEntity):  # pylint: disable=abstract-method
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
        self._attr_unique_id = f"{device['id']}_auto_elevate_access"
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
            await self._api.elevate_access(
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
