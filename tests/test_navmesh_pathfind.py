"""Tests for scripts/navmesh_pathfind.py."""

from __future__ import annotations

import pytest

from scripts.navmesh_pathfind import (
    compute_path_distance,
    extract_waypoints_from_straight_path,
    parse_coords,
    validate_path,
)


class TestParseCoords:
    """Test coordinate string parsing."""

    def test_basic_coords(self) -> None:
        """Standard comma-separated coordinates."""
        assert parse_coords("1.0,2.0,3.0") == (1.0, 2.0, 3.0)

    def test_negative_coords(self) -> None:
        """Negative coordinates."""
        assert parse_coords("-10.5,0.0,-99.9") == (-10.5, 0.0, -99.9)

    def test_integer_coords(self) -> None:
        """Integer-valued coordinates."""
        assert parse_coords("100,200,300") == (100.0, 200.0, 300.0)

    def test_whitespace_around_coords(self) -> None:
        """Whitespace around coordinates should be stripped."""
        assert parse_coords("  1.0 , 2.0 , 3.0  ") == (1.0, 2.0, 3.0)

    def test_too_few_values_raises(self) -> None:
        """Two values should raise ValueError."""
        with pytest.raises(ValueError):
            parse_coords("1.0,2.0")

    def test_too_many_values_raises(self) -> None:
        """Four values should raise ValueError."""
        with pytest.raises(ValueError):
            parse_coords("1.0,2.0,3.0,4.0")

    def test_non_numeric_raises(self) -> None:
        """Non-numeric values should raise ValueError."""
        with pytest.raises(ValueError):
            parse_coords("abc,def,ghi")

    def test_empty_string_raises(self) -> None:
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError):
            parse_coords("")


class TestExtractWaypointsFromStraightPath:
    """Test StraightPathItem to waypoint dict conversion."""

    def test_empty_list(self) -> None:
        """Empty input → empty output."""
        assert extract_waypoints_from_straight_path([]) == []

    def test_single_item(self) -> None:
        """A single StraightPathItem-like mock object."""

        class MockItem:
            def getPos(self) -> list[float]:  # noqa: N802
                return [1.0, 2.0, 3.0]

            def getFlags(self) -> int:  # noqa: N802
                return 1

            def getRef(self) -> int:  # noqa: N802
                return 42

        result = extract_waypoints_from_straight_path([MockItem()])
        assert len(result) == 1
        assert result[0]["pos"] == [1.0, 2.0, 3.0]
        assert result[0]["flags"] == 1
        assert result[0]["poly_ref"] == 42

    def test_multiple_items(self) -> None:
        """Multiple items should produce a list of dicts."""

        class MockItem:
            def __init__(self, pos: list[float], flags: int, ref: int) -> None:
                self._pos = pos
                self._flags = flags
                self._ref = ref

            def getPos(self) -> list[float]:  # noqa: N802
                return self._pos

            def getFlags(self) -> int:  # noqa: N802
                return self._flags

            def getRef(self) -> int:  # noqa: N802
                return self._ref

        items = [
            MockItem([0.0, 0.0, 0.0], 1, 10),
            MockItem([5.0, 1.0, 5.0], 0, 20),
            MockItem([10.0, 2.0, 10.0], 2, 30),
        ]
        result = extract_waypoints_from_straight_path(items)
        assert len(result) == 3
        assert result[0]["pos"] == [0.0, 0.0, 0.0]
        assert result[1]["pos"] == [5.0, 1.0, 5.0]
        assert result[2]["pos"] == [10.0, 2.0, 10.0]
        assert result[2]["flags"] == 2
        assert result[2]["poly_ref"] == 30


class TestComputePathDistance:
    """Test path distance computation."""

    def test_empty_path(self) -> None:
        """Empty path → 0.0 distance."""
        assert compute_path_distance([]) == 0.0

    def test_single_waypoint(self) -> None:
        """Single waypoint → 0.0 distance (no segments)."""
        wp = [{"pos": [1.0, 2.0, 3.0]}]
        assert compute_path_distance(wp) == 0.0

    def test_two_waypoints_straight(self) -> None:
        """Two waypoints 10 units apart on one axis."""
        wp = [{"pos": [0.0, 0.0, 0.0]}, {"pos": [10.0, 0.0, 0.0]}]
        assert compute_path_distance(wp) == 10.0

    def test_two_waypoints_diagonal(self) -> None:
        """Two waypoints in 3D diagonal."""
        wp = [{"pos": [0.0, 0.0, 0.0]}, {"pos": [3.0, 4.0, 0.0]}]
        assert compute_path_distance(wp) == 5.0  # 3-4-5 triangle

    def test_three_waypoints(self) -> None:
        """Three waypoints forming an L-shaped path."""
        wp = [
            {"pos": [0.0, 0.0, 0.0]},
            {"pos": [3.0, 0.0, 0.0]},
            {"pos": [3.0, 4.0, 0.0]},
        ]
        assert compute_path_distance(wp) == 7.0  # 3 + 4

    def test_negative_directions(self) -> None:
        """Path going in negative direction."""
        wp = [{"pos": [5.0, 5.0, 5.0]}, {"pos": [0.0, 0.0, 0.0]}]
        expected = 5.0 * 3**0.5  # sqrt(75) = 5*sqrt(3)
        assert abs(compute_path_distance(wp) - round(expected, 4)) < 0.01


class TestValidatePath:
    """Test path validation checks."""

    def test_empty_path(self) -> None:
        """Empty path → has_waypoints=False, count=0."""
        checks = validate_path([], (0, 0, 0), (10, 0, 0))
        assert checks["has_waypoints"] is False
        assert checks["waypoint_count"] == 0
        assert checks["start_matches"] is False
        assert checks["goal_matches"] is False

    def test_single_waypoint(self) -> None:
        """Single waypoint → count=1, no segment validation."""
        checks = validate_path([{"pos": [1.0, 0.0, 0.0]}], (1, 0, 0), (10, 0, 0))
        assert checks["has_waypoints"] is True
        assert checks["waypoint_count"] == 1
        assert checks["start_matches"] is False  # Need >=2 for match check
        assert checks["goal_matches"] is False

    def test_valid_path_start_and_goal_match(self) -> None:
        """A straight path where start and goal match endpoints."""
        wp = [
            {"pos": [0.0, 0.0, 0.0]},
            {"pos": [5.0, 0.0, 0.0]},
            {"pos": [10.0, 0.0, 0.0]},
        ]
        checks = validate_path(wp, (0, 0, 0), (10, 0, 0))
        assert checks["has_waypoints"] is True
        assert checks["waypoint_count"] == 3
        assert checks["start_matches"] is True
        assert checks["goal_matches"] is True
        assert checks["total_distance"] == 10.0
        assert checks["no_backward_segments"] is True

    def test_start_not_matching(self) -> None:
        """Start waypoint far from requested start position."""
        wp = [{"pos": [100.0, 0.0, 0.0]}, {"pos": [110.0, 0.0, 0.0]}]
        checks = validate_path(wp, (0, 0, 0), (110, 0, 0))
        assert checks["start_matches"] is False
        assert checks["goal_matches"] is True

    def test_backward_segment_detected(self) -> None:
        """A path that goes forward then backward."""
        wp = [
            {"pos": [0.0, 0.0, 0.0]},
            {"pos": [10.0, 0.0, 0.0]},
            {"pos": [1.0, 0.0, 0.0]},  # Backward!
        ]
        checks = validate_path(wp, (0, 0, 0), (1, 0, 0))
        assert checks["no_backward_segments"] is False

    def test_no_backward_with_only_two_waypoints(self) -> None:
        """Two waypoints → no backward check (need >=3)."""
        wp = [{"pos": [0.0, 0.0, 0.0]}, {"pos": [10.0, 0.0, 0.0]}]
        checks = validate_path(wp, (0, 0, 0), (10, 0, 0))
        assert checks["no_backward_segments"] is True

    def test_total_distance_computed(self) -> None:
        """Verify total_distance is computed and included."""
        wp = [
            {"pos": [0.0, 0.0, 0.0]},
            {"pos": [3.0, 0.0, 0.0]},
            {"pos": [3.0, 4.0, 0.0]},
        ]
        checks = validate_path(wp, (0, 0, 0), (3, 4, 0))
        assert checks["total_distance"] == 7.0
