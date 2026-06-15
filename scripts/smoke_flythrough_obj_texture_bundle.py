#!/usr/bin/env python3
"""Smoke-validate a generated flythrough OBJ/MTL bundle for downstream import.

The bundle verifier in ``build_flythrough_obj_texture_manifest.py`` checks file
presence and texture references. This script goes one step closer to a real
consumer: it parses bundled OBJ faces/material directives and MTL map paths, so
the generated bundle can be treated as importer-ready local evidence before a
Blender/RiftFlythrough smoke gate.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH_ROOT = REPO_ROOT / "Assets" / "build" / "flythrough"
DEFAULT_MANIFEST = FLYTHROUGH_ROOT / "flythrough-obj-texture-manifest-full-available.json"
DEFAULT_JSON_OUT = FLYTHROUGH_ROOT / "evidence" / "obj-texture-bundle-smoke" / "smoke-report.json"
DEFAULT_MARKDOWN_OUT = FLYTHROUGH_ROOT / "evidence" / "obj-texture-bundle-smoke" / "SMOKE_REPORT.md"
MTL_MAP_KEYS = {"map_Kd", "map_Ka", "map_Ks", "map_Bump", "bump", "map_d", "disp", "decal"}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    tmp.replace(path)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def _to_posix(value: str | Path) -> str:
    return str(value).replace("\\", "/")


def repo_relative_path(path: str | Path, *, repo_root: Path = REPO_ROOT) -> str:
    raw = _to_posix(path)
    root = _to_posix(repo_root.resolve()).rstrip("/")
    if raw.lower().startswith((root + "/").lower()):
        return raw[len(root) + 1 :]
    for segment in ("Assets/build/flythrough/", "Exports/"):
        index = raw.find(segment)
        if index >= 0:
            return raw[index:]
    return raw


def repo_path(path_value: str | Path, *, repo_root: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return repo_root / path


def _valid_positive_index(value: str, count: int) -> bool:
    try:
        index = int(value)
    except ValueError:
        return False
    return 1 <= index <= count


def parse_face_token(token: str, *, vertex_count: int, texture_coord_count: int, normal_count: int) -> list[str]:
    issues: list[str] = []
    parts = token.split("/")
    if not parts or not parts[0]:
        return [f"missing vertex index in `{token}`"]
    if not _valid_positive_index(parts[0], vertex_count):
        issues.append(f"vertex index out of bounds in `{token}` with vertex_count={vertex_count}")
    if len(parts) > 1 and parts[1] and not _valid_positive_index(parts[1], texture_coord_count):
        issues.append(f"texture coordinate index out of bounds in `{token}` with vt_count={texture_coord_count}")
    if len(parts) > 2 and parts[2] and not _valid_positive_index(parts[2], normal_count):
        issues.append(f"normal index out of bounds in `{token}` with vn_count={normal_count}")
    return issues


def parse_obj(path: Path, *, issue_limit: int = 20) -> dict[str, Any]:
    vertices = 0
    texture_coords = 0
    normals = 0
    faces = 0
    mtllibs: list[str] = []
    usemtls: list[str] = []
    issues: list[str] = []

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line_no, line in enumerate(lines, start=1):
        if line.startswith("v "):
            vertices += 1
            parts = line.split()
            if len(parts) < 4:
                if len(issues) < issue_limit:
                    issues.append(f"L{line_no}: vertex has fewer than 3 coordinates")
                continue
            try:
                coords = [float(value) for value in parts[1:4]]
            except ValueError:
                if len(issues) < issue_limit:
                    issues.append(f"L{line_no}: vertex coordinate parse failed")
                continue
            if not all(math.isfinite(value) for value in coords) and len(issues) < issue_limit:
                issues.append(f"L{line_no}: vertex contains NaN/Inf")
        elif line.startswith("vt "):
            texture_coords += 1
        elif line.startswith("vn "):
            normals += 1
        elif line.startswith("mtllib "):
            mtllibs.append(line.split(maxsplit=1)[1].strip())
        elif line.startswith("usemtl "):
            usemtls.append(line.split(maxsplit=1)[1].strip())

    for line_no, line in enumerate(lines, start=1):
        if not line.startswith("f "):
            continue
        tokens = line.split()[1:]
        if len(tokens) < 3 and len(issues) < issue_limit:
            issues.append(f"L{line_no}: face has fewer than 3 vertices")
        faces += 1
        for token in tokens:
            for issue in parse_face_token(
                token,
                vertex_count=vertices,
                texture_coord_count=texture_coords,
                normal_count=normals,
            ):
                if len(issues) < issue_limit:
                    issues.append(f"L{line_no}: {issue}")

    return {
        "vertices": vertices,
        "texture_coords": texture_coords,
        "normals": normals,
        "faces": faces,
        "mtllibs": mtllibs,
        "usemtls": usemtls,
        "issues": issues,
    }


def parse_mtl(path: Path, *, repo_root: Path, issue_limit: int = 20) -> dict[str, Any]:
    newmtls: list[str] = []
    texture_refs: list[str] = []
    missing_texture_refs: list[str] = []
    issues: list[str] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(maxsplit=1)
        if len(parts) < 2:
            continue
        key, value = parts
        if key == "newmtl":
            newmtls.append(value.strip())
        elif key in MTL_MAP_KEYS:
            texture_refs.append(value.strip())
            texture_path = (path.parent / value.strip()).resolve()
            if not texture_path.exists():
                missing_texture_refs.append(repo_relative_path(texture_path, repo_root=repo_root))
                if len(issues) < issue_limit:
                    issues.append(f"L{line_no}: missing texture ref `{value.strip()}`")
    return {
        "newmtls": newmtls,
        "texture_refs": texture_refs,
        "missing_texture_refs": missing_texture_refs,
        "issues": issues,
    }


def smoke_bundle(
    *,
    repo_root: Path = REPO_ROOT,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    materializable_entries = [entry for entry in manifest.get("entries", []) if entry.get("materializable")]
    issue_samples: list[dict[str, Any]] = []
    zero_face_samples: list[dict[str, Any]] = []
    texture_source_counter: Counter[str] = Counter()
    summary = {
        "manifest_entries": len(manifest.get("entries", [])),
        "checked_materializable_entries": len(materializable_entries),
        "missing_outputs": 0,
        "obj_issue_entries": 0,
        "mtl_issue_entries": 0,
        "material_directive_issue_entries": 0,
        "missing_texture_refs": 0,
        "zero_face_entries": 0,
        "neutral_material_entries": 0,
        "textured_material_entries": 0,
        "total_vertices": 0,
        "total_faces": 0,
        "total_texture_refs": 0,
    }

    for entry in materializable_entries:
        texture_source = str(entry.get("texture_source") or "unknown")
        texture_source_counter[texture_source] += 1
        obj_path = repo_path(entry["bundled_obj"], repo_root=repo_root)
        mtl_path = repo_path(entry["bundled_mtl"], repo_root=repo_root)
        entry_issues: list[str] = []

        if not obj_path.exists() or not mtl_path.exists():
            summary["missing_outputs"] += 1
            if not obj_path.exists():
                entry_issues.append(f"missing OBJ {entry['bundled_obj']}")
            if not mtl_path.exists():
                entry_issues.append(f"missing MTL {entry['bundled_mtl']}")
            issue_samples.append({"manifest_index": entry["manifest_index"], "issues": entry_issues})
            continue

        obj = parse_obj(obj_path)
        mtl = parse_mtl(mtl_path, repo_root=repo_root)
        summary["total_vertices"] += obj["vertices"]
        summary["total_faces"] += obj["faces"]
        summary["total_texture_refs"] += len(mtl["texture_refs"])

        expected_mtllib = os.path.relpath(mtl_path, obj_path.parent).replace("\\", "/")
        if expected_mtllib not in obj["mtllibs"]:
            entry_issues.append(f"OBJ missing expected mtllib `{expected_mtllib}`")
        if entry["material_name"] not in obj["usemtls"]:
            entry_issues.append(f"OBJ missing expected usemtl `{entry['material_name']}`")
        if entry["material_name"] not in mtl["newmtls"]:
            entry_issues.append(f"MTL missing expected newmtl `{entry['material_name']}`")
        if entry_issues:
            summary["material_directive_issue_entries"] += 1

        if obj["issues"]:
            summary["obj_issue_entries"] += 1
            entry_issues.extend(obj["issues"])
        if mtl["issues"]:
            summary["mtl_issue_entries"] += 1
            entry_issues.extend(mtl["issues"])
        if mtl["missing_texture_refs"]:
            summary["missing_texture_refs"] += len(mtl["missing_texture_refs"])

        if obj["faces"] == 0:
            summary["zero_face_entries"] += 1
            if len(zero_face_samples) < 25:
                zero_face_samples.append(
                    {
                        "manifest_index": entry["manifest_index"],
                        "source_obj": entry["source_obj"],
                        "texture_source": texture_source,
                    }
                )

        if texture_source == "untextured-neutral":
            summary["neutral_material_entries"] += 1
        else:
            summary["textured_material_entries"] += 1
            if not mtl["texture_refs"]:
                summary["mtl_issue_entries"] += 1
                entry_issues.append("textured entry has no MTL texture map refs")

        if entry_issues and len(issue_samples) < 25:
            issue_samples.append({"manifest_index": entry["manifest_index"], "issues": entry_issues})

    summary["texture_source_breakdown"] = dict(sorted(texture_source_counter.items()))
    summary["pass"] = (
        summary["missing_outputs"] == 0
        and summary["obj_issue_entries"] == 0
        and summary["mtl_issue_entries"] == 0
        and summary["material_directive_issue_entries"] == 0
        and summary["missing_texture_refs"] == 0
    )

    return {
        "schema": "flythrough-obj-texture-bundle-smoke-v1",
        "generated_at": _now_iso(),
        "inputs": {
            "manifest": repo_relative_path(manifest_path, repo_root=repo_root),
            "bundle_root": manifest.get("summary", {}).get("bundle_root"),
        },
        "summary": summary,
        "issue_samples": issue_samples,
        "zero_face_samples": zero_face_samples,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Flythrough OBJ/MTL Bundle Smoke Report",
        "",
        f"**Generated**: {report['generated_at']}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Pass | {summary['pass']} |",
        f"| Checked materializable entries | {summary['checked_materializable_entries']} |",
        f"| Missing outputs | {summary['missing_outputs']} |",
        f"| OBJ issue entries | {summary['obj_issue_entries']} |",
        f"| MTL issue entries | {summary['mtl_issue_entries']} |",
        f"| Material directive issue entries | {summary['material_directive_issue_entries']} |",
        f"| Missing texture refs | {summary['missing_texture_refs']} |",
        f"| Textured material entries | {summary['textured_material_entries']} |",
        f"| Neutral material entries | {summary['neutral_material_entries']} |",
        f"| Zero-face entries | {summary['zero_face_entries']} |",
        f"| Total vertices | {summary['total_vertices']} |",
        f"| Total faces | {summary['total_faces']} |",
        f"| Total MTL texture refs | {summary['total_texture_refs']} |",
        "",
        "## Texture source breakdown",
        "",
    ]
    for source, count in summary["texture_source_breakdown"].items():
        lines.append(f"- `{source}`: {count}")

    lines.extend(["", "## Issue samples", ""])
    if report["issue_samples"]:
        for sample in report["issue_samples"]:
            lines.append(f"- #{sample['manifest_index']}: {'; '.join(sample['issues'])}")
    else:
        lines.append("- None.")

    lines.extend(["", "## Zero-face sample rows", ""])
    if report["zero_face_samples"]:
        for sample in report["zero_face_samples"]:
            lines.append(
                f"- #{sample['manifest_index']} `{sample['source_obj']}` texture_source=`{sample['texture_source']}`"
            )
    else:
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    report = smoke_bundle(repo_root=repo_root, manifest_path=args.manifest)
    _write_json(args.json_out, report)
    _write_text(args.markdown_out, render_markdown(report))
    summary = report["summary"]
    print(
        "bundle smoke: "
        f"pass={summary['pass']} checked={summary['checked_materializable_entries']} "
        f"obj_issues={summary['obj_issue_entries']} mtl_issues={summary['mtl_issue_entries']} "
        f"missing_textures={summary['missing_texture_refs']} zero_face={summary['zero_face_entries']}"
    )
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
