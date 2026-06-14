"""Tests for downstream flythrough OBJ texture manifest/bundle generation."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from build_flythrough_obj_texture_manifest import (  # noqa: E402
    build_manifest,
    choose_material_textures,
    classify_texture_role,
    normalize_converted_texture_path,
    obj_with_material_text,
    write_bundle,
)


def test_classify_texture_role_uses_rift_suffixes_and_keywords() -> None:
    assert classify_texture_role("abcdef12_stone_wall_c.png") == "diffuse"
    assert classify_texture_role("abcdef12_stone_wall_d.png") == "diffuse"
    assert classify_texture_role("abcdef12_stone_wall_n.png") == "normal"
    assert classify_texture_role("abcdef12_stone_wall_s.png") == "specular"
    assert classify_texture_role("abcdef12_structure_alpha_01.png") == "alpha"
    assert classify_texture_role("abcdef12_sky_gradient.png") == "diffuse"
    assert classify_texture_role("abcdef12_unclassified_texture.png") == "unknown"


def test_choose_material_textures_selects_diffuse_normal_specular() -> None:
    chosen = choose_material_textures(
        [
            "11111111_wall_n.png",
            "22222222_wall_s.png",
            "33333333_wall_c.png",
        ]
    )
    assert chosen["diffuse"] == "33333333_wall_c.png"
    assert chosen["normal"] == "11111111_wall_n.png"
    assert chosen["specular"] == "22222222_wall_s.png"


def test_choose_material_textures_falls_back_to_unknown_for_diffuse() -> None:
    chosen = choose_material_textures(["11111111_custom.png"])
    assert chosen["diffuse"] == "11111111_custom.png"


def test_normalize_converted_texture_path_promotes_flythrough_relative_path(tmp_path: Path) -> None:
    assert (
        normalize_converted_texture_path("textures/converted/abc.png", repo_root=tmp_path)
        == "Assets/build/flythrough/textures/converted/abc.png"
    )


def test_build_manifest_preserves_350_style_rows_and_material_paths(tmp_path: Path) -> None:
    audit = {
        "schema": "flythrough-asset-texture-coverage-audit-v1",
        "obj_file_level": {
            "entry_texture_status_breakdown": {"texture-linked": 1, "no-asset-id": 1},
            "entries_without_asset_id_candidate_status_breakdown": {"single-asset-signature-match": 1},
            "entries": [
                {
                    "manifest_index": 0,
                    "path": "Exports/a/abcdef0123456789.obj",
                    "exists_on_disk": True,
                    "asset_id": "abcdef0123456789",
                    "candidate_asset_ids": [],
                    "texture_status": "texture-linked",
                    "linked_textures": ["abc_wall_c.png", "abc_wall_n.png"],
                    "mesh_block": "6",
                    "mesh_size": 240,
                    "vertex_count": 3,
                    "face_count": 1,
                    "faced": True,
                    "export_batch": "individual-export",
                    "provenance": "copied",
                },
                {
                    "manifest_index": 1,
                    "path": "Exports/idless.obj",
                    "exists_on_disk": False,
                    "asset_id": None,
                    "candidate_asset_ids": ["abcdef0123456789"],
                    "texture_status": "no-asset-id",
                    "linked_textures": [],
                    "mesh_block": "6",
                    "mesh_size": 240,
                    "vertex_count": 3,
                    "face_count": 1,
                    "faced": True,
                    "export_batch": "individual-export",
                    "provenance": "copied",
                },
            ],
        },
    }
    manifest = build_manifest(
        repo_root=tmp_path,
        audit=audit,
        converted_texture_paths={
            "abc_wall_c.png": "Assets/build/flythrough/textures/converted/abc_wall_c.png",
            "abc_wall_n.png": "Assets/build/flythrough/textures/converted/abc_wall_n.png",
        },
        bundle_root=tmp_path / "Assets" / "build" / "flythrough" / "obj-texture-bundle",
    )

    assert manifest["schema"] == "flythrough-obj-texture-manifest-v1"
    assert manifest["summary"]["total_entries"] == 2
    assert manifest["summary"]["materializable_entries"] == 1
    assert manifest["summary"]["entries_missing_source_obj"] == 1
    assert manifest["entries"][0]["materializable"] is True
    assert manifest["entries"][0]["chosen_material_textures"]["diffuse"] == "abc_wall_c.png"
    assert manifest["entries"][0]["bundled_obj"].endswith(".obj")
    assert manifest["entries"][1]["candidate_asset_ids"] == ["abcdef0123456789"]


def test_write_bundle_creates_obj_with_material_refs_and_mtl(tmp_path: Path) -> None:
    source_obj = tmp_path / "Exports" / "a" / "abcdef0123456789.obj"
    source_obj.parent.mkdir(parents=True)
    source_obj.write_text("# source\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
    texture_path = tmp_path / "Assets" / "build" / "flythrough" / "textures" / "converted" / "abc_wall_c.png"
    texture_path.parent.mkdir(parents=True)
    texture_path.write_text("png", encoding="utf-8")

    manifest = {
        "entries": [
            {
                "source_obj": "Exports/a/abcdef0123456789.obj",
                "materializable": True,
                "material_name": "mat_000_abcdef0123456789",
                "chosen_material_textures": {"diffuse": "abc_wall_c.png"},
                "bundled_obj": "Assets/build/flythrough/obj-texture-bundle/objs/000.obj",
                "bundled_mtl": "Assets/build/flythrough/obj-texture-bundle/materials/mat_000_abcdef0123456789.mtl",
            }
        ]
    }

    result = write_bundle(
        manifest,
        repo_root=tmp_path,
        bundle_root=tmp_path / "Assets" / "build" / "flythrough" / "obj-texture-bundle",
    )
    assert result["written_objs"] == 1
    assert result["written_mtls"] == 1

    bundled_obj = tmp_path / manifest["entries"][0]["bundled_obj"]
    bundled_mtl = tmp_path / manifest["entries"][0]["bundled_mtl"]
    assert bundled_obj.read_text(encoding="utf-8").startswith(
        "mtllib ../materials/mat_000_abcdef0123456789.mtl\nusemtl mat_000_abcdef0123456789\n"
    )
    assert "map_Kd ../../textures/converted/abc_wall_c.png" in bundled_mtl.read_text(encoding="utf-8")


def test_obj_with_material_text_removes_existing_material_directives(tmp_path: Path) -> None:
    source_obj = tmp_path / "source.obj"
    source_obj.write_text("mtllib old.mtl\nusemtl old\nv 0 0 0\n", encoding="utf-8")
    out = obj_with_material_text(source_obj, mtllib="new.mtl", material_name="newmat")
    assert out == "mtllib new.mtl\nusemtl newmat\nv 0 0 0\n"
