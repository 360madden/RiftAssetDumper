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
    (out_dir / "position-source-sibling-probe-report.json").write_text(
        json.dumps(
            {
                "Schema": "position-source-sibling-probe-report/v1",
                "CandidateOnly": True,
                "PairSummaries": [
                    {
                        "Pair": "8e016329",
                        "PairLabel": "meshSize 329 repeated-position sibling",
                        "Id": "8e01613d7ce9e297",
                        "MeshBlocks": "mesh#6, mesh#31",
                        "MeshSizes": "329, 329",
                        "VertexCount": 93,
                        "PrimaryTopology": "implicit-triangle-list-candidate",
                        "SharedPositionStream": (
                            "block#25 payload=1116 usage=1 access=19 "
                            "role=position-float3-ror1-lead"
                        ),
                        "PositionOffsetPattern": "same mesh payload offset",
                        "NormalStreams": "mesh#6:block#26 payload=1116 | mesh#31:block#45 payload=1116",
                        "UvStreams": "mesh#6:block#30 payload=744 | mesh#31:block#49 payload=744",
                        "Decision": "shared-position-stream sibling evidence; candidate-only",
                    }
                ],
                "ProbeRows": [],
                "Interpretation": "candidate-only",
            }
        ),
        encoding="utf-8",
    )
    (out_dir / "position-source-sibling-extra-position-report.json").write_text(
        json.dumps(
            {
                "Schema": "position-source-sibling-extra-position-report/v1",
                "CandidateOnly": True,
                "PairSummaries": [
                    {
                        "Pair": "mesh329extra0364",
                        "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                        "Id": "0364ea142bc00ce7",
                        "SharedPrimaryPosition": "block#28 payload=576 offsets=@212/@212",
                        "Mesh34ExtraPosition": "@304/#57 payload=240 position-float3-ror1-lead",
                        "Mesh7Summary": "mesh#7 attr=v=48 p@212/#28 n@220/#29 uv@304/#33",
                        "Mesh34Summary": "mesh#34 attr=none; pos=@212/#28 | @304/#57",
                        "Decision": "mesh#34 extra @304/#57 position-like stream repeats",
                    },
                    {
                        "Pair": "mesh329extra04de",
                        "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                        "Id": "04de901531a091ab",
                        "SharedPrimaryPosition": "block#28 payload=444 offsets=@212/@212",
                        "Mesh34ExtraPosition": "@304/#57 payload=280 position-float3-ror1-lead",
                        "Mesh7Summary": "mesh#7 attr=v=37 p@212/#28 n@220/#29 uv@304/#33",
                        "Mesh34Summary": "mesh#34 attr=none; pos=@212/#28 | @304/#57",
                        "Decision": "mesh#34 extra @304/#57 position-like stream repeats",
                    },
                ],
                "ProbeRows": [
                    {
                        "Pair": "mesh329extra0364",
                        "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                        "Id": "0364ea142bc00ce7",
                        "MeshBlock": 7,
                        "MeshSize": 329,
                        "PositionStreams": [
                            {
                                "MeshPayloadOffset": 212,
                                "TargetBlockIndex": 28,
                                "Payload": 576,
                                "Role": "position-float3-ror1-lead",
                            }
                        ],
                        "NormalStreams": [],
                        "UvStreams": [],
                        "SideStreams": [],
                        "AttributeSetCount": 1,
                        "AttributeSummary": "v=48 p@212/#28 n@220/#29 uv@304/#33",
                        "ProbePath": "Exports/probe-nif-mesh-0364ea142bc00ce7-mesh7.json",
                    },
                    {
                        "Pair": "mesh329extra0364",
                        "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                        "Id": "0364ea142bc00ce7",
                        "MeshBlock": 34,
                        "MeshSize": 329,
                        "PositionStreams": [
                            {
                                "MeshPayloadOffset": 212,
                                "TargetBlockIndex": 28,
                                "Payload": 576,
                                "Role": "position-float3-ror1-lead",
                            },
                            {
                                "MeshPayloadOffset": 304,
                                "TargetBlockIndex": 57,
                                "Payload": 240,
                                "Role": "position-float3-ror1-lead",
                            },
                        ],
                        "NormalStreams": [],
                        "UvStreams": [],
                        "SideStreams": [],
                        "AttributeSetCount": 0,
                        "AttributeSummary": "none",
                        "ProbePath": "Exports/probe-nif-mesh-0364ea142bc00ce7-mesh34.json",
                    },
                ],
                "Interpretation": "candidate-only",
            }
        ),
        encoding="utf-8",
    )
    extra_schema = json.loads(
        Path("docs/schemas/position-source-sibling-extra-position-report-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    extra_report = json.loads(
        (out_dir / "position-source-sibling-extra-position-report.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(extra_report, extra_schema)
    print("  PASS: extra-position report schema validation")
    (out_dir / "post50-mesh329-family-proof.json").write_text(
        json.dumps(
            {
                "SchemaVersion": "post50-mesh329-family-proof/v1",
                "CandidateOnly": True,
                "Aggregate": {
                    "EvidenceGroups": 23,
                    "TotalStreamLinks": 46,
                    "ExportReady": False,
                },
            }
        ),
        encoding="utf-8",
    )
    (out_dir / "post50-mesh329-source-binding-compare.json").write_text(
        json.dumps(
            {
                "SchemaVersion": "post50-mesh329-source-binding-compare/v1",
                "CandidateOnly": True,
                "Aggregate": {
                    "ExampleCount": 2,
                    "ExtraStreamCount": 2,
                    "ExtraPayloads": [240, 280],
                    "ExportReady": False,
                },
            }
        ),
        encoding="utf-8",
    )
    (out_dir / "post50-mesh34-complete-binding-negative-proof.json").write_text(
        json.dumps(
            {
                "SchemaVersion": "post50-mesh34-complete-binding-negative-proof/v1",
                "CandidateOnly": True,
                "Aggregate": {
                    "ExampleCount": 2,
                    "CompleteGeometryBindingCount": 0,
                    "NegativeBindingCount": 2,
                    "AllRowsNegativeBinding": True,
                    "ParserExportPromotionAllowed": False,
                    "ExportReady": False,
                },
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
    check("report status count", len(status["ReportStatuses"]), 9)
    check("freshness existing reports", status["ReportFreshness"]["ExistingReportCount"], 9)
    check("freshness missing reports", status["ReportFreshness"]["MissingReportCount"], 0)
    check("freshness unreadable reports", status["ReportFreshness"]["UnreadableReportCount"], 0)
    check("freshness missing keys", status["ReportFreshness"]["MissingOrUnreadableKeys"], [])
    check(
        "schema-backed report statuses",
        {report_status["EvidenceLevel"] for report_status in status["ReportStatuses"]},
        {"schema-backed-candidate"},
    )
    check("recommended lane", status["RecommendedLane"], "source-binding-family")
    check("lane count", len(status["CandidateLanes"]), 4)
    check("top lane mesh", status["CandidateLanes"][0]["MeshSize"], 329)
    check("top lane stream", status["CandidateLanes"][0]["Stream"], "stream@212")
    check_contains("top lane schema-backed rationale", status["CandidateLanes"][0]["Rationale"], "schema-backed")
    check("extra-position lane", status["CandidateLanes"][1]["Lane"], "source-binding-extra-position")
    check("extra-position stream", status["CandidateLanes"][1]["Stream"], "mesh#34 @304/#57")
    check_contains("extra-position schema-backed rationale", status["CandidateLanes"][1]["Rationale"], "schema-backed")
    check("residual payload lane", status["CandidateLanes"][2]["Payload"], 288)
    check("cluster structure lane", status["CandidateLanes"][3]["Rationale"], "magic-43606-u16-ternary-alternating")
    check("mesh325 residual disposition", status["Mesh325Disposition"]["ResidualStreamCount"], 0)
    check("promotion locked", status["ParserExportPromotionAllowed"], False)
    check_contains("strict blocker", "\n".join(status["Blockers"]), "residual-position-strict-threshold-not-met")
    check_contains("extra-position blocker", "\n".join(status["Blockers"]), "mesh329-extra-position-like-stream")
    check_contains("family proof blocker", "\n".join(status["Blockers"]), "mesh329-family-proof-candidate-only")
    check_contains("compare export blocker", "\n".join(status["Blockers"]), "mesh329-source-binding-compare-export-blocked")
    check_contains("next action", status["NextAction"], "source-binding compare report")

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
    check("missing freshness existing reports", missing_status["ReportFreshness"]["ExistingReportCount"], 0)
    check("missing freshness missing reports", missing_status["ReportFreshness"]["MissingReportCount"], 9)
    check(
        "missing report evidence levels",
        {report_status["EvidenceLevel"] for report_status in missing_status["ReportStatuses"]},
        {"missing-or-unreadable"},
    )
    check_contains("missing report blocker", "\n".join(missing_status["Blockers"]), "missing-or-unreadable-report")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
