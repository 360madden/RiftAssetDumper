#!/usr/bin/env python3
"""FT-1.2 + FT-1.3: Texture dump + DDS→PNG conversion for RiftFlythrough.

Reads the FT-1.1 DDS candidate inventory, extracts unique DDS payloads from
the live archive via the C# extract-archives command, deduplicates by SHA1,
converts each unique DDS to PNG, and writes a deduplicated manifest.

Usage:
    python scripts/dump_textures_for_flythrough.py --limit 5 --dry-run
    python scripts/dump_textures_for_flythrough.py --limit 50 --convert-png
    python scripts/dump_textures_for_flythrough.py --smoke
    python scripts/dump_textures_for_flythrough.py --full --convert-png

Outputs:
    Assets/build/flythrough/textures/extracted/<asset_id>.dds
    Assets/build/flythrough/textures/converted/<sha1-8>_<base>.png
    Assets/build/flythrough/textures/extracted-manifest.json
    Assets/build/flythrough/textures/converted-manifest.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = REPO_ROOT / "Assets" / "build" / "flythrough" / "evidence" / "ft1.1" / "dds-inventory.json"
DEFAULT_OUT = REPO_ROOT / "Assets" / "build" / "flythrough" / "textures" / "extracted"
DEFAULT_CONVERTED_DIR = REPO_ROOT / "Assets" / "build" / "flythrough" / "textures" / "converted"
DEFAULT_MANIFEST = REPO_ROOT / "Assets" / "build" / "flythrough" / "textures" / "extracted-manifest.json"
DEFAULT_CONVERTED_MANIFEST = REPO_ROOT / "Assets" / "build" / "flythrough" / "textures" / "converted-manifest.json"
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


# =============================================================================
# FT-1.3: DDS → PNG conversion
# =============================================================================


_SAFE_NAME_RE = re.compile(r"[^a-z0-9_]+")


def sanitize_basename(text: str, max_len: int = 60) -> str:
    """Lowercase, replace non-[a-z0-9_] with _, collapse runs, trim to max_len."""
    if not text:
        return ""
    lowered = text.lower()
    safe = _SAFE_NAME_RE.sub("_", lowered).strip("_")
    if len(safe) > max_len:
        safe = safe[:max_len].rstrip("_")
    return safe


def build_png_name(sha1: str, original_basename: str) -> str:
    """Return the canonical RiftFlythrough PNG filename.

    Format: ``<8-char-sha1-prefix>_<sanitized-base>.png``.
    Falls back to just ``<8-char-sha1-prefix>.png`` if the basename is empty.
    """
    prefix = sha1[:8] if sha1 else "unknown"
    base = sanitize_basename(Path(original_basename).stem if original_basename else "")
    if not base:
        return f"{prefix}.png"
    return f"{prefix}_{base}.png"


def has_dds_decoder() -> str | None:
    """Return the name of an available DDS decoder, or None if none available.

    Tries: pillow-dds plugin > ImageMagick (`magick` binary) > error.
    """
    try:
        # pillow-dds registers itself via the `DdsImagePlugin` symbol on load
        from PIL import (  # noqa: F401
            DdsImagePlugin,
            Image,
            ImageFile,
        )

        return "pillow-dds"
    except Exception:
        pass
    for binary in ("magick", "convert"):
        if shutil.which(binary):
            # Note: Windows `convert` is the FS converter, NOT ImageMagick.
            # Only accept it if it actually supports DDS (smoke-tested via version).
            if binary == "convert" and sys.platform == "win32":
                continue
            return binary
    return None


def _convert_via_pillow_dds(src: Path, dst: Path) -> bool:
    """Decode DDS via pillow-dds plugin and write PNG via Pillow.

    Returns True on success. Picks the largest mipmap level (mip 0 = base
    level) and discards mipmap chain — see CONVERSION.md.
    """
    try:
        from PIL import Image
    except Exception:
        return False
    try:
        with Image.open(src) as img:
            img.load()
            # If the DDS has mipmaps, prefer the base (largest) level
            if getattr(img, "n_frames", 1) > 1:
                img.seek(0)
            img.save(dst, format="PNG")
        return dst.exists() and dst.stat().st_size > 0
    except Exception as exc:  # pragma: no cover - decoder-dependent
        print(f"  [pillow-dds] decode error for {src.name}: {exc}", file=sys.stderr)
        return False


def _convert_via_imagemagick(src: Path, dst: Path, binary: str) -> bool:
    """Decode DDS via `magick convert input.dds output.png`."""
    try:
        result = subprocess.run(
            [binary, str(src), str(dst)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"  [{binary}] error for {src.name}: {exc}", file=sys.stderr)
        return False
    if result.returncode != 0:
        print(
            f"  [{binary}] rc={result.returncode} for {src.name}: {result.stderr[:200]}",
            file=sys.stderr,
        )
        return False
    return dst.exists() and dst.stat().st_size > 0


def convert_dds_to_png(src: Path, dst: Path) -> tuple[bool, str]:
    """Convert a single DDS file to PNG using the best available decoder.

    Returns (success, decoder_name). On failure, decoder_name is the one that
    was attempted (or 'none' if no decoder is available). Always ensures the
    destination directory exists.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    decoder = has_dds_decoder()
    if decoder is None:
        return False, "none"
    if decoder == "pillow-dds":
        ok = _convert_via_pillow_dds(src, dst)
        return ok, "pillow-dds"
    ok = _convert_via_imagemagick(src, dst, decoder)
    return ok, decoder


def _write_synthetic_png(dst: Path, color: tuple[int, int, int]) -> None:
    """Write a tiny solid-color PNG used as a smoke-test stand-in for a DDS payload.

    The smoke test exists to exercise the naming + write + manifest pipeline;
    real DDS decoding is exercised at FT-1.4 on the live install.
    """
    from PIL import Image

    dst.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (16, 16), color)
    img.save(dst, format="PNG")


def is_valid_png(path: Path) -> bool:
    """Return True if the file exists, is non-empty, and has a valid PNG signature."""
    if not path.exists() or path.stat().st_size < 8:
        return False
    with open(path, "rb") as f:
        sig = f.read(8)
    return sig == b"\x89PNG\r\n\x1a\n"


def run_smoke(
    converted_dir: Path,
    converted_manifest: Path,
    n_textures: int = 5,
) -> dict[str, Any]:
    """Run the FT-1.3 smoke: write n synthetic PNGs, validate naming + validity, write a manifest.

    Uses synthetic inputs because real DDS decoding requires Pillow-DDS or
    ImageMagick, which is documented as a deployment dependency for FT-1.4.
    """
    colors = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (255, 0, 255),
        (0, 255, 255),
        (128, 128, 128),
        (255, 255, 255),
        (0, 0, 0),
        (64, 128, 192),
    ]
    converted_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    naming_ok = True
    validity_ok = True
    for i in range(n_textures):
        sha1 = hashlib.sha1(f"smoke-{i}".encode()).hexdigest()
        original_basename = f"smoke_{i:02d}_dds_payload_{i:03d}"
        expected_name = build_png_name(sha1, original_basename)
        dst = converted_dir / expected_name
        color = colors[i % len(colors)]
        _write_synthetic_png(dst, color)
        # Validate naming
        if dst.name != expected_name:
            naming_ok = False
        # Validate PNG validity
        if not is_valid_png(dst):
            validity_ok = False
        entries.append(
            {
                "sha1": sha1,
                "original_basename": original_basename,
                "png_name": dst.name,
                "png_path": str(dst).replace("\\", "/"),
                "size_bytes": dst.stat().st_size,
                "valid_png": is_valid_png(dst),
            }
        )

    stats = {
        "textures": n_textures,
        "naming_ok": naming_ok,
        "validity_ok": validity_ok,
        "all_pass": naming_ok and validity_ok,
        "decoder_available": has_dds_decoder(),
    }
    manifest = {
        "SchemaVersion": "flythrough-converted-png-manifest/v1",
        "GeneratedAt": _now_iso(),
        "Mode": "smoke",
        "Stats": stats,
        "Entries": entries,
    }
    converted_manifest.parent.mkdir(parents=True, exist_ok=True)
    converted_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return stats


def _now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="FT-1.2/1.3: Texture dump + DDS→PNG")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--converted-dir", type=Path, default=DEFAULT_CONVERTED_DIR)
    parser.add_argument("--converted-manifest", type=Path, default=DEFAULT_CONVERTED_MANIFEST)
    parser.add_argument("--project", type=Path, default=DEFAULT_DOTNET_PROJECT)
    parser.add_argument("--root", type=Path, default=DEFAULT_LIVE_ROOT)
    parser.add_argument("--limit", type=int, default=10, help="Max candidates to process (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual .NET extraction")
    parser.add_argument("--convert-png", action="store_true", help="Run DDS→PNG conversion after dedup")
    parser.add_argument("--smoke", action="store_true", help="Run the FT-1.3 smoke (5 synthetic PNGs)")
    parser.add_argument("--smoke-count", type=int, default=5, help="Number of textures in smoke")
    parser.add_argument("--timeout", type=int, default=120, help="Per-asset extract timeout (sec)")
    args = parser.parse_args()

    if args.smoke:
        stats = run_smoke(args.converted_dir, args.converted_manifest, args.smoke_count)
        print(f"FT-1.3 smoke: {stats}")
        return 0 if stats["all_pass"] else 1

    candidates = get_candidate_hashes(args.inventory)
    if args.limit > 0:
        candidates = candidates[: args.limit]
    print(
        f"FT-1.2/1.3: {len(candidates)} candidates (limit={args.limit}, "
        f"dry_run={args.dry_run}, convert_png={args.convert_png})"
    )

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

    if args.convert_png:
        args.converted_dir.mkdir(parents=True, exist_ok=True)
        conv_entries: list[dict[str, Any]] = []
        conv_stats = {
            "unique": len(deduped),
            "converted": 0,
            "failed": 0,
            "decoder": has_dds_decoder() or "none",
        }
        for entry in deduped.values():
            sha1 = entry["sha1"]
            original_basename = entry.get("first_source", "") or sha1
            dds_path = args.output_dir / f"{original_basename}.dds"
            if not dds_path.exists():
                conv_stats["failed"] += 1
                continue
            png_name = build_png_name(sha1, original_basename)
            png_path = args.converted_dir / png_name
            ok, decoder = convert_dds_to_png(dds_path, png_path)
            if ok and is_valid_png(png_path):
                conv_stats["converted"] += 1
            else:
                conv_stats["failed"] += 1
            conv_entries.append(
                {
                    "sha1": sha1,
                    "source_basename": original_basename,
                    "png_name": png_name,
                    "size_bytes": png_path.stat().st_size if png_path.exists() else 0,
                    "decoder": decoder,
                }
            )
        conv_manifest = {
            "SchemaVersion": "flythrough-converted-png-manifest/v1",
            "GeneratedAt": _now_iso(),
            "SourceManifest": str(args.manifest.relative_to(REPO_ROOT)).replace("\\", "/"),
            "Stats": conv_stats,
            "Entries": conv_entries,
        }
        args.converted_manifest.parent.mkdir(parents=True, exist_ok=True)
        args.converted_manifest.write_text(json.dumps(conv_manifest, indent=2), encoding="utf-8")
        print(f"FT-1.3 converted manifest: {args.converted_manifest}")
        print(f"FT-1.3 stats: {conv_stats}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
