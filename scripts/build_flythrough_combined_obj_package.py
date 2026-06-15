#!/usr/bin/env python3
"""Build one downstream-friendly OBJ/MTL package from the flythrough bundle.

The full-available bundle materializes one OBJ and one MTL per manifest row.
That is useful for auditability, but awkward for downstream importers. This
script combines all currently materialized rows into a single OBJ plus a single
MTL while preserving material assignments and rewriting texture paths relative
to the combined package.

For zero-face meshes, the builder can emit OBJ ``p`` point directives so
position-only rows become visible in viewers that support OBJ point clouds.
Generated outputs stay under ``Assets/build/flythrough`` and must not be
committed.
"""

from __future__ import annotations

import argparse
import json
import posixpath
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH_ROOT = REPO_ROOT / "Assets" / "build" / "flythrough"
DEFAULT_MANIFEST = FLYTHROUGH_ROOT / "flythrough-obj-texture-manifest-full-available.json"
DEFAULT_PACKAGE_ROOT = FLYTHROUGH_ROOT / "combined-obj-package-full-available"
DEFAULT_OBJ_OUT = DEFAULT_PACKAGE_ROOT / "flythrough-full-available.obj"
DEFAULT_MTL_OUT = DEFAULT_PACKAGE_ROOT / "flythrough-full-available.mtl"
DEFAULT_REPORT_OUT = DEFAULT_PACKAGE_ROOT / "combined-obj-package-report.json"
DEFAULT_MARKDOWN_OUT = DEFAULT_PACKAGE_ROOT / "COMBINED_OBJ_PACKAGE.md"
MTL_TEXTURE_DIRECTIVES = {"bump", "decal", "disp", "norm", "refl"}


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


def repo_path_from_manifest(repo_root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root.joinpath(*_to_posix(value).split("/"))


def safe_object_name(entry: dict[str, Any]) -> str:
    asset = entry.get("asset_id") or "idless"
    source = Path(str(entry.get("source_obj") or entry.get("bundled_obj") or "obj")).stem
    return f"row_{int(entry.get('manifest_index', 0)):03d}_{asset}_{source}".replace(" ", "_")


def parse_obj(path: Path) -> dict[str, list[str]]:
    parsed = {"v": [], "vt": [], "vn": [], "f": [], "p": [], "usemtl": []}
    with path.open(encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            if line.startswith("v "):
                parsed["v"].append(line)
            elif line.startswith("vt "):
                parsed["vt"].append(line)
            elif line.startswith("vn "):
                parsed["vn"].append(line)
            elif line.startswith("f "):
                parsed["f"].append(line)
            elif line.startswith("p "):
                parsed["p"].append(line)
            elif line.startswith("usemtl "):
                parsed["usemtl"].append(line)
    return parsed


def resolve_obj_index(index: int, source_count: int) -> int:
    if index < 0:
        return source_count + index + 1
    return index


def offset_index_text(index_text: str, source_count: int, offset: int) -> str:
    if not index_text:
        return ""
    index = resolve_obj_index(int(index_text), source_count)
    return str(index + offset)


def offset_face_line(
    face_line: str,
    *,
    v_offset: int,
    vt_offset: int,
    vn_offset: int,
    source_v_count: int,
    source_vt_count: int,
    source_vn_count: int,
) -> str:
    parts = face_line.split()
    out = ["f"]
    for token in parts[1:]:
        indices = token.split("/")
        v = offset_index_text(indices[0], source_v_count, v_offset)
        vt = offset_index_text(indices[1], source_vt_count, vt_offset) if len(indices) > 1 else ""
        vn = offset_index_text(indices[2], source_vn_count, vn_offset) if len(indices) > 2 else ""
        if len(indices) > 2:
            out.append(f"{v}/{vt}/{vn}")
        elif len(indices) > 1:
            out.append(f"{v}/{vt}")
        else:
            out.append(v)
    return " ".join(out)


def offset_point_line(point_line: str, *, v_offset: int, source_v_count: int) -> str:
    parts = point_line.split()
    indices = [offset_index_text(part, source_v_count, v_offset) for part in parts[1:]]
    return "p " + " ".join(indices)


def chunked_point_lines(indices: list[int], *, chunk_size: int = 120) -> list[str]:
    return [
        "p " + " ".join(str(index) for index in indices[start : start + chunk_size])
        for start in range(0, len(indices), chunk_size)
    ]


def rewrite_mtl_texture_path(line: str, *, source_mtl: Path, output_mtl: Path) -> str:
    stripped = line.strip()
    if not is_mtl_texture_directive(stripped):
        return line
    parts = line.split()
    if len(parts) < 2:
        return line

    texture_ref = parts[-1]
    texture_path = (source_mtl.parent / Path(texture_ref)).resolve()
    try:
        rel = texture_path.relative_to(output_mtl.parent.resolve())
        rel_posix = _to_posix(rel)
    except ValueError:
        rel_posix = posixpath.relpath(_to_posix(texture_path), _to_posix(output_mtl.parent.resolve()))
    return " ".join([*parts[:-1], rel_posix])


def is_mtl_texture_directive(line: str) -> bool:
    if not line or line.startswith("#"):
        return False
    keyword = line.split(maxsplit=1)[0].lower()
    return keyword.startswith("map_") or keyword in MTL_TEXTURE_DIRECTIVES


def collect_mtl_lines(source_mtls: list[Path], *, output_mtl: Path) -> tuple[list[str], list[str]]:
    lines = [
        "# Combined flythrough material library",
        "# Generated by scripts/build_flythrough_combined_obj_package.py",
        "",
    ]
    missing: list[str] = []
    seen: set[Path] = set()
    for source_mtl in source_mtls:
        if source_mtl in seen:
            continue
        seen.add(source_mtl)
        if not source_mtl.exists():
            missing.append(str(source_mtl))
            continue
        lines.append(f"# Source: {repo_relative_path(source_mtl)}")
        with source_mtl.open(encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                lines.append(
                    rewrite_mtl_texture_path(raw_line.rstrip("\n"), source_mtl=source_mtl, output_mtl=output_mtl)
                )
        lines.append("")
    return lines, missing


def build_combined_obj_package(
    *,
    repo_root: Path = REPO_ROOT,
    manifest_path: Path = DEFAULT_MANIFEST,
    obj_out: Path = DEFAULT_OBJ_OUT,
    mtl_out: Path = DEFAULT_MTL_OUT,
    report_out: Path = DEFAULT_REPORT_OUT,
    markdown_out: Path = DEFAULT_MARKDOWN_OUT,
    emit_points_for_zero_face: bool = True,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    entries = manifest.get("entries", [])
    selected: list[tuple[dict[str, Any], Path, Path]] = []
    skipped: list[dict[str, Any]] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        bundled_obj = repo_path_from_manifest(repo_root, entry.get("bundled_obj"))
        bundled_mtl = repo_path_from_manifest(repo_root, entry.get("bundled_mtl"))
        if not entry.get("materializable") or bundled_obj is None or bundled_mtl is None:
            skipped.append(
                {
                    "manifest_index": entry.get("manifest_index"),
                    "source_obj": entry.get("source_obj"),
                    "reason": "not-materializable",
                }
            )
            continue
        if not bundled_obj.exists() or not bundled_mtl.exists():
            skipped.append(
                {
                    "manifest_index": entry.get("manifest_index"),
                    "source_obj": entry.get("source_obj"),
                    "bundled_obj": repo_relative_path(bundled_obj, repo_root=repo_root),
                    "bundled_mtl": repo_relative_path(bundled_mtl, repo_root=repo_root),
                    "reason": "missing-bundle-output",
                }
            )
            continue
        selected.append((entry, bundled_obj, bundled_mtl))

    mtl_lines, missing_mtls = collect_mtl_lines([mtl for _, _, mtl in selected], output_mtl=mtl_out)
    obj_lines = [
        "# Combined flythrough OBJ package",
        "# Generated by scripts/build_flythrough_combined_obj_package.py",
        f"# Source manifest: {repo_relative_path(manifest_path, repo_root=repo_root)}",
        f"mtllib {mtl_out.name}",
        "",
    ]

    totals = Counter()
    texture_sources = Counter()
    missing_objs: list[str] = []
    point_directive_entries = 0

    for entry, bundled_obj, _bundled_mtl in selected:
        parsed = parse_obj(bundled_obj)
        v_offset = totals["vertices"]
        vt_offset = totals["texcoords"]
        vn_offset = totals["normals"]
        source_v_count = len(parsed["v"])
        source_vt_count = len(parsed["vt"])
        source_vn_count = len(parsed["vn"])
        source_face_count = len(parsed["f"])

        obj_lines.append(f"o {safe_object_name(entry)}")
        obj_lines.append(f"# manifest_index={entry.get('manifest_index')} source={entry.get('source_obj')}")
        if parsed["usemtl"]:
            obj_lines.extend(parsed["usemtl"])
        elif entry.get("material_name"):
            obj_lines.append(f"usemtl {entry['material_name']}")
        obj_lines.extend(parsed["v"])
        obj_lines.extend(parsed["vt"])
        obj_lines.extend(parsed["vn"])

        for face in parsed["f"]:
            obj_lines.append(
                offset_face_line(
                    face,
                    v_offset=v_offset,
                    vt_offset=vt_offset,
                    vn_offset=vn_offset,
                    source_v_count=source_v_count,
                    source_vt_count=source_vt_count,
                    source_vn_count=source_vn_count,
                )
            )
        for point in parsed["p"]:
            obj_lines.append(offset_point_line(point, v_offset=v_offset, source_v_count=source_v_count))

        if not parsed["f"] and not parsed["p"] and emit_points_for_zero_face and source_v_count:
            indices = list(range(v_offset + 1, v_offset + source_v_count + 1))
            obj_lines.extend(chunked_point_lines(indices))
            point_directive_entries += 1

        obj_lines.append("")
        totals["vertices"] += source_v_count
        totals["texcoords"] += source_vt_count
        totals["normals"] += source_vn_count
        totals["faces"] += source_face_count
        totals["source_point_lines"] += len(parsed["p"])
        totals["zero_face_entries"] += 1 if source_face_count == 0 else 0
        texture_sources[str(entry.get("texture_source") or "unknown")] += 1
        if not bundled_obj.exists():
            missing_objs.append(repo_relative_path(bundled_obj, repo_root=repo_root))

    _write_text(mtl_out, "\n".join(mtl_lines).rstrip() + "\n")
    _write_text(obj_out, "\n".join(obj_lines).rstrip() + "\n")

    verify = verify_combined_package(obj_path=obj_out, mtl_path=mtl_out)
    report = {
        "schema": "flythrough-combined-obj-package-v1",
        "generated_at": _now_iso(),
        "inputs": {
            "manifest": repo_relative_path(manifest_path, repo_root=repo_root),
            "emit_points_for_zero_face": emit_points_for_zero_face,
        },
        "outputs": {
            "obj": repo_relative_path(obj_out, repo_root=repo_root),
            "mtl": repo_relative_path(mtl_out, repo_root=repo_root),
            "report": repo_relative_path(report_out, repo_root=repo_root),
            "markdown": repo_relative_path(markdown_out, repo_root=repo_root),
        },
        "summary": {
            "manifest_entries": len(entries),
            "combined_entries": len(selected),
            "skipped_entries": len(skipped),
            "vertices": totals["vertices"],
            "texcoords": totals["texcoords"],
            "normals": totals["normals"],
            "faces": totals["faces"],
            "zero_face_entries": totals["zero_face_entries"],
            "point_directive_entries": point_directive_entries,
            "texture_source_breakdown": dict(sorted(texture_sources.items())),
            "missing_bundle_objs": len(missing_objs),
            "missing_bundle_mtls": len(missing_mtls),
            "verify_pass": verify["pass"],
        },
        "skipped": skipped,
        "verify": verify,
    }
    _write_json(report_out, report)
    _write_text(markdown_out, render_markdown(report))
    return report


def parse_defined_materials(mtl_path: Path) -> tuple[set[str], list[str]]:
    materials: set[str] = set()
    texture_refs: list[str] = []
    with mtl_path.open(encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.strip()
            if line.startswith("newmtl "):
                materials.add(line.split(maxsplit=1)[1])
            elif is_mtl_texture_directive(line):
                parts = line.split()
                if len(parts) > 1:
                    texture_refs.append(parts[-1])
    return materials, texture_refs


def verify_combined_package(*, obj_path: Path, mtl_path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    materials, texture_refs = parse_defined_materials(mtl_path) if mtl_path.exists() else (set(), [])
    used_materials: set[str] = set()
    vertex_count = texcoord_count = normal_count = face_count = point_count = 0

    if not obj_path.exists():
        issues.append({"kind": "missing-output", "path": str(obj_path)})
    else:
        with obj_path.open(encoding="utf-8", errors="replace") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("v "):
                    vertex_count += 1
                elif line.startswith("vt "):
                    texcoord_count += 1
                elif line.startswith("vn "):
                    normal_count += 1
                elif line.startswith("usemtl "):
                    used_materials.add(line.split(maxsplit=1)[1])
                elif line.startswith("f "):
                    face_count += 1
                    issues.extend(validate_index_line(line, line_no, vertex_count, texcoord_count, normal_count))
                elif line.startswith("p "):
                    point_count += 1
                    issues.extend(validate_point_line(line, line_no, vertex_count))

    for material in sorted(used_materials - materials):
        issues.append({"kind": "undefined-material", "material": material})
    for texture_ref in texture_refs:
        texture_path = (mtl_path.parent / Path(texture_ref)).resolve()
        if not texture_path.exists():
            issues.append({"kind": "missing-texture", "texture": texture_ref})

    return {
        "pass": not issues,
        "issues": issues[:200],
        "issue_count": len(issues),
        "defined_materials": len(materials),
        "used_materials": len(used_materials),
        "texture_refs": len(texture_refs),
        "vertices": vertex_count,
        "texcoords": texcoord_count,
        "normals": normal_count,
        "faces": face_count,
        "point_lines": point_count,
    }


def validate_index_line(
    line: str,
    line_no: int,
    vertex_count: int,
    texcoord_count: int,
    normal_count: int,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for token in line.split()[1:]:
        parts = token.split("/")
        refs = [
            ("vertex", parts[0], vertex_count),
            ("texcoord", parts[1] if len(parts) > 1 else "", texcoord_count),
            ("normal", parts[2] if len(parts) > 2 else "", normal_count),
        ]
        for kind, value, limit in refs:
            if not value:
                continue
            index = int(value)
            if index <= 0 or index > limit:
                issues.append({"kind": f"{kind}-index-out-of-range", "line": line_no, "index": index, "limit": limit})
    return issues


def validate_point_line(line: str, line_no: int, vertex_count: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for value in line.split()[1:]:
        index = int(value)
        if index <= 0 or index > vertex_count:
            issues.append({"kind": "point-index-out-of-range", "line": line_no, "index": index, "limit": vertex_count})
    return issues


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    verify = report["verify"]
    lines = [
        "# Flythrough Combined OBJ Package",
        "",
        f"**Generated**: {report['generated_at']}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Manifest entries | {summary['manifest_entries']} |",
        f"| Combined entries | {summary['combined_entries']} |",
        f"| Skipped entries | {summary['skipped_entries']} |",
        f"| Vertices | {summary['vertices']} |",
        f"| Faces | {summary['faces']} |",
        f"| Zero-face entries | {summary['zero_face_entries']} |",
        f"| Entries emitted as point clouds | {summary['point_directive_entries']} |",
        f"| Verify pass | {summary['verify_pass']} |",
        "",
        "## Outputs",
        "",
        f"- OBJ: `{report['outputs']['obj']}`",
        f"- MTL: `{report['outputs']['mtl']}`",
        f"- JSON report: `{report['outputs']['report']}`",
        "",
        "## Texture source breakdown",
        "",
        "| Texture source | Entries |",
        "|---|---:|",
    ]
    for source, count in summary["texture_source_breakdown"].items():
        lines.append(f"| `{source}` | {count} |")

    lines.extend(
        [
            "",
            "## Verification",
            "",
            f"- Pass: `{verify['pass']}`",
            f"- Issue count: `{verify['issue_count']}`",
            f"- Defined materials: `{verify['defined_materials']}`",
            f"- Used materials: `{verify['used_materials']}`",
            f"- Texture refs: `{verify['texture_refs']}`",
            f"- Point lines: `{verify['point_lines']}`",
            "",
            "## Notes",
            "",
            "- This package is generated and should stay out of git.",
            "- Point directives are emitted for zero-face rows to preserve access to position-only geometry.",
            "- The package is intended for generic OBJ/MTL importers; current RiftFlythrough viewer integration may still need an MTL-aware load path.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--package-root", type=Path, default=DEFAULT_PACKAGE_ROOT)
    parser.add_argument("--obj-out", type=Path)
    parser.add_argument("--mtl-out", type=Path)
    parser.add_argument("--report-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument(
        "--no-point-clouds",
        action="store_true",
        help="Do not emit OBJ point directives for zero-face rows.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    package_root = args.package_root
    obj_out = args.obj_out or package_root / DEFAULT_OBJ_OUT.name
    mtl_out = args.mtl_out or package_root / DEFAULT_MTL_OUT.name
    report_out = args.report_out or package_root / DEFAULT_REPORT_OUT.name
    markdown_out = args.markdown_out or package_root / DEFAULT_MARKDOWN_OUT.name
    report = build_combined_obj_package(
        repo_root=repo_root,
        manifest_path=args.manifest,
        obj_out=obj_out,
        mtl_out=mtl_out,
        report_out=report_out,
        markdown_out=markdown_out,
        emit_points_for_zero_face=not args.no_point_clouds,
    )
    summary = report["summary"]
    print(
        "combined OBJ package: "
        f"entries={summary['combined_entries']} skipped={summary['skipped_entries']} "
        f"vertices={summary['vertices']} faces={summary['faces']} "
        f"point_entries={summary['point_directive_entries']} verify={summary['verify_pass']} "
        f"obj={report['outputs']['obj']}"
    )
    return 0 if summary["verify_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
