#!/usr/bin/env python3
"""Cycle 4.1 \u2014 LOD-aware metadata application.

Extends ft7_lod_detector.py's classification from 193 to a target of
all flythrough assets by classifying the remaining 34 unclassified via
bounded heuristics:

1. MeshSize-family vertex-rank: group by mesh_size, rank by vertex_count desc.
2. Singleton detection: family size == 1 \u2192 lod_type="singleton".
3. Absolute-vertex-count tier: assets with mesh_size=None, applied against
   the cohort-wide vertex count distribution (top 20% = high, mid 60% = medium,
   bottom 20% = low).

Patches each stage6 manifest at Assets/Exports/discovery-plan/cycle-2/stage6/
with three new fields under geometry: lod_index, lod_type ("single"|"low"|"medium"|"high"), lod_tier.

Writes evidence artifacts to Assets/build/flythrough/evidence/cycle4.1/.

Pure Python data-fusion; no dotnet spawns. Idempotent re-runs.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH_INDEX = REPO_ROOT / "Assets" / "build" / "flythrough" / "flythrough-index.json"
LOD_MANIFEST = REPO_ROOT / "Assets" / "build" / "flythrough" / "lod-manifest.json"
STAGE6_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage6"
EVIDENCE_DIR = REPO_ROOT / "Assets" / "build" / "flythrough" / "evidence" / "cycle4.1"

PRODUCER_TOOL = "scripts/cycle4_lod_metadata.py"
PRODUCER_VERSION = "v0.1"
SCHEMA_VERSION = "cycle4-lod-metadata/v1"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_flythrough_index() -> dict[str, Any]:
    return json.loads(FLYTHROUGH_INDEX.read_text(encoding="utf-8-sig"))


def load_lod_manifest() -> dict[str, Any] | None:
    if not LOD_MANIFEST.exists():
        return None
    return json.loads(LOD_MANIFEST.read_text(encoding="utf-8-sig"))


def classify_remaining(
    flythrough_assets: dict[str, Any],
    asset_lod_map: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Classify unclassified flythrough assets via bounded heuristics.

    Returns {asset_id: {lod_index, lod_type, lod_reason, vertex_count, mesh_size, family_size}}.
    """
    classified: dict[str, dict[str, Any]] = {}
    unclassified = sorted(
        aid
        for aid, _ in flythrough_assets.items()
        if aid not in asset_lod_map and flythrough_assets[aid].get("vertex_count", 0) > 0
    )

    # Heuristic 1: Group by mesh_size, rank vertex_count desc (lod_index = family rank)
    by_ms: dict[int, list[str]] = defaultdict(list)
    ms_none: list[str] = []
    for aid in unclassified:
        ms = flythrough_assets[aid].get("mesh_size")
        if isinstance(ms, int) and ms > 0:
            by_ms[ms].append(aid)
        else:
            ms_none.append(aid)

    for ms, aids in sorted(by_ms.items()):
        # Sort by vertex_count desc within family
        aids_sorted = sorted(
            aids,
            key=lambda a: (-flythrough_assets[a].get("vertex_count", 0), a),
        )
        family_size = len(aids_sorted)
        if family_size == 1:
            # Heuristic 2: singletons
            classified[aids_sorted[0]] = {
                "lod_index": 0,
                "lod_type": "singleton",
                "lod_reason": "family_size=1",
                "vertex_count": flythrough_assets[aids_sorted[0]].get("vertex_count", 0),
                "mesh_size": ms,
                "family_size": family_size,
            }
        else:
            # Heuristic 1: family rank
            max_vc = flythrough_assets[aids_sorted[0]].get("vertex_count", 0)
            min_vc = flythrough_assets[aids_sorted[-1]].get("vertex_count", 0)
            tier = "high" if max_vc >= 100 and min_vc >= 50 else "medium"
            for rank, aid in enumerate(aids_sorted):
                classified[aid] = {
                    "lod_index": rank,
                    "lod_type": tier,
                    "lod_reason": f"mesh_size={ms}_rank={rank}/{family_size}",
                    "vertex_count": flythrough_assets[aid].get("vertex_count", 0),
                    "mesh_size": ms,
                    "family_size": family_size,
                }

    # Heuristic 3: ms=None assets get absolute-vertex-count tier
    if ms_none:
        no_ms_vcs = [flythrough_assets[aid].get("vertex_count", 0) for aid in ms_none]
        non_zero = [v for v in no_ms_vcs if v > 0]
        if non_zero:
            p20 = statistics.quantiles(non_zero, n=5)[0] if len(non_zero) >= 5 else min(non_zero)
            p80 = statistics.quantiles(non_zero, n=5)[-1] if len(non_zero) >= 5 else max(non_zero)
        else:
            p20, p80 = 0, 0
        for aid in ms_none:
            vc = flythrough_assets[aid].get("vertex_count", 0)
            if vc >= p80:
                tier = "high"
            elif vc >= p20:
                tier = "medium"
            else:
                tier = "low"
            classified[aid] = {
                "lod_index": 0,
                "lod_type": tier,
                "lod_reason": f"absolute_tier_ms_none.vc={vc}",
                "vertex_count": vc,
                "mesh_size": None,
                "family_size": 1,
            }

    return classified


def patch_stage6_manifest(
    asset_id: str,
    lod_meta: dict[str, Any],
) -> tuple[bool, str]:
    """Patch the stage6 manifest for this asset with cyclic-4 LOD fields.

    Idempotent: re-patching refreshes the cycle4.* fields under geometry,
    leaves validation status untouched. Returns (modified, error_message).
    """
    manifest_path = STAGE6_DIR / f"manifest-{asset_id}.json"
    if not manifest_path.exists():
        return False, f"manifest-{asset_id}.json missing"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))

    geometry = manifest.setdefault("geometry", {})
    geometry["lod_index"] = lod_meta["lod_index"]
    geometry["lod_type"] = lod_meta["lod_type"]
    geometry["lod_tier_count_in_family"] = lod_meta["family_size"]

    # Producer metadata (cycle 4.1 stamp)
    producer = manifest.setdefault("producer", {})
    c4_producers = producer.get("cycle4_producers", [])
    if PRODUCER_TOOL not in c4_producers:
        c4_producers.append(PRODUCER_TOOL)
    producer["cycle4_producers"] = c4_producers
    producer["cycle4_version"] = PRODUCER_VERSION
    producer["cycle4_last_applied"] = _now_iso()

    # Cleanup: historically this script wrote a root-level `last_updated_at`,
    # but the locked schema (v1 cycle4 extension) keeps the cycle4 timestamp
    # under `producer.cycle4_last_applied` only. Drop any stale root copy.
    manifest.pop("last_updated_at", None)

    tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, manifest_path)
    return True, ""


def build_evidence(
    already_classified: dict[str, Any],
    newly_classified: dict[str, dict[str, Any]],
    patch_results: dict[str, tuple[bool, str]],
) -> dict[str, Any]:
    """Build the cycle4.1 evidence JSON summarising the classification."""
    by_tier: dict[str, int] = defaultdict(int)
    by_reason: dict[str, int] = defaultdict(int)
    for meta in newly_classified.values():
        by_tier[meta["lod_type"]] += 1
        reason_class = meta["lod_reason"].split("_")[0] if "_" in meta["lod_reason"] else meta["lod_reason"]
        by_reason[reason_class] += 1
    patched_ok = sum(1 for ok, _ in patch_results.values() if ok)
    patched_failed = sum(1 for ok, _ in patch_results.values() if not ok)
    failed_ids = [aid for aid, (ok, err) in patch_results.items() if not ok]
    return {
        "SchemaVersion": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "producer": {"tool": PRODUCER_TOOL, "version": PRODUCER_VERSION},
        "summary": {
            "flythrough_total": len(already_classified) + len(newly_classified),
            "previously_classified": len(already_classified),
            "newly_classified": len(newly_classified),
            "patched_ok": patched_ok,
            "patched_failed": patched_failed,
            "by_tier": dict(sorted(by_tier.items())),
            "by_reason_class": dict(sorted(by_reason.items())),
        },
        "previously_classified_assets": sorted(already_classified.keys()),
        "newly_classified": sorted((aid, meta) for aid, meta in newly_classified.items()),
        "patch_failures": failed_ids,
    }


def render_markdown(evidence: dict[str, Any]) -> str:
    summary = evidence["summary"]
    lines = [
        "# Cycle 4.1 \u2014 LOD-Aware Closure Report",
        "",
        f"**Generated**: {evidence['generated_at']}",
        f"**Producer**: `{evidence['producer']['tool']}` ({evidence['producer']['version']})",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Flythrough total | {summary['flythrough_total']} |",
        f"| Previously classified (FT-7.2) | {summary['previously_classified']} |",
        f"| Newly classified (Cycle 4.1) | {summary['newly_classified']} |",
        f"| Manifests patched (OK) | {summary['patched_ok']} |",
        f"| Manifests patched (FAILED) | {summary['patched_failed']} |",
        "",
        "## Tier distribution (newly classified)",
        "",
        "| Tier | Count |",
        "|---|---:|",
    ]
    for tier, count in sorted(summary["by_tier"].items()):
        lines.append(f"| {tier} | {count} |")
    lines.append("")
    lines.append("## Reason class distribution")

    lines.append("")
    lines.append("| Reason class | Count |")
    lines.append("|---|---:|")
    for reason, count in sorted(summary["by_reason_class"].items()):
        lines.append(f"| {reason} | {count} |")
    lines.append("")
    if evidence["patch_failures"]:
        lines.append("## Patch failures")
        lines.append("")
        for aid in evidence["patch_failures"]:
            lines.append(f"- `{aid}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview classification without writing")
    args = parser.parse_args()

    flythrough = load_flythrough_index()
    flythrough_assets = flythrough.get("assets", {})

    lod_manifest = load_lod_manifest()
    asset_lod_map = (lod_manifest or {}).get("asset_lod_map", {})

    print(f"flythrough assets: {len(flythrough_assets)}")
    print(f"already classified: {len(asset_lod_map)}")

    newly_classified = classify_remaining(flythrough_assets, asset_lod_map)
    print(f"newly classified: {len(newly_classified)}")

    if args.dry_run:
        for aid, meta in sorted(newly_classified.items()):
            print(f"  [DRY] would patch {aid}: lod_type={meta['lod_type']} lod_index={meta['lod_index']}")
        return 0

    # Patch stage6 manifests
    patch_results: dict[str, tuple[bool, str]] = {}
    for aid, meta in newly_classified.items():
        ok, err = patch_stage6_manifest(aid, meta)
        patch_results[aid] = (ok, err)

    # Write evidence
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    evidence = build_evidence(asset_lod_map, newly_classified, patch_results)
    evidence_path = EVIDENCE_DIR / "lod-closure.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path = EVIDENCE_DIR / "LOD_CLOSURE.md"
    md_path.write_text(render_markdown(evidence), encoding="utf-8")
    print(f"evidence: {evidence_path.relative_to(REPO_ROOT)}")
    print(f"markdown: {md_path.relative_to(REPO_ROOT)}")
    summary = evidence["summary"]
    print("\ncyclic-4 LOD closure summary:")
    print(
        f"  total=({summary['previously_classified']} ft7.2 + {summary['newly_classified']} cycle4.1) = {summary['flythrough_total']}"
    )
    print(f"  patched_ok={summary['patched_ok']} patched_failed={summary['patched_failed']}")
    return 0 if summary["patched_failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
