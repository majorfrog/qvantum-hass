"""Test fixtures with mock API responses for Qvantum integration."""

from __future__ import annotations

# Test credentials
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test_password_123"
TEST_USER_INPUT = {
    "email": TEST_EMAIL,
    "password": TEST_PASSWORD,
}

# Mock authentication response
MOCK_AUTH_RESPONSE = {
    "idToken": "mock_id_token_12345",
    "refreshToken": "mock_refresh_token_67890",
    "expiresIn": "3600",
    "localId": "mock_user_id",
    "email": "test@example.com",
}

# Mock devices list response
MOCK_DEVICES_RESPONSE = {
    "devices": [
        {
            "id": "device_123",
            "name": "Heat Pump Living Room",
            "model": "Qvantum Plus",
            "serialNumber": "QV2024-123456",
        }
    ]
}

# Mock status response with key metrics
MOCK_STATUS_RESPONSE = {
    "deviceId": "device_123",
    "timestamp": "2026-02-25T12:00:00Z",
    "online": True,
    "status": "ok",
}

# Mock settings response
MOCK_SETTINGS_RESPONSE = {
    "settings": [
        {
            "name": "target_temperature",
            "value": 22.0,
            "dataType": "float",
            "readOnly": False,
            "min": 15.0,
            "max": 30.0,
            "step": 0.5,
            "description": "Target room temperature",
        },
        {
            "name": "operating_mode",
            "value": "heat",
            "dataType": "string",
            "readOnly": False,
            "options": ["heat", "cool", "auto", "off"],
            "description": "Operating mode",
        },
    ]
}

# Mock settings inventory
MOCK_SETTINGS_INVENTORY_RESPONSE = {
    "settings": [
        {
            "name": "target_temperature",
            "dataType": "float",
            "min": 15.0,
            "max": 30.0,
            "step": 0.5,
            "description": "Target room temperature",
        },
        {
            "name": "operating_mode",
            "dataType": "string",
            "options": ["heat", "cool", "auto", "off"],
            "description": "Operating mode",
        },
    ]
}

# Mock metrics inventory
MOCK_METRICS_INVENTORY_RESPONSE = {
    "metrics": [
        {
            "name": "indoor_temperature",
            "description": "Indoor temperature",
            "unit": "°C",
            "dataType": "float",
        },
        {
            "name": "outdoor_temperature",
            "description": "Outdoor temperature",
            "unit": "°C",
            "dataType": "float",
        },
        {
            "name": "power_consumption",
            "description": "Current power consumption",
            "unit": "W",
            "dataType": "float",
        },
        {
            "name": "cop",
            "description": "Coefficient of Performance",
            "unit": "",
            "dataType": "float",
        },
    ]
}

# Mock internal metrics (actual values)
# Keys must match the internal metric names used by sensor/binary_sensor entity defs.
MOCK_INTERNAL_METRICS_RESPONSE = {
    "values": {
        # Temperature sensors
        "bt1": 5.2,
        "bt10": 45.0,
        "bt11": 40.0,
        "bt30": 52.1,
        # Power / energy sensors
        "powertotal": 1250.0,
        "heatingpower": 3.5,
        "dhwpower": 1.2,
        # Current sensors
        "inputcurrent1": 5.2,
        "inputcurrent2": 4.8,
        "inputcurrent3": 4.9,
        # Flow sensor
        "bf1_l_min": 8.5,
        # Binary metric: heating relay
        "picpin_relay_heat_l1": True,
        "picpin_relay_heat_l2": False,
        # SmartControl flags
        "enable_sc_sh": False,
        "enable_sc_dhw": False,
        "use_adaptive": False,
    }
}

# Mock access level response
# Keys must match what the real API returns (used by coordinator and service handlers).
MOCK_ACCESS_LEVEL_RESPONSE = {
    "writeAccessLevel": 10,
    "readAccessLevel": 10,
    "expiresAt": None,
}

# Mock alarms inventory
MOCK_ALARMS_INVENTORY_RESPONSE = {
    "alarms": [
        {
            "code": "E01",
            "description": "Low pressure alarm",
            "severity": "warning",
        },
        {
            "code": "E02",
            "description": "High pressure alarm",
            "severity": "critical",
        },
    ]
}

# Mock active alarms response (empty - no active alarms)
MOCK_ALARMS_RESPONSE = {"alarms": []}

# Mock active alarms response (with alarm)
# Key must be "is_active" — matches what binary_sensor.py and sensor.py check.
MOCK_ALARMS_ACTIVE_RESPONSE = {
    "alarms": [
        {
            "code": "E01",
            "description": "Low pressure alarm",
            "severity": "warning",
            "timestamp": "2026-02-25T11:30:00Z",
            "is_active": True,
        }
    ]
}

# Mock error responses
MOCK_AUTH_ERROR_RESPONSE = {
    "error": {
        "code": 400,
        "message": "INVALID_LOGIN_CREDENTIALS",
        "errors": [{"message": "Invalid email or password", "domain": "global"}],
    }
}

MOCK_CONNECTION_ERROR_MESSAGE = "Connection timeout"
MOCK_SERVER_ERROR_RESPONSE = {"error": "Internal server error", "status": 500}
