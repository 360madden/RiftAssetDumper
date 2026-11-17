"""RA-2b negative controls for source-hash-bound grid and native index evidence."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pytest

from scripts import audit_live_archive_samples as audit
from scripts import audit_nif_terrain_grid as grid


def encode_ror1(value: float) -> bytes:
    """Inverse of C# NifFloatByteTransform.RotateRight1 (synthetic bytes)."""
    packed = struct.pack("<f", value)
    return packed[1:] + packed[:1]


def vec_bytes(vectors: list[tuple[float, ...]]) -> bytes:
    return b"".join(encode_ror1(value) for vector in vectors for value in vector)


def synthetic_nif(side: int = 3) -> tuple[bytes, dict]:
    """Construct synthetic block offsets and valid reference strides; not a game NIF."""
    assert side == 3
    positions = [(float(c * 2), 760.0, float(r * 2)) for r in range(side) for c in range(side)]
    normals = [(0.0, 1.0, 0.0) for _ in positions]
    uvs = [(c / side, r / side) for r in range(side) for c in range(side)]
    # Two triangles per cell; intentionally a test convention, not RIFT topology.
    indices: list[int] = []
    for r in range(side - 1):
        for c in range(side - 1):
            a = r * side + c
            indices.extend((a + side + 1, a + 1, a, a + side, a + side + 1, a + 1))
    streams = {
        20: b"".join(struct.pack(">H", index) for index in indices),
        21: vec_bytes(positions),
        22: vec_bytes(normals),
        23: b"\x00" * (len(positions) * 4),
        24: vec_bytes(uvs),
    }
    data = bytearray(b"Gamebryo File Format, Version 20.6.0.0\n")
    data.extend(b"\x00" * (128 - len(data)))
    mesh = bytearray(243)
    for offset, target in zip((134, 155, 176, 197, 218), range(20, 25), strict=True):
        struct.pack_into("<I", mesh, offset, target)
    mesh_start = len(data)
    data.extend(mesh)
    blocks = [{"Index": 2, "TypeName": "NiMesh", "DataOffset": mesh_start, "Size": len(mesh)}]
    for idx, body in streams.items():
        start = len(data)
        # Declared-data byte count + 25-byte stream-header metadata.
        data.extend(struct.pack("<I", len(body)) + b"\x00" * 25 + body)
        blocks.append({
            "Index": idx, "TypeName": "NiDataStream", "DataOffset": start,
            "Size": len(body) + 29,
        })
    probe = {"Length": len(data), "Header": {"Warnings": [], "Blocks": blocks}}
    return bytes(data), probe


def analyze_synthetic() -> dict:
    source, report = synthetic_nif()
    return grid.analyze(source, report, hashlib.sha256(source).hexdigest())


def test_ror1_bytes_decode_expected_float() -> None:
    for expected in (-32.125, 0.0, 0.125, 0.99, 760.5, 256.0):
        actual = grid.rotate_right_1_float32(encode_ror1(expected))
        assert actual == pytest.approx(expected, rel=1e-6)
    with pytest.raises(ValueError, match="exactly 4"):
        grid.rotate_right_1_float32(b"\x00\x00")


def test_synthetic_streams_qualify_grid_without_promoting_geometry() -> None:
    data = analyze_synthetic()
    assert data["schema"] == grid.SCHEMA
    assert data["gridEvidence"]["side"] == 3
    assert data["gridEvidence"]["vertexCount"] == 9
    assert data["gridEvidence"]["normalInteriorComparisons"] == 1
    assert data["gridEvidence"]["meanSurfaceNormalDot"] == pytest.approx(1.0)
    assert [x["targetBlockIndex"] for x in data["referenceHypothesis"]["refs"]] == [20, 21, 22, 23, 24]
    assert [x["meshPayloadOffset"] for x in data["referenceHypothesis"]["refs"]] == [134, 155, 176, 197, 218]
    assert data["dataStreams"]["21"]["role"] == "validated-grid-position"
    assert data["dataStreams"]["22"]["role"] == "validated-grid-normal"
    assert data["dataStreams"]["24"]["role"] == "validated-grid-uv"
    assert data["consumerBoundary"]["modelGeometryId"] is None
    assert data["consumerBoundary"]["sourceNodeTransform"] is None
    assert data["consumerBoundary"]["sourceWorldPlacement"] is None
    assert data["consumerBoundary"]["originalSourceTopologyQualified"] is False
    assert data["consumerBoundary"]["riftworldModelReady"] is False
    assert data["nativeIndexHypothesis"]["originalTopologyQualified"] is False


def test_broken_hash_and_invalid_nif_probe_refuse_promotion() -> None:
    raw, probe = synthetic_nif()
    with pytest.raises(ValueError, match="source NIF SHA256"):
        grid.analyze(raw, probe, "0" * 64)
    with pytest.raises(ValueError, match="NIF header report"):
        bad_probe = json.loads(json.dumps(probe))
        bad_probe["Header"]["Warnings"] = ["untrusted"]
        grid.analyze(raw, bad_probe, hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match="non-Gamebryo"):
        buf = b"nonsense" + raw[8:]
        grid.analyze(buf, probe, hashlib.sha256(buf).hexdigest())


def test_corrupted_stream_reference_fails_closed() -> None:
    raw, probe = synthetic_nif()
    payload = bytearray(raw)
    mesh = next(b for b in probe["Header"]["Blocks"] if b["Index"] == 2)
    struct.pack_into("<I", payload, mesh["DataOffset"] + 155, 99)
    with pytest.raises(ValueError, match="five-stream"):
        grid.analyze(bytes(payload), probe, hashlib.sha256(payload).hexdigest())


def test_mismatched_stream_body_length_fails_closed() -> None:
    raw, probe = synthetic_nif()
    payload = bytearray(raw)
    stream = next(b for b in probe["Header"]["Blocks"] if b["Index"] == 22)
    struct.pack_into("<I", payload, stream["DataOffset"], 0)
    with pytest.raises(ValueError, match="declared data length mismatch"):
        grid.analyze(bytes(payload), probe, hashlib.sha256(payload).hexdigest())


def test_invalid_normal_and_uv_alignment_fails() -> None:
    raw, probe = synthetic_nif()
    normal_block = next(b for b in probe["Header"]["Blocks"] if b["Index"] == 22)
    uv_block = next(b for b in probe["Header"]["Blocks"] if b["Index"] == 24)
    corrupted = bytearray(raw)
    start = normal_block["DataOffset"] + 29
    corrupted[start:start + 12] = vec_bytes([(0.0, 0.0, 0.0)])
    with pytest.raises(ValueError, match="not approximately unit"):
        grid.analyze(bytes(corrupted), probe, hashlib.sha256(corrupted).hexdigest())
    corrupted = bytearray(raw)
    start = uv_block["DataOffset"] + 29
    corrupted[start:start + 8] = vec_bytes([(7.0, 0.0)])
    with pytest.raises(ValueError, match="grid XYZ/UV alignment"):
        grid.analyze(bytes(corrupted), probe, hashlib.sha256(corrupted).hexdigest())


def test_rejects_index_bounds_and_retain_unpromoted_native_topology() -> None:
    source, probe = synthetic_nif()
    normal = grid.analyze(source, probe, hashlib.sha256(source).hexdigest())
    assert normal["nativeIndexHypothesis"]["outOfRangeReferences"] == 0
    assert normal["nativeIndexHypothesis"]["originalTopologyQualified"] is False
    block = next(b for b in probe["Header"]["Blocks"] if b["Index"] == 20)
    buf = bytearray(source)
    struct.pack_into(">H", buf, block["DataOffset"] + 29 + 2, 65535)
    corrupted = grid.analyze(bytes(buf), probe, hashlib.sha256(buf).hexdigest())
    assert corrupted["nativeIndexHypothesis"]["outOfRangeReferences"] == 1
    assert corrupted["nativeIndexHypothesis"]["promotion"] == "rejected"
    assert corrupted["consumerBoundary"]["originalSourceTopologyQualified"] is False


def test_cli_generates_only_ignored_diagnostic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw, probe = synthetic_nif()
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(grid, "ROOT", repo)
    monkeypatch.setattr(audit, "REPO_ROOT", repo)
    nif = tmp_path / "sample.nif"
    nif.write_bytes(raw)
    header = tmp_path / "header.json"
    header.write_text(json.dumps(probe), encoding="utf-8")
    out = repo / "Exports" / "ra2b" / "grid.json"
    assert grid.main([
        "--nif", str(nif), "--nif-header-report", str(header),
        "--expected-nif-sha256", hashlib.sha256(raw).hexdigest(),
        "--out", str(out),
    ]) == 0
    received = json.loads(out.read_text(encoding="utf-8"))
    assert received["gridEvidence"]["vertexCount"] == 9
    assert received["consumerBoundary"]["riftworldModelReady"] is False
    assert "C:" not in json.dumps(received)
    assert not out.with_name(out.name + ".tmp").exists()


@pytest.mark.parametrize("invalid", [b"", b"\x00" * 3, struct.pack("<I", 12) + b"\x00" * 3])
def test_invalid_vector_bytes_rejected(invalid: bytes) -> None:
    with pytest.raises(ValueError):
        grid.decode_ror1_vectors(invalid, 3)
