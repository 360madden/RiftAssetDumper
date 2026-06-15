#!/usr/bin/env python3
"""Audit unresolved practical texture rows against local texture-link evidence.

The practical 350 package deliberately separates usable review fallbacks from
durable texture truth. This report keeps the remaining texture work grounded by
checking the unresolved exact DDS refs and neutral review-material rows against
local name-match and texture-link JSONL evidence.

Generated reports stay under ``Assets/build/flythrough`` and must not be
committed.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH_ROOT = REPO_ROOT / "Assets" / "build" / "flythrough"

DEFAULT_TEXTURE_GAP_REPORT = (
    FLYTHROUGH_ROOT / "evidence" / "practical-350-texture-fallbacks" / "texture-gap-report.json"
)
DEFAULT_JSON_OUT = (
    FLYTHROUGH_ROOT / "evidence" / "practical-350-texture-fallbacks" / "unresolved-texture-evidence-report.json"
)
DEFAULT_MARKDOWN_OUT = (
    FLYTHROUGH_ROOT / "evidence" / "practical-350-texture-fallbacks" / "UNRESOLVED_TEXTURE_EVIDENCE.md"
)
DEFAULT_NAME_MATCHES = REPO_ROOT / "Exports" / "nif-reference-name-matches.jsonl"
DEFAULT_TEXTURE_LINKS = REPO_ROOT / "Exports" / "nif-texture-links.jsonl"
DEFAULT_LIVE_TEXTURE_LINKS_ALL4 = REPO_ROOT / "Exports" / "live-texture-links-all4.jsonl"

DDS_SUFFIX_RE = re.compile(r"_(?P<id>[0-9a-f]{16})\.dds$", re.IGNORECASE)


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


def texture_basename(value: str) -> str:
    return Path(value.replace("\\", "/")).name.lower()


def canonical_dds_ref(value: str) -> str:
    name = texture_basename(value)
    return DDS_SUFFIX_RE.sub(".dds", name)


def _candidate_dds_values(row: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for key in ("Name", "Candidate", "Reference", "target_dds_ref", "replacement_dds_ref"):
        value = row.get(key)
        if isinstance(value, str) and value.lower().endswith(".dds"):
            refs.add(canonical_dds_ref(value))
    return refs


def _row_asset_ids(row: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in ("ModelIdPrefix", "IdPrefix", "asset_id"):
        value = row.get(key)
        if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{16}", value):
            ids.add(value.lower())
    return ids


def _compact_match(source: str, line_number: int, row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "Name",
        "Reference",
        "Candidate",
        "ModelIdPrefix",
        "IdPrefix",
        "TextureIdPrefix",
        "TextureManifestEntryIndex",
        "TexturePakIndex",
        "TexturePakOffset",
        "TextureCompressedSize",
        "TextureSize",
        "Confidence",
        "CollisionCount",
        "CandidateKind",
        "Algorithm",
    )
    compact = {"source": source, "line_number": line_number}
    for key in keys:
        if key in row:
            compact[key] = row[key]
    return compact


def _append_limited(bucket: dict[str, list[dict[str, Any]]], key: str, value: dict[str, Any], *, limit: int) -> None:
    values = bucket.setdefault(key, [])
    if len(values) < limit:
        values.append(value)


def scan_jsonl_sources(
    *,
    sources: list[tuple[str, Path]],
    exact_dds_refs: list[str],
    asset_ids: list[str],
    repo_root: Path = REPO_ROOT,
    sample_limit: int = 20,
) -> dict[str, Any]:
    exact_targets = {canonical_dds_ref(ref) for ref in exact_dds_refs}
    asset_targets = {asset_id.lower() for asset_id in asset_ids}
    needles = sorted(exact_targets | asset_targets)
    exact_counts: dict[str, Counter[str]] = {ref: Counter() for ref in exact_targets}
    asset_counts: dict[str, Counter[str]] = {asset_id: Counter() for asset_id in asset_targets}
    exact_matches: dict[str, list[dict[str, Any]]] = {}
    asset_matches: dict[str, list[dict[str, Any]]] = {}
    source_stats: list[dict[str, Any]] = []

    for source_name, path in sources:
        if not path.exists():
            source_stats.append(
                {
                    "source": source_name,
                    "path": repo_relative_path(path, repo_root=repo_root),
                    "exists": False,
                    "scanned_lines": 0,
                    "candidate_lines": 0,
                }
            )
            continue

        scanned = 0
        candidate_lines = 0
        parse_errors = 0
        with path.open(encoding="utf-8-sig", errors="replace") as f:
            for line_number, line in enumerate(f, start=1):
                scanned += 1
                line_lower = line.lower()
                if needles and not any(needle in line_lower for needle in needles):
                    continue
                candidate_lines += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    parse_errors += 1
                    continue
                if not isinstance(row, dict):
                    continue

                matched_refs = exact_targets & _candidate_dds_values(row)
                matched_assets = asset_targets & _row_asset_ids(row)
                compact = _compact_match(source_name, line_number, row)
                for ref in matched_refs:
                    exact_counts[ref][source_name] += 1
                    _append_limited(exact_matches, ref, compact, limit=sample_limit)
                for asset_id in matched_assets:
                    asset_counts[asset_id][source_name] += 1
                    _append_limited(asset_matches, asset_id, compact, limit=sample_limit)

        source_stats.append(
            {
                "source": source_name,
                "path": repo_relative_path(path, repo_root=repo_root),
                "exists": True,
                "scanned_lines": scanned,
                "candidate_lines": candidate_lines,
                "parse_errors": parse_errors,
            }
        )

    return {
        "source_stats": source_stats,
        "exact_counts": {ref: dict(sorted(counts.items())) for ref, counts in sorted(exact_counts.items())},
        "asset_counts": {asset: dict(sorted(counts.items())) for asset, counts in sorted(asset_counts.items())},
        "exact_matches": exact_matches,
        "asset_matches": asset_matches,
    }


def _neutral_asset_rows(neutral_rows: list[dict[str, Any]]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = defaultdict(list)
    for row in neutral_rows:
        asset_id = row.get("asset_id")
        if isinstance(asset_id, str) and asset_id:
            out[asset_id.lower()].append(int(row.get("manifest_index")))
    return {asset_id: rows for asset_id, rows in sorted(out.items())}


def build_unresolved_texture_evidence_report(
    *,
    repo_root: Path = REPO_ROOT,
    texture_gap_report_path: Path = DEFAULT_TEXTURE_GAP_REPORT,
    name_matches_path: Path = DEFAULT_NAME_MATCHES,
    texture_links_path: Path = DEFAULT_TEXTURE_LINKS,
    live_texture_links_all4_path: Path = DEFAULT_LIVE_TEXTURE_LINKS_ALL4,
    include_live_all4: bool = True,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    texture_gap = _load_json(texture_gap_report_path)
    neutral_rows = [row for row in texture_gap.get("neutral_rows", []) if isinstance(row, dict)]
    exact_refs = [canonical_dds_ref(ref) for ref in texture_gap.get("unmatched_exact_dds_refs", [])]
    neutral_asset_rows = _neutral_asset_rows(neutral_rows)
    asset_ids = sorted(neutral_asset_rows)
    sources = [
        ("nif-reference-name-matches", name_matches_path),
        ("nif-texture-links", texture_links_path),
    ]
    if include_live_all4:
        sources.append(("live-texture-links-all4", live_texture_links_all4_path))

    scan = scan_jsonl_sources(
        sources=sources,
        exact_dds_refs=exact_refs,
        asset_ids=asset_ids,
        repo_root=repo_root,
    )

    exact_ref_reports = []
    for ref in exact_refs:
        counts = scan["exact_counts"].get(ref, {})
        exact_ref_reports.append(
            {
                "dds_ref": ref,
                "exact_match_count": sum(counts.values()),
                "counts_by_source": counts,
                "sample_matches": scan["exact_matches"].get(ref, []),
            }
        )

    neutral_asset_reports = []
    for asset_id, rows in neutral_asset_rows.items():
        counts = scan["asset_counts"].get(asset_id, {})
        neutral_asset_reports.append(
            {
                "asset_id": asset_id,
                "manifest_indices": rows,
                "texture_link_row_count": sum(counts.values()),
                "counts_by_source": counts,
                "sample_matches": scan["asset_matches"].get(asset_id, []),
            }
        )

    exact_refs_with_matches = sum(1 for row in exact_ref_reports if row["exact_match_count"] > 0)
    neutral_assets_with_links = sum(1 for row in neutral_asset_reports if row["texture_link_row_count"] > 0)
    return {
        "schema": "flythrough-unresolved-texture-evidence-v1",
        "generated_at": _now_iso(),
        "inputs": {
            "texture_gap_report": repo_relative_path(texture_gap_report_path, repo_root=repo_root),
            "name_matches": repo_relative_path(name_matches_path, repo_root=repo_root),
            "texture_links": repo_relative_path(texture_links_path, repo_root=repo_root),
            "live_texture_links_all4": repo_relative_path(live_texture_links_all4_path, repo_root=repo_root)
            if include_live_all4
            else None,
        },
        "summary": {
            "unmatched_exact_dds_refs": len(exact_refs),
            "unmatched_exact_dds_refs_with_any_exact_match": exact_refs_with_matches,
            "neutral_asset_ids": len(asset_ids),
            "neutral_asset_ids_with_texture_link_rows": neutral_assets_with_links,
            "neutral_rows": len(neutral_rows),
            "neutral_rows_with_asset_id": sum(len(rows) for rows in neutral_asset_rows.values()),
            "neutral_rows_without_asset_id": len([row for row in neutral_rows if not row.get("asset_id")]),
            "sources_scanned": len([source for source in scan["source_stats"] if source.get("exists")]),
        },
        "source_stats": scan["source_stats"],
        "exact_dds_refs": exact_ref_reports,
        "neutral_assets": neutral_asset_reports,
        "neutral_rows": neutral_rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Unresolved Practical Texture Evidence",
        "",
        f"**Generated**: {report['generated_at']}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Unmatched exact DDS refs checked | {summary['unmatched_exact_dds_refs']} |",
        f"| Exact DDS refs with any exact local match | {summary['unmatched_exact_dds_refs_with_any_exact_match']} |",
        f"| Neutral asset IDs checked | {summary['neutral_asset_ids']} |",
        f"| Neutral asset IDs with texture-link rows | {summary['neutral_asset_ids_with_texture_link_rows']} |",
        f"| Neutral rows | {summary['neutral_rows']} |",
        f"| Neutral rows with asset IDs | {summary['neutral_rows_with_asset_id']} |",
        f"| Neutral rows without asset IDs | {summary['neutral_rows_without_asset_id']} |",
        "",
        "## Source scan stats",
        "",
        "| Source | Exists | Scanned lines | Candidate lines | Parse errors |",
        "|---|---:|---:|---:|---:|",
    ]
    for source in report.get("source_stats", []):
        lines.append(
            f"| `{source.get('source')}` | {source.get('exists')} | {source.get('scanned_lines')} | "
            f"{source.get('candidate_lines')} | {source.get('parse_errors', 0)} |"
        )

    lines.extend(
        [
            "",
            "## Exact DDS refs",
            "",
            "| DDS ref | Exact matches | Counts by source |",
            "|---|---:|---|",
        ]
    )
    for row in report.get("exact_dds_refs", []):
        counts = ", ".join(f"{source}={count}" for source, count in row.get("counts_by_source", {}).items()) or "none"
        lines.append(f"| `{row.get('dds_ref')}` | {row.get('exact_match_count')} | {counts} |")

    lines.extend(
        [
            "",
            "## Neutral asset IDs",
            "",
            "| Asset ID | Rows | Texture-link rows | Counts by source |",
            "|---|---|---:|---|",
        ]
    )
    for row in report.get("neutral_assets", []):
        counts = ", ".join(f"{source}={count}" for source, count in row.get("counts_by_source", {}).items()) or "none"
        rows = ", ".join(str(index) for index in row.get("manifest_indices", []))
        lines.append(f"| `{row.get('asset_id')}` | {rows} | {row.get('texture_link_row_count')} | {counts} |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Exact DDS refs with zero exact matches remain unresolved durable texture truth.",
            "- Neutral asset IDs with zero texture-link rows should be investigated through non-mesh or parent/provenance evidence rather than normal asset texture links.",
            "- Any practical visual fallback remains non-durable until an exact DDS/name/archive proof appears.",
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
    parser.add_argument("--texture-gap-report", type=Path, default=DEFAULT_TEXTURE_GAP_REPORT)
    parser.add_argument("--name-matches", type=Path, default=DEFAULT_NAME_MATCHES)
    parser.add_argument("--texture-links", type=Path, default=DEFAULT_TEXTURE_LINKS)
    parser.add_argument("--live-texture-links-all4", type=Path, default=DEFAULT_LIVE_TEXTURE_LINKS_ALL4)
    parser.add_argument("--skip-live-all4", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_unresolved_texture_evidence_report(
        repo_root=args.repo_root,
        texture_gap_report_path=args.texture_gap_report,
        name_matches_path=args.name_matches,
        texture_links_path=args.texture_links,
        live_texture_links_all4_path=args.live_texture_links_all4,
        include_live_all4=not args.skip_live_all4,
    )
    write_report_outputs(report, json_out=args.json_out, markdown_out=args.markdown_out)
    summary = report["summary"]
    print(
        "unresolved texture evidence: "
        f"exact_refs={summary['unmatched_exact_dds_refs']} "
        f"exact_matches={summary['unmatched_exact_dds_refs_with_any_exact_match']} "
        f"neutral_assets={summary['neutral_asset_ids']} "
        f"neutral_assets_with_links={summary['neutral_asset_ids_with_texture_link_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
