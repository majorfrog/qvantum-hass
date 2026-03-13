"""Integration tests for Qvantum — schemas and cache edge cases.

Covers items that are not exercised elsewhere:
- Pydantic schema validation against mock API payloads
- CachedValue behaviour when never populated

Entity definition integrity is covered by test_entity_definitions.py.
API HTTP-level behaviour is covered by test_api.py.
"""

from __future__ import annotations

from datetime import timedelta

from tests.fixtures import (
    MOCK_DEVICES_RESPONSE,
    MOCK_INTERNAL_METRICS_RESPONSE,
    MOCK_SETTINGS_RESPONSE,
)


# =============================================================================
# Cache edge-case tests
# =============================================================================


class TestCachedValue:
    """Test edge cases of the CachedValue helper."""

    def test_cache_returns_none_when_empty(self):
        """CachedValue.get() returns None when no value has been set."""
        from custom_components.qvantum_hass.coordinator import CachedValue

        cache = CachedValue[str](timedelta(hours=1))

        assert not cache.is_cached()
        assert cache.get() is None

    def test_cache_returns_value_when_fresh(self):
        """CachedValue.get() returns the stored value before TTL expires."""
        from custom_components.qvantum_hass.coordinator import CachedValue

        cache = CachedValue[str](timedelta(hours=1))
        cache.set("hello")

        assert cache.is_cached()
        assert cache.get() == "hello"

    def test_cache_returns_none_after_expiry(self):
        """CachedValue.get() returns None after the TTL has elapsed."""
        from custom_components.qvantum_hass.coordinator import CachedValue
        from unittest.mock import patch
        from datetime import UTC, datetime

        cache = CachedValue[str](timedelta(seconds=60))
        cache.set("stale")

        assert cache.is_cached()

        # Simulate time passing beyond the TTL
        far_future = datetime.now(tz=UTC) + timedelta(hours=2)
        with patch("custom_components.qvantum_hass.coordinator.datetime") as mock_dt:
            mock_dt.now.return_value = far_future

            assert not cache.is_cached()
            assert cache.get() is None


# =============================================================================
# Schema validation tests
# =============================================================================


class TestSchemas:
    """Pydantic schema classes validate correctly against mock API payloads."""

    def test_devices_list_response_validation(self):
        """DevicesListResponse parses a valid device list."""
        from custom_components.qvantum_hass.schemas import DevicesListResponse

        response = DevicesListResponse(**MOCK_DEVICES_RESPONSE)
        assert len(response.devices) == 1
        assert response.devices[0].id == "device_123"

    def test_settings_response_validation(self):
        """SettingsResponse parses a valid settings list."""
        from custom_components.qvantum_hass.schemas import SettingsResponse

        response = SettingsResponse(**MOCK_SETTINGS_RESPONSE)
        assert len(response.settings) == 2
        assert response.settings[0].name == "target_temperature"

    def test_internal_metrics_response_validation(self):
        """InternalMetricsResponse parses metric values correctly."""
        from custom_components.qvantum_hass.schemas import InternalMetricsResponse

        response = InternalMetricsResponse(**MOCK_INTERNAL_METRICS_RESPONSE)
        assert response.values["bt1"] == MOCK_INTERNAL_METRICS_RESPONSE["values"]["bt1"]
        assert (
            response.values["powertotal"]
            == MOCK_INTERNAL_METRICS_RESPONSE["values"]["powertotal"]
        )
