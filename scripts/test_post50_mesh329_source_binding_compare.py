"""Validate the post-50 meshSize=329 source-binding compare report."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import jsonschema

sys.path.insert(0, ".")

from scripts.rift_workflow_reports import post50_mesh329_source_binding_compare

failed = 0


def check(desc: str, actual: object, expected: object) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} expected={expected!r} actual={actual!r}")
        failed += 1


def check_contains(desc: str, values: list[object], expected: object) -> None:
    global failed
    if expected in values:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} missing={expected!r} actual={values!r}")
        failed += 1


def stream(offset: int, block: int, payload: int, role: str) -> dict[str, object]:
    return {
        "MeshPayloadOffset": offset,
        "TargetBlockIndex": block,
        "Payload": payload,
        "Role": role,
    }


def probe_row(
    pair: str,
    id_value: str,
    mesh_block: int,
    primary_payload: int,
    extra_payload: int,
    normal_payload: int,
) -> dict[str, object]:
    if mesh_block == 7:
        position_streams = [stream(212, 28, primary_payload, "position-float3-ror1-lead")]
        normal_streams = [stream(220, 29, primary_payload, "normal-float3-ror1-lead")]
        uv_streams = [stream(304, 33, (primary_payload // 12) * 8, "uv-float2-ror1-lead")]
        attribute_count = 1
        attribute_summary = f"v={primary_payload // 12} p@212/#28 n@220/#29 uv@304/#33"
    else:
        position_streams = [
            stream(212, 28, primary_payload, "position-float3-ror1-lead"),
            stream(304, 57, extra_payload, "position-float3-ror1-lead"),
        ]
        normal_streams = [stream(220, 53, normal_payload, "normal-float3-ror1-lead")]
        uv_streams = []
        attribute_count = 0
        attribute_summary = "none"

    return {
        "Pair": pair,
        "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
        "Id": id_value,
        "MeshBlock": mesh_block,
        "MeshSize": 329,
        "PositionStreams": position_streams,
        "NormalStreams": normal_streams,
        "UvStreams": uv_streams,
        "SideStreams": [stream(296, 32, max(primary_payload // 3, 0), "u32-repeated-pattern-body")],
        "AttributeSetCount": attribute_count,
        "AttributeSummary": attribute_summary,
        "ProbePath": f"Exports/probe-nif-mesh-{id_value}-mesh{mesh_block}.json",
    }


examples = [
    ("mesh329extra0364", "0364ea142bc00ce7", 576, 240, 360),
    ("mesh329extra04de", "04de901531a091ab", 444, 280, 420),
    ("mesh329extra066f", "066fa520a8ce62e3", 264, 96, 144),
]

source_report = {
    "Schema": "position-source-sibling-extra-position-report/v1",
    "CandidateOnly": True,
    "PairSummaries": [
        {
            "Pair": pair,
            "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
            "Id": id_value,
            "SharedPrimaryPosition": f"block#28 payload={primary_payload} offsets=@212/@212",
            "Mesh34ExtraPosition": f"@304/#57 payload={extra_payload} position-float3-ror1-lead",
            "Mesh7Summary": "mesh#7 complete attribute set",
            "Mesh34Summary": "mesh#34 attr=none; pos=@212/#28 | @304/#57; uv=none",
            "Decision": "candidate-only source-binding oddity",
        }
        for pair, id_value, primary_payload, extra_payload, _normal_payload in examples
    ],
    "ProbeRows": [
        probe_row(pair, id_value, mesh_block, primary_payload, extra_payload, normal_payload)
        for pair, id_value, primary_payload, extra_payload, normal_payload in examples
        for mesh_block in (7, 34)
    ],
    "Interpretation": "candidate-only",
}

schema = json.loads(
    Path("docs/schemas/post50-mesh329-source-binding-compare-v1.schema.json").read_text(encoding="utf-8")
)

with tempfile.TemporaryDirectory() as tmp:
    out_dir = Path(tmp)
    source_path = out_dir / "position-source-sibling-extra-position-report.json"
    source_path.write_text(json.dumps(source_report), encoding="utf-8")

    json_path, md_path = post50_mesh329_source_binding_compare(source_path, out_dir)
    report = json.loads(json_path.read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)
    print("  PASS: compare report schema validation")

    check("schema version", report["SchemaVersion"], "post50-mesh329-source-binding-compare/v1")
    check("candidate only", report["CandidateOnly"], True)
    check("mesh size", report["MeshSize"], 329)
    check("row count", len(report["ComparisonRows"]), 3)
    check("primary stream offset", report["PrimaryStream"]["MeshPayloadOffset"], 212)
    check("extra stream block", report["ExtraStream"]["TargetBlockIndex"], 57)
    check("aggregate example count", report["Aggregate"]["ExampleCount"], 3)
    check("primary payloads", report["Aggregate"]["PrimaryPayloads"], [264, 444, 576])
    check("extra payloads", report["Aggregate"]["ExtraPayloads"], [96, 240, 280])
    check("extra payload remainders", report["Aggregate"]["ExtraPayloadRemainders"], [0, 4])
    check("mesh#34 lacks complete attribute set", report["Aggregate"]["AllMesh34LacksCompleteAttributeSet"], True)
    check("parser/export promotion locked", report["ParserExportPromotionAllowed"], False)
    check_contains(
        "promotion blocker",
        report["Aggregate"]["Blockers"],
        "parser-export-promotion-not-allowed",
    )

    row_04de = next(row for row in report["ComparisonRows"] if row["Id"] == "04de901531a091ab")
    check("04de extra vector count floors", row_04de["ExtraVectorCount"], 23)
    check("04de extra remainder", row_04de["ExtraPayloadRemainder"], 4)
    check("markdown exists", md_path.exists(), True)

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
