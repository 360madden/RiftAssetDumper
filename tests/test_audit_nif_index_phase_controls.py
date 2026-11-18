"""Synthetic/negative RA-2j triplet phase controls."""

from __future__ import annotations

import hashlib
import struct

import pytest

from scripts import audit_nif_index_phase_controls as audit


def words(*values: int) -> bytes:
    return struct.pack(">" + "H" * len(values), *values)


def ror1_float(value: float) -> bytes:
    packed = struct.pack("<f", value)
    return packed[1:] + packed[:1]


def vector_stream(vectors: list[tuple[float, float, float]]) -> bytes:
    return b"".join(ror1_float(value) for vector in vectors for value in vector)


def synthetic_source(
    index_words: tuple[int, ...] = (0, 2, 3, 0, 3, 1, 0, 2, 3, 0, 3, 1),
    *,
    normal_count: int = 4,
) -> tuple[bytes, dict, str]:
    positions = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 0.0, 2.0), (2.0, 0.0, 2.0)]
    normals = [(0.0, 1.0, 0.0)] * normal_count
    bodies = (words(*index_words), vector_stream(positions), vector_stream(normals))
    source = b""
    blocks = []
    for index, body in zip((20, 21, 22), bodies, strict=True):
        block = struct.pack("<I", len(body)) + b"\0" * 25 + body
        blocks.append({"Index": index, "TypeName": "NiDataStream", "DataOffset": len(source), "Size": len(block)})
        source += block
    return source, {"Header": {"Blocks": blocks}}, hashlib.sha256(source).hexdigest()


POSITIONS = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 0.0, 2.0), (2.0, 0.0, 2.0)]
NORMALS = [(0.0, 1.0, 0.0)] * 4


def test_all_three_phases_both_byte_orders_no_auto_selection() -> None:
    result = audit.compare_phases(words(0, 2, 3, 0, 3, 1, 0, 2, 3, 0, 3, 1), POSITIONS, NORMALS)
    assert [(p["endian"], p["leadingWordsOmitted"]) for p in result] == [
        ("big", 0),
        ("big", 1),
        ("big", 2),
        ("little", 0),
        ("little", 1),
        ("little", 2),
    ]
    assert all(p["originalTopologyQualified"] is False for p in result)
    assert [(p["trailingWordsOmitted"], p["candidateTripletCount"]) for p in result[:3]] == [(0, 4), (2, 3), (1, 3)]


def test_phase_two_reduces_duplicates_but_does_not_prove_faces() -> None:
    raw = words(2, 1, 0, 1, 2, 1, 2, 3, 3, 2, 0, 2)
    p0, _, p2, *_ = audit.compare_phases(raw, POSITIONS, NORMALS)
    assert p0["counts"]["degenerateIndexTriangles"] == 3
    assert p2["counts"]["degenerateIndexTriangles"] == 0
    assert p2["originalTopologyQualified"] is False


def test_noncontradictory_synthetic_triangles_are_still_not_native_proof() -> None:
    raw = words(0, 2, 3, 0, 3, 1, 0, 2, 3, 0, 3, 1)
    first = audit.compare_phases(raw, POSITIONS, NORMALS)[0]
    assert first["phaseControlVerdict"] == "no-observed-contradiction"
    assert first["originalTopologyQualified"] is False


@pytest.mark.parametrize("raw", [b"", b"\0" * 9, b"\0" * 10, b"\0" * (audit.structure.MAX_INDEX_BYTES + 6)])
def test_invalid_stream_sizes_fail_closed(raw: bytes) -> None:
    with pytest.raises(ValueError, match="bounded"):
        audit.compare_phases(raw, POSITIONS, NORMALS)


def test_malformed_source_grids_and_normals_fail_closed() -> None:
    raw = words(0, 2, 3, 0, 3, 1)
    with pytest.raises(ValueError, match="square grid"):
        audit.compare_phases(raw, POSITIONS[:3], NORMALS[:3])
    with pytest.raises(ValueError, match="square grid"):
        audit.compare_phases(raw, POSITIONS, NORMALS[:3])
    with pytest.raises(ValueError, match="three components"):
        audit.compare_phases(raw, [(0.0, 0.0)] * 4, NORMALS)


def test_source_and_index_hashes_are_enforced() -> None:
    source, header, digest = synthetic_source()
    report = audit.analyze_source(source, header, digest)
    assert len(report["candidatePhaseProfiles"]) == 6
    assert report["selectedNativeByteOrder"] is None
    assert report["selectedTripletWordOffset"] is None
    assert report["originalTopologyQualified"] is False
    assert report["worldPlacementQualified"] is False
    assert report["riftworldModelReady"] is False
    assert report["sourceGridVertexCount"] == 4
    assert (
        audit.analyze_source(source, header, digest, expected_index_sha256=report["indexStreamSha256"].upper())
        == report
    )
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        audit.analyze_source(source + b"!", header, digest)
    with pytest.raises(ValueError, match="INDEX stream SHA-256 mismatch"):
        audit.analyze_source(source, header, digest, expected_index_sha256="0" * 64)
    with pytest.raises(ValueError, match="64 hex"):
        audit.analyze_source(source, header, digest, expected_index_sha256="wrong")


def test_source_stream_corruption_and_normal_count_refused() -> None:
    source, header, digest = synthetic_source(normal_count=3)
    with pytest.raises(ValueError, match="square grid"):
        audit.analyze_source(source, header, digest)
    source, header, digest = synthetic_source()
    header["Header"]["Blocks"][0]["Size"] += 1
    with pytest.raises(ValueError, match="declared data length mismatch"):
        audit.analyze_source(source, header, digest)
