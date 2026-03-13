"""Entity data models for the Qvantum Heat Pump integration.

This module contains the shared entity types used across all platform modules:
- EntityPlatform: HA platform types (sensor, binary_sensor, select, etc.)
- EntitySource: Data source identifiers (internal_metrics, settings, etc.)
- QvantumEntityDef: Frozen dataclass describing one entity.

These live in a dedicated models module (not const.py or entity.py) to avoid
circular imports.  Both const.py and the platform modules import from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from homeassistant.const import EntityCategory


class EntityPlatform(StrEnum):
    """Home Assistant platform types for Qvantum entities."""

    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    SELECT = "select"
    SWITCH = "switch"
    NUMBER = "number"
    BUTTON = "button"


class EntitySource(StrEnum):
    """Data sources for Qvantum entities."""

    INTERNAL_METRICS = "internal_metrics"  # From get_internal_metrics() API
    SETTINGS = "settings"  # From get_settings() API
    STATUS = "status"  # From get_status() (connectivity, metadata, service_access)
    ALARMS = "alarms"  # From get_alarms() API
    ACCESS_LEVEL = "access_level"  # From get_access_level() API
    COMMAND = "command"  # Uses command APIs (buttons, extra hot water)
    COORDINATOR = "coordinator"  # From coordinator internal state (auto_elevate)


@dataclass(frozen=True, slots=True)
class QvantumEntityDef:
    """Single source of truth for one Qvantum entity.

    Every entity in the integration MUST have an entry in ENTITY_DEFINITIONS.
    No entity should be created dynamically from API responses.

    Attributes:
        key: Unique entity key. Used for translation_key and unique_id suffix.
        description: Human-readable description of what the entity represents.
            Since metric names (bt1, bp2_pressure, etc.) are cryptic, this
            comment explains the purpose so developers can understand the list.
        platform: Home Assistant platform type. Automatically set by
            collect_all_entity_definitions() based on the source module.
            Leave as None in ENTITY_DEFS declarations.
        source: Where the entity reads its primary data from (see EntitySource).
        unit: Unit of measurement. Standard strings: "°C", "%", "bar", "Hz",
            "L/min", "W", "kW", "kWh", "A", "rpm", "minutes", "L", or None.
        enabled_by_default: Whether entity is enabled by default in the UI.
            Set to False for technical/diagnostic metrics that most users
            don't need on their dashboard.
        fast_polling: Whether to use the fast polling coordinator (5s vs 30s).
            Only applies to source=INTERNAL_METRICS entities.
        entity_category: Home Assistant entity category.
            - "diagnostic": System/technical information sensors.
            - "config": Configuration/control entities.
            - None: Primary/default entities shown in main controls.
        api_key: API key if different from `key`. Used when the setting or
            metric name in the API differs from the entity key (e.g.,
            select "operation_mode" reads API key "op_mode").
        entity_type: Platform-specific subtype for class dispatch. Each
            platform file defines a factory dict mapping entity_type values
            to constructor callables. When None, the platform's default
            generic class is used. This eliminates the need for hardcoded
            if/elif dispatch chains in async_setup_entry.
    """

    key: str
    description: str
    platform: EntityPlatform | None = None
    source: EntitySource = EntitySource.INTERNAL_METRICS
    unit: str | None = None
    enabled_by_default: bool = True
    fast_polling: bool = False
    entity_category: EntityCategory | None = None
    api_key: str | None = None
    entity_type: str | None = None

    def __post_init__(self) -> None:
        """Coerce string entity_category values to EntityCategory enum instances."""
        if isinstance(self.entity_category, str):
            object.__setattr__(
                self, "entity_category", EntityCategory(self.entity_category)
            )
