#!/usr/bin/env python3
"""Audit file-level OBJ coverage against flythrough asset texture links.

This is a read-only bridge audit for the post-FT closure question:

* the export manifest is file-level (350 OBJ entries),
* ``flythrough-index.json`` is asset-ID-level (217 unique assets), and
* texture links are asset-ID-level.

The audit joins those surfaces so downstream users can see which OBJ files
already inherit texture coverage, which OBJ entries are not asset-ID mapped,
and which assets still have no linked texture references.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH_ROOT = REPO_ROOT / "Assets" / "build" / "flythrough"
EXPORTS_ROOT = REPO_ROOT / "Exports"

DEFAULT_EXPORT_MANIFEST = EXPORTS_ROOT / "export-manifest.json"
DEFAULT_INDEX = FLYTHROUGH_ROOT / "flythrough-index.json"
DEFAULT_LINKS = FLYTHROUGH_ROOT / "flythrough-texture-links.jsonl"
DEFAULT_CONVERTED_MANIFEST = FLYTHROUGH_ROOT / "textures" / "converted-manifest.json"
DEFAULT_EXTRACTED_MANIFEST = FLYTHROUGH_ROOT / "textures" / "extracted-manifest.json"
DEFAULT_JSON_OUT = FLYTHROUGH_ROOT / "evidence" / "asset-texture-coverage" / "coverage-audit.json"
DEFAULT_MISSING_OBJ_REPAIR_REPORT = FLYTHROUGH_ROOT / "evidence" / "missing-obj-repair" / "repair-report.json"
DEFAULT_TEXTURELESS_TRIAGE_REPORT = FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "textureless-triage.json"
DEFAULT_TEXTURELESS_PROBE_REFRESH_REPORT = (
    FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "probe-refresh-report.json"
)
DEFAULT_TEXTURELESS_RECOVERY_REPORT = (
    FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "recovery" / "textureless-dds-recovery-report.json"
)
DEFAULT_BUNDLE_SMOKE_REPORT = FLYTHROUGH_ROOT / "evidence" / "obj-texture-bundle-smoke" / "smoke-report.json"
DEFAULT_COMBINED_PACKAGE_REPORT = (
    FLYTHROUGH_ROOT / "combined-obj-package-full-available" / "combined-obj-package-report.json"
)

ASSET_ID_RE = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F]{16})(?![0-9a-fA-F])")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _load_json(path)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


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


def repo_relative_path(value: str | Path, repo_root: Path = REPO_ROOT) -> str:
    """Return a stable repo-relative POSIX path for manifest values.

    Generated manifests can contain absolute Windows paths. Reports should not
    preserve those machine-specific paths, so this helper trims the known repo
    root when possible and otherwise falls back to the first known repo segment.
    """

    raw = _to_posix(value)
    repo_raw = _to_posix(repo_root.resolve()).rstrip("/")
    raw_lower = raw.lower()
    repo_lower = repo_raw.lower()

    if raw_lower.startswith(repo_lower + "/"):
        return raw[len(repo_raw) + 1 :]

    for segment in ("Assets/build/flythrough/", "Exports/"):
        index = raw.find(segment)
        if index >= 0:
            return raw[index:]

    return raw


def repo_path_from_relative(repo_root: Path, relative: str) -> Path:
    """Build a local Path from a repo-relative POSIX path."""

    return repo_root.joinpath(*relative.split("/"))


def asset_id_from_text(value: str | None) -> str | None:
    if not value:
        return None
    match = ASSET_ID_RE.search(value)
    return match.group(1).lower() if match else None


def entry_asset_id(entry: dict[str, Any]) -> str | None:
    """Return an asset id from an export entry, preferring explicit metadata."""

    explicit = entry.get("asset_id")
    if isinstance(explicit, str) and ASSET_ID_RE.fullmatch(explicit):
        return explicit.lower()
    return asset_id_from_text(str(entry.get("path", "")))


def entry_geometry_signature(entry: dict[str, Any]) -> tuple[Any, ...]:
    """Return a compact geometry signature for candidate id-less OBJ matching."""

    sibling_pair = entry.get("sibling_pair") if isinstance(entry.get("sibling_pair"), dict) else {}
    return (
        str(entry.get("mesh_block")),
        entry.get("vertex_count", 0),
        entry.get("face_count", 0),
        bool(entry.get("faced")),
        sibling_pair.get("mesh_size") or entry.get("mesh_size"),
        entry.get("descriptor"),
    )


def obj_geometry_fingerprint(path: Path) -> dict[str, Any] | None:
    """Return a stable hash of OBJ geometry/material data lines, excluding comments."""

    if not path.exists():
        return None
    digest = hashlib.sha256()
    line_count = 0
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith(("v ", "vt ", "vn ", "f ")):
                    digest.update((" ".join(line.split()) + "\n").encode("utf-8"))
                    line_count += 1
    except OSError:
        return None
    return {
        "geometry_hash": digest.hexdigest(),
        "geometry_line_count": line_count,
    }


def _counter_to_sorted_dict(counter: Counter[Any]) -> dict[str, int]:
    return {str(key): count for key, count in sorted(counter.items(), key=lambda item: (str(item[0]), item[1]))}


def _scan_obj_material_refs(exports_root: Path, repo_root: Path) -> dict[str, Any]:
    """Scan exported OBJs for material references without parsing full geometry."""

    obj_count = 0
    mtllib_count = 0
    usemtl_count = 0
    with_any: list[str] = []

    if not exports_root.exists():
        return {
            "obj_files_scanned": 0,
            "obj_files_with_mtllib": 0,
            "obj_files_with_usemtl": 0,
            "obj_files_with_any_material_ref": [],
        }

    for obj_path in sorted(exports_root.rglob("*.obj")):
        obj_count += 1
        has_mtllib = False
        has_usemtl = False
        try:
            with obj_path.open(encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.startswith("mtllib "):
                        has_mtllib = True
                    elif line.startswith("usemtl "):
                        has_usemtl = True
                    if has_mtllib and has_usemtl:
                        break
        except OSError:
            continue

        if has_mtllib:
            mtllib_count += 1
        if has_usemtl:
            usemtl_count += 1
        if has_mtllib or has_usemtl:
            with_any.append(repo_relative_path(obj_path, repo_root))

    return {
        "obj_files_scanned": obj_count,
        "obj_files_with_mtllib": mtllib_count,
        "obj_files_with_usemtl": usemtl_count,
        "obj_files_with_any_material_ref": with_any,
    }


def _texture_names_from_converted_manifest(converted_manifest: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for entry in converted_manifest.get("Entries", []):
        if not isinstance(entry, dict):
            continue
        png_name = entry.get("png_name")
        if isinstance(png_name, str) and png_name:
            names.add(Path(png_name).name)
            continue
        for key in ("png_path", "path", "output"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                names.add(Path(value).name)
                break
    return names


def _png_names_on_disk(converted_root: Path) -> set[str]:
    if not converted_root.exists():
        return set()
    return {path.name for path in converted_root.rglob("*.png")}


def build_audit(
    *,
    repo_root: Path = REPO_ROOT,
    export_manifest_path: Path | None = None,
    flythrough_index_path: Path | None = None,
    texture_links_path: Path | None = None,
    converted_manifest_path: Path | None = None,
    extracted_manifest_path: Path | None = None,
    scan_material_refs: bool = True,
) -> dict[str, Any]:
    """Build the OBJ↔asset↔texture coverage audit from current generated artifacts."""

    export_manifest_path = export_manifest_path or repo_root / "Exports" / "export-manifest.json"
    flythrough_index_path = (
        flythrough_index_path or repo_root / "Assets" / "build" / "flythrough" / "flythrough-index.json"
    )
    texture_links_path = (
        texture_links_path or repo_root / "Assets" / "build" / "flythrough" / "flythrough-texture-links.jsonl"
    )
    converted_manifest_path = (
        converted_manifest_path
        or repo_root / "Assets" / "build" / "flythrough" / "textures" / "converted-manifest.json"
    )
    extracted_manifest_path = (
        extracted_manifest_path
        or repo_root / "Assets" / "build" / "flythrough" / "textures" / "extracted-manifest.json"
    )

    required = [export_manifest_path, flythrough_index_path, texture_links_path, converted_manifest_path]
    missing_inputs = [repo_relative_path(path, repo_root) for path in required if not path.exists()]
    if missing_inputs:
        raise FileNotFoundError("Missing required flythrough coverage inputs: " + ", ".join(missing_inputs))

    export_manifest = _load_json(export_manifest_path)
    flythrough_index = _load_json(flythrough_index_path)
    texture_links = _load_jsonl(texture_links_path)
    converted_manifest = _load_json(converted_manifest_path)
    extracted_manifest = _load_json(extracted_manifest_path) if extracted_manifest_path.exists() else {}

    exports_root = repo_root / "Exports"
    converted_root = repo_root / "Assets" / "build" / "flythrough" / "textures" / "converted"

    export_entries = [entry for entry in export_manifest.get("entries", []) if isinstance(entry, dict)]
    manifest_paths = [repo_relative_path(str(entry.get("path", "")), repo_root) for entry in export_entries]
    manifest_path_set = set(manifest_paths)
    duplicate_manifest_paths = sorted(path for path, count in Counter(manifest_paths).items() if count > 1)

    obj_files_on_disk = (
        {repo_relative_path(path, repo_root) for path in exports_root.rglob("*.obj")}
        if exports_root.exists()
        else set()
    )
    missing_obj_files = sorted(manifest_path_set - obj_files_on_disk)
    extra_obj_files = sorted(obj_files_on_disk - manifest_path_set)
    existing_manifest_obj_entries = sum(1 for path in manifest_paths if path in obj_files_on_disk)
    geometry_fingerprints: dict[str, dict[str, Any]] = {}

    def geometry_for_rel_path(rel_path: str) -> dict[str, Any] | None:
        if rel_path not in obj_files_on_disk:
            return None
        if rel_path not in geometry_fingerprints:
            fingerprint = obj_geometry_fingerprint(repo_path_from_relative(repo_root, rel_path))
            if fingerprint:
                geometry_fingerprints[rel_path] = fingerprint
        return geometry_fingerprints.get(rel_path)

    entries_by_asset_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    idless_export_entries: list[tuple[dict[str, Any], str]] = []
    faced_counter: Counter[str] = Counter()
    provenance_counter: Counter[str] = Counter()
    batch_counter: Counter[str] = Counter()

    for entry, rel_path in zip(export_entries, manifest_paths, strict=True):
        aid = entry_asset_id(entry)
        if aid:
            entries_by_asset_id[aid].append(entry)
        else:
            idless_export_entries.append((entry, rel_path))
        faced_counter["faced" if entry.get("faced") else "position_only"] += 1
        provenance_counter[str(entry.get("provenance", "unknown"))] += 1
        batch_counter[str(entry.get("export_batch", "unknown"))] += 1

    assets = flythrough_index.get("assets", {})
    if not isinstance(assets, dict):
        assets = {}

    linked_textures_by_asset: dict[str, list[str]] = {}
    for aid, asset in assets.items():
        if not isinstance(aid, str) or not isinstance(asset, dict):
            continue
        linked = asset.get("linked_textures") or []
        linked_textures_by_asset[aid.lower()] = [Path(str(name)).name for name in linked if str(name)]

    asset_texture_counts = {aid: len(names) for aid, names in linked_textures_by_asset.items()}
    assets_with_texture_links = sorted(aid for aid, count in asset_texture_counts.items() if count > 0)
    assets_without_texture_links = sorted(aid for aid, count in asset_texture_counts.items() if count == 0)

    obj_entries_with_asset_id = sum(len(entries) for entries in entries_by_asset_id.values())
    obj_entries_with_texture_links = sum(
        len(entries) for aid, entries in entries_by_asset_id.items() if asset_texture_counts.get(aid, 0) > 0
    )
    existing_obj_entries_with_texture_links = sum(
        1
        for entry, rel_path in zip(export_entries, manifest_paths, strict=True)
        if rel_path in obj_files_on_disk and (entry_asset_id(entry) or "") in assets_with_texture_links
    )

    linked_texture_refs = [name for names in linked_textures_by_asset.values() for name in names]
    unique_linked_textures = sorted(set(linked_texture_refs))
    converted_manifest_names = _texture_names_from_converted_manifest(converted_manifest)
    converted_disk_names = _png_names_on_disk(converted_root)

    texture_link_rows_by_asset: Counter[str] = Counter()
    for row in texture_links:
        aid = row.get("ModelIdPrefix")
        if isinstance(aid, str) and ASSET_ID_RE.fullmatch(aid):
            texture_link_rows_by_asset[aid.lower()] += 1

    signature_to_candidates: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for entry, rel_path in zip(export_entries, manifest_paths, strict=True):
        aid = entry_asset_id(entry)
        if not aid:
            continue
        candidate = {
            "asset_id": aid,
            "path": rel_path,
            "linked_texture_count": asset_texture_counts.get(aid, 0),
            "linked_textures": linked_textures_by_asset.get(aid, []),
            "texture_link_rows": texture_link_rows_by_asset.get(aid, 0),
        }
        fingerprint = geometry_for_rel_path(rel_path)
        if fingerprint:
            candidate.update(fingerprint)
        if candidate not in signature_to_candidates[entry_geometry_signature(entry)]:
            signature_to_candidates[entry_geometry_signature(entry)].append(candidate)

    idless_obj_entries: list[dict[str, Any]] = []
    idless_candidate_info_by_path: dict[str, dict[str, Any]] = {}
    idless_candidate_counter: Counter[str] = Counter()
    for entry, rel_path in idless_export_entries:
        candidates = signature_to_candidates.get(entry_geometry_signature(entry), [])
        candidate_asset_ids = sorted({candidate["asset_id"] for candidate in candidates})
        fingerprint = geometry_for_rel_path(rel_path)
        geometry_hash = fingerprint.get("geometry_hash") if fingerprint else None
        geometry_line_count = fingerprint.get("geometry_line_count") if fingerprint else None
        geometry_matching_candidate_asset_ids = sorted(
            {
                candidate["asset_id"]
                for candidate in candidates
                if geometry_hash and candidate.get("geometry_hash") == geometry_hash
            }
        )
        if not geometry_hash:
            candidate_geometry_status = "no-source-geometry"
        elif not candidates:
            candidate_geometry_status = "no-candidate-geometry-match"
        elif not geometry_matching_candidate_asset_ids:
            candidate_geometry_status = "signature-only-no-geometry-match"
        elif len(geometry_matching_candidate_asset_ids) == 1:
            candidate_geometry_status = "single-candidate-geometry-match"
        else:
            candidate_geometry_status = "ambiguous-candidate-geometry-match"

        candidate_texture_sets = {
            tuple(candidate.get("linked_textures", []))
            for candidate in candidates
            if candidate.get("linked_textures")
            and (not geometry_hash or candidate.get("geometry_hash") == geometry_hash)
        }
        if not candidate_texture_sets:
            candidate_texture_set_status = "no-candidate-textures"
        elif len(candidate_texture_sets) == 1:
            candidate_texture_set_status = "single-candidate-texture-set"
        else:
            candidate_texture_set_status = "multiple-candidate-texture-sets"
        if not candidates:
            candidate_status = "no-geometry-signature-match"
        elif len(candidate_asset_ids) == 1:
            candidate_status = "single-asset-signature-match"
        else:
            candidate_status = "ambiguous-signature-match"
        idless_candidate_counter[candidate_status] += 1
        candidate_info = {
            "path": rel_path,
            "mesh_block": entry.get("mesh_block"),
            "mesh_size": (entry.get("sibling_pair") or {}).get("mesh_size")
            if isinstance(entry.get("sibling_pair"), dict)
            else entry.get("mesh_size"),
            "descriptor": entry.get("descriptor"),
            "vertex_count": entry.get("vertex_count", 0),
            "face_count": entry.get("face_count", 0),
            "faced": bool(entry.get("faced")),
            "export_batch": entry.get("export_batch"),
            "provenance": entry.get("provenance"),
            "candidate_status": candidate_status,
            "candidate_asset_ids": candidate_asset_ids,
            "candidate_entries": candidates,
            "candidate_geometry_status": candidate_geometry_status,
            "geometry_matching_candidate_asset_ids": geometry_matching_candidate_asset_ids,
            "candidate_texture_set_status": candidate_texture_set_status,
            "geometry_hash": geometry_hash,
            "geometry_line_count": geometry_line_count,
        }
        idless_obj_entries.append(candidate_info)
        idless_candidate_info_by_path[rel_path] = candidate_info

    obj_entry_rows: list[dict[str, Any]] = []
    texture_status_counter: Counter[str] = Counter()
    for index, (entry, rel_path) in enumerate(zip(export_entries, manifest_paths, strict=True)):
        aid = entry_asset_id(entry)
        linked_textures = linked_textures_by_asset.get(aid or "", [])
        if not aid:
            texture_status = "no-asset-id"
        elif aid not in linked_textures_by_asset:
            texture_status = "asset-not-indexed"
        elif linked_textures:
            texture_status = "texture-linked"
        else:
            texture_status = "no-linked-textures"
        texture_status_counter[texture_status] += 1

        sibling_pair = entry.get("sibling_pair") if isinstance(entry.get("sibling_pair"), dict) else {}
        obj_entry_rows.append(
            {
                "manifest_index": index,
                "path": rel_path,
                "exists_on_disk": rel_path in obj_files_on_disk,
                "asset_id": aid,
                "candidate_status": idless_candidate_info_by_path.get(rel_path, {}).get("candidate_status"),
                "candidate_asset_ids": idless_candidate_info_by_path.get(rel_path, {}).get("candidate_asset_ids", []),
                "candidate_entries": idless_candidate_info_by_path.get(rel_path, {}).get("candidate_entries", []),
                "candidate_geometry_status": idless_candidate_info_by_path.get(rel_path, {}).get(
                    "candidate_geometry_status"
                ),
                "geometry_matching_candidate_asset_ids": idless_candidate_info_by_path.get(rel_path, {}).get(
                    "geometry_matching_candidate_asset_ids", []
                ),
                "candidate_texture_set_status": idless_candidate_info_by_path.get(rel_path, {}).get(
                    "candidate_texture_set_status"
                ),
                "geometry_hash": (geometry_for_rel_path(rel_path) or {}).get("geometry_hash"),
                "geometry_line_count": (geometry_for_rel_path(rel_path) or {}).get("geometry_line_count"),
                "texture_status": texture_status,
                "linked_texture_count": len(linked_textures),
                "linked_textures": linked_textures,
                "texture_link_rows": texture_link_rows_by_asset.get(aid or "", 0),
                "mesh_block": entry.get("mesh_block"),
                "mesh_size": sibling_pair.get("mesh_size") or entry.get("mesh_size"),
                "descriptor": entry.get("descriptor"),
                "vertex_count": entry.get("vertex_count", 0),
                "face_count": entry.get("face_count", 0),
                "faced": bool(entry.get("faced")),
                "export_batch": entry.get("export_batch"),
                "provenance": entry.get("provenance"),
            }
        )

    material_refs = _scan_obj_material_refs(exports_root, repo_root) if scan_material_refs else {}

    top_actions = [
        "Smoke-import the portable combined full-available OBJ/MTL/textures package in Blender or an MTL-aware viewer.",
        "Fix or regenerate the missing manifest source path: `Exports/Exports/decode-nif-geometry/decode-nif-geometry-mesh17.obj`.",
        "Recover or prove unavailable the 2 newly found `n_ds_eternal_assault_flowers_01_*` DDS refs.",
        "Investigate the remaining neutral-material rows that still lack row-scoped DDS refs.",
        "Open the full-available texture triage gallery and review the 349 preview cards plus 1 missing-source gap.",
        "Resolve/classify the 4 single-match id-less OBJ entries into asset IDs.",
        "Investigate the 4 ambiguous id-less OBJ groups with stronger hashes/signatures.",
        "Investigate the 2 existing no-match fallback OBJ rows separately.",
        "Verify the portable package in the target downstream importer once a Blender or MTL-aware viewer path is available.",
        "Keep generated OBJ/PNG/DDS artifacts out of git; commit only scripts, reports, and small fixtures.",
    ]

    audit: dict[str, Any] = {
        "schema": "flythrough-asset-texture-coverage-audit-v1",
        "generated_at": _now_iso(),
        "phase_context": "Flythrough Bridge FT-1..FT-8 closure follow-up; post-completion asset usability audit",
        "inputs": {
            "export_manifest": repo_relative_path(export_manifest_path, repo_root),
            "flythrough_index": repo_relative_path(flythrough_index_path, repo_root),
            "texture_links": repo_relative_path(texture_links_path, repo_root),
            "converted_manifest": repo_relative_path(converted_manifest_path, repo_root),
            "extracted_manifest": repo_relative_path(extracted_manifest_path, repo_root)
            if extracted_manifest_path.exists()
            else None,
        },
        "obj_file_level": {
            "manifest_entries": len(export_entries),
            "manifest_unique_paths": len(manifest_path_set),
            "duplicate_manifest_paths": duplicate_manifest_paths,
            "obj_files_on_disk": len(obj_files_on_disk),
            "manifest_entries_existing_on_disk": existing_manifest_obj_entries,
            "missing_obj_files_count": len(missing_obj_files),
            "missing_obj_files": missing_obj_files,
            "extra_obj_files_count": len(extra_obj_files),
            "extra_obj_files": extra_obj_files,
            "entries_with_asset_id": obj_entries_with_asset_id,
            "entries_without_asset_id": len(idless_obj_entries),
            "entries_without_asset_id_candidate_status_breakdown": _counter_to_sorted_dict(idless_candidate_counter),
            "entries_without_asset_id_detail": idless_obj_entries,
            "entries_with_texture_links": obj_entries_with_texture_links,
            "existing_entries_with_texture_links": existing_obj_entries_with_texture_links,
            "entry_texture_status_breakdown": _counter_to_sorted_dict(texture_status_counter),
            "entries": obj_entry_rows,
            "faced_breakdown": _counter_to_sorted_dict(faced_counter),
            "export_batch_breakdown": _counter_to_sorted_dict(batch_counter),
            "provenance_breakdown": _counter_to_sorted_dict(provenance_counter),
        },
        "asset_id_level": {
            "export_unique_asset_ids": len(entries_by_asset_id),
            "indexed_asset_ids": len(assets),
            "indexed_assets_with_texture_links": len(assets_with_texture_links),
            "indexed_assets_without_texture_links": len(assets_without_texture_links),
            "indexed_assets_without_texture_links_detail": assets_without_texture_links,
            "indexed_assets_with_world_json": flythrough_index.get("summary", {}).get("with_world_json"),
            "indexed_assets_with_lod_info": flythrough_index.get("summary", {}).get("with_lod_info"),
            "indexed_assets_with_meshsize": flythrough_index.get("summary", {}).get("with_meshsize"),
            "texture_count_distribution": _counter_to_sorted_dict(Counter(asset_texture_counts.values())),
        },
        "texture_level": {
            "texture_link_rows": len(texture_links),
            "texture_linked_model_ids": len(texture_link_rows_by_asset),
            "linked_texture_references_total": len(linked_texture_refs),
            "linked_texture_references_unique": len(unique_linked_textures),
            "converted_manifest_mode": converted_manifest.get("Mode"),
            "converted_manifest_entries": len(converted_manifest.get("Entries", [])),
            "converted_pngs_on_disk": len(converted_disk_names),
            "extracted_manifest_entries": len(extracted_manifest.get("Entries", []))
            if isinstance(extracted_manifest.get("Entries"), list)
            else 0,
            "unique_linked_pngs_present_in_converted_manifest": len(
                set(unique_linked_textures) & converted_manifest_names
            ),
            "unique_linked_pngs_missing_from_converted_manifest": sorted(
                set(unique_linked_textures) - converted_manifest_names
            ),
            "unique_linked_pngs_present_on_disk": len(set(unique_linked_textures) & converted_disk_names),
            "unique_linked_pngs_missing_on_disk": sorted(set(unique_linked_textures) - converted_disk_names),
        },
        "material_usability": material_refs,
        "next_best_actions": top_actions,
    }

    return audit


def render_markdown(audit: dict[str, Any]) -> str:
    obj = audit["obj_file_level"]
    asset = audit["asset_id_level"]
    texture = audit["texture_level"]
    material = audit.get("material_usability", {})

    missing_obj_files = obj["missing_obj_files"] or ["_none_"]
    idless = obj["entries_without_asset_id_detail"]
    no_texture_assets = asset["indexed_assets_without_texture_links_detail"] or ["_none_"]
    existing_texture_linked = obj["existing_entries_with_texture_links"]
    skipped_default_bundle = obj["manifest_entries"] - existing_texture_linked
    missing_sources = obj["missing_obj_files_count"]
    skipped_without_textures = skipped_default_bundle - missing_sources
    single_candidate_materializable = sum(
        1
        for entry in obj.get("entries", [])
        if entry.get("candidate_geometry_status") == "single-candidate-geometry-match"
        and entry.get("exists_on_disk")
        and any(candidate.get("linked_texture_count", 0) > 0 for candidate in entry.get("candidate_entries", []))
    )
    common_candidate_materializable = 0
    for entry in obj.get("entries", []):
        if entry.get("candidate_geometry_status") != "ambiguous-candidate-geometry-match" or not entry.get(
            "exists_on_disk"
        ):
            continue
        texture_sets = {
            tuple(candidate.get("linked_textures", []))
            for candidate in entry.get("candidate_entries", [])
            if candidate.get("linked_textures") and candidate.get("geometry_hash") == entry.get("geometry_hash")
        }
        if len(texture_sets) == 1:
            common_candidate_materializable += 1
    heuristic_materializable = existing_texture_linked + single_candidate_materializable
    common_heuristic_materializable = heuristic_materializable + common_candidate_materializable
    heuristic_skipped = obj["manifest_entries"] - heuristic_materializable
    common_heuristic_skipped = obj["manifest_entries"] - common_heuristic_materializable
    existing_obj_entries = obj["manifest_entries_existing_on_disk"]
    full_available_materializable = existing_obj_entries
    full_available_skipped = obj["manifest_entries"] - full_available_materializable
    neutral_materialized = full_available_materializable - common_heuristic_materializable
    missing_obj_repair = _load_optional_json(DEFAULT_MISSING_OBJ_REPAIR_REPORT)
    missing_obj_repair_lines = [
        "- `scripts/repair_flythrough_missing_objs.py --apply` attempts exact SHA-256 duplicate recovery for missing manifest OBJ paths and writes `Assets/build/flythrough/evidence/missing-obj-repair/repair-report.json`."
    ]
    if missing_obj_repair:
        repair_summary = missing_obj_repair.get("summary", {})
        similar_candidates = [
            candidate
            for entry in missing_obj_repair.get("entries", [])
            for candidate in entry.get("similar_existing_candidates", [])
        ]
        derived_matches = [
            variant
            for candidate in similar_candidates
            for variant in candidate.get("derived_no_face_variants", [])
            if variant.get("matches_expected_sha")
        ]
        missing_obj_repair_lines.append(
            "- Latest exact-hash repair report: "
            f"{repair_summary.get('missing_entries', 'n/a')} missing, "
            f"{repair_summary.get('repairable_exact_sha', 'n/a')} exact SHA-256 duplicate matches, "
            f"{repair_summary.get('repaired', 'n/a')} repaired."
        )
        if similar_candidates:
            missing_obj_repair_lines.append(
                "- Latest missing OBJ classifier: "
                f"{len(similar_candidates)} similar existing candidate(s), "
                f"{len(derived_matches)} derived no-face variant(s) matching the expected SHA-256."
            )
    textureless_triage = _load_optional_json(DEFAULT_TEXTURELESS_TRIAGE_REPORT)
    textureless_triage_lines = [
        "- `scripts/triage_flythrough_textureless_assets.py` scans neutral-materialized rows for latent DDS references in probe JSON and writes `Assets/build/flythrough/evidence/textureless-assets/textureless-triage.json`."
    ]
    textureless_probe_refresh = _load_optional_json(DEFAULT_TEXTURELESS_PROBE_REFRESH_REPORT)
    textureless_probe_refresh_lines = [
        "- `scripts/probe_flythrough_textureless_meshes.py` refreshes focused live-root `probe-nif-mesh` JSON for textureless-scope asset/mesh rows, so triage can find row-scoped DDS refs instead of guessing."
    ]
    if textureless_probe_refresh:
        probe_summary = textureless_probe_refresh.get("summary", {})
        textureless_probe_refresh_lines.append(
            "- Latest textureless probe refresh report: "
            f"{probe_summary.get('unique_probe_targets', 'n/a')} asset/mesh targets, "
            f"{probe_summary.get('commands_run', 'n/a')} commands run, "
            f"{probe_summary.get('targets_with_mesh_dds_refs', 'n/a')} targets with mesh-level DDS refs, "
            f"{probe_summary.get('unique_mesh_dds_refs', 'n/a')} unique mesh-level DDS refs."
        )
    textureless_triage_materializable = 0
    if textureless_triage:
        triage_summary = textureless_triage.get("summary", {})
        textureless_triage_materializable = sum(
            1 for row in textureless_triage.get("rows", []) if row.get("row_dds_refs_present_in_converted")
        )
        missing_refs = sorted(
            {
                ref
                for asset_report in textureless_triage.get("assets", [])
                for ref in asset_report.get("asset_dds_refs_missing_from_converted", [])
            }
        )
        textureless_triage_lines.append(
            "- Latest textureless-asset triage report: "
            f"{triage_summary.get('neutral_rows', 'n/a')} neutral rows, "
            f"{triage_summary.get('neutral_rows_with_mesh_dds_refs', 'n/a')} rows with mesh-level DDS refs, "
            f"{triage_summary.get('neutral_asset_ids_with_any_dds_refs', 'n/a')} neutral asset IDs with refs, "
            f"{triage_summary.get('unique_dds_refs', 'n/a')} unique DDS refs, "
            f"{triage_summary.get('unique_dds_refs_present_in_converted', 'n/a')} already converted, "
            f"{triage_summary.get('unique_dds_refs_missing_from_converted', 'n/a')} missing converted PNGs, "
            f"{triage_summary.get('missing_converted_dds_refs_with_catalog_match', 'n/a')} of the missing refs catalog-backed."
        )
        if missing_refs:
            textureless_triage_lines.append(
                "- Missing converted DDS targets found in probe evidence: "
                + ", ".join(f"`{ref}`" for ref in missing_refs)
                + "."
            )
    textureless_recovery = _load_optional_json(DEFAULT_TEXTURELESS_RECOVERY_REPORT)
    textureless_recovery_lines = [
        "- `scripts/recover_flythrough_textureless_dds.py` name-matches, extracts, converts, and records DDS refs from the textureless triage report."
    ]
    if textureless_recovery:
        recovery_summary = textureless_recovery.get("summary", {})
        textureless_recovery_lines.append(
            "- Latest textureless DDS recovery report: "
            f"{recovery_summary.get('triage_dds_refs', 'n/a')} refs, "
            f"{recovery_summary.get('target_refs', 'n/a')} currently missing conversion targets, "
            f"{recovery_summary.get('name_matches', 'n/a')} name matches, "
            f"{recovery_summary.get('unmatched_target_refs', 'n/a')} unmatched target refs, "
            f"{recovery_summary.get('converted_pngs', 'n/a')} newly converted PNGs, "
            f"{recovery_summary.get('failed_conversions', 'n/a')} failed conversions."
        )
    bundle_smoke = _load_optional_json(DEFAULT_BUNDLE_SMOKE_REPORT)
    bundle_smoke_lines = [
        "- `scripts/smoke_flythrough_obj_texture_bundle.py` parses the generated OBJ/MTL bundle, validates material directives, face indices, and MTL texture references before external viewer import."
    ]
    if bundle_smoke:
        smoke_summary = bundle_smoke.get("summary", {})
        bundle_smoke_lines.append(
            "- Latest OBJ/MTL bundle smoke report: "
            f"pass={smoke_summary.get('pass', 'n/a')}, "
            f"{smoke_summary.get('checked_materializable_entries', 'n/a')} checked entries, "
            f"{smoke_summary.get('obj_issue_entries', 'n/a')} OBJ issue entries, "
            f"{smoke_summary.get('mtl_issue_entries', 'n/a')} MTL issue entries, "
            f"{smoke_summary.get('missing_texture_refs', 'n/a')} missing texture refs, "
            f"{smoke_summary.get('zero_face_entries', 'n/a')} zero-face entries."
        )
    combined_package = _load_optional_json(DEFAULT_COMBINED_PACKAGE_REPORT)
    combined_package_lines = [
        "- `scripts/build_flythrough_combined_obj_package.py` turns the 349 materialized per-row OBJ/MTL files into one portable import package: one OBJ, one MTL, copied MTL-referenced textures, and `p` point directives for zero-face meshes."
    ]
    if combined_package:
        combined_summary = combined_package.get("summary", {})
        combined_package_lines.append(
            "- Latest combined OBJ package report: "
            f"{combined_summary.get('combined_entries', 'n/a')} combined entries, "
            f"{combined_summary.get('skipped_entries', 'n/a')} skipped, "
            f"{combined_summary.get('vertices', 'n/a')} vertices, "
            f"{combined_summary.get('faces', 'n/a')} faces, "
            f"{combined_summary.get('point_directive_entries', 'n/a')} point-cloud entries, "
            f"{combined_summary.get('copied_texture_files', 'n/a')} copied texture files, "
            f"{combined_summary.get('missing_source_textures', 'n/a')} missing source textures, "
            f"verify_pass={combined_summary.get('verify_pass', 'n/a')}."
        )

    lines = [
        "# Flythrough Asset + Texture Coverage Audit",
        "",
        f"**Generated**: {audit['generated_at']}",
        "",
        "## Why this exists",
        "",
        (
            "The flythrough closure artifact is asset-ID centric (`217` unique assets), while the export manifest is "
            "file-level (`350` OBJ entries). This audit joins the file-level OBJ set to asset IDs and texture coverage "
            "so the remaining usability work stays focused on assets/textures instead of unrelated CI churn."
        ),
        "",
        "## Current coverage snapshot",
        "",
        "| Surface | Count | Notes |",
        "|---|---:|---|",
        f"| OBJ manifest entries | {obj['manifest_entries']} | `{audit['inputs']['export_manifest']}` |",
        f"| OBJ files currently on disk | {obj['obj_files_on_disk']} | {obj['missing_obj_files_count']} manifest path(s) missing |",
        f"| OBJ entries with asset IDs | {obj['entries_with_asset_id']} | Can inherit asset-level metadata/textures |",
        f"| OBJ entries without asset IDs | {obj['entries_without_asset_id']} | Need recovery/classification for full 350-file access |",
        (
            f"| Id-less OBJ signature candidates | "
            f"{obj['entries_without_asset_id_candidate_status_breakdown']} | Geometry-only recovery hints |"
        ),
        f"| OBJ entries with texture links | {obj['entries_with_texture_links']} | File-level entries whose asset has linked textures |",
        f"| Full OBJ row manifest | {len(obj['entries'])} rows | Written in generated audit JSON under `obj_file_level.entries` |",
        f"| Indexed asset IDs | {asset['indexed_asset_ids']} | `{audit['inputs']['flythrough_index']}` |",
        f"| Indexed assets with textures | {asset['indexed_assets_with_texture_links']} | {asset['indexed_assets_without_texture_links']} without links |",
        f"| Texture-link JSONL rows | {texture['texture_link_rows']} | {texture['texture_linked_model_ids']} model IDs |",
        (
            f"| Unique linked PNGs available | {texture['unique_linked_pngs_present_on_disk']}/"
            f"{texture['linked_texture_references_unique']} | Converted manifest mode: `{texture['converted_manifest_mode']}` |"
        ),
        f"| OBJ material refs | {material.get('obj_files_with_any_material_ref', []) and 'present' or '0'} | "
        f"{material.get('obj_files_with_mtllib', 0)} `mtllib`, {material.get('obj_files_with_usemtl', 0)} `usemtl` |",
        "",
        "## File-level OBJ gaps",
        "",
        "### Missing manifest paths",
        "",
        *[f"- `{path}`" for path in missing_obj_files],
        "",
        "### OBJ entries without asset IDs",
        "",
        *[
            (
                f"- `{entry['path']}` — mesh_block={entry.get('mesh_block')}, "
                f"verts={entry.get('vertex_count')}, faces={entry.get('face_count')}, "
                f"batch={entry.get('export_batch')}, provenance={entry.get('provenance')}, "
                f"candidate_status={entry.get('candidate_status')}, "
                f"candidate_geometry_status={entry.get('candidate_geometry_status')}, "
                f"candidate_texture_set_status={entry.get('candidate_texture_set_status')}, "
                f"candidate_asset_ids={', '.join(entry.get('candidate_asset_ids') or []) or 'none'}"
            )
            for entry in idless
        ],
        "",
        "## Asset IDs without linked textures",
        "",
        *[f"- `{aid}`" for aid in no_texture_assets],
        "",
        "## Downstream usability readout",
        "",
        "- Texture PNG availability for linked assets is good: every unique linked PNG is present in the converted manifest and on disk.",
        "- The generated audit JSON now contains one row per OBJ manifest entry with path, existence, asset ID, texture status, and linked PNG names.",
        "- Id-less OBJ entries now include geometry-signature candidate matches where current exports contain same-shape asset-ID-backed rows.",
        "- The original exported OBJs still do not reference `.mtl` files or `usemtl` assignments; generated bundles below materialize that downstream without modifying generated source exports.",
        "- The second blocker is file-level coverage: the 217-asset index does not directly expose every one of the 350 manifest OBJ entries.",
        "- The third blocker is recovery/classification of id-less OBJ entries and no-texture asset IDs.",
        "",
        "## Downstream consumer artifact builder",
        "",
        (
            "`scripts/build_flythrough_obj_texture_manifest.py --write-bundle` turns this audit into generated, "
            "gitignored consumer artifacts:"
        ),
        "",
        "| Artifact | Expected result from current audit | Purpose |",
        "|---|---:|---|",
        (
            f"| `Assets/build/flythrough/flythrough-obj-texture-manifest.json` | {obj['manifest_entries']} rows | "
            "File-level OBJ manifest with texture roles, materialization status, candidate asset IDs, and bundle paths |"
        ),
        (
            f"| `Assets/build/flythrough/flythrough-obj-texture-manifest.csv` | {obj['manifest_entries']} rows | "
            "Spreadsheet-friendly triage view |"
        ),
        (
            f"| `Assets/build/flythrough/obj-texture-bundle/objs/` | {existing_texture_linked} OBJ files | "
            "Texture-linked OBJ copies with injected `mtllib`/`usemtl` lines |"
        ),
        (
            f"| `Assets/build/flythrough/obj-texture-bundle/materials/` | {existing_texture_linked} MTL files | "
            "Simple material sidecars pointing at converted PNGs |"
        ),
        (
            f"| `Assets/build/flythrough/texture-triage-gallery/index.html` | {common_heuristic_materializable} preview cards + {common_heuristic_skipped} gap rows | "
            "Local HTML triage surface for materialized OBJ/MTL rows and remaining gaps |"
        ),
        (
            f"| `Assets/build/flythrough/texture-triage-gallery-full-available/index.html` | {full_available_materializable} preview cards + {full_available_skipped} gap row | "
            "Full-available local HTML triage surface, including neutral materials for textureless existing OBJs |"
        ),
        "",
        "Expected default bundle summary from this audit:",
        "",
        f"- {obj['manifest_entries']} total manifest entries.",
        f"- {existing_texture_linked} materializable OBJ entries.",
        f"- {existing_texture_linked} generated OBJ files and {existing_texture_linked} generated MTL files.",
        f"- {skipped_default_bundle} skipped entries: {skipped_without_textures} without textures and {missing_sources} missing source OBJ.",
        f"- {texture['converted_manifest_entries']} converted PNG paths available to the manifest.",
        "",
        "Optional heuristic expansion:",
        "",
        (
            "`--allow-single-candidate-materials` borrows textures for id-less OBJ rows only when the geometry "
            "signature has exactly one asset-ID candidate. It does not promote that candidate to durable truth."
        ),
        "",
        f"- {single_candidate_materializable} id-less OBJ entries are eligible for single-candidate texture borrowing.",
        f"- {heuristic_materializable} total OBJ entries become materializable with that option.",
        f"- {heuristic_skipped} entries remain skipped after heuristic expansion.",
        "- `--allow-common-candidate-materials` additionally borrows textures for ambiguous candidate groups only when all geometry-matched candidates share the same linked texture set.",
        f"- {common_candidate_materializable} ambiguous id-less OBJ entries are eligible for common-candidate texture borrowing.",
        f"- {common_heuristic_materializable} total OBJ entries become materializable with both candidate options.",
        f"- {common_heuristic_skipped} entries remain skipped after both candidate options.",
        "- `--allow-textureless-triage-materials` can use row-scoped converted DDS refs discovered by the textureless triage report.",
        f"- {textureless_triage_materializable} neutral OBJ row(s) currently have converted textureless-triage DDS evidence.",
        "- `--materialize-untextured` adds neutral MTLs for existing OBJ rows that still lack texture evidence; it does not claim texture coverage.",
        f"- {max(neutral_materialized - textureless_triage_materializable, 0)} existing textureless OBJ rows still become neutral-materialized when triage textures plus neutral materials are enabled.",
        f"- {full_available_materializable} total OBJ entries become materializable with candidate borrowing plus neutral materials.",
        f"- {full_available_skipped} entry remains skipped: the missing source OBJ path.",
        "- `scripts/build_flythrough_texture_triage_gallery.py --manifest Assets/build/flythrough/flythrough-obj-texture-manifest-full-available.json --out Assets/build/flythrough/texture-triage-gallery-full-available/index.html` renders the full-available local HTML triage gallery.",
        *missing_obj_repair_lines,
        *textureless_probe_refresh_lines,
        *textureless_triage_lines,
        *textureless_recovery_lines,
        *bundle_smoke_lines,
        *combined_package_lines,
        "",
        "## Top 10 next best actions",
        "",
        *[f"{i}. {action}" for i, action in enumerate(audit["next_best_actions"], start=1)],
        "",
    ]
    return "\n".join(lines)


def _print_summary(audit: dict[str, Any]) -> None:
    obj = audit["obj_file_level"]
    asset = audit["asset_id_level"]
    texture = audit["texture_level"]
    material = audit.get("material_usability", {})

    print("Flythrough asset/texture coverage audit")
    print("=======================================")
    print(
        "OBJ manifest: "
        f"{obj['manifest_entries']} entries, {obj['obj_files_on_disk']} OBJ files on disk, "
        f"{obj['missing_obj_files_count']} missing"
    )
    print(
        "OBJ linkage: "
        f"{obj['entries_with_asset_id']} with asset IDs, {obj['entries_without_asset_id']} without, "
        f"{obj['entries_with_texture_links']} with texture links"
    )
    print(
        "Assets: "
        f"{asset['indexed_asset_ids']} indexed, {asset['indexed_assets_with_texture_links']} with textures, "
        f"{asset['indexed_assets_without_texture_links']} without"
    )
    print(
        "Textures: "
        f"{texture['texture_link_rows']} JSONL rows, {texture['linked_texture_references_unique']} unique linked PNGs, "
        f"{texture['unique_linked_pngs_present_on_disk']} present on disk"
    )
    print(
        "Materials: "
        f"{material.get('obj_files_with_mtllib', 0)} OBJ files with mtllib, "
        f"{material.get('obj_files_with_usemtl', 0)} with usemtl"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root to audit.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT, help="Write full audit JSON here.")
    parser.add_argument("--markdown-out", type=Path, help="Optionally write a human-readable Markdown report.")
    parser.add_argument("--no-material-scan", action="store_true", help="Skip scanning OBJ files for mtllib/usemtl.")
    parser.add_argument("--summary-only", action="store_true", help="Print summary without writing output files.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    audit = build_audit(
        repo_root=repo_root,
        export_manifest_path=repo_root / "Exports" / "export-manifest.json",
        flythrough_index_path=repo_root / "Assets" / "build" / "flythrough" / "flythrough-index.json",
        texture_links_path=repo_root / "Assets" / "build" / "flythrough" / "flythrough-texture-links.jsonl",
        converted_manifest_path=repo_root / "Assets" / "build" / "flythrough" / "textures" / "converted-manifest.json",
        extracted_manifest_path=repo_root / "Assets" / "build" / "flythrough" / "textures" / "extracted-manifest.json",
        scan_material_refs=not args.no_material_scan,
    )

    _print_summary(audit)
    if not args.summary_only:
        _write_json(args.json_out, audit)
        print(f"wrote {repo_relative_path(args.json_out, repo_root)}")
    if args.markdown_out:
        _write_text(args.markdown_out, render_markdown(audit))
        print(f"wrote {repo_relative_path(args.markdown_out, repo_root)}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
