"""Validate the post-50 meshSize=329 family proof report."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import jsonschema

sys.path.insert(0, ".")

from scripts.rift_workflow_reports import post50_mesh329_family_proof_report

failed = 0


def check(desc: str, actual: object, expected: object) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} expected={expected!r} actual={actual!r}")
        failed += 1


def stream(payload: int) -> dict[str, Any]:
    return {
        "MeshPayloadOffset": 212,
        "TargetBlockIndex": 28,
        "DeclaredPayloadBytes": payload,
        "DataStreamUsage": "1",
        "DataStreamAccess": "19",
        "GhidraStyleLayoutValid": True,
        "StringValue": "POSITION",
        "RoleStats": {"PrimaryRole": "position-float3-ror1-lead"},
    }


def sample(id_prefix: str, mesh_block: int, payload: int) -> dict[str, Any]:
    return {
        "ArchiveName": "assets.050",
        "EntryIndex": 1000 + mesh_block,
        "IdPrefix": id_prefix,
        "MeshBlockIndex": mesh_block,
        "MeshSize": 329,
        "Stream": stream(payload),
    }


def sibling_row(id_prefix: str, payload: int) -> dict[str, Any]:
    return {
        "Pattern": (f"id={id_prefix}|target=#28|payload={payload}:usage=1 access=19|role=position-float3-ror1-lead"),
        "IdPrefix": id_prefix,
        "TargetBlockIndex": 28,
        "DeclaredPayloadBytes": payload,
        "DataStreamUsage": "1",
        "DataStreamAccess": "19",
        "Role": "position-float3-ror1-lead",
        "Count": 2,
        "NifPayloads": 1,
        "DistinctMeshBlocks": 2,
        "MeshBlockIndices": [7, 34],
        "MeshSizes": [{"Size": 329, "Count": 2}],
        "MeshPayloadOffsets": [212],
        "Samples": [sample(id_prefix, 7, payload), sample(id_prefix, 34, payload)],
    }


inventory = {
    "TopPositionSourceSiblings": [
        sibling_row("0364ea142bc00ce7", 576),
        sibling_row("066fa520a8ce62e3", 264),
        {
            "IdPrefix": "ignored0000000000",
            "TargetBlockIndex": 21,
            "DeclaredPayloadBytes": 288,
            "DataStreamUsage": "1",
            "DataStreamAccess": "19",
            "Role": "position-float3-ror1-lead",
            "Count": 2,
            "DistinctMeshBlocks": 2,
            "MeshBlockIndices": [7, 27],
            "MeshSizes": [{"Size": 305, "Count": 2}],
            "MeshPayloadOffsets": [188],
            "Samples": [],
        },
    ]
}

family_report = {
    "Schema": "position-source-sibling-family-report/v1",
    "CandidateOnly": True,
    "SourceReport": "Exports/nif-mesh-binding-inventory.json",
    "Families": [
        {
            "MeshSize": 329,
            "MeshBlocks": "mesh#7, mesh#34",
            "MeshPayloadOffsets": "stream@212",
            "EvidenceGroups": 2,
            "TotalStreamLinks": 4,
            "DistinctIds": 2,
            "TargetBlocks": "block#28",
            "PayloadBytes": "264, 576",
            "RepresentativeIds": "0364ea142bc00ce7, 066fa520a8ce62e3",
            "UsageAccess": "1/19",
            "Roles": "position-float3-ror1-lead",
            "Decision": "repeated meshSize=329 source-binding family; candidate-only probe queue",
        }
    ],
    "GuardedFamilies": [
        {
            "MeshSize": 329,
            "MeshBlocks": "mesh#7, mesh#34",
            "MeshPayloadOffsets": "stream@212",
            "MinimumEvidenceGroups": 2,
            "ExpectedTargetBlocks": "block#28",
        }
    ],
    "Interpretation": "candidate-only",
}

schema = json.loads(Path("docs/schemas/post50-mesh329-family-proof-v1.schema.json").read_text(encoding="utf-8"))

with tempfile.TemporaryDirectory() as tmp:
    out_dir = Path(tmp)
    inventory_path = out_dir / "nif-mesh-binding-inventory.json"
    family_report_path = out_dir / "position-source-sibling-family-report.json"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    family_report_path.write_text(json.dumps(family_report), encoding="utf-8")

    json_path, md_path = post50_mesh329_family_proof_report(inventory_path, out_dir, family_report_path)
    report = json.loads(json_path.read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)
    print("  PASS: family proof report schema validation")

    check("schema version", report["SchemaVersion"], "post50-mesh329-family-proof/v1")
    check("candidate only", report["CandidateOnly"], True)
    check("mesh size", report["MeshSize"], 329)
    check("proof row count", len(report["ProofRows"]), 2)
    check("evidence groups", report["Aggregate"]["EvidenceGroups"], 2)
    check("total stream links", report["Aggregate"]["TotalStreamLinks"], 4)
    check("distinct ids", report["Aggregate"]["DistinctIds"], 2)
    check("payload bytes", report["Aggregate"]["PayloadBytes"], [264, 576])
    check("family report evidence match", report["Aggregate"]["FamilyReportConsistency"]["EvidenceGroupsMatch"], True)
    check("parser/export promotion locked", report["ParserExportPromotionAllowed"], False)
    check("markdown exists", md_path.exists(), True)

actual_path = Path("Exports/post50-mesh329-family-proof.json")
if actual_path.exists():
    actual = json.loads(actual_path.read_text(encoding="utf-8"))
    jsonschema.validate(actual, schema)
    print("  PASS: actual ignored family proof report validates against schema")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
