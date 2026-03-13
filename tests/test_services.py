"""Tests for Qvantum service actions."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.qvantum_hass.api import QvantumApiError
from custom_components.qvantum_hass.const import (
    DOMAIN,
    SERVICE_SET_ACCESS_LEVEL,
    SERVICE_TOGGLE_AUTO_ELEVATE,
)


async def test_set_access_level_service(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test set_access_level service call."""
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Call service
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_ACCESS_LEVEL,
            {
                "config_entry_id": mock_config_entry.entry_id,
                "device_id": "device_123",
                "access_level": "installer",
            },
            blocking=True,
        )

        # Verify API was called
        mock_api.set_access_level.assert_called_once_with("device_123", "installer")


async def test_set_access_level_invalid_config_entry(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test set_access_level with invalid config entry."""
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_ACCESS_LEVEL,
            {
                "config_entry_id": "invalid_entry_id",
                "device_id": "device_123",
                "access_level": "installer",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "service_entry_not_found"


async def test_set_access_level_api_error(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test set_access_level handles API errors."""
    mock_api.set_access_level.side_effect = QvantumApiError("API Error")

    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SET_ACCESS_LEVEL,
                {
                    "config_entry_id": mock_config_entry.entry_id,
                    "device_id": "device_123",
                    "access_level": "installer",
                },
                blocking=True,
            )
        assert exc_info.value.translation_key == "set_access_level_failed"


async def test_toggle_auto_elevate_service(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test toggle_auto_elevate service call."""
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Call service to enable
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TOGGLE_AUTO_ELEVATE,
            {
                "config_entry_id": mock_config_entry.entry_id,
                "device_id": "device_123",
                "enable": True,
            },
            blocking=True,
        )

        # Verify state was stored — use runtime_data instead of hass.data
        coordinator = mock_config_entry.runtime_data["coordinators"]["device_123"]
        assert coordinator.auto_elevate_enabled is True


async def test_toggle_auto_elevate_invalid_entry(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test toggle_auto_elevate with invalid config entry."""
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TOGGLE_AUTO_ELEVATE,
            {
                "config_entry_id": "invalid_entry_id",
                "device_id": "device_123",
                "enable": True,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "service_entry_not_found"


async def test_toggle_auto_elevate_error(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test toggle_auto_elevate raises HomeAssistantError on coordinator failure."""
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data["coordinators"]["device_123"]

    with patch.object(
        coordinator,
        "async_set_auto_elevate",
        side_effect=QvantumApiError("Storage error"),
    ):
        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_TOGGLE_AUTO_ELEVATE,
                {
                    "config_entry_id": mock_config_entry.entry_id,
                    "device_id": "device_123",
                    "enable": True,
                },
                blocking=True,
            )
        assert exc_info.value.translation_key == "toggle_auto_elevate_failed"


async def test_set_access_level_entry_not_loaded(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test set_access_level raises ServiceValidationError when entry is not loaded."""
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Unload the entry so state is NOT_LOADED
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_ACCESS_LEVEL,
            {
                "config_entry_id": mock_config_entry.entry_id,
                "device_id": "device_123",
                "access_level": "installer",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "service_entry_not_loaded"


async def test_toggle_auto_elevate_entry_not_loaded(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test toggle_auto_elevate raises ServiceValidationError when entry is not loaded."""
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Unload the entry so state is NOT_LOADED
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TOGGLE_AUTO_ELEVATE,
            {
                "config_entry_id": mock_config_entry.entry_id,
                "device_id": "device_123",
                "enable": True,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "service_entry_not_loaded"


async def test_toggle_auto_elevate_disable(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test toggle_auto_elevate service call with enable=False disables auto-elevate."""
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # First enable so we can verify the state actually transitions
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TOGGLE_AUTO_ELEVATE,
            {
                "config_entry_id": mock_config_entry.entry_id,
                "device_id": "device_123",
                "enable": True,
            },
            blocking=True,
        )
        coordinator = mock_config_entry.runtime_data["coordinators"]["device_123"]
        assert coordinator.auto_elevate_enabled is True

        # Now disable it
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TOGGLE_AUTO_ELEVATE,
            {
                "config_entry_id": mock_config_entry.entry_id,
                "device_id": "device_123",
                "enable": False,
            },
            blocking=True,
        )

    assert coordinator.auto_elevate_enabled is False
