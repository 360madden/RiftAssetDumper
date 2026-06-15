#!/usr/bin/env python3
"""Build a focused downstream access report for the practical 350 OBJ package."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH_ROOT = REPO_ROOT / "Assets" / "build" / "flythrough"
PRACTICAL_EVIDENCE_ROOT = FLYTHROUGH_ROOT / "evidence" / "practical-350-texture-fallbacks"

DEFAULT_MANIFEST = FLYTHROUGH_ROOT / "flythrough-obj-texture-manifest-practical-350-texture-fallbacks.json"
DEFAULT_BUILD_REPORT = PRACTICAL_EVIDENCE_ROOT / "practical-package-build-report.json"
DEFAULT_TEXTURE_GAP_REPORT = PRACTICAL_EVIDENCE_ROOT / "texture-gap-report.json"
DEFAULT_UNRESOLVED_TEXTURE_REPORT = PRACTICAL_EVIDENCE_ROOT / "unresolved-texture-evidence-report.json"
DEFAULT_NEUTRAL_PROVENANCE_REPORT = PRACTICAL_EVIDENCE_ROOT / "neutral-row-provenance-report.json"
DEFAULT_COMBINED_REPORT = (
    FLYTHROUGH_ROOT / "combined-obj-package-practical-350-texture-fallbacks" / "combined-obj-package-report.json"
)
DEFAULT_REPORT_OUT = PRACTICAL_EVIDENCE_ROOT / "practical-access-report.json"
DEFAULT_MARKDOWN_OUT = PRACTICAL_EVIDENCE_ROOT / "PRACTICAL_350_ACCESS.md"


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


def _entrypoints(build_report: dict[str, Any]) -> list[dict[str, str]]:
    outputs = build_report.get("outputs", {})
    return [
        {
            "kind": "manifest_json",
            "path": str(outputs.get("manifest", "")),
            "purpose": "Authoritative 350-row per-OBJ texture/source manifest.",
        },
        {
            "kind": "manifest_csv",
            "path": str(outputs.get("csv", "")),
            "purpose": "Spreadsheet-friendly 350-row access table.",
        },
        {
            "kind": "per_row_bundle",
            "path": str(outputs.get("bundle_root", "")),
            "purpose": "Per-row OBJ/MTL files for selective import and review.",
        },
        {
            "kind": "combined_obj",
            "path": str(outputs.get("combined_markdown", "")),
            "purpose": "Portable combined OBJ/MTL package documentation and import checklist.",
        },
        {
            "kind": "gallery",
            "path": str(outputs.get("gallery", "")),
            "purpose": "Local HTML review surface with filters for fallbacks, neutral rows, and non-durable truth.",
        },
        {
            "kind": "texture_gap_report",
            "path": str(outputs.get("texture_gap_markdown", "")),
            "purpose": "Focused report for the remaining texture/review gaps.",
        },
        {
            "kind": "neutral_provenance",
            "path": str(outputs.get("neutral_provenance_markdown", "")),
            "purpose": "Focused provenance report for the 13 neutral material rows.",
        },
        {
            "kind": "unresolved_texture_evidence",
            "path": str(outputs.get("unresolved_texture_markdown", "")),
            "purpose": "Exact DDS and neutral asset evidence audit.",
        },
    ]


def _fallback_lookup(manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    lookup: dict[str, list[dict[str, Any]]] = {}
    for entry in manifest.get("entries", []):
        if not isinstance(entry, dict):
            continue
        for fallback in entry.get("texture_fallbacks", []):
            if not isinstance(fallback, dict):
                continue
            target = str(fallback.get("target_dds_ref") or "")
            if not target:
                continue
            lookup.setdefault(target, []).append(
                {
                    "manifest_index": entry.get("manifest_index"),
                    "asset_id": entry.get("asset_id"),
                    "replacement_dds_ref": fallback.get("replacement_dds_ref"),
                    "replacement_png_name": fallback.get("replacement_png_name"),
                    "durable_truth": fallback.get("durable_truth"),
                    "score": fallback.get("score"),
                }
            )
    return lookup


def _exact_dds_queue(
    *,
    manifest: dict[str, Any],
    texture_gap_report: dict[str, Any],
    unresolved_texture_report: dict[str, Any],
) -> list[dict[str, Any]]:
    fallback_lookup = _fallback_lookup(manifest)
    exact_ref_rows = unresolved_texture_report.get("exact_dds_refs") or [
        {"dds_ref": ref, "exact_match_count": None} for ref in texture_gap_report.get("unmatched_exact_dds_refs", [])
    ]
    queue: list[dict[str, Any]] = []
    for row in exact_ref_rows:
        if not isinstance(row, dict):
            continue
        dds_ref = str(row.get("dds_ref") or "")
        if not dds_ref:
            continue
        queue.append(
            {
                "dds_ref": dds_ref,
                "exact_match_count": row.get("exact_match_count", 0),
                "fallbacks": fallback_lookup.get(dds_ref, []),
                "next_action": "Continue exact DDS/path/hash recovery; keep any visual fallback marked non-durable.",
            }
        )
    return queue


def _neutral_asset_queue(neutral_provenance_report: dict[str, Any]) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for group in neutral_provenance_report.get("asset_groups", []):
        if not isinstance(group, dict):
            continue
        queue.append(
            {
                "asset_id": group.get("asset_id"),
                "manifest_indices": group.get("manifest_indices", []),
                "mesh_blocks": group.get("mesh_blocks", []),
                "world_parent_node_names": group.get("world_parent_node_names", []),
                "world_named_nodes": group.get("world_named_nodes", []),
                "world_mesh_sizes": group.get("world_mesh_sizes", []),
                "world_mesh_size_mismatch_rows": group.get("world_mesh_size_mismatch_rows", []),
                "candidate_links": group.get("candidate_links", 0),
                "mesh_dds_refs": group.get("mesh_dds_refs", []),
                "texture_link_row_count": group.get("texture_link_row_count", 0),
                "next_action": group.get(
                    "next_best_action",
                    "Inspect parent, non-mesh, or provenance references; normal mesh/link evidence is empty.",
                ),
            }
        )
    return queue


def _idless_or_substituted_queue(neutral_provenance_report: dict[str, Any]) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for row in neutral_provenance_report.get("rows", []):
        if not isinstance(row, dict):
            continue
        classification = str(row.get("classification") or "")
        if classification not in {"idless-provenance-gap", "source-substitution-provenance-gap"}:
            continue
        coverage = row.get("coverage_entry") if isinstance(row.get("coverage_entry"), dict) else {}
        queue.append(
            {
                "manifest_index": row.get("manifest_index"),
                "classification": classification,
                "review_material_kind": row.get("review_material_kind"),
                "source_obj": row.get("source_obj"),
                "candidate_asset_id": row.get("source_substitution_candidate_asset_id"),
                "original_source_exists": row.get("original_source_exists"),
                "geometry_status": coverage.get("candidate_geometry_status"),
                "geometry_line_count": coverage.get("geometry_line_count"),
                "next_action": row.get("next_best_action"),
            }
        )
    return queue


def _truth_boundaries(summary: dict[str, Any]) -> list[str]:
    boundaries = [
        "350-row practical access is an import/review package, not proof that every original source or texture has been durably recovered.",
        "Visual texture fallbacks are usability aids and remain non-durable until exact DDS evidence is found.",
        "Neutral review materials are colored review aids and remain non-durable texture truth.",
        "The source-substituted row improves access but does not replace exact source recovery proof.",
    ]
    if summary.get("exact_dds_gaps", 0) == 0:
        boundaries.append("No exact DDS gaps are currently reported by the package evidence.")
    return boundaries


def _next_best_actions(summary: dict[str, Any]) -> list[str]:
    return [
        "Continue exact recovery for the remaining Eternal Assault flower DDS refs before promoting fallback textures.",
        "Review row 118 in the gallery/combined import and keep its flower textures marked non-durable unless exact DDS proof appears.",
        "Inspect the five asset-backed neutral IDs for parent, non-mesh, or provenance references beyond normal mesh/link evidence.",
        "Prioritize the neutral IDs with named scene context or mesh-size mismatches because they have the strongest extra provenance clues.",
        "Recover source identity/provenance for id-less rows 5 and 6 before assigning texture truth.",
        "Prove or replace row 121's practical source substitution by finding the original source OBJ or stronger replacement evidence.",
        "Use the manifest CSV for downstream filtering by texture_source, review_material, source_substitution, and texture_fallback_count.",
        "Open the filtered gallery for neutral, texture-fallback, source-substitution, id-less, and non-durable review passes.",
        "Smoke-import the combined OBJ/MTL package in the target viewer with point-cloud rows enabled or explicitly accepted.",
        f"Keep quick local validation on the package gates only; current verification pass is {summary.get('verification_pass')}.",
    ]


def build_access_report(
    *,
    manifest: dict[str, Any],
    build_report: dict[str, Any],
    texture_gap_report: dict[str, Any],
    unresolved_texture_report: dict[str, Any],
    neutral_provenance_report: dict[str, Any],
    combined_report: dict[str, Any],
) -> dict[str, Any]:
    package_summary = build_report.get("summary", {})
    texture_summary = texture_gap_report.get("summary", {})
    neutral_summary = neutral_provenance_report.get("summary", {})
    combined_summary = combined_report.get("summary", {})
    manifest_summary = manifest.get("summary", {})

    total_entries = int(package_summary.get("manifest_entries", manifest_summary.get("total_entries", 0)) or 0)
    materialized_entries = int(
        package_summary.get("materializable_entries", manifest_summary.get("materializable_entries", 0)) or 0
    )
    verification_pass = all(
        [
            materialized_entries == total_entries,
            bool(package_summary.get("bundle_verify_pass")),
            bool(package_summary.get("smoke_pass")),
            bool(package_summary.get("combined_verify_pass")),
            int(package_summary.get("combined_skipped_entries", 0) or 0) == 0,
            bool(package_summary.get("gallery_exists")),
        ]
    )
    summary = {
        "total_obj_rows": total_entries,
        "materialized_obj_rows": materialized_entries,
        "downstream_access_ready_rows": materialized_entries if verification_pass else 0,
        "rows_with_non_neutral_textures_or_fallbacks": int(
            package_summary.get(
                "non_neutral_texture_entries",
                texture_summary.get("entries_with_non_neutral_textures", 0),
            )
            or 0
        ),
        "neutral_review_rows": int(
            package_summary.get("neutral_material_entries", texture_summary.get("neutral_material_entries", 0)) or 0
        ),
        "asset_backed_neutral_rows": int(neutral_summary.get("asset_backed_neutral_rows", 0) or 0),
        "idless_neutral_rows": int(neutral_summary.get("idless_neutral_rows", 0) or 0),
        "source_substituted_entries": int(package_summary.get("source_substituted_entries", 0) or 0),
        "texture_fallback_refs": int(package_summary.get("texture_fallback_refs", 0) or 0),
        "exact_dds_gaps": int(package_summary.get("unmatched_exact_dds_refs", 0) or 0),
        "exact_dds_gaps_with_any_exact_match": int(
            package_summary.get("unmatched_exact_dds_refs_with_any_exact_match", 0) or 0
        ),
        "combined_entries": int(
            package_summary.get("combined_entries", combined_summary.get("combined_entries", 0)) or 0
        ),
        "combined_skipped_entries": int(package_summary.get("combined_skipped_entries", 0) or 0),
        "zero_face_entries": int(combined_summary.get("zero_face_entries", 0) or 0),
        "point_cloud_entries": int(
            combined_summary.get("point_cloud_entries", combined_summary.get("point_directive_entries", 0)) or 0
        ),
        "copied_texture_files": int(combined_summary.get("copied_texture_files", 0) or 0),
        "verification_pass": verification_pass,
    }
    exact_dds_queue = _exact_dds_queue(
        manifest=manifest,
        texture_gap_report=texture_gap_report,
        unresolved_texture_report=unresolved_texture_report,
    )
    neutral_asset_queue = _neutral_asset_queue(neutral_provenance_report)
    idless_or_substituted_queue = _idless_or_substituted_queue(neutral_provenance_report)

    status = (
        "practical-access-ready-with-review-queues"
        if verification_pass
        else "practical-access-incomplete-or-unverified"
    )
    return {
        "schema": "flythrough-practical-access-report-v1",
        "generated_at": _now_iso(),
        "status": status,
        "summary": summary,
        "entrypoints": _entrypoints(build_report),
        "review_queues": {
            "exact_dds_recovery": exact_dds_queue,
            "neutral_asset_provenance": neutral_asset_queue,
            "idless_or_source_substituted_rows": idless_or_substituted_queue,
        },
        "truth_boundaries": _truth_boundaries(summary),
        "next_best_actions": _next_best_actions(summary),
    }


def _markdown_entrypoints(entrypoints: list[dict[str, str]]) -> list[str]:
    lines = ["## Downstream entrypoints", "", "| Kind | Path | Purpose |", "|---|---|---|"]
    for entrypoint in entrypoints:
        if not entrypoint.get("path"):
            continue
        lines.append(f"| `{entrypoint['kind']}` | `{entrypoint['path']}` | {entrypoint['purpose']} |")
    lines.append("")
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    queues = report.get("review_queues", {})
    lines = [
        "# Practical 350 OBJ Access Report",
        "",
        f"**Generated**: {report['generated_at']}",
        f"**Status**: `{report['status']}`",
        "",
        "## Current access truth",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Total OBJ rows | {summary['total_obj_rows']} |",
        f"| Materialized OBJ rows | {summary['materialized_obj_rows']} |",
        f"| Downstream-access-ready rows | {summary['downstream_access_ready_rows']} |",
        (f"| Rows with non-neutral textures/fallbacks | {summary['rows_with_non_neutral_textures_or_fallbacks']} |"),
        f"| Neutral review rows | {summary['neutral_review_rows']} |",
        f"| Asset-backed neutral rows | {summary['asset_backed_neutral_rows']} |",
        f"| Id-less/source-substituted neutral rows | {summary['idless_neutral_rows']} |",
        f"| Texture fallback refs | {summary['texture_fallback_refs']} |",
        f"| Exact DDS gaps | {summary['exact_dds_gaps']} |",
        f"| Source-substituted entries | {summary['source_substituted_entries']} |",
        f"| Combined entries | {summary['combined_entries']} |",
        f"| Combined skipped entries | {summary['combined_skipped_entries']} |",
        f"| Point-cloud entries | {summary['point_cloud_entries']} |",
        f"| Copied texture files | {summary['copied_texture_files']} |",
        f"| Verification pass | {summary['verification_pass']} |",
        "",
    ]
    lines.extend(_markdown_entrypoints(report.get("entrypoints", [])))

    exact_dds_queue = queues.get("exact_dds_recovery", [])
    lines.extend(["## Review queue: exact DDS recovery", ""])
    if exact_dds_queue:
        lines.extend(["| DDS ref | Exact matches | Active fallback(s) | Next action |", "|---|---:|---|---|"])
        for item in exact_dds_queue:
            fallbacks = item.get("fallbacks", [])
            fallback_text = "<br>".join(
                (
                    f"row {fallback.get('manifest_index')}: "
                    f"`{fallback.get('replacement_dds_ref')}` / `{fallback.get('replacement_png_name')}` "
                    f"(durable={fallback.get('durable_truth')})"
                )
                for fallback in fallbacks
            )
            lines.append(
                f"| `{item.get('dds_ref')}` | {item.get('exact_match_count')} | "
                f"{fallback_text or '_none_'} | {item.get('next_action')} |"
            )
    else:
        lines.append("_No exact DDS recovery queue items._")
    lines.append("")

    neutral_queue = queues.get("neutral_asset_provenance", [])
    lines.extend(["## Review queue: asset-backed neutral provenance", ""])
    if neutral_queue:
        lines.extend(
            [
                "| Asset ID | Rows | Mesh blocks | Scene clues | Normal texture evidence | Next action |",
                "|---|---|---|---|---|---|",
            ]
        )
        for item in neutral_queue:
            scene_bits = []
            if item.get("world_parent_node_names"):
                scene_bits.append("parent=" + ", ".join(f"`{name}`" for name in item["world_parent_node_names"]))
            if item.get("world_named_nodes"):
                scene_bits.append("named=" + ", ".join(f"`{name}`" for name in item["world_named_nodes"]))
            if item.get("world_mesh_size_mismatch_rows"):
                scene_bits.append(
                    "mismatch rows=" + ", ".join(str(row) for row in item["world_mesh_size_mismatch_rows"])
                )
            evidence = (
                f"mesh DDS refs={len(item.get('mesh_dds_refs', []))}; "
                f"texture-link rows={item.get('texture_link_row_count', 0)}"
            )
            lines.append(
                f"| `{item.get('asset_id')}` | `{', '.join(str(row) for row in item.get('manifest_indices', []))}` | "
                f"`{', '.join(str(block) for block in item.get('mesh_blocks', []))}` | "
                f"{'; '.join(scene_bits) or 'world context only'} | {evidence} | {item.get('next_action')} |"
            )
    else:
        lines.append("_No asset-backed neutral provenance queue items._")
    lines.append("")

    idless_queue = queues.get("idless_or_source_substituted_rows", [])
    lines.extend(["## Review queue: id-less/source-substituted rows", ""])
    if idless_queue:
        lines.extend(
            ["| Row | Classification | Geometry/source status | Source | Next action |", "|---:|---|---|---|---|"]
        )
        for item in idless_queue:
            status = (
                f"original_source_exists={item.get('original_source_exists')}; "
                f"geometry={item.get('geometry_status')}; lines={item.get('geometry_line_count')}"
            )
            lines.append(
                f"| {item.get('manifest_index')} | `{item.get('classification')}` | {status} | "
                f"`{item.get('source_obj')}` | {item.get('next_action')} |"
            )
    else:
        lines.append("_No id-less/source-substituted queue items._")
    lines.append("")

    lines.extend(["## Truth boundaries", ""])
    lines.extend(f"- {boundary}" for boundary in report.get("truth_boundaries", []))
    lines.extend(["", "## Top 10 next asset-focused actions", ""])
    lines.extend(f"{index}. {action}" for index, action in enumerate(report.get("next_best_actions", []), start=1))
    lines.append("")
    return "\n".join(lines)


def build_practical_access_report(
    *,
    repo_root: Path = REPO_ROOT,
    manifest_path: Path = DEFAULT_MANIFEST,
    build_report_path: Path = DEFAULT_BUILD_REPORT,
    texture_gap_report_path: Path = DEFAULT_TEXTURE_GAP_REPORT,
    unresolved_texture_report_path: Path = DEFAULT_UNRESOLVED_TEXTURE_REPORT,
    neutral_provenance_report_path: Path = DEFAULT_NEUTRAL_PROVENANCE_REPORT,
    combined_report_path: Path = DEFAULT_COMBINED_REPORT,
    report_out: Path = DEFAULT_REPORT_OUT,
    markdown_out: Path = DEFAULT_MARKDOWN_OUT,
) -> dict[str, Any]:
    report = build_access_report(
        manifest=_load_json(manifest_path),
        build_report=_load_json(build_report_path),
        texture_gap_report=_load_json(texture_gap_report_path),
        unresolved_texture_report=_load_json(unresolved_texture_report_path),
        neutral_provenance_report=_load_json(neutral_provenance_report_path),
        combined_report=_load_json(combined_report_path),
    )
    report["inputs"] = {
        "manifest": repo_relative_path(manifest_path, repo_root=repo_root),
        "build_report": repo_relative_path(build_report_path, repo_root=repo_root),
        "texture_gap_report": repo_relative_path(texture_gap_report_path, repo_root=repo_root),
        "unresolved_texture_report": repo_relative_path(unresolved_texture_report_path, repo_root=repo_root),
        "neutral_provenance_report": repo_relative_path(neutral_provenance_report_path, repo_root=repo_root),
        "combined_report": repo_relative_path(combined_report_path, repo_root=repo_root),
    }
    report["outputs"] = {
        "json": repo_relative_path(report_out, repo_root=repo_root),
        "markdown": repo_relative_path(markdown_out, repo_root=repo_root),
    }
    _write_json(report_out, report)
    _write_text(markdown_out, render_markdown(report))
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--build-report", type=Path, default=DEFAULT_BUILD_REPORT)
    parser.add_argument("--texture-gap-report", type=Path, default=DEFAULT_TEXTURE_GAP_REPORT)
    parser.add_argument("--unresolved-texture-report", type=Path, default=DEFAULT_UNRESOLVED_TEXTURE_REPORT)
    parser.add_argument("--neutral-provenance-report", type=Path, default=DEFAULT_NEUTRAL_PROVENANCE_REPORT)
    parser.add_argument("--combined-report", type=Path, default=DEFAULT_COMBINED_REPORT)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT_OUT)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_practical_access_report(
        repo_root=args.repo_root.resolve(),
        manifest_path=args.manifest,
        build_report_path=args.build_report,
        texture_gap_report_path=args.texture_gap_report,
        unresolved_texture_report_path=args.unresolved_texture_report,
        neutral_provenance_report_path=args.neutral_provenance_report,
        combined_report_path=args.combined_report,
        report_out=args.report_out,
        markdown_out=args.markdown_out,
    )
    summary = report["summary"]
    print(
        "practical access: "
        f"status={report['status']} "
        f"rows={summary['materialized_obj_rows']}/{summary['total_obj_rows']} "
        f"textured_or_fallback={summary['rows_with_non_neutral_textures_or_fallbacks']} "
        f"neutral={summary['neutral_review_rows']} "
        f"exact_dds_gaps={summary['exact_dds_gaps']} "
        f"source_substitutions={summary['source_substituted_entries']} "
        f"verification={summary['verification_pass']}"
    )
    return 0 if summary["verification_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
