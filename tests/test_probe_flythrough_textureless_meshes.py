"""Tests for textureless flythrough mesh probe refresh helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from probe_flythrough_textureless_meshes import (  # noqa: E402
    build_probe_refresh_report,
    select_probe_targets,
    summarize_probe_file,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_select_probe_targets_dedupes_textureless_asset_mesh_rows(tmp_path: Path) -> None:
    existing_probe = tmp_path / "Exports" / "probe-nif-mesh-abcdef0123456789-mesh6.json"
    _write_json(existing_probe, {"Meshes": []})
    manifest = {
        "entries": [
            {
                "manifest_index": 1,
                "texture_source": "untextured-neutral",
                "asset_id": "ABCDEF0123456789",
                "mesh_block": "6",
                "source_obj": "Exports/a.obj",
            },
            {
                "manifest_index": 2,
                "texture_source": "textureless-triage-probe",
                "asset_id": "abcdef0123456789",
                "mesh_block": 6,
                "source_obj": "Exports/b.obj",
            },
            {
                "manifest_index": 3,
                "texture_source": "untextured-neutral",
                "asset_id": None,
                "mesh_block": "7",
                "source_obj": "Exports/idless.obj",
            },
            {
                "manifest_index": 4,
                "texture_source": "asset-id",
                "asset_id": "1111222233334444",
                "mesh_block": "9",
                "source_obj": "Exports/textured.obj",
            },
        ]
    }

    targets, stats = select_probe_targets(manifest, repo_root=tmp_path)

    assert stats["textureless_scope_rows"] == 3
    assert stats["rows_without_asset_id"] == 1
    assert stats["duplicate_target_rows"] == 1
    assert len(targets) == 1
    assert targets[0]["asset_id"] == "abcdef0123456789"
    assert targets[0]["manifest_indices"] == [1, 2]
    assert targets[0]["output_exists_before"] is True
    assert targets[0]["planned_action"] == "skip-existing"


def test_summarize_probe_file_extracts_mesh_scoped_dds_refs(tmp_path: Path) -> None:
    probe = tmp_path / "probe.json"
    _write_json(
        probe,
        {
            "MeshesEmitted": 1,
            "CandidateLinks": [{"a": 1}],
            "Pairings": [{"a": 1}, {"b": 2}],
            "AttributeSets": [],
            "Meshes": [
                {"MeshBlockIndex": 6, "StringSamples": ["Wanted_C.dds"]},
                {"MeshBlockIndex": 7, "StringSamples": ["Other_C.dds"]},
            ],
        },
    )

    summary = summarize_probe_file(probe, "6")

    assert summary["probe_exists"] is True
    assert summary["mesh_dds_refs"] == ["wanted_c.dds"]
    assert summary["asset_dds_refs"] == ["other_c.dds", "wanted_c.dds"]
    assert summary["candidate_links"] == 1
    assert summary["pairings"] == 2


def test_summarize_probe_file_accepts_count_fields(tmp_path: Path) -> None:
    probe = tmp_path / "probe.json"
    _write_json(
        probe,
        {
            "MeshesEmitted": 1,
            "CandidateLinks": 3,
            "Pairings": 0,
            "AttributeSets": 2,
            "Meshes": [{"MeshBlockIndex": 6, "StringSamples": []}],
        },
    )

    summary = summarize_probe_file(probe, "6")

    assert summary["candidate_links"] == 3
    assert summary["pairings"] == 0
    assert summary["attribute_sets"] == 2


def test_probe_refresh_dry_run_reports_targets_without_dotnet(tmp_path: Path) -> None:
    manifest = tmp_path / "Assets" / "build" / "flythrough" / "flythrough-obj-texture-manifest-full-available.json"
    _write_json(
        manifest,
        {
            "entries": [
                {
                    "manifest_index": 8,
                    "texture_source": "untextured-neutral",
                    "asset_id": "abcdef0123456789",
                    "mesh_block": "6",
                    "source_obj": "Exports/a.obj",
                }
            ]
        },
    )

    report = build_probe_refresh_report(
        repo_root=tmp_path,
        manifest_path=manifest,
        live_root=tmp_path / "missing-live",
        project=tmp_path / "missing.csproj",
        dry_run=True,
    )

    assert report["summary"]["unique_probe_targets"] == 1
    assert report["summary"]["commands_run"] == 0
    assert report["summary"]["status_counts"] == {"planned": 1}
    assert report["targets"][0]["output"] == "Exports/probe-nif-mesh-abcdef0123456789-mesh6.json"
