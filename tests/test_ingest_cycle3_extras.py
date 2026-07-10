"""Tests for ``scripts/ingest_cycle3_extras.py`` — idempotency contract locks.

Locks in the v0.2 wire contract after the silent-overwrite bug fix:

  * ``materialize(..., dry_run=True)`` MUST NOT write any OBJ / sidecar.
  * First-run ingestion creates a flythrough-index entry with enrichment
    fields set to ``None`` / ``[]`` (downstream pipeline fills them).
  * Self re-run (same ``source``) refreshes geometry only; preserves any
    sentinel ``linked_textures`` / ``world_json`` / ``mesh_size`` values.
  * External-source re-run (different ``source``) pushes the Cycle-3 mesh
    block into ``extra_blocks``; does NOT touch geometry or enrichment.
  * Extras are written with zero-padded ``mb{nnn}.obj`` (sort-stable).

Fixtures are pure-Python (no ``dotnet`` spawn); tmp paths isolate filesystem
state from the real flythrough pipeline.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

import scripts.ingest_cycle3_extras as ic3


def _fake_record(asset_id: str, mesh_block: int, v: int, f: int, src: Path, *, size: int = 1024) -> ic3.ObjRecord:
    return ic3.ObjRecord(
        asset_id=asset_id,
        src_path=src,
        mesh_block=mesh_block,
        vertex_count=v,
        face_count=f,
        obj_bytes=size,
        obj_sha1="0" * 40,
    )


def _write_minimal_obj(path: Path, v_count: int, f_count: int) -> None:
    """Write a tiny OBJ with the requested vertex + face counts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# minimal OBJ for testing", f"o test_{path.stem}"]
    for i in range(1, v_count + 1):
        lines.append(f"v {i}.0 {i}.0 {i}.0")
    for _i in range(f_count):
        lines.append("f 1 1 1")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class DryRunWritesNothing(unittest.TestCase):
    """``materialize(..., dry_run=True)`` MUST NOT touch the filesystem."""

    def test_dry_run_creates_no_files(self) -> None:
        tmp_root = Path(self._tmpd())
        probe_root = tmp_root / "probe"
        obj_root = tmp_root / "objs"
        extras_dir = obj_root / "extra"

        src = probe_root / "03bcfae6561407a1" / "decode-nif-geometry" / "decode-nif-geometry-mesh6.obj"
        _write_minimal_obj(src, v_count=4, f_count=2)
        record = _fake_record("03bcfae6561407a1", mesh_block=6, v=4, f=2, src=src)

        with (
            mock.patch.object(ic3, "REPO_ROOT", tmp_root),
            mock.patch.object(ic3, "PROBE_DIRS", [probe_root]),
            mock.patch.object(ic3, "OBJ_DIR", obj_root),
            mock.patch.object(ic3, "EXTRAS_DIR", extras_dir),
        ):
            summary = ic3.materialize([record], dry_run=True)

        # Sanity: summary records what *would* be written
        self.assertEqual(len(summary["canonical"]), 1)
        self.assertEqual(len(summary["extras"]), 0)

        # Critical: filesystem is untouched
        self.assertFalse(obj_root.exists(), "OBJ_DIR must not be created in dry-run")
        self.assertFalse(extras_dir.exists(), "EXTRAS_DIR must not be created in dry-run")

    _tmpd = staticmethod(lambda: str(__import__("tempfile").mkdtemp(prefix="ic3-dryrun-")))


class AssetIdResolution(unittest.TestCase):
    """The 3-layer asset-ID resolution is the most failure-prone layer."""

    def test_explicit_dir_map_lighthouse(self) -> None:
        """lighthouse ``mb<N>`` must resolve to b89ced7d511388d2 via layer 1."""
        tmp_root = Path(self._tmpd())
        probe_root = tmp_root / "mesh321-probe"
        probe_root.mkdir(parents=True)
        obj_dir = tmp_root / "objs"
        src = probe_root / "mb11" / "decode-nif-geometry" / "decode-nif-geometry-mesh11.obj"
        _write_minimal_obj(src, v_count=10, f_count=8)

        with (
            mock.patch.object(ic3, "REPO_ROOT", tmp_root),
            mock.patch.object(ic3, "PROBE_DIRS", [probe_root]),
            mock.patch.object(ic3, "OBJ_DIR", obj_dir),
            mock.patch.object(ic3, "EXTRAS_DIR", obj_dir / "extra"),
        ):
            records = ic3.discover_records()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].asset_id, "b89ced7d511388d2")
        self.assertEqual(records[0].mesh_block, 11)

    def test_truncated_prefix_8char(self) -> None:
        """``9f32d2`` truncated prefix must resolve to 9f32d26c425ed264."""
        tmp_root = Path(self._tmpd())
        probe_root = tmp_root / "mesh297-probe"
        probe_root.mkdir(parents=True)
        obj_dir = tmp_root / "objs"
        # Build a tree that exercises layer 3 (no 16-hex parent, no explicit hit)
        src = probe_root / "9f32d2" / "mb27" / "decode-nif-geometry" / "decode-nif-geometry-mesh27.obj"
        _write_minimal_obj(src, v_count=20, f_count=18)

        with (
            mock.patch.object(ic3, "REPO_ROOT", tmp_root),
            mock.patch.object(ic3, "PROBE_DIRS", [probe_root]),
            mock.patch.object(ic3, "OBJ_DIR", obj_dir),
            mock.patch.object(ic3, "EXTRAS_DIR", obj_dir / "extra"),
        ):
            records = ic3.discover_records()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].asset_id, "9f32d26c425ed264")
        self.assertEqual(records[0].mesh_block, 27)

    _tmpd = staticmethod(lambda: str(__import__("tempfile").mkdtemp(prefix="ic3-resolve-")))


class ExtrasAccumulateAdd(unittest.TestCase):
    """`extra_blocks` must accumulate — never replace or drop prior entries."""

    def test_external_rerun_appends_not_replaces(self) -> None:
        tmp = Path(self._tmpd())
        idx_path = tmp / "flythrough-index.json"
        idx_path.write_text(
            json.dumps(
                {
                    "SchemaVersion": "x",
                    "assets": {
                        "03bcfae6561407a1": {
                            "asset_id": "03bcfae6561407a1",
                            "obj_path": "03bcfae6561407a1.obj",
                            "mesh_block": 6,
                            "vertex_count": 4,
                            "face_count": 2,
                            "faced": True,
                            "linked_textures": ["p.png"],
                            "world_json": "p.world.json",
                            "mesh_size": 297,
                            "extra_blocks": [
                                {
                                    "obj_path": "extra/a__mb001.obj",
                                    "mesh_block": 1,
                                    "vertex_count": 10,
                                    "face_count": 9,
                                    "obj_sha1": "1" * 40,
                                    "source": "prior",
                                },
                                {
                                    "obj_path": "extra/a__mb002.obj",
                                    "mesh_block": 2,
                                    "vertex_count": 20,
                                    "face_count": 19,
                                    "obj_sha1": "2" * 40,
                                    "source": "prior",
                                },
                            ],
                            "source": "bulk_export_for_flythrough",
                        },
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        summary = {
            "canonical": [
                {
                    "asset_id": "03bcfae6561407a1",
                    "dst": "03bcfae6561407a1.obj",
                    "mesh_block": 27,
                    "vertex_count": 100,
                    "face_count": 99,
                    "obj_sha1": "3" * 40,
                }
            ],
            "extras": [],
            "skipped": [],
        }

        with mock.patch.object(ic3, "FLYTHROUGH_INDEX", idx_path):
            ic3.update_flythrough_index(summary, dry_run=False)

        entry = json.loads(idx_path.read_text(encoding="utf-8"))["assets"]["03bcfae6561407a1"]
        # Two prior + one new = three extras
        self.assertEqual(len(entry["extra_blocks"]), 3)
        self.assertEqual(entry["extra_blocks"][-1]["source"], "ingest-cycle3-extras")
        # Geometry still NOT touched
        self.assertEqual(entry["mesh_block"], 6)
        self.assertEqual(entry["mesh_size"], 297)

    _tmpd = staticmethod(lambda: str(__import__("tempfile").mkdtemp(prefix="ic3-acc-")))


class NewEntrySeedsEnrichmentAsEmpty(unittest.TestCase):
    """First-run ingestion creates enrichment fields as None/[]."""

    def test_new_entry_enrichment_empty(self) -> None:
        tmp = Path(self._tmpd())
        idx_path = tmp / "flythrough-index.json"
        idx_path.write_text(json.dumps({"SchemaVersion": "x", "assets": {}}, indent=2), encoding="utf-8")

        summary = {
            "canonical": [
                {
                    "asset_id": "03bcfae6561407a1",
                    "dst": "03bcfae6561407a1.obj",
                    "mesh_block": 6,
                    "vertex_count": 4,
                    "face_count": 2,
                    "obj_sha1": "0" * 40,
                }
            ],
            "extras": [],
            "skipped": [],
        }

        with mock.patch.object(ic3, "FLYTHROUGH_INDEX", idx_path):
            rc = ic3.update_flythrough_index(summary, dry_run=False)
        self.assertEqual(rc, 0)

        idx = json.loads(idx_path.read_text(encoding="utf-8"))
        entry = idx["assets"]["03bcfae6561407a1"]
        self.assertEqual(entry["linked_textures"], [])
        self.assertEqual(entry["extra_blocks"], [])
        self.assertIsNone(entry["world_json"])
        self.assertIsNone(entry["mesh_size"])
        self.assertEqual(entry["source"], "ingest-cycle3-extras")

    _tmpd = staticmethod(lambda: str(__import__("tempfile").mkdtemp(prefix="ic3-new-")))


class OwnRerunPreservesEnrichment(unittest.TestCase):
    """Self re-run (source == ingest-cycle3-extras) preserves enrichment."""

    def test_own_rerun_keeps_linked_textures(self) -> None:
        tmp = Path(self._tmpd())
        idx_path = tmp / "flythrough-index.json"

        # Pre-populate entry with sentinel enrichment (post-tex-link / scene-graph)
        sentinel_textures = ["sentinel_texture_a.png", "sentinel_texture_b.png"]
        sentinel_world = "sentinel_world.json"
        sentinel_mesh_size = 305
        idx_path.write_text(
            json.dumps(
                {
                    "SchemaVersion": "x",
                    "assets": {
                        "03bcfae6561407a1": {
                            "asset_id": "03bcfae6561407a1",
                            "obj_path": "03bcfae6561407a1.obj",
                            "mesh_block": 6,
                            "vertex_count": 4,
                            "face_count": 2,
                            "faced": True,
                            "linked_textures": list(sentinel_textures),
                            "world_json": sentinel_world,
                            "mesh_size": sentinel_mesh_size,
                            "extra_blocks": [],
                            "source": "ingest-cycle3-extras",
                        },
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        # Re-run with fresh counts (different vertex_count)
        summary = {
            "canonical": [
                {
                    "asset_id": "03bcfae6561407a1",
                    "dst": "03bcfae6561407a1.obj",
                    "mesh_block": 7,
                    "vertex_count": 999,
                    "face_count": 998,
                    "obj_sha1": "f" * 40,
                }
            ],
            "extras": [],
            "skipped": [],
        }

        with mock.patch.object(ic3, "FLYTHROUGH_INDEX", idx_path):
            rc = ic3.update_flythrough_index(summary, dry_run=False)
        self.assertEqual(rc, 0)

        entry = json.loads(idx_path.read_text(encoding="utf-8"))["assets"]["03bcfae6561407a1"]
        # Geometry refreshed
        self.assertEqual(entry["vertex_count"], 999)
        self.assertEqual(entry["face_count"], 998)
        self.assertEqual(entry["mesh_block"], 7)
        # Enrichment PRESERVED (the whole point of the fix)
        self.assertEqual(entry["linked_textures"], sentinel_textures)
        self.assertEqual(entry["world_json"], sentinel_world)
        self.assertEqual(entry["mesh_size"], sentinel_mesh_size)
        self.assertEqual(entry["source"], "ingest-cycle3-extras")

    _tmpd = staticmethod(lambda: str(__import__("tempfile").mkdtemp(prefix="ic3-rerun-")))


class ExternalSourcePushesToExtras(unittest.TestCase):
    """Asset owned by another ingestion path: Cycle-3 block goes to extra_blocks."""

    def test_external_rerun_appends_extra_blocks(self) -> None:
        tmp = Path(self._tmpd())
        idx_path = tmp / "flythrough-index.json"
        idx_path.write_text(
            json.dumps(
                {
                    "SchemaVersion": "x",
                    "assets": {
                        "09f32d26c425ed264": {
                            "asset_id": "09f32d26c425ed264",
                            "obj_path": "09f32d26c425ed264.obj",
                            "mesh_block": 27,
                            "vertex_count": 12993,
                            "face_count": 12991,
                            "faced": True,
                            "linked_textures": ["prior.png"],
                            "world_json": "prior.world.json",
                            "mesh_size": 297,
                            "extra_blocks": [],
                            "source": "bulk_export_for_flythrough",
                        },
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        summary = {
            "canonical": [
                {
                    "asset_id": "09f32d26c425ed264",
                    "dst": "09f32d26c425ed264.obj",
                    "mesh_block": 27,
                    "vertex_count": 12993,
                    "face_count": 12991,
                    "obj_sha1": "9" * 40,
                }
            ],
            "extras": [],
            "skipped": [],
        }

        with mock.patch.object(ic3, "FLYTHROUGH_INDEX", idx_path):
            rc = ic3.update_flythrough_index(summary, dry_run=False)
        self.assertEqual(rc, 0)

        entry = json.loads(idx_path.read_text(encoding="utf-8"))["assets"]["09f32d26c425ed264"]
        # Geometry NOT touched
        self.assertEqual(entry["vertex_count"], 12993)
        self.assertEqual(entry["mesh_block"], 27)
        self.assertEqual(entry["source"], "bulk_export_for_flythrough")
        # Enrichment NOT touched
        self.assertEqual(entry["linked_textures"], ["prior.png"])
        self.assertEqual(entry["world_json"], "prior.world.json")
        self.assertEqual(entry["mesh_size"], 297)
        # But extra_blocks has the cycle-3 mesh
        self.assertEqual(len(entry["extra_blocks"]), 1)
        eb = entry["extra_blocks"][0]
        self.assertEqual(eb["mesh_block"], 27)
        self.assertEqual(eb["obj_path"], "extra/09f32d26c425ed264__mb027.obj")  # zero-padded
        self.assertEqual(eb["source"], "ingest-cycle3-extras")

    _tmpd = staticmethod(lambda: str(__import__("tempfile").mkdtemp(prefix="ic3-ext-")))


if __name__ == "__main__":
    unittest.main()
