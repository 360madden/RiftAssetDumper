"""Extract NIF files from live RIFT TWAD archives, handling LZMA2 decompression.

Usage:
    python scripts/extract_live_nifs.py --archive 50 --max 200 --out Exports/live-nifs-050
    python scripts/extract_live_nifs.py --archive 53 --max 200 --out Exports/live-nifs-053
"""

import os
import sys
import json
import struct
import lzma
import zlib
import hashlib
import argparse
from pathlib import Path

LIVE_ROOT = "C:/Program Files (x86)/Glyph/Games/RIFT/Live"
ARCHIVE_ENTRY_SIZE = 44
ARCHIVE_HEADER_SIZE = 0x14


def read_archive_entry(data: bytes, offset: int, index: int) -> dict:
    """Read a single archive entry (44 bytes) at the given offset."""
    entry_data = data[offset:offset + ARCHIVE_ENTRY_SIZE]
    id_bytes = entry_data[0:8]
    data_offset = struct.unpack_from("<I", entry_data, 8)[0]
    size = struct.unpack_from("<I", entry_data, 12)[0]
    streamed_or_unknown = struct.unpack_from("<I", entry_data, 16)[0]
    next_raw = struct.unpack_from("<H", entry_data, 20)[0]
    compression = struct.unpack_from("<H", entry_data, 22)[0]
    sha1 = entry_data[24:44].hex()

    is_null = all(b == 0 for b in id_bytes) and data_offset == 0 and size == 0

    return {
        "index": index,
        "id_prefix": id_bytes.hex(),
        "offset": data_offset,
        "size": size,
        "compression": compression,
        "next_raw": next_raw,
        "sha1": sha1,
        "is_null": is_null,
    }


def decompress_payload(entry: dict, packed: bytes) -> bytes | None:
    """Decompress an archive entry payload."""
    comp = entry["compression"]

    if comp == 0:
        return packed

    if comp == 1:
        try:
            return zlib.decompress(packed)
        except zlib.error:
            try:
                return zlib.decompress(packed, -zlib.MAX_WBITS)
            except zlib.error:
                return None

    if comp == 2:
        try:
            # RIFT uses LZMA2 with a custom envelope (4 bytes uncompressed size + LZMA2 stream)
            if len(packed) < 4:
                return None
            # Try stripping 4-byte uncompressed size prefix
            uncomp_size = struct.unpack_from("<I", packed, 0)[0]
            lzma2_data = packed[4:]
            if uncomp_size > 0 and uncomp_size < 10 * 1024 * 1024:  # 10MB sanity
                return lzma.decompress(lzma2_data)
            # Try direct LZMA2 without prefix
            return lzma.decompress(packed)
        except lzma.LZMAError:
            try:
                return lzma.decompress(packed)
            except lzma.LZMAError:
                return None

    return None  # Unknown compression


NIF_MAGIC_BYTES = {
    b"Gamebryo",
    b"NetImmerse",
    b"NS2000",
}


def is_nif_magic(data: bytes) -> bool:
    """Check if data starts with NIF magic bytes."""
    if len(data) < 8:
        return False
    for magic in NIF_MAGIC_BYTES:
        if data[:len(magic)] == magic:
            return True
    return False


def read_archive(archive_path: str) -> list[dict]:
    """Read all entries from a TWAD archive file."""
    with open(archive_path, "rb") as f:
        data = f.read()

    if len(data) < ARCHIVE_HEADER_SIZE:
        print(f"  ERROR: archive too small: {len(data)} bytes")
        return []

    magic = data[0:4].decode("ascii", errors="replace")
    if magic != "TWAD":
        print(f"  ERROR: invalid magic '{magic}'")
        return []

    version = struct.unpack_from("<I", data, 4)[0]
    header_size = struct.unpack_from("<I", data, 8)[0]
    max_entries = struct.unpack_from("<I", data, 12)[0]
    first_linked = struct.unpack_from("<I", data, 16)[0]

    table_offset = header_size
    readable_entries = min(max_entries, (len(data) - table_offset) // ARCHIVE_ENTRY_SIZE)

    entries = []
    for i in range(readable_entries):
        entry = read_archive_entry(data, table_offset + i * ARCHIVE_ENTRY_SIZE, i)
        entries.append(entry)

    return entries


def extract_nifs_from_archive(
    archive_path: str,
    archive_name: str,
    out_dir: str,
    max_count: int = 200,
) -> list[dict]:
    """Extract NIF files from a live TWAD archive."""
    print(f"\n=== Processing {archive_name} ===")

    with open(archive_path, "rb") as f:
        data = f.read()

    entries = read_archive_entry_table(data)
    if entries is None:
        print(f"  ERROR: could not read entry table")
        return []

    nif_found = 0
    nif_entries = []
    scanned = 0
    failures = 0

    for entry in entries:
        if nif_found >= max_count:
            break
        if entry["is_null"]:
            continue

        scanned += 1

        try:
            # Read compressed payload
            if entry["offset"] + entry["size"] > len(data):
                failures += 1
                continue

            packed = data[entry["offset"]:entry["offset"] + entry["size"]]
            payload = decompress_payload(entry, packed)
            if payload is None:
                failures += 1
                continue

            if not is_nif_magic(payload):
                continue

            nif_found += 1
            nif_entries.append(entry)

            # Write NIF file
            nif_name = f"{entry['id_prefix']}.nif"
            nif_path = os.path.join(out_dir, nif_name)
            with open(nif_path, "wb") as out_f:
                out_f.write(payload)

            if nif_found <= 3 or nif_found % 50 == 0:
                print(f"  [{nif_found}/{max_count}] entry={entry['index']} id={entry['id_prefix']} "
                      f"comp={entry['compression']} size={len(payload)}")

        except Exception as e:
            failures += 1
            if failures <= 5:
                print(f"  WARN: entry {entry['index']} failed: {e}")

    print(f"\n  Done: {nif_found} NIFs extracted, {scanned} scanned, {failures} failures")
    return nif_entries


def read_archive_entry_table(data: bytes) -> list[dict] | None:
    """Read entry table from archive data."""
    if len(data) < ARCHIVE_HEADER_SIZE:
        return None

    magic = data[0:4].decode("ascii", errors="replace")
    if magic != "TWAD":
        return None

    header_size = struct.unpack_from("<I", data, 8)[0]
    max_entries = struct.unpack_from("<I", data, 12)[0]

    table_offset = header_size
    readable_entries = min(max_entries, (len(data) - table_offset) // ARCHIVE_ENTRY_SIZE)

    if readable_entries <= 0:
        return []

    entries = []
    for i in range(readable_entries):
        entry = read_archive_entry(data, table_offset + i * ARCHIVE_ENTRY_SIZE, i)
        entries.append(entry)

    return entries


def main():
    parser = argparse.ArgumentParser(description="Extract NIFs from live RIFT TWAD archives")
    parser.add_argument("--archive", type=int, required=True, help="Archive number (e.g. 50, 53)")
    parser.add_argument("--max", type=int, default=200, help="Max NIFs to extract")
    parser.add_argument("--out", type=str, help="Output directory (default: Exports/live-nifs-<archive>)")
    parser.add_argument("--live-root", type=str, default=LIVE_ROOT, help="Live RIFT root")
    args = parser.parse_args()

    assets_dir = os.path.join(args.live_root, "Assets")
    archive_name = f"assets.{args.archive:03d}"
    archive_path = os.path.join(assets_dir, archive_name)

    if not os.path.isfile(archive_path):
        print(f"ERROR: archive not found: {archive_path}")
        sys.exit(1)

    out_dir = args.out or os.path.join("Exports", f"live-nifs-{args.archive:03d}")
    nif_dir = os.path.join(out_dir, "Assets")
    os.makedirs(nif_dir, exist_ok=True)

    archive_size = os.path.getsize(archive_path)
    print(f"Archive: {archive_name} ({archive_size:,} bytes)")
    print(f"Output: {nif_dir}")

    nif_entries = extract_nifs_from_archive(archive_path, archive_name, nif_dir, args.max)

    # Write manifest
    manifest = {
        "archive": archive_name,
        "archive_path": archive_path,
        "nif_count": len(nif_entries),
        "nif_entries": [
            {"index": e["index"], "id_prefix": e["id_prefix"], "compression": e["compression"]}
            for e in nif_entries
        ],
    }
    manifest_path = os.path.join(out_dir, "extract-manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nTotal NIFs: {len(nif_entries)}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
