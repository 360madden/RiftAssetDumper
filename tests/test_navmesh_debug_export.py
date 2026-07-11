"""Tests for scripts/navmesh_debug_export.py.

These tests exercise the pure-Python OBJ export helpers without requiring
a JVM or recast4j. They verify that navmesh polygons, boundary edges, and
path waypoints are emitted as valid Wavefront OBJ with the expected
material tags.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.navmesh_debug_export import (
    MAT_NAVMESH_EDGE,
    MAT_NAVMESH_WALKABLE,
    MAT_PATH_GOAL,
    MAT_PATH_ROUTE,
    MAT_PATH_START,
    _compute_marker_size,
    export_navmesh_and_path,
    export_navmesh_to_obj,
    export_path_to_obj,
    write_mtl_file,
)


@pytest.fixture
def tmp_obj(tmp_path: Path) -> Path:
    """Return a temporary OBJ path for a test."""
    return tmp_path / "debug.obj"


def _read_lines(path: Path) -> list[str]:
    """Read an OBJ file and return its non-empty lines."""
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_export_navmesh_to_obj_writes_vertices_and_faces(tmp_obj: Path) -> None:
    """Navmesh export should emit vertices and fan-triangulated faces."""
    vertices = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 10.0), (0.0, 0.0, 10.0)]
    polys = [[0, 1, 2, 3]]

    export_navmesh_to_obj(vertices, polys, tmp_obj, include_edges=False)

    lines = _read_lines(tmp_obj)
    assert any(line.startswith("v ") for line in lines)
    assert any(line.startswith("f ") for line in lines)
    assert any(MAT_NAVMESH_WALKABLE in line for line in lines)
    assert not any(MAT_NAVMESH_EDGE in line for line in lines)


def test_export_navmesh_to_obj_includes_edges_when_requested(tmp_obj: Path) -> None:
    """Navmesh export should emit boundary edges when include_edges=True."""
    vertices = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 10.0)]
    polys = [[0, 1, 2]]

    export_navmesh_to_obj(vertices, polys, tmp_obj, include_edges=True)

    lines = _read_lines(tmp_obj)
    assert any(line.startswith("l ") for line in lines)
    assert any(MAT_NAVMESH_EDGE in line for line in lines)


def test_export_navmesh_to_obj_triangulates_quad(tmp_obj: Path) -> None:
    """A quad polygon should be fan-triangulated into two triangles."""
    vertices = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 10.0), (0.0, 0.0, 10.0)]
    polys = [[0, 1, 2, 3]]

    export_navmesh_to_obj(vertices, polys, tmp_obj, include_edges=False)

    lines = _read_lines(tmp_obj)
    face_lines = [line for line in lines if line.startswith("f ")]
    assert len(face_lines) == 2


def test_export_navmesh_to_obj_skips_degenerate_polygons(tmp_obj: Path) -> None:
    """Polygons with fewer than 3 vertices should be skipped."""
    vertices = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
    polys = [[0, 1]]

    export_navmesh_to_obj(vertices, polys, tmp_obj, include_edges=False)

    lines = _read_lines(tmp_obj)
    assert any(line.startswith("v ") for line in lines)
    assert not any(line.startswith("f ") for line in lines)


def test_export_path_to_obj_writes_waypoints_and_markers(tmp_obj: Path) -> None:
    """Path export should emit waypoints as vertices and line segments."""
    waypoints = [(0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (10.0, 0.0, 0.0)]

    export_path_to_obj(waypoints, tmp_obj, marker_size=1.0)

    lines = _read_lines(tmp_obj)
    assert any(line.startswith("v ") for line in lines)
    assert any(line.startswith("l ") for line in lines)
    assert any(MAT_PATH_ROUTE in line for line in lines)
    assert any(MAT_PATH_START in line for line in lines)
    assert any(MAT_PATH_GOAL in line for line in lines)


def test_export_path_to_obj_line_count_matches_waypoints(tmp_obj: Path) -> None:
    """A path with N waypoints should produce N-1 line segments."""
    waypoints = [(0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (10.0, 0.0, 0.0), (15.0, 0.0, 0.0)]

    export_path_to_obj(waypoints, tmp_obj, marker_size=1.0)

    lines = _read_lines(tmp_obj)
    line_segments = [line for line in lines if line.startswith("l ")]
    assert len(line_segments) == len(waypoints) - 1


def test_export_path_to_obj_empty_waypoints(tmp_obj: Path) -> None:
    """An empty waypoint list should produce no route or marker objects."""
    export_path_to_obj([], tmp_obj, marker_size=1.0)

    lines = _read_lines(tmp_obj)
    assert not any(MAT_PATH_ROUTE in line for line in lines)
    assert not any(MAT_PATH_START in line for line in lines)
    assert not any(MAT_PATH_GOAL in line for line in lines)


def test_export_navmesh_and_path_combines_both(tmp_obj: Path) -> None:
    """Combined export should contain navmesh faces and path lines."""
    navmesh_result = {
        "verts": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 10.0), (0.0, 0.0, 10.0)],
        "polys": [[0, 1, 2, 3]],
    }
    waypoints = [(2.0, 0.0, 2.0), (8.0, 0.0, 8.0)]

    export_navmesh_and_path(navmesh_result, waypoints, tmp_obj, include_edges=False, marker_size=1.0)

    lines = _read_lines(tmp_obj)
    assert any(line.startswith("f ") for line in lines)
    assert any(line.startswith("l ") for line in lines)
    assert any(MAT_NAVMESH_WALKABLE in line for line in lines)
    assert any(MAT_PATH_ROUTE in line for line in lines)
    assert any(MAT_PATH_START in line for line in lines)
    assert any(MAT_PATH_GOAL in line for line in lines)


def test_export_navmesh_and_path_without_waypoints(tmp_obj: Path) -> None:
    """Combined export should still work when no path waypoints are provided."""
    navmesh_result = {
        "verts": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 10.0)],
        "polys": [[0, 1, 2]],
    }

    export_navmesh_and_path(navmesh_result, None, tmp_obj, include_edges=False, marker_size=1.0)

    lines = _read_lines(tmp_obj)
    assert any(line.startswith("f ") for line in lines)
    assert not any(MAT_PATH_ROUTE in line for line in lines)


def test_export_path_to_obj_marker_geometry_counts(tmp_obj: Path) -> None:
    """Path markers should be symmetric octahedra with 6 verts and 8 faces each."""
    waypoints = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]

    export_path_to_obj(waypoints, tmp_obj, marker_size=1.0)

    lines = _read_lines(tmp_obj)
    vertex_lines = [line for line in lines if line.startswith("v ")]
    face_lines = [line for line in lines if line.startswith("f ")]

    # 2 waypoints + 2 markers * 6 vertices each = 14 vertices
    assert len(vertex_lines) == 14
    # 2 markers * 8 faces each = 16 marker faces
    assert len(face_lines) == 16


def test_export_path_to_obj_marker_centroid(tmp_obj: Path) -> None:
    """The octahedron marker centroid should equal the input waypoint."""
    waypoints = [(5.0, 2.0, -3.0)]

    export_path_to_obj(waypoints, tmp_obj, marker_size=1.0)

    lines = _read_lines(tmp_obj)
    # First 6 vertices after the waypoint are the start marker
    marker_verts = []
    for line in lines:
        if line.startswith("v "):
            marker_verts.append([float(x) for x in line.split()[1:]])
    marker_verts = marker_verts[1:7]
    centroid = [sum(v[i] for v in marker_verts) / len(marker_verts) for i in range(3)]
    assert centroid == pytest.approx(list(waypoints[0]), abs=1e-6)


def test_export_path_to_obj_auto_marker_size(tmp_obj: Path) -> None:
    """Auto marker size should scale with the waypoint bounding box."""
    waypoints = [(0.0, 0.0, 0.0), (100.0, 0.0, 0.0)]
    export_path_to_obj(waypoints, tmp_obj, marker_size=None)
    # Marker size should be 2% of 100 = 2.0, clamped to [0.1, 50.0]
    assert _compute_marker_size([], waypoints) == 2.0


def test_export_navmesh_to_obj_writes_mtl(tmp_obj: Path) -> None:
    """Navmesh export should generate a companion MTL file."""
    vertices = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 10.0)]
    polys = [[0, 1, 2]]

    export_navmesh_to_obj(vertices, polys, tmp_obj, include_edges=False, name="zone_a")

    mtl_path = tmp_obj.with_suffix(".mtl")
    assert mtl_path.exists()
    mtl_text = mtl_path.read_text(encoding="utf-8")
    assert f"newmtl {MAT_NAVMESH_WALKABLE}" in mtl_text
    assert f"newmtl {MAT_NAVMESH_EDGE}" in mtl_text


def test_export_navmesh_to_obj_uses_custom_name(tmp_obj: Path) -> None:
    """Navmesh export should use the provided object name."""
    vertices = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 10.0)]
    polys = [[0, 1, 2]]

    export_navmesh_to_obj(vertices, polys, tmp_obj, include_edges=False, name="zone_a")

    lines = _read_lines(tmp_obj)
    assert "o zone_a" in lines


def test_export_navmesh_and_path_index_continuity(tmp_obj: Path) -> None:
    """Combined export should use continuous 1-indexed vertex ranges."""
    navmesh_result = {
        "verts": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 10.0), (0.0, 0.0, 10.0)],
        "polys": [[0, 1, 2, 3]],
    }
    waypoints = [(2.0, 0.0, 2.0), (8.0, 0.0, 8.0)]

    export_navmesh_and_path(navmesh_result, waypoints, tmp_obj, include_edges=False, name="zone_b")

    lines = _read_lines(tmp_obj)
    # Find the navmesh object and the route object to slice navmesh-only faces
    navmesh_obj_idx = next(i for i, line in enumerate(lines) if line == "o zone_b")
    route_obj_idx = next(i for i, line in enumerate(lines) if line == "o zone_b_route")
    navmesh_face_lines = [line for line in lines[navmesh_obj_idx:route_obj_idx] if line.startswith("f ")]
    route_line = next(line for line in lines[route_obj_idx:] if line.startswith("l "))

    # Navmesh face indices should be in 1..4
    for face in navmesh_face_lines:
        indices = [int(x) for x in face.split()[1:]]
        assert all(1 <= i <= 4 for i in indices)

    # Path route line should connect the two waypoints (indices 5 and 6)
    assert route_line == "l 5 6"


def test_write_mtl_file(tmp_path: Path) -> None:
    """write_mtl_file should create a valid MTL with all expected materials."""
    mtl_path = tmp_path / "debug.mtl"
    write_mtl_file(mtl_path)
    text = mtl_path.read_text(encoding="utf-8")
    assert f"newmtl {MAT_NAVMESH_WALKABLE}" in text
    assert f"newmtl {MAT_PATH_ROUTE}" in text
    assert f"newmtl {MAT_PATH_START}" in text
    assert f"newmtl {MAT_PATH_GOAL}" in text
