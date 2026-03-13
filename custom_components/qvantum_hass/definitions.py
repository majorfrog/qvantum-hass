"""Entity definition registry for the Qvantum Heat Pump integration.

This module sits at the top of the platform-file import hierarchy. It
imports ENTITY_DEFS from every platform module and provides the combined
collection plus the metric-name constants used by the coordinator.

Because this module is only imported by coordinator.py and __init__.py
(never by the platform files themselves), there are no circular imports
and no lazy loading is required.

Import hierarchy (no cycles):
    models.py  ←  const.py  ←  api.py
                           ←  coordinator.py  ←  entity.py
                                              ←  sensor.py
                                              ←  binary_sensor.py
                                              ←  select.py
                                              ←  switch.py
                                              ←  number.py
                                              ←  button.py
                                                  ↑  (all platform files)
                                             definitions.py
                                                  ↑
                                             __init__.py
"""

from __future__ import annotations

from dataclasses import replace

from .binary_sensor import ENTITY_DEFS as _binary_sensor_defs
from .button import ENTITY_DEFS as _button_defs
from .models import EntityPlatform, EntitySource, QvantumEntityDef
from .number import ENTITY_DEFS as _number_defs
from .select import ENTITY_DEFS as _select_defs
from .sensor import ENTITY_DEFS as _sensor_defs
from .switch import ENTITY_DEFS as _switch_defs

# =============================================================================
# Collect and tag all entity definitions at import time.
#
# Each definition is tagged with its platform using dataclasses.replace().
# This runs once when the module is first imported — no caching needed.
# =============================================================================

_ALL_ENTITY_DEFS: tuple[QvantumEntityDef, ...] = tuple(
    replace(entity_def, platform=platform)
    for platform, defs in (
        (EntityPlatform.SENSOR, _sensor_defs),
        (EntityPlatform.BINARY_SENSOR, _binary_sensor_defs),
        (EntityPlatform.SELECT, _select_defs),
        (EntityPlatform.SWITCH, _switch_defs),
        (EntityPlatform.NUMBER, _number_defs),
        (EntityPlatform.BUTTON, _button_defs),
    )
    for entity_def in defs
)

# Metric names derived once at import time for use by the coordinator.
_METRIC_NAMES: tuple[str, ...] = tuple(
    sorted(
        {
            e.api_key or e.key
            for e in _ALL_ENTITY_DEFS
            if e.source == EntitySource.INTERNAL_METRICS
        }
    )
)

_FAST_POLLING_METRICS: tuple[str, ...] = tuple(
    sorted(
        {
            e.api_key or e.key
            for e in _ALL_ENTITY_DEFS
            if e.fast_polling and e.source == EntitySource.INTERNAL_METRICS
        }
    )
)


# =============================================================================
# Public API
# =============================================================================


def collect_all_entity_definitions() -> tuple[QvantumEntityDef, ...]:
    """Return all entity definitions tagged with their platform."""
    return _ALL_ENTITY_DEFS


def get_entity_def(key: str) -> QvantumEntityDef | None:
    """Look up an entity definition by key across all platforms.

    Args:
        key: The entity key to look up.

    Returns:
        The entity definition, or None if not found.
    """
    return next((e for e in _ALL_ENTITY_DEFS if e.key == key), None)


def get_entity_defs(
    platform: EntityPlatform | None = None,
    source: EntitySource | None = None,
) -> list[QvantumEntityDef]:
    """Return entity definitions filtered by platform and/or source.

    Args:
        platform: Filter by platform type (e.g., EntityPlatform.SENSOR).
        source: Filter by data source (e.g., EntitySource.INTERNAL_METRICS).

    Returns:
        List of matching entity definitions.
    """
    return [
        e
        for e in _ALL_ENTITY_DEFS
        if (platform is None or e.platform == platform)
        and (source is None or e.source == source)
    ]


def get_metric_names() -> tuple[str, ...]:
    """Return all metric names to request from the internal-metrics API.

    Derived from all entities whose source is INTERNAL_METRICS.
    Uses api_key when set, otherwise falls back to key.
    """
    return _METRIC_NAMES


def get_fast_polling_metrics() -> tuple[str, ...]:
    """Return metric names that use the fast polling coordinator.

    These are power/current sensors that change rapidly (5s updates).
    """
    return _FAST_POLLING_METRICS
