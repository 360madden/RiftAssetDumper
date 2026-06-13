"""Invariant test: POST50_POSITION_SOURCE_REPORTS <-> test fixture writers.

This test guards against the next occurrence of the "registry grew, test
fixtures didn't" CI failure. It enforces that every report in the
POST50_POSITION_SOURCE_REPORTS registry has a matching fixture writer
in at least one scripts/test_post50_*.py file.

History: this invariant was added on 2026-06-13 after a 4-commit fix
(910b168, 88af1a9, ac7db4c, 4187892) addressed the same gap for the
3 previously-affected test files. If a 12th report is added to the
registry without updating the test fixtures, this test will fail and
point at the missing report by filename.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Add scripts/ to sys.path so we can import rift_workflow when this
# file is invoked directly via `python scripts/test_post50_registry_invariant.py`
# (which is the pattern used by the CI Python tests job).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rift_workflow import POST50_POSITION_SOURCE_REPORTS  # noqa: E402


def get_report_filenames() -> set[str]:
    """Return a fresh snapshot of POST50_POSITION_SOURCE_REPORTS filenames.

    Encapsulated as a function so callers always see the current state of
    the registry rather than a frozen module-level snapshot.
    """
    return set(POST50_POSITION_SOURCE_REPORTS.values())


def _collect_fixture_writes(test_file: Path, report_filenames: set[str]) -> set[str]:
    """Parse a Python file and collect all string literals that look like
    fixture filenames (matching known POST50 report filenames).

    This intentionally uses AST (not regex) to be robust against cosmetic
    changes like quoting, line wrapping, and trailing punctuation.
    """
    source = test_file.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fixture_files: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in report_filenames:
                fixture_files.add(node.value)
    return fixture_files


def test_all_reports_have_fixtures() -> None:
    """Every report in the registry must have at least one fixture writer
    in some scripts/test_post50_*.py file."""
    test_dir = Path(__file__).resolve().parent
    test_files = sorted(test_dir.glob("test_post50_*.py"))
    report_filenames = get_report_filenames()

    per_file: dict[str, set[str]] = {}
    all_fixtures: set[str] = set()
    for tf in test_files:
        per_file[tf.name] = _collect_fixture_writes(tf, report_filenames)
        all_fixtures.update(per_file[tf.name])

    missing = report_filenames - all_fixtures
    assert not missing, (
        f"Reports in POST50_POSITION_SOURCE_REPORTS with no fixture writer in "
        f"any test_post50_*.py file: {sorted(missing)}\n"
        f"Per-file coverage: {dict(sorted(per_file.items()))}"
    )


def test_no_orphan_fixtures() -> None:
    """No test file should reference a fixture for a report not in the
    registry. Indicates either a typo in the filename or a removed report
    whose fixture was left behind."""
    test_dir = Path(__file__).resolve().parent
    test_files = sorted(test_dir.glob("test_post50_*.py"))
    report_filenames = get_report_filenames()

    orphans: list[tuple[str, str]] = []
    for tf in test_files:
        for fixture in _collect_fixture_writes(tf, report_filenames):
            if fixture not in report_filenames:
                orphans.append((tf.name, fixture))

    assert not orphans, f"Test files referencing fixtures not in POST50_POSITION_SOURCE_REPORTS: {orphans}"


if __name__ == "__main__":
    test_all_reports_have_fixtures()
    report_filenames = get_report_filenames()
    print(f"PASS: all {len(report_filenames)} reports in POST50_POSITION_SOURCE_REPORTS have fixture writers")
    test_no_orphan_fixtures()
    print("PASS: no orphan fixture references in test_post50_*.py files")
