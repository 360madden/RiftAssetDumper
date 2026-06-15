"""Tests for textureless flythrough asset triage."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from triage_flythrough_textureless_assets import (  # noqa: E402
    build_textureless_triage,
    extract_dds_refs,
    render_markdown,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_extract_dds_refs_walks_nested_probe_data() -> None:
    data = {
        "StringSamples": ["A_Texture_C.dds", "not-a-texture"],
        "Meshes": [{"StringSamples": ["Folder\\B_Texture_N.DDS"]}],
    }
    assert extract_dds_refs(data) == ["a_texture_c.dds", "b_texture_n.dds"]


def test_build_textureless_triage_finds_mesh_and_asset_refs(tmp_path: Path) -> None:
    manifest = tmp_path / "Assets" / "build" / "flythrough" / "flythrough-obj-texture-manifest-full-available.json"
    converted = tmp_path / "Assets" / "build" / "flythrough" / "textures" / "converted-manifest.json"
    name_matches = tmp_path / "Exports" / "nif-reference-name-matches.jsonl"
    texture_links = tmp_path / "Exports" / "nif-texture-links.jsonl"
    _write_json(
        manifest,
        {
            "entries": [
                {
                    "manifest_index": 7,
                    "texture_source": "untextured-neutral",
                    "source_obj": "Exports/foo.obj",
                    "asset_id": "abcdef0123456789",
                    "mesh_block": "6",
                    "vertex_count": 3,
                    "face_count": 1,
                }
            ]
        },
    )
    _write_json(
        converted,
        {
            "Entries": [
                {
                    "original_basename": "known_texture_c",
                    "png_name": "12345678_known_texture_c.png",
                    "png_path": "Assets/build/flythrough/textures/converted/12345678_known_texture_c.png",
                }
            ]
        },
    )
    _write_json(
        tmp_path / "Exports" / "probe-nif-mesh-abcdef0123456789-mesh6.json",
        {
            "Meshes": [
                {
                    "MeshBlockIndex": 6,
                    "StringSamples": ["Known_Texture_C.dds", "Missing_Texture_N.dds"],
                }
            ]
        },
    )
    _write_jsonl(
        name_matches,
        [
            {
                "Name": "Missing_Texture_N.dds",
                "IdPrefix": "1111222233334444",
                "ManifestEntryIndex": 123,
                "PakIndex": 4,
                "PakOffset": 5678,
                "CompressedSize": 90,
                "Size": 100,
                "Confidence": 100,
                "CollisionCount": 1,
                "IsUniqueHashMatch": True,
            }
        ],
    )
    _write_jsonl(texture_links, [])

    report = build_textureless_triage(
        repo_root=tmp_path,
        manifest_path=manifest,
        converted_manifest_path=converted,
        name_matches_path=name_matches,
        texture_links_path=texture_links,
    )
    assert report["summary"]["neutral_rows"] == 1
    assert report["summary"]["neutral_rows_with_mesh_dds_refs"] == 1
    assert report["summary"]["neutral_asset_ids_with_any_dds_refs"] == 1
    assert report["summary"]["unique_dds_refs"] == 2
    assert report["summary"]["unique_dds_refs_present_in_converted"] == 1
    assert report["summary"]["unique_dds_refs_missing_from_converted"] == 1
    assert report["summary"]["unique_dds_refs_with_catalog_match"] == 1
    assert report["summary"]["missing_converted_dds_refs_with_catalog_match"] == 1
    assert report["rows"][0]["row_dds_refs"] == ["known_texture_c.dds", "missing_texture_n.dds"]
    assert report["rows"][0]["row_dds_refs_present_in_converted"] == ["known_texture_c.dds"]
    assert report["rows"][0]["row_dds_refs_missing_from_converted"] == ["missing_texture_n.dds"]
    assert report["dds_reference_status"][1]["dds_ref"] == "missing_texture_n.dds"
    assert report["dds_reference_status"][1]["catalog_matches"][0]["texture_id_prefix"] == "1111222233334444"

    markdown = render_markdown(report)
    assert "Flythrough Textureless Asset Triage" in markdown
    assert "Global texture catalog recovery hints" in markdown
    assert "missing_texture_n.dds" in markdown
