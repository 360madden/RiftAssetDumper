#!/usr/bin/env python3
"""build_world_placed_merge.py — Build a world-placed merged OBJ for RiftFlythrough.

Reads flythrough-index.json, loads each asset's world.json transform, applies the
transform (Scale → Rotate → Translate) to vertex positions, and writes a single
merged OBJ with per-mesh group markers.

The Rotation in world.json is a 3x3 row-major matrix: [r0c0,r0c1,r0c2, r1c0,r1c1,r1c2, r2c0,r2c1,r2c2].
Normals are rotated (no scale/translation). Face indices are offset-adjusted for merging.

Output: Assets/build/flythrough/world-placed-merged.obj
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH_DIR = REPO_ROOT / "Assets" / "build" / "flythrough"
INDEX_PATH = FLYTHROUGH_DIR / "flythrough-index.json"
OUTPUT_PATH = FLYTHROUGH_DIR / "world-placed-merged.obj"
WORLDS_DIR = REPO_ROOT / "Assets" / "build" / "flythrough" / "objs" / "worlds"

IDENTITY_ROTATION: list[float] = [1, 0, 0, 0, 1, 0, 0, 0, 1]
IDENTITY_TRANSLATION: list[float] = [0, 0, 0]
IDENTITY_SCALE: float = 1.0


def _load_json(path: Path, *, encoding: str = "utf-8") -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, encoding=encoding) as f:
            return json.load(f)
    except Exception as e:
        print(f"  WARN: failed to parse {path}: {e}")
        return {}


def _is_identity(trans: list[float], rot: list[float], scale: float) -> bool:
    return all(abs(v) < 1e-6 for v in trans) and rot == IDENTITY_ROTATION and abs(scale - 1.0) < 1e-6


def _transform_vertex(
    vx: float,
    vy: float,
    vz: float,
    trans: list[float],
    rot: list[float],
    scale: float,
) -> tuple[float, float, float]:
    """Scale → Rotate (3x3 row-major) → Translate."""
    sx, sy, sz = vx * scale, vy * scale, vz * scale
    rx = rot[0] * sx + rot[1] * sy + rot[2] * sz
    ry = rot[3] * sx + rot[4] * sy + rot[5] * sz
    rz = rot[6] * sx + rot[7] * sy + rot[8] * sz
    return rx + trans[0], ry + trans[1], rz + trans[2]


def _rotate_normal(
    nx: float,
    ny: float,
    nz: float,
    rot: list[float],
) -> tuple[float, float, float]:
    """Rotate a normal vector (no scale, no translation)."""
    rn_x = rot[0] * nx + rot[1] * ny + rot[2] * nz
    rn_y = rot[3] * nx + rot[4] * ny + rot[5] * nz
    rn_z = rot[6] * nx + rot[7] * ny + rot[8] * nz
    return rn_x, rn_y, rn_z


def _extract_transform(world_data: dict[str, Any]) -> tuple[list[float], list[float], float]:
    """Extract (Translation, Rotation, Scale) from world.json data."""
    nodes = world_data.get("Nodes", [])
    if nodes:
        node = nodes[0]
        return (
            node.get("Translation", IDENTITY_TRANSLATION[:]),
            node.get("Rotation", IDENTITY_ROTATION[:]),
            node.get("Scale", IDENTITY_SCALE),
        )
    return (IDENTITY_TRANSLATION[:], IDENTITY_ROTATION[:], IDENTITY_SCALE)


def _process_obj(
    obj_path: Path,
    asset_id: str,
    trans: list[float],
    rot: list[float],
    scale: float,
    offsets: dict[str, int],
    lines_out: list[str],
) -> tuple[bool, int]:
    """Process one OBJ file, returning (has_faces, vertices_added)."""
    if not obj_path.exists():
        print(f"  SKIP: OBJ not found: {obj_path}")
        return False, 0

    try:
        with open(obj_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"  SKIP: error reading {obj_path}: {e}")
        return False, 0

    # Check if this OBJ has faces
    has_faces = any(line.startswith("f ") for line in lines)

    # Group marker
    prefix = "" if has_faces else "ptonly_"
    lines_out.append(f"o {prefix}{asset_id}\n")

    identity = _is_identity(trans, rot, scale)
    v_added = 0
    vt_added = 0
    vn_added = 0

    for line in lines:
        parts = line.split()
        if not parts:
            lines_out.append(line)
            continue

        cmd = parts[0]

        if cmd == "v" and len(parts) >= 4:
            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
            if not identity:
                x, y, z = _transform_vertex(x, y, z, trans, rot, scale)
            lines_out.append(f"v {x:.6f} {y:.6f} {z:.6f}\n")
            v_added += 1

        elif cmd == "vt" and len(parts) >= 3:
            lines_out.append(line)
            vt_added += 1

        elif cmd == "vn" and len(parts) >= 4:
            nx, ny, nz = float(parts[1]), float(parts[2]), float(parts[3])
            if not identity:
                nx, ny, nz = _rotate_normal(nx, ny, nz, rot)
            lines_out.append(f"vn {nx:.6f} {ny:.6f} {nz:.6f}\n")
            vn_added += 1

        elif cmd in ("f", "p", "l"):
            new_parts: list[str] = [cmd]
            for face_part in parts[1:]:
                indices = face_part.split("/")
                new_indices: list[str] = []
                for i, idx_str in enumerate(indices):
                    if not idx_str:
                        new_indices.append("")
                        continue
                    idx = int(idx_str)
                    if idx > 0:
                        if i == 0:
                            idx += offsets["v"]
                        elif i == 1:
                            idx += offsets["vt"]
                        elif i == 2:
                            idx += offsets["vn"]
                    else:
                        # Relative index: offset from total+1
                        if i == 0:
                            idx = offsets["v"] + v_added + idx + 1
                        elif i == 1:
                            idx = offsets["vt"] + vt_added + idx + 1
                        elif i == 2:
                            idx = offsets["vn"] + vn_added + idx + 1
                    new_indices.append(str(idx))
                new_parts.append("/".join(new_indices))
            lines_out.append(" ".join(new_parts) + "\n")

        else:
            lines_out.append(line)

    offsets["v"] += v_added
    offsets["vt"] += vt_added
    offsets["vn"] += vn_added

    return has_faces, v_added


def main() -> None:
    if not INDEX_PATH.exists():
        print(f"ERROR: index not found: {INDEX_PATH}")
        sys.exit(1)

    with open(INDEX_PATH, encoding="utf-8") as f:
        manifest = json.load(f)

    assets: dict[str, dict[str, Any]] = manifest.get("assets", {})
    if not assets:
        print("No assets in index. Exiting.")
        sys.exit(0)

    offsets: dict[str, int] = {"v": 0, "vt": 0, "vn": 0}
    processed = 0
    skipped = 0
    faced_count = 0
    identity_count = 0

    total_assets = len(assets)
    lines_out: list[str] = ["# World-placed merged OBJ — generated by build_world_placed_merge.py\n"]
    lines_out.append(f"# {total_assets} assets indexed\n")
    lines_out.append("#\n")

    print(f"Processing {total_assets} assets...")
    for i, (asset_id, data) in enumerate(sorted(assets.items()), 1):
        obj_path_str = data.get("obj_path", "")
        if not obj_path_str:
            skipped += 1
            continue

        obj_path = Path(obj_path_str)
        world_json_file = data.get("world_json", f"{asset_id}.world.json")
        world_path = WORLDS_DIR / world_json_file

        if not world_path.exists():
            world_path = WORLDS_DIR / f"{asset_id}.world.json"

        world_data = _load_json(world_path, encoding="utf-8-sig")
        trans, rot, scale = _extract_transform(world_data)

        if _is_identity(trans, rot, scale):
            identity_count += 1

        has_faces, v_added = _process_obj(
            obj_path,
            asset_id,
            trans,
            rot,
            scale,
            offsets,
            lines_out,
        )

        if v_added == 0:
            skipped += 1
        else:
            processed += 1
            if has_faces:
                faced_count += 1

        if i % 50 == 0:
            print(f"  [{i}/{total_assets}] {processed} processed, {skipped} skipped...")

    # Write output
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines_out)

    # Report
    print(f"\nAssets indexed:  {len(assets)}")
    print(f"Processed:       {processed}")
    print(f"Skipped:         {skipped}")
    print(f"  Faced meshes:  {faced_count}")
    print(f"  Pos-only:      {processed - faced_count}")
    print(f"Identity xforms: {identity_count}")
    print(f"Total vertices:  {offsets['v']}")
    print(f"Total vt:        {offsets['vt']}")
    print(f"Total vn:        {offsets['vn']}")
    print(f"Output:          {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
