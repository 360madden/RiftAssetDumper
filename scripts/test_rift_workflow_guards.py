"""Smoke tests for rift_workflow_guards.py guard routing."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

sys.path.insert(0, ".")

from scripts import rift_workflow
from scripts.rift_workflow_guards import (
    ghidra_attribute_candidate_guard,
    ghidra_pairing_non_export_guard,
    nidatastream_parser_export_non_consumption_guard,
)

failed = 0


def check(desc: str, actual: Any, expected: Any) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc}  expected={expected!r}  actual={actual!r}")
        failed += 1


def check_raises(desc: str, fn: Any, exc_type: type[Exception] = ValueError) -> None:
    global failed
    try:
        fn()
        print(f"  FAIL: {desc} (no exception raised)")
        failed += 1
    except exc_type:
        print(f"  PASS: {desc}")


def minimal_program(extra_decode_line: str = "", extra_pairing_line: str = "") -> str:
    guarded_methods = "\n".join(
        [
            "  private static int DecodeNifGeometry(AppOptions options)\n"
            "  {\n"
            f"    {extra_decode_line}\n"
            "    return 0;\n"
            "  }\n",
            "  private static List<NifMeshAttributeSetSample> FindNifMeshAttributeSets()\n"
            "  {\n"
            "    return new List<NifMeshAttributeSetSample>();\n"
            "  }\n",
            "  private static List<NifAttributeExtraStreamSample> FindNifAttributeSetExtraStreams()\n"
            "  {\n"
            "    return new List<NifAttributeExtraStreamSample>();\n"
            "  }\n",
            "  private static List<NifLinkedStreamPositionCandidate> ScanNifLinkedStreamPositionCandidates()\n"
            "  {\n"
            "    return new List<NifLinkedStreamPositionCandidate>();\n"
            "  }\n",
            "  private static List<NifAttributeVertexSample> BuildNifAttributeFloatVertexSamples()\n"
            "  {\n"
            "    return new List<NifAttributeVertexSample>();\n"
            "  }\n",
            "  private static List<NifAttributeVertexSample> BuildNifAttributeUInt16VertexSamples()\n"
            "  {\n"
            "    return new List<NifAttributeVertexSample>();\n"
            "  }\n",
            "  private static List<NifMeshBoundStreamSummary> BuildNifMeshBoundStreamSummaries()\n"
            "  {\n"
            "    streamSummaries.Add(new NifMeshBoundStreamSummary(\n"
            "        RoleStats: roleStats,\n"
            "        GhidraRoleStats: ghidraRoleStats));\n"
            "    return streamSummaries;\n"
            "  }\n",
            "  private static List<NifMeshProbePairing> FindNifMeshProbePairings(\n"
            "      List<NifMeshBoundStreamSummary> streams)\n"
            "  {\n"
            f"    {extra_pairing_line}\n"
            "    var indexStreams = streams\n"
            "        .Where(static s => s.RoleStats.PrimaryRole.StartsWith(\"index-\", StringComparison.OrdinalIgnoreCase) && s.RoleStats.IndexMax is not null)\n"
            "        .ToList();\n"
            "    var vertexStreams = streams\n"
            "        .Where(static s => !s.RoleStats.PrimaryRole.StartsWith(\"index-\", StringComparison.OrdinalIgnoreCase) && s.RoleStats.VertexCountCandidates.Count > 0)\n"
            "        .ToList();\n"
            "    return new List<NifMeshProbePairing>();\n"
            "  }\n",
        ]
    )
    return (
        "internal static class Program\n"
        "{\n"
        "  private static int ProbeNifMesh(AppOptions options)\n"
        "  {\n"
        "    var ghidraPairings = FindNifMeshProbePairings(\n"
        "          BuildNifGhidraRoleStreamSummaries(streamSummaries),\n"
        "          pairingSource: \"ghidra-sidecar\",\n"
        "          candidateOnly: true);\n"
        "    return 0;\n"
        "  }\n"
        f"{guarded_methods}"
        "}\n"
    )


def baseline_attribute_report() -> dict[str, Any]:
    return {
        "SchemaVersion": "ghidra-attribute-candidate-report/v1",
        "CandidateOnly": True,
        "Summary": {
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
        },
        "Groups": [
            {
                "SampleIdPrefix": "25f30ec90608eab7",
                "SampleMeshBlockIndex": 7,
                "CompletePositionNormalUvCandidate": False,
            }
        ],
    }


print("=== Ghidra pairing non-export guard ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    safe_program = temp_path / "Program.safe.cs"
    safe_program.write_text(minimal_program(), encoding="utf-8")
    ghidra_pairing_non_export_guard(safe_program)
    print("  PASS: safe candidate-only program")

    unsafe_program = temp_path / "Program.unsafe.cs"
    unsafe_program.write_text(
        minimal_program("var promoted = BuildNifGhidraRoleStreamSummaries(streamSummaries);"),
        encoding="utf-8",
    )
    check_raises("decode/export Ghidra use fails closed", lambda: ghidra_pairing_non_export_guard(unsafe_program))

    unmarked_program = temp_path / "Program.unmarked.cs"
    unmarked_program.write_text(minimal_program().replace("          candidateOnly: true", "          candidateOnly: false"), encoding="utf-8")
    check_raises("unmarked sidecar fails closed", lambda: ghidra_pairing_non_export_guard(unmarked_program))

check("actual Program.cs guard", True, True)
ghidra_pairing_non_export_guard()

print("=== NiDataStream parser/export non-consumption guard ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    safe_program = temp_path / "Program.nidatastream.safe.cs"
    safe_program.write_text(minimal_program(), encoding="utf-8")
    nidatastream_parser_export_non_consumption_guard(safe_program)
    print("  PASS: safe NiDataStream candidate-only program")

    unsafe_decode_program = temp_path / "Program.nidatastream.unsafe.decode.cs"
    unsafe_decode_program.write_text(
        minimal_program("var promoted = SliceNifDataStreamGhidraBody(payload, layout);"),
        encoding="utf-8",
    )
    check_raises(
        "decode/export NiDataStream Ghidra body use fails closed",
        lambda: nidatastream_parser_export_non_consumption_guard(unsafe_decode_program),
    )

    unsafe_pairing_program = temp_path / "Program.nidatastream.unsafe.pairing.cs"
    unsafe_pairing_program.write_text(
        minimal_program(extra_pairing_line="var promoted = streams.Where(static s => s.GhidraRoleStats != null);"),
        encoding="utf-8",
    )
    check_raises(
        "pairing helper GhidraRoleStats use fails closed",
        lambda: nidatastream_parser_export_non_consumption_guard(unsafe_pairing_program),
    )

check("actual Program.cs NiDataStream parser/export guard", True, True)
nidatastream_parser_export_non_consumption_guard()

print("=== Ghidra attribute candidate guard ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    report_path = temp_path / "ghidra-attribute-candidate-report.json"
    baseline = baseline_attribute_report()
    report_path.write_text(json.dumps(baseline), encoding="utf-8")
    ghidra_attribute_candidate_guard(report_path)
    print("  PASS: baseline attribute candidate report")

    promoted_path = temp_path / "ghidra-attribute-candidate-report-promoted.json"
    promoted = json.loads(json.dumps(baseline))
    promoted["Summary"]["CompletePositionNormalUvCandidateGroups"] = 1
    promoted["Groups"][0]["CompletePositionNormalUvCandidate"] = True
    promoted_path.write_text(json.dumps(promoted), encoding="utf-8")
    check_raises("complete Ghidra group fails closed", lambda: ghidra_attribute_candidate_guard(promoted_path))

print("=== Ghidra workflow guard suite ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    (temp_path / "ghidra-attribute-candidate-report.json").write_text(
        json.dumps(baseline_attribute_report()),
        encoding="utf-8",
    )
    suite_calls: dict[str, bool] = {}

    def fake_non_export_guard() -> None:
        suite_calls["non_export"] = True

    def fake_nidatastream_non_consumption_guard() -> None:
        suite_calls["nidatastream_non_consumption"] = True

    suite_argv = [
        "rift_workflow.py",
        "ghidra-workflow-guard-suite",
        "--out",
        str(temp_path),
    ]
    with (
        patch.object(sys, "argv", suite_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        patch("scripts.rift_workflow.ghidra_pairing_non_export_guard", side_effect=fake_non_export_guard),
        patch(
            "scripts.rift_workflow.nidatastream_parser_export_non_consumption_guard",
            side_effect=fake_nidatastream_non_consumption_guard,
        ),
    ):
        rift_workflow.main()

    check("workflow suite ran non-export guard", suite_calls.get("non_export"), True)
    check(
        "workflow suite ran NiDataStream non-consumption guard",
        suite_calls.get("nidatastream_non_consumption"),
        True,
    )

with TemporaryDirectory() as temp_dir:
    try:
        rift_workflow._ensure_ghidra_attribute_candidate_report(Path(temp_dir), 100)
        print("  FAIL: missing attribute report error context (no exception)")
        failed += 1
    except ValueError as exc:
        check("missing attribute report error context", "Ghidra attribute candidate workflow" in str(exc), True)

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
