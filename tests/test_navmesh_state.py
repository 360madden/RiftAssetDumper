"""Tests for scripts/navmesh_state.py — NM-4 Runtime Bridge.

Pure-Python tests; no JVM, no live game. Mocks implement both
PositionSource and NavmeshQueryProvider protocols structurally.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from scripts.navmesh_state import (
    DEFAULT_TELEPORT_THRESHOLD,
    LiveMemoryPositionSource,
    NavmeshQueryProvider,
    NavmeshState,
    PlayerPosition,
    PositionSource,
    StaticPositionSource,
)

# ── Mocks ────────────────────────────────────────────────────────────────


class MockPositionSource:
    """PositionSource returning scripted positions with monotonic timestamps."""

    def __init__(self, positions: list[tuple[float, float, float]]) -> None:
        self._positions = list(positions)
        self._idx = 0

    def get_position(self) -> PlayerPosition:
        if self._idx >= len(self._positions):
            raise RuntimeError("MockPositionSource exhausted")
        x, y, z = self._positions[self._idx]
        self._idx += 1
        return PlayerPosition(x=x, y=y, z=z, timestamp=float(self._idx))


class MockNavmeshQuery:
    """NavmeshQueryProvider with explicit scripted poly refs and a path result."""

    def __init__(
        self,
        *,
        scripted_polys: list[tuple[int, tuple[float, float, float]]] | None = None,
        fail_nearest_poly: bool = False,
        path_result: dict | None = None,
    ) -> None:
        self.queried: list[tuple[float, float, float]] = []
        self._fail = fail_nearest_poly
        self._scripted = list(scripted_polys or [])
        self._idx = 0
        self.path_calls: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
        self._path_result = path_result or {
            "success": True,
            "waypoints": [{"pos": [0.0, 0.0, 0.0]}, {"pos": [10.0, 0.0, 0.0]}],
            "raw_path": [1, 2],
            "waypoint_count": 2,
        }

    def find_nearest_poly(
        self,
        x: float,
        y: float,
        z: float,
        *,
        search_extents: tuple[float, float, float] = (50.0, 50.0, 50.0),
    ) -> tuple[int, tuple[float, float, float]]:
        self.queried.append((x, y, z))
        if self._fail:
            raise RuntimeError("Mock: find_nearest_poly failed")
        if self._idx < len(self._scripted):
            poly_ref, snapped = self._scripted[self._idx]
            self._idx += 1
            return (poly_ref, snapped)
        return (1, (x, y, z))

    def find_path(
        self,
        start: tuple[float, float, float],
        goal: tuple[float, float, float],
        *,
        smooth: bool = True,
        search_extents: tuple[float, float, float] = (50.0, 50.0, 50.0),
    ) -> dict:
        self.path_calls.append((start, goal))
        return self._path_result


class MockScanner:
    """Mock RIFTMemoryScanner for LiveMemoryPositionSource."""

    def __init__(
        self,
        return_value: tuple[float, float, float] = (10.0, 20.0, 30.0),
        raise_exc: Exception | None = None,
    ) -> None:
        self._return_value = return_value
        self._raise_exc = raise_exc
        self.calls = 0

    def get_position(self) -> tuple[float, float, float]:
        self.calls += 1
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._return_value


# ── Fixtures ──────────────────────────────────────────────────────────────


IDENTITY_TRANSFORM: dict[str, Any] = {
    "scale": [1.0, 1.0, 1.0],
    "offset": [0.0, 0.0, 0.0],
    "axis_mapping": [1, 1, 1],
}

SCALE_10_TRANSFORM: dict[str, Any] = {
    "scale": [10.0, 10.0, 10.0],
    "offset": [0.0, 5.0, 0.0],
    "axis_mapping": [1, 1, 1],
}


# ── PlayerPosition ───────────────────────────────────────────────────────


class TestPlayerPosition:
    def test_as_tuple(self) -> None:
        p = PlayerPosition(x=1.0, y=2.0, z=3.0, timestamp=100.0)
        assert p.as_tuple() == (1.0, 2.0, 3.0)

    def test_frozen(self) -> None:
        p = PlayerPosition(x=1.0, y=2.0, z=3.0, timestamp=100.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.x = 5.0  # type: ignore[misc]


# ── StaticPositionSource ─────────────────────────────────────────────────


class TestStaticPositionSource:
    def test_returns_first_position(self) -> None:
        src = StaticPositionSource([(0.0, 0.0, 0.0)])
        pos = src.get_position()
        assert pos.as_tuple() == (0.0, 0.0, 0.0)

    def test_advances_through_sequence(self) -> None:
        src = StaticPositionSource([(1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0)])
        assert src.get_position().as_tuple() == (1.0, 2.0, 3.0)
        assert src.get_position().as_tuple() == (4.0, 5.0, 6.0)
        assert src.get_position().as_tuple() == (7.0, 8.0, 9.0)

    def test_loop_wraps_around(self) -> None:
        src = StaticPositionSource([(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)], loop=True)
        seen = [src.get_position().x for _ in range(5)]
        assert seen == [1.0, 2.0, 1.0, 2.0, 1.0]

    def test_no_loop_holds_last_when_exhausted(self) -> None:
        src = StaticPositionSource([(1.0, 2.0, 3.0)])
        for _ in range(3):
            assert src.get_position().as_tuple() == (1.0, 2.0, 3.0)

    def test_empty_sequence_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            StaticPositionSource([])

    def test_protocol_conformance(self) -> None:
        src = StaticPositionSource([(0.0, 0.0, 0.0)])
        assert isinstance(src, PositionSource)


# ── LiveMemoryPositionSource ─────────────────────────────────────────────


class TestLiveMemoryPositionSource:
    def test_wraps_scanner_get_position(self) -> None:
        scanner = MockScanner(return_value=(10.0, 20.0, 30.0))
        src = LiveMemoryPositionSource(scanner)
        pos = src.get_position()
        assert pos.as_tuple() == (10.0, 20.0, 30.0)
        assert scanner.calls == 1

    def test_injects_timestamp_via_time_func(self) -> None:
        scanner = MockScanner()
        ts = {"v": 100.0}
        src = LiveMemoryPositionSource(scanner, time_func=lambda: ts["v"])
        first = src.get_position()
        ts["v"] = 200.0
        second = src.get_position()
        assert second.timestamp > first.timestamp
        assert first.timestamp == 100.0
        assert second.timestamp == 200.0

    def test_propagates_scanner_error(self) -> None:
        scanner = MockScanner(raise_exc=RuntimeError("memory read failed"))
        src = LiveMemoryPositionSource(scanner)
        with pytest.raises(RuntimeError, match="memory read failed"):
            src.get_position()

    def test_protocol_conformance(self) -> None:
        scanner = MockScanner()
        src = LiveMemoryPositionSource(scanner)
        assert isinstance(src, PositionSource)


# ── NavmeshState.update ──────────────────────────────────────────────────


class TestNavmeshStateUpdate:
    def test_first_update_records_last_memory_pos(self) -> None:
        query = MockNavmeshQuery(scripted_polys=[(7, (1.0, 2.0, 3.0))])
        state = NavmeshState(
            position_source=MockPositionSource([(5.0, 5.0, 5.0)]),
            query_provider=query,
            coord_transform=IDENTITY_TRANSFORM,
        )
        status = state.update()
        assert status.on_navmesh is True
        assert status.poly_ref == 7
        assert status.memory_pos == (5.0, 5.0, 5.0)
        assert status.teleport_detected is False
        assert state.last_memory_pos is not None
        assert state.last_memory_pos.as_tuple() == (5.0, 5.0, 5.0)
        assert state.last_obj_pos == (5.0, 5.0, 5.0)
        assert state.update_count == 1

    def test_query_projection_with_identity_transform_passes_through(self) -> None:
        query = MockNavmeshQuery(scripted_polys=[(1, (0.0, 0.0, 0.0))])
        state = NavmeshState(
            position_source=MockPositionSource([(123.0, 456.0, 789.0)]),
            query_provider=query,
            coord_transform=IDENTITY_TRANSFORM,
        )
        state.update()
        # find_nearest_poly should be called with the OBJ pos (== memory pos here)
        assert query.queried == [(123.0, 456.0, 789.0)]

    def test_query_projection_with_scale_10_transform(self) -> None:
        transform = SCALE_10_TRANSFORM
        # Memory (100, 105, 200) → OBJ ((100-0)/10, (105-5)/10, (200-0)/10) = (10.0, 10.0, 20.0)
        query = MockNavmeshQuery(scripted_polys=[(1, (10.0, 10.0, 20.0))])
        state = NavmeshState(
            position_source=MockPositionSource([(100.0, 105.0, 200.0)]),
            query_provider=query,
            coord_transform=transform,
        )
        state.update()
        assert query.queried[0] == pytest.approx((10.0, 10.0, 20.0))

    def test_off_navmesh_when_poly_ref_zero(self) -> None:
        query = MockNavmeshQuery(scripted_polys=[(0, (0.0, 0.0, 0.0))])
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0)]),
            query_provider=query,
            coord_transform=IDENTITY_TRANSFORM,
        )
        status = state.update()
        assert status.on_navmesh is False
        assert status.poly_ref == 0

    def test_query_exception_marked_off_navmesh(self) -> None:
        query = MockNavmeshQuery(fail_nearest_poly=True)
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0)]),
            query_provider=query,
            coord_transform=IDENTITY_TRANSFORM,
        )
        status = state.update()
        assert status.on_navmesh is False
        assert status.poly_ref == 0
        # state remains usable and countable
        assert state.update_count == 1

    def test_malformed_poly_response_marked_off_navmesh(self) -> None:
        # poly_ref must be int >= 0; if a backend ever returns a sentinel,
        # the safe-wrapper should treat it as off-navmesh.
        class _BadQuery:
            def find_nearest_poly(self, x, y, z, *, search_extents=(50, 50, 50)):
                return (-1, (x, y, z))

            def find_path(self, start, goal, *, smooth=True, search_extents=(50, 50, 50)):
                return {"success": False}

        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0)]),
            query_provider=_BadQuery(),
            coord_transform=IDENTITY_TRANSFORM,
        )
        status = state.update()
        assert status.on_navmesh is False

    def test_malformed_snapped_response_marked_off_navmesh(self) -> None:
        # poly_ref valid but snapped has wrong shape — treat as off-navmesh so
        # on_navmesh and snapped_obj_pos stay consistent (caller never sees
        # "on_navmesh=True paired with un-snapped position").

        class _MalformedSnapped:
            def find_nearest_poly(self, x, y, z, *, search_extents=(50, 50, 50)):
                return (1, [x, y])  # only 2 floats

            def find_path(self, start, goal, *, smooth=True, search_extents=(50, 50, 50)):
                return {"success": False}

        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0)]),
            query_provider=_MalformedSnapped(),
            coord_transform=IDENTITY_TRANSFORM,
        )
        status = state.update()
        assert status.on_navmesh is False
        assert status.poly_ref == 0
        # last_obj_pos should NOT have been updated to the bogus snapped result
        assert state.last_obj_pos is None

    def test_malformed_snapped_with_non_numeric_components_marked_off_navmesh(self) -> None:
        # poly_ref valid but snapped has 3 elements that aren't all numeric
        class _NonNumericSnapped:
            def find_nearest_poly(self, x, y, z, *, search_extents=(50, 50, 50)):
                return (1, ["a", "b", "c"])

            def find_path(self, start, goal, *, smooth=True, search_extents=(50, 50, 50)):
                return {"success": False}

        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0)]),
            query_provider=_NonNumericSnapped(),
            coord_transform=IDENTITY_TRANSFORM,
        )
        status = state.update()
        assert status.on_navmesh is False


# ── NavmeshState — teleport detection ────────────────────────────────────


class TestNavmeshStateTeleport:
    def test_first_update_never_teleport(self) -> None:
        state = NavmeshState(
            position_source=MockPositionSource([(100000.0, 0.0, 0.0)]),
            query_provider=MockNavmeshQuery(),
            coord_transform=IDENTITY_TRANSFORM,
        )
        status = state.update()
        assert status.teleport_detected is False  # no prior reading to compare

    def test_small_movement_no_teleport(self) -> None:
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)]),
            query_provider=MockNavmeshQuery(),
            coord_transform=IDENTITY_TRANSFORM,
            teleport_threshold=DEFAULT_TELEPORT_THRESHOLD,
        )
        state.update()
        s2 = state.update()
        assert s2.teleport_detected is False

    def test_large_jump_above_threshold_detected(self) -> None:
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0), (10000.0, 0.0, 0.0)]),
            query_provider=MockNavmeshQuery(),
            coord_transform=IDENTITY_TRANSFORM,
            teleport_threshold=5000.0,
        )
        state.update()
        s2 = state.update()
        assert s2.teleport_detected is True

    def test_just_below_threshold_not_detected(self) -> None:
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0), (4999.0, 0.0, 0.0)]),
            query_provider=MockNavmeshQuery(),
            coord_transform=IDENTITY_TRANSFORM,
            teleport_threshold=5000.0,
        )
        state.update()
        s2 = state.update()
        assert s2.teleport_detected is False

    def test_threshold_zero_disables_detection(self) -> None:
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0), (1000000.0, 0.0, 0.0)]),
            query_provider=MockNavmeshQuery(),
            coord_transform=IDENTITY_TRANSFORM,
            teleport_threshold=0.0,
        )
        state.update()
        s2 = state.update()
        assert s2.teleport_detected is False


# ── NavmeshState — zone tracking ──────────────────────────────────────────


class TestNavmeshStateZone:
    def test_zone_change_on_poly_ref_change(self) -> None:
        polys = [(1, (0.0, 0.0, 0.0)), (2, (0.0, 0.0, 0.0))]
        query = MockNavmeshQuery(scripted_polys=polys)
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)]),
            query_provider=query,
            coord_transform=IDENTITY_TRANSFORM,
        )
        state.update()
        state.mark_zone("ep1_dungeons")
        s2 = state.update()
        assert s2.zone_changed is True

    def test_no_zone_change_when_caller_did_not_set_zone(self) -> None:
        polys = [(1, (0.0, 0.0, 0.0)), (2, (0.0, 0.0, 0.0))]
        query = MockNavmeshQuery(scripted_polys=polys)
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)]),
            query_provider=query,
            coord_transform=IDENTITY_TRANSFORM,
        )
        state.update()  # no mark_zone
        s2 = state.update()
        assert s2.zone_changed is False

    def test_zone_unchanged_when_poly_ref_stable(self) -> None:
        query = MockNavmeshQuery(scripted_polys=[(1, (0.0, 0.0, 0.0)), (1, (0.0, 0.0, 0.0))])
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)]),
            query_provider=query,
            coord_transform=IDENTITY_TRANSFORM,
        )
        state.update()
        state.mark_zone("ep1_dungeons")
        s2 = state.update()
        assert s2.zone_changed is False

    def test_recompute_zone_clears_state(self) -> None:
        query = MockNavmeshQuery(scripted_polys=[(1, (0.0, 0.0, 0.0))])
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0)]),
            query_provider=query,
            coord_transform=IDENTITY_TRANSFORM,
        )
        state.update()
        state.mark_zone("ep1_dungeons")
        assert state.current_zone == "ep1_dungeons"
        state.recompute_zone_from_zone_change()
        assert state.current_zone is None


# ── NavmeshState.find_path ───────────────────────────────────────────────


class TestNavmeshStateFindPath:
    def test_calls_provider_with_last_obj_pos(self) -> None:
        query = MockNavmeshQuery(scripted_polys=[(1, (0.0, 0.0, 0.0))])
        state = NavmeshState(
            position_source=MockPositionSource([(5.0, 5.0, 5.0)]),
            query_provider=query,
            coord_transform=IDENTITY_TRANSFORM,
        )
        state.update()
        result = state.find_path((20.0, 20.0, 20.0))
        assert result["success"] is True
        assert query.path_calls == [((5.0, 5.0, 5.0), (20.0, 20.0, 20.0))]

    def test_fail_closed_before_update(self) -> None:
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0)]),
            query_provider=MockNavmeshQuery(),
            coord_transform=IDENTITY_TRANSFORM,
        )
        result = state.find_path((10.0, 10.0, 10.0))
        assert result["success"] is False
        assert "update()" in result["error"]

    def test_fail_closed_when_off_navmesh(self) -> None:
        query = MockNavmeshQuery(scripted_polys=[(0, (0.0, 0.0, 0.0))])
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0)]),
            query_provider=query,
            coord_transform=IDENTITY_TRANSFORM,
        )
        state.update()  # poly_ref = 0 (off navmesh)
        result = state.find_path((10.0, 10.0, 10.0))
        assert result["success"] is False
        assert "off-navmesh" in result["error"]

    def test_find_path_memory_converts_goal_to_obj(self) -> None:
        query = MockNavmeshQuery(scripted_polys=[(1, (0.0, 0.0, 0.0))])
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0)]),
            query_provider=query,
            coord_transform=SCALE_10_TRANSFORM,
        )
        state.update()
        state.find_path_memory((100.0, 105.0, 200.0))  # → obj (10, 10, 20)
        # start obj is the identity-transformed start position (memory pos == obj
        # pos in OBJ space because the transform is applied to memory coords)
        assert len(query.path_calls) == 1
        assert query.path_calls[0][1] == pytest.approx((10.0, 10.0, 20.0))

    def test_smooth_kwarg_passed_through(self) -> None:
        captured: dict[str, bool] = {}

        class _SmoothProbe:
            def find_nearest_poly(self, x, y, z, *, search_extents=(50, 50, 50)):
                return (1, (x, y, z))

            def find_path(self, start, goal, *, smooth=True, search_extents=(50, 50, 50)):
                captured["smooth"] = smooth
                return {"success": True, "waypoints": []}

        query = _SmoothProbe()
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0)]),
            query_provider=query,
            coord_transform=IDENTITY_TRANSFORM,
        )
        state.update()
        state.find_path((10.0, 10.0, 10.0), smooth=False)
        assert captured["smooth"] is False
        state.find_path((20.0, 20.0, 20.0), smooth=True)
        assert captured["smooth"] is True


# ── NavmeshState — counter + history ─────────────────────────────────────


class TestNavmeshStateCounters:
    def test_update_count_increments(self) -> None:
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (2.0, 2.0, 2.0)]),
            query_provider=MockNavmeshQuery(),
            coord_transform=IDENTITY_TRANSFORM,
        )
        for _ in range(3):
            state.update()
        assert state.update_count == 3

    def test_history_ring_buffer_caps_at_history_len(self) -> None:
        positions = [(float(i), 0.0, 0.0) for i in range(50)]
        state = NavmeshState(
            position_source=MockPositionSource(positions),
            query_provider=MockNavmeshQuery(),
            coord_transform=IDENTITY_TRANSFORM,
            history_len=8,
        )
        for _ in range(50):
            state.update()
        assert len(state._history) == 8
        # The most recent entry should be position (49, 0, 0).
        assert state._history[-1][1] == (49.0, 0.0, 0.0)


# ── Protocol isinstance checks ───────────────────────────────────────────


class TestProtocolConformance:
    def test_navmesh_query_provider_runtime_checkable(self) -> None:
        q = MockNavmeshQuery()
        assert isinstance(q, NavmeshQueryProvider)

    def test_position_source_runtime_checkable(self) -> None:
        src = StaticPositionSource([(0.0, 0.0, 0.0)])
        assert isinstance(src, PositionSource)


# ── Defaults ──────────────────────────────────────────────────────────────


class TestDefaults:
    def test_default_teleport_threshold_is_5000(self) -> None:
        assert DEFAULT_TELEPORT_THRESHOLD == 5000.0

    def test_default_history_len_is_32(self) -> None:
        state = NavmeshState(
            position_source=MockPositionSource([(0.0, 0.0, 0.0)]),
            query_provider=MockNavmeshQuery(),
            coord_transform=IDENTITY_TRANSFORM,
        )
        assert state.history_len == 32
