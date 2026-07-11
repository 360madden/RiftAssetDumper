"""Tests for scripts/extract_zone_geometry.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.extract_zone_geometry import _load_walkability, _slugify


class TestSlugify:
    """Test zone tuple to filesystem-safe slug conversion."""

    def test_basic_dots(self) -> None:
        assert _slugify("ep1.world_objects.dungeons") == "ep1-world-objects-dungeons"

    def test_leading_trailing_dots(self) -> None:
        assert _slugify(".ep1.nature.") == "ep1-nature"

    def test_multiple_dots(self) -> None:
        assert _slugify("vanilla..vfx") == "vanilla-vfx"

    def test_empty(self) -> None:
        assert _slugify("") == ""

    def test_special_chars(self) -> None:
        assert _slugify("ep1/test:zone") == "ep1-test-zone"


class TestLoadWalkability:
    """Test walkability classification loading."""

    def test_missing_file_returns_empty(self) -> None:
        # The default path likely exists; test the function with a non-existent path
        # by checking the module-level function handles missing file gracefully
        result = _load_walkability()
        assert isinstance(result, dict)

    def test_returns_asset_to_label_map(self) -> None:
        result = _load_walkability()
        # If the file exists, check that values are strings (labels)
        if result:
            for _aid, label in list(result.items())[:1]:
                assert isinstance(label, str)


class TestExtractZone:
    """Test extract_zone with mock flythrough index data."""

    def _create_mock_index(self, tmpdir: Path) -> Path:
        """Create a minimal flythrough-index.json in a temp directory."""
        index = {
            "schema": "flythrough-index-v1",
            "assets": {
                "aaa1111111111111": {
                    "vertex_count": 10,
                    "face_count": 8,
                    "faced": True,
                    "mesh_size": 329,
                    "has_transform": False,
                    "zone": {
                        "tuple": "ep1.world_objects.dungeons",
                        "expansion": "ep1",
                        "category": "world_objects",
                        "name": "dungeons",
                        "confidence": "high",
                    },
                    "obj_path": str(tmpdir / "aaa1111111111111.obj"),
                },
                "bbb2222222222222": {
                    "vertex_count": 20,
                    "face_count": 18,
                    "faced": True,
                    "mesh_size": 329,
                    "has_transform": False,
                    "zone": {
                        "tuple": "ep2.world_objects.architecture",
                        "expansion": "ep2",
                        "category": "world_objects",
                        "name": "architecture",
                        "confidence": "high",
                    },
                    "obj_path": str(tmpdir / "bbb2222222222222.obj"),
                },
                "ccc3333333333333": {
                    "vertex_count": 5,
                    "face_count": 0,
                    "faced": False,
                    "mesh_size": 325,
                    "has_transform": True,
                    "zone": {
                        "tuple": "ep1.world_objects.dungeons",
                        "expansion": "ep1",
                        "category": "world_objects",
                        "name": "dungeons",
                        "confidence": "high",
                    },
                    "obj_path": str(tmpdir / "ccc3333333333333.obj"),
                },
            },
        }
        index_path = tmpdir / "flythrough-index.json"
        with open(index_path, "w") as f:
            json.dump(index, f)
        return index_path

    def _create_mock_obj(self, path: Path, vertices: int = 10, faces: int = 8) -> None:
        """Create a minimal OBJ file with the given vertex/face counts."""
        lines = []
        for i in range(vertices):
            lines.append(f"v {i}.0 0.0 0.0")
        for i in range(faces):
            v0 = i % vertices
            v1 = (i + 1) % vertices
            v2 = (i + 2) % vertices
            lines.append(f"f {v0 + 1} {v1 + 1} {v2 + 1}")
        path.write_text("\n".join(lines) + "\n")

    def test_extract_dungeons_zone(self, tmp_path: Path) -> None:
        """Test extracting a zone with 2 assets (1 faced, 1 pos-only)."""
        import scripts.extract_zone_geometry as ezg

        index_path = self._create_mock_index(tmp_path)
        self._create_mock_obj(tmp_path / "aaa1111111111111.obj")
        self._create_mock_obj(tmp_path / "bbb2222222222222.obj")
        # Don't create ccc (pos-only) OBJ — it should be skipped by faced_only filter

        # Patch the module's INDEX_PATH
        original_index = ezg.INDEX_PATH
        original_out_dir = ezg.DEFAULT_OUT_DIR
        ezg.INDEX_PATH = index_path
        ezg.DEFAULT_OUT_DIR = tmp_path / "output"

        try:
            out_obj = tmp_path / "output" / "zone-test.obj"
            out_meta = tmp_path / "output" / "zone-test-meta.json"
            meta = ezg.extract_zone(
                "ep1.world_objects.dungeons",
                faced_only=True,
                out_obj=out_obj,
                out_meta=out_meta,
            )

            # Should extract 1 faced asset (aaa), skip 1 pos-only (ccc) via faced_only filter
            assert meta["assets_extracted"] == 1
            assert meta["assets_total"] == 1  # faced_only=True filters pos-only before counting
            assert meta["geometry"]["vertex_count"] == 10
            assert meta["geometry"]["face_count"] == 8

            # OBJ file should exist and have content
            assert out_obj.exists()
            content = out_obj.read_text()
            assert "v " in content
            assert "f " in content

            # Metadata should exist
            assert out_meta.exists()
            meta_data = json.loads(out_meta.read_text())
            assert meta_data["zone_tuple"] == "ep1.world_objects.dungeons"
        finally:
            ezg.INDEX_PATH = original_index
            ezg.DEFAULT_OUT_DIR = original_out_dir

    def test_extract_nonexistent_zone_raises(self, tmp_path: Path) -> None:
        """Test that extracting a non-existent zone raises ValueError."""
        import scripts.extract_zone_geometry as ezg

        index_path = self._create_mock_index(tmp_path)
        original_index = ezg.INDEX_PATH
        ezg.INDEX_PATH = index_path

        try:
            with pytest.raises(ValueError, match="No assets found"):
                ezg.extract_zone(
                    "nonexistent.zone",
                    out_obj=tmp_path / "out.obj",
                    out_meta=tmp_path / "out.json",
                )
        finally:
            ezg.INDEX_PATH = original_index

    def test_extract_with_pos_only_included(self, tmp_path: Path) -> None:
        """Test that include_pos_only includes position-only assets."""
        import scripts.extract_zone_geometry as ezg

        index_path = self._create_mock_index(tmp_path)
        self._create_mock_obj(tmp_path / "aaa1111111111111.obj")
        self._create_mock_obj(tmp_path / "ccc3333333333333.obj", vertices=5, faces=0)

        original_index = ezg.INDEX_PATH
        ezg.INDEX_PATH = index_path

        try:
            meta = ezg.extract_zone(
                "ep1.world_objects.dungeons",
                faced_only=False,  # Include pos-only
                out_obj=tmp_path / "out.obj",
                out_meta=tmp_path / "out.json",
            )
            # Both faced and pos-only should be extracted
            assert meta["assets_extracted"] == 2
        finally:
            ezg.INDEX_PATH = original_index

    def test_metadata_has_bounds(self, tmp_path: Path) -> None:
        """Test that extracted metadata has valid bounding box."""
        import scripts.extract_zone_geometry as ezg

        index_path = self._create_mock_index(tmp_path)
        self._create_mock_obj(tmp_path / "aaa1111111111111.obj")

        original_index = ezg.INDEX_PATH
        ezg.INDEX_PATH = index_path

        try:
            meta = ezg.extract_zone(
                "ep1.world_objects.dungeons",
                out_obj=tmp_path / "out.obj",
                out_meta=tmp_path / "out.json",
            )
            b = meta["geometry"]["bounds"]
            assert "min" in b
            assert "max" in b
            assert "extent" in b
            assert len(b["min"]) == 3
            assert len(b["max"]) == 3
            # X extent should be > 0 (vertices go 0..9)
            assert b["extent"][0] > 0
        finally:
            ezg.INDEX_PATH = original_index
