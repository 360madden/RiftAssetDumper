"""Tests for the file-level flythrough OBJ/texture coverage audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from audit_flythrough_asset_texture_coverage import build_audit, render_markdown, repo_relative_path  # noqa: E402


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_repo_relative_path_redacts_absolute_windows_repo_prefix(tmp_path: Path) -> None:
    assert repo_relative_path(r"C:\RIFT MODDING\Assets\Exports\foo\bar.obj", tmp_path) == "Exports/foo/bar.obj"
    assert (
        repo_relative_path(
            r"C:\RIFT MODDING\Assets\Assets\build\flythrough\flythrough-index.json",
            tmp_path,
        )
        == "Assets/build/flythrough/flythrough-index.json"
    )


def test_build_audit_joins_obj_asset_and_texture_surfaces(tmp_path: Path) -> None:
    exports = tmp_path / "Exports"
    flythrough = tmp_path / "Assets" / "build" / "flythrough"
    converted = flythrough / "textures" / "converted"

    textured_obj = exports / "textured" / "abcdef0123456789.obj"
    untextured_obj = exports / "plain" / "fedcba9876543210.obj"
    _write_text(textured_obj, "mtllib textured.mtl\nusemtl textured\nv 0 0 0\n")
    _write_text(untextured_obj, "v 0 0 0\n")
    _write_text(converted / "abc12345_diffuse.png", "not really a png for this unit test\n")

    _write_json(
        exports / "export-manifest.json",
        {
            "schema": "export-manifest-v3",
            "entries": [
                {
                    "path": str(textured_obj),
                    "vertex_count": 1,
                    "face_count": 0,
                    "faced": False,
                    "export_batch": "individual-export",
                    "provenance": "copied",
                },
                {
                    "path": "C:/RIFT MODDING/Assets/Exports/missing/idless.obj",
                    "mesh_block": "6",
                    "vertex_count": 3,
                    "face_count": 1,
                    "faced": True,
                    "export_batch": "batch-264-v128",
                    "provenance": "copied",
                },
                {
                    "path": str(untextured_obj),
                    "vertex_count": 1,
                    "face_count": 0,
                    "faced": False,
                    "export_batch": "sibling-export",
                    "provenance": "live",
                },
            ],
        },
    )
    _write_json(
        flythrough / "flythrough-index.json",
        {
            "summary": {"with_world_json": 2, "with_lod_info": 1, "with_meshsize": 2},
            "assets": {
                "abcdef0123456789": {"linked_textures": ["abc12345_diffuse.png", "missing_normal.png"]},
                "fedcba9876543210": {"linked_textures": []},
            },
        },
    )
    _write_text(
        flythrough / "flythrough-texture-links.jsonl",
        json.dumps({"ModelIdPrefix": "abcdef0123456789", "TextureIdPrefix": "0011223344556677"}) + "\n",
    )
    _write_json(
        flythrough / "textures" / "converted-manifest.json",
        {"Mode": "unit", "Entries": [{"png_name": "abc12345_diffuse.png"}]},
    )
    _write_json(flythrough / "textures" / "extracted-manifest.json", {"Entries": []})

    audit = build_audit(repo_root=tmp_path)

    assert audit["obj_file_level"]["manifest_entries"] == 3
    assert audit["obj_file_level"]["obj_files_on_disk"] == 2
    assert audit["obj_file_level"]["missing_obj_files"] == ["Exports/missing/idless.obj"]
    assert audit["obj_file_level"]["entries_with_asset_id"] == 2
    assert audit["obj_file_level"]["entries_without_asset_id"] == 1
    assert audit["obj_file_level"]["entries_with_texture_links"] == 1
    assert audit["obj_file_level"]["entry_texture_status_breakdown"] == {
        "no-asset-id": 1,
        "no-linked-textures": 1,
        "texture-linked": 1,
    }
    assert audit["obj_file_level"]["entries_without_asset_id_candidate_status_breakdown"] == {
        "no-geometry-signature-match": 1
    }
    assert audit["obj_file_level"]["entries_without_asset_id_detail"][0]["candidate_asset_ids"] == []
    assert len(audit["obj_file_level"]["entries"]) == 3
    assert audit["obj_file_level"]["entries"][0]["asset_id"] == "abcdef0123456789"
    assert audit["obj_file_level"]["entries"][0]["texture_status"] == "texture-linked"
    assert audit["obj_file_level"]["entries"][0]["linked_textures"] == ["abc12345_diffuse.png", "missing_normal.png"]
    assert audit["obj_file_level"]["entries"][1]["candidate_status"] == "no-geometry-signature-match"
    assert audit["obj_file_level"]["entries"][1]["candidate_asset_ids"] == []
    assert audit["asset_id_level"]["indexed_assets_with_texture_links"] == 1
    assert audit["asset_id_level"]["indexed_assets_without_texture_links_detail"] == ["fedcba9876543210"]
    assert audit["texture_level"]["linked_texture_references_unique"] == 2
    assert audit["texture_level"]["unique_linked_pngs_present_on_disk"] == 1
    assert audit["texture_level"]["unique_linked_pngs_missing_on_disk"] == ["missing_normal.png"]
    assert audit["material_usability"]["obj_files_with_mtllib"] == 1
    assert audit["material_usability"]["obj_files_with_usemtl"] == 1

    markdown = render_markdown(audit)
    assert "Flythrough Asset + Texture Coverage Audit" in markdown
    assert "Exports/missing/idless.obj" in markdown
    assert "fedcba9876543210" in markdown
