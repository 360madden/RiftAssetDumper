#!/usr/bin/env python3
"""Ingest Discovery Cycle 3 OBJs into the flythrough pipeline.

The 27 newly-decoded OBJs (17 meshSize=297 + 10 meshSize=321) live under
``Exports/discovery-plan/mesh297-probe/`` and ``mesh321-probe/`` but are NOT
yet visible to downstream consumers. This script:

1. Walks each probe directory's ``*.obj`` files.
2. Groups OBJs by asset ID and computes per-OBJ (vertex_count, face_count,
   mesh_block_index).
3. Selects the per-asset ``canonical`` block — the one with the LARGEST
   ``face_count`` (most representative of the asset's visible geometry).
4. Copies the canonical OBJ to the canonical flythrough path
   ``Assets/build/flythrough/objs/<hash>.obj`` and writes the FT-3 sidecar.
5. Copies non-canonical blocks (multi-block assets) to
   ``Assets/build/flythrough/objs/extra/<hash>__mb<N>.obj`` with sidecars.
6. Updates ``flythrough-index.json`` with one entry per asset pointing at the
   canonical OBJ (the same shape ``build_scene_manifest.py`` expects).

The script is intentionally pure-Python filesystem work — no ``dotnet`` spawns.
Texture linkage, scene-graph probes, material scans, manifest rebuild, and
delivery rebuild are run separately (each has its own tool).

Usage:
    python scripts/ingest_cycle3_extras.py
    python scripts/ingest_cycle3_extras.py --dry-run
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PROBE_DIRS: list[Path] = [
    REPO_ROOT / "Exports" / "discovery-plan" / "mesh297-probe",
    REPO_ROOT / "Exports" / "discovery-plan" / "mesh321-probe",
]
OBJ_DIR = REPO_ROOT / "Assets" / "build" / "flythrough" / "objs"
EXTRAS_DIR = OBJ_DIR / "extra"
FLYTHROUGH_INDEX = OBJ_DIR.parent / "flythrough-index.json"

# An OBJ filename like ``decode-nif-geometry-mesh7.obj`` tells us mesh block 7.
OBJ_FILENAME_RE = re.compile(r"decode-nif-geometry-mesh(\d+)\.obj$", re.IGNORECASE)
ASSET_ID_RE = re.compile(r"^[0-9a-f]{16}$", re.IGNORECASE)
PROBE_ASSET_RE = re.compile(
    r"^[0-9a-f]{4,16}$", re.IGNORECASE
)  # retained for future cycle support — referenced by cycle-4 scaffolding


@dataclasses.dataclass
class ObjRecord:
    """One probe OBJ, parsed from filename + filesystem."""

    asset_id: str
    src_path: Path
    mesh_block: int
    vertex_count: int
    face_count: int
    obj_bytes: int
    obj_sha1: str


def parse_obj_counts(obj_path: Path) -> tuple[int, int]:
    """One-pass count of ``v `` and ``f `` lines. Skips comments/verts/normals/UVs."""
    v_count = f_count = 0
    with open(obj_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("v "):
                v_count += 1
            elif s.startswith("f "):
                f_count += 1
    return v_count, f_count


def sha1_of(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_asset_id(dir_path: Path) -> str | None:
    """Recover the 16-char hex asset ID from a probe subdirectory.

    Cycle 3 probe dirs are either ``<16-hex>``, ``<16-hex-truncated>``, or
    ``mb<N>`` for the mesh-block-name convention used in mesh321-probe.
    Returns None when neither parent nor grandparent yields a valid 16-hex ID.
    """
    for candidate in (dir_path.name, dir_path.parent.name):
        if ASSET_ID_RE.match(candidate.lower()):
            return candidate.lower()
        # Truncated: ``9f32d2`` -> ``9f32d26c425ed264`` is unknown to us
        # without the source map, so we fall back to the basename pattern.
    return None


def _resolve_from_path(obj_path: Path) -> str | None:
    """Recover the asset ID from an OBJ path using several resolution layers:

    1. Explicit probe-root + immediate-subdir map (``_EXPLICIT_DIR_MAP``) ─
       the safest mechanism for blocks known to belong to a specific asset.
    2. Walk the path upward looking for a 16-hex component.
    3. Try the truncated 8-char prefix table (``_TRUNCATED_PREFIXES``).

    Returns None when no layer resolves the asset ID; the caller logs a WARN
    so the operator can extend the explicit map.
    """
    # Layer 1: explicit directory map (lighthouse mb<N> entries, bare decode dir)
    explicit = _resolve_explicit(obj_path)
    if explicit is not None:
        return explicit
    # Layer 2: walk upward for any 16-hex component
    cur = obj_path.parent
    for _ in range(6):  # up to 6 levels
        if cur == REPO_ROOT:
            break
        name = cur.name.lower()
        if ASSET_ID_RE.match(name):
            return name
        # Layer 3: 8-char truncation table
        if name in _TRUNCATED_PREFIXES:
            return _TRUNCATED_PREFIXES[name]
        cur = cur.parent
    return None


# Known 8-char-prefix -> 16-char asset ID alias map. Each entry was used as a
# directory name in Cycle 3 when the asset name was manually shortened. Keep
# this map append-only; new discoveries should match 16-hex directly.
_TRUNCATED_PREFIXES: dict[str, str] = {
    "0910220": "0910220376b18d36",
    "9f32d2": "9f32d26c425ed264",
}

# (probe_dir_basename, subdir_name) -> explicit 16-hex asset ID.
# Used when Cycle 3 organizers placed blocks under stable per-directory names
# (the lighthouse ``mb<N>`` subdirs) and the parent directory isn't informative.
# Also covers the lone ``mesh297-probe/decode-nif-geometry/`` block whose
# asset ID was lost in the directory tree (best-effort fallback).
_EXPLICIT_DIR_MAP: dict[tuple[str, str], str] = {
    ("mesh321-probe", "mb11"): "b89ced7d511388d2",
    ("mesh321-probe", "mb41"): "b89ced7d511388d2",
    ("mesh321-probe", "mb55"): "b89ced7d511388d2",
    ("mesh321-probe", "mb68"): "b89ced7d511388d2",
    ("mesh321-probe", "mb92"): "b89ced7d511388d2",
    ("mesh321-probe", "mb110"): "b89ced7d511388d2",
    ("mesh321-probe", "mb132"): "b89ced7d511388d2",
    ("mesh321-probe", "mb146"): "b89ced7d511388d2",
    ("mesh321-probe", "mb159"): "b89ced7d511388d2",
    ("mesh321-probe", "mb176"): "b89ced7d511388d2",
    ("mesh321-probe", "mb189"): "b89ced7d511388d2",
    ("mesh321-probe", "mb211"): "b89ced7d511388d2",
    ("mesh321-probe", "mb225"): "b89ced7d511388d2",
    ("mesh321-probe", "mb244"): "b89ced7d511388d2",
    ("mesh321-probe", "mb263"): "b89ced7d511388d2",
    ("mesh321-probe", "mb287"): "b89ced7d511388d2",
    ("mesh321-probe", "mb311"): "b89ced7d511388d2",
    ("mesh321-probe", "mb330"): "b89ced7d511388d2",
    ("mesh321-probe", "mb349"): "b89ced7d511388d2",
    ("mesh321-probe", "mb368"): "b89ced7d511388d2",
    ("mesh321-probe", "mb382"): "b89ced7d511388d2",
    ("mesh321-probe", "mb401"): "b89ced7d511388d2",
    ("mesh321-probe", "mb425"): "b89ced7d511388d2",
    ("mesh321-probe", "mb444"): "b89ced7d511388d2",
    ("mesh321-probe", "mb463"): "b89ced7d511388d2",
    ("mesh321-probe", "mb482"): "b89ced7d511388d2",
    ("mesh321-probe", "mb505"): "b89ced7d511388d2",
    # The lone mesh297-probe/decode-nif-geometry/ dir was a Cycle 3 side
    # channel copy from an earlier export round. Its mesh6.obj matches the
    # `03bcfae6561407a1` canonical (same 6559 bytes / sha1); map it so the
    # duplication guard catches it on subsequent runs.
    ("mesh297-probe", "decode-nif-geometry"): "03bcfae6561407a1",
}


def _resolve_explicit(obj_path: Path) -> str | None:
    """Resolve to an explicit 16-hex asset ID by matching probe-dir + subdir."""
    # Walk up the path looking for the probe root; the path between the probe
    # root and the OBJ is the disambiguating prefix (mb<N> or asset fragment).
    for probe in PROBE_DIRS:
        try:
            rel = obj_path.relative_to(probe)
        except ValueError:
            continue
        parts = rel.parts
        if not parts:
            continue
        # The first path component inside the probe root is the disambiguator.
        head = parts[0].lower()
        key = (probe.name, head)
        if key in _EXPLICIT_DIR_MAP:
            return _EXPLICIT_DIR_MAP[key]
        # Also try the head as a 8-char-prefix truncation
        if head in _TRUNCATED_PREFIXES:
            return _TRUNCATED_PREFIXES[head]
    return None


def discover_records() -> list[ObjRecord]:
    """Scan the two Cycle 3 probe directories and return one record per OBJ."""
    records: list[ObjRecord] = []
    for probe in PROBE_DIRS:
        if not probe.is_dir():
            print(f"WARN: probe dir missing: {probe}", file=sys.stderr)
            continue
        for obj_path in probe.rglob("*.obj"):
            m = OBJ_FILENAME_RE.search(obj_path.name)
            if not m:
                continue
            mesh_block = int(m.group(1))
            asset_id = _resolve_from_path(obj_path)
            if asset_id is None:
                print(f"WARN: cannot resolve asset ID for {obj_path}", file=sys.stderr)
                continue
            try:
                v, f = parse_obj_counts(obj_path)
            except OSError as exc:
                print(f"WARN: cannot parse {obj_path}: {exc}", file=sys.stderr)
                continue
            try:
                sha = sha1_of(obj_path)
                size = obj_path.stat().st_size
            except OSError as exc:
                print(f"WARN: cannot hash/size {obj_path}: {exc}", file=sys.stderr)
                continue
            records.append(
                ObjRecord(
                    asset_id=asset_id,
                    src_path=obj_path,
                    mesh_block=mesh_block,
                    vertex_count=v,
                    face_count=f,
                    obj_bytes=size,
                    obj_sha1=sha,
                )
            )
    return records


def group_by_asset(records: list[ObjRecord]) -> dict[str, list[ObjRecord]]:
    """Group records by asset_id and sort each group by face_count desc."""
    groups: dict[str, list[ObjRecord]] = defaultdict(list)
    for r in records:
        groups[r.asset_id].append(r)
    for aid in groups:
        groups[aid].sort(key=lambda r: (-r.face_count, r.mesh_block))
    return dict(sorted(groups.items()))


def write_sidecar(
    asset_id: str,
    obj_path: Path,
    record: ObjRecord,
    canonical: bool,
    mesh_size_hint: int | None = None,
) -> Path:
    """Write an FT-3 asset-mesh-manifest/v1 sidecar next to the OBJ.

    The schema mirrors ``_write_obj_sidecar`` in bulk_export_for_flythrough.py
    (same keys; ``bulk_export`` produces the canonical copy for FT-3 PASS).
    FT-4 fields (parent_node, transform, zone_id, lod_index) are intentionally
    null here — populated later by ``bulk_export scene-graph-only``.
    """
    sidecar: dict[str, Any] = {
        "SchemaVersion": "asset-mesh-manifest/v1",
        "nif_hash": asset_id,
        "obj_filename": obj_path.name,
        "mesh_block": record.mesh_block,
        "mesh_size": mesh_size_hint,
        "vertex_count": record.vertex_count,
        "face_count": record.face_count,
        "faced": record.face_count > 0,
        "position_descriptor": None,
        "export_mode": "ingest-cycle3-extras",
        "export_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "export_command": f"ingest-cycle3-extras (mesh_block={record.mesh_block}, canonical={canonical})",
        "obj_sha1": record.obj_sha1,
        "obj_bytes": record.obj_bytes,
        "export_duration_sec": 0,
        "parent_node": None,
        "sibling_meshes": [],
        "linked_textures": [],
        "original_path_candidates": [str(record.src_path)],
        "bounding_box": None,
        "transform": None,
        "zone_id": None,
        "lod_index": None,
        "probe_note": "ingested from Discovery Cycle 3 (mesh297-probe/mesh321-probe)",
    }
    sidecar_path = obj_path.with_suffix(".obj.manifest.json")
    sidecar_path.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return sidecar_path


def materialize(records: list[ObjRecord], *, dry_run: bool = False) -> dict[str, Any]:
    """Copy OBJs into the flythrough pipeline and return a per-asset summary.

    When ``dry_run`` is True, no OBJ/extras/sidecar is written; the returned
    ``summary`` still reflects what *would* be written so callers can preview.
    """
    groups = group_by_asset(records)
    if not dry_run:
        OBJ_DIR.mkdir(parents=True, exist_ok=True)
        EXTRAS_DIR.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {"canonical": [], "extras": [], "skipped": []}
    for aid, group in groups.items():
        canonical = group[0]
        canonical_dest = OBJ_DIR / f"{aid}.obj"
        canonical_sidecar = OBJ_DIR / f"{aid}.obj.manifest.json"
        # Resolve effective counts — if a different canonical already exists
        # at the canonical path (from a prior FT-2 run), use ITS counts, not
        # the Cycle 3 probe's, so we preserve the prior wire contract.
        if canonical_dest.exists() and canonical_dest.stat().st_size > 0:
            try:
                ev, ef = parse_obj_counts(canonical_dest)
                esz = canonical_dest.stat().st_size
                ehash = sha1_of(canonical_dest)
                canonical = ObjRecord(
                    asset_id=aid,
                    src_path=canonical_dest,
                    mesh_block=canonical.mesh_block,
                    vertex_count=ev,
                    face_count=ef,
                    obj_bytes=esz,
                    obj_sha1=ehash,
                )
            except OSError:
                pass
        # If canonical already exists (and non-empty), skip copy + write sidecar
        if canonical_dest.exists() and canonical_dest.stat().st_size > 0:
            print(f"PRESERVE canonical {canonical_dest.name} (exists)")
            summary["skipped"].append({"asset_id": aid, "reason": "canonical-exists"})
            # Write sidecar only if absent — preserve FT-3 wire schema from
            # any prior bulk_export run that already populated it. In dry-run
            # we still emit the would-write sidecar to preview.
            if not canonical_sidecar.exists():
                if dry_run:
                    print(f"[DRY] would WRITE sidecar {canonical_sidecar.name}")
                else:
                    write_sidecar(aid, canonical_dest, canonical, canonical=True)
            # Always record in ``canonical`` list so flythrough-index update
            # below creates the per-asset entry, even if the OBJ pre-exists.
            summary["canonical"].append(
                {
                    "asset_id": aid,
                    "src": str(canonical_dest.relative_to(REPO_ROOT)),
                    "dst": str(canonical_dest.relative_to(REPO_ROOT)),
                    "mesh_block": canonical.mesh_block,
                    "vertex_count": canonical.vertex_count,
                    "face_count": canonical.face_count,
                    "obj_sha1": canonical.obj_sha1,
                }
            )
            for extra in group[1:]:
                extra_dest = EXTRAS_DIR / f"{aid}__mb{extra.mesh_block:03d}.obj"
                if extra_dest.exists() and extra_dest.stat().st_size > 0:
                    print(f"SKIP extra {extra_dest.name} (exists)")
                summary["skipped"].append({"asset_id": aid, "extra_block": extra.mesh_block, "reason": "exists"})
            continue
        # Copy canonical (skipped in --dry-run; preview only)
        if dry_run:
            print(
                f"[DRY] would WRITE canonical {canonical_dest.name} from {canonical.src_path.relative_to(REPO_ROOT)}"
                f" (mesh#{canonical.mesh_block}, v={canonical.vertex_count}, f={canonical.face_count})"
            )
        else:
            canonical_dest.write_bytes(canonical.src_path.read_bytes())
            write_sidecar(aid, canonical_dest, canonical, canonical=True)
            print(
                f"WRITE canonical {canonical_dest.name} from {canonical.src_path.relative_to(REPO_ROOT)}"
                f" (mesh#{canonical.mesh_block}, v={canonical.vertex_count}, f={canonical.face_count})"
            )
        summary["canonical"].append(
            {
                "asset_id": aid,
                "src": str(canonical.src_path.relative_to(REPO_ROOT)),
                "dst": str(canonical_dest.relative_to(REPO_ROOT)),
                "mesh_block": canonical.mesh_block,
                "vertex_count": canonical.vertex_count,
                "face_count": canonical.face_count,
                "obj_sha1": canonical.obj_sha1,
            }
        )
        # Copy extras (only the non-canonical blocks)
        for extra in group[1:]:
            extra_dest = EXTRAS_DIR / f"{aid}__mb{extra.mesh_block:03d}.obj"
            if dry_run:
                print(
                    f"[DRY] would WRITE extra {extra_dest.name} from {extra.src_path.relative_to(REPO_ROOT)}"
                    f" (mesh#{extra.mesh_block}, v={extra.vertex_count}, f={extra.face_count})"
                )
            else:
                extra_dest.write_bytes(extra.src_path.read_bytes())
                write_sidecar(aid, extra_dest, extra, canonical=False)
                print(
                    f"  WRITE extra   {extra_dest.name} from {extra.src_path.relative_to(REPO_ROOT)}"
                    f" (mesh#{extra.mesh_block}, v={extra.vertex_count}, f={extra.face_count})"
                )
            summary["extras"].append(
                {
                    "asset_id": aid,
                    "src": str(extra.src_path.relative_to(REPO_ROOT)),
                    "dst": str(extra_dest.relative_to(REPO_ROOT)),
                    "mesh_block": extra.mesh_block,
                    "vertex_count": extra.vertex_count,
                    "face_count": extra.face_count,
                    "obj_sha1": extra.obj_sha1,
                }
            )
    return summary


def update_flythrough_index(summary: dict[str, Any], dry_run: bool) -> int:
    """Insert one entry per canonical into flythrough-index.json.

    Preserves any enrichment accumulated by downstream pipeline stages
    (texture linkage, scene-graph probes, material scan):

    - Newly created entries start with ``None`` values for enrichment fields.
    - Entries previously added by THIS script keep their enrichment; only
      geometry fields (``obj_path``, ``mesh_block``, ``vertex_count``,
      ``face_count``, ``faced``) are refreshed to the latest counts (a
      defensive merge — protects against partial re-runs, never overwrites
      populated ``linked_textures``/``world_json``/``mesh_size``).
    - Entries owned by *other* ingestion paths keep their data verbatim;
      Cycle 3 blocks are recorded under ``extra_blocks`` (additive).
    """
    if not FLYTHROUGH_INDEX.exists():
        print(f"ERROR: flythrough-index.json missing: {FLYTHROUGH_INDEX}", file=sys.stderr)
        return 1

    idx = json.loads(FLYTHROUGH_INDEX.read_text(encoding="utf-8-sig"))
    assets: dict[str, Any] = idx.setdefault("assets", {})

    # Defensive normalize: strip any leading ``worlds/`` prefix on existing
    # ``world_json`` paths.  WORLD_DIR already ends in ``worlds/`` so paths
    # written with the prefix would re-double under load_world(); this guards
    # against future ingestion paths that bypass this normalization.
    def _normalize_world_json(p: str | None) -> str | None:
        if not isinstance(p, str):
            return p
        return p.replace("\\", "/").removeprefix("worlds/")

    for canvas in assets.values():
        if isinstance(canvas, dict):
            canvas["world_json"] = _normalize_world_json(canvas.get("world_json"))

    added = 0
    refreshed = 0
    extended = 0
    for entry in summary["canonical"]:
        aid = entry["asset_id"]
        rel_path = entry["dst"]
        if aid not in assets:
            assets[aid] = {
                "asset_id": aid,
                "obj_path": rel_path,
                "mesh_block": entry["mesh_block"],
                "vertex_count": entry["vertex_count"],
                "face_count": entry["face_count"],
                "faced": entry["face_count"] > 0,
                "linked_textures": [],
                "sidecar_path": rel_path.replace(".obj", ".obj.manifest.json").replace("\\", "/"),
                "world_json": None,
                "mesh_size": None,
                "lod_index": None,
                "zone_id": None,
                "extra_blocks": [],
                "source": "ingest-cycle3-extras",
            }
            added += 1
            continue
        canvas = assets[aid]
        if canvas.get("source") == "ingest-cycle3-extras":
            # Re-run by THIS script: refresh geometry only; preserve
            # enrichment (linked_textures/world_json/mesh_size/extras).
            canvas["obj_path"] = rel_path
            canvas["mesh_block"] = entry["mesh_block"]
            canvas["vertex_count"] = entry["vertex_count"]
            canvas["face_count"] = entry["face_count"]
            canvas["faced"] = entry["face_count"] > 0
            refreshed += 1
        else:
            # Owned by another ingestion path — additive only.
            extras = canvas.setdefault("extra_blocks", [])
            extras.append(
                {
                    "obj_path": f"extra/{aid}__mb{entry['mesh_block']:03d}.obj",
                    "mesh_block": entry["mesh_block"],
                    "vertex_count": entry["vertex_count"],
                    "face_count": entry["face_count"],
                    "obj_sha1": entry["obj_sha1"],
                    "source": "ingest-cycle3-extras",
                }
            )
            extended += 1

    if dry_run:
        print(
            f"\n[DRY-RUN] Would add {added} new + refresh {refreshed} own + extend {extended} external flythrough-index entries."
        )
        return 0

    tmp = str(FLYTHROUGH_INDEX) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=2, ensure_ascii=False)
    tmp_path = Path(tmp)
    tmp_path.replace(FLYTHROUGH_INDEX)
    print(
        f"\nflythrough-index.json: added={added}, refreshed={refreshed},"
        f" extended={extended}, total_assets={len(assets)}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest Discovery Cycle 3 OBJs into the flythrough pipeline",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(f"Probe dirs: {[str(p.relative_to(REPO_ROOT)) for p in PROBE_DIRS]}")
    records = discover_records()
    print(f"Discovered OBJs: {len(records)}")
    if not records:
        print("Nothing to ingest.")
        return 0
    summary = materialize(records, dry_run=args.dry_run)
    print(
        f"\nCanonical: {len(summary['canonical'])} OBJs across {len(summary['canonical'])} assets;"
        f"  Extras: {len(summary['extras'])}"
    )
    rc = update_flythrough_index(summary, dry_run=args.dry_run)
    if rc != 0:
        return rc

    # Persist summary for downstream review (skip in --dry-run)
    summary_path = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-3-ingest-summary.json"
    if not args.dry_run:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Summary: {summary_path.relative_to(REPO_ROOT)}")
    else:
        print(f"[DRY-RUN] Would write summary: {summary_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
