#!/usr/bin/env python3
"""FT-1.2: Texture dump driver for the RiftFlythrough build pipeline.

Reads the FT-1.1 DDS candidate inventory, extracts unique DDS payloads from
the live archive via the C# extract-archives command, deduplicates by SHA1,
and writes a deduplicated manifest.

Usage:
    python scripts/dump_textures_for_flythrough.py --limit 5 --dry-run
    python scripts/dump_textures_for_flythrough.py --limit 50
    python scripts/dump_textures_for_flythrough.py --full

Outputs:
    Assets/build/flythrough/textures/extracted/<asset_id>.dds
    Assets/build/flythrough/textures/extracted-manifest.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = REPO_ROOT / "Assets" / "build" / "flythrough" / "evidence" / "ft1.1" / "dds-inventory.json"
DEFAULT_OUT = REPO_ROOT / "Assets" / "build" / "flythrough" / "textures" / "extracted"
DEFAULT_MANIFEST = REPO_ROOT / "Assets" / "build" / "flythrough" / "textures" / "extracted-manifest.json"
DEFAULT_DOTNET_PROJECT = REPO_ROOT / "src" / "RiftAssetDumper" / "RiftAssetDumper.csproj"
DEFAULT_LIVE_ROOT = Path("C:/Program Files (x86)/Glyph/Games/RIFT/Live")


def compute_sha1(path: Path) -> str:
    """Return the SHA1 hex digest of a file's bytes."""
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def dedupe_by_sha1(payloads: list[tuple[str, Path]]) -> dict[str, dict[str, Any]]:
    """Return sha1 -> {sha1, first_source, sources, count, size_bytes}.

    Skips entries whose file does not exist. The first observed source for a
    given hash becomes the `first_source`; subsequent collisions are appended
    to `sources`.
    """
    out: dict[str, dict[str, Any]] = {}
    for source_id, path in payloads:
        if not isinstance(path, Path):
            path = Path(path)
        if not path.exists():
            continue
        sha1 = compute_sha1(path)
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        if sha1 not in out:
            out[sha1] = {
                "sha1": sha1,
                "first_source": source_id,
                "sources": [source_id],
                "count": 1,
                "size_bytes": size,
            }
        else:
            entry = out[sha1]
            entry["sources"].append(source_id)
            entry["count"] += 1
    return out


def extract_one(
    asset_id: str,
    out_dir: Path,
    project: Path,
    root: Path,
    *,
    dry_run: bool = False,
    timeout_sec: int = 120,
) -> Path | None:
    """Extract one asset via the C# extract-archives command.

    Returns the extracted file path, or None on failure. In dry-run mode,
    writes a small placeholder file so dedup logic can be exercised without
    invoking .NET.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{asset_id}.dds"
    if dry_run:
        target.write_bytes(b"DRYRUN-PLACEHOLDER")
        return target
    if not shutil.which("dotnet"):
        print(f"  [skip] dotnet not on PATH; cannot extract {asset_id}", file=sys.stderr)
        return None
    args = [
        "dotnet",
        "run",
        "--project",
        str(project),
        "--no-build",
        "--",
        "extract-archives",
        "--root",
        str(root),
        "--id",
        asset_id,
        "--out",
        str(out_dir),
    ]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        print(f"  [timeout] extract-archives for {asset_id} after {timeout_sec}s", file=sys.stderr)
        return None
    except Exception as exc:  # pragma: no cover - defensive
        print(f"  [error] extract-archives for {asset_id}: {exc}", file=sys.stderr)
        return None
    if result.returncode != 0:
        print(f"  [rc={result.returncode}] extract-archives for {asset_id}", file=sys.stderr)
        return None
    return target if target.exists() else None


def get_candidate_hashes(inventory_path: Path) -> list[str]:
    """Read the FT-1.1 inventory and return candidate asset IDs to extract.

    The inventory's `DdsSignatureGroups[].Archive` carries archive-level IDs.
    The `TopArchives[].Archive` carries archive identifiers. Both are
    collected, deduped, and returned in a stable order.
    """
    if not inventory_path.exists():
        raise FileNotFoundError(f"Inventory not found: {inventory_path}")
    with open(inventory_path, encoding="utf-8-sig") as f:
        data = json.load(f)
    seen: set[str] = set()
    out: list[str] = []
    for group in data.get("DdsSignatureGroups", []) or []:
        if not isinstance(group, dict):
            continue
        group_type = str(group.get("Type", "")).lower()
        if group_type and group_type != "dds":
            continue
        archive = group.get("Archive")
        if isinstance(archive, str) and archive and archive not in seen:
            seen.add(archive)
            out.append(archive)
    for row in data.get("TopArchives", []) or []:
        if not isinstance(row, dict):
            continue
        archive = row.get("Archive")
        if isinstance(archive, str) and archive and archive not in seen:
            seen.add(archive)
            out.append(archive)
    return out


def _now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="FT-1.2: Texture dump driver")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--project", type=Path, default=DEFAULT_DOTNET_PROJECT)
    parser.add_argument("--root", type=Path, default=DEFAULT_LIVE_ROOT)
    parser.add_argument("--limit", type=int, default=10, help="Max candidates to process (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual .NET extraction")
    parser.add_argument("--timeout", type=int, default=120, help="Per-asset extract timeout (sec)")
    args = parser.parse_args()

    candidates = get_candidate_hashes(args.inventory)
    if args.limit > 0:
        candidates = candidates[: args.limit]
    print(f"FT-1.2: {len(candidates)} candidates (limit={args.limit}, dry_run={args.dry_run})")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[tuple[str, Path]] = []
    stats = {
        "candidates": len(candidates),
        "extracted": 0,
        "failed": 0,
        "skipped": 0,
    }
    for asset_id in candidates:
        print(f"  extracting {asset_id}...")
        path = extract_one(
            asset_id,
            args.output_dir,
            args.project,
            args.root,
            dry_run=args.dry_run,
            timeout_sec=args.timeout,
        )
        if path is None:
            stats["failed"] += 1
        else:
            stats["extracted"] += 1
            extracted.append((asset_id, path))

    deduped = dedupe_by_sha1(extracted)
    stats["unique"] = len(deduped)
    stats["dedup_ratio"] = round(stats["extracted"] / max(1, stats["unique"]), 3)

    manifest = {
        "SchemaVersion": "flythrough-deduped-texture-manifest/v1",
        "GeneratedAt": _now_iso(),
        "SourceInventory": str(args.inventory.relative_to(REPO_ROOT)).replace("\\", "/"),
        "Stats": stats,
        "Entries": list(deduped.values()),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"FT-1.2 manifest: {args.manifest}")
    print(f"FT-1.2 stats: {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
