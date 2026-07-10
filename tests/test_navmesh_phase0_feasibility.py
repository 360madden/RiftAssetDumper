"""Tests for scripts/navmesh_phase0_feasibility.py."""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import pytest

from scripts.navmesh_phase0_feasibility import (
    Grid2D,
    analyze_obj,
    normalize,
    parse_obj,
    point_in_triangle_xz,
    slope_angle,
    triangle_area,
    triangle_normal,
    triangle_xz_bounds,
    write_debug_obj,
)

# ---------------------------------------------------------------------------
# OBJ parser
# ---------------------------------------------------------------------------


class TestParseObj:
    def test_parse_simple_triangle(self) -> None:
        obj = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".obj", delete=False) as f:
            f.write(obj)
            f.flush()
            path = Path(f.name)
        try:
            vertices, faces = parse_obj(path)
            assert len(vertices) == 3
            assert vertices[0] == (0.0, 0.0, 0.0)
            assert faces == [[0, 1, 2]]
        finally:
            path.unlink()

    def test_parse_with_normals_and_uvs(self) -> None:
        obj = "v 1 2 3\nv 4 5 6\nv 7 8 9\nf 1/1/1 2/2/2 3/3/3\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".obj", delete=False) as f:
            f.write(obj)
            f.flush()
            path = Path(f.name)
        try:
            vertices, faces = parse_obj(path)
            assert len(vertices) == 3
            assert faces == [[0, 1, 2]]
        finally:
            path.unlink()

    def test_parse_negative_indices(self) -> None:
        # -1 refers to the last vertex
        obj = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf -3 -2 -1\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".obj", delete=False) as f:
            f.write(obj)
            f.flush()
            path = Path(f.name)
        try:
            vertices, faces = parse_obj(path)
            assert faces == [[0, 1, 2]]
        finally:
            path.unlink()

    def test_skips_quads(self) -> None:
        obj = "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\nf 1 2 3\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".obj", delete=False) as f:
            f.write(obj)
            f.flush()
            path = Path(f.name)
        try:
            vertices, faces = parse_obj(path)
            assert len(faces) == 1  # quad skipped, triangle kept
            assert faces[0] == [0, 1, 2]
        finally:
            path.unlink()

    def test_skips_comments_and_blanks(self) -> None:
        obj = "# comment\nv 0 0 0\n\nv 1 0 0\n# another\nv 0 1 0\nf 1 2 3\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".obj", delete=False) as f:
            f.write(obj)
            f.flush()
            path = Path(f.name)
        try:
            vertices, faces = parse_obj(path)
            assert len(vertices) == 3
            assert len(faces) == 1
        finally:
            path.unlink()


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


class TestTriangleNormal:
    def test_horizontal_triangle(self) -> None:
        # Winding order (0,0,0)→(0,0,1)→(1,0,0) produces upward normal (0,1,0)
        n = triangle_normal((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
        # Should point up (positive Y)
        n = normalize(n)
        assert abs(n[0]) < 1e-10
        assert abs(n[1] - 1.0) < 1e-10
        assert abs(n[2]) < 1e-10

    def test_vertical_triangle(self) -> None:
        n = triangle_normal((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 1.0, 1.0))
        # Should point along X axis
        n = normalize(n)
        assert abs(abs(n[0]) - 1.0) < 1e-10
        assert abs(n[1]) < 1e-10
        assert abs(n[2]) < 1e-10


class TestNormalize:
    def test_unit_vector(self) -> None:
        v = normalize((1.0, 0.0, 0.0))
        assert v == (1.0, 0.0, 0.0)

    def test_zero_vector(self) -> None:
        v = normalize((0.0, 0.0, 0.0))
        assert v == (0.0, 0.0, 0.0)

    def test_arbitrary(self) -> None:
        v = normalize((3.0, 4.0, 0.0))
        assert abs(v[0] - 0.6) < 1e-10
        assert abs(v[1] - 0.8) < 1e-10


class TestSlopeAngle:
    def test_horizontal(self) -> None:
        # Normal pointing straight up
        assert slope_angle((0.0, 1.0, 0.0)) == pytest.approx(0.0)

    def test_vertical(self) -> None:
        # Normal pointing sideways
        assert slope_angle((1.0, 0.0, 0.0)) == pytest.approx(90.0)

    def test_45_degree(self) -> None:
        n = normalize((0.0, 1.0, 1.0))
        assert slope_angle(n) == pytest.approx(45.0)

    def test_upside_down_is_still_horizontal(self) -> None:
        # Face normal pointing down — slope angle is still angle from Y-axis
        assert slope_angle((0.0, -1.0, 0.0)) == pytest.approx(0.0)


class TestTriangleArea:
    def test_right_triangle(self) -> None:
        area = triangle_area((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        assert area == pytest.approx(0.5)

    def test_unit_square_half(self) -> None:
        area = triangle_area((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0))
        assert area == pytest.approx(2.0)


class TestTriangleXzBounds:
    def test_basic(self) -> None:
        b = triangle_xz_bounds((0.0, 5.0, 1.0), (3.0, 7.0, 4.0), (1.0, 6.0, 2.0))
        assert b == (0.0, 1.0, 3.0, 4.0)


class TestPointInTriangleXz:
    def test_center_point(self) -> None:
        inside = point_in_triangle_xz(
            0.33,
            0.33,
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
        )
        assert inside is True

    def test_outside_point(self) -> None:
        inside = point_in_triangle_xz(
            2.0,
            2.0,
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
        )
        assert inside is False

    def test_vertex_point(self) -> None:
        inside = point_in_triangle_xz(
            0.0,
            0.0,
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
        )
        assert inside is True


# ---------------------------------------------------------------------------
# Grid2D
# ---------------------------------------------------------------------------


class TestGrid2D:
    def test_basic_creation(self) -> None:
        grid = Grid2D(0.0, 0.0, 10.0, 10.0, 1.0)
        assert grid.cols == 10
        assert grid.rows == 10
        assert len(grid.cells) == 100
        assert grid.walkable_count() == 0

    def test_mark_and_check(self) -> None:
        grid = Grid2D(0.0, 0.0, 10.0, 10.0, 1.0)
        grid.mark_walkable(5, 5)
        assert grid.is_walkable(5, 5) is True
        assert grid.is_walkable(0, 0) is False
        assert grid.walkable_count() == 1

    def test_out_of_bounds(self) -> None:
        grid = Grid2D(0.0, 0.0, 10.0, 10.0, 1.0)
        grid.mark_walkable(-1, 5)  # Should be no-op
        grid.mark_walkable(10, 5)  # Should be no-op
        assert grid.walkable_count() == 0

    def test_world_to_cell(self) -> None:
        grid = Grid2D(0.0, 0.0, 10.0, 10.0, 1.0)
        assert grid.world_to_cell(0.3, 0.7) == (0, 0)
        assert grid.world_to_cell(5.5, 5.5) == (5, 5)
        assert grid.world_to_cell(9.9, 9.9) == (9, 9)

    def test_cell_to_world(self) -> None:
        grid = Grid2D(0.0, 0.0, 10.0, 10.0, 1.0)
        x, z = grid.cell_to_world(3, 7)
        assert x == 3.5
        assert z == 7.5

    def test_rasterize_triangle(self) -> None:
        grid = Grid2D(0.0, 0.0, 10.0, 10.0, 1.0)
        count = grid.rasterize_triangle(
            (0.0, 0.0, 0.0),
            (5.0, 0.0, 0.0),
            (0.0, 0.0, 5.0),
        )
        assert count > 0
        # Center of the triangle should be walkable
        assert grid.is_walkable(1, 1) is True

    def test_find_connected_components_single(self) -> None:
        grid = Grid2D(0.0, 0.0, 10.0, 10.0, 1.0)
        # Mark a 3x3 block
        for c in range(2, 5):
            for r in range(2, 5):
                grid.mark_walkable(c, r)
        components = grid.find_connected_components()
        assert len(components) == 1
        assert components[0] == 9

    def test_find_connected_components_two_islands(self) -> None:
        grid = Grid2D(0.0, 0.0, 10.0, 10.0, 1.0)
        # Island 1: 2x2 at (1,1)
        for c, r in [(1, 1), (1, 2), (2, 1), (2, 2)]:
            grid.mark_walkable(c, r)
        # Island 2: 1 cell at (8,8)
        grid.mark_walkable(8, 8)
        components = grid.find_connected_components()
        assert len(components) == 2
        assert components[0] == 4  # Largest first
        assert components[1] == 1

    def test_empty_grid(self) -> None:
        grid = Grid2D(0.0, 0.0, 10.0, 10.0, 1.0)
        components = grid.find_connected_components()
        assert components == []

    def test_single_cell_bounds(self) -> None:
        grid = Grid2D(0.0, 0.0, 0.1, 0.1, 1.0)
        assert grid.cols == 1
        assert grid.rows == 1


# ---------------------------------------------------------------------------
# Debug OBJ export
# ---------------------------------------------------------------------------


class TestWriteDebugObj:
    def test_writes_valid_obj(self) -> None:
        walkable = [((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))]
        non_walkable = [((0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (0.0, 1.0, 1.0))]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".obj", delete=False) as f:
            path = Path(f.name)
        try:
            write_debug_obj(path, walkable, non_walkable)
            content = path.read_text()
            assert "usemtl walkable" in content
            assert "usemtl non_walkable" in content
            # Should have 6 vertices and 2 faces
            assert content.count("v ") == 6
            assert content.count("f ") == 2
        finally:
            path.unlink()


# ---------------------------------------------------------------------------
# Analyze OBJ (integration)
# ---------------------------------------------------------------------------


class TestAnalyzeObj:
    def test_horizontal_plane(self) -> None:
        """A flat horizontal plane should be 100% walkable."""
        obj = "v 0 0 0\nv 10 0 0\nv 10 0 10\nv 0 0 10\nf 1 2 3\nf 1 3 4\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".obj", delete=False) as f:
            f.write(obj)
            f.flush()
            path = Path(f.name)
        try:
            result = analyze_obj(path, cell_size=1.0, max_slope=45.0)
            assert result["geometry"]["walkable_face_count"] == 2
            assert result["connectivity"]["component_count"] == 1
            assert result["feasibility"]["verdict"] == "PROMISING"
        finally:
            path.unlink()

    def test_vertical_wall(self) -> None:
        """A vertical wall should have zero walkable faces."""
        obj = "v 0 0 0\nv 0 10 0\nv 0 10 1\nv 0 0 1\nf 1 2 3\nf 1 3 4\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".obj", delete=False) as f:
            f.write(obj)
            f.flush()
            path = Path(f.name)
        try:
            result = analyze_obj(path, cell_size=1.0, max_slope=45.0)
            assert result["geometry"]["walkable_face_count"] == 0
            assert result["feasibility"]["verdict"] == "BLOCKED"
        finally:
            path.unlink()

    def test_mixed_geometry(self) -> None:
        """A mix of horizontal and vertical faces."""
        obj = (
            # Floor
            "v 0 0 0\nv 5 0 0\nv 5 0 5\nv 0 0 5\n"
            # Wall
            "v 0 0 0\nv 0 5 0\nv 0 5 1\nv 0 0 1\n"
            "f 1 2 3\nf 1 3 4\n"  # floor
            "f 5 6 7\nf 5 7 8\n"  # wall
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".obj", delete=False) as f:
            f.write(obj)
            f.flush()
            path = Path(f.name)
        try:
            result = analyze_obj(path, cell_size=1.0, max_slope=45.0)
            assert result["geometry"]["walkable_face_count"] == 2
            assert result["geometry"]["non_walkable_face_count"] == 2
        finally:
            path.unlink()

    def test_empty_obj(self) -> None:
        obj = "# Just a comment\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".obj", delete=False) as f:
            f.write(obj)
            f.flush()
            path = Path(f.name)
        try:
            result = analyze_obj(path)
            assert "error" in result
        finally:
            path.unlink()

    def test_output_is_valid_json(self) -> None:
        obj = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".obj", delete=False) as f:
            f.write(obj)
            f.flush()
            path = Path(f.name)
        try:
            result = analyze_obj(path)
            # Verify all expected keys exist
            assert "bounds" in result
            assert "geometry" in result
            assert "grid" in result
            assert "connectivity" in result
            assert "feasibility" in result
            assert "parameters" in result
            # Verify feasibility has required fields
            f = result["feasibility"]
            assert "verdict" in f
            assert "signals" in f
            assert "concerns" in f
            assert "recommendation" in f
        finally:
            path.unlink()

    def test_custom_max_slope(self) -> None:
        """A 30-degree slope should be walkable at max_slope=45 but not at max_slope=15."""
        # Triangle with 30-degree slope: vertices at y=0 and y=sin(30°)
        h = math.sin(math.radians(30))
        obj = f"v 0 0 0\nv 1 {h} 0\nv 0 0 1\nf 1 2 3\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".obj", delete=False) as f:
            f.write(obj)
            f.flush()
            path = Path(f.name)
        try:
            result_45 = analyze_obj(path, max_slope=45.0)
            result_15 = analyze_obj(path, max_slope=15.0)
            assert result_45["geometry"]["walkable_face_count"] == 1
            assert result_15["geometry"]["walkable_face_count"] == 0
        finally:
            path.unlink()
