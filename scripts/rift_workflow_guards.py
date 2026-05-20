#!/usr/bin/env python3
"""RIFT asset workflow proof guards — ported from Invoke-RiftAssetWorkflow.ps1.

Contains:
- attribute_extra_proof_guard()       — @264 raw-zero-based regression guard
- attribute_extra_sibling_proof_guard() — deep per-asset @264 sibling proof guard

All assertions raise ValueError on regression.  Called from rift_workflow.py.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.rift_workflow_utils import (  # noqa: E402
    assert_proof_guard,
    json_value_or_dash,
    json_value_or_none,
    load_json_report,
    required_json_boolean,
    required_json_integer,
    required_json_number,
    required_json_value,
)


# ============================================================================
# Helpers (ported from Get-NamedJsonObject, Test-JsonArrayEquals)
# ============================================================================


def _get_named_json_object(
    items: list[Any],
    name: str,
    context: str,
    name_keys: tuple[str, ...] = ("Name", "MappingName"),
) -> dict[str, Any]:
    """Find exactly one object in items where a name-key matches.

    Mirrors: Get-NamedJsonObject
    """
    matches: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in name_keys:
            if str(json_value_or_dash(item, key)) == name:
                matches.append(item)
                break
    assert_proof_guard(
        len(matches) == 1,
        f"{context} expected exactly one item named {name}, found {len(matches)}.",
    )
    return matches[0]


def _test_json_array_equals(actual: list[Any], expected: list[Any]) -> bool:
    """Element-wise equality check for JSON arrays.

    Mirrors: Test-JsonArrayEquals
    """
    if len(actual) != len(expected):
        return False
    return all(a == e for a, e in zip(actual, expected))


# ============================================================================
# AttributeExtraProofGuard
# ============================================================================


def attribute_extra_proof_guard(report_path: str | Path) -> None:
    """Rerun regression guard: assert @264 extras remain raw-zero-based preferred.

    Reads mesh-binding-inventory JSON, checks 4 vertex-count groups
    (128, 95, 80, 64) at meshSize=297, extra@264, role=index-u16be-strip-lead.

    Asserts raw-zero-based is still preferred across all groups, degenerate-
    bridge-stitch structure is intact, sentinels/parity-breaks/dropped-cross
    remain at zero, and edge/normal/area deltas stay positive.

    Mirrors: Invoke-AttributeExtraProofGuard
    """
    report = load_json_report(report_path)
    fitness = report.get("TopAttributeExtraMappingFitness")
    assert_proof_guard(
        fitness is not None and isinstance(fitness, list),
        "TopAttributeExtraMappingFitness is missing from mesh-binding inventory.",
    )

    groups: list[dict[str, Any]] = list(fitness)  # type: ignore[arg-type]

    expected_groups = [
        {"VertexCount": 128, "MinCount": 2},
        {"VertexCount": 95, "MinCount": 1},
        {"VertexCount": 80, "MinCount": 1},
        {"VertexCount": 64, "MinCount": 1},
    ]

    results: list[dict[str, Any]] = []
    raw_preferred_total = 0
    subtract_one_preferred_total = 0
    tie_total = 0

    for expected in expected_groups:
        vc = expected["VertexCount"]
        context = f"meshSize=297 extra@264 v={vc}"

        # Find matching group
        matches = [
            g
            for g in groups
            if isinstance(g, dict)
            and json_value_or_dash(g, "MeshSize") == 297
            and json_value_or_dash(g, "ExtraMeshPayloadOffset") == 264
            and json_value_or_dash(g, "ExtraRole") == "index-u16be-strip-lead"
            and json_value_or_dash(g, "VertexCount") == vc
        ]
        assert_proof_guard(
            len(matches) == 1,
            f"{context} expected exactly one aggregate group, found {len(matches)}.",
        )
        group = matches[0]

        count = required_json_integer(group, "Count", context)
        raw_preferred = required_json_integer(group, "RawZeroBasedPreferredCount", context)
        sub1_preferred = required_json_integer(group, "SubtractOnePreferredCount", context)
        ties = required_json_integer(group, "TieCount", context)
        segmented_delta = required_json_number(group, "AverageSegmentedMedianMaxEdgeDelta", context)
        normal_gap = required_json_number(group, "AverageSegmentedMedianNormalDeltaGap", context)
        area_gap = required_json_number(group, "AverageSegmentedMedianTriangleAreaGap", context)
        raw_seg_edge = required_json_number(group, "AverageRawSegmentedMedianMaxEdge", context)
        sub1_seg_edge = required_json_number(group, "AverageSubtractOneSegmentedMedianMaxEdge", context)
        raw_area = required_json_number(group, "AverageRawSegmentedMedianTriangleArea", context)
        sub1_area = required_json_number(group, "AverageSubtractOneSegmentedMedianTriangleArea", context)
        dropped_cross = required_json_number(group, "AverageDroppedCrossSegmentWindowCount", context)
        raw_parity_breaks = required_json_number(
            group, "AverageRawFirstSegmentNonAlternatingParityTransitionCount", context
        )
        sub1_parity_breaks = required_json_number(
            group, "AverageSubtractOneFirstSegmentNonAlternatingParityTransitionCount", context
        )
        sentinel_restarts = required_json_integer(group, "SentinelRestartValueCountTotal", context)
        preferred_mapping = str(required_json_value(group, "PreferredMapping", context))
        strip_hint = str(required_json_value(group, "DominantStripStructureHint", context))

        # Guard assertions
        assert_proof_guard(
            count >= expected["MinCount"],
            f"{context} count {count} is below expected minimum {expected['MinCount']}.",
        )
        assert_proof_guard(
            preferred_mapping == "raw-zero-based",
            f"{context} preferred mapping changed to {preferred_mapping}.",
        )
        assert_proof_guard(
            raw_preferred == count,
            f"{context} raw preferred count {raw_preferred} does not equal group count {count}.",
        )
        assert_proof_guard(
            raw_preferred >= expected["MinCount"],
            f"{context} raw preferred count {raw_preferred} is below expected minimum {expected['MinCount']}.",
        )
        assert_proof_guard(
            sub1_preferred == 0,
            f"{context} subtract-one preferred count changed to {sub1_preferred}.",
        )
        assert_proof_guard(
            ties == 0,
            f"{context} tie count changed to {ties}.",
        )
        assert_proof_guard(
            segmented_delta > 0,
            f"{context} segmented edge delta is not positive: {segmented_delta}.",
        )
        assert_proof_guard(
            normal_gap > 0,
            f"{context} segmented normal gap is not positive: {normal_gap}.",
        )
        assert_proof_guard(
            area_gap > 0,
            f"{context} triangle area gap is not positive: {area_gap}.",
        )
        assert_proof_guard(
            raw_seg_edge < sub1_seg_edge,
            f"{context} raw segmented edge median is not lower than subtract-one.",
        )
        assert_proof_guard(
            raw_area < sub1_area,
            f"{context} raw triangle-area median is not lower than subtract-one.",
        )
        assert_proof_guard(
            strip_hint == "degenerate-bridge-stitch-candidate",
            f"{context} strip structure changed to {strip_hint}.",
        )
        assert_proof_guard(
            sentinel_restarts == 0,
            f"{context} sentinel restart total changed to {sentinel_restarts}.",
        )
        assert_proof_guard(
            dropped_cross == 0,
            f"{context} dropped cross-segment window average changed to {dropped_cross}.",
        )
        assert_proof_guard(
            raw_parity_breaks == 0,
            f"{context} raw parity break average changed to {raw_parity_breaks}.",
        )
        assert_proof_guard(
            sub1_parity_breaks == 0,
            f"{context} subtract-one parity break average changed to {sub1_parity_breaks}.",
        )

        raw_preferred_total += raw_preferred
        subtract_one_preferred_total += sub1_preferred
        tie_total += ties
        results.append({
            "VertexCount": vc,
            "Count": count,
            "RawWins": raw_preferred,
            "SubtractOneWins": sub1_preferred,
            "EdgeDelta": segmented_delta,
            "NormalGap": normal_gap,
            "AreaGap": area_gap,
            "Strip": strip_hint,
        })

    # Cross-group assertions
    assert_proof_guard(
        raw_preferred_total >= 5,
        f"raw preferred total {raw_preferred_total} is below expected minimum 5.",
    )
    assert_proof_guard(
        subtract_one_preferred_total == 0,
        f"subtract-one preferred total changed to {subtract_one_preferred_total}.",
    )
    assert_proof_guard(
        tie_total == 0,
        f"tie total changed to {tie_total}.",
    )

    # Report
    print(f"\n--- AttributeExtraProofGuard @264 raw-zero-based proof guard")
    for r in sorted(results, key=lambda x: -x["VertexCount"]):
        print(
            f"  v={r['VertexCount']} count={r['Count']} "
            f"rawWins={r['RawWins']} sub1Wins={r['SubtractOneWins']} "
            f"edgeΔ={r['EdgeDelta']:.6g} normGap={r['NormalGap']:.6g} "
            f"areaGap={r['AreaGap']:.6g} strip={r['Strip']}"
        )
    print(
        f"AttributeExtraProofGuard passed: {len(expected_groups)} groups, "
        f"raw preferred total={raw_preferred_total}, "
        f"subtract-one total={subtract_one_preferred_total}, "
        f"ties={tie_total}."
    )


# ============================================================================
# AttributeExtraSiblingProofGuard
# ============================================================================


def attribute_extra_sibling_proof_guard(
    report_path: str | Path,
    asset_id: str,
) -> dict[str, Any]:
    """Deep proof guard on a single asset's attribute-extra probe JSON.

    Asserts exact stream/block shape, index prefix, mapping candidates,
    stitch structure, first-segment triangle proof, and raw-vs-subtract-one
    fitness gaps for asset=$Id mesh=6 extra@264.

    Returns a summary dict for aggregation.

    Mirrors: Invoke-AttributeExtraSiblingProofGuard
    """
    report = load_json_report(report_path)
    context = f"asset={asset_id} mesh=6 extra@264"

    # --- top-level shape ---
    assert_proof_guard(
        required_json_integer(report, "MeshBlockIndex", context) == 6,
        f"{context} mesh block changed.",
    )
    assert_proof_guard(
        required_json_integer(report, "MeshSize", context) == 297,
        f"{context} mesh size changed.",
    )
    assert_proof_guard(
        required_json_integer(report, "AttributeSets", context) == 1,
        f"{context} attribute-set count changed.",
    )
    assert_proof_guard(
        required_json_integer(report, "ExtraMeshPayloadOffset", context) == 264,
        f"{context} report extra offset changed.",
    )
    assert_proof_guard(
        required_json_integer(report, "Matches", context) == 1,
        f"{context} match count changed.",
    )

    # --- extra stream ---
    extra_streams = required_json_value(report, "ExtraStreams", context)
    assert_proof_guard(
        isinstance(extra_streams, list) and len(extra_streams) == 1,
        f"{context} expected one matching extra stream, found {len(extra_streams) if isinstance(extra_streams, list) else '?'}.",
    )
    extra = extra_streams[0]

    assert_proof_guard(
        required_json_integer(extra, "ExtraMeshPayloadOffset", context) == 264,
        f"{context} extra stream offset changed.",
    )
    assert_proof_guard(
        required_json_integer(extra, "ExtraBlockIndex", context) == 15,
        f"{context} extra block index changed.",
    )
    assert_proof_guard(
        required_json_integer(extra, "ExtraDeclaredPayloadBytes", context) == 906,
        f"{context} extra payload size changed.",
    )
    assert_proof_guard(
        required_json_integer(extra, "HeaderBytes", context) == 29,
        f"{context} extra header size changed.",
    )
    assert_proof_guard(
        str(required_json_value(extra, "Role", context)) == "index-u16be-strip-lead",
        f"{context} extra role changed.",
    )
    assert_proof_guard(
        required_json_integer(extra, "VertexCount", context) == 128,
        f"{context} vertex count changed.",
    )
    assert_proof_guard(
        str(required_json_value(extra, "PositionRole", context)) == "position-float3-ror1-lead",
        f"{context} position role changed.",
    )
    assert_proof_guard(
        str(required_json_value(extra, "NormalRole", context)) == "normal-float3-ror1-lead",
        f"{context} normal role changed.",
    )
    assert_proof_guard(
        str(required_json_value(extra, "UvRole", context)) == "uv-float2-ror1-lead",
        f"{context} UV role changed.",
    )
    assert_proof_guard(
        required_json_integer(extra, "PositionDeclaredPayloadBytes", context) == 1536,
        f"{context} position payload size changed.",
    )
    assert_proof_guard(
        required_json_integer(extra, "NormalDeclaredPayloadBytes", context) == 1536,
        f"{context} normal payload size changed.",
    )
    assert_proof_guard(
        required_json_integer(extra, "UvDeclaredPayloadBytes", context) == 1024,
        f"{context} UV payload size changed.",
    )
    body_first64 = str(required_json_value(extra, "BodyFirst64", context))
    assert_proof_guard(
        body_first64.startswith("00010002000200010003000400050006"),
        f"{context} index prefix changed.",
    )

    # --- index compatibility ---
    idx = required_json_value(extra, "IndexCompatibility", context)
    assert_proof_guard(
        str(required_json_value(idx, "CandidateTopology", context)) == "explicit-index-strip-lead",
        f"{context} candidate topology changed.",
    )
    assert_proof_guard(
        required_json_integer(idx, "PairCount", context) == 453,
        f"{context} pair count changed.",
    )
    assert_proof_guard(
        required_json_integer(idx, "MinIndex", context) == 1,
        f"{context} min index changed.",
    )
    assert_proof_guard(
        required_json_integer(idx, "MaxIndex", context) == 127,
        f"{context} max index changed.",
    )
    assert_proof_guard(
        required_json_integer(idx, "DistinctIndexCount", context) == 127,
        f"{context} distinct index count changed.",
    )
    assert_proof_guard(
        required_json_boolean(idx, "MaxIndexWithinVertexCount", context),
        f"{context} max index no longer fits vertex count.",
    )
    assert_proof_guard(
        not required_json_boolean(idx, "UsesZeroIndex", context),
        f"{context} unexpectedly uses raw zero index.",
    )
    assert_proof_guard(
        str(required_json_value(idx, "IndexBaseHint", context)) == "one-based-or-reserved-zero-ambiguous",
        f"{context} index-base hint changed.",
    )
    assert_proof_guard(
        required_json_integer(idx, "TriangleStripWindowCount", context) == 451,
        f"{context} strip window count changed.",
    )
    assert_proof_guard(
        required_json_integer(idx, "TriangleStripNonDegenerateWindowCount", context) == 318,
        f"{context} non-degenerate strip window count changed.",
    )
    strip_deg = required_json_number(idx, "TriangleStripDegenerateRatio", context)
    triple_deg = required_json_number(idx, "DegenerateTriangleRatio", context)
    assert_proof_guard(
        strip_deg < triple_deg,
        f"{context} strip degeneracy is no longer better than fixed triples.",
    )

    # --- strip structure ---
    strip = required_json_value(idx, "StripStructure", context)
    assert_proof_guard(
        str(required_json_value(strip, "Hint", context)) == "degenerate-bridge-stitch-candidate",
        f"{context} strip structure changed.",
    )
    assert_proof_guard(
        required_json_integer(strip, "DegenerateWindowCount", context) == 133,
        f"{context} degenerate window count changed.",
    )
    assert_proof_guard(
        required_json_integer(strip, "NonDegenerateWindowCount", context) == 318,
        f"{context} non-degenerate window count changed.",
    )
    assert_proof_guard(
        required_json_integer(strip, "DegenerateRunCount", context) == 77,
        f"{context} degenerate run count changed.",
    )
    assert_proof_guard(
        required_json_integer(strip, "MaxDegenerateRunLength", context) == 2,
        f"{context} max degenerate run length changed.",
    )
    assert_proof_guard(
        required_json_integer(strip, "NonDegenerateRunCount", context) == 77,
        f"{context} non-degenerate run count changed.",
    )
    assert_proof_guard(
        required_json_integer(strip, "MaxNonDegenerateRunLength", context) == 19,
        f"{context} max non-degenerate run length changed.",
    )
    assert_proof_guard(
        required_json_integer(strip, "AdjacentRepeatCount", context) == 56,
        f"{context} adjacent repeat count changed.",
    )
    assert_proof_guard(
        required_json_integer(strip, "MirroredAdjacentRepeatBridgeCount", context) == 51,
        f"{context} mirrored bridge count changed.",
    )
    assert_proof_guard(
        required_json_integer(strip, "SentinelRestartValueCount", context) == 0,
        f"{context} sentinel restart count changed.",
    )
    assert_proof_guard(
        required_json_integer(strip, "ZeroIndexValueCount", context) == 0,
        f"{context} zero index value count changed.",
    )

    # --- mapping candidates ---
    mappings: list[dict[str, Any]] = required_json_value(idx, "MappingCandidates", context)
    raw_candidate = _get_named_json_object(mappings, "raw-zero-based", context)
    sub1_candidate = _get_named_json_object(mappings, "subtract-one", context)

    assert_proof_guard(
        required_json_boolean(raw_candidate, "ValidForVertexCount", context),
        f"{context} raw-zero-based mapping no longer fits.",
    )
    assert_proof_guard(
        required_json_boolean(sub1_candidate, "ValidForVertexCount", context),
        f"{context} subtract-one mapping no longer fits.",
    )
    assert_proof_guard(
        required_json_integer(raw_candidate, "MappedMinIndex", context) == 1
        and required_json_integer(raw_candidate, "MappedMaxIndex", context) == 127,
        f"{context} raw mapped range changed.",
    )
    assert_proof_guard(
        required_json_integer(sub1_candidate, "MappedMinIndex", context) == 0
        and required_json_integer(sub1_candidate, "MappedMaxIndex", context) == 126,
        f"{context} subtract-one mapped range changed.",
    )
    assert_proof_guard(
        _test_json_array_equals(
            required_json_value(raw_candidate, "MissingVertexSamples", context),
            [0],
        ),
        f"{context} raw missing-vertex sample changed.",
    )
    assert_proof_guard(
        _test_json_array_equals(
            required_json_value(sub1_candidate, "MissingVertexSamples", context),
            [127],
        ),
        f"{context} subtract-one missing-vertex sample changed.",
    )

    # --- mapping position fitness ---
    fitness_list: list[dict[str, Any]] = required_json_value(extra, "MappingPositionFitness", context)
    raw_fitness = _get_named_json_object(fitness_list, "raw-zero-based", context)
    sub1_fitness = _get_named_json_object(fitness_list, "subtract-one", context)

    raw_edge = required_json_number(raw_fitness, "SegmentedMedianMaxEdge", context)
    sub1_edge = required_json_number(sub1_fitness, "SegmentedMedianMaxEdge", context)
    raw_normal = required_json_number(raw_fitness, "SegmentedMedianNormalDelta", context)
    sub1_normal = required_json_number(sub1_fitness, "SegmentedMedianNormalDelta", context)
    raw_uv = required_json_number(raw_fitness, "SegmentedMedianUvDelta", context)
    sub1_uv = required_json_number(sub1_fitness, "SegmentedMedianUvDelta", context)
    raw_area = required_json_number(raw_fitness, "SegmentedMedianTriangleArea", context)
    sub1_area = required_json_number(sub1_fitness, "SegmentedMedianTriangleArea", context)

    # Fitness shape
    assert_proof_guard(
        required_json_integer(raw_fitness, "SegmentCount", context) == 77,
        f"{context} raw segment count changed.",
    )
    assert_proof_guard(
        required_json_integer(raw_fitness, "SegmentedFiniteTriangleWindowCount", context) == 318,
        f"{context} raw segmented finite window count changed.",
    )
    assert_proof_guard(
        required_json_integer(raw_fitness, "SegmentedTriangleWindowCount", context) == 318,
        f"{context} raw segmented window count changed.",
    )
    assert_proof_guard(
        required_json_integer(raw_fitness, "DroppedDegenerateWindowCount", context) == 133,
        f"{context} raw dropped-degenerate count changed.",
    )
    assert_proof_guard(
        required_json_integer(raw_fitness, "DroppedCrossSegmentWindowCount", context) == 0,
        f"{context} raw dropped-cross count changed.",
    )
    assert_proof_guard(
        required_json_integer(sub1_fitness, "SegmentCount", context) == 77,
        f"{context} subtract-one segment count changed.",
    )
    assert_proof_guard(
        required_json_integer(sub1_fitness, "SegmentedFiniteTriangleWindowCount", context) == 318,
        f"{context} subtract-one segmented finite window count changed.",
    )
    assert_proof_guard(
        required_json_integer(sub1_fitness, "SegmentedTriangleWindowCount", context) == 318,
        f"{context} subtract-one segmented window count changed.",
    )
    assert_proof_guard(
        required_json_integer(sub1_fitness, "DroppedDegenerateWindowCount", context) == 133,
        f"{context} subtract-one dropped-degenerate count changed.",
    )
    assert_proof_guard(
        required_json_integer(sub1_fitness, "DroppedCrossSegmentWindowCount", context) == 0,
        f"{context} subtract-one dropped-cross count changed.",
    )

    # Fitness deltas
    assert_proof_guard(
        raw_edge < sub1_edge and (sub1_edge - raw_edge) > 4,
        f"{context} raw edge fitness no longer clearly beats subtract-one.",
    )
    assert_proof_guard(
        raw_normal < sub1_normal and (sub1_normal - raw_normal) > 0.3,
        f"{context} raw normal fitness no longer clearly beats subtract-one.",
    )
    assert_proof_guard(
        raw_uv <= sub1_uv,
        f"{context} raw UV fitness is worse than subtract-one.",
    )
    assert_proof_guard(
        raw_area < sub1_area and (sub1_area - raw_area) > 10,
        f"{context} raw triangle-area fitness no longer clearly beats subtract-one.",
    )

    # --- first-segment triangle proof ---
    raw_triangles: list[dict[str, Any]] = required_json_value(raw_fitness, "FirstSegmentTriangles", context)
    sub1_triangles: list[dict[str, Any]] = required_json_value(sub1_fitness, "FirstSegmentTriangles", context)
    assert_proof_guard(
        len(raw_triangles) == 24,
        f"{context} raw first-segment triangle proof count changed.",
    )
    assert_proof_guard(
        len(sub1_triangles) == 24,
        f"{context} subtract-one first-segment triangle proof count changed.",
    )

    raw_first = raw_triangles[0]
    sub1_first = sub1_triangles[0]
    assert_proof_guard(
        required_json_integer(raw_first, "StripWindowIndex", context) == 2
        and required_json_integer(raw_first, "A", context) == 2
        and required_json_integer(raw_first, "B", context) == 1
        and required_json_integer(raw_first, "C", context) == 3,
        f"{context} first raw triangle changed.",
    )
    assert_proof_guard(
        required_json_integer(sub1_first, "StripWindowIndex", context) == 2
        and required_json_integer(sub1_first, "A", context) == 1
        and required_json_integer(sub1_first, "B", context) == 0
        and required_json_integer(sub1_first, "C", context) == 2,
        f"{context} first subtract-one triangle changed.",
    )
    assert_proof_guard(
        str(required_json_value(raw_first, "DominantAreaPlane", context)) == "xy"
        and required_json_number(raw_first, "DominantSignedArea", context) > 0,
        f"{context} first raw signed-area proof changed.",
    )
    assert_proof_guard(
        str(required_json_value(sub1_first, "DominantAreaPlane", context)) == "xy"
        and required_json_number(sub1_first, "DominantSignedArea", context) < 0,
        f"{context} first subtract-one signed-area proof changed.",
    )

    # --- proof review ---
    raw_review = required_json_value(raw_fitness, "FirstSegmentProofReview", context)
    sub1_review = required_json_value(sub1_fitness, "FirstSegmentProofReview", context)
    assert_proof_guard(
        required_json_integer(raw_review, "TriangleSampleCount", context) == 24,
        f"{context} raw proof-review sample count changed.",
    )
    assert_proof_guard(
        required_json_integer(sub1_review, "TriangleSampleCount", context) == 24,
        f"{context} subtract-one proof-review sample count changed.",
    )
    assert_proof_guard(
        required_json_integer(raw_review, "NonAlternatingParityTransitionCount", context) == 0,
        f"{context} raw parity proof changed.",
    )
    assert_proof_guard(
        required_json_integer(sub1_review, "NonAlternatingParityTransitionCount", context) == 0,
        f"{context} subtract-one parity proof changed.",
    )

    # --- success ---
    print(f"\n--- AttributeExtraSiblingProofGuard {asset_id} mesh=6 extra@264")
    print(
        f"  rawEdge={raw_edge:.6g} sub1Edge={sub1_edge:.6g} "
        f"rawNormal={raw_normal:.6g} sub1Normal={sub1_normal:.6g} "
        f"rawArea={raw_area:.6g} sub1Area={sub1_area:.6g} "
        f"segments=77 bridges=51"
    )
    print(f"AttributeExtraSiblingProofGuard {asset_id}: passed — proof signals intact.")

    return {
        "AssetId": asset_id,
        "RawEdgeMedian": raw_edge,
        "SubtractOneEdgeMedian": sub1_edge,
        "RawNormalMedian": raw_normal,
        "SubtractOneNormalMedian": sub1_normal,
        "RawAreaMedian": raw_area,
        "SubtractOneAreaMedian": sub1_area,
        "Segments": required_json_integer(raw_fitness, "SegmentCount", context),
        "MirroredBridges": required_json_integer(
            strip, "MirroredAdjacentRepeatBridgeCount", context
        ),
    }
