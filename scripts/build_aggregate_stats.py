#!/usr/bin/env python3
"""Build aggregate scene-manifest pack and summary stats for the C2-4 cohort.

Reads all 24 per-asset manifests from stage2/ and combines them into:
  1. scene-manifest-pack-v1.json — aggregate pack (one entry per asset)
  2. summary-stats.json — mesh_size breakdown + textures.source distribution
  3. summary-stats.md — human-readable stats report

Usage:
    python scripts/build_aggregate_stats.py
    python scripts/build_aggregate_stats.py --out-dir Assets/Exports/discovery-plan/cycle-2/stage4
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGE2_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage2"
STAGE3_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage3"
DEFAULT_OUT_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage4"
MANIFEST_SCHEMA_PATH = STAGE2_DIR / "scene-manifest-v1.schema.json"
PRODUCER_TOOL = "scripts/build_aggregate_stats.py"
PRODUCER_VERSION = "v0.2"
# Rounding precision for transform fingerprint comparison
TRANSFORM_DP = 4
# Rounded scale precision for fingerprinting (1e-6 identity tol becomes 6dp)
SCALE_DP = 6


def load_manifests() -> dict[str, dict[str, Any]]:
    """Load all sample-manifest-*.json files from stage2, keyed by asset_id."""
    manifests: dict[str, dict[str, Any]] = {}
    for path in sorted(STAGE2_DIR.glob("sample-manifest-????????????????.json")):
        m = json.loads(path.read_text(encoding="utf-8-sig"))
        aid = m["asset_id"]
        manifests[aid] = m
    return manifests


def load_texture_coverage() -> dict[str, Any] | None:
    """Load texture-coverage.json from stage3 if available."""
    path = STAGE3_DIR / "texture-coverage.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8-sig"))
    return None


def build_pack(manifests: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build the aggregate scene-manifest pack."""
    entries = sorted(manifests.values(), key=lambda m: m["asset_id"])
    identity_count = sum(1 for m in entries if m["world"]["world_transform_identity"])
    non_identity_count = len(entries) - identity_count

    return {
        "SchemaVersion": "scene-manifest-pack/v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "producer": {
            "tool": PRODUCER_TOOL,
            "version": PRODUCER_VERSION,
            "command": f"python {PRODUCER_TOOL}",
        },
        "manifest_schema": "scene-manifest/v1",
        "manifest_schema_path": str(MANIFEST_SCHEMA_PATH.relative_to(REPO_ROOT)),
        "cohort_size": len(entries),
        "cohort_identity_count": identity_count,
        "cohort_non_identity_count": non_identity_count,
        "entries": entries,
    }


def build_stats(
    manifests: dict[str, dict[str, Any]],
    texture_coverage: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build summary statistics from the cohort manifests."""
    entries = list(manifests.values())

    # MeshSize breakdown
    mesh_sizes: Counter = Counter()
    for m in entries:
        ms = m["geometry"].get("mesh_size")
        mesh_sizes[str(ms) if ms is not None else "null"] += 1

    # textures.source distribution
    source_dist: Counter = Counter()
    for m in entries:
        src = m["textures"].get("source", "unknown")
        source_dist[src] += 1

    # linked_texture_count distribution
    texture_counts: list[int] = []
    for m in entries:
        texture_counts.append(m["textures"].get("linked_texture_count", 0))

    # render_class distribution
    render_dist: Counter = Counter()
    for m in entries:
        render_dist[m["geometry"].get("render_class", "unknown")] += 1

    # Transform breakdown
    identity_assets = [m for m in entries if m["world"]["world_transform_identity"]]
    non_identity_assets = [m for m in entries if not m["world"]["world_transform_identity"]]

    # Consumer-ready check
    consumer_ready_count = sum(1 for m in entries if m["validation"]["consumer_ready"])

    # Warnings summary
    warning_counts: Counter = Counter()
    for m in entries:
        for w in m["validation"].get("warnings", []):
            # Normalize: extract key phrase from warning
            key = w.split(" - ")[0] if " - " in w else w.split(":")[0]
            warning_counts[key] += 1

    return {
        "SchemaVersion": "summary-stats/v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "producer": {
            "tool": PRODUCER_TOOL,
            "version": PRODUCER_VERSION,
        },
        "cohort": {
            "total": len(entries),
            "identity_transform": len(identity_assets),
            "non_identity_transform": len(non_identity_assets),
            "consumer_ready": consumer_ready_count,
            "consumer_not_ready": len(entries) - consumer_ready_count,
        },
        "mesh_size_breakdown": dict(sorted(mesh_sizes.items())),
        "textures_source_distribution": dict(source_dist),
        "textures": {
            "total_linked_textures": sum(texture_counts),
            "max_per_asset": max(texture_counts) if texture_counts else 0,
            "min_per_asset": min(texture_counts) if texture_counts else 0,
            "assets_with_textures": sum(1 for c in texture_counts if c > 0),
            "assets_textureless": sum(1 for c in texture_counts if c == 0),
        },
        "render_class_distribution": dict(render_dist),
        "non_identity_assets": [
            {
                "asset_id": m["asset_id"],
                "translation": m["world"]["world_transform_summary"]["translation"],
                "textures_source": m["textures"].get("source", "unknown"),
                "linked_texture_count": m["textures"].get("linked_texture_count", 0),
            }
            for m in non_identity_assets
        ],
        "top_warnings": dict(warning_counts.most_common(10)),
        "texture_coverage_reference": (
            str(STAGE3_DIR.relative_to(REPO_ROOT) / "texture-coverage.json") if texture_coverage else None
        ),
    }


def build_markdown_report(stats: dict[str, Any]) -> str:
    """Generate human-readable markdown stats report."""
    lines = [
        "# Cycle 2 — Summary Stats (C2-4.4)",
        "",
        "Generated: {}".format(stats["generated_at"]),
        "Producer: {} {}".format(stats["producer"]["tool"], stats["producer"]["version"]),
        "",
        "## Cohort",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Total assets | {stats['cohort']['total']} |",
        f"| Identity transform | {stats['cohort']['identity_transform']} |",
        f"| Non-identity transform | {stats['cohort']['non_identity_transform']} |",
        f"| Consumer-ready | {stats['cohort']['consumer_ready']} |",
        f"| Not consumer-ready | {stats['cohort']['consumer_not_ready']} |",
        "",
        "## MeshSize Breakdown",
        "",
        "| MeshSize | Count |",
        "|---|---:|",
    ]
    for ms, count in stats["mesh_size_breakdown"].items():
        lines.append(f"| {ms} | {count} |")

    lines += [
        "",
        "## Textures",
        "",
        "- Total linked textures: {}".format(stats["textures"]["total_linked_textures"]),
        "- Assets with textures: {}".format(stats["textures"]["assets_with_textures"]),
        "- Assets textureless: {}".format(stats["textures"]["assets_textureless"]),
        "- Max per asset: {}".format(stats["textures"]["max_per_asset"]),
        "- Min per asset: {}".format(stats["textures"]["min_per_asset"]),
        "",
        "### Textures Source Distribution",
        "",
        "| Source | Count |",
        "|---|---:|",
    ]
    for src, count in sorted(stats["textures_source_distribution"].items()):
        lines.append(f"| {src} | {count} |")

    lines += [
        "",
        "## Render Class Distribution",
        "",
        "| Class | Count |",
        "|---|---:|",
    ]
    for rc, count in sorted(stats["render_class_distribution"].items()):
        lines.append(f"| {rc} | {count} |")

    if stats["non_identity_assets"]:
        lines += [
            "",
            "## Non-Identity Transform Assets",
            "",
            "| Asset ID | Translation | Textures Source | Linked Count |",
            "|---|---:|---:|---:|",
        ]
        for a in stats["non_identity_assets"]:
            t = a["translation"]
            lines.append(
                f"| {a['asset_id']} | [{t[0]:.2f}, {t[1]:.2f}, {t[2]:.2f}]"
                f" | {a['textures_source']} | {a['linked_texture_count']} |"
            )

    if stats.get("top_warnings"):
        lines += [
            "",
            "## Top Warnings",
            "",
            "| Warning | Count |",
            "|---|---:|",
        ]
        for w, count in stats["top_warnings"].items():
            lines.append(f"| {w} | {count} |")

    return "\n".join(lines) + "\n"


def build_dedupe_report(
    manifests: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Detect duplicate and near-duplicate assets by (transform, mesh_size, texture) tuples.

    Fingerprints each manifest as: (transform_rounded_tuple, mesh_size, texture_fset).
    Groups assets with identical full fingerprints (exact structural duplicates)
    and assets sharing 2-of-3 components (near-duplicates).

    Returns a dedupe report with group assignments, sizes, and the dedupe ratio.
    """
    entries = list(manifests.values())

    # Build fingerprints
    fingerprints: dict[str, tuple[tuple[float, ...], tuple[float, ...], float, int | None, frozenset[str]]] = {}
    for m in entries:
        ws = m["world"]["world_transform_summary"]
        t = tuple(round(x, TRANSFORM_DP) for x in ws["translation"])
        r = tuple(round(x, TRANSFORM_DP) for x in ws["rotation"])
        s = round(ws["scale"], SCALE_DP)
        ms = m["geometry"].get("mesh_size")
        tex_fset = frozenset(m["textures"].get("linked_textures", []))
        fingerprints[m["asset_id"]] = (t, r, s, ms, tex_fset)

    # Group by full fingerprint
    full_groups: dict[tuple, list[str]] = {}
    for aid, fp in fingerprints.items():
        full_groups.setdefault(fp, []).append(aid)

    # Exact duplicates: groups with >1 asset (structurally identical)
    exact_groups = {fp: aids for fp, aids in full_groups.items() if len(aids) > 1}

    # Near-duplicates: assets sharing transform+mesh_size but different textures,
    # or sharing transform+textures but different mesh_size, etc.
    # Require mesh_size to match AND at least 4 of 5 components to match —
    # this filters out the trivial "shares identity transform" false positives
    # (20 assets x identity transform = 190 noise pairs).
    near_duplicates: list[dict[str, Any]] = []
    all_ids = list(fingerprints.keys())
    seen_pairs: set[tuple[str, str]] = set()
    for i in range(len(all_ids)):
        for j in range(i + 1, len(all_ids)):
            aid_a, aid_b = all_ids[i], all_ids[j]
            if aid_a == aid_b:
                continue
            pair_key = (min(aid_a, aid_b), max(aid_a, aid_b))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            fp_a, fp_b = fingerprints[aid_a], fingerprints[aid_b]
            # t, r, s, ms, tex = indices 0-4
            matches = sum(1 for k in range(5) if fp_a[k] == fp_b[k])
            if matches >= 4:  # require mesh_size match + 3 others (model-level near-duplicate)
                matched_fields = []
                field_names = ["translation", "rotation", "scale", "mesh_size", "textures"]
                for k in range(5):
                    if fp_a[k] == fp_b[k]:
                        matched_fields.append(field_names[k])
                near_duplicates.append(
                    {
                        "asset_a": aid_a,
                        "asset_b": aid_b,
                        "matches": matches,
                        "matched_fields": matched_fields,
                        "differing_fields": [f for f in field_names if f not in matched_fields],
                    }
                )

    # Dedupe ratio: unique fingerprints / total assets
    unique_count = len(full_groups)
    total = len(entries)
    dedupe_ratio = (total - unique_count) / total if total > 0 else 0.0

    return {
        "SchemaVersion": "dedupe-report/v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "producer": {
            "tool": PRODUCER_TOOL,
            "version": PRODUCER_VERSION,
        },
        "cohort_size": total,
        "unique_fingerprints": unique_count,
        "dedupe_ratio": round(dedupe_ratio, 4),
        "exact_duplicate_groups": len(exact_groups),
        "exact_duplicate_redundant_assets": sum(len(g) - 1 for g in exact_groups.values()),
        "near_duplicate_pairs": len(near_duplicates),
        "exact_groups": [
            {
                "asset_ids": sorted(aids),
                "count": len(aids),
                "fingerprint": {
                    "translation": list(fp[0]),
                    "scale": fp[2],
                    "mesh_size": fp[3],
                    "texture_count": len(fp[4]),
                },
            }
            for fp, aids in sorted(exact_groups.items(), key=lambda x: -len(x[1]))
        ],
        "near_duplicates": sorted(near_duplicates, key=lambda x: -x["matches"]),
    }


def build_dedupe_markdown(dedupe: dict[str, Any]) -> str:
    """Generate human-readable deduplication report markdown."""
    lines = [
        "# Cycle 2 — Deduplication Report (C2-4.3)",
        "",
        "Generated: {}".format(dedupe["generated_at"]),
        "Producer: {} {}".format(dedupe["producer"]["tool"], dedupe["producer"]["version"]),
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        "| Cohort size | {} |".format(dedupe["cohort_size"]),
        "| Unique fingerprints | {} |".format(dedupe["unique_fingerprints"]),
        "| Dedupe ratio | {} |".format(dedupe["dedupe_ratio"]),
        "| Exact duplicate groups | {} |".format(dedupe["exact_duplicate_groups"]),
        "| Assets in exact groups (redundant) | {} |".format(dedupe["exact_duplicate_redundant_assets"]),
        "| Near-duplicate pairs | {} |".format(dedupe["near_duplicate_pairs"]),
        "",
        "Fingerprint components: (translation, rotation, scale, mesh_size, linked_textures set)",
        "",
    ]

    if dedupe["exact_groups"]:
        lines += [
            "## Exact Duplicate Groups",
            "",
            "| Count | Asset IDs | Translation | Scale | MeshSize | Textures |",
            "|---|---:|---|---|---:|",
        ]
        for g in dedupe["exact_groups"]:
            f = g["fingerprint"]
            t_str = "[{:.2f}, {:.2f}, {:.2f}]".format(f["translation"][0], f["translation"][1], f["translation"][2])
            lines.append(
                "| {} | {} | {} | {} | {} | {} |".format(
                    g["count"],
                    ", ".join(g["asset_ids"]),
                    t_str,
                    f["scale"],
                    f["mesh_size"],
                    f["texture_count"],
                )
            )
        lines.append("")
    else:
        lines += ["## Exact Duplicate Groups", "", "*None found in the 24-asset cohort.*", ""]

    if dedupe["near_duplicates"]:
        lines += [
            "## Near-Duplicate Pairs",
            "",
            "| Matches | Asset A | Asset B | Matched Fields | Differing |",
            "|---|---|---|---|---|",
        ]
        for nd in dedupe["near_duplicates"]:
            lines.append(
                "| {} | {} | {} | {} | {} |".format(
                    nd["matches"],
                    nd["asset_a"],
                    nd["asset_b"],
                    ", ".join(nd["matched_fields"]),
                    ", ".join(nd["differing_fields"]),
                )
            )
        lines.append("")
    else:
        lines += ["## Near-Duplicate Pairs", "", "*None found in the 24-asset cohort.*", ""]

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build aggregate pack and stats")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Output directory (default: stage4/)",
    )
    parser.add_argument(
        "--dedupe",
        action="store_true",
        help="Also run deduplication analysis (C2-4.3)",
    )
    args = parser.parse_args()

    manifests = load_manifests()
    if not manifests:
        print("ERROR: no sample-manifest-*.json files found in stage2/", file=sys.stderr)
        return 1

    texture_coverage = load_texture_coverage()

    # Build and write aggregate pack
    pack = build_pack(manifests)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    pack_path = args.out_dir / "scene-manifest-pack-v1.json"
    pack_path.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    print("wrote {} ({} entries)".format(pack_path, len(pack["entries"])))

    # Build and write stats
    stats = build_stats(manifests, texture_coverage)
    stats_path = args.out_dir / "summary-stats.json"
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"wrote {stats_path}")

    # Build and write markdown report
    md = build_markdown_report(stats)
    md_path = args.out_dir / "summary-stats.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"wrote {md_path}")

    # Deduplication (C2-4.3)
    if args.dedupe:
        dedupe = build_dedupe_report(manifests)
        dedupe_path = args.out_dir / "dedupe-report.json"
        dedupe_path.write_text(json.dumps(dedupe, indent=2), encoding="utf-8")
        print(
            "wrote {} (unique={}, dedupe_ratio={}, exact_groups={}, near_pairs={})".format(
                dedupe_path,
                dedupe["unique_fingerprints"],
                dedupe["dedupe_ratio"],
                dedupe["exact_duplicate_groups"],
                dedupe["near_duplicate_pairs"],
            )
        )
        dedupe_md = build_dedupe_markdown(dedupe)
        dedupe_md_path = args.out_dir / "dedupe-report.md"
        dedupe_md_path.write_text(dedupe_md, encoding="utf-8")
        print(f"wrote {dedupe_md_path}")

    # Summary
    print("\nCohort: {} assets".format(stats["cohort"]["total"]))
    print("  Identity: {}".format(stats["cohort"]["identity_transform"]))
    print("  Non-identity: {}".format(stats["cohort"]["non_identity_transform"]))
    print("  Consumer-ready: {}/{}".format(stats["cohort"]["consumer_ready"], stats["cohort"]["total"]))
    print(
        "  Textures: {} linked ({} with, {} without)".format(
            stats["textures"]["total_linked_textures"],
            stats["textures"]["assets_with_textures"],
            stats["textures"]["assets_textureless"],
        )
    )
    print("  MeshSize families: {}".format(len(stats["mesh_size_breakdown"])))
    print("  Textures source: {}".format(stats["textures_source_distribution"]))
    if args.dedupe:
        print(
            "  Dedupe: {} unique / {} total (ratio={})".format(
                dedupe["unique_fingerprints"],
                dedupe["cohort_size"],
                dedupe["dedupe_ratio"],
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
