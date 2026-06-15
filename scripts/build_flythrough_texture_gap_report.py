#!/usr/bin/env python3
"""Build a focused remaining-gap report for the practical 350 OBJ package.

The practical package can now materialize all 350 OBJ rows, but that does not
mean every row has durable texture/source truth. This report keeps those
boundaries visible for downstream review:

* rows still using neutral materials,
* exact DDS refs that remain unrecovered,
* practical visual texture fallbacks,
* practical source substitutions, and
* probe/triage evidence explaining why the next asset-texture work is bounded.

Generated outputs belong under ``Assets/build/flythrough`` and must not be
committed.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH_ROOT = REPO_ROOT / "Assets" / "build" / "flythrough"

DEFAULT_MANIFEST = FLYTHROUGH_ROOT / "flythrough-obj-texture-manifest-practical-350-texture-fallbacks.json"
DEFAULT_TRIAGE_REPORT = FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "textureless-triage.json"
DEFAULT_RECOVERY_REPORT = (
    FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "recovery" / "textureless-dds-recovery-report.json"
)
DEFAULT_PROBE_REFRESH_REPORT = FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "probe-refresh-report.json"
DEFAULT_JSON_OUT = FLYTHROUGH_ROOT / "evidence" / "practical-350-texture-fallbacks" / "texture-gap-report.json"
DEFAULT_MARKDOWN_OUT = FLYTHROUGH_ROOT / "evidence" / "practical-350-texture-fallbacks" / "TEXTURE_GAP_REPORT.md"


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


def _row_key(manifest_index: Any) -> int | None:
    return manifest_index if isinstance(manifest_index, int) else None


def triage_rows_by_index(triage_report: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for row in triage_report.get("rows", []):
        if not isinstance(row, dict):
            continue
        manifest_index = _row_key(row.get("manifest_index"))
        if manifest_index is not None:
            rows[manifest_index] = row
    return rows


def probe_targets_by_index(probe_refresh_report: dict[str, Any]) -> dict[int, dict[str, Any]]:
    targets: dict[int, dict[str, Any]] = {}
    for target in probe_refresh_report.get("targets", []):
        if not isinstance(target, dict):
            continue
        for manifest_index in target.get("manifest_indices", []):
            if isinstance(manifest_index, int):
                targets[manifest_index] = target
    return targets


def texture_gap_bucket(
    entry: dict[str, Any], triage_row: dict[str, Any] | None, probe_target: dict[str, Any] | None
) -> str:
    """Classify a practical manifest row's remaining texture gap."""

    if entry.get("texture_source") != "untextured-neutral":
        return "not-neutral"
    if not entry.get("asset_id"):
        if entry.get("source_substitution"):
            return "no-asset-id-source-substitution"
        return "no-asset-id-no-texture-candidate"
    row_refs = (triage_row or {}).get("row_dds_refs", [])
    if row_refs:
        return "probe-dds-refs-unmaterialized"
    if probe_target and probe_target.get("probe_exists") is True:
        return "probed-no-mesh-dds-refs"
    return "needs-probe-evidence"


def neutral_gap_row(
    entry: dict[str, Any],
    *,
    triage_row: dict[str, Any] | None,
    probe_target: dict[str, Any] | None,
) -> dict[str, Any]:
    bucket = texture_gap_bucket(entry, triage_row, probe_target)
    row_dds_refs = sorted(str(ref) for ref in (triage_row or {}).get("row_dds_refs", []) if isinstance(ref, str))
    missing_refs = sorted(
        str(ref) for ref in (triage_row or {}).get("row_dds_refs_missing_from_converted", []) if isinstance(ref, str)
    )
    return {
        "manifest_index": entry.get("manifest_index"),
        "asset_id": entry.get("asset_id"),
        "source_obj": entry.get("source_obj"),
        "mesh_block": entry.get("mesh_block"),
        "mesh_size": entry.get("mesh_size"),
        "vertex_count": entry.get("vertex_count"),
        "face_count": entry.get("face_count"),
        "faced": entry.get("faced"),
        "texture_status": entry.get("texture_status"),
        "texture_source": entry.get("texture_source"),
        "bucket": bucket,
        "row_dds_refs": row_dds_refs,
        "row_dds_refs_missing_from_converted": missing_refs,
        "asset_probe_files": sorted(
            str(path) for path in (triage_row or {}).get("asset_probe_files", []) if isinstance(path, str)
        ),
        "mesh_probe_files": sorted(
            str(path) for path in (triage_row or {}).get("mesh_probe_files", []) if isinstance(path, str)
        ),
        "probe_exists": (probe_target or {}).get("probe_exists"),
        "mesh_dds_refs": sorted(
            str(ref) for ref in (probe_target or {}).get("mesh_dds_refs", []) if isinstance(ref, str)
        ),
        "asset_dds_refs": sorted(
            str(ref) for ref in (probe_target or {}).get("asset_dds_refs", []) if isinstance(ref, str)
        ),
        "source_substitution": entry.get("source_substitution"),
        "review_material": entry.get("review_material"),
    }


def fallback_rows(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in entries:
        fallbacks = [fallback for fallback in entry.get("texture_fallbacks", []) if isinstance(fallback, dict)]
        if not fallbacks:
            continue
        rows.append(
            {
                "manifest_index": entry.get("manifest_index"),
                "asset_id": entry.get("asset_id"),
                "source_obj": entry.get("source_obj"),
                "texture_source": entry.get("texture_source"),
                "fallback_count": len(fallbacks),
                "fallbacks": fallbacks,
            }
        )
    return rows


def source_substitution_rows(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in entries:
        substitution = entry.get("source_substitution")
        if not isinstance(substitution, dict):
            continue
        rows.append(
            {
                "manifest_index": entry.get("manifest_index"),
                "asset_id": entry.get("asset_id"),
                "source_obj": entry.get("source_obj"),
                "texture_source": entry.get("texture_source"),
                "source_substitution": substitution,
            }
        )
    return rows


def build_texture_gap_report(
    *,
    repo_root: Path = REPO_ROOT,
    manifest: dict[str, Any] | None = None,
    manifest_path: Path = DEFAULT_MANIFEST,
    triage_report_path: Path = DEFAULT_TRIAGE_REPORT,
    recovery_report_path: Path = DEFAULT_RECOVERY_REPORT,
    probe_refresh_report_path: Path = DEFAULT_PROBE_REFRESH_REPORT,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    manifest = manifest or _load_json(manifest_path)
    triage_report = _load_optional_json(triage_report_path)
    recovery_report = _load_optional_json(recovery_report_path)
    probe_refresh_report = _load_optional_json(probe_refresh_report_path)

    entries = [entry for entry in manifest.get("entries", []) if isinstance(entry, dict)]
    triage_by_index = triage_rows_by_index(triage_report)
    probe_by_index = probe_targets_by_index(probe_refresh_report)

    texture_source_counts = Counter(str(entry.get("texture_source") or "none") for entry in entries)
    texture_status_counts = Counter(str(entry.get("texture_status") or "none") for entry in entries)
    review_material_counts = Counter(
        str(entry.get("review_material", {}).get("kind"))
        for entry in entries
        if isinstance(entry.get("review_material"), dict)
    )
    neutral_rows = [
        neutral_gap_row(
            entry,
            triage_row=triage_by_index.get(int(entry["manifest_index"]))
            if isinstance(entry.get("manifest_index"), int)
            else None,
            probe_target=probe_by_index.get(int(entry["manifest_index"]))
            if isinstance(entry.get("manifest_index"), int)
            else None,
        )
        for entry in entries
        if entry.get("texture_source") == "untextured-neutral"
    ]
    neutral_bucket_counts = Counter(str(row["bucket"]) for row in neutral_rows)
    practical_fallback_rows = fallback_rows(entries)
    practical_source_substitution_rows = source_substitution_rows(entries)

    unmatched_target_refs = sorted(
        str(ref)
        for ref in recovery_report.get("refs", {}).get(
            "unmatched_target",
            recovery_report.get("refs", {}).get("target", []),
        )
        if isinstance(ref, str)
    )
    fallback_target_refs = sorted(
        {
            str(fallback.get("target_dds_ref"))
            for row in practical_fallback_rows
            for fallback in row.get("fallbacks", [])
            if isinstance(fallback, dict) and fallback.get("target_dds_ref")
        }
    )

    report = {
        "schema": "flythrough-practical-texture-gap-report-v1",
        "generated_at": _now_iso(),
        "inputs": {
            "manifest": repo_relative_path(manifest_path, repo_root=repo_root),
            "textureless_triage": repo_relative_path(triage_report_path, repo_root=repo_root),
            "texture_recovery_report": repo_relative_path(recovery_report_path, repo_root=repo_root),
            "probe_refresh_report": repo_relative_path(probe_refresh_report_path, repo_root=repo_root),
        },
        "summary": {
            "total_entries": len(entries),
            "materializable_entries": int(manifest.get("summary", {}).get("materializable_entries", 0)),
            "entries_with_non_neutral_textures": len(entries) - len(neutral_rows),
            "neutral_material_entries": len(neutral_rows),
            "neutral_entries_with_asset_id": len([row for row in neutral_rows if row.get("asset_id")]),
            "neutral_entries_without_asset_id": len([row for row in neutral_rows if not row.get("asset_id")]),
            "texture_fallback_entries": len(practical_fallback_rows),
            "texture_fallback_refs": sum(int(row.get("fallback_count") or 0) for row in practical_fallback_rows),
            "review_material_entries": sum(review_material_counts.values()),
            "source_substituted_entries": len(practical_source_substitution_rows),
            "unmatched_exact_dds_refs": len(unmatched_target_refs),
            "fallback_target_dds_refs": len(fallback_target_refs),
        },
        "texture_source_counts": _counter_to_sorted_dict(texture_source_counts),
        "texture_status_counts": _counter_to_sorted_dict(texture_status_counts),
        "review_material_counts": _counter_to_sorted_dict(review_material_counts),
        "neutral_bucket_counts": _counter_to_sorted_dict(neutral_bucket_counts),
        "unmatched_exact_dds_refs": unmatched_target_refs,
        "fallback_target_dds_refs": fallback_target_refs,
        "neutral_rows": neutral_rows,
        "texture_fallback_rows": practical_fallback_rows,
        "source_substitution_rows": practical_source_substitution_rows,
        "source_reports": {
            "triage_summary": triage_report.get("summary", {}),
            "recovery_summary": recovery_report.get("summary", {}),
            "probe_refresh_summary": probe_refresh_report.get("summary", {}),
        },
    }
    return report


def _format_refs(refs: list[str]) -> str:
    return ", ".join(f"`{ref}`" for ref in refs) if refs else "none"


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Practical 350 Texture Gap Report",
        "",
        f"**Generated**: {report['generated_at']}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Total OBJ rows | {summary['total_entries']} |",
        f"| Materializable OBJ rows | {summary['materializable_entries']} |",
        f"| Rows with non-neutral textures/fallbacks | {summary['entries_with_non_neutral_textures']} |",
        f"| Neutral material rows still lacking texture evidence | {summary['neutral_material_entries']} |",
        f"| Neutral rows with asset IDs | {summary['neutral_entries_with_asset_id']} |",
        f"| Neutral rows without asset IDs | {summary['neutral_entries_without_asset_id']} |",
        f"| Neutral review-color materials | {summary.get('review_material_entries', 0)} |",
        f"| Practical texture-fallback rows | {summary['texture_fallback_entries']} |",
        f"| Practical texture-fallback refs | {summary['texture_fallback_refs']} |",
        f"| Practical source-substituted rows | {summary['source_substituted_entries']} |",
        f"| Exact DDS refs still unmatched | {summary['unmatched_exact_dds_refs']} |",
        "",
        "## Remaining texture buckets",
        "",
        "| Bucket | Rows | Meaning |",
        "|---|---:|---|",
    ]
    bucket_meanings = {
        "no-asset-id-no-texture-candidate": "No asset ID and no texture candidate is available.",
        "no-asset-id-source-substitution": "Practical source substitution exists, but texture truth is still absent.",
        "probed-no-mesh-dds-refs": "Focused probe exists and found no mesh-level DDS refs.",
        "probe-dds-refs-unmaterialized": "Probe found DDS refs that are not materialized as exact PNGs.",
        "needs-probe-evidence": "No current focused probe evidence is attached.",
    }
    for bucket, count in report.get("neutral_bucket_counts", {}).items():
        lines.append(f"| `{bucket}` | {count} | {bucket_meanings.get(bucket, '')} |")
    if not report.get("neutral_bucket_counts"):
        lines.append("| _none_ | 0 | All rows have non-neutral textures/fallbacks. |")

    lines.extend(
        [
            "",
            "## Exact DDS refs still unresolved",
            "",
            _format_refs(report.get("unmatched_exact_dds_refs", [])),
            "",
            "## Practical visual fallbacks",
            "",
        ]
    )
    fallback_rows_list = report.get("texture_fallback_rows", [])
    if fallback_rows_list:
        lines.extend(
            ["| Row | Asset ID | Target DDS | Replacement DDS/PNG | Durable truth? |", "|---:|---|---|---|---:|"]
        )
        for row in fallback_rows_list:
            for fallback in row.get("fallbacks", []):
                if not isinstance(fallback, dict):
                    continue
                replacement = f"`{fallback.get('replacement_dds_ref')}`<br>`{fallback.get('replacement_png_name')}`"
                lines.append(
                    f"| {row.get('manifest_index')} | `{row.get('asset_id') or 'n/a'}` | "
                    f"`{fallback.get('target_dds_ref')}` | {replacement} | "
                    f"{'yes' if fallback.get('durable_truth') else 'no'} |"
                )
    else:
        lines.append("- No practical visual fallbacks are active.")

    lines.extend(["", "## Neutral rows to keep focused", ""])
    neutral_rows_list = report.get("neutral_rows", [])
    if neutral_rows_list:
        lines.extend(
            [
                "| Row | Bucket | Review material | Asset ID | Mesh | Verts/Faces | Probe/DDS evidence | Source |",
                "|---:|---|---|---|---|---:|---|---|",
            ]
        )
        for row in neutral_rows_list:
            probe_note = _format_refs(row.get("row_dds_refs", []) or row.get("mesh_dds_refs", []))
            review_material = row.get("review_material") or {}
            lines.append(
                f"| {row.get('manifest_index')} | `{row.get('bucket')}` | "
                f"`{review_material.get('kind') or 'n/a'}` | `{row.get('asset_id') or 'n/a'}` | "
                f"{row.get('mesh_block')} / {row.get('mesh_size')} | "
                f"{row.get('vertex_count')}/{row.get('face_count')} | {probe_note} | "
                f"`{row.get('source_obj')}` |"
            )
    else:
        lines.append("- No neutral rows remain.")

    lines.extend(["", "## Practical source substitutions", ""])
    substitution_rows = report.get("source_substitution_rows", [])
    if substitution_rows:
        for row in substitution_rows:
            substitution = row["source_substitution"]
            lines.append(
                f"- Row {row.get('manifest_index')}: `{substitution.get('original_source_obj')}` -> "
                f"`{substitution.get('replacement_source_obj')}` "
                f"(durable_truth={str(bool(substitution.get('durable_truth'))).lower()})"
            )
    else:
        lines.append("- No practical source substitutions are active.")

    lines.extend(
        [
            "",
            "## Next best asset/texture actions",
            "",
            "1. Inspect the neutral rows grouped as `probed-no-mesh-dds-refs`; these are likely genuinely textureless or need non-mesh reference evidence.",
            "2. Continue exact name/hash recovery for the unmatched Eternal Assault flower DDS refs before promoting any fallback to truth.",
            "3. Review the practical fallback previews for row 118 and keep them marked non-durable unless exact DDS evidence appears.",
            "4. Investigate the no-asset-id neutral rows separately from texture work; they need classification/source provenance before texture truth can improve.",
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
    parser.add_argument("--textureless-triage", type=Path, default=DEFAULT_TRIAGE_REPORT)
    parser.add_argument("--texture-recovery-report", type=Path, default=DEFAULT_RECOVERY_REPORT)
    parser.add_argument("--probe-refresh-report", type=Path, default=DEFAULT_PROBE_REFRESH_REPORT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_texture_gap_report(
        repo_root=args.repo_root,
        manifest_path=args.manifest,
        triage_report_path=args.textureless_triage,
        recovery_report_path=args.texture_recovery_report,
        probe_refresh_report_path=args.probe_refresh_report,
    )
    write_report_outputs(report, json_out=args.json_out, markdown_out=args.markdown_out)
    summary = report["summary"]
    print(
        "texture gap report: "
        f"materializable={summary['materializable_entries']}/{summary['total_entries']} "
        f"neutral={summary['neutral_material_entries']} "
        f"fallback_refs={summary['texture_fallback_refs']} "
        f"unmatched_dds={summary['unmatched_exact_dds_refs']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
