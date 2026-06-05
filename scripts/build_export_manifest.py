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
    """Extract the 16-char hex asset ID from a decode-nif-geometry-{id} path."""
    for part in filepath.parts:
        if part.startswith("decode-nif-geometry-"):
            candidate = part.replace("decode-nif-geometry-", "")
            # Handle suffix like -mesh6 by stripping it
            candidate = re.sub(r"-mesh\d+$", "", candidate)
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

    # Load pairing map if available
    pair_lookup: dict = {}  # asset_id -> pair info
    if PAIRING_MAP_PATH.exists():
        with open(PAIRING_MAP_PATH, encoding="utf-8") as f:
            pairs = json.load(f).get("pairs", [])
        for p in pairs:
            f2_id = p.get("float2_id", "")
            if f2_id:
                pair_lookup[f2_id] = p
        print(f"Loaded {len(pairs)} sibling pairs for cross-reference")
    else:
        print("(No pairing map found — skipping cross-reference)")

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
        # 1. Check pairing map (sibling-paired OBJs)
        # 2. Check if it's a @264 export (MeshSize 297)
        # 3. Otherwise unknown
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
