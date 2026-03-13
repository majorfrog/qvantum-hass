"""Pydantic schemas for Qvantum API response validation.

This module defines structured data models for API responses to ensure
data integrity and provide clear typing throughout the integration.
Validates response structure and provides safe fallbacks for missing data.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class DeviceResponse(BaseModel):
    """Device information from API."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str | None = None
    model: str | None = None
    serial_number: str | None = Field(None, alias="serialNumber")


class DevicesListResponse(BaseModel):
    """Response containing list of devices."""

    devices: list[DeviceResponse] = Field(default_factory=list)


class SettingItem(BaseModel):
    """Individual setting from API.

    ``value`` is present in the settings-values response but absent in the
    settings-inventory response (which only describes the schema). Making it
    optional with a ``None`` default allows the same model to be used for both.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str
    value: Any = None
    data_type: str | None = Field(None, alias="dataType")
    read_only: bool = Field(False, alias="readOnly")
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: list[str] | None = None
    description: str | None = None


class SettingsResponse(BaseModel):
    """Settings response from API."""

    settings: list[SettingItem] = Field(default_factory=list)


class MetricItem(BaseModel):
    """Individual metric from inventory."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str | None = None
    unit: str | None = None
    data_type: str | None = Field(None, alias="dataType")


class MetricsInventoryResponse(BaseModel):
    """Metrics inventory response."""

    metrics: list[MetricItem] = Field(default_factory=list)


class SettingsInventoryResponse(BaseModel):
    """Settings inventory response."""

    settings: list[SettingItem] = Field(default_factory=list)


class InternalMetricsResponse(BaseModel):
    """Internal metrics values response."""

    values: dict[str, Any] = Field(default_factory=dict)

    @field_validator("values", mode="before")
    @classmethod
    def ensure_dict(cls, v: Any) -> dict[str, Any]:
        """Ensure values is a dictionary."""
        if isinstance(v, dict):
            return v
        return {}


class AlarmItem(BaseModel):
    """Individual alarm."""

    id: str
    name: str | None = None
    description: str | None = None
    severity: str | None = None
    timestamp: str | None = None
    active: bool = True


class AlarmsResponse(BaseModel):
    """Alarms response from API."""

    alarms: list[AlarmItem] = Field(default_factory=list)


class AlarmsInventoryResponse(BaseModel):
    """Alarms inventory (possible alarms)."""

    alarms: list[AlarmItem] = Field(default_factory=list)


class AccessLevelResponse(BaseModel):
    """Access level information."""

    model_config = ConfigDict(populate_by_name=True)

    write_access_level: int = Field(10, alias="writeAccessLevel")
    read_access_level: int = Field(10, alias="readAccessLevel")
    expires_at: str | None = Field(None, alias="expiresAt")


class StatusResponse(BaseModel):
    """Device status response."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # Status structure varies by device, keep flexible
    metrics: dict[str, Any] | None = None
    timestamp: str | None = None


def validate_response(response_data: Any, model: type[_ModelT]) -> _ModelT:
    """Validate API response against a pydantic model.

    Args:
        response_data: Raw API response data
        model: Pydantic model class to validate against

    Returns:
        Validated model instance

    Raises:
        ValueError: If validation fails
    """
    try:
        return model.model_validate(response_data)
    except Exception as err:
        raise ValueError(f"Response validation failed: {err}") from err
