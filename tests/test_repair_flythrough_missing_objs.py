"""Tests for exact-hash flythrough missing OBJ repair."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from repair_flythrough_missing_objs import build_repair_report, file_sha256  # noqa: E402


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_manifest(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": "export-manifest-v3", "entries": entries}), encoding="utf-8")


def test_build_repair_report_copies_only_exact_sha_matches(tmp_path: Path) -> None:
    source = _write(tmp_path / "Exports" / "existing" / "source.obj", "v 0 0 0\n")
    target = tmp_path / "Exports" / "missing" / "target.obj"
    manifest = tmp_path / "Exports" / "export-manifest.json"
    _write_manifest(
        manifest,
        [
            {
                "path": str(target),
                "sha256": file_sha256(source),
                "file_size": source.stat().st_size,
                "mesh_block": "6",
                "vertex_count": 1,
                "face_count": 0,
                "faced": False,
            }
        ],
    )

    dry = build_repair_report(repo_root=tmp_path, export_manifest_path=manifest, scan_roots=[tmp_path / "Exports"])
    assert dry["summary"] == {
        "missing_entries": 1,
        "repairable_exact_sha": 1,
        "same_size_file_matches": 1,
        "repaired": 0,
        "unrepaired": 1,
    }
    assert dry["entries"][0]["same_size_file_candidates"][0]["matches_expected_sha"] is True
    assert target.exists() is False

    applied = build_repair_report(
        repo_root=tmp_path,
        export_manifest_path=manifest,
        scan_roots=[tmp_path / "Exports"],
        apply=True,
    )
    assert applied["summary"] == {
        "missing_entries": 1,
        "repairable_exact_sha": 1,
        "same_size_file_matches": 1,
        "repaired": 1,
        "unrepaired": 0,
    }
    assert target.read_text(encoding="utf-8") == "v 0 0 0\n"


def test_build_repair_report_leaves_unmatched_missing_entry_unrepaired(tmp_path: Path) -> None:
    similar = _write(
        tmp_path / "Exports" / "existing" / "decode-nif-geometry-mesh17.obj",
        "\n".join(
            [
                "v 1 0 0",
                "v 0 1 0",
                "f 1 2 1",
                "",
            ]
        ),
    )
    target = tmp_path / "Exports" / "missing" / "target.obj"
    manifest = tmp_path / "Exports" / "export-manifest.json"
    _write_manifest(
        manifest,
        [
            {
                "path": str(similar),
                "sha256": file_sha256(similar),
                "file_size": similar.stat().st_size,
                "mesh_block": "17",
                "vertex_count": 50,
                "face_count": 1,
                "faced": True,
                "asset_id": "abcdef0123456789",
            },
            {
                "path": str(target),
                "sha256": "0" * 64,
                "file_size": 123,
                "mesh_block": "17",
                "vertex_count": 50,
                "face_count": 0,
                "faced": False,
            },
        ],
    )

    report = build_repair_report(
        repo_root=tmp_path,
        export_manifest_path=manifest,
        scan_roots=[tmp_path / "Exports"],
        apply=True,
    )
    assert report["summary"] == {
        "missing_entries": 1,
        "repairable_exact_sha": 0,
        "same_size_file_matches": 0,
        "repaired": 0,
        "unrepaired": 1,
    }
    assert report["entries"][0]["repair_status"] == "not-repairable"
    assert report["entries"][0]["same_size_file_candidates"] == []
    candidates = report["entries"][0]["similar_existing_candidates"]
    assert candidates[0]["path"] == "Exports/existing/decode-nif-geometry-mesh17.obj"
    assert candidates[0]["score_reasons"] == ["same-mesh-block", "same-vertex-count"]
    assert candidates[0]["derived_no_face_variants"][0]["variant"] == "no-face-lf"
    assert candidates[0]["derived_no_face_variants"][0]["matches_expected_sha"] is False
    assert target.exists() is False
