"""Configuration flow for Qvantum Heat Pump integration.

This module handles the user interface for adding and configuring
the Qvantum integration. It provides:
- Initial setup flow for entering credentials
- Reauthentication flow for refreshing credentials
- Reconfiguration flow for changing credentials
- Validation and error handling
- Duplicate entry prevention
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers import selector

from .api import ApiConnectionError, AuthenticationError, QvantumApi, QvantumApiError
from .const import DEFAULT_API_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): selector.TextSelector(
            selector.TextSelectorConfig(
                type=selector.TextSelectorType.EMAIL,
            ),
        ),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(
                type=selector.TextSelectorType.PASSWORD,
            ),
        ),
    }
)

STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(
                type=selector.TextSelectorType.PASSWORD,
            ),
        ),
    }
)


async def _validate_credentials(email: str, password: str) -> None:
    """Authenticate and verify at least one device is reachable.

    Raises:
        AuthenticationError: Credentials are invalid.
        ApiConnectionError: Could not reach the API.
        QvantumApiError: Unexpected API error.
    """
    api = QvantumApi(email=email, password=password, api_key=DEFAULT_API_KEY)
    try:
        await api.authenticate()
        await api.get_devices()
    finally:
        await api.close()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # pylint: disable=abstract-method
    """Handle a config flow for Qvantum Heat Pump integration."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _validate_credentials(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
            except AuthenticationError as err:
                _LOGGER.warning("Authentication failed: %s", err)
                errors["base"] = "invalid_auth"
            except ApiConnectionError as err:
                _LOGGER.warning("Connection error: %s", err)
                errors["base"] = "cannot_connect"
            except QvantumApiError:
                _LOGGER.exception("API error during authentication")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Qvantum Heat Pump",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, _entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauth — called when credentials are no longer valid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt the user to re-enter their password."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            email = reauth_entry.data[CONF_EMAIL]
            try:
                await _validate_credentials(email, user_input[CONF_PASSWORD])
            except AuthenticationError as err:
                _LOGGER.warning("Reauth failed: %s", err)
                errors["base"] = "invalid_auth"
            except ApiConnectionError as err:
                _LOGGER.warning("Connection error during reauth: %s", err)
                errors["base"] = "cannot_connect"
            except QvantumApiError:
                _LOGGER.exception("API error during reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"email": reauth_entry.data[CONF_EMAIL]},
            data_schema=STEP_REAUTH_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the user to change credentials (email + password)."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                await _validate_credentials(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
            except AuthenticationError as err:
                _LOGGER.warning("Reconfigure auth failed: %s", err)
                errors["base"] = "invalid_auth"
            except ApiConnectionError as err:
                _LOGGER.warning("Connection error during reconfigure: %s", err)
                errors["base"] = "cannot_connect"
            except QvantumApiError:
                _LOGGER.exception("API error during reconfigure")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL])
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                reconfigure_entry.data,
            ),
            errors=errors,
        )
