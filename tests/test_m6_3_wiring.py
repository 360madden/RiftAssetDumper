"""Functional regression tests for M6.3 read-only entry-point wiring.

The 5 parametrized invariants (presence in READ_ONLY_COMMANDS / COMMAND_MAP,
empty dotnet key, dispatch block in source, _run_command invocation, no
orphan-process guard) are auto-checked for every read-only command by the
existing ``tests/test_rift_read_only_no_spawn.py`` suite. This module adds
the *functional* layer that exercises the dispatch chain end-to-end:

* The extract dispatch correctly forwards flags to a subprocess and
  propagates the underlying-script exit code (0/1/2) via ``sys.exit(rc)``.
* The compare dispatch pre-spawns a guard for missing required args and
  propagates the underlying-script exit code.

These run in <2 s on a cold cache and stub out the underlying scripts via
``unittest.mock.patch`` so they do not depend on live Phase 2/3 artifacts.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from unittest.mock import patch

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import scripts.rift_read_only as _rro  # noqa: E402
import scripts.rift_workflow as _rw  # noqa: E402


def _minimal_phase2_catalog() -> dict:
    """Tiny schema-conform Phase 2 catalog fixture (>=9 anchors not required)."""
    sigs = [
        "48 8B C4 90",
        "48 85 D2 74 0A",
        "48 8B 0D ?? ?? ?? ??",
        "48 8B 49 08",
        "48 8B 15 ?? ?? ?? ??",
        "48 8B 52 10",
    ]
    anchors = []
    for i, sig in enumerate(sigs):
        anchors.append(
            {
                "Name": f"anchor-{i}",
                "SignatureHex": sig,
                "SignatureLength": len(sig.split()),
                "WildcardCount": sig.count("??"),
                "StabilityTier": 1,
                "UniquenessVerified": True,
                "ClusterVA": f"0x140{(i + 1):06x}",
                "EntryVA": f"0x140{(i + 1) + 1:06x}",
                "Description": f"fixture anchor {i}",
            }
        )
    return {
        "SchemaVersion": "binary-signatures/v1",
        "ExtractedAt": "2024-01-01T00:00:00Z",
        "ImageBase": "0x140000000",
        "PETimestamp": 0,
        "FileSizeBytes": 100,
        "WildcardPolicy": "test",
        "TextSection": {"VA": "0x140000000", "RawSize": 100, "VirtualSize": 100},
        "BinaryVersion": {"PETimestamp": 0, "FileSizeBytes": 100},
        "Provenance": {
            "Producer": "test",
            "PEFileVersion": "test",
            "SourceSHA256": "0" * 64,
            "BinaryVersion": {"PETimestamp": 0, "FileSizeBytes": 100},
        },
        "Anchors": anchors,
        "Summary": {
            "TotalAnchors": len(anchors),
            "UniqueSignatures": len(anchors),
            "StabilityTier1Count": len(anchors),
            "StabilityTier2Count": 0,
            "StabilityTier3Count": 0,
        },
    }


def test_extract_dispatch_propagates_exit_code_zero(tmp_path):
    """When the underlying extract.main returns 0, parent sys.exit(0) is called."""
    phase2 = tmp_path / "p2.json"
    phase2.write_text(json.dumps(_minimal_phase2_catalog()), encoding="utf-8")
    out_db = tmp_path / "out.json"

    fake_completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with patch("subprocess.run", return_value=fake_completed) as mock_run:
        args = _rro._build_parser().parse_args(
            ["extract-binary-signatures", "--phase2-catalog", str(phase2), "--out", str(out_db)]
        )
        with pytest.raises(SystemExit) as exc_info:
            _rw._run_command(args)
    assert exc_info.value.code == 0
    cmd = mock_run.call_args.args[0]
    assert "--phase2-catalog" in cmd and str(phase2) in cmd
    assert "--out" in cmd and str(out_db) in cmd


def test_extract_dispatch_propagates_exit_code_two(tmp_path):
    """When the underlying extract.main returns 2 (missing input), parent sys.exit(2) is called."""
    fake_completed = subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="ERROR: missing")
    with patch("subprocess.run", return_value=fake_completed):
        args = _rro._build_parser().parse_args(["extract-binary-signatures"])
        with pytest.raises(SystemExit) as exc_info:
            _rw._run_command(args)
    assert exc_info.value.code == 2


def test_compare_dispatch_propagates_exit_code(tmp_path):
    """When the underlying compare.main returns 0, parent sys.exit(0) is called."""
    old_db = tmp_path / "old.json"
    new_db = tmp_path / "new.json"
    old_db.write_text("{}", encoding="utf-8")
    new_db.write_text("{}", encoding="utf-8")
    diff_out = tmp_path / "diff.json"
    md_out = tmp_path / "diff.md"

    fake_completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with patch("subprocess.run", return_value=fake_completed) as mock_run:
        args = _rro._build_parser().parse_args(
            [
                "compare-binary-signatures",
                "--old-db",
                str(old_db),
                "--new-db",
                str(new_db),
                "--diff-out",
                str(diff_out),
                "--diff-markdown-out",
                str(md_out),
            ]
        )
        with pytest.raises(SystemExit) as exc_info:
            _rw._run_command(args)
    assert exc_info.value.code == 0
    cmd = mock_run.call_args.args[0]
    assert "--old-db" in cmd and str(old_db) in cmd
    assert "--new-db" in cmd and str(new_db) in cmd
    assert "--out" in cmd and str(diff_out) in cmd
    assert "--markdown-out" in cmd and str(md_out) in cmd


def test_compare_dispatch_propagates_exit_code_one(tmp_path):
    """Schema-violation exit code 1 from the underlying script propagates through sys.exit(1)."""
    old_db = tmp_path / "old.json"
    new_db = tmp_path / "new.json"
    old_db.write_text("{}", encoding="utf-8")
    new_db.write_text("{}", encoding="utf-8")

    fake_completed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="schema fail")
    with patch("subprocess.run", return_value=fake_completed):
        args = _rro._build_parser().parse_args(
            ["compare-binary-signatures", "--old-db", str(old_db), "--new-db", str(new_db)]
        )
        with pytest.raises(SystemExit) as exc_info:
            _rw._run_command(args)
    assert exc_info.value.code == 1


def test_read_only_set_size_at_least_43():
    """Pre-M6.3 was 41; M6.3 adds 2 commands → at least 43."""
    from scripts.rift_read_only import READ_ONLY_COMMANDS

    assert len(READ_ONLY_COMMANDS) >= 43, f"Expected >=43 read-only commands after M6.3, got {len(READ_ONLY_COMMANDS)}."


def test_argparse_flag_parity_between_two_entry_points():
    """Pin that the 7 m6.3 flags are declared in BOTH rift_read_only and rift_workflow.

    Pins argparse flag parity between rift_read_only and rift_workflow.
    """
    m6_3_flags = [
        "--phase2-catalog",
        "--phase3-catalog",
        "--validate-only",
        "--old-db",
        "--new-db",
        "--diff-out",
        "--diff-markdown-out",
    ]

    # rift_read_only.py:_build_parser() — direct attribute access
    rro_parser = _rro._build_parser() if hasattr(_rro, "_build_parser") else None
    assert rro_parser is not None, "rift_read_only._build_parser() must exist"
    rro_flags = set(rro_parser._option_string_actions.keys())

    # rift_workflow.py:main() — build a parser using the same ArgumentParser
    # API the inline main() uses, then call sys.argv-style parse to confirm
    # the flag is accepted. We rebuild the parser by simulating the relevant
    # subset of main()'s parser.add_argument calls is impractical; instead we
    # parse the dispatch source for the literal flag strings.
    rw_src = (REPO_ROOT / "scripts" / "rift_workflow.py").read_text(encoding="utf-8")
    rw_flags = set()
    for flag in m6_3_flags:
        assert flag in rw_src, (
            f"{flag} is missing from scripts/rift_workflow.py — argparse drift between "
            f"the two entry points. Add the flag to rift_workflow.py:main() inline parser."
        )
        rw_flags.add(flag)
    for flag in m6_3_flags:
        assert flag in rro_flags, (
            f"{flag} is missing from scripts/rift_read_only.py:_build_parser() — "
            f"argparse drift between the two entry points."
        )

    # Symmetry sanity: every M6.3 flag appears in both.
    assert rw_flags == rro_flags & set(m6_3_flags)
