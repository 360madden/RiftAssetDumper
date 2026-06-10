#!/usr/bin/env python3
"""Unit tests for FT-6.2 validation suite."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _import_ft6() -> Any:
    """Import the ft6_validation module."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import ft6_validation

    return ft6_validation


# ─── synthetic OBJ helpers ─────────────────────────────────────────────────


def _obj_text(vertices: int, faces: list[str]) -> str:
    """Build a minimal OBJ text blob."""
    lines = [f"v {i}.0 {i}.0 {i}.0" for i in range(1, vertices + 1)]
    lines.extend(faces)
    return "\n".join(lines)


# ─── _parse_obj_faces tests ────────────────────────────────────────────────


class TestParseObjFaces:
    """Tests for the face parsing helper."""

    def test_no_faces(self) -> None:
        ft6 = _import_ft6()
        text = "v 1.0 2.0 3.0\nv 4.0 5.0 6.0\n"
        fc, mx, bok, neg, zero = ft6._parse_obj_faces(text, 2)
        assert fc == 0
        assert mx == -1
        assert bok is True
        assert neg == []
        assert zero == 0

    def test_normal_faces(self) -> None:
        ft6 = _import_ft6()
        text = _obj_text(4, ["f 1 2 3", "f 2 3 4"])
        fc, mx, bok, neg, zero = ft6._parse_obj_faces(text, 4)
        assert fc == 2
        assert mx == 4
        assert bok is True
        assert neg == []
        assert zero == 0

    def test_bounds_fail(self) -> None:
        ft6 = _import_ft6()
        text = _obj_text(3, ["f 1 2 5"])  # index 5 > vertex count 3
        fc, mx, bok, neg, zero = ft6._parse_obj_faces(text, 3)
        assert fc == 1
        assert mx == 5
        assert bok is False
        assert neg == []

    def test_negative_indices(self) -> None:
        ft6 = _import_ft6()
        text = _obj_text(3, ["f -1 1 2", "f -2 3 1"])
        fc, mx, bok, neg, zero = ft6._parse_obj_faces(text, 3)
        assert fc == 2
        assert neg == [-1, -2]

    def test_zero_indices(self) -> None:
        ft6 = _import_ft6()
        text = _obj_text(3, ["f 0 1 2", "f 1 0 3"])
        fc, mx, bok, neg, zero = ft6._parse_obj_faces(text, 3)
        assert fc == 2
        assert zero == 2  # two zero-valued indices

    def test_texture_coords_skipped(self) -> None:
        ft6 = _import_ft6()
        text = _obj_text(3, ["f 1/1 2/2 3/3"])
        fc, mx, bok, neg, zero = ft6._parse_obj_faces(text, 3)
        assert fc == 1
        assert mx == 3

    def test_nan_in_text_not_parsed_as_face(self) -> None:
        ft6 = _import_ft6()
        text = "v 1.0 nan 3.0\nv 4.0 5.0 6.0\nf 1 2 1\n"
        fc, mx, bok, neg, zero = ft6._parse_obj_faces(text, 2)
        # The line starting with "f " is the face; "nan" line is a vertex line
        assert fc == 1
        assert mx == 2


# ─── deduplication tests ───────────────────────────────────────────────────


class TestDedup:
    """Tests for the _deduplicate_entries helper."""

    def test_no_dupes(self) -> None:
        ft6 = _import_ft6()
        entries = [
            {"asset_id": "aa", "mesh_block": "6", "file_size": 100},
            {"asset_id": "bb", "mesh_block": "6", "file_size": 200},
        ]
        result = ft6._deduplicate_entries(entries)
        assert len(result) == 2

    def test_keeps_largest(self) -> None:
        ft6 = _import_ft6()
        entries = [
            {"asset_id": "aa", "mesh_block": "6", "file_size": 100, "path": "/small"},
            {"asset_id": "aa", "mesh_block": "6", "file_size": 200, "path": "/large"},
        ]
        result = ft6._deduplicate_entries(entries)
        assert len(result) == 1
        assert result[0]["path"] == "/large"

    def test_different_mesh_blocks(self) -> None:
        ft6 = _import_ft6()
        entries = [
            {"asset_id": "aa", "mesh_block": "6", "file_size": 100},
            {"asset_id": "aa", "mesh_block": "7", "file_size": 150},
        ]
        result = ft6._deduplicate_entries(entries)
        assert len(result) == 2  # different mesh blocks = different entries

    def test_missing_asset_id(self) -> None:
        ft6 = _import_ft6()
        entries = [
            {"mesh_block": "6", "file_size": 100},
            {"mesh_block": "6", "file_size": 200},
        ]
        result = ft6._deduplicate_entries(entries)
        assert len(result) == 1  # both "unknown" with same mesh_block
        assert result[0]["file_size"] == 200


# ─── load_json tests ───────────────────────────────────────────────────────


class TestLoadJson:
    """Tests for the _load_json helper."""

    def test_missing_file(self) -> None:
        ft6 = _import_ft6()
        result = ft6._load_json(Path("/nonexistent/path.json"))
        assert result == {}

    def test_invalid_json(self, tmp_path: Path) -> None:
        ft6 = _import_ft6()
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        result = ft6._load_json(bad)
        assert result == {}


# ─── coverage tests ────────────────────────────────────────────────────────


class TestCoverage:
    """Tests for check_world_json_coverage."""

    def test_full_coverage(self) -> None:
        ft6 = _import_ft6()
        sg = {"entries": [{"asset_id": "a"}, {"asset_id": "b"}]}
        deduped = {"a", "b"}
        result = ft6.check_world_json_coverage(sg, deduped)
        assert result["covered"] == 2
        assert result["missing_world_json"] == 0
        assert result["coverage_pct"] == 100.0
        assert result["status"] == "pass"

    def test_partial_coverage(self) -> None:
        ft6 = _import_ft6()
        sg = {"entries": [{"asset_id": "a"}]}
        deduped = {"a", "b"}
        result = ft6.check_world_json_coverage(sg, deduped)
        assert result["covered"] == 1
        assert result["missing_world_json"] == 1
        assert result["coverage_pct"] == 50.0
        assert result["status"] == "warn"

    def test_empty_deduped_ids(self) -> None:
        ft6 = _import_ft6()
        sg = {"entries": [{"asset_id": "a"}]}
        result = ft6.check_world_json_coverage(sg, set())
        assert result["coverage_pct"] == 0
        assert result["status"] == "pass"  # nothing missing = pass


# ─── world.json validation tests ───────────────────────────────────────────


class TestWorldJsonValidation:
    """Tests for validate_world_jsons."""

    def test_all_valid(self, tmp_path: Path, monkeypatch: Any) -> None:
        ft6 = _import_ft6()
        # Create a worlds dir with valid world.json
        worlds = tmp_path / "worlds"
        worlds.mkdir()
        wj = {
            "SchemaVersion": "scene-graph/v1",
            "NodeCount": 1,
            "MeshCount": 1,
            "Nodes": [{"Name": "root", "Scale": 1.0}],
            "Meshes": [{"MeshBlock": 6}],
        }
        (worlds / "test.world.json").write_text(json.dumps(wj), encoding="utf-8")
        monkeypatch.setattr(ft6, "WORLDS_DIR", worlds)

        sg = {"entries": [{"asset_id": "test", "world_json": "test.world.json"}]}
        result = ft6.validate_world_jsons(sg)
        assert result["total_world_jsons"] == 1
        assert result["missing_files"] == 0
        assert result["invalid_json"] == 0
        assert result["empty_nodes"] == 0
        assert result["status"] == "pass"


# ─── CLI smoke test ────────────────────────────────────────────────────────


def test_cli_quick() -> None:
    """Smoke: quick mode runs without error."""
    result = subprocess.run(
        ["python", str(SCRIPTS_DIR / "ft6_validation.py"), "--quick", "--json-only"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=60,
    )
    assert result.returncode == 0, f"stderr: {result.stderr[-500:]}"


def test_cli_help() -> None:
    """Help text prints."""
    result = subprocess.run(
        ["python", str(SCRIPTS_DIR / "ft6_validation.py"), "--help"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
    )
    assert result.returncode == 0
    assert "--quick" in result.stdout
    assert "--json-only" in result.stdout


# ─── OBJ integrity with synthetic data ─────────────────────────────────────


class TestObjIntegrity:
    """Tests for check_obj_integrity with synthetic data."""

    def test_all_clean(self, tmp_path: Path) -> None:
        ft6 = _import_ft6()
        # Create a clean OBJ
        obj = tmp_path / "clean.obj"
        obj.write_text(_obj_text(4, ["f 1 2 3", "f 2 3 4"]), encoding="utf-8")
        sha = ft6.hashlib.sha256(obj.read_bytes()).hexdigest()

        entries = [
            {
                "path": str(obj),
                "asset_id": "0000000000000001",
                "mesh_block": "6",
                "file_size": obj.stat().st_size,
                "sha256": sha,
            }
        ]
        result = ft6.check_obj_integrity(entries)
        assert result["total_objs"] == 1
        assert result["missing"] == 0
        assert result["nan_count"] == 0
        assert result["bounds_fail"] == 0
        assert result["neg_index_count"] == 0
        assert result["zero_face_idx"] == 0
        assert result["sha256_mismatch"] == 0
        assert result["status"] == "pass"

    def test_nan_detected(self, tmp_path: Path) -> None:
        ft6 = _import_ft6()
        obj = tmp_path / "nan.obj"
        obj.write_text("v 1.0 nan 3.0\nv 4.0 5.0 6.0\nf 1 2 2\n", encoding="utf-8")
        entries = [
            {
                "path": str(obj),
                "asset_id": "nan",
                "mesh_block": "6",
                "file_size": obj.stat().st_size,
            }
        ]
        result = ft6.check_obj_integrity(entries)
        assert result["nan_count"] == 1
        assert result["status"] == "fail"

    def test_bounds_fail_detected(self, tmp_path: Path) -> None:
        ft6 = _import_ft6()
        obj = tmp_path / "bounds.obj"
        obj.write_text(_obj_text(3, ["f 1 2 99"]), encoding="utf-8")
        entries = [
            {
                "path": str(obj),
                "asset_id": "bounds",
                "mesh_block": "6",
                "file_size": obj.stat().st_size,
            }
        ]
        result = ft6.check_obj_integrity(entries)
        assert result["bounds_fail"] == 1
        assert result["status"] == "fail"

    def test_missing_file(self, tmp_path: Path) -> None:
        ft6 = _import_ft6()
        entries = [
            {
                "path": str(tmp_path / "nonexistent.obj"),
                "asset_id": "missing",
                "mesh_block": "6",
                "file_size": 0,
            }
        ]
        result = ft6.check_obj_integrity(entries)
        assert result["missing"] == 1
        assert result["status"] == "fail"


# ─── manifest consistency tests ────────────────────────────────────────────


class TestManifestConsistency:
    """Tests for check_manifest_consistency."""

    def test_matching(self) -> None:
        ft6 = _import_ft6()
        em = {
            "summary": {
                "total_obj_files": 10,
                "total_unique_asset_ids": 5,
            },
            "entries": [
                {"asset_id": "aa00000000000001"},
                {"asset_id": "bb00000000000002"},
            ],
        }
        sg = {
            "total_world_jsons": 2,
            "total_bytes": 1000,
            "entries": [
                {"asset_id": "aa00000000000001"},
                {"asset_id": "bb00000000000002"},
            ],
        }
        result = ft6.check_manifest_consistency(em, sg)
        assert result["ids_in_em_only"] == 0
        assert result["status"] == "pass"

    def test_gap(self) -> None:
        ft6 = _import_ft6()
        em = {
            "summary": {},
            "entries": [
                {"asset_id": "aa00000000000001"},
                {"asset_id": "bb00000000000002"},
            ],
        }
        sg = {
            "entries": [{"asset_id": "aa00000000000001"}],
        }
        result = ft6.check_manifest_consistency(em, sg)
        assert result["ids_in_em_only"] == 1
        assert result["status"] == "warn"
