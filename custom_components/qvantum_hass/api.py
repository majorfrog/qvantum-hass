"""Qvantum API client for heat pump integration.

This module provides a comprehensive async API client for communicating with
Qvantum heat pumps through their cloud service. It handles authentication,
token management, and all device operations.

The client uses Firebase Authentication for user authentication and provides
methods for:
- Device discovery and management
- Real-time metrics and settings retrieval
- Settings updates and control commands
- Access level management
- Alarm monitoring
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

import aiohttp
from pydantic import ValidationError

from .const import (
    DEFAULT_API_ENDPOINT,
    DEFAULT_API_KEY,
    DEFAULT_AUTH_SERVER,
    DEFAULT_INTERNAL_API_ENDPOINT,
    DEFAULT_TOKEN_SERVER,
)
from .schemas import (
    DevicesListResponse,
    InternalMetricsResponse,
    MetricsInventoryResponse,
    SettingsInventoryResponse,
    SettingsResponse,
    StatusResponse,
    validate_response,
)

_LOGGER = logging.getLogger(__name__)

# Request timeout for all operations (seconds)
REQUEST_TIMEOUT = 30


class QvantumApiError(Exception):
    """Base exception for Qvantum API errors."""

    def __init__(
        self, message: str, status_code: int | None = None, response_data: Any = None
    ) -> None:
        """Initialize API error with optional status code and response data."""
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class AuthenticationError(QvantumApiError):
    """Exception raised when authentication fails (401)."""


class ApiConnectionError(QvantumApiError):
    """Exception raised for network/connection issues or 5xx errors."""


class ApiClientError(QvantumApiError):
    """Exception raised for 4xx client errors."""


class QvantumApi:
    """Async client for Qvantum API communication.

    This class handles all communication with the Qvantum cloud API,
    including authentication, token management, and device operations.
    Uses aiohttp for true async/await support.

    Attributes:
        email: User email for authentication
        password: User password for authentication
        api_key: Firebase API key
        api_endpoint: Base URL for public API endpoints
        internal_api_endpoint: Base URL for internal API endpoints
        auth_server: Firebase authentication server URL
        token_server: Firebase token server URL
        tokens: Current authentication tokens
        token_expiry: Token expiration timestamp
        session: aiohttp ClientSession (created on first use)
    """

    def __init__(
        self,
        email: str,
        password: str,
        api_key: str = DEFAULT_API_KEY,
        api_endpoint: str = DEFAULT_API_ENDPOINT,
        internal_api_endpoint: str = DEFAULT_INTERNAL_API_ENDPOINT,
        auth_server: str = DEFAULT_AUTH_SERVER,
        token_server: str = DEFAULT_TOKEN_SERVER,
    ) -> None:
        """Initialize the async API client.

        Args:
            email: User email address
            password: User password
            api_key: Firebase API key (defaults to Qvantum's public key)
            api_endpoint: Base URL for API requests
            internal_api_endpoint: Base URL for internal API requests
            auth_server: Firebase auth server URL
            token_server: Firebase token server URL
        """
        self.email = email
        self.password = password
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self.internal_api_endpoint = internal_api_endpoint
        self.auth_server = auth_server
        self.token_server = token_server

        self.tokens: dict[str, Any] | None = None
        self.token_expiry: datetime | None = None
        self.session: aiohttp.ClientSession | None = None

    def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session.

        Note: Session must be closed externally when no longer needed.

        Returns:
            aiohttp.ClientSession instance
        """
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def _ensure_tokens_valid(self) -> None:
        """Ensure we have valid authentication tokens."""
        if (
            not self.tokens
            or self.token_expiry is None
            or datetime.now(UTC) >= self.token_expiry
        ):
            if self.tokens:
                try:
                    await self._refresh_access_token()
                except AuthenticationError:
                    # Refresh failed, do full authentication
                    await self.authenticate()
            else:
                await self.authenticate()

            if self.tokens is None:
                raise AuthenticationError(
                    "Authentication succeeded but tokens were not set"
                )
            self.token_expiry = datetime.now(UTC) + timedelta(
                seconds=int(self.tokens["expiresIn"]) - 60
            )

    async def _handle_response(
        self, response: aiohttp.ClientResponse, context: str, is_write: bool = False
    ) -> Any:
        """Handle HTTP response and raise appropriate exceptions.

        Args:
            response: aiohttp ClientResponse
            context: Description for logging (e.g., "GET request to /api/...")
            is_write: If True, treat as write operation for error logging

        Returns:
            Parsed JSON response

        Raises:
            AuthenticationError: For 401 responses
            ApiConnectionError: For 5xx errors
            ApiClientError: For 4xx errors
            QvantumApiError: For other errors
        """
        try:
            response_data = await response.json()
        except (ValueError, aiohttp.ContentTypeError):
            response_data = None

        # 401 Unauthorized - authentication failure
        if response.status == 401:
            _LOGGER.error("Authentication failed for %s", context)
            raise AuthenticationError(
                "Authentication failed",
                status_code=401,
                response_data=response_data,
            )

        # 5xx errors - transient server issues
        if response.status >= 500:
            raise ApiConnectionError(
                f"Server error {response.status}",
                status_code=response.status,
                response_data=response_data,
            )

        # 4xx errors - client errors (except 401, handled above)
        if response.status >= 400:
            log_level = logging.WARNING if is_write else logging.DEBUG
            _LOGGER.log(
                log_level,
                "Client error %d for %s: %s",
                response.status,
                context,
                response_data,
            )
            raise ApiClientError(
                f"Client error {response.status}",
                status_code=response.status,
                response_data=response_data,
            )

        return response_data

    async def _get_request(self, endpoint: str) -> Any:
        """Make a GET request to the public API."""
        return await self._do_get_request(endpoint, self.api_endpoint)

    async def _get_internal_request(self, endpoint: str) -> Any:
        """Make a GET request to the internal API."""
        return await self._do_get_request(endpoint, self.internal_api_endpoint)

    async def _do_get_request(self, endpoint: str, base_url: str) -> Any:
        """Make a GET request to the specified base URL.

        Args:
            endpoint: API endpoint path
            base_url: Base URL (api_endpoint or internal_api_endpoint)

        Returns:
            JSON response data

        Raises:
            AuthenticationError: For 401 responses
            ApiConnectionError: For timeouts or 5xx errors
            ApiClientError: For 4xx client errors
            QvantumApiError: For other errors
        """
        await self._ensure_tokens_valid()
        if self.tokens is None:
            raise AuthenticationError("No valid tokens available after authentication")

        url = f"{base_url}/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.tokens['idToken']}",
        }

        try:
            session = self._get_session()
            async with session.get(url, headers=headers) as response:
                return await self._handle_response(
                    response, f"GET {url}", is_write=False
                )
        except TimeoutError as err:
            _LOGGER.error("Timeout for GET %s", url)
            raise ApiConnectionError(f"Request timeout: {err}") from err
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error for GET %s: %s", url, err)
            raise ApiConnectionError(f"Connection error: {err}") from err

    async def _patch_request(self, endpoint: str, data: dict) -> Any:
        """Make a PATCH request to the API."""
        await self._ensure_tokens_valid()
        if self.tokens is None:
            raise AuthenticationError("No valid tokens available after authentication")

        url = f"{self.api_endpoint}/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.tokens['idToken']}",
        }

        _LOGGER.debug("Making PATCH request to %s with data %s", url, data)

        try:
            session = self._get_session()
            async with session.patch(url, json=data, headers=headers) as response:
                return await self._handle_response(
                    response, f"PATCH {url}", is_write=True
                )
        except TimeoutError as err:
            _LOGGER.warning("Timeout for PATCH %s", url)
            raise ApiConnectionError(f"Request timeout: {err}") from err
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error for PATCH %s: %s", url, err)
            raise ApiConnectionError(f"Connection error: {err}") from err

    async def _post_request(self, endpoint: str, data: dict) -> Any:
        """Make a POST request to the API."""
        await self._ensure_tokens_valid()
        if self.tokens is None:
            raise AuthenticationError("No valid tokens available after authentication")

        url = f"{self.api_endpoint}/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.tokens['idToken']}",
        }

        _LOGGER.debug("Making POST request to %s with data %s", url, data)

        try:
            session = self._get_session()
            async with session.post(url, json=data, headers=headers) as response:
                _LOGGER.debug("POST %s returned status %s", url, response.status)
                if response.status in {200, 201}:
                    try:
                        response_json = await response.json()
                        _LOGGER.debug("POST %s response body: %s", url, response_json)
                        return response_json
                    except (ValueError, aiohttp.ContentTypeError):
                        # Some endpoints return empty responses
                        raw = await response.text()
                        _LOGGER.debug("POST %s non-JSON response body: %r", url, raw)
                        return {}
                return await self._handle_response(
                    response, f"POST {url}", is_write=True
                )
        except TimeoutError as err:
            _LOGGER.warning("Timeout for POST %s", url)
            raise ApiConnectionError(f"Request timeout: {err}") from err
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error for POST %s: %s", url, err)
            raise ApiConnectionError(f"Connection error: {err}") from err

    async def authenticate(self) -> None:
        """Authenticate with the API server."""
        payload = {
            "returnSecureToken": "true",
            "email": self.email,
            "password": self.password,
            "clientType": "CLIENT_TYPE_WEB",
        }
        url = f"{self.auth_server}/v1/accounts:signInWithPassword?key={self.api_key}"

        _LOGGER.debug("Authenticating with Qvantum API")

        try:
            session = self._get_session()
            async with session.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Qvantum-HA",
                },
            ) as response:
                if response.status == 200:
                    self.tokens = await response.json()
                    _LOGGER.info("Successfully authenticated with Qvantum API")
                else:
                    error_data = None
                    with contextlib.suppress(ValueError, aiohttp.ContentTypeError):
                        error_data = await response.json()

                    if response.status == 401:
                        raise AuthenticationError(
                            "Invalid credentials",
                            status_code=401,
                            response_data=error_data,
                        )
                    if response.status >= 500:
                        raise ApiConnectionError(
                            f"Server error during authentication: {response.status}",
                            status_code=response.status,
                            response_data=error_data,
                        )
                    raise QvantumApiError(
                        f"Authentication error: {response.status}",
                        status_code=response.status,
                        response_data=error_data,
                    )
        except TimeoutError as err:
            _LOGGER.error("Timeout while authenticating")
            raise ApiConnectionError(f"Authentication timeout: {err}") from err
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error during authentication: %s", err)
            raise ApiConnectionError(f"Connection error: {err}") from err

    async def _refresh_access_token(self) -> None:
        """Refresh the access token."""
        if not self.tokens:
            raise AuthenticationError("No tokens available for refresh")

        _LOGGER.debug("Refreshing access token")

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.tokens["refreshToken"],
        }
        url = f"{self.token_server}/v1/token?key={self.api_key}"

        try:
            session = self._get_session()
            async with session.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Qvantum-HA",
                },
            ) as response:
                if response.status == 200:
                    refresh_data = await response.json()
                    # Update tokens
                    if self.tokens is None:
                        raise AuthenticationError("Tokens lost during refresh")
                    self.tokens.update(
                        {
                            "idToken": refresh_data.get("id_token"),
                            "refreshToken": refresh_data.get("refresh_token"),
                            "expiresIn": refresh_data.get("expires_in"),
                        }
                    )
                    _LOGGER.debug("Successfully refreshed access token")
                else:
                    error_data = None
                    with contextlib.suppress(ValueError, aiohttp.ContentTypeError):
                        error_data = await response.json()

                    if response.status == 401:
                        raise AuthenticationError(
                            "Invalid refresh token",
                            status_code=401,
                            response_data=error_data,
                        )
                    if response.status >= 500:
                        raise ApiConnectionError(
                            f"Server error during token refresh: {response.status}",
                            status_code=response.status,
                            response_data=error_data,
                        )
                    raise QvantumApiError(
                        f"Token refresh error: {response.status}",
                        status_code=response.status,
                        response_data=error_data,
                    )
        except TimeoutError as err:
            _LOGGER.error("Timeout while refreshing token")
            raise ApiConnectionError(f"Token refresh timeout: {err}") from err
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error during token refresh: %s", err)
            raise ApiConnectionError(f"Connection error: {err}") from err

    async def get_devices(self) -> list[dict[str, Any]]:
        """Get all devices for the user.

        Returns:
            List of device dictionaries

        Raises:
            QvantumApiError: If API call fails or response validation fails
        """
        path = "api/inventory/v1/users/me/devices"
        response = await self._get_request(path)

        # Validate response structure
        try:
            validated = validate_response(response, DevicesListResponse)
            devices = [device.model_dump() for device in validated.devices]
            _LOGGER.info("Found %d device(s)", len(devices))
        except (ValidationError, ValueError) as err:
            _LOGGER.warning("Response validation failed for get_devices: %s", err)
            # Fallback to unvalidated response for backward compatibility
            devices = response.get("devices", [])
            _LOGGER.info("Found %d device(s) (unvalidated)", len(devices))
        else:
            return devices
        return devices

    async def get_status(self, device_id: str) -> dict[str, Any]:
        """Get device status.

        Returns:
            Device status dictionary

        Raises:
            QvantumApiError: If API call fails or response validation fails
        """
        path = f"api/device-info/v1/devices/{device_id}/status?metrics=now"
        response = await self._get_request(path)

        # Validate response structure
        try:
            validated = validate_response(response, StatusResponse)
            return validated.model_dump()
        except (ValidationError, ValueError) as err:
            _LOGGER.debug("Response validation warning for get_status: %s", err)
            # Return unvalidated for device-specific formats
            return response

    async def get_settings(self, device_id: str) -> dict[str, Any]:
        """Get device settings.

        Returns:
            Device settings dictionary

        Raises:
            QvantumApiError: If API call fails or response validation fails
        """
        path = f"api/device-info/v1/devices/{device_id}/settings"
        response = await self._get_request(path)

        # Validate response structure
        try:
            validated = validate_response(response, SettingsResponse)
            return validated.model_dump()
        except (ValidationError, ValueError) as err:
            _LOGGER.debug("Response validation warning for get_settings: %s", err)
            return response

    async def get_settings_inventory(self, device_id: str) -> dict[str, Any]:
        """Get settings inventory.

        Returns:
            Settings inventory dictionary

        Raises:
            QvantumApiError: If API call fails or response validation fails
        """
        path = f"api/inventory/v1/devices/{device_id}/settings"
        response = await self._get_request(path)

        # Validate response structure
        try:
            validated = validate_response(response, SettingsInventoryResponse)
            return validated.model_dump()
        except (ValidationError, ValueError) as err:
            _LOGGER.debug(
                "Response validation warning for get_settings_inventory: %s", err
            )
            return response

    async def get_metrics_inventory(self, device_id: str) -> dict[str, Any]:
        """Get metrics inventory.

        Returns:
            Metrics inventory dictionary

        Raises:
            QvantumApiError: If API call fails or response validation fails
        """
        path = f"api/inventory/v1/devices/{device_id}/metrics"
        response = await self._get_request(path)

        # Validate response structure
        try:
            validated = validate_response(response, MetricsInventoryResponse)
            return validated.model_dump()
        except (ValidationError, ValueError) as err:
            _LOGGER.debug(
                "Response validation warning for get_metrics_inventory: %s", err
            )
            return response

    async def get_internal_metrics(
        self, device_id: str, metric_names: list[str]
    ) -> dict[str, Any]:
        """Get internal metrics.

        Returns:
            Internal metrics dictionary with 'values' key

        Raises:
            QvantumApiError: If API call fails or response validation fails
        """
        metrics_str = "&".join([f"names={name}" for name in metric_names])
        path = f"api/internal/v1/devices/{device_id}/values?use_internal_names=true&timeout=12&{metrics_str}"
        response = await self._get_internal_request(path)

        # Validate response structure
        try:
            validated = validate_response(response, InternalMetricsResponse)
            return validated.model_dump()
        except (ValidationError, ValueError) as err:
            _LOGGER.debug(
                "Response validation warning for get_internal_metrics: %s", err
            )
            return response

    async def set_setting(
        self, device_id: str, setting: str, value: Any
    ) -> dict[str, Any]:
        """Update a device setting using command API.

        Automatically elevates access if permission denied error is received.

        Args:
            device_id: The device ID
            setting: The setting name
            value: The value to set

        Returns:
            API response
        """
        _LOGGER.debug("Setting %s to %s for device %s", setting, value, device_id)

        # Try to convert to int if possible
        try:
            if isinstance(value, str) and value.lstrip("-").isdigit():
                value = int(value)
        except (ValueError, AttributeError):
            pass

        # Use command API instead of settings PATCH endpoint
        payload = {"command": {"update_settings": {setting: value}}}

        path = f"api/commands/v1/devices/{device_id}/commands?wait=true&use_internal_names=true"
        response = await self._post_request(path, payload)

        _LOGGER.debug(
            "set_setting response for %s=%s on device %s: %s",
            setting,
            value,
            device_id,
            response,
        )

        # Check if we got a permission denied error in the response
        if response and "response" in response:
            setting_response = response["response"].get(setting)
            _LOGGER.debug(
                "set_setting API result for %s: %s",
                setting,
                setting_response,
            )
            if setting_response == "permission denied":
                _LOGGER.debug(
                    "Permission denied for setting %s on device %s, elevating access",
                    setting,
                    device_id,
                )

                # Elevate access
                elevated = await self.elevate_access(device_id)
                if elevated:
                    _LOGGER.info(
                        "Access elevated, retrying setting %s to %s",
                        setting,
                        value,
                    )
                    # Retry the setting
                    response = await self._post_request(path, payload)
                    _LOGGER.debug(
                        "set_setting retry response for %s=%s on device %s: %s",
                        setting,
                        value,
                        device_id,
                        response,
                    )
                else:
                    _LOGGER.error(
                        "Failed to elevate access for device %s, cannot set %s",
                        device_id,
                        setting,
                    )
        elif response is not None:
            _LOGGER.debug(
                "set_setting response has unexpected structure for %s on device %s: %s",
                setting,
                device_id,
                response,
            )

        return response

    async def set_smartcontrol(
        self, device_id: str, sh: int, dhw: int
    ) -> dict[str, Any]:
        """Update SmartControl settings.

        Args:
            device_id: The device ID
            sh: Space heating mode (-1 to disable, 0=Eco, 1=Balanced, 2=Comfort)
            dhw: Domestic hot water mode (-1 to disable, 0=Eco, 1=Balanced, 2=Comfort)

        Returns:
            API response
        """
        _LOGGER.debug(
            "Setting SmartControl on device %s: SH=%d, DHW=%d",
            device_id,
            sh,
            dhw,
        )

        use_adaptive = sh != -1 and dhw != -1
        if not use_adaptive:
            settings = {"use_adaptive": False}
        else:
            settings = {
                "use_adaptive": True,
                "smart_sh_mode": sh,
                "smart_dhw_mode": dhw,
            }

        # Use command API instead of settings PATCH endpoint
        payload = {"command": {"update_settings": settings}}

        path = f"api/commands/v1/devices/{device_id}/commands?wait=true&use_internal_names=true"
        response = await self._post_request(path, payload)

        # Check for permission denied errors in any of the settings
        if response and "response" in response:
            has_permission_denied = False
            for setting_name, setting_response in response["response"].items():
                if setting_response == "permission denied":
                    has_permission_denied = True
                    _LOGGER.warning(
                        "Permission denied for setting %s on device %s",
                        setting_name,
                        device_id,
                    )

            if has_permission_denied:
                _LOGGER.debug("Elevating access and retrying SmartControl settings")
                elevated = await self.elevate_access(device_id)
                if elevated:
                    _LOGGER.info("Access elevated, retrying SmartControl settings")
                    response = await self._post_request(path, payload)
                else:
                    _LOGGER.error(
                        "Failed to elevate access for device %s, cannot set SmartControl",
                        device_id,
                    )

        return response

    async def set_extra_hot_water(
        self, device_id: str, hours: int = 1, indefinite: bool = False
    ) -> dict[str, Any]:
        """Activate extra hot water for specified number of hours or indefinitely.

        Args:
            device_id: The device ID
            hours: Number of hours to activate (1-24), 0 to cancel
            indefinite: If True, enable indefinitely regardless of hours value

        Returns:
            API response
        """
        _LOGGER.debug(
            "Activating extra hot water for %d hour(s) on device %s (indefinite: %s)",
            hours,
            device_id,
            indefinite,
        )

        if hours == 0 and not indefinite:
            # Cancel extra hot water
            command_payload = {
                "set_additional_hot_water": {
                    "stopTime": None,
                    "indefinite": False,
                    "cancel": True,
                }
            }
        elif indefinite:
            # Enable indefinitely
            command_payload = {
                "set_additional_hot_water": {
                    "stopTime": None,
                    "indefinite": True,
                    "cancel": False,
                }
            }
        else:
            # Calculate stop time (current time + hours)
            stop_time = datetime.now() + timedelta(hours=hours)
            # Format as ISO 8601 string
            stop_time_str = stop_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")

            command_payload = {
                "set_additional_hot_water": {
                    "stopTime": stop_time_str,
                    "indefinite": False,
                    "cancel": False,
                }
            }

        wrapped_payload = {"command": command_payload}

        path = f"api/commands/v1/devices/{device_id}/commands?wait=true&use_internal_names=true"
        return await self._post_request(path, wrapped_payload)

    async def get_access_level(self, device_id: str) -> dict[str, Any]:
        """Get current access level for a device.

        Args:
            device_id: The device ID

        Returns:
            API response with access level information including writeAccessLevel
        """
        path = f"api/internal/v1/auth/device/{device_id}/my-access-level?use_internal_names=true"
        return await self._get_internal_request(path)

    async def elevate_access(self, device_id: str) -> dict[str, Any] | None:
        """Elevate access for a device to enable advanced settings.

        This grants temporary elevated permissions (writeAccessLevel >= 20) required
        for certain commands like dhw_prioritytime.

        Args:
            device_id: The device ID

        Returns:
            API response with updated access level, or None if elevation failed
        """
        _LOGGER.debug("Elevating access for device %s", device_id)

        # Check current access level
        access_data = await self.get_access_level(device_id)
        write_level = access_data.get("writeAccessLevel", 0)

        _LOGGER.debug(
            "Current access level for device %s: writeAccessLevel=%s",
            device_id,
            write_level,
        )

        if write_level >= 20:
            _LOGGER.debug("Access level already sufficient (>= 20)")
            return access_data

        # Access insufficient, elevate it
        _LOGGER.info("Access level insufficient (%s < 20), elevating", write_level)

        # Generate access code
        code_data = await self._generate_access_code(device_id)
        if not code_data:
            _LOGGER.error("Failed to generate access code for device %s", device_id)
            return None

        access_code = code_data.get("accessCode")
        if not access_code:
            _LOGGER.error("No access code in response for device %s", device_id)
            return None

        _LOGGER.debug("Generated access code: %s", access_code)

        # Claim the grant
        if not await self._claim_grant(device_id, access_code):
            _LOGGER.error("Failed to claim grant for device %s", device_id)
            return None

        # Approve the access
        if not await self._approve_access(device_id, access_code):
            _LOGGER.error("Failed to approve access for device %s", device_id)
            return None

        # Get updated access level
        updated_access = await self.get_access_level(device_id)
        new_write_level = updated_access.get("writeAccessLevel", 0)

        _LOGGER.info(
            "Successfully elevated access for device %s: %s -> %s",
            device_id,
            write_level,
            new_write_level,
        )

        return updated_access

    async def _generate_access_code(self, device_id: str) -> dict[str, Any] | None:
        """Generate an access code for a device.

        Args:
            device_id: The device ID

        Returns:
            API response with accessCode, or None if failed
        """
        path = f"api/internal/v1/auth/device/{device_id}/generate-access-code?use_internal_names=true"

        try:
            return await self._post_request(path, {})
        except QvantumApiError as err:
            _LOGGER.error("Failed to generate access code: %s", err)
            return None

    async def _claim_grant(self, device_id: str, access_code: str) -> bool:
        """Claim a grant for a device.

        Args:
            device_id: The device ID
            access_code: The access code to claim

        Returns:
            True if successful, False otherwise
        """
        path = f"api/internal/v1/auth/device/claim-grant?access_code={access_code}&use_internal_names=true"

        try:
            await self._post_request(path, {})
            _LOGGER.debug("Successfully claimed grant for device %s", device_id)
        except QvantumApiError as err:
            _LOGGER.error("Failed to claim grant: %s", err)
            return False
        return True

    async def _approve_access(self, device_id: str, access_code: str) -> bool:
        """Approve an access grant for a device.

        Args:
            device_id: The device ID
            access_code: The access code to approve

        Returns:
            True if successful, False otherwise
        """
        path = f"api/internal/v1/auth/device/{device_id}/access-grants?access_code={access_code}&approve=true&use_internal_names=true"

        try:
            await self._post_request(path, {})
            _LOGGER.debug("Successfully approved access for device %s", device_id)
        except QvantumApiError as err:
            _LOGGER.error("Failed to approve access: %s", err)
            return False
        return True

    async def get_alarms(self, device_id: str) -> dict[str, Any]:
        """Get active alarms for a device.

        Args:
            device_id: The device ID

        Returns:
            API response with alarms
        """
        path = f"api/events/v1/devices/{device_id}/alarms"
        return await self._get_request(path)

    async def get_alarms_inventory(self, device_id: str) -> dict[str, Any]:
        """Get alarm inventory (possible alarms) for a device.

        Args:
            device_id: The device ID

        Returns:
            API response with alarm definitions
        """
        path = f"api/inventory/v1/devices/{device_id}/alarms"
        return await self._get_request(path)


# Re-export for backward compatibility
__all__ = [
    "ApiClientError",
    "ApiConnectionError",
    "AuthenticationError",
    "QvantumApi",
    "QvantumApiError",
]
