"""Tests for Qvantum config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResultType

from custom_components.qvantum_hass.api import (
    ApiConnectionError,
    AuthenticationError,
    QvantumApiError,
)
from custom_components.qvantum_hass.const import DOMAIN

# Import test credentials from fixtures (loaded dynamically in conftest)
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test_password_123"
TEST_USER_INPUT = {
    CONF_EMAIL: TEST_EMAIL,
    CONF_PASSWORD: TEST_PASSWORD,
}


async def test_user_flow_success(hass, mock_api_constructor):
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Qvantum Heat Pump"
    assert result["data"][CONF_EMAIL] == TEST_EMAIL
    assert result["data"][CONF_PASSWORD] == TEST_PASSWORD


async def test_user_flow_authentication_error(hass, mock_api):
    """Test authentication error during config flow."""
    mock_api.authenticate.side_effect = AuthenticationError("Invalid credentials")

    with patch(
        "custom_components.qvantum_hass.config_flow.QvantumApi",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=TEST_USER_INPUT
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_connection_error(hass, mock_api):
    """Test connection error during config flow."""
    mock_api.authenticate.side_effect = ApiConnectionError("Connection timeout")

    with patch(
        "custom_components.qvantum_hass.config_flow.QvantumApi",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=TEST_USER_INPUT
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unknown_error(hass, mock_api):
    """Test unknown error during config flow."""
    mock_api.authenticate.side_effect = QvantumApiError("Unknown error")

    with patch(
        "custom_components.qvantum_hass.config_flow.QvantumApi",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=TEST_USER_INPUT
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}


async def test_duplicate_entry(hass, mock_api_constructor):
    """Test that duplicate entries are prevented."""
    # Create first entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Try to create duplicate
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Reauth flow
# ---------------------------------------------------------------------------


async def test_reauth_flow_success(hass, mock_config_entry, mock_api):
    """Test successful reauthentication flow."""
    with patch(
        "custom_components.qvantum_hass.config_flow.QvantumApi",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
            },
            data=mock_config_entry.data,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "new_password_456"},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password_456"


async def test_reauth_flow_wrong_credentials(hass, mock_config_entry, mock_api):
    """Test reauth flow shows error when credentials are invalid."""
    mock_api.authenticate.side_effect = AuthenticationError("Bad creds")

    with patch(
        "custom_components.qvantum_hass.config_flow.QvantumApi",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
            },
            data=mock_config_entry.data,
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "wrong_password"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_connection_error(hass, mock_config_entry, mock_api):
    """Test reauth flow shows error on connection failure."""
    mock_api.authenticate.side_effect = ApiConnectionError("Timeout")

    with patch(
        "custom_components.qvantum_hass.config_flow.QvantumApi",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
            },
            data=mock_config_entry.data,
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "some_password"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow_unknown_error(hass, mock_config_entry, mock_api):
    """Test reauth flow shows error when an unexpected API exception occurs."""
    mock_api.authenticate.side_effect = QvantumApiError("Unexpected error")

    with patch(
        "custom_components.qvantum_hass.config_flow.QvantumApi",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
            },
            data=mock_config_entry.data,
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "some_password"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


# ---------------------------------------------------------------------------
# Reconfigure flow
# ---------------------------------------------------------------------------


async def test_reconfigure_flow_success(hass, mock_config_entry, mock_api):
    """Test successful reconfigure flow with same account."""
    with patch(
        "custom_components.qvantum_hass.config_flow.QvantumApi",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": mock_config_entry.entry_id,
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_EMAIL: TEST_EMAIL,
                CONF_PASSWORD: "updated_password",
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "updated_password"


async def test_reconfigure_flow_wrong_account(hass, mock_config_entry, mock_api):
    """Test reconfigure aborts when a different account email is entered."""
    with patch(
        "custom_components.qvantum_hass.config_flow.QvantumApi",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": mock_config_entry.entry_id,
            },
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_EMAIL: "different@example.com",
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "wrong_account"


async def test_reconfigure_flow_connection_error(hass, mock_config_entry, mock_api):
    """Test reconfigure flow shows error on connection failure."""
    mock_api.authenticate.side_effect = ApiConnectionError("Timeout")

    with patch(
        "custom_components.qvantum_hass.config_flow.QvantumApi",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": mock_config_entry.entry_id,
            },
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=TEST_USER_INPUT,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_unknown_error(hass, mock_config_entry, mock_api):
    """Test reconfigure flow shows error when an unexpected API exception occurs."""
    mock_api.authenticate.side_effect = QvantumApiError("Unexpected error")

    with patch(
        "custom_components.qvantum_hass.config_flow.QvantumApi",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": mock_config_entry.entry_id,
            },
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=TEST_USER_INPUT,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
