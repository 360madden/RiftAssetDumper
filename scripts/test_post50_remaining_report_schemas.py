"""Validate remaining post-50 position-source report schemas."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import jsonschema

failed = 0


def check(desc: str, actual: object, expected: object) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} expected={expected!r} actual={actual!r}")
        failed += 1


def load_schema(name: str) -> dict[str, Any]:
    return json.loads(Path("docs/schemas", name).read_text(encoding="utf-8"))


def validate_actual_report(report_name: str, schema: dict[str, Any]) -> dict[str, Any] | None:
    path = Path("Exports") / report_name
    if not path.exists():
        print(f"  SKIP: actual ignored {report_name} is not present")
        return None
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    jsonschema.validate(report, schema)
    print(f"  PASS: actual ignored {report_name} validates")
    return report


gap_schema = load_schema("position-source-gap-report-v1.schema.json")
gap_fixture: dict[str, Any] = {
    "Schema": "position-source-gap-report/v1",
    "CandidateOnly": True,
    "SourceReport": "Exports/nif-mesh-binding-inventory.json",
    "TargetMeshSizes": [305, 325, 329],
    "Rows": [
        {
            "MeshSize": 325,
            "PositionLeadCount": 1,
            "TopPairingRows": 3,
            "TopologyPairingCount": 300.0,
            "NormalPairingCount": 0.0,
            "UvPairingCount": 0.0,
            "PositionPairingCount": 0.0,
            "AttributeSetRows": 1,
            "ResidualStreamCount": 0,
            "ResidualPositionCandidateRows": 0,
            "Decision": "topology-rich sparse-position singleton lead",
            "PositionSamples": "-",
            "TopologyHints": "v=1 count=1 implicit",
            "ResidualHints": "-",
        }
    ],
    "Interpretation": "candidate-only",
}
jsonschema.validate(gap_fixture, gap_schema)
print("  PASS: position-source gap fixture validates")
actual_gap = validate_actual_report("position-source-gap-report.json", gap_schema)
if actual_gap:
    mesh325 = next(row for row in actual_gap["Rows"] if row["MeshSize"] == 325)
    check("actual gap mesh325 residual count", mesh325["ResidualStreamCount"], 0)


classifier_schema = load_schema("residual-position-classifier-report-v1.schema.json")
classifier_row: dict[str, Any] = {
    "MeshSize": 305,
    "Stream": "stream@188",
    "Payload": 288,
    "Count": 6,
    "SampleCount": 6,
    "ArchiveCount": 1,
    "SampleMeshes": "mesh#27,mesh#7",
    "SampleIds": "example:mesh#7",
    "VectorCount": 24,
    "Finite": 1.0,
    "Plausible": 0.9444,
    "NonZero": 1.0,
    "Extent": 37.0,
    "StrictPass": False,
    "MaxPlausibleThresholdForSample": 0.9444,
    "MissReasons": "PlausibleValueRatio 0.9444 < 0.95",
}
classifier_fixture: dict[str, Any] = {
    "Schema": "residual-position-classifier-report/v1",
    "CandidateOnly": True,
    "Target": "meshSize=305 stream@188 StringValue=POSITION usage=1 access=19",
    "SourceReport": "Exports/nif-mesh-binding-inventory.json",
    "StrictClassifierRole": "position-float3-ror1-lead",
    "StrictClassifierThresholds": {"PlausibleValueRatio": ">= 0.95"},
    "Summary": {
        "TargetRows": 1,
        "StrictPassRows": 0,
        "CandidateGuardRows": 1,
        "MinCandidatePlausible": 0.9444,
        "MaxCandidatePlausible": 0.9444,
    },
    "Rows": [classifier_row],
    "CandidateGuardRows": [classifier_row],
    "Interpretation": "candidate-only",
}
jsonschema.validate(classifier_fixture, classifier_schema)
print("  PASS: residual classifier fixture validates")
actual_classifier = validate_actual_report("residual-position-classifier-report.json", classifier_schema)
if actual_classifier:
    check("actual classifier strict pass rows", actual_classifier["Summary"]["StrictPassRows"], 0)


cluster_schema = load_schema("residual-position-cluster-probe-report-v1.schema.json")
cluster_fixture: dict[str, Any] = {
    "Schema": "residual-position-cluster-probe-report/v1",
    "CandidateOnly": True,
    "Target": "meshSize=305 stream@188 StringValue=POSITION usage=1 access=19",
    "StrictClassifierThresholdUnchanged": True,
    "ExportPromotion": "blocked",
    "ExportReadinessAssertion": "blocked-for-all-rows",
    "SourceReports": {"ResidualClassifier": "Exports/residual-position-classifier-report.json"},
    "SourceReportStatuses": [],
    "MissingSourceReports": [],
    "BoundaryNotes": ["OBJ/export remains blocked"],
    "Mesh305SiblingFamily": None,
    "PayloadRows": [
        {
            "Payload": 288,
            "Id": "example",
            "StreamBlock": 21,
            "StreamClassification": "uint16-compatible-body",
            "ClassifierPlausible": 0.9444,
            "ClassifierStrictPass": False,
            "ResidualFamilyCandidateGuard": True,
            "AttributeSetTotal": 0,
            "PairingTotal": 0,
            "ReviewRequired": False,
            "ExportReady": False,
            "GeometryTruthPromoted": False,
            "Decision": "candidate-only; no complete geometry binding",
        }
    ],
    "BodyComparisonRows": [
        {
            "Payload": 288,
            "BaselinePayload": 288,
            "ComparedBytes": 128,
            "DiffBytes": 0,
            "Decision": "candidate-only byte-layout evidence",
        }
    ],
    "FocusedAttributeBindingSearchRows": [
        {
            "Payload": 288,
            "AttributeSetTotal": 0,
            "PairingTotal": 0,
            "CompleteBindingFound": False,
            "Decision": "candidate-only; no complete geometry binding",
        }
    ],
    "StreamRows": [
        {
            "Payload": 288,
            "Id": "example",
            "StreamBlock": 21,
            "DeclaredPayloadBytes": 288,
            "Classification": "uint16-compatible-body",
            "ByteLength": 288,
        }
    ],
    "MeshRows": [
        {
            "Payload": 288,
            "Id": "example",
            "MeshBlock": 7,
            "MeshSize": 305,
            "MeshPayloadOffset": 188,
            "TargetBlock": 21,
            "StreamPayload": 288,
            "AttributeSetCount": 0,
            "PairingCount": 0,
            "ReviewRequired": False,
            "Decision": "candidate-only; no complete geometry binding",
        }
    ],
    "UInt16TriplesStructureSummary": {
        "StructuralFamilies": [],
        "Magic43606Payloads": [],
        "AlternatingPayloads": [],
        "Interpretation": "candidate-only",
    },
    "Interpretation": "candidate-only",
}
jsonschema.validate(cluster_fixture, cluster_schema)
print("  PASS: residual cluster fixture validates")
actual_cluster = validate_actual_report("residual-position-cluster-probe-report.json", cluster_schema)
if actual_cluster:
    check("actual cluster export promotion", actual_cluster["ExportPromotion"], "blocked")
    check(
        "actual cluster payload exports blocked",
        {row["ExportReady"] for row in actual_cluster["PayloadRows"]},
        {False},
    )


print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
