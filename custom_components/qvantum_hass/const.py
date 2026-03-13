"""Constants for the Qvantum Heat Pump integration.

This module contains only pure constants shared across all modules.
No entity definitions, no collection infrastructure — those live in
definitions.py (top of the hierarchy).

State mapping dicts (e.g. HP_STATUS_MAP, OP_MODE_MAP) live in the
platform file that uses them (sensor.py or select.py) to co-locate
data with the logic that consumes it.

Organization:
    1. Domain and basic configuration
    2. API endpoints and authentication
    3. Device information
"""

from __future__ import annotations

from typing import Final

# =============================================================================
# Domain and basic configuration constants
# =============================================================================

DOMAIN: Final = "qvantum_hass"

# Configuration keys
CONF_API_KEY: Final = "api_key"

# Polling intervals — not user-configurable; change here to adjust globally
DEFAULT_SCAN_INTERVAL: Final = 30  # seconds — normal coordinator
DEFAULT_FAST_SCAN_INTERVAL: Final = 5  # seconds — fast coordinator (power/current)

# =============================================================================
# API Endpoints and authentication
# =============================================================================

DEFAULT_API_ENDPOINT: Final = "https://api.qvantum.com"
# Currently the same as DEFAULT_API_ENDPOINT; update here if Qvantum
# introduces a separate internal endpoint.
DEFAULT_INTERNAL_API_ENDPOINT: Final = DEFAULT_API_ENDPOINT
DEFAULT_AUTH_SERVER: Final = "https://identitytoolkit.googleapis.com"
DEFAULT_TOKEN_SERVER: Final = "https://securetoken.googleapis.com"

# Firebase Web API key - Intentionally public
# Security is enforced by Firebase Security Rules and user authentication (email/password).
# See: https://firebase.google.com/docs/projects/api-keys
DEFAULT_API_KEY: Final = "AIzaSyCLQ22XHjH8LmId-PB1DY8FBsN53rWTpFw"  # nosemgrep: generic.secrets.security.detected-generic-secret.detected-generic-secret

# =============================================================================
# Device information
# =============================================================================

MANUFACTURER: Final = "Qvantum"
MODEL: Final = "Qvantum Heat Pump"

# =============================================================================
# Service action names
# =============================================================================

SERVICE_SET_ACCESS_LEVEL: Final = "set_access_level"
SERVICE_TOGGLE_AUTO_ELEVATE: Final = "toggle_auto_elevate"
SERVICE_ACTIVATE_EXTRA_HOT_WATER: Final = "activate_extra_hot_water"
SERVICE_CANCEL_EXTRA_HOT_WATER: Final = "cancel_extra_hot_water"
