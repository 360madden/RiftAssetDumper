#!/usr/bin/env python3
"""Parse RIFT 0x6906-magic map blob binary format.

These binary blobs were discovered via semantic Phase 1 (hint:map-zone) and
have a consistent structure:

    Magic (2 bytes): 0x6906
    NameLen (1 byte): length of map name
    Name (N bytes): ASCII map name (e.g., "defiant_map", "guardian_map")
    Body (remaining): protobuf-like tag-length-value encoded asset references

Usage:
    python scripts/parse_map_blobs.py --file <raw_blob.bin>
    python scripts/parse_map_blobs.py --hex <first64_hex>
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any

MAP_BLOB_MAGIC = 0x6906


def _decode_length_prefixed_strings(data: bytes, offset: int) -> list[tuple[int, str, int]]:
    """Decode length-prefixed ASCII strings from binary data.

    Returns list of (length_byte_offset, string, str_len) tuples.
    The first element is the offset of the length-prefix byte (not the string itself).
    """
    strings: list[tuple[int, str, int]] = []
    data_len = len(data)

    while offset < data_len:
        if offset + 1 > data_len:
            break
        str_len = data[offset]
        if str_len == 0:
            break
        offset += 1
        if offset + str_len > data_len:
            break
        try:
            s = data[offset : offset + str_len].decode("ascii", errors="replace")
            strings.append((offset - 1, s, str_len))
        except Exception:
            strings.append((offset - 1, repr(data[offset : offset + str_len]), str_len))
        offset += str_len

    return strings


def _decode_protobuf_like(data: bytes, offset: int, max_depth: int = 4) -> list[dict[str, Any]]:
    """Decode protobuf-like tag-length-value records from binary data.

    Each record: tag (1 byte) -> length (1 byte) -> value (N bytes).

    Returns list of {tag, length, value_hex, value_ascii, offset, nested} dicts.
    """
    records: list[dict[str, Any]] = []
    data_len = len(data)

    while offset < data_len and max_depth > 0:
        if offset + 2 > data_len:
            break
        tag = data[offset]
        length = data[offset + 1]

        if tag == 0:
            break

        offset += 2
        if offset + length > data_len:
            break

        value = data[offset : offset + length]
        try:
            ascii_repr = value.decode("ascii", errors="replace")
        except Exception:
            ascii_repr = ""

        record: dict[str, Any] = {
            "tag": tag,
            "length": length,
            "offset": offset - 2,
            "value_hex": value.hex(),
            "value_ascii": ascii_repr,
        }

        # Try nested decode if the value looks like more TLV data
        if _looks_like_protobuf(value):
            record["nested"] = _decode_protobuf_like(value, 0, max_depth - 1)

        records.append(record)
        offset += length

    return records


def _looks_like_protobuf(data: bytes) -> bool:
    """Heuristic: does this byte sequence look like TLV-encoded data?

    Uses a tag range of 1-100 as a heuristic — tuned for the observed
    0x12/0x08/0x1a tag pattern in RIFT map blobs. Real protobuf tags can
    exceed 100, so this may miss deeply-nested or unusual structures.
    """
    if len(data) < 4:
        return False
    # Check first few tag-length pairs
    for i in range(0, min(len(data) - 2, 8), 2):
        tag = data[i]
        length = data[i + 1]
        if tag == 0:
            continue
        if tag < 1 or tag > 100:
            return False
        if i + 2 + length > len(data):
            return False
    return True


def parse_map_blob(data: bytes) -> dict[str, Any]:
    """Parse a 0x6906-magic map blob and return structured metadata.

    Args:
        data: Raw uncompressed binary payload bytes.

    Returns:
        Dict with map_name, magic, embedded_paths, records, and raw_size.
    """
    if len(data) < 3:
        return {"error": f"payload too small: {len(data)} bytes", "map_name": "", "embedded_paths": []}

    magic = struct.unpack_from(">H", data, 0)[0]
    if magic != MAP_BLOB_MAGIC:
        return {
            "error": f"unexpected magic: 0x{magic:04x} (expected 0x{MAP_BLOB_MAGIC:04x})",
            "map_name": "",
            "embedded_paths": [],
        }

    name_len = data[2]
    if 3 + name_len > len(data):
        return {
            "error": f"name_len {name_len} exceeds payload size {len(data)}",
            "map_name": "",
            "embedded_paths": [],
        }

    map_name = data[3 : 3 + name_len].decode("ascii", errors="replace")
    body = data[3 + name_len :]

    # Extract all ASCII strings from the body
    strings = _decode_length_prefixed_strings(body, 0)

    # Try protobuf-like decode for deeper structure
    records = _decode_protobuf_like(body, 0)

    # Extract file paths (look for \ or / path separators)
    embedded_paths: list[str] = []
    for _, s, _ in strings:
        if "\\" in s or "/" in s:
            embedded_paths.append(s)

    return {
        "magic": f"0x{magic:04x}",
        "map_name": map_name,
        "name_len": name_len,
        "body_size": len(body),
        "total_size": len(data),
        "embedded_paths": embedded_paths,
        "body_strings": [s for _, s, _ in strings],
        "body_records": records,
        "body_hex_preview": body[:64].hex() if len(body) > 64 else body.hex(),
    }


def parse_map_blob_from_first64(first64_hex: str) -> dict[str, Any]:
    """Parse a map blob from its First64 hex string (from semantic index output)."""
    data = bytes.fromhex(first64_hex)
    return parse_map_blob(data)


def _render_result(result: dict[str, Any]) -> str:
    """Render a parse result as a human-readable string."""
    if result.get("error"):
        return f"ERROR: {result['error']}"

    lines = [
        f"Map name: {result['map_name']}",
        f"Magic: {result['magic']}",
        f"Name length: {result['name_len']}",
        f"Body size: {result['body_size']} bytes",
        f"Total size: {result['total_size']} bytes",
        "",
    ]

    if result.get("embedded_paths"):
        lines.append(f"Embedded asset paths ({len(result['embedded_paths'])}):")
        for path in result["embedded_paths"]:
            lines.append(f"  {path}")
        lines.append("")

    if result.get("body_strings"):
        lines.append(f"Body strings ({len(result['body_strings'])}):")
        for s in result["body_strings"]:
            lines.append(f"  {repr(s)}")
        lines.append("")

    if result.get("body_records"):
        lines.append(f"Body records ({len(result['body_records'])}):")
        for r in result["body_records"]:
            nested = f" [nested:{len(r.get('nested', []))}]" if r.get("nested") else ""
            lines.append(f"  tag={r['tag']:3d} len={r['length']:3d} ascii={repr(r['value_ascii'][:60])}{nested}")
        lines.append("")

    if result.get("body_hex_preview"):
        lines.append(f"Body hex preview: {result['body_hex_preview']}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse RIFT 0x6906-magic map blob binary format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/parse_map_blobs.py --hex 69060b64656669616e745f6d61701206
  python scripts/parse_map_blobs.py --file defiant_map.bin
  python scripts/parse_map_blobs.py --json --hex 69060c677561726469616e5f6d617012
        """,
    )
    parser.add_argument("--file", help="Path to raw binary blob file")
    parser.add_argument("--hex", help="Hex string (e.g., First64 from semantic index)")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of human-readable")
    args = parser.parse_args()

    if not args.file and not args.hex:
        parser.print_help()
        sys.exit(1)

    if args.file:
        data = Path(args.file).read_bytes()
        result = parse_map_blob(data)
    else:
        result = parse_map_blob_from_first64(args.hex)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(_render_result(result))


if __name__ == "__main__":
    main()
