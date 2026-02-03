"""Base entity classes for Qvantum Heat Pump integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import QvantumDataUpdateCoordinator
from .const import DOMAIN, MANUFACTURER


def create_device_info(device: dict[str, Any]) -> DeviceInfo:
    """Create standard device info for Qvantum entities.

    Args:
        device: Device dictionary containing id, serial, model, etc.

    Returns:
        Device info dictionary for entity registration.

    """
    return {
        "identifiers": {(DOMAIN, device["id"])},
        "name": f"Qvantum Heat Pump {device['serial']}",
        "manufacturer": MANUFACTURER,
        "model": device.get("model", "Heat Pump"),
        "serial_number": device["serial"],
    }


class QvantumEntity(CoordinatorEntity[QvantumDataUpdateCoordinator]):
    """Base entity class for all Qvantum entities.

    Provides common functionality shared across all entity types including:
    - Device information setup
    - Availability checking based on connectivity
    - Reference to device and API

    """

    _attr_has_entity_name = True

    @staticmethod
    def get_available_setting_names(coordinator_data: dict[str, Any]) -> set[str]:
        """Get list of settings that are actually returned by the API.

        Many settings in the settings_inventory aren't actually readable/writable.
        This function extracts the names of settings that are available in the
        actual API response.

        Args:
            coordinator_data: The coordinator.data dictionary containing settings.

        Returns:
            Set of available setting names, or empty set if none found.

        """
        if (
            coordinator_data
            and "settings" in coordinator_data
            and "settings" in coordinator_data["settings"]
        ):
            return {s["name"] for s in coordinator_data["settings"]["settings"]}
        return set()

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: Any,
    ) -> None:
        """Initialize the base Qvantum entity

        Args:
            coordinator: Data update coordinator instance.
            device: Device dictionary containing id, serial, model, etc.
            api: Qvantum API instance.

        """
        super().__init__(coordinator)
        self._device = device
        self._api = api
        self._attr_device_info = create_device_info(device)

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Checks both coordinator update success and device connectivity status.

        Returns:
            True if entity is available, False otherwise.

        """
        if not self.coordinator.last_update_success:
            return False

        # Check connectivity status
        if (
            self.coordinator.data
            and "status" in self.coordinator.data
            and "connectivity" in self.coordinator.data["status"]
        ):
            connectivity = self.coordinator.data["status"]["connectivity"]
            return connectivity.get("connected", False)

        return True
