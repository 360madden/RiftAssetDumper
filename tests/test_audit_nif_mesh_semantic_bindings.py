"""RA-2g synthetic NiMesh semantic binding layout/negative controls."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pytest

from scripts import audit_live_archive_samples as archive_audit
from scripts import audit_nif_mesh_semantic_bindings as bindings


def synthetic() -> tuple[bytes, dict]:
    mesh = bytearray(243)
    struct.pack_into("<i", mesh, 0, -1)
    struct.pack_into("<I", mesh, 4, 2)
    struct.pack_into("<ii", mesh, 8, 3, 4)
    struct.pack_into("<iH", mesh, 16, -1, 0x10)
    struct.pack_into("<fff", mesh, 22, 0, 0, 0)
    for r in range(9):
        struct.pack_into("<f", mesh, 34 + r * 4, 1.0 if r in (0, 4, 8) else 0.0)
    struct.pack_into("<f", mesh, 70, 1.0)
    struct.pack_into("<Iii", mesh, 74, 2, 6, 5)
    struct.pack_into("<i", mesh, 86, -1)
    struct.pack_into("<I", mesh, 130, 5)
    for r in range(5):
        struct.pack_into("<IBIIII", mesh, 134 + r * 21, r + 20, 0, 1, 1, r + 16, 0)

    buffer = bytearray(b"Gamebryo File Format, Version 20.6.0.0\n")
    buffer.extend(b"\x00" * (128 - len(buffer)))
    mesh_offset = len(buffer)
    buffer.extend(mesh)
    blocks = [{"Index": 2, "TypeName": "NiMesh", "DataOffset": mesh_offset, "Size": len(mesh)}]
    for target in range(20, 25):
        off = len(buffer)
        stream_body = struct.pack("<I", 12) + b"\x00" * 25 + b"\x00" * 12
        buffer.extend(stream_body)
        blocks.append({"Index": target, "TypeName": "NiDataStream", "DataOffset": off, "Size": len(stream_body)})
    header = {
        "Length": len(buffer),
        "Header": {
            "Warnings": [],
            "Blocks": blocks,
            "Strings": [
                {"Index": i + 16, "Value": name}
                for i, name in enumerate(bindings.SEMANTICS)
            ],
        },
    }
    return bytes(buffer), header


def test_semantic_roles_are_bound_to_real_string_indices() -> None:
    source, header = synthetic()
    report = bindings.analyze_source(source, header, hashlib.sha256(source).hexdigest())
    assert report["bindingCount"] == 5
    assert [b["semanticName"] for b in report["semanticBindings"]] == list(bindings.SEMANTICS)
    assert [b["targetBlockIndex"] for b in report["semanticBindings"]] == [20, 21, 22, 23, 24]
    assert [b["semanticNameStringIndex"] for b in report["semanticBindings"]] == [16, 17, 18, 19, 20]
    assert [b["meshByteOffset"] for b in report["semanticBindings"]] == [134, 155, 176, 197, 218]
    assert report["qualified"]["streamIdsBoundToStringTableSemanticNames"] is True
    assert report["qualified"]["fullDescriptorFieldsSemanticsKnown"] is False
    assert report["qualified"]["nativeTrianglesQualified"] is False
    assert report["qualified"]["riftworldModelReady"] is False
    assert report["schema"] == bindings.SCHEMA


def test_same_mesh_record_and_index_blob_can_have_different_position_bytes() -> None:
    first, header = synthetic()
    altered = bytearray(first)
    position = next(b for b in header["Header"]["Blocks"] if b["Index"] == 21)
    altered[position["DataOffset"] + 29 + 3] = 1
    other = bytes(altered)
    one = bindings.analyze_source(first, header, hashlib.sha256(first).hexdigest())
    two = bindings.analyze_source(other, header, hashlib.sha256(other).hexdigest())
    assert one["sourceNifSha256"] != two["sourceNifSha256"]
    assert [r["rawRecordSha256"] for r in one["semanticBindings"]] == [
        r["rawRecordSha256"] for r in two["semanticBindings"]
    ]
    assert one["semanticBindings"][0]["streamBodySha256"] == two["semanticBindings"][0]["streamBodySha256"]
    assert one["semanticBindings"][1]["streamBodySha256"] != two["semanticBindings"][1]["streamBodySha256"]
    assert one["semanticBindings"][4]["streamBodySha256"] == two["semanticBindings"][4]["streamBodySha256"]
    assert one["qualified"]["nativeTrianglesQualified"] is False
    assert two["qualified"]["nativeTrianglesQualified"] is False


def test_invalid_semantic_string_index_and_name_are_rejected() -> None:
    source, header = synthetic()
    data = bytearray(source)
    struct.pack_into("<I", data, 128 + 134 + 13, 999)
    with pytest.raises(ValueError, match="semantic string index"):
        bindings.analyze_source(bytes(data), header, hashlib.sha256(data).hexdigest())

    source, header = synthetic()
    header["Header"]["Strings"][1]["Value"] = "INDEX"
    with pytest.raises(ValueError, match="semantic ordering"):
        bindings.analyze_source(source, header, hashlib.sha256(source).hexdigest())


@pytest.mark.parametrize("relative", [4, 5, 9, 17])
def test_unqualified_unknown_descriptor_fields_are_rejected(relative: int) -> None:
    source, header = synthetic()
    data = bytearray(source)
    data[128 + 134 + relative] = 9
    with pytest.raises(ValueError, match="descriptor fields"):
        bindings.analyze_source(bytes(data), header, hashlib.sha256(data).hexdigest())


def test_invalid_stream_count_or_duplicate_target_is_rejected() -> None:
    source, header = synthetic()
    data = bytearray(source)
    struct.pack_into("<I", data, 128 + 130, 4)
    with pytest.raises(ValueError, match="21-byte record count"):
        bindings.analyze_source(bytes(data), header, hashlib.sha256(data).hexdigest())
    data = bytearray(source)
    struct.pack_into("<I", data, 128 + 155, 20)
    with pytest.raises(ValueError, match="duplicate"):
        bindings.analyze_source(bytes(data), header, hashlib.sha256(data).hexdigest())


def test_invalid_stream_target_type_and_declared_bytes_fail_closed() -> None:
    source, header = synthetic()
    header["Header"]["Blocks"][1]["TypeName"] = "NiSourceTexture"
    with pytest.raises(ValueError, match="not a NiDataStream"):
        bindings.analyze_source(source, header, hashlib.sha256(source).hexdigest())
    source, header = synthetic()
    data = bytearray(source)
    target = next(b for b in header["Header"]["Blocks"] if b["Index"] == 20)
    struct.pack_into("<I", data, target["DataOffset"], 99)
    with pytest.raises(ValueError, match="declared"):
        bindings.analyze_source(bytes(data), header, hashlib.sha256(data).hexdigest())


def test_source_sha256_and_header_mismatch_fail_closed() -> None:
    source, header = synthetic()
    with pytest.raises(ValueError, match="SHA256"):
        bindings.analyze_source(source, header, "0" * 64)
    header["Header"]["Warnings"] = ["bad"]
    with pytest.raises(ValueError, match="header report"):
        bindings.analyze_source(source, header, hashlib.sha256(source).hexdigest())


def test_cli_writes_only_ignored_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, header = synthetic()
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(bindings, "ROOT", repo)
    monkeypatch.setattr(archive_audit, "REPO_ROOT", repo)
    nif = tmp_path / "source.nif"
    nif.write_bytes(source)
    hdr = tmp_path / "header.json"
    hdr.write_text(json.dumps(header), encoding="utf-8")
    out = repo / "Exports" / "ra2g" / "semantic.json"
    assert bindings.main([
        "--nif", str(nif), "--nif-header-report", str(hdr),
        "--expected-nif-sha256", hashlib.sha256(source).hexdigest(),
        "--out", str(out),
    ]) == 0
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["bindingCount"] == 5
    assert all(x is False for k, x in receipt["qualified"].items() if k != "streamIdsBoundToStringTableSemanticNames")
    assert "C:" not in json.dumps(receipt)
    with pytest.raises(ValueError, match="ignored Exports"):
        bindings.write_report(tmp_path / "outside.json", receipt)
