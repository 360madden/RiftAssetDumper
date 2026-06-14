#!/usr/bin/env python3
"""Build downstream-friendly OBJ↔texture manifests and optional OBJ/MTL bundles.

The flythrough audit establishes truth about the 350 OBJ export entries. This
script turns that truth into a consumer artifact:

* a 350-row JSON manifest,
* an optional CSV triage sheet, and
* an optional generated OBJ/MTL bundle for entries that already have texture
  links.

Generated files stay under ``Assets/build/flythrough`` and must not be
committed.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_flythrough_asset_texture_coverage import (  # noqa: E402
    DEFAULT_CONVERTED_MANIFEST,
    build_audit,
    repo_path_from_relative,
    repo_relative_path,
)

FLYTHROUGH_ROOT = REPO_ROOT / "Assets" / "build" / "flythrough"
DEFAULT_MANIFEST_OUT = FLYTHROUGH_ROOT / "flythrough-obj-texture-manifest.json"
DEFAULT_CSV_OUT = FLYTHROUGH_ROOT / "flythrough-obj-texture-manifest.csv"
DEFAULT_BUNDLE_ROOT = FLYTHROUGH_ROOT / "obj-texture-bundle"

SLUG_RE = re.compile(r"[^a-zA-Z0-9_.-]+")


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


def _to_posix(value: str | Path) -> str:
    return str(value).replace("\\", "/")


def safe_slug(value: str, *, max_len: int = 96) -> str:
    slug = SLUG_RE.sub("_", value.strip()).strip("._-").lower()
    return (slug or "item")[:max_len]


def texture_name_from_path_or_name(value: str) -> str:
    return Path(value.replace("\\", "/")).name


def load_converted_texture_paths(
    converted_manifest_path: Path = DEFAULT_CONVERTED_MANIFEST,
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, str]:
    """Return PNG basename -> repo-relative converted PNG path."""

    manifest = _load_json(converted_manifest_path)
    out: dict[str, str] = {}
    for entry in manifest.get("Entries", []):
        if not isinstance(entry, dict):
            continue
        name = entry.get("png_name")
        path_value = entry.get("png_path") or entry.get("path") or entry.get("output")
        if isinstance(name, str) and name:
            if isinstance(path_value, str) and path_value:
                out[Path(name).name] = normalize_converted_texture_path(path_value, repo_root=repo_root)
            else:
                out[Path(name).name] = f"Assets/build/flythrough/textures/converted/{Path(name).name}"
            continue
        if isinstance(path_value, str) and path_value:
            out[texture_name_from_path_or_name(path_value)] = normalize_converted_texture_path(
                path_value,
                repo_root=repo_root,
            )
    return out


def normalize_converted_texture_path(path_value: str, *, repo_root: Path = REPO_ROOT) -> str:
    rel = repo_relative_path(path_value, repo_root)
    if rel.startswith("textures/converted/"):
        return f"Assets/build/flythrough/{rel}"
    return rel


def classify_texture_role(texture_name: str) -> str:
    """Classify a converted PNG basename into a practical material role."""

    stem = Path(texture_name).stem.lower()
    parts = stem.split("_")
    suffix = parts[-1] if parts else stem

    if suffix in {"n", "nm", "normal"} or "normal" in stem or "norm" in stem:
        return "normal"
    if suffix in {"s", "spec", "specular"} or "spec" in stem:
        return "specular"
    if suffix in {"m", "mask"} or "mask" in stem:
        return "mask"
    if suffix in {"a", "alpha"} or "alpha" in stem or "opacity" in stem:
        return "alpha"
    if suffix in {"g", "glow"} or "glow" in stem or "emiss" in stem:
        return "emissive"
    if suffix in {"c", "d", "diff", "diffuse", "albedo", "color"}:
        return "diffuse"
    if "sky" in stem or "gradient" in stem or "blank" in stem or "white" in stem:
        return "diffuse"
    return "unknown"


def choose_material_textures(linked_textures: list[str]) -> dict[str, str]:
    """Choose one texture per material role, including a diffuse fallback."""

    chosen: dict[str, str] = {}
    unknowns: list[str] = []
    for texture_name in linked_textures:
        name = texture_name_from_path_or_name(texture_name)
        role = classify_texture_role(name)
        if role == "unknown":
            unknowns.append(name)
            continue
        chosen.setdefault(role, name)

    if "diffuse" not in chosen:
        for fallback_role in ("unknown", "emissive", "specular", "normal", "mask", "alpha"):
            if fallback_role == "unknown" and unknowns:
                chosen["diffuse"] = unknowns[0]
                break
            if fallback_role in chosen:
                chosen["diffuse"] = chosen[fallback_role]
                break
    return chosen


def material_name_for_entry(entry: dict[str, Any]) -> str:
    aid = entry.get("asset_id") or "idless"
    return safe_slug(f"mat_{int(entry['manifest_index']):03d}_{aid}")


def build_manifest(
    *,
    repo_root: Path = REPO_ROOT,
    audit: dict[str, Any] | None = None,
    converted_texture_paths: dict[str, str] | None = None,
    bundle_root: Path = DEFAULT_BUNDLE_ROOT,
) -> dict[str, Any]:
    """Build a 350-row downstream OBJ texture manifest."""

    audit = audit or build_audit(repo_root=repo_root)
    converted_texture_paths = converted_texture_paths or load_converted_texture_paths(repo_root=repo_root)
    bundle_rel = repo_relative_path(bundle_root, repo_root)

    entries: list[dict[str, Any]] = []
    materializable = 0
    missing_source = 0
    no_texture = 0

    for entry in audit["obj_file_level"]["entries"]:
        linked_texture_names = [texture_name_from_path_or_name(name) for name in entry.get("linked_textures", [])]
        texture_rows = [
            {
                "name": name,
                "path": converted_texture_paths.get(name),
                "role": classify_texture_role(name),
                "available": name in converted_texture_paths,
            }
            for name in linked_texture_names
        ]
        chosen = choose_material_textures(linked_texture_names)
        material_name = material_name_for_entry(entry)
        source_exists = bool(entry.get("exists_on_disk"))
        has_textures = bool(linked_texture_names)
        can_materialize = source_exists and has_textures and bool(chosen.get("diffuse"))
        if can_materialize:
            materializable += 1
        elif not source_exists:
            missing_source += 1
        elif not has_textures:
            no_texture += 1

        source_obj = entry["path"]
        obj_slug = safe_slug(
            f"{int(entry['manifest_index']):03d}_{entry.get('asset_id') or 'idless'}_{Path(source_obj).stem}"
        )
        bundled_obj = f"{bundle_rel}/objs/{obj_slug}.obj"
        bundled_mtl = f"{bundle_rel}/materials/{material_name}.mtl"

        entries.append(
            {
                "manifest_index": entry["manifest_index"],
                "source_obj": source_obj,
                "source_exists": source_exists,
                "asset_id": entry.get("asset_id"),
                "candidate_asset_ids": entry.get("candidate_asset_ids", []),
                "texture_status": entry.get("texture_status"),
                "linked_texture_count": len(linked_texture_names),
                "linked_textures": texture_rows,
                "chosen_material_textures": chosen,
                "materializable": can_materialize,
                "material_name": material_name if can_materialize else None,
                "bundled_obj": bundled_obj if can_materialize else None,
                "bundled_mtl": bundled_mtl if can_materialize else None,
                "mesh_block": entry.get("mesh_block"),
                "mesh_size": entry.get("mesh_size"),
                "descriptor": entry.get("descriptor"),
                "vertex_count": entry.get("vertex_count", 0),
                "face_count": entry.get("face_count", 0),
                "faced": bool(entry.get("faced")),
                "export_batch": entry.get("export_batch"),
                "provenance": entry.get("provenance"),
            }
        )

    return {
        "schema": "flythrough-obj-texture-manifest-v1",
        "generated_at": _now_iso(),
        "source_audit_schema": audit.get("schema"),
        "summary": {
            "total_entries": len(entries),
            "materializable_entries": materializable,
            "entries_missing_source_obj": missing_source,
            "entries_without_textures": no_texture,
            "converted_texture_paths": len(converted_texture_paths),
            "bundle_root": bundle_rel,
            "texture_status_breakdown": audit["obj_file_level"].get("entry_texture_status_breakdown", {}),
            "idless_candidate_status_breakdown": audit["obj_file_level"].get(
                "entries_without_asset_id_candidate_status_breakdown", {}
            ),
        },
        "entries": entries,
    }


def mtl_lines(material_name: str, chosen_textures: dict[str, str], *, mtl_path: Path, repo_root: Path) -> list[str]:
    lines = [
        f"newmtl {material_name}",
        "Ka 1.000000 1.000000 1.000000",
        "Kd 1.000000 1.000000 1.000000",
        "Ks 0.100000 0.100000 0.100000",
        "Ns 10.000000",
        "d 1.000000",
        "illum 2",
    ]

    role_to_statement = {
        "diffuse": "map_Kd",
        "specular": "map_Ks",
        "normal": "bump",
        "alpha": "map_d",
        "emissive": "map_Ke",
    }
    for role, statement in role_to_statement.items():
        texture_name = chosen_textures.get(role)
        if not texture_name:
            continue
        texture_path = repo_root / "Assets" / "build" / "flythrough" / "textures" / "converted" / texture_name
        rel = os.path.relpath(texture_path, mtl_path.parent).replace("\\", "/")
        lines.append(f"{statement} {rel}")
    return lines


def obj_with_material_text(source_obj: Path, *, mtllib: str, material_name: str) -> str:
    text = source_obj.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    body = [line for line in lines if not line.startswith("mtllib ") and not line.startswith("usemtl ")]
    header = [f"mtllib {mtllib}", f"usemtl {material_name}"]
    return "\n".join(header + body) + "\n"


def write_bundle(
    manifest: dict[str, Any], *, repo_root: Path = REPO_ROOT, bundle_root: Path = DEFAULT_BUNDLE_ROOT
) -> dict[str, Any]:
    """Write generated OBJ/MTL files for materializable manifest entries."""

    objs_dir = bundle_root / "objs"
    materials_dir = bundle_root / "materials"
    objs_dir.mkdir(parents=True, exist_ok=True)
    materials_dir.mkdir(parents=True, exist_ok=True)

    written_objs = 0
    written_mtls = 0
    skipped = 0

    for entry in manifest["entries"]:
        if not entry.get("materializable"):
            skipped += 1
            continue
        source_obj = repo_path_from_relative(repo_root, entry["source_obj"])
        if not source_obj.exists():
            skipped += 1
            continue

        out_obj = repo_path_from_relative(repo_root, entry["bundled_obj"])
        out_mtl = repo_path_from_relative(repo_root, entry["bundled_mtl"])
        out_obj.parent.mkdir(parents=True, exist_ok=True)
        out_mtl.parent.mkdir(parents=True, exist_ok=True)

        mtl_text = "\n".join(
            mtl_lines(
                entry["material_name"],
                entry["chosen_material_textures"],
                mtl_path=out_mtl,
                repo_root=repo_root,
            )
        )
        out_mtl.write_text(mtl_text + "\n", encoding="utf-8", newline="\n")
        written_mtls += 1

        mtllib_rel = os.path.relpath(out_mtl, out_obj.parent).replace("\\", "/")
        out_obj.write_text(
            obj_with_material_text(source_obj, mtllib=mtllib_rel, material_name=entry["material_name"]),
            encoding="utf-8",
            newline="\n",
        )
        written_objs += 1

    return {
        "bundle_root": repo_relative_path(bundle_root, repo_root),
        "written_objs": written_objs,
        "written_mtls": written_mtls,
        "skipped_entries": skipped,
    }


def write_csv(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "manifest_index",
        "source_obj",
        "source_exists",
        "asset_id",
        "candidate_asset_ids",
        "texture_status",
        "linked_texture_count",
        "materializable",
        "material_name",
        "bundled_obj",
        "bundled_mtl",
        "mesh_block",
        "mesh_size",
        "vertex_count",
        "face_count",
        "faced",
        "export_batch",
        "provenance",
    ]
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in manifest["entries"]:
            row = {key: entry.get(key) for key in fieldnames}
            row["candidate_asset_ids"] = ";".join(entry.get("candidate_asset_ids") or [])
            writer.writerow(row)
    tmp.replace(path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root.")
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST_OUT, help="Output JSON manifest path.")
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV_OUT, help="Output CSV manifest path.")
    parser.add_argument("--no-csv", action="store_true", help="Skip writing the CSV triage sheet.")
    parser.add_argument("--write-bundle", action="store_true", help="Generate OBJ/MTL bundle for materializable rows.")
    parser.add_argument("--bundle-root", type=Path, default=DEFAULT_BUNDLE_ROOT, help="Generated OBJ/MTL bundle root.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    manifest = build_manifest(repo_root=repo_root, bundle_root=args.bundle_root)
    _write_json(args.manifest_out, manifest)
    print(f"wrote {repo_relative_path(args.manifest_out, repo_root)}")
    if not args.no_csv:
        write_csv(args.csv_out, manifest)
        print(f"wrote {repo_relative_path(args.csv_out, repo_root)}")
    if args.write_bundle:
        result = write_bundle(manifest, repo_root=repo_root, bundle_root=args.bundle_root)
        manifest["summary"]["bundle_write"] = result
        _write_json(args.manifest_out, manifest)
        print(
            "bundle: "
            f"{result['written_objs']} OBJ, {result['written_mtls']} MTL, "
            f"{result['skipped_entries']} skipped under {result['bundle_root']}"
        )
    summary = manifest["summary"]
    print(
        "summary: "
        f"{summary['total_entries']} entries, {summary['materializable_entries']} materializable, "
        f"{summary['entries_without_textures']} without textures, {summary['entries_missing_source_obj']} missing source"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
