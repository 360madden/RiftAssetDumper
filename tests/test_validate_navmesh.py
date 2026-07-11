"""Tests for scripts/validate_navmesh.py."""

from __future__ import annotations

import pytest

from scripts.validate_navmesh import (
    _build_adjacency,
    _connected_components,
    _edge_length,
    _find_isolated_polys,
    _poly_area,
    validate_navmesh,
)


class TestEdgeLength:
    """Test 3D edge length computation."""

    def test_unit_edge(self) -> None:
        assert _edge_length([0, 0, 0], [1, 0, 0]) == pytest.approx(1.0)

    def test_diagonal_edge(self) -> None:
        assert _edge_length([0, 0, 0], [3, 4, 0]) == pytest.approx(5.0)

    def test_3d_diagonal(self) -> None:
        assert _edge_length([0, 0, 0], [1, 2, 2]) == pytest.approx(3.0)

    def test_zero_length(self) -> None:
        assert _edge_length([1, 2, 3], [1, 2, 3]) == pytest.approx(0.0)


class TestPolyArea:
    """Test polygon area computation (fan-triangulated)."""

    def test_unit_triangle(self) -> None:
        verts = [[0, 0, 0], [1, 0, 0], [0, 0, 1]]
        assert _poly_area(verts, [0, 1, 2]) == pytest.approx(0.5)

    def test_unit_square(self) -> None:
        verts = [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]]
        area = _poly_area(verts, [0, 1, 2, 3])
        assert area == pytest.approx(1.0)  # Two triangles of 0.5 each

    def test_degenerate_poly(self) -> None:
        """Collinear vertices → zero area."""
        verts = [[0, 0, 0], [1, 0, 0], [2, 0, 0]]
        assert _poly_area(verts, [0, 1, 2]) == pytest.approx(0.0)

    def test_less_than_3_verts(self) -> None:
        verts = [[0, 0, 0], [1, 0, 0]]
        assert _poly_area(verts, [0, 1]) == 0.0


class TestBuildAdjacency:
    """Test poly-to-poly adjacency from shared vertices."""

    def test_two_polys_sharing_edge(self) -> None:
        """Two triangles sharing an edge (2 shared vertices)."""
        polys = [[0, 1, 2], [1, 3, 2]]  # Share vertices 1 and 2
        adj = _build_adjacency(polys)
        assert 1 in adj[0]
        assert 0 in adj[1]

    def test_two_polys_sharing_vertex_only(self) -> None:
        """Two triangles sharing only 1 vertex → NOT adjacent (need 2+ for edge)."""
        polys = [[0, 1, 2], [2, 3, 4]]  # Share only vertex 2
        adj = _build_adjacency(polys)
        assert 1 not in adj[0]
        assert 0 not in adj[1]

    def test_no_shared_polys(self) -> None:
        polys = [[0, 1, 2], [3, 4, 5]]
        adj = _build_adjacency(polys)
        assert adj[0] == set()
        assert adj[1] == set()

    def test_three_polys_chain(self) -> None:
        """A→B→C chain where each shares an edge with the next."""
        polys = [[0, 1, 2], [1, 3, 2], [3, 4, 2]]
        adj = _build_adjacency(polys)
        assert 1 in adj[0]  # A-B
        assert 0 in adj[1]
        assert 2 in adj[1]  # B-C
        assert 1 in adj[2]


class TestFindIsolatedPolys:
    """Test finding polys with no neighbors."""

    def test_no_isolated(self) -> None:
        adjacency = {0: {1}, 1: {0, 2}, 2: {1}}
        isolated = _find_isolated_polys(adjacency, 3)
        assert isolated == []

    def test_one_isolated(self) -> None:
        adjacency = {0: {1}, 1: {0}, 2: set()}
        isolated = _find_isolated_polys(adjacency, 3)
        assert isolated == [2]

    def test_all_isolated(self) -> None:
        adjacency = {0: set(), 1: set(), 2: set()}
        isolated = _find_isolated_polys(adjacency, 3)
        assert sorted(isolated) == [0, 1, 2]


class TestConnectedComponents:
    """Test connected component detection via flood-fill."""

    def test_single_component(self) -> None:
        adjacency = {0: {1}, 1: {0, 2}, 2: {1}}
        components = _connected_components(adjacency, 3)
        assert components == [3]

    def test_two_components(self) -> None:
        adjacency = {0: {1}, 1: {0}, 2: set()}
        components = _connected_components(adjacency, 3)
        assert sorted(components) == [1, 2]

    def test_all_isolated(self) -> None:
        adjacency = {0: set(), 1: set(), 2: set()}
        components = _connected_components(adjacency, 3)
        assert sorted(components) == [1, 1, 1]


class TestValidateNavmesh:
    """Test the full validation function."""

    def test_valid_navmesh(self) -> None:
        """A simple valid navmesh with 2 connected polys."""
        navmesh = {
            "success": True,
            "mesh": {"npolys": 2, "nverts": 4, "nvp": 3, "walkable_polys": 2},
            "polys": [[0, 1, 2], [1, 3, 2]],
            "verts": [[0, 0, 0], [1, 0, 0], [0, 0, 1], [1, 0, 1]],
        }
        result = validate_navmesh(navmesh)
        assert result["valid"] is True
        assert all(c["pass"] for c in result["checks"])

    def test_zero_polys_fails(self) -> None:
        """Navmesh with 0 polys should fail."""
        navmesh = {
            "success": True,
            "mesh": {"npolys": 0, "nverts": 0, "nvp": 3, "walkable_polys": 0},
            "polys": [],
            "verts": [],
        }
        result = validate_navmesh(navmesh)
        assert result["valid"] is False

    def test_degenerate_poly_fails(self) -> None:
        """Navmesh with a degenerate (zero-area) poly should fail."""
        navmesh = {
            "success": True,
            "mesh": {"npolys": 2, "nverts": 5, "nvp": 3, "walkable_polys": 2},
            "polys": [[0, 1, 2], [0, 3, 4]],  # [0,3,4] is collinear → 0 area
            "verts": [[0, 0, 0], [1, 0, 0], [0, 0, 1], [2, 0, 0], [3, 0, 0]],
        }
        result = validate_navmesh(navmesh, min_poly_area=1e-10)
        # The degenerate check should fail
        degenerate_check = [c for c in result["checks"] if c["check"] == "no_degenerate_polys"]
        assert len(degenerate_check) == 1
        assert degenerate_check[0]["pass"] is False

    def test_isolated_poly_fails(self) -> None:
        """Navmesh with an isolated poly (no neighbors) should be flagged."""
        navmesh = {
            "success": True,
            "mesh": {"npolys": 2, "nverts": 6, "nvp": 3, "walkable_polys": 2},
            "polys": [[0, 1, 2], [3, 4, 5]],  # No shared vertices
            "verts": [[0, 0, 0], [1, 0, 0], [0, 0, 1], [10, 0, 0], [11, 0, 0], [10, 0, 1]],
        }
        result = validate_navmesh(navmesh)
        isolated_check = [c for c in result["checks"] if c["check"] == "no_isolated_polys"]
        assert len(isolated_check) == 1
        assert isolated_check[0]["pass"] is False

    def test_long_edge_fails(self) -> None:
        """Navmesh with an edge exceeding max_edge_length should fail."""
        navmesh = {
            "success": True,
            "mesh": {"npolys": 1, "nverts": 3, "nvp": 3, "walkable_polys": 1},
            "polys": [[0, 1, 2]],
            "verts": [[0, 0, 0], [100, 0, 0], [0, 0, 1]],  # Edge 0-1 is 100 units
        }
        result = validate_navmesh(navmesh, max_edge_length=50.0)
        edge_check = [c for c in result["checks"] if c["check"] == "max_edge_length_ok"]
        assert len(edge_check) == 1
        assert edge_check[0]["pass"] is False

    def test_summary_only_json(self) -> None:
        """Summary-only JSON (no polys/verts arrays) runs basic checks."""
        navmesh = {
            "success": True,
            "mesh": {"npolys": 9, "nverts": 33, "nvp": 6, "walkable_polys": 9},
        }
        result = validate_navmesh(navmesh)
        assert result["valid"] is True
        assert "note" in result
        assert "Summary-only" in result["note"]

    def test_summary_zero_polys(self) -> None:
        """Summary-only JSON with 0 polys fails."""
        navmesh = {
            "success": True,
            "mesh": {"npolys": 0, "nverts": 0, "nvp": 6, "walkable_polys": 0},
        }
        result = validate_navmesh(navmesh)
        assert result["valid"] is False
