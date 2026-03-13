"""Tests for Qvantum entity state correctness.

Verifies that entities created after integration setup carry the correct
initial states derived from the mocked coordinator data.  These tests
catch regressions where a value is present in the coordinator but not
surfaced in the entity state.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.qvantum_hass.const import DOMAIN
from tests.fixtures import MOCK_ALARMS_ACTIVE_RESPONSE, MOCK_INTERNAL_METRICS_RESPONSE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _setup(hass: HomeAssistant, mock_api) -> er.EntityRegistry:
    """Set up the integration and return the entity registry."""
    # hass fixture already has mock_config_entry added via fixture
    with patch(
        "custom_components.qvantum_hass.QvantumApi",
        return_value=mock_api,
    ):
        entries = hass.config_entries.async_entries(DOMAIN)
        assert entries, "Expected at least one config entry to be registered"
        await hass.config_entries.async_setup(entries[0].entry_id)
        await hass.async_block_till_done()

    return er.async_get(hass)


# ---------------------------------------------------------------------------
# Sensor entities (source: internal_metrics)
# ---------------------------------------------------------------------------


async def test_metric_sensor_state_reflects_coordinator_data(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """bt1 sensor state equals the bt1 value in MOCK_INTERNAL_METRICS_RESPONSE."""
    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "device_123_internal_bt1"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    expected = MOCK_INTERNAL_METRICS_RESPONSE["values"]["bt1"]
    assert float(state.state) == pytest.approx(expected)


async def test_fast_polling_metric_sensor_state(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """powertotal (fast_polling=True) sensor state equals the fixture value."""
    entity_registry = await _setup(hass, mock_api)

    # powertotal uses the fast coordinator but shares the same unique_id logic
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "device_123_internal_powertotal"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    expected = MOCK_INTERNAL_METRICS_RESPONSE["values"]["powertotal"]
    assert float(state.state) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Binary sensor entities (source: internal_metrics)
# ---------------------------------------------------------------------------


async def test_internal_binary_sensor_on_when_metric_is_true(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """picpin_relay_heat_l1 is 'on' when its metric value is True in coordinator data."""
    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor",
        DOMAIN,
        "device_123_internal_picpin_relay_heat_l1",
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    # MOCK_INTERNAL_METRICS_RESPONSE["values"]["picpin_relay_heat_l1"] = True
    assert state.state == "on"


async def test_internal_binary_sensor_off_when_metric_is_false(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """picpin_relay_heat_l2 is 'off' when its metric value is False in coordinator data."""
    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor",
        DOMAIN,
        "device_123_internal_picpin_relay_heat_l2",
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    # MOCK_INTERNAL_METRICS_RESPONSE["values"]["picpin_relay_heat_l2"] = False
    assert state.state == "off"


# ---------------------------------------------------------------------------
# Alarm state binary sensor (source: alarms)
# ---------------------------------------------------------------------------


async def test_alarm_state_sensor_is_off_with_no_active_alarms(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """alarm_state binary sensor is 'off' when the alarms list is empty."""
    # Default mock returns MOCK_ALARMS_RESPONSE which has an empty alarms list
    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "device_123_alarm_state"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


async def test_alarm_state_sensor_is_on_with_active_alarm(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """alarm_state binary sensor is 'on' when an alarm with is_active=True is present."""
    # Override the default empty-alarms response before setup
    mock_api.get_alarms.return_value = MOCK_ALARMS_ACTIVE_RESPONSE

    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "device_123_alarm_state"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


# ---------------------------------------------------------------------------
# Switch entity state and actions
# ---------------------------------------------------------------------------


async def test_auto_elevate_switch_toggle_reflects_coordinator(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """auto_elevate_access switch state tracks coordinator.auto_elevate_enabled."""
    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, "device_123_auto_elevate_access"
    )
    assert entity_id is not None
    coordinator = mock_config_entry.runtime_data["coordinators"]["device_123"]

    # Turn off — ensures a deterministic starting state
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "off"
    assert coordinator.auto_elevate_enabled is False

    # Turn on and confirm entity and coordinator flag are both updated
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"
    assert coordinator.auto_elevate_enabled is True


async def test_switch_turn_on_calls_set_setting(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """Turning on a settings-backed switch calls api.set_setting with True."""
    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, "device_123_vacation_mode"
    )
    assert entity_id is not None

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id}, blocking=True
    )

    mock_api.set_setting.assert_called_with("device_123", "vacation_mode", True)


async def test_switch_turn_off_calls_set_setting(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """Turning off a settings-backed switch calls api.set_setting with False."""
    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, "device_123_vacation_mode"
    )
    assert entity_id is not None

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": entity_id}, blocking=True
    )

    mock_api.set_setting.assert_called_with("device_123", "vacation_mode", False)


# ---------------------------------------------------------------------------
# Select entity state and actions
# ---------------------------------------------------------------------------


async def test_smartcontrol_select_is_off_when_adaptive_disabled(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """SmartControl select returns 'off' when use_adaptive=False in coordinator data."""
    # MOCK_INTERNAL_METRICS_RESPONSE has use_adaptive = False
    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "select", DOMAIN, "device_123_smartcontrol"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


async def test_select_option_calls_set_smartcontrol(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """Selecting 'eco' on SmartControl select calls api.set_smartcontrol with mode 0."""
    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "select", DOMAIN, "device_123_smartcontrol"
    )
    assert entity_id is not None

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "eco"},
        blocking=True,
    )

    mock_api.set_smartcontrol.assert_called_once_with("device_123", 0, 0)


# ---------------------------------------------------------------------------
# Number entity actions
# ---------------------------------------------------------------------------


async def test_number_set_value_calls_set_setting() -> None:
    """QvantumNumberEntity.async_set_native_value delegates to api.set_setting."""
    from unittest.mock import AsyncMock, MagicMock

    from custom_components.qvantum_hass.models import EntitySource, QvantumEntityDef
    from custom_components.qvantum_hass.number import QvantumNumberEntity

    mock_api = MagicMock()
    mock_api.set_setting = AsyncMock()
    mock_coordinator = MagicMock()
    mock_coordinator.api = mock_api
    mock_coordinator.data = None
    mock_coordinator.async_request_refresh = AsyncMock()

    entity_def = QvantumEntityDef(
        "tap_water_start",
        "DHW start temperature",
        source=EntitySource.SETTINGS,
        unit="°C",
    )
    device = {"id": "device_123", "name": "Test"}
    entity = QvantumNumberEntity(mock_coordinator, device, mock_api, entity_def)
    entity.async_write_ha_state = MagicMock()  # no hass in unit test

    await entity.async_set_native_value(45)

    mock_api.set_setting.assert_called_with("device_123", "tap_water_start", 45)


# ---------------------------------------------------------------------------
# Extra hot water switch — actions and state sync
# ---------------------------------------------------------------------------


async def test_extra_hot_water_switch_turn_on_calls_set_extra_hot_water(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """Turning on the extra_hot_water switch calls api.set_extra_hot_water indefinitely."""
    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, "device_123_extra_hot_water"
    )
    assert entity_id is not None

    mock_api.set_extra_hot_water.reset_mock()
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id}, blocking=True
    )

    mock_api.set_extra_hot_water.assert_called_once_with("device_123", indefinite=True)


async def test_extra_hot_water_switch_turn_off_calls_set_extra_hot_water(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """Turning off the extra_hot_water switch calls api.set_extra_hot_water with hours=0."""
    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, "device_123_extra_hot_water"
    )
    assert entity_id is not None

    mock_api.set_extra_hot_water.reset_mock()
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": entity_id}, blocking=True
    )

    mock_api.set_extra_hot_water.assert_called_once_with("device_123", hours=0)


async def test_extra_hot_water_switch_pending_cleared_after_coordinator_refresh(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """Pending state is cleared by coordinator refresh; API data rules afterwards."""
    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, "device_123_extra_hot_water"
    )
    assert entity_id is not None
    coordinator = mock_config_entry.runtime_data["coordinators"]["device_123"]

    # Pre-configure mock so the refresh inside turn_on sees the "on" state
    mock_api.get_settings.return_value = {
        "settings": [{"name": "extra_tap_water", "value": "on"}]
    }

    mock_api.set_extra_hot_water.reset_mock()
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    # Coordinator has refreshed and API confirms "on" — no flicker
    assert hass.states.get(entity_id).state == "on"

    # External cancel: next poll returns "off" — state must sync
    mock_api.get_settings.return_value = {
        "settings": [{"name": "extra_tap_water", "value": "off"}]
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "off"


async def test_extra_hot_water_button_press_calls_api(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """Pressing the extra_hot_water_1h button calls api.set_extra_hot_water."""
    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "button", DOMAIN, "device_123_extra_hot_water_1h"
    )
    assert entity_id is not None

    mock_api.set_extra_hot_water.reset_mock()
    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id}, blocking=True
    )

    mock_api.set_extra_hot_water.assert_called_once_with("device_123", 1, False)


async def test_refresh_button_triggers_coordinator_refresh(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """Pressing the refresh button triggers a coordinator data refresh."""
    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "button", DOMAIN, "device_123_refresh"
    )
    assert entity_id is not None

    initial_call_count = mock_api.get_status.call_count

    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    assert mock_api.get_status.call_count > initial_call_count


# ---------------------------------------------------------------------------
# Entity availability
# ---------------------------------------------------------------------------


async def test_entity_becomes_unavailable_when_coordinator_fails(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """Entity state becomes 'unavailable' when the coordinator fails to update."""
    entity_registry = await _setup(hass, mock_api)

    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, "device_123_vacation_mode"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state != "unavailable"

    coordinator = mock_config_entry.runtime_data["coordinators"]["device_123"]
    mock_api.get_status.side_effect = Exception("network failure")

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unavailable"
