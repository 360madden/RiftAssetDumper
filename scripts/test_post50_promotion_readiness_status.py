"""Validate post-50 mesh34 negative-binding and promotion-readiness statuses."""

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
                    "DistinctIds": 23,
                    "Decision": "candidate-only",
                }
            ],
        },
    )
    write_json(
        out_dir,
        "position-source-sibling-probe-report.json",
        {
            "Schema": "position-source-sibling-probe-report/v1",
            "CandidateOnly": True,
            "PairSummaries": [],
            "ProbeRows": [],
            "Interpretation": "candidate-only",
        },
    )
    write_json(
        out_dir,
        "position-source-sibling-extra-position-report.json",
        {
            "Schema": "position-source-sibling-extra-position-report/v1",
            "CandidateOnly": True,
            "PairSummaries": [{"Id": "0364ea142bc00ce7", "Mesh34ExtraPosition": "@304/#57 payload=240"}],
            "ProbeRows": [],
            "Interpretation": "candidate-only",
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
                    "Id": "0364ea142bc00ce7",
                    "PrimaryStream": "@212/#28",
                    "PrimaryVectorCount": 48,
                    "ExtraStream": "@304/#57",
                    "ExtraVectorCount": 20,
                    "ExtraPayloadRemainder": 0,
                    "Mesh34AttributeSetCount": 0,
                    "Mesh34UvStreamCount": 0,
                    "ExportReady": False,
                    "Decision": "candidate-only negative binding",
                }
            ],
            "Aggregate": {
                "ExampleCount": 1,
                "ExtraStreamCount": 1,
                "ExtraPayloads": [240],
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
                    "MissReasons": "PlausibleValueRatio 0.9444 < 0.95",
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
                    "Decision": "candidate-only; no complete geometry binding",
                }
            ],
        },
    )


negative_schema = json.loads(
    Path("docs/schemas/post50-mesh34-negative-binding-status-v1.schema.json").read_text(encoding="utf-8")
)
readiness_schema = json.loads(
    Path("docs/schemas/post50-promotion-readiness-status-v1.schema.json").read_text(encoding="utf-8")
)

with tempfile.TemporaryDirectory() as tmp:
    out_dir = Path(tmp)
    write_minimal_post50_reports(out_dir)

    output = StringIO()
    with patch.object(
        sys,
        "argv",
        ["rift_workflow.py", "post50-mesh34-negative-binding-status", "--out", str(out_dir), "--list-json"],
    ), redirect_stdout(output):
        rift_workflow.main()
    negative_status = json.loads(output.getvalue())
    jsonschema.validate(negative_status, negative_schema)
    print("  PASS: mesh34 negative-binding status schema validation")
    check("negative schema", negative_status["SchemaVersion"], "post50-mesh34-negative-binding-status/v1")
    check("negative candidate only", negative_status["CandidateOnly"], True)
    check("negative example count", negative_status["Aggregate"]["ExampleCount"], 1)
    check("negative binding proven", negative_status["Aggregate"]["NegativeBindingProven"], True)
    check("negative parser/export locked", negative_status["ParserExportPromotionAllowed"], False)
    check_contains("negative blocker", "\n".join(negative_status["Blockers"]), "mesh34-complete-geometry-binding")

    output = StringIO()
    with patch.object(
        sys,
        "argv",
        ["rift_workflow.py", "post50-promotion-readiness-status", "--out", str(out_dir), "--list-json"],
    ), redirect_stdout(output):
        rift_workflow.main()
    readiness_status = json.loads(output.getvalue())
    jsonschema.validate(readiness_status, readiness_schema)
    print("  PASS: promotion-readiness status schema validation")
    check("readiness schema", readiness_status["SchemaVersion"], "post50-promotion-readiness-status/v1")
    check("overall ready", readiness_status["OverallReady"], False)
    check("promotion locked", readiness_status["ParserExportPromotionAllowed"], False)
    check("schema backed report count", readiness_status["SchemaBackedReportCount"], 8)
    check("freshness existing reports", readiness_status["ReportFreshness"]["ExistingReportCount"], 8)
    check("freshness missing reports", readiness_status["ReportFreshness"]["MissingReportCount"], 0)
    gates = {row["Gate"]: row["Pass"] for row in readiness_status["GateRows"]}
    check("all reports schema-backed gate", gates["all-post50-reports-schema-backed"], True)
    check("mesh34 binding gate blocked", gates["mesh34-complete-geometry-binding"], False)
    check("residual strict gate blocked", gates["residual-strict-threshold"], False)
    check_contains("readiness blocker", "\n".join(readiness_status["Blockers"]), "parser-export-promotion-not-allowed")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
