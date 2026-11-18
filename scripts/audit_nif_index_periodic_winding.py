"""RA-2k: held-out periodic winding controls on candidate terrain triplets.

A source-observed eight-group sign motif is only a hypothesis. Window-local
polarity is fitted on a short prefix and scored on untouched remainder groups.
No candidate sign, primitive or native face topology is ever promoted.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import audit_nif_index_structure as structure  # noqa: E402
from scripts import audit_nif_terrain_grid as grid  # noqa: E402
from scripts.audit_live_archive_samples import write_report  # noqa: E402

SCHEMA = "ra2k-index-periodic-winding-controls/1"
WORD_OFFSET = 2
TRAINING_GROUPS = 64
STRONG_DOT = 0.9
WINDOW_SIZES = (128, 512, 2048)
TEMPLATES: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("uniform-sign-control", (1,)),
    ("alternating-sign-control", (1, -1)),
    ("observed-eight-group-candidate", (1, 1, 1, -1, -1, -1, -1, 1)),
)


def candidate_signs(
    raw: bytes,
    positions: list[tuple[float, ...]],
    normals: list[tuple[float, ...]],
) -> tuple[list[int], dict[str, int]]:
    """Yield +1/-1 strong normal agreement, or 0 for invalid/ambiguous groups."""
    if not 12 <= len(raw) <= structure.MAX_INDEX_BYTES or len(raw) % 6:
        raise ValueError("INDEX body must be bounded and triplet-aligned")
    count = len(positions)
    side = math.isqrt(count)
    if not 4 <= count <= grid.MAX_VERTICES or side * side != count or len(normals) != count:
        raise ValueError("positions/normals must share a square source grid")
    if any(len(v) != 3 or not all(math.isfinite(x) for x in v) for v in positions + normals):
        raise ValueError("positions/normals must be finite float3 vectors")

    values = [item[0] for item in struct.iter_unpack(">H", raw)]
    signs: list[int] = []
    counts = {"outOfRange": 0, "duplicate": 0, "zeroAreaOrNormal": 0, "weakNormalAgreement": 0}
    for i in range(WORD_OFFSET, len(values) - 2, 3):
        a, b, c = values[i : i + 3]
        if max(a, b, c) >= count:
            counts["outOfRange"] += 1
            signs.append(0)
            continue
        if len({a, b, c}) != 3:
            counts["duplicate"] += 1
            signs.append(0)
            continue
        pa, pb, pc = positions[a], positions[b], positions[c]
        ab = [pb[k] - pa[k] for k in range(3)]
        ac = [pc[k] - pa[k] for k in range(3)]
        cross = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        normal = [(normals[a][k] + normals[b][k] + normals[c][k]) / 3 for k in range(3)]
        scale = math.sqrt(sum(x * x for x in cross)) * math.sqrt(sum(x * x for x in normal))
        if scale < 1e-10:
            counts["zeroAreaOrNormal"] += 1
            signs.append(0)
            continue
        dot = sum(cross[k] * normal[k] for k in range(3)) / scale
        if dot > STRONG_DOT:
            signs.append(1)
        elif dot < -STRONG_DOT:
            signs.append(-1)
        else:
            counts["weakNormalAgreement"] += 1
            signs.append(0)
    return signs, counts


def score_window_model(signs: list[int], *, window_groups: int, template: tuple[int, ...]) -> dict:
    """Fit only a polarity bit on a window prefix; score the held-out suffix."""
    if not isinstance(window_groups, int) or isinstance(window_groups, bool) or not 8 <= window_groups <= 2048:
        raise ValueError("window must contain 8..2048 groups")
    if window_groups % 8:
        raise ValueError("window size must be a multiple of eight groups")
    if not template or any(type(x) is not int or x not in (-1, 1) for x in template):
        raise ValueError("model sign template must contain only +1/-1")
    if any(type(x) is not int or x not in (-1, 0, 1) for x in signs):
        raise ValueError("candidate signs must be -1/0/+1")

    windows = []
    accuracy = []
    total_scored = total_matched = 0
    for start in range(0, len(signs), window_groups):
        stop = min(len(signs), start + window_groups)
        training = min(TRAINING_GROUPS, (stop - start) // 2)
        trained = [i for i in range(start, start + training) if signs[i]]
        if trained:
            matches = sum(signs[i] == template[i % len(template)] for i in trained)
            polarity = 1 if matches * 2 >= len(trained) else -1
        else:
            polarity = None

        held_out = [i for i in range(start + training, stop) if signs[i]]
        matched = sum(signs[i] == polarity * template[i % len(template)] for i in held_out) if polarity else 0
        ratio = matched / len(held_out) if held_out and polarity else None
        if ratio is not None:
            accuracy.append(ratio)
            total_scored += len(held_out)
            total_matched += matched
        windows.append(
            {
                "startCandidateTriplet": start,
                "stopCandidateTripletExclusive": stop,
                "trainingStrongGroups": len(trained),
                "fittedPolarity": polarity,
                "heldOutStrongGroups": len(held_out),
                "heldOutMatches": matched,
                "heldOutAgreement": round(ratio, 6) if ratio is not None else None,
            }
        )
    return {
        "template": list(template),
        "windowTriplets": window_groups,
        "trainingPrefixLimit": TRAINING_GROUPS,
        "windowCount": len(windows),
        "scoredWindows": len(accuracy),
        "unscoredWindows": len(windows) - len(accuracy),
        "heldOutStrongGroups": total_scored,
        "heldOutMatches": total_matched,
        "weightedHeldOutAgreement": round(total_matched / total_scored, 6) if total_scored else None,
        "meanWindowHeldOutAgreement": round(statistics.mean(accuracy), 6) if accuracy else None,
        "medianWindowHeldOutAgreement": round(statistics.median(accuracy), 6) if accuracy else None,
        "minWindowHeldOutAgreement": round(min(accuracy), 6) if accuracy else None,
        "windowsAtLeast90Percent": sum(x >= 0.9 for x in accuracy),
        "windowsAtLeast98Percent": sum(x >= 0.98 for x in accuracy),
        "windows": windows,
        "originalTopologyQualified": False,
    }


def analyze_source(
    source: bytes,
    header: dict,
    expected_nif_sha256: str,
    *,
    expected_index_sha256: str | None = None,
    window_groups: int = 128,
) -> dict:
    """Require source SHA-256; preserve candidate-only classification."""
    baseline = structure.analyze_source(source, header, expected_nif_sha256)
    if expected_index_sha256 is not None:
        if not structure.SHA256.fullmatch(expected_index_sha256):
            raise ValueError("expected INDEX SHA-256 must be 64 hex characters")
        if baseline["indexStreamSha256"] != expected_index_sha256.lower():
            raise ValueError("INDEX stream SHA-256 mismatch")
    blocks = {block["Index"]: block for block in header["Header"]["Blocks"]}
    raw = grid._stream_body(source, blocks, 20)
    positions = grid.decode_ror1_vectors(grid._stream_body(source, blocks, 21), 3)
    normals = grid.decode_ror1_vectors(grid._stream_body(source, blocks, 22), 3)
    signs, rejected = candidate_signs(raw, positions, normals)
    models = []
    candidate_windows = []
    for label, template in TEMPLATES:
        score = score_window_model(signs, window_groups=window_groups, template=template)
        if label == "observed-eight-group-candidate":
            candidate_windows = score.pop("windows")
        else:
            score.pop("windows")
        models.append({"model": label, **score})
    return {
        "schema": SCHEMA,
        "sourceNifSha256": baseline["sourceNifSha256"],
        "indexStreamSha256": baseline["indexStreamSha256"],
        "sourceGridVertexCount": baseline["sourceGridVertexCount"],
        "diagnosticByteOrder": "big",
        "diagnosticLeadingWordsOmitted": WORD_OFFSET,
        "diagnosticTrailingWordsOmitted": (len(raw) // 2 - WORD_OFFSET) % 3,
        "candidateTripletCount": len(signs),
        "strongPositiveGroups": signs.count(1),
        "strongNegativeGroups": signs.count(-1),
        "candidateRejectionCounts": rejected,
        "modelControls": models,
        "observedEightGroupWindows": candidate_windows,
        "selectedPrimitive": None,
        "selectedNativeByteOrder": None,
        "selectedNativeWinding": None,
        "originalTopologyQualified": False,
        "worldPlacementQualified": False,
        "riftworldModelReady": False,
        "qualification": (
            "Held-out sign-template scores are source-local diagnostics only. "
            "An observed period and fitted per-window polarity cannot prove primitive order, "
            "explain edge words/outliers, or authorize native faces."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nif", type=Path, required=True)
    parser.add_argument("--nif-header-report", type=Path, required=True)
    parser.add_argument("--expected-nif-sha256", required=True)
    parser.add_argument("--expected-index-sha256")
    parser.add_argument("--window-triplets", type=int, choices=WINDOW_SIZES, default=128)
    parser.add_argument("--out", type=Path, default=ROOT / "Exports/ra2k/index-periodic-controls.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.nif.is_file() or not 100 <= args.nif.stat().st_size <= grid.MAX_SOURCE_BYTES:
            raise ValueError("NIF source unavailable or outside bounded byte range")
        source = args.nif.read_bytes()
        header = json.loads(args.nif_header_report.read_text(encoding="utf-8-sig"))
        report = analyze_source(
            source,
            header,
            args.expected_nif_sha256,
            expected_index_sha256=args.expected_index_sha256,
            window_groups=args.window_triplets,
        )
        if args.dry_run:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            out = args.out if args.out.is_absolute() else ROOT / args.out
            write_report(out, report)
            print(f"RA-2k: bounded periodic candidate controls -> {out}; original topology unqualified")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"RA-2k ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
