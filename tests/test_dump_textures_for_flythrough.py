"""Unit tests for scripts/dump_textures_for_flythrough.py — FT-1.2 dedup logic.

Covers the three behaviors called out in the FT-1.2 acceptance criteria:
1. Identical payloads collapse to a single SHA1 entry with count > 1
2. Distinct payloads are preserved as separate entries
3. Missing files are skipped silently (no crash, no entry)
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest  # noqa: F401  # used implicitly via tmp_path fixture assertion helpers

# Add scripts/ to import path without requiring a package install
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from dump_textures_for_flythrough import (  # noqa: E402
    compute_sha1,
    dedupe_by_sha1,
    get_candidate_hashes,
)


def _write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_dedupe_by_sha1_merges_identical_payloads() -> None:
    """Two files with identical bytes must collapse to one SHA1 entry with count=2."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        a = _write(tmp / "a.dds", b"identical-payload-bytes")
        b = _write(tmp / "b.dds", b"identical-payload-bytes")
        result = dedupe_by_sha1([("hash-a", a), ("hash-b", b)])
        assert len(result) == 1, f"expected 1 unique SHA1, got {len(result)}"
        entry = next(iter(result.values()))
        assert entry["count"] == 2
        assert sorted(entry["sources"]) == ["hash-a", "hash-b"]
        assert entry["size_bytes"] == len(b"identical-payload-bytes")


def test_dedupe_by_sha1_keeps_distinct_payloads() -> None:
    """Two files with different bytes must remain as two separate SHA1 entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        a = _write(tmp / "a.dds", b"unique-payload-A")
        b = _write(tmp / "b.dds", b"unique-payload-B")
        c = _write(tmp / "c.dds", b"unique-payload-C")
        result = dedupe_by_sha1([("hash-a", a), ("hash-b", b), ("hash-c", c)])
        assert len(result) == 3
        total_count = sum(entry["count"] for entry in result.values())
        assert total_count == 3
        sha1s = {entry["sha1"] for entry in result.values()}
        assert compute_sha1(a) in sha1s
        assert compute_sha1(b) in sha1s
        assert compute_sha1(c) in sha1s


def test_dedupe_by_sha1_skips_missing_files() -> None:
    """A non-existent file must be silently skipped — no entry, no crash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        existing = _write(tmp / "exists.dds", b"only-real-file")
        missing = tmp / "does-not-exist.dds"
        result = dedupe_by_sha1([("hash-existing", existing), ("hash-missing", missing)])
        assert len(result) == 1
        entry = next(iter(result.values()))
        assert entry["first_source"] == "hash-existing"
        assert "hash-missing" not in entry["sources"]
        assert entry["count"] == 1


def test_get_candidate_hashes_reads_inventory_groups() -> None:
    """The candidate-hash reader must dedupe groups + top-archives archives in order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        inv = Path(tmpdir) / "inv.json"
        inv.write_text(
            json.dumps(
                {
                    "DdsSignatureGroups": [
                        {"Archive": "alpha"},
                        {"Archive": "beta"},
                        {"Type": "non-dds", "Archive": "should-skip"},
                    ],
                    "TopArchives": [
                        {"Archive": "beta"},  # already in seen; should not reappear
                        {"Archive": "gamma"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = get_candidate_hashes(inv)
        assert result == ["alpha", "beta", "gamma"]
