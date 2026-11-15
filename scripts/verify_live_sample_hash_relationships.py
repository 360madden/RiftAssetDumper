"""RA-1.3: independently verify archive/packed/decoded hash relationships.

Consumes existing C# extract-archives outputs; does NOT reimplement decompression.
Inputs and generated JSON remain private. No process attach or game writes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_live_archive_samples import sha256_file, write_report  # noqa: E402
from scripts.extract_live_nifs import LIVE_ROOT  # noqa: E402

ID_RE = re.compile(r"^[a-f0-9]{16}$")
ARCHIVE_RE = re.compile(r"^assets\.\d{3}$")
MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
SCHEMA = "ra1-decoded-hash-relationships/v1"


def identify_magic(payload: bytes) -> str:
    """Identify only strongly evident formats; others remain unknown."""
    if payload.startswith(b"DDS "):
        return "dds"
    if payload.startswith(b"Gamebryo File Format"):
        return "nif"
    return "unknown"


def verify_sample(
    archive_sample: dict[str, Any],
    joined_row: dict[str, Any],
    live_root: Path,
    decoded_root: Path,
) -> dict[str, Any]:
    """Check one exact source sample against an existing extracted payload file."""
    archive_rel = joined_row.get("archive_source_path")
    asset_id = joined_row.get("asset_id_prefix")
    if not isinstance(archive_rel, str) or not archive_rel.startswith("Assets/"):
        raise ValueError("invalid archive source path")
    archive_name = archive_rel.removeprefix("Assets/")
    if not ARCHIVE_RE.fullmatch(archive_name) or not isinstance(asset_id, str) or not ID_RE.fullmatch(asset_id):
        raise ValueError("invalid archive or asset identity")
    if archive_sample.get("id_prefix") != asset_id:
        raise ValueError("archive sample identity does not match manifest join")
    if archive_sample.get("entry_index") != joined_row.get("archive_entry_index"):
        raise ValueError("archive entry index mismatch")
    if archive_sample.get("packed_size") != joined_row.get("archive_packed_size"):
        raise ValueError("packed size differs across RA-1.1 / RA-1.2 reports")
    if archive_sample.get("packed_sha256") != joined_row.get("archive_packed_sha256"):
        raise ValueError("packed SHA256 differs across RA-1.1 / RA-1.2 reports")
    candidates = joined_row.get("manifest_candidates", [])
    if joined_row.get("join_status") != "unique-id" or not isinstance(candidates, list) or len(candidates) != 1:
        raise ValueError("a unique manifest ID join is required")
    candidate = candidates[0]

    archive_path = live_root / "Assets" / archive_name
    if not archive_path.is_file():
        raise FileNotFoundError(f"source archive is missing: Assets/{archive_name}")
    archive_digest = sha256_file(archive_path)
    if archive_digest != joined_row.get("archive_sha256"):
        raise ValueError("full live archive SHA256 changed from original RA-1.1 evidence")

    offset, packed_size = archive_sample["offset"], archive_sample["packed_size"]
    if (
        type(offset) is not int or type(packed_size) is not int
        or offset < 20 or not 1 <= packed_size <= MAX_PAYLOAD_BYTES
        or offset + packed_size > archive_path.stat().st_size
    ):
        raise ValueError("packed source bounds outside the bounded archive sample")
    with archive_path.open("rb") as source:
        source.seek(offset)
        packed = source.read(packed_size)
    if len(packed) != packed_size:
        raise ValueError("short packed-source read")
    packed_sha1 = hashlib.sha1(packed).hexdigest()
    packed_sha256 = hashlib.sha256(packed).hexdigest()
    if packed_sha256 != archive_sample.get("packed_sha256"):
        raise ValueError("packed SHA256 does not match original RA-1.1 evidence")
    if packed_sha1 != archive_sample.get("stored_sha1_field"):
        raise ValueError("archive table SHA1 differs from packed payload SHA1")
    if joined_row.get("archive_table_sha1_field") != packed_sha1:
        raise ValueError("manifest join and archive table SHA1 evidence disagree")

    decoded_dir = decoded_root / archive_name.replace(".", "-")
    if not decoded_dir.is_dir():
        raise FileNotFoundError(f"decoded sample directory unavailable: {archive_name}")
    filenames = [
        p for p in decoded_dir.rglob(f"*_{asset_id}.*")
        if p.is_file() and p.suffix.lower() in {".dds", ".nif", ".bin"}
    ]
    if len(filenames) != 1:
        raise ValueError(f"expected exactly one decoded file for {asset_id}, found {len(filenames)}")
    decoded_file = filenames[0]
    if not decoded_file.resolve().is_relative_to(decoded_root.resolve()):
        raise ValueError("decoded source escapes bounded output directory")
    if not 1 <= decoded_file.stat().st_size <= MAX_PAYLOAD_BYTES:
        raise ValueError("decoded payload outside bounded size")
    decoded_bytes = decoded_file.read_bytes()
    if not 1 <= len(decoded_bytes) <= MAX_PAYLOAD_BYTES:
        raise ValueError("decoded payload outside bounded size")
    decoded_sha1 = hashlib.sha1(decoded_bytes).hexdigest()
    decoded_type = identify_magic(decoded_bytes)
    if decoded_type == "unknown" or decoded_file.suffix.lower() != f".{decoded_type}":
        raise ValueError("decoded payload magic is unqualified or conflicts with output type")
    if not decoded_sha1.startswith(asset_id):
        raise ValueError("archive ID is not the decoded SHA1's first 8 bytes")
    if len(decoded_bytes) != candidate.get("manifest_uncompressed_size"):
        raise ValueError("decoded length differs from primary manifest Size")

    manifest_hash = candidate.get("manifest_entry_hash_field")
    return {
        "archive_source_path": archive_rel,
        "archive_sha256": archive_digest,
        "archive_entry_index": joined_row["archive_entry_index"],
        "asset_id_prefix": asset_id,
        "decoded_type": decoded_type,
        "decoded_length": len(decoded_bytes),
        "packed_length": packed_size,
        "packed_sha1": packed_sha1,
        "packed_sha256": packed_sha256,
        "decoded_sha1": decoded_sha1,
        "decoded_sha256": hashlib.sha256(decoded_bytes).hexdigest(),
        "manifest_entry_index": candidate["manifest_entry_index"],
        "manifest_pak_index": candidate["pak_index"],
        "manifest_pak_path": candidate["pak_path"],
        "manifest_hash_field": manifest_hash,
        "manifest_hash_equals_packed_sha1": manifest_hash == packed_sha1,
        "manifest_hash_equals_decoded_sha1": manifest_hash == decoded_sha1,
        "evidence": {
            "source_archive_sha256_reverified": True,
            "archive_table_sha1_equals_packed_sha1": True,
            "archive_id_equals_first_8_bytes_of_decoded_sha1": True,
            "manifest_size_equals_decoded_length": True,
            "decoded_file_magic_qualified": True,
            "decoded_with_existing_dotnet_reader": True,
            "independent_decoder_replay": False,
            "manifest_hash_field_meaning_known": False,
            "world_placement_or_collision": False,
        },
    }


def verify_cohort(
    source_report: dict[str, Any],
    joined: dict[str, Any],
    live_root: Path,
    decoded_root: Path,
) -> dict[str, Any]:
    """Verify a small joined cohort, preserving source hash and unknown boundaries."""
    if source_report.get("schema") != "ra1-live-archive-samples/v1":
        raise ValueError("RA-1.1 evidence schema mismatch")
    if joined.get("schema") != "ra1-archive-manifest-id-join/v1":
        raise ValueError("RA-1.2 manifest join schema mismatch")
    samples = {}
    source_archive_hashes = {}
    for archive in source_report.get("archives", []):
        source_archive_hashes[archive.get("source_path")] = archive.get("archive_sha256")
        rel = archive.get("source_path")
        for sample in archive.get("samples", []):
            key = (rel, sample.get("entry_index"), sample.get("id_prefix"))
            if key in samples:
                raise ValueError("duplicate source sample identity")
            samples[key] = sample
    rows = joined.get("rows", [])
    if not isinstance(rows, list) or not 1 <= len(rows) <= 8:
        raise ValueError("RA-1.3 requires 1..8 bounded joined samples")
    verified = []
    for row in rows:
        if source_archive_hashes.get(row.get("archive_source_path")) != row.get("archive_sha256"):
            raise ValueError("RA-1.1 / RA-1.2 source archive SHA256 mismatch")
        key = (row.get("archive_source_path"), row.get("archive_entry_index"), row.get("asset_id_prefix"))
        if key not in samples:
            raise ValueError("manifest joined row lacks RA-1.1 source evidence")
        verified.append(verify_sample(samples[key], row, live_root, decoded_root))
    verified.sort(key=lambda r: (r["archive_source_path"], r["archive_entry_index"]))
    return {
        "schema": SCHEMA,
        "source_sample_count": len(verified),
        "nif_count": sum(r["decoded_type"] == "nif" for r in verified),
        "dds_count": sum(r["decoded_type"] == "dds" for r in verified),
        "unresolved_manifest_hash_field_count": sum(
            not r["manifest_hash_equals_packed_sha1"] and not r["manifest_hash_equals_decoded_sha1"]
            for r in verified
        ),
        "rows": verified,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Validate RA-1 TWAD packed vs decoded SHA1 relationships")
    p.add_argument("--archive-report", type=Path, default=ROOT / "Exports/ra1/live-archive-samples.json")
    p.add_argument("--manifest-join", type=Path, default=ROOT / "Exports/ra1/manifest-joined-samples.json")
    p.add_argument("--live-root", type=Path, default=Path(LIVE_ROOT))
    p.add_argument("--manifest-file", type=Path, default=Path(LIVE_ROOT) / "assets64.manifest")
    p.add_argument("--decoded-root", type=Path, default=ROOT / "Exports/ra1/decoded-assets")
    p.add_argument("--out", type=Path, default=ROOT / "Exports/ra1/hash-relationships.json")
    a = p.parse_args(argv)
    try:
        source = json.loads(a.archive_report.read_text(encoding="utf-8"))
        joined = json.loads(a.manifest_join.read_text(encoding="utf-8"))
        if sha256_file(a.archive_report) != joined.get("source_report_sha256"):
            raise ValueError("RA-1.1 report changed after the RA-1.2 join")
        if sha256_file(a.manifest_file) != joined.get("manifest_sha256"):
            raise ValueError("manifest changed after the RA-1.2 join")
        verified = verify_cohort(source, joined, a.live_root, a.decoded_root)
        dest = a.out if a.out.is_absolute() else ROOT / a.out
        write_report(dest, verified)
        print(
            f"RA-1.3: {verified['source_sample_count']} verified "
            f"({verified['nif_count']} NIF, {verified['dds_count']} DDS), "
            f"manifest hash unresolved={verified['unresolved_manifest_hash_field_count']} -> {dest}"
        )
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"RA-1.3 ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
