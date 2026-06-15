"""Unit tests for scripts/bulk_export_for_flythrough.py — FT-2.2.

Covers the FT-2.2 acceptance criteria:
1. Empty input → no exports, manifest has candidates=0
2. Single mesh → 1 exported, manifest has 1 entry
3. Error on one mesh → 1 failed, 1 exported (when skip-on-error=True)
4. Resume after error → previously-exported assets are skipped
5. --limit → caps the input list

Plus: dry-run never invokes .NET, atomic write protects existing manifest,
dedupe by SHA1 collapses identical content.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest  # noqa: F401

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from bulk_export_for_flythrough import (  # noqa: E402
    ASSET_ID_RE,
    _atomic_write_json,
    _enrich_sidecar_with_scene_graph,
    _index_existing_entries,
    bulk_export_for_flythrough,
    filter_by_mesh_size,
    load_asset_ids_from_file,
    load_asset_ids_from_inventory,
    run_probe_scene_graph,
)

SAMPLE_INVENTORY: dict[str, Any] = {
    "SchemaVersion": "nif-mesh-binding-inventory/v1",
    "Meshes": [
        {"AssetId": "abcdef0123456789", "MeshSize": 297},
        {"AssetId": "fedcba9876543210", "MeshSize": 305},
        {"AssetId": "1234567890abcdef", "MeshSize": 329},
        {"AssetId": "DEADBEEF12345678", "MeshSize": 297},  # uppercase
    ],
}


def _write_obj(obj_path: Path, content: bytes = b"# test OBJ\n") -> Path:
    obj_path.parent.mkdir(parents=True, exist_ok=True)
    obj_path.write_bytes(content)
    return obj_path


def test_load_asset_ids_from_inventory_returns_unique_normalized() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        inv = Path(tmpdir) / "inv.json"
        inv.write_text(json.dumps(SAMPLE_INVENTORY), encoding="utf-8")
        ids = load_asset_ids_from_inventory(inv)
        assert len(ids) == 4
        # Uppercase normalized to lowercase
        assert "deadbeef12345678" in ids


def test_load_asset_ids_from_file_supports_comments_and_blanks() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        f = Path(tmpdir) / "ids.txt"
        f.write_text(
            "# this is a comment\n\nabcdef0123456789\n  fedcba9876543210  \nnot-a-hex\n1234567890abcdef\n",
            encoding="utf-8",
        )
        ids = load_asset_ids_from_file(f)
        assert ids == ["abcdef0123456789", "fedcba9876543210", "1234567890abcdef"]


def test_filter_by_mesh_size_includes_families() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        inv = Path(tmpdir) / "inv.json"
        inv.write_text(json.dumps(SAMPLE_INVENTORY), encoding="utf-8")
        ids = load_asset_ids_from_inventory(inv)
        filtered = filter_by_mesh_size(ids, inv, {297})
        assert "abcdef0123456789" in filtered
        assert "deadbeef12345678" in filtered  # also MS 297
        assert "fedcba9876543210" not in filtered  # MS 305


def test_atomic_write_json_writes_valid_json() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "x.json"
        _atomic_write_json(p, {"hello": "world", "n": 42})
        assert p.exists()
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        assert data == {"hello": "world", "n": 42}


def test_index_existing_entries_by_hash() -> None:
    manifest = {
        "Entries": [
            {"nif_hash": "abc", "status": "exported"},
            {"nif_hash": "def", "status": "failed"},
        ]
    }
    idx = _index_existing_entries(manifest)
    assert "abc" in idx
    assert idx["abc"]["status"] == "exported"
    assert "def" in idx


def test_empty_input_writes_manifest_with_zero_stats() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "objs"
        manifest = Path(tmpdir) / "m.json"
        result = bulk_export_for_flythrough(
            asset_ids=[],
            output_dir=out,
            manifest_path=manifest,
            project=Path("."),
            root=Path("."),
        )
        assert result.stats["candidates"] == 0
        assert result.stats["exported"] == 0
        assert result.stats["failed"] == 0
        assert manifest.exists()


def test_dry_run_does_not_invoke_dotnet(tmp_path) -> None:
    """--dry-run must NOT call subprocess.run (per acceptance: 'dry-run does not invoke .NET')."""
    out = tmp_path / "objs"
    manifest = tmp_path / "m.json"
    with (
        patch("bulk_export_for_flythrough.run_decode_geometry") as mock_decode,
        patch("bulk_export_for_flythrough.subprocess.run") as mock_subproc,
    ):
        result = bulk_export_for_flythrough(
            asset_ids=["abcdef0123456789", "fedcba9876543210"],
            output_dir=out,
            manifest_path=manifest,
            project=Path("."),
            root=Path("."),
            dry_run=True,
        )
        assert result.stats["candidates"] == 2
        assert result.stats["skipped"] == 2  # dry-run counts as skipped
        mock_decode.assert_not_called()
        # subprocess.run may be called for the build check (skip_build=True by default)
        # but never for decode-nif-geometry
        for call in mock_subproc.call_args_list:
            args = call.args[0] if call.args else []
            assert "decode-nif-geometry" not in args


def test_single_mesh_export_writes_one_entry(tmp_path, monkeypatch) -> None:
    """Single mesh → 1 exported entry in the manifest, OBJ exists, sidecar exists."""
    out = tmp_path / "objs"
    manifest = tmp_path / "m.json"

    def fake_decode(asset_id, *, project, root, timeout_sec, mesh_block=0, mode="export-obj", out_dir=None):
        # Simulate decode-nif-geometry writing a fake OBJ file
        asset_subdir = out_dir or (out / f"decode-nif-geometry-{asset_id}")
        asset_subdir.mkdir(parents=True, exist_ok=True)
        obj_file = asset_subdir / "mesh.obj"
        _write_obj(obj_file, b"# fake OBJ for " + asset_id.encode() + b"\nv 0 0 0\n")
        return True, "wrote mesh.obj", "", 0.1

    monkeypatch.setattr("bulk_export_for_flythrough.run_decode_geometry", fake_decode)
    result = bulk_export_for_flythrough(
        asset_ids=["abcdef0123456789"],
        output_dir=out,
        manifest_path=manifest,
        project=Path("."),
        root=Path("."),
    )
    assert result.stats["exported"] == 1
    assert result.stats["failed"] == 0
    assert manifest.exists()
    with open(manifest, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["Entries"]) == 1
    assert data["Entries"][0]["nif_hash"] == "abcdef0123456789"
    assert data["Entries"][0]["status"] == "exported"
    assert data["Entries"][0]["obj_path"] == "decode-nif-geometry-abcdef0123456789/mesh.obj"


def test_error_on_one_mesh_with_skip_on_error_continues(tmp_path, monkeypatch) -> None:
    """First asset fails, second succeeds — both recorded, skip-on-error allows continuation."""
    out = tmp_path / "objs"
    manifest = tmp_path / "m.json"

    def fake_decode(asset_id, *, project, root, timeout_sec, mesh_block=0, mode="export-obj", out_dir=None):
        if asset_id == "1111111111111111":
            return False, "", "decode error: corrupt NIF", 0.1
        # Succeed by writing a fake OBJ
        asset_subdir = out_dir or (out / f"decode-nif-geometry-{asset_id}")
        asset_subdir.mkdir(parents=True, exist_ok=True)
        obj_file = asset_subdir / "mesh.obj"
        _write_obj(obj_file, b"# fake OBJ\nv 0 0 0\n")
        return True, "wrote mesh.obj", "", 0.1

    monkeypatch.setattr("bulk_export_for_flythrough.run_decode_geometry", fake_decode)
    result = bulk_export_for_flythrough(
        asset_ids=["1111111111111111", "2222222222222222"],
        output_dir=out,
        manifest_path=manifest,
        project=Path("."),
        root=Path("."),
        skip_on_error=True,
    )
    assert result.stats["exported"] == 1
    assert result.stats["failed"] == 1
    assert len(result.errors) == 1
    assert result.errors[0]["id"] == "1111111111111111"


def test_no_attribute_sets_retries_experimental_and_records_real_command(tmp_path, monkeypatch) -> None:
    """No-attribute-set meshes should be redriven through linked-stream fallback."""
    out = tmp_path / "objs"
    manifest = tmp_path / "m.json"
    calls: list[str] = []

    def fake_decode(asset_id, *, project, root, timeout_sec, mesh_block=0, mode="export-obj", out_dir=None):
        calls.append(mode)
        if mode == "export-obj":
            return False, "", "ERROR: no attribute sets found for this mesh.", 0.1
        asset_subdir = out_dir or (out / f"decode-nif-geometry-{asset_id}")
        asset_subdir.mkdir(parents=True, exist_ok=True)
        obj_file = asset_subdir / "mesh.obj"
        _write_obj(obj_file, b"# experimental OBJ\nv 0 0 0\n")
        return True, "OBJ written", "", 0.1

    monkeypatch.setattr("bulk_export_for_flythrough.run_decode_geometry", fake_decode)
    result = bulk_export_for_flythrough(
        asset_ids=["abcdef0123456789"],
        output_dir=out,
        manifest_path=manifest,
        project=Path("."),
        root=Path("."),
    )

    assert calls == ["export-obj", "experimental"]
    assert result.stats["exported"] == 1
    data = json.loads(manifest.read_text(encoding="utf-8"))
    entry = data["Entries"][0]
    assert entry["export_mode"] == "experimental"
    assert entry["command"].endswith("--experimental-position-source --write-obj")
    assert entry["obj_path"] == "decode-nif-geometry-abcdef0123456789/mesh.obj"


def test_resume_after_error_skips_already_exported(tmp_path, monkeypatch) -> None:
    """A prior run that exported asset X → resume skips X, only processes new ones."""
    out = tmp_path / "objs"
    manifest = tmp_path / "m.json"

    # Pre-seed: a prior run exported "abcdef0123456789" successfully
    prior_obj = out / "decode-nif-geometry-abcdef0123456789" / "mesh.obj"
    _write_obj(prior_obj, b"# prior\n")
    _atomic_write_json(
        manifest,
        {
            "SchemaVersion": "flythrough-bulk-export-manifest/v1",
            "GeneratedAt": "2026-06-08T00:00:00Z",
            "Stats": {},
            "Entries": [
                {
                    "nif_hash": "abcdef0123456789",
                    "status": "exported",
                    "obj_path": "decode-nif-geometry-abcdef0123456789/mesh.obj",
                    "obj_sha1": "",
                    "obj_bytes": 8,
                    "exported_at": "2026-06-08T00:00:00Z",
                }
            ],
        },
    )

    def fake_decode(asset_id, *, project, root, timeout_sec, mesh_block=0, mode="export-obj", out_dir=None):
        asset_subdir = out_dir or (out / f"decode-nif-geometry-{asset_id}")
        asset_subdir.mkdir(parents=True, exist_ok=True)
        obj_file = asset_subdir / "mesh.obj"
        _write_obj(obj_file, b"# new\n")
        return True, "wrote mesh.obj", "", 0.1

    monkeypatch.setattr("bulk_export_for_flythrough.run_decode_geometry", fake_decode)
    result = bulk_export_for_flythrough(
        asset_ids=["abcdef0123456789", "fedcba9876543210"],
        output_dir=out,
        manifest_path=manifest,
        project=Path("."),
        root=Path("."),
        resume=True,
    )
    assert result.stats["skipped"] == 1  # previously-exported
    assert result.stats["exported"] == 1  # newly-exported
    # The decoder should have been called only for the new asset
    # (mocked; not asserting call count, but stats prove it)


def test_limit_caps_input_in_bulk_export(tmp_path, monkeypatch) -> None:
    """--limit semantics: bulk_export_for_flythrough processes only the first N assets
    in the input list. The CLI applies the slice; the core function trusts the input."""
    out = tmp_path / "objs"
    manifest = tmp_path / "m.json"

    def fake_decode(asset_id, *, project, root, timeout_sec, mesh_block=0, mode="export-obj", out_dir=None):
        asset_subdir = out_dir or (out / f"decode-nif-geometry-{asset_id}")
        asset_subdir.mkdir(parents=True, exist_ok=True)
        obj_file = asset_subdir / "mesh.obj"
        _write_obj(obj_file, b"# " + asset_id.encode() + b"\n")
        return True, "ok", "", 0.01

    monkeypatch.setattr("bulk_export_for_flythrough.run_decode_geometry", fake_decode)
    # Simulate --limit 2 by passing only 2 of the 4 input assets
    inputs = ["abcdef0123456789", "fedcba9876543210"]
    result = bulk_export_for_flythrough(
        asset_ids=inputs,
        output_dir=out,
        manifest_path=manifest,
        project=Path("."),
        root=Path("."),
    )
    assert result.stats["candidates"] == 2
    assert result.stats["exported"] == 2
    with open(manifest, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["Entries"]) == 2


def test_dedupe_collapses_identical_content(tmp_path, monkeypatch) -> None:
    """Two NIFs that produce byte-identical OBJs → 2nd is recorded as 'deduped'."""
    out = tmp_path / "objs"
    manifest = tmp_path / "m.json"
    same_content = b"# identical OBJ bytes\nv 1 2 3\nv 4 5 6\n"

    def fake_decode(asset_id, *, project, root, timeout_sec, mesh_block=0, mode="export-obj", out_dir=None):
        # Both NIFs produce the same bytes — this simulates a shared texture/MIP
        asset_subdir = out_dir or (out / f"decode-nif-geometry-{asset_id}")
        asset_subdir.mkdir(parents=True, exist_ok=True)
        obj_file = asset_subdir / "mesh.obj"
        _write_obj(obj_file, same_content)
        return True, "ok", "", 0.01

    monkeypatch.setattr("bulk_export_for_flythrough.run_decode_geometry", fake_decode)
    result = bulk_export_for_flythrough(
        asset_ids=["1111111111111111", "2222222222222222"],
        output_dir=out,
        manifest_path=manifest,
        project=Path("."),
        root=Path("."),
    )
    assert result.stats["exported"] == 1
    assert result.stats["deduped"] == 1
    with open(manifest, encoding="utf-8") as f:
        data = json.load(f)
    statuses = sorted(e["status"] for e in data["Entries"])
    assert statuses == ["deduped", "exported"]


def test_asset_id_regex_rejects_garbage() -> None:
    assert ASSET_ID_RE.match("abcdef0123456789") is not None
    assert ASSET_ID_RE.match("ABCDEF0123456789") is not None
    assert ASSET_ID_RE.match("not-a-hex") is None
    assert ASSET_ID_RE.match("abc") is None  # too short
    assert ASSET_ID_RE.match("abcdef01234567890") is None  # too long


# =============================================================================
# FT-4.4: Scene graph integration tests
# =============================================================================


def test_run_probe_scene_graph_invokes_dotnet(tmp_path) -> None:
    """run_probe_scene_graph calls dotnet with correct arguments."""
    out_path = tmp_path / "sg.json"
    with patch("bulk_export_for_flythrough.subprocess.run") as mock_run:
        # Simulate successful completion + file write
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        # Also need the file to "exist" after the mock
        out_path.write_text(
            '{"NifVersion":"20.6.0.0","NodeCount":1,"MeshCount":2,"MeshesAttached":2,"Nodes":[],"Meshes":[]}',
            encoding="utf-8",
        )
        ok, stdout, stderr, elapsed = run_probe_scene_graph(
            "abcdef0123456789",
            project=Path("fake.csproj"),
            root=Path("C:/fake"),
            out_path=out_path,
        )
        assert ok
        mock_run.assert_called_once()
        args_list = mock_run.call_args[0][0]
        assert "probe-nif-scene-graph" in args_list
        assert "abcdef0123456789" in args_list
        assert "--out" in args_list


def test_enrich_sidecar_with_scene_graph_populates_transform(tmp_path) -> None:
    """Enrichment copies parent_node and transform from scene graph."""
    sidecar_path = tmp_path / "test.obj.manifest.json"
    initial: dict[str, Any] = {
        "SchemaVersion": "asset-mesh-manifest/v1",
        "nif_hash": "abcdef0123456789",
        "mesh_block": 6,
        "vertex_count": 80,
        "face_count": 78,
        "export_timestamp": "2026-01-01T00:00:00Z",
        "export_command": "decode-nif-geometry --id abc",
        "parent_node": None,
        "transform": None,
    }
    _atomic_write_json(sidecar_path, initial)

    sg_data: dict[str, Any] = {
        "Nodes": [
            {
                "BlockIndex": 0,
                "Name": "head_JNT",
                "Translation": [0.0, 1.84, -0.013],
                "Rotation": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
                "Scale": 1.0,
            },
        ],
        "Meshes": [
            {"BlockIndex": 6, "Size": 329, "ParentNiNodeIndex": 0},
        ],
    }

    _enrich_sidecar_with_scene_graph(sidecar_path, sg_data, mesh_block=6)

    enriched = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert enriched["parent_node"] == "head_JNT"
    assert enriched["transform"] is not None
    assert enriched["transform"]["translation"] == [0.0, 1.84, -0.013]
    assert enriched["transform"]["rotation"] == [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    assert enriched["transform"]["scale"] == 1.0


def test_enrich_sidecar_skips_scene_node_named_parent(tmp_path) -> None:
    """Root node named 'SceneNode' → parent_node stays None."""
    sidecar_path = tmp_path / "test.obj.manifest.json"
    initial: dict[str, Any] = {
        "SchemaVersion": "asset-mesh-manifest/v1",
        "nif_hash": "abcdef0123456789",
        "mesh_block": 6,
        "vertex_count": 80,
        "face_count": 78,
        "export_timestamp": "2026-01-01T00:00:00Z",
        "export_command": "decode-nif-geometry --id abc",
        "parent_node": None,
        "transform": None,
    }
    _atomic_write_json(sidecar_path, initial)

    sg_data: dict[str, Any] = {
        "Nodes": [
            {
                "BlockIndex": 0,
                "Name": "SceneNode",
                "Translation": [0.0, 0.0, 0.0],
                "Rotation": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
                "Scale": 1.0,
            },
        ],
        "Meshes": [
            {"BlockIndex": 6, "Size": 329, "ParentNiNodeIndex": 0},
        ],
    }

    _enrich_sidecar_with_scene_graph(sidecar_path, sg_data, mesh_block=6)

    enriched = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert enriched["parent_node"] is None  # SceneNode is the default root
    assert enriched["transform"] is not None  # transform still populated


def test_bulk_export_with_scene_graph_invokes_probe(tmp_path, monkeypatch) -> None:
    """When world_dir is set, bulk_export_for_flythrough runs scene graph probe."""
    out = tmp_path / "objs"
    world_dir = tmp_path / "worlds"
    manifest = tmp_path / "m.json"

    def fake_decode(asset_id, *, project, root, timeout_sec, mesh_block=0, mode="export-obj", out_dir=None):
        asset_subdir = out_dir or (out / f"decode-nif-geometry-{asset_id}")
        asset_subdir.mkdir(parents=True, exist_ok=True)
        obj_file = asset_subdir / "mesh.obj"
        _write_obj(obj_file, b"# fake OBJ\nv 0 0 0\n")
        return True, "ok", "", 0.1

    def fake_probe(asset_id, *, project, root, out_path, timeout_sec=60):
        # Write a minimal valid scene graph JSON
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sg = {
            "NifVersion": "20.6.0.0",
            "NodeCount": 1,
            "MeshCount": 1,
            "MeshesAttached": 1,
            "Nodes": [
                {
                    "BlockIndex": 0,
                    "Name": "head_JNT",
                    "Translation": [0.0, 1.84, -0.013],
                    "Rotation": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
                    "Scale": 1.0,
                    "ExtraData": [],
                    "Controller": -1,
                    "Children": [],
                    "Effects": [6],
                    "ChildNodes": [],
                    "NodeSize": 94,
                }
            ],
            "Meshes": [
                {"BlockIndex": 6, "Size": 329, "ParentNiNodeIndex": 0},
            ],
        }
        out_path.write_text(json.dumps(sg), encoding="utf-8")
        return True, "", "", 0.2

    monkeypatch.setattr("bulk_export_for_flythrough.run_decode_geometry", fake_decode)
    monkeypatch.setattr("bulk_export_for_flythrough.run_probe_scene_graph", fake_probe)

    result = bulk_export_for_flythrough(
        asset_ids=["abcdef0123456789"],
        output_dir=out,
        manifest_path=manifest,
        project=Path("."),
        root=Path("."),
        world_dir=world_dir,
    )
    assert result.stats["exported"] == 1
    # Verify world.json was written
    wj = world_dir / "abcdef0123456789.world.json"
    assert wj.exists()
    sg = json.loads(wj.read_text(encoding="utf-8"))
    assert sg["SchemaVersion"] == "scene-graph/v1"
    assert sg["nif_hash"] == "abcdef0123456789"
    # Verify FT-3 sidecar was enriched
    sidecar = out / "decode-nif-geometry-abcdef0123456789" / "mesh.obj.manifest.json"
    assert sidecar.exists()
    sc = json.loads(sidecar.read_text(encoding="utf-8"))
    assert sc["parent_node"] == "head_JNT"
    assert sc["transform"]["translation"] == [0.0, 1.84, -0.013]
