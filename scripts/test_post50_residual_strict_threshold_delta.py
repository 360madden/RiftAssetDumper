"""Validate post-50 residual strict-threshold delta report."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import jsonschema

sys.path.insert(0, ".")

from scripts.rift_workflow_reports import post50_residual_strict_threshold_delta_report

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


schema = json.loads(
    Path("docs/schemas/post50-residual-strict-threshold-delta-v1.schema.json").read_text(encoding="utf-8")
)

with tempfile.TemporaryDirectory() as tmp:
    out_dir = Path(tmp)
    classifier_path = out_dir / "residual-position-classifier-report.json"
    cluster_path = out_dir / "residual-position-cluster-probe-report.json"
    classifier_path.write_text(
        json.dumps(
            {
                "Schema": "residual-position-classifier-report/v1",
                "CandidateOnly": True,
                "CandidateGuardRows": [
                    {
                        "MeshSize": 305,
                        "Stream": "stream@188",
                        "Payload": 96,
                        "Count": 6,
                        "SampleCount": 6,
                        "VectorCount": 8,
                        "Plausible": 0.875,
                        "StrictPass": False,
                        "MaxPlausibleThresholdForSample": 0.875,
                        "MissReasons": "PlausibleValueRatio 0.875 < 0.95",
                    },
                    {
                        "MeshSize": 305,
                        "Stream": "stream@188",
                        "Payload": 288,
                        "Count": 6,
                        "SampleCount": 6,
                        "VectorCount": 24,
                        "Plausible": 0.9444,
                        "StrictPass": False,
                        "MaxPlausibleThresholdForSample": 0.9444,
                        "MissReasons": "PlausibleValueRatio 0.9444 < 0.95",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    cluster_path.write_text(
        json.dumps(
            {
                "Schema": "residual-position-cluster-probe-report/v1",
                "CandidateOnly": True,
                "PayloadRows": [
                    {
                        "Payload": 288,
                        "AttributeSetTotal": 0,
                        "PairingTotal": 0,
                        "ExportReady": False,
                        "GeometryTruthPromoted": False,
                        "Decision": "candidate-only; no complete geometry binding",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    json_path, md_path = post50_residual_strict_threshold_delta_report(classifier_path, out_dir, cluster_path)
    report = json.loads(json_path.read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)
    print("  PASS: residual strict-threshold delta schema validation")
    check("markdown exists", md_path.exists(), True)
    check("schema version", report["SchemaVersion"], "post50-residual-strict-threshold-delta/v1")
    check("candidate only", report["CandidateOnly"], True)
    check("target payload", report["Target"]["Payload"], 288)
    check("target plausible", report["Aggregate"]["TargetPlausible"], 0.9444)
    check("target delta", report["Aggregate"]["TargetPlausibleDeltaToStrict"], 0.0056)
    check("target strict pass", report["Aggregate"]["TargetStrictPass"], False)
    check("geometry binding", report["Aggregate"]["TargetCompleteGeometryBindingProven"], False)
    check("parser/export locked", report["ParserExportPromotionAllowed"], False)
    check_contains(
        "deferred", "\n".join(report["Aggregate"].get("Deferred", [])), "residual-position-strict-threshold-not-met"
    )

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
