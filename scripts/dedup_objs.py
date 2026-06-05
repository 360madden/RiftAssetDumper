#!/usr/bin/env python3
"""Safe OBJ duplicate cleaner — deduplicates exports by (asset_id, mesh_block).

Groups OBJ files by (asset_id, mesh_block) key extracted from path patterns,
keeps the largest file per group, and removes SHA256-verified duplicates.

Default mode is dry-run (reports what would be deleted).
Use --execute to actually delete duplicates.

Usage:
    python scripts/dedup_objs.py                  # Dry-run: report duplicates
    python scripts/dedup_objs.py --execute        # Delete duplicates
    python scripts/dedup_objs.py --json report.json  # Write structured report
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OBJ_ROOT = REPO_ROOT / "Exports"


def extract_key(path: Path) -> tuple[str, str] | None:
    """Extract (asset_id, mesh_block) key from an OBJ path.

    Handles patterns:
      - decode-nif-geometry-{ID}-mesh{N}.obj
      - decode-nif-geometry-{ID}.json/decode-nif-geometry-mesh{N}.obj
      - decode-264-{variant}/mesh{N}.obj
    """
    path_str = str(path)
    m = re.search(r"decode-nif-geometry-([0-9a-f]{16})", path_str)
    if not m:
        m = re.search(r"decode-264-([0-9a-f]{16})", path_str)
    if not m:
        return None
    aid = m.group(1)

    mb_match = re.search(r"-mesh(\d+)\.", path_str)
    if not mb_match:
        mb_match = re.search(r"mesh(\d+)\.obj$", path_str)
    mb = mb_match.group(1) if mb_match else "?"

    return (aid, mb)


def compute_sha256(path: Path) -> str:
    """Compute SHA256 hash of a file's contents."""
    sha = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def find_duplicates(obj_root: Path) -> dict[tuple[str, str], list[Path]]:
    """Find duplicate OBJ files grouped by (asset_id, mesh_block).

    Returns dict mapping key -> list of paths where len > 1 indicates duplicates.
    Only includes OBJs in decode-nif-geometry or decode-264 directories.
    """
    all_objs = sorted(p for p in obj_root.rglob("*.obj") if p.is_file())

    by_key: dict[tuple[str, str], list[Path]] = defaultdict(list)
    no_key_count = 0

    for path in all_objs:
        key = extract_key(path)
        if key is None:
            no_key_count += 1
            continue
        by_key[key].append(path)

    if no_key_count > 0:
        print(f"  ({no_key_count} OBJs could not be keyed — skipped)", file=sys.stderr)

    return {k: v for k, v in by_key.items() if len(v) > 1}


def analyze_duplicates(
    by_key: dict[tuple[str, str], list[Path]],
) -> tuple[list[dict[str, Any]], int, int, list[dict[str, Any]]]:
    """Analyze duplicates: keep largest per SHA256-identical group, report conflicts.

    Returns (deletions list, total_to_delete, total_bytes_freed, warnings list).
    Only deletes SHA256-identical duplicates (true duplicates).
    Files with same (aid, mb) key but different content are reported as warnings
    (different export runs) and NOT deleted.
    """
    deletions: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    total_to_delete = 0
    total_bytes = 0

    for (aid, mb), paths in sorted(by_key.items()):
        # SHA256-verify: group files by content hash
        hashes: dict[str, list[Path]] = defaultdict(list)
        for p in paths:
            h = compute_sha256(p)
            hashes[h].append(p)

        if len(hashes) == 1:
            # All files identical — true duplicates, keep largest
            sorted_paths = sorted(paths, key=lambda p: p.stat().st_size, reverse=True)
            keeper = sorted_paths[0]
            for p in sorted_paths[1:]:
                size = p.stat().st_size
                deletions.append({
                    "action": "delete",
                    "asset_id": aid,
                    "mesh_block": mb,
                    "path": str(p.relative_to(REPO_ROOT)),
                    "size": size,
                    "sha256": list(hashes.keys())[0],
                    "reason": f"true duplicate of {keeper.relative_to(REPO_ROOT)}",
                })
                total_to_delete += 1
                total_bytes += size
        else:
            # Hash mismatch — files with same (aid, mb) but different content
            # These are different export runs, NOT safe to delete
            # Keep one per hash group, warn about the rest
            for h, h_paths in hashes.items():
                h_sorted = sorted(h_paths, key=lambda p: p.stat().st_size, reverse=True)
                h_keeper = h_sorted[0]
                for p in h_sorted[1:]:
                    size = p.stat().st_size
                    deletions.append({
                        "action": "delete",
                        "asset_id": aid,
                        "mesh_block": mb,
                        "path": str(p.relative_to(REPO_ROOT)),
                        "size": size,
                        "sha256": h,
                        "reason": f"hash-group duplicate of {h_keeper.relative_to(REPO_ROOT)}",
                    })
                    total_to_delete += 1
                    total_bytes += size
            # Warn about content-mismatched groups (different export runs)
            warnings.append({
                "asset_id": aid,
                "mesh_block": mb,
                "hash_groups": len(hashes),
                "total_files": len(paths),
                "sha256s": list(hashes.keys()),
                "message": (
                    f"Found {len(hashes)} different content versions for same "
                    f"(aid={aid}, mb={mb}). Different export runs — only "
                    "duplicates WITHIN each hash group will be deleted."
                ),
            })

    return deletions, total_to_delete, total_bytes, warnings


def execute_deletions(deletions: list[dict[str, Any]]) -> int:
    """Delete duplicate files. Returns count of successfully deleted files."""
    deleted = 0
    for d in deletions:
        if d["action"] != "delete":
            continue
        path = REPO_ROOT / d["path"]
        try:
            path.unlink()
            deleted += 1
        except OSError as exc:
            print(f"  ERROR deleting {d['path']}: {exc}", file=sys.stderr)
    return deleted


def print_report(
    deletions: list[dict[str, Any]],
    total_groups: int,
    total_to_delete: int,
    total_bytes: int,
    warnings: list[dict[str, Any]] | None = None,
    dry_run: bool = True,
) -> None:
    """Pretty-print duplicate report."""
    mode = "DRY-RUN" if dry_run else "EXECUTED"
    print()
    print("=" * 80)
    print(f"  OBJ Duplicate Cleaner — {mode}")
    print("=" * 80)
    print()
    print(f"  Duplicate groups found:  {total_groups}")
    print(f"  Files to delete:         {total_to_delete}")
    print(f"  Space to reclaim:        {total_bytes:,} bytes ({total_bytes // 1024:,} KB)")
    print()

    # Show content-mismatch warnings first
    if warnings:
        print(f"  WARNINGS ({len(warnings)} groups with different content versions):")
        for w in warnings:
            print(f"    [!] {w['asset_id']} mb={w['mesh_block']}: {w['hash_groups']} versions, {w['total_files']} files")
            print("        These are different export runs — only hash-group duplicates deleted.")
        print()

    if not deletions:
        print("  [OK] No duplicates found.")
        print()
        return

    # Group by asset_id for concise display
    by_aid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in deletions:
        by_aid[d["asset_id"]].append(d)

    for aid, group in sorted(by_aid.items()):
        total = sum(d["size"] for d in group)
        mbs = sorted(set(d["mesh_block"] for d in group))
        print(f"  {aid}: {len(group)} duplicate(s), {total:,} B, MBs={mbs}")
        for d in group[:3]:
            print(f"    -> {d['path']} ({d['size']:,}B)")
        if len(group) > 3:
            print(f"    ... and {len(group) - 3} more")

    if dry_run:
        print()
        print("  Run with --execute to delete these files.")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safe OBJ duplicate cleaner — deduplicates exports by (asset_id, mesh_block)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete duplicates (default: dry-run only)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="Write structured report to JSON file",
    )
    parser.add_argument(
        "--obj-root",
        type=Path,
        default=DEFAULT_OBJ_ROOT,
        help=f"Root directory for OBJ files (default: {DEFAULT_OBJ_ROOT})",
    )
    args = parser.parse_args()

    obj_root = args.obj_root
    if not obj_root.exists():
        print(f"ERROR: OBJ root not found: {obj_root}", file=sys.stderr)
        sys.exit(1)

    # Find duplicates
    print("Scanning for duplicates...")
    by_key = find_duplicates(obj_root)
    total_groups = len(by_key)

    if total_groups == 0:
        print("  No duplicate groups found.")
        return

    # Analyze
    deletions, total_to_delete, total_bytes, warnings = analyze_duplicates(by_key)

    # Report
    print_report(deletions, total_groups, total_to_delete, total_bytes, warnings, dry_run=not args.execute)

    # Execute if requested
    if args.execute and deletions:
        print(f"Deleting {total_to_delete} duplicate files...")
        deleted = execute_deletions(deletions)
        print(f"  Deleted: {deleted}/{total_to_delete}")
        if deleted != total_to_delete:
            print(f"  WARNING: {total_to_delete - deleted} files could not be deleted.", file=sys.stderr)
            sys.exit(1)

    # Write JSON report
    if args.json:
        report = {
            "schema": "dedup-report/v1",
            "mode": "executed" if args.execute else "dry-run",
            "total_groups": total_groups,
            "total_to_delete": total_to_delete,
            "total_bytes": total_bytes,
            "warnings": warnings,
            "deletions": deletions,
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"  Report written: {args.json}")


if __name__ == "__main__":
    main()
