"""Smoke tests for `scripts/build_cycle_2_transform_examples.py`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_cycle_2_transform_examples.py"


def test_help_exits_zero() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"--help returned {result.returncode}: {result.stderr}"
    assert "transform" in result.stdout.lower()


def test_dry_run_uses_current_v03_cohort() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"--dry-run returned {result.returncode}: {result.stderr}"
    summary = json.loads(result.stdout)
    assert summary["plan"] == "cycle-2"
    assert summary["step"] == "C2-2.1"
    assert 20 <= summary["cohort_size"] <= 30
    assert summary["available_count"] == summary["cohort_size"]
    assert summary["non_identity_count"] == 4
    assert summary["summary"]["all_fields_finite"] is True
    assert summary["summary"]["all_scales_unity"] is True
