#!/usr/bin/env python3
"""Read-only NiDataStream layout report for copied/extracted NIF files.

This intentionally does not change decoder behavior. It validates the static
Ghidra hypothesis that a NiDataStream block stores descriptor/header bytes,
then declared payload bytes, then a trailing 1-byte flag.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.ghidra_report_summary import markdown_cell, redact_user_profile_paths  # noqa: E402

DEFAULT_ROOT = REPO_ROOT / "Extracted"
DEFAULT_OUT = REPO_ROOT / "Exports"


class NifParseError(ValueError):
    """Raised when a NIF header/table cannot be parsed safely."""


def _u16le(data: bytes, offset: int) -> int:
    if offset + 2 > len(data):
        raise NifParseError(f"Unexpected EOF reading uint16 at offset {offset}.")
    return struct.unpack_from("<H", data, offset)[0]


def _u32le(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise NifParseError(f"Unexpected EOF reading uint32 at offset {offset}.")
    return struct.unpack_from("<I", data, offset)[0]


def _read_sized_ascii(data: bytes, offset: int, *, max_length: int = 4096) -> tuple[str, int]:
    length = _u32le(data, offset)
    offset += 4
    if length > max_length:
        raise NifParseError(f"String length {length} at offset {offset - 4} exceeds max {max_length}.")
    if offset + length > len(data):
        raise NifParseError(f"String length {length} at offset {offset - 4} extends past EOF.")
    value = data[offset : offset + length].decode("utf-8", errors="replace").rstrip("\0")
    return value, offset + length


def _hex_prefix(data: bytes, max_bytes: int = 16) -> str:
    return " ".join(f"{byte:02x}" for byte in data[:max_bytes])


def _safe_relative(path: Path, root: Path = REPO_ROOT) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return redact_user_profile_paths(str(resolved))


def _counter_rows(counter: Counter[Any], limit: int = 12) -> list[dict[str, Any]]:
    return [
        {"Value": value, "Count": count}
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))[:limit]
    ]


def _parse_nif_tables(data: bytes) -> tuple[list[str], list[int], list[int], int, list[str]]:
    warnings: list[str] = []
    newline = data[:256].find(b"\n")
    if newline < 0:
        raise NifParseError("NIF header line terminator was not found in first 256 bytes.")

    offset = newline + 1
    if offset + 15 > len(data):
        raise NifParseError("NIF header is truncated before version/endian/block-count fields.")

    offset += 4  # version
    endian = data[offset]
    offset += 1
    if endian != 1:
        warnings.append(f"Unexpected endian marker {endian}; report assumes little-endian RIFT samples.")

    offset += 4  # user version
    block_count = _u32le(data, offset)
    offset += 4
    block_type_count = _u16le(data, offset)
    offset += 2

    if block_count > 1_000_000:
        raise NifParseError(f"Block count {block_count} is implausibly large.")
    if block_type_count > 100_000:
        raise NifParseError(f"Block type count {block_type_count} is implausibly large.")

    block_types: list[str] = []
    for index in range(block_type_count):
        name, offset = _read_sized_ascii(data, offset)
        if not name:
            warnings.append(f"Block type {index} is empty.")
        block_types.append(name)

    block_type_indices: list[int] = []
    for _ in range(block_count):
        block_type_indices.append(_u16le(data, offset))
        offset += 2

    block_sizes: list[int] = []
    for _ in range(block_count):
        block_sizes.append(_u32le(data, offset))
        offset += 4

    if offset + 8 > len(data):
        raise NifParseError("NIF header ended before string table count fields.")
    string_count = _u32le(data, offset)
    offset += 4
    max_string_length = _u32le(data, offset)
    offset += 4
    if string_count > 1_000_000:
        raise NifParseError(f"NIF string count {string_count} is implausibly large.")
    if max_string_length > 1_000_000:
        warnings.append(f"NIF max string length {max_string_length} is large.")

    for _ in range(string_count):
        _, offset = _read_sized_ascii(data, offset, max_length=max(1_000_000, max_string_length))

    if offset + 4 <= len(data):
        group_count = _u32le(data, offset)
        if group_count <= 1_000_000 and offset + 4 + (group_count * 4) <= len(data):
            offset += 4 + (group_count * 4)
        else:
            warnings.append(f"NIF group count candidate {group_count} is implausible at offset {offset}.")

    return block_types, block_type_indices, block_sizes, offset, warnings


def _is_nidatastream_type(type_name: str) -> bool:
    parts = type_name.split("\x01")
    return bool(parts) and parts[0].lower() == "nidatastream"


def _usage_access(type_name: str) -> tuple[str | None, str | None]:
    parts = type_name.split("\x01")
    usage = parts[1] if len(parts) > 1 and parts[1] else None
    access = parts[2] if len(parts) > 2 and parts[2] else None
    return usage, access


def _analyze_block(payload: bytes) -> dict[str, Any]:
    if len(payload) < 4:
        return {
            "ValidDeclaredPayload": False,
            "GhidraStyleLayoutValid": False,
            "Warning": "Block payload is shorter than declared-payload uint32.",
        }

    declared = _u32le(payload, 0)
    valid_declared = declared <= len(payload)
    legacy_offset = len(payload) - declared if valid_declared else None

    offset = 4
    second_u32 = None
    pair_count = None
    descriptor_count = None
    pair_records_offset = None
    descriptor_count_offset = None
    descriptor_records_offset = None
    payload_prefix_bytes = None
    payload_end_offset = None
    payload_trailer_bytes = None
    trailing_flag = None
    first_pair_record_bytes = ""
    first_descriptor_record_bytes = ""
    ghidra_valid = False
    warning = None

    try:
        second_u32 = _u32le(payload, offset)
        offset += 4
        pair_count = _u32le(payload, offset)
        offset += 4
        if pair_count > 100_000 or offset + (pair_count * 8) > len(payload):
            raise NifParseError(f"Pair count {pair_count} does not fit in block.")
        pair_records_offset = offset
        first_pair_record_bytes = _hex_prefix(
            payload[pair_records_offset : pair_records_offset + min(8, pair_count * 8)], 8
        )
        offset += pair_count * 8
        descriptor_count_offset = offset
        descriptor_count = _u32le(payload, offset)
        offset += 4
        if descriptor_count > 100_000 or offset + (descriptor_count * 4) > len(payload):
            raise NifParseError(f"Descriptor count {descriptor_count} does not fit in block.")
        descriptor_records_offset = offset
        first_descriptor_record_bytes = _hex_prefix(
            payload[descriptor_records_offset : descriptor_records_offset + min(4, descriptor_count * 4)],
            4,
        )
        offset += descriptor_count * 4
        payload_prefix_bytes = offset
        payload_end_offset = payload_prefix_bytes + declared
        if payload_end_offset > len(payload):
            raise NifParseError("Descriptor prefix plus declared payload extends past block.")
        payload_trailer_bytes = len(payload) - payload_end_offset
        trailing_flag = payload[payload_end_offset] if payload_trailer_bytes >= 1 else None
        ghidra_valid = payload_trailer_bytes == 1 and trailing_flag in (0, 1)
    except NifParseError as exc:
        warning = str(exc)

    legacy_body = payload[legacy_offset : legacy_offset + min(declared, 16)] if legacy_offset is not None else b""
    ghidra_body = (
        payload[payload_prefix_bytes : payload_prefix_bytes + min(declared, 16)]
        if payload_prefix_bytes is not None and payload_prefix_bytes + declared <= len(payload)
        else b""
    )

    return {
        "DeclaredPayloadBytes": declared,
        "ValidDeclaredPayload": valid_declared,
        "SecondUInt32": second_u32,
        "PairCount": pair_count,
        "PairRecordsOffset": pair_records_offset,
        "FirstPairRecordBytes": first_pair_record_bytes,
        "DescriptorCountOffset": descriptor_count_offset,
        "DescriptorCount": descriptor_count,
        "DescriptorRecordsOffset": descriptor_records_offset,
        "FirstDescriptorRecordBytes": first_descriptor_record_bytes,
        "LegacyPayloadOffset": legacy_offset,
        "PayloadPrefixBytes": payload_prefix_bytes,
        "PayloadEndOffset": payload_end_offset,
        "PayloadTrailerBytes": payload_trailer_bytes,
        "TrailingFlag": trailing_flag,
        "GhidraStyleLayoutValid": ghidra_valid,
        "LegacyOffsetMinusGhidraOffset": (
            legacy_offset - payload_prefix_bytes
            if legacy_offset is not None and payload_prefix_bytes is not None
            else None
        ),
        "LegacyBodyFirst16": _hex_prefix(legacy_body),
        "GhidraBodyFirst16": _hex_prefix(ghidra_body),
        "Warning": warning,
    }


def analyze_nif(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    block_types, block_type_indices, block_sizes, block_data_offset, warnings = _parse_nif_tables(data)
    rows: list[dict[str, Any]] = []
    offset = block_data_offset

    for block_index, size in enumerate(block_sizes):
        if offset + size > len(data):
            warnings.append(f"Block {block_index} size {size} extends past EOF.")
            break
        type_index = block_type_indices[block_index] if block_index < len(block_type_indices) else -1
        type_name = block_types[type_index] if 0 <= type_index < len(block_types) else f"type-index-{type_index}"
        if _is_nidatastream_type(type_name):
            usage, access = _usage_access(type_name)
            analysis = _analyze_block(data[offset : offset + size])
            rows.append(
                {
                    "File": _safe_relative(path),
                    "BlockIndex": block_index,
                    "TypeIndex": type_index,
                    "TypeName": type_name.replace("\x01", "\\u0001"),
                    "DataStreamUsage": usage,
                    "DataStreamAccess": access,
                    "BlockSize": size,
                    "BlockDataOffset": offset,
                    **analysis,
                }
            )
        offset += size

    return {
        "Path": _safe_relative(path),
        "Warnings": warnings,
        "NiDataStreamBlocks": rows,
    }


def _iter_nif_files(root: Path, max_files: int | None) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        return []
    files = sorted(path for path in root.rglob("*.nif") if path.is_file())
    return files if max_files is None else files[:max_files]


def build_report(root: Path, *, max_files: int | None = 100, sample_limit: int = 50) -> dict[str, Any]:
    files = _iter_nif_files(root, max_files)
    parse_errors: list[dict[str, Any]] = []
    all_blocks: list[dict[str, Any]] = []
    files_with_datastreams = 0

    for path in files:
        try:
            nif_report = analyze_nif(path)
        except Exception as exc:
            parse_errors.append({"Path": _safe_relative(path), "Error": str(exc)})
            continue
        blocks = nif_report["NiDataStreamBlocks"]
        if blocks:
            files_with_datastreams += 1
            all_blocks.extend(blocks)

    valid_declared = [block for block in all_blocks if block.get("ValidDeclaredPayload")]
    ghidra_valid = [block for block in all_blocks if block.get("GhidraStyleLayoutValid")]
    shifted = [block for block in all_blocks if block.get("LegacyOffsetMinusGhidraOffset") not in (None, 0)]

    prefix_counts: Counter[Any] = Counter(block.get("PayloadPrefixBytes") for block in all_blocks)
    trailer_counts: Counter[Any] = Counter(block.get("PayloadTrailerBytes") for block in all_blocks)
    flag_counts: Counter[Any] = Counter(block.get("TrailingFlag") for block in all_blocks)
    shift_counts: Counter[Any] = Counter(block.get("LegacyOffsetMinusGhidraOffset") for block in all_blocks)
    second_u32_counts: Counter[Any] = Counter(block.get("SecondUInt32") for block in all_blocks)
    pair_counts: Counter[Any] = Counter(block.get("PairCount") for block in all_blocks)
    pair_record_offset_counts: Counter[Any] = Counter(block.get("PairRecordsOffset") for block in all_blocks)
    first_pair_record_bytes_counts: Counter[Any] = Counter(block.get("FirstPairRecordBytes") for block in all_blocks)
    descriptor_counts: Counter[Any] = Counter(block.get("DescriptorCount") for block in all_blocks)
    descriptor_count_offset_counts: Counter[Any] = Counter(block.get("DescriptorCountOffset") for block in all_blocks)
    descriptor_record_offset_counts: Counter[Any] = Counter(
        block.get("DescriptorRecordsOffset") for block in all_blocks
    )
    first_descriptor_record_bytes_counts: Counter[Any] = Counter(
        block.get("FirstDescriptorRecordBytes") for block in all_blocks
    )

    report = {
        "Schema": "nidatastream-layout-report/v1",
        "CandidateOnly": True,
        "Interpretation": "Read-only static/copy-data layout check. Do not promote parser/export behavior without a separate guarded decoder patch.",
        "Root": _safe_relative(root) if root.exists() else redact_user_profile_paths(str(root)),
        "MaxFiles": max_files,
        "FilesScanned": len(files),
        "FilesParsed": len(files) - len(parse_errors),
        "FilesWithNiDataStreamBlocks": files_with_datastreams,
        "ParseErrorCount": len(parse_errors),
        "NiDataStreamBlocks": len(all_blocks),
        "ValidDeclaredPayloadBlocks": len(valid_declared),
        "GhidraStyleLayoutValidBlocks": len(ghidra_valid),
        "LegacyOffsetShiftedBlocks": len(shifted),
        "TopPayloadPrefixBytes": _counter_rows(prefix_counts),
        "TopPayloadTrailerBytes": _counter_rows(trailer_counts),
        "TopTrailingFlags": _counter_rows(flag_counts),
        "TopLegacyOffsetMinusGhidraOffset": _counter_rows(shift_counts),
        "TopSecondUInt32": _counter_rows(second_u32_counts),
        "TopPairCounts": _counter_rows(pair_counts),
        "TopPairRecordOffsets": _counter_rows(pair_record_offset_counts),
        "TopFirstPairRecordBytes": _counter_rows(first_pair_record_bytes_counts),
        "TopDescriptorCounts": _counter_rows(descriptor_counts),
        "TopDescriptorCountOffsets": _counter_rows(descriptor_count_offset_counts),
        "TopDescriptorRecordOffsets": _counter_rows(descriptor_record_offset_counts),
        "TopFirstDescriptorRecordBytes": _counter_rows(first_descriptor_record_bytes_counts),
        "ShiftedSamples": shifted[:sample_limit],
        "Warnings": parse_errors[:sample_limit],
    }
    return report


def report_to_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# NiDataStream layout report",
        "",
        "| Field | Value |",
        "|---|---:|",
        f"| Root | {markdown_cell(report.get('Root'))} |",
        f"| Max files | {markdown_cell(report.get('MaxFiles'))} |",
        f"| Files scanned | {markdown_cell(report.get('FilesScanned'))} |",
        f"| Files parsed | {markdown_cell(report.get('FilesParsed'))} |",
        f"| Files with NiDataStream blocks | {markdown_cell(report.get('FilesWithNiDataStreamBlocks'))} |",
        f"| Parse errors | {markdown_cell(report.get('ParseErrorCount'))} |",
        f"| NiDataStream blocks | {markdown_cell(report.get('NiDataStreamBlocks'))} |",
        f"| Valid declared payload blocks | {markdown_cell(report.get('ValidDeclaredPayloadBlocks'))} |",
        f"| Ghidra-style layout valid blocks | {markdown_cell(report.get('GhidraStyleLayoutValidBlocks'))} |",
        f"| Legacy offset shifted blocks | {markdown_cell(report.get('LegacyOffsetShiftedBlocks'))} |",
        "",
        "## Distribution summary",
        "",
    ]

    for title, key in [
        ("Payload prefix bytes", "TopPayloadPrefixBytes"),
        ("Payload trailer bytes", "TopPayloadTrailerBytes"),
        ("Trailing flags", "TopTrailingFlags"),
        ("Legacy offset minus Ghidra offset", "TopLegacyOffsetMinusGhidraOffset"),
        ("Second UInt32 values", "TopSecondUInt32"),
        ("Pair counts", "TopPairCounts"),
        ("Pair record offsets", "TopPairRecordOffsets"),
        ("First pair record bytes", "TopFirstPairRecordBytes"),
        ("Descriptor counts", "TopDescriptorCounts"),
        ("Descriptor count offsets", "TopDescriptorCountOffsets"),
        ("Descriptor record offsets", "TopDescriptorRecordOffsets"),
        ("First descriptor record bytes", "TopFirstDescriptorRecordBytes"),
    ]:
        lines.extend([f"### {title}", "", "| Value | Count |", "|---|---:|"])
        rows = report.get(key)
        if isinstance(rows, list) and rows:
            for row_value in rows:
                row = row_value if isinstance(row_value, Mapping) else {}
                lines.append(f"| {markdown_cell(row.get('Value'))} | {markdown_cell(row.get('Count'))} |")
        else:
            lines.append("| - | 0 |")
        lines.append("")

    samples = report.get("ShiftedSamples")
    lines.extend(
        [
            "## Shifted samples",
            "",
            "| File | Block | Size | Declared | Pair record | Descriptor record | Legacy offset | Ghidra offset | Trailer | Flag | Legacy first16 | Ghidra first16 |",
            "|---|---:|---:|---:|---|---|---:|---:|---:|---:|---|---|",
        ]
    )
    if isinstance(samples, list) and samples:
        for sample_value in samples[:20]:
            sample = sample_value if isinstance(sample_value, Mapping) else {}
            lines.append(
                "| "
                + " | ".join(
                    [
                        markdown_cell(sample.get("File")),
                        markdown_cell(sample.get("BlockIndex")),
                        markdown_cell(sample.get("BlockSize")),
                        markdown_cell(sample.get("DeclaredPayloadBytes")),
                        markdown_cell(sample.get("FirstPairRecordBytes")),
                        markdown_cell(sample.get("FirstDescriptorRecordBytes")),
                        markdown_cell(sample.get("LegacyPayloadOffset")),
                        markdown_cell(sample.get("PayloadPrefixBytes")),
                        markdown_cell(sample.get("PayloadTrailerBytes")),
                        markdown_cell(sample.get("TrailingFlag")),
                        markdown_cell(sample.get("LegacyBodyFirst16")),
                        markdown_cell(sample.get("GhidraBodyFirst16")),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| - | - | - | - | - | - | - | - | - | - | - | - |")

    lines.extend(
        [
            "",
            "## Interpretation guard",
            "",
            str(report.get("Interpretation") or "Candidate-only report."),
        ]
    )
    return "\n".join(lines) + "\n"


def write_report(report: Mapping[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "nidatastream-layout-report.json"
    markdown_path = out_dir / "nidatastream-layout-report.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_path.write_text(report_to_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a read-only NiDataStream layout report from NIF files.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help=f"NIF root or file (default: {DEFAULT_ROOT})")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help=f"Output directory (default: {DEFAULT_OUT})")
    parser.add_argument("--max-files", type=int, default=100, help="Max NIF files to scan; use 0 for unlimited")
    parser.add_argument("--sample-limit", type=int, default=50, help="Max shifted/error samples to keep")
    args = parser.parse_args(argv)

    max_files = None if args.max_files == 0 else args.max_files
    report = build_report(Path(args.root), max_files=max_files, sample_limit=args.sample_limit)
    json_path, markdown_path = write_report(report, Path(args.out))
    print(f"NiDataStream blocks: {report['NiDataStreamBlocks']}")
    print(f"Ghidra-style valid blocks: {report['GhidraStyleLayoutValidBlocks']}")
    print(f"Legacy offset shifted blocks: {report['LegacyOffsetShiftedBlocks']}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
