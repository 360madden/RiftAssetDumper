"""RA-2j: compare bounded INDEX triplet phases without claiming native faces.

Offsets are counted in 16-bit words from the already SHA-qualified body.
A cleaner grouping is still not evidence of primitive topology or winding.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import audit_nif_index_structure as structure  # noqa: E402
from scripts import audit_nif_terrain_grid as grid  # noqa: E402
from scripts.audit_live_archive_samples import write_report  # noqa: E402
from scripts.audit_nif_native_index_candidates import score_uint16_hypothesis  # noqa: E402

SCHEMA = "ra2j-index-triplet-phase-controls/1"


def compare_phases(
    raw: bytes,
    positions: list[tuple[float, ...]],
    normals: list[tuple[float, ...]],
) -> list[dict]:
    """Score six bounded phase/byte-order hypotheses, never selecting one."""
    if not 12 <= len(raw) <= structure.MAX_INDEX_BYTES or len(raw) % 6:
        raise ValueError("INDEX body must be bounded and have complete six-byte groups")
    count = len(positions)
    side = math.isqrt(count)
    if not 4 <= count <= grid.MAX_VERTICES or side * side != count or len(normals) != count:
        raise ValueError("source positions and normals must share one square grid")
    if any(len(p) != 3 for p in positions + normals):
        raise ValueError("source position/normal vectors must have three components")

    profiles = []
    for endian in ("big", "little"):
        for phase in (0, 1, 2):
            trailing = (len(raw) // 2 - phase) % 3
            start = phase * 2
            stop = len(raw) - trailing * 2
            sample = raw[start:stop]
            if len(sample) < 6:
                raise ValueError("phase produces no complete triplet")
            score = score_uint16_hypothesis(sample, positions, normals, endian=endian, primitive="list")
            counts = score["counts"]
            contradictions = (
                counts["outOfRangeTriangles"]
                + counts["degenerateIndexTriangles"]
                + counts["zeroAreaTriangles"]
                + counts["zeroNormalTriangles"]
                + counts["negativeNormalAgreement"]
                + counts["scoredNormalTriangles"]
                - counts["highNormalAgreement"]
            )
            profiles.append(
                {
                    "hypothesis": f"{endian}-u16-disjoint-triplets-word-offset-{phase}",
                    "endian": endian,
                    "leadingWordsOmitted": phase,
                    "trailingWordsOmitted": trailing,
                    "candidateTripletCount": score["candidateTriangleGroups"],
                    "counts": counts,
                    "phaseControlVerdict": "contradicted" if contradictions else "no-observed-contradiction",
                    "originalTopologyQualified": False,
                }
            )
    return profiles


def analyze_source(
    source: bytes,
    header: dict,
    expected_nif_sha256: str,
    *,
    expected_index_sha256: str | None = None,
) -> dict:
    """Read only bounded source NiDataStreams after the RA-2i source hash gate."""
    baseline = structure.analyze_source(source, header, expected_nif_sha256)
    index_sha = baseline["indexStreamSha256"]
    if expected_index_sha256 is not None:
        if not structure.SHA256.fullmatch(expected_index_sha256):
            raise ValueError("expected INDEX SHA-256 must be 64 hex characters")
        if expected_index_sha256.lower() != index_sha:
            raise ValueError("INDEX stream SHA-256 mismatch")
    blocks = {block["Index"]: block for block in header["Header"]["Blocks"]}
    raw = grid._stream_body(source, blocks, 20)
    positions = grid.decode_ror1_vectors(grid._stream_body(source, blocks, 21), 3)
    normals = grid.decode_ror1_vectors(grid._stream_body(source, blocks, 22), 3)
    return {
        "schema": SCHEMA,
        "sourceNifSha256": baseline["sourceNifSha256"],
        "indexStreamSha256": index_sha,
        "sourceGridVertexCount": baseline["sourceGridVertexCount"],
        "candidatePhaseProfiles": compare_phases(raw, positions, normals),
        "selectedNativeByteOrder": None,
        "selectedTripletWordOffset": None,
        "originalTopologyQualified": False,
        "worldPlacementQualified": False,
        "riftworldModelReady": False,
        "qualification": (
            "Six offset/byte-order diagnostics; dropped edge words, invalid references, "
            "normal agreement and primitive encoding remain unresolved. No native faces."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nif", type=Path, required=True)
    parser.add_argument("--nif-header-report", type=Path, required=True)
    parser.add_argument("--expected-nif-sha256", required=True)
    parser.add_argument("--expected-index-sha256")
    parser.add_argument("--out", type=Path, default=ROOT / "Exports/ra2j/index-phase-controls.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.nif.is_file() or not 100 <= args.nif.stat().st_size <= grid.MAX_SOURCE_BYTES:
            raise ValueError("NIF source unavailable or outside bounded byte range")
        source = args.nif.read_bytes()
        header = json.loads(args.nif_header_report.read_text(encoding="utf-8-sig"))
        report = analyze_source(
            source, header, args.expected_nif_sha256, expected_index_sha256=args.expected_index_sha256
        )
        if args.dry_run:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            out = args.out if args.out.is_absolute() else ROOT / args.out
            write_report(out, report)
            print(f"RA-2j: six phase controls -> {out}; original topology unqualified")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"RA-2j ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
