"""Base entity classes for Qvantum Heat Pump integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import QvantumDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def create_device_info(device: dict[str, Any]) -> DeviceInfo:
    """Create standard device info for Qvantum entities.

    Args:
        device: Device dictionary containing id, serial_number, model, etc.
            The key is ``serial_number`` when the dict comes from Pydantic
            ``model_dump()``, ``serialNumber`` in raw API fallback responses.

    Returns:
        Device info dictionary for entity registration.

    """
    # Pydantic model_dump() → serial_number; raw API fallback → serialNumber
    serial = (
        device.get("serial_number")
        or device.get("serialNumber")
        or device.get("serial", "")
    )
    model = device.get("model", "Heat Pump")
    return DeviceInfo(
        identifiers={(DOMAIN, device["id"])},
        name=model,
        manufacturer=MANUFACTURER,
        model=model,
        serial_number=serial or None,
    )


class QvantumEntity(CoordinatorEntity[QvantumDataUpdateCoordinator]):
    """Base entity class for all Qvantum entities.

    Provides common functionality shared across all entity types including:
    - Device information setup
    - Availability checking based on connectivity
    - Reference to device and API

    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: Any,
    ) -> None:
        """Initialize the base Qvantum entity.

        Args:
            coordinator: Data update coordinator instance.
            device: Device dictionary containing id, serial, model, etc.
            api: Qvantum API instance.
        """
        super().__init__(coordinator)
        self._device = device
        self._api = api
        self._attr_device_info = create_device_info(device)
        self._unavailable_logged = False

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
            connected = connectivity.get("connected", False)
            if not connected:
                if not self._unavailable_logged:
                    _LOGGER.info(
                        "Device %s is not connected",
                        self._device.get("id", "unknown"),
                    )
                    self._unavailable_logged = True
                return False
            if self._unavailable_logged:
                _LOGGER.info(
                    "Device %s is back online",
                    self._device.get("id", "unknown"),
                )
                self._unavailable_logged = False

        return True
