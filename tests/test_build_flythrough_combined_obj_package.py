"""Tests for the combined flythrough OBJ/MTL package builder."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from build_flythrough_combined_obj_package import (  # noqa: E402
    build_combined_obj_package,
    offset_face_line,
)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_offset_face_line_rewrites_vertex_texcoord_and_normal_indices() -> None:
    assert (
        offset_face_line(
            "f 1/1/1 -1/-1/-1",
            v_offset=10,
            vt_offset=20,
            vn_offset=30,
            source_v_count=4,
            source_vt_count=5,
            source_vn_count=6,
        )
        == "f 11/21/31 14/25/36"
    )


def test_build_combined_obj_package_rewrites_mtl_and_emits_point_clouds(tmp_path: Path) -> None:
    texture = tmp_path / "Assets" / "build" / "flythrough" / "textures" / "converted" / "tex.png"
    _write_text(texture, "fake png")
    bundle = tmp_path / "Assets" / "build" / "flythrough" / "obj-texture-bundle-full-available"
    obj_a = bundle / "objs" / "001_face.obj"
    mtl_a = bundle / "materials" / "mat_face.mtl"
    obj_b = bundle / "objs" / "002_points.obj"
    mtl_b = bundle / "materials" / "mat_points.mtl"
    _write_text(
        obj_a,
        "\n".join(
            [
                "mtllib ../materials/mat_face.mtl",
                "usemtl mat_face",
                "v 0 0 0",
                "v 1 0 0",
                "v 0 1 0",
                "vt 0 0",
                "vt 1 0",
                "vt 0 1",
                "vn 0 0 1",
                "vn 0 0 1",
                "vn 0 0 1",
                "f 1/1/1 2/2/2 3/3/3",
                "",
            ]
        ),
    )
    _write_text(
        obj_b,
        "\n".join(
            [
                "mtllib ../materials/mat_points.mtl",
                "usemtl mat_points",
                "v 2 0 0",
                "v 3 0 0",
                "",
            ]
        ),
    )
    _write_text(
        mtl_a,
        "\n".join(
            [
                "newmtl mat_face",
                "Kd 1 1 1",
                "map_Kd ../../textures/converted/tex.png",
                "bump ../../textures/converted/tex.png",
                "",
            ]
        ),
    )
    _write_text(
        mtl_b,
        "\n".join(
            [
                "newmtl mat_points",
                "Kd 0.5 0.5 0.5",
                "",
            ]
        ),
    )
    manifest = tmp_path / "Assets" / "build" / "flythrough" / "flythrough-obj-texture-manifest-full-available.json"
    _write_json(
        manifest,
        {
            "entries": [
                {
                    "manifest_index": 1,
                    "asset_id": "abcdef0123456789",
                    "source_obj": "Exports/a.obj",
                    "bundled_obj": "Assets/build/flythrough/obj-texture-bundle-full-available/objs/001_face.obj",
                    "bundled_mtl": "Assets/build/flythrough/obj-texture-bundle-full-available/materials/mat_face.mtl",
                    "material_name": "mat_face",
                    "materializable": True,
                    "texture_source": "asset-id",
                },
                {
                    "manifest_index": 2,
                    "asset_id": "1111222233334444",
                    "source_obj": "Exports/b.obj",
                    "bundled_obj": "Assets/build/flythrough/obj-texture-bundle-full-available/objs/002_points.obj",
                    "bundled_mtl": "Assets/build/flythrough/obj-texture-bundle-full-available/materials/mat_points.mtl",
                    "material_name": "mat_points",
                    "materializable": True,
                    "texture_source": "untextured-neutral",
                },
                {"manifest_index": 3, "source_obj": "Exports/missing.obj", "materializable": False},
            ]
        },
    )
    package_root = tmp_path / "Assets" / "build" / "flythrough" / "combined"

    report = build_combined_obj_package(
        repo_root=tmp_path,
        manifest_path=manifest,
        obj_out=package_root / "combined.obj",
        mtl_out=package_root / "combined.mtl",
        report_out=package_root / "report.json",
        markdown_out=package_root / "README.md",
    )

    assert report["summary"]["combined_entries"] == 2
    assert report["summary"]["skipped_entries"] == 1
    assert report["summary"]["faces"] == 1
    assert report["summary"]["point_directive_entries"] == 1
    assert report["summary"]["copied_texture_files"] == 1
    assert report["summary"]["missing_source_textures"] == 0
    assert report["summary"]["verify_pass"] is True
    assert report["verify"]["texture_refs"] == 2
    assert report["outputs"]["textures"] == "Assets/build/flythrough/combined/textures"

    obj_text = (package_root / "combined.obj").read_text(encoding="utf-8")
    assert "mtllib combined.mtl" in obj_text
    assert "f 1/1/1 2/2/2 3/3/3" in obj_text
    assert "p 4 5" in obj_text

    mtl_text = (package_root / "combined.mtl").read_text(encoding="utf-8")
    assert "newmtl mat_face" in mtl_text
    assert "map_Kd textures/converted/tex.png" in mtl_text
    assert "bump textures/converted/tex.png" in mtl_text
    copied_texture = package_root / "textures" / "converted" / "tex.png"
    assert copied_texture.read_text(encoding="utf-8") == "fake png"

    shared_root = tmp_path / "Assets" / "build" / "flythrough" / "combined-shared-textures"
    shared_report = build_combined_obj_package(
        repo_root=tmp_path,
        manifest_path=manifest,
        obj_out=shared_root / "combined.obj",
        mtl_out=shared_root / "combined.mtl",
        report_out=shared_root / "report.json",
        markdown_out=shared_root / "README.md",
        copy_textures=False,
    )

    assert shared_report["summary"]["copied_texture_files"] == 0
    assert shared_report["outputs"]["textures"] is None
    shared_mtl_text = (shared_root / "combined.mtl").read_text(encoding="utf-8")
    assert "map_Kd ../textures/converted/tex.png" in shared_mtl_text
    assert "bump ../textures/converted/tex.png" in shared_mtl_text
