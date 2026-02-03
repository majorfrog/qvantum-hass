"""Button platform for Qvantum Heat Pump integration.

This module provides button entities for one-time actions on the heat pump:
- Extra hot water activation (1 hour)
- Manual sensor refresh
- Service technician access elevation

Buttons provide immediate actions without maintaining state, perfect
for triggering temporary modes or manual operations.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import QvantumDataUpdateCoordinator
from .api import QvantumApiError
from .const import DOMAIN
from .entity import QvantumEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qvantum button entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    devices = data["devices"]
    api = data["api"]

    entities = []

    for device in devices:
        device_id = device["id"]
        coordinator = coordinators[device_id]

        # Add extra hot water button (1 hour)
        entities.append(
            QvantumExtraHotWaterButton(
                coordinator,
                device,
                api,
            )
        )

        # Add refresh button
        entities.append(
            QvantumRefreshButton(
                coordinator,
                device,
            )
        )

        # Add elevate access button
        entities.append(
            QvantumElevateAccessButton(
                coordinator,
                device,
                api,
            )
        )

    async_add_entities(entities)


class QvantumExtraHotWaterButton(QvantumEntity, ButtonEntity):
    """Button entity for extra hot water control (1 hour)."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: Any,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator, device, api)
        self._attr_translation_key = "extra_hot_water_1h"
        self._attr_unique_id = f"qvantum_{device['id']}_extra_hot_water_1h"
        self._attr_icon = "mdi:water-boiler-auto"

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.hass.async_add_executor_job(
                self._api.set_extra_hot_water,
                self._device["id"],
                1,  # 1 hour
                False,  # Not indefinite
            )
            _LOGGER.info(
                "Activated extra hot water for 1 hour on device %s",
                self._device["id"],
            )
            # Request immediate update
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to activate extra hot water: %s",
                err,
            )


class QvantumRefreshButton(QvantumEntity, ButtonEntity):
    """Button entity to refresh sensor data immediately."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator, device, None)
        self._attr_translation_key = "refresh_sensors"
        self._attr_unique_id = f"qvantum_{device['id']}_refresh"
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Refreshing sensor data for device %s", self._device["id"])
        await self.coordinator.async_request_refresh()


class QvantumElevateAccessButton(QvantumEntity, ButtonEntity):
    """Button entity to elevate access level to service technician."""

    def __init__(
        self,
        coordinator: QvantumDataUpdateCoordinator,
        device: dict[str, Any],
        api: Any,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator, device, api)
        self._attr_translation_key = "elevate_access_level"
        self._attr_unique_id = f"qvantum_{device['id']}_elevate_access"
        self._attr_icon = "mdi:shield-key"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Handle the button press - elevate access to service technician level."""
        try:
            _LOGGER.info("Elevating access level for device %s", self._device["id"])
            result = await self.hass.async_add_executor_job(
                self._api.elevate_access,
                self._device["id"],
            )
            _LOGGER.info(
                "Access elevated successfully. New access level: %s, expires at: %s",
                result.get("writeAccessLevel"),
                result.get("expiresAt"),
            )
            # Request immediate update to refresh access level sensors
            await self.coordinator.async_request_refresh()
        except QvantumApiError as err:
            _LOGGER.error(
                "Failed to elevate access level: %s",
                err,
            )
