"""Smoke tests for rift_workflow_reports.py summaries."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

import jsonschema

sys.path.insert(0, ".")

from scripts.rift_workflow_reports import (
    ghidra_attribute_candidate_report,
    ghidra_pairing_review_report,
    position_source_sibling_probe_report,
    show_report_summary,
)

failed = 0


def check_contains(desc: str, text: str, expected: str) -> None:
    global failed
    if expected in text:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc}  missing={expected!r}")
        failed += 1


def write_sibling_probe_fixture(
    temp_dir: Path,
    asset_id: str,
    mesh_block: int,
    *,
    mesh_size: int,
    vertex_count: int,
    topology: str,
    position_offset: int,
    position_block: int,
    position_payload: int,
    normal_offset: int,
    normal_block: int,
    normal_payload: int,
    uv_offset: int,
    uv_block: int,
    uv_payload: int,
) -> Path:
    path = temp_dir / f"probe-nif-mesh-{asset_id}-mesh{mesh_block}.json"
    attr = {
        "MeshSize": mesh_size,
        "VertexCount": vertex_count,
        "Topology": {
            "PrimaryTopology": topology,
            "Confidence": 75,
        },
        "PositionMeshPayloadOffset": position_offset,
        "PositionBlockIndex": position_block,
        "PositionDeclaredPayloadBytes": position_payload,
        "PositionDataStreamUsage": 1,
        "PositionDataStreamAccess": 19,
        "PositionRole": "position-float3-ror1-lead",
        "NormalMeshPayloadOffset": normal_offset,
        "NormalBlockIndex": normal_block,
        "NormalDeclaredPayloadBytes": normal_payload,
        "UvMeshPayloadOffset": uv_offset,
        "UvBlockIndex": uv_block,
        "UvDeclaredPayloadBytes": uv_payload,
        "ExtraStreams": [],
    }
    path.write_text(
        json.dumps(
            {
                "Meshes": [
                    {
                        "MeshBlockIndex": mesh_block,
                        "AttributeSets": [attr],
                        "Pairings": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


print("=== MeshBindings summary ===")
with TemporaryDirectory() as temp_dir:
    report_path = Path(temp_dir) / "mesh-bindings.json"
    mesh_bindings_fixture = {
        "NifPayloads": 2,
        "MeshBlocks": 3,
        "CandidateLinks": 4,
        "GhidraStyleLayoutValidStreamBodies": 4,
        "LegacyOffsetShiftedStreamBodies": 4,
        "GhidraRoleDeltaStreamBodies": 1,
        "PairCompatibleMeshes": 0,
        "PairCompatibleLinks": 0,
        "GhidraPairCompatibleMeshes": 1,
        "GhidraPairCompatibleLinks": 2,
        "GhidraSharedPairings": 1,
        "LegacyOnlyPairings": 0,
        "GhidraOnlyPairings": 1,
        "TopGhidraRoleDeltas": [
            {
                "MeshSize": 325,
                "DeclaredPayloadBytes": 96,
                "DataStreamUsage": 1,
                "DataStreamAccess": 19,
                "LegacyRole": "unknown-binary",
                "GhidraRole": "position-float3-ror1-lead",
                "Count": 7,
                "AverageLegacyConfidence": 10,
                "AverageGhidraConfidence": 85,
            }
        ],
        "TopGhidraPairings": [
            {
                "MeshSize": 325,
                "Count": 2,
                "IndexDataStreamUsage": 0,
                "IndexDataStreamAccess": 19,
                "IndexRole": "index-u16le-lead",
                "VertexDataStreamUsage": 1,
                "VertexDataStreamAccess": 19,
                "VertexRole": "normal-float3-lead",
                "VertexCount": 24,
                "MaxIndexObserved": 23,
                "IndexPairCount": 36,
                "TriangleListTriangleCount": 12,
                "TriangleStripWindowCount": 34,
                "MaxIndexCoverageRatio": 1,
            }
        ],
        "TopGhidraPairingComparisons": [
            {
                "Status": "shared",
                "MeshSize": 325,
                "Count": 2,
                "LegacyIndexRole": "index-u16be-strip-lead",
                "LegacyVertexRole": "normal-float3-ror1-lead",
                "GhidraIndexRole": "index-u16le-lead",
                "GhidraVertexRole": "normal-float3-lead",
                "AverageLegacyConfidence": 85,
                "AverageGhidraConfidence": 45,
            }
        ],
        "TopGhidraPairingReviewFindings": [
            {
                "ReviewKind": "vertex-semantic-change",
                "Priority": 2,
                "MeshSize": 301,
                "Count": 7,
                "LegacyIndexRole": "index-u16be-strip-lead",
                "LegacyVertexRole": "uv-float2-ror1-lead",
                "LegacyVertexSemanticClass": "uv",
                "GhidraIndexRole": "index-u16le-lead",
                "GhidraVertexRole": "position-float3-lead",
                "GhidraVertexSemanticClass": "position",
                "AverageLegacyConfidence": 89.75,
                "AverageGhidraConfidence": 54.75,
                "AverageConfidenceDelta": -35,
                "Samples": [
                    {
                        "IdPrefix": "abc123abc123abcd",
                        "MeshBlockIndex": 6,
                        "GhidraPairing": {
                            "IndexRole": "index-u16le-lead",
                            "VertexRole": "position-float3-lead",
                            "IndexMeshPayloadOffset": 292,
                            "IndexBlockIndex": 24,
                            "VertexMeshPayloadOffset": 188,
                            "VertexBlockIndex": 21,
                            "IndexBodyFirst16": "00000100020003000000000000000000",
                            "VertexBodyFirst16": "0000803f000000000000000000000000",
                        },
                        "LegacyPairing": {
                            "IndexRole": "index-u16be-strip-lead",
                            "VertexRole": "uv-float2-ror1-lead",
                            "IndexMeshPayloadOffset": 292,
                            "IndexBlockIndex": 24,
                            "VertexMeshPayloadOffset": 188,
                            "VertexBlockIndex": 21,
                            "IndexBodyFirst16": "00010002000300040000000000000000",
                            "VertexBodyFirst16": "000000000000803f0000000000000000",
                        },
                    }
                ],
            }
        ],
    }
    report_path.write_text(
        json.dumps(mesh_bindings_fixture),
        encoding="utf-8",
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        show_report_summary("MeshBindings", str(report_path))
    text = buffer.getvalue()
    check_contains("summary counts", text, "roleDeltas=1")
    check_contains("ghidra pairing counts", text, "ghidraPairMeshes=1 ghidraPairLinks=2")
    check_contains("pairing overlap counts", text, "sharedPairs=1 legacyOnlyPairs=0 ghidraOnlyPairs=1")
    check_contains("delta heading", text, "Top Ghidra role deltas")
    check_contains("delta role arrow", text, "unknown-binary->position-float3-ror1-lead=7")
    check_contains("delta grouping fields", text, "meshSize=325 payload=96 usage=1 access=19")
    check_contains("ghidra pairing heading", text, "Top Ghidra pairings")
    check_contains("ghidra pairing roles", text, "index-u16le-lead->vertex[usage=1 access=19] normal-float3-lead")
    check_contains("ghidra comparison heading", text, "Top Ghidra pairing comparisons")
    check_contains(
        "ghidra comparison roles",
        text,
        "shared meshSize=325 count=2 legacy=index-u16be-strip-lead->normal-float3-ror1-lead ghidra=index-u16le-lead->normal-float3-lead",
    )
    check_contains("ghidra review heading", text, "Top Ghidra pairing review findings")
    check_contains(
        "ghidra review roles",
        text,
        "vertex-semantic-change p=2 meshSize=301 count=7 legacy=index-u16be-strip-lead->uv-float2-ror1-lead(uv) ghidra=index-u16le-lead->position-float3-lead(position)",
    )

    no_delta_path = Path(temp_dir) / "mesh-bindings-no-deltas.json"
    no_delta_path.write_text(
        json.dumps({"NifPayloads": 1, "MeshBlocks": 1, "CandidateLinks": 1}),
        encoding="utf-8",
    )
    no_delta_buffer = io.StringIO()
    with redirect_stdout(no_delta_buffer):
        show_report_summary("MeshBindings", str(no_delta_path))
    check_contains("missing deltas does not crash", no_delta_buffer.getvalue(), "NIF payloads=1")

    print("=== Ghidra pairing review report ===")
    review_buffer = io.StringIO()
    with redirect_stdout(review_buffer):
        ghidra_pairing_review_report(report_path, temp_dir, take=5)
    review_json = Path(temp_dir) / "ghidra-pairing-review-report.json"
    review_md = Path(temp_dir) / "ghidra-pairing-review-report.md"
    review_report = json.loads(review_json.read_text(encoding="utf-8"))
    check_contains("ghidra review report console", review_buffer.getvalue(), "GhidraPairingReviewReport passed")
    check_contains("ghidra review report candidate-only", str(review_report.get("CandidateOnly")), "True")
    check_contains("ghidra review report finding", json.dumps(review_report), "abc123abc123abcd")
    check_contains("ghidra review markdown", review_md.read_text(encoding="utf-8"), "vertex-semantic-change")
    schema = json.loads(Path("docs/schemas/ghidra-pairing-review-v1.schema.json").read_text(encoding="utf-8"))
    check_contains(
        "ghidra review schema version",
        str(schema["properties"]["SchemaVersion"]["const"]),
        str(review_report["SchemaVersion"]),
    )
    jsonschema.validate(review_report, schema)
    print("  PASS: ghidra review schema validation")

    print("=== Ghidra attribute candidate report ===")
    attr_review_path = Path(temp_dir) / "ghidra-pairing-review-report.json"
    attr_id = "def456def456abcd"
    attr_findings = [
        {
            "Rank": 1,
            "CandidateOnly": True,
            "ReviewKind": "ghidra-only",
            "Count": 2,
            "SampleIdPrefix": attr_id,
            "SampleMeshBlockIndex": 6,
            "SampleIndexOffset": 24,
            "SampleVertexOffset": 188,
            "GhidraRoles": "index-u16le-lead->position-float3-lead",
            "GhidraVertexSemanticClass": "position",
        },
        {
            "Rank": 2,
            "CandidateOnly": True,
            "ReviewKind": "ghidra-only",
            "Count": 2,
            "SampleIdPrefix": attr_id,
            "SampleMeshBlockIndex": 6,
            "SampleIndexOffset": 24,
            "SampleVertexOffset": 196,
            "GhidraRoles": "index-u16le-lead->normal-float3-lead",
            "GhidraVertexSemanticClass": "normal",
        },
        {
            "Rank": 3,
            "CandidateOnly": True,
            "ReviewKind": "ghidra-only",
            "Count": 2,
            "SampleIdPrefix": attr_id,
            "SampleMeshBlockIndex": 6,
            "SampleIndexOffset": 24,
            "SampleVertexOffset": 204,
            "GhidraRoles": "index-u16le-lead->uv-float2-lead",
            "GhidraVertexSemanticClass": "uv",
        },
    ]
    attr_review_path.write_text(
        json.dumps(
            {
                "SchemaVersion": "ghidra-pairing-review/v1",
                "CandidateOnly": True,
                "Findings": attr_findings,
            }
        ),
        encoding="utf-8",
    )
    for finding in attr_findings:
        rank_dir = Path(temp_dir) / "ghidra-review-rank-probes" / f"rank{finding['Rank']:02d}"
        rank_dir.mkdir(parents=True, exist_ok=True)
        role = str(finding["GhidraRoles"]).split("->", 1)[1]
        probe_pairing = {
            "IndexMeshPayloadOffset": 24,
            "VertexMeshPayloadOffset": finding["SampleVertexOffset"],
            "VertexRole": role,
        }
        if role.startswith("position-"):
            probe_pairing["VertexPositionBoundsReview"] = {"PassesBasicReview": True, "MaxExtent": 10.0}
        elif role.startswith("normal-"):
            probe_pairing["VertexNormalVectorReview"] = {"PassesBasicReview": True, "NearUnitVectorRatio": 1.0}
        elif role.startswith("uv-"):
            probe_pairing["VertexUvRangeReview"] = {"PassesBasicReview": True, "UvRangeRatio": 1.0}
        (rank_dir / f"probe-nif-mesh-{attr_id}.json").write_text(
            json.dumps({"Meshes": [{"GhidraPairings": [probe_pairing]}]}),
            encoding="utf-8",
        )

    attr_buffer = io.StringIO()
    with redirect_stdout(attr_buffer):
        ghidra_attribute_candidate_report(attr_review_path, temp_dir)
    attr_json = Path(temp_dir) / "ghidra-attribute-candidate-report.json"
    attr_md = Path(temp_dir) / "ghidra-attribute-candidate-report.md"
    attr_report = json.loads(attr_json.read_text(encoding="utf-8"))
    check_contains("ghidra attribute report console", attr_buffer.getvalue(), "GhidraAttributeCandidateReport passed")
    check_contains("ghidra attribute report candidate-only", str(attr_report.get("CandidateOnly")), "True")
    check_contains("ghidra attribute report complete group", json.dumps(attr_report), "CompletePositionNormalUvCandidate")
    check_contains("ghidra attribute markdown", attr_md.read_text(encoding="utf-8"), "Complete position/normal/UV")
    attr_schema = json.loads(Path("docs/schemas/ghidra-attribute-candidate-v1.schema.json").read_text(encoding="utf-8"))
    check_contains(
        "ghidra attribute schema version",
        str(attr_schema["properties"]["SchemaVersion"]["const"]),
        str(attr_report["SchemaVersion"]),
    )
    check_contains("ghidra attribute schema groups", json.dumps(attr_schema.get("required", [])), "Groups")
    check_contains("ghidra attribute schema completion marker", json.dumps(attr_schema), "CompletePositionNormalUvCandidate")
    jsonschema.validate(attr_report, attr_schema)
    print("  PASS: ghidra attribute schema validation")

print("=== PositionSourceSiblingProbeReport ===")
with TemporaryDirectory() as temp_dir_name:
    temp_dir = Path(temp_dir_name)
    shifted_id = "e3de1077a37d0337"
    repeated_id = "8e01613d7ce9e297"
    shifted_left = write_sibling_probe_fixture(
        temp_dir,
        shifted_id,
        6,
        mesh_size=325,
        vertex_count=71,
        topology="implicit-triangle-strip-or-fan-candidate",
        position_offset=292,
        position_block=24,
        position_payload=852,
        normal_offset=216,
        normal_block=25,
        normal_payload=852,
        uv_offset=300,
        uv_block=29,
        uv_payload=568,
    )
    shifted_right = write_sibling_probe_fixture(
        temp_dir,
        shifted_id,
        30,
        mesh_size=329,
        vertex_count=71,
        topology="implicit-triangle-strip-or-fan-candidate",
        position_offset=296,
        position_block=24,
        position_payload=852,
        normal_offset=220,
        normal_block=44,
        normal_payload=852,
        uv_offset=304,
        uv_block=48,
        uv_payload=568,
    )
    repeated_left = write_sibling_probe_fixture(
        temp_dir,
        repeated_id,
        6,
        mesh_size=329,
        vertex_count=93,
        topology="implicit-triangle-list-candidate",
        position_offset=296,
        position_block=25,
        position_payload=1116,
        normal_offset=220,
        normal_block=26,
        normal_payload=1116,
        uv_offset=304,
        uv_block=30,
        uv_payload=744,
    )
    repeated_right = write_sibling_probe_fixture(
        temp_dir,
        repeated_id,
        31,
        mesh_size=329,
        vertex_count=93,
        topology="implicit-triangle-list-candidate",
        position_offset=296,
        position_block=25,
        position_payload=1116,
        normal_offset=220,
        normal_block=45,
        normal_payload=1116,
        uv_offset=304,
        uv_block=49,
        uv_payload=744,
    )
    probe_specs = [
        {
            "Pair": "e3de325329",
            "PairLabel": "meshSize 325/329 shifted-position sibling",
            "Id": shifted_id,
            "MeshBlock": 6,
            "Path": str(shifted_left),
        },
        {
            "Pair": "e3de325329",
            "PairLabel": "meshSize 325/329 shifted-position sibling",
            "Id": shifted_id,
            "MeshBlock": 30,
            "Path": str(shifted_right),
        },
        {
            "Pair": "8e016329",
            "PairLabel": "meshSize 329 repeated-position sibling",
            "Id": repeated_id,
            "MeshBlock": 6,
            "Path": str(repeated_left),
        },
        {
            "Pair": "8e016329",
            "PairLabel": "meshSize 329 repeated-position sibling",
            "Id": repeated_id,
            "MeshBlock": 31,
            "Path": str(repeated_right),
        },
    ]
    sibling_buffer = io.StringIO()
    with redirect_stdout(sibling_buffer):
        position_source_sibling_probe_report(probe_specs)
    sibling_json = temp_dir / "position-source-sibling-probe-report.json"
    sibling_md = temp_dir / "position-source-sibling-probe-report.md"
    sibling_report = json.loads(sibling_json.read_text(encoding="utf-8"))
    check_contains(
        "sibling probe console",
        sibling_buffer.getvalue(),
        "PositionSourceSiblingProbeReport passed",
    )
    check_contains(
        "sibling probe candidate-only",
        str(sibling_report.get("CandidateOnly")),
        "True",
    )
    check_contains(
        "sibling probe source paths",
        str(len(sibling_report.get("SourceProbes", []))),
        "4",
    )
    check_contains(
        "sibling shifted offset pattern",
        json.dumps(sibling_report),
        "mesh payload offset shifts with mesh-size delta (4)",
    )
    check_contains(
        "sibling repeated offset pattern",
        json.dumps(sibling_report),
        "same mesh payload offset",
    )
    check_contains(
        "sibling markdown probe rows",
        sibling_md.read_text(encoding="utf-8"),
        "## Probe rows",
    )

print("=== MeshProbe Ghidra pairing summary ===")
with TemporaryDirectory() as temp_dir:
    report_path = Path(temp_dir) / "mesh-probe.json"
    report_path.write_text(
        json.dumps(
            {
                "NifVersion": "20.6.0.0",
                "MeshBlockCount": 1,
                "MeshesEmitted": 1,
                "CandidateLinks": 2,
                "Pairings": 0,
                "GhidraPairings": 3,
                "AttributeSets": 0,
                "Meshes": [
                    {
                        "MeshBlockIndex": 6,
                        "MeshSize": 301,
                        "Streams": [],
                        "Pairings": [],
                        "GhidraPairings": [
                            {
                                "CandidateOnly": True,
                                "IndexMeshPayloadOffset": 292,
                                "IndexBlockIndex": 24,
                                "IndexRole": "index-u16le-lead",
                                "IndexMax": 47,
                                "VertexMeshPayloadOffset": 188,
                                "VertexBlockIndex": 21,
                                "VertexRole": "position-float3-lead",
                                "VertexCount": 48,
                                "VertexPositionBoundsReview": {
                                    "PassesBasicReview": True,
                                    "MaxExtent": 12.5,
                                },
                            },
                            {
                                "CandidateOnly": True,
                                "IndexMeshPayloadOffset": 292,
                                "IndexBlockIndex": 24,
                                "IndexRole": "index-u16le-lead",
                                "IndexMax": 47,
                                "VertexMeshPayloadOffset": 196,
                                "VertexBlockIndex": 22,
                                "VertexRole": "normal-float3-lead",
                                "VertexCount": 48,
                                "VertexNormalVectorReview": {
                                    "PassesBasicReview": True,
                                    "NearUnitVectorRatio": 1.0,
                                },
                            },
                            {
                                "CandidateOnly": True,
                                "IndexMeshPayloadOffset": 292,
                                "IndexBlockIndex": 24,
                                "IndexRole": "index-u16le-lead",
                                "IndexMax": 47,
                                "VertexMeshPayloadOffset": 204,
                                "VertexBlockIndex": 23,
                                "VertexRole": "uv-float2-lead",
                                "VertexCount": 48,
                                "VertexUvRangeReview": {
                                    "PassesBasicReview": True,
                                    "UvRangeRatio": 1.0,
                                },
                            }
                        ],
                        "AttributeSets": [],
                        "PayloadWindows": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        show_report_summary("MeshProbe", str(report_path))
    text = buffer.getvalue()
    check_contains("mesh probe ghidra count", text, "ghidraPairings=3")
    check_contains("mesh probe ghidra row", text, "candidateOnly=True index@292/#24 index-u16le-lead max=47")
    check_contains("mesh probe normal review", text, "normalReview=True nearUnit=1.0")
    check_contains("mesh probe uv review", text, "uvReview=True uvRange=1.0")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
