"""Tests for downstream flythrough OBJ texture manifest/bundle generation."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from build_flythrough_obj_texture_manifest import (  # noqa: E402
    build_manifest,
    choose_material_textures,
    classify_texture_role,
    common_candidate_texture_names,
    load_source_substitutions,
    load_texture_fallbacks,
    mtl_lines,
    normalize_converted_texture_path,
    normalize_face_token_for_available_attributes,
    obj_with_material_text,
    verify_bundle,
    write_bundle,
    write_csv,
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


def test_build_manifest_can_use_explicit_source_substitution_for_practical_access(tmp_path: Path) -> None:
    replacement = tmp_path / "Assets" / "build" / "flythrough" / "evidence" / "candidate.obj"
    replacement.parent.mkdir(parents=True)
    replacement.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
    substitutions_path = tmp_path / "source-substitutions.json"
    substitutions_path.write_text(
        json.dumps(
            {
                "schema": "flythrough-source-substitutions-v1",
                "entries": [
                    {
                        "manifest_index": 1,
                        "replacement_source_obj": str(replacement),
                        "candidate_asset_id": "07f37c99a80da009",
                        "review_status": "candidate-practical-access",
                        "durable_truth": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    audit = {
        "schema": "flythrough-asset-texture-coverage-audit-v1",
        "obj_file_level": {
            "entry_texture_status_breakdown": {"no-asset-id": 1},
            "entries_without_asset_id_candidate_status_breakdown": {},
            "entries": [
                {
                    "manifest_index": 1,
                    "path": "Exports/missing/decode-nif-geometry-mesh17.obj",
                    "exists_on_disk": False,
                    "asset_id": None,
                    "candidate_asset_ids": [],
                    "texture_status": "no-asset-id",
                    "linked_textures": [],
                    "mesh_block": "17",
                    "mesh_size": 197,
                    "vertex_count": 50,
                    "face_count": 0,
                    "faced": False,
                }
            ],
        },
    }

    substitutions = load_source_substitutions(substitutions_path, repo_root=tmp_path)
    manifest = build_manifest(
        repo_root=tmp_path,
        audit=audit,
        converted_texture_paths={},
        materialize_untextured=True,
        source_substitutions=substitutions,
    )

    assert manifest["summary"]["materializable_entries"] == 1
    assert manifest["summary"]["entries_missing_source_obj"] == 0
    assert manifest["summary"]["entries_missing_original_source_obj"] == 1
    assert manifest["summary"]["source_substituted_entries"] == 1
    row = manifest["entries"][0]
    assert row["source_obj"] == "Assets/build/flythrough/evidence/candidate.obj"
    assert row["original_source_obj"] == "Exports/missing/decode-nif-geometry-mesh17.obj"
    assert row["source_substitution"]["status"] == "active"
    assert row["source_substitution"]["durable_truth"] is False
    assert row["texture_source"] == "untextured-neutral"


def test_build_manifest_can_borrow_single_candidate_textures_without_promoting_asset_id(tmp_path: Path) -> None:
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
                    "linked_textures": ["abc_wall_c.png"],
                },
                {
                    "manifest_index": 1,
                    "path": "Exports/idless.obj",
                    "exists_on_disk": True,
                    "asset_id": None,
                    "candidate_asset_ids": ["abcdef0123456789"],
                    "candidate_status": "single-asset-signature-match",
                    "texture_status": "no-asset-id",
                    "linked_textures": [],
                },
            ],
        },
    }

    conservative = build_manifest(
        repo_root=tmp_path,
        audit=audit,
        converted_texture_paths={"abc_wall_c.png": "Assets/build/flythrough/textures/converted/abc_wall_c.png"},
    )
    assert conservative["summary"]["materializable_entries"] == 1
    assert conservative["entries"][1]["materializable"] is False
    assert conservative["entries"][1]["asset_id"] is None

    heuristic = build_manifest(
        repo_root=tmp_path,
        audit=audit,
        converted_texture_paths={"abc_wall_c.png": "Assets/build/flythrough/textures/converted/abc_wall_c.png"},
        allow_single_candidate_materials=True,
    )
    assert heuristic["summary"]["materializable_entries"] == 2
    assert heuristic["summary"]["single_candidate_materialized_entries"] == 1
    assert heuristic["entries"][1]["asset_id"] is None
    assert heuristic["entries"][1]["texture_source"] == "single-candidate-heuristic"
    assert heuristic["entries"][1]["borrowed_texture_asset_id"] == "abcdef0123456789"
    assert heuristic["entries"][1]["chosen_material_textures"]["diffuse"] == "abc_wall_c.png"


def test_build_manifest_can_borrow_common_candidate_textures_without_promoting_asset_id(tmp_path: Path) -> None:
    audit = {
        "schema": "flythrough-asset-texture-coverage-audit-v1",
        "obj_file_level": {
            "entry_texture_status_breakdown": {"texture-linked": 2, "no-asset-id": 1},
            "entries_without_asset_id_candidate_status_breakdown": {"ambiguous-signature-match": 1},
            "entries": [
                {
                    "manifest_index": 0,
                    "path": "Exports/a/aaaaaaaaaaaaaaaa.obj",
                    "exists_on_disk": True,
                    "asset_id": "aaaaaaaaaaaaaaaa",
                    "candidate_asset_ids": [],
                    "texture_status": "texture-linked",
                    "linked_textures": ["shared_diffuse_c.png"],
                },
                {
                    "manifest_index": 1,
                    "path": "Exports/b/bbbbbbbbbbbbbbbb.obj",
                    "exists_on_disk": True,
                    "asset_id": "bbbbbbbbbbbbbbbb",
                    "candidate_asset_ids": [],
                    "texture_status": "texture-linked",
                    "linked_textures": ["shared_diffuse_c.png"],
                },
                {
                    "manifest_index": 2,
                    "path": "Exports/idless.obj",
                    "exists_on_disk": True,
                    "asset_id": None,
                    "candidate_asset_ids": ["aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"],
                    "geometry_matching_candidate_asset_ids": ["aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"],
                    "candidate_status": "ambiguous-signature-match",
                    "candidate_geometry_status": "ambiguous-candidate-geometry-match",
                    "texture_status": "no-asset-id",
                    "linked_textures": [],
                },
            ],
        },
    }
    asset_textures = {
        "aaaaaaaaaaaaaaaa": ["shared_diffuse_c.png"],
        "bbbbbbbbbbbbbbbb": ["shared_diffuse_c.png"],
    }
    entries: list[dict[str, object]] = audit["obj_file_level"]["entries"]  # type: ignore[index]
    assert common_candidate_texture_names(entries[2], asset_textures) == ["shared_diffuse_c.png"]

    manifest = build_manifest(
        repo_root=tmp_path,
        audit=audit,
        converted_texture_paths={
            "shared_diffuse_c.png": "Assets/build/flythrough/textures/converted/shared_diffuse_c.png"
        },
        allow_common_candidate_materials=True,
    )
    assert manifest["summary"]["materializable_entries"] == 3
    assert manifest["summary"]["common_candidate_materialized_entries"] == 1
    assert manifest["entries"][2]["asset_id"] is None
    assert manifest["entries"][2]["texture_source"] == "common-candidate-textures"
    assert manifest["entries"][2]["borrowed_texture_asset_id"] == "aaaaaaaaaaaaaaaa,bbbbbbbbbbbbbbbb"


def test_build_manifest_can_materialize_untextured_existing_obj_as_neutral(tmp_path: Path) -> None:
    audit = {
        "schema": "flythrough-asset-texture-coverage-audit-v1",
        "obj_file_level": {
            "entry_texture_status_breakdown": {"no-linked-textures": 1},
            "entries_without_asset_id_candidate_status_breakdown": {},
            "entries": [
                {
                    "manifest_index": 0,
                    "path": "Exports/textureless.obj",
                    "exists_on_disk": True,
                    "asset_id": "abcdef0123456789",
                    "candidate_asset_ids": [],
                    "texture_status": "no-linked-textures",
                    "linked_textures": [],
                }
            ],
        },
    }

    conservative = build_manifest(repo_root=tmp_path, audit=audit, converted_texture_paths={})
    assert conservative["summary"]["materializable_entries"] == 0
    assert conservative["summary"]["entries_without_textures"] == 1

    neutral = build_manifest(
        repo_root=tmp_path,
        audit=audit,
        converted_texture_paths={},
        materialize_untextured=True,
    )
    assert neutral["summary"]["materializable_entries"] == 1
    assert neutral["summary"]["entries_without_textures"] == 0
    assert neutral["summary"]["entries_lacking_texture_links"] == 1
    assert neutral["summary"]["untextured_materialized_entries"] == 1
    assert neutral["summary"]["review_material_entries"] == 1
    assert neutral["entries"][0]["texture_source"] == "untextured-neutral"
    assert neutral["entries"][0]["chosen_material_textures"] == {}
    assert neutral["entries"][0]["review_material"]["kind"] == "asset-id-no-linked-textures"
    assert neutral["entries"][0]["review_material"]["durable_texture_truth"] is False
    assert neutral["entries"][0]["review_material_kind"] == "asset-id-no-linked-textures"
    assert neutral["entries"][0]["review_material_label"] == "asset-id row without linked texture refs"
    assert neutral["entries"][0]["review_material_diffuse_color"] == [0.35, 0.55, 1.0]
    assert neutral["entries"][0]["review_material_durable_texture_truth"] is False
    assert "no row textures" in neutral["entries"][0]["review_material_reason"]

    csv_path = tmp_path / "manifest.csv"
    write_csv(csv_path, neutral)
    with csv_path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["review_material_kind"] == "asset-id-no-linked-textures"
    assert rows[0]["review_material_diffuse_color"] == "0.350000 0.550000 1.000000"
    assert "no row textures" in rows[0]["review_material_reason"]


def test_mtl_lines_colors_neutral_review_material_without_texture_claim(tmp_path: Path) -> None:
    lines = mtl_lines(
        "neutral_mat",
        {},
        mtl_path=tmp_path / "neutral_mat.mtl",
        repo_root=tmp_path,
        review_material={
            "kind": "idless-no-texture-candidate",
            "label": "id-less row without texture candidate",
            "diffuse_color": [1.0, 0.65, 0.25],
            "durable_texture_truth": False,
            "reason": "No durable asset ID or texture candidate is available.",
        },
    )

    assert lines[0] == "newmtl neutral_mat"
    assert "# Durable texture truth: false" in lines
    assert "Kd 1.000000 0.650000 0.250000" in lines
    assert not any(line.startswith("map_Kd ") for line in lines)


def test_build_manifest_can_use_textureless_triage_converted_refs(tmp_path: Path) -> None:
    audit = {
        "schema": "flythrough-asset-texture-coverage-audit-v1",
        "obj_file_level": {
            "entry_texture_status_breakdown": {"no-linked-textures": 1},
            "entries_without_asset_id_candidate_status_breakdown": {},
            "entries": [
                {
                    "manifest_index": 7,
                    "path": "Exports/textureless.obj",
                    "exists_on_disk": True,
                    "asset_id": "abcdef0123456789",
                    "candidate_asset_ids": [],
                    "texture_status": "no-linked-textures",
                    "linked_textures": [],
                }
            ],
        },
    }
    triage_report = tmp_path / "textureless-triage.json"
    converted_manifest = tmp_path / "converted-manifest.json"
    triage_report.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "manifest_index": 7,
                        "row_dds_refs": ["recovered_wall_c.dds", "still_missing_n.dds"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    converted_manifest.write_text(
        json.dumps(
            {
                "Entries": [
                    {
                        "original_basename": "recovered_wall_c",
                        "png_name": "12345678_recovered_wall_c.png",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    manifest = build_manifest(
        repo_root=tmp_path,
        audit=audit,
        converted_texture_paths={
            "12345678_recovered_wall_c.png": "Assets/build/flythrough/textures/converted/12345678_recovered_wall_c.png"
        },
        allow_textureless_triage_materials=True,
        textureless_triage_report_path=triage_report,
        converted_manifest_path=converted_manifest,
    )
    assert manifest["summary"]["materializable_entries"] == 1
    assert manifest["summary"]["textureless_triage_materialized_entries"] == 1
    assert manifest["summary"]["entries_lacking_texture_links"] == 0
    assert manifest["entries"][0]["texture_source"] == "textureless-triage-probe"
    assert manifest["entries"][0]["chosen_material_textures"]["diffuse"] == "12345678_recovered_wall_c.png"


def test_build_manifest_can_use_explicit_visual_texture_fallbacks_without_promoting_truth(tmp_path: Path) -> None:
    texture = tmp_path / "Assets" / "build" / "flythrough" / "textures" / "converted" / "fallback_wall_c.png"
    texture.parent.mkdir(parents=True)
    texture.write_text("png", encoding="utf-8")
    fallbacks_path = tmp_path / "texture-fallbacks.json"
    fallbacks_path.write_text(
        json.dumps(
            {
                "schema": "flythrough-texture-fallbacks-v1",
                "entries": [
                    {
                        "manifest_index": 5,
                        "target_dds_ref": "missing_wall_c.dds",
                        "replacement_dds_ref": "similar_wall_c.dds",
                        "replacement_png_name": "fallback_wall_c.png",
                        "replacement_png_path": str(texture),
                        "review_status": "visual-fallback",
                        "durable_truth": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    audit = {
        "schema": "flythrough-asset-texture-coverage-audit-v1",
        "obj_file_level": {
            "entry_texture_status_breakdown": {"no-linked-textures": 1},
            "entries_without_asset_id_candidate_status_breakdown": {},
            "entries": [
                {
                    "manifest_index": 5,
                    "path": "Exports/textureless.obj",
                    "exists_on_disk": True,
                    "asset_id": "abcdef0123456789",
                    "candidate_asset_ids": [],
                    "texture_status": "no-linked-textures",
                    "linked_textures": [],
                }
            ],
        },
    }

    manifest = build_manifest(
        repo_root=tmp_path,
        audit=audit,
        converted_texture_paths={
            "fallback_wall_c.png": "Assets/build/flythrough/textures/converted/fallback_wall_c.png"
        },
        texture_fallbacks=load_texture_fallbacks(fallbacks_path, repo_root=tmp_path),
        materialize_untextured=True,
    )

    assert manifest["summary"]["materializable_entries"] == 1
    assert manifest["summary"]["entries_lacking_original_texture_links"] == 1
    assert manifest["summary"]["entries_lacking_texture_links"] == 0
    assert manifest["summary"]["texture_fallback_materialized_entries"] == 1
    assert manifest["summary"]["texture_fallback_refs"] == 1
    row = manifest["entries"][0]
    assert row["texture_source"] == "visual-fallback-textures"
    assert row["texture_fallbacks"][0]["durable_truth"] is False
    assert row["texture_fallbacks"][0]["status"] == "active"
    assert row["chosen_material_textures"]["diffuse"] == "fallback_wall_c.png"


def test_texture_fallbacks_override_same_role_asset_textures_for_review(tmp_path: Path) -> None:
    fallbacks_path = tmp_path / "texture-fallbacks.json"
    fallbacks_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "manifest_index": 8,
                        "target_dds_ref": "missing_wall_c.dds",
                        "replacement_png_name": "fallback_wall_c.png",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    audit = {
        "schema": "flythrough-asset-texture-coverage-audit-v1",
        "obj_file_level": {
            "entry_texture_status_breakdown": {"texture-linked": 1},
            "entries_without_asset_id_candidate_status_breakdown": {},
            "entries": [
                {
                    "manifest_index": 8,
                    "path": "Exports/textured.obj",
                    "exists_on_disk": True,
                    "asset_id": "abcdef0123456789",
                    "candidate_asset_ids": [],
                    "texture_status": "texture-linked",
                    "linked_textures": ["original_wall_c.png"],
                }
            ],
        },
    }

    manifest = build_manifest(
        repo_root=tmp_path,
        audit=audit,
        converted_texture_paths={
            "fallback_wall_c.png": "Assets/build/flythrough/textures/converted/fallback_wall_c.png",
            "original_wall_c.png": "Assets/build/flythrough/textures/converted/original_wall_c.png",
        },
        texture_fallbacks=load_texture_fallbacks(fallbacks_path, repo_root=tmp_path),
    )

    row = manifest["entries"][0]
    assert row["texture_source"] == "asset-id+visual-fallback-textures"
    assert row["chosen_material_textures"]["diffuse"] == "fallback_wall_c.png"
    assert [texture["name"] for texture in row["linked_textures"]] == ["fallback_wall_c.png", "original_wall_c.png"]


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
    verify = verify_bundle(manifest, repo_root=tmp_path)
    assert verify["pass"] is True
    assert verify["texture_refs_checked"] == 1

    bundled_obj = tmp_path / str(manifest["entries"][0]["bundled_obj"])
    bundled_mtl = tmp_path / str(manifest["entries"][0]["bundled_mtl"])
    assert bundled_obj.read_text(encoding="utf-8").startswith(
        "mtllib ../materials/mat_000_abcdef0123456789.mtl\nusemtl mat_000_abcdef0123456789\n"
    )
    assert "map_Kd ../../textures/converted/abc_wall_c.png" in bundled_mtl.read_text(encoding="utf-8")


def test_obj_with_material_text_removes_existing_material_directives(tmp_path: Path) -> None:
    source_obj = tmp_path / "source.obj"
    source_obj.write_text("mtllib old.mtl\nusemtl old\nv 0 0 0\n", encoding="utf-8")
    out = obj_with_material_text(source_obj, mtllib="new.mtl", material_name="newmat")
    assert out == "mtllib new.mtl\nusemtl newmat\nv 0 0 0\n"


def test_normalize_face_token_drops_missing_normal_reference() -> None:
    assert normalize_face_token_for_available_attributes("3/2/9", texture_coord_count=4, normal_count=0) == "3/2"
    assert normalize_face_token_for_available_attributes("3/2/9", texture_coord_count=0, normal_count=0) == "3"
    assert normalize_face_token_for_available_attributes("3/2/9", texture_coord_count=4, normal_count=12) == "3/2/9"
    assert normalize_face_token_for_available_attributes("3/2/99", texture_coord_count=4, normal_count=12) == "3/2"


def test_obj_with_material_text_normalizes_faces_for_missing_normals(tmp_path: Path) -> None:
    source_obj = tmp_path / "source.obj"
    source_obj.write_text(
        "\n".join(
            [
                "v 0 0 0",
                "v 1 0 0",
                "v 0 1 0",
                "vt 0 0",
                "vt 1 0",
                "vt 0 1",
                "f 1/1/1 2/2/2 3/3/3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out = obj_with_material_text(source_obj, mtllib="new.mtl", material_name="newmat")
    assert "f 1/1 2/2 3/3\n" in out
