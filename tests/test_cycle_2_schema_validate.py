"""Tests for `scripts/cycle_2_schema_validate.py`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "cycle_2_schema_validate.py"


def test_help_exits_zero() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Draft 2020-12" in result.stdout


def test_validates_schema_and_instance(tmp_path: Path) -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["name"],
        "properties": {"name": {"type": "string"}},
        "additionalProperties": False,
    }
    instance = {"name": "rift"}
    schema_path = tmp_path / "schema.json"
    instance_path = tmp_path / "instance.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    instance_path.write_text(json.dumps(instance), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(schema_path), "--instance", str(instance_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "validates against" in result.stdout
