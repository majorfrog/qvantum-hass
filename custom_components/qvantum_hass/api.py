"""Qvantum API client for heat pump integration.

This module provides a comprehensive API client for communicating with
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

from datetime import datetime, timedelta
import logging
from typing import Any

import requests

from .const import (
    DEFAULT_API_ENDPOINT,
    DEFAULT_API_KEY,
    DEFAULT_AUTH_SERVER,
    DEFAULT_INTERNAL_API_ENDPOINT,
    DEFAULT_TOKEN_SERVER,
)

_LOGGER = logging.getLogger(__name__)


class QvantumApiError(Exception):
    """Base exception for Qvantum API errors."""


class AuthenticationError(QvantumApiError):
    """Exception raised when authentication fails."""


class ApiConnectionError(QvantumApiError):
    """Exception raised when connection to API fails."""


class QvantumApi:
    """Client for Qvantum API communication.
    
    This class handles all communication with the Qvantum cloud API,
    including authentication, token management, and device operations.
    
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
        """Initialize the API client.
        
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

    def _ensure_tokens_valid(self) -> None:
        """Ensure we have valid authentication tokens."""
        if (
            not self.tokens
            or self.token_expiry is None
            or datetime.now() >= self.token_expiry
        ):
            if self.tokens:
                try:
                    self._refresh_access_token()
                except AuthenticationError:
                    # Refresh failed, do full authentication
                    self.authenticate()
            else:
                self.authenticate()

            # Type assertion: tokens should be set after authentication
            assert self.tokens is not None, "Tokens should be set after authentication"
            self.token_expiry = datetime.now() + timedelta(
                seconds=int(self.tokens["expiresIn"]) - 60
            )

    def _get_request(self, endpoint: str) -> Any:
        """Make a GET request to the API."""
        self._ensure_tokens_valid()
        assert self.tokens is not None, "Tokens should be valid"
        url = f"{self.api_endpoint}/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.tokens['idToken']}",
        }

        _LOGGER.debug("Making API request to %s", url)

        try:
            response = requests.get(url=url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout as err:
            _LOGGER.error("Timeout while making request to %s", url)
            raise ApiConnectionError(f"Request timeout: {err}") from err
        except requests.exceptions.RequestException as err:
            _LOGGER.error("Request failed: %s", err)
            if (
                hasattr(err, "response")
                and err.response
                and err.response.status_code == 401
            ):
                raise AuthenticationError("Authentication failed") from err
            if (
                hasattr(err, "response")
                and err.response
                and err.response.status_code >= 500
            ):
                raise ApiConnectionError(
                    f"Server error {err.response.status_code}"
                ) from err
            raise QvantumApiError(f"API error: {err}") from err

    def _get_internal_request(self, endpoint: str) -> Any:
        """Make a GET request to the internal API."""
        self._ensure_tokens_valid()
        assert self.tokens is not None, "Tokens should be valid"
        url = f"{self.internal_api_endpoint}/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.tokens['idToken']}",
        }

        _LOGGER.debug("Making internal API request to %s", url)

        try:
            response = requests.get(url=url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout as err:
            _LOGGER.error("Timeout while making internal request to %s", url)
            raise ApiConnectionError(f"Request timeout: {err}") from err
        except requests.exceptions.RequestException as err:
            _LOGGER.error("Internal request failed: %s", err)
            if (
                hasattr(err, "response")
                and err.response
                and err.response.status_code == 401
            ):
                raise AuthenticationError("Authentication failed") from err
            if (
                hasattr(err, "response")
                and err.response
                and err.response.status_code >= 500
            ):
                raise ApiConnectionError(
                    f"Internal server error {err.response.status_code}"
                ) from err
            raise QvantumApiError(f"API error: {err}") from err

    def _patch_request(self, endpoint: str, data: dict) -> Any:
        """Make a PATCH request to the API."""
        self._ensure_tokens_valid()
        assert self.tokens is not None, "Tokens should be valid"
        url = f"{self.api_endpoint}/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.tokens['idToken']}",
        }

        _LOGGER.debug("Making PATCH request to %s with data %s", url, data)

        try:
            response = requests.patch(url=url, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout as err:
            _LOGGER.error("Timeout while making PATCH request to %s", url)
            raise ApiConnectionError(f"Request timeout: {err}") from err
        except requests.exceptions.RequestException as err:
            _LOGGER.error("PATCH request failed: %s", err)
            if (
                hasattr(err, "response")
                and err.response
                and err.response.status_code == 401
            ):
                raise AuthenticationError("Authentication failed") from err
            if (
                hasattr(err, "response")
                and err.response
                and err.response.status_code >= 500
            ):
                raise ApiConnectionError(
                    f"Server error {err.response.status_code}"
                ) from err
            raise QvantumApiError(f"API error: {err}") from err

    def _post_request(self, endpoint: str, data: dict) -> Any:
        """Make a POST request to the API."""
        self._ensure_tokens_valid()
        assert self.tokens is not None, "Tokens should be valid"
        url = f"{self.api_endpoint}/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.tokens['idToken']}",
        }

        _LOGGER.debug("Making POST request to %s with data %s", url, data)

        try:
            response = requests.post(url=url, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            # Some endpoints return empty responses (e.g., approve access)
            if response.text:
                return response.json()
            return {}
        except requests.exceptions.Timeout as err:
            _LOGGER.error("Timeout while making POST request to %s", url)
            raise ApiConnectionError(f"Request timeout: {err}") from err
        except requests.exceptions.RequestException as err:
            _LOGGER.error("POST request failed: %s", err)
            if (
                hasattr(err, "response")
                and err.response
                and err.response.status_code == 401
            ):
                raise AuthenticationError("Authentication failed") from err
            if (
                hasattr(err, "response")
                and err.response
                and err.response.status_code >= 500
            ):
                raise ApiConnectionError(
                    f"Server error {err.response.status_code}"
                ) from err
            raise QvantumApiError(f"API error: {err}") from err

    def authenticate(self) -> None:
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
            response = requests.post(
                url=url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Qvantum-HA",
                },
                timeout=30,
            )
            response.raise_for_status()
            self.tokens = response.json()
            _LOGGER.info("Successfully authenticated with Qvantum API")
        except requests.exceptions.Timeout as err:
            _LOGGER.error("Timeout while authenticating")
            raise ApiConnectionError(f"Authentication timeout: {err}") from err
        except requests.exceptions.RequestException as err:
            _LOGGER.error("Authentication failed: %s", err)
            if (
                hasattr(err, "response")
                and err.response
                and err.response.status_code == 401
            ):
                raise AuthenticationError("Invalid credentials") from err
            if (
                hasattr(err, "response")
                and err.response
                and err.response.status_code >= 500
            ):
                raise ApiConnectionError(
                    f"Server error during authentication: {err}"
                ) from err
            raise QvantumApiError(f"Authentication error: {err}") from err

    def _refresh_access_token(self) -> None:
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
            response = requests.post(
                url=url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Qvantum-HA",
                },
                timeout=30,
            )
            response.raise_for_status()
            refresh_data = response.json()

            # Update tokens
            self.tokens.update(
                {
                    "idToken": refresh_data.get("id_token"),
                    "refreshToken": refresh_data.get("refresh_token"),
                    "expiresIn": refresh_data.get("expires_in"),
                }
            )
            _LOGGER.debug("Successfully refreshed access token")
        except requests.exceptions.Timeout as err:
            _LOGGER.error("Timeout while refreshing token")
            raise ApiConnectionError(f"Token refresh timeout: {err}") from err
        except requests.exceptions.RequestException as err:
            _LOGGER.error("Token refresh failed: %s", err)
            if (
                hasattr(err, "response")
                and err.response
                and err.response.status_code == 401
            ):
                raise AuthenticationError("Invalid refresh token") from err
            if (
                hasattr(err, "response")
                and err.response
                and err.response.status_code >= 500
            ):
                raise ApiConnectionError(
                    f"Server error during token refresh: {err}"
                ) from err
            raise QvantumApiError(f"Token refresh error: {err}") from err

    def get_devices(self) -> list[dict[str, Any]]:
        """Get all devices for the user."""
        path = "api/inventory/v1/users/me/devices"
        _LOGGER.debug("Fetching devices")
        response = self._get_request(path)
        devices = response.get("devices", [])
        _LOGGER.info("Found %d device(s)", len(devices))
        return devices

    def get_status(self, device_id: str) -> dict[str, Any]:
        """Get device status."""
        path = f"api/device-info/v1/devices/{device_id}/status?metrics=now"
        _LOGGER.debug("Fetching status for device %s", device_id)
        return self._get_request(path)

    def get_settings(self, device_id: str) -> dict[str, Any]:
        """Get device settings."""
        path = f"api/device-info/v1/devices/{device_id}/settings"
        _LOGGER.debug("Fetching settings for device %s", device_id)
        return self._get_request(path)

    def get_settings_inventory(self, device_id: str) -> dict[str, Any]:
        """Get settings inventory."""
        path = f"api/inventory/v1/devices/{device_id}/settings"
        _LOGGER.debug("Fetching settings inventory for device %s", device_id)
        return self._get_request(path)

    def get_metrics_inventory(self, device_id: str) -> dict[str, Any]:
        """Get metrics inventory."""
        path = f"api/inventory/v1/devices/{device_id}/metrics"
        _LOGGER.debug("Fetching metrics inventory for device %s", device_id)
        return self._get_request(path)

    def get_internal_metrics(
        self, device_id: str, metric_names: list[str]
    ) -> dict[str, Any]:
        """Get internal metrics."""
        metrics_str = "&".join([f"names={name}" for name in metric_names])
        path = f"api/internal/v1/devices/{device_id}/values?use_internal_names=true&timeout=12&{metrics_str}"
        _LOGGER.debug("Fetching internal metrics for device %s", device_id)
        return self._get_internal_request(path)

    def set_setting(self, device_id: str, setting: str, value: Any) -> dict[str, Any]:
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
        response = self._post_request(path, payload)

        # Check if we got a permission denied error in the response
        if response and "response" in response:
            setting_response = response["response"].get(setting)
            if setting_response == "permission denied":
                _LOGGER.warning(
                    "Permission denied for setting %s on device %s, elevating access...",
                    setting,
                    device_id,
                )

                # Elevate access
                if self.elevate_access(device_id):
                    _LOGGER.info(
                        "Access elevated, retrying setting %s to %s",
                        setting,
                        value,
                    )
                    # Retry the setting
                    response = self._post_request(path, payload)
                else:
                    _LOGGER.error(
                        "Failed to elevate access for device %s, cannot set %s",
                        device_id,
                        setting,
                    )

        return response

    def set_smartcontrol(self, device_id: str, sh: int, dhw: int) -> dict[str, Any]:
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
        response = self._post_request(path, payload)

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
                _LOGGER.warning(
                    "Elevating access and retrying SmartControl settings..."
                )
                if self.elevate_access(device_id):
                    _LOGGER.info("Access elevated, retrying SmartControl settings")
                    response = self._post_request(path, payload)
                else:
                    _LOGGER.error(
                        "Failed to elevate access for device %s, cannot set SmartControl",
                        device_id,
                    )

        return response

    def set_extra_hot_water(
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
        return self._post_request(path, wrapped_payload)

    def get_access_level(self, device_id: str) -> dict[str, Any]:
        """Get current access level for a device.

        Args:
            device_id: The device ID

        Returns:
            API response with access level information including writeAccessLevel
        """
        path = f"api/internal/v1/auth/device/{device_id}/my-access-level?use_internal_names=true"
        _LOGGER.debug("Getting access level for device %s", device_id)
        return self._get_internal_request(path)

    def elevate_access(self, device_id: str) -> dict[str, Any] | None:
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
        access_data = self.get_access_level(device_id)
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
        _LOGGER.info("Access level insufficient (%s < 20), elevating...", write_level)

        # Generate access code
        code_data = self._generate_access_code(device_id)
        if not code_data:
            _LOGGER.error("Failed to generate access code for device %s", device_id)
            return None

        access_code = code_data.get("accessCode")
        if not access_code:
            _LOGGER.error("No access code in response for device %s", device_id)
            return None

        _LOGGER.debug("Generated access code: %s", access_code)

        # Claim the grant
        if not self._claim_grant(device_id, access_code):
            _LOGGER.error("Failed to claim grant for device %s", device_id)
            return None

        # Approve the access
        if not self._approve_access(device_id, access_code):
            _LOGGER.error("Failed to approve access for device %s", device_id)
            return None

        # Get updated access level
        updated_access = self.get_access_level(device_id)
        new_write_level = updated_access.get("writeAccessLevel", 0)

        _LOGGER.info(
            "Successfully elevated access for device %s: %s -> %s",
            device_id,
            write_level,
            new_write_level,
        )

        return updated_access

    def _generate_access_code(self, device_id: str) -> dict[str, Any] | None:
        """Generate an access code for a device.

        Args:
            device_id: The device ID

        Returns:
            API response with accessCode, or None if failed
        """
        path = f"api/internal/v1/auth/device/{device_id}/generate-access-code?use_internal_names=true"

        try:
            return self._post_request(path, {})
        except QvantumApiError as err:
            _LOGGER.error("Failed to generate access code: %s", err)
            return None

    def _claim_grant(self, device_id: str, access_code: str) -> bool:
        """Claim a grant for a device.

        Args:
            device_id: The device ID
            access_code: The access code to claim

        Returns:
            True if successful, False otherwise
        """
        path = f"api/internal/v1/auth/device/claim-grant?access_code={access_code}&use_internal_names=true"

        try:
            self._post_request(path, {})
            _LOGGER.debug("Successfully claimed grant for device %s", device_id)
            return True
        except QvantumApiError as err:
            _LOGGER.error("Failed to claim grant: %s", err)
            return False

    def _approve_access(self, device_id: str, access_code: str) -> bool:
        """Approve an access grant for a device.

        Args:
            device_id: The device ID
            access_code: The access code to approve

        Returns:
            True if successful, False otherwise
        """
        path = f"api/internal/v1/auth/device/{device_id}/access-grants?access_code={access_code}&approve=true&use_internal_names=true"

        try:
            self._post_request(path, {})
            _LOGGER.debug("Successfully approved access for device %s", device_id)
            return True
        except QvantumApiError as err:
            _LOGGER.error("Failed to approve access: %s", err)
            return False

    def get_alarms(self, device_id: str) -> dict[str, Any]:
        """Get active alarms for a device.

        Args:
            device_id: The device ID

        Returns:
            API response with alarms
        """
        path = f"api/events/v1/devices/{device_id}/alarms"
        _LOGGER.debug("Fetching alarms for device %s", device_id)
        return self._get_request(path)

    def get_alarms_inventory(self, device_id: str) -> dict[str, Any]:
        """Get alarm inventory (possible alarms) for a device.

        Args:
            device_id: The device ID

        Returns:
            API response with alarm definitions
        """
        path = f"api/inventory/v1/devices/{device_id}/alarms"
        _LOGGER.debug("Fetching alarms inventory for device %s", device_id)
        return self._get_request(path)
