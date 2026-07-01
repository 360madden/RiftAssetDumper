"""Tests for scripts/analyze_obb_shape.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from scripts.analyze_obb_shape import (  # noqa: E402
    classify_shape,
    parse_obj_bounds,
)


class TestParseObjBounds:
    """Bounding box extraction from OBJ content."""

    def test_simple_triangle(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".obj", delete=False
        ) as f:
            f.write("v 0.0 0.0 0.0\nv 10.0 0.0 0.0\nv 0.0 0.0 5.0\n")
            f.write("f 1 2 3\n")
            f.flush()
            result = parse_obj_bounds(Path(f.name))
        assert result is not None
        assert result["vertex_count"] == 3
        assert result["face_count"] == 1
        b = result["bbox"]
        assert b["dx"] == 10.0
        assert b["dy"] == 0.0
        assert b["dz"] == 5.0
        assert b["min"] == [0.0, 0.0, 0.0]
        assert b["max"] == [10.0, 0.0, 5.0]

    def test_extended_bbox(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".obj", delete=False
        ) as f:
            f.write("v -5.0 2.0 -10.0\nv 15.0 20.0 30.0\n")
            f.write("f 1 2\n")
            f.flush()
            result = parse_obj_bounds(Path(f.name))
        assert result is not None
        b = result["bbox"]
        assert b["dx"] == 20.0
        assert b["dy"] == 18.0
        assert b["dz"] == 40.0
        assert b["min"] == [-5.0, 2.0, -10.0]
        assert b["max"] == [15.0, 20.0, 30.0]

    def test_empty_file(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".obj", delete=False
        ) as f:
            f.write("# Just a comment\n")
            f.flush()
            result = parse_obj_bounds(Path(f.name))
        assert result is None

    def test_no_vertices(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".obj", delete=False
        ) as f:
            f.write("f 1 2 3\n")
            f.flush()
            result = parse_obj_bounds(Path(f.name))
        assert result is None

    def test_skips_normals_and_uvs(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".obj", delete=False
        ) as f:
            f.write("v 0.0 0.0 0.0\nv 1.0 0.0 0.0\nv 0.0 1.0 0.0\n")
            f.write("vn 0.0 0.0 1.0\nvt 0.5 0.5\n")
            f.write("f 1/1/1 2/1/1 3/1/1\n")
            f.flush()
            result = parse_obj_bounds(Path(f.name))
        assert result is not None
        assert result["vertex_count"] == 3  # Only v lines counted

    def test_malformed_v_line(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".obj", delete=False
        ) as f:
            f.write("v 0.0 0.0 0.0\nv 1.0\nv 2.0 2.0 2.0\n")
            f.write("f 1 3\n")
            f.flush()
            result = parse_obj_bounds(Path(f.name))
        assert result is not None
        # The "v 1.0" line is malformed, skipped
        assert result["vertex_count"] == 2
        b = result["bbox"]
        assert b["dx"] == 2.0
        assert b["dz"] == 2.0

    def test_includes_path_and_filename(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".obj", delete=False
        ) as f:
            f.write("v 0.0 0.0 0.0\nv 1.0 1.0 1.0\nf 1 2\n")
            f.flush()
            result = parse_obj_bounds(Path(f.name))
        assert result is not None
        assert "path" in result
        assert "filename" in result
        assert result["filename"].endswith(".obj")


class TestClassifyShape:
    """Shape classification from bounding-box dimensions."""

    def test_floor_very_flat(self) -> None:
        """Flat plane: height much smaller than width."""
        bounds = {
            "bbox": {"dx": 100.0, "dy": 1.0, "dz": 100.0},
            "vertex_count": 100,
            "face_count": 50,
        }
        result = classify_shape(bounds)
        assert result["shape_label"] == "floor"
        assert result["hw_ratio"] == pytest.approx(0.01, abs=1e-3)
        assert result["wh_ratio"] == 100.0

    def test_floor_extreme_wide(self) -> None:
        """w/h > 10 override: extremely wide."""
        bounds = {
            "bbox": {"dx": 50.0, "dy": 3.0, "dz": 50.0},
            "vertex_count": 50,
            "face_count": 20,
        }
        result = classify_shape(bounds)
        # h/w = 3/50 = 0.06 → floor, wh = 50/3 = 16.7 → floor override
        assert result["shape_label"] == "floor"
        assert result["wh_ratio"] == pytest.approx(16.666, abs=0.1)

    def test_platform(self) -> None:
        """Moderately flat."""
        bounds = {
            "bbox": {"dx": 10.0, "dy": 3.0, "dz": 10.0},
            "vertex_count": 100,
            "face_count": 50,
        }
        result = classify_shape(bounds)
        assert result["shape_label"] == "platform"
        assert result["hw_ratio"] == 0.3

    def test_platform_upper_boundary(self) -> None:
        """Just below structure threshold (h/w = 0.49)."""
        bounds = {
            "bbox": {"dx": 10.0, "dy": 4.9, "dz": 10.0},
            "vertex_count": 100,
            "face_count": 50,
        }
        result = classify_shape(bounds)
        assert result["shape_label"] == "platform"

    def test_structure_cubic(self) -> None:
        """Roughly cubic."""
        bounds = {
            "bbox": {"dx": 10.0, "dy": 8.0, "dz": 12.0},
            "vertex_count": 100,
            "face_count": 50,
        }
        result = classify_shape(bounds)
        assert result["shape_label"] == "structure"

    def test_structure_at_lower_boundary(self) -> None:
        """h/w = 0.5 — exact boundary."""
        bounds = {
            "bbox": {"dx": 10.0, "dy": 5.0, "dz": 10.0},
            "vertex_count": 100,
            "face_count": 50,
        }
        result = classify_shape(bounds)
        assert result["shape_label"] == "structure"

    def test_wall_pillar(self) -> None:
        """Tall and thin."""
        bounds = {
            "bbox": {"dx": 2.0, "dy": 20.0, "dz": 2.0},
            "vertex_count": 50,
            "face_count": 20,
        }
        result = classify_shape(bounds)
        assert result["shape_label"] == "wall_pillar"
        assert result["hw_ratio"] == 10.0

    def test_unit_cube_detection_exact_1(self) -> None:
        """1.0 x 1.0 x 1.0 is a unit cube."""
        bounds = {
            "bbox": {"dx": 1.0, "dy": 1.0, "dz": 1.0},
            "vertex_count": 5000,
            "face_count": 5000,
        }
        result = classify_shape(bounds)
        assert result["is_unit_cube"] is True
        assert result["shape_quality"] == "normalized_unit_cube"
        assert result["shape_confidence"] == "low"

    def test_unit_cube_detection_exact_2(self) -> None:
        """2.0 x 2.0 x 2.0 is a unit cube."""
        bounds = {
            "bbox": {"dx": 2.0, "dy": 2.0, "dz": 2.0},
            "vertex_count": 6489,
            "face_count": 6487,
        }
        result = classify_shape(bounds)
        assert result["is_unit_cube"] is True
        assert result["shape_quality"] == "normalized_unit_cube"

    def test_not_unit_cube_slightly_off(self) -> None:
        """1.02 x 0.98 x 1.0 — not unit cube (outside 0.01 tolerance)."""
        bounds = {
            "bbox": {"dx": 1.02, "dy": 0.98, "dz": 1.0},
            "vertex_count": 100,
            "face_count": 50,
        }
        result = classify_shape(bounds)
        assert result["is_unit_cube"] is False

    def test_zero_dimensions_handled(self) -> None:
        """All-zero dimensions should still produce a result (not detected as unit cube)."""
        bounds = {
            "bbox": {"dx": 0.0, "dy": 0.0, "dz": 0.0},
            "vertex_count": 1,
            "face_count": 0,
        }
        result = classify_shape(bounds)
        assert result["shape_label"] in (
            "floor", "platform", "structure", "wall_pillar"
        )
        # 0.0 does not match 1.0 or 2.0 unit-cube patterns
        assert result["is_unit_cube"] is False

    def test_high_confidence_non_unit_cube(self) -> None:
        """Non-unit-cube meshes get high confidence if ratios are clear."""
        bounds = {
            "bbox": {"dx": 100.0, "dy": 2.0, "dz": 100.0},
            "vertex_count": 500,
            "face_count": 400,
        }
        result = classify_shape(bounds)
        assert result["shape_confidence"] == "high"
        assert result["shape_quality"] == "raw"

    def test_mesh107_like_flat_surface(self) -> None:
        """Real example: mesh107 (3.1 x 0.1 x 3.1)."""
        bounds = {
            "bbox": {"dx": 3.1, "dy": 0.1, "dz": 3.1},
            "vertex_count": 41,
            "face_count": 39,
        }
        result = classify_shape(bounds)
        assert result["shape_label"] == "floor"
        assert result["hw_ratio"] == pytest.approx(0.032, abs=1e-3)
        assert result["wh_ratio"] == 31.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
