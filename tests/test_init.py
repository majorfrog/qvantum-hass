"""Tests for Qvantum integration setup and coordinators."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.qvantum_hass.api import ApiConnectionError, AuthenticationError


async def test_setup_success(hass: HomeAssistant, mock_config_entry, mock_api):
    """Test successful integration setup."""
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.LOADED
        assert mock_config_entry.runtime_data is not None


async def test_setup_authentication_failure(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test setup fails with authentication error."""
    mock_api.authenticate.side_effect = AuthenticationError("Invalid token")

    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_setup_connection_error_raises_not_ready(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test setup results in SETUP_RETRY on connection errors."""
    mock_api.authenticate.side_effect = ApiConnectionError(
        "Connection timeout", status_code=503
    )

    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant, mock_config_entry, mock_api):
    """Test unloading a config entry."""
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.LOADED

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
        mock_api.close.assert_called_once()


async def test_coordinator_updates_data(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test that coordinator fetches and updates data."""
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify coordinator has data
        coordinator = mock_config_entry.runtime_data["coordinators"]["device_123"]
        assert coordinator.data is not None
        assert "status" in coordinator.data
        assert "settings" in coordinator.data


async def test_fast_coordinator_updates_metrics(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test that fast coordinator fetches metrics."""
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify fast coordinator has data
        fast_coordinator = mock_config_entry.runtime_data["fast_coordinators"][
            "device_123"
        ]
        assert fast_coordinator.data is not None
        assert "internal_metrics" in fast_coordinator.data


async def test_coordinator_update_failure_marks_coordinator_unavailable(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test that a coordinator marks last_update_success=False when fetching fails."""
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state == ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data["coordinators"]["device_123"]

    # A plain Exception from get_status is not caught by the coordinator's
    # QvantumApiError handler and propagates out of _async_update_data,
    # causing the DataUpdateCoordinator to set last_update_success=False.
    mock_api.get_status.side_effect = Exception("network failure")

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success


async def test_fast_coordinator_preserves_data_on_transient_server_error(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test that the fast coordinator keeps previous metrics on 5xx server errors."""
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state == ConfigEntryState.LOADED

    fast_coordinator = mock_config_entry.runtime_data["fast_coordinators"]["device_123"]

    # Record the data from the initial successful fetch
    previous_metrics = dict(fast_coordinator.data.get("internal_metrics", {}))
    assert previous_metrics, "Expected initial internal_metrics to be populated"

    # Simulate a transient 5xx server error on the next poll
    mock_api.get_internal_metrics.side_effect = ApiConnectionError(
        "Gateway timeout", status_code=504
    )

    await fast_coordinator.async_refresh()
    await hass.async_block_till_done()

    # The fast coordinator keeps old data and does NOT raise UpdateFailed
    assert fast_coordinator.last_update_success
    # Previous metric values must still be present
    assert fast_coordinator.data["internal_metrics"] == previous_metrics


async def test_fast_coordinator_update_failure_on_unrecoverable_error(
    hass: HomeAssistant, mock_config_entry, mock_api
):
    """Test that the fast coordinator marks last_update_success=False on unexpected errors."""
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state == ConfigEntryState.LOADED

    fast_coordinator = mock_config_entry.runtime_data["fast_coordinators"]["device_123"]

    # An exception that is NOT a QvantumApiError propagates through the coordinator
    mock_api.get_internal_metrics.side_effect = RuntimeError(
        "unexpected internal error"
    )

    await fast_coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not fast_coordinator.last_update_success
