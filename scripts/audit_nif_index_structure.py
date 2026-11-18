"""RA-2i: inventory an observed NiMesh INDEX stream without inventing triangles.

The two qualified terrain NIFs bind NiDataStream #20 to the semantic INDEX.
This tool inventories 16-bit interpretations and fixed-triplet negative
controls; it does not select a byte order or qualify original topology.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import audit_nif_terrain_grid as grid  # noqa: E402
from scripts.audit_live_archive_samples import write_report  # noqa: E402

SCHEMA = "ra2i-index-stream-structure/1"
MAX_INDEX_BYTES = 2 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")


def inventory_words(raw: bytes, vertex_count: int, *, endian: str) -> dict:
    """Count source index words; fixed triplets are a diagnostic, not faces."""
    if endian not in ("big", "little"):
        raise ValueError("unknown index byte order")
    if not 6 <= len(raw) <= MAX_INDEX_BYTES or len(raw) % 2:
        raise ValueError("index byte length outside even bounded range")
    if type(vertex_count) is not int or not 4 <= vertex_count <= grid.MAX_VERTICES:
        raise ValueError("invalid source vertex count")
    side = math.isqrt(vertex_count)
    if side * side != vertex_count:
        raise ValueError("source positions are not a square grid")

    values = [item[0] for item in struct.iter_unpack(">H" if endian == "big" else "<H", raw)]
    counts = Counter(values)
    missing = [value for value in range(vertex_count) if value not in counts]
    outliers = sorted((value, count) for value, count in counts.items() if value >= vertex_count)

    bad_groups = 0
    duplicate_groups = 0
    local_groups = 0
    for start in range(0, len(values) - 2, 3):
        tri = values[start : start + 3]
        if max(tri) >= vertex_count:
            bad_groups += 1
            continue
        if len(set(tri)) != 3:
            duplicate_groups += 1
            continue
        rowcol = [divmod(value, side) for value in tri]
        if all(abs(rowcol[i][axis] - rowcol[j][axis]) <= 1 for i, j in ((0, 1), (1, 2), (0, 2)) for axis in (0, 1)):
            local_groups += 1

    return {
        "endianHypothesis": endian,
        "wordCount": len(values),
        "minWord": min(values),
        "maxWord": max(values),
        "distinctWords": len(counts),
        "gridSide": side,
        "gridCellCount": (side - 1) ** 2,
        "exactSixWordsPerGridCell": len(values) == 6 * (side - 1) ** 2,
        "outOfRangeOccurrences": sum(count for _, count in outliers),
        "outOfRangeDistinctCount": len(outliers),
        "outOfRangeWordSamples": [{"value": value, "occurrences": count} for value, count in outliers[:32]],
        "missingVertexWordCount": len(missing),
        "missingVertexWordSamples": missing[:32],
        "fixedTripletGroups": len(values) // 3,
        "trailingWordsAfterFixedTriplets": len(values) % 3,
        "outOfRangeFixedTriplets": bad_groups,
        "duplicateFixedTriplets": duplicate_groups,
        "localGridFixedTriplets": local_groups,
        "fixedTripletInterpretationQualified": False,
    }


def analyze_source(source: bytes, header: dict, expected_nif_sha256: str) -> dict:
    """Use existing bounded NIF stream extraction, preserving hash identity."""
    if not SHA256.fullmatch(expected_nif_sha256):
        raise ValueError("expected NIF SHA-256 must be 64 hex characters")
    actual_sha = hashlib.sha256(source).hexdigest()
    if actual_sha != expected_nif_sha256.lower():
        raise ValueError("source NIF SHA-256 mismatch")
    blocks = {item["Index"]: item for item in header["Header"]["Blocks"]}
    index_body = grid._stream_body(source, blocks, 20)
    position_body = grid._stream_body(source, blocks, 21)
    vertex_count = len(grid.decode_ror1_vectors(position_body, 3))
    return {
        "schema": SCHEMA,
        "sourceNifSha256": actual_sha,
        "indexStreamBlock": 20,
        "indexStreamSha256": hashlib.sha256(index_body).hexdigest(),
        "sourceGridVertexCount": vertex_count,
        "byteOrderProfiles": [inventory_words(index_body, vertex_count, endian=endian) for endian in ("big", "little")],
        "selectedNativeByteOrder": None,
        "originalTopologyQualified": False,
        "worldPlacementQualified": False,
        "riftworldModelReady": False,
        "qualification": (
            "Source-hash-bound word distributions and fixed-triplet negative controls only; "
            "INDEX stream encoding, triangle ordering, winding, and world frame remain unproven."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nif", type=Path, required=True)
    parser.add_argument("--nif-header-report", type=Path, required=True)
    parser.add_argument("--expected-nif-sha256", required=True)
    parser.add_argument("--expected-index-sha256", default=None)
    parser.add_argument("--out", type=Path, default=ROOT / "Exports/ra2i/index-structure.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.nif.is_file() or not 100 <= args.nif.stat().st_size <= grid.MAX_SOURCE_BYTES:
            raise ValueError("NIF source unavailable or outside bounded byte range")
        source = args.nif.read_bytes()
        header = json.loads(args.nif_header_report.read_text(encoding="utf-8-sig"))
        report = analyze_source(source, header, args.expected_nif_sha256)
        if args.expected_index_sha256:
            expected = args.expected_index_sha256
            if not SHA256.fullmatch(expected) or report["indexStreamSha256"] != expected.lower():
                raise ValueError("INDEX stream SHA-256 mismatch")
        if args.dry_run:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            out = args.out if args.out.is_absolute() else ROOT / args.out
            write_report(out, report)
            print(f"RA-2i: index word inventory -> {out}; original topology unqualified")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"RA-2i ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
