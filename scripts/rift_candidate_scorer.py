#!/usr/bin/env python3
"""Candidate scorer — scores live memory scan results against the asset semantic index.

Reads a live scan result JSON (from scan-live-memory / scan-live-values / scan-live-diff)
and an asset-semantic-index.json, then scores each matched address against asset-backed
semantic categories (zone, waypoint, actor, UI, audio) to produce a scored-candidate list.

Scoring is a *lead* — it does not promote addresses to durable truth.

Usage:
    python scripts/rift_candidate_scorer.py \\
        --scan-result Exports/discovery-plan/stage5-live/live-memory-scan-*.json \\
        --semantic-index Exports/asset-semantic-index.json \\
        --out Exports/discovery-plan/stage5-live/scored-candidates.json

Safety: Read-only. No process attachment. All outputs under Exports/ (ignored).
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "scored-candidates/v1"

# ---------------------------------------------------------------------------
# Semantic-category scoring weights
# ---------------------------------------------------------------------------
# Higher weight = stronger asset-backed signal for that candidate category.
CATEGORY_WEIGHTS: dict[str, int] = {
    "hint:map-zone": 100,
    "hint:waypoint-poi": 90,
    "hint:actor-model": 80,
    "hint:ui-lua-xml": 70,
    "hint:audio-vfx": 60,
    "hint:quest-objective": 85,
    "type:nif": 40,
    "type:dds": 30,
    "type:xml": 25,
    "type:lua": 20,
    "type:json": 15,
    "type:ogg": 10,
    "type:rif": 10,
}

# Name-candidate boost patterns (regex matched against NameCandidates)
_NAME_BOOSTS: list[tuple[str, int]] = [
    (r"(?i)(zone|map|world|terrain| continent)", 30),
    (r"(?i)(waypoint|poi|objective|quest|task|journal)", 25),
    (r"(?i)(npc|creature|character|player|actor|unit)", 20),
    (r"(?i)(ui|frame|button|window|menu|hud|addon|lua)", 15),
    (r"(?i)(audio|sound|music|ambience|sfx)", 10),
    (r"(?i)(model|mesh|nif|texture|material)", 10),
    (r"(?i)(camera|view|render)", 10),
]

# Pattern-label boosts (from live scan pattern labels)
_LABEL_BOOSTS: list[tuple[str, int]] = [
    (r"(?i)zone|map|world", 40),
    (r"(?i)waypoint|poi|objective", 35),
    (r"(?i)player|unit|actor|npc", 30),
    (r"(?i)camera|view", 25),
    (r"(?i)lua|ui|frame|addon", 20),
    (r"(?i)audio|sound|music", 15),
    (r"(?i)float|coord|position|vec3", 20),
]


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def _build_category_index(semantic_index: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Build a lookup from semantic category → list of index entries."""
    index_by_cat: dict[str, list[dict[str, Any]]] = {}
    for entry in semantic_index.get("Entries", []):
        for cat in entry.get("SemanticCategories", []):
            index_by_cat.setdefault(cat, []).append(entry)
    return index_by_cat


def _build_name_index(semantic_index: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Build a lookup from lowercase name candidate → list of index entries."""
    name_index: dict[str, list[dict[str, Any]]] = {}
    for entry in semantic_index.get("Entries", []):
        for name in entry.get("NameCandidates", []):
            name_index.setdefault(name.lower(), []).append(entry)
    return name_index


def _score_pattern_label(label: str) -> int:
    """Score a live scan pattern label against known label-boost patterns."""
    score = 0
    for pattern, weight in _LABEL_BOOSTS:
        if re.search(pattern, label):
            score = max(score, weight)
    return score


def _score_categories(categories: list[str]) -> int:
    """Sum weights for matched semantic categories."""
    total = 0
    for cat in categories:
        total += CATEGORY_WEIGHTS.get(cat, 0)
    return total


def _score_name_candidates(names: list[str]) -> int:
    """Score name candidates against boost patterns."""
    score = 0
    for name in names:
        for pattern, weight in _NAME_BOOSTS:
            if re.search(pattern, name):
                score = max(score, weight)
                break
    return score


def _find_asset_matches(
    address_hex: str,
    pattern_label: str,
    snippet_hex: str,
    category_index: dict[str, list[dict[str, Any]]],
    name_index: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Find asset-index entries that match a live candidate by category or name overlap."""
    matches: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # Try matching by pattern label against category keys
    for cat, entries in category_index.items():
        if re.search(pattern_label, cat, re.IGNORECASE):
            for entry in entries:
                entry_id = (
                    f"{entry.get('AssetIdPrefix', '')}:{entry.get('ArchiveName', '')}:{entry.get('EntryIndex', '')}"
                )
                if entry_id not in seen_ids:
                    seen_ids.add(entry_id)
                    matches.append(entry)

    return matches


def score_candidates(
    scan_result: dict[str, Any],
    semantic_index: dict[str, Any],
) -> dict[str, Any]:
    """Score live memory scan candidates against the asset semantic index."""
    category_index = _build_category_index(semantic_index)
    name_index = _build_name_index(semantic_index)

    scored: list[dict[str, Any]] = []

    scan_result_data = scan_result.get("ScanResult", scan_result)
    for pattern_row in scan_result_data.get("PatternResults", []):
        pattern_label = pattern_row.get("Label", "")
        pattern_label_score = _score_pattern_label(pattern_label)

        for match in pattern_row.get("Matches", []):
            address = match.get("Address", "")
            snippet = match.get("SnippetHex", "")

            # Base score from pattern label
            base_score = pattern_label_score

            # Find asset-backed matches
            asset_matches = _find_asset_matches(address, pattern_label, snippet, category_index, name_index)

            # Score from asset categories
            asset_cat_score = 0
            asset_names: list[str] = []
            for am in asset_matches:
                cats = am.get("SemanticCategories", [])
                asset_cat_score = max(asset_cat_score, _score_categories(cats))
                asset_names.extend(am.get("NameCandidates", []))

            # Score from name candidates
            name_score = _score_name_candidates(asset_names)

            total_score = base_score + asset_cat_score + name_score

            scored.append(
                {
                    "Address": address,
                    "RegionBase": match.get("RegionBase", ""),
                    "OffsetInRegion": match.get("OffsetInRegion", 0),
                    "SnippetHex": snippet,
                    "PatternLabel": pattern_label,
                    "TotalScore": total_score,
                    "BaseScore": base_score,
                    "AssetCategoryScore": asset_cat_score,
                    "NameScore": name_score,
                    "AssetMatchCount": len(asset_matches),
                    "AssetCategories": list({cat for am in asset_matches for cat in am.get("SemanticCategories", [])}),
                    "AssetNames": list(set(asset_names))[:20],
                }
            )

    scored.sort(key=lambda c: c["TotalScore"], reverse=True)

    return {
        "SchemaVersion": SCHEMA_VERSION,
        "GeneratedAt": datetime.now(UTC).isoformat(),
        "SemanticIndexVersion": semantic_index.get("SchemaVersion", "unknown"),
        "SemanticIndexEntries": len(semantic_index.get("Entries", [])),
        "ScanResultPatternCount": len(scan_result_data.get("PatternResults", [])),
        "TotalCandidates": len(scored),
        "ScoredBudget": [
            "Scoring is a lead — not durable truth.",
            "High-score candidates need live readback and two-restart rediscovery.",
        ],
        "Candidates": scored,
    }


def write_scored_reports(scored: dict[str, Any], repo_root: Path, out_dir: Path | None = None) -> tuple[Path, Path]:
    """Write scored-candidate JSON and Markdown reports."""
    if out_dir is None:
        out_dir = repo_root / "Exports" / "discovery-plan" / "stage5-live"
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = out_dir / f"scored-candidates-{ts}.json"
    md_path = out_dir / f"scored-candidates-{ts}.md"

    json_path.write_text(json.dumps(scored, indent=2), encoding="utf-8")

    lines = [
        "# Scored candidates",
        "",
        f"SchemaVersion: `{scored['SchemaVersion']}`",
        f"SemanticIndexEntries: `{scored['SemanticIndexEntries']}`",
        f"TotalCandidates: `{scored['TotalCandidates']}`",
        "",
        "## Top candidates",
        "",
        "| Rank | Address | Score | Pattern | AssetCategories | AssetNames |",
        "|------|---------|-------|---------|-----------------|------------|",
    ]

    for i, c in enumerate(scored.get("Candidates", [])[:30], 1):
        cats = ", ".join(c.get("AssetCategories", [])[:3]) or "—"
        names = ", ".join(c.get("AssetNames", [])[:3]) or "—"
        lines.append(f"| {i} | `{c['Address']}` | {c['TotalScore']} | `{c['PatternLabel']}` | {cats} | {names} |")

    lines.extend(
        [
            "",
            "> Scoring is a lead — not durable truth. High-score candidates need live "
            "readback and two-restart rediscovery before promotion.",
            "",
        ]
    )

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Score live memory scan candidates against the asset semantic index.")
    parser.add_argument(
        "--scan-result",
        type=Path,
        required=True,
        help="Path to live scan result JSON.",
    )
    parser.add_argument(
        "--semantic-index",
        type=Path,
        required=True,
        help="Path to asset-semantic-index.json.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory (default: Exports/discovery-plan/stage5-live/).",
    )
    parser.add_argument(
        "--list-json",
        action="store_true",
        help="Emit machine-readable JSON to stdout.",
    )
    args = parser.parse_args(argv)

    scan_result = _load_json(args.scan_result)
    semantic_index = _load_json(args.semantic_index)

    scored = score_candidates(scan_result, semantic_index)

    if args.list_json:
        print(json.dumps(scored, indent=2))
        return

    json_path, md_path = write_scored_reports(scored, REPO_ROOT, args.out)
    print(f"Scored {scored['TotalCandidates']} candidates.")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
