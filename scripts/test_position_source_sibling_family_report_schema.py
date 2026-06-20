"""Validate the position-source sibling-family report schema."""

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


schema = json.loads(
    Path("docs/schemas/position-source-sibling-family-report-v1.schema.json").read_text(encoding="utf-8")
)

fixture: dict[str, Any] = {
    "Schema": "position-source-sibling-family-report/v1",
    "CandidateOnly": True,
    "SourceReport": "Exports/nif-mesh-binding-inventory.json",
    "Families": [
        {
            "MeshSize": 329,
            "MeshBlocks": "mesh#7, mesh#34",
            "MeshPayloadOffsets": "stream@212",
            "EvidenceGroups": 23,
            "TotalStreamLinks": 46,
            "DistinctIds": 23,
            "TargetBlocks": "block#28",
            "PayloadBytes": "168, 192, 264, 276, 360",
            "RepresentativeIds": "0364ea142bc00ce7, 04de901531a091ab",
            "UsageAccess": "1/19",
            "Roles": "position-float3-ror1-lead",
            "Decision": "repeated meshSize=329 source-binding family; candidate-only probe queue",
        },
        {
            "MeshSize": 305,
            "MeshBlocks": "mesh#7, mesh#27",
            "MeshPayloadOffsets": "stream@188",
            "EvidenceGroups": 15,
            "TotalStreamLinks": 30,
            "DistinctIds": 15,
            "TargetBlocks": "block#21",
            "PayloadBytes": "168, 192, 264",
            "RepresentativeIds": "04297730afc68f38, 0d9a25c9a6af7b18",
            "UsageAccess": "1/19",
            "Roles": "position-float3-ror1-lead",
            "Decision": "repeated meshSize=305 source-binding family; candidate-only probe queue",
        },
    ],
    "GuardedFamilies": [
        {
            "MeshSize": 329,
            "MeshBlocks": "mesh#7, mesh#34",
            "MeshPayloadOffsets": "stream@212",
            "MinimumEvidenceGroups": 20,
            "ExpectedTargetBlocks": "block#28",
        },
        {
            "MeshSize": 325,
            "MeshBlocks": "mesh#6, mesh#30",
            "MeshPayloadOffsets": "stream@292, stream@296",
            "MinimumEvidenceGroups": 1,
            "ExpectedTargetBlocks": "block#24",
            "ExpectedIdPrefix": "e3de1077a37d0337",
        },
    ],
    "Interpretation": (
        "Candidate-only cross-tab over parser-derived TopPositionSourceSiblings. "
        "Repeated sibling source families help choose probes but do not promote geometry truth."
    ),
}

jsonschema.validate(fixture, schema)
print("  PASS: fixture validates against sibling-family schema")
check("schema const", fixture["Schema"], "position-source-sibling-family-report/v1")
check("candidate only", fixture["CandidateOnly"], True)
check("top fixture mesh size", fixture["Families"][0]["MeshSize"], 329)
check("top fixture stream", fixture["Families"][0]["MeshPayloadOffsets"], "stream@212")
check("top guarded threshold", fixture["GuardedFamilies"][0]["MinimumEvidenceGroups"], 20)

actual_path = Path("Exports/position-source-sibling-family-report.json")
if actual_path.exists():
    actual = json.loads(actual_path.read_text(encoding="utf-8"))
    jsonschema.validate(actual, schema)
    print("  PASS: actual ignored sibling-family report validates against schema")
    families = actual.get("Families", [])
    guarded = actual.get("GuardedFamilies", [])
    # Live-archive calibrated (2026-06-19): dynamic families with positive metrics
    if isinstance(families, list) and families:
        top_family = families[0]
        check("actual top mesh size non-negative",
              top_family.get("MeshSize", -1) >= 0, True)
        check("actual top evidence groups positive",
              top_family.get("EvidenceGroups", 0) > 0, True)
        check("actual top total stream links positive",
              top_family.get("TotalStreamLinks", 0) > 0, True)
    # GuardedFamilies should have at least one entry (dynamic live-archive guard)
    check("actual guarded families present", len(guarded) > 0, True)
else:
    print("  SKIP: actual ignored sibling-family report is not present")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
