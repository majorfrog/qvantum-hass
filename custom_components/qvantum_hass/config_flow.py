"""Configuration flow for Qvantum Heat Pump integration.

This module handles the user interface for adding and configuring
the Qvantum integration. It provides:
- Initial setup flow for entering credentials
- Options flow for adjusting scan interval
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

from .api import QvantumApi
from .const import (
    CONF_FAST_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_API_KEY,
    DEFAULT_FAST_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

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


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qvantum Heat Pump integration.

    This class handles the configuration flow when a user adds the
    integration through the UI. It validates credentials and prevents
    duplicate entries.
    """

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return QvantumOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow.

        Prompts the user for their Qvantum account credentials and
        validates them by attempting to authenticate and fetch devices.

        Args:
            user_input: Form data from the user (None on first call)

        Returns:
            Form to show or entry creation result
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the user input
            api = QvantumApi(
                email=user_input[CONF_EMAIL],
                password=user_input[CONF_PASSWORD],
                api_key=DEFAULT_API_KEY,
            )

            try:
                # Try to authenticate
                await self.hass.async_add_executor_job(api.authenticate)

                # Get devices to verify connection
                devices = await self.hass.async_add_executor_job(api.get_devices)

                if not devices:
                    errors["base"] = "no_devices"
                else:
                    # Create entry
                    await self.async_set_unique_id(user_input[CONF_EMAIL])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=user_input[CONF_EMAIL],
                        data=user_input,
                    )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error authenticating with Qvantum API")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class QvantumOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Qvantum integration options.

    Allows users to configure the scan interval for data updates
    after the integration has been set up. Two separate intervals:
    - Normal scan interval: For temperature/status sensors (default 30s)
    - Fast scan interval: For power/current sensors (default 5s)
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options flow.

        Allows users to adjust both scan intervals for data updates.
        The integration will reload when options are saved.

        Args:
            user_input: Form data from the user (None on first call)

        Returns:
            Form to show or options update result
        """
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL,
                            DEFAULT_SCAN_INTERVAL,
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                    vol.Optional(
                        CONF_FAST_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_FAST_SCAN_INTERVAL,
                            DEFAULT_FAST_SCAN_INTERVAL,
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
                }
            ),
        )
