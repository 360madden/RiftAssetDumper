"""Unit tests for phase1_m12_304_magic_analysis (fixture dir only; no Exports required)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

from scripts.phase1_m12_304_magic_analysis import phase1_m12_304_magic_analysis

failed = 0


def check(desc: str, actual: object, expected: object) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} expected={expected!r} actual={actual!r}")
        failed += 1


def _stream(offset: int, body_first16: str, role: str = "position-float3-ror1-lead") -> dict:
    return {
        "MeshPayloadOffset": offset,
        "TargetBlockIndex": 57 if offset == 304 else 28,
        "DeclaredPayloadBytes": 136 if offset == 304 else 552,
        "BodyFirst16": body_first16,
        "RoleStats": {"PrimaryRole": role, "Confidence": 75},
    }


def _probe(asset_id: str, body304: str, body212: str) -> dict:
    return {
        "Source": {"IdPrefix": asset_id},
        "Meshes": [
            {
                "MeshBlockIndex": 34,
                "MeshSize": 329,
                "AttributeSets": [],
                "Streams": [
                    _stream(212, body212),
                    _stream(304, body304),
                ],
            }
        ],
    }


def run() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        matrix = {
            "Schema": "329-family-attribute-role-matrix/v1",
            "IDsCovered": ["aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"],
            "MatrixRows": [],
        }
        (root / "mesh329-family-attribute-role-matrix.json").write_text(
            json.dumps(matrix), encoding="utf-8"
        )
        (root / "probe-nif-mesh-aaaaaaaaaaaaaaaa-mesh34.json").write_text(
            json.dumps(
                _probe(
                    "aaaaaaaaaaaaaaaa",
                    "022bc245761141fdb72ac22794114182",
                    "f18141842c09421ee776c2a8a7834124",
                )
            ),
            encoding="utf-8",
        )
        (root / "probe-nif-mesh-bbbbbbbbbbbbbbbb-mesh34.json").write_text(
            json.dumps(
                _probe(
                    "bbbbbbbbbbbbbbbb",
                    "a92cc2fd1bcf402ca52cc2da04cf4036",
                    "875741890b1342981e81c2dff257413c",
                )
            ),
            encoding="utf-8",
        )

        json_path, md_path = phase1_m12_304_magic_analysis(root)
        report = json.loads(json_path.read_text(encoding="utf-8"))

        check("schema", report.get("Schema"), "phase1-m1.2-@304-magic-analysis/v1")
        check("candidate only", report.get("CandidateOnly"), True)
        check("processed count", report["Aggregates"]["IDsProcessed"], 2)
        check("022bc2 count", report["Aggregates"]["Prefix022bc2Count"], 1)
        check("c2 positions 2-5", report["Aggregates"]["C2InBytePositions2To5Count"], 2)
        check("shared 4-byte prefix", report["Aggregates"]["SharedPrefixAt304"]["SharedPrefixBytes4"], 0)
        check("json exists", json_path.name, "phase1-m1.2-@304-magic-analysis.json")
        check("md exists", md_path.exists(), True)

        per = {row["Id"]: row for row in report["PerID"]}
        check("aaaa 022bc2", per["aaaaaaaaaaaaaaaa"]["HasPrefix022bc2"], True)
        check("bbbb 022bc2", per["bbbbbbbbbbbbbbbb"]["HasPrefix022bc2"], False)
        check("aaaa c2 pos", per["aaaaaaaaaaaaaaaa"]["C2InBytePositions2To5"], True)
        check("bbbb c2 pos", per["bbbbbbbbbbbbbbbb"]["C2InBytePositions2To5"], True)
        check(
            "aaaa 212 contrast",
            per["aaaaaaaaaaaaaaaa"]["StreamAt212"]["BodyFirst16"],
            "f18141842c09421ee776c2a8a7834124",
        )

    if failed:
        print(f"\n{failed} test(s) failed.")
        raise SystemExit(1)
    print("\nAll phase1_m12_304_magic_analysis tests passed.")


if __name__ == "__main__":
    run()