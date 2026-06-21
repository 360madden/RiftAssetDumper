"""Tests for ``scripts/cycle4_lod_metadata.py`` \u2014 Cycle 4.1 LOD-aware closure.

Locks the v0.1 wire format:

  * ``classify_remaining()`` groups by mesh_size, ranks by vertex_count
    desc, detects singletons, falls back to absolute-vertex-count tier for
    assets with mesh_size=None.
  * ``patch_stage6_manifest()`` writes geometry.lod_index,
    geometry.lod_type, geometry.lod_tier_count_in_family; atomically
    replaces the manifest (no partial-write corruption).
  * ``render_markdown()`` includes tier + reason-class distribution.
  * Re-runs are idempotent.

Fixtures are pure-Python (no dotnet spawn).
"""

from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import jsonschema

ic4 = importlib.import_module("scripts.cycle4_lod_metadata")

SCENE_MANIFEST_SCHEMA = json.loads(
    Path("docs/schemas/scene-manifest-v1.schema.json").read_text(
        encoding="utf-8-sig"
    )
)


def _make_flythrough_entry(aid: str, vertex_count: int, mesh_size: int | None = None) -> dict:
    entry: dict = {
        "asset_id": aid,
        "vertex_count": vertex_count,
        "face_count": vertex_count - 2 if vertex_count > 4 else 0,
        "faced": vertex_count > 4,
        "mesh_block": "6",
        "descriptor": None,
    }
    if mesh_size is not None:
        entry["mesh_size"] = mesh_size
    return entry


class ClassifyByFamily(unittest.TestCase):
    """``classify_remaining()`` MeshSize-family vertex-rank path."""

    def test_high_density_family_ranks_descending(self) -> None:
        flythrough = {
            "00000000000000a1": _make_flythrough_entry("00000000000000a1", 100, mesh_size=405),
            "00000000000000a2": _make_flythrough_entry("00000000000000a2", 75, mesh_size=405),
            "00000000000000a3": _make_flythrough_entry("00000000000000a3", 50, mesh_size=405),
        }
        asset_lod_map: dict = {
            "00000000000000a0": {"lod_type": "meshsize-family"},
        }
        result = ic4.classify_remaining(flythrough, asset_lod_map)
        ranked = [(aid, result[aid]["lod_index"]) for aid in sorted(result)]
        self.assertEqual(ranked[0], ("00000000000000a1", 0))
        self.assertEqual(ranked[1], ("00000000000000a2", 1))
        self.assertEqual(ranked[2], ("00000000000000a3", 2))
        for _aid, meta in result.items():
            self.assertEqual(meta["family_size"], 3)
            self.assertEqual(meta["lod_type"], "high")


class SingletonDetection(unittest.TestCase):
    """family_size == 1 \u2192 lod_type='singleton'."""

    def test_singleton_with_mesh_size(self) -> None:
        flythrough = {
            "00000000000000b1": _make_flythrough_entry("00000000000000b1", 87, mesh_size=275),
        }
        result = ic4.classify_remaining(flythrough, {})
        self.assertEqual(set(result.keys()), {"00000000000000b1"})
        meta = result["00000000000000b1"]
        self.assertEqual(meta["lod_type"], "singleton")
        self.assertEqual(meta["family_size"], 1)
        self.assertEqual(meta["lod_index"], 0)


class AbsoluteTierFallback(unittest.TestCase):
    """mesh_size=None \u2192 absolute-vertex-count tier."""

    def test_high_tier_above_p80(self) -> None:
        vcs = [5, 10, 15, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200]
        flythrough = {}
        for i, vc in enumerate(vcs):
            aid = f"00000000000{i:05x}"
            flythrough[aid] = _make_flythrough_entry(aid, vc, mesh_size=None)
        result = ic4.classify_remaining(flythrough, {})
        # Top tier assets should map to "high"
        highest_aid = max(flythrough, key=lambda k: flythrough[k]["vertex_count"])
        self.assertEqual(result[highest_aid]["lod_type"], "high")
        # Lowest-vertex asset should map to "low"
        lowest_aid = min(flythrough, key=lambda k: flythrough[k]["vertex_count"])
        self.assertEqual(result[lowest_aid]["lod_type"], "low")


class PatchStage6Manifest(unittest.TestCase):
    """``patch_stage6_manifest()`` writes the v0.1 wire format."""

    def test_writes_geometry_lod_fields_and_producer_stamp(self) -> None:
        tmp = self._tmpd()
        stage6_dir = Path(tmp) / "stage6"
        stage6_dir.mkdir()
        manifest_path = stage6_dir / "manifest-000000000000aaa1.json"
        original = {
            "SchemaVersion": "scene-manifest/v1",
            "asset_id": "000000000000aaa1",
            "geometry": {"vertex_count": 100, "face_count": 98, "has_faces": True},
            "producer": {"tool": "build_scene_manifest.py", "version": "v0.8"},
            "validation": {"schema_valid": True, "consumer_ready": True},
        }
        manifest_path.write_text(json.dumps(original, indent=2), encoding="utf-8")

        lod_meta: dict[str, Any] = {"lod_index": 0, "lod_type": "singleton", "family_size": 1}
        with mock.patch.object(ic4, "REPO_ROOT", Path(tmp)), mock.patch.object(
            ic4, "STAGE6_DIR", stage6_dir
        ):
            ok, err = ic4.patch_stage6_manifest("000000000000aaa1", lod_meta)
        self.assertTrue(ok, f"unexpected error: {err}")
        patched = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(patched["geometry"]["lod_index"], 0)
        self.assertEqual(patched["geometry"]["lod_type"], "singleton")
        self.assertEqual(patched["geometry"]["lod_tier_count_in_family"], 1)
        self.assertIn("scripts/cycle4_lod_metadata.py", patched["producer"]["cycle4_producers"])
        self.assertEqual(patched["producer"]["cycle4_version"], "v0.1")
        # legacy root `last_updated_at` must NOT remain (schema cleanup)
        self.assertNotIn("last_updated_at", patched)
        # cycle4 timestamp tracking lives under producer.cycle4_last_applied
        self.assertIn("cycle4_last_applied", patched["producer"])

    def test_atomic_write_no_tmp_left_behind(self) -> None:
        tmp = self._tmpd()
        stage6_dir = Path(tmp) / "stage6"
        stage6_dir.mkdir()
        manifest_path = stage6_dir / "manifest-000000000000aaa2.json"
        original = {
            "SchemaVersion": "scene-manifest/v1",
            "asset_id": "000000000000aaa2",
            "geometry": {"vertex_count": 50, "face_count": 48, "has_faces": True},
            "producer": {"tool": "build_scene_manifest.py", "version": "v0.8"},
        }
        manifest_path.write_text(json.dumps(original, indent=2), encoding="utf-8")
        lod_meta: dict[str, Any] = {"lod_index": 0, "lod_type": "low", "family_size": 1}
        with mock.patch.object(ic4, "REPO_ROOT", Path(tmp)), mock.patch.object(
            ic4, "STAGE6_DIR", stage6_dir
        ):
            ic4.patch_stage6_manifest("000000000000aaa2", lod_meta)

        leftover = list(stage6_dir.glob("*.tmp"))
        self.assertEqual(leftover, [], f"tmp leak: {leftover}")

    def test_idempotent_second_run_preserves_producer_version(self) -> None:
        tmp = self._tmpd()
        stage6_dir = Path(tmp) / "stage6"
        stage6_dir.mkdir()
        manifest_path = stage6_dir / "manifest-000000000000aaa3.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "SchemaVersion": "scene-manifest/v1",
                    "asset_id": "000000000000aaa3",
                    "geometry": {"vertex_count": 50, "face_count": 48, "has_faces": True},
                    "producer": {"tool": "build_scene_manifest.py", "version": "v0.8"},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        lod_meta: dict[str, Any] = {"lod_index": 0, "lod_type": "medium", "family_size": 1}
        with mock.patch.object(ic4, "REPO_ROOT", Path(tmp)), mock.patch.object(
            ic4, "STAGE6_DIR", stage6_dir
        ):
            ic4.patch_stage6_manifest("000000000000aaa3", lod_meta)
            first = json.loads(manifest_path.read_text(encoding="utf-8"))
            ic4.patch_stage6_manifest("000000000000aaa3", lod_meta)
            second = json.loads(manifest_path.read_text(encoding="utf-8"))
        # No duplicate entries in cycle4_producers
        self.assertEqual(first["producer"]["cycle4_producers"].count("scripts/cycle4_lod_metadata.py"), 1)
        self.assertEqual(second["producer"]["cycle4_producers"].count("scripts/cycle4_lod_metadata.py"), 1)
        # Geometry fields stable
        self.assertEqual(first["geometry"]["lod_type"], second["geometry"]["lod_type"])

    def test_patched_manifest_validates_against_locked_schema(self) -> None:
        """The cycle4 patch output must validate against scene-manifest-v1 schema."""
        tmp = self._tmpd()
        stage6_dir = Path(tmp) / "stage6"
        stage6_dir.mkdir()
        manifest_path = stage6_dir / "manifest-000000000000aaa4.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "SchemaVersion": "scene-manifest/v1",
                    "asset_id": "000000000000aaa4",
                    "generated_at": "2026-06-20T00:00:00Z",
                    "geometry": {
                        "obj_path": "Assets/build/flythrough/objs/dummy.obj",
                        "vertex_count": 100,
                        "face_count": 98,
                        "has_faces": True,
                        "render_class": "faced",
                    },
                    "producer": {"tool": "build_scene_manifest.py", "version": "v0.8"},
                    "world": {
                        "world_json": "Assets/build/flythrough/objs/worlds/dummy.world.json",
                        "node_count": 1,
                        "mesh_count": 1,
                        "transform_semantics": "mesh-parent-chain",
                        "coordinate_system": {
                            "handedness": "right",
                            "up_axis": "Y",
                            "forward_axis": "-Z",
                            "translation_layout": "xyz",
                            "rotation_layout": "row-major-3x3",
                            "scale_layout": "uniform-float",
                            "trs_composition": "v_world = R * (S * v_local) + T",
                            "identity_tolerance": 1e-6,
                        },
                        "world_transform_summary": {
                            "translation": [0, 0, 0],
                            "rotation": [1, 0, 0, 0, 1, 0, 0, 0, 1],
                            "scale": 1,
                        },
                        "world_transform_identity": True,
                    },
                    "materials": {
                        "material_status": "textured",
                        "texture_property_count": 1,
                        "material_property_count": 0,
                        "vertex_color_property_count": 0,
                        "notes": [],
                    },
                    "textures": {
                        "source": "scene",
                        "linked_texture_count": 1,
                        "linked_textures": ["textures/converted/dummy.png"],
                        "missing_texture_count": 0,
                        "placeholder_texture_count": 0,
                    },
                    "provenance": {
                        "cohort": "core-flythrough",
                        "source_nif_hash": "000000000000aaa4",
                        "flythrough_index_entry": "000000000000aaa4",
                        "evidence_files": [],
                    },
                    "validation": {
                        "schema_valid": True,
                        "consumer_ready": True,
                        "warnings": [],
                        "errors": [],
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        lod_meta: dict[str, Any] = {
            "lod_index": 0,
            "lod_type": "singleton",
            "family_size": 1,
        }
        with mock.patch.object(ic4, "REPO_ROOT", Path(tmp)), mock.patch.object(
            ic4, "STAGE6_DIR", stage6_dir
        ):
            ok, err = ic4.patch_stage6_manifest("000000000000aaa4", lod_meta)
        self.assertTrue(ok, f"unexpected patch error: {err}")
        patched = json.loads(manifest_path.read_text(encoding="utf-8"))
        # Hard guarantee: the patched manifest validates against the locked schema.
        jsonschema.validate(patched, SCENE_MANIFEST_SCHEMA)

    @staticmethod
    def _tmpd() -> str:
        return tempfile.mkdtemp(prefix="cycle4-")


class MarkdownRender(unittest.TestCase):
    """``render_markdown()`` includes tier + reason distributions."""

    def test_markdown_includes_tier_table_and_reason_table(self) -> None:
        evidence = {
            "SchemaVersion": "cycle4-lod-metadata/v1",
            "generated_at": "2026-06-21T00:00:00Z",
            "producer": {"tool": "scripts/cycle4_lod_metadata.py", "version": "v0.1"},
            "summary": {
                "flythrough_total": 227,
                "previously_classified": 193,
                "newly_classified": 34,
                "patched_ok": 34,
                "patched_failed": 0,
                "by_tier": {"high": 5, "medium": 20, "low": 9},
                "by_reason_class": {"mesh": 25, "singleton": 4, "absolute": 5},
            },
            "previously_classified_assets": [],
            "newly_classified": [],
            "patch_failures": [],
        }
        md = ic4.render_markdown(evidence)
        self.assertIn("Cycle 4.1", md)
        self.assertIn("| high | 5 |", md)
        self.assertIn("| medium | 20 |", md)
        self.assertIn("| low | 9 |", md)
        self.assertIn("| mesh | 25 |", md)
        self.assertIn("| singleton | 4 |", md)
        self.assertIn("| absolute | 5 |", md)
        self.assertIn("227", md)


if __name__ == "__main__":
    unittest.main()
