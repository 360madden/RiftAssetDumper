"""Lock the dedup-merge contract for scripts/_merge_full_scan_links.py.

This test builds a minimal handcrafted flythrough-index.json + baseline +
scratch fixture on tmp_path, then asserts the four core invariants of the
additive merge:

1. Baseline entries already covered → not duplicated (dedup works).
2. Genuinely-new scratch entries that are in flythrough-subset → appended.
3. Out-of-subset scratch entries → excluded.
4. Atomic write: scratch view sees tmp file created and replaced (no
   partial-truncation surface for an interrupted run).

These lock the design intent of the merge utility so a regression in the
filter / dedup / atomic-write path can never silently lose flythrough-subset
texture references (the cost is felt by RiftFlythrough's visual fidelity).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_jsonl(path: Path, records: list[dict]) -> None:
    """Write JSONL with one line per record (no trailing newline concerns)."""
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
                    encoding="utf-8")


def _make_flythrough_index(index_path: Path, asset_ids: list[str]) -> None:
    """Write a minimal flythrough-index.json holding the given asset keys."""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"schema": "test", "assets": {aid: {} for aid in asset_ids}}
    index_path.write_text(json.dumps(doc), encoding="utf-8")


def test_merge_dedups_existing_and_appends_new(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """baseline dedup + new append + out-of-subset skip + atomic write."""
    from scripts import _merge_full_scan_links

    # Minimal flythrough-subset of 2 assets
    ft_keys = ["aaa11aaa11aaa11a", "bbb22bbb22bbb22b"]
    _make_flythrough_index(
        tmp_path / "flythrough-index.json",
        ft_keys,
    )
    monkeypatch.setattr(_merge_full_scan_links, "FLYTHROUGH_INDEX",
                        tmp_path / "flythrough-index.json")

    # Baseline holds two already-covered entries (one per asset)
    baseline = tmp_path / "flythrough-texture-links.jsonl"
    _write_jsonl(baseline, [
        {"ModelIdPrefix": "aaa11aaa11aaa11a", "Reference": "alpha.dds"},
        {"ModelIdPrefix": "bbb22bbb22bbb22b", "Reference": "beta.dds"},
    ])

    # Scratch holds:
    #   - one duplicate of "alpha.dds" (should be ignored)
    #   - one NEW entry for asset bbb (gamma.dds — should be appended)
    #   - one OUT-OF-SUBSET entry for a different model
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True)
    _write_jsonl(scratch_dir / "scratch.jsonl", [
        {"ModelIdPrefix": "aaa11aaa11aaa11a", "Reference": "alpha.dds"},   # dup
        {"ModelIdPrefix": "bbb22bbb22bbb22b", "Reference": "gamma.dds"},   # new
        {"ModelIdPrefix": "xxx99xxx99xxx99x", "Reference": "stray.dds"},   # oos
    ])

    # Real merge
    base, added, out = _merge_full_scan_links.merge(baseline, scratch_dir, dry_run=False)
    assert base == 2
    assert added == 1, f"Expected 1 new entry, got {added}"
    assert out == 3, f"Expected 3 lines total in output, got {out}"

    # Verify the written content
    lines = baseline.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    refs = sorted(json.loads(rec)["Reference"] for rec in lines)
    assert refs == ["alpha.dds", "beta.dds", "gamma.dds"], (
        f"Dedup/append mismatch; expected sorted [alpha, beta, gamma], got {refs}"
    )
    # Verify the out-of-subset entry was correctly filtered out
    assert all(
        json.loads(rec)["ModelIdPrefix"] != "xxx99xxx99xxx99x"
        for rec in lines
    ), "Out-of-subset entry leaked into baseline"


def test_merge_tolerates_bom_in_scratch_and_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mid-stream + leading BOMs in JSONL inputs must not break dedup."""
    from scripts import _merge_full_scan_links

    _make_flythrough_index(tmp_path / "flythrough-index.json", ["aaa11aaa11aaa11a"])
    monkeypatch.setattr(_merge_full_scan_links, "FLYTHROUGH_INDEX",
                        tmp_path / "flythrough-index.json")

    baseline = tmp_path / "flythrough-texture-links.jsonl"
    baseline.write_bytes(b"\xef\xbb\xbf" + b'{"ModelIdPrefix": "aaa11aaa11aaa11a", "Reference": "alpha.dds"}\n')

    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True)
    # First line clean, second line BOM-prefixed
    scratch_file = scratch_dir / "bom.jsonl"
    scratch_file.write_bytes(
        b'{"ModelIdPrefix": "aaa11aaa11aaa11a", "Reference": "beta.dds"}\n'
        + b"\xef\xbb\xbf" + b'{"ModelIdPrefix": "aaa11aaa11aaa11a", "Reference": "gamma.dds"}\n'
    )

    base, added, out = _merge_full_scan_links.merge(baseline, scratch_dir, dry_run=False)
    assert base == 1
    assert added == 2, f"Both BOM-tolerant entries should have been added; got {added}"
    assert out == 3


def test_merge_dry_run_does_not_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """dry-run must keep baseline bytes unchanged."""
    from scripts import _merge_full_scan_links

    _make_flythrough_index(tmp_path / "flythrough-index.json", ["aaa11aaa11aaa11a"])
    monkeypatch.setattr(_merge_full_scan_links, "FLYTHROUGH_INDEX",
                        tmp_path / "flythrough-index.json")

    baseline = tmp_path / "flythrough-texture-links.jsonl"
    _write_jsonl(baseline, [{"ModelIdPrefix": "aaa11aaa11aaa11a", "Reference": "alpha.dds"}])

    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True)
    _write_jsonl(scratch_dir / "fresh.jsonl", [
        {"ModelIdPrefix": "aaa11aaa11aaa11a", "Reference": "beta.dds"},
    ])

    before = baseline.read_text(encoding="utf-8")
    base, added, out = _merge_full_scan_links.merge(baseline, scratch_dir, dry_run=True)
    after = baseline.read_text(encoding="utf-8")
    assert before == after, "dry-run mutated the baseline on disk"
    assert added == 1  # dry-run still returns the count

    # Crucially: no leftover *.tmp file from atomic-write machinery
    leftover = list(tmp_path.glob("**/*.tmp"))
    assert not leftover, f"dry-run left temp files behind: {leftover}"


def test_merge_logs_unparseable_lines_to_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Corrupt lines in scratch JSONL must surface to stderr, not silently skip."""
    from scripts import _merge_full_scan_links

    _make_flythrough_index(tmp_path / "flythrough-index.json", ["aaa11aaa11aaa11a"])
    monkeypatch.setattr(_merge_full_scan_links, "FLYTHROUGH_INDEX",
                        tmp_path / "flythrough-index.json")

    baseline = tmp_path / "flythrough-texture-links.jsonl"
    _write_jsonl(baseline, [{"ModelIdPrefix": "aaa11aaa11aaa11a", "Reference": "alpha.dds"}])

    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True)
    # Mixed: one valid line + one corrupted JSON + one valid line
    (scratch_dir / "mixed.jsonl").write_text(
        '{"ModelIdPrefix": "aaa11aaa11aaa11a", "Reference": "beta.dds"}\n'
        'NOT VALID JSON !!\n'
        '{"ModelIdPrefix": "aaa11aaa11aaa11a", "Reference": "gamma.dds"}\n',
        encoding="utf-8",
    )

    base, added, _ = _merge_full_scan_links.merge(baseline, scratch_dir, dry_run=False)
    assert base == 1
    assert added == 2  # both valid lines added, the bad one skipped
    captured = capsys.readouterr()
    assert "skipping unparseable line" in captured.err, (
        f"Expected JSONDecodeError stderr-log, got: {captured.err!r}"
    )
    assert "mixed.jsonl" in captured.err, "stderr log should name the file"


def test_merge_emits_saturation_warning_on_zero_new_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Saturated-baseline (0 new entries on populated scratch) must warn to stderr."""
    from scripts import _merge_full_scan_links

    _make_flythrough_index(tmp_path / "flythrough-index.json", ["aaa11aaa11aaa11a"])
    monkeypatch.setattr(_merge_full_scan_links, "FLYTHROUGH_INDEX",
                        tmp_path / "flythrough-index.json")

    baseline = tmp_path / "flythrough-texture-links.jsonl"
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True)
    # Baseline already covers the only scratch entry — saturation case
    _write_jsonl(baseline, [{"ModelIdPrefix": "aaa11aaa11aaa11a", "Reference": "alpha.dds"}])
    _write_jsonl(scratch_dir / "scratch.jsonl", [
        {"ModelIdPrefix": "aaa11aaa11aaa11a", "Reference": "alpha.dds"},
    ])

    # Drive via main() so the saturation-warning code path runs
    monkeypatch.setattr("sys.argv",
                        ["_merge_full_scan_links",
                         "--baseline", str(baseline),
                         "--scratch", str(scratch_dir),
                         "--dry-run"])
    rc = _merge_full_scan_links.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "added 0 entries" in captured.err, (
        f"Saturation regression: expected stderr warning, got: {captured.err!r}"
    )


def test_merge_cleans_up_tmp_file_on_atomic_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`.tmp` file from atomic write must be replaced, not left behind."""
    from scripts import _merge_full_scan_links

    _make_flythrough_index(tmp_path / "flythrough-index.json", ["aaa11aaa11aaa11a"])
    monkeypatch.setattr(_merge_full_scan_links, "FLYTHROUGH_INDEX",
                        tmp_path / "flythrough-index.json")

    baseline = tmp_path / "flythrough-texture-links.jsonl"
    _write_jsonl(baseline, [{"ModelIdPrefix": "aaa11aaa11aaa11a", "Reference": "alpha.dds"}])

    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True)
    _write_jsonl(scratch_dir / "fresh.jsonl", [
        {"ModelIdPrefix": "aaa11aaa11aaa11a", "Reference": "beta.dds"},
    ])

    _merge_full_scan_links.merge(baseline, scratch_dir, dry_run=False)
    leftover = list(tmp_path.glob("**/*.tmp"))
    assert not leftover, f"atomic-write left temp files behind: {leftover}"
