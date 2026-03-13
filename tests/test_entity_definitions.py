"""Tests for Qvantum entity definition collection and integrity.

These tests verify that:
- All entity definitions are properly collected from platform modules
- No duplicate entity keys exist
- Expected entity counts per platform are correct
- Derived constants (metric names, fast polling metrics) are correct
- Entity definitions are well-formed
"""

from __future__ import annotations

from custom_components.qvantum_hass.definitions import (
    collect_all_entity_definitions,
    get_entity_def,
    get_entity_defs,
    get_fast_polling_metrics,
    get_metric_names,
)
from custom_components.qvantum_hass.models import (
    EntityPlatform,
    EntitySource,
)


# =============================================================================
# Expected counts — update these when adding/removing entities
# =============================================================================

EXPECTED_TOTAL = 119
EXPECTED_PER_PLATFORM = {
    EntityPlatform.SENSOR: 77,
    EntityPlatform.BINARY_SENSOR: 18,
    EntityPlatform.SELECT: 11,
    EntityPlatform.SWITCH: 8,
    EntityPlatform.NUMBER: 2,
    EntityPlatform.BUTTON: 3,
}


# =============================================================================
# Collection tests
# =============================================================================


def test_collect_returns_all_entities() -> None:
    """Verify collect_all_entity_definitions returns the expected total."""
    all_defs = collect_all_entity_definitions()
    assert len(all_defs) == EXPECTED_TOTAL, (
        f"Expected {EXPECTED_TOTAL} entity definitions, got {len(all_defs)}"
    )


# =============================================================================
# Duplicate detection
# =============================================================================


def test_no_duplicate_keys() -> None:
    """Verify all entity keys are unique across all platforms."""
    all_defs = collect_all_entity_definitions()
    keys = [e.key for e in all_defs]
    seen: dict[str, EntityPlatform] = {}
    duplicates: list[str] = []

    for entity_def in all_defs:
        if entity_def.key in seen:
            duplicates.append(
                f"  '{entity_def.key}' in {entity_def.platform} "
                f"AND {seen[entity_def.key]}"
            )
        seen[entity_def.key] = entity_def.platform

    assert not duplicates, f"Duplicate entity keys found:\n" + "\n".join(duplicates)


# =============================================================================
# Per-platform counts
# =============================================================================


def test_per_platform_counts() -> None:
    """Verify each platform has the expected number of entities."""
    all_defs = collect_all_entity_definitions()
    counts: dict[EntityPlatform, int] = {}
    for entity_def in all_defs:
        counts[entity_def.platform] = counts.get(entity_def.platform, 0) + 1

    for platform, expected_count in EXPECTED_PER_PLATFORM.items():
        actual = counts.get(platform, 0)
        assert actual == expected_count, (
            f"{platform}: expected {expected_count} entities, got {actual}"
        )


# =============================================================================
# Platform-local ENTITY_DEFS match collection
# =============================================================================


def test_platform_defs_match_collection() -> None:
    """Verify each platform's ENTITY_DEFS is included in the collection.

    This catches the case where a new platform module is added but the
    collect function in const.py is not updated.
    """
    from custom_components.qvantum_hass.sensor import ENTITY_DEFS as sensor_defs
    from custom_components.qvantum_hass.binary_sensor import (
        ENTITY_DEFS as binary_sensor_defs,
    )
    from custom_components.qvantum_hass.select import ENTITY_DEFS as select_defs
    from custom_components.qvantum_hass.switch import ENTITY_DEFS as switch_defs
    from custom_components.qvantum_hass.number import ENTITY_DEFS as number_defs
    from custom_components.qvantum_hass.button import ENTITY_DEFS as button_defs

    all_defs = collect_all_entity_definitions()
    all_keys = {e.key for e in all_defs}

    platform_lists = {
        "sensor": sensor_defs,
        "binary_sensor": binary_sensor_defs,
        "select": select_defs,
        "switch": switch_defs,
        "number": number_defs,
        "button": button_defs,
    }

    for platform_name, defs in platform_lists.items():
        for entity_def in defs:
            assert entity_def.key in all_keys, (
                f"Entity '{entity_def.key}' from {platform_name}.ENTITY_DEFS "
                f"not found in collect_all_entity_definitions()"
            )


# =============================================================================
# Entity definition well-formedness
# =============================================================================


def test_all_descriptions_are_non_empty() -> None:
    """Verify all entities have descriptions."""
    for entity_def in collect_all_entity_definitions():
        assert isinstance(entity_def.description, str) and entity_def.description, (
            f"Entity '{entity_def.key}' has empty description"
        )


def test_fast_polling_only_for_internal_metrics() -> None:
    """Verify fast_polling is only set for internal_metrics entities."""
    for entity_def in collect_all_entity_definitions():
        if entity_def.fast_polling:
            assert entity_def.source == EntitySource.INTERNAL_METRICS, (
                f"Entity '{entity_def.key}' has fast_polling=True "
                f"but source={entity_def.source} (expected INTERNAL_METRICS)"
            )


# =============================================================================
# Lookup function tests
# =============================================================================


def test_get_entity_def_found() -> None:
    """Verify get_entity_def returns a definition for a known key."""
    result = get_entity_def("bt1")
    assert result is not None
    assert result.key == "bt1"
    assert result.platform == EntityPlatform.SENSOR


def test_get_entity_def_not_found() -> None:
    """Verify get_entity_def returns None for an unknown key."""
    assert get_entity_def("nonexistent_entity_xyz") is None


def test_get_entity_defs_by_platform() -> None:
    """Verify get_entity_defs filters by platform correctly."""
    sensors = get_entity_defs(platform=EntityPlatform.SENSOR)
    assert len(sensors) == EXPECTED_PER_PLATFORM[EntityPlatform.SENSOR]
    for entity_def in sensors:
        assert entity_def.platform == EntityPlatform.SENSOR


def test_get_entity_defs_by_source() -> None:
    """Verify get_entity_defs filters by source correctly."""
    settings = get_entity_defs(source=EntitySource.SETTINGS)
    assert len(settings) > 0
    for entity_def in settings:
        assert entity_def.source == EntitySource.SETTINGS


# =============================================================================
# Derived constant tests
# =============================================================================


def test_get_metric_names_no_duplicates() -> None:
    """Verify metric names have no duplicates."""
    names = get_metric_names()
    assert len(names) == len(set(names))


def test_fast_polling_metrics_subset_of_metric_names() -> None:
    """Verify all fast polling metrics are also in the full metric names set."""
    all_names = set(get_metric_names())
    for metric in get_fast_polling_metrics():
        assert metric in all_names, (
            f"Fast polling metric '{metric}' not in get_metric_names()"
        )


def test_expected_fast_polling_count() -> None:
    """Verify the expected number of fast polling metrics."""
    metrics = get_fast_polling_metrics()
    assert len(metrics) == 7, (
        f"Expected 7 fast polling metrics, got {len(metrics)}: {metrics}"
    )
