"""Smoke tests for rift_workflow_reports.py summaries."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, ".")

from scripts.rift_workflow_reports import show_report_summary

failed = 0


def check_contains(desc: str, text: str, expected: str) -> None:
    global failed
    if expected in text:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc}  missing={expected!r}")
        failed += 1


print("=== MeshBindings summary ===")
with TemporaryDirectory() as temp_dir:
    report_path = Path(temp_dir) / "mesh-bindings.json"
    report_path.write_text(
        json.dumps(
            {
                "NifPayloads": 2,
                "MeshBlocks": 3,
                "CandidateLinks": 4,
                "GhidraStyleLayoutValidStreamBodies": 4,
                "LegacyOffsetShiftedStreamBodies": 4,
                "GhidraRoleDeltaStreamBodies": 1,
                "PairCompatibleMeshes": 0,
                "PairCompatibleLinks": 0,
                "GhidraPairCompatibleMeshes": 1,
                "GhidraPairCompatibleLinks": 2,
                "TopGhidraRoleDeltas": [
                    {
                        "MeshSize": 325,
                        "DeclaredPayloadBytes": 96,
                        "DataStreamUsage": 1,
                        "DataStreamAccess": 19,
                        "LegacyRole": "unknown-binary",
                        "GhidraRole": "position-float3-ror1-lead",
                        "Count": 7,
                        "AverageLegacyConfidence": 10,
                        "AverageGhidraConfidence": 85,
                    }
                ],
                "TopGhidraPairings": [
                    {
                        "MeshSize": 325,
                        "Count": 2,
                        "IndexDataStreamUsage": 0,
                        "IndexDataStreamAccess": 19,
                        "IndexRole": "index-u16le-lead",
                        "VertexDataStreamUsage": 1,
                        "VertexDataStreamAccess": 19,
                        "VertexRole": "normal-float3-lead",
                        "VertexCount": 24,
                        "MaxIndexObserved": 23,
                        "IndexPairCount": 36,
                        "TriangleListTriangleCount": 12,
                        "TriangleStripWindowCount": 34,
                        "MaxIndexCoverageRatio": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        show_report_summary("MeshBindings", str(report_path))
    text = buffer.getvalue()
    check_contains("summary counts", text, "roleDeltas=1")
    check_contains("ghidra pairing counts", text, "ghidraPairMeshes=1 ghidraPairLinks=2")
    check_contains("delta heading", text, "Top Ghidra role deltas")
    check_contains("delta role arrow", text, "unknown-binary->position-float3-ror1-lead=7")
    check_contains("delta grouping fields", text, "meshSize=325 payload=96 usage=1 access=19")
    check_contains("ghidra pairing heading", text, "Top Ghidra pairings")
    check_contains("ghidra pairing roles", text, "index-u16le-lead->vertex[usage=1 access=19] normal-float3-lead")

    no_delta_path = Path(temp_dir) / "mesh-bindings-no-deltas.json"
    no_delta_path.write_text(
        json.dumps({"NifPayloads": 1, "MeshBlocks": 1, "CandidateLinks": 1}),
        encoding="utf-8",
    )
    no_delta_buffer = io.StringIO()
    with redirect_stdout(no_delta_buffer):
        show_report_summary("MeshBindings", str(no_delta_path))
    check_contains("missing deltas does not crash", no_delta_buffer.getvalue(), "NIF payloads=1")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
