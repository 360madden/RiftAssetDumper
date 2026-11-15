"""RA-1: bounded, source-hash-bound provenance samples from installed TWAD archives.

No extraction, game process access, or consumer edits. Reads each requested
archive's entry table plus a small number of packed entry payloads. Output
must stay under gitignored Exports/ in this repository.

Usage:
  python scripts/audit_live_archive_samples.py --archive assets.001 --archive assets.100
  python scripts/audit_live_archive_samples.py --archive assets.001 --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
from pathlib import Path
from typing import Any

# Direct execution via python scripts/<name>.py must resolve scripts.* imports.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.extract_live_nifs import (  # noqa: E402
    ARCHIVE_ENTRY_SIZE,
    ARCHIVE_HEADER_SIZE,
    LIVE_ROOT,
    read_archive_table_streaming,
)

ARCHIVE_NAME_RE = re.compile(r"^assets\.\d{3}$")
REPORT_SCHEMA = "ra1-live-archive-samples/v1"
MAX_ARCHIVES = 8
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
DEFAULT_OUT = Path("Exports/ra1/live-archive-samples.json")


def sha256_file(path: Path) -> str:
    """Hash archive bytes in chunks, not by loading an archive in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def audit_archive(
    live_root: Path,
    archive_name: str,
    *,
    samples: int = 4,
    max_packed_bytes: int = 1024 * 1024,
) -> dict[str, Any]:
    """Join raw TWAD table identity with bounded packed-byte SHA256 evidence."""
    if not ARCHIVE_NAME_RE.fullmatch(archive_name):
        raise ValueError(f"invalid archive name: {archive_name!r}")
    if not 1 <= samples <= 50 or not 1 <= max_packed_bytes <= 8 * 1024 * 1024:
        raise ValueError("samples or max_packed_bytes is outside the bounded range")

    path = live_root / "Assets" / archive_name
    if not path.is_file():
        raise FileNotFoundError(f"archive unavailable: Assets/{archive_name}")
    stat_before = path.stat()
    file_size = stat_before.st_size
    if not ARCHIVE_HEADER_SIZE <= file_size <= MAX_ARCHIVE_BYTES:
        raise ValueError(f"archive size outside bounded range: Assets/{archive_name}: {file_size}")

    with path.open("rb") as source:
        header = source.read(ARCHIVE_HEADER_SIZE)
    if len(header) != ARCHIVE_HEADER_SIZE or header[:4] != b"TWAD":
        raise ValueError(f"invalid TWAD header: Assets/{archive_name}")
    version, header_size, table_count, first_linked = struct.unpack_from("<IIII", header, 4)
    if version != 1:
        raise ValueError(f"unsupported TWAD version: Assets/{archive_name}: {version}")

    entries = read_archive_table_streaming(str(path))
    if len(entries) != table_count:
        raise ValueError(f"entry-table row-count mismatch: Assets/{archive_name}")
    table_end = header_size + table_count * ARCHIVE_ENTRY_SIZE
    non_null = [entry for entry in entries if not entry["is_null"]]
    bad_bounds = [
        int(e["index"])
        for e in non_null
        if int(e["offset"]) < table_end or int(e["size"]) <= 0 or int(e["offset"]) + int(e["size"]) > file_size
    ]
    if bad_bounds:
        raise ValueError(f"entry payload bounds invalid in Assets/{archive_name}: {bad_bounds[:5]}")

    sample_rows: list[dict[str, Any]] = []
    oversized = 0
    with path.open("rb") as source:
        for entry in non_null:
            if len(sample_rows) >= samples:
                break
            packed_size = int(entry["size"])
            if packed_size > max_packed_bytes:
                oversized += 1
                continue
            source.seek(int(entry["offset"]))
            packed = source.read(packed_size)
            if len(packed) != packed_size:
                raise ValueError(f"short packed payload read: Assets/{archive_name}:{entry['index']}")
            sample_rows.append(
                {
                    "entry_index": int(entry["index"]),
                    "id_prefix": str(entry["id_prefix"]),
                    "compression_code": int(entry["compression"]),
                    "offset": int(entry["offset"]),
                    "packed_size": packed_size,
                    "packed_sha256": hashlib.sha256(packed).hexdigest(),
                    "stored_sha1_field": str(entry["sha1"]),  # observed table bytes; NOT revalidated payload SHA1
                }
            )

    archive_sha256 = sha256_file(path)
    stat_after = path.stat()
    if (stat_before.st_size, stat_before.st_mtime_ns) != (stat_after.st_size, stat_after.st_mtime_ns):
        raise ValueError(f"archive changed during audit: Assets/{archive_name}")

    return {
        "source_path": f"Assets/{archive_name}",
        "file_size": file_size,
        "archive_sha256": archive_sha256,
        "twad_header": {
            "version": version,
            "header_size": header_size,
            "max_entries": table_count,
            "first_linked_raw": first_linked,
        },
        "table_entries": len(entries),
        "non_null_entries": len(non_null),
        "oversized_before_sample_limit": oversized,
        "samples": sample_rows,
        "evidence": {
            "raw_archive_hashed": True,
            "table_read": True,
            "sampled_packed_bytes_hashed": True,
            "decompressed_payload_qualified": False,
            "nif_type_qualified": False,
            "world_placement_qualified": False,
            "native_collision_or_traversal_qualified": False,
        },
    }


def build_report(
    live_root: Path,
    archives: list[str],
    *,
    samples: int = 4,
    max_packed_bytes: int = 1024 * 1024,
) -> dict[str, Any]:
    """Stable archive selection/order; never include absolute host paths in reports."""
    names = sorted(set(archives))
    if not names or len(names) > MAX_ARCHIVES:
        raise ValueError(f"select 1..{MAX_ARCHIVES} archives")
    rows = [
        audit_archive(live_root, name, samples=samples, max_packed_bytes=max_packed_bytes)
        for name in names
    ]
    return {
        "schema": REPORT_SCHEMA,
        "source_kind": "installed-game-archive",
        "archive_count": len(rows),
        "sample_count": sum(len(row["samples"]) for row in rows),
        "archives": rows,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    """Atomic publication under the repo's ignored Exports directory only."""
    allowed = (REPO_ROOT / "Exports").resolve()
    target = path.resolve()
    if not target.is_relative_to(allowed):
        raise ValueError("output must be under this repository's ignored Exports/ directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    try:
        temp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--live-root", type=Path, default=Path(LIVE_ROOT))
    parser.add_argument("--archive", action="append", dest="archives", default=None)
    parser.add_argument("--samples", type=int, default=4)
    parser.add_argument("--max-packed-bytes", type=int, default=1024 * 1024)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = build_report(
            args.live_root,
            args.archives or ["assets.001"],
            samples=args.samples,
            max_packed_bytes=args.max_packed_bytes,
        )
        if args.dry_run:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            out = args.out if args.out.is_absolute() else REPO_ROOT / args.out
            write_report(out, report)
            print(f"RA-1: {report['archive_count']} archives, {report['sample_count']} packed samples -> {out}")
    except (OSError, ValueError) as exc:
        print(f"RA-1 ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
