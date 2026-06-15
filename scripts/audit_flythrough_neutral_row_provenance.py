#!/usr/bin/env python3
"""Audit provenance for neutral-material rows in the practical 350 OBJ package.

The practical package can materialize all 350 OBJ rows, but the remaining
neutral review materials still need sharper asset/texture direction. This
report answers the next asset-access question: are the neutral rows blocked on
normal texture links, missing probes, missing asset identity, or practical
source substitution truth?

Generated reports stay under ``Assets/build/flythrough`` and must not be
committed.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH_ROOT = REPO_ROOT / "Assets" / "build" / "flythrough"

DEFAULT_MANIFEST = FLYTHROUGH_ROOT / "flythrough-obj-texture-manifest-practical-350-texture-fallbacks.json"
DEFAULT_TEXTURE_GAP_REPORT = (
    FLYTHROUGH_ROOT / "evidence" / "practical-350-texture-fallbacks" / "texture-gap-report.json"
)
DEFAULT_UNRESOLVED_TEXTURE_REPORT = (
    FLYTHROUGH_ROOT / "evidence" / "practical-350-texture-fallbacks" / "unresolved-texture-evidence-report.json"
)
DEFAULT_ASSETS64_ENTRIES = REPO_ROOT / "Exports" / "assets64.entries.jsonl"
DEFAULT_PROBE_REFRESH_REPORT = FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "probe-refresh-report.json"
DEFAULT_JSON_OUT = (
    FLYTHROUGH_ROOT / "evidence" / "practical-350-texture-fallbacks" / "neutral-row-provenance-report.json"
)
DEFAULT_MARKDOWN_OUT = FLYTHROUGH_ROOT / "evidence" / "practical-350-texture-fallbacks" / "NEUTRAL_ROW_PROVENANCE.md"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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


def repo_path_from_relative(repo_root: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(str(value))
    if path.is_absolute():
        return path
    return repo_root.joinpath(*_to_posix(path).split("/"))


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def _load_optional_json(path: Path) -> dict[str, Any]:
    return _load_json(path) if path.exists() else {}


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


def _counter_to_sorted_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _compact_asset_manifest_entry(row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "Index",
        "IdPrefix",
        "FilenameFnv1Hash",
        "PakIndex",
        "PakOffset",
        "CompressedSize",
        "Size",
        "NameLength",
        "Hash",
        "Bitfield1",
        "Bitfield2",
        "UnknownByte",
        "Language",
    )
    return {key: row.get(key) for key in keys if key in row}


def load_assets64_entries(path: Path, asset_ids: set[str]) -> dict[str, list[dict[str, Any]]]:
    """Load compact assets64 metadata for the target IDs only."""

    targets = {asset_id.lower() for asset_id in asset_ids if asset_id}
    if not path.exists() or not targets:
        return {}

    found: dict[str, list[dict[str, Any]]] = defaultdict(list)
    remaining = set(targets)
    with path.open(encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            if not remaining and all(found.values()):
                break
            line_lower = line.lower()
            if not any(asset_id in line_lower for asset_id in remaining):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            asset_id = row.get("IdPrefix")
            if not isinstance(asset_id, str):
                continue
            asset_id = asset_id.lower()
            if asset_id not in targets:
                continue
            found[asset_id].append(_compact_asset_manifest_entry(row))
            remaining.discard(asset_id)
    return dict(sorted(found.items()))


def _entries_by_index(manifest: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for entry in manifest.get("entries", []):
        if isinstance(entry, dict) and isinstance(entry.get("manifest_index"), int):
            out[int(entry["manifest_index"])] = entry
    return out


def _neutral_gap_rows(texture_gap_report: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [row for row in texture_gap_report.get("neutral_rows", []) if isinstance(row, dict)]
    if rows:
        return sorted(rows, key=lambda row: int(row.get("manifest_index", -1)))
    manifest_rows = [
        entry
        for entry in manifest.get("entries", [])
        if isinstance(entry, dict) and entry.get("texture_source") == "untextured-neutral"
    ]
    return sorted(manifest_rows, key=lambda row: int(row.get("manifest_index", -1)))


def unresolved_assets_by_id(unresolved_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in unresolved_report.get("neutral_assets", []):
        if not isinstance(row, dict):
            continue
        asset_id = row.get("asset_id")
        if isinstance(asset_id, str) and asset_id:
            out[asset_id.lower()] = row
    return out


def probe_targets_by_index(probe_refresh_report: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for target in probe_refresh_report.get("targets", []):
        if not isinstance(target, dict):
            continue
        for manifest_index in target.get("manifest_indices", []):
            if isinstance(manifest_index, int):
                out[manifest_index] = target
    return out


def _compact_probe_target(target: dict[str, Any] | None) -> dict[str, Any] | None:
    if not target:
        return None
    keys = (
        "asset_id",
        "mesh_block",
        "manifest_indices",
        "source_objs",
        "texture_sources",
        "output",
        "status",
        "action",
        "probe_exists",
        "meshes_emitted",
        "candidate_links",
        "pairings",
        "attribute_sets",
        "mesh_dds_refs",
        "asset_dds_refs",
    )
    return {key: target.get(key) for key in keys if key in target}


def _count_or_value(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, (list, dict, tuple, set)):
        return len(value)
    return None


def _mesh_block_matches(mesh: dict[str, Any], mesh_block: str | int | None) -> bool:
    if mesh_block is None:
        return False
    return str(mesh.get("MeshBlockIndex")) == str(mesh_block)


def _summarize_probe_file(repo_root: Path, output: str | Path | None, mesh_block: str | int | None) -> dict[str, Any]:
    path = repo_path_from_relative(repo_root, output)
    if path is None:
        return {"path": None, "exists": False}
    rel_path = repo_relative_path(path, repo_root=repo_root)
    if not path.exists():
        return {"path": rel_path, "exists": False}
    try:
        probe = _load_json(path)
    except OSError, json.JSONDecodeError:
        return {"path": rel_path, "exists": True, "parse_error": True}

    meshes = [mesh for mesh in probe.get("Meshes", []) if isinstance(mesh, dict)]
    selected_mesh = next((mesh for mesh in meshes if _mesh_block_matches(mesh, mesh_block)), None)
    string_samples = [str(value) for value in (selected_mesh or {}).get("StringSamples", []) if isinstance(value, str)]
    dds_strings = sorted({sample for sample in string_samples if sample.lower().endswith(".dds")})
    streams = [stream for stream in (selected_mesh or {}).get("Streams", []) if isinstance(stream, dict)]
    role_counts = Counter(
        str(stream.get("RoleStats", {}).get("PrimaryRole"))
        for stream in streams
        if isinstance(stream.get("RoleStats"), dict) and stream.get("RoleStats", {}).get("PrimaryRole")
    )
    source = probe.get("Source") if isinstance(probe.get("Source"), dict) else {}

    return {
        "path": rel_path,
        "exists": True,
        "parse_error": False,
        "source": {
            key: source.get(key)
            for key in (
                "ArchiveName",
                "EntryIndex",
                "IdPrefix",
                "ManifestEntryIndex",
                "PakIndex",
                "PakOffset",
                "SourceKind",
            )
            if key in source
        },
        "length": probe.get("Length"),
        "nif_version": probe.get("NifVersion"),
        "mesh_block_count": probe.get("MeshBlockCount"),
        "meshes_emitted": probe.get("MeshesEmitted"),
        "candidate_links": _count_or_value(probe.get("CandidateLinks")),
        "pairings": _count_or_value(probe.get("Pairings")),
        "ghidra_pairings": _count_or_value(probe.get("GhidraPairings")),
        "attribute_sets": _count_or_value(probe.get("AttributeSets")),
        "header_warning_count": len(probe.get("HeaderWarnings", []) or []),
        "selected_mesh": {
            "mesh_block": selected_mesh.get("MeshBlockIndex") if selected_mesh else None,
            "mesh_size": selected_mesh.get("MeshSize") if selected_mesh else None,
            "mesh_data_offset": selected_mesh.get("MeshDataOffset") if selected_mesh else None,
            "stream_count": len(streams),
            "string_sample_count": len(string_samples),
            "dds_strings": dds_strings,
            "stream_role_counts": _counter_to_sorted_dict(role_counts),
        },
    }


def _source_substitution_candidate_id(entry: dict[str, Any]) -> str | None:
    substitution = entry.get("source_substitution")
    if not isinstance(substitution, dict):
        return None
    candidate = substitution.get("candidate_asset_id")
    return candidate.lower() if isinstance(candidate, str) and candidate else None


def classify_neutral_row(
    *,
    entry: dict[str, Any],
    gap_row: dict[str, Any],
    probe_target: dict[str, Any] | None,
    texture_link_row_count: int,
) -> tuple[str, str]:
    if entry.get("source_substitution"):
        return (
            "source-substitution-provenance-gap",
            "Prove or replace the practical source substitute before trying to promote texture truth.",
        )
    if not entry.get("asset_id"):
        return (
            "idless-provenance-gap",
            "Recover asset identity/source provenance first; texture assignment is not durable without it.",
        )
    mesh_refs = [ref for ref in (probe_target or {}).get("mesh_dds_refs", []) if isinstance(ref, str)]
    row_refs = [ref for ref in gap_row.get("row_dds_refs", []) if isinstance(ref, str)]
    if row_refs or mesh_refs:
        return (
            "mesh-dds-refs-unmaterialized",
            "Recover exact DDS materialization for the mesh-level refs before using a neutral material.",
        )
    if texture_link_row_count > 0:
        return (
            "has-texture-link-rows-needs-manifest-wiring",
            "Reconcile existing texture-link evidence with this manifest row.",
        )
    if probe_target and probe_target.get("probe_exists") is True:
        return (
            "asset-backed-probed-no-mesh-or-link-textures",
            "Inspect parent, non-mesh, or provenance references; normal mesh/link evidence is empty.",
        )
    return (
        "asset-backed-needs-focused-probe",
        "Refresh focused NIF probe evidence for this asset/mesh before classifying it as textureless.",
    )


def _review_material_kind(entry: dict[str, Any]) -> str | None:
    review = entry.get("review_material")
    if isinstance(review, dict):
        kind = review.get("kind")
        return str(kind) if kind else None
    return None


def _build_provenance_row(
    *,
    repo_root: Path,
    entry: dict[str, Any],
    gap_row: dict[str, Any],
    asset_entries: dict[str, list[dict[str, Any]]],
    unresolved_assets: dict[str, dict[str, Any]],
    probe_target: dict[str, Any] | None,
) -> dict[str, Any]:
    asset_id = entry.get("asset_id")
    asset_id_key = asset_id.lower() if isinstance(asset_id, str) and asset_id else None
    texture_link_row_count = 0
    if asset_id_key and asset_id_key in unresolved_assets:
        texture_link_row_count = int(unresolved_assets[asset_id_key].get("texture_link_row_count") or 0)
    classification, next_action = classify_neutral_row(
        entry=entry,
        gap_row=gap_row,
        probe_target=probe_target,
        texture_link_row_count=texture_link_row_count,
    )
    candidate_id = _source_substitution_candidate_id(entry)
    compact_target = _compact_probe_target(probe_target)
    probe_file = _summarize_probe_file(repo_root, (compact_target or {}).get("output"), entry.get("mesh_block"))
    return {
        "manifest_index": entry.get("manifest_index"),
        "asset_id": asset_id,
        "source_obj": entry.get("source_obj"),
        "original_source_obj": entry.get("original_source_obj"),
        "mesh_block": entry.get("mesh_block"),
        "mesh_size": entry.get("mesh_size"),
        "vertex_count": entry.get("vertex_count"),
        "face_count": entry.get("face_count"),
        "faced": entry.get("faced"),
        "texture_status": entry.get("texture_status"),
        "texture_source": entry.get("texture_source"),
        "review_material_kind": _review_material_kind(entry),
        "review_material": entry.get("review_material"),
        "row_dds_refs": sorted(str(ref) for ref in gap_row.get("row_dds_refs", []) if isinstance(ref, str)),
        "mesh_dds_refs": sorted(
            str(ref) for ref in (probe_target or {}).get("mesh_dds_refs", []) if isinstance(ref, str)
        ),
        "asset_dds_refs": sorted(
            str(ref) for ref in (probe_target or {}).get("asset_dds_refs", []) if isinstance(ref, str)
        ),
        "texture_link_row_count": texture_link_row_count,
        "asset_manifest_entries": asset_entries.get(asset_id_key or "", []),
        "source_substitution": entry.get("source_substitution"),
        "source_substitution_candidate_asset_id": candidate_id,
        "source_substitution_candidate_manifest_entries": asset_entries.get(candidate_id or "", []),
        "probe_target": compact_target,
        "probe_file": probe_file,
        "classification": classification,
        "next_best_action": next_action,
        "durable_texture_truth": False,
    }


def _group_asset_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        asset_id = row.get("asset_id")
        if isinstance(asset_id, str) and asset_id:
            grouped[asset_id.lower()].append(row)

    out: list[dict[str, Any]] = []
    for asset_id, asset_rows in sorted(grouped.items()):
        mesh_refs = sorted({ref for row in asset_rows for ref in row.get("mesh_dds_refs", [])})
        asset_refs = sorted({ref for row in asset_rows for ref in row.get("asset_dds_refs", [])})
        probe_paths = sorted(
            {str(row.get("probe_file", {}).get("path")) for row in asset_rows if row.get("probe_file", {}).get("path")}
        )
        classifications = Counter(str(row.get("classification")) for row in asset_rows)
        first = asset_rows[0]
        probe_target = first.get("probe_target") or {}
        out.append(
            {
                "asset_id": asset_id,
                "manifest_indices": [row.get("manifest_index") for row in asset_rows],
                "mesh_blocks": sorted({str(row.get("mesh_block")) for row in asset_rows if row.get("mesh_block")}),
                "row_count": len(asset_rows),
                "asset_manifest_entries": first.get("asset_manifest_entries", []),
                "texture_link_row_count": max(int(row.get("texture_link_row_count") or 0) for row in asset_rows),
                "probe_outputs": probe_paths,
                "probe_exists": any(row.get("probe_file", {}).get("exists") for row in asset_rows),
                "candidate_links": probe_target.get("candidate_links"),
                "pairings": probe_target.get("pairings"),
                "attribute_sets": probe_target.get("attribute_sets"),
                "mesh_dds_refs": mesh_refs,
                "asset_dds_refs": asset_refs,
                "classification_counts": _counter_to_sorted_dict(classifications),
                "next_best_action": first.get("next_best_action"),
            }
        )
    return out


def build_neutral_row_provenance_report(
    *,
    repo_root: Path = REPO_ROOT,
    manifest: dict[str, Any] | None = None,
    manifest_path: Path = DEFAULT_MANIFEST,
    texture_gap_report_path: Path = DEFAULT_TEXTURE_GAP_REPORT,
    unresolved_texture_report_path: Path = DEFAULT_UNRESOLVED_TEXTURE_REPORT,
    assets64_entries_path: Path = DEFAULT_ASSETS64_ENTRIES,
    probe_refresh_report_path: Path = DEFAULT_PROBE_REFRESH_REPORT,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    manifest = manifest or _load_json(manifest_path)
    texture_gap_report = _load_optional_json(texture_gap_report_path)
    unresolved_report = _load_optional_json(unresolved_texture_report_path)
    probe_refresh_report = _load_optional_json(probe_refresh_report_path)

    entries_by_index = _entries_by_index(manifest)
    gap_rows = _neutral_gap_rows(texture_gap_report, manifest)
    unresolved_assets = unresolved_assets_by_id(unresolved_report)
    probe_by_index = probe_targets_by_index(probe_refresh_report)

    asset_ids: set[str] = set()
    for gap_row in gap_rows:
        entry = entries_by_index.get(int(gap_row.get("manifest_index", -1)), gap_row)
        asset_id = entry.get("asset_id")
        if isinstance(asset_id, str) and asset_id:
            asset_ids.add(asset_id.lower())
        candidate_id = _source_substitution_candidate_id(entry)
        if candidate_id:
            asset_ids.add(candidate_id)
    asset_entries = load_assets64_entries(assets64_entries_path, asset_ids)

    provenance_rows: list[dict[str, Any]] = []
    for gap_row in gap_rows:
        manifest_index = gap_row.get("manifest_index")
        entry = entries_by_index.get(int(manifest_index), gap_row) if isinstance(manifest_index, int) else gap_row
        provenance_rows.append(
            _build_provenance_row(
                repo_root=repo_root,
                entry=entry,
                gap_row=gap_row,
                asset_entries=asset_entries,
                unresolved_assets=unresolved_assets,
                probe_target=probe_by_index.get(int(manifest_index)) if isinstance(manifest_index, int) else None,
            )
        )

    classification_counts = Counter(str(row["classification"]) for row in provenance_rows)
    review_counts = Counter(
        str(row.get("review_material_kind")) for row in provenance_rows if row.get("review_material_kind")
    )
    unique_asset_ids = sorted({str(row["asset_id"]).lower() for row in provenance_rows if row.get("asset_id")})
    source_candidate_ids = sorted(
        {
            str(row["source_substitution_candidate_asset_id"]).lower()
            for row in provenance_rows
            if row.get("source_substitution_candidate_asset_id")
        }
    )
    rows_with_probe_files = [
        row
        for row in provenance_rows
        if row.get("probe_file", {}).get("exists") and not row.get("probe_file", {}).get("parse_error")
    ]
    rows_with_asset_manifest = [row for row in provenance_rows if row.get("asset_manifest_entries")]
    rows_with_texture_link_rows = [row for row in provenance_rows if int(row.get("texture_link_row_count") or 0) > 0]
    rows_with_mesh_dds_refs = [row for row in provenance_rows if row.get("mesh_dds_refs") or row.get("row_dds_refs")]
    source_substituted_rows = [row for row in provenance_rows if row.get("source_substitution")]

    return {
        "schema": "flythrough-neutral-row-provenance-v1",
        "generated_at": _now_iso(),
        "inputs": {
            "manifest": repo_relative_path(manifest_path, repo_root=repo_root),
            "texture_gap_report": repo_relative_path(texture_gap_report_path, repo_root=repo_root),
            "unresolved_texture_report": repo_relative_path(unresolved_texture_report_path, repo_root=repo_root),
            "assets64_entries": repo_relative_path(assets64_entries_path, repo_root=repo_root),
            "probe_refresh_report": repo_relative_path(probe_refresh_report_path, repo_root=repo_root),
        },
        "summary": {
            "neutral_rows": len(provenance_rows),
            "asset_backed_neutral_rows": len([row for row in provenance_rows if row.get("asset_id")]),
            "idless_neutral_rows": len([row for row in provenance_rows if not row.get("asset_id")]),
            "source_substituted_neutral_rows": len(source_substituted_rows),
            "unique_neutral_asset_ids": len(unique_asset_ids),
            "source_substitution_candidate_asset_ids": len(source_candidate_ids),
            "neutral_asset_rows_with_assets64_manifest_entry": len(rows_with_asset_manifest),
            "neutral_rows_with_probe_file": len(rows_with_probe_files),
            "neutral_rows_with_mesh_dds_refs": len(rows_with_mesh_dds_refs),
            "neutral_rows_with_texture_link_rows": len(rows_with_texture_link_rows),
            "asset_backed_rows_with_no_mesh_or_link_textures": classification_counts.get(
                "asset-backed-probed-no-mesh-or-link-textures", 0
            ),
        },
        "classification_counts": _counter_to_sorted_dict(classification_counts),
        "review_material_counts": _counter_to_sorted_dict(review_counts),
        "unique_neutral_asset_ids": unique_asset_ids,
        "source_substitution_candidate_asset_ids": source_candidate_ids,
        "asset_groups": _group_asset_rows(provenance_rows),
        "rows": provenance_rows,
        "source_reports": {
            "texture_gap_summary": texture_gap_report.get("summary", {}),
            "unresolved_texture_summary": unresolved_report.get("summary", {}),
            "probe_refresh_summary": probe_refresh_report.get("summary", {}),
        },
    }


def _format_code_list(values: list[Any]) -> str:
    clean = [str(value) for value in values if value not in (None, "")]
    return ", ".join(f"`{value}`" for value in clean) if clean else "none"


def _asset_manifest_note(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "missing"
    first = entries[0]
    return (
        f"Index {first.get('Index')}, pak {first.get('PakIndex')}, "
        f"offset {first.get('PakOffset')}, size {first.get('Size')}"
    )


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Neutral Row Provenance Report",
        "",
        f"**Generated**: {report['generated_at']}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Neutral material rows | {summary['neutral_rows']} |",
        f"| Asset-backed neutral rows | {summary['asset_backed_neutral_rows']} |",
        f"| Unique neutral asset IDs | {summary['unique_neutral_asset_ids']} |",
        f"| Id-less neutral rows | {summary['idless_neutral_rows']} |",
        f"| Source-substituted neutral rows | {summary['source_substituted_neutral_rows']} |",
        f"| Neutral asset rows with assets64 manifest metadata | {summary['neutral_asset_rows_with_assets64_manifest_entry']} |",
        f"| Neutral rows with focused probe files | {summary['neutral_rows_with_probe_file']} |",
        f"| Neutral rows with mesh DDS refs | {summary['neutral_rows_with_mesh_dds_refs']} |",
        f"| Neutral rows with texture-link rows | {summary['neutral_rows_with_texture_link_rows']} |",
        f"| Asset-backed rows with no mesh/link texture evidence | {summary['asset_backed_rows_with_no_mesh_or_link_textures']} |",
        "",
        "## Classification",
        "",
        "| Classification | Rows |",
        "|---|---:|",
    ]
    for classification, count in report.get("classification_counts", {}).items():
        lines.append(f"| `{classification}` | {count} |")
    if not report.get("classification_counts"):
        lines.append("| _none_ | 0 |")

    lines.extend(
        [
            "",
            "## Asset-backed neutral IDs",
            "",
            "| Asset ID | Rows | Mesh | assets64 metadata | Probe | Candidate links | Pairings | Mesh DDS refs | Texture-link rows | Next action |",
            "|---|---|---|---|---|---:|---:|---|---:|---|",
        ]
    )
    asset_groups = report.get("asset_groups", [])
    if asset_groups:
        for group in asset_groups:
            lines.append(
                f"| `{group.get('asset_id')}` | {_format_code_list(group.get('manifest_indices', []))} | "
                f"{_format_code_list(group.get('mesh_blocks', []))} | "
                f"{_asset_manifest_note(group.get('asset_manifest_entries', []))} | "
                f"{_format_code_list(group.get('probe_outputs', []))} | "
                f"{group.get('candidate_links') if group.get('candidate_links') is not None else 'n/a'} | "
                f"{group.get('pairings') if group.get('pairings') is not None else 'n/a'} | "
                f"{_format_code_list(group.get('mesh_dds_refs', []))} | "
                f"{group.get('texture_link_row_count', 0)} | {group.get('next_best_action')} |"
            )
    else:
        lines.append("| _none_ | none | none | none | none | 0 | 0 | none | 0 | none |")

    lines.extend(
        [
            "",
            "## Id-less and source-substituted neutral rows",
            "",
            "| Row | Classification | Review material | Candidate asset | Source | Next action |",
            "|---:|---|---|---|---|---|",
        ]
    )
    special_rows = [row for row in report.get("rows", []) if not row.get("asset_id") or row.get("source_substitution")]
    if special_rows:
        for row in special_rows:
            candidate = row.get("source_substitution_candidate_asset_id")
            lines.append(
                f"| {row.get('manifest_index')} | `{row.get('classification')}` | "
                f"`{row.get('review_material_kind') or 'n/a'}` | "
                f"`{candidate or 'n/a'}` | `{row.get('source_obj')}` | {row.get('next_best_action')} |"
            )
    else:
        lines.append("| _none_ | none | none | none | none | none |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The asset-backed neutral rows have asset IDs, assets64 metadata, and focused probe files, but no mesh DDS refs or texture-link rows in current evidence.",
            "- That makes parent, non-mesh, or provenance reference discovery the best next asset/texture workflow, not broad CI work.",
            "- Id-less rows need identity/provenance recovery before any texture assignment can become durable truth.",
            "- The source-substituted row remains practical access only until the original source OBJ or a stronger replacement proof is recovered.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report_outputs(report: dict[str, Any], *, json_out: Path, markdown_out: Path) -> None:
    _write_json(json_out, report)
    _write_text(markdown_out, render_markdown(report))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--texture-gap-report", type=Path, default=DEFAULT_TEXTURE_GAP_REPORT)
    parser.add_argument("--unresolved-texture-report", type=Path, default=DEFAULT_UNRESOLVED_TEXTURE_REPORT)
    parser.add_argument("--assets64-entries", type=Path, default=DEFAULT_ASSETS64_ENTRIES)
    parser.add_argument("--probe-refresh-report", type=Path, default=DEFAULT_PROBE_REFRESH_REPORT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_neutral_row_provenance_report(
        repo_root=args.repo_root,
        manifest_path=args.manifest,
        texture_gap_report_path=args.texture_gap_report,
        unresolved_texture_report_path=args.unresolved_texture_report,
        assets64_entries_path=args.assets64_entries,
        probe_refresh_report_path=args.probe_refresh_report,
    )
    write_report_outputs(report, json_out=args.json_out, markdown_out=args.markdown_out)
    summary = report["summary"]
    print(
        "neutral row provenance: "
        f"neutral={summary['neutral_rows']} "
        f"asset_backed={summary['asset_backed_neutral_rows']} "
        f"unique_assets={summary['unique_neutral_asset_ids']} "
        f"idless={summary['idless_neutral_rows']} "
        f"probe_files={summary['neutral_rows_with_probe_file']} "
        f"mesh_dds_rows={summary['neutral_rows_with_mesh_dds_refs']} "
        f"texture_link_rows={summary['neutral_rows_with_texture_link_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
