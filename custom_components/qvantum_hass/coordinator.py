"""Data update coordinator for the Qvantum Heat Pump integration.

This module owns the coordinator class and the CachedValue helper. It sits
between const/api (which it imports) and the platform files (which import
it), enabling definitions.py to import platform files without a cycle.

Import hierarchy (no cycles):
    models.py  ←  const.py  ←  api.py
                           ←  coordinator.py  ←  entity.py
                                              ←  platform files
                                                  ↑
                                             definitions.py
                                                  ↑
                                             __init__.py
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from typing import Any, Generic, TypeVar

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ApiClientError, ApiConnectionError, QvantumApi, QvantumApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Cache TTL for inventory data (24 hours)
INVENTORY_CACHE_TTL = timedelta(hours=24)

T = TypeVar("T")


class CachedValue(Generic[T]):
    """Generic cached value with TTL support.

    Provides automatic expiration and refresh capability for expensive
    API calls like inventory fetching.
    """

    def __init__(self, ttl: timedelta) -> None:
        """Initialize cached value.

        Args:
            ttl: Time to live for cached value
        """
        self.ttl = ttl
        self.value: T | None = None
        self.expires_at: datetime | None = None

    def set(self, value: T) -> None:
        """Set the cached value."""
        self.value = value
        self.expires_at = datetime.now(tz=UTC) + self.ttl

    def get(self) -> T | None:
        """Get the cached value if not expired."""
        if self.value is None:
            return None

        if self.expires_at is None:
            return None

        if datetime.now(tz=UTC) >= self.expires_at:
            # Expired
            self.value = None
            self.expires_at = None
            return None

        return self.value

    def is_cached(self) -> bool:
        """Check if we have a valid cached value."""
        return self.get() is not None


class QvantumDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data update coordinator for Qvantum devices.

    This coordinator manages periodic data fetching from the Qvantum API
    for a single device. Two instances are created per device:

    - **Normal** (``fetch_full_data=True``): slow interval, fetches settings,
      alarms, inventories, access level, and all internal metrics.
    - **Fast** (``fetch_full_data=False``): rapid interval, fetches only the
      real-time metric values assigned to it via ``metrics``.

    Entities with ``fast_polling=True`` subscribe to the fast coordinator;
    all other entities subscribe to the normal coordinator.

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
        config_entry: Any = None,
        metrics: tuple[str, ...] = (),
        fetch_full_data: bool = True,
    ) -> None:
        """Initialize the data update coordinator.

        Args:
            hass: Home Assistant instance
            api: Qvantum API client (now async)
            device_id: Unique device identifier
            update_interval: How often to fetch updates
            store: Storage for persisting auto-elevate state
            config_entry: Config entry associated with this coordinator.
            metrics: Metric names this coordinator should fetch.
            fetch_full_data: If True, also fetches settings, alarms, access
                level, and inventory data. Set to False for fast coordinators
                that only need real-time metric values.
        """
        self.api = api
        self.device_id = device_id
        self._store = store
        self._metrics = metrics
        self._fetch_full_data = fetch_full_data
        # Backoff tracking: track the base interval and consecutive failures so
        # that transient server errors don't hammer the API at full polling rate.
        self._base_update_interval = update_interval
        self._consecutive_failures = 0

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}_{'normal' if fetch_full_data else 'fast'}",
            update_interval=update_interval,
            config_entry=config_entry,
        )
        # Initialize cached inventories with TTL (Issue #18)
        # Fast coordinators (fetch_full_data=False) don't need inventories
        if fetch_full_data:
            self._settings_inventory: CachedValue[dict[str, Any]] = CachedValue(
                INVENTORY_CACHE_TTL
            )
            self._metrics_inventory: CachedValue[dict[str, Any]] = CachedValue(
                INVENTORY_CACHE_TTL
            )
            self._alarms_inventory: CachedValue[dict[str, Any]] = CachedValue(
                INVENTORY_CACHE_TTL
            )
        # Auto-elevate access control flag - will be loaded from store
        # Default to False for new devices
        self.auto_elevate_enabled = False
        # Linked coordinator (e.g. fast ↔ normal) that must stay in sync
        self._linked_coordinator: QvantumDataUpdateCoordinator | None = None

    def set_linked_coordinator(
        self, coordinator: QvantumDataUpdateCoordinator
    ) -> None:
        """Link another coordinator to keep auto_elevate_enabled in sync."""
        self._linked_coordinator = coordinator

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

    def _apply_backoff(self, error: Exception) -> None:
        """Increment the failure counter and double the polling interval up to a cap."""
        self._consecutive_failures += 1
        # Double the interval per failure, capped at 32× the base (roughly 16 minutes
        # at the default 30 s interval).
        multiplier = min(2**self._consecutive_failures, 32)
        self.update_interval = self._base_update_interval * multiplier
        _LOGGER.warning(
            "Transient error for %s (%s), back-off applied: next update in %s s",
            self.device_id,
            error,
            int(self.update_interval.total_seconds()),
        )

    async def async_set_auto_elevate(self, enabled: bool) -> None:
        """Set auto-elevate state and persist to storage."""
        self.auto_elevate_enabled = enabled
        if self._linked_coordinator is not None:
            self._linked_coordinator.auto_elevate_enabled = enabled

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

    async def _async_update_data(self) -> dict[str, Any]:  # noqa: C901
        """Fetch data from API (async, no executor needed)."""
        data = {}

        # Fast coordinator only fetches the assigned real-time metrics
        if not self._fetch_full_data:
            try:
                metrics = await self.api.get_internal_metrics(
                    self.device_id, list(self._metrics)
                )
                # Extract just the values dict from the response
                if isinstance(metrics, dict) and "values" in metrics:
                    data["internal_metrics"] = metrics["values"]
                else:
                    data["internal_metrics"] = metrics
            except QvantumApiError as err:
                # For transient server errors, keep previous data to avoid entities becoming unavailable
                # Use status_code check instead of string parsing (Issue #4)
                if isinstance(err, ApiConnectionError) and (
                    err.status_code is None or err.status_code >= 500
                ):
                    _LOGGER.debug(
                        "Transient server error (status %s) fetching fast metrics for %s, keeping previous values: %s",
                        err.status_code,
                        self.device_id,
                        err,
                    )
                    self._apply_backoff(err)
                    # Return previous data if available, otherwise empty
                    if self.data and "internal_metrics" in self.data:
                        data["internal_metrics"] = self.data["internal_metrics"]
                else:
                    # For other errors, log but don't fail the update
                    _LOGGER.debug(
                        "Error fetching fast metrics for %s: %s", self.device_id, err
                    )
            return data

        # Normal coordinator fetches all data
        # If auto-elevate is enabled, ensure we have elevated access before fetching data
        # This allows reading advanced settings that require service tech access
        if self.auto_elevate_enabled:
            try:
                current_access = await self.api.get_access_level(self.device_id)
                if current_access.get("writeAccessLevel", 0) < 20:
                    _LOGGER.debug(
                        "Auto-elevate enabled but access level is %s, elevating",
                        current_access.get("writeAccessLevel"),
                    )
                    await self.api.elevate_access(self.device_id)
            except QvantumApiError as err:
                _LOGGER.debug("Could not check/elevate access level: %s", err)

        # Get status (optional - some devices may not support this endpoint)
        try:
            status = await self.api.get_status(self.device_id)
            data["status"] = status
        except ApiConnectionError as err:
            # Transient server errors - raise to trigger retry (Issue #2)
            if err.status_code is None or err.status_code >= 500:
                _LOGGER.warning(
                    "Server error fetching status for %s (status %s), will retry",
                    self.device_id,
                    err.status_code,
                )
                self._apply_backoff(err)
                raise UpdateFailed(f"Transient error fetching status: {err}") from err
            # 4xx errors - endpoint not available or not supported
            _LOGGER.debug(
                "Status endpoint not available for %s (status %s): %s",
                self.device_id,
                err.status_code,
                err,
            )
        except ApiClientError as err:
            # 4xx client errors - not available or permission issue
            _LOGGER.debug(
                "Status endpoint not available for %s (status %s): %s",
                self.device_id,
                err.status_code,
                err,
            )
        except QvantumApiError as err:
            # Other errors - log and continue without status
            _LOGGER.debug("Status endpoint error for %s: %s", self.device_id, err)

        # Get settings (optional but important - some devices may not support this endpoint)
        try:
            settings = await self.api.get_settings(self.device_id)
            data["settings"] = settings

        except ApiConnectionError as err:
            # Transient server errors - raise to trigger retry (Issue #2)
            if err.status_code is None or err.status_code >= 500:
                _LOGGER.warning(
                    "Server error fetching settings for %s (status %s), will retry",
                    self.device_id,
                    err.status_code,
                )
                self._apply_backoff(err)
                raise UpdateFailed(f"Transient error fetching settings: {err}") from err
            # 4xx errors - endpoint not available or not supported
            _LOGGER.debug(
                "Settings endpoint not available for %s (status %s): %s",
                self.device_id,
                err.status_code,
                err,
            )
        except ApiClientError as err:
            # 4xx client errors - not available or permission issue
            _LOGGER.debug(
                "Settings endpoint not available for %s (status %s): %s",
                self.device_id,
                err.status_code,
                err,
            )
        except QvantumApiError as err:
            # Other errors - log and continue without settings
            _LOGGER.debug("Settings endpoint error for %s: %s", self.device_id, err)

        # Get internal metrics
        try:
            metrics = await self.api.get_internal_metrics(
                self.device_id, list(self._metrics)
            )
            # Extract just the values dict from the response
            if isinstance(metrics, dict) and "values" in metrics:
                data["internal_metrics"] = metrics["values"]
            else:
                data["internal_metrics"] = metrics
        except QvantumApiError as err:
            # For transient server errors, keep previous data to avoid entities becoming unavailable
            # Use status_code check instead of string parsing (Issue #4)
            if isinstance(err, ApiConnectionError) and (
                err.status_code is None or err.status_code >= 500
            ):
                _LOGGER.debug(
                    "Transient server error (status %s) fetching internal metrics for %s, keeping previous values: %s",
                    err.status_code,
                    self.device_id,
                    err,
                )
                # Keep previous data if available
                if self.data and "internal_metrics" in self.data:
                    data["internal_metrics"] = self.data["internal_metrics"]
            else:
                # For other errors, log at debug level to avoid log spam
                _LOGGER.debug(
                    "Error fetching internal metrics for %s: %s", self.device_id, err
                )

        # Get settings inventory (cached with TTL - Issue #18)
        if not self._settings_inventory.is_cached():
            try:
                settings_inv = await self.api.get_settings_inventory(self.device_id)
                self._settings_inventory.set(settings_inv)

                # Debug: Log detailed information about all settings
                if settings_inv and "settings" in settings_inv:
                    _LOGGER.debug(
                        "Settings inventory for device %s contains %d settings",
                        self.device_id,
                        len(settings_inv["settings"]),
                    )
                    for setting in settings_inv["settings"]:
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
                _LOGGER.debug(
                    "Error fetching settings inventory for %s: %s", self.device_id, err
                )

        data["settings_inventory"] = self._settings_inventory.get()

        # Get metrics inventory (cached with TTL - Issue #18)
        if not self._metrics_inventory.is_cached():
            try:
                metrics_inv = await self.api.get_metrics_inventory(self.device_id)
                self._metrics_inventory.set(metrics_inv)
                # Debug log to check smart_status metrics
                if metrics_inv and "metrics" in metrics_inv:
                    for metric in metrics_inv["metrics"]:
                        _LOGGER.debug(
                            "Metric found: name=%s, description=%s, unit=%s",
                            metric.get("name"),
                            metric.get("description"),
                            metric.get("unit"),
                        )
            except QvantumApiError as err:
                _LOGGER.debug(
                    "Error fetching metrics inventory for %s: %s", self.device_id, err
                )

        data["metrics_inventory"] = self._metrics_inventory.get()

        # Get alarms
        try:
            alarms = await self.api.get_alarms(self.device_id)
            data["alarms"] = alarms
        except QvantumApiError as err:
            _LOGGER.debug("Error fetching alarms for %s: %s", self.device_id, err)
            data["alarms"] = {"alarms": []}

        # Get alarms inventory (cached with TTL - Issue #18)
        if not self._alarms_inventory.is_cached():
            try:
                alarms_inv = await self.api.get_alarms_inventory(self.device_id)
                self._alarms_inventory.set(alarms_inv)
            except QvantumApiError as err:
                _LOGGER.debug(
                    "Error fetching alarms inventory for %s: %s", self.device_id, err
                )

        data["alarms_inventory"] = self._alarms_inventory.get()

        # Get access level information
        try:
            access_level = await self.api.get_access_level(self.device_id)
            data["access_level"] = access_level

            # Check if elevated access is about to expire (within 5 minutes)
            # Only auto-renew if auto_elevate_enabled is True
            if access_level.get("expiresAt") and self.auto_elevate_enabled:
                try:
                    expires_at = datetime.fromisoformat(access_level["expiresAt"])
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
                            new_access = await self.api.elevate_access(self.device_id)
                            if new_access:
                                data["access_level"] = new_access
                                _LOGGER.info(
                                    "Access re-elevated successfully, new expiry: %s",
                                    new_access.get("expiresAt"),
                                )
                        except QvantumApiError as elevate_err:
                            _LOGGER.debug(
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

        # Reset back-off on a successful full update.
        if self._consecutive_failures > 0:
            self._consecutive_failures = 0
            if self.update_interval != self._base_update_interval:
                self.update_interval = self._base_update_interval
                _LOGGER.info(
                    "Back-off cleared: resuming normal update interval for %s",
                    self.device_id,
                )

        return data
