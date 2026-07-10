"""Unit tests for scripts/build_texture_coverage.py.

Covers:
- _cohort_asset_ids returns 20 identity + 4 non-identity
- _coverage_status maps (scene_textures, fly_textures) -> status hard rules
- _detect_contradiction detects scene-vs-fly linked count mismatches (positive + negative delta)
- build_report produces a JSON-shaped TextureCoverageReport
- main --dry-run prints summary and exits 0
- produced texture-coverage.json + .md roundtrip via write_outputs
- _flythrough_index_assets returns None (not {}) when file is missing (monkeypatch)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
STAGE2 = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage2"
STAGE3 = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage3"
FLYTHROUGH_INDEX_PATH = REPO_ROOT / "Assets" / "build" / "flythrough" / "flythrough-index.json"
sys.path.insert(0, str(SCRIPTS))

from build_texture_coverage import (  # noqa: E402
    FLYTHROUGH_INDEX,
    _cohort_asset_ids,
    _coverage_status,
    _detect_contradiction,
    _flythrough_index_assets,
    _flythrough_index_textures,
    _scene_manifest_textures,
    build_report,
)

# ---------- _cohort_asset_ids ----------


def test_cohort_asset_ids_20_identity_4_non_identity() -> None:
    identity_ids, non_identity_ids = _cohort_asset_ids()
    assert len(identity_ids) == 20
    assert len(non_identity_ids) == 4
    for aid in identity_ids + non_identity_ids:
        assert len(aid) == 16 and all(c in "0123456789abcdef" for c in aid)


def test_cohort_no_internal_duplicates() -> None:
    identity_ids, non_identity_ids = _cohort_asset_ids()
    all_ids = identity_ids + non_identity_ids
    assert len(all_ids) == len(set(all_ids)), f"duplicate ids: {all_ids}"


# ---------- _scene_manifest_textures ----------


@pytest.mark.skipif(
    not (STAGE2 / "sample-manifest-07f37c99a80da009.json").exists(),
    reason="scene-manifests not generated",
)
def test_scene_manifest_textures_07f37_returns_dict() -> None:
    t = _scene_manifest_textures("07f37c99a80da009")
    assert isinstance(t, dict)
    assert "linked_texture_count" in t
    assert "linked_textures" in t


def test_scene_manifest_textures_missing_returns_none() -> None:
    t = _scene_manifest_textures("0000000000000000")
    assert t is None


# ---------- _coverage_status ----------


def test_coverage_status_missing_manifest() -> None:
    assert _coverage_status(None, {"asset_in_index": True, "linked_texture_count": 0}) == "missing-manifest"


def test_coverage_status_missing_flythrough() -> None:
    scene = {"linked_texture_count": 0, "placeholder_texture_count": 0}
    assert _coverage_status(scene, {"asset_in_index": False, "linked_texture_count": 0}) == "missing-flythrough"


def test_coverage_status_covered_when_scene_linked_positive() -> None:
    scene = {"linked_texture_count": 3, "placeholder_texture_count": 0}
    fly = {"asset_in_index": True, "linked_texture_count": 3}
    assert _coverage_status(scene, fly) == "covered"


def test_coverage_status_partial_when_placeholders_but_no_linked() -> None:
    scene = {"linked_texture_count": 0, "placeholder_texture_count": 2}
    fly = {"asset_in_index": True, "linked_texture_count": 0}
    assert _coverage_status(scene, fly) == "partial"


def test_coverage_status_textureless_when_neither() -> None:
    scene = {"linked_texture_count": 0, "placeholder_texture_count": 0}
    fly = {"asset_in_index": True, "linked_texture_count": 0}
    assert _coverage_status(scene, fly) == "textureless"


# ---------- _detect_contradiction ----------


def test_detect_contradiction_when_counts_differ_positive_delta() -> None:
    scene = {"linked_texture_count": 0, "placeholder_texture_count": 0}
    fly = {"asset_in_index": True, "linked_texture_count": 2}
    contradiction, notes = _detect_contradiction(scene, fly)
    assert contradiction is True
    assert "mismatch" in notes
    assert "flythrough has more" in notes
    assert "delta=+2" in notes


def test_detect_contradiction_when_counts_differ_negative_delta() -> None:
    """When scene-manifest reports more linked textures than flythrough-index,
    the contradiction still fires but the note says the opposite direction.
    This guards the negative-delta branch in ``_detect_contradiction``.
    """
    scene = {"linked_texture_count": 5, "placeholder_texture_count": 0}
    fly = {"asset_in_index": True, "linked_texture_count": 2}
    contradiction, notes = _detect_contradiction(scene, fly)
    assert contradiction is True
    assert "scene-manifest has more" in notes
    assert "delta=-3" in notes


def test_detect_contradiction_skips_when_assets_missing() -> None:
    scene = None
    fly = {"asset_in_index": False, "linked_texture_count": 0}
    contradiction, notes = _detect_contradiction(scene, fly)
    assert contradiction is False


# ---------- _flythrough_index_assets / _flythrough_index_textures ----------


def test_flythrough_index_assets_returns_none_when_file_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real test (not a tautology) — monkeypatches ``FLYTHROUGH_INDEX``
    to point at a non-existent file, then asserts ``_flythrough_index_assets``
    returns ``None``. Guards the asymmetric return-type contract.
    """
    bogus = FLYTHROUGH_INDEX.parent / "definitely-not-a-real-file.json"
    assert not bogus.exists(), "test fixture invalidation: file exists?"
    monkeypatch.setattr(
        "build_texture_coverage.FLYTHROUGH_INDEX",
        bogus,
        raising=False,
    )
    # Re-import the module-level constant from the patched binding.
    import build_texture_coverage as m

    assert m._flythrough_index_assets() is None


def test_flythrough_index_textures_handles_missing_key() -> None:
    assets = _flythrough_index_assets() or {}
    fly = _flythrough_index_textures("0000000000000000", assets)
    assert fly["asset_in_index"] is False
    assert fly["linked_texture_count"] == 0


def test_flythrough_index_textures_handles_none_assets() -> None:
    """Defensive: passes None through to _flythrough_index_textures directly."""
    fly = _flythrough_index_textures("000b6b5d431aea29", None)
    assert fly["asset_in_index"] is False
    assert fly["linked_texture_count"] == 0


# ---------- build_report + write_outputs (end-to-end) ----------


@pytest.mark.skipif(
    not (STAGE2 / "transform-examples.json").exists() or not FLYTHROUGH_INDEX.exists(),
    reason="cohort source or flythrough-index missing",
)
def test_build_report_end_to_end(tmp_path: Path) -> None:
    report = build_report()
    # Top-level shape
    assert report["SchemaVersion"] == "texture-coverage/v1-draft"
    assert report["cohort_size"] == 24
    assert report["cohort_identity_count"] == 20
    assert report["cohort_non_identity_count"] == 4
    assert len(report["entries"]) == 24
    summary = report["coverage_summary"]
    # All cohort assets have scene-manifests (24/24); expect exactly one of:
    # covered / partial / textureless. None should be missing-manifest.
    assert summary.get("missing-manifest", 0) == 0
    # Each entry has the expected keys
    for e in report["entries"]:
        assert e["asset_id"] and e["cohort_kind"] in ("identity", "non_identity")
        assert "scene_manifest_textures" in e
        assert "flythrough_index_textures" in e
        assert e["coverage_status"] in ("covered", "partial", "textureless", "missing-flythrough", "missing-manifest")
    # Roundtrip write to a temp dir, then re-read
    from build_texture_coverage import write_outputs

    json_path, md_path = write_outputs(report, tmp_path)
    assert json_path.exists() and md_path.exists()
    rt = json.loads(json_path.read_text(encoding="utf-8-sig"))
    assert rt["SchemaVersion"] == "texture-coverage/v1-draft"


# ---------- CLI dry-run ----------


def test_main_dry_run_exits_0() -> None:
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "build_texture_coverage.py"), "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, f"dry-run exited {r.returncode}: {r.stderr}"
    assert "cohort_size=" in r.stdout
    assert "summary=" in r.stdout
