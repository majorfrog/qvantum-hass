"""Pytest configuration and fixtures for Qvantum tests."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant import loader as _ha_loader

# Import from HA core tests.common.
# Pytest adds the local package root to sys.path[0] when importing this
# conftest, which causes the local 'tests' package to shadow HA core's
# tests.common.  Fix: ensure core is first in sys.path and temporarily
# remove the local 'tests' entry from sys.modules so Python resolves
# 'tests.common' from core (not locally).
_CORE_PATH = "/workspaces/core"
# Ensure core path is first
if _CORE_PATH in sys.path:
    sys.path.remove(_CORE_PATH)
sys.path.insert(0, _CORE_PATH)

# Save & evict local 'tests' package so import below finds core's
_local_tests_module = sys.modules.pop("tests", None)
_local_tests_conftest = sys.modules.pop("tests.conftest", None)

from tests.common import MockConfigEntry, async_test_home_assistant  # noqa: E402

# Restore the local 'tests' package so later relative imports in this file work
if _local_tests_module is not None:
    sys.modules["tests"] = _local_tests_module
if _local_tests_conftest is not None:
    sys.modules["tests.conftest"] = _local_tests_conftest

from custom_components.qvantum_hass.const import DOMAIN

# Import fixtures directly from fixtures file
from .fixtures import (  # noqa: F401
    MOCK_ACCESS_LEVEL_RESPONSE,
    MOCK_ALARMS_INVENTORY_RESPONSE,
    MOCK_ALARMS_RESPONSE,
    MOCK_AUTH_ERROR_RESPONSE,
    MOCK_AUTH_RESPONSE,
    MOCK_CONNECTION_ERROR_MESSAGE,
    MOCK_DEVICES_RESPONSE,
    MOCK_INTERNAL_METRICS_RESPONSE,
    MOCK_METRICS_INVENTORY_RESPONSE,
    MOCK_SERVER_ERROR_RESPONSE,
    MOCK_SETTINGS_INVENTORY_RESPONSE,
    MOCK_SETTINGS_RESPONSE,
    MOCK_STATUS_RESPONSE,
)

# Test credentials
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test_password_123"
TEST_USER_INPUT = {
    CONF_EMAIL: TEST_EMAIL,
    CONF_PASSWORD: TEST_PASSWORD,
}


@pytest.fixture
async def hass():
    """Fixture to provide a test instance of Home Assistant."""
    # Use test config pointing to this repo
    config_dir = str(Path(__file__).parent.parent)
    async with async_test_home_assistant(config_dir=config_dir) as hass_instance:
        # async_test_home_assistant pre-sets DATA_CUSTOM_COMPONENTS to {} which
        # prevents the loader from scanning the filesystem for custom integrations.
        # Remove it so the loader discovers custom_components/ in our config_dir.
        hass_instance.data.pop(_ha_loader.DATA_CUSTOM_COMPONENTS, None)
        yield hass_instance


@pytest.fixture
def mock_api():
    """Create a mock QvantumApi that returns successful responses."""
    api = AsyncMock()

    # Authentication
    api.authenticate = AsyncMock(return_value=MOCK_AUTH_RESPONSE)
    api.refresh_token = AsyncMock(return_value=MOCK_AUTH_RESPONSE)
    api.is_token_valid = MagicMock(return_value=True)

    # Device operations
    api.get_devices = AsyncMock(return_value=MOCK_DEVICES_RESPONSE["devices"])
    api.get_status = AsyncMock(return_value=MOCK_STATUS_RESPONSE)
    # get_settings returns a validated Pydantic model_dump(): {"settings": [...]}
    api.get_settings = AsyncMock(return_value=MOCK_SETTINGS_RESPONSE)

    # Inventory endpoints — also return full dicts matching model_dump() output
    api.get_settings_inventory = AsyncMock(
        return_value=MOCK_SETTINGS_INVENTORY_RESPONSE
    )
    api.get_metrics_inventory = AsyncMock(return_value=MOCK_METRICS_INVENTORY_RESPONSE)

    # Metrics — returns {"values": {...}}, coordinator extracts ["values"]
    api.get_internal_metrics = AsyncMock(return_value=MOCK_INTERNAL_METRICS_RESPONSE)

    # Access level — raw dict with writeAccessLevel / readAccessLevel keys
    api.get_access_level = AsyncMock(return_value=MOCK_ACCESS_LEVEL_RESPONSE)
    api.set_access_level = AsyncMock(return_value={"success": True})

    # Alarms — raw API dicts: {"alarms": [...]}
    api.get_alarms_inventory = AsyncMock(return_value=MOCK_ALARMS_INVENTORY_RESPONSE)
    api.get_alarms = AsyncMock(return_value=MOCK_ALARMS_RESPONSE)

    # Settings / command writes
    api.set_setting = AsyncMock(return_value={"response": {}})
    api.set_extra_hot_water = AsyncMock(return_value={"success": True})
    api.set_smartcontrol = AsyncMock(return_value={"success": True})
    api.elevate_access = AsyncMock(
        return_value={"writeAccessLevel": 20, "expiresAt": None}
    )

    # Session management
    api.close = AsyncMock()

    return api


@pytest.fixture
def mock_api_constructor(mock_api):
    """Mock the QvantumApi constructor to return our mock API."""
    with (
        patch(
            "custom_components.qvantum_hass.config_flow.QvantumApi",
            return_value=mock_api,
        ),
        patch(
            "custom_components.qvantum_hass.QvantumApi",
            return_value=mock_api,
        ),
    ):
        yield mock_api


@pytest.fixture
def mock_config_entry(hass):
    """Create a mock config entry."""
    entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Qvantum Heat Pump",
        data={
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        source="user",
        unique_id=TEST_EMAIL,
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)
    return entry
