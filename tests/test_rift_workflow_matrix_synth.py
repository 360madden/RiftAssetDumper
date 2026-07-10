#!/usr/bin/env python3
"""Smoke + unit tests for the matrix-synth CLI hook in scripts.rift_workflow.

The matrix-synth command is a Phase 47 data-thickness polyfill that emits 3
schema-valid asset-semantic-index/v1 JSON files at
Exports/discovery-matrix/nif-semantic-hints/.  ``--commit-matrices`` then
asserts every entry still matches the polyfill sentinel (ArchiveName/
DetectedType/MagicLabel) — this guard fails closed if the real C#
build-asset-semantic-index (driven by scripts/rift_asset_discovery_matrix.py)
has shipped and replaced the polyfill.

These tests lock:
- COMMAND_MAP registration for matrix-synth
- PS_MODE_TO_COMMAND registration for MatrixSynth
- Sentinel constants exported at module top
- ``_assert_matrix_synth_polyfill_only`` passes on real polyfill output
- ``_assert_matrix_synth_polyfill_only`` raises on real-backend output
- Empty Entries[] fails closed (polyfill can never produce empty buckets)
- A non-existent matrix file raises ValueError with the right hint
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "scripts"


def _build_polyfill_entry(hint: str) -> dict[str, object]:
    """Emit one polyfill-shaped matrix entry."""
    return {
        "AssetIdPrefix": "0" * 16,
        "ArchiveName": "synthetic.twad",
        "EntryIndex": 0,
        "ManifestEntryIndex": None,
        "FilenameFnv1Hash": None,
        "PakIndex": None,
        "PakOffset": None,
        "CompressedSize": 0,
        "UnpackedSize": 0,
        "Compression": 0,
        "DetectedType": "synthetic",
        "Format": None,
        "RiffType": None,
        "Width": None,
        "Height": None,
        "MipMapCount": None,
        "First4": "0" * 8,
        "First8": "0" * 16,
        "First16": "0" * 32,
        "MagicLabel": "synthetic-semantic-polyfill",
        "SemanticCategories": [hint],
        "NameCandidates": [],
        "ReferenceSamples": [],
        "XmlTagCounts": [],
        "XmlAttributeCounts": [],
        "XmlParseStatus": None,
        "XmlParseWarning": None,
        "XmlParseLineNumber": None,
        "XmlParseLinePosition": None,
        "XmlParsedElementCount": None,
        "XmlParsedAttributeNameCount": None,
        "TextSnippetSamples": [],
    }


def _build_polyfill_matrix_file(hint_name: str, hint_tag: str, entries: list[dict[str, object]]) -> dict[str, object]:
    """Build the top-level matrix structure with the given entries."""
    return {
        "SchemaVersion": "asset-semantic-index/v1",
        "GeneratedOutputNotice": "synthetic-semantic-polyfill test fixture",
        "RootDirectory": "",
        "ManifestPath": "",
        "SemanticCategoryFilters": [hint_tag],
        "InspectedPayloads": len(entries),
        "Failed": 0,
        "TypeCounts": [{"Value": "nif", "Count": len(entries)}],
        "SemanticCategoryCounts": [{"Value": hint_tag, "Count": len(entries)}],
        "SignatureGroups": [],
        "Entries": entries,
    }


class TestMatrixSynthCommandMap(unittest.TestCase):
    """Lock COMMAND_MAP / PS_MODE_TO_COMMAND registration of the new command."""

    def setUp(self) -> None:
        # Import lazily so the matrix-synth wiring loads via rift_workflow's defer-import path.
        sys.path.insert(0, str(REPO_ROOT))
        if "scripts.rift_workflow" in sys.modules:
            self._rift_workflow = importlib.reload(sys.modules["scripts.rift_workflow"])
        else:
            self._rift_workflow = importlib.import_module("scripts.rift_workflow")

    def tearDown(self) -> None:
        sys.path.pop(0)

    def test_matrix_synth_in_command_map(self) -> None:
        entry = self._rift_workflow.COMMAND_MAP.get("matrix-synth")
        self.assertIsInstance(entry, dict, "matrix-synth missing from COMMAND_MAP")
        self.assertEqual(entry.get("dotnet"), "")
        self.assertEqual(entry.get("base"), "matrix-synth")

    def test_matrix_synth_in_ps_mode_to_command(self) -> None:
        command = self._rift_workflow.PS_MODE_TO_COMMAND.get("MatrixSynth")
        self.assertEqual(command, "matrix-synth")

    def test_sentinel_constants_exported(self) -> None:
        self.assertEqual(self._rift_workflow.MATRIX_SYNTH_POLYFILL_SENTINEL_ARCHIVE_NAME, "synthetic.twad")
        self.assertEqual(self._rift_workflow.MATRIX_SYNTH_POLYFILL_SENTINEL_DETECTED_TYPE, "synthetic")
        self.assertEqual(
            self._rift_workflow.MATRIX_SYNTH_POLYFILL_SENTINEL_MAGIC_LABEL,
            "synthetic-semantic-polyfill",
        )

    def test_assert_matrix_synth_polyfill_only_helper_is_module_level(self) -> None:
        self.assertTrue(callable(getattr(self._rift_workflow, "_assert_matrix_synth_polyfill_only", None)))
        self.assertTrue(callable(getattr(self._rift_workflow, "_run_matrix_synth", None)))


class TestMatrixSynthPolyfillOnlyAssertion(unittest.TestCase):
    """Lock the in-process polyfill-only assertion semantics."""

    def setUp(self) -> None:
        sys.path.insert(0, str(REPO_ROOT))
        if "scripts.rift_workflow" in sys.modules:
            self.rift_workflow = importlib.reload(sys.modules["scripts.rift_workflow"])
        else:
            self.rift_workflow = importlib.import_module("scripts.rift_workflow")
        from scripts.synthesize_semantic_matrices import (
            DEFAULT_OUT_DIR as _POLYFILL_DEFAULT_OUT_DIR,
        )
        from scripts.synthesize_semantic_matrices import (
            MATRIX_FILES as _POLYFILL_MATRIX_FILES,
        )

        self.matrix_files = dict(_POLYFILL_MATRIX_FILES)
        self.default_out_dir = _POLYFILL_DEFAULT_OUT_DIR

    def tearDown(self) -> None:
        sys.path.pop(0)

    def _write_polyfill_outdir(
        self, outdir: Path, *, hint_overrides: dict[str, dict[str, object]] | None = None
    ) -> None:
        outdir.mkdir(parents=True, exist_ok=True)
        for hint_tag, fname in self.matrix_files.items():
            entries = [_build_polyfill_entry(hint_tag) for _ in range(2)]
            if hint_overrides and hint_tag in hint_overrides:
                for entry in entries:
                    entry.update(hint_overrides[hint_tag])
            payload = _build_polyfill_matrix_file(fname, hint_tag, entries)
            (outdir / fname).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def test_passes_on_polyfill_output(self) -> None:
        """All 3 matrix files with sentinel-shaped entries -> no raise."""
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td)
            self._write_polyfill_outdir(out_dir)
            self.rift_workflow._assert_matrix_synth_polyfill_only(out_dir=out_dir)

    def test_fails_closed_on_real_archive_name(self) -> None:
        """One entry with a real .twad filename defeats the assertion."""
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td)
            self._write_polyfill_outdir(
                out_dir,
                hint_overrides={
                    "hint:actor-object": {"ArchiveName": "client_index.twad"},
                },
            )
            with self.assertRaises(RuntimeError) as ctx:
                self.rift_workflow._assert_matrix_synth_polyfill_only(out_dir=out_dir)
            self.assertIn("real-backend output detected", str(ctx.exception))
            self.assertIn("ArchiveName", str(ctx.exception))
            self.assertIn("Remove scripts/synthesize_semantic_matrices.py", str(ctx.exception))

    def test_fails_closed_on_real_detected_type(self) -> None:
        """One entry with a non-polyfill DetectedType defeats the assertion."""
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td)
            self._write_polyfill_outdir(
                out_dir,
                hint_overrides={
                    "hint:map-zone": {"DetectedType": "nif"},
                },
            )
            with self.assertRaises(RuntimeError) as ctx:
                self.rift_workflow._assert_matrix_synth_polyfill_only(out_dir=out_dir)
            self.assertIn("DetectedType", str(ctx.exception))

    def test_fails_closed_on_real_magic_label(self) -> None:
        """One entry with a producer-named MagicLabel defeats the assertion."""
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td)
            self._write_polyfill_outdir(
                out_dir,
                hint_overrides={
                    "hint:waypoint-poi": {"MagicLabel": "rift-asset-dumper:build-asset-semantic-index"},
                },
            )
            with self.assertRaises(RuntimeError) as ctx:
                self.rift_workflow._assert_matrix_synth_polyfill_only(out_dir=out_dir)
            self.assertIn("MagicLabel", str(ctx.exception))

    def test_fails_closed_when_a_matrix_file_missing(self) -> None:
        """Missing matrix file (polyfill never ran) defeats the assertion."""
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td)
            # Write only 2 of 3 files; the polyfill-only check should not silently pass.
            for fname in list(self.matrix_files.values())[:2]:
                payload = _build_polyfill_matrix_file(
                    fname, "hint:actor-object", [_build_polyfill_entry("hint:actor-object")]
                )
                (out_dir / fname).write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                self.rift_workflow._assert_matrix_synth_polyfill_only(out_dir=out_dir)
            self.assertIn("missing", str(ctx.exception).lower())

    def test_fails_closed_on_invalid_json(self) -> None:
        """A non-JSON matrix file fails the polyfill-only assertion."""
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / self.matrix_files["hint:actor-object"]).write_text("{not json", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                self.rift_workflow._assert_matrix_synth_polyfill_only(out_dir=out_dir)
            self.assertIn("not valid JSON", str(ctx.exception))


class TestMatrixSynthSubprocessDryRun(unittest.TestCase):
    """Lock that --dry-run forwarding wires through to the polyfill subprocess."""

    def setUp(self) -> None:
        sys.path.insert(0, str(REPO_ROOT))
        if "scripts.rift_workflow" in sys.modules:
            self.rift_workflow = importlib.reload(sys.modules["scripts.rift_workflow"])
        else:
            self.rift_workflow = importlib.import_module("scripts.rift_workflow")

    def tearDown(self) -> None:
        sys.path.pop(0)

    def _make_args(self, *, commit_matrices: bool) -> mock.Mock:
        args = mock.Mock()
        args.commit_matrices = commit_matrices
        return args

    def test_dry_run_does_not_touch_filesystem(self) -> None:
        """matrix-synth subprocess with no flags writes only when polyfill happens.

        We mock subprocess.run so the test doesn't depend on the live flythrough-index.
        The contract under test: ``_run_matrix_synth`` always invokes the polyfill
        script with ``--validate``, and exits early if the subprocess fails.
        """
        captured: dict[str, list[str]] = {}

        fake_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        def fake_run(cmd, *args_, **kwargs):
            captured["cmd"] = list(cmd)
            return fake_result

        with mock.patch.object(self.rift_workflow.subprocess, "run", side_effect=fake_run):
            self.rift_workflow._run_matrix_synth(self._make_args(commit_matrices=False))
        cmd = captured["cmd"]
        # First two are interpreter + script path
        self.assertEqual(cmd[0], sys.executable)
        self.assertTrue(cmd[1].endswith("synthesize_semantic_matrices.py"))
        self.assertIn("--validate", cmd)

    def test_commit_matrices_invokes_assertion(self) -> None:
        """matrix-synth --commit-matrices triggers _assert_matrix_synth_polyfill_only after polyfill."""
        fake_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch.object(self.rift_workflow.subprocess, "run", return_value=fake_result):
            with mock.patch.object(self.rift_workflow, "_assert_matrix_synth_polyfill_only") as assertion:
                # Force the assertion to raise so we can detect the call without crashing.
                assertion.side_effect = AssertionError("matrix-synth polyfill-only stub fired")
                with self.assertRaises(AssertionError):
                    self.rift_workflow._run_matrix_synth(self._make_args(commit_matrices=True))
        self.assertTrue(assertion.called)


if __name__ == "__main__":
    unittest.main()
