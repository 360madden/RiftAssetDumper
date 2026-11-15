"""Bounded TWAD header/table-reader tests; no live process or archive extraction."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from scripts.build_live_archive_index import extract_rows
from scripts.extract_live_nifs import read_archive, read_archive_table_streaming


def make_twaddata() -> bytes:
    """Three entries: one compressed, one null, one plain, plus payload bytes."""
    payload_a = b"packed-asset-one"
    payload_b = b"asset-two"
    offset = 20 + 3 * 44
    row_a = struct.pack(
        "<8sIIIHH20s", bytes.fromhex("362cf8866d891279"), offset,
        len(payload_a), 0, 0, 1, b"\x01" * 20,
    )
    row_null = bytes(44)
    row_b = struct.pack(
        "<8sIIIHH20s", bytes.fromhex("47fcedb50d249a17"), offset + len(payload_a),
        len(payload_b), 0, 2, 0, b"\x02" * 20,
    )
    return struct.pack("<4sIIII", b"TWAD", 1, 20, 3, 3) + row_a + row_null + row_b + payload_a + payload_b


def test_stream_reader_matches_existing_table_decoder(tmp_path: Path) -> None:
    archive = tmp_path / "assets.001"
    archive.write_bytes(make_twaddata())
    rows = read_archive_table_streaming(str(archive))
    assert rows == read_archive(str(archive))
    assert len(rows) == 3
    assert rows[0]["id_prefix"] == "362cf8866d891279"
    assert rows[0]["compression"] == 1
    assert rows[0]["sha1"] == "01" * 20
    assert rows[1]["is_null"] is True
    assert rows[2]["id_prefix"] == "47fcedb50d249a17"


def test_stream_reader_powers_cohort_index_default(tmp_path: Path) -> None:
    archive = tmp_path / "assets.001"
    archive.write_bytes(make_twaddata())
    rows, stats = extract_rows([archive], {"362cf8866d891279"})
    assert rows == [{"NifHash": "362cf8866d891279", "ArchiveName": "assets.001", "EntryIndex": 0}]
    assert stats == {
        "archives_scanned": 1,
        "cohort_hashes": 1,
        "rows_emitted": 1,
        "missing_in_archives": 0,
    }


@pytest.mark.parametrize(
    "bad",
    [
        b"",
        b"xxxx" + make_twaddata()[4:],
        make_twaddata()[:60],
        make_twaddata()[:4] + (2).to_bytes(4, "little") + make_twaddata()[8:],
        make_twaddata()[:8] + (0).to_bytes(4, "little") + make_twaddata()[12:],
        make_twaddata()[:12] + (65_537).to_bytes(4, "little") + make_twaddata()[16:],
    ],
)
def test_stream_reader_rejects_invalid_or_truncated_tables(tmp_path: Path, bad: bytes) -> None:
    archive = tmp_path / "bad.twad"
    archive.write_bytes(bad)
    with pytest.raises(ValueError):
        read_archive_table_streaming(str(archive))
