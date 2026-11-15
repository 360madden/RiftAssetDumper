"""RA-1 deterministic source-provenance CLI tests with synthetic TWAD files only."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pytest

from scripts import audit_live_archive_samples as audit


def _sample_root(tmp_path: Path, archive_name: str = "assets.001") -> tuple[Path, bytes]:
    root = tmp_path / "Live"
    assets = root / "Assets"
    assets.mkdir(parents=True)
    payload_a = b"compressed-first-entry"
    payload_b = b"plain-2nd"
    offset = 20 + 3 * 44
    first = struct.pack(
        "<8sIIIHH20s", bytes.fromhex("0011223344556677"),
        offset, len(payload_a), 0, 0, 1, bytes.fromhex("11" * 20),
    )
    second = struct.pack(
        "<8sIIIHH20s", bytes.fromhex("8899aabbccddeeff"),
        offset + len(payload_a), len(payload_b), 0, 1, 0, bytes.fromhex("22" * 20),
    )
    data = struct.pack("<4sIIII", b"TWAD", 1, 20, 3, 3) + first + second + bytes(44) + payload_a + payload_b
    (assets / archive_name).write_bytes(data)
    return root, data


def test_archive_report_binds_source_table_and_packed_hashes(tmp_path: Path) -> None:
    root, data = _sample_root(tmp_path)
    record = audit.audit_archive(root, "assets.001", samples=2)
    assert record["source_path"] == "Assets/assets.001"
    assert record["archive_sha256"] == hashlib.sha256(data).hexdigest()
    assert record["twad_header"]["max_entries"] == 3
    assert record["table_entries"] == 3
    assert record["non_null_entries"] == 2
    assert [row["entry_index"] for row in record["samples"]] == [0, 1]
    assert [row["id_prefix"] for row in record["samples"]] == [
        "0011223344556677", "8899aabbccddeeff",
    ]
    assert record["samples"][0]["packed_sha256"] == hashlib.sha256(b"compressed-first-entry").hexdigest()
    assert record["samples"][0]["stored_sha1_field"] == "11" * 20
    assert record["evidence"]["decompressed_payload_qualified"] is False
    assert record["evidence"]["world_placement_qualified"] is False
    assert record["evidence"]["native_collision_or_traversal_qualified"] is False


def test_sample_selection_skips_oversized_payloads_without_promotion(tmp_path: Path) -> None:
    root, _data = _sample_root(tmp_path)
    record = audit.audit_archive(root, "assets.001", samples=2, max_packed_bytes=10)
    assert len(record["samples"]) == 1
    assert record["samples"][0]["entry_index"] == 1
    assert record["oversized_before_sample_limit"] == 1


def test_report_is_repeatable_and_archive_order_is_deterministic(tmp_path: Path) -> None:
    root, _data = _sample_root(tmp_path, "assets.002")
    other = root / "Assets" / "assets.001"
    other.write_bytes((root / "Assets" / "assets.002").read_bytes())
    first = audit.build_report(root, ["assets.002", "assets.001", "assets.002"], samples=1)
    second = audit.build_report(root, ["assets.001", "assets.002"], samples=1)
    assert first == second
    assert first["archive_count"] == 2
    assert first["sample_count"] == 2
    assert [item["source_path"] for item in first["archives"]] == [
        "Assets/assets.001", "Assets/assets.002",
    ]


def test_invalid_archive_name_and_truncated_payload_fail_closed(tmp_path: Path) -> None:
    root, _data = _sample_root(tmp_path)
    with pytest.raises(ValueError, match="invalid archive name"):
        audit.audit_archive(root, "../assets.001")
    with pytest.raises(FileNotFoundError, match="unavailable"):
        audit.audit_archive(root, "assets.002")
    path = root / "Assets" / "assets.001"
    path.write_bytes(path.read_bytes()[:-5])
    with pytest.raises(ValueError, match="payload bounds"):
        audit.audit_archive(root, "assets.001")


def test_archive_change_during_hash_refuses_mixed_source_epochs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, _data = _sample_root(tmp_path)

    def hash_and_mutate(path: Path) -> str:
        original = path.read_bytes()
        path.write_bytes(original + b"mutated")
        return hashlib.sha256(original).hexdigest()

    monkeypatch.setattr(audit, "sha256_file", hash_and_mutate)
    with pytest.raises(ValueError, match="archive changed during audit"):
        audit.audit_archive(root, "assets.001", samples=1)


def test_report_writes_only_under_ignored_exports_and_is_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(audit, "REPO_ROOT", repo)
    report = {"schema": audit.REPORT_SCHEMA, "archives": []}
    target = repo / "Exports" / "ra1" / "report.json"
    audit.write_report(target, report)
    assert json.loads(target.read_text(encoding="utf-8")) == report
    assert not target.with_name(target.name + ".tmp").exists()
    with pytest.raises(ValueError, match="ignored Exports"):
        audit.write_report(tmp_path / "outside.json", report)


def test_cli_dry_run_emits_json_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _data = _sample_root(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(audit, "REPO_ROOT", repo)
    rc = audit.main(["--live-root", str(root), "--archive", "assets.001", "--dry-run", "--samples", "1"])
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["archive_count"] == 1
    assert parsed["sample_count"] == 1
    assert not (audit.REPO_ROOT / "Exports" / "ra1" / "live-archive-samples.json").exists()


@pytest.mark.parametrize("samples,limit", [(0, 1024), (51, 1024), (1, 0), (1, 8 * 1024 * 1024 + 1)])
def test_limits_refuse_unbounded_sampling(tmp_path: Path, samples: int, limit: int) -> None:
    root, _data = _sample_root(tmp_path)
    with pytest.raises(ValueError, match="bounded range"):
        audit.audit_archive(root, "assets.001", samples=samples, max_packed_bytes=limit)
