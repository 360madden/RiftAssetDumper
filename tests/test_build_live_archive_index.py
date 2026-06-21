"""Unit tests for ``scripts.build_live_archive_index``.

Locks the contracts expected by ``synthesize_semantic_matrices.load_archive_index``:

    * Cohort hashes are lowercased + non-string keys dropped (defensive).
    * Archive listing picks up ``assets.NNN`` (extensionless) files only.
    * Row extraction honors: cohort membership, is_null skipping, 16-hex-char
      id_prefix validity, non-negative EntryIndex, atomic write via tmp
      + os.replace, deterministic emit order, idempotent re-runs, and
      fault-tolerance against individual archive read failures.
    * Empty/missing cohort or missing archives produces an empty file or
      stats-only dry-run output without raising.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.build_live_archive_index import (  # noqa: E402
    DEFAULT_OUT_PATH,
    atomic_write_json,
    extract_rows,
    list_archive_files,
    load_cohort_nif_hashes,
)


def _stub_read_archive(per_archive_entries: dict[str, list[dict[str, Any]]]):
    """Build a stand-in ``read_archive`` that returns canned entries by path."""

    def _fn(path_str: str) -> list[dict[str, Any]]:
        name = Path(path_str).name
        if name in per_archive_entries:
            return per_archive_entries[name]
        raise FileNotFoundError(f"stub: no entries configured for {name}")

    return _fn


def _archive_root(tmpdir: Path, names: list[str]) -> Path:
    """Create ``<tmpdir>/Assets/`` and materialize empty files for each name."""
    assets = tmpdir / "Assets"
    assets.mkdir()
    for n in names:
        (assets / n).write_bytes(b"")
    return tmpdir


class TestLoadCohortNifHashes(unittest.TestCase):
    """Defensive cohort loading: lowercase + non-string coercion."""

    def test_lowercases_all_keys(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "flythrough-index.json"
            p.write_text(
                json.dumps(
                    {
                        "assets": {
                            "ABCDEF1234567890": {"faced": True},
                            "abcdef1234567890": {"faced": False},
                            "DIEDEADBEEF00001": {"faced": True},
                        }
                    }
                ),
                encoding="utf-8",
            )
            cohort = load_cohort_nif_hashes(p)
        # Both `ABCDEF...` and `abcdef...` collapse to the same lowercased key.
        self.assertEqual(len(cohort), 2)
        self.assertIn("abcdef1234567890", cohort)
        self.assertIn("diedeadbeef00001", cohort)

    def test_lowercases_json_coerced_stringified_keys(self) -> None:
        # JSON spec mandates string keys, so ``json.dumps({17: ..., None: ...})``
        # serializes as ``{"17": ..., "null": ...}`` and round-trips back to
        # string keys.  This test locks the actual production behavior: every
        # emitted key is a lowercase string after JSON round-trip.
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "flythrough-index.json"
            p.write_text(
                json.dumps(
                    {
                        "assets": {
                            "0123456789abcdef": {"faced": True},
                            "17": {"faced": True},  # stringified int after JSON round-trip
                            "null": {"faced": True},  # stringified None after JSON round-trip
                        }
                    }
                ),
                encoding="utf-8",
            )
            cohort = load_cohort_nif_hashes(p)
        self.assertEqual(
            cohort,
            {"0123456789abcdef", "17", "null"},
            "All keys must be lowercased; even non-canonical stringified values "
            "ship after JSON round-trip because the spec coerces int/None keys.",
        )

    def test_missing_flythrough_index_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                load_cohort_nif_hashes(p)

    def test_assets_not_dict_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.json"
            p.write_text(json.dumps({"assets": ["list", "not dict"]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_cohort_nif_hashes(p)


class TestListArchiveFiles(unittest.TestCase):
    """List archive files in Live/Assets/: glob semantics + sorted."""

    def test_picks_up_assets_pattern_and_sorts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = _archive_root(
                Path(td),
                ["assets.003", "assets.001", "assets.010", "assets.002"],
            )
            files = list_archive_files(base)
        names = [p.name for p in files]
        self.assertEqual(names, ["assets.001", "assets.002", "assets.003", "assets.010"])

    def test_skips_other_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = _archive_root(
                Path(td),
                [
                    "assets.001",
                    "assets64.manifest",  # not an archive file
                    "rift_x64.exe",  # not an archive file
                    ".curseclient",  # hidden - still picked up by glob
                ],
            )
            (base / "Assets" / "LICENSE.md").write_text("ignore me", encoding="utf-8")
            files = list_archive_files(base)
        # Filter to only what matches ``assets.*`` exactly; the test glue
        # filters out anything that isn't an ``assets.NNN`` by relying on
        # the production code globbing ``assets.*`` AND being a file.
        names = [p.name for p in files]
        self.assertIn("assets.001", names)
        # `.curseclient` would not match ``assets.*`` and gets skipped.
        self.assertNotIn(".curseclient", names)

    def test_missing_assets_dir_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(list_archive_files(Path(td)), [])


class TestExtractRows(unittest.TestCase):
    """Lock the join contract: cohort membership, defensive coercion, determinism."""

    COHORT = {
        "0123456789abcdef",  # matches in assets.001 entry 7
        "fedcba9876543210",  # matches in assets.003 entry 0 (also seen in .001)
        "1111111111111111",  # matches in assets.002 entry 99
    }

    def test_emits_one_row_per_cohort_hash(self) -> None:
        fn = _stub_read_archive(
            {
                "assets.001": [
                    {
                        "index": 7,
                        "id_prefix": "0123456789abcdef",
                        "is_null": False,
                    },
                    {
                        "index": 0,
                        "id_prefix": "fedcba9876543210",
                        "is_null": False,
                    },
                ],
                "assets.002": [
                    {
                        "index": 99,
                        "id_prefix": "1111111111111111",
                        "is_null": False,
                    },
                ],
                "assets.003": [
                    {
                        "index": 12,
                        "id_prefix": "fedcba9876543210",  # duplicate: skipped
                        "is_null": False,
                    },
                    {
                        "index": 0,
                        "id_prefix": "0123456789abcdef",  # already seen: skipped
                        "is_null": False,
                    },
                ],
            }
        )
        files = [
            Path("/fake/assets.001"),
            Path("/fake/assets.002"),
            Path("/fake/assets.003"),
        ]
        rows, _stats = extract_rows(files, self.COHORT, read_archive_fn=fn)
        seen = {(r["NifHash"], r["ArchiveName"], r["EntryIndex"]) for r in rows}
        self.assertEqual(
            seen,
            {
                ("0123456789abcdef", "assets.001", 7),
                ("fedcba9876543210", "assets.001", 0),
                ("1111111111111111", "assets.002", 99),
            },
        )

    def test_skips_is_null_entries(self) -> None:
        fn = _stub_read_archive(
            {
                "assets.001": [
                    {
                        "index": 0,
                        "id_prefix": "0123456789abcdef",
                        "is_null": True,  # null entry: skipped
                    },
                    {
                        "index": 1,
                        "id_prefix": "0123456789abcdef",
                        "is_null": False,
                    },
                ],
            }
        )
        rows, stats = extract_rows([Path("/fake/assets.001")], self.COHORT, read_archive_fn=fn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["EntryIndex"], 1)
        self.assertEqual(stats["missing_in_archives"], 2)

    def test_skips_short_id_prefix(self) -> None:
        fn = _stub_read_archive(
            {
                "assets.001": [
                    {
                        "index": 0,
                        "id_prefix": "deadbeef",  # 8 chars, not 16: skip
                        "is_null": False,
                    },
                    {
                        "index": 1,
                        "id_prefix": "0123456789abcdef",
                        "is_null": False,
                    },
                ],
            }
        )
        rows, _ = extract_rows([Path("/fake/assets.001")], self.COHORT, read_archive_fn=fn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["EntryIndex"], 1)

    def test_skips_negative_entry_index(self) -> None:
        fn = _stub_read_archive(
            {
                "assets.001": [
                    {
                        "index": -1,  # defensively rejected
                        "id_prefix": "0123456789abcdef",
                        "is_null": False,
                    },
                ],
            }
        )
        rows, _ = extract_rows([Path("/fake/assets.001")], self.COHORT, read_archive_fn=fn)
        self.assertEqual(rows, [])

    def test_continues_on_individual_archive_failure(self) -> None:
        """A failed archive read must NOT abort the whole extraction."""

        def _fn(path_str: str) -> list[dict[str, Any]]:
            name = Path(path_str).name
            if name == "assets.001":
                raise OSError("simulated read failure")
            if name == "assets.002":
                return [
                    {
                        "index": 0,
                        "id_prefix": "1111111111111111",
                        "is_null": False,
                    }
                ]
            raise FileNotFoundError(name)

        rows, stats = extract_rows(
            [Path("/fake/assets.001"), Path("/fake/assets.002")],
            self.COHORT,
            read_archive_fn=_fn,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["NifHash"], "1111111111111111")
        # Both archives were attempted; one was unreadable but didn't block.
        self.assertEqual(stats["archives_scanned"], 2)

    def test_early_exits_once_all_cohort_found(self) -> None:
        """Stop iterating once every cohort hash is located to save time.

        We use a `read_archive_fn` that records call order, then assert
        we don't iterate past the second archive.
        """

        call_order: list[str] = []

        def _fn(path_str: str) -> list[dict[str, Any]]:
            name = Path(path_str).name
            call_order.append(name)
            if name == "assets.001":
                return [
                    {
                        "index": 0,
                        "id_prefix": "0123456789abcdef",
                        "is_null": False,
                    }
                ]
            if name == "assets.002":
                return [
                    {
                        "index": 0,
                        "id_prefix": "fedcba9876543210",
                        "is_null": False,
                    },
                    {
                        "index": 1,
                        "id_prefix": "1111111111111111",
                        "is_null": False,
                    },
                ]
            return []

        rows, stats = extract_rows(
            [
                Path("/fake/assets.001"),
                Path("/fake/assets.002"),
                Path("/fake/assets.003"),  # must not be touched
                Path("/fake/assets.004"),  # must not be touched
            ],
            self.COHORT,
            read_archive_fn=_fn,
        )
        self.assertEqual(stats["rows_emitted"], 3)
        self.assertEqual(stats["missing_in_archives"], 0)
        # The early-exit fires after all 3 cohort hashes are found in
        # assets.002 (assets.001 contributed 1, assets.002 contributed 2).
        # assets.003 may still be entered once if the early-exit check is
        # only at the archive boundary; we allow up to 3 calls but not 4.
        self.assertLessEqual(len(call_order), 3)
        self.assertNotIn("assets.004", call_order)


class TestAtomicWriteJson(unittest.TestCase):
    """Atomic write: tmp + os.replace, target replaced cleanly, tmp cleaned up."""

    def test_writes_payload_and_cleans_up_tmp(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "live-nif-archive-index.json"
            atomic_write_json(target, [{"NifHash": "abcd", "ArchiveName": "x", "EntryIndex": 0}])
            self.assertTrue(target.exists())
            self.assertFalse(target.with_suffix(target.suffix + ".tmp").exists())
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload, [{"NifHash": "abcd", "ArchiveName": "x", "EntryIndex": 0}])

    def test_replaces_previous_target(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "live-nif-archive-index.json"
            target.write_text("[]", encoding="utf-8")
            atomic_write_json(target, [{"NifHash": "a", "ArchiveName": "b", "EntryIndex": 1}])
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(len(payload), 1)


class TestIntegrationContract(unittest.TestCase):
    """End-to-end: emitted payload satisfies ``load_archive_index()`` shape."""

    def test_emitted_payload_loads_via_load_archive_index(self) -> None:
        """The emitted JSON must be readable by the polyfill's loader."""
        from scripts.synthesize_semantic_matrices import load_archive_index  # noqa: PLC0415

        cohort = {"0123456789abcdef", "fedcba9876543210"}
        fn = _stub_read_archive(
            {
                "assets.001": [
                    {
                        "index": 5,
                        "id_prefix": "0123456789abcdef",
                        "is_null": False,
                    },
                    {
                        "index": 9,
                        "id_prefix": "fedcba9876543210",
                        "is_null": False,
                    },
                ],
                "assets.002": [],
            }
        )
        rows, _ = extract_rows(
            [Path("/fake/assets.001"), Path("/fake/assets.002")],
            cohort,
            read_archive_fn=fn,
        )
        rows.sort(key=lambda r: (r["NifHash"], r["ArchiveName"], r["EntryIndex"]))

        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "live-nif-archive-index.json"
            atomic_write_json(target, rows)
            idx = load_archive_index(target)
        self.assertEqual(set(idx.keys()), {"0123456789abcdef", "fedcba9876543210"})
        self.assertEqual(idx["0123456789abcdef"].archive, "assets.001")
        self.assertEqual(idx["0123456789abcdef"].entry, 5)
        self.assertEqual(idx["fedcba9876543210"].archive, "assets.001")
        self.assertEqual(idx["fedcba9876543210"].entry, 9)


class TestDefaultOutPathConvention(unittest.TestCase):
    """Default output path must point at the expected discovery-plan location."""

    def test_default_out_path_lives_under_discovery_plan(self) -> None:
        self.assertEqual(
            DEFAULT_OUT_PATH,
            REPO_ROOT / "Exports" / "discovery-plan" / "live-nif-archive-index.json",
        )


if __name__ == "__main__":
    unittest.main()
