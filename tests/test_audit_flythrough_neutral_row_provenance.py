"""Tests for neutral-row provenance reporting."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from audit_flythrough_neutral_row_provenance import (  # noqa: E402
    build_neutral_row_provenance_report,
    render_markdown,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_build_neutral_row_provenance_report_classifies_remaining_texture_work(tmp_path: Path) -> None:
    manifest = {
        "entries": [
            {
                "manifest_index": 10,
                "asset_id": "aaaaaaaaaaaaaaaa",
                "source_obj": "Exports/asset.obj",
                "texture_status": "no-linked-textures",
                "texture_source": "untextured-neutral",
                "mesh_block": "7",
                "mesh_size": 193,
                "vertex_count": 56,
                "face_count": 54,
                "faced": True,
                "review_material": {"kind": "asset-id-no-linked-textures"},
            },
            {
                "manifest_index": 11,
                "asset_id": None,
                "source_obj": "Exports/idless.obj",
                "texture_status": "no-asset-id",
                "texture_source": "untextured-neutral",
                "mesh_block": "6",
                "mesh_size": 272,
                "vertex_count": 24,
                "face_count": 0,
                "faced": False,
                "review_material": {"kind": "idless-no-texture-candidate"},
            },
            {
                "manifest_index": 12,
                "asset_id": None,
                "source_obj": "Assets/build/flythrough/evidence/candidate.obj",
                "original_source_obj": "Exports/missing.obj",
                "texture_status": "no-asset-id",
                "texture_source": "untextured-neutral",
                "mesh_block": "17",
                "mesh_size": 197,
                "vertex_count": 50,
                "face_count": 0,
                "faced": False,
                "source_substitution": {
                    "candidate_asset_id": "bbbbbbbbbbbbbbbb",
                    "replacement_source_obj": "Assets/build/flythrough/evidence/candidate.obj",
                    "durable_truth": False,
                },
                "review_material": {"kind": "source-substitution-no-textures"},
            },
        ]
    }
    manifest_path = tmp_path / "Assets" / "build" / "flythrough" / "manifest.json"
    gap_path = tmp_path / "Assets" / "build" / "flythrough" / "gap.json"
    unresolved_path = tmp_path / "Assets" / "build" / "flythrough" / "unresolved.json"
    assets64_path = tmp_path / "Exports" / "assets64.entries.jsonl"
    probe_report_path = tmp_path / "Assets" / "build" / "flythrough" / "probe-refresh.json"
    probe_path = tmp_path / "Exports" / "probe-nif-mesh-aaaaaaaaaaaaaaaa-mesh7.json"

    _write_json(manifest_path, manifest)
    _write_json(
        gap_path,
        {
            "neutral_rows": [
                {"manifest_index": 10, "asset_id": "aaaaaaaaaaaaaaaa", "row_dds_refs": []},
                {"manifest_index": 11, "asset_id": None, "row_dds_refs": []},
                {"manifest_index": 12, "asset_id": None, "row_dds_refs": []},
            ]
        },
    )
    _write_json(
        unresolved_path,
        {
            "neutral_assets": [
                {
                    "asset_id": "aaaaaaaaaaaaaaaa",
                    "manifest_indices": [10],
                    "texture_link_row_count": 0,
                }
            ]
        },
    )
    _write_jsonl(
        assets64_path,
        [
            {
                "Index": 100,
                "IdPrefix": "aaaaaaaaaaaaaaaa",
                "PakIndex": 5,
                "PakOffset": 123,
                "CompressedSize": 50,
                "Size": 75,
                "NameLength": 24,
                "Hash": "hash-a",
            },
            {
                "Index": 101,
                "IdPrefix": "bbbbbbbbbbbbbbbb",
                "PakIndex": 6,
                "PakOffset": 456,
                "CompressedSize": 60,
                "Size": 90,
                "NameLength": 26,
                "Hash": "hash-b",
            },
        ],
    )
    _write_json(
        probe_report_path,
        {
            "targets": [
                {
                    "asset_id": "aaaaaaaaaaaaaaaa",
                    "mesh_block": "7",
                    "manifest_indices": [10],
                    "output": "Exports/probe-nif-mesh-aaaaaaaaaaaaaaaa-mesh7.json",
                    "status": "skipped-existing",
                    "probe_exists": True,
                    "candidate_links": 1,
                    "pairings": 0,
                    "attribute_sets": 0,
                    "mesh_dds_refs": [],
                    "asset_dds_refs": [],
                }
            ]
        },
    )
    _write_json(
        probe_path,
        {
            "Source": {
                "ArchiveName": "assets.001",
                "EntryIndex": 1,
                "IdPrefix": "aaaaaaaaaaaaaaaa",
                "ManifestEntryIndex": 100,
                "PakIndex": 5,
                "PakOffset": 123,
                "SourceKind": "copied",
            },
            "Length": 75,
            "NifVersion": "20.6.0.0",
            "MeshBlockCount": 1,
            "MeshesEmitted": 1,
            "CandidateLinks": 1,
            "Pairings": 0,
            "AttributeSets": 0,
            "HeaderWarnings": [],
            "Meshes": [
                {
                    "MeshBlockIndex": 7,
                    "MeshSize": 193,
                    "MeshDataOffset": 32,
                    "StringSamples": ["SceneNode", "POSITION"],
                    "Streams": [{"RoleStats": {"PrimaryRole": "normal-float3-ror1-lead"}}],
                }
            ],
        },
    )

    report = build_neutral_row_provenance_report(
        repo_root=tmp_path,
        manifest_path=manifest_path,
        texture_gap_report_path=gap_path,
        unresolved_texture_report_path=unresolved_path,
        assets64_entries_path=assets64_path,
        probe_refresh_report_path=probe_report_path,
    )

    assert report["summary"]["neutral_rows"] == 3
    assert report["summary"]["asset_backed_neutral_rows"] == 1
    assert report["summary"]["idless_neutral_rows"] == 2
    assert report["summary"]["source_substituted_neutral_rows"] == 1
    assert report["summary"]["unique_neutral_asset_ids"] == 1
    assert report["summary"]["source_substitution_candidate_asset_ids"] == 1
    assert report["summary"]["neutral_asset_rows_with_assets64_manifest_entry"] == 1
    assert report["classification_counts"] == {
        "asset-backed-probed-no-mesh-or-link-textures": 1,
        "idless-provenance-gap": 1,
        "source-substitution-provenance-gap": 1,
    }
    asset_group = report["asset_groups"][0]
    assert asset_group["asset_id"] == "aaaaaaaaaaaaaaaa"
    assert asset_group["texture_link_row_count"] == 0
    assert asset_group["candidate_links"] == 1
    source_row = next(row for row in report["rows"] if row["manifest_index"] == 12)
    assert source_row["source_substitution_candidate_manifest_entries"][0]["IdPrefix"] == "bbbbbbbbbbbbbbbb"


def test_render_markdown_points_next_work_at_asset_texture_provenance() -> None:
    markdown = render_markdown(
        {
            "generated_at": "2026-06-15T00:00:00Z",
            "summary": {
                "neutral_rows": 1,
                "asset_backed_neutral_rows": 1,
                "unique_neutral_asset_ids": 1,
                "idless_neutral_rows": 0,
                "source_substituted_neutral_rows": 0,
                "neutral_asset_rows_with_assets64_manifest_entry": 1,
                "neutral_rows_with_probe_file": 1,
                "neutral_rows_with_mesh_dds_refs": 0,
                "neutral_rows_with_texture_link_rows": 0,
                "asset_backed_rows_with_no_mesh_or_link_textures": 1,
            },
            "classification_counts": {"asset-backed-probed-no-mesh-or-link-textures": 1},
            "asset_groups": [
                {
                    "asset_id": "aaaaaaaaaaaaaaaa",
                    "manifest_indices": [10],
                    "mesh_blocks": ["7"],
                    "asset_manifest_entries": [{"Index": 100, "PakIndex": 5, "PakOffset": 123, "Size": 75}],
                    "probe_outputs": ["Exports/probe-nif-mesh-aaaaaaaaaaaaaaaa-mesh7.json"],
                    "candidate_links": 1,
                    "pairings": 0,
                    "mesh_dds_refs": [],
                    "texture_link_row_count": 0,
                    "next_best_action": "Inspect parent, non-mesh, or provenance references.",
                }
            ],
            "rows": [],
        }
    )

    assert "aaaaaaaaaaaaaaaa" in markdown
    assert "parent, non-mesh, or provenance" in markdown
    assert "not broad CI work" in markdown
