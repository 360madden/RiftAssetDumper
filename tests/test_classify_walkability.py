"""Tests for scripts/classify_walkability.py."""

from __future__ import annotations

from scripts.classify_walkability import _classify_asset  # noqa: E402

# ---------------------------------------------------------------------------
# _classify_asset unit tests
# ---------------------------------------------------------------------------

class TestClassifyAsset:
    """Exercise every classification branch in _classify_asset."""

    def test_character_is_non_walkable(self) -> None:
        ze = {"category": "character", "name": "common", "confidence": "high"}
        result = _classify_asset("deadbeef00000001", ze, None)
        assert result["label"] == "non_walkable_character"
        assert result["confidence"] == "high"
        assert result["needs_shape_analysis"] is False

    def test_vfx_atmosphere_is_non_walkable_high_confidence(self) -> None:
        ze = {"category": "vfx", "name": "atmosphere", "confidence": "high"}
        result = _classify_asset("deadbeef00000002", ze, None)
        assert result["label"] == "non_walkable_vfx"
        assert result["confidence"] == "high"

    def test_vfx_generic_is_non_walkable_medium_confidence(self) -> None:
        ze = {"category": "vfx", "name": "unknown_vfx", "confidence": "high"}
        result = _classify_asset("deadbeef00000003", ze, None)
        assert result["label"] == "non_walkable_vfx"
        assert result["confidence"] == "medium"

    def test_architecture_is_walkable_structure(self) -> None:
        ze = {
            "category": "world_objects",
            "name": "architecture",
            "confidence": "high",
            "expansion": "vanilla",
            "tuple": "vanilla.world_objects.architecture",
        }
        result = _classify_asset("deadbeef00000004", ze, None)
        assert result["label"] == "walkable_structure"
        assert result["confidence"] == "medium"
        assert result["needs_shape_analysis"] is True

    def test_dungeons_is_walkable_structure(self) -> None:
        ze = {
            "category": "world_objects",
            "name": "dungeons",
            "confidence": "high",
        }
        result = _classify_asset("deadbeef00000005", ze, None)
        assert result["label"] == "walkable_structure"
        assert result["needs_shape_analysis"] is True

    def test_housing_is_potentially_walkable(self) -> None:
        ze = {"category": "world_objects", "name": "housing", "confidence": "high"}
        result = _classify_asset("deadbeef00000006", ze, None)
        assert result["label"] == "potentially_walkable"
        assert result["confidence"] == "low"
        assert result["needs_shape_analysis"] is True

    def test_nature_world_geometry_is_potentially_walkable(self) -> None:
        ze = {"category": "world_objects", "name": "nature", "confidence": "high"}
        # Archive in assets.03x range → world geometry
        se = {"ArchiveName": "assets.037", "SemanticCategories": ["hint:map-zone"]}
        result = _classify_asset("deadbeef00000007", ze, se)
        assert result["label"] == "potentially_walkable"

    def test_nature_outside_world_geometry_is_non_walkable(self) -> None:
        ze = {"category": "world_objects", "name": "nature", "confidence": "high"}
        # Archive in assets.1xx range → not world geometry
        se = {"ArchiveName": "assets.188", "SemanticCategories": ["hint:map-zone"]}
        result = _classify_asset("deadbeef00000008", ze, se)
        assert result["label"] == "non_walkable_nature"

    def test_nature_no_semantic_is_non_walkable(self) -> None:
        ze = {"category": "world_objects", "name": "nature", "confidence": "high"}
        result = _classify_asset("deadbeef00000009", ze, None)
        assert result["label"] == "non_walkable_nature"

    def test_prop_is_non_walkable(self) -> None:
        ze = {"category": "world_objects", "name": "prop", "confidence": "high"}
        result = _classify_asset("deadbeef0000000a", ze, None)
        assert result["label"] == "non_walkable_prop"
        assert result["needs_shape_analysis"] is False

    def test_unknown_world_object_is_potentially_walkable(self) -> None:
        ze = {"category": "world_objects", "name": "unknown_thing", "confidence": "low"}
        result = _classify_asset("deadbeef0000000b", ze, None)
        assert result["label"] == "potentially_walkable"
        assert result["confidence"] == "low"
        assert result["needs_shape_analysis"] is True

    def test_unknown_category_is_unknown(self) -> None:
        ze = {"category": "weird_category", "name": "stuff", "confidence": "low"}
        result = _classify_asset("deadbeef0000000c", ze, None)
        assert result["label"] == "unknown"
        assert result["confidence"] == "unknown"
        assert result["needs_shape_analysis"] is True

    # ----- zone confidence downgrades -----

    def test_zone_low_confidence_downgrades_high_to_medium(self) -> None:
        ze = {"category": "character", "name": "common", "confidence": "low"}
        result = _classify_asset("deadbeef0000000d", ze, None)
        assert result["confidence"] == "medium"
        assert "downgrade" in result["rationale"]

    def test_zone_medium_confidence_downgrades_high_to_medium(self) -> None:
        ze = {"category": "character", "name": "common", "confidence": "medium"}
        result = _classify_asset("deadbeef0000000e", ze, None)
        assert result["confidence"] == "medium"
        assert "downgrade" in result["rationale"]

    def test_zone_high_confidence_preserves_high(self) -> None:
        ze = {"category": "character", "name": "common", "confidence": "high"}
        result = _classify_asset("deadbeef0000000f", ze, None)
        assert result["confidence"] == "high"
        assert "downgrade" not in result["rationale"]

    # ----- edge cases -----

    def test_none_zone_entry_is_unknown(self) -> None:
        result = _classify_asset("deadbeef00000010", None, None)
        assert result["label"] == "unknown"
        assert result["confidence"] == "unknown"
        assert result["zone"]["category"] is None

    def test_none_semantic_entry_does_not_crash(self) -> None:
        ze = {"category": "world_objects", "name": "architecture", "confidence": "high"}
        result = _classify_asset("deadbeef00000011", ze, None)
        assert result["label"] == "walkable_structure"
        assert result["semantic"]["archive"] is None
        assert result["semantic"]["categories"] == []

    def test_empty_semantic_categories(self) -> None:
        ze = {"category": "world_objects", "name": "architecture", "confidence": "high"}
        se = {"ArchiveName": "assets.050", "SemanticCategories": []}
        result = _classify_asset("deadbeef00000012", ze, se)
        assert result["label"] == "walkable_structure"

    # ----- rationale -----

    def test_rationale_is_non_empty(self) -> None:
        ze = {"category": "world_objects", "name": "dungeons", "confidence": "high"}
        result = _classify_asset("deadbeef00000013", ze, None)
        assert len(result["rationale"]) > 0
        assert "dungeons" in result["rationale"]

    # ----- zone data passthrough -----

    def test_zone_data_passthrough(self) -> None:
        ze = {
            "category": "world_objects",
            "name": "architecture",
            "expansion": "vanilla",
            "tuple": "vanilla.world_objects.architecture",
            "confidence": "high",
        }
        result = _classify_asset("deadbeef00000014", ze, None)
        assert result["zone"]["expansion"] == "vanilla"
        assert result["zone"]["tuple"] == "vanilla.world_objects.architecture"
        assert result["zone"]["zone_confidence"] == "high"
