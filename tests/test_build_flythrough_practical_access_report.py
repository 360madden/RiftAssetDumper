"""Tests for the practical 350 access report."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from build_flythrough_practical_access_report import build_access_report, render_markdown  # noqa: E402


def _manifest() -> dict:
    return {
        "summary": {
            "total_entries": 350,
            "materializable_entries": 350,
        },
        "entries": [
            {
                "manifest_index": 118,
                "asset_id": "fa78ee2d8c3abca7",
                "texture_fallbacks": [
                    {
                        "target_dds_ref": "n_ds_eternal_assault_flowers_01_c.dds",
                        "replacement_dds_ref": "n_ds_ruinouspassage_flowers_01_c.dds",
                        "replacement_png_name": "b3024468_n_ds_ruinouspassage_flowers_01_c.png",
                        "durable_truth": False,
                        "score": 157,
                    }
                ],
            }
        ],
    }


def _build_report() -> dict:
    return {
        "outputs": {
            "manifest": "Assets/build/flythrough/manifest.json",
            "csv": "Assets/build/flythrough/manifest.csv",
            "bundle_root": "Assets/build/flythrough/bundle",
            "combined_markdown": "Assets/build/flythrough/combined/COMBINED_OBJ_PACKAGE.md",
            "gallery": "Assets/build/flythrough/gallery/index.html",
            "texture_gap_markdown": "Assets/build/flythrough/evidence/TEXTURE_GAP_REPORT.md",
            "neutral_provenance_markdown": "Assets/build/flythrough/evidence/NEUTRAL_ROW_PROVENANCE.md",
            "unresolved_texture_markdown": "Assets/build/flythrough/evidence/UNRESOLVED_TEXTURE_EVIDENCE.md",
        },
        "summary": {
            "manifest_entries": 350,
            "materializable_entries": 350,
            "non_neutral_texture_entries": 337,
            "neutral_material_entries": 13,
            "source_substituted_entries": 1,
            "texture_fallback_refs": 2,
            "unmatched_exact_dds_refs": 2,
            "unmatched_exact_dds_refs_with_any_exact_match": 0,
            "bundle_verify_pass": True,
            "smoke_pass": True,
            "combined_entries": 350,
            "combined_skipped_entries": 0,
            "combined_verify_pass": True,
            "gallery_exists": True,
        },
    }


def _texture_gap_report() -> dict:
    return {
        "summary": {
            "entries_with_non_neutral_textures": 337,
            "neutral_material_entries": 13,
        },
        "unmatched_exact_dds_refs": ["n_ds_eternal_assault_flowers_01_c.dds"],
    }


def _unresolved_texture_report() -> dict:
    return {
        "exact_dds_refs": [
            {
                "dds_ref": "n_ds_eternal_assault_flowers_01_c.dds",
                "exact_match_count": 0,
            }
        ],
        "summary": {
            "unmatched_exact_dds_refs": 1,
            "unmatched_exact_dds_refs_with_any_exact_match": 0,
        },
    }


def _neutral_provenance_report() -> dict:
    return {
        "summary": {
            "asset_backed_neutral_rows": 10,
            "idless_neutral_rows": 3,
        },
        "asset_groups": [
            {
                "asset_id": "b5dc665faa848f85",
                "manifest_indices": [89, 324],
                "mesh_blocks": ["12"],
                "world_parent_node_names": ["prop"],
                "world_named_nodes": ["blade_base", "blade_tip"],
                "world_mesh_size_mismatch_rows": [],
                "world_non_texture_property_type_counts": {"NiMaterialProperty": 1},
                "mesh_dds_refs": [],
                "texture_link_row_count": 0,
                "next_best_action": "Inspect parent, non-mesh, or provenance references.",
            }
        ],
        "rows": [
            {
                "manifest_index": 5,
                "classification": "idless-provenance-gap",
                "review_material_kind": "idless-no-texture-candidate",
                "source_obj": "Exports/decode-fallback-1/mesh6.obj",
                "original_source_exists": True,
                "coverage_entry": {
                    "candidate_geometry_status": "no-candidate-geometry-match",
                    "geometry_line_count": 48,
                },
                "next_best_action": "Recover asset identity/source provenance first.",
            }
        ],
    }


def _combined_report() -> dict:
    return {
        "summary": {
            "combined_entries": 350,
            "zero_face_entries": 79,
            "point_directive_entries": 79,
            "copied_texture_files": 158,
        }
    }


def test_build_access_report_summarizes_access_and_review_queues() -> None:
    report = build_access_report(
        manifest=_manifest(),
        build_report=_build_report(),
        texture_gap_report=_texture_gap_report(),
        unresolved_texture_report=_unresolved_texture_report(),
        neutral_provenance_report=_neutral_provenance_report(),
        combined_report=_combined_report(),
    )

    assert report["schema"] == "flythrough-practical-access-report-v1"
    assert report["status"] == "practical-access-ready-with-review-queues"
    assert report["summary"]["materialized_obj_rows"] == 350
    assert report["summary"]["rows_with_non_neutral_textures_or_fallbacks"] == 337
    assert report["summary"]["neutral_review_rows"] == 13
    assert report["summary"]["exact_dds_gaps"] == 2
    assert report["summary"]["point_cloud_entries"] == 79
    assert report["summary"]["verification_pass"] is True
    assert report["review_queues"]["exact_dds_recovery"][0]["fallbacks"][0]["manifest_index"] == 118
    assert report["review_queues"]["neutral_asset_provenance"][0]["asset_id"] == "b5dc665faa848f85"
    assert report["review_queues"]["idless_or_source_substituted_rows"][0]["manifest_index"] == 5
    assert len(report["next_best_actions"]) == 10


def test_render_markdown_keeps_downstream_paths_and_truth_boundaries_visible() -> None:
    report = build_access_report(
        manifest=_manifest(),
        build_report=_build_report(),
        texture_gap_report=_texture_gap_report(),
        unresolved_texture_report=_unresolved_texture_report(),
        neutral_provenance_report=_neutral_provenance_report(),
        combined_report=_combined_report(),
    )

    markdown = render_markdown(report)

    assert "# Practical 350 OBJ Access Report" in markdown
    assert "Assets/build/flythrough/gallery/index.html" in markdown
    assert "n_ds_eternal_assault_flowers_01_c.dds" in markdown
    assert "b5dc665faa848f85" in markdown
    assert "NiMaterialProperty" in markdown
    assert "Visual texture fallbacks are usability aids" in markdown
    assert "## Top 10 next asset-focused actions" in markdown
