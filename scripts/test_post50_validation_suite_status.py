"""Validate compact post-50 validation-suite status."""

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


def write_json(out_dir: Path, file_name: str, payload: object) -> None:
    (out_dir / file_name).write_text(json.dumps(payload), encoding="utf-8")


def write_minimal_post50_reports(out_dir: Path) -> None:
    write_json(
        out_dir,
        "position-source-gap-report.json",
        {
            "Schema": "position-source-gap-report/v1",
            "CandidateOnly": True,
            "Rows": [{"MeshSize": 325, "ResidualStreamCount": 0, "Decision": "sparse"}],
        },
    )
    write_json(
        out_dir,
        "position-source-sibling-family-report.json",
        {
            "Schema": "position-source-sibling-family-report/v1",
            "CandidateOnly": True,
            "Families": [
                {
                    "MeshSize": 329,
                    "MeshPayloadOffsets": "stream@212",
                    "EvidenceGroups": 23,
                    "TotalStreamLinks": 46,
                    "DistinctIds": 3,
                    "Decision": "family",
                }
            ],
        },
    )
    write_json(out_dir, "position-source-sibling-probe-report.json", {"Schema": "position-source-sibling-probe-report/v1", "CandidateOnly": True})
    write_json(
        out_dir,
        "position-source-sibling-extra-position-report.json",
        {
            "Schema": "position-source-sibling-extra-position-report/v1",
            "CandidateOnly": True,
            "PairSummaries": [
                {"Id": "a", "MeshSize": 329, "MeshBlock": 34, "ExtraPayload": 96},
                {"Id": "b", "MeshSize": 329, "MeshBlock": 34, "ExtraPayload": 240},
                {"Id": "c", "MeshSize": 329, "MeshBlock": 34, "ExtraPayload": 280},
            ],
        },
    )
    write_json(
        out_dir,
        "post50-mesh329-family-proof.json",
        {
            "SchemaVersion": "post50-mesh329-family-proof/v1",
            "CandidateOnly": True,
            "Aggregate": {"EvidenceGroups": 23, "TotalStreamLinks": 46, "ExportReady": False},
        },
    )
    write_json(
        out_dir,
        "post50-mesh329-source-binding-compare.json",
        {
            "SchemaVersion": "post50-mesh329-source-binding-compare/v1",
            "CandidateOnly": True,
            "ComparisonRows": [
                {
                    "Id": "a",
                    "PrimaryStream": "@212/#28",
                    "PrimaryVectorCount": 48,
                    "ExtraStream": "@304/#57",
                    "ExtraVectorCount": 20,
                    "ExtraPayloadRemainder": 0,
                    "Mesh34AttributeSetCount": 0,
                    "Mesh34UvStreamCount": 0,
                    "ExportReady": False,
                    "Decision": "candidate-only",
                }
            ],
            "Aggregate": {
                "ExampleCount": 1,
                "ExtraStreamCount": 1,
                "ExtraPayloads": [96],
                "AllMesh34LacksCompleteAttributeSet": True,
                "AllMesh34LacksUvStreams": True,
                "Mesh34CompleteAttributeSetCount": 0,
                "Mesh34UvStreamTotal": 0,
                "ExportReady": False,
            },
        },
    )
    write_json(
        out_dir,
        "residual-position-classifier-report.json",
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
                    "MissReasons": "threshold",
                }
            ],
        },
    )
    write_json(
        out_dir,
        "residual-position-cluster-probe-report.json",
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
                    "Decision": "candidate-only",
                }
            ],
        },
    )


schema = json.loads(Path("docs/schemas/post50-validation-suite-status-v1.schema.json").read_text(encoding="utf-8"))

with tempfile.TemporaryDirectory() as tmp:
    out_dir = Path(tmp)
    write_minimal_post50_reports(out_dir)

    output = StringIO()
    with patch.object(
        sys,
        "argv",
        ["rift_workflow.py", "post50-validation-suite", "--out", str(out_dir), "--list-json"],
    ), redirect_stdout(output):
        rift_workflow.main()
    status = json.loads(output.getvalue())
    jsonschema.validate(status, schema)
    print("  PASS: validation-suite status schema validation")
    check("schema version", status["SchemaVersion"], "post50-validation-suite-status/v1")
    check("candidate only", status["CandidateOnly"], True)
    check("validation passed", status["ValidationPassed"], True)
    check("failed required checks", status["FailedRequiredChecks"], [])
    check("promotion locked", status["ParserExportPromotionAllowed"], False)
    check("freshness existing reports", status["ReportFreshness"]["ExistingReportCount"], 8)
    rows = {row["Check"]: row for row in status["ValidationRows"]}
    check("schema-backed row", rows["post50-reports-schema-backed-candidate"]["Pass"], True)
    check("promotion lock row", rows["post50-parser-export-promotion-locked"]["Pass"], True)
    check("mesh34 negative row", rows["mesh34-negative-binding-recorded"]["Pass"], True)
    check_contains("next action", status["NextAction"], "do not change parser/export behavior")

with tempfile.TemporaryDirectory() as tmp:
    missing_status = rift_workflow._post50_validation_suite_status_payload(Path(tmp))
    jsonschema.validate(missing_status, schema)
    print("  PASS: missing validation-suite status schema validation")
    check("missing validation failed", missing_status["ValidationPassed"], False)
    check_contains(
        "missing failed checks",
        "\n".join(missing_status["FailedRequiredChecks"]),
        "post50-reports-present-and-readable",
    )

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
