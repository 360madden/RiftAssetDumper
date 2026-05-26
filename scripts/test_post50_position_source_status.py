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
                        "Decision": "mesh#34 extra @304/#57 position-like stream repeats",
                    },
                    {
                        "Pair": "mesh329extra04de",
                        "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                        "Id": "04de901531a091ab",
                        "SharedPrimaryPosition": "block#28 payload=444 offsets=@212/@212",
                        "Mesh34ExtraPosition": "@304/#57 payload=280 position-float3-ror1-lead",
                        "Decision": "mesh#34 extra @304/#57 position-like stream repeats",
                    },
                ],
                "ProbeRows": [],
                "Interpretation": "candidate-only",
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
    check("report status count", len(status["ReportStatuses"]), 6)
    check("recommended lane", status["RecommendedLane"], "source-binding-family")
    check("lane count", len(status["CandidateLanes"]), 4)
    check("top lane mesh", status["CandidateLanes"][0]["MeshSize"], 329)
    check("top lane stream", status["CandidateLanes"][0]["Stream"], "stream@212")
    check("extra-position lane", status["CandidateLanes"][1]["Lane"], "source-binding-extra-position")
    check("extra-position stream", status["CandidateLanes"][1]["Stream"], "mesh#34 @304/#57")
    check("residual payload lane", status["CandidateLanes"][2]["Payload"], 288)
    check("cluster structure lane", status["CandidateLanes"][3]["Rationale"], "magic-43606-u16-ternary-alternating")
    check("mesh325 residual disposition", status["Mesh325Disposition"]["ResidualStreamCount"], 0)
    check("promotion locked", status["ParserExportPromotionAllowed"], False)
    check_contains("strict blocker", "\n".join(status["Blockers"]), "residual-position-strict-threshold-not-met")
    check_contains("extra-position blocker", "\n".join(status["Blockers"]), "mesh329-extra-position-like-stream")
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
