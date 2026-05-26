"""Validate post-50 offline position-source status ranking."""

from __future__ import annotations

import json
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import jsonschema

sys.path.insert(0, ".")

from scripts import rift_workflow

failed = 0


def check(desc: str, actual: object, expected: object) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} expected={expected!r} actual={actual!r}")
        failed += 1


def check_contains(desc: str, text: str, expected: str) -> None:
    global failed
    if expected in text:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} missing={expected!r}")
        failed += 1


schema = json.loads(Path("docs/schemas/post50-position-source-status-v1.schema.json").read_text(encoding="utf-8"))

with tempfile.TemporaryDirectory() as tmp:
    out_dir = Path(tmp)
    (out_dir / "position-source-gap-report.json").write_text(
        json.dumps(
            {
                "Schema": "position-source-gap-report/v1",
                "CandidateOnly": True,
                "Rows": [
                    {
                        "MeshSize": 325,
                        "ResidualStreamCount": 0,
                        "Decision": "topology-rich sparse-position singleton lead",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (out_dir / "position-source-sibling-family-report.json").write_text(
        json.dumps(
            {
                "Schema": "position-source-sibling-family-report/v1",
                "CandidateOnly": True,
                "Families": [
                    {
                        "MeshSize": 305,
                        "MeshPayloadOffsets": "stream@188",
                        "EvidenceGroups": 15,
                        "TotalStreamLinks": 30,
                        "DistinctIds": 15,
                        "Decision": "repeated meshSize=305 source-binding family; candidate-only probe queue",
                    },
                    {
                        "MeshSize": 329,
                        "MeshPayloadOffsets": "stream@212",
                        "EvidenceGroups": 23,
                        "TotalStreamLinks": 46,
                        "DistinctIds": 23,
                        "Decision": "repeated meshSize=329 source-binding family; candidate-only probe queue",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (out_dir / "residual-position-classifier-report.json").write_text(
        json.dumps(
            {
                "Schema": "residual-position-classifier-report/v1",
                "CandidateOnly": True,
                "CandidateGuardRows": [
                    {
                        "MeshSize": 305,
                        "Stream": "stream@188",
                        "Payload": 288,
                        "Count": 6,
                        "Plausible": 0.9444,
                        "StrictPass": False,
                        "MissReasons": "PlausibleValueRatio 0.9444 < 0.95",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (out_dir / "residual-position-cluster-probe-report.json").write_text(
        json.dumps(
            {
                "Schema": "residual-position-cluster-probe-report/v1",
                "CandidateOnly": True,
                "PayloadRows": [
                    {
                        "Payload": 288,
                        "StreamBlock": 21,
                        "ClassifierPlausible": 0.9444,
                        "ClassifierStrictPass": False,
                        "ExportReady": False,
                        "ResidualFamilyIdCount": 3,
                        "SiblingFamilyTotalStreamLinks": 30,
                        "UInt16TriplesStructureFamily": "magic-43606-u16-ternary-alternating",
                        "Decision": "candidate-only; no complete geometry binding",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    output = StringIO()
    with patch.object(
        sys,
        "argv",
        ["rift_workflow.py", "post50-position-source-status", "--out", str(out_dir), "--list-json"],
    ), redirect_stdout(output):
        rift_workflow.main()
    status = json.loads(output.getvalue())
    jsonschema.validate(status, schema)
    print("  PASS: post-50 status schema validation")
    check("schema version", status["SchemaVersion"], "post50-position-source-status/v1")
    check("candidate only", status["CandidateOnly"], True)
    check("recommended lane", status["RecommendedLane"], "source-binding-family")
    check("lane count", len(status["CandidateLanes"]), 3)
    check("top lane mesh", status["CandidateLanes"][0]["MeshSize"], 329)
    check("top lane stream", status["CandidateLanes"][0]["Stream"], "stream@212")
    check("residual payload lane", status["CandidateLanes"][1]["Payload"], 288)
    check("cluster structure lane", status["CandidateLanes"][2]["Rationale"], "magic-43606-u16-ternary-alternating")
    check("mesh325 residual disposition", status["Mesh325Disposition"]["ResidualStreamCount"], 0)
    check("promotion locked", status["ParserExportPromotionAllowed"], False)
    check_contains("strict blocker", "\n".join(status["Blockers"]), "residual-position-strict-threshold-not-met")
    check_contains("next action", status["NextAction"], "meshSize=329 stream@212")

with tempfile.TemporaryDirectory() as tmp:
    output = StringIO()
    with patch.object(
        sys,
        "argv",
        ["rift_workflow.py", "post50-position-source-status", "--out", tmp, "--list-json"],
    ), redirect_stdout(output):
        rift_workflow.main()
    missing_status = json.loads(output.getvalue())
    jsonschema.validate(missing_status, schema)
    print("  PASS: missing-report status schema validation")
    check("missing report lanes", missing_status["CandidateLanes"], [])
    check_contains("missing report blocker", "\n".join(missing_status["Blockers"]), "missing-or-unreadable-report")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
