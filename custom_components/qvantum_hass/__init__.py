"""Qvantum Heat Pump Integration for Home Assistant.

This integration provides comprehensive monitoring and control capabilities
for Qvantum heat pumps through their cloud API. It supports multiple devices
per account and provides real-time data updates, configuration options, and
device controls.

Key Features:
    - Multi-device support
    - Real-time sensor data
    - Configuration controls
    - Service access management
    - Alarm monitoring
    - Automatic token refresh
"""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import AuthenticationError, QvantumApi, QvantumApiError
from .const import (
    CONF_FAST_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_API_KEY,
    DEFAULT_FAST_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FAST_POLLING_METRICS,
    METRIC_NAMES,
)

_LOGGER = logging.getLogger(__name__)

# Storage version for auto_elevate state
STORAGE_VERSION = 1
STORAGE_KEY = "qvantum_auto_elevate"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update for config entry.

    This function is called when the user updates integration options
    (such as scan interval). It triggers a reload of the config entry
    to apply the new settings.

    Args:
        hass: Home Assistant instance
        entry: Config entry being updated
    """
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Qvantum from a config entry.

    This function is called when a config entry is being loaded. It:
    1. Authenticates with the Qvantum API
    2. Discovers all devices on the account
    3. Creates a data coordinator for each device
    4. Sets up platform entities
    5. Registers service handlers

    Args:
        hass: Home Assistant instance
        entry: Config entry containing user credentials

    Returns:
        True if setup was successful, False otherwise

    Raises:
        ConfigEntryNotReady: If API is temporarily unavailable
    """
    hass.data.setdefault(DOMAIN, {})

    # Create API instance
    api = QvantumApi(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        api_key=DEFAULT_API_KEY,
    )

    # Try to authenticate
    try:
        await hass.async_add_executor_job(api.authenticate)
    except AuthenticationError as err:
        _LOGGER.error("Failed to authenticate with Qvantum API: %s", err)
        raise ConfigEntryNotReady from err

    # Get devices
    try:
        devices = await hass.async_add_executor_job(api.get_devices)
    except QvantumApiError as err:
        _LOGGER.error("Failed to get devices from Qvantum API: %s", err)
        raise ConfigEntryNotReady from err

    if not devices:
        _LOGGER.warning("No devices found for Qvantum account")
        return False

    # Create coordinators for each device
    # We use two coordinators per device:
    # 1. Fast coordinator (5s default) for power/current sensors
    # 2. Normal coordinator (30s default) for other sensors
    coordinators = {}
    fast_coordinators = {}
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    fast_scan_interval = entry.options.get(
        CONF_FAST_SCAN_INTERVAL, DEFAULT_FAST_SCAN_INTERVAL
    )

    # Create shared storage for auto_elevate state
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")

    for device in devices:
        # Create normal coordinator for all sensors
        coordinator = QvantumDataUpdateCoordinator(
            hass,
            api,
            device["id"],
            update_interval=timedelta(seconds=scan_interval),
            store=store,
            is_fast_coordinator=False,
        )

        # Create fast coordinator for power/current sensors
        fast_coordinator = QvantumDataUpdateCoordinator(
            hass,
            api,
            device["id"],
            update_interval=timedelta(seconds=fast_scan_interval),
            store=store,
            is_fast_coordinator=True,
        )

        # Load auto_elevate state from storage (shared between coordinators)
        await coordinator.async_load_auto_elevate_state()
        # Fast coordinator shares the same auto_elevate state
        fast_coordinator.auto_elevate_enabled = coordinator.auto_elevate_enabled

        # Fetch initial data for both coordinators
        try:
            _LOGGER.debug("Attempting first refresh for device %s", device["id"])
            await coordinator.async_config_entry_first_refresh()
            await fast_coordinator.async_config_entry_first_refresh()
            _LOGGER.debug("First refresh successful for device %s", device["id"])
        except Exception as err:
            _LOGGER.error(
                "Failed first refresh for device %s: %s",
                device["id"],
                err,
                exc_info=True,
            )
            raise

        coordinators[device["id"]] = coordinator
        fast_coordinators[device["id"]] = fast_coordinator

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinators": coordinators,
        "fast_coordinators": fast_coordinators,
        "devices": devices,
    }

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Register services
    async def handle_activate_extra_hot_water(call):
        """Handle the activate_extra_hot_water service call.

        Activates extra hot water mode for the specified duration.

        Args:
            call: Service call data containing device_id and duration
        """
        device_id = call.data.get("device_id")
        duration = call.data.get("duration", 1)

        if not device_id:
            _LOGGER.error("No device_id provided for activate_extra_hot_water service")
            return

        try:
            await hass.async_add_executor_job(
                api.set_extra_hot_water,
                device_id,
                duration,
            )
            _LOGGER.info(
                "Activated extra hot water for %d hours on device %s",
                duration,
                device_id,
            )
            # Refresh coordinator if exists
            if device_id in coordinators:
                await coordinators[device_id].async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to activate extra hot water on device %s: %s",
                device_id,
                err,
            )

    async def handle_cancel_extra_hot_water(call):
        """Handle the cancel_extra_hot_water service call.

        Cancels any active extra hot water mode.

        Args:
            call: Service call data containing device_id
        """
        device_id = call.data.get("device_id")

        if not device_id:
            _LOGGER.error("No device_id provided for cancel_extra_hot_water service")
            return

        try:
            await hass.async_add_executor_job(
                api.set_extra_hot_water,
                device_id,
                0,  # 0 hours = cancel
            )
            _LOGGER.info("Cancelled extra hot water on device %s", device_id)
            # Refresh coordinator if exists
            if device_id in coordinators:
                await coordinators[device_id].async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to cancel extra hot water on device %s: %s",
                device_id,
                err,
            )

    hass.services.async_register(
        DOMAIN,
        "activate_extra_hot_water",
        handle_activate_extra_hot_water,
    )

    hass.services.async_register(
        DOMAIN,
        "cancel_extra_hot_water",
        handle_cancel_extra_hot_water,
    )

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class QvantumDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Qvantum devices.

    This coordinator manages periodic data fetching from the Qvantum API
    for a single device. It handles:
    - Periodic data updates
    - Auto-elevate access control
    - Inventory caching
    - Error handling and recovery

    Attributes:
        api: QvantumApi instance for API communication
        device_id: Unique identifier for the device
        auto_elevate_enabled: Whether to automatically elevate access
    """

    def __init__(
        self,
        hass: HomeAssistant,
        api: QvantumApi,
        device_id: str,
        update_interval: timedelta,
        store: Store,
        is_fast_coordinator: bool = False,
    ) -> None:
        """Initialize the data update coordinator.

        Args:
            hass: Home Assistant instance
            api: Qvantum API client
            device_id: Unique device identifier
            update_interval: How often to fetch updates
            store: Storage for persisting auto-elevate state
            is_fast_coordinator: If True, only fetches fast-polling metrics
        """
        self.api = api
        self.device_id = device_id
        self._store = store
        self.is_fast_coordinator = is_fast_coordinator

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}_{'fast' if is_fast_coordinator else 'normal'}",
            update_interval=update_interval,
        )
        # Initialize cached inventories (only for normal coordinator)
        # Fast coordinator doesn't need inventories
        if not is_fast_coordinator:
            self._settings_inventory = None
            self._metrics_inventory = None
            self._alarms_inventory = None
        # Auto-elevate access control flag - will be loaded from store
        # Default to False for new devices
        self.auto_elevate_enabled = False

    async def async_load_auto_elevate_state(self) -> None:
        """Load auto-elevate state from storage."""
        data = await self._store.async_load()
        if data and self.device_id in data:
            self.auto_elevate_enabled = data[self.device_id]
            _LOGGER.debug(
                "Loaded auto_elevate state for device %s: %s",
                self.device_id,
                self.auto_elevate_enabled,
            )
        else:
            self.auto_elevate_enabled = False

    async def async_set_auto_elevate(self, enabled: bool) -> None:
        """Set auto-elevate state and persist to storage."""
        self.auto_elevate_enabled = enabled

        # Load current data
        data = await self._store.async_load() or {}

        # Update for this device
        data[self.device_id] = enabled

        # Save to storage (non-blocking)
        await self._store.async_save(data)

        _LOGGER.debug(
            "Saved auto_elevate state for device %s: %s",
            self.device_id,
            enabled,
        )

    async def _async_update_data(self):
        """Fetch data from API."""
        return await self.hass.async_add_executor_job(self._update_data)

    def _update_data(self):
        """Fetch data from API (runs in executor)."""
        _LOGGER.debug(
            "Starting data update for device %s (fast_mode: %s)",
            self.device_id,
            self.is_fast_coordinator,
        )
        data = {}

        # Fast coordinator only fetches power/current metrics
        if self.is_fast_coordinator:
            try:
                metrics = self.api.get_internal_metrics(
                    self.device_id, FAST_POLLING_METRICS
                )
                # Extract just the values dict from the response
                if isinstance(metrics, dict) and "values" in metrics:
                    data["internal_metrics"] = metrics["values"]
                else:
                    data["internal_metrics"] = metrics
                _LOGGER.debug(
                    "Fetched fast metrics for %s: %s",
                    self.device_id,
                    data["internal_metrics"],
                )
            except QvantumApiError as err:
                # Raise UpdateFailed to preserve entity values on transient errors
                # This prevents entities from becoming 'unknown' during server issues
                error_msg = str(err)
                if (
                    "Server error" in error_msg
                    or "502" in error_msg
                    or "503" in error_msg
                    or "500" in error_msg
                ):
                    _LOGGER.warning(
                        "Transient server error fetching fast metrics for %s (entities will retain previous values): %s",
                        self.device_id,
                        err,
                    )
                    raise UpdateFailed(f"Transient server error: {err}") from err
                # For other errors, log but don't fail the update
                _LOGGER.error(
                    "Error fetching fast metrics for %s: %s", self.device_id, err
                )
            return data

        # Normal coordinator fetches all data
        # If auto-elevate is enabled, ensure we have elevated access before fetching data
        # This allows reading advanced settings that require service tech access
        if self.auto_elevate_enabled:
            try:
                current_access = self.api.get_access_level(self.device_id)
                if current_access.get("writeAccessLevel", 0) < 20:
                    _LOGGER.debug(
                        "Auto-elevate enabled but access level is %s, elevating",
                        current_access.get("writeAccessLevel"),
                    )
                    self.api.elevate_access(self.device_id)
            except QvantumApiError as err:
                _LOGGER.debug("Could not check/elevate access level: %s", err)

        # Get status (optional - some devices may not support this endpoint)
        try:
            status = self.api.get_status(self.device_id)
            data["status"] = status
        except QvantumApiError as err:
            _LOGGER.debug(
                "Status endpoint not available for %s: %s", self.device_id, err
            )

        # Get settings (optional - some devices may not support this endpoint)
        try:
            settings = self.api.get_settings(self.device_id)
            data["settings"] = settings
            if settings and "settings" in settings:
                _LOGGER.debug(
                    "Fetched %d settings for device %s (auto_elevate: %s)",
                    len(settings["settings"]),
                    self.device_id,
                    self.auto_elevate_enabled,
                )
                # Debug: Log detailed information about actual settings response
                for setting in settings["settings"]:
                    _LOGGER.debug(
                        "Settings response: name=%s, value=%s, data_type=%s, read_only=%s, min=%s, max=%s, step=%s, options=%s",
                        setting.get("name"),
                        setting.get("value"),
                        setting.get("data_type"),
                        setting.get("read_only", False),
                        setting.get("min"),
                        setting.get("max"),
                        setting.get("step"),
                        setting.get("options"),
                    )
        except QvantumApiError as err:
            _LOGGER.debug(
                "Settings endpoint not available for %s: %s", self.device_id, err
            )

        # Get internal metrics
        try:
            metrics = self.api.get_internal_metrics(self.device_id, METRIC_NAMES)
            # Extract just the values dict from the response
            if isinstance(metrics, dict) and "values" in metrics:
                data["internal_metrics"] = metrics["values"]
            else:
                data["internal_metrics"] = metrics
            _LOGGER.debug(
                "Fetched internal_metrics for %s: %s",
                self.device_id,
                data["internal_metrics"],
            )
        except QvantumApiError as err:
            # Raise UpdateFailed for server errors to preserve entity values
            error_msg = str(err)
            if (
                "Server error" in error_msg
                or "502" in error_msg
                or "503" in error_msg
                or "500" in error_msg
            ):
                _LOGGER.warning(
                    "Transient server error fetching internal metrics for %s (entities will retain previous values): %s",
                    self.device_id,
                    err,
                )
                raise UpdateFailed(f"Transient server error: {err}") from err
            # For other errors, log but don't fail the update
            _LOGGER.error(
                "Error fetching internal metrics for %s: %s", self.device_id, err
            )

        # Get settings inventory (cached, only needs to be fetched once)
        if self._settings_inventory is None:
            try:
                self._settings_inventory = self.api.get_settings_inventory(
                    self.device_id
                )

                # Debug: Log detailed information about all settings
                if self._settings_inventory and "settings" in self._settings_inventory:
                    _LOGGER.debug(
                        "Settings inventory for device %s contains %d settings",
                        self.device_id,
                        len(self._settings_inventory["settings"]),
                    )
                    for setting in self._settings_inventory["settings"]:
                        _LOGGER.debug(
                            "Setting: name=%s, data_type=%s, read_only=%s, min=%s, max=%s, step=%s, options=%s, description=%s",
                            setting.get("name"),
                            setting.get("data_type"),
                            setting.get("read_only", False),
                            setting.get("min"),
                            setting.get("max"),
                            setting.get("step"),
                            setting.get("options"),
                            setting.get("description", "")[
                                :100
                            ],  # Truncate long descriptions
                        )
            except QvantumApiError as err:
                _LOGGER.error(
                    "Error fetching settings inventory for %s: %s", self.device_id, err
                )
                self._settings_inventory = None

        data["settings_inventory"] = self._settings_inventory

        # Get metrics inventory (cached)
        if self._metrics_inventory is None:
            try:
                self._metrics_inventory = self.api.get_metrics_inventory(self.device_id)
                # Debug log to check smart_status metrics
                if self._metrics_inventory and "metrics" in self._metrics_inventory:
                    for metric in self._metrics_inventory["metrics"]:
                        # if "smart_status" in metric.get("name", ""):
                        _LOGGER.debug(
                            "Metric found: name=%s, description=%s, unit=%s, all_data=%s",
                            metric.get("name"),
                            metric.get("description"),
                            metric.get("unit"),
                            metric,
                        )
            except QvantumApiError as err:
                _LOGGER.error(
                    "Error fetching metrics inventory for %s: %s", self.device_id, err
                )
                self._metrics_inventory = None

        data["metrics_inventory"] = self._metrics_inventory

        # Get alarms
        try:
            alarms = self.api.get_alarms(self.device_id)
            data["alarms"] = alarms
        except QvantumApiError as err:
            _LOGGER.error("Error fetching alarms for %s: %s", self.device_id, err)
            data["alarms"] = {"alarms": []}

        # Get alarms inventory (cached, only needs to be fetched once)
        if self._alarms_inventory is None:
            try:
                self._alarms_inventory = self.api.get_alarms_inventory(self.device_id)
            except QvantumApiError as err:
                _LOGGER.error(
                    "Error fetching alarms inventory for %s: %s", self.device_id, err
                )
                self._alarms_inventory = None

        data["alarms_inventory"] = self._alarms_inventory

        # Get access level information
        try:
            access_level = self.api.get_access_level(self.device_id)
            data["access_level"] = access_level
            _LOGGER.debug(
                "Fetched access_level for %s: %s",
                self.device_id,
                access_level,
            )

            # Check if elevated access is about to expire (within 5 minutes)
            # Only auto-renew if auto_elevate_enabled is True
            if access_level.get("expiresAt") and self.auto_elevate_enabled:
                from datetime import datetime

                try:
                    expires_at = datetime.fromisoformat(
                        access_level["expiresAt"].replace("Z", "+00:00")
                    )
                    now = datetime.now(expires_at.tzinfo)
                    time_until_expiry = (expires_at - now).total_seconds()

                    # If elevated and expiring soon, re-elevate
                    if (
                        access_level.get("writeAccessLevel", 0) >= 20
                        and 0 < time_until_expiry < 300
                    ):  # Less than 5 minutes
                        _LOGGER.info(
                            "Auto-elevate enabled: Access expiring in %d seconds, re-elevating",
                            int(time_until_expiry),
                        )
                        try:
                            new_access = self.api.elevate_access(self.device_id)
                            if new_access:
                                data["access_level"] = new_access
                                _LOGGER.info(
                                    "Access re-elevated successfully, new expiry: %s",
                                    new_access.get("expiresAt"),
                                )
                        except QvantumApiError as elevate_err:
                            _LOGGER.warning(
                                "Failed to re-elevate access: %s", elevate_err
                            )
                except (ValueError, AttributeError) as parse_err:
                    _LOGGER.debug("Could not parse expiration time: %s", parse_err)

        except QvantumApiError as err:
            _LOGGER.debug("Error fetching access level for %s: %s", self.device_id, err)
            # Set default values if access level fetch fails
            data["access_level"] = {
                "writeAccessLevel": 10,  # Assume normal user level
                "readAccessLevel": 10,
                "expiresAt": None,
            }

        return data
