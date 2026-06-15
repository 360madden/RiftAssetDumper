"""Tests for practical texture fallback provenance reporting."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from audit_flythrough_texture_fallback_provenance import (  # noqa: E402
    build_texture_fallback_provenance_report,
    render_markdown,
    texture_name_to_assets,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_texture_name_to_assets_maps_linked_textures() -> None:
    assert texture_name_to_assets(
        {
            "assets": {
                "aaaaaaaaaaaaaaaa": {"linked_textures": ["flower_c.png", "flower_s.png"]},
                "bbbbbbbbbbbbbbbb": {"linked_textures": ["flower_c.png"]},
            }
        }
    ) == {
        "flower_c.png": ["aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"],
        "flower_s.png": ["aaaaaaaaaaaaaaaa"],
    }


def test_build_texture_fallback_provenance_report_finds_same_mesh_source_asset(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    flythrough_index_path = tmp_path / "flythrough-index.json"
    _write_json(
        manifest_path,
        {
            "entries": [
                {
                    "manifest_index": 118,
                    "asset_id": "fa78ee2d8c3abca7",
                    "mesh_block": "7",
                    "mesh_size": 280,
                    "vertex_count": 32,
                    "face_count": 30,
                    "texture_fallbacks": [
                        {
                            "target_dds_ref": "n_ds_eternal_assault_flowers_01_c.dds",
                            "replacement_dds_ref": "n_ds_ruinouspassage_flowers_01_c.dds",
                            "replacement_png_name": "b3024468_n_ds_ruinouspassage_flowers_01_c.png",
                            "durable_truth": False,
                            "score": 157,
                            "reasons": ["same leading namespace tokens"],
                        }
                    ],
                }
            ]
        },
    )
    _write_json(
        flythrough_index_path,
        {
            "assets": {
                "fa78ee2d8c3abca7": {
                    "mesh_block": "7",
                    "mesh_size": 280,
                    "vertex_count": 32,
                    "face_count": 30,
                    "node_count": 2,
                    "mesh_count": 1,
                    "linked_textures": [],
                },
                "bd1a97be88dfb781": {
                    "mesh_block": "7",
                    "mesh_size": 280,
                    "vertex_count": 32,
                    "face_count": 30,
                    "node_count": 2,
                    "mesh_count": 1,
                    "linked_textures": ["b3024468_n_ds_ruinouspassage_flowers_01_c.png"],
                },
            }
        },
    )

    report = build_texture_fallback_provenance_report(
        manifest_path=manifest_path,
        flythrough_index_path=flythrough_index_path,
        repo_root=tmp_path,
    )

    assert report["schema"] == "flythrough-texture-fallback-provenance-v1"
    assert report["summary"]["fallback_rows"] == 1
    assert report["summary"]["fallback_refs"] == 1
    assert report["summary"]["fallback_refs_with_source_assets"] == 1
    assert report["summary"]["fallback_refs_with_same_mesh_source_assets"] == 1
    ref = report["fallback_refs"][0]
    assert ref["target_asset_id"] == "fa78ee2d8c3abca7"
    assert ref["source_assets"][0]["asset_id"] == "bd1a97be88dfb781"
    assert ref["source_assets"][0]["same_mesh_signature"] is True
    assert ref["durable_truth"] is False


def test_render_markdown_keeps_non_durable_boundary_visible() -> None:
    markdown = render_markdown(
        {
            "generated_at": "2026-06-15T00:00:00Z",
            "summary": {
                "fallback_rows": 1,
                "fallback_refs": 1,
                "fallback_refs_with_source_assets": 1,
                "fallback_refs_with_same_mesh_source_assets": 1,
                "unique_source_assets": 1,
                "non_durable_fallback_refs": 1,
            },
            "fallback_refs": [
                {
                    "manifest_index": 118,
                    "target_asset_id": "fa78ee2d8c3abca7",
                    "target_dds_ref": "n_ds_eternal_assault_flowers_01_c.dds",
                    "replacement_dds_ref": "n_ds_ruinouspassage_flowers_01_c.dds",
                    "replacement_png_name": "b3024468_n_ds_ruinouspassage_flowers_01_c.png",
                    "target_mesh_signature": {"mesh_block": "7", "mesh_size": 280},
                    "source_assets": [{"asset_id": "bd1a97be88dfb781", "same_mesh_signature": True}],
                    "durable_truth": False,
                    "next_action": "Keep as practical fallback.",
                }
            ],
        }
    )

    assert "Texture Fallback Provenance" in markdown
    assert "bd1a97be88dfb781" in markdown
    assert "same mesh" in markdown
    assert "durable_truth=false" in markdown
