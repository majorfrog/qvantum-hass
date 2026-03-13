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

import asyncio
from datetime import timedelta
import logging
from typing import Any, TypedDict

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .api import ApiConnectionError, AuthenticationError, QvantumApi, QvantumApiError
from .const import (
    DEFAULT_API_KEY,
    DEFAULT_FAST_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_ACTIVATE_EXTRA_HOT_WATER,
    SERVICE_CANCEL_EXTRA_HOT_WATER,
    SERVICE_SET_ACCESS_LEVEL,
    SERVICE_TOGGLE_AUTO_ELEVATE,
)
from .coordinator import (
    QvantumDataUpdateCoordinator,
)
from .definitions import get_fast_polling_metrics, get_metric_names

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


class QvantumRuntimeData(TypedDict):
    """Typed runtime data stored on a Qvantum config entry."""

    api: QvantumApi
    coordinators: dict[str, QvantumDataUpdateCoordinator]
    fast_coordinators: dict[str, QvantumDataUpdateCoordinator]
    devices: list[dict[str, Any]]


type QvantumConfigEntry = ConfigEntry[QvantumRuntimeData]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# ---------------------------------------------------------------------------
# Service call schemas — validated by HA before handlers are invoked.
# ---------------------------------------------------------------------------

_SCHEMA_SET_ACCESS_LEVEL = vol.Schema(
    {
        vol.Required("config_entry_id"): cv.string,
        vol.Required("device_id"): cv.string,
        vol.Required("access_level"): cv.string,
    }
)

_SCHEMA_TOGGLE_AUTO_ELEVATE = vol.Schema(
    {
        vol.Required("config_entry_id"): cv.string,
        vol.Required("device_id"): cv.string,
        vol.Required("enable"): cv.boolean,
    }
)

_SCHEMA_ACTIVATE_EXTRA_HOT_WATER = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Optional("duration", default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=24)
        ),
    }
)

_SCHEMA_CANCEL_EXTRA_HOT_WATER = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Set up the Qvantum integration.

    Registers all integration-level service actions that are available
    regardless of how many config entries are loaded.  Each handler
    validates its inputs and raises ``ServiceValidationError`` or
    ``HomeAssistantError`` as appropriate.
    """

    async def handle_set_access_level(call: ServiceCall) -> None:
        """Handle the set_access_level service call."""
        entry_id = call.data["config_entry_id"]
        device_id = call.data["device_id"]
        access_level = call.data["access_level"]

        entry = hass.config_entries.async_get_entry(entry_id)
        if not entry:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_entry_not_found",
                translation_placeholders={"entry_id": entry_id},
            )

        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_entry_not_loaded",
                translation_placeholders={"entry_id": entry_id},
            )

        api = entry.runtime_data["api"]

        try:
            await api.set_access_level(device_id, access_level)
        except QvantumApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_access_level_failed",
            ) from err

    async def handle_toggle_auto_elevate(call: ServiceCall) -> None:
        """Handle the toggle_auto_elevate service call."""
        entry_id = call.data["config_entry_id"]
        device_id = call.data["device_id"]
        enable = call.data["enable"]

        entry = hass.config_entries.async_get_entry(entry_id)
        if not entry:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_entry_not_found",
                translation_placeholders={"entry_id": entry_id},
            )

        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_entry_not_loaded",
                translation_placeholders={"entry_id": entry_id},
            )

        coordinators = entry.runtime_data.get("coordinators", {})
        coordinator = coordinators.get(device_id)
        if coordinator is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_device_not_found",
                translation_placeholders={
                    "device_id": device_id,
                    "entry_id": entry_id,
                },
            )

        try:
            await coordinator.async_set_auto_elevate(enable)
        except QvantumApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="toggle_auto_elevate_failed",
            ) from err

    async def handle_activate_extra_hot_water(call: ServiceCall) -> None:
        """Handle the activate_extra_hot_water service call."""
        device_id = call.data["device_id"]
        duration = call.data.get("duration", 1)

        # Find which loaded entry owns this device_id.
        # Iterating all entries allows the service to work without requiring
        # a config_entry_id field, keeping backward compatibility.
        api = None
        coordinators_for_device = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is not ConfigEntryState.LOADED or not entry.runtime_data:
                continue
            entry_coordinators = entry.runtime_data.get("coordinators", {})
            if device_id in entry_coordinators:
                api = entry.runtime_data["api"]
                coordinators_for_device = entry_coordinators
                break

        if api is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_unknown_device",
                translation_placeholders={"device_id": device_id},
            )

        try:
            await api.set_extra_hot_water(device_id, duration)
            _LOGGER.info(
                "Activated extra hot water for %d hours on device %s",
                duration,
                device_id,
            )
            if coordinators_for_device and device_id in coordinators_for_device:
                await coordinators_for_device[device_id].async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to activate extra hot water on device %s: %s",
                device_id,
                err,
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="activate_extra_hot_water_failed",
            ) from err

    async def handle_cancel_extra_hot_water(call: ServiceCall) -> None:
        """Handle the cancel_extra_hot_water service call."""
        device_id = call.data["device_id"]

        # Find which loaded entry owns this device_id.
        api = None
        coordinators_for_device = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is not ConfigEntryState.LOADED or not entry.runtime_data:
                continue
            entry_coordinators = entry.runtime_data.get("coordinators", {})
            if device_id in entry_coordinators:
                api = entry.runtime_data["api"]
                coordinators_for_device = entry_coordinators
                break

        if api is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_unknown_device",
                translation_placeholders={"device_id": device_id},
            )

        try:
            await api.set_extra_hot_water(device_id, 0)  # 0 hours = cancel
            _LOGGER.info("Cancelled extra hot water on device %s", device_id)
            if coordinators_for_device and device_id in coordinators_for_device:
                await coordinators_for_device[device_id].async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to cancel extra hot water on device %s: %s",
                device_id,
                err,
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cancel_extra_hot_water_failed",
            ) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ACCESS_LEVEL,
        handle_set_access_level,
        schema=_SCHEMA_SET_ACCESS_LEVEL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_TOGGLE_AUTO_ELEVATE,
        handle_toggle_auto_elevate,
        schema=_SCHEMA_TOGGLE_AUTO_ELEVATE,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ACTIVATE_EXTRA_HOT_WATER,
        handle_activate_extra_hot_water,
        schema=_SCHEMA_ACTIVATE_EXTRA_HOT_WATER,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_EXTRA_HOT_WATER,
        handle_cancel_extra_hot_water,
        schema=_SCHEMA_CANCEL_EXTRA_HOT_WATER,
    )

    return True


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
    # Create API instance
    api = QvantumApi(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        api_key=DEFAULT_API_KEY,
        session=async_get_clientsession(hass),
    )

    # Try to authenticate
    try:
        await api.authenticate()
    except AuthenticationError as err:
        await api.close()
        raise ConfigEntryAuthFailed from err
    except ApiConnectionError as err:
        await api.close()
        raise ConfigEntryNotReady from err

    # Get devices
    try:
        devices = await api.get_devices()
    except QvantumApiError as err:
        await api.close()
        raise ConfigEntryNotReady from err

    if not devices:
        _LOGGER.warning("No devices found for account")
        await api.close()
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="setup_no_devices",
        )

    # Remove device-registry entries that no longer exist in the account.
    # This prevents orphaned entities from accumulating when a device is deleted
    # from the user's Qvantum account.
    current_device_ids = {d["id"] for d in devices}
    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        # Identify the device by the domain+device-id identifier we set during setup.
        entry_device_ids = {
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        }
        if entry_device_ids and not entry_device_ids.intersection(current_device_ids):
            _LOGGER.info(
                "Removing stale device %s (no longer in Qvantum account)",
                entry_device_ids,
            )
            device_registry.async_update_device(
                device_entry.id,
                remove_config_entry_id=entry.entry_id,
            )

    # Create coordinators for each device
    # We use two coordinators per device:
    # 1. Fast coordinator (5s default) for power/current sensors
    # 2. Normal coordinator (30s default) for other sensors
    coordinators = {}
    fast_coordinators = {}
    scan_interval = DEFAULT_SCAN_INTERVAL
    fast_scan_interval = DEFAULT_FAST_SCAN_INTERVAL

    # Create shared storage for auto_elevate state
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")

    for device in devices:
        # Normal coordinator: full data fetch (settings, alarms, access level, etc.)
        # plus all internal metrics at the configured slow interval.
        #
        # fetch_full_data=True is necessary because the normal coordinator calls
        # several distinct API endpoints beyond get_internal_metrics: get_status,
        # get_settings, get_settings_inventory, get_metrics_inventory, get_alarms,
        # get_alarms_inventory, and get_access_level. These are separate REST
        # endpoints — they cannot be collapsed into the metrics list.
        coordinator = QvantumDataUpdateCoordinator(
            hass,
            api,
            device["id"],
            update_interval=timedelta(seconds=scan_interval),
            store=store,
            config_entry=entry,
            metrics=get_metric_names(),
            fetch_full_data=True,
        )

        # Fast coordinator: only the real-time power/current metrics at a rapid interval.
        # Entities with fast_polling=True subscribe to this coordinator.
        fast_coordinator = QvantumDataUpdateCoordinator(
            hass,
            api,
            device["id"],
            update_interval=timedelta(seconds=fast_scan_interval),
            store=store,
            config_entry=entry,
            metrics=get_fast_polling_metrics(),
            fetch_full_data=False,
        )

        # Load auto_elevate state from storage (shared between coordinators)
        await coordinator.async_load_auto_elevate_state()
        # Fast coordinator shares the same auto_elevate state
        fast_coordinator.auto_elevate_enabled = coordinator.auto_elevate_enabled
        # Link coordinators so auto_elevate stays in sync when toggled at runtime
        coordinator.set_linked_coordinator(fast_coordinator)

        # Fetch initial data for both coordinators with timeout protection (Issue #7)
        try:
            _LOGGER.debug("Attempting first refresh for device %s", device["id"])
            # Add 60-second timeout to prevent hanging indefinitely
            async with asyncio.timeout(60):
                await coordinator.async_config_entry_first_refresh()
                await fast_coordinator.async_config_entry_first_refresh()
            _LOGGER.debug("First refresh successful for device %s", device["id"])
        except TimeoutError as err:
            raise ConfigEntryNotReady(
                f"Device {device['id']} not responding (timeout)"
            ) from err
        except ConfigEntryAuthFailed:
            raise
        except Exception as err:  # TODO remove this broad catch?
            _LOGGER.warning(
                "Failed first refresh for device %s: %s",
                device["id"],
                err,
            )
            raise ConfigEntryNotReady(
                f"Unexpected error during first refresh for device {device['id']}: {err}"
            ) from err

        coordinators[device["id"]] = coordinator
        fast_coordinators[device["id"]] = fast_coordinator

    entry.runtime_data = {
        "api": api,
        "coordinators": coordinators,
        "fast_coordinators": fast_coordinators,
        "devices": devices,
    }

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if entry.runtime_data:
            await entry.runtime_data["api"].close()

    return unload_ok
