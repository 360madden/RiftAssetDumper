"""Tests for flythrough OBJ/MTL bundle smoke validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from smoke_flythrough_obj_texture_bundle import parse_face_token, render_markdown, smoke_bundle  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_parse_face_token_flags_missing_normal_array() -> None:
    assert parse_face_token("1/1/1", vertex_count=3, texture_coord_count=3, normal_count=0) == [
        "normal index out of bounds in `1/1/1` with vn_count=0"
    ]


def test_smoke_bundle_passes_textured_and_neutral_rows(tmp_path: Path) -> None:
    texture = tmp_path / "Assets" / "build" / "flythrough" / "textures" / "converted" / "wall_c.png"
    _write(texture, "png")
    obj = tmp_path / "Assets" / "build" / "flythrough" / "bundle" / "objs" / "textured.obj"
    mtl = tmp_path / "Assets" / "build" / "flythrough" / "bundle" / "materials" / "textured.mtl"
    _write(
        obj,
        "mtllib ../materials/textured.mtl\n"
        "usemtl mat_textured\n"
        "v 0 0 0\nv 1 0 0\nv 0 1 0\n"
        "vt 0 0\nvt 1 0\nvt 0 1\n"
        "f 1/1 2/2 3/3\n",
    )
    _write(mtl, "newmtl mat_textured\nmap_Kd ../../textures/converted/wall_c.png\n")
    neutral_obj = tmp_path / "Assets" / "build" / "flythrough" / "bundle" / "objs" / "neutral.obj"
    neutral_mtl = tmp_path / "Assets" / "build" / "flythrough" / "bundle" / "materials" / "neutral.mtl"
    _write(neutral_obj, "mtllib ../materials/neutral.mtl\nusemtl mat_neutral\nv 0 0 0\n")
    _write(neutral_mtl, "newmtl mat_neutral\nKd 0.8 0.8 0.8\n")
    manifest = tmp_path / "manifest.json"
    _write_json(
        manifest,
        {
            "summary": {"bundle_root": "Assets/build/flythrough/bundle"},
            "entries": [
                {
                    "manifest_index": 0,
                    "materializable": True,
                    "bundled_obj": "Assets/build/flythrough/bundle/objs/textured.obj",
                    "bundled_mtl": "Assets/build/flythrough/bundle/materials/textured.mtl",
                    "material_name": "mat_textured",
                    "source_obj": "Exports/textured.obj",
                    "texture_source": "asset-id",
                },
                {
                    "manifest_index": 1,
                    "materializable": True,
                    "bundled_obj": "Assets/build/flythrough/bundle/objs/neutral.obj",
                    "bundled_mtl": "Assets/build/flythrough/bundle/materials/neutral.mtl",
                    "material_name": "mat_neutral",
                    "source_obj": "Exports/neutral.obj",
                    "texture_source": "untextured-neutral",
                },
                {"manifest_index": 2, "materializable": False},
            ],
        },
    )

    report = smoke_bundle(repo_root=tmp_path, manifest_path=manifest)
    assert report["summary"]["pass"] is True
    assert report["summary"]["checked_materializable_entries"] == 2
    assert report["summary"]["zero_face_entries"] == 1
    assert report["summary"]["total_texture_refs"] == 1
    assert "OBJ/MTL Bundle Smoke Report" in render_markdown(report)


def test_smoke_bundle_fails_missing_texture_ref(tmp_path: Path) -> None:
    obj = tmp_path / "Assets" / "build" / "flythrough" / "bundle" / "objs" / "bad.obj"
    mtl = tmp_path / "Assets" / "build" / "flythrough" / "bundle" / "materials" / "bad.mtl"
    _write(
        obj,
        "mtllib ../materials/bad.mtl\nusemtl mat_bad\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n",
    )
    _write(mtl, "newmtl mat_bad\nmap_Kd ../../textures/converted/missing.png\n")
    manifest = tmp_path / "manifest.json"
    _write_json(
        manifest,
        {
            "entries": [
                {
                    "manifest_index": 0,
                    "materializable": True,
                    "bundled_obj": "Assets/build/flythrough/bundle/objs/bad.obj",
                    "bundled_mtl": "Assets/build/flythrough/bundle/materials/bad.mtl",
                    "material_name": "mat_bad",
                    "source_obj": "Exports/bad.obj",
                    "texture_source": "asset-id",
                }
            ]
        },
    )

    report = smoke_bundle(repo_root=tmp_path, manifest_path=manifest)
    assert report["summary"]["pass"] is False
    assert report["summary"]["missing_texture_refs"] == 1
