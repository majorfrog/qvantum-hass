"""Diagnostics support for Qvantum Heat Pump integration.

This module provides diagnostic data collection for troubleshooting
and debugging purposes. It safely redacts sensitive information while
providing comprehensive system state information.

The diagnostics include:
- Config entry information
- Device details
- Coordinator state
- API response data
- Settings and metrics inventories
- Access level information
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, DOMAIN

# Fields to redact from diagnostic data for privacy and security
TO_REDACT = {
    CONF_PASSWORD,
    CONF_EMAIL,
    CONF_API_KEY,
    "email",
    "password",
    "api_key",
    "idToken",
    "refreshToken",
    "localId",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        Dictionary with diagnostic data
    """
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    devices = data["devices"]

    diagnostics_data = {
        "config_entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
        },
        "devices": [],
    }

    for device in devices:
        device_id = device["id"]
        coordinator = coordinators.get(device_id)

        device_info = {
            "device_id": device_id,
            "device_name": device.get("name", "Unknown"),
            "device_type": device.get("type", "Unknown"),
        }

        if coordinator:
            device_info["coordinator"] = {
                "update_interval": str(coordinator.update_interval),
                "last_update_success": coordinator.last_update_success,
            }

            if coordinator.data:
                # Include coordinator data (redacted where needed)
                device_info["data"] = {
                    "has_status": "status" in coordinator.data,
                    "has_settings": "settings" in coordinator.data,
                    "has_internal_metrics": "internal_metrics" in coordinator.data,
                    "has_settings_inventory": coordinator.data.get("settings_inventory")
                    is not None,
                    "has_metrics_inventory": coordinator.data.get("metrics_inventory")
                    is not None,
                    "has_alarms_inventory": coordinator.data.get("alarms_inventory")
                    is not None,
                }

                # Include full status data (connectivity, metrics, etc.)
                if "status" in coordinator.data:
                    device_info["status"] = coordinator.data["status"]

                # Include internal metrics (all sensor values)
                if "internal_metrics" in coordinator.data:
                    device_info["internal_metrics"] = coordinator.data[
                        "internal_metrics"
                    ]

                # Include settings data (configuration values)
                if "settings" in coordinator.data:
                    device_info["settings"] = coordinator.data["settings"]

                # Include access level information
                if "access_level" in coordinator.data:
                    device_info["access_level"] = coordinator.data["access_level"]

                # Include inventories (metadata about available metrics/settings)
                if coordinator.data.get("settings_inventory"):
                    device_info["settings_inventory"] = coordinator.data[
                        "settings_inventory"
                    ]

                if coordinator.data.get("metrics_inventory"):
                    device_info["metrics_inventory"] = coordinator.data[
                        "metrics_inventory"
                    ]

                if coordinator.data.get("alarms_inventory"):
                    device_info["alarms_inventory"] = coordinator.data[
                        "alarms_inventory"
                    ]

                # Include alarm info if present
                if coordinator.data.get("alarms"):
                    alarms_data = coordinator.data["alarms"]
                    device_info["alarms"] = {
                        "alarm_count": len(alarms_data.get("alarms", [])),
                        "all_alarms": alarms_data.get("alarms", []),
                        "active_alarms": [
                            {
                                "code": a.get("code"),
                                "severity": a.get("severity"),
                                "type": a.get("type"),
                                "is_active": a.get("is_active"),
                                "created_at": a.get("created_at"),
                                "resolved_at": a.get("resolved_at"),
                            }
                            for a in alarms_data.get("alarms", [])
                            if a.get("is_active", False)
                        ],
                    }

        diagnostics_data["devices"].append(device_info)

    return diagnostics_data
