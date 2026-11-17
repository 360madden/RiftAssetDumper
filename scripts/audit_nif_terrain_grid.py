"""RA-2b: source-hash-bound terrain grid/normal/UV analysis without geometry promotion.

Uses the already existing .NET NIF-header report. Tests a narrow five-stream
21-byte-spaced NiMesh reference hypothesis. No OBJ, modelGeometryId, placement,
navigation or collision output; index triplets must pass their own source gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_live_archive_samples import write_report  # noqa: E402

SCHEMA = "ra2b-terrain-grid-evidence/v1"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
STREAM_IDS = (20, 21, 22, 23, 24)
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_VERTICES = 257 * 257


def rotate_right_1_float32(raw4: bytes) -> float:
    """Reassemble one four-byte float using the existing C# ROR1 convention."""
    if len(raw4) != 4:
        raise ValueError("ROR1 float32 requires exactly 4 bytes")
    return struct.unpack("<f", bytes((raw4[3], raw4[0], raw4[1], raw4[2])))[0]


def decode_ror1_vectors(body: bytes, components: int) -> list[tuple[float, ...]]:
    if components not in (2, 3) or not body or len(body) % (components * 4):
        raise ValueError("ROR1 vector body has invalid component or byte count")
    count = len(body) // (components * 4)
    if not 1 <= count <= MAX_VERTICES:
        raise ValueError("ROR1 vector count exceeds bounded grid limit")
    result = [
        tuple(rotate_right_1_float32(body[j + k * 4:j + k * 4 + 4]) for k in range(components))
        for j in range(0, len(body), components * 4)
    ]
    if any(not all(math.isfinite(value) for value in vec) for vec in result):
        raise ValueError("ROR1 vectors include non-finite components")
    return result


def _block_bytes(source: bytes, blocks: dict[int, dict], index: int) -> bytes:
    item = blocks.get(index)
    if not isinstance(item, dict):
        raise ValueError(f"NIF block #{index} is missing from report")
    offset, size = item.get("DataOffset"), item.get("Size")
    if (type(offset) is not int or type(size) is not int
            or offset < 0 or size < 4 or offset + size > len(source)):
        raise ValueError(f"NIF block #{index} has invalid byte bounds")
    return source[offset:offset + size]


def _stream_body(source: bytes, blocks: dict[int, dict], index: int) -> bytes:
    item = blocks.get(index)
    if item is None or not str(item.get("TypeName", "")).startswith("NiDataStream"):
        raise ValueError(f"NIF block #{index} is not a NiDataStream")
    block = _block_bytes(source, blocks, index)
    if len(block) < 29:
        raise ValueError(f"NiDataStream #{index} has truncated metadata")
    declared = struct.unpack_from("<I", block)[0]
    if declared != len(block) - 29:
        raise ValueError(f"NiDataStream #{index} declared data length mismatch")
    return block[29:]


def find_five_stream_references(mesh: bytes) -> list[dict[str, int]]:
    """Find one exact 20..24 sequence at 21-byte intervals; hypothesis only."""
    expected = STREAM_IDS
    stride = 21
    stop = len(mesh) - (len(expected) - 1) * stride - 4 + 1
    matches: list[list[dict[str, int]]] = []
    for start in range(max(0, stop)):
        found = [
            struct.unpack_from("<I", mesh, start + stride * i)[0]
            for i in range(len(expected))
        ]
        if tuple(found) == expected:
            matches.append([
                {"meshPayloadOffset": start + stride * i, "targetBlockIndex": block}
                for i, block in enumerate(expected)
            ])
    if len(matches) != 1:
        raise ValueError(f"expected one five-stream 21-byte reference sequence; found {len(matches)}")
    return matches[0]


def _vsub(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(a[i] - b[i] for i in range(3))


def _cross(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _unit(v: tuple[float, ...]) -> tuple[float, ...]:
    mag = math.sqrt(sum(value * value for value in v))
    if mag < 1e-10:
        raise ValueError("degenerate terrain surface or normal")
    return tuple(value / mag for value in v)


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(a[i] * b[i] for i in range(3))


def inspect_grid(
    positions: list[tuple[float, ...]],
    normals: list[tuple[float, ...]],
    uvs: list[tuple[float, ...]],
) -> dict:
    """Qualify positions/normals/UV correspondence; not original topology."""
    count = len(positions)
    side = math.isqrt(count)
    if not (3 <= side <= 257 and side * side == count == len(normals) == len(uvs)):
        raise ValueError("position/normal/UV vector counts are not one matching square grid")
    if not all(len(v) == 3 for v in positions + normals) or not all(len(v) == 2 for v in uvs):
        raise ValueError("position/normal/UV vector components are incompatible")
    pos_err_x, pos_err_z, uv_err = [], [], []
    normal_lengths = []
    for r in range(side):
        for c in range(side):
            i = r * side + c
            pos_err_x.append(abs(positions[i][0] - c * 2))
            pos_err_z.append(abs(positions[i][2] - r * 2))
            uv_err.extend((abs(uvs[i][0] - c / side), abs(uvs[i][1] - r / side)))
            normal_lengths.append(math.sqrt(_dot(normals[i], normals[i])))
    if max(pos_err_x) > 0.05 or max(pos_err_z) > 0.01 or max(uv_err) > 0.001:
        raise ValueError("grid XYZ/UV alignment is inconsistent with tested source layout")
    if max(abs(length - 1) for length in normal_lengths) > 0.05:
        raise ValueError("stream normals are not approximately unit length")
    dots = []
    for row in range(1, side - 1):
        for col in range(1, side - 1):
            i = row * side + col
            dx = _vsub(positions[i + 1], positions[i - 1])
            dz = _vsub(positions[i + side], positions[i - side])
            dots.append(_dot(_unit(_cross(dz, dx)), _unit(normals[i])))
    if not dots or min(dots) < 0.99 or statistics.fmean(dots) < 0.995:
        raise ValueError("stream normals disagree with independent surface gradients")
    return {
        "side": side,
        "vertexCount": count,
        "cellCountIfRegularGrid": (side - 1) ** 2,
        "positionsXYZMin": [min(p[k] for p in positions) for k in range(3)],
        "positionsXYZMax": [max(p[k] for p in positions) for k in range(3)],
        "maximumGridXError": max(pos_err_x),
        "maximumGridZError": max(pos_err_z),
        "maximumUVAlignmentError": max(uv_err),
        "normalInteriorComparisons": len(dots),
        "minimumSurfaceNormalDot": min(dots),
        "meanSurfaceNormalDot": statistics.fmean(dots),
        "firstPosition": list(positions[0]),
        "firstNormal": list(normals[0]),
        "firstUV": list(uvs[0]),
        "lastPosition": list(positions[-1]),
    }


def inspect_native_indices(body: bytes, vertex_count: int) -> dict:
    """Test the native #20 big-endian uint16 *triplet hypothesis*, not promote it."""
    if len(body) % 6:
        raise ValueError("candidate native index stream is not triangle-triplet aligned")
    indices = [entry[0] for entry in struct.iter_unpack(">H", body)]
    bad = sum(index >= vertex_count for index in indices)
    degenerate = sum(
        len(set(indices[i:i + 3])) < 3
        for i in range(0, len(indices), 3)
        if all(index < vertex_count for index in indices[i:i + 3])
    )
    return {
        "interpretation": "candidate-big-endian-uint16-triangle-triplets",
        "indexCount": len(indices),
        "triangleGroups": len(indices) // 3,
        "maximumIndex": max(indices),
        "outOfRangeReferences": bad,
        "degenerateInRangeTriplets": degenerate,
        "sampleFirst12Indices": indices[:12],
        "originalTopologyQualified": False,
        "promotion": "rejected" if bad or degenerate else "unqualified",
    }


def analyze(source: bytes, header_probe: dict, expected_sha256: str) -> dict:
    if not 100 <= len(source) <= MAX_SOURCE_BYTES or not source.startswith(b"Gamebryo File Format"):
        raise ValueError("missing, oversized, or non-Gamebryo source NIF")
    actual_sha = hashlib.sha256(source).hexdigest()
    if SHA256.fullmatch(expected_sha256) is None or expected_sha256 != actual_sha:
        raise ValueError("source NIF SHA256 does not match the declared immutable source")
    if (not isinstance(header_probe, dict) or
            header_probe.get("Length") != len(source) or
            header_probe.get("Header", {}).get("Warnings") != []):
        raise ValueError("NIF header report disagrees with source or has warnings")
    raw_blocks = header_probe["Header"].get("Blocks")
    if not isinstance(raw_blocks, list):
        raise ValueError("NIF header block list is absent")
    blocks: dict[int, dict] = {}
    for item in raw_blocks:
        if not isinstance(item, dict) or type(item.get("Index")) is not int or item["Index"] in blocks:
            raise ValueError("invalid or duplicate NIF block declaration")
        blocks[item["Index"]] = item
    if blocks.get(2, {}).get("TypeName") != "NiMesh":
        raise ValueError("NIF block #2 is not a NiMesh")
    mesh = _block_bytes(source, blocks, 2)
    refs = find_five_stream_references(mesh)
    bodies = {index: _stream_body(source, blocks, index) for index in STREAM_IDS}
    positions = decode_ror1_vectors(bodies[21], 3)
    normals = decode_ror1_vectors(bodies[22], 3)
    uv = decode_ror1_vectors(bodies[24], 2)
    grid = inspect_grid(positions, normals, uv)
    original_index = inspect_native_indices(bodies[20], grid["vertexCount"])
    return {
        "schema": SCHEMA,
        "sourceNifSha256": actual_sha,
        "sourceKind": "Gamebryo NIF decoded bytes, producer-only",
        "nifMeshBlock": 2,
        "referenceHypothesis": {
            "kind": "five-unverified-21-byte-stride-NiMesh-stream-references",
            "refs": refs,
            "qualification": "raw repeated sequence; general NiMesh descriptor format not independently verified",
        },
        "dataStreams": {
            str(index): {
                "block": index,
                "declaredBodyBytes": len(bodies[index]),
                "bodySha256": hashlib.sha256(bodies[index]).hexdigest(),
                "role": {20: "candidate-index", 21: "validated-grid-position", 22: "validated-grid-normal",
                         23: "unqualified-packed-attribute", 24: "validated-grid-uv"}[index],
            }
            for index in STREAM_IDS
        },
        "gridEvidence": grid,
        "nativeIndexHypothesis": original_index,
        "consumerBoundary": {
            "modelGeometryId": None,
            "sourceNodeTransform": None,
            "sourceWorldPlacement": None,
            "originalSourceTopologyQualified": False,
            "riftworldModelReady": False,
            "riftworldSceneReady": False,
            "collisionOrTraversalQualified": False,
            "qualification": (
                "Position/normal/UV correspondence independently validated; source index topology, "
                "mesh-to-stream descriptor semantics, node transform, world placement and game collision unqualified."
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--nif", type=Path, required=True)
    p.add_argument("--nif-header-report", type=Path, required=True)
    p.add_argument("--expected-nif-sha256", required=True)
    p.add_argument("--out", type=Path, default=ROOT / "Exports/ra2b/terrain-grid-diagnostic.json")
    args = p.parse_args(argv)
    try:
        if not args.nif.is_file() or not 100 <= args.nif.stat().st_size <= MAX_SOURCE_BYTES:
            raise ValueError("bounded source NIF missing or oversized")
        probe = json.loads(args.nif_header_report.read_text(encoding="utf-8-sig"))
        report = analyze(args.nif.read_bytes(), probe, args.expected_nif_sha256)
        dest = args.out if args.out.is_absolute() else ROOT / args.out
        write_report(dest, report)
        print(
            f"RA-2b: grid {report['gridEvidence']['side']}x{report['gridEvidence']['side']}, "
            f"normals dot mean={report['gridEvidence']['meanSurfaceNormalDot']:.7f}, "
            f"native index promotion={report['nativeIndexHypothesis']['promotion']} -> {dest}"
        )
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"RA-2b ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
