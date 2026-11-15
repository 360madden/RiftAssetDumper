"""RA-1.2 ID-only join tests. No game-file or native-process dependency."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import audit_live_archive_samples
from scripts import join_live_archive_manifest_samples as joiner


def _source_report() -> dict:
    return {
        "schema": "ra1-live-archive-samples/v1",
        "archives": [
            {
                "source_path": "Assets/assets.001",
                "archive_sha256": "a" * 64,
                "samples": [
                    {
                        "entry_index": 0,
                        "id_prefix": "0011223344556677",
                        "packed_size": 15,
                        "packed_sha256": "b" * 64,
                        "stored_sha1_field": "c" * 40,
                    }
                ],
            }
        ],
    }


def _manifest_row() -> dict:
    return {
        "Index": 159072,
        "IdPrefix": "0011223344556677",
        "PakIndex": 1398,
        "PakOffset": 60016,
        "CompressedSize": 848,
        "Size": 1152,
        "Hash": "d" * 40,
        "NameLength": 26,
        "FilenameFnv1Hash": 1690490081,
    }


def _join(source: dict, rows: list[dict], paks: dict[int, dict]) -> dict:
    return joiner.join_report(
        source,
        {("assets.001", "0011223344556677"): rows},
        paks,
        source_report_sha256="e" * 64,
        manifest_sha256="f" * 64,
        paks_export_sha256="1" * 64,
    )


def test_exact_id_join_preserves_different_hashes_and_pak_path() -> None:
    joined = _join(
        _source_report(),
        [_manifest_row()],
        {1398: {"Index": 1398, "Path": "ep1_assets/map/world2/world2geometry_48.pak"}},
    )
    assert joined["schema"] == "ra1-archive-manifest-id-join/v1"
    assert joined["unique_id_matches"] == 1
    assert joined["cli_exports_confirmed_same_manifest_epoch"] is False
    row = joined["rows"][0]
    assert row["join_status"] == "unique-id"
    assert row["asset_id_prefix"] == "0011223344556677"
    candidate = row["manifest_candidates"][0]
    assert candidate["manifest_entry_index"] == 159072
    assert candidate["pak_path"] == "ep1_assets/map/world2/world2geometry_48.pak"
    assert candidate["raw_sha1_fields_equal"] is False
    assert candidate["compressed_sizes_equal"] is False
    assert row["qualification"]["packed_payload_equivalence"] is False
    assert row["qualification"]["decoded_asset_type"] is False
    assert row["qualification"]["collision_or_traversal"] is False


def test_missing_manifest_id_is_unmatched_not_a_false_join() -> None:
    joined = _join(_source_report(), [], {})
    assert joined["unique_id_matches"] == 0
    assert joined["unmatched_samples"] == 1
    assert joined["rows"][0]["manifest_candidates"] == []
    assert joined["rows"][0]["qualification"]["archive_id_equals_manifest_id"] is False


def test_duplicate_id_is_ambiguous_and_keeps_all_candidates() -> None:
    first = _manifest_row()
    second = {**first, "Index": 159073}
    joined = _join(_source_report(), [first, second], {1398: {"Path": "assets/texture/x.pak"}})
    assert joined["ambiguous_samples"] == 1
    assert joined["rows"][0]["join_status"] == "ambiguous-id"
    assert len(joined["rows"][0]["manifest_candidates"]) == 2


def test_mismatched_manifest_id_is_rejected() -> None:
    bad = {**_manifest_row(), "IdPrefix": "ffffffffffffffff"}
    with pytest.raises(ValueError, match="mismatches sampled ID"):
        _join(_source_report(), [bad], {1398: {"Path": "assets/texture/x.pak"}})


def test_missing_pak_index_and_absolute_pak_path_refused() -> None:
    with pytest.raises(ValueError, match="missing PAK"):
        _join(_source_report(), [_manifest_row()], {})
    with pytest.raises(ValueError, match="absolute"):
        _join(_source_report(), [_manifest_row()], {1398: {"Path": r"C:\private\wrong.pak"}})


def test_invalid_source_path_and_id_are_rejected() -> None:
    bad_path = _source_report()
    bad_path["archives"][0]["source_path"] = "Assets/../outside"
    with pytest.raises(ValueError, match="invalid source archive name"):
        _join(bad_path, [_manifest_row()], {1398: {"Path": "x.pak"}})
    bad_id = _source_report()
    bad_id["archives"][0]["samples"][0]["id_prefix"] = "not-an-id"
    with pytest.raises(ValueError, match="invalid sampled archive asset ID"):
        _join(bad_id, [_manifest_row()], {1398: {"Path": "x.pak"}})


def test_invalid_pak_index_map_fails_closed() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        joiner.pak_index_map([{"Index": 1}, {"Index": 1}])
    with pytest.raises(ValueError, match="invalid"):
        joiner.pak_index_map([{"Index": "1"}])


def test_cli_joins_existing_cli_files_without_parsing_twam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    data = repo / "Exports" / "ra1"
    data.mkdir(parents=True)
    monkeypatch.setattr(joiner, "ROOT", repo)
    monkeypatch.setattr(audit_live_archive_samples, "REPO_ROOT", repo)
    manifest = tmp_path / "assets64.manifest"
    manifest.write_bytes(b"TWAM-fixture-only: not parsed by Python")
    source_file = data / "live-archive-samples.json"
    source_file.write_text(json.dumps(_source_report()), encoding="utf-8")
    (data / "assets64-paks.jsonl").write_text(
        json.dumps({"Index": 1398, "Path": "assets/texture/x.pak"}) + "\n", encoding="utf-8"
    )
    (data / "manifest-join-assets-001-0011223344556677.jsonl").write_text(
        json.dumps(_manifest_row()) + "\n", encoding="utf-8"
    )
    target = data / "joined.json"
    assert joiner.main(
        [
            "--archive-report", str(source_file), "--manifest-file", str(manifest),
            "--paks-jsonl", str(data / "assets64-paks.jsonl"), "--rows-dir", str(data),
            "--out", str(target),
        ]
    ) == 0
    result = json.loads(target.read_text(encoding="utf-8"))
    assert result["unique_id_matches"] == 1
    assert result["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert result["manifest_source_path"] == "assets64.manifest"
    assert result["source_report_sha256"] == hashlib.sha256(source_file.read_bytes()).hexdigest()
    assert "C:" not in json.dumps(result)


def test_cli_refuses_other_manifest_name(tmp_path: Path) -> None:
    wrong = tmp_path / "assets64_debug.manifest"
    wrong.write_bytes(b"data")
    assert joiner.main(["--manifest-file", str(wrong)]) == 1


def test_cli_missing_row_file_refuses_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    data = repo / "Exports" / "ra1"
    data.mkdir(parents=True)
    monkeypatch.setattr(joiner, "ROOT", repo)
    monkeypatch.setattr(audit_live_archive_samples, "REPO_ROOT", repo)
    manifest = tmp_path / "assets64.manifest"
    manifest.write_bytes(b"test")
    (data / "live-archive-samples.json").write_text(json.dumps(_source_report()), encoding="utf-8")
    (data / "assets64-paks.jsonl").write_text("", encoding="utf-8")
    out = data / "joined.json"
    assert joiner.main(
        [
            "--archive-report", str(data / "live-archive-samples.json"),
            "--manifest-file", str(manifest), "--paks-jsonl", str(data / "assets64-paks.jsonl"),
            "--rows-dir", str(data), "--out", str(out),
        ]
    ) == 1
    assert not out.exists()
