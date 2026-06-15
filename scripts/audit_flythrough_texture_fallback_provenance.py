#!/usr/bin/env python3
"""Audit practical texture fallback provenance for the 350 OBJ package."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH_ROOT = REPO_ROOT / "Assets" / "build" / "flythrough"
PRACTICAL_EVIDENCE_ROOT = FLYTHROUGH_ROOT / "evidence" / "practical-350-texture-fallbacks"

DEFAULT_MANIFEST = FLYTHROUGH_ROOT / "flythrough-obj-texture-manifest-practical-350-texture-fallbacks.json"
DEFAULT_FLYTHROUGH_INDEX = FLYTHROUGH_ROOT / "flythrough-index.json"
DEFAULT_NIF_INVENTORY = REPO_ROOT / "Exports" / "inventory-nif-copied-full.json"
DEFAULT_JSON_OUT = PRACTICAL_EVIDENCE_ROOT / "texture-fallback-provenance-report.json"
DEFAULT_MARKDOWN_OUT = PRACTICAL_EVIDENCE_ROOT / "TEXTURE_FALLBACK_PROVENANCE.md"

MESH_SIGNATURE_KEYS = (
    "mesh_block",
    "mesh_size",
    "vertex_count",
    "face_count",
    "node_count",
    "mesh_count",
)


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


def repo_path_from_maybe_absolute(value: str | Path | None, *, repo_root: Path = REPO_ROOT) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(str(value))
    if path.is_absolute():
        return path
    return repo_root.joinpath(*_to_posix(path).split("/"))


def obj_geometry_fingerprint(path: Path | None) -> dict[str, Any] | None:
    """Return a stable geometry hash for OBJ geometry/material data lines."""

    if path is None or not path.exists():
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


def mesh_signature(asset: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(asset, dict):
        return {}
    return {key: asset.get(key) for key in MESH_SIGNATURE_KEYS if key in asset}


def signatures_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if not left or not right:
        return False
    return all(left.get(key) == right.get(key) for key in MESH_SIGNATURE_KEYS if key in left or key in right)


def texture_name_to_assets(flythrough_index: dict[str, Any]) -> dict[str, list[str]]:
    assets = flythrough_index.get("assets", {})
    out: dict[str, list[str]] = {}
    if not isinstance(assets, dict):
        return out
    for asset_id, asset in assets.items():
        if not isinstance(asset, dict):
            continue
        for texture_name in asset.get("linked_textures", []):
            if isinstance(texture_name, str) and texture_name:
                out.setdefault(texture_name.lower(), []).append(str(asset_id).lower())
    return {texture: sorted(set(asset_ids)) for texture, asset_ids in sorted(out.items())}


def inventory_reference_context(inventory: dict[str, Any], asset_ids: set[str]) -> dict[str, dict[str, Any]]:
    """Collect compact model/DDS string reference context by asset id."""

    contexts = {
        asset_id: {
            "model_paths": [],
            "dds_refs": [],
            "string_indices": [],
            "sample_count": 0,
        }
        for asset_id in asset_ids
    }
    groups = inventory.get("Groups", [])
    if not isinstance(groups, list):
        return contexts

    seen_values: dict[str, set[str]] = {asset_id: set() for asset_id in asset_ids}
    seen_indices: dict[str, set[int]] = {asset_id: set() for asset_id in asset_ids}
    for group in groups:
        if not isinstance(group, dict):
            continue
        for sample in group.get("ReferenceSamples", []):
            if not isinstance(sample, dict):
                continue
            asset_id = str(sample.get("IdPrefix") or "").lower()
            if asset_id not in contexts:
                continue
            contexts[asset_id]["sample_count"] += 1
            value = str(sample.get("Value") or "")
            value_key = value.lower()
            if value and value_key not in seen_values[asset_id]:
                seen_values[asset_id].add(value_key)
                if value_key.endswith(".ma"):
                    contexts[asset_id]["model_paths"].append(value)
                elif value_key.endswith(".dds"):
                    contexts[asset_id]["dds_refs"].append(value)
            string_index = sample.get("StringIndex")
            if isinstance(string_index, int) and string_index not in seen_indices[asset_id]:
                seen_indices[asset_id].add(string_index)
                contexts[asset_id]["string_indices"].append(string_index)

    for context in contexts.values():
        context["model_paths"] = sorted(context["model_paths"])
        context["dds_refs"] = sorted(context["dds_refs"])
        context["string_indices"] = sorted(context["string_indices"])
    return contexts


def _fallback_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in manifest.get("entries", []):
        if not isinstance(entry, dict):
            continue
        fallbacks = [fallback for fallback in entry.get("texture_fallbacks", []) if isinstance(fallback, dict)]
        if not fallbacks:
            continue
        rows.append(entry)
    return rows


def _source_asset_notes(
    *,
    source_asset_ids: list[str],
    flythrough_assets: dict[str, Any],
    target_signature: dict[str, Any],
    target_geometry_hash: str | None,
    reference_contexts: dict[str, dict[str, Any]],
    repo_root: Path,
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for source_asset_id in source_asset_ids:
        source_asset = flythrough_assets.get(source_asset_id, {})
        source_signature = mesh_signature(source_asset)
        source_obj_path = repo_path_from_maybe_absolute(
            source_asset.get("obj_path") if isinstance(source_asset, dict) else None,
            repo_root=repo_root,
        )
        source_geometry = obj_geometry_fingerprint(source_obj_path)
        notes.append(
            {
                "asset_id": source_asset_id,
                "mesh_signature": source_signature,
                "same_mesh_signature": signatures_match(target_signature, source_signature),
                "geometry_fingerprint": source_geometry,
                "same_geometry_hash": bool(
                    target_geometry_hash
                    and source_geometry
                    and source_geometry.get("geometry_hash") == target_geometry_hash
                ),
                "reference_context": reference_contexts.get(source_asset_id, {}),
                "linked_textures": source_asset.get("linked_textures", []) if isinstance(source_asset, dict) else [],
                "obj_path": repo_relative_path(source_obj_path, repo_root=repo_root) if source_obj_path else None,
                "world_json": source_asset.get("world_json") if isinstance(source_asset, dict) else None,
            }
        )
    return notes


def build_texture_fallback_provenance_report(
    *,
    manifest: dict[str, Any] | None = None,
    manifest_path: Path = DEFAULT_MANIFEST,
    flythrough_index_path: Path = DEFAULT_FLYTHROUGH_INDEX,
    inventory_path: Path | None = DEFAULT_NIF_INVENTORY,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    manifest = manifest or _load_json(manifest_path)
    flythrough_index = _load_json(flythrough_index_path)
    flythrough_assets = flythrough_index.get("assets", {})
    if not isinstance(flythrough_assets, dict):
        flythrough_assets = {}
    texture_sources = texture_name_to_assets(flythrough_index)
    fallback_rows = _fallback_rows(manifest)
    target_asset_ids = {
        str(entry.get("asset_id") or "").lower()
        for entry in fallback_rows
        if isinstance(entry.get("asset_id"), str) and entry.get("asset_id")
    }
    source_asset_ids_for_context = {
        asset_id
        for entry in fallback_rows
        for fallback in entry.get("texture_fallbacks", [])
        if isinstance(fallback, dict)
        for asset_id in texture_sources.get(str(fallback.get("replacement_png_name") or "").lower(), [])
    }
    reference_contexts: dict[str, dict[str, Any]] = {}
    if inventory_path and inventory_path.exists():
        reference_contexts = inventory_reference_context(
            _load_json(inventory_path),
            target_asset_ids | source_asset_ids_for_context,
        )

    fallback_ref_reports: list[dict[str, Any]] = []
    source_asset_counter: Counter[str] = Counter()
    same_mesh_ref_count = 0
    same_geometry_ref_count = 0
    source_asset_ref_count = 0
    non_durable_ref_count = 0

    for entry in fallback_rows:
        target_asset_id = str(entry.get("asset_id") or "").lower()
        target_asset = flythrough_assets.get(target_asset_id, {})
        target_signature = mesh_signature(target_asset) or {
            key: entry.get(key) for key in ("mesh_block", "mesh_size", "vertex_count", "face_count") if key in entry
        }
        target_obj_path = repo_path_from_maybe_absolute(
            target_asset.get("obj_path") if isinstance(target_asset, dict) else entry.get("source_obj"),
            repo_root=repo_root,
        )
        target_geometry = obj_geometry_fingerprint(target_obj_path)
        target_geometry_hash = str(target_geometry.get("geometry_hash")) if isinstance(target_geometry, dict) else None
        for fallback in entry.get("texture_fallbacks", []):
            if not isinstance(fallback, dict):
                continue
            replacement_png = str(fallback.get("replacement_png_name") or "")
            source_asset_ids = texture_sources.get(replacement_png.lower(), [])
            source_notes = _source_asset_notes(
                source_asset_ids=source_asset_ids,
                flythrough_assets=flythrough_assets,
                target_signature=target_signature,
                target_geometry_hash=target_geometry_hash,
                reference_contexts=reference_contexts,
                repo_root=repo_root,
            )
            has_same_mesh_source = any(note.get("same_mesh_signature") for note in source_notes)
            has_same_geometry_source = any(note.get("same_geometry_hash") for note in source_notes)
            if source_asset_ids:
                source_asset_ref_count += 1
            if has_same_mesh_source:
                same_mesh_ref_count += 1
            if has_same_geometry_source:
                same_geometry_ref_count += 1
            if fallback.get("durable_truth") is not True:
                non_durable_ref_count += 1
            for source_asset_id in source_asset_ids:
                source_asset_counter[source_asset_id] += 1

            fallback_ref_reports.append(
                {
                    "manifest_index": entry.get("manifest_index"),
                    "target_asset_id": target_asset_id or None,
                    "target_mesh_signature": target_signature,
                    "target_geometry_fingerprint": target_geometry,
                    "target_reference_context": reference_contexts.get(target_asset_id, {}),
                    "target_obj_path": repo_relative_path(target_obj_path, repo_root=repo_root)
                    if target_obj_path
                    else None,
                    "target_dds_ref": fallback.get("target_dds_ref"),
                    "replacement_dds_ref": fallback.get("replacement_dds_ref"),
                    "replacement_png_name": replacement_png,
                    "fallback_score": fallback.get("score"),
                    "fallback_reasons": fallback.get("reasons", []),
                    "durable_truth": fallback.get("durable_truth"),
                    "source_assets": source_notes,
                    "source_asset_count": len(source_notes),
                    "same_mesh_source_asset_count": sum(1 for note in source_notes if note.get("same_mesh_signature")),
                    "same_geometry_source_asset_count": sum(
                        1 for note in source_notes if note.get("same_geometry_hash")
                    ),
                    "best_current_interpretation": (
                        "replacement texture comes from a flythrough-index asset with the same OBJ geometry hash"
                        if has_same_geometry_source
                        else "replacement texture comes from a flythrough-index asset with the same mesh signature"
                        if has_same_mesh_source
                        else "replacement texture is a visual fallback without a same-mesh source asset"
                    ),
                    "next_action": "Keep as practical fallback; continue exact DDS recovery before promoting durable truth.",
                }
            )

    return {
        "schema": "flythrough-texture-fallback-provenance-v1",
        "generated_at": _now_iso(),
        "inputs": {
            "manifest": repo_relative_path(manifest_path, repo_root=repo_root),
            "flythrough_index": repo_relative_path(flythrough_index_path, repo_root=repo_root),
            "nif_inventory": repo_relative_path(inventory_path, repo_root=repo_root)
            if inventory_path is not None
            else None,
        },
        "summary": {
            "fallback_rows": len(fallback_rows),
            "fallback_refs": len(fallback_ref_reports),
            "fallback_refs_with_source_assets": source_asset_ref_count,
            "fallback_refs_with_same_mesh_source_assets": same_mesh_ref_count,
            "fallback_refs_with_same_geometry_hash": same_geometry_ref_count,
            "unique_source_assets": len(source_asset_counter),
            "non_durable_fallback_refs": non_durable_ref_count,
        },
        "source_asset_counts": dict(sorted(source_asset_counter.items())),
        "fallback_refs": fallback_ref_reports,
    }


def _format_signature(signature: dict[str, Any]) -> str:
    if not signature:
        return "n/a"
    return ", ".join(f"{key}={signature.get(key)}" for key in MESH_SIGNATURE_KEYS if key in signature)


def _format_source_assets(notes: list[dict[str, Any]]) -> str:
    if not notes:
        return "none"
    formatted = []
    for note in notes:
        if note.get("same_geometry_hash"):
            suffix = "same geometry hash"
        elif note.get("same_mesh_signature"):
            suffix = "same mesh"
        else:
            suffix = "different mesh"
        formatted.append(f"`{note.get('asset_id')}` ({suffix})")
    return "<br>".join(formatted)


def _format_reference_context(context: dict[str, Any]) -> str:
    if not context:
        return "none"
    model_paths = context.get("model_paths", [])
    dds_refs = context.get("dds_refs", [])
    parts = []
    if model_paths:
        parts.append("model=" + "<br>".join(f"`{path}`" for path in model_paths[:2]))
    if dds_refs:
        parts.append("dds=" + ", ".join(f"`{ref}`" for ref in dds_refs[:4]))
    return "<br>".join(parts) if parts else "none"


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Texture Fallback Provenance",
        "",
        f"**Generated**: {report['generated_at']}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Fallback rows | {summary['fallback_rows']} |",
        f"| Fallback refs | {summary['fallback_refs']} |",
        f"| Fallback refs with source assets | {summary['fallback_refs_with_source_assets']} |",
        f"| Fallback refs with same-mesh source assets | {summary['fallback_refs_with_same_mesh_source_assets']} |",
        f"| Fallback refs with same OBJ geometry hash | {summary.get('fallback_refs_with_same_geometry_hash', 0)} |",
        f"| Unique source assets | {summary['unique_source_assets']} |",
        f"| Non-durable fallback refs | {summary['non_durable_fallback_refs']} |",
        "",
        "## Fallback refs",
        "",
        "| Row | Target asset | Missing DDS | Replacement | Source asset evidence | Target mesh signature | Target/source string context | Durable truth | Next action |",
        "|---:|---|---|---|---|---|---|---:|---|",
    ]
    for row in report.get("fallback_refs", []):
        replacement = f"`{row.get('replacement_dds_ref')}`<br>`{row.get('replacement_png_name')}`"
        source_contexts = [
            _format_reference_context(note.get("reference_context", {})) for note in row.get("source_assets", [])
        ]
        context = (
            f"target: {_format_reference_context(row.get('target_reference_context', {}))}<br>"
            f"source: {'<br>'.join(source_contexts) if source_contexts else 'none'}"
        )
        lines.append(
            f"| {row.get('manifest_index')} | `{row.get('target_asset_id')}` | "
            f"`{row.get('target_dds_ref')}` | {replacement} | "
            f"{_format_source_assets(row.get('source_assets', []))} | "
            f"{_format_signature(row.get('target_mesh_signature', {}))} | "
            f"{context} | "
            f"{row.get('durable_truth')} | {row.get('next_action')} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Same-geometry source assets make a fallback stronger for practical review/import usability, but they do not prove the missing DDS was recovered.",
            "- `durable_truth=false` remains correct until an exact DDS/name/archive proof exists.",
            "- This report is intended to justify practical texture coverage without weakening exact recovery boundaries.",
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
    parser.add_argument("--flythrough-index", type=Path, default=DEFAULT_FLYTHROUGH_INDEX)
    parser.add_argument("--nif-inventory", type=Path, default=DEFAULT_NIF_INVENTORY)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_texture_fallback_provenance_report(
        manifest_path=args.manifest,
        flythrough_index_path=args.flythrough_index,
        inventory_path=args.nif_inventory,
        repo_root=args.repo_root,
    )
    write_report_outputs(report, json_out=args.json_out, markdown_out=args.markdown_out)
    summary = report["summary"]
    print(
        "texture fallback provenance: "
        f"rows={summary['fallback_rows']} refs={summary['fallback_refs']} "
        f"source_assets={summary['fallback_refs_with_source_assets']} "
        f"same_mesh={summary['fallback_refs_with_same_mesh_source_assets']} "
        f"same_geometry={summary['fallback_refs_with_same_geometry_hash']} "
        f"non_durable={summary['non_durable_fallback_refs']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
