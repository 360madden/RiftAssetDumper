"""Unit tests for scripts/dump_textures_for_flythrough.py — FT-1.2 dedup + FT-1.3 PNG conversion.

Covers the acceptance criteria for both sub-steps:
- FT-1.2: dedup by SHA1, keep unique, skip missing files, candidate-hash reader
- FT-1.3: build_png_name naming, sanitize_basename, is_valid_png, run_smoke all_pass
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest  # noqa: F401

# Add scripts/ to import path without requiring a package install
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from dump_textures_for_flythrough import (  # noqa: E402
    build_png_name,
    compute_sha1,
    dedupe_by_sha1,
    get_candidate_hashes,
    is_valid_png,
    run_smoke,
    sanitize_basename,
)


def _write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# --- FT-1.2 tests ---


def test_dedupe_by_sha1_merges_identical_payloads() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        a = _write(tmp / "a.dds", b"identical-payload-bytes")
        b = _write(tmp / "b.dds", b"identical-payload-bytes")
        result = dedupe_by_sha1([("hash-a", a), ("hash-b", b)])
        assert len(result) == 1
        entry = next(iter(result.values()))
        assert entry["count"] == 2
        assert sorted(entry["sources"]) == ["hash-a", "hash-b"]


def test_dedupe_by_sha1_keeps_distinct_payloads() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        a = _write(tmp / "a.dds", b"unique-payload-A")
        b = _write(tmp / "b.dds", b"unique-payload-B")
        c = _write(tmp / "c.dds", b"unique-payload-C")
        result = dedupe_by_sha1([("hash-a", a), ("hash-b", b), ("hash-c", c)])
        assert len(result) == 3
        assert sum(e["count"] for e in result.values()) == 3
        sha1s = {e["sha1"] for e in result.values()}
        assert compute_sha1(a) in sha1s


def test_dedupe_by_sha1_skips_missing_files() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        existing = _write(tmp / "exists.dds", b"only-real-file")
        missing = tmp / "does-not-exist.dds"
        result = dedupe_by_sha1([("hash-existing", existing), ("hash-missing", missing)])
        assert len(result) == 1
        entry = next(iter(result.values()))
        assert entry["first_source"] == "hash-existing"
        assert "hash-missing" not in entry["sources"]


def test_get_candidate_hashes_reads_inventory_groups() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        inv = Path(tmpdir) / "inv.json"
        inv.write_text(
            json.dumps(
                {
                    "DdsSignatureGroups": [
                        {"Type": "dds", "Archive": "alpha"},
                        {"Type": "dds", "Archive": "beta"},
                        {"Type": "non-dds", "Archive": "should-skip"},
                    ],
                    "TopArchives": [
                        {"Archive": "beta"},
                        {"Archive": "gamma"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = get_candidate_hashes(inv)
        assert result == ["alpha", "beta", "gamma"]


# --- FT-1.3 tests ---


def test_sanitize_basename_lowercases_and_strips_unsafe() -> None:
    assert sanitize_basename("Hello World!.dds") == "hello_world_dds"
    assert sanitize_basename("Foo/Bar\\Baz") == "foo_bar_baz"
    assert sanitize_basename("___trim___") == "trim"
    assert sanitize_basename("") == ""
    # long input gets truncated
    long = "a" * 200
    out = sanitize_basename(long, max_len=10)
    assert len(out) == 10


def test_build_png_name_canonical_format() -> None:
    sha1 = "abcdef1234567890" + "f" * 24
    name = build_png_name(sha1, "Foo_Bar.dds")
    assert name == "abcdef12_foo_bar.png"
    # Empty basename → just prefix
    assert build_png_name(sha1, "") == "abcdef12.png"
    # Empty sha1 → 'unknown' prefix
    assert build_png_name("", "x") == "unknown_x.png"
    # Path with directory + extension
    assert build_png_name(sha1, "C:/path/to/Texture_001.DDS") == "abcdef12_texture_001.png"


def test_is_valid_png_checks_signature() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # Write a real PNG
        from PIL import Image

        valid = tmp / "valid.png"
        Image.new("RGB", (4, 4), "red").save(valid, format="PNG")
        assert is_valid_png(valid) is True
        # Garbage bytes
        invalid = tmp / "invalid.png"
        invalid.write_bytes(b"not a png at all, just text")
        assert is_valid_png(invalid) is False
        # Empty file
        empty = tmp / "empty.png"
        empty.write_bytes(b"")
        assert is_valid_png(empty) is False
        # Missing file
        assert is_valid_png(tmp / "nope.png") is False


def test_run_smoke_writes_n_pngs_with_pass_status(tmp_path) -> None:
    converted_dir = tmp_path / "converted"
    manifest_path = tmp_path / "converted-manifest.json"
    stats = run_smoke(converted_dir, manifest_path, n_textures=5)
    assert stats["textures"] == 5
    assert stats["naming_ok"] is True
    assert stats["validity_ok"] is True
    assert stats["all_pass"] is True
    # Verify the manifest was written
    assert manifest_path.exists()
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["SchemaVersion"] == "flythrough-converted-png-manifest/v1"
    assert manifest["Mode"] == "smoke"
    assert len(manifest["Entries"]) == 5
    # Verify each PNG file exists, has the right name, and is valid
    for entry in manifest["Entries"]:
        png_path = converted_dir / Path(entry["png_path"]).name
        assert png_path.exists()
        assert png_path.suffix == ".png"
        assert entry["valid_png"] is True
        # Naming format: <8-hex>_<base>.png
        stem = png_path.stem
        assert "_" in stem
        prefix, _ = stem.split("_", 1)
        assert len(prefix) == 8
        assert all(c in "0123456789abcdef" for c in prefix)
