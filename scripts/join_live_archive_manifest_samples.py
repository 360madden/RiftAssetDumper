"""RA-1.2: join bounded live TWAD samples with existing .NET TWAM CLI outputs.

Does not parse TWAM independently or claim decoded payload identity.
Run the .NET list-entries --id and list-paks commands first; see RA-1.2 handoff.
All generated JSON stays in this checkout's ignored Exports directory.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_live_archive_samples import sha256_file, write_report  # noqa: E402

ID_RE = re.compile(r"^[a-f0-9]{16}$")
ARCHIVE_RE = re.compile(r"^assets\.\d{3}$")
JOIN_SCHEMA = "ra1-archive-manifest-id-join/v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL as record objects; refuse malformed rows."""
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict):
            raise ValueError(f"JSONL row is not an object: {path.name}")
        rows.append(obj)
    return rows


def pak_index_map(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Reject conflicting/duplicate indexes in the authority's PAK table."""
    mapping: dict[int, dict[str, Any]] = {}
    for row in rows:
        key = row.get("Index")
        if type(key) is not int or key < 0 or key in mapping:
            raise ValueError(f"invalid/duplicate manifest PAK index: {key}")
        mapping[key] = row
    return mapping


def join_report(
    archive_report: dict[str, Any],
    manifest_rows: dict[tuple[str, str], list[dict[str, Any]]],
    paks: dict[int, dict[str, Any]],
    *,
    source_report_sha256: str,
    manifest_sha256: str,
    paks_export_sha256: str,
    per_archive: int = 1,
) -> dict[str, Any]:
    """Pure candidate ID join. Never conflate archive and manifest content hashes."""
    if archive_report.get("schema") != "ra1-live-archive-samples/v1":
        raise ValueError("expected RA-1.1 archive samples schema")
    if per_archive < 1 or per_archive > 50:
        raise ValueError("per_archive must be 1..50")

    results: list[dict[str, Any]] = []
    for archive in archive_report.get("archives", []):
        rel_source = archive.get("source_path")
        if not isinstance(rel_source, str) or not rel_source.startswith("Assets/"):
            raise ValueError("archive source path is missing or not relative")
        archive_name = rel_source.removeprefix("Assets/")
        if not ARCHIVE_RE.fullmatch(archive_name):
            raise ValueError(f"invalid source archive name: {archive_name}")
        if not re.fullmatch(r"[a-f0-9]{64}", str(archive.get("archive_sha256", ""))):
            raise ValueError("archive source is not SHA256-bound")
        for entry in archive.get("samples", [])[:per_archive]:
            asset_id = entry.get("id_prefix")
            if not isinstance(asset_id, str) or not ID_RE.fullmatch(asset_id):
                raise ValueError("invalid sampled archive asset ID")
            matches = manifest_rows[(archive_name, asset_id)]
            for candidate in matches:
                if str(candidate.get("IdPrefix", "")).lower() != asset_id:
                    raise ValueError(f"manifest CLI row mismatches sampled ID in {archive_name}")

            row: dict[str, Any] = {
                "archive_source_path": rel_source,
                "archive_sha256": archive["archive_sha256"],
                "archive_entry_index": entry["entry_index"],
                "asset_id_prefix": asset_id,
                "archive_packed_size": entry["packed_size"],
                "archive_packed_sha256": entry["packed_sha256"],
                "archive_table_sha1_field": entry["stored_sha1_field"],
                "manifest_id_candidate_count": len(matches),
                "join_status": "unmatched" if not matches else "ambiguous-id" if len(matches) > 1 else "unique-id",
                "manifest_candidates": [],
                "qualification": {
                    "archive_id_equals_manifest_id": bool(matches),
                    "manifest_pak_path_from_manifest": False,
                    "packed_payload_equivalence": False,
                    "decoded_asset_type": False,
                    "world_placement": False,
                    "collision_or_traversal": False,
                },
            }
            for candidate in matches:
                pak_index = candidate.get("PakIndex")
                if type(pak_index) is not int or pak_index < 0 or pak_index not in paks:
                    raise ValueError(f"manifest row references missing PAK index: {pak_index}")
                pak_path = paks[pak_index].get("Path")
                if not isinstance(pak_path, str) or not pak_path or Path(pak_path).is_absolute():
                    raise ValueError("invalid or absolute manifest PAK path")
                row["manifest_candidates"].append(
                    {
                        "manifest_entry_index": candidate["Index"],
                        "pak_index": pak_index,
                        "pak_path": pak_path.replace("\\", "/"),
                        "name_fnv1_hash": candidate["FilenameFnv1Hash"],
                        "name_length": candidate.get("NameLength"),
                        "manifest_compressed_size": candidate["CompressedSize"],
                        "manifest_uncompressed_size": candidate["Size"],
                        "manifest_entry_hash_field": candidate["Hash"],
                        "raw_sha1_fields_equal": candidate["Hash"] == entry["stored_sha1_field"],
                        "compressed_sizes_equal": candidate["CompressedSize"] == entry["packed_size"],
                    }
                )
            row["qualification"]["manifest_pak_path_from_manifest"] = bool(matches)
            results.append(row)

    results.sort(key=lambda item: (item["archive_source_path"], item["archive_entry_index"], item["asset_id_prefix"]))
    return {
        "schema": JOIN_SCHEMA,
        "source_report_sha256": source_report_sha256,
        "manifest_source_path": "assets64.manifest",
        "manifest_sha256": manifest_sha256,
        "paks_cli_export_sha256": paks_export_sha256,
        "cli_exports_confirmed_same_manifest_epoch": False,
        "total_joined_samples": len(results),
        "unique_id_matches": sum(x["join_status"] == "unique-id" for x in results),
        "unmatched_samples": sum(x["join_status"] == "unmatched" for x in results),
        "ambiguous_samples": sum(x["join_status"] == "ambiguous-id" for x in results),
        "rows": results,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Join existing .NET manifest output with bounded source samples")
    p.add_argument("--archive-report", type=Path, default=ROOT / "Exports/ra1/live-archive-samples.json")
    p.add_argument("--manifest-file", type=Path, required=True)
    p.add_argument("--paks-jsonl", type=Path, default=ROOT / "Exports/ra1/assets64-paks.jsonl")
    p.add_argument("--rows-dir", type=Path, default=ROOT / "Exports/ra1")
    p.add_argument("--per-archive", type=int, default=1)
    p.add_argument("--out", type=Path, default=ROOT / "Exports/ra1/manifest-joined-samples.json")
    a = p.parse_args(argv)
    try:
        if a.manifest_file.name.lower() != "assets64.manifest":
            raise ValueError("RA-1.2 requires the primary assets64.manifest")
        if a.per_archive < 1 or a.per_archive > 50:
            raise ValueError("per_archive must be 1..50")
        report = json.loads(a.archive_report.read_text(encoding="utf-8"))
        selected: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for archive in report["archives"]:
            archive_name = str(archive["source_path"]).removeprefix("Assets/")
            if not ARCHIVE_RE.fullmatch(archive_name):
                raise ValueError("archive name is invalid")
            for item in archive["samples"][:a.per_archive]:
                asset_id = str(item["id_prefix"])
                if not ID_RE.fullmatch(asset_id):
                    raise ValueError("asset ID is invalid")
                row_name = f"manifest-join-{archive_name.replace('.', '-')}-{asset_id}.jsonl"
                selected[(archive_name, asset_id)] = read_jsonl(a.rows_dir / row_name)

        pak_rows = pak_index_map(read_jsonl(a.paks_jsonl))
        joined = join_report(
            report, selected, pak_rows,
            source_report_sha256=sha256_file(a.archive_report),
            manifest_sha256=sha256_file(a.manifest_file),
            paks_export_sha256=sha256_file(a.paks_jsonl),
            per_archive=a.per_archive,
        )
        out = a.out if a.out.is_absolute() else ROOT / a.out
        write_report(out, joined)
        print(
            f"RA-1.2: unique={joined['unique_id_matches']} unmatched={joined['unmatched_samples']} "
            f"ambiguous={joined['ambiguous_samples']} -> {out}"
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"RA-1.2 ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
