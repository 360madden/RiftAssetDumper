"""Synthetic and negative controls for RA-2i index-stream inventory."""

from __future__ import annotations

import hashlib
import struct

import pytest

from scripts import audit_nif_index_structure as audit


def words(*values: int) -> bytes:
    return struct.pack(">" + "H" * len(values), *values)


def synthetic_source() -> tuple[bytes, dict, str]:
    indices = words(0, 1, 2, 0, 2, 3)
    positions = b"\0" * (4 * 3 * 4)  # Four finite ROR1 float3 records.
    index = struct.pack("<I", len(indices)) + b"\0" * 25 + indices
    position = struct.pack("<I", len(positions)) + b"\0" * 25 + positions
    source = index + position
    header = {
        "Header": {
            "Blocks": [
                {"Index": 20, "TypeName": "NiDataStream", "DataOffset": 0, "Size": len(index)},
                {"Index": 21, "TypeName": "NiDataStream", "DataOffset": len(index), "Size": len(position)},
            ]
        }
    }
    return source, header, hashlib.sha256(source).hexdigest()


def test_exact_six_words_for_one_grid_cell() -> None:
    result = audit.inventory_words(words(0, 1, 2, 0, 2, 3), 4, endian="big")
    assert result["wordCount"] == 6
    assert result["exactSixWordsPerGridCell"] is True
    assert result["localGridFixedTriplets"] == 2
    assert result["duplicateFixedTriplets"] == 0
    assert result["missingVertexWordCount"] == 0
    assert result["fixedTripletInterpretationQualified"] is False


def test_outlier_and_missing_vertex_are_explicit() -> None:
    result = audit.inventory_words(words(0, 1, 2, 0, 3, 999), 4, endian="big")
    assert result["outOfRangeOccurrences"] == 1
    assert result["outOfRangeWordSamples"] == [{"value": 999, "occurrences": 1}]
    assert result["outOfRangeFixedTriplets"] == 1
    assert result["missingVertexWordCount"] == 0


def test_duplicates_do_not_count_as_valid_local_triplets() -> None:
    result = audit.inventory_words(words(0, 0, 1, 1, 2, 3), 4, endian="big")
    assert result["duplicateFixedTriplets"] == 1
    assert result["localGridFixedTriplets"] == 1


def test_byte_order_is_reported_without_promotion() -> None:
    raw = words(0, 1, 2, 0, 2, 3)
    big = audit.inventory_words(raw, 4, endian="big")
    little = audit.inventory_words(raw, 4, endian="little")
    assert big["outOfRangeOccurrences"] == 0
    assert little["outOfRangeOccurrences"] > 0
    assert little["fixedTripletInterpretationQualified"] is False


@pytest.mark.parametrize(
    ("raw", "vertices", "endian"),
    [
        (b"\0" * 5, 4, "big"),
        (b"\0" * (audit.MAX_INDEX_BYTES + 2), 4, "big"),
        (words(0, 1, 2), 5, "big"),
        (words(0, 1, 2), True, "big"),
        (words(0, 1, 2), 4, "middle"),
    ],
)
def test_malformed_index_inputs_fail_closed(raw: bytes, vertices: int, endian: str) -> None:
    with pytest.raises(ValueError):
        audit.inventory_words(raw, vertices, endian=endian)


def test_source_hash_and_semantics_are_not_promoted() -> None:
    source, header, digest = synthetic_source()
    result = audit.analyze_source(source, header, digest)
    assert result["sourceNifSha256"] == digest
    assert result["sourceGridVertexCount"] == 4
    assert result["byteOrderProfiles"][0]["localGridFixedTriplets"] == 2
    assert result["selectedNativeByteOrder"] is None
    assert result["originalTopologyQualified"] is False
    assert result["worldPlacementQualified"] is False
    assert result["riftworldModelReady"] is False


def test_source_hash_tampering_is_refused() -> None:
    source, header, digest = synthetic_source()
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        audit.analyze_source(source + b"!", header, digest)
    with pytest.raises(ValueError, match="64 hex"):
        audit.analyze_source(source, header, "wrong")


def test_broken_stream_bounds_are_refused() -> None:
    source, header, digest = synthetic_source()
    header["Header"]["Blocks"][0]["Size"] += 1
    with pytest.raises(ValueError, match="declared data length mismatch"):
        audit.analyze_source(source, header, digest)
