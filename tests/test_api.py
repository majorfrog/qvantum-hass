"""Unit tests for the QvantumApi HTTP client.

These tests exercise the real API class with a mocked aiohttp session,
verifying that responses are parsed correctly and errors raise the right
exception types.  No Home Assistant infrastructure is needed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.qvantum_hass.api import (
    ApiClientError,
    ApiConnectionError,
    AuthenticationError,
    QvantumApi,
)
from tests.fixtures import (
    MOCK_ACCESS_LEVEL_RESPONSE,
    MOCK_ALARMS_RESPONSE,
    MOCK_AUTH_ERROR_RESPONSE,
    MOCK_AUTH_RESPONSE,
    MOCK_DEVICES_RESPONSE,
    MOCK_INTERNAL_METRICS_RESPONSE,
    MOCK_SETTINGS_RESPONSE,
    MOCK_STATUS_RESPONSE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(status: int, json_body) -> MagicMock:
    """Return a MagicMock that behaves like an aiohttp ClientResponse."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.json = AsyncMock(return_value=json_body)
    return mock_resp


def _make_session(method: str, response: MagicMock) -> MagicMock:
    """Return a MagicMock session whose *method* returns *response* as an async CM."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    getattr(session, method).return_value = cm
    return session


def _api_with_token(
    email: str = "test@example.com", password: str = "pw"
) -> QvantumApi:
    """Create a QvantumApi pre-populated with a valid token."""
    api = QvantumApi(email, password)
    api.tokens = {
        "idToken": "mock_token",
        "refreshToken": "mock_refresh",
        "expiresIn": "3600",
    }
    api.token_expiry = datetime.now(UTC) + timedelta(hours=1)
    return api


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authentication_success():
    """Successful authentication stores the returned tokens."""
    mock_session = _make_session("post", _make_response(200, MOCK_AUTH_RESPONSE))

    api = QvantumApi("test@example.com", "testpass")
    api.session = mock_session
    await api.authenticate()

    assert api.tokens is not None
    assert api.tokens["idToken"] == "mock_id_token_12345"


@pytest.mark.asyncio
async def test_authentication_failure_raises():
    """A 401 response raises AuthenticationError."""
    mock_session = _make_session("post", _make_response(401, MOCK_AUTH_ERROR_RESPONSE))

    api = QvantumApi("test@example.com", "wrongpass")
    api.session = mock_session

    with pytest.raises(AuthenticationError):
        await api.authenticate()


# ---------------------------------------------------------------------------
# Device fetching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_devices_returns_list():
    """get_devices returns a list of device dicts from the API response."""
    mock_session = _make_session("get", _make_response(200, MOCK_DEVICES_RESPONSE))

    api = _api_with_token()
    api.session = mock_session

    devices = await api.get_devices()

    assert len(devices) == 1
    assert devices[0]["id"] == "device_123"
    assert devices[0]["name"] == "Heat Pump Living Room"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connection_error_raises_api_connection_error():
    """An aiohttp.ClientError propagates as ApiConnectionError."""
    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=aiohttp.ClientError("Connection failed"))

    api = _api_with_token()
    api.session = mock_session

    with pytest.raises(ApiConnectionError):
        await api.get_devices()


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_status_returns_dict():
    """get_status returns a dict containing at least the timestamp from the fixture."""
    mock_session = _make_session("get", _make_response(200, MOCK_STATUS_RESPONSE))

    api = _api_with_token()
    api.session = mock_session

    result = await api.get_status("device_123")

    assert isinstance(result, dict)
    # StatusResponse uses extra="allow" so extra fields pass through model_dump()
    assert result["timestamp"] == MOCK_STATUS_RESPONSE["timestamp"]
    mock_session.get.assert_called_once()


# ---------------------------------------------------------------------------
# get_internal_metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_internal_metrics_returns_values():
    """get_internal_metrics returns a dict containing a 'values' key."""
    mock_session = _make_session(
        "get", _make_response(200, MOCK_INTERNAL_METRICS_RESPONSE)
    )

    api = _api_with_token()
    api.session = mock_session

    result = await api.get_internal_metrics("device_123", ["bt1", "powertotal"])

    assert "values" in result
    assert result["values"]["bt1"] == MOCK_INTERNAL_METRICS_RESPONSE["values"]["bt1"]
    assert (
        result["values"]["powertotal"]
        == MOCK_INTERNAL_METRICS_RESPONSE["values"]["powertotal"]
    )


# ---------------------------------------------------------------------------
# HTTP error-code handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_server_error_raises_api_connection_error():
    """A 5xx response from the server raises ApiConnectionError."""
    mock_session = _make_session("get", _make_response(503, {"error": "unavailable"}))

    api = _api_with_token()
    api.session = mock_session

    with pytest.raises(ApiConnectionError) as exc_info:
        await api.get_devices()

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_client_error_raises_api_client_error():
    """A 4xx (non-401) response from the server raises ApiClientError."""
    mock_session = _make_session("get", _make_response(404, {"error": "not found"}))

    api = _api_with_token()
    api.session = mock_session

    with pytest.raises(ApiClientError) as exc_info:
        await api.get_devices()

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Timeout / network error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_timeout_raises_api_connection_error():
    """A TimeoutError during a request propagates as ApiConnectionError."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(side_effect=TimeoutError("request timed out"))
    cm.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get.return_value = cm

    api = _api_with_token()
    api.session = mock_session

    with pytest.raises(ApiConnectionError):
        await api.get_devices()


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expired_token_triggers_refresh():
    """When the token has expired, _refresh_access_token is called before the request."""
    mock_session = _make_session("get", _make_response(200, MOCK_DEVICES_RESPONSE))

    api = QvantumApi("test@example.com", "pw")
    api.session = mock_session
    # Pre-populate stale tokens so refresh path (not full re-auth) is taken
    api.tokens = {
        "idToken": "old_token",
        "refreshToken": "valid_refresh",
        "expiresIn": "3600",
    }
    api.token_expiry = datetime.now(UTC) - timedelta(minutes=5)  # already expired

    refreshed_tokens = {
        "idToken": "new_token",
        "refreshToken": "new_refresh",
        "expiresIn": "3600",
    }

    with patch.object(
        api, "_refresh_access_token", new_callable=AsyncMock
    ) as mock_refresh:
        # After refresh, give it valid tokens so the GET request can proceed
        async def do_refresh():
            api.tokens = refreshed_tokens
            api.token_expiry = datetime.now(UTC) + timedelta(hours=1)

        mock_refresh.side_effect = do_refresh
        await api.get_devices()

    mock_refresh.assert_called_once()


# ---------------------------------------------------------------------------
# get_settings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_settings_returns_settings_list():
    """get_settings parses and returns a dict with a validated 'settings' list."""
    mock_session = _make_session("get", _make_response(200, MOCK_SETTINGS_RESPONSE))

    api = _api_with_token()
    api.session = mock_session

    result = await api.get_settings("device_123")

    assert isinstance(result, dict)
    assert "settings" in result
    # Pydantic model_dump() — first setting must match fixture
    first = result["settings"][0]
    assert first["name"] == "target_temperature"
    assert first["value"] == 22.0


# ---------------------------------------------------------------------------
# get_alarms
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_alarms_returns_alarms_dict():
    """get_alarms returns the raw dict with an 'alarms' key."""
    mock_session = _make_session("get", _make_response(200, MOCK_ALARMS_RESPONSE))

    api = _api_with_token()
    api.session = mock_session

    result = await api.get_alarms("device_123")

    assert isinstance(result, dict)
    assert "alarms" in result
    assert isinstance(result["alarms"], list)


# ---------------------------------------------------------------------------
# get_access_level
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_access_level_returns_level_dict():
    """get_access_level returns the raw dict with writeAccessLevel key."""
    mock_session = _make_session("get", _make_response(200, MOCK_ACCESS_LEVEL_RESPONSE))

    api = _api_with_token()
    api.session = mock_session

    result = await api.get_access_level("device_123")

    assert isinstance(result, dict)
    assert result["writeAccessLevel"] == 10
    assert result["readAccessLevel"] == 10


# ---------------------------------------------------------------------------
# _refresh_access_token (direct)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_token_updates_id_token():
    """_refresh_access_token POSTs to the token server and updates api.tokens."""
    refresh_body = {
        "id_token": "brand_new_id_token",
        "refresh_token": "brand_new_refresh",
        "expires_in": "3600",
    }
    mock_session = _make_session("post", _make_response(200, refresh_body))

    api = QvantumApi("test@example.com", "pw")
    api.session = mock_session
    api.tokens = {
        "idToken": "old_id",
        "refreshToken": "old_refresh",
        "expiresIn": "3600",
    }

    await api._refresh_access_token()

    assert api.tokens["idToken"] == "brand_new_id_token"
    assert api.tokens["refreshToken"] == "brand_new_refresh"


@pytest.mark.asyncio
async def test_refresh_token_401_raises_authentication_error():
    """A 401 from the token endpoint raises AuthenticationError."""
    mock_session = _make_session(
        "post", _make_response(401, {"error": "invalid_grant"})
    )

    api = QvantumApi("test@example.com", "pw")
    api.session = mock_session
    api.tokens = {"idToken": "old", "refreshToken": "bad_refresh", "expiresIn": "3600"}

    with pytest.raises(AuthenticationError):
        await api._refresh_access_token()
