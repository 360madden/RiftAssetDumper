"""Tests for scripts/combine_walkability_scores.py."""

from __future__ import annotations

from scripts.combine_walkability_scores import combined_label  # noqa: E402


class TestCombinedLabel:
    """Decision rules for combining shape + slope into walkability labels."""

    # Floor + PROMISING series
    def test_floor_promising(self) -> None:
        label, conf = combined_label("floor", "PROMISING")
        assert label == "walkable_floor"
        assert conf == "high"

    def test_floor_promising_with_caveats(self) -> None:
        label, conf = combined_label("floor", "PROMISING_WITH_CAVEATS")
        assert label == "walkable_floor"
        assert conf == "high"

    # Floor + BLOCKED
    def test_floor_blocked(self) -> None:
        label, conf = combined_label("floor", "BLOCKED")
        assert label == "non_walkable_decorative"
        assert conf == "high"

    # Platform + PROMISING series
    def test_platform_promising(self) -> None:
        label, conf = combined_label("platform", "PROMISING")
        assert label == "walkable_platform"
        assert conf == "high"

    def test_platform_promising_with_caveats(self) -> None:
        label, conf = combined_label("platform", "PROMISING_WITH_CAVEATS")
        assert label == "walkable_platform"
        assert conf == "high"

    # Platform + BLOCKED
    def test_platform_blocked(self) -> None:
        label, conf = combined_label("platform", "BLOCKED")
        assert label == "non_walkable_steep_ramp"
        assert conf == "medium"

    # Structure + PROMISING series
    def test_structure_promising(self) -> None:
        label, conf = combined_label("structure", "PROMISING")
        assert label == "walkable_structure"
        assert conf == "medium"

    def test_structure_promising_with_caveats(self) -> None:
        label, conf = combined_label("structure", "PROMISING_WITH_CAVEATS")
        assert label == "walkable_structure"
        assert conf == "medium"

    # Structure + BLOCKED
    def test_structure_blocked(self) -> None:
        label, conf = combined_label("structure", "BLOCKED")
        assert label == "non_walkable_vertical"
        assert conf == "medium"

    # Wall_pillar + BLOCKED
    def test_wall_pillar_blocked(self) -> None:
        label, conf = combined_label("wall_pillar", "BLOCKED")
        assert label == "non_walkable_wall"
        assert conf == "high"

    # Wall_pillar + PROMISING (suspicious)
    def test_wall_pillar_promising(self) -> None:
        label, conf = combined_label("wall_pillar", "PROMISING")
        assert label == "review_wall_walkable"
        assert conf == "low"

    def test_wall_pillar_promising_with_caveats(self) -> None:
        label, conf = combined_label("wall_pillar", "PROMISING_WITH_CAVEATS")
        assert label == "review_wall_walkable"
        assert conf == "low"

    # Unknown shape/slope
    def test_unknown_shape_with_promising(self) -> None:
        label, conf = combined_label("unknown_shape", "PROMISING")
        assert label == "unknown"
        assert conf == "unknown"

    def test_floor_with_unknown_slope(self) -> None:
        label, conf = combined_label("floor", "UNKNOWN_VERDICT")
        assert label == "non_walkable_decorative"  # floor + non-PROMISING = decorative
        assert conf == "high"

    # Edge: empty strings
    def test_empty_shape_and_slope(self) -> None:
        label, conf = combined_label("", "")
        assert label == "unknown"
        assert conf == "unknown"
