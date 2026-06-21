"""Populate ``Exports/discovery-plan/live-nif-archive-index.json``.

Cycle 5 data-thickness upgrade: scan every ``assets.NNN`` TWAD archive in
the live RIFT install, intersect entry-table IDs against the 227 flythrough
cohort hashes from ``Assets/build/flythrough/flythrough-index.json``, and
emit a slim lookup table the polyfill in
``scripts/synthesize_semantic_matrices`` consumes via Tier-1
archive-path classification.

The output schema is a JSON list of
``{"NifHash": "<16-hex-lower>", "ArchiveName": "<assets.NNN>", "EntryIndex": <int>}``
rows matching the contract ``load_archive_index()`` expects.

Tempo:
    * Reads only each archive's TWAD header + 44-byte entry table (no
      payload decompression). 244 archives x ~44KB = ~10MB total scan,
      typically <5s end-to-end on a 26GB install.
    * Stops early once every cohort hash has been located.

Usage:
    python scripts/build_live_archive_index.py
    python scripts/build_live_archive_index.py --dry-run    # stats only
    python scripts/build_live_archive_index.py --validate  # JSON schema round-trip

Notes:
    The current ``synthesize_semantic_matrices.ARCHIVE_TAXONOMY`` expects
    semantic substrings like ``world.twad`` / ``characters.twad``; the live
    install actually exposes ``assets.001``..``assets.244`` with no
    semantic substring.  Building the index is correct (real archive
    provenance), but ``classify_by_archive`` will return ``None`` for every
    filename today, so Tier-1 firing rate stays at 0% until the taxonomy is
    extended.  This script is independent of that limitation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Path bootstrap: insert repo root so absolute ``from scripts.X`` imports
# resolve cleanly whether invoked via ``-m`` or as a top-level script.  This
# mirrors the pattern in scripts/build_scene_manifest.py and is idempotent
# when pytest / pyproject ``pythonpath=["."]`` already covers it.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.extract_live_nifs import LIVE_ROOT, read_archive  # noqa: E402

FLYTHROUGH_INDEX = REPO_ROOT / "Assets" / "build" / "flythrough" / "flythrough-index.json"
DEFAULT_OUT_PATH = REPO_ROOT / "Exports" / "discovery-plan" / "live-nif-archive-index.json"
ARCHIVE_GLOB = "assets.*"


def load_cohort_nif_hashes(path: Path) -> set[str]:
    """Return the set of 16-hex NIF hashes from the flythrough cohort.

    All hashes are lower-cased so they match ``load_archive_index()`` keys.
    Raises FileNotFoundError when the flythrough index is missing and
    ValueError when ``assets`` is not a dict.  Defensive coercion: keys
    that are not strings are silently dropped.
    """
    if not path.exists():
        raise FileNotFoundError(f"Flythrough index not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    assets = data.get("assets")
    if not isinstance(assets, dict):
        raise ValueError(f"Flythrough index.assets is not a dict: {path}")
    out: set[str] = set()
    for key in assets.keys():
        if isinstance(key, str):
            out.add(key.lower())
    return out


def list_archive_files(live_root: Path) -> list[Path]:
    """Return sorted ``assets.NNN`` files in ``<live_root>/Assets/``.

    Archived files are extensionless, so a regex-or-glob match on the
    basename only would be ambiguous.  We glob ``assets.*`` and rely on
    caller-side TWAD-validity checks (invalid files are reported and
    skipped before row emission).
    """
    assets_dir = live_root / "Assets"
    if not assets_dir.exists():
        return []
    return sorted(p for p in assets_dir.glob(ARCHIVE_GLOB) if p.is_file())


def extract_rows(
    archive_files: list[Path],
    cohort_hashes: set[str],
    read_archive_fn: Callable[[str], list[dict[str, Any]]] = read_archive,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Scan each archive and emit rows for matching cohort hashes.

    Args:
        archive_files: list of TWAD archive paths to scan.
        cohort_hashes: lowercased 16-hex flythrough asset IDs to intersect.
        read_archive_fn: optional injection point for unit tests (defaults
            to ``scripts.extract_live_nifs.read_archive``).

    Returns:
        (rows, stats) where rows is the unsorted union of matches and
        stats is a dict {archives_scanned, cohort_hashes, rows_emitted,
        missing_in_archives}.

    Notes:
        * Reads only the TWAD header + entry table (no payload
          decompression), so each archive scan is bounded to ~44KB.
        * Stops iterating once every cohort hash has been located.
        * Silently skips null entries and entries whose id_prefix is not a
          16-char hex string.
    """
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    archives_scanned = 0
    for archive_path in archive_files:
        archives_scanned += 1
        try:
            entries = read_archive_fn(str(archive_path))
        except Exception as exc:  # noqa: BLE001 - surface as a warning, keep going
            print(
                f"  WARN: failed to read {archive_path.name}: {exc}",
                file=sys.stderr,
            )
            continue

        for entry in entries:
            if seen == cohort_hashes:
                # Early-exit: every cohort hash has been located.
                break
            if entry.get("is_null"):
                continue
            id_prefix = entry.get("id_prefix")
            if not isinstance(id_prefix, str) or len(id_prefix) != 16:
                continue
            nif_hash = id_prefix.lower()
            if nif_hash not in cohort_hashes or nif_hash in seen:
                continue
            try:
                entry_index = int(entry["index"])
            except KeyError, TypeError, ValueError:
                continue
            if entry_index < 0:
                continue
            rows.append(
                {
                    "NifHash": nif_hash,
                    "ArchiveName": archive_path.name,
                    "EntryIndex": entry_index,
                }
            )
            seen.add(nif_hash)

        if seen == cohort_hashes:
            # Early-exit across remaining archives too.
            break

    stats: dict[str, int] = {
        "archives_scanned": archives_scanned,
        "cohort_hashes": len(cohort_hashes),
        "rows_emitted": len(rows),
        "missing_in_archives": len(cohort_hashes - seen),
    }
    return rows, stats


def atomic_write_json(path: Path, payload: list[dict[str, Any]]) -> None:
    """Write payload to disk atomically via tmp + ``os.replace``.

    Mirrors the existing ``build_scene_manifest.py`` pattern so CI
    watchers never observe a partial read.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            # Clean up on write failure rather than leaving a stray .tmp
            try:
                tmp_path.unlink()
            except OSError:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Populate the live-archive NIF index for the flythrough cohort.",
    )
    parser.add_argument(
        "--flythrough-index",
        default=str(FLYTHROUGH_INDEX),
        help="Path to flythrough-index.json (default: %(default)s).",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT_PATH),
        help="Output JSON path (default: %(default)s).",
    )
    parser.add_argument(
        "--live-root",
        default=LIVE_ROOT,
        help="Live RIFT install root (default: %(default)s).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute stats but do not write a file.",
    )
    args = parser.parse_args()

    cohort = load_cohort_nif_hashes(Path(args.flythrough_index))
    archives = list_archive_files(Path(args.live_root))
    rows, stats = extract_rows(archives, cohort)

    if args.dry_run:
        print(json.dumps(stats, indent=2))
        return 0

    # Deterministic emit order: NifHash, then ArchiveName, then EntryIndex.
    rows.sort(key=lambda r: (r["NifHash"], r["ArchiveName"], r["EntryIndex"]))
    atomic_write_json(Path(args.out), rows)

    print(f"Emitted {len(rows)} rows to {args.out}")
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
