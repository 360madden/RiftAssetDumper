"""RA-2d synthetic NiTerrainNode/NiMesh transform and hierarchy negative controls."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pytest

from scripts import audit_live_archive_samples as audit
from scripts import audit_nif_terrain_node_transform as node


def _avobject(
    size: int, *,
    flags: int,
    translation: tuple[float, float, float],
    extras: list[int],
    properties: list[int],
) -> tuple[bytearray, int]:
    payload = bytearray(size)
    off = 0

    def put(fmt: str, value: int | float) -> None:
        nonlocal off
        struct.pack_into(fmt, payload, off, value)
        off += struct.calcsize(fmt)

    put("<i", -1)
    put("<I", len(extras))
    for extra in extras:
        put("<i", extra)
    put("<i", -1)
    put("<H", flags)
    for value in translation:
        put("<f", value)
    for i in range(9):
        put("<f", 1.0 if i in (0, 4, 8) else 0.0)
    put("<f", 1.0)
    put("<I", len(properties))
    for property_ref in properties:
        put("<i", property_ref)
    put("<i", -1)
    return payload, off


def synthetic() -> tuple[bytes, dict]:
    root, offset = _avobject(
        106, flags=0x110, translation=(8960.0, 0.0, 6400.0),
        extras=[], properties=[1],
    )
    assert offset == 78
    struct.pack_into("<I", root, 78, 1)  # one child
    struct.pack_into("<i", root, 82, 2)  # NiMesh #2
    struct.pack_into("<I", root, 86, 0)  # no effects
    mesh, offset = _avobject(
        243, flags=0x10, translation=(0.0, 0.0, 0.0),
        extras=[3, 4], properties=[6, 5],
    )
    assert offset == 90
    struct.pack_into("<I", mesh, 130, 5)
    for i in range(5):
        struct.pack_into("<I", mesh, 134 + i * 21, 20 + i)

    parts: dict[int, tuple[str, bytes]] = {
        0: ("NiTerrainNode", bytes(root)),
        1: ("NiVertexColorProperty", bytes(14)),
        2: ("NiMesh", bytes(mesh)),
        3: ("NiColorExtraData", bytes(20)),
        4: ("NiIntegersExtraData", bytes(28)),
        5: ("NiMaterialProperty", bytes(68)),
        6: ("NiTexturingProperty", bytes(259)),
    }
    for i in range(20, 25):
        parts[i] = ("NiDataStream", struct.pack("<I", 12) + bytes(25) + bytes(12))

    source = bytearray(b"Gamebryo File Format, Version 20.6.0.0\n")
    source.extend(b"\x00" * (128 - len(source)))
    blocks = []
    for i, (kind, payload) in sorted(parts.items()):
        offset = len(source)
        source.extend(payload)
        blocks.append({"Index": i, "TypeName": kind, "DataOffset": offset, "Size": len(payload)})
    header = {"Length": len(source), "Header": {"Warnings": [], "Blocks": blocks}}
    return bytes(source), header


def _analyze(source: bytes, header: dict) -> dict:
    return node.analyze(source, header, hashlib.sha256(source).hexdigest())


def _block(header: dict, index: int) -> dict:
    return next(x for x in header["Header"]["Blocks"] if x["Index"] == index)


def test_source_node_transform_and_qualified_child() -> None:
    source, header = synthetic()
    result = _analyze(source, header)
    assert result["sourceNifNode"]["transform"]["translation"] == [8960.0, 0.0, 6400.0]
    assert result["sourceNifNode"]["transform"]["scale"] == 1.0
    assert result["sourceNifNode"]["transform"]["propertyIndices"] == [1]
    assert result["sourceNifNode"]["childMeshIndices"] == [2]
    assert result["sourceNifNode"]["effectIndices"] == []
    assert result["sourceMesh"]["transform"]["translation"] == [0.0, 0.0, 0.0]
    assert result["sourceMesh"]["transform"]["extraDataIndices"] == [3, 4]
    assert result["sourceMesh"]["transform"]["propertyIndices"] == [6, 5]
    assert result["sourceMesh"]["streamReferenceCount"] == 5
    assert result["sourceMesh"]["streamBlockIndices"] == [20, 21, 22, 23, 24]
    assert result["localNodeComposition"]["parentRelativeTranslation"] == [8960.0, 0.0, 6400.0]
    assert result["consumerBoundary"]["sourceHierarchyQualified"] is True
    assert result["consumerBoundary"]["worldPlacementMatrix"] is None
    assert result["consumerBoundary"]["riftworldModelReady"] is False
    assert result["consumerBoundary"]["originalTrianglesQualified"] is False


def test_hierarchy_rejects_property_as_child_and_wrong_stream_count() -> None:
    source, header = synthetic()
    target = bytearray(source)
    root = _block(header, 0)
    struct.pack_into("<i", target, root["DataOffset"] + 82, 1)
    with pytest.raises(ValueError, match="NiMesh #2 child"):
        _analyze(bytes(target), header)

    target = bytearray(source)
    mesh = _block(header, 2)
    struct.pack_into("<I", target, mesh["DataOffset"] + 130, 4)
    with pytest.raises(ValueError, match="five-stream"):
        _analyze(bytes(target), header)


def test_property_collision_and_extra_data_negative_controls() -> None:
    source, header = synthetic()
    root, mesh = _block(header, 0), _block(header, 2)
    for where, value, message in (
        (root["DataOffset"] + 70, 2, "property"),
        (mesh["DataOffset"] + 78, 4, "property"),
        (mesh["DataOffset"] + 8, 5, "extra-data"),
        (root["DataOffset"] + 74, 99, "collision"),
    ):
        buf = bytearray(source)
        struct.pack_into("<i", buf, where, value)
        with pytest.raises(ValueError, match=message):
            _analyze(bytes(buf), header)


def test_nonidentity_or_bad_scale_not_promoted() -> None:
    source, header = synthetic()
    root = _block(header, 0)
    buf = bytearray(source)
    struct.pack_into("<f", buf, root["DataOffset"] + 62, 2.0)
    with pytest.raises(ValueError, match="nonidentity"):
        _analyze(bytes(buf), header)
    buf = bytearray(source)
    struct.pack_into("<f", buf, root["DataOffset"] + 14, float("nan"))
    with pytest.raises(ValueError, match="non-finite"):
        _analyze(bytes(buf), header)


def test_broken_sha_and_header_report_fail_closed() -> None:
    source, header = synthetic()
    with pytest.raises(ValueError, match="SHA256"):
        node.analyze(source, header, "0" * 64)
    header["Header"]["Warnings"] = ["bad"]
    with pytest.raises(ValueError, match="header report"):
        _analyze(source, header)


def test_cli_writes_only_ignored_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, header = synthetic()
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(node, "ROOT", repo)
    monkeypatch.setattr(audit, "REPO_ROOT", repo)
    nif = tmp_path / "nif.bin"
    nif.write_bytes(source)
    hdr = tmp_path / "nif-header.json"
    hdr.write_text(json.dumps(header), encoding="utf-8")
    out = repo / "Exports" / "ra2d" / "node.json"
    assert node.main([
        "--nif", str(nif),
        "--nif-header-report", str(hdr),
        "--expected-nif-sha256", hashlib.sha256(source).hexdigest(),
        "--out", str(out),
    ]) == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["localNodeComposition"]["parentRelativeTranslation"] == [8960.0, 0.0, 6400.0]
    assert result["consumerBoundary"]["sourceWorld"] is None
    assert result["consumerBoundary"]["collisionOrNavigationQualified"] is False
    assert not out.with_name(out.name + ".tmp").exists()


def test_cli_rejects_output_outside_ignored_exports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, header = synthetic()
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(node, "ROOT", repo)
    monkeypatch.setattr(audit, "REPO_ROOT", repo)
    with pytest.raises(ValueError, match="ignored Exports"):
        node.write_report(tmp_path / "other.json", _analyze(source, header))
