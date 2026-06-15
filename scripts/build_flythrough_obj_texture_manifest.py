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
DEFAULT_TEXTURELESS_TRIAGE_REPORT = FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "textureless-triage.json"
DEFAULT_SOURCE_SUBSTITUTIONS = FLYTHROUGH_ROOT / "evidence" / "missing-obj-repair" / "source-substitutions.json"

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


def load_converted_dds_to_png_names(converted_manifest_path: Path = DEFAULT_CONVERTED_MANIFEST) -> dict[str, str]:
    """Return normalized DDS basename -> converted PNG basename."""

    manifest = _load_json(converted_manifest_path)
    out: dict[str, str] = {}
    for entry in manifest.get("Entries", []):
        if not isinstance(entry, dict):
            continue
        png_name = entry.get("png_name")
        original_basename = entry.get("original_basename")
        if not isinstance(png_name, str) or not png_name:
            continue
        if isinstance(original_basename, str) and original_basename:
            dds_name = original_basename.lower()
            if not dds_name.endswith(".dds"):
                dds_name += ".dds"
            out[dds_name] = Path(png_name).name
    return out


def textureless_triage_row_textures(
    triage_report_path: Path = DEFAULT_TEXTURELESS_TRIAGE_REPORT,
    *,
    converted_manifest_path: Path = DEFAULT_CONVERTED_MANIFEST,
) -> dict[int, list[str]]:
    """Return manifest index -> converted PNGs found through textureless DDS triage."""

    if not triage_report_path.exists():
        return {}
    report = _load_json(triage_report_path)
    dds_to_png = load_converted_dds_to_png_names(converted_manifest_path)
    out: dict[int, list[str]] = {}
    for row in report.get("rows", []):
        if not isinstance(row, dict):
            continue
        manifest_index = row.get("manifest_index")
        if not isinstance(manifest_index, int):
            continue
        textures = [
            dds_to_png[ref] for ref in row.get("row_dds_refs", []) if isinstance(ref, str) and ref in dds_to_png
        ]
        if textures:
            out[manifest_index] = sorted(set(textures))
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


def asset_texture_names_by_id(audit: dict[str, Any]) -> dict[str, list[str]]:
    """Return asset ID -> linked texture names from asset-backed audit rows."""

    out: dict[str, list[str]] = {}
    for entry in audit["obj_file_level"]["entries"]:
        aid = entry.get("asset_id")
        if not isinstance(aid, str) or not aid:
            continue
        names = [texture_name_from_path_or_name(name) for name in entry.get("linked_textures", [])]
        if names and aid not in out:
            out[aid] = names
    return out


def candidate_ids_for_texture_borrowing(entry: dict[str, Any]) -> list[str]:
    geometry_matches = entry.get("geometry_matching_candidate_asset_ids")
    if isinstance(geometry_matches, list) and geometry_matches:
        return [str(asset_id) for asset_id in geometry_matches]
    candidate_asset_ids = entry.get("candidate_asset_ids", [])
    if isinstance(candidate_asset_ids, list):
        return [str(asset_id) for asset_id in candidate_asset_ids]
    return []


def common_candidate_texture_names(entry: dict[str, Any], asset_textures: dict[str, list[str]]) -> list[str]:
    texture_sets = {
        tuple(asset_textures[asset_id])
        for asset_id in candidate_ids_for_texture_borrowing(entry)
        if asset_textures.get(asset_id)
    }
    if len(texture_sets) == 1:
        return list(next(iter(texture_sets)))
    return []


def load_source_substitutions(path: Path, *, repo_root: Path = REPO_ROOT) -> dict[int, dict[str, Any]]:
    """Return manifest index -> replacement source OBJ metadata.

    Source substitutions are intentionally explicit and opt-in. They are for
    practical downstream access to a generated review bundle when exact source
    recovery is not proven; callers should keep ``durable_truth`` false unless
    an exact source repair has been independently proven.
    """

    if not path.exists():
        return {}
    data = _load_json(path)
    out: dict[int, dict[str, Any]] = {}
    for row in data.get("entries", []):
        if not isinstance(row, dict):
            continue
        manifest_index = row.get("manifest_index")
        replacement = row.get("replacement_source_obj")
        if not isinstance(manifest_index, int) or not isinstance(replacement, str) or not replacement:
            continue
        normalized = dict(row)
        normalized["replacement_source_obj"] = repo_relative_path(replacement, repo_root)
        normalized.setdefault("durable_truth", False)
        out[manifest_index] = normalized
    return out


def build_manifest(
    *,
    repo_root: Path = REPO_ROOT,
    audit: dict[str, Any] | None = None,
    converted_texture_paths: dict[str, str] | None = None,
    bundle_root: Path = DEFAULT_BUNDLE_ROOT,
    allow_single_candidate_materials: bool = False,
    allow_common_candidate_materials: bool = False,
    allow_textureless_triage_materials: bool = False,
    textureless_triage_report_path: Path = DEFAULT_TEXTURELESS_TRIAGE_REPORT,
    converted_manifest_path: Path = DEFAULT_CONVERTED_MANIFEST,
    materialize_untextured: bool = False,
    source_substitutions: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a 350-row downstream OBJ texture manifest."""

    audit = audit or build_audit(repo_root=repo_root)
    converted_texture_paths = converted_texture_paths or load_converted_texture_paths(repo_root=repo_root)
    asset_textures = asset_texture_names_by_id(audit)
    bundle_rel = repo_relative_path(bundle_root, repo_root)

    entries: list[dict[str, Any]] = []
    materializable = 0
    missing_source = 0
    no_texture = 0
    single_candidate_materialized = 0
    common_candidate_materialized = 0
    textureless_triage_materialized = 0
    untextured_materialized = 0
    entries_lacking_texture_links = 0
    original_missing_source = 0
    source_substituted_entries = 0
    source_substitution_replacement_missing = 0
    textureless_triage_textures = (
        textureless_triage_row_textures(
            textureless_triage_report_path,
            converted_manifest_path=converted_manifest_path,
        )
        if allow_textureless_triage_materials
        else {}
    )

    for entry in audit["obj_file_level"]["entries"]:
        manifest_index = int(entry["manifest_index"])
        original_source_obj = entry["path"]
        original_source_exists = bool(entry.get("exists_on_disk"))
        if not original_source_exists:
            original_missing_source += 1

        source_obj = original_source_obj
        source_exists = original_source_exists
        source_substitution = None
        requested_substitution = (source_substitutions or {}).get(manifest_index)
        if requested_substitution:
            replacement_source_obj = repo_relative_path(
                requested_substitution["replacement_source_obj"],
                repo_root,
            )
            replacement_exists = repo_path_from_relative(repo_root, replacement_source_obj).exists()
            source_substitution = {
                **requested_substitution,
                "replacement_source_obj": replacement_source_obj,
                "replacement_source_exists": replacement_exists,
                "replaces_source_obj": original_source_obj,
                "status": "active" if replacement_exists else "replacement-missing",
            }
            if replacement_exists:
                source_obj = replacement_source_obj
                source_exists = True
                source_substituted_entries += 1
            else:
                source_substitution_replacement_missing += 1

        linked_texture_names = [texture_name_from_path_or_name(name) for name in entry.get("linked_textures", [])]
        texture_source = "asset-id" if linked_texture_names else "none"
        borrowed_texture_asset_id = None
        candidate_asset_ids = entry.get("candidate_asset_ids", [])
        if (
            allow_single_candidate_materials
            and not linked_texture_names
            and not entry.get("asset_id")
            and len(candidate_ids_for_texture_borrowing(entry)) == 1
        ):
            candidate_asset_id = candidate_ids_for_texture_borrowing(entry)[0]
            candidate_textures = asset_textures.get(candidate_asset_id, [])
            if candidate_textures:
                linked_texture_names = candidate_textures
                texture_source = "single-candidate-heuristic"
                borrowed_texture_asset_id = candidate_asset_id
        elif allow_common_candidate_materials and not linked_texture_names and not entry.get("asset_id"):
            candidate_textures = common_candidate_texture_names(entry, asset_textures)
            candidate_ids = candidate_ids_for_texture_borrowing(entry)
            if candidate_textures and len(candidate_ids) > 1:
                linked_texture_names = candidate_textures
                texture_source = "common-candidate-textures"
                borrowed_texture_asset_id = ",".join(candidate_ids)
        if allow_textureless_triage_materials and not linked_texture_names:
            triage_textures = textureless_triage_textures.get(int(entry["manifest_index"]), [])
            if triage_textures:
                linked_texture_names = triage_textures
                texture_source = "textureless-triage-probe"

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
        has_textures = bool(linked_texture_names)
        if not has_textures:
            entries_lacking_texture_links += 1
        can_materialize = source_exists and (
            (has_textures and bool(chosen.get("diffuse"))) or (materialize_untextured and not has_textures)
        )
        if can_materialize and not has_textures:
            texture_source = "untextured-neutral"
        if can_materialize:
            materializable += 1
            if texture_source == "single-candidate-heuristic":
                single_candidate_materialized += 1
            if texture_source == "common-candidate-textures":
                common_candidate_materialized += 1
            if texture_source == "textureless-triage-probe":
                textureless_triage_materialized += 1
            if texture_source == "untextured-neutral":
                untextured_materialized += 1
        elif not source_exists:
            missing_source += 1
        elif not has_textures:
            no_texture += 1

        obj_slug = safe_slug(f"{manifest_index:03d}_{entry.get('asset_id') or 'idless'}_{Path(source_obj).stem}")
        bundled_obj = f"{bundle_rel}/objs/{obj_slug}.obj"
        bundled_mtl = f"{bundle_rel}/materials/{material_name}.mtl"

        entries.append(
            {
                "manifest_index": manifest_index,
                "source_obj": source_obj,
                "source_exists": source_exists,
                "original_source_obj": original_source_obj if source_obj != original_source_obj else None,
                "original_source_exists": original_source_exists,
                "source_substitution": source_substitution,
                "asset_id": entry.get("asset_id"),
                "candidate_asset_ids": candidate_asset_ids,
                "candidate_status": entry.get("candidate_status"),
                "texture_status": entry.get("texture_status"),
                "texture_source": texture_source,
                "borrowed_texture_asset_id": borrowed_texture_asset_id,
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
            "entries_missing_original_source_obj": original_missing_source,
            "source_substituted_entries": source_substituted_entries,
            "source_substitution_replacement_missing": source_substitution_replacement_missing,
            "entries_without_textures": no_texture,
            "entries_lacking_texture_links": entries_lacking_texture_links,
            "allow_single_candidate_materials": allow_single_candidate_materials,
            "allow_common_candidate_materials": allow_common_candidate_materials,
            "allow_textureless_triage_materials": allow_textureless_triage_materials,
            "materialize_untextured": materialize_untextured,
            "single_candidate_materialized_entries": single_candidate_materialized,
            "common_candidate_materialized_entries": common_candidate_materialized,
            "textureless_triage_materialized_entries": textureless_triage_materialized,
            "untextured_materialized_entries": untextured_materialized,
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


def _obj_attribute_counts(lines: list[str]) -> tuple[int, int, int]:
    vertices = sum(1 for line in lines if line.startswith("v "))
    texture_coords = sum(1 for line in lines if line.startswith("vt "))
    normals = sum(1 for line in lines if line.startswith("vn "))
    return vertices, texture_coords, normals


def _positive_index_in_bounds(value: str, count: int) -> bool:
    try:
        index = int(value)
    except ValueError:
        return False
    return 1 <= index <= count


def normalize_face_token_for_available_attributes(token: str, *, texture_coord_count: int, normal_count: int) -> str:
    """Drop OBJ face UV/normal references when the referenced arrays are absent.

    Some source OBJs use ``v/vt/vn`` face tokens even when no ``vn`` lines were
    emitted. Many viewers are tolerant, but downstream importers can reject
    those dangling normal references. The generated consumer bundle should be
    stricter than the raw source exports, so it only preserves UV/normal indices
    that point at available arrays.
    """

    parts = token.split("/")
    vertex = parts[0]
    texture_coord = parts[1] if len(parts) > 1 and parts[1] else None
    normal = parts[2] if len(parts) > 2 and parts[2] else None

    keep_texture_coord = (
        texture_coord is not None
        and texture_coord_count > 0
        and _positive_index_in_bounds(texture_coord, texture_coord_count)
    )
    keep_normal = normal is not None and normal_count > 0 and _positive_index_in_bounds(normal, normal_count)

    if keep_normal:
        return f"{vertex}/{texture_coord if keep_texture_coord else ''}/{normal}"
    if keep_texture_coord:
        return f"{vertex}/{texture_coord}"
    return vertex


def normalize_obj_faces_for_available_attributes(lines: list[str]) -> list[str]:
    _, texture_coord_count, normal_count = _obj_attribute_counts(lines)
    normalized: list[str] = []
    for line in lines:
        if not line.startswith("f "):
            normalized.append(line)
            continue
        tokens = line.split()
        normalized.append(
            " ".join(
                [tokens[0]]
                + [
                    normalize_face_token_for_available_attributes(
                        token,
                        texture_coord_count=texture_coord_count,
                        normal_count=normal_count,
                    )
                    for token in tokens[1:]
                ]
            )
        )
    return normalized


def obj_with_material_text(source_obj: Path, *, mtllib: str, material_name: str) -> str:
    text = source_obj.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    body = normalize_obj_faces_for_available_attributes(
        [line for line in lines if not line.startswith("mtllib ") and not line.startswith("usemtl ")]
    )
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


def verify_bundle(manifest: dict[str, Any], *, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify generated OBJ/MTL files and MTL texture references for materializable rows."""

    checked_entries = 0
    objs_present = 0
    mtls_present = 0
    obj_material_refs_ok = 0
    texture_refs_checked = 0
    missing_outputs: list[str] = []
    missing_texture_refs: list[str] = []

    map_statements = {"map_Kd", "map_Ks", "bump", "map_d", "map_Ke"}

    for entry in manifest["entries"]:
        if not entry.get("materializable"):
            continue
        checked_entries += 1
        obj_path = repo_path_from_relative(repo_root, entry["bundled_obj"])
        mtl_path = repo_path_from_relative(repo_root, entry["bundled_mtl"])

        if obj_path.exists():
            objs_present += 1
            obj_lines = obj_path.read_text(encoding="utf-8", errors="replace").splitlines()
            expected_mtllib = os.path.relpath(mtl_path, obj_path.parent).replace("\\", "/")
            if f"mtllib {expected_mtllib}" in obj_lines[:5] and f"usemtl {entry['material_name']}" in obj_lines[:5]:
                obj_material_refs_ok += 1
        else:
            missing_outputs.append(repo_relative_path(obj_path, repo_root))

        if mtl_path.exists():
            mtls_present += 1
            for line in mtl_path.read_text(encoding="utf-8", errors="replace").splitlines():
                parts = line.strip().split(maxsplit=1)
                if len(parts) != 2 or parts[0] not in map_statements:
                    continue
                texture_refs_checked += 1
                texture_path = (mtl_path.parent / parts[1]).resolve()
                if not texture_path.exists():
                    missing_texture_refs.append(repo_relative_path(texture_path, repo_root))
        else:
            missing_outputs.append(repo_relative_path(mtl_path, repo_root))

    return {
        "checked_entries": checked_entries,
        "objs_present": objs_present,
        "mtls_present": mtls_present,
        "obj_material_refs_ok": obj_material_refs_ok,
        "texture_refs_checked": texture_refs_checked,
        "missing_outputs_count": len(missing_outputs),
        "missing_outputs": missing_outputs[:50],
        "missing_texture_refs_count": len(missing_texture_refs),
        "missing_texture_refs": missing_texture_refs[:50],
        "pass": (
            checked_entries == objs_present
            and checked_entries == mtls_present
            and checked_entries == obj_material_refs_ok
            and not missing_texture_refs
        ),
    }


def write_csv(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "manifest_index",
        "source_obj",
        "source_exists",
        "original_source_obj",
        "original_source_exists",
        "source_substitution_status",
        "asset_id",
        "candidate_asset_ids",
        "candidate_status",
        "texture_status",
        "texture_source",
        "borrowed_texture_asset_id",
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
            substitution = entry.get("source_substitution") or {}
            row["source_substitution_status"] = substitution.get("status")
            writer.writerow(row)
    tmp.replace(path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root.")
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST_OUT, help="Output JSON manifest path.")
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV_OUT, help="Output CSV manifest path.")
    parser.add_argument("--no-csv", action="store_true", help="Skip writing the CSV triage sheet.")
    parser.add_argument("--write-bundle", action="store_true", help="Generate OBJ/MTL bundle for materializable rows.")
    parser.add_argument(
        "--allow-single-candidate-materials",
        action="store_true",
        help="For id-less OBJ entries with exactly one geometry-signature asset candidate, borrow that asset's textures.",
    )
    parser.add_argument(
        "--allow-common-candidate-materials",
        action="store_true",
        help="For id-less OBJ entries with multiple candidates, borrow textures only when all candidates share one texture set.",
    )
    parser.add_argument(
        "--allow-textureless-triage-materials",
        action="store_true",
        help="Use converted DDS refs from textureless probe triage as row-scoped material evidence.",
    )
    parser.add_argument(
        "--textureless-triage-report",
        type=Path,
        default=DEFAULT_TEXTURELESS_TRIAGE_REPORT,
        help="Textureless triage report JSON used by --allow-textureless-triage-materials.",
    )
    parser.add_argument(
        "--converted-manifest",
        type=Path,
        default=DEFAULT_CONVERTED_MANIFEST,
        help="Converted texture manifest used for textureless triage DDS→PNG mapping.",
    )
    parser.add_argument(
        "--materialize-untextured",
        action="store_true",
        help="Generate neutral MTL/OBJ bundle rows for existing OBJs that still have no texture links.",
    )
    parser.add_argument(
        "--source-substitutions",
        type=Path,
        default=None,
        help=(
            "Optional flythrough-source-substitutions-v1 JSON. Replaces missing source OBJs with explicit "
            "generated candidate OBJs for practical review without promoting durable source truth."
        ),
    )
    parser.add_argument(
        "--verify-bundle", action="store_true", help="Verify generated OBJ/MTL outputs and texture refs."
    )
    parser.add_argument("--bundle-root", type=Path, default=DEFAULT_BUNDLE_ROOT, help="Generated OBJ/MTL bundle root.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    manifest = build_manifest(
        repo_root=repo_root,
        bundle_root=args.bundle_root,
        allow_single_candidate_materials=args.allow_single_candidate_materials,
        allow_common_candidate_materials=args.allow_common_candidate_materials,
        allow_textureless_triage_materials=args.allow_textureless_triage_materials,
        textureless_triage_report_path=args.textureless_triage_report,
        converted_manifest_path=args.converted_manifest,
        materialize_untextured=args.materialize_untextured,
        source_substitutions=load_source_substitutions(args.source_substitutions, repo_root=repo_root)
        if args.source_substitutions
        else None,
    )
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
    if args.write_bundle or args.verify_bundle:
        result = verify_bundle(manifest, repo_root=repo_root)
        manifest["summary"]["bundle_verify"] = result
        _write_json(args.manifest_out, manifest)
        print(
            "verify: "
            f"pass={result['pass']} checked={result['checked_entries']} "
            f"missing_outputs={result['missing_outputs_count']} "
            f"missing_textures={result['missing_texture_refs_count']}"
        )
    summary = manifest["summary"]
    print(
        "summary: "
        f"{summary['total_entries']} entries, {summary['materializable_entries']} materializable, "
        f"{summary['entries_without_textures']} without textures, "
        f"{summary['entries_missing_source_obj']} missing source, "
        f"{summary['source_substituted_entries']} source-substituted, "
        f"{summary['single_candidate_materialized_entries']} single-candidate materialized, "
        f"{summary['common_candidate_materialized_entries']} common-candidate materialized, "
        f"{summary['textureless_triage_materialized_entries']} textureless-triage materialized, "
        f"{summary['untextured_materialized_entries']} untextured-neutral materialized"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
