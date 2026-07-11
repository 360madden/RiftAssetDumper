"""extract_zone_geometry.py — Zone-filtered world-placed OBJ extractor for navmesh Phase 1.

Reads flythrough-index.json, filters assets by zone tuple, applies world-space
transforms (Scale → Rotate → Translate) from each asset's world.json, and writes
a single merged OBJ containing only the selected zone's geometry.

This is the geometry input for the navmesh build pipeline (scripts/build_navmesh.py).

Inputs:
  - Assets/build/flythrough/flythrough-index.json (asset index with zone + obj paths)
  - Assets/build/flythrough/objs/worlds/<asset_id>.world.json (per-asset scene graph transforms)
  - Exports/navmesh-phase0/walkability-classification.json (optional walkability filter)

Output:
  - Exports/navmesh-phase1/zone-<slug>-walkable.obj (merged, world-placed OBJ)
  - Exports/navmesh-phase1/zone-<slug>-metadata.json (asset list, vertex/face counts, bounds)

Usage:
  python scripts/extract_zone_geometry.py --zone ep1.world_objects.dungeons
  python scripts/extract_zone_geometry.py --zone ep1.world_objects.dungeons --walkable-only
  python scripts/extract_zone_geometry.py --zone ep2.world_objects.architecture --out custom.obj
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path for scripts.* imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.build_world_placed_merge import (  # noqa: E402
    _compute_world_transform,
    _is_identity,
    _transform_vertex,
)

REPO_ROOT = _PROJECT_ROOT
FLYTHROUGH_DIR = REPO_ROOT / "Assets" / "build" / "flythrough"
INDEX_PATH = FLYTHROUGH_DIR / "flythrough-index.json"
WORLDS_DIR = FLYTHROUGH_DIR / "objs" / "worlds"
WALKABILITY_PATH = REPO_ROOT / "Exports" / "navmesh-phase0" / "walkability-classification.json"
DEFAULT_OUT_DIR = REPO_ROOT / "Exports" / "navmesh-phase1"


def _slugify(zone_tuple: str) -> str:
    """Convert a zone tuple like 'ep1.world_objects.dungeons' to a filesystem-safe slug."""
    return re.sub(r"[^a-zA-Z0-9]+", "-", zone_tuple).strip("-")


def _load_walkability() -> dict[str, str]:
    """Load walkability classification and return asset_id → label map."""
    if not WALKABILITY_PATH.exists():
        return {}
    with open(WALKABILITY_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {c["asset_id"]: c["label"] for c in data.get("classifications", [])}


def _load_obj_vertices_and_faces(obj_path: Path) -> tuple[list[tuple[float, float, float]], list[list[int]]]:
    """Load vertices and faces from an OBJ file.

    Reuses parse_obj from navmesh_phase0_feasibility (handles v, f, negative
    indices, triangle-only extraction). Flythrough OBJs are pre-triangulated
    by the C# dumper so no quad/n-gon handling is needed.
    """
    from scripts.navmesh_phase0_feasibility import parse_obj

    return parse_obj(obj_path)


def _resolve_obj_path(asset_id: str, data: dict[str, Any]) -> Path | None:
    """Find the OBJ file for an asset, trying multiple locations."""
    # Try flythrough objs dir first
    flythrough_obj = FLYTHROUGH_DIR / "objs" / f"{asset_id}.obj"
    if flythrough_obj.exists():
        return flythrough_obj

    # Try the obj_path from the index
    obj_path_str = data.get("obj_path", "")
    if obj_path_str:
        p = Path(obj_path_str)
        if p.exists():
            return p

    return None


def extract_zone(
    zone_tuple: str,
    *,
    walkable_only: bool = False,
    faced_only: bool = True,
    out_obj: Path | None = None,
    out_meta: Path | None = None,
) -> dict[str, Any]:
    """Extract zone-filtered geometry into a merged world-placed OBJ.

    Args:
        zone_tuple: Zone tuple string (e.g., "ep1.world_objects.dungeons").
        walkable_only: If True, only include assets labeled walkable_* or potentially_walkable.
        faced_only: If True, skip assets with 0 faces.
        out_obj: Output OBJ path. Defaults to Exports/navmesh-phase1/zone-<slug>-walkable.obj.
        out_meta: Output metadata JSON path. Defaults to ...-metadata.json.

    Returns:
        Metadata dict with asset list, vertex/face counts, and bounding box.
    """
    slug = _slugify(zone_tuple)
    if out_obj is None:
        out_obj = DEFAULT_OUT_DIR / f"zone-{slug}-walkable.obj"
    if out_meta is None:
        out_meta = DEFAULT_OUT_DIR / f"zone-{slug}-metadata.json"

    # Load index
    if not INDEX_PATH.exists():
        raise FileNotFoundError(f"flythrough-index.json not found: {INDEX_PATH}")
    with open(INDEX_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    assets: dict[str, dict[str, Any]] = manifest.get("assets", {})

    # Load walkability classification
    walkability = _load_walkability()
    walkable_labels = {
        "walkable_structure",
        "walkable_terrain",
        "walkable_floor",
        "walkable_platform",
        "potentially_walkable",
    }

    # Filter assets
    zone_assets: list[tuple[str, dict[str, Any]]] = []
    for aid, data in sorted(assets.items()):
        z = data.get("zone", {})
        if z.get("tuple") != zone_tuple:
            continue
        if faced_only and not data.get("faced", False):
            continue
        if walkable_only and walkability:
            label = walkability.get(aid, "unknown")
            if label not in walkable_labels:
                continue
        zone_assets.append((aid, data))

    if not zone_assets:
        raise ValueError(f"No assets found for zone '{zone_tuple}' with current filters")

    # Extract and merge geometry
    all_verts: list[tuple[float, float, float]] = []
    all_faces: list[list[int]] = []
    asset_records: list[dict[str, Any]] = []
    identity_count = 0
    v_offset = 0

    # Track bounds
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")

    for aid, data in zone_assets:
        obj_path = _resolve_obj_path(aid, data)
        if obj_path is None:
            asset_records.append({"asset_id": aid, "status": "obj_not_found"})
            continue

        vertices, faces = _load_obj_vertices_and_faces(obj_path)
        if not vertices:
            asset_records.append({"asset_id": aid, "status": "no_vertices"})
            continue

        # Load world transform
        world_json_file = data.get("world_json", f"{aid}.world.json")
        world_path = WORLDS_DIR / world_json_file
        if not world_path.exists():
            world_path = WORLDS_DIR / f"{aid}.world.json"

        world_data: dict[str, Any] = {}
        if world_path.exists():
            try:
                with open(world_path, encoding="utf-8-sig") as f:
                    world_data = json.load(f)
            except Exception:
                pass

        trans, rot, scale = _compute_world_transform(world_data)
        is_identity = _is_identity(trans, rot, scale)
        if is_identity:
            identity_count += 1

        # Transform vertices and accumulate
        for vx, vy, vz in vertices:
            if not is_identity:
                vx, vy, vz = _transform_vertex(vx, vy, vz, trans, rot, scale)
            all_verts.append((vx, vy, vz))
            min_x = min(min_x, vx)
            min_y = min(min_y, vy)
            min_z = min(min_z, vz)
            max_x = max(max_x, vx)
            max_y = max(max_y, vy)
            max_z = max(max_z, vz)

        # Offset faces
        for face in faces:
            all_faces.append([fi + v_offset for fi in face])

        v_offset += len(vertices)
        asset_records.append(
            {
                "asset_id": aid,
                "status": "ok",
                "vertex_count": len(vertices),
                "face_count": len(faces),
                "mesh_size": data.get("mesh_size"),
                "has_transform": not is_identity,
                "obj_path": str(obj_path),
            }
        )

    if not all_verts:
        raise ValueError(f"No vertices extracted for zone '{zone_tuple}'")

    # Write merged OBJ
    out_obj.parent.mkdir(parents=True, exist_ok=True)
    with open(out_obj, "w", encoding="utf-8") as f:
        f.write(f"# Zone-filtered world-placed OBJ — zone: {zone_tuple}\n")
        f.write(f"# {len(asset_records)} assets, {len(all_verts)} vertices, {len(all_faces)} faces\n")
        f.write("# Generated by extract_zone_geometry.py\n")
        for vx, vy, vz in all_verts:
            f.write(f"v {vx:.6f} {vy:.6f} {vz:.6f}\n")
        for face in all_faces:
            f.write(f"f {face[0] + 1} {face[1] + 1} {face[2] + 1}\n")

    # Build metadata
    ok_assets = [r for r in asset_records if r["status"] == "ok"]
    metadata = {
        "schema": "zone-geometry-v1",
        "zone_tuple": zone_tuple,
        "zone_slug": slug,
        "filters": {
            "walkable_only": walkable_only,
            "faced_only": faced_only,
        },
        "assets_total": len(zone_assets),
        "assets_extracted": len(ok_assets),
        "assets_skipped": len(asset_records) - len(ok_assets),
        "identity_transforms": identity_count,
        "non_identity_transforms": len(ok_assets) - identity_count,
        "geometry": {
            "vertex_count": len(all_verts),
            "face_count": len(all_faces),
            "bounds": {
                "min": [round(min_x, 2), round(min_y, 2), round(min_z, 2)],
                "max": [round(max_x, 2), round(max_y, 2), round(max_z, 2)],
                "extent": [
                    round(max_x - min_x, 2),
                    round(max_y - min_y, 2),
                    round(max_z - min_z, 2),
                ],
            },
        },
        "output_obj": str(out_obj),
        "assets": asset_records,
    }

    out_meta.parent.mkdir(parents=True, exist_ok=True)
    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract zone-filtered world-placed geometry for navmesh generation",
    )
    parser.add_argument(
        "--zone",
        required=True,
        help="Zone tuple (e.g., 'ep1.world_objects.dungeons')",
    )
    parser.add_argument(
        "--walkable-only",
        action="store_true",
        help="Only include assets classified as walkable (requires walkability-classification.json)",
    )
    parser.add_argument(
        "--include-pos-only",
        action="store_true",
        help="Include position-only assets (no faces). Default: skip them.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output OBJ path (default: Exports/navmesh-phase1/zone-<slug>-walkable.obj)",
    )
    parser.add_argument(
        "--out-meta",
        default=None,
        help="Output metadata JSON path (default: ...-metadata.json)",
    )
    args = parser.parse_args()

    out_obj = Path(args.out) if args.out else None
    out_meta = Path(args.out_meta) if args.out_meta else None

    print("=== Zone Geometry Extractor ===")
    print(f"Zone: {args.zone}")
    print(f"Walkable only: {args.walkable_only}")
    print(f"Include pos-only: {args.include_pos_only}")
    print()

    try:
        meta = extract_zone(
            args.zone,
            walkable_only=args.walkable_only,
            faced_only=not args.include_pos_only,
            out_obj=out_obj,
            out_meta=out_meta,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    g = meta["geometry"]
    b = g["bounds"]
    print(f"Assets: {meta['assets_extracted']}/{meta['assets_total']} extracted")
    print(f"  Identity transforms: {meta['identity_transforms']}")
    print(f"  Non-identity: {meta['non_identity_transforms']}")
    print(f"Geometry: {g['vertex_count']} vertices, {g['face_count']} faces")
    print(f"  Bounds: X[{b['min'][0]:.1f}..{b['max'][0]:.1f}] extent={b['extent'][0]:.1f}")
    print(f"          Y[{b['min'][1]:.1f}..{b['max'][1]:.1f}] extent={b['extent'][1]:.1f}")
    print(f"          Z[{b['min'][2]:.1f}..{b['max'][2]:.1f}] extent={b['extent'][2]:.1f}")
    print(f"Output OBJ: {meta['output_obj']}")
    print(f"Output metadata: {out_meta or DEFAULT_OUT_DIR / f'zone-{meta["zone_slug"]}-metadata.json'}")


if __name__ == "__main__":
    main()
