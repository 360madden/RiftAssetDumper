"""
Phase 26: Export Manifest — catalog all OBJs across Exports/

Scans .obj files under the given root directory, parses header comments
for mesh block, vertex counts, face data, and descriptor. Cross-references
with the Phase 19 sibling pairing map when the asset ID matches.

Outputs:
  - Exports/export-manifest.json (full per-OBJ catalog)
  - Console summary with per-MeshSize faced/position-only breakdown

Usage:
    python scripts/build_export_manifest.py [--out DIR] [--obj-root PATH]
"""

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

SEP = "=" * 80
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OBJ_ROOT = REPO_ROOT / "Exports"
PAIRING_MAP_PATH = REPO_ROOT / "Exports" / "phase19-sibling-pairing-map.json"
PROBE_LOOKUP_PATH = REPO_ROOT / "Exports" / "probe-meshsize-lookup.json"
DEFAULT_OUT = REPO_ROOT / "Exports"

# Known MeshSize for @264-indexed meshes
MESHSIZE_264 = 297


def _parse_int_header(line: str, split_idx: int = 2) -> int | None:
    """Extract an integer from a header line like '# Key: Value extra'.

    line.split() produces ['#', 'Key:', 'Value', 'extra', ...]
    so the value is at index 2.
    """
    parts = line.split()
    if len(parts) > split_idx:
        try:
            return int(parts[split_idx])
        except (ValueError, IndexError):
            return None
    return None


def parse_obj_header(path: Path) -> dict:
    """Parse comment lines from an OBJ header to extract metadata."""
    meta: dict = {
        "path": str(path),
        "file_size": path.stat().st_size,
        "nif_version": None,
        "mesh_block": None,
        "positions": None,
        "normals": None,
        "uvs": None,
        "faces": None,
        "face_type": None,
        "descriptor": None,
        "validation": None,
        "vertex_count": 0,
        "face_count": 0,
    }

    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()

                # Parse comment headers (split()[0] is '#', split()[1] is 'Key:', split()[2] is value)
                if line.startswith("# NIF version:"):
                    meta["nif_version"] = line.split(":", 1)[1].strip()
                elif line.startswith("# Mesh block:"):
                    raw = line.split(":", 1)[1].strip().lstrip("#")
                    meta["mesh_block"] = raw.strip()
                elif line.startswith("# Positions:"):
                    meta["positions"] = _parse_int_header(line)
                elif line.startswith("# Normals:"):
                    meta["normals"] = _parse_int_header(line)
                elif line.startswith("# UVs:"):
                    meta["uvs"] = _parse_int_header(line)
                elif line.startswith("# Faces:"):
                    meta["faces"] = _parse_int_header(line)
                    meta["face_type"] = line.split("(")[-1].rstrip(")") if "(" in line else None
                elif line.startswith("# Position descriptor:"):
                    meta["descriptor"] = line.split(":", 1)[1].strip()
                elif line.startswith("#   Export validation:"):
                    meta["validation"] = line.split(":", 1)[1].strip()

                # Count vertices and faces from data lines
                if line.startswith("v "):
                    meta["vertex_count"] += 1
                elif line.startswith("f "):
                    meta["face_count"] += 1

            # Fallback: use data-line counts when header value is missing or zero
            # (header may say 0 faces for position-only, or f-lines may be absent)
            if meta["vertex_count"] > 0:
                if meta["positions"] is None:
                    meta["positions"] = meta["vertex_count"]
            if meta["face_count"] > 0 and (meta["faces"] is None or meta["faces"] == 0):
                meta["faces"] = meta["face_count"]

    except Exception as e:
        meta["parse_error"] = str(e)

    return meta


def extract_asset_id(filepath: Path) -> str | None:
    """Extract the 16-char hex asset ID from a decode-nif-geometry-{id} path.

    Handles filenames like:
      - decode-nif-geometry-{ID}-mesh{N}.obj
      - decode-nif-geometry-{ID}-mesh{N}.obj (inside subdirectory)
    """
    for part in filepath.parts:
        if part.startswith("decode-nif-geometry-"):
            candidate = part.replace("decode-nif-geometry-", "")
            # Strip mesh suffix and any remaining extension (e.g. -mesh6.obj, -mesh31.obj)
            candidate = re.sub(r"-mesh\d+\..*$", "", candidate)
            # Also handle case where file has no mesh suffix (just .obj)
            candidate = re.sub(r"\..*$", "", candidate)
            if len(candidate) == 16:
                return candidate
    return None


def classify_export_batch(obj_path: Path) -> str:
    """Classify which batch/phase exported this OBJ based on its path."""
    parts = obj_path.parts
    for part in parts:
        if part.startswith("decode-264-"):
            return f"batch-264-{part.replace('decode-264-', '')}"
        if part.startswith("decode-nif-geometry-"):
            # Check if it's a sibling export by looking for obj-exports in path
            if "obj-exports" in parts:
                return "sibling-export"
            return "individual-export"
    return "unknown"


def main() -> int:
    print(SEP)
    print("PHASE 26: EXPORT MANIFEST — COMPREHENSIVE OBJ CATALOG")
    print(SEP)

    # Parse args
    out_dir = DEFAULT_OUT
    obj_root = DEFAULT_OBJ_ROOT
    for i, arg in enumerate(sys.argv):
        if arg == "--out" and i + 1 < len(sys.argv):
            out_dir = Path(sys.argv[i + 1])
        if arg == "--obj-root" and i + 1 < len(sys.argv):
            obj_root = Path(sys.argv[i + 1])

    # Find all OBJs
    if not obj_root.exists():
        print(f"ERROR: OBJ root not found: {obj_root}")
        return 1

    obj_files = sorted(obj_root.rglob("*.obj"))
    print(f"\nFound {len(obj_files)} .obj files under {obj_root}")

    # Load pairing map if available (bidirectional: float2 and float3)
    pair_lookup: dict = {}  # asset_id -> pair info (float2)
    float3_lookup: dict = {}  # asset_id -> pair info (float3)
    if PAIRING_MAP_PATH.exists():
        with open(PAIRING_MAP_PATH, encoding="utf-8") as f:
            pairs = json.load(f).get("pairs", [])
        for p in pairs:
            f2_id = p.get("float2_id", "")
            if f2_id:
                pair_lookup[f2_id] = p
            f3_id = p.get("float3_id", "")
            if f3_id and f3_id not in pair_lookup:
                float3_lookup[f3_id] = p
        print(f"Loaded {len(pairs)} sibling pairs ({len(pair_lookup)} f2 + {len(float3_lookup)} f3 unique)")
    else:
        print("(No pairing map found — skipping cross-reference)")

    # Load probe-based MeshSize lookup if available
    probe_lookup: dict = {}
    if PROBE_LOOKUP_PATH.exists():
        with open(PROBE_LOOKUP_PATH, encoding="utf-8") as f:
            probe_data = json.load(f).get("entries", {})
            for aid, info in probe_data.items():
                probe_lookup[aid] = info.get("meshsize")
        print(f"Loaded {len(probe_lookup)} probe-based MeshSize entries")

    # Scan each OBJ
    entries: list[dict] = []
    faced_count = 0
    position_only_count = 0
    total_vertices = 0
    total_faces = 0
    total_bytes = 0
    descriptors: dict = {}
    asset_ids_found: set = set()

    # Per-MeshSize breakdown (key: mesh_size_str, value: {faced, pos_only})
    ms_breakdown: dict[str, dict] = {}
    # Per-export-batch breakdown
    batch_counts: Counter = Counter()

    start = time.time()

    for i, obj_path in enumerate(obj_files):
        # Parse header
        meta = parse_obj_header(obj_path)
        asset_id = extract_asset_id(obj_path)
        if asset_id:
            meta["asset_id"] = asset_id
            asset_ids_found.add(asset_id)

        # Classify export batch
        batch = classify_export_batch(obj_path)
        meta["export_batch"] = batch
        batch_counts[batch] += 1

        # Determine MeshSize:
        # 1. Check pairing map (float2 side)
        # 2. Check pairing map (float3 side)
        # 3. Check probe lookup
        # 4. Check if it's a @264 export (MeshSize 297)
        # 5. Otherwise unknown
        ms = None
        if asset_id and asset_id in pair_lookup:
            pair_info = pair_lookup[asset_id]
            ms = pair_info.get("meshsize")
            meta["sibling_pair"] = {
                "distance": pair_info.get("distance"),
                "float3_id": pair_info.get("float3_id"),
                "float3_mb": pair_info.get("float3_mb"),
                "archive": pair_info.get("archive"),
                "mesh_size": ms,
            }
        elif asset_id and asset_id in float3_lookup:
            pair_info = float3_lookup[asset_id]
            ms = pair_info.get("meshsize")
            meta["sibling_pair"] = {
                "distance": pair_info.get("distance"),
                "float2_id": pair_info.get("float2_id"),
                "float2_mb": pair_info.get("float2_mb"),
                "archive": pair_info.get("archive"),
                "mesh_size": ms,
                "note": "resolved via float3_id in pairing map",
            }
        elif asset_id and asset_id in probe_lookup:
            ms = probe_lookup[asset_id]
            meta["sibling_pair"] = {
                "mesh_size": ms,
                "note": "resolved via probe lookup",
            }
        elif batch.startswith("batch-264-"):
            ms = MESHSIZE_264
            meta["sibling_pair"] = None
        else:
            meta["sibling_pair"] = None

        # Determine if faced or position-only
        has_faces = meta.get("faces", 0) > 0
        meta["faced"] = has_faces

        # Track per-MeshSize breakdown
        ms_key = str(ms) if ms else "unknown"
        if ms_key not in ms_breakdown:
            ms_breakdown[ms_key] = {"faced": 0, "position_only": 0}
        if has_faces:
            ms_breakdown[ms_key]["faced"] += 1
            faced_count += 1
        else:
            ms_breakdown[ms_key]["position_only"] += 1
            position_only_count += 1

        total_vertices += meta.get("vertex_count", 0)
        total_faces += meta.get("faces", 0) or 0
        total_bytes += meta.get("file_size", 0)

        # Track descriptor types
        desc = meta.get("descriptor")
        if desc:
            descriptors[desc] = descriptors.get(desc, 0) + 1

        entries.append(meta)

        # Progress indicator
        if (i + 1) % 50 == 0:
            elapsed = time.time() - start
            print(f"  Scanned {i+1}/{len(obj_files)} OBJs ({elapsed:.1f}s)...")

    elapsed = time.time() - start

    # PHASE 41: Pattern-match no-ID entries to known MeshSizes
    # Build a pattern lookup from entries that have resolved MeshSizes
    # Key: (faces, vertex_count, mesh_block, faced) -> mesh_size
    pattern_lookup: dict[tuple, int] = {}
    for e in entries:
        ms_entry = e.get("sibling_pair") or {}
        ms_val = ms_entry.get("mesh_size") if isinstance(ms_entry, dict) else None
        if ms_val:
            key = (e.get("faces", 0) or 0, e.get("vertex_count", 0), e.get("mesh_block"), e.get("faced"))
            if key not in pattern_lookup:
                pattern_lookup[key] = ms_val

    # Use tolerance matching for entries that don't exactly match
    # (face/vertex counts may differ by a few due to export variations)
    resolved_from_pattern = 0
    for e in entries:
        # Skip entries that already have a MeshSize
        ms_entry = e.get("sibling_pair") or {}
        if isinstance(ms_entry, dict) and ms_entry.get("mesh_size"):
            continue

        # Skip entries with asset_id (they should use pairing map or probe lookup)
        if e.get("asset_id"):
            continue

        e_faces = e.get("faces", 0) or 0
        e_verts = e.get("vertex_count", 0)
        e_mb = e.get("mesh_block")
        e_faced = e.get("faced")

        if e_faces == 0 and not e_faced:
            # Position-only zero-face entries are harder to match
            # Try matching by (verts, MB) alone
            for (pf, pv, pmb, pfaced), pms in pattern_lookup.items():
                if not pfaced and pv == e_verts and pmb == e_mb and abs(pf - e_faces) <= 5:
                    e["sibling_pair"] = {"mesh_size": pms, "note": "resolved via pattern match (pos-only)"}
                    resolved_from_pattern += 1
                    break
        else:
            # Try exact match first
            exact_key = (e_faces, e_verts, e_mb, e_faced)
            if exact_key in pattern_lookup:
                pms = pattern_lookup[exact_key]
                # Check this isn't a self-match (identical to the source probe entry)
                e["sibling_pair"] = {"mesh_size": pms, "note": f"resolved via pattern match (faces={e_faces}, verts={e_verts}, MB={e_mb})"}
                resolved_from_pattern += 1
            else:
                # Try tolerance match (±2% for faces, ±2% for verts)
                for (pf, pv, pmb, pfaced), pms in pattern_lookup.items():
                    if pmb == e_mb and pfaced == e_faced:
                        face_diff = abs(pf - e_faces) / max(pf, 1)
                        vert_diff = abs(pv - e_verts) / max(pv, 1)
                        if face_diff <= 0.10 and vert_diff <= 0.10:
                            e["sibling_pair"] = {"mesh_size": pms, "note": f"resolved via fuzzy pattern match (faces={e_faces}, verts={e_verts}, MB={e_mb}) match={pf}f/{pv}v"}
                            resolved_from_pattern += 1
                            break

    if resolved_from_pattern > 0:
        print(f"\n  Resolved {resolved_from_pattern} entries via face/vertex/MB pattern matching")

    # Recalculate per-MeshSize breakdown after pattern matching
    # (Reset and recount with resolved MeshSizes)
    ms_breakdown.clear()
    faced_count = 0
    position_only_count = 0
    for e in entries:
        ms_entry = e.get("sibling_pair") or {}
        ms_val = ms_entry.get("mesh_size") if isinstance(ms_entry, dict) else None
        has_faces = e.get("faced", False)
        ms_key = str(ms_val) if ms_val else "unknown"
        if ms_key not in ms_breakdown:
            ms_breakdown[ms_key] = {"faced": 0, "position_only": 0}
        if has_faces:
            ms_breakdown[ms_key]["faced"] += 1
            faced_count += 1
        else:
            ms_breakdown[ms_key]["position_only"] += 1
            position_only_count += 1

    # Build manifest
    manifest = {
        "schema": "export-manifest-v2",
        "generated_output_notice": "Generated from local copied RIFT assets. Keep under ignored Exports/.",
        "scan_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scan_duration_s": round(elapsed, 1),
        "obj_root": str(obj_root),
        "summary": {
            "total_obj_files": len(obj_files),
            "total_unique_asset_ids": len(asset_ids_found),
            "faced": faced_count,
            "position_only": position_only_count,
            "total_vertices": total_vertices,
            "total_faces": total_faces,
            "total_bytes": total_bytes,
            "descriptors": descriptors,
            "mesh_size_breakdown": ms_breakdown,
            "export_batch_breakdown": dict(batch_counts.most_common()),
        },
        "entries": entries,
    }

    # Write manifest
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "export-manifest.json"
    with open(str(manifest_path), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)

    # Summary
    print(f"\n{SEP}")
    print("EXPORT MANIFEST SUMMARY")
    print(SEP)
    print(f"\n  Total OBJ files: {len(obj_files)}")
    print(f"  Total unique asset IDs: {len(asset_ids_found)}")
    print(f"  Faced: {faced_count}")
    print(f"  Position-only: {position_only_count}")
    print(f"  Total vertices: {total_vertices:,}")
    print(f"  Total faces: {total_faces:,}")
    print(f"  Total bytes: {total_bytes:,} ({total_bytes/1024:.0f} KB)")

    print("\n  Per-MeshSize Breakdown:")
    for ms_key in sorted(ms_breakdown.keys()):
        fb = ms_breakdown[ms_key]
        pct = (fb["faced"] / (fb["faced"] + fb["position_only"]) * 100) if (fb["faced"] + fb["position_only"]) > 0 else 0
        print(f"    MeshSize {ms_key}: {fb['faced']} faced + {fb['position_only']} pos-only = {fb['faced'] + fb['position_only']} ({pct:.0f}% faced)")

    print("\n  Export Batch Breakdown:")
    for batch, count in batch_counts.most_common():
        print(f"    {batch}: {count}")

    if descriptors:
        print("\n  Position descriptors:")
        for desc, count in sorted(descriptors.items(), key=lambda x: -x[1]):
            print(f"    {desc}: {count}")

    print(f"\n  Manifest written: {manifest_path}")
    print(f"  Scan time: {elapsed:.1f}s")
    print(SEP)
    print("DONE")

    return 0


if __name__ == "__main__":
    sys.exit(main())
