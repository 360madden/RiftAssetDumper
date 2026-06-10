#!/usr/bin/env python3
"""validate_meshsize_inference.py — Cross-validate vc_proximity mesh_size inferences against ground truth.

Loads the enriched probe-meshsize-lookup and export manifest, separates ground-truth from inferred
entries, then cross-validates each vc_proximity inference by:
  1. Checking if any ground-truth entry with the same vertex_count has the same mesh_size
  2. Measuring vertex_count delta from nearest ground-truth entry with the same mesh_size
  3. Detecting (VC, FC) pattern collisions where different mesh_sizes map to the same pattern
  4. Computing per-entry confidence scores and aggregate accuracy metrics

Output: Assets/build/flythrough/evidence/ft8.1/meshsize-validation-report.json
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROBE_LOOKUP = Path("Exports/probe-meshsize-lookup.json")
EXPORT_MANIFEST = Path("Exports/export-manifest.json")
EVIDENCE_DIR = Path("Assets/build/flythrough/evidence/ft8.1")
OUT_PATH = EVIDENCE_DIR / "meshsize-validation-report.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    pl = _load_json(PROBE_LOOKUP)
    em = _load_json(EXPORT_MANIFEST)

    entries = pl.get("entries", {})
    if not entries:
        print("No probe lookup entries found.")
        return

    # Build aid -> {vc, fc, desc, faced} from export manifest
    aid_info: dict[str, dict[str, Any]] = {}
    for e in em.get("entries", []):
        aid = e.get("asset_id", "")
        if aid and len(aid) == 16:
            aid_info[aid] = {
                "vc": e.get("vertex_count", 0),
                "fc": e.get("face_count", 0),
                "desc": e.get("descriptor", ""),
                "faced": e.get("faced", False),
            }

    # Classify entries by inference method
    ground_truth: dict[str, dict[str, Any]] = {}  # original probes
    vc_proximity: dict[str, dict[str, Any]] = {}  # vc_proximity inferred
    exact_match: dict[str, dict[str, Any]] = {}  # exact (VC,FC) match
    sibling_pair: dict[str, dict[str, Any]] = {}  # sibling_pair fallback
    probe_verified: dict[str, dict[str, Any]] = {}  # verified by live probe

    for aid, pinfo in entries.items():
        note = str(pinfo.get("note", ""))
        ms = pinfo.get("meshsize")
        entry_data = {"aid": aid, "mesh_size": ms, "note": note}
        if aid in aid_info:
            entry_data.update(aid_info[aid])

        if "ground_truth" in note.lower() or "probe_verified" in note.lower():
            probe_verified[aid] = entry_data
        elif "vc_proximity" in note:
            vc_proximity[aid] = entry_data
        elif "exact_match" in note:
            exact_match[aid] = entry_data
        elif "sibling_pair" in note:
            sibling_pair[aid] = entry_data
        else:
            # Original probe entries = ground truth
            ground_truth[aid] = entry_data

    # Build ground-truth lookups
    # (VC, FC) -> set of mesh_sizes (for conflict detection)
    gt_patterns: dict[tuple[int, int], set[int]] = {}
    # mesh_size -> list of (aid, vc, fc) for proximity checks
    gt_by_ms: dict[int, list[dict[str, Any]]] = {}
    # vertex_count -> set of mesh_sizes
    gt_vc_to_ms: dict[int, set[int]] = {}

    for _aid, entry in {**ground_truth, **probe_verified}.items():
        ms = entry.get("mesh_size")
        vc = entry.get("vc", 0)
        fc = entry.get("fc", 0)
        if ms is not None:
            key = (vc, fc)
            gt_patterns.setdefault(key, set()).add(ms)
            gt_by_ms.setdefault(ms, []).append(entry)
            gt_vc_to_ms.setdefault(vc, set()).add(ms)

    # Detect (VC, FC) pattern collisions in ground truth
    collisions = {k: v for k, v in gt_patterns.items() if len(v) > 1}

    # Validate each vc_proximity entry
    validated: list[dict[str, Any]] = []
    correct = 0
    likely_correct = 0
    uncertain = 0
    likely_wrong = 0

    for aid, entry in vc_proximity.items():
        inferred_ms = entry.get("mesh_size")
        vc = entry.get("vc", 0)
        fc = entry.get("fc", 0)
        if inferred_ms is None or vc == 0:
            continue

        # Check 1: Does ground truth have the same (VC, FC) with same mesh_size?
        # (This would mean an exact_match should have caught it — sanity check)
        pattern_ms_set = gt_patterns.get((vc, fc), set())
        pattern_agree = inferred_ms in pattern_ms_set
        pattern_conflict = len(pattern_ms_set) > 0 and inferred_ms not in pattern_ms_set

        # Check 2: Does any ground-truth entry with same VC have same mesh_size?
        vc_ms_set = gt_vc_to_ms.get(vc, set())
        vc_agree = inferred_ms in vc_ms_set

        # Check 3: Nearest ground-truth entry with same mesh_size (VC delta)
        same_ms_entries = gt_by_ms.get(inferred_ms, [])
        nearest_vc_delta = None
        if same_ms_entries:
            nearest_vc_delta = min(abs(e.get("vc", 0) - vc) for e in same_ms_entries)

        # Check 4: Vertex count proximity ratio
        vc_ratio = None
        if same_ms_entries:
            nearest_vc = min(
                same_ms_entries,
                key=lambda e: abs(e.get("vc", 0) - vc),
            ).get("vc", 0)
            if nearest_vc > 0:
                vc_ratio = abs(vc - nearest_vc) / max(vc, nearest_vc)

        # Confidence scoring
        confidence: float = 0.0
        flags: list[str] = []

        if pattern_agree:
            confidence = 0.95
            flags.append("pattern_agree")
        elif vc_agree:
            confidence = 0.85
            flags.append("vc_agree")
        elif pattern_conflict:
            confidence = 0.1
            flags.append("pattern_conflict")
        elif nearest_vc_delta is not None:
            # Score based on VC proximity
            if nearest_vc_delta == 0:
                confidence = 0.9
                flags.append("vc_exact_match")
            elif vc_ratio is not None and vc_ratio <= 0.1:
                confidence = 0.75
                flags.append("vc_close_10pct")
            elif vc_ratio is not None and vc_ratio <= 0.2:
                confidence = 0.6
                flags.append("vc_close_20pct")
            elif vc_ratio is not None and vc_ratio <= 0.3:
                confidence = 0.4
                flags.append("vc_moderate")
            else:
                confidence = 0.25
                flags.append("vc_distant")
        else:
            confidence = 0.15
            flags.append("no_gt_match")

        # Classify
        if confidence >= 0.8:
            correct += 1
            category = "correct"
        elif confidence >= 0.55:
            likely_correct += 1
            category = "likely_correct"
        elif confidence >= 0.3:
            uncertain += 1
            category = "uncertain"
        else:
            likely_wrong += 1
            category = "likely_wrong"

        validated.append(
            {
                "asset_id": aid,
                "inferred_mesh_size": inferred_ms,
                "vertex_count": vc,
                "face_count": fc,
                "nearest_gt_vc_delta": nearest_vc_delta,
                "vc_ratio": round(vc_ratio, 4) if vc_ratio is not None else None,
                "pattern_agree": pattern_agree,
                "vc_agree": vc_agree,
                "pattern_conflict": pattern_conflict,
                "confidence": round(confidence, 4),
                "confidence_category": category,
                "flags": flags,
            }
        )

    # Sort by confidence ascending (worst first)
    validated.sort(key=lambda v: v["confidence"])

    # Build report
    total = len(validated)
    report = {
        "schema": "meshsize-validation-report-v1",
        "generated": datetime.now(UTC).isoformat(),
        "summary": {
            "total_ground_truth": len(ground_truth),
            "total_probe_verified": len(probe_verified),
            "total_exact_match": len(exact_match),
            "total_vc_proximity": total,
            "total_sibling_pair": len(sibling_pair),
            "pattern_collisions_in_ground_truth": len(collisions),
            "vc_proximity_accuracy": {
                "correct": correct,
                "likely_correct": likely_correct,
                "uncertain": uncertain,
                "likely_wrong": likely_wrong,
                "high_confidence_pct": (round(100 * (correct + likely_correct) / max(1, total), 1)),
            },
        },
        "collisions": [
            {
                "vertex_count": vc,
                "face_count": fc,
                "mesh_sizes": sorted(ms_set),
            }
            for (vc, fc), ms_set in sorted(collisions.items())
        ],
        "validated_entries": validated,
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    # Print summary
    print(f"Ground-truth entries: {len(ground_truth)}")
    print(f"Probe-verified entries: {len(probe_verified)}")
    print(f"Exact-match inferred: {len(exact_match)}")
    print(f"VC-proximity inferred: {total}")
    print(f"Sibling-pair inferred: {len(sibling_pair)}")
    print()
    print(f"Pattern collisions in ground truth: {len(collisions)}")
    if collisions:
        for (vc, fc), ms_set in sorted(collisions.items()):
            print(f"  (VC={vc}, FC={fc}) -> mesh_sizes={sorted(ms_set)}")
    print()
    print("VC-proximity accuracy:")
    print(f"  Correct (>=0.80):         {correct} ({round(100 * correct / max(1, total), 1)}%)")
    print(f"  Likely correct (>=0.55):  {likely_correct} ({round(100 * likely_correct / max(1, total), 1)}%)")
    print(f"  Uncertain (>=0.30):       {uncertain} ({round(100 * uncertain / max(1, total), 1)}%)")
    print(f"  Likely wrong (<0.30):     {likely_wrong} ({round(100 * likely_wrong / max(1, total), 1)}%)")
    print(
        f"  High confidence total:    {correct + likely_correct}/{total} ({round(100 * (correct + likely_correct) / max(1, total), 1)}%)"
    )
    print()
    print(f"Report written: {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
