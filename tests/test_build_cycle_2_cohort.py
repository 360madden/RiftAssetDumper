"""Smoke tests for `scripts/build_cycle_2_cohort.py` (C2-1.4 reproducible cohort builder)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_cycle_2_cohort.py"
COHORT_JSON = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage1" / "cohort.json"


def test_help_exits_zero() -> None:
    """--help must exit 0 and mention the script name."""
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, f"--help returned {r.returncode}: {r.stderr}"
    assert "build_cycle_2_cohort" in r.stdout or "cohort" in r.stdout.lower()


def test_dry_run_smoke() -> None:
    """--dry-run must exit 0 and produce a JSON-cohort-shaped summary on stdout."""
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, f"--dry-run returned {r.returncode}: {r.stderr}"
    # The first line of stdout is a log line; skip to the JSON.
    first_brace = r.stdout.find("{")
    assert first_brace >= 0, f"no JSON in stdout: {r.stdout[:200]}"
    summary = json.loads(r.stdout[first_brace:])
    assert summary["plan"] == "cycle-2"
    assert summary["step"] == "C2-1.4"
    assert 20 <= summary["cohort_size"] <= 30, f"cohort_size {summary['cohort_size']} outside 20-30 band"
    assert summary["non_identity_count"] == 4
    # Lock the v0.3 contract: target_band + family_take_per_family
    assert summary.get("target_band") == "20-30", f"target_band {summary.get('target_band')} != 20-30"
    assert summary.get("family_take_per_family") == 5, f"family_take {summary.get('family_take_per_family')} != 5"
    # The 4 non-id IDs must be present (asset_id has .world suffix from world.json lookup)
    asset_ids = {e["asset_id"] for e in summary["cohort"]}
    assert {
        "07f37c99a80da009.world",
        "2c85cfa17543443b.world",
        "4a97d66a665a538e.world",
        "593ea328978bde38.world",
    }.issubset(asset_ids), "missing one of the 4 known non-id assets"


@pytest.mark.skipif(not COHORT_JSON.exists(), reason="cohort.json not yet generated")
def test_committed_cohort_in_band() -> None:
    """The on-disk cohort.json must be in the 30-50 band and have 4 non-id entries."""
    cohort = json.loads(COHORT_JSON.read_text(encoding="utf-8-sig"))
    assert 20 <= cohort["cohort_size"] <= 30
    # Lock the v0.3 contract on the on-disk cohort.json
    assert cohort.get("target_band") == "20-30", f"target_band {cohort.get('target_band')} != 20-30"
    assert cohort.get("family_take_per_family") == 5, f"family_take {cohort.get('family_take_per_family')} != 5"
    asset_ids = {e["asset_id"] for e in cohort["cohort"]}
    assert {
        "07f37c99a80da009.world",
        "2c85cfa17543443b.world",
        "4a97d66a665a538e.world",
        "593ea328978bde38.world",
    }.issubset(asset_ids)
