"""Tests for practical texture fallback provenance reporting."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from audit_flythrough_texture_fallback_provenance import (  # noqa: E402
    build_texture_fallback_provenance_report,
    inventory_reference_context,
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


def test_inventory_reference_context_groups_model_and_dds_refs() -> None:
    contexts = inventory_reference_context(
        {
            "Groups": [
                {
                    "ReferenceSamples": [
                        {
                            "IdPrefix": "aaaaaaaaaaaaaaaa",
                            "StringIndex": 2,
                            "Value": "art/project/model/example.ma",
                        },
                        {
                            "IdPrefix": "aaaaaaaaaaaaaaaa",
                            "StringIndex": 9,
                            "Value": "Example_C.dds",
                        },
                    ]
                }
            ]
        },
        {"aaaaaaaaaaaaaaaa"},
    )

    assert contexts["aaaaaaaaaaaaaaaa"]["model_paths"] == ["art/project/model/example.ma"]
    assert contexts["aaaaaaaaaaaaaaaa"]["dds_refs"] == ["Example_C.dds"]
    assert contexts["aaaaaaaaaaaaaaaa"]["string_indices"] == [2, 9]


def test_build_texture_fallback_provenance_report_finds_same_geometry_source_asset(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    flythrough_index_path = tmp_path / "flythrough-index.json"
    inventory_path = tmp_path / "inventory.json"
    target_obj = tmp_path / "Exports" / "target.obj"
    source_obj = tmp_path / "Exports" / "source.obj"
    obj_text = "# exported OBJ\nv 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nf 1/1 2/1 3/1\n"
    target_obj.parent.mkdir(parents=True)
    target_obj.write_text(obj_text, encoding="utf-8")
    source_obj.write_text(obj_text, encoding="utf-8")
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
                    "obj_path": str(target_obj),
                },
                "bd1a97be88dfb781": {
                    "mesh_block": "7",
                    "mesh_size": 280,
                    "vertex_count": 32,
                    "face_count": 30,
                    "node_count": 2,
                    "mesh_count": 1,
                    "linked_textures": ["b3024468_n_ds_ruinouspassage_flowers_01_c.png"],
                    "obj_path": str(source_obj),
                },
            }
        },
    )
    _write_json(
        inventory_path,
        {
            "Groups": [
                {
                    "ReferenceSamples": [
                        {
                            "IdPrefix": "fa78ee2d8c3abca7",
                            "StringIndex": 2,
                            "Value": "art/project/ep1/world_objects/nature/dusk_spires/plants/model/N_DS_eternal_assault_flower_instanced_04.ma",
                        },
                        {
                            "IdPrefix": "fa78ee2d8c3abca7",
                            "StringIndex": 9,
                            "Value": "N_DS_eternal_assault_flowers_01_c.dds",
                        },
                        {
                            "IdPrefix": "bd1a97be88dfb781",
                            "StringIndex": 2,
                            "Value": "art/project/ep1/world_objects/nature/dusk_spires/plants/model/N_DS_ruinouspassage_flower_instanced_04.ma",
                        },
                        {
                            "IdPrefix": "bd1a97be88dfb781",
                            "StringIndex": 9,
                            "Value": "N_DS_ruinouspassage_flowers_01_c.dds",
                        },
                    ]
                }
            ]
        },
    )

    report = build_texture_fallback_provenance_report(
        manifest_path=manifest_path,
        flythrough_index_path=flythrough_index_path,
        inventory_path=inventory_path,
        repo_root=tmp_path,
    )

    assert report["schema"] == "flythrough-texture-fallback-provenance-v1"
    assert report["summary"]["fallback_rows"] == 1
    assert report["summary"]["fallback_refs"] == 1
    assert report["summary"]["fallback_refs_with_source_assets"] == 1
    assert report["summary"]["fallback_refs_with_same_mesh_source_assets"] == 1
    assert report["summary"]["fallback_refs_with_same_geometry_hash"] == 1
    ref = report["fallback_refs"][0]
    assert ref["target_asset_id"] == "fa78ee2d8c3abca7"
    assert ref["target_geometry_fingerprint"]["geometry_line_count"] == 5
    assert ref["target_reference_context"]["dds_refs"] == ["N_DS_eternal_assault_flowers_01_c.dds"]
    assert ref["source_assets"][0]["asset_id"] == "bd1a97be88dfb781"
    assert ref["source_assets"][0]["same_mesh_signature"] is True
    assert ref["source_assets"][0]["same_geometry_hash"] is True
    assert ref["source_assets"][0]["reference_context"]["dds_refs"] == ["N_DS_ruinouspassage_flowers_01_c.dds"]
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
                "fallback_refs_with_same_geometry_hash": 1,
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
                    "target_reference_context": {
                        "model_paths": ["art/project/model/eternal.ma"],
                        "dds_refs": ["N_DS_eternal_assault_flowers_01_c.dds"],
                    },
                    "source_assets": [
                        {
                            "asset_id": "bd1a97be88dfb781",
                            "same_mesh_signature": True,
                            "same_geometry_hash": True,
                            "reference_context": {
                                "model_paths": ["art/project/model/ruinous.ma"],
                                "dds_refs": ["N_DS_ruinouspassage_flowers_01_c.dds"],
                            },
                        }
                    ],
                    "durable_truth": False,
                    "next_action": "Keep as practical fallback.",
                }
            ],
        }
    )

    assert "Texture Fallback Provenance" in markdown
    assert "bd1a97be88dfb781" in markdown
    assert "same geometry hash" in markdown
    assert "art/project/model/eternal.ma" in markdown
    assert "N_DS_ruinouspassage_flowers_01_c.dds" in markdown
    assert "durable_truth=false" in markdown
