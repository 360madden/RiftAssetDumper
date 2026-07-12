"""Tests for scripts/build_navmesh.py."""

from __future__ import annotations

from pathlib import Path

from scripts.build_navmesh import (
    _adaptive_params,
    _auto_agent_params,
    _auto_cell_size,
    _compute_walkable_ratio,
    export_navmesh_obj,
)


class TestAutoCellSize:
    """Test auto-calibration of cell_size from geometry bounds."""

    def test_small_geometry(self) -> None:
        """Small geometry (28 units) → cell ~0.14."""
        verts = [(float(i), 0.0, 0.0) for i in range(10)]
        cell = _auto_cell_size(verts)
        assert 0.1 <= cell <= 2.0

    def test_large_geometry(self) -> None:
        """Large geometry (3000 units) → cell clamped to 2.0."""
        verts = [(float(i) * 300, 0.0, 0.0) for i in range(10)]
        cell = _auto_cell_size(verts)
        assert cell == 2.0  # Clamped

    def test_medium_geometry(self) -> None:
        """Medium geometry (100 units) → cell ~0.5."""
        verts = [(float(i) * 10, 0.0, 0.0) for i in range(10)]
        cell = _auto_cell_size(verts)
        assert 0.4 <= cell <= 0.6

    def test_empty_vertices(self) -> None:
        """Empty vertex list → default 0.5."""
        cell = _auto_cell_size([])
        assert cell == 0.5

    def test_tiny_geometry_clamped(self) -> None:
        """Very tiny geometry → cell clamped to 0.1."""
        verts = [(0.01 * i, 0.0, 0.0) for i in range(5)]
        cell = _auto_cell_size(verts)
        assert cell == 0.1  # Clamped to minimum


class TestAutoAgentParams:
    """Test auto-calibration of agent parameters from geometry scale."""

    def test_small_y_extent(self) -> None:
        """Small Y extent (5 units) → agent_height=1.8 (minimum)."""
        verts = [(0.0, float(i), 0.0) for i in range(5)]
        params = _auto_agent_params(verts)
        assert params["agent_height"] == 1.8
        assert params["agent_radius"] == 0.54  # 1.8 * 0.3 = 0.54

    def test_large_y_extent(self) -> None:
        """Large Y extent (3300 units) → agent_height clamped to 10.0."""
        verts = [(0.0, float(i) * 330, 0.0) for i in range(10)]
        params = _auto_agent_params(verts)
        assert params["agent_height"] == 10.0  # Clamped

    def test_empty_vertices(self) -> None:
        """Empty vertices → default params."""
        params = _auto_agent_params([])
        assert params["agent_height"] == 1.8
        assert params["agent_radius"] == 0.5

    def test_radius_proportional(self) -> None:
        """Agent radius should be ~30% of agent height."""
        verts = [(0.0, float(i) * 100, 0.0) for i in range(10)]
        params = _auto_agent_params(verts)
        ratio = params["agent_radius"] / params["agent_height"]
        assert 0.25 <= ratio <= 0.35

    def test_climb_proportional(self) -> None:
        """Agent max climb should be ~25% of agent height."""
        verts = [(0.0, float(i) * 100, 0.0) for i in range(10)]
        params = _auto_agent_params(verts)
        ratio = params["agent_max_climb"] / params["agent_height"]
        assert 0.20 <= ratio <= 0.30


class TestComputeWalkableRatio:
    """Test walkable face ratio computation."""

    def test_all_walkable_flat_plane(self) -> None:
        """A flat horizontal plane should be 100% walkable."""
        verts = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 10.0), (0.0, 0.0, 10.0)]
        faces = [[0, 1, 2], [0, 2, 3]]
        result = _compute_walkable_ratio(verts, faces)
        assert result["walkable_faces"] == 2
        assert result["total_faces"] == 2
        assert result["walkable_ratio"] == 1.0
        assert result["steep_ratio"] == 0.0

    def test_all_steep_vertical_wall(self) -> None:
        """A vertical wall should have 0% walkable faces."""
        verts = [(0.0, 0.0, 0.0), (0.0, 10.0, 0.0), (0.0, 10.0, 1.0), (0.0, 0.0, 1.0)]
        faces = [[0, 1, 2], [0, 2, 3]]
        result = _compute_walkable_ratio(verts, faces)
        assert result["walkable_faces"] == 0
        assert result["walkable_ratio"] == 0.0
        assert result["steep_ratio"] == 1.0

    def test_mixed_geometry(self) -> None:
        """A mix of horizontal and vertical faces."""
        # 2 horizontal (walkable) + 2 vertical (steep)
        verts = [
            (0.0, 0.0, 0.0),
            (5.0, 0.0, 0.0),
            (5.0, 0.0, 5.0),
            (0.0, 0.0, 5.0),  # floor
            (0.0, 0.0, 0.0),
            (0.0, 5.0, 0.0),
            (0.0, 5.0, 1.0),
            (0.0, 0.0, 1.0),  # wall
        ]
        faces = [
            [0, 1, 2],
            [0, 2, 3],  # floor: walkable
            [4, 5, 6],
            [4, 6, 7],  # wall: steep
        ]
        result = _compute_walkable_ratio(verts, faces)
        assert result["walkable_faces"] == 2
        assert result["total_faces"] == 4
        assert result["walkable_ratio"] == 0.5

    def test_empty_faces(self) -> None:
        """No faces → zero ratio."""
        result = _compute_walkable_ratio([(0, 0, 0)], [])
        assert result["walkable_faces"] == 0
        assert result["total_faces"] == 0
        assert result["walkable_ratio"] == 0.0

    def test_custom_max_slope(self) -> None:
        """A 30-degree slope is walkable at 45deg but not at 15deg."""
        import math

        h = math.sin(math.radians(30))
        verts = [(0.0, 0.0, 0.0), (1.0, h, 0.0), (0.0, 0.0, 1.0)]
        faces = [[0, 1, 2]]
        result_45 = _compute_walkable_ratio(verts, faces, max_slope=45.0)
        result_15 = _compute_walkable_ratio(verts, faces, max_slope=15.0)
        assert result_45["walkable_faces"] == 1
        assert result_15["walkable_faces"] == 0


class TestAdaptiveParams:
    """Test adaptive parameter calibration based on walkable face ratio."""

    def test_normalized_small_geometry_avoids_total_erosion(self) -> None:
        verts = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 0.0, 2.0), (0.0, 0.0, 2.0)]
        result = _adaptive_params(verts, [[0, 1, 2], [0, 2, 3]])
        assert result["walkable_profile"] == "normalized_small"
        assert result["agent_radius"] == 0.05
        assert result["region_min_size"] == 1

    def test_high_walkable_ratio_standard_params(self) -> None:
        """High walkable ratio (>=30%) → standard params, no reduction."""
        # Flat plane: 100% walkable
        verts = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 10.0), (0.0, 0.0, 10.0)]
        faces = [[0, 1, 2], [0, 2, 3]]
        result = _adaptive_params(verts, faces)
        assert result["walkable_profile"] == "high_walkable"
        assert result["agent_max_slope"] == 45.0
        assert result["region_min_size"] == 8
        # Agent radius should NOT be reduced (stays at auto_agent_params default)
        assert result["agent_radius"] >= 0.3
        # Cell size should not be reduced for high walkable
        assert "cell_size" in result
        assert "cell_height" in result

    def test_mid_walkable_ratio_reduced_params(self) -> None:
        """Mid walkable ratio (10-29%) → reduced agent_radius, 50deg slope, finer cells."""
        # 1 walkable + 9 steep = 10% walkable
        verts = [
            # 3 horizontal faces (walkable)
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            # 9 vertical faces (steep) — need enough verts for 9 triangles
            (10.0, 0.0, 0.0),
            (10.0, 10.0, 0.0),
            (10.0, 10.0, 1.0),
            (10.0, 0.0, 1.0),
            (10.0, 10.0, 2.0),
            (10.0, 0.0, 2.0),
            (10.0, 10.0, 3.0),
            (10.0, 0.0, 3.0),
            (10.0, 10.0, 4.0),
        ]
        faces = [
            [0, 1, 2],  # walkable
            [3, 4, 5],
            [3, 5, 6],
            [4, 5, 7],
            [4, 7, 8],  # steep
            [5, 7, 9],
            [6, 8, 10],
            [7, 9, 10],
            [8, 10, 11],  # steep
            [9, 10, 11],  # steep — total 3 walkable + 9 steep = 25%
        ]
        result = _adaptive_params(verts, faces)
        assert result["walkable_profile"] == "mid_walkable"
        assert result["agent_max_slope"] == 50.0
        assert result["region_min_size"] == 4
        # Agent radius should be reduced
        assert result["agent_radius"] < 0.5
        # Cell size should be reduced for mid walkable (at most 50% of base)
        assert result["cell_size"] <= 0.5

    def test_low_walkable_ratio_minimal_params(self) -> None:
        """Low walkable ratio (<10%) → minimal agent_radius, 60deg slope, finest cells."""
        # 1 walkable + 19 steep = 5% walkable
        verts = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),  # walkable tri
        ]
        # Add 19 steep (vertical) faces — each needs 3 unique verts on X=10 plane
        for i in range(19):
            y_base = i * 2
            verts.extend(
                [
                    (10.0, float(y_base), 0.0),
                    (10.0, float(y_base + 1), 0.0),
                    (10.0, float(y_base), 1.0),
                ]
            )
        faces = [[0, 1, 2]]  # 1 walkable
        for i in range(19):
            base = 3 + i * 3
            faces.append([base, base + 1, base + 2])  # steep
        result = _adaptive_params(verts, faces)
        assert result["walkable_profile"] == "low_walkable"
        assert result["agent_max_slope"] == 60.0
        assert result["region_min_size"] == 1
        assert result["agent_radius"] <= 0.1
        # Cell size should be finest for low walkable
        assert result["cell_size"] <= 0.15

    def test_empty_geometry_returns_defaults(self) -> None:
        """Empty geometry → low_walkable profile (0% walkable ratio)."""
        result = _adaptive_params([], [])
        assert result["walkable_profile"] == "low_walkable"
        assert result["walkable_ratio"] == 0.0

    def test_returns_walkability_analysis(self) -> None:
        """Result should include walkable_faces and total_faces."""
        verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)]
        faces = [[0, 1, 2]]
        result = _adaptive_params(verts, faces)
        assert "walkable_faces" in result
        assert "total_faces" in result
        assert result["total_faces"] == 1
        assert result["walkable_faces"] == 1

    def test_high_ratio_boundary_30_pct(self) -> None:
        """Exactly 30% walkable should be high_walkable."""
        # 3 walkable + 7 steep = 30%
        verts = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
        ]
        # Duplicate verts for steep faces on X=10 plane
        for i in range(7):
            y_base = i * 2
            verts.extend(
                [
                    (10.0, float(y_base), 0.0),
                    (10.0, float(y_base + 1), 0.0),
                    (10.0, float(y_base), 1.0),
                ]
            )
        faces = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]  # 3 walkable
        for i in range(7):
            base = 9 + i * 3
            faces.append([base, base + 1, base + 2])  # steep
        result = _adaptive_params(verts, faces)
        assert result["walkable_ratio"] == 0.3
        assert result["walkable_profile"] == "high_walkable"

    def test_mid_ratio_boundary_10_pct(self) -> None:
        """Exactly 10% walkable should be mid_walkable (boundary is < 0.10 for low)."""
        # 1 walkable + 9 steep = 10%
        verts = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),  # walkable
        ]
        for i in range(9):
            y_base = i * 2
            verts.extend(
                [
                    (10.0, float(y_base), 0.0),
                    (10.0, float(y_base + 1), 0.0),
                    (10.0, float(y_base), 1.0),
                ]
            )
        faces = [[0, 1, 2]]  # 1 walkable
        for i in range(9):
            base = 3 + i * 3
            faces.append([base, base + 1, base + 2])  # steep
        result = _adaptive_params(verts, faces)
        assert result["walkable_ratio"] == 0.1
        assert result["walkable_profile"] == "mid_walkable"


class TestAggressiveAdaptiveParams:
    """Test aggressive adaptive mode — mid_walkable uses low_walkable params."""

    def test_aggressive_mid_walkable_uses_low_params(self) -> None:
        """Aggressive mode: mid walkable ratio should use low_walkable params (60deg, 0.05 radius)."""
        # 1 walkable + 9 steep = 10% walkable
        verts = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
        ]
        for i in range(9):
            y_base = i * 2
            verts.extend(
                [
                    (10.0, float(y_base), 0.0),
                    (10.0, float(y_base + 1), 0.0),
                    (10.0, float(y_base), 1.0),
                ]
            )
        faces = [[0, 1, 2]]
        for i in range(9):
            base = 3 + i * 3
            faces.append([base, base + 1, base + 2])
        result = _adaptive_params(verts, faces, aggressive=True)
        # Should use low_walkable params, not mid_walkable
        assert result["walkable_profile"] == "mid_walkable_aggressive"
        assert result["agent_max_slope"] == 60.0
        assert result["region_min_size"] == 1
        assert result["agent_radius"] <= 0.1
        assert result["cell_size"] <= 0.15

    def test_aggressive_high_walkable_unchanged(self) -> None:
        """Aggressive mode: high walkable ratio should still use standard params."""
        verts = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 10.0), (0.0, 0.0, 10.0)]
        faces = [[0, 1, 2], [0, 2, 3]]
        result = _adaptive_params(verts, faces, aggressive=True)
        assert result["walkable_profile"] == "high_walkable"
        assert result["agent_max_slope"] == 45.0
        assert result["region_min_size"] == 8

    def test_aggressive_low_walkable_unchanged(self) -> None:
        """Aggressive mode: low walkable ratio should still use low_walkable params."""
        verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)]
        for i in range(19):
            y_base = i * 2
            verts.extend(
                [
                    (10.0, float(y_base), 0.0),
                    (10.0, float(y_base + 1), 0.0),
                    (10.0, float(y_base), 1.0),
                ]
            )
        faces = [[0, 1, 2]]
        for i in range(19):
            base = 3 + i * 3
            faces.append([base, base + 1, base + 2])
        result = _adaptive_params(verts, faces, aggressive=True)
        # Low walkable is still low_walkable (aggressive doesn't change it)
        assert result["walkable_profile"] == "low_walkable"
        assert result["agent_max_slope"] == 60.0

    def test_aggressive_vs_non_aggressive_mid_walkable_differs(self) -> None:
        """Aggressive and non-aggressive should produce different params for mid_walkable."""
        verts = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
        ]
        for i in range(9):
            y_base = i * 2
            verts.extend(
                [
                    (10.0, float(y_base), 0.0),
                    (10.0, float(y_base + 1), 0.0),
                    (10.0, float(y_base), 1.0),
                ]
            )
        faces = [[0, 1, 2]]
        for i in range(9):
            base = 3 + i * 3
            faces.append([base, base + 1, base + 2])
        non_agg = _adaptive_params(verts, faces, aggressive=False)
        agg = _adaptive_params(verts, faces, aggressive=True)
        # Profiles should differ
        assert non_agg["walkable_profile"] == "mid_walkable"
        assert agg["walkable_profile"] == "mid_walkable_aggressive"
        # Slope should be higher in aggressive mode
        assert agg["agent_max_slope"] > non_agg["agent_max_slope"]
        # Radius should be smaller in aggressive mode
        assert agg["agent_radius"] < non_agg["agent_radius"]
        # Region min should be smaller in aggressive mode
        assert agg["region_min_size"] < non_agg["region_min_size"]


class TestExportNavmeshObj:
    """Test navmesh debug OBJ export."""

    def test_simple_export(self, tmp_path: Path) -> None:
        """Export a simple navmesh with 1 triangle."""
        result = {
            "verts": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            "polys": [[0, 1, 2]],
        }
        out = tmp_path / "navmesh.obj"
        export_navmesh_obj(result, out)
        content = out.read_text()
        assert "v 0.000000 0.000000 0.000000" in content
        assert "f 1 2 3" in content

    def test_empty_navmesh(self, tmp_path: Path) -> None:
        """Export with no polys should produce header only."""
        result = {"verts": [], "polys": []}
        out = tmp_path / "empty.obj"
        export_navmesh_obj(result, out)
        content = out.read_text()
        assert "Polymesh: 0 polys" in content
        assert "f " not in content

    def test_quad_polygon_fan_triangulated(self, tmp_path: Path) -> None:
        """Quad polygon should be fan-triangulated into 2 triangles."""
        result = {
            "verts": [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 0.0, 1.0],
                [0.0, 0.0, 1.0],
            ],
            "polys": [[0, 1, 2, 3]],
        }
        out = tmp_path / "quad.obj"
        export_navmesh_obj(result, out)
        content = out.read_text()
        # Fan triangulation: f 1 2 3, f 1 3 4
        assert "f 1 2 3" in content
        assert "f 1 3 4" in content

    def test_multiple_polys(self, tmp_path: Path) -> None:
        """Export with multiple polys."""
        result = {
            "verts": [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0],
                [2.0, 0.0, 0.0],
                [3.0, 0.0, 0.0],
                [2.0, 0.0, 1.0],
            ],
            "polys": [[0, 1, 2], [3, 4, 5]],
        }
        out = tmp_path / "multi.obj"
        export_navmesh_obj(result, out)
        content = out.read_text()
        assert "f 1 2 3" in content
        assert "f 4 5 6" in content
