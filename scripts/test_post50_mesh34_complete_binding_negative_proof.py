"""Validate post-50 mesh34 complete-binding negative proof report."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import jsonschema

sys.path.insert(0, ".")

from scripts.rift_workflow_reports import post50_mesh34_complete_binding_negative_proof

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
    Path("docs/schemas/post50-mesh34-complete-binding-negative-proof-v1.schema.json").read_text(encoding="utf-8")
)

with tempfile.TemporaryDirectory() as tmp:
    out_dir = Path(tmp)
    source_path = out_dir / "post50-mesh329-source-binding-compare.json"
    source_path.write_text(
        json.dumps(
            {
                "SchemaVersion": "post50-mesh329-source-binding-compare/v1",
                "CandidateOnly": True,
                "ComparisonRows": [
                    {
                        "Pair": "mesh329extra0364",
                        "Id": "0364ea142bc00ce7",
                        "PrimaryStream": "@212/#28",
                        "PrimaryVectorCount": 48,
                        "SharedPrimaryStream": True,
                        "ExtraStream": "@304/#57",
                        "ExtraVectorCount": 20,
                        "ExtraPayloadRemainder": 0,
                        "Mesh34NormalStream": "@220/#53",
                        "Mesh34NormalVectorCount": 30,
                        "Mesh34AttributeSetCount": 0,
                        "Mesh34UvStreamCount": 0,
                    },
                    {
                        "Pair": "mesh329extra04de",
                        "Id": "04de901531a091ab",
                        "PrimaryStream": "@212/#28",
                        "PrimaryVectorCount": 37,
                        "SharedPrimaryStream": True,
                        "ExtraStream": "@304/#57",
                        "ExtraVectorCount": 23,
                        "ExtraPayloadRemainder": 4,
                        "Mesh34NormalStream": "@220/#53",
                        "Mesh34NormalVectorCount": 35,
                        "Mesh34AttributeSetCount": 0,
                        "Mesh34UvStreamCount": 0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    json_path, md_path = post50_mesh34_complete_binding_negative_proof(source_path, out_dir)
    report = json.loads(json_path.read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)
    print("  PASS: mesh34 complete-binding negative proof schema validation")
    check("markdown exists", md_path.exists(), True)
    check("schema version", report["SchemaVersion"], "post50-mesh34-complete-binding-negative-proof/v1")
    check("candidate only", report["CandidateOnly"], True)
    check("example count", report["Aggregate"]["ExampleCount"], 2)
    check("complete binding count", report["Aggregate"]["CompleteGeometryBindingCount"], 0)
    check("negative binding count", report["Aggregate"]["NegativeBindingCount"], 2)
    check("all negative binding", report["Aggregate"]["AllRowsNegativeBinding"], True)
    check("parser/export locked", report["ParserExportPromotionAllowed"], False)
    check_contains("blocker", "\n".join(report["Aggregate"]["Blockers"]), "mesh34-complete-geometry-binding-not-proven")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
