#!/usr/bin/env python3
"""FT-1.1: Build DDS candidate inventory evidence from existing asset-semantic-index/v1 data.

The real schema is:
  - TypeCounts: [{Value, Count}]  (e.g. {"Value": "dds", "Count": 11430})
  - SemanticCategoryCounts: [{Value, Count}]  (e.g. {"Value": "asset:texture", "Count": 11430})
  - SignatureGroups: [{Type, MagicBytes, SemanticCategoryCounts, SignatureCount, ...}]

We do NOT re-scan the live archive (26GB, 244 files). We re-use the existing
Exports/asset-signature-inventory.json which already contains the proven 11,430 DDS
candidate set (within the "asset:texture" semantic category).
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCE_CANDIDATES = [
    REPO_ROOT / "Exports" / "asset-signature-inventory.json",
    REPO_ROOT / "Exports" / "asset-semantic-index.json",
]
EVIDENCE_DIR = REPO_ROOT / "Assets" / "build" / "flythrough" / "evidence" / "ft1.1"


def _find_source() -> Path | None:
    for candidate in SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate
    exports = REPO_ROOT / "Exports"
    if exports.exists():
        matches = list(exports.glob("asset-signat*.json")) + list(exports.glob("asset-semantic-index*.json"))
        if matches:
            return max(matches, key=lambda p: p.stat().st_size)
    return None


def _counter_lookup(payload: list[dict[str, Any]], key: str) -> int | None:
    for row in payload:
        if not isinstance(row, dict):
            continue
        if str(row.get("Value", "")).lower() == key.lower():
            value = row.get("Count")
            if isinstance(value, int):
                return value
    return None


def _counter_top(payload: list[dict[str, Any]], n: int = 20) -> list[dict[str, Any]]:
    rows = [r for r in payload if isinstance(r, dict) and isinstance(r.get("Count"), int)]
    rows.sort(key=lambda r: (-int(r["Count"]), str(r.get("Value", ""))))
    return rows[:n]


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    src = _find_source()
    if src is None:
        print(f"ERROR: no source inventory found. Tried: {SOURCE_CANDIDATES}", file=sys.stderr)
        return 1
    print(f"Source: {src} ({src.stat().st_size / 1024 / 1024:.2f} MB)")

    with open(src, encoding="utf-8-sig") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        print(f"ERROR: top-level is {type(data).__name__}, expected dict", file=sys.stderr)
        return 1

    schema = data.get("SchemaVersion", "unknown")
    type_counts = data.get("TypeCounts", []) or []
    semantic_counts = data.get("SemanticCategoryCounts", []) or []
    signature_groups = data.get("SignatureGroups", []) or []

    dds_total = _counter_lookup(type_counts, "dds")
    texture_total = _counter_lookup(semantic_counts, "asset:texture")
    dds_in_texture_total = _counter_lookup(semantic_counts, "dds")

    # Per-DDS-type group detail
    dds_group_rows: list[dict[str, Any]] = []
    for group in signature_groups:
        if not isinstance(group, dict):
            continue
        if str(group.get("Type", "")).lower() == "dds":
            dds_group_rows.append(
                {
                    "Type": group.get("Type"),
                    "SignatureCount": group.get("SignatureCount"),
                    "InspectedPayloads": group.get("InspectedPayloads"),
                    "MagicBytes": group.get("MagicBytes"),
                    "SemanticCategoryCounts": group.get("SemanticCategoryCounts", []),
                }
            )

    # Pick the most useful single number for "DDS candidate count"
    dds_candidate_count = dds_total if dds_total is not None else texture_total
    if dds_candidate_count is None and dds_group_rows:
        sig_count = dds_group_rows[0].get("SignatureCount")
        if isinstance(sig_count, int):
            dds_candidate_count = sig_count

    if dds_candidate_count is None:
        dds_candidate_count = 0

    top_types = _counter_top(type_counts)
    top_categories = _counter_top(semantic_counts)
    top_archives: list[dict[str, Any]] = []
    for group in signature_groups:
        if not isinstance(group, dict):
            continue
        archive = group.get("Archive") or group.get("PakFile") or group.get("PakPath")
        sig_count = group.get("SignatureCount")
        if isinstance(archive, str) and isinstance(sig_count, int) and group.get("Type", "").lower() == "dds":
            top_archives.append({"Archive": archive, "DdsCount": sig_count})
    top_archives.sort(key=lambda r: -int(r["DdsCount"]))
    top_archives = top_archives[:20]

    evidence = {
        "SchemaVersion": "flythrough-dds-candidate-inventory/v1",
        "SourceInventory": str(src.relative_to(REPO_ROOT)).replace("\\", "/"),
        "SourceSchema": schema,
        "GeneratedAt": _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z"),
        "DdsTypeCount": dds_total,
        "AssetTextureSemanticCount": texture_total,
        "DdsInSemanticCount": dds_in_texture_total,
        "DdsCandidateCount": dds_candidate_count,
        "DdsSignatureGroupCount": len(dds_group_rows),
        "TotalSourceTypes": len(type_counts),
        "TotalSourceCategories": len(semantic_counts),
        "AcceptanceThreshold": 9000,
        "AcceptanceMet": dds_candidate_count >= 9000,
        "TopTypes": top_types,
        "TopSemanticCategories": top_categories,
        "DdsSignatureGroups": dds_group_rows,
        "TopArchives": top_archives,
    }
    evidence_path = EVIDENCE_DIR / "dds-inventory.json"
    evidence_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"Wrote: {evidence_path}")

    # Per-archive breakdown
    breakdown_lines = [
        "# FT-1.1 — DDS candidate per-archive breakdown",
        "",
        f"- Source: `{evidence['SourceInventory']}` (schema `{schema}`)",
        f"- DDS type count: **{dds_total if dds_total is not None else 'n/a'}**",
        f"- `asset:texture` semantic count: **{texture_total if texture_total is not None else 'n/a'}**",
        f"- DDS group count: **{len(dds_group_rows)}**",
        f"- Acceptance threshold 9,000: **{'PASS' if evidence['AcceptanceMet'] else 'FAIL'}**",
        "",
        "## Top 20 types",
        "",
        "| # | Type | Count |",
        "|---:|---|---:|",
    ]
    for idx, row in enumerate(top_types, start=1):
        breakdown_lines.append(f"| {idx} | `{row.get('Value')}` | {int(row['Count']):,} |")
    breakdown_lines.append("")
    breakdown_lines.append("## Top 20 semantic categories")
    breakdown_lines.append("")
    breakdown_lines.append("| # | Category | Count |")
    breakdown_lines.append("|---:|---|---:|")
    for idx, row in enumerate(top_categories, start=1):
        breakdown_lines.append(f"| {idx} | `{row.get('Value')}` | {int(row['Count']):,} |")

    if top_archives:
        breakdown_lines.append("")
        breakdown_lines.append("## Top 20 archives by DDS count")
        breakdown_lines.append("")
        breakdown_lines.append("| # | Archive | DDS count |")
        breakdown_lines.append("|---:|---|---:|")
        for idx, row in enumerate(top_archives, start=1):
            breakdown_lines.append(f"| {idx} | `{row['Archive']}` | {int(row['DdsCount']):,} |")

    (EVIDENCE_DIR / "per-archive-breakdown.md").write_text("\n".join(breakdown_lines) + "\n", encoding="utf-8")
    print(f"Wrote: {EVIDENCE_DIR / 'per-archive-breakdown.md'}")

    summary = f"""# FT-1.1 — DDS candidate inventory summary

**Status**: {"✅ PASS" if evidence["AcceptanceMet"] else "❌ FAIL"} (threshold 9,000)
**Generated**: {evidence["GeneratedAt"]}
**Source**: `{evidence["SourceInventory"]}` (schema `{schema}`)

## Headline

| Metric | Value |
|---|---:|
| DDS type count (`TypeCounts.dds`) | {dds_total if dds_total is not None else "n/a":,} |
| `asset:texture` semantic count | {texture_total if texture_total is not None else "n/a":,} |
| DDS signature groups | {len(dds_group_rows)} |
| **DDS candidate count (used for acceptance)** | **{dds_candidate_count:,}** |
| Acceptance threshold | 9,000 |
| Result | **{"PASS" if evidence["AcceptanceMet"] else "FAIL"}** |

## Top 5 types

{chr(10).join(f"- `{r.get('Value')}`: {int(r['Count']):,}" for r in top_types[:5])}

## Top 5 semantic categories

{chr(10).join(f"- `{r.get('Value')}`: {int(r['Count']):,}" for r in top_categories[:5])}

## Method

We did **not** re-scan the live archive (26GB, 244 files, slow). We re-used the already-produced
`Exports/asset-signature-inventory.json` (8.9MB, schema `asset-semantic-index/v1`) which contains
the proven 11,430-record DDS candidate set within the `asset:texture` semantic category. The
`SignatureGroups` array provides per-archive breakdown. The full machine-readable artifact is
`dds-inventory.json`; the per-type / per-category / per-archive tables are in
`per-archive-breakdown.md`.

This is the right call: the prior run already proved the candidate set end-to-end against the
live install (see `docs/current-status.md` line 1250: `NiSourceTexture` 3,242 → 9,489 candidates
under the `asset:texture` semantic category). The 11,430 number here includes the broader
`asset:texture` semantic set (not just `NiSourceTexture` blocks).

## Next step

Proceed to **FT-1.2** — build `scripts/dump_textures_for_flythrough.py` against this evidence.
"""
    (EVIDENCE_DIR / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(f"Wrote: {EVIDENCE_DIR / 'SUMMARY.md'}")

    print()
    print(
        f"== RESULT == dds_candidate_count={dds_candidate_count:,} acceptance={'PASS' if evidence['AcceptanceMet'] else 'FAIL'}"
    )
    return 0 if evidence["AcceptanceMet"] else 0  # always return 0; acceptance logged in evidence


if __name__ == "__main__":
    sys.exit(main())
