"""Tests for practical flythrough texture/source gap reporting."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from build_flythrough_texture_gap_report import build_texture_gap_report, render_markdown  # noqa: E402


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_build_texture_gap_report_buckets_neutral_fallback_and_source_gaps(tmp_path: Path) -> None:
    manifest = {
        "summary": {
            "materializable_entries": 4,
        },
        "entries": [
            {
                "manifest_index": 0,
                "asset_id": "aaaaaaaaaaaaaaaa",
                "source_obj": "Exports/textured.obj",
                "texture_status": "texture-linked",
                "texture_source": "asset-id",
                "mesh_block": "6",
                "mesh_size": 240,
                "vertex_count": 3,
                "face_count": 1,
                "faced": True,
            },
            {
                "manifest_index": 1,
                "asset_id": "bbbbbbbbbbbbbbbb",
                "source_obj": "Exports/neutral.obj",
                "texture_status": "no-linked-textures",
                "texture_source": "untextured-neutral",
                "mesh_block": "7",
                "mesh_size": 193,
                "vertex_count": 56,
                "face_count": 54,
                "faced": True,
            },
            {
                "manifest_index": 2,
                "asset_id": "cccccccccccccccc",
                "source_obj": "Exports/fallback.obj",
                "texture_status": "texture-linked",
                "texture_source": "asset-id+visual-fallback-textures",
                "mesh_block": "7",
                "mesh_size": 280,
                "vertex_count": 32,
                "face_count": 30,
                "faced": True,
                "texture_fallbacks": [
                    {
                        "target_dds_ref": "missing_flowers_c.dds",
                        "replacement_dds_ref": "similar_flowers_c.dds",
                        "replacement_png_name": "similar_flowers_c.png",
                        "durable_truth": False,
                    }
                ],
            },
            {
                "manifest_index": 3,
                "asset_id": None,
                "source_obj": "Assets/build/flythrough/evidence/candidate.obj",
                "texture_status": "no-asset-id",
                "texture_source": "untextured-neutral",
                "mesh_block": "17",
                "mesh_size": 197,
                "vertex_count": 50,
                "face_count": 0,
                "faced": False,
                "source_substitution": {
                    "original_source_obj": "Exports/missing.obj",
                    "replacement_source_obj": "Assets/build/flythrough/evidence/candidate.obj",
                    "durable_truth": False,
                },
            },
        ],
    }
    triage_path = tmp_path / "triage.json"
    recovery_path = tmp_path / "recovery.json"
    probe_path = tmp_path / "probe-refresh.json"
    _write_json(
        triage_path,
        {
            "summary": {"neutral_rows": 2},
            "rows": [
                {
                    "manifest_index": 1,
                    "row_dds_refs": [],
                    "row_dds_refs_missing_from_converted": [],
                    "asset_probe_files": ["Exports/probe-nif-mesh-bbbbbbbbbbbbbbbb-mesh7.json"],
                }
            ],
        },
    )
    _write_json(
        recovery_path,
        {
            "summary": {"unmatched_target_refs": 1},
            "refs": {
                "unmatched_target": ["missing_flowers_c.dds"],
            },
        },
    )
    _write_json(
        probe_path,
        {
            "summary": {"targets_with_mesh_dds_refs": 0},
            "targets": [
                {
                    "manifest_indices": [1],
                    "probe_exists": True,
                    "mesh_dds_refs": [],
                    "asset_dds_refs": [],
                }
            ],
        },
    )

    report = build_texture_gap_report(
        repo_root=tmp_path,
        manifest=manifest,
        manifest_path=tmp_path / "manifest.json",
        triage_report_path=triage_path,
        recovery_report_path=recovery_path,
        probe_refresh_report_path=probe_path,
    )

    assert report["summary"]["total_entries"] == 4
    assert report["summary"]["entries_with_non_neutral_textures"] == 2
    assert report["summary"]["neutral_material_entries"] == 2
    assert report["summary"]["texture_fallback_refs"] == 1
    assert report["summary"]["source_substituted_entries"] == 1
    assert report["neutral_bucket_counts"] == {
        "no-asset-id-source-substitution": 1,
        "probed-no-mesh-dds-refs": 1,
    }
    assert report["unmatched_exact_dds_refs"] == ["missing_flowers_c.dds"]
    assert report["fallback_target_dds_refs"] == ["missing_flowers_c.dds"]


def test_render_markdown_keeps_non_durable_truth_boundaries_visible() -> None:
    markdown = render_markdown(
        {
            "generated_at": "2026-06-15T00:00:00Z",
            "summary": {
                "total_entries": 1,
                "materializable_entries": 1,
                "entries_with_non_neutral_textures": 1,
                "neutral_material_entries": 0,
                "neutral_entries_with_asset_id": 0,
                "neutral_entries_without_asset_id": 0,
                "texture_fallback_entries": 1,
                "texture_fallback_refs": 1,
                "source_substituted_entries": 0,
                "unmatched_exact_dds_refs": 1,
            },
            "neutral_bucket_counts": {},
            "unmatched_exact_dds_refs": ["missing_flowers_c.dds"],
            "texture_fallback_rows": [
                {
                    "manifest_index": 118,
                    "asset_id": "fa78ee2d8c3abca7",
                    "fallbacks": [
                        {
                            "target_dds_ref": "missing_flowers_c.dds",
                            "replacement_dds_ref": "similar_flowers_c.dds",
                            "replacement_png_name": "similar_flowers_c.png",
                            "durable_truth": False,
                        }
                    ],
                }
            ],
            "neutral_rows": [],
            "source_substitution_rows": [],
        }
    )

    assert "missing_flowers_c.dds" in markdown
    assert "Durable truth?" in markdown
    assert "| no |" in markdown
    assert "| 118 |" in markdown
    assert "| _none_ | 0 |" in markdown
