"""Tests for textureless DDS recovery workflow helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import recover_flythrough_textureless_dds as recovery  # noqa: E402


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_dds_refs_from_triage_dedupes_row_refs() -> None:
    report = {
        "rows": [
            {"row_dds_refs": ["Foo_C.dds", "folder\\Bar_N.DDS"]},
            {"row_dds_refs": ["foo_c.dds", "not-texture.txt"]},
        ],
        "assets": [{"asset_dds_refs": ["Asset_Only_S.dds", "Foo_C_abcdef0123456789.dds"]}],
    }
    assert recovery.dds_refs_from_triage(report) == ["asset_only_s.dds", "bar_n.dds", "foo_c.dds"]


def test_converted_dds_refs_accepts_original_basename_and_png_fallback() -> None:
    manifest = {
        "Entries": [
            {"original_basename": "known_wall_c", "png_name": "11111111_known_wall_c.png"},
            {"png_name": "22222222_already_prefixed_n.png"},
        ]
    }
    assert "known_wall_c.dds" in recovery.converted_dds_refs(manifest)
    assert "22222222_already_prefixed_n.dds" in recovery.converted_dds_refs(manifest)


def test_texture_link_from_name_match_builds_extractable_record() -> None:
    link = recovery.texture_link_from_name_match(
        {
            "Name": "D_FT_Test_C.dds",
            "Algorithm": "fnv1",
            "Hash": 123,
            "Length": 15,
            "Confidence": 100,
            "CollisionCount": 1,
            "ManifestEntryIndex": 7,
            "IdPrefix": "abcdef0123456789",
            "PakIndex": 4,
            "PakOffset": 5678,
            "CompressedSize": 90,
            "Size": 100,
            "ManifestNameLength": 15,
        }
    )
    assert link["Candidate"] == "d_ft_test_c.dds"
    assert link["TextureIdPrefix"] == "abcdef0123456789"
    assert link["TextureManifestEntryIndex"] == 7


def test_recover_textureless_dds_noops_when_all_refs_converted(tmp_path: Path) -> None:
    triage = tmp_path / "triage.json"
    converted_manifest = tmp_path / "converted-manifest.json"
    _write_json(triage, {"rows": [{"row_dds_refs": ["Known_C.dds"]}]})
    _write_json(
        converted_manifest,
        {"Entries": [{"original_basename": "known_c", "png_name": "11111111_known_c.png"}]},
    )

    report = recovery.recover_textureless_dds(
        repo_root=tmp_path,
        triage_report_path=triage,
        converted_manifest_path=converted_manifest,
        converted_dir=tmp_path / "converted",
        recovery_root=tmp_path / "recovery",
        dds_out=tmp_path / "dds",
        project=tmp_path / "missing.csproj",
        live_root=None,
    )
    assert report["summary"]["triage_dds_refs"] == 1
    assert report["summary"]["target_refs"] == 0
    assert report["commands"] == []
    assert (tmp_path / "recovery" / "textureless-dds-recovery-report.json").exists()


def test_recover_textureless_dds_reports_unmatched_targets(monkeypatch, tmp_path: Path) -> None:
    triage = tmp_path / "triage.json"
    converted_manifest = tmp_path / "converted-manifest.json"
    matches_out = tmp_path / "recovery" / "textureless-dds-name-matches.jsonl"
    _write_json(triage, {"rows": [{"row_dds_refs": ["Missing_C.dds"]}]})
    _write_json(converted_manifest, {"Entries": []})

    def fake_match_names(**kwargs: object) -> dict:
        matches_out.parent.mkdir(parents=True, exist_ok=True)
        matches_out.write_text("", encoding="utf-8")
        return {"args": ["fake"], "returncode": 0, "stdout": "Matches: 0", "stderr": ""}

    def fail_convert_recovered_dds(**kwargs: object) -> dict:
        raise AssertionError("conversion should not run without texture links")

    monkeypatch.setattr(recovery, "match_names", fake_match_names)
    monkeypatch.setattr(recovery, "convert_recovered_dds", fail_convert_recovered_dds)

    report = recovery.recover_textureless_dds(
        repo_root=tmp_path,
        triage_report_path=triage,
        converted_manifest_path=converted_manifest,
        converted_dir=tmp_path / "converted",
        recovery_root=tmp_path / "recovery",
        dds_out=tmp_path / "dds",
        project=tmp_path / "missing.csproj",
        live_root=tmp_path,
    )

    assert report["summary"]["target_refs"] == 1
    assert report["summary"]["name_matches"] == 0
    assert report["summary"]["unmatched_target_refs"] == 1
    assert report["refs"]["unmatched_target"] == ["missing_c.dds"]
    assert report["summary"]["converted_pngs"] == 0
    assert len(report["commands"]) == 1


def test_convert_recovered_dds_updates_manifest_with_png(monkeypatch, tmp_path: Path) -> None:
    dds_dir = tmp_path / "dds" / "recovered"
    dds_dir.mkdir(parents=True)
    dds = dds_dir / "Recovered_C.dds"
    dds.write_bytes(b"DDS fake payload")
    converted_dir = tmp_path / "converted"
    converted_manifest = tmp_path / "converted-manifest.json"

    def fake_convert_dds_to_png(src: Path, dst: Path) -> tuple[bool, str]:
        assert src == dds
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b"PNG fake payload")
        return True, "fake"

    monkeypatch.setattr(recovery, "convert_dds_to_png", fake_convert_dds_to_png)
    result = recovery.convert_recovered_dds(
        dds_out=tmp_path / "dds",
        converted_dir=converted_dir,
        converted_manifest_path=converted_manifest,
    )

    assert result["converted"] == 1
    manifest = json.loads(converted_manifest.read_text(encoding="utf-8"))
    assert manifest["Entries"][0]["original_basename"] == "recovered_c"
    assert manifest["Entries"][0]["png_name"].endswith("_recovered_c.png")
