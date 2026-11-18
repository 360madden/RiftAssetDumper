"""Negative and held-out synthetic controls for RA-2k periodic winding."""

from __future__ import annotations

import hashlib
import struct

import pytest

from scripts import audit_nif_index_periodic_winding as audit


def pack_words(*values: int) -> bytes:
    return struct.pack(">" + "H" * len(values), *values)


def source_fixture(*, normal_count: int = 4) -> tuple[bytes, dict, str]:
    positions = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 0.0, 2.0), (2.0, 0.0, 2.0)]
    normals = [(0.0, 1.0, 0.0)] * normal_count
    raw = pack_words(2, 1, 0, 1, 2, 1, 2, 3, 3, 2, 0, 2)

    def vectors(rows: list[tuple[float, float, float]]) -> bytes:
        return b"".join((lambda b: b[1:] + b[:1])(struct.pack("<f", x)) for row in rows for x in row)

    source = b""
    blocks = []
    for index, body in zip((20, 21, 22), (raw, vectors(positions), vectors(normals)), strict=True):
        block = struct.pack("<I", len(body)) + b"\0" * 25 + body
        blocks.append({"Index": index, "TypeName": "NiDataStream", "DataOffset": len(source), "Size": len(block)})
        source += block
    return source, {"Header": {"Blocks": blocks}}, hashlib.sha256(source).hexdigest()


PATTERN = (1, 1, 1, -1, -1, -1, -1, 1)


def test_period_eight_predicts_held_out_groups() -> None:
    signs = [PATTERN[i % 8] for i in range(256)]
    model = audit.score_window_model(signs, window_groups=128, template=PATTERN)
    assert model["windowCount"] == 2
    assert model["heldOutStrongGroups"] == 128
    assert model["heldOutMatches"] == 128
    assert model["windowsAtLeast90Percent"] == 2
    assert model["originalTopologyQualified"] is False
    assert audit.score_window_model(signs, window_groups=128, template=(1,))["weightedHeldOutAgreement"] == 0.5


def test_window_local_inversion_is_fitted_only_on_training_prefix() -> None:
    signs = [PATTERN[i % 8] for i in range(128)] + [-PATTERN[i % 8] for i in range(128, 256)]
    model = audit.score_window_model(signs, window_groups=128, template=PATTERN)
    assert [w["fittedPolarity"] for w in model["windows"]] == [1, -1]
    assert model["weightedHeldOutAgreement"] == 1


def test_unseen_midwindow_flip_fails_holdout() -> None:
    signs = [PATTERN[i % 8] for i in range(64)] + [-PATTERN[i % 8] for i in range(64, 128)]
    model = audit.score_window_model(signs, window_groups=128, template=PATTERN)
    assert model["windowsAtLeast90Percent"] == 0
    assert model["weightedHeldOutAgreement"] == 0


def test_constant_sign_negative_control_rejects_period_eight() -> None:
    signs = [1] * 128
    observed = audit.score_window_model(signs, window_groups=128, template=PATTERN)
    uniform = audit.score_window_model(signs, window_groups=128, template=(1,))
    assert observed["weightedHeldOutAgreement"] == 0.5
    assert uniform["weightedHeldOutAgreement"] == 1


def test_unknown_signs_cannot_create_fictitious_passes() -> None:
    score = audit.score_window_model([0] * 128, window_groups=128, template=PATTERN)
    assert score["unscoredWindows"] == 1
    assert score["weightedHeldOutAgreement"] is None
    assert score["windowsAtLeast90Percent"] == 0
    assert score["windows"][0]["fittedPolarity"] is None


@pytest.mark.parametrize(
    ("signs", "window", "template"),
    [
        ([1] * 8, 0, PATTERN),
        ([1] * 8, 9, PATTERN),
        ([1] * 8, 2056, PATTERN),
        ([1] * 8, True, PATTERN),
        ([1] * 8, 8, (1, 0)),
        ([1] * 8, 8, ()),
        ([1, 2, -1], 8, PATTERN),
        ([True, 0, 1], 8, PATTERN),
    ],
)
def test_invalid_window_or_labels_fail_closed(signs: list[int], window: int, template: tuple[int, ...]) -> None:
    with pytest.raises(ValueError):
        audit.score_window_model(signs, window_groups=window, template=template)


POSITIONS = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 0.0, 2.0), (2.0, 0.0, 2.0)]
NORMALS = [(0.0, 1.0, 0.0)] * 4


def test_candidate_signs_only_diagnose_shifted_source() -> None:
    raw = pack_words(2, 1, 0, 1, 2, 1, 2, 3, 3, 2, 0, 2)
    signs, discarded = audit.candidate_signs(raw, POSITIONS, NORMALS)
    assert len(signs) == 3
    assert discarded["outOfRange"] == 0
    assert discarded["duplicate"] == 0
    assert set(signs) <= {-1, 0, 1}


def test_out_of_range_candidate_cannot_become_strong_sign() -> None:
    raw = pack_words(2, 1, 0, 1, 2, 1, 2, 999, 3, 2, 0, 2)
    signs, discarded = audit.candidate_signs(raw, POSITIONS, NORMALS)
    assert discarded["outOfRange"] == 1
    assert signs[1] == 0


@pytest.mark.parametrize(
    ("raw", "positions", "normals"),
    [
        (b"\0" * 11, POSITIONS, NORMALS),
        (b"\0" * 13, POSITIONS, NORMALS),
        (b"\0" * (audit.structure.MAX_INDEX_BYTES + 6), POSITIONS, NORMALS),
        (pack_words(*([0] * 6)), POSITIONS[:3], NORMALS[:3]),
        (pack_words(*([0] * 6)), POSITIONS, NORMALS[:3]),
        (pack_words(*([0] * 6)), [(0.0, 0.0)] * 4, NORMALS),
    ],
)
def test_candidate_input_malformed_fails_closed(
    raw: bytes, positions: list[tuple[float, ...]], normals: list[tuple[float, ...]]
) -> None:
    with pytest.raises(ValueError):
        audit.candidate_signs(raw, positions, normals)


def test_source_report_is_explicitly_nonpromotional() -> None:
    source, header, digest = source_fixture()
    report = audit.analyze_source(source, header, digest)
    assert report["diagnosticLeadingWordsOmitted"] == 2
    assert report["selectedPrimitive"] is None
    assert report["selectedNativeByteOrder"] is None
    assert report["selectedNativeWinding"] is None
    assert report["originalTopologyQualified"] is False
    assert report["riftworldModelReady"] is False
    assert len(report["modelControls"]) == 3
    assert report["candidateTripletCount"] == 3
    assert len(report["observedEightGroupWindows"]) == 1


def test_source_hash_and_stream_corruption_refused() -> None:
    source, header, digest = source_fixture()
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        audit.analyze_source(source + b"!", header, digest)
    with pytest.raises(ValueError, match="64 hex"):
        audit.analyze_source(source, header, digest, expected_index_sha256="bad")
    with pytest.raises(ValueError, match="INDEX stream SHA-256 mismatch"):
        audit.analyze_source(source, header, digest, expected_index_sha256="0" * 64)
    source, header, digest = source_fixture(normal_count=3)
    with pytest.raises(ValueError, match="square source grid"):
        audit.analyze_source(source, header, digest)


def test_truncated_stream_refused() -> None:
    source, header, digest = source_fixture()
    header["Header"]["Blocks"][0]["Size"] += 1
    with pytest.raises(ValueError, match="declared data length mismatch"):
        audit.analyze_source(source, header, digest)
