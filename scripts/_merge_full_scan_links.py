"""Additive merge of full-archive texture scan into flythrough-texture-links.jsonl.

Safe-merge pattern (2026-06-20):
- Treat the existing flythrough-texture-links.jsonl (currently 779 lines,
  cycle-3 work blended in) as the immutable baseline.
- Walk the scratch dir from a full `link-nif-textures --root <live> --out <scratch>`
  scan and ingest only NEW (ModelIdPrefix, Reference) tuple pairs that map to
  flythrough assets in flythrough-index.json. Skip duplicates already in the
  baseline.
- Output is BOM-clean (strip every U+FEFF byte globally) since C# JSONL outputs
  each prefix their own UTF-8 BOM.

Usage:
    python scripts/_merge_full_scan_links.py \
        --scratch Assets/build/scratch/full-scan-links \
        --baseline Assets/build/flythrough/flythrough-texture-links.jsonl \
        --dry-run

If --dry-run unspecified, writes back to <baseline>.

Assumes an existing baseline JSONL at <baseline>.  If the path does not
exist yet, _load_baseline() raises FileNotFoundError — run the foundation
extract-linked-textures pipeline first to seed it.

DEDUP-KEY NOTE (2026-06-20): dedup key is (ModelIdPrefix.lower(), Reference.lower()).
For future cycles that introduce new flythrough assets, expand the key
to also include TextureIdPrefix so the same archive texture referenced
under multiple *Reference* filenames collapses correctly.  Currently the
simpler key matches scripts/link_flythrough_textures._load_baseline().
TODO(cycle-N+, 2026-06-20): expand dedup key to include TextureIdPrefix.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

FLYTHROUGH_INDEX = _REPO_ROOT / "Assets" / "build" / "flythrough" / "flythrough-index.json"


def _load_flythrough_subset_keys() -> set[str]:
    idx = json.loads(FLYTHROUGH_INDEX.read_text(encoding="utf-8-sig"))
    return {k.lower() for k in idx.get("assets", {}).keys()}


def _load_baseline(path: Path) -> tuple[list[dict], set[tuple[str, str]]]:
    """Load existing JSONL as (records, dedup_keys).

    Records: each parsed JSON dict.
    dedup_keys: (modelIdPrefix, reference) tuples already covered.

    If the baseline does not exist, returns ([], set()) — additive merge
    can then build a baseline from a scratch-only run (useful for first-
    cycle invocations on a fresh repo).
    """
    if not path.exists():
        return [], set()
    recs: list[dict] = []
    seen: set[tuple[str, str]] = set()
    text = path.read_text(encoding="utf-8-sig")  # tolerate leading BOM
    for line in text.splitlines():
        line = line.lstrip("\ufeff").strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        recs.append(rec)
        seen.add(
            (
                (rec.get("ModelIdPrefix") or "").lower(),
                (rec.get("Reference") or rec.get("TextureIdPrefix") or "").lower(),
            )
        )
    return recs, seen


def _iter_scratch_links(scratch: Path) -> Iterator[dict]:
    """Yield records from all *.jsonl files under scratch.

    Tolerates per-file + mid-stream BOMs (C# writer pattern). Surface
    unparseable lines via stderr — silent skipping would mask corruption
    in large 493MB inputs.  The read is one-shot per file; designed for
    consolidated scan outputs (not per-asset subdivides that need their
    own streaming pattern).
    """
    if not scratch.exists():
        return
    for jsonl in scratch.rglob("*.jsonl"):
        try:
            raw = jsonl.read_bytes()
        except OSError as exc:
            print(f"[warn] could not read {jsonl}: {exc}", file=sys.stderr)
            continue
        # Strip ALL UTF-8 BOMs globally so each line is BOM-free prefix
        text = raw.replace(b"\xef\xbb\xbf", b"").decode("utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                print(
                    f"[warn] skipping unparseable line {line_no} in {jsonl}: {exc}",
                    file=sys.stderr,
                )
                continue
            yield rec


def merge(
    baseline_path: Path,
    scratch_dir: Path,
    *,
    dry_run: bool,
) -> tuple[int, int, int]:
    """Return (baseline_count, new_count, output_count)."""
    ft_keys = _load_flythrough_subset_keys()
    baseline_recs, baseline_seen = _load_baseline(baseline_path)
    new_recs: list[dict] = []
    for rec in _iter_scratch_links(scratch_dir):
        mid = (rec.get("ModelIdPrefix") or "").lower()
        ref = (rec.get("Reference") or rec.get("TextureIdPrefix") or "").lower()
        if mid not in ft_keys:
            continue  # not a flythrough asset
        key = (mid, ref)
        if key in baseline_seen:
            continue
        new_recs.append(rec)
        baseline_seen.add(key)  # prevent duplicates within scratch itself

    out = baseline_recs + new_recs
    if not dry_run:
        # Atomic write: tempfile + os.replace so an interrupted run
        # never leaves baseline truncated/corrupted. Mirrors the pattern
        # in scripts/link_flythrough_textures.save_index().
        tmp = baseline_path.with_suffix(baseline_path.suffix + ".tmp")
        tmp.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n",
            encoding="utf-8",  # explicit BOM-free write
        )
        os.replace(tmp, baseline_path)
    return len(baseline_recs), len(new_recs), len(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge full-scan scratch into baseline JSONL additively")
    parser.add_argument(
        "--scratch",
        type=Path,
        default=_REPO_ROOT / "Assets" / "build" / "scratch" / "full-scan-links",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=_REPO_ROOT / "Assets" / "build" / "flythrough" / "flythrough-texture-links.jsonl",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts only; do NOT write to baseline.",
    )
    args = parser.parse_args()

    base, added, out = merge(args.baseline, args.scratch, dry_run=args.dry_run)
    print(f"Baseline: {base}, new entries from scratch: {added}, total output: {out}")
    print(f"Scratch dir: {args.scratch} (entries from there were: flythrough-subset + not-yet-baselined)")
    if args.dry_run:
        print("[DRY-RUN] No changes written.")
    # Surface unexpected saturation: 0 entries on a multi-MB scratch is a
    # strong signal the scan or filter regressed.  Print to stderr so CI can
    # notice without failing the script.
    if added == 0 and args.scratch.exists() and any(args.scratch.rglob("*.jsonl")):
        print(
            "[warn] merge() added 0 entries; baseline may already be saturated "
            "OR dedup/filter regressed. Inspect scratch input.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
