"""Tests for the practical 350 flythrough package builder."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from build_flythrough_practical_package import (  # noqa: E402
    build_source_substitution_payload,
    build_texture_fallback_payload,
    target_ref_to_manifest_indices,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_build_source_substitution_payload_uses_exported_redrive_obj(tmp_path: Path) -> None:
    redrive_output_dir = tmp_path / "Assets" / "build" / "flythrough" / "evidence" / "redrive-objs"
    obj_path = redrive_output_dir / "decode-nif-geometry-07f37c99a80da009" / "decode-nif-geometry" / "mesh17.obj"
    obj_path.parent.mkdir(parents=True)
    obj_path.write_text("v 0 0 0\n", encoding="utf-8")
    redrive_manifest = tmp_path / "redrive.json"
    _write_json(
        redrive_manifest,
        {
            "Entries": [
                {
                    "nif_hash": "07f37c99a80da009",
                    "status": "exported",
                    "obj_path": "decode-nif-geometry-07f37c99a80da009/decode-nif-geometry/mesh17.obj",
                }
            ]
        },
    )

    payload = build_source_substitution_payload(
        repo_root=tmp_path,
        redrive_manifest_path=redrive_manifest,
        redrive_output_dir=redrive_output_dir,
    )

    assert payload["schema"] == "flythrough-source-substitutions-v1"
    assert payload["entries"][0]["manifest_index"] == 121
    assert payload["entries"][0]["candidate_asset_id"] == "07f37c99a80da009"
    assert payload["entries"][0]["durable_truth"] is False
    assert payload["entries"][0]["replacement_source_obj"].endswith(
        "decode-nif-geometry-07f37c99a80da009/decode-nif-geometry/mesh17.obj"
    )


def test_build_texture_fallback_payload_uses_top_recovery_candidate(tmp_path: Path) -> None:
    triage = tmp_path / "triage.json"
    recovery = tmp_path / "recovery.json"
    _write_json(
        triage,
        {
            "rows": [
                {
                    "manifest_index": 118,
                    "row_dds_refs": ["missing_flowers_c.dds", "missing_flowers_s.dds"],
                }
            ]
        },
    )
    _write_json(
        recovery,
        {
            "visual_fallback_candidates": {
                "missing_flowers_c.dds": [
                    {
                        "dds_ref": "similar_flowers_c.dds",
                        "png_name": "abcd_similar_flowers_c.png",
                        "png_path": "textures/converted/abcd_similar_flowers_c.png",
                        "score": 157,
                        "reasons": ["same role"],
                    }
                ],
                "missing_flowers_s.dds": [],
            }
        },
    )

    payload = build_texture_fallback_payload(
        triage_report_path=triage,
        recovery_report_path=recovery,
    )

    assert payload["schema"] == "flythrough-texture-fallbacks-v1"
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["manifest_index"] == 118
    assert payload["entries"][0]["target_dds_ref"] == "missing_flowers_c.dds"
    assert payload["entries"][0]["replacement_png_name"] == "abcd_similar_flowers_c.png"
    assert payload["entries"][0]["durable_truth"] is False


def test_target_ref_to_manifest_indices_maps_multiple_refs() -> None:
    assert target_ref_to_manifest_indices(
        {
            "rows": [
                {"manifest_index": 1, "row_dds_refs": ["a.dds", "b.dds"]},
                {"manifest_index": 2, "row_dds_refs": ["a.dds"]},
            ]
        }
    ) == {"a.dds": [1, 2], "b.dds": [1]}
