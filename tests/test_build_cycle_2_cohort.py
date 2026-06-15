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
    last_brace = r.stdout.rfind("{")
    assert last_brace >= 0, f"no JSON in stdout: {r.stdout[:200]}"
    summary = json.loads(r.stdout[last_brace:])
    assert summary["plan"] == "cycle-2"
    assert summary["step"] == "C2-1.4"
    assert 30 <= summary["cohort_size"] <= 50, f"cohort_size {summary['cohort_size']} outside 30-50 band"
    assert summary["non_identity_count"] == 4
    # The 4 non-id IDs must be present
    asset_ids = {e["asset_id"] for e in summary["cohort"]}
    assert {
        "07f37c99a80da009",
        "2c85cfa17543443b",
        "4a97d66a665a538e",
        "593ea328978bde38",
    }.issubset(asset_ids), "missing one of the 4 known non-id assets"


@pytest.mark.skipif(not COHORT_JSON.exists(), reason="cohort.json not yet generated")
def test_committed_cohort_in_band() -> None:
    """The on-disk cohort.json must be in the 30-50 band and have 4 non-id entries."""
    cohort = json.loads(COHORT_JSON.read_text(encoding="utf-8-sig"))
    assert 30 <= cohort["cohort_size"] <= 50
    asset_ids = {e["asset_id"] for e in cohort["cohort"]}
    assert {
        "07f37c99a80da009",
        "2c85cfa17543443b",
        "4a97d66a665a538e",
        "593ea328978bde38",
    }.issubset(asset_ids)
