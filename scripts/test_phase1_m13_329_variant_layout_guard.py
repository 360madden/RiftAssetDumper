"""Unit tests for phase1_m13_329_variant_layout_guard (fixture dir only; no Exports required)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

from scripts.rift_workflow_guards import (
    PHASE1_M13_GUARD_JSON,
    PHASE1_M13_MESH34_304_CONF,
    PHASE1_M13_PILOT_IDS,
    PHASE1_M13_PRIMARY_ROLE,
    phase1_m13_329_variant_layout_guard,
)

failed = 0


def check(desc: str, actual: object, expected: object) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} expected={expected!r} actual={actual!r}")
        failed += 1


def _stream_at212() -> dict:
    return {
        "block": 28,
        "payload": 552,
        "role": PHASE1_M13_PRIMARY_ROLE,
        "conf": 75,
        "vectorCount": 46,
    }


def _matrix_row(asset_id: str, mesh_block: int, attr_sets: int, stream304: dict | None) -> dict:
    return {
        "Id": asset_id,
        "MeshBlock": mesh_block,
        "MeshSize": 329,
        "AttributeSetCount": attr_sets,
        "VertexCount": 22 if attr_sets else 0,
        "StreamsAt212": _stream_at212(),
        "StreamsAt220": {"block": 53, "payload": 552, "role": "normal-float3-ror1-lead", "conf": 75, "vectorCount": 46},
        "StreamsAt296": {
            "block": 55,
            "payload": 136,
            "role": "u32-repeated-pattern-body",
            "conf": 60,
            "vectorCount": 34,
        },
        "StreamsAt304": stream304,
        "CandidateOnly": True,
    }


def _pair_row(asset_id: str, mesh7_uv304: bool) -> dict:
    return {
        "Id": asset_id,
        "AttrSetCount7": 1,
        "AttrSetCount34": 0,
        "AttrDelta": 1,
        "Shared212Payload": True,
        "Shared212Block": True,
        "Mesh34_304Role": PHASE1_M13_PRIMARY_ROLE,
        "Mesh34_304Conf": PHASE1_M13_MESH34_304_CONF,
        "Mesh34_304VectorCount": 20,
        "Mesh7HasUV": mesh7_uv304,
        "Mesh34HasUV": False,
        "CandidateOnly": True,
    }


def _build_matrix(ids: list[str]) -> dict:
    rows: list[dict] = []
    pairs: list[dict] = []
    for asset_id in ids:
        rows.append(
            _matrix_row(
                asset_id,
                7,
                1,
                {"block": 33, "payload": 176, "role": "uv-float2-ror1-lead", "conf": 75, "vectorCount": 22},
            )
        )
        rows.append(
            _matrix_row(
                asset_id,
                34,
                0,
                {
                    "block": 57,
                    "payload": 240,
                    "role": PHASE1_M13_PRIMARY_ROLE,
                    "conf": PHASE1_M13_MESH34_304_CONF,
                    "vectorCount": 20,
                },
            )
        )
        pairs.append(_pair_row(asset_id, True))
    return {
        "Schema": "329-family-attribute-role-matrix/v1",
        "CandidateOnly": True,
        "IDsCovered": ids,
        "MatrixRows": rows,
        "PairComparisons": pairs,
    }


def _probe(asset_id: str, mesh_block: int, attr_set_count: int, role304: str, conf304: int) -> dict:
    streams = [
        {
            "MeshPayloadOffset": 212,
            "TargetBlockIndex": 28,
            "DeclaredPayloadBytes": 552,
            "RoleStats": {"PrimaryRole": PHASE1_M13_PRIMARY_ROLE, "Confidence": 75},
        },
    ]
    if mesh_block == 34:
        streams.append(
            {
                "MeshPayloadOffset": 304,
                "TargetBlockIndex": 57,
                "DeclaredPayloadBytes": 240,
                "RoleStats": {"PrimaryRole": role304, "Confidence": conf304},
            }
        )
    return {
        "Source": {"IdPrefix": asset_id},
        "Meshes": [
            {
                "MeshBlockIndex": mesh_block,
                "MeshSize": 329,
                "AttributeSets": [{}] * attr_set_count,
                "Streams": streams,
            }
        ],
    }


def run() -> None:
    pilot = list(PHASE1_M13_PILOT_IDS)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "mesh329-family-attribute-role-matrix.json").write_text(
            json.dumps(_build_matrix(pilot)), encoding="utf-8"
        )
        json_path, md_path = phase1_m13_329_variant_layout_guard(root)
        report = json.loads(json_path.read_text(encoding="utf-8"))

        check("schema", report.get("Schema"), "phase1-m1.3-329-variant-layout-guard/v1")
        check("candidate only", report.get("CandidateOnly"), True)
        check("pilot count", len(report.get("PerID", [])), 3)
        check("all matrix validated", report["Aggregate"]["AllMatrixValidated"], True)
        check("json basename", json_path.name, PHASE1_M13_GUARD_JSON)
        check("md exists", md_path.exists(), True)

        per = {row["Id"]: row for row in report["PerID"]}
        for asset_id in pilot:
            check(f"{asset_id} attr7", per[asset_id]["AttrSetCount7"], 1)
            check(f"{asset_id} attr34", per[asset_id]["AttrSetCount34"], 0)
            check(f"{asset_id} 304 role", per[asset_id]["Mesh34_304Role"], PHASE1_M13_PRIMARY_ROLE)
            check(f"{asset_id} 304 conf", per[asset_id]["Mesh34_304Conf"], PHASE1_M13_MESH34_304_CONF)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        asset_id = pilot[0]
        (root / "mesh329-family-attribute-role-matrix.json").write_text(
            json.dumps(_build_matrix([asset_id])), encoding="utf-8"
        )
        (root / f"probe-nif-mesh-{asset_id}-mesh7.json").write_text(
            json.dumps(_probe(asset_id, 7, 1, "", 0)), encoding="utf-8"
        )
        (root / f"probe-nif-mesh-{asset_id}-mesh34.json").write_text(
            json.dumps(_probe(asset_id, 34, 0, PHASE1_M13_PRIMARY_ROLE, PHASE1_M13_MESH34_304_CONF)),
            encoding="utf-8",
        )
        _, _ = phase1_m13_329_variant_layout_guard(root, pilot_ids=[asset_id])
        report = json.loads((root / PHASE1_M13_GUARD_JSON).read_text(encoding="utf-8"))
        check("probe cross-check", report["Aggregate"]["ProbeCrossCheckCount"], 1)
        check("probe validated flag", report["PerID"][0]["ProbeValidated"], True)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bad = _build_matrix([pilot[0]])
        bad["PairComparisons"][0]["AttrSetCount34"] = 1
        (root / "mesh329-family-attribute-role-matrix.json").write_text(json.dumps(bad), encoding="utf-8")
        try:
            phase1_m13_329_variant_layout_guard(root, pilot_ids=[pilot[0]])
            check("regression raises", False, True)
        except ValueError:
            check("regression raises", True, True)

    if failed:
        print(f"\n{failed} test(s) failed.")
        raise SystemExit(1)
    print("\nAll phase1_m13_329_variant_layout_guard tests passed.")


if __name__ == "__main__":
    run()
