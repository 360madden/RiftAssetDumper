"""RA-1.3 synthetic controls for raw/packed/decoded hash assertions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import audit_live_archive_samples
from scripts import verify_live_sample_hash_relationships as verifier


def fixture(tmp_path: Path, payload_kind: str = "nif") -> tuple[dict, dict, Path, Path]:
    live = tmp_path / "Live"
    assets = live / "Assets"
    assets.mkdir(parents=True)
    packed = b"synthetic-packed-entry"
    decoded = b"Gamebryo File Format, Version 20.6.0.0" if payload_kind == "nif" else b"DDS " + b"\x00" * 40
    decoded += b"\x80\xffsynthetic-payload"
    asset_id = hashlib.sha1(decoded).hexdigest()[:16]
    source_file = assets / "assets.001"
    offset = 40
    source_file.write_bytes(b"\x00" * offset + packed)
    digest = hashlib.sha256(source_file.read_bytes()).hexdigest()
    table_sha = hashlib.sha1(packed).hexdigest()
    sample = {
        "entry_index": 0,
        "id_prefix": asset_id,
        "offset": offset,
        "packed_size": len(packed),
        "packed_sha256": hashlib.sha256(packed).hexdigest(),
        "stored_sha1_field": table_sha,
    }
    source_report = {
        "schema": "ra1-live-archive-samples/v1",
        "archives": [
            {"source_path": "Assets/assets.001", "archive_sha256": digest, "samples": [sample]}
        ],
    }
    joined = {
        "schema": "ra1-archive-manifest-id-join/v1",
        "rows": [
            {
                "archive_source_path": "Assets/assets.001",
                "archive_sha256": digest,
                "archive_entry_index": 0,
                "asset_id_prefix": asset_id,
                "archive_table_sha1_field": table_sha,
                "archive_packed_size": len(packed),
                "archive_packed_sha256": hashlib.sha256(packed).hexdigest(),
                "join_status": "unique-id",
                "manifest_candidates": [
                    {
                        "manifest_entry_index": 25,
                        "pak_index": 2,
                        "pak_path": "ep1_assets/map/world2/geometry.pak",
                        "manifest_uncompressed_size": len(decoded),
                        "manifest_entry_hash_field": "f" * 40,
                    }
                ],
            }
        ],
    }
    decoded_root = tmp_path / "decoded"
    folder = decoded_root / "assets-001"
    folder.mkdir(parents=True)
    (folder / f"000000_{asset_id}.{payload_kind}").write_bytes(decoded)
    return source_report, joined, live, decoded_root


@pytest.mark.parametrize("kind", ["nif", "dds"])
def test_exact_hash_relationships_on_synthetic_binary(tmp_path: Path, kind: str) -> None:
    source, joined, live, decoded_root = fixture(tmp_path, kind)
    result = verifier.verify_cohort(source, joined, live, decoded_root)
    assert result["source_sample_count"] == 1
    row = result["rows"][0]
    assert row["asset_id_prefix"] == row["decoded_sha1"][:16]
    assert row["packed_sha1"] == joined["rows"][0]["archive_table_sha1_field"]
    assert row["decoded_type"] == kind
    assert row["manifest_hash_equals_packed_sha1"] is False
    assert row["manifest_hash_equals_decoded_sha1"] is False
    assert row["evidence"]["independent_decoder_replay"] is False
    assert row["evidence"]["world_placement_or_collision"] is False


def test_mutated_source_archive_is_rejected(tmp_path: Path) -> None:
    source, joined, live, decoded = fixture(tmp_path)
    with (live / "Assets" / "assets.001").open("ab") as f:
        f.write(b"tamper")
    with pytest.raises(ValueError, match="archive SHA256 changed"):
        verifier.verify_cohort(source, joined, live, decoded)


def test_joined_packed_sha256_conflict_is_rejected(tmp_path: Path) -> None:
    source, joined, live, decoded = fixture(tmp_path)
    joined["rows"][0]["archive_packed_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="packed SHA256 differs"):
        verifier.verify_cohort(source, joined, live, decoded)


def test_mutated_decoded_payload_is_rejected(tmp_path: Path) -> None:
    source, joined, live, decoded = fixture(tmp_path)
    path = next(decoded.rglob("*.nif"))
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="decoded SHA1"):
        verifier.verify_cohort(source, joined, live, decoded)


def test_manifest_size_disagreement_is_rejected(tmp_path: Path) -> None:
    source, joined, live, decoded = fixture(tmp_path)
    joined["rows"][0]["manifest_candidates"][0]["manifest_uncompressed_size"] = 1
    with pytest.raises(ValueError, match="manifest Size"):
        verifier.verify_cohort(source, joined, live, decoded)


def test_archive_table_sha1_disagreement_is_rejected(tmp_path: Path) -> None:
    source, joined, live, decoded = fixture(tmp_path)
    source["archives"][0]["samples"][0]["stored_sha1_field"] = "0" * 40
    with pytest.raises(ValueError, match="table SHA1"):
        verifier.verify_cohort(source, joined, live, decoded)


def test_missing_or_duplicate_decoded_files_are_refused(tmp_path: Path) -> None:
    source, joined, live, decoded = fixture(tmp_path)
    path = next(decoded.rglob("*.nif"))
    copy = path.with_name("000001_" + path.name.split("_", 1)[1])
    copy.write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match="exactly one"):
        verifier.verify_cohort(source, joined, live, decoded)
    path.unlink()
    copy.unlink()
    with pytest.raises(ValueError, match="exactly one"):
        verifier.verify_cohort(source, joined, live, decoded)


def test_unqualified_manifest_join_is_refused(tmp_path: Path) -> None:
    source, joined, live, decoded = fixture(tmp_path)
    joined["rows"][0]["join_status"] = "ambiguous-id"
    with pytest.raises(ValueError, match="unique manifest"):
        verifier.verify_cohort(source, joined, live, decoded)


def test_report_cli_produces_ignored_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, joined, live, decoded = fixture(tmp_path)
    repo = tmp_path / "repo"
    outbase = repo / "Exports" / "ra1"
    outbase.mkdir(parents=True)
    source_path, joined_path = outbase / "samples.json", outbase / "joined.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    manifest = tmp_path / "assets64.manifest"
    manifest.write_bytes(b"synthetic-manifest-hash-only")
    joined["source_report_sha256"] = hashlib.sha256(source_path.read_bytes()).hexdigest()
    joined["manifest_sha256"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    joined_path.write_text(json.dumps(joined), encoding="utf-8")
    monkeypatch.setattr(verifier, "ROOT", repo)
    monkeypatch.setattr(audit_live_archive_samples, "REPO_ROOT", repo)
    target = outbase / "hash-relationships.json"
    assert verifier.main([
        "--archive-report", str(source_path), "--manifest-join", str(joined_path),
        "--live-root", str(live), "--manifest-file", str(manifest),
        "--decoded-root", str(decoded), "--out", str(target),
    ]) == 0
    result = json.loads(target.read_text(encoding="utf-8"))
    assert result["nif_count"] == 1
    assert result["dds_count"] == 0
    assert "C:" not in json.dumps(result)
