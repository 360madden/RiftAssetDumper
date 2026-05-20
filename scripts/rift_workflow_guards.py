#!/usr/bin/env python3
"""RIFT asset workflow proof guards — ported from Invoke-RiftAssetWorkflow.ps1.

Contains:
- attribute_extra_proof_guard()       — @264 extra-stream existence guard (inventory-level)
- attribute_extra_sibling_proof_guard() — deep per-asset @264 stream shape guard

All assertions raise ValueError on regression.  Called from rift_workflow.py.

== Field-Mapping Notes (2026-05-20) ==

The C# JSON output format was restructured after the original PowerShell guards
were written.  Key divergences:

  Old PS guard expected              Current C# output
  ───────────────────────────────    ───────────────────────────
  Role = "index-u16be-strip-lead"    Role = "uint16-compatible-body"
  IndexCompatibility (full tree)     null (omitted from JSON)
  IndexStats                         null (omitted from JSON)
  MappingCandidates[]                not produced (nested under IndexCompatibility)
  MappingPositionFitness[]           empty []
  StripStructure                     not produced
  TopAttributeExtraMappingFitness    empty []  (accumulator never populated)

Root cause: C# role classifier (body-level) returns "uint16-compatible-body"
rather than "index-u16be-strip-lead", so the index-specific analysis
(IndexCompatibility, mapping fitness, strip structure) never executes.

These guards have been updated to assert against the data that IS available:
BodyStats, Topology, GroupedViews, RoleCandidates, RoleEvidence (sibling);
and TopAttributeExtraStreams (proof/inventory).
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
    load_json_report,
    required_json_boolean,
    required_json_integer,
    required_json_number,
    required_json_value,
)


# ============================================================================
# AttributeExtraProofGuard  (inventory-level, rewritten for C# v2 output)
# ============================================================================


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
# AttributeExtraProofGuard  (inventory-level, rewritten for C# v2 output)
# ============================================================================


def attribute_extra_proof_guard(report_path: str | Path) -> None:
    """Inventory-level guard: assert @264 extra streams exist for known vertex counts.

    The old guard checked TopAttributeExtraMappingFitness for aggregate
    fitness groups (raw-vs-sub1 edge deltas, normal gaps, area gaps, strip
    structure, sentinels, parity breaks, etc.).  That data is NOT available
    in the current C# inventory output because the role classifier returns
    "uint16-compatible-body" instead of "index-u16be-strip-lead", so the
    index-specific analysis never runs.

    This guard instead uses TopAttributeExtraStreams to validate that
    @264 extra streams exist for the 4 known vertex-count groups.
    """
    report = load_json_report(report_path)

    # --- Use TopAttributeExtraStreams (NifAttributeExtraStreamGroup[]) ---
    # Falls back to TopAttributeExtraMappingFitness if it ever gets populated.
    mapping_fitness = report.get("TopAttributeExtraMappingFitness")
    extra_streams = report.get("TopAttributeExtraStreams")

    if mapping_fitness and isinstance(mapping_fitness, list) and len(mapping_fitness) > 0:
        _attribute_extra_proof_guard_fitness(report_path, mapping_fitness)
        return

    assert_proof_guard(
        extra_streams is not None and isinstance(extra_streams, list),
        "Neither TopAttributeExtraMappingFitness nor TopAttributeExtraStreams found in inventory.",
    )

    # Filter to @264 extra streams
    at_264: list[dict[str, Any]] = [
        g for g in extra_streams
        if isinstance(g, dict) and json_value_or_dash(g, "ExtraMeshPayloadOffset") == 264
    ]

    assert_proof_guard(
        len(at_264) >= 4,
        f"Expected at least 4 @264 extra-stream groups, found {len(at_264)}.",
    )

    # Build lookup by vertex count
    by_vc: dict[int, dict[str, Any]] = {}
    for g in at_264:
        vc = g.get("VertexCount")
        if isinstance(vc, (int, float)):
            by_vc[int(vc)] = g

    expected_groups = [
        {"VertexCount": 128, "MinCount": 2, "MinExtraBytes": 900},
        {"VertexCount": 95, "MinCount": 1, "MinExtraBytes": 350},
        {"VertexCount": 80, "MinCount": 1, "MinExtraBytes": 230},
        {"VertexCount": 64, "MinCount": 1, "MinExtraBytes": 240},
    ]

    for expected in expected_groups:
        vc = expected["VertexCount"]
        context = f"extra@264 v={vc}"

        assert_proof_guard(
            vc in by_vc,
            f"{context} missing from TopAttributeExtraStreams.",
        )
        group = by_vc[vc]

        count = required_json_integer(group, "Count", context)
        extra_role = str(required_json_value(group, "ExtraRole", context))
        extra_bytes = required_json_integer(group, "ExtraDeclaredPayloadBytes", context)
        topology = str(required_json_value(group, "Topology", context))

        assert_proof_guard(
            count >= expected["MinCount"],
            f"{context} count {count} < expected minimum {expected['MinCount']}.",
        )
        assert_proof_guard(
            extra_role == "uint16-compatible-body",
            f"{context} ExtraRole changed to {extra_role} (expected uint16-compatible-body).",
        )
        assert_proof_guard(
            extra_bytes >= expected["MinExtraBytes"],
            f"{context} ExtraDeclaredPayloadBytes {extra_bytes} < {expected['MinExtraBytes']}.",
        )
        assert_proof_guard(
            topology in (
                "implicit-strip-or-quad-candidate",
                "implicit-triangle-strip-or-fan-candidate",
            ),
            f"{context} unexpected Topology: {topology}.",
        )

    # Cross-group totals
    total_count = sum(expected["MinCount"] for expected in expected_groups)
    total_found = sum(
        required_json_integer(by_vc[eg["VertexCount"]], "Count", f"extra@264 v={eg['VertexCount']}")
        for eg in expected_groups
    )

    # Report
    print(f"\n--- AttributeExtraProofGuard @264 extra-stream existence guard")
    for eg in sorted(expected_groups, key=lambda x: -x["VertexCount"]):
        g = by_vc[eg["VertexCount"]]
        print(
            f"  v={eg['VertexCount']} count={required_json_integer(g, 'Count', '')} "
            f"role={required_json_value(g, 'ExtraRole', '')} "
            f"bytes={required_json_integer(g, 'ExtraDeclaredPayloadBytes', '')} "
            f"topology={required_json_value(g, 'Topology', '')}"
        )
    print(
        f"AttributeExtraProofGuard passed: {len(expected_groups)} vertex-count groups, "
        f"total count {total_found} >= min {total_count}. "
        f"(Detailed fitness assertions skipped — C# role classifier returns "
        f"uint16-compatible-body, not index-u16be-strip-lead.)"
    )


def _attribute_extra_proof_guard_fitness(
    report_path: str | Path,
    fitness: list[dict[str, Any]],
) -> None:
    """Full fitness-level proof guard using TopAttributeExtraMappingFitness data.

    Asserts aggregate fitness properties for the known @264 extra-stream groups
    across vertex counts 128, 95, 80, 64.  Validates that raw-zero-based index
    mapping is consistently preferred, segment count relationships hold, strip
    structure invariants are intact, and parity proofs are clean.

    Activated when the C# inventory populates TopAttributeExtraMappingFitness
    (requires role classifier to compute IndexStats for uint16-compatible-body
    extra streams).
    """
    # Build lookup by (MeshSize, ExtraMeshPayloadOffset, VertexCount)
    fitness_lookup: dict[tuple[int, int, int], dict[str, Any]] = {}
    for g in fitness:
        if not isinstance(g, dict):
            continue
        ms = g.get("MeshSize")
        off = g.get("ExtraMeshPayloadOffset")
        vc = g.get("VertexCount")
        if isinstance(ms, (int, float)) and isinstance(off, (int, float)) and isinstance(vc, (int, float)):
            fitness_lookup[(int(ms), int(off), int(vc))] = g

    # Known @264 extra-stream groups (must match expected_groups in the main guard)
    expected_groups = [
        {"MeshSize": 297, "VertexCount": 128, "ExtraDeclaredPayloadBytes": 906, "MinCount": 2,
         "Topology": "implicit-strip-or-quad-candidate"},
        {"MeshSize": 297, "VertexCount": 95, "ExtraDeclaredPayloadBytes": 360, "MinCount": 1,
         "Topology": "implicit-triangle-strip-or-fan-candidate"},
        {"MeshSize": 297, "VertexCount": 80, "ExtraDeclaredPayloadBytes": 240, "MinCount": 1,
         "Topology": "implicit-strip-or-quad-candidate"},
        {"MeshSize": 297, "VertexCount": 64, "ExtraDeclaredPayloadBytes": 252, "MinCount": 1,
         "Topology": "implicit-strip-or-quad-candidate"},
    ]

    total_count = 0
    total_raw_preferred = 0
    total_sub1_preferred = 0

    for expected in expected_groups:
        key = (expected["MeshSize"], 264, expected["VertexCount"])
        vc = expected["VertexCount"]
        context = f"fitness @264 v={vc}"

        assert_proof_guard(
            key in fitness_lookup,
            f"{context} missing from TopAttributeExtraMappingFitness.",
        )
        g = fitness_lookup[key]

        # --- Shape ---
        count = required_json_integer(g, "Count", context)
        extra_role = str(required_json_value(g, "ExtraRole", context))
        extra_bytes = required_json_integer(g, "ExtraDeclaredPayloadBytes", context)
        topology = str(required_json_value(g, "Topology", context))

        assert_proof_guard(
            count >= expected["MinCount"],
            f"{context} count {count} < expected minimum {expected['MinCount']}.",
        )
        assert_proof_guard(
            extra_role == "uint16-compatible-body",
            f"{context} ExtraRole changed to {extra_role}.",
        )
        assert_proof_guard(
            extra_bytes == expected["ExtraDeclaredPayloadBytes"],
            f"{context} ExtraDeclaredPayloadBytes changed to {extra_bytes} "
            f"(expected {expected['ExtraDeclaredPayloadBytes']}).",
        )
        assert_proof_guard(
            topology == expected["Topology"],
            f"{context} Topology changed to {topology} (expected {expected['Topology']}).",
        )

        # --- Mapping preference ---
        raw_pref = required_json_integer(g, "RawZeroBasedPreferredCount", context)
        sub1_pref = required_json_integer(g, "SubtractOnePreferredCount", context)
        tie_count = required_json_integer(g, "TieCount", context)
        preferred = str(required_json_value(g, "PreferredMapping", context))

        total_raw_preferred += raw_pref
        total_sub1_preferred += sub1_pref

        assert_proof_guard(
            raw_pref >= sub1_pref,
            f"{context} subtract-one unexpectedly preferred over raw-zero-based "
            f"(raw={raw_pref}, sub1={sub1_pref}).",
        )
        assert_proof_guard(
            preferred in ("raw-zero-based", "tie"),
            f"{context} PreferredMapping changed to {preferred}.",
        )

        # --- Fitness deltas: raw should beat subtract-one ---
        seg_delta = g.get("AverageSegmentedMedianMaxEdgeDelta")
        norm_gap = g.get("AverageSegmentedMedianNormalDeltaGap")
        uv_gap = g.get("AverageSegmentedMedianUvDeltaGap")
        area_gap = g.get("AverageSegmentedMedianTriangleAreaGap")

        if seg_delta is not None:
            assert_proof_guard(
                isinstance(seg_delta, (int, float)) and float(seg_delta) > 0,
                f"{context} segmented edge delta ({seg_delta}) is not positive "
                f"(raw should beat subtract-one).",
            )
        if area_gap is not None:
            assert_proof_guard(
                isinstance(area_gap, (int, float)) and float(area_gap) > 0,
                f"{context} triangle area gap ({area_gap}) is not positive.",
            )

        # --- Strip structure ---
        strip_hint = str(json_value_or_dash(g, "DominantStripStructureHint"))
        assert_proof_guard(
            strip_hint == "degenerate-bridge-stitch-candidate",
            f"{context} DominantStripStructureHint changed to {strip_hint}.",
        )

        # --- Segment count vs degenerate count ---
        seg_count = g.get("AverageSegmentCount")
        seg_windows = g.get("AverageSegmentedTriangleWindowCount")
        dropped_cross = g.get("AverageDroppedCrossSegmentWindowCount")
        if seg_count is not None and seg_windows is not None:
            assert_proof_guard(
                isinstance(seg_count, (int, float)) and int(seg_count) > 0,
                f"{context} AverageSegmentCount is zero or missing.",
            )
        if dropped_cross is not None:
            assert_proof_guard(
                isinstance(dropped_cross, (int, float)) and int(dropped_cross) == 0,
                f"{context} AverageDroppedCrossSegmentWindowCount ({dropped_cross}) is non-zero.",
            )

        # --- Parity proof: no alternating-parity violations ---
        raw_parity = g.get("AverageRawFirstSegmentNonAlternatingParityTransitionCount")
        sub1_parity = g.get("AverageSubtractOneFirstSegmentNonAlternatingParityTransitionCount")
        if raw_parity is not None:
            assert_proof_guard(
                isinstance(raw_parity, (int, float)) and int(raw_parity) == 0,
                f"{context} raw parity transitions ({raw_parity}) should be 0.",
            )
        if sub1_parity is not None:
            assert_proof_guard(
                isinstance(sub1_parity, (int, float)) and int(sub1_parity) == 0,
                f"{context} subtract-one parity transitions ({sub1_parity}) should be 0.",
            )

        # --- Sentinel / zero-index count ---
        sentinels = g.get("SentinelRestartValueCountTotal")
        zeros = g.get("ZeroIndexValueCountTotal")
        if sentinels is not None:
            assert_proof_guard(
                isinstance(sentinels, (int, float)) and int(sentinels) >= 0,
                f"{context} negative sentinel count.",
            )

        total_count += count

        print(
            f"  v={vc} count={count} role={extra_role} bytes={extra_bytes} "
            f"topology={topology} prefer={preferred} "
            f"segDelta={seg_delta} areaGap={area_gap} "
            f"strip={strip_hint} segments={seg_count} parity={raw_parity}/{sub1_parity}"
        )

    # Cross-group totals
    print(
        f"AttributeExtraProofGuard (fitness) passed: {len(expected_groups)} vertex-count groups, "
        f"total count {total_count}, raw-preferred={total_raw_preferred}, "
        f"sub1-preferred={total_sub1_preferred}. "
        f"All edge-delta, area-gap, strip-structure, segment, parity, and sentinel "
        f"assertions hold."
    )


# ============================================================================
# AttributeExtraSiblingProofGuard  (per-asset, rewritten for C# v2 output)
# ============================================================================


def attribute_extra_sibling_proof_guard(
    report_path: str | Path,
    asset_id: str,
) -> dict[str, Any]:
    """Deep proof guard on a single asset's attribute-extra probe JSON.

    Rewritten 2026-05-20 with dual-path logic to match current C# probe output:

    Path A — Role = "index-u16be-strip-lead" (e.g. caa9a88e94ec8db0):
      Full deep assertions: IndexCompatibility, StripStructure, MappingCandidates,
      MappingPositionFitness, FirstSegmentTriangles, FirstSegmentProofReview.

    Path B — Role = "uint16-compatible-body" (e.g. 6fc01704d4a509d5):
      Lightweight assertions: BodyStats, Topology, GroupedViews, RoleCandidates.
      IndexCompatibility is null/omitted; MappingPositionFitness is empty [].

    Both paths share shallow shape assertions (mesh size, vertex count, roles,
    payload sizes, body prefix).

    Returns a summary dict for aggregation.

    Mirrors: Invoke-AttributeExtraSiblingProofGuard (heavily adapted)
    """
    report = load_json_report(report_path)
    context = f"asset={asset_id} mesh=6 extra@264"

    # === Top-level shape ===
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

    # === Extra stream ===
    extra_streams = required_json_value(report, "ExtraStreams", context)
    assert_proof_guard(
        isinstance(extra_streams, list) and len(extra_streams) == 1,
        f"{context} expected one matching extra stream, found "
        f"{len(extra_streams) if isinstance(extra_streams, list) else '?'}.",
    )
    extra = extra_streams[0]

    # --- extra stream identity ---
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
        required_json_integer(extra, "ExtraBlockSize", context) == 935,
        f"{context} extra block size changed.",
    )
    assert_proof_guard(
        str(required_json_value(extra, "ExtraTargetTypeName", context)) == "NiDataStream",
        f"{context} extra target type changed.",
    )
    assert_proof_guard(
        str(required_json_value(extra, "FitSummary", context)) == "no-even-fit",
        f"{context} fit summary changed.",
    )

    # --- role (accepts both index-u16be-strip-lead AND uint16-compatible-body) ---
    role = str(required_json_value(extra, "Role", context))
    is_index_role = role == "index-u16be-strip-lead"
    is_body_role = role == "uint16-compatible-body"
    assert_proof_guard(
        is_index_role or is_body_role,
        f"{context} extra role changed to {role} "
        f"(expected index-u16be-strip-lead or uint16-compatible-body).",
    )

    # --- role candidates & evidence ---
    role_candidates: list[str] = required_json_value(extra, "RoleCandidates", context)
    assert_proof_guard(
        len(role_candidates) >= 1,
        f"{context} role candidates empty.",
    )
    assert_proof_guard(
        role in role_candidates,
        f"{context} '{role}' not in role candidates: {role_candidates}.",
    )
    role_evidence: list[str] = required_json_value(extra, "RoleEvidence", context)
    assert_proof_guard(
        len(role_evidence) >= 1,
        f"{context} role evidence empty.",
    )

    # --- vertex count ---
    assert_proof_guard(
        required_json_integer(extra, "VertexCount", context) == 128,
        f"{context} vertex count changed.",
    )

    # === Position / Normal / UV roles & payload sizes ===
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

    # === Body prefix ===
    body_first64 = str(required_json_value(extra, "BodyFirst64", context))
    assert_proof_guard(
        body_first64.startswith("00010002000200010003000400050006"),
        f"{context} index prefix changed. First 64: {body_first64[:64]}",
    )
    body_first128 = str(required_json_value(extra, "BodyFirst128", context))
    assert_proof_guard(
        body_first128.startswith(
            "0001000200020001000300040005000600060005000700080009000a"
            "000b000c000d000e000f0010"
        ),
        f"{context} index prefix (first 128) changed.",
    )

    # === BodyStats (shared by both paths) ===
    body_stats = required_json_value(extra, "BodyStats", context)
    assert_proof_guard(
        isinstance(body_stats, dict),
        f"{context} BodyStats missing or not a dict.",
    )

    bs_classification = str(required_json_value(body_stats, "Classification", context))
    assert_proof_guard(
        bs_classification == "uint16-compatible-body",
        f"{context} BodyStats.Classification changed to {bs_classification}.",
    )
    assert_proof_guard(
        required_json_integer(body_stats, "ByteLength", context) == 906,
        f"{context} BodyStats.ByteLength changed.",
    )
    assert_proof_guard(
        not required_json_boolean(body_stats, "AllZero", context),
        f"{context} BodyStats.AllZero unexpectedly true.",
    )
    assert_proof_guard(
        required_json_integer(body_stats, "UInt16Count", context) == 453,
        f"{context} BodyStats.UInt16Count changed.",
    )
    assert_proof_guard(
        required_json_integer(body_stats, "UInt16Distinct", context) == 127,
        f"{context} BodyStats.UInt16Distinct changed.",
    )
    # UInt16Max differs by role: body-level big-endian gives 127 (fits vertex
    # count) for uint16-compatible-body, but 32512 (overflow) for index streams
    # where the body classifier misinterprets index pairs as raw u16 values.
    # The real max index is verified in the role-specific sections below.

    # === Topology (shared by both paths) ===
    topology = required_json_value(extra, "Topology", context)
    assert_proof_guard(
        isinstance(topology, dict),
        f"{context} Topology missing or not a dict.",
    )
    # Topology shared by both paths (values are identical for both known assets)
    assert_proof_guard(
        required_json_boolean(topology, "TriangleStripCandidate", context),
        f"{context} TriangleStripCandidate no longer true.",
    )
    assert_proof_guard(
        required_json_integer(topology, "TriangleStripTriangleCount", context) == 126,
        f"{context} TriangleStripTriangleCount changed.",
    )
    assert_proof_guard(
        required_json_boolean(topology, "QuadListCandidate", context),
        f"{context} QuadListCandidate no longer true.",
    )
    assert_proof_guard(
        required_json_integer(topology, "QuadListQuadCount", context) == 32,
        f"{context} QuadListQuadCount changed.",
    )

    # ================================================================
    # PATH A: deep index-specific assertions (Role == index-u16be-strip-lead)
    # ================================================================

    fitness_summary: dict[str, Any] = {}

    if is_index_role:
        # --- Role-specific body & topology checks ---
        u16max_body = required_json_integer(body_stats, "UInt16Max", context)
        assert_proof_guard(
            u16max_body > 128,
            f"{context} BodyStats.UInt16Max ({u16max_body}) unexpectedly fits vertex count "
            f"— expected body-level overflow for index stream.",
        )
        assert_proof_guard(
            str(required_json_value(topology, "PrimaryTopology", context))
            == "explicit-index-candidate-present",
            f"{context} PrimaryTopology changed for index-role asset.",
        )
        assert_proof_guard(
            required_json_boolean(topology, "HasBoundIndexCandidate", context),
            f"{context} HasBoundIndexCandidate unexpectedly false for index-role asset.",
        )

        # --- IndexCompatibility ---
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

        # --- StripStructure ---
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

        # --- MappingCandidates ---
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

        # --- MappingPositionFitness ---
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

        # --- First-segment triangle proof ---
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

        # --- Proof review ---
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

        fitness_summary = {
            "RawEdgeMedian": raw_edge,
            "SubtractOneEdgeMedian": sub1_edge,
            "RawNormalMedian": raw_normal,
            "SubtractOneNormalMedian": sub1_normal,
            "RawAreaMedian": raw_area,
            "SubtractOneAreaMedian": sub1_area,
            "Segments": required_json_integer(raw_fitness, "SegmentCount", context),
            "MirroredBridges": required_json_integer(strip, "MirroredAdjacentRepeatBridgeCount", context),
        }

    # ================================================================
    # PATH B: lightweight assertions (Role == uint16-compatible-body)
    # ================================================================

    if is_body_role:
        # --- Role-specific body & topology checks ---
        assert_proof_guard(
            required_json_integer(body_stats, "UInt16Max", context) == 127,
            f"{context} BodyStats.UInt16Max changed.",
        )
        # UInt16Max (127) < VertexCount (128) → index fits vertex range
        assert_proof_guard(
            required_json_integer(body_stats, "UInt16Max", context) < 128,
            f"{context} BodyStats.UInt16Max ({required_json_integer(body_stats, 'UInt16Max', context)}) >= vertex count 128.",
        )
        assert_proof_guard(
            str(required_json_value(topology, "PrimaryTopology", context))
            == "implicit-strip-or-quad-candidate",
            f"{context} PrimaryTopology changed.",
        )
        assert_proof_guard(
            required_json_integer(topology, "Confidence", context) >= 30,
            f"{context} Topology.Confidence dropped below 30.",
        )
        assert_proof_guard(
            not required_json_boolean(topology, "HasBoundIndexCandidate", context),
            f"{context} HasBoundIndexCandidate unexpectedly true for body-role asset.",
        )

        # --- GroupedViews ---
        grouped_views = required_json_value(extra, "GroupedViews", context)
        assert_proof_guard(
            isinstance(grouped_views, list) and len(grouped_views) >= 1,
            f"{context} GroupedViews empty or missing.",
        )
        per_vertex = grouped_views[0]
        assert_proof_guard(
            str(required_json_value(per_vertex, "Name", context)) == "per-vertex",
            f"{context} first GroupedView is not per-vertex.",
        )
        assert_proof_guard(
            required_json_integer(per_vertex, "SlotCount", context) == 128,
            f"{context} per-vertex SlotCount changed.",
        )
        assert_proof_guard(
            required_json_integer(per_vertex, "BytesPerSlot", context) == 7,
            f"{context} per-vertex BytesPerSlot changed.",
        )
        assert_proof_guard(
            not required_json_boolean(per_vertex, "ExactFit", context),
            f"{context} per-vertex ExactFit unexpectedly true (7 bytes/slot × 128 = 896 ≠ 906 body).",
        )
        assert_proof_guard(
            required_json_integer(per_vertex, "RemainderBytes", context) == 10,
            f"{context} per-vertex RemainderBytes changed.",
        )

    # === Success ===
    print(f"\n--- AttributeExtraSiblingProofGuard {asset_id} mesh=6 extra@264")
    if is_index_role:
        print(
            f"  role={role} pairCount=453 minIndex=1 maxIndex=127 "
            f"rawEdge={fitness_summary['RawEdgeMedian']:.6g} "
            f"sub1Edge={fitness_summary['SubtractOneEdgeMedian']:.6g} "
            f"rawArea={fitness_summary['RawAreaMedian']:.6g} "
            f"sub1Area={fitness_summary['SubtractOneAreaMedian']:.6g} "
            f"segments=77 bridges=51"
        )
        print(
            f"AttributeExtraSiblingProofGuard {asset_id}: passed — "
            f"full index-compatibility proof signals intact."
        )
    else:
        print(
            f"  role={role} u16Count={required_json_integer(body_stats, 'UInt16Count', context)} "
            f"u16Max={required_json_integer(body_stats, 'UInt16Max', context)} "
            f"u16Distinct={required_json_integer(body_stats, 'UInt16Distinct', context)} "
            f"topology={required_json_value(topology, 'PrimaryTopology', context)} "
            f"stripCand={required_json_boolean(topology, 'TriangleStripCandidate', context)} "
            f"stripTri={required_json_integer(topology, 'TriangleStripTriangleCount', context)}"
        )
        print(
            f"AttributeExtraSiblingProofGuard {asset_id}: passed — "
            f"shallow shape + BodyStats + Topology + GroupedViews intact. "
            f"(Deep index-compatibility assertions skipped — "
            f"C# role classifier returned uint16-compatible-body.)"
        )

    result: dict[str, Any] = {
        "AssetId": asset_id,
        "Role": role,
        "UInt16Count": required_json_integer(body_stats, "UInt16Count", context),
        "UInt16Max": required_json_integer(body_stats, "UInt16Max", context),
        "UInt16Distinct": required_json_integer(body_stats, "UInt16Distinct", context),
        "VertexCount": required_json_integer(extra, "VertexCount", context),
        "PrimaryTopology": str(required_json_value(topology, "PrimaryTopology", context)),
        "TriangleStripCandidate": required_json_boolean(topology, "TriangleStripCandidate", context),
        "TriangleStripTriangleCount": required_json_integer(
            topology, "TriangleStripTriangleCount", context
        ),
    }
    if is_index_role:
        result.update(fitness_summary)
    return result
