"""RA-2f: reject unsupported native index interpretations against verified source normals.

Tests direct uint16 LE/BE lists and continuous strips on a hash-bound NIF.
No original triangles, OBJ, RiftWorld model, placement or navigation is emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import audit_nif_terrain_grid as grid  # noqa: E402
from scripts.audit_live_archive_samples import write_report  # noqa: E402

SCHEMA = "ra2f-native-index-hypotheses/1"


def score_uint16_hypothesis(
    raw: bytes,
    positions: list[tuple[float, ...]],
    normals: list[tuple[float, ...]],
    *,
    endian: str,
    primitive: str,
) -> dict:
    """Score one unqualified direct native index interpretation."""
    if endian not in ("big", "little") or primitive not in ("list", "continuous-strip"):
        raise ValueError("unsupported native index hypothesis")
    if len(raw) < 6 or len(raw) % 6 or len(raw) > 2 * 1024 * 1024:
        raise ValueError("index stream must be bounded and triplet-aligned")
    side = math.isqrt(len(positions))
    if side * side != len(positions) or len(normals) != len(positions):
        raise ValueError("positions and normals must form one matching source grid")
    indices = [item[0] for item in struct.iter_unpack(">H" if endian == "big" else "<H", raw)]
    if primitive == "list":
        triangles = ((indices[i:i + 3], i // 3) for i in range(0, len(indices), 3))
        groups = len(indices) // 3
    else:
        triangles = ((indices[i:i + 3], i) for i in range(len(indices) - 2))
        groups = len(indices) - 2
    counts: Counter[str] = Counter()
    for tri, ordinal in triangles:
        if max(tri) >= len(positions):
            counts["outOfRangeTriangles"] += 1
            continue
        if len(set(tri)) < 3:
            counts["degenerateIndexTriangles"] += 1
            continue
        coords = [divmod(v, side) for v in tri]
        max_jump = max(
            max(abs(coords[i][k] - coords[j][k]) for k in range(2))
            for i, j in ((0, 1), (1, 2), (0, 2))
        )
        if max_jump <= 1:
            counts["localGridNeighborTriangles"] += 1
        p = [positions[i] for i in tri]
        ab = [p[1][k] - p[0][k] for k in range(3)]
        ac = [p[2][k] - p[0][k] for k in range(3)]
        cross = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        magnitude = math.sqrt(sum(v * v for v in cross))
        if magnitude < 1e-8:
            counts["zeroAreaTriangles"] += 1
            continue
        avg = [sum(normals[i][k] for i in tri) / 3 for k in range(3)]
        length = math.sqrt(sum(v * v for v in avg))
        if length == 0:
            counts["zeroNormalTriangles"] += 1
            continue
        dot = sum(cross[k] * avg[k] for k in range(3)) / (magnitude * length)
        if primitive == "continuous-strip" and ordinal % 2:
            dot = -dot
        counts["highNormalAgreement"] += int(dot > 0.9)
        counts["negativeNormalAgreement"] += int(dot < 0)
        counts["scoredNormalTriangles"] += 1

    complete = {key: counts[key] for key in (
        "outOfRangeTriangles", "degenerateIndexTriangles", "localGridNeighborTriangles",
        "zeroAreaTriangles", "zeroNormalTriangles", "highNormalAgreement",
        "negativeNormalAgreement", "scoredNormalTriangles",
    )}
    return {
        "hypothesis": f"{endian}-endian-u16-{primitive}",
        "sourceIndexValueCount": len(indices),
        "candidateTriangleGroups": groups,
        "minIndex": min(indices),
        "maxIndex": max(indices),
        "distinctIndexValues": len(set(indices)),
        "counts": complete,
        "directTopologyGate": (
            "rejected"
            if complete["outOfRangeTriangles"] > 0 or complete["degenerateIndexTriangles"] > 0
            or complete["negativeNormalAgreement"] > 0
            else "candidate-only"
        ),
        "originalTopologyQualified": False,
    }


def analyze_source(source: bytes, header: dict, sha256: str) -> dict:
    baseline = grid.analyze(source, header, sha256)
    blocks = {b["Index"]: b for b in header["Header"]["Blocks"]}
    source_index = grid._stream_body(source, blocks, 20)
    positions = grid.decode_ror1_vectors(grid._stream_body(source, blocks, 21), 3)
    normals = grid.decode_ror1_vectors(grid._stream_body(source, blocks, 22), 3)
    candidates = [
        score_uint16_hypothesis(source_index, positions, normals, endian=endian, primitive=primitive)
        for endian in ("big", "little")
        for primitive in ("list", "continuous-strip")
    ]
    return {
        "schema": SCHEMA,
        "sourceNifSha256": sha256,
        "streamIndexBlock": 20,
        "streamBodySha256": hashlib.sha256(source_index).hexdigest(),
        "sourceGridVertices": baseline["gridEvidence"]["vertexCount"],
        "evaluatedHypotheses": candidates,
        "originalTopologyQualified": False,
        "sourceWorldPlacementQualified": False,
        "riftworldModelReady": False,
        "qualification": (
            "Four naive native-index interpretations tested against already-validated "
            "source grid/normals; not a proof of actual NIF primitive ordering. "
            "Unknown topology remains unavailable."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--nif", type=Path, required=True)
    p.add_argument("--nif-header-report", type=Path, required=True)
    p.add_argument("--expected-nif-sha256", required=True)
    p.add_argument("--out", type=Path, default=ROOT / "Exports/ra2f/index-hypotheses.json")
    args = p.parse_args(argv)
    try:
        if not args.nif.is_file() or not 100 <= args.nif.stat().st_size <= grid.MAX_SOURCE_BYTES:
            raise ValueError("NIF source missing or oversized")
        header = json.loads(args.nif_header_report.read_text(encoding="utf-8-sig"))
        source = args.nif.read_bytes()
        report = analyze_source(source, header, args.expected_nif_sha256)
        target = args.out if args.out.is_absolute() else ROOT / args.out
        write_report(target, report)
        results = ", ".join(
            f"{r['hypothesis']}={r['directTopologyGate']}"
            for r in report["evaluatedHypotheses"]
        )
        print(f"RA-2f: {results}; original topology unqualified -> {target}")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"RA-2f ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
