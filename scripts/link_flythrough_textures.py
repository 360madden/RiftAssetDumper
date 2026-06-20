#!/usr/bin/env python3
"""FT: Texture-linking bridge — DDS→PNG conversion + flythrough-index enrichment.

Reads the filtered flythrough texture links, converts each unique DDS to PNG
(via pillow-dds), and populates the ``linked_textures`` field in
``flythrough-index.json`` so RiftFlythrough can consume per-mesh texture data.

Usage:
    python scripts/link_flythrough_textures.py           # convert + populate
    python scripts/link_flythrough_textures.py --dry-run # skip PNG conversion, only populate manifest
    python scripts/link_flythrough_textures.py --status  # show coverage stats

Outputs:
    Assets/build/flythrough/textures/converted/<sha1-8>_<base>.png (new PNGs)
    Assets/build/flythrough/textures/converted-manifest.json (updated)
    Assets/build/flythrough/flythrough-index.json (updated with linked_textures)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Ensure repo root is on sys.path for imports from scripts/ package
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.dump_textures_for_flythrough import (  # noqa: E402
    build_png_name,
    compute_sha1,
)

FLYTHROUGH_ROOT = _REPO_ROOT / "Assets" / "build" / "flythrough"
LINKS_PATH = FLYTHROUGH_ROOT / "flythrough-texture-links.jsonl"
INDEX_PATH = FLYTHROUGH_ROOT / "flythrough-index.json"
DDS_DIR = FLYTHROUGH_ROOT / "textures" / "linked-dds" / "recovered"
CONVERTED_DIR = FLYTHROUGH_ROOT / "textures" / "converted"
CONVERTED_MANIFEST_PATH = FLYTHROUGH_ROOT / "textures" / "converted-manifest.json"


def _convert_dds_to_png(dds_path: Path, png_path: Path) -> bool:
    """Convert a single DDS to PNG via pillow-dds. Returns True on success.

    Thin wrapper around the pillow-dds decoder path from dump_textures_for_flythrough
    with added skip-if-already-converted logic."""
    try:
        from PIL import Image
    except ImportError:
        print(f"  [error] Pillow not available; cannot convert {dds_path.name}", file=sys.stderr)
        return False

    png_path.parent.mkdir(parents=True, exist_ok=True)

    # Skip if already converted and valid
    if png_path.exists():
        try:
            with Image.open(png_path) as img:
                img.verify()
            return True
        except Exception:
            pass  # re-convert

    try:
        with Image.open(dds_path) as img:
            img.load()
            if getattr(img, "n_frames", 1) > 1:
                img.seek(0)
            img.save(png_path, format="PNG")
        return png_path.exists() and png_path.stat().st_size > 0
    except Exception as exc:
        print(f"  [pillow-dds] error for {dds_path.name}: {exc}", file=sys.stderr)
        return False


def _now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z")


def load_links() -> list[dict[str, Any]]:
    """Load flythrough-texture-links.jsonl."""
    if not LINKS_PATH.exists():
        print(f"ERROR: {LINKS_PATH} not found.", file=sys.stderr)
        sys.exit(1)
    links: list[dict[str, Any]] = []
    # BOM-tolerant: utf-8-sig strips leading file BOM; the inline lstrip
    # catches mid-stream BOMs left when concatenated C#-written JSONL files
    # are appended (each retains its own BOM). See scripts/link_flythrough_textures.py
    # docs note on this defensive fix (2026-06-20 cycle 3 texture fusion).
    with open(LINKS_PATH, encoding="utf-8-sig") as f:
        for line in f:
            line = line.lstrip("\ufeff").strip()
            if not line:
                continue
            links.append(json.loads(line))
    return links


def load_index() -> dict[str, Any]:
    """Load flythrough-index.json."""
    if not INDEX_PATH.exists():
        print(f"ERROR: {INDEX_PATH} not found.", file=sys.stderr)
        sys.exit(1)
    with open(INDEX_PATH, encoding="utf-8-sig") as f:
        return json.load(f)


def save_index(idx: dict[str, Any]) -> None:
    """Atomically write flythrough-index.json."""
    tmp = str(INDEX_PATH) + ".tmp"
    # Preserve original encoding (no BOM for clean git diffs)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=2, ensure_ascii=False)
    os.replace(tmp, INDEX_PATH)


def load_converted_manifest() -> dict[str, Any]:
    """Load or initialize converted-manifest.json."""
    if CONVERTED_MANIFEST_PATH.exists():
        with open(CONVERTED_MANIFEST_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {
        "SchemaVersion": "flythrough-converted-png-manifest/v1",
        "GeneratedAt": _now_iso(),
        "Mode": "flythrough-links",
        "Stats": {},
        "Entries": [],
    }


def save_converted_manifest(manifest: dict[str, Any]) -> None:
    """Write converted-manifest.json."""
    CONVERTED_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(CONVERTED_MANIFEST_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONVERTED_MANIFEST_PATH)


def show_status() -> int:
    """Print texture-link coverage stats."""
    links = load_links()
    idx = load_index()
    assets = idx.get("assets", {})

    # Model-level stats
    model_ids = {link["ModelIdPrefix"] for link in links}
    ft_ids = set(assets.keys())
    _overlap = model_ids & ft_ids  # noqa: F841 — computed for clarity
    print(f"Flythrough assets: {len(ft_ids)}")
    print(f"Models with texture links: {len(model_ids & ft_ids)}/{len(ft_ids)}")

    # Currently populated linked_textures
    populated = sum(1 for a in assets.values() if a.get("linked_textures"))
    print(f"Assets with linked_textures populated: {populated}/{len(ft_ids)}")

    # DDS extraction status
    dds_files = list(DDS_DIR.glob("*.dds")) if DDS_DIR.exists() else []
    print(f"Extracted DDS files: {len(dds_files)}")

    # PNG conversion status
    png_files = list(CONVERTED_DIR.glob("*.png")) if CONVERTED_DIR.exists() else []
    print(f"Converted PNG files: {len(png_files)}")

    return 0


def run(*, dry_run: bool = False) -> int:
    """Convert DDS→PNG and populate flythrough-index.json."""
    links = load_links()
    idx = load_index()
    assets: dict[str, Any] = idx.get("assets", {})
    ft_ids = set(assets.keys())

    if not DDS_DIR.exists():
        print(f"ERROR: DDS directory not found: {DDS_DIR}", file=sys.stderr)
        print("Run extract-linked-textures first:", file=sys.stderr)
        print(
            "  dotnet run -- extract-linked-textures --root <live> --input flythrough-texture-links.jsonl",
            file=sys.stderr,
        )
        return 1

    # Build Candidate (lowercase) → DDS filename lookup
    dds_files: dict[str, Path] = {}
    for dds_path in DDS_DIR.glob("*.dds"):
        dds_files[dds_path.name.lower()] = dds_path

    print(f"DDS files available: {len(dds_files)}")

    # Convert unique DDS files to PNG
    cm = load_converted_manifest()
    existing_pngs: dict[str, str] = {}  # sha1 -> png_name from existing manifest
    for entry in cm.get("Entries", []):
        existing_pngs[entry["sha1"]] = entry["png_name"]

    conversion_stats = {"converted": 0, "skipped": 0, "failed": 0, "total_unique": 0}
    candidate_to_png: dict[str, str] = {}  # lowercase candidate → png filename

    # Find all unique candidates linked to flythrough models
    unique_candidates: dict[str, Path] = {}  # lowercase candidate → dds_path
    for link in links:
        mid = link["ModelIdPrefix"]
        if mid not in ft_ids:
            continue
        cand = link["Candidate"].lower()
        if cand in dds_files and cand not in unique_candidates:
            unique_candidates[cand] = dds_files[cand]

    conversion_stats["total_unique"] = len(unique_candidates)
    print(f"Unique DDS to convert: {len(unique_candidates)}")

    for cand_lower, dds_path in sorted(unique_candidates.items()):
        if not dry_run:
            sha1 = compute_sha1(dds_path)
            png_name = build_png_name(sha1, dds_path.name)
            png_path = CONVERTED_DIR / png_name

            if sha1 in existing_pngs:
                candidate_to_png[cand_lower] = existing_pngs[sha1]
                conversion_stats["skipped"] += 1
                continue

            ok = _convert_dds_to_png(dds_path, png_path)
            if ok:
                candidate_to_png[cand_lower] = png_name
                conversion_stats["converted"] += 1
                existing_pngs[sha1] = png_name
                cm["Entries"].append(
                    {
                        "sha1": sha1,
                        "original_basename": dds_path.stem,
                        "png_name": png_name,
                        "png_path": str(png_path.relative_to(FLYTHROUGH_ROOT)).replace("\\", "/"),
                        "size_bytes": png_path.stat().st_size,
                        "valid_png": True,
                    }
                )
            else:
                conversion_stats["failed"] += 1
        else:
            # Dry run: just build the mapping
            candidate_to_png[cand_lower] = f"DRYRUN_{dds_path.stem}.png"

    # Build model-to-png mapping
    model_to_pngs: dict[str, list[str]] = defaultdict(list)
    seen_edges: set[tuple[str, str]] = set()  # deduplicate
    for link in links:
        mid = link["ModelIdPrefix"]
        if mid not in ft_ids:
            continue
        cand = link["Candidate"].lower()
        png = candidate_to_png.get(cand)
        if png is None:
            continue
        edge = (mid, png)
        if edge not in seen_edges:
            seen_edges.add(edge)
            model_to_pngs[mid].append(png)

    # Populate linked_textures in flythrough-index
    populated = 0
    for mid, pngs in model_to_pngs.items():
        if mid in assets:
            assets[mid]["linked_textures"] = sorted(pngs)
            populated += 1

    print(f"\nConversion stats: {conversion_stats}")
    print(f"Models with linked textures: {populated}/{len(ft_ids)}")
    print(f"Models without texture links: {len(ft_ids) - populated}")
    print(f"Total texture assignments: {sum(len(p) for p in model_to_pngs.values())}")

    # Save outputs
    idx["assets"] = assets
    if "texture_count" in idx:
        idx["texture_count"] = len(existing_pngs)

    if not dry_run:
        cm["GeneratedAt"] = _now_iso()
        cm["Stats"] = conversion_stats
        save_converted_manifest(cm)
        print(f"Updated converted-manifest: {CONVERTED_MANIFEST_PATH}")

        save_index(idx)
        print(f"Updated flythrough-index: {INDEX_PATH}")
    else:
        print("\n[DRY-RUN] Index and manifest NOT saved. Remove --dry-run to persist changes.")
        # Show what would be written
        print(f"  Would write: {INDEX_PATH}")
        if conversion_stats["converted"] > 0:
            print(f"  Would update: {CONVERTED_MANIFEST_PATH}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="FT: Texture-linking bridge for RiftFlythrough")
    parser.add_argument("--dry-run", action="store_true", help="Skip PNG conversion, only build mapping")
    parser.add_argument("--status", action="store_true", help="Show coverage stats")
    args = parser.parse_args()

    if args.status:
        return show_status()

    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
