"""RA-2f synthetic negative gates for native-index interpretation candidates."""

from __future__ import annotations

import struct

import pytest

from scripts import audit_nif_native_index_candidates as audit

POSITIONS = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0),
             (0.0, 0.0, 2.0), (2.0, 0.0, 2.0)]
NORMALS = [(0.0, 1.0, 0.0)] * 4


def packed(values: list[int], endian: str = "big") -> bytes:
    prefix = ">" if endian == "big" else "<"
    return struct.pack(prefix + "H" * len(values), *values)


def test_valid_synthetic_list_stays_candidate_only() -> None:
    raw = packed([3, 1, 0, 2, 3, 0])
    result = audit.score_uint16_hypothesis(
        raw, POSITIONS, NORMALS, endian="big", primitive="list",
    )
    assert result["candidateTriangleGroups"] == 2
    assert result["maxIndex"] == 3
    assert result["counts"]["outOfRangeTriangles"] == 0
    assert result["counts"]["degenerateIndexTriangles"] == 0
    assert result["counts"]["highNormalAgreement"] == 2
    assert result["directTopologyGate"] == "candidate-only"
    assert result["originalTopologyQualified"] is False


def test_out_of_bounds_and_degenerate_indices_fail() -> None:
    for indexes, failing in (
        ([3, 1, 65535, 2, 3, 0], "outOfRangeTriangles"),
        ([3, 3, 0, 2, 3, 0], "degenerateIndexTriangles"),
    ):
        result = audit.score_uint16_hypothesis(
            packed(indexes), POSITIONS, NORMALS, endian="big", primitive="list",
        )
        assert result["counts"][failing] == 1
        assert result["directTopologyGate"] == "rejected"
        assert result["originalTopologyQualified"] is False


def test_wrong_winding_rejects_against_normals() -> None:
    result = audit.score_uint16_hypothesis(
        packed([3, 0, 1, 2, 0, 3]), POSITIONS, NORMALS,
        endian="big", primitive="list",
    )
    assert result["counts"]["negativeNormalAgreement"] == 2
    assert result["directTopologyGate"] == "rejected"


def test_big_endian_bytes_misinterpreted_as_little_fail_bounds() -> None:
    raw = packed([3, 1, 0, 2, 3, 0])
    result = audit.score_uint16_hypothesis(
        raw, POSITIONS, NORMALS, endian="little", primitive="list",
    )
    assert result["maxIndex"] > len(POSITIONS)
    assert result["counts"]["outOfRangeTriangles"] > 0
    assert result["directTopologyGate"] == "rejected"


def test_strip_does_not_promote_even_when_values_are_valid() -> None:
    result = audit.score_uint16_hypothesis(
        packed([3, 1, 0, 2, 3, 0]), POSITIONS, NORMALS,
        endian="big", primitive="continuous-strip",
    )
    assert result["candidateTriangleGroups"] == 4
    assert result["originalTopologyQualified"] is False


@pytest.mark.parametrize("raw", [b"", b"\x00\x00", b"\x00" * 7, b"\x00" * 10])
def test_rejects_unaligned_or_empty_candidate_stream(raw: bytes) -> None:
    with pytest.raises(ValueError, match="bounded and triplet-aligned"):
        audit.score_uint16_hypothesis(
            raw, POSITIONS, NORMALS, endian="big", primitive="list",
        )


def test_rejects_invalid_endian_primitive_and_grid_mismatch() -> None:
    payload = packed([3, 1, 0, 2, 3, 0])
    for endian, primitive in (("native", "list"), ("big", "fan")):
        with pytest.raises(ValueError, match="unsupported"):
            audit.score_uint16_hypothesis(
                payload, POSITIONS, NORMALS, endian=endian, primitive=primitive,
            )
    with pytest.raises(ValueError, match="matching source grid"):
        audit.score_uint16_hypothesis(
            payload, POSITIONS[:3], NORMALS[:3], endian="big", primitive="list",
        )


def test_scoring_is_stable_and_does_not_mutate_inputs() -> None:
    payload = packed([3, 1, 0, 2, 3, 0])
    original_positions, original_normals = POSITIONS[:], NORMALS[:]
    a = audit.score_uint16_hypothesis(
        payload, POSITIONS, NORMALS, endian="big", primitive="list",
    )
    b = audit.score_uint16_hypothesis(
        payload, POSITIONS, NORMALS, endian="big", primitive="list",
    )
    assert a == b
    assert POSITIONS == original_positions
    assert NORMALS == original_normals
