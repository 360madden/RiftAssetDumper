"""Lock BOM-tolerance contract for link_flythrough_textures.load_links().

Cycle 3 texture fusion (2026-06-20): per-asset C# link-nif-textures emits JSONL
files each prefixed with a UTF-8 BOM (EF BB BF). Concatenating 10 such files
into flythrough-texture-links.jsonl planted a BOM at byte 0 AND 9 mid-stream
BOMs between lines. load_links() must tolerate both.

This test writes a JSONL with a leading BOM AND a mid-stream BOM, then asserts
that load_links() returns the expected number of parsed entries.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_bom_corrupted_jsonl(path: Path) -> None:
    """Write a JSONL with one leading BOM + one mid-stream BOM."""
    rec_a = {"ModelIdPrefix": "03bcfae6561407a1", "Reference": "alpha.dds", "Confidence": 100}
    rec_b = {"ModelIdPrefix": "b89ced7d511388d2", "Reference": "lighthouse.dds", "Confidence": 100}
    rec_c = {"ModelIdPrefix": "9f32d26c425ed264", "Reference": "shrub.dds", "Confidence": 100}
    # First line: leading BOM (mimics C# file write of concatenated JSONL)
    # Second line: clean
    # Third line: with leftover mid-stream BOM (mimics second C# concat)
    body = (
        b"\xef\xbb\xbf"
        + json.dumps(rec_a).encode("utf-8")
        + b"\n"
        + json.dumps(rec_b).encode("utf-8")
        + b"\n"
        + b"\xef\xbb\xbf"
        + json.dumps(rec_c).encode("utf-8")
        + b"\n"
    )
    path.write_bytes(body)


def test_load_links_tolerates_leading_and_mid_stream_boms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """load_links() must return all 3 records even with BOMs at byte 0 and mid-file."""
    from scripts import link_flythrough_textures

    links_path = tmp_path / "flythrough-texture-links.jsonl"
    _write_bom_corrupted_jsonl(links_path)

    # Patch the module's LINKS_PATH to point at our fixture
    monkeypatch.setattr(link_flythrough_textures, "LINKS_PATH", links_path)

    links = link_flythrough_textures.load_links()

    assert len(links) == 3, f"Expected 3 records but got {len(links)} — load_links() did not tolerate BOMs."
    refs = sorted(rec["Reference"] for rec in links)
    assert refs == ["alpha.dds", "lighthouse.dds", "shrub.dds"], (
        f"Parsed references not in expected order/decode: {refs}"
    )
    # Confidence survived the BOM-prefixed JSON.loads round-trip
    for link in links:
        assert link["Confidence"] == 100


def test_load_links_tolerates_clean_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression guard: BOM-clean JSONL behaviour unchanged."""
    from scripts import link_flythrough_textures

    rec = {"ModelIdPrefix": "cleanasset0000000", "Reference": "clean.dds", "Confidence": 100}
    links_path = tmp_path / "clean.jsonl"
    links_path.write_text(json.dumps(rec) + "\n", encoding="utf-8")

    monkeypatch.setattr(link_flythrough_textures, "LINKS_PATH", links_path)

    links = link_flythrough_textures.load_links()
    assert len(links) == 1
    assert links[0]["ModelIdPrefix"] == "cleanasset0000000"
