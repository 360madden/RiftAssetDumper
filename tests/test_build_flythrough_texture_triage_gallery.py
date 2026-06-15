"""Tests for the flythrough OBJ texture triage gallery renderer."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from build_flythrough_texture_triage_gallery import (  # noqa: E402
    build_gallery_model,
    choose_preview_texture,
    non_materialized_reason,
    render_gallery,
)


def _manifest() -> dict:
    return {
        "schema": "flythrough-obj-texture-manifest-v1",
        "summary": {
            "total_entries": 3,
            "materializable_entries": 2,
            "bundle_root": "Assets/build/flythrough/obj-texture-bundle-candidate-textures",
            "single_candidate_materialized_entries": 1,
            "common_candidate_materialized_entries": 0,
            "bundle_verify": {"pass": True, "missing_texture_refs_count": 0},
        },
        "entries": [
            {
                "manifest_index": 0,
                "materializable": True,
                "asset_id": "abcdef0123456789",
                "texture_source": "asset-id",
                "linked_texture_count": 2,
                "linked_textures": [
                    {
                        "name": "wall_n.png",
                        "path": "Assets/build/flythrough/textures/converted/wall_n.png",
                        "role": "normal",
                    },
                    {
                        "name": "wall_c.png",
                        "path": "Assets/build/flythrough/textures/converted/wall_c.png",
                        "role": "diffuse",
                    },
                ],
                "chosen_material_textures": {"diffuse": "wall_c.png"},
                "bundled_obj": "Assets/build/flythrough/obj-texture-bundle-candidate-textures/objs/000.obj",
                "bundled_mtl": "Assets/build/flythrough/obj-texture-bundle-candidate-textures/materials/000.mtl",
            },
            {
                "manifest_index": 1,
                "materializable": True,
                "asset_id": None,
                "texture_source": "single-candidate-heuristic",
                "linked_texture_count": 1,
                "linked_textures": [
                    {
                        "name": "fallback_c.png",
                        "path": "Assets/build/flythrough/textures/converted/fallback_c.png",
                        "role": "diffuse",
                    }
                ],
                "chosen_material_textures": {"diffuse": "fallback_c.png"},
                "texture_fallbacks": [
                    {
                        "target_dds_ref": "missing_flowers_c.dds",
                        "replacement_dds_ref": "similar_flowers_c.dds",
                        "replacement_png_name": "fallback_c.png",
                        "durable_truth": False,
                    }
                ],
                "bundled_obj": "Assets/build/flythrough/obj-texture-bundle-candidate-textures/objs/001.obj",
                "bundled_mtl": "Assets/build/flythrough/obj-texture-bundle-candidate-textures/materials/001.mtl",
            },
            {
                "manifest_index": 2,
                "materializable": False,
                "source_obj": "Exports/missing.obj",
                "source_exists": False,
                "original_source_obj": "Exports/original-missing.obj",
                "source_substitution": {
                    "replacement_source_obj": "Assets/build/flythrough/evidence/candidate.obj",
                    "candidate_asset_id": "07f37c99a80da009",
                    "durable_truth": False,
                    "status": "active",
                },
                "asset_id": None,
                "candidate_asset_ids": [],
                "candidate_status": "no-geometry-signature-match",
                "linked_texture_count": 0,
                "texture_source": "untextured-neutral",
                "review_material": {
                    "kind": "source-substitution-no-textures",
                    "label": "source-substituted row without texture refs",
                    "diffuse_color": [0.65, 0.45, 0.95],
                    "durable_texture_truth": False,
                    "reason": "Source OBJ is a practical substitute and still has no texture evidence.",
                },
            },
        ],
    }


def test_choose_preview_texture_prefers_chosen_diffuse() -> None:
    entry = _manifest()["entries"][0]
    preview = choose_preview_texture(entry)
    assert preview is not None
    assert preview["name"] == "wall_c.png"


def test_non_materialized_reason_identifies_missing_source() -> None:
    assert non_materialized_reason(_manifest()["entries"][2]) == "missing-source-obj"


def test_build_gallery_model_counts_sources_roles_and_remaining() -> None:
    model = build_gallery_model(_manifest())
    assert len(model["materialized"]) == 2
    assert len(model["remaining"]) == 1
    assert model["texture_sources"] == {"asset-id": 1, "single-candidate-heuristic": 1}
    assert model["remaining_reasons"] == {"missing-source-obj": 1}
    assert model["texture_roles"] == {"diffuse": 2, "normal": 1}
    assert len(model["texture_fallback_refs"]) == 1
    assert model["review_materials"] == {}


def test_render_gallery_includes_remaining_rows_and_links(tmp_path: Path) -> None:
    html_out = tmp_path / "Assets" / "build" / "flythrough" / "texture-triage-gallery" / "index.html"
    text = render_gallery(_manifest(), html_out=html_out, repo_root=tmp_path, max_cards=10)
    assert "Flythrough OBJ Texture Triage" in text
    assert "missing-source-obj" in text
    assert "wall_c.png" in text
    assert "Practical texture fallbacks" in text
    assert "missing_flowers_c.dds" in text
    assert "durable=false" in text
    assert "../textures/converted/wall_c.png" in text
    assert "../obj-texture-bundle-candidate-textures/objs/000.obj" in text


def test_render_gallery_lists_source_substitutions(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["entries"][2]["materializable"] = True
    manifest["entries"][2]["bundled_obj"] = "Assets/build/flythrough/obj-texture-bundle-candidate-textures/objs/002.obj"
    manifest["entries"][2]["bundled_mtl"] = (
        "Assets/build/flythrough/obj-texture-bundle-candidate-textures/materials/002.mtl"
    )
    html_out = tmp_path / "Assets" / "build" / "flythrough" / "texture-triage-gallery" / "index.html"
    text = render_gallery(manifest, html_out=html_out, repo_root=tmp_path, max_cards=10)
    assert "Practical source substitutions" in text
    assert "Exports/original-missing.obj" in text
    assert "07f37c99a80da009" in text
    assert "Neutral review materials" in text
    assert "source-substitution-no-textures" in text
    assert "durable_texture_truth=False" in text
    assert "rgb(166, 115, 242)" in text
