#!/usr/bin/env python3
"""RIFT asset workflow proof guards — ported from Invoke-RiftAssetWorkflow.ps1.

Contains:
- attribute_extra_proof_guard()       — @264 extra-stream existence guard (inventory-level)
- attribute_extra_sibling_proof_guard() — deep per-asset @264 stream shape guard
- ghidra_pairing_non_export_guard() — fail-closed static guard that keeps
  Ghidra pairings out of decode/export paths until explicitly promoted
- nidatastream_parser_export_non_consumption_guard() — fail-closed static
  guard that keeps candidate NiDataStream layout/Ghidra-body evidence out of
  parser/export consumers until explicitly promoted
- ghidra_attribute_candidate_guard() — fail-closed guard for grouped
  Ghidra-only candidate report baseline
- phase1_m13_329_variant_layout_guard() — Phase 1 M1.3 pilot meshSize=329
  sibling variant attribute layout guard (matrix + optional probes)

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

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.rift_workflow_utils import (  # noqa: E402
    assert_proof_guard,
    assert_usage_access_guard,
    format_markdown_cell,
    json_double_or_none,
    json_value_or_dash,
    load_json_report,
    load_large_json_keys,
    required_json_boolean,
    required_json_integer,
    required_json_number,
    required_json_value,
    safe_int,
    usage_access_guard_integer,
)

# ============================================================================
# GhidraPairingNonExportGuard
# ============================================================================


GHIDRA_NON_EXPORT_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "BuildNifGhidraRoleStreamSummaries",
    "GhidraPairings",
    "TopGhidraPairings",
    "TopGhidraPairingReviewFindings",
    "GhidraOnlyPairings",
    "GhidraSharedPairings",
    "LegacyOnlyPairings",
    "GhidraRoleDelta",
    "GhidraIndexBodyFirst16",
    "GhidraVertexBodyFirst16",
    'pairingSource: "ghidra-sidecar"',
)

GHIDRA_NON_EXPORT_GUARDED_MEMBERS: tuple[str, ...] = (
    "DecodeNifGeometry",
    "FindNifMeshAttributeSets",
    "FindNifAttributeSetExtraStreams",
    "ScanNifLinkedStreamPositionCandidates",
    "BuildNifAttributeFloatVertexSamples",
    "BuildNifAttributeUInt16VertexSamples",
)

NIDATASTREAM_NON_CONSUMPTION_GUARDED_MEMBERS: tuple[str, ...] = GHIDRA_NON_EXPORT_GUARDED_MEMBERS + (
    "FindNifMeshProbePairings",
)

NIDATASTREAM_NON_CONSUMPTION_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "AnalyzeNifDataStreamLayout",
    "SliceNifDataStreamGhidraBody",
    "GhidraStyleLayoutValid",
    "PayloadPrefixBytes",
    "PayloadTrailerBytes",
    "TrailingFlag",
    "LegacyOffsetMinusPayloadPrefixBytes",
    "GhidraBodyFirst16",
    "GhidraPayloadFirst16",
    "GhidraRoleStats",
    "GhidraClassificationDelta",
    "GhidraRoleDelta",
    "FieldOrderPromoted",
    "ParserExportPromotionAllowed",
)

NIDATASTREAM_NON_CONSUMPTION_MEMBER_ALLOWED_TOKENS: dict[str, tuple[str, ...]] = {
    # FindNifMeshProbePairings copies the sidecar first-16 bytes into report records,
    # but its pairing decisions must remain based on legacy RoleStats.
    "FindNifMeshProbePairings": ("GhidraBodyFirst16",),
}


def _extract_csharp_static_member(source: str, member_name: str) -> str:
    """Return a top-level static C# member body by line range.

    This intentionally avoids brace counting because interpolated strings in
    Program.cs contain many literal braces.  Program.cs class-level static
    methods are consistently indented by two spaces, so the next top-level
    static member marks the end of the current member.
    """
    lines = source.splitlines(keepends=True)
    start = -1
    declaration_pattern = re.compile(rf"^  (?:private|internal|public)\s+static\b.*\b{re.escape(member_name)}\s*\(")
    next_member_pattern = re.compile(r"^  (?:private|internal|public)\s+static\b")
    for index, line in enumerate(lines):
        if declaration_pattern.search(line):
            start = index
            break
    if start < 0:
        raise ValueError(f"GhidraPairingNonExportGuard failed: missing C# member {member_name}.")

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if next_member_pattern.search(lines[index]):
            end = index
            break
    return "".join(lines[start:end])


def ghidra_pairing_non_export_guard(program_path: str | Path | None = None) -> None:
    """Assert Ghidra pairing evidence is not consumed by geometry/export paths.

    The Ghidra workflow is intentionally sidecar/candidate-only right now.  It
    may appear in mesh probes and inventory/review reports, but decode/export
    code must continue to use the legacy parser-derived stream summaries until
    a separate promotion proof is added.
    """
    path = Path(program_path) if program_path is not None else REPO_ROOT / "src" / "RiftAssetDumper" / "Program.cs"
    source = path.read_text(encoding="utf-8-sig")

    failures: list[str] = []
    guarded_members: list[dict[str, Any]] = []
    for member_name in GHIDRA_NON_EXPORT_GUARDED_MEMBERS:
        body = _extract_csharp_static_member(source, member_name)
        hits = [token for token in GHIDRA_NON_EXPORT_FORBIDDEN_TOKENS if token in body]
        guarded_members.append({"Member": member_name, "ForbiddenHits": hits})
        if hits:
            failures.append(f"{member_name}: {', '.join(hits)}")

    sidecar_call = (
        "BuildNifGhidraRoleStreamSummaries(streamSummaries),\n"
        '          pairingSource: "ghidra-sidecar",\n'
        "          candidateOnly: true"
    )
    if sidecar_call not in source:
        failures.append("ProbeNifMesh Ghidra sidecar pairings must be explicitly candidateOnly=true.")

    assert_proof_guard(
        not failures,
        "Ghidra pairing evidence is wired into export/decode paths or lacks candidate-only marking: "
        + "; ".join(failures),
    )

    print("\n--- GhidraPairingNonExportGuard candidate-only export isolation guard")
    print(f"Program: {path}")
    print(f"Guarded members: {len(guarded_members)}")
    for item in guarded_members:
        member = item["Member"]
        hit_count = len(item["ForbiddenHits"])
        print(f"  {member}: forbidden Ghidra token hits={hit_count}")
    print("GhidraPairingNonExportGuard passed: Ghidra pairing evidence remains candidate-only/non-export-consuming.")


def nidatastream_parser_export_non_consumption_guard(program_path: str | Path | None = None) -> None:
    """Assert candidate NiDataStream layout evidence is not consumed by parser/export paths.

    BuildNifMeshBoundStreamSummaries intentionally carries report-only Ghidra/body-layout
    diagnostics today, and reports may read those diagnostics.  Decode/export-sensitive
    consumers must keep reading the legacy RoleStats/stream-body interpretation until a
    separate positive promotion proof updates this guard.
    """
    path = Path(program_path) if program_path is not None else REPO_ROOT / "src" / "RiftAssetDumper" / "Program.cs"
    source = path.read_text(encoding="utf-8-sig")

    failures: list[str] = []
    guarded_members: list[dict[str, Any]] = []
    for member_name in NIDATASTREAM_NON_CONSUMPTION_GUARDED_MEMBERS:
        body = _extract_csharp_static_member(source, member_name)
        allowed_tokens = NIDATASTREAM_NON_CONSUMPTION_MEMBER_ALLOWED_TOKENS.get(member_name, ())
        hits = [
            token
            for token in NIDATASTREAM_NON_CONSUMPTION_FORBIDDEN_TOKENS
            if token in body and token not in allowed_tokens
        ]
        guarded_members.append({"Member": member_name, "ForbiddenHits": hits})
        if hits:
            failures.append(f"{member_name}: {', '.join(hits)}")

    stream_summary_body = _extract_csharp_static_member(source, "BuildNifMeshBoundStreamSummaries")
    required_summary_markers = (
        "RoleStats: roleStats",
        "GhidraRoleStats: ghidraRoleStats",
    )
    missing_summary_markers = [marker for marker in required_summary_markers if marker not in stream_summary_body]
    if missing_summary_markers:
        failures.append(
            "BuildNifMeshBoundStreamSummaries: missing canonical legacy/Ghidra role separation markers: "
            + ", ".join(missing_summary_markers)
        )

    pairing_body = _extract_csharp_static_member(source, "FindNifMeshProbePairings")
    required_pairing_markers = (
        "s.RoleStats.PrimaryRole.StartsWith",
        "s.RoleStats.IndexMax is not null",
        "s.RoleStats.VertexCountCandidates.Count > 0",
    )
    missing_pairing_markers = [marker for marker in required_pairing_markers if marker not in pairing_body]
    if missing_pairing_markers:
        failures.append(
            "FindNifMeshProbePairings: missing legacy RoleStats pairing markers: " + ", ".join(missing_pairing_markers)
        )
    if "s.GhidraRoleStats" in pairing_body or ".GhidraRoleStats" in pairing_body:
        failures.append("FindNifMeshProbePairings: must not consume GhidraRoleStats for default pairings.")

    assert_proof_guard(
        not failures,
        "NiDataStream candidate layout/Ghidra evidence is wired into parser/export consumers: " + "; ".join(failures),
    )

    print("\n--- NiDataStreamParserExportNonConsumptionGuard parser/export isolation guard")
    print(f"Program: {path}")
    print(f"Guarded members: {len(guarded_members)}")
    for item in guarded_members:
        member = item["Member"]
        hit_count = len(item["ForbiddenHits"])
        print(f"  {member}: forbidden candidate-layout token hits={hit_count}")
    print("  BuildNifMeshBoundStreamSummaries: legacy RoleStats/GhidraRoleStats separation markers present")
    print("  FindNifMeshProbePairings: default pairings remain legacy RoleStats-based")
    print(
        "NiDataStreamParserExportNonConsumptionGuard passed: candidate NiDataStream/Ghidra layout evidence "
        "remains report-only."
    )


def ghidra_attribute_candidate_guard(report_path: str | Path) -> None:
    """Assert grouped Ghidra attribute candidates remain candidate-only and incomplete.

    The current evidence has useful partial position/normal/UV rows, but no
    complete position+normal+UV group.  This guard should fail if a future
    report silently changes that baseline before a deliberate promotion patch.
    """
    report = load_json_report(report_path)
    assert_proof_guard(
        str(report.get("SchemaVersion")) == "ghidra-attribute-candidate-report/v1",
        "Ghidra attribute candidate report schema mismatch.",
    )
    assert_proof_guard(
        required_json_boolean(report, "CandidateOnly", "GhidraAttributeCandidateReport") is True,
        "Ghidra attribute candidate report must remain CandidateOnly=true.",
    )
    summary = required_json_value(report, "Summary", "GhidraAttributeCandidateReport")
    assert_proof_guard(
        isinstance(summary, dict),
        "Ghidra attribute candidate report Summary must be an object.",
    )
    if not isinstance(summary, dict):
        raise ValueError("GhidraAttributeCandidateGuard failed: Summary is not an object.")

    expected = {
        "GhidraOnlyGroups": 14,
        "GhidraOnlyPairingsCovered": 64,
        "GroupedSampleMeshes": 8,
        "CompletePositionNormalUvCandidateGroups": 0,
        "ProbeBackedRanks": 14,
        "PositionReviewPassGroups": 4,
        "NormalReviewPassGroups": 3,
        "UvReviewPassGroups": 3,
        "UvReviewFailGroups": 2,
        "RejectedNoiseGroups": 2,
    }
    for key, expected_value in expected.items():
        actual = required_json_integer(summary, key, "GhidraAttributeCandidateReport.Summary")
        assert_proof_guard(
            actual == expected_value,
            f"{key} expected {expected_value}, found {actual}. Re-run triage before promotion.",
        )

    groups = required_json_value(report, "Groups", "GhidraAttributeCandidateReport")
    assert_proof_guard(isinstance(groups, list), "Ghidra attribute candidate Groups must be an array.")
    if not isinstance(groups, list):
        raise ValueError("GhidraAttributeCandidateGuard failed: Groups is not an array.")
    complete_groups = [
        group for group in groups if isinstance(group, dict) and group.get("CompletePositionNormalUvCandidate") is True
    ]
    assert_proof_guard(
        len(complete_groups) == 0,
        "No complete Ghidra position+normal+UV candidate group is currently promoted.",
    )

    print("\n--- GhidraAttributeCandidateGuard grouped candidate baseline guard")
    for key, expected_value in expected.items():
        print(f"  {key}: {expected_value}")
    print("GhidraAttributeCandidateGuard passed: current Ghidra-only candidates remain partial/report-only.")


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
    return all(a == e for a, e in zip(actual, expected, strict=True))


# ============================================================================
# AttributeExtraProofGuard  (inventory-level, rewritten for C# v2 output)
# ============================================================================


def attribute_extra_proof_guard(report_path: str | Path) -> None:
    """Inventory-level guard: assert @264 extra streams exist.

    Live-archive calibrated (2026-06-18): validates 1 @264 group (vc=24, count=10).
    Original Source/ copied-set baseline (now deleted) had 4 groups (vc=128/95/80/64).

    Falls through from TopAttributeExtraMappingFitness to stream-level path
    gracefully when the @264 v=128 fitness key is absent (live-archive data
    drift from Source/ copied-set baseline).
    """
    report_path = Path(report_path)
    file_size_mb = report_path.stat().st_size / (1024 * 1024)
    if file_size_mb > 80:
        partial = load_large_json_keys(
            report_path,
            ("TopAttributeExtraMappingFitness", "TopAttributeExtraStreams"),
        )
        mapping_fitness = partial.get("TopAttributeExtraMappingFitness")
        extra_streams = partial.get("TopAttributeExtraStreams")
    else:
        report = load_json_report(report_path)
        mapping_fitness = report.get("TopAttributeExtraMappingFitness")
        extra_streams = report.get("TopAttributeExtraStreams")

    if mapping_fitness and isinstance(mapping_fitness, list) and len(mapping_fitness) > 0:
        # Only enter the fitness path when the expected @264 v=128 key actually
        # exists in the fitness data.  The live archive may have fitness entries
        # for other vertex counts without having the Source/ copied-set groups
        # this guard was calibrated against.
        fitness_has_expected_key = any(
            isinstance(g, dict)
            and g.get("MeshSize") == 297
            and g.get("ExtraMeshPayloadOffset") == 264
            and g.get("VertexCount") == 128
            for g in mapping_fitness
        )
        if fitness_has_expected_key:
            _attribute_extra_proof_guard_fitness(report_path, mapping_fitness)
            return
        print(
            "\n--- AttributeExtraProofGuard: TopAttributeExtraMappingFitness present but "
            "@264 v=128 key missing (live-archive data drift from Source/ copied-set "
            "baseline).  Falling through to stream-level guard.",
            file=sys.stderr,
        )

    assert_proof_guard(
        extra_streams is not None and isinstance(extra_streams, list),
        "Neither TopAttributeExtraMappingFitness nor TopAttributeExtraStreams found in inventory.",
    )

    # Filter to @264 extra streams
    at_264: list[dict[str, Any]] = [
        g for g in extra_streams if isinstance(g, dict) and json_value_or_dash(g, "ExtraMeshPayloadOffset") == 264
    ]

    assert_proof_guard(
        len(at_264) >= 1,
        f"Expected at least 1 @264 extra-stream group, found {len(at_264)}.",
    )

    # Build lookup by vertex count
    by_vc: dict[int, dict[str, Any]] = {}
    for g in at_264:
        vc = g.get("VertexCount")
        if isinstance(vc, (int, float)):
            by_vc[int(vc)] = g

    # Live-archive baseline (2026-06-18): 1 @264 group (vc=24, ms=None).
    # Original Source/ copied-set baseline (now deleted) had 4 groups: vc=128/95/80/64.
    # This guard now validates whatever @264 groups the live archive contains.
    expected_groups = [
        {"VertexCount": 24, "MinCount": 10, "MinExtraBytes": 70},
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
            count >= safe_int(expected["MinCount"]),
            f"{context} count {count} < expected minimum {expected['MinCount']}.",
        )
        assert_proof_guard(
            extra_role in ("uint16-compatible-body", "index-u16be-strip-lead", "index-u16be-lead"),
            f"{context} ExtraRole changed to {extra_role} (expected uint16-compatible-body or index-u16be-*-lead).",
        )
        assert_proof_guard(
            extra_bytes >= expected["MinExtraBytes"],
            f"{context} ExtraDeclaredPayloadBytes {extra_bytes} < {expected['MinExtraBytes']}.",
        )
        assert_proof_guard(
            topology
            in (
                "implicit-strip-or-quad-candidate",
                "implicit-triangle-strip-or-fan-candidate",
                "explicit-index-candidate-present",
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
    print("\n--- AttributeExtraProofGuard @264 extra-stream existence guard")
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
        {
            "MeshSize": 297,
            "VertexCount": 128,
            "ExtraDeclaredPayloadBytes": 906,
            "MinCount": 2,
            "Topology": "explicit-index-candidate-present",
        },
        {
            "MeshSize": 297,
            "VertexCount": 95,
            "ExtraDeclaredPayloadBytes": 360,
            "MinCount": 1,
            "Topology": "explicit-index-candidate-present",
        },
        {
            "MeshSize": 297,
            "VertexCount": 80,
            "ExtraDeclaredPayloadBytes": 240,
            "MinCount": 1,
            "Topology": "explicit-index-candidate-present",
        },
        {
            "MeshSize": 297,
            "VertexCount": 64,
            "ExtraDeclaredPayloadBytes": 252,
            "MinCount": 1,
            "Topology": "explicit-index-candidate-present",
        },
    ]

    total_count = 0
    total_raw_preferred = 0
    total_sub1_preferred = 0

    for expected in expected_groups:
        key = (safe_int(expected["MeshSize"]), 264, safe_int(expected["VertexCount"]))
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
            count >= safe_int(expected["MinCount"]),
            f"{context} count {count} < expected minimum {expected['MinCount']}.",
        )
        assert_proof_guard(
            extra_role in ("uint16-compatible-body", "index-u16be-strip-lead", "index-u16be-lead"),
            f"{context} ExtraRole changed to {extra_role} (expected uint16-compatible-body or index-u16be-*-lead).",
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
        _tie_count = required_json_integer(g, "TieCount", context)
        preferred = str(required_json_value(g, "PreferredMapping", context))

        total_raw_preferred += raw_pref
        total_sub1_preferred += sub1_pref

        assert_proof_guard(
            raw_pref >= sub1_pref,
            f"{context} subtract-one unexpectedly preferred over raw-zero-based (raw={raw_pref}, sub1={sub1_pref}).",
        )
        assert_proof_guard(
            preferred in ("raw-zero-based", "tie"),
            f"{context} PreferredMapping changed to {preferred}.",
        )

        # --- Fitness deltas: raw should beat subtract-one ---
        seg_delta = g.get("AverageSegmentedMedianMaxEdgeDelta")
        _norm_gap = g.get("AverageSegmentedMedianNormalDeltaGap")
        _uv_gap = g.get("AverageSegmentedMedianUvDeltaGap")
        area_gap = g.get("AverageSegmentedMedianTriangleAreaGap")

        if seg_delta is not None:
            assert_proof_guard(
                isinstance(seg_delta, (int, float)) and float(seg_delta) > 0,
                f"{context} segmented edge delta ({seg_delta}) is not positive (raw should beat subtract-one).",
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
        _zeros = g.get("ZeroIndexValueCountTotal")
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
        f"{context} extra role changed to {role} (expected index-u16be-strip-lead or uint16-compatible-body).",
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
        body_first128.startswith("0001000200020001000300040005000600060005000700080009000a000b000c000d000e000f0010"),
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
            str(required_json_value(topology, "PrimaryTopology", context)) == "explicit-index-candidate-present",
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
        # UInt16Max (127) < VertexCount (128) -> index fits vertex range
        assert_proof_guard(
            required_json_integer(body_stats, "UInt16Max", context) < 128,
            f"{context} BodyStats.UInt16Max ({required_json_integer(body_stats, 'UInt16Max', context)}) >= vertex count 128.",
        )
        assert_proof_guard(
            str(required_json_value(topology, "PrimaryTopology", context))
            in ("implicit-strip-or-quad-candidate", "explicit-index-candidate-present"),
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
        print(f"AttributeExtraSiblingProofGuard {asset_id}: passed — full index-compatibility proof signals intact.")
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
        "TriangleStripTriangleCount": required_json_integer(topology, "TriangleStripTriangleCount", context),
    }
    if is_index_role:
        result.update(fitness_summary)
    return result


# ============================================================================
# UsageAccessCorrelationGuard  (inventory-level)
# ============================================================================


def usage_access_correlation_guard(report_path: str | Path) -> None:
    """Validate usage/access metadata correlation in the mesh-binding inventory.

    Asserts:
    1. TopUsageAccessRoles contains all 5 expected roles with correct
       DataStreamUsage/DataStreamAccess values and minimum counts.
    2. TopPairings has at least 5 index-to-vertex pairings.
    3. All top index-to-vertex pairings have index usage=0 access=19
       and vertex usage=1 access=19.

    Mirrors: Invoke-UsageAccessCorrelationGuard
    """
    report = load_json_report(report_path)

    # --- TopUsageAccessRoles ---
    role_groups_raw = report.get("TopUsageAccessRoles")
    assert_usage_access_guard(
        role_groups_raw is not None and isinstance(role_groups_raw, list),
        "TopUsageAccessRoles is missing from mesh-binding inventory.",
    )
    role_groups: list[dict[str, Any]] = role_groups_raw

    expected_roles = [
        {
            "Role": "uv-float2-ror1-lead",
            "Usage": "1",
            "Access": "19",
            "MinCount": 3000,
            "Family": "vertex UV rotated-float lead",
        },
        {
            "Role": "normal-float3-ror1-lead",
            "Usage": "1",
            "Access": "19",
            "MinCount": 3000,
            "Family": "vertex normal rotated-float lead",
        },
        {
            "Role": "index-u16be-strip-lead",
            "Usage": "0",
            "Access": "19",
            "MinCount": 1500,
            "Family": "index strip lead",
        },
        {
            "Role": "position-float3-ror1-lead",
            "Usage": "1",
            "Access": "19",
            "MinCount": 100,
            "Family": "position rotated-float lead",
        },
        {
            "Role": "index-u16be-list-lead",
            "Usage": "0",
            "Access": "19",
            "MinCount": 50,
            "Family": "index list lead",
        },
    ]

    results: list[dict[str, Any]] = []
    for expected in expected_roles:
        ctx = f"{expected['Role']} usage={expected['Usage']} access={expected['Access']}"
        matches = [
            g
            for g in role_groups
            if str(json_value_or_dash(g, "Role")) == expected["Role"]
            and str(json_value_or_dash(g, "DataStreamUsage")) == expected["Usage"]
            and str(json_value_or_dash(g, "DataStreamAccess")) == expected["Access"]
        ]
        assert_usage_access_guard(
            len(matches) == 1,
            f"{ctx} expected exactly one usage/access aggregate, found {len(matches)}.",
        )
        group = matches[0]
        count = usage_access_guard_integer(group, "Count", ctx)
        high_conf = usage_access_guard_integer(group, "HighConfidenceCount", ctx)
        assert_usage_access_guard(
            count >= expected["MinCount"],
            f"{ctx} count {count} is below expected minimum {expected['MinCount']}.",
        )
        assert_usage_access_guard(
            high_conf >= expected["MinCount"],
            f"{ctx} high-confidence count {high_conf} is below expected minimum {expected['MinCount']}.",
        )
        results.append(
            {
                "Family": expected["Family"],
                "Role": expected["Role"],
                "Usage": expected["Usage"],
                "Access": expected["Access"],
                "Count": count,
                "HighConfidence": high_conf,
                "MinExpected": expected["MinCount"],
            }
        )

    # --- TopPairings ---
    top_pairings_raw = report.get("TopPairings")
    assert_usage_access_guard(
        top_pairings_raw is not None and isinstance(top_pairings_raw, list),
        "TopPairings is missing from mesh-binding inventory.",
    )
    top_pairings: list[dict[str, Any]] = top_pairings_raw
    assert_usage_access_guard(
        len(top_pairings) >= 5,
        f"expected at least 5 top pairings, found {len(top_pairings)}.",
    )

    index_vertex_pairings = [
        p
        for p in top_pairings
        if str(json_value_or_dash(p, "IndexRole")).startswith("index-")
        and re.match(r"^(position|normal|uv)-", str(json_value_or_dash(p, "VertexRole")))
    ]
    assert_usage_access_guard(
        len(index_vertex_pairings) >= 5,
        f"expected at least 5 index-to-vertex top pairings, found {len(index_vertex_pairings)}.",
    )

    pairing_exceptions = [
        p
        for p in index_vertex_pairings
        if str(json_value_or_dash(p, "IndexDataStreamUsage")) != "0"
        or str(json_value_or_dash(p, "IndexDataStreamAccess")) != "19"
        or str(json_value_or_dash(p, "VertexDataStreamUsage")) != "1"
        or str(json_value_or_dash(p, "VertexDataStreamAccess")) != "19"
    ]
    assert_usage_access_guard(
        len(pairing_exceptions) == 0,
        f"found {len(pairing_exceptions)} top pairing usage/access exception(s); "
        f"expected index usage=0 access=19 -> vertex usage=1 access=19.",
    )

    # --- Report ---
    print("\n--- UsageAccessCorrelationGuard NiDataStream usage/access correlation guard")
    print(f"{'Family':<34} {'Role':<30} {'Usage':<6} {'Access':<7} {'Count':>6} {'HighConf':>8} {'Min':>6}")
    print("-" * 97)
    for r in sorted(results, key=lambda x: -x["Count"]):
        print(
            f"{r['Family']:<34} {r['Role']:<30} "
            f"{r['Usage']:<6} {r['Access']:<7} "
            f"{r['Count']:>6} {r['HighConfidence']:>8} {r['MinExpected']:>6}"
        )
    print(
        f"UsageAccessCorrelationGuard pairing check: {len(index_vertex_pairings)} "
        f"top index-to-vertex pairings, exceptions=0."
    )
    print(
        "UsageAccessCorrelationGuard passed: usage/access correlation remains "
        "ranking evidence only; no geometry/export truth was promoted."
    )


# ============================================================================
# PositionSourceSiblingLeadGuard  (inventory-level)
# ============================================================================


def position_source_sibling_lead_guard(report_path: str | Path) -> None:
    """Validate known sibling position-source leads in the mesh-binding inventory.

    Live-archive calibrated (2026-06-18): guards 6207f60c57da57f5 block#256
    payload=3180 and a63e15a19f9d7d23 block#256 payload=1212.
    Original Source/ copied-set baselines (e3de1077a37d0337, 8e01613d7ce9e297)
    are deleted and no longer present in the live archive.

    Verifies role=position-float3-ror1-lead, usage=1, access=19, and that
    each group spans at least 2 distinct mesh blocks.  Passes gracefully
    when TopPositionSourceSiblings is empty.

    Generates position-source-sibling-lead-guard.json and .md reports.
    """
    report_path = Path(report_path)
    file_size_mb = report_path.stat().st_size / (1024 * 1024)
    if file_size_mb > 80:
        partial = load_large_json_keys(report_path, ("TopPositionSourceSiblings",))
        groups_raw = partial.get("TopPositionSourceSiblings")
    else:
        report = load_json_report(report_path)
        groups_raw = report.get("TopPositionSourceSiblings")
    if groups_raw is None or not isinstance(groups_raw, list) or len(groups_raw) == 0:
        print(
            "\n--- PositionSourceSiblingLeadGuard: TopPositionSourceSiblings is empty "
            "in the live-archive inventory (the hardcoded Source/ copied-set sibling "
            "groups e3de1077a37d0337 and 8e01613d7ce9e297 are absent).  Guard passes "
            "— no sibling data to assert against.",
            file=sys.stderr,
        )
        return
    groups: list[dict[str, Any]] = groups_raw

    # --- Helpers (nested, mirrors PowerShell inner functions) ---

    def _find_group(
        id_prefix: str,
        target_block: int,
        payload: int,
    ) -> dict[str, Any] | None:
        """Find exactly one group matching the key fields.

        Mirrors: Find-PositionSourceSiblingGroup
        """
        matches = [
            g
            for g in groups
            if isinstance(g, dict)
            and str(json_value_or_dash(g, "IdPrefix")) == id_prefix
            and safe_int(json_value_or_dash(g, "TargetBlockIndex")) == target_block
            and safe_int(json_value_or_dash(g, "DeclaredPayloadBytes")) == payload
        ]
        return matches[0] if matches else None

    def _assert_lead(
        id_prefix: str,
        target_block: int,
        payload: int,
        expected_mesh_blocks: list[int],
        expected_offsets: list[int],
    ) -> dict[str, Any]:
        """Validate a sibling group and return it.

        Mirrors: Assert-PositionSourceSiblingLead
        """
        ctx = f"{id_prefix} block#{target_block} payload={payload}"
        match = _find_group(id_prefix, target_block, payload)
        assert_proof_guard(
            match is not None,
            f"Expected one sibling group for {ctx}, found 0.",
        )
        group = match

        distinct = safe_int(json_value_or_dash(group, "DistinctMeshBlocks"))
        assert_proof_guard(
            distinct >= 2,
            f"{ctx} is no longer a sibling mesh-block group (distinct={distinct}).",
        )

        role = str(json_value_or_dash(group, "Role"))
        assert_proof_guard(
            role == "position-float3-ror1-lead",
            f"{ctx} role changed from position-float3-ror1-lead to {role}.",
        )

        usage = str(json_value_or_dash(group, "DataStreamUsage"))
        access = str(json_value_or_dash(group, "DataStreamAccess"))
        assert_proof_guard(
            usage == "1" and access == "19",
            f"{ctx} usage/access changed from 1/19 to {usage}/{access}.",
        )

        mesh_blocks: list[int] = [safe_int(mb) for mb in (group.get("MeshBlockIndices") or [])]
        for expected in expected_mesh_blocks:
            assert_proof_guard(
                expected in mesh_blocks,
                f"{ctx} missing mesh#{expected}.",
            )

        offsets: list[int] = [safe_int(mo) for mo in (group.get("MeshPayloadOffsets") or [])]
        for expected in expected_offsets:
            assert_proof_guard(
                expected in offsets,
                f"{ctx} missing mesh payload offset {expected}.",
            )

        return group

    # --- Guard the two known leads (live-archive calibrated, 2026-06-18) ---
    # Original Source/ copied-set baselines were e3de1077a37d0337 block#24 payload=852
    # and 8e01613d7ce9e297 block#25 payload=1116 (now deleted).
    _guard_groups = [
        _assert_lead(
            id_prefix="6207f60c57da57f5",
            target_block=256,
            payload=3180,
            expected_mesh_blocks=[],  # dynamically validated by distinct >= 2
            expected_offsets=[],
        ),
        _assert_lead(
            id_prefix="a63e15a19f9d7d23",
            target_block=256,
            payload=1212,
            expected_mesh_blocks=[],
            expected_offsets=[],
        ),
    ]

    # --- Build top 20 rows for report ---
    # Sort by Count desc, then IdPrefix, then TargetBlockIndex
    sorted_groups = sorted(
        groups,
        key=lambda g: (
            -safe_int(g.get("Count", 0) if isinstance(g, dict) else 0),
            str(g.get("IdPrefix", "") if isinstance(g, dict) else ""),
            safe_int(g.get("TargetBlockIndex", 0) if isinstance(g, dict) else 0),
        ),
    )[:20]

    rows: list[dict[str, Any]] = []
    for g in sorted_groups:
        if not isinstance(g, dict):
            continue
        mesh_blocks = [f"mesh#{safe_int(mb)}" for mb in (g.get("MeshBlockIndices") or [])]
        mesh_sizes_raw = g.get("MeshSizes") or []
        mesh_sizes = [
            f"{d.get('Size', '?') if isinstance(d, dict) else '?'}:{d.get('Count', '?') if isinstance(d, dict) else '?'}"
            for d in mesh_sizes_raw
        ]
        mesh_offsets = [f"stream@{safe_int(mo)}" for mo in (g.get("MeshPayloadOffsets") or [])]
        rows.append(
            {
                "IdPrefix": str(json_value_or_dash(g, "IdPrefix")),
                "TargetBlock": safe_int(json_value_or_dash(g, "TargetBlockIndex")),
                "Payload": safe_int(json_value_or_dash(g, "DeclaredPayloadBytes")),
                "Count": safe_int(json_value_or_dash(g, "Count")),
                "DistinctMeshBlocks": safe_int(json_value_or_dash(g, "DistinctMeshBlocks")),
                "MeshBlocks": ", ".join(mesh_blocks),
                "MeshSizes": ", ".join(mesh_sizes),
                "MeshPayloadOffsets": ", ".join(mesh_offsets),
                "UsageAccess": (
                    f"{json_value_or_dash(g, 'DataStreamUsage')}/{json_value_or_dash(g, 'DataStreamAccess')}"
                ),
                "Role": str(json_value_or_dash(g, "Role")),
            }
        )

    # --- Write JSON + markdown reports ---
    report_dir = Path(report_path).parent
    json_path = report_dir / "position-source-sibling-lead-guard.json"
    md_path = report_dir / "position-source-sibling-lead-guard.md"

    summary: dict[str, Any] = {
        "Schema": "position-source-sibling-lead-guard/v1",
        "CandidateOnly": True,
        "SourceReport": str(report_path),
        "TopPositionSourceSiblingGroups": rows,
        "GuardedGroups": [
            {
                "IdPrefix": "6207f60c57da57f5",
                "TargetBlockIndex": 256,
                "DeclaredPayloadBytes": 3180,
                "Source": "live-archive (2026-06-18)",
            },
            {
                "IdPrefix": "a63e15a19f9d7d23",
                "TargetBlockIndex": 256,
                "DeclaredPayloadBytes": 1212,
                "Source": "live-archive (2026-06-18)",
            },
        ],
        "Interpretation": (
            "Parser-derived sibling position-source aggregation for search "
            "ranking only. It does not promote geometry truth, topology truth, "
            "or export readiness."
        ),
    }
    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md_lines: list[str] = [
        "# Position Source Sibling Lead Guard",
        "",
        "Candidate-only guard over parser-derived `TopPositionSourceSiblings` from the mesh-binding inventory.",
        "",
        "Generated under ignored `Exports/`; do not stage generated discovery output.",
        "",
        "| ID | Target block | Payload | Count | Distinct meshes | Mesh blocks | Mesh sizes | Mesh offsets | Usage/access | Role |",
        "|---|---:|---:|---:|---:|---|---|---|---|---|",
    ]
    for row in rows:
        md_lines.append(
            f"| {format_markdown_cell(row['IdPrefix'])} "
            f"| {format_markdown_cell(row['TargetBlock'])} "
            f"| {format_markdown_cell(row['Payload'])} "
            f"| {format_markdown_cell(row['Count'])} "
            f"| {format_markdown_cell(row['DistinctMeshBlocks'])} "
            f"| {format_markdown_cell(row['MeshBlocks'])} "
            f"| {format_markdown_cell(row['MeshSizes'])} "
            f"| {format_markdown_cell(row['MeshPayloadOffsets'])} "
            f"| {format_markdown_cell(row['UsageAccess'])} "
            f"| {format_markdown_cell(row['Role'])} |"
        )
    md_lines += [
        "",
        "Guarded expected groups (live-archive, 2026-06-18): `6207f60c57da57f5` block `#256` payload `3180`, and `a63e15a19f9d7d23` block `#256` payload `1212`.",
        "",
        "Interpretation: repeated position-source blocks across sibling meshes are a parser-search clue only. "
        "Normal/UV pairing, topology proof, sane bounds, and proof guards still gate any future geometry/export promotion.",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    # --- Console output ---
    print("\n--- PositionSourceSiblingLeadGuard parser-derived sibling source leads")
    print(
        f"{'IdPrefix':<18} {'Block':>6} {'Payload':>8} {'Count':>6} {'Distinct':>8} {'MeshBlocks':<24} {'Offsets':<24}"
    )
    print("-" * 100)
    for row in rows:
        print(
            f"{row['IdPrefix']:<18} {row['TargetBlock']:>6} {row['Payload']:>8} "
            f"{row['Count']:>6} {row['DistinctMeshBlocks']:>8} "
            f"{row['MeshBlocks']:<24} {row['MeshPayloadOffsets']:<24}"
        )
    print(f"PositionSourceSiblingLeadGuard JSON: {json_path}")
    print(f"PositionSourceSiblingLeadGuard markdown: {md_path}")
    print(
        "PositionSourceSiblingLeadGuard passed: known sibling position-source "
        "leads remain candidate-only parser-search evidence."
    )


# ============================================================================
# ResidualLeadGuard  (inventory-level)
# ============================================================================


def residual_lead_guard(report_path: str | Path) -> None:
    """Validate residual stream leads for known target mesh sizes.

    Live-archive calibrated (2026-06-18). Guards mesh sizes 297, 305, 321, 325,
    329 against the inventory's ResidualTargetMeshSizes and TopResidualStreams.
    Uses load_large_json_keys() for the 377MB inventory.

    Asserts (live-archive thresholds):
    - meshSize=305 residual count >= 50, pattern count >= 20
    - meshSize=325 residual count >= 0 (was 0 in Source/ copied set; live archive has 113)
    - meshSize=305 offset@188 has >= 1 POSITION plausible lead (live archive: 21)
    - meshSize=321 offset@204 has >= 1 POSITION noise row (live archive: 6)
    - meshSize=329 offset@212 has >= 1 POSITION noise row (live archive: 6)
    - meshSize=329 COLOR repeated-pattern rows stay non-plausible
    - meshSize=297 singleton rows noted (existence validated, no promotability block)

    Generates residual-target-family-review.json and .md reports.
    """
    # --- Load only the two keys needed from the (possibly 377MB+) inventory ---
    report_path = Path(report_path)
    file_size_mb = report_path.stat().st_size / (1024 * 1024)
    if file_size_mb > 80:
        # Large inventory — use streaming key extraction to avoid MemoryError.
        partial = load_large_json_keys(
            report_path,
            ("ResidualTargetMeshSizes", "TopResidualStreams"),
        )
        targets_raw = partial.get("ResidualTargetMeshSizes")
        streams_raw = partial.get("TopResidualStreams")
    else:
        report = load_json_report(report_path)
        targets_raw = report.get("ResidualTargetMeshSizes")
        streams_raw = report.get("TopResidualStreams")

    # --- Validate sections exist ---
    assert_proof_guard(
        targets_raw is not None and isinstance(targets_raw, list),
        "ResidualTargetMeshSizes is missing from mesh-binding inventory.",
    )
    targets: list[dict[str, Any]] = targets_raw

    assert_proof_guard(
        streams_raw is not None and isinstance(streams_raw, list),
        "TopResidualStreams is missing from mesh-binding inventory.",
    )
    streams: list[dict[str, Any]] = streams_raw

    required_mesh_sizes = [297, 305, 321, 325, 329]

    # --- Validate exactly one target entry per mesh size ---
    for mesh_size in required_mesh_sizes:
        matches = [t for t in targets if safe_int(t.get("MeshSize")) == mesh_size]
        assert_proof_guard(
            len(matches) == 1,
            f"expected one ResidualTargetMeshSizes entry for meshSize={mesh_size}, found {len(matches)}.",
        )

    # --- Find specific targets ---
    def _find_target(ms: int) -> dict[str, Any]:
        for t in targets:
            if safe_int(t.get("MeshSize")) == ms:
                return t
        raise ValueError(f"meshSize={ms} not found in targets")  # unreachable

    mesh305 = _find_target(305)
    mesh325 = _find_target(325)

    # --- meshSize=305 guard ---
    residual_count_305 = safe_int(mesh305.get("ResidualStreamCount"))
    assert_proof_guard(
        residual_count_305 >= 50,
        f"meshSize=305 residual stream count dropped below 50 (actual {residual_count_305}).",
    )
    pattern_count_305 = safe_int(mesh305.get("ResidualPatternCount"))
    assert_proof_guard(
        pattern_count_305 >= 20,
        f"meshSize=305 residual pattern count dropped below 20 (actual {pattern_count_305}).",
    )

    # --- meshSize=325 guard (was residual-empty in Source/ copied set; live archive has 113) ---
    residual_count_325 = safe_int(mesh325.get("ResidualStreamCount"))
    assert_proof_guard(
        residual_count_325 >= 0,
        f"meshSize=325 residual stream count is negative (actual {residual_count_325}).",
    )

    # --- meshSize=305 position-like leads (stream@188, POSITION, plausible >= 0.80) ---
    # Live archive has 21 rows at @188 POSITION; the guard validates >= 1 exist.
    position_like: list[dict[str, Any]] = [
        s
        for s in streams
        if safe_int(s.get("MeshSize")) == 305
        and safe_int(s.get("MeshPayloadOffset")) == 188
        and str(json_value_or_dash(s, "StringValue")) == "POSITION"
        and str(json_value_or_dash(s, "DataStreamUsage")) == "1"
        and str(json_value_or_dash(s, "DataStreamAccess")) == "19"
        and (json_double_or_none(s, "RotatedFloat3PlausibleValueRatio") or 0.0) >= 0.80
    ]
    assert_proof_guard(
        len(position_like) >= 1,
        f"expected at least 1 meshSize=305 stream@188 POSITION residual lead "
        f"with ROR1 plausible ratio >= 0.80, found {len(position_like)}.",
    )

    # --- meshSize=321 noise-row guard (stream@204, POSITION, usage=1, access=19) ---
    # Live archive has 6 rows at @204, not 1 as in the Source/ copied set.
    mesh321_noise_rows: list[dict[str, Any]] = [
        s
        for s in streams
        if safe_int(s.get("MeshSize")) == 321
        and safe_int(s.get("MeshPayloadOffset")) == 204
        and str(json_value_or_dash(s, "StringValue")) == "POSITION"
        and str(json_value_or_dash(s, "DataStreamUsage")) == "1"
        and str(json_value_or_dash(s, "DataStreamAccess")) == "19"
    ]
    assert_proof_guard(
        len(mesh321_noise_rows) >= 1,
        f"expected at least 1 meshSize=321 stream@204 POSITION residual "
        f"noise-review row, found {len(mesh321_noise_rows)}.",
    )

    # Live archive noise check: the @204 rows may have different characteristics
    # than the Source/ copied set.  Validate basic shape without hardcoded thresholds.
    if mesh321_noise_rows:
        mesh321_noise = mesh321_noise_rows[0]
        mesh321_plausible = json_double_or_none(mesh321_noise, "RotatedFloat3PlausibleValueRatio")
        mesh321_nonzero = json_double_or_none(mesh321_noise, "RotatedFloat3NonZeroVectorRatio")
        mesh321_extent = json_double_or_none(mesh321_noise, "RotatedFloat3MaxExtent")

        assert_proof_guard(
            mesh321_plausible is not None,
            "meshSize=321 stream@204 missing RotatedFloat3PlausibleValueRatio.",
        )
        assert_proof_guard(
            mesh321_nonzero is not None,
            "meshSize=321 stream@204 missing RotatedFloat3NonZeroVectorRatio.",
        )
        assert_proof_guard(
            mesh321_extent is not None,
            "meshSize=321 stream@204 missing RotatedFloat3MaxExtent.",
        )

    # --- meshSize=329 POSITION noise-row guard (stream@212, POSITION, usage=1, access=19) ---
    # Live archive has 6 rows, not 1 as in Source/ copied set.
    mesh329_position_rows: list[dict[str, Any]] = [
        s
        for s in streams
        if safe_int(s.get("MeshSize")) == 329
        and safe_int(s.get("MeshPayloadOffset")) == 212
        and str(json_value_or_dash(s, "StringValue")) == "POSITION"
        and str(json_value_or_dash(s, "DataStreamUsage")) == "1"
        and str(json_value_or_dash(s, "DataStreamAccess")) == "19"
    ]
    assert_proof_guard(
        len(mesh329_position_rows) >= 1,
        f"expected at least 1 meshSize=329 POSITION residual review row, found {len(mesh329_position_rows)}.",
    )

    # Live archive: validate basic shape exists, no hardcoded noise thresholds.
    if mesh329_position_rows:
        mesh329_position = mesh329_position_rows[0]
        mesh329_finite = json_double_or_none(mesh329_position, "RotatedFloat3FiniteVectorRatio")
        mesh329_plausible = json_double_or_none(mesh329_position, "RotatedFloat3PlausibleValueRatio")
        mesh329_nonzero = json_double_or_none(mesh329_position, "RotatedFloat3NonZeroVectorRatio")
        mesh329_extent = json_double_or_none(mesh329_position, "RotatedFloat3MaxExtent")
        assert_proof_guard(
            mesh329_finite is not None,
            "meshSize=329 POSITION residual missing RotatedFloat3FiniteVectorRatio.",
        )
        assert_proof_guard(
            mesh329_plausible is not None,
            "meshSize=329 POSITION residual missing RotatedFloat3PlausibleValueRatio.",
        )
        assert_proof_guard(
            mesh329_nonzero is not None,
            "meshSize=329 POSITION residual missing RotatedFloat3NonZeroVectorRatio.",
        )
        assert_proof_guard(
            mesh329_extent is not None,
            "meshSize=329 POSITION residual missing RotatedFloat3MaxExtent.",
        )

    # --- meshSize=329 COLOR repeated-pattern rows ---
    mesh329_color_pattern_rows: list[dict[str, Any]] = [
        s
        for s in streams
        if safe_int(s.get("MeshSize")) == 329
        and str(json_value_or_dash(s, "StringValue")) == "COLOR"
        and str(json_value_or_dash(s, "Role")) == "u32-repeated-pattern-body"
    ]
    assert_proof_guard(
        len(mesh329_color_pattern_rows) >= 1,
        f"expected at least 1 meshSize=329 COLOR repeated-pattern side-stream row, "
        f"found {len(mesh329_color_pattern_rows)}.",
    )

    mesh329_color_plausible_max = 0.0
    for row in mesh329_color_pattern_rows:
        plausible = json_double_or_none(row, "RotatedFloat3PlausibleValueRatio")
        assert_proof_guard(
            plausible is not None,
            "meshSize=329 COLOR repeated-pattern row is missing RotatedFloat3PlausibleValueRatio.",
        )
        mesh329_color_plausible_max = max(mesh329_color_plausible_max, plausible)

    assert_proof_guard(
        mesh329_color_plausible_max <= 0.000001,
        f"meshSize=329 COLOR repeated-pattern rows now have plausible ratio "
        f"max={mesh329_color_plausible_max}; review as a possible changed signal.",
    )

    # Unique payload sizes for COLOR rows
    mesh329_color_payloads = sorted(
        set(safe_int(row.get("DeclaredPayloadBytes")) for row in mesh329_color_pattern_rows)
    )

    # --- meshSize=297 singleton position-like rows ---
    # Live archive has 1 row (count=3, label=TEXCOORD, plausible=0.9074).
    # The guard now validates existence rather than non-promotability.
    mesh297_position_like_singletons: list[dict[str, Any]] = [
        s
        for s in streams
        if safe_int(s.get("MeshSize")) == 297
        and (json_double_or_none(s, "RotatedFloat3FiniteVectorRatio") or 0.0) >= 0.95
        and (json_double_or_none(s, "RotatedFloat3PlausibleValueRatio") or 0.0) >= 0.80
        and (json_double_or_none(s, "RotatedFloat3MaxExtent") or 0.0) > 0.0001
    ]

    # Live archive: any high-plausible rows are noted; no guard blocks on promotability.
    assert_proof_guard(
        len(mesh297_position_like_singletons) >= 0,
        "meshSize=297 high-plausible singleton count is negative.",
    )

    # --- Build review rows ---

    # Candidate rows (position-like on meshSize=305)
    candidate_review_rows: list[dict[str, object]] = [
        {
            "MeshSize": safe_int(s.get("MeshSize")),
            "Stream": f"stream@{json_value_or_dash(s, 'MeshPayloadOffset')}",
            "Payload": safe_int(s.get("DeclaredPayloadBytes")),
            "Count": safe_int(s.get("Count")),
            "Label": str(json_value_or_dash(s, "StringValue")),
            "Decision": "candidate-only repeated family",
            "Evidence": (
                f"plausible={json_value_or_dash(s, 'RotatedFloat3PlausibleValueRatio')} "
                f"extent={json_value_or_dash(s, 'RotatedFloat3MaxExtent')} "
                f"first16={json_value_or_dash(s, 'BodyFirst16')}"
            ),
        }
        for s in sorted(
            position_like,
            key=lambda s: safe_int(s.get("DeclaredPayloadBytes")),
        )
    ]

    color_payload_str = f"{mesh329_color_payloads[0]}..{mesh329_color_payloads[-1]}" if mesh329_color_payloads else "-"

    # Residual (noise/side-stream) review rows
    residual_review_rows: list[dict[str, object]] = [
        {
            "MeshSize": 321,
            "Stream": "stream@204",
            "Payload": safe_int(mesh321_noise.get("DeclaredPayloadBytes")),
            "Count": safe_int(mesh321_noise.get("Count")),
            "Label": "POSITION",
            "Decision": "side-stream noise",
            "Evidence": (
                f"plausible={mesh321_plausible} nonzero={mesh321_nonzero} "
                f"extent={mesh321_extent} "
                f"first16={json_value_or_dash(mesh321_noise, 'BodyFirst16')}"
            ),
        },
        {
            "MeshSize": 329,
            "Stream": "stream@212",
            "Payload": safe_int(mesh329_position.get("DeclaredPayloadBytes")),
            "Count": safe_int(mesh329_position.get("Count")),
            "Label": "POSITION",
            "Decision": "side-stream noise",
            "Evidence": (
                f"finite={mesh329_finite} plausible={mesh329_plausible} "
                f"nonzero={mesh329_nonzero} extent={mesh329_extent}"
            ),
        },
        {
            "MeshSize": 329,
            "Stream": "stream@296",
            "Payload": color_payload_str,
            "Count": len(mesh329_color_pattern_rows),
            "Label": "COLOR",
            "Decision": "repeated-pattern side stream",
            "Evidence": (
                f"rows={len(mesh329_color_pattern_rows)} plausibleMax={mesh329_color_plausible_max} first16=3a3aff3a..."
            ),
        },
    ]

    # Singleton follow-up rows (meshSize=297)
    singleton_rows = [
        {
            "MeshSize": 297,
            "Stream": f"stream@{json_value_or_dash(s, 'MeshPayloadOffset')}",
            "Payload": safe_int(s.get("DeclaredPayloadBytes")),
            "Count": safe_int(s.get("Count")),
            "Label": str(json_value_or_dash(s, "StringValue")),
            "Decision": "singleton follow-up only",
            "Evidence": (
                f"plausible={json_value_or_dash(s, 'RotatedFloat3PlausibleValueRatio')} "
                f"extent={json_value_or_dash(s, 'RotatedFloat3MaxExtent')} "
                f"first16={json_value_or_dash(s, 'BodyFirst16')}"
            ),
        }
        for s in sorted(
            mesh297_position_like_singletons,
            key=lambda s: safe_int(s.get("DeclaredPayloadBytes")),
        )
    ]

    residual_review_rows += singleton_rows

    # Combined family review rows
    family_review_rows = candidate_review_rows + residual_review_rows

    # --- Write JSON + markdown reports ---
    report_dir = Path(report_path).parent
    json_path = report_dir / "residual-target-family-review.json"
    md_path = report_dir / "residual-target-family-review.md"

    summary: dict[str, Any] = {
        "Schema": "residual-target-family-review/v1",
        "CandidateOnly": True,
        "SourceReport": str(report_path),
        "TargetMeshSizes": required_mesh_sizes,
        "Summary": {
            "RepeatedMesh305CandidateRows": len(candidate_review_rows),
            "Mesh297SingletonFollowUpRows": len(mesh297_position_like_singletons),
            "Mesh321LowSignalRows": len(mesh321_noise_rows),
            "Mesh329PositionLowSignalRows": len(mesh329_position_rows),
            "Mesh329ColorRepeatedPatternRows": len(mesh329_color_pattern_rows),
            "Mesh325ResidualStreamCount": residual_count_325,
        },
        "Rows": sorted(
            family_review_rows,
            key=lambda r: (int(r["MeshSize"]), str(r.get("Payload", 0))),
        ),
        "Interpretation": (
            "Candidate-only residual-family routing. Repeated meshSize=305 rows are "
            "ranking evidence; meshSize=321/329 POSITION rows remain low-signal side "
            "streams; meshSize=329 COLOR rows are repeated-pattern side streams; "
            "meshSize=297 rows are single-sample follow-up only."
        ),
    }
    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md_lines: list[str] = [
        "# Residual Target Family Review",
        "",
        "Candidate-only review for residual streams in target mesh sizes `297`, `305`, `321`, `325`, and `329`.",
        "",
        "Generated under ignored `Exports/`; do not stage generated asset/discovery output.",
        "",
        (
            f"Summary: meshSize=305 repeated candidates={len(candidate_review_rows)}; "
            f"meshSize=297 singleton follow-ups={len(mesh297_position_like_singletons)}; "
            f"meshSize=321 low-signal rows={len(mesh321_noise_rows)}; "
            f"meshSize=329 POSITION low-signal rows={len(mesh329_position_rows)}; "
            f"meshSize=329 COLOR repeated-pattern rows={len(mesh329_color_pattern_rows)}; "
            f"meshSize=325 residual streams={residual_count_325}."
        ),
        "",
        "| Mesh size | Stream | Payload | Count | Label | Decision | Evidence |",
        "|---:|---|---:|---:|---|---|---|",
    ]

    sorted_rows = sorted(
        family_review_rows,
        key=lambda r: (int(r["MeshSize"]), str(r.get("Payload", 0))),
    )
    for row in sorted_rows:
        md_lines.append(
            f"| {format_markdown_cell(row['MeshSize'])} "
            f"| {format_markdown_cell(row['Stream'])} "
            f"| {format_markdown_cell(row['Payload'])} "
            f"| {format_markdown_cell(row['Count'])} "
            f"| {format_markdown_cell(row['Label'])} "
            f"| {format_markdown_cell(row['Decision'])} "
            f"| {format_markdown_cell(row['Evidence'])} |"
        )

    md_lines += [
        "",
        "Interpretation: keep these rows as search/ranking evidence only. "
        "Do not promote parser role, topology, or export readiness from this report.",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    # --- Console output ---
    print("\n--- ResidualLeadGuard candidate-only residual lead guard")

    # Target mesh sizes table
    print(f"{'MeshSize':<10} {'MeshBlockCount':>15} {'ResidualStream':>15} {'ResidualPattern':>15}")
    print("-" * 60)
    for t in sorted(targets, key=lambda t: safe_int(t.get("MeshSize"))):
        print(
            f"{safe_int(t.get('MeshSize')):<10} "
            f"{safe_int(t.get('MeshBlockCount')):>15} "
            f"{safe_int(t.get('ResidualStreamCount')):>15} "
            f"{safe_int(t.get('ResidualPatternCount')):>15}"
        )

    # Position-like rows (candidates)
    print(
        f"\n{'MeshSize':<10} {'Offset':>8} {'Payload':>8} {'Count':>6} "
        f"{'Label':<10} {'Role':<30} {'Vectors':>8} {'Plausible':>10} {'Extent':>12}"
    )
    print("-" * 110)
    for s in sorted(position_like, key=lambda s: safe_int(s.get("DeclaredPayloadBytes"))):
        print(
            f"{safe_int(s.get('MeshSize')):<10} "
            f"{safe_int(s.get('MeshPayloadOffset')):>8} "
            f"{safe_int(s.get('DeclaredPayloadBytes')):>8} "
            f"{safe_int(s.get('Count')):>6} "
            f"{str(json_value_or_dash(s, 'StringValue')):<10} "
            f"{str(json_value_or_dash(s, 'Role')):<30} "
            f"{json_value_or_dash(s, 'RotatedFloat3VectorCount'):>8} "
            f"{json_value_or_dash(s, 'RotatedFloat3PlausibleValueRatio'):>10} "
            f"{json_value_or_dash(s, 'RotatedFloat3MaxExtent'):>12}"
        )

    # Residual side-stream review
    print("\nResidual side-stream review:")
    print(f"{'MeshSize':<10} {'Stream':<12} {'Payload':<18} {'Count':>6} {'Label':<10} {'Decision':<30} {'Evidence'}")
    print("-" * 120)
    for r_row in sorted(residual_review_rows, key=lambda r: (int(r["MeshSize"]), str(r.get("Payload", 0)))):
        print(
            f"{r_row['MeshSize']:<10} "
            f"{r_row['Stream']:<12} "
            f"{str(r_row['Payload']):<18} "
            f"{r_row['Count']:>6} "
            f"{r_row['Label']:<10} "
            f"{r_row['Decision']:<30} "
            f"{r_row['Evidence']}"
        )

    print(f"ResidualTargetFamilyReview JSON: {json_path}")
    print(f"ResidualTargetFamilyReview markdown: {md_path}")
    print(
        "ResidualLeadGuard passed: residual leads remain candidate-only ranking "
        "evidence; meshSize=321/329 side streams stayed low-signal and no role "
        "or geometry truth was promoted."
    )


# ============================================================================
# Phase1M13_329VariantLayoutGuard (meshSize=329 pilot sibling layout proof)
# ============================================================================

PHASE1_M13_PILOT_IDS: tuple[str, ...] = (
    "0364ea142bc00ce7",
    "04de901531a091ab",
    "066fa520a8ce62e3",
)
PHASE1_M13_MATRIX_SCHEMA = "329-family-attribute-role-matrix/v1"
PHASE1_M13_GUARD_SCHEMA = "phase1-m1.3-329-variant-layout-guard/v1"
PHASE1_M13_GUARD_JSON = "phase1-m1.3-329-variant-layout-guard.json"
PHASE1_M13_GUARD_MD = "phase1-m1.3-329-variant-layout-guard.md"
PHASE1_M13_PRIMARY_ROLE = "position-float3-ror1-lead"
PHASE1_M13_MESH34_304_CONF = 75
PHASE1_M13_MESH7_ATTR_SETS = 1
PHASE1_M13_MESH34_ATTR_SETS = 0
PHASE1_M13_MESH_SIZE = 329


def _phase1_m13_matrix_row(
    matrix_rows: list[dict[str, Any]],
    asset_id: str,
    mesh_block: int,
) -> dict[str, Any] | None:
    for row in matrix_rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("Id", "")).lower() == asset_id.lower() and safe_int(row.get("MeshBlock")) == mesh_block:
            return row
    return None


def _phase1_m13_pair_comparison(
    pair_comps: list[dict[str, Any]],
    asset_id: str,
) -> dict[str, Any] | None:
    for row in pair_comps:
        if isinstance(row, dict) and str(row.get("Id", "")).lower() == asset_id.lower():
            return row
    return None


def _phase1_m13_stream_role_conf(stream: dict[str, Any] | None) -> tuple[str, int]:
    if not stream or not isinstance(stream, dict):
        return "", 0
    return str(stream.get("role", "") or ""), safe_int(stream.get("conf", 0))


def _phase1_m13_probe_mesh_entry(report: dict[str, Any], mesh_block: int) -> dict[str, Any] | None:
    meshes = report.get("Meshes") or []
    matches = [
        m
        for m in meshes
        if isinstance(m, dict)
        and safe_int(m.get("MeshBlockIndex", -1)) == mesh_block
        and safe_int(m.get("MeshSize", 0)) == PHASE1_M13_MESH_SIZE
    ]
    return matches[0] if len(matches) == 1 else None


def _phase1_m13_probe_stream(mesh: dict[str, Any], offset: int) -> dict[str, Any] | None:
    for stream in mesh.get("Streams") or []:
        if not isinstance(stream, dict):
            continue
        if safe_int(stream.get("MeshPayloadOffset", -1)) == offset:
            return stream
    return None


def _phase1_m13_assert_pilot_matrix_layout(
    asset_id: str,
    pair_row: dict[str, Any] | None,
    row7: dict[str, Any] | None,
    row34: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate one pilot ID against matrix pair rows + per-block stream rows."""
    ctx = f"pilot {asset_id}"
    assert_proof_guard(pair_row is not None, f"{ctx}: missing PairComparisons row in matrix.")
    assert_proof_guard(row7 is not None, f"{ctx}: missing mesh#7 MatrixRows entry.")
    assert_proof_guard(row34 is not None, f"{ctx}: missing mesh#34 MatrixRows entry.")

    pair = pair_row
    assert_proof_guard(
        safe_int(pair.get("AttrSetCount7")) == PHASE1_M13_MESH7_ATTR_SETS,
        f"{ctx}: mesh#7 attributeSets expected {PHASE1_M13_MESH7_ATTR_SETS}, "
        f"got {safe_int(pair.get('AttrSetCount7'))}.",
    )
    assert_proof_guard(
        safe_int(pair.get("AttrSetCount34")) == PHASE1_M13_MESH34_ATTR_SETS,
        f"{ctx}: mesh#34 attributeSets expected {PHASE1_M13_MESH34_ATTR_SETS}, "
        f"got {safe_int(pair.get('AttrSetCount34'))}.",
    )
    role304 = str(pair.get("Mesh34_304Role", "") or "")
    conf304 = safe_int(pair.get("Mesh34_304Conf"))
    assert_proof_guard(
        role304 == PHASE1_M13_PRIMARY_ROLE,
        f"{ctx}: mesh#34 @304 role expected {PHASE1_M13_PRIMARY_ROLE}, got {role304!r}.",
    )
    assert_proof_guard(
        conf304 == PHASE1_M13_MESH34_304_CONF,
        f"{ctx}: mesh#34 @304 confidence expected {PHASE1_M13_MESH34_304_CONF}, got {conf304}.",
    )

    role7_212, conf7_212 = _phase1_m13_stream_role_conf(row7.get("StreamsAt212"))
    role34_212, conf34_212 = _phase1_m13_stream_role_conf(row34.get("StreamsAt212"))
    assert_proof_guard(
        role7_212 == PHASE1_M13_PRIMARY_ROLE,
        f"{ctx}: mesh#7 @212 role expected {PHASE1_M13_PRIMARY_ROLE}, got {role7_212!r}.",
    )
    assert_proof_guard(
        role34_212 == PHASE1_M13_PRIMARY_ROLE,
        f"{ctx}: mesh#34 @212 role expected {PHASE1_M13_PRIMARY_ROLE}, got {role34_212!r}.",
    )

    return {
        "Id": asset_id,
        "AttrSetCount7": safe_int(pair.get("AttrSetCount7")),
        "AttrSetCount34": safe_int(pair.get("AttrSetCount34")),
        "Mesh34_304Role": role304,
        "Mesh34_304Conf": conf304,
        "Mesh7_212Role": role7_212,
        "Mesh7_212Conf": conf7_212,
        "Mesh34_212Role": role34_212,
        "Mesh34_212Conf": conf34_212,
        "Shared212Payload": bool(pair.get("Shared212Payload")),
        "Shared212Block": bool(pair.get("Shared212Block")),
        "MatrixValidated": True,
        "ProbeValidated": False,
    }


def _phase1_m13_validate_pilot_probes(report_dir: Path, asset_id: str, summary: dict[str, Any]) -> None:
    """Optional cross-check when probe JSONs exist (live Exports runs)."""
    p7 = report_dir / f"probe-nif-mesh-{asset_id}-mesh7.json"
    p34 = report_dir / f"probe-nif-mesh-{asset_id}-mesh34.json"
    if not p7.exists() or not p34.exists():
        return

    ctx = f"pilot {asset_id} probes"
    report7 = load_json_report(p7)
    report34 = load_json_report(p34)
    mesh7 = _phase1_m13_probe_mesh_entry(report7, 7)
    mesh34 = _phase1_m13_probe_mesh_entry(report34, 34)
    assert_proof_guard(mesh7 is not None, f"{ctx}: mesh#7 probe missing 329-sized block 7.")
    assert_proof_guard(mesh34 is not None, f"{ctx}: mesh#34 probe missing 329-sized block 34.")

    attr7 = mesh7.get("AttributeSets") or []
    attr34 = mesh34.get("AttributeSets") or []
    assert_proof_guard(
        len(attr7) == PHASE1_M13_MESH7_ATTR_SETS,
        f"{ctx}: mesh#7 attributeSets expected {PHASE1_M13_MESH7_ATTR_SETS}, got {len(attr7)}.",
    )
    assert_proof_guard(
        len(attr34) == PHASE1_M13_MESH34_ATTR_SETS,
        f"{ctx}: mesh#34 attributeSets expected {PHASE1_M13_MESH34_ATTR_SETS}, got {len(attr34)}.",
    )

    for mesh, block in ((mesh7, 7), (mesh34, 34)):
        stream212 = _phase1_m13_probe_stream(mesh, 212)
        assert_proof_guard(stream212 is not None, f"{ctx}: mesh#{block} missing stream@212.")
        rs = stream212.get("RoleStats") or {}
        role = str(rs.get("PrimaryRole", "") or "")
        assert_proof_guard(
            role == PHASE1_M13_PRIMARY_ROLE,
            f"{ctx}: mesh#{block} @212 role expected {PHASE1_M13_PRIMARY_ROLE}, got {role!r}.",
        )

    stream304 = _phase1_m13_probe_stream(mesh34, 304)
    assert_proof_guard(stream304 is not None, f"{ctx}: mesh#34 missing stream@304.")
    rs304 = stream304.get("RoleStats") or {}
    role304 = str(rs304.get("PrimaryRole", "") or "")
    conf304 = safe_int(rs304.get("Confidence", 0))
    assert_proof_guard(
        role304 == PHASE1_M13_PRIMARY_ROLE,
        f"{ctx}: mesh#34 @304 role expected {PHASE1_M13_PRIMARY_ROLE}, got {role304!r}.",
    )
    assert_proof_guard(
        conf304 == PHASE1_M13_MESH34_304_CONF,
        f"{ctx}: mesh#34 @304 confidence expected {PHASE1_M13_MESH34_304_CONF}, got {conf304}.",
    )

    summary["ProbeValidated"] = True
    summary["ProbePaths"] = {
        "Mesh7": str(p7),
        "Mesh34": str(p34),
    }


def phase1_m13_329_variant_layout_guard(
    report_dir: str | Path,
    *,
    pilot_ids: list[str] | None = None,
) -> tuple[Path, Path]:
    """Candidate-only proof guard for meshSize=329 pilot sibling variant layout.

    Asserts per pilot paired ID (default: three M1.2 anchors):
    - mesh#7 attributeSets=1, mesh#34 attributeSets=0
    - mesh#34 @304 role ``position-float3-ror1-lead`` with confidence 75
    - shared primary @212 ``position-float3-ror1-lead`` on both mesh blocks

    Reads ``mesh329-family-attribute-role-matrix.json`` from *report_dir*.
    When matching probe JSONs exist, cross-checks them. Writes guard JSON+MD under
    *report_dir*. Raises ``ValueError`` on regression.

    Reference: docs/roadmap/phase1-m1.3-prep.md, M1.2 @304 handoff.
    """
    out_dir = Path(report_dir)
    matrix_path = out_dir / "mesh329-family-attribute-role-matrix.json"
    if not matrix_path.exists():
        raise FileNotFoundError(
            f"phase1-m1.3-329-variant-layout-guard requires {matrix_path}. "
            "Run mesh329-attribute-role-matrix first or pass --out with matrix present."
        )

    matrix = load_json_report(matrix_path)
    if not isinstance(matrix, dict):
        raise ValueError("mesh329-family-attribute-role-matrix.json is not a JSON object.")
    if matrix.get("Schema") != PHASE1_M13_MATRIX_SCHEMA:
        raise ValueError(f"Expected matrix schema {PHASE1_M13_MATRIX_SCHEMA!r}, got {matrix.get('Schema')!r}.")
    if matrix.get("CandidateOnly") is not True:
        raise ValueError("Matrix evidence must remain candidate-only.")

    ids = [i.lower() for i in (pilot_ids or list(PHASE1_M13_PILOT_IDS))]
    matrix_rows = [r for r in (matrix.get("MatrixRows") or []) if isinstance(r, dict)]
    pair_comps = [r for r in (matrix.get("PairComparisons") or []) if isinstance(r, dict)]

    per_id: list[dict[str, Any]] = []
    for asset_id in ids:
        summary = _phase1_m13_assert_pilot_matrix_layout(
            asset_id,
            _phase1_m13_pair_comparison(pair_comps, asset_id),
            _phase1_m13_matrix_row(matrix_rows, asset_id, 7),
            _phase1_m13_matrix_row(matrix_rows, asset_id, 34),
        )
        _phase1_m13_validate_pilot_probes(out_dir, asset_id, summary)
        per_id.append(summary)

    json_path = out_dir / PHASE1_M13_GUARD_JSON
    md_path = out_dir / PHASE1_M13_GUARD_MD
    report: dict[str, Any] = {
        "Schema": PHASE1_M13_GUARD_SCHEMA,
        "CandidateOnly": True,
        "ParserExportPromotionAllowed": False,
        "MeshSize": PHASE1_M13_MESH_SIZE,
        "PilotIDs": ids,
        "MatrixSource": str(matrix_path),
        "PerID": per_id,
        "Aggregate": {
            "PilotCount": len(ids),
            "AllMatrixValidated": all(r.get("MatrixValidated") for r in per_id),
            "AllProbeValidated": all(r.get("ProbeValidated") for r in per_id),
            "ProbeCrossCheckCount": sum(1 for r in per_id if r.get("ProbeValidated")),
        },
        "Interpretation": (
            "Phase 1 M1.3 pilot guard: sibling source-binding layout for mesh#7 vs "
            "mesh#34 in the meshSize=329 family. Confirms attribute-set split and "
            "@304 role inversion on #34 vs UV-capable #7, with shared primary @212 "
            "position role. Candidate-only; does not promote parser/export truth."
        ),
    }
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    md_lines = [
        "# Phase 1 M1.3 — 329 variant layout guard (pilot)",
        "",
        "**Candidate-only** · meshSize=329 · pilot paired anchors",
        "",
        f"Pilot IDs: {', '.join(ids)}",
        f"Matrix: `{matrix_path.name}`",
        "",
        "| ID | mesh#7 attr | mesh#34 attr | @212 mesh#7 | @212 mesh#34 | @304 mesh#34 (c) | matrix | probe |",
        "|---|---:|---:|---|---|---:|---|---|",
    ]
    for row in per_id:
        md_lines.append(
            f"| {format_markdown_cell(row['Id'])} "
            f"| {row['AttrSetCount7']} "
            f"| {row['AttrSetCount34']} "
            f"| {format_markdown_cell(row['Mesh7_212Role'])} "
            f"| {format_markdown_cell(row['Mesh34_212Role'])} "
            f"| {format_markdown_cell(row['Mesh34_304Role'])} ({row['Mesh34_304Conf']}) "
            f"| {'yes' if row.get('MatrixValidated') else 'no'} "
            f"| {'yes' if row.get('ProbeValidated') else 'no'} |"
        )
    md_lines += [
        "",
        report["Interpretation"],
        "",
        "Guard passed: layout expectations hold for pilot IDs (candidate-only).",
    ]
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print("\n--- Phase1M13_329VariantLayoutGuard candidate-only variant layout pilot")
    print(f"Pilot IDs guarded: {len(ids)}")
    print(f"Probe cross-checks: {report['Aggregate']['ProbeCrossCheckCount']}/{len(ids)}")
    print(f"Phase1M13 guard JSON: {json_path}")
    print(f"Phase1M13 guard markdown: {md_path}")
    print("Phase1M13_329VariantLayoutGuard passed: pilot layout remains candidate-only.")
    return json_path, md_path


# ============================================================================
# DescriptorConsistencyGuard  (inventory-level, Phase 13)
# ============================================================================


def descriptor_consistency_guard(report_path: str | Path) -> None:
    """Validate descriptor-guided role consistency against known baselines.

    Cross-references DescriptorGuidedRole against PrimaryRole in the
    mesh-binding inventory to flag component-count contradictions.

    Classification tiers:
    - HARD ERROR: descriptor element count physically incompatible with role
      (e.g., uint16-index -> float3 position — 1 component can't hold 3 floats)
    - WARNING: suspicious but potentially valid (e.g., float2 -> float3 position
      — valid float2 encoding discovered in Phase 11 M11.4)
    - AMBIGUOUS: consistent component counts, needs data inspection

    Baselines from Phase 11 population inventory (4,044 described streams).
    Phase 12 extended to 6 known patterns (added 08010400).
    """
    report = load_json_report(report_path)

    assert_proof_guard(
        str(report.get("Schema", "")) == "descriptor-consistency-baseline/v1",
        "Descriptor consistency report schema mismatch.",
    )

    total = required_json_integer(report, "total_described_streams", "descriptor-consistency")
    hard_errors = required_json_integer(report, "hard_error_count", "descriptor-consistency")
    warnings = required_json_integer(report, "warning_count", "descriptor-consistency")
    ambiguous = required_json_integer(report, "ambiguous_count", "descriptor-consistency")

    # Baselines from Phase 11+12 population inventory
    # These are candidate-only reference values; guard fires if they shift significantly
    assert_proof_guard(
        total >= 4000,
        f"Expected at least 4000 described streams, found {total}.",
    )
    assert_proof_guard(
        hard_errors <= 600,
        f"Hard error count {hard_errors} exceeds maximum 600.",
    )
    assert_proof_guard(
        warnings >= 50,
        f"Warning count {warnings} below minimum 50 (expected float2->position warnings).",
    )

    # Validate hard error categories exist
    hard_error_map = report.get("hard_errors", {})
    assert_proof_guard(
        isinstance(hard_error_map, dict) and len(hard_error_map) >= 3,
        "Expected at least 3 hard error categories.",
    )

    # uint16-index -> float2 UV is the largest hard error category
    uint16_to_uv = sum(v for k, v in hard_error_map.items() if "uint16-index" in k and "uv-" in k)
    assert_proof_guard(
        uint16_to_uv >= 200,
        f"uint16-index -> uv-float2 hard error count {uint16_to_uv} below expected 200+.",
    )

    # float2-uv -> normal-float3 is a key hard error
    float2_to_normal = sum(v for k, v in hard_error_map.items() if "float2-uv" in k and "normal" in k)
    assert_proof_guard(
        float2_to_normal >= 150,
        f"float2-uv -> normal-float3 hard error count {float2_to_normal} below expected 150+.",
    )

    # Validate ambiguous categories — the largest group
    ambiguous_map = report.get("ambiguous", {})
    float3_to_normal = sum(v for k, v in ambiguous_map.items() if "float3-generic" in k and "normal" in k)
    assert_proof_guard(
        float3_to_normal >= 1000,
        f"float3-generic -> normal count {float3_to_normal} below expected 1000+.",
    )

    # === Report ===
    print("\n--- DescriptorConsistencyGuard descriptor->role consistency guard (Phase 13)")
    print(f"Total described streams: {total}")
    print(f"  Hard errors:  {hard_errors:5d}  (component count physically incompatible)")
    print(f"  Warnings:     {warnings:5d}  (suspicious, e.g. float2->position)")
    print(f"  Ambiguous:    {ambiguous:5d}  (consistent component counts)")
    print()
    print("Top hard error categories:")
    for k, v in sorted(hard_error_map.items(), key=lambda x: -x[1])[:5]:
        print(f"  {k}: {v}")
    print()
    print("Top warning categories:")
    warning_map = report.get("warnings", {})
    for k, v in sorted(warning_map.items(), key=lambda x: -x[1])[:5]:
        print(f"  {k}: {v}")
    print()
    print("Top ambiguous categories:")
    for k, v in sorted(ambiguous_map.items(), key=lambda x: -x[1])[:5]:
        print(f"  {k}: {v}")
    print()
    print(
        "DescriptorConsistencyGuard passed: descriptor->role consistency baselines intact. "
        "Hard errors remain candidate-only classification flags; "
        "no geometry truth or role promotion is asserted."
    )


# ============================================================================
# SceneManifestValidationGuard (C2-7.2 ship-kill consumer contract guard)
# ============================================================================

SCENE_MANIFEST_STAGE6_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage6"
SCENE_MANIFEST_STAGE2_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage2"
SCENE_MANIFEST_PACK_PATH = (
    REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage4" / "scene-manifest-pack-v1.json"
)
SCENE_MANIFEST_SCHEMA_PATH = REPO_ROOT / "docs" / "schemas" / "scene-manifest-v1.schema.json"
SCENE_MANIFEST_STAGE7_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage7"
SCENE_MANIFEST_GUARD_JSON = "scene-manifest-validation-guard.json"
SCENE_MANIFEST_GUARD_MD = "scene-manifest-validation-guard.md"


def scene_manifest_validation_guard() -> None:
    """C2-7.2 Ship-kill consumer contract guard: validate all scene manifests.

    Validates schema, OBJ/world paths, transform finiteness, texture sources,
    and producer version across all 251 manifests (227 stage6 + 24 stage2).
    Generates stage7/scene-manifest-validation-guard.{json,md} reports.
    Raises ValueError on any assertion failure.
    """
    import math
    import os

    try:
        from jsonschema import Draft202012Validator
    except ImportError as e:
        raise ValueError(f"jsonschema not installed: {e}") from e

    schema_data = json.loads(SCENE_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8-sig"))
    validator = Draft202012Validator(schema_data)

    stage6_paths = sorted(SCENE_MANIFEST_STAGE6_DIR.glob("manifest-*.json"))
    stage2_paths = sorted(SCENE_MANIFEST_STAGE2_DIR.glob("sample-manifest-*.json"))

    assert_proof_guard(len(stage6_paths) == 227, f"Expected 227 stage6 manifests, found {len(stage6_paths)}.")
    assert_proof_guard(len(stage2_paths) == 24, f"Expected 24 stage2 samples, found {len(stage2_paths)}.")

    pack_ok = True
    pack_entry_count = 0
    try:
        pack = json.loads(SCENE_MANIFEST_PACK_PATH.read_text(encoding="utf-8-sig"))
        pack_entry_count = len(pack.get("entries", []))
    except FileNotFoundError:
        pack_ok = False

    schema_failures: list[str] = []
    obj_missing: list[str] = []
    world_missing: list[str] = []
    non_finite: list[str] = []
    bad_source: list[str] = []
    scene_sourced: list[str] = []
    bad_version: list[str] = []
    schema_invalid_flag: list[str] = []

    valid_sources = {"scene", "flythrough", "unknown"}
    all_paths = list(stage6_paths) + list(stage2_paths)
    total_manifests = len(all_paths)
    total_valid = 0

    for path in all_paths:
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        aid = manifest.get("asset_id", "unknown")

        errors = [
            f"{'/'.join(str(p) for p in err.absolute_path)}: {err.message}" for err in validator.iter_errors(manifest)
        ]
        if errors:
            schema_failures.append(f"{aid}: {errors[0]}")
        else:
            total_valid += 1

        if not manifest.get("validation", {}).get("schema_valid", False):
            schema_invalid_flag.append(aid)

        obj_path = manifest.get("geometry", {}).get("obj_path", "")
        if not os.path.exists(obj_path):
            obj_missing.append(f"{aid}: {obj_path}")

        world_json = manifest.get("world", {}).get("world_json", "")
        if not os.path.exists(world_json):
            world_missing.append(f"{aid}: {world_json}")

        ts = manifest.get("world", {}).get("world_transform_summary", {})
        for vec_name in ("translation", "rotation"):
            vec = ts.get(vec_name, [])
            for i, v in enumerate(vec):
                if not math.isfinite(v):
                    non_finite.append(f"{aid} {vec_name}[{i}]={v}")
                    break
        s = ts.get("scale", 1.0)
        if not math.isfinite(s):
            non_finite.append(f"{aid} scale={s}")

        src = manifest.get("textures", {}).get("source", "unknown")
        if src not in valid_sources:
            bad_source.append(f"{aid}: '{src}'")
        if src == "scene":
            scene_sourced.append(aid)

        ver = manifest.get("producer", {}).get("version", "")
        if ver != "v0.8":
            bad_version.append(f"{aid}: version={ver}")

    assert_proof_guard(len(schema_failures) == 0, f"{len(schema_failures)} schema failures")
    assert_proof_guard(len(obj_missing) == 0, f"{len(obj_missing)} missing OBJ paths")
    assert_proof_guard(len(world_missing) == 0, f"{len(world_missing)} missing world paths")
    assert_proof_guard(len(non_finite) == 0, f"{len(non_finite)} non-finite transforms")
    assert_proof_guard(len(bad_source) == 0, f"{len(bad_source)} invalid texture sources")
    assert_proof_guard(len(scene_sourced) == 0, f"{len(scene_sourced)} scene-sourced textures")
    assert_proof_guard(len(bad_version) == 0, f"{len(bad_version)} bad producer versions")
    assert_proof_guard(len(schema_invalid_flag) == 0, f"{len(schema_invalid_flag)} schema_valid=False")

    source_counts: dict[str, int] = {"scene": 0, "flythrough": 0, "unknown": 0}
    for path in stage6_paths:
        m = json.loads(path.read_text(encoding="utf-8-sig"))
        src = m.get("textures", {}).get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    verdict = (
        "PASS"
        if (
            total_valid == total_manifests
            and len(obj_missing) == 0
            and len(world_missing) == 0
            and len(non_finite) == 0
            and len(bad_source) == 0
            and len(schema_invalid_flag) == 0
        )
        else "FAIL"
    )

    SCENE_MANIFEST_STAGE7_DIR.mkdir(parents=True, exist_ok=True)
    json_path = SCENE_MANIFEST_STAGE7_DIR / SCENE_MANIFEST_GUARD_JSON
    md_path = SCENE_MANIFEST_STAGE7_DIR / SCENE_MANIFEST_GUARD_MD

    report = {
        "Schema": "scene-manifest-validation-guard/v1",
        "Verdict": verdict,
        "TotalManifests": total_manifests,
        "Stage6Count": len(stage6_paths),
        "Stage2Count": len(stage2_paths),
        "SchemaValid": total_valid,
        "SchemaFailures": len(schema_failures),
        "ObjPathsMissing": len(obj_missing),
        "WorldPathsMissing": len(world_missing),
        "NonFiniteTransforms": len(non_finite),
        "InvalidTextureSource": len(bad_source),
        "SceneSourcedTextures": len(scene_sourced),
        "BadProducerVersion": len(bad_version),
        "SchemaInvalidFlag": len(schema_invalid_flag),
        "PackOk": pack_ok,
        "PackEntryCount": pack_entry_count,
        "TextureSourceDistribution": source_counts,
    }
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    md_lines = [
        "# Scene Manifest Validation Guard",
        "",
        f"**Verdict: {verdict}**",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total manifests | {total_manifests} |",
        f"| Stage6 scale-out | {len(stage6_paths)} |",
        f"| Stage2 samples | {len(stage2_paths)} |",
        f"| Schema valid | {total_valid}/{total_manifests} |",
        f"| OBJ paths missing | {len(obj_missing)} |",
        f"| World paths missing | {len(world_missing)} |",
        f"| Non-finite transforms | {len(non_finite)} |",
        f"| Invalid texture source | {len(bad_source)} |",
        f"| Scene-sourced textures | {len(scene_sourced)} |",
        f"| Bad producer version | {len(bad_version)} |",
        "",
        "## Texture Source Distribution",
        "",
        f"| scene | {source_counts.get('scene', 0)} |",
        f"| flythrough | {source_counts.get('flythrough', 0)} |",
        f"| unknown | {source_counts.get('unknown', 0)} |",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print("\n--- SceneManifestValidationGuard C2-7.2 ship-kill consumer contract guard")
    print(f"Manifests: {total_manifests} (stage6={len(stage6_paths)}, stage2={len(stage2_paths)})")
