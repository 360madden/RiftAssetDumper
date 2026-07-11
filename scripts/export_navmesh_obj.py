"""export_navmesh_obj.py — Export a Recast navmesh as a debug OBJ.

Rebuilds the navmesh in memory from a source OBJ, then writes the polygon
mesh (and optional boundary edges) as a Wavefront OBJ with material
color-coding for RiftFlythrough visualization.

Usage:
  python scripts/export_navmesh_obj.py --obj <zone-obj-path>
      [--out <obj>] [--cell-size 0.5] [--agent-height 1.8]
      [--agent-radius 0.5] [--max-slope 45] [--region-min-size 8]
      [--auto-cell-size] [--auto-agent-params] [--adaptive]
      [--no-edges]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path for scripts.* imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.build_navmesh import (  # noqa: E402
    DETOUR_JAR,
    RECAST_JAR,
    _adaptive_params,
    _auto_agent_params,
    _auto_cell_size,
    _start_jvm,
    build_navmesh,
)
from scripts.navmesh_debug_export import export_navmesh_to_obj  # noqa: E402
from scripts.navmesh_phase0_feasibility import parse_obj  # noqa: E402

REPO_ROOT = _PROJECT_ROOT
DEFAULT_OUT_DIR = REPO_ROOT / "Exports" / "navmesh-phase5"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a Recast navmesh as a debug OBJ for visualization",
    )
    parser.add_argument("--obj", required=True, help="Path to source OBJ file")
    parser.add_argument("--out", default=None, help="Output OBJ path")
    parser.add_argument("--cell-size", type=float, default=0.5)
    parser.add_argument("--cell-height", type=float, default=0.25)
    parser.add_argument("--agent-height", type=float, default=1.8)
    parser.add_argument("--agent-radius", type=float, default=0.5)
    parser.add_argument("--max-climb", type=float, default=0.5)
    parser.add_argument("--max-slope", type=float, default=45.0)
    parser.add_argument("--region-min-size", type=int, default=8)
    parser.add_argument("--auto-cell-size", action="store_true")
    parser.add_argument("--auto-agent-params", action="store_true")
    parser.add_argument("--adaptive", action="store_true", help="Adaptive params (implies --auto-agent-params)")
    parser.add_argument("--no-edges", action="store_true", help="Skip boundary edge lines")
    args = parser.parse_args()

    obj_path = Path(args.obj)
    if not obj_path.exists():
        print(f"ERROR: OBJ not found: {obj_path}", file=sys.stderr)
        sys.exit(1)

    if not RECAST_JAR.exists() or not DETOUR_JAR.exists():
        print(f"ERROR: recast4j jars not found at:\n  {RECAST_JAR}\n  {DETOUR_JAR}", file=sys.stderr)
        sys.exit(1)

    vertices, faces = parse_obj(obj_path)
    print(f"Loading OBJ: {obj_path}")
    print(f"  {len(vertices)} vertices, {len(faces)} faces")

    if not vertices or not faces:
        print("ERROR: OBJ has no vertices or faces", file=sys.stderr)
        sys.exit(1)

    cell_size = args.cell_size
    cell_height = args.cell_height
    agent_height = args.agent_height
    agent_radius = args.agent_radius
    agent_max_climb = args.max_climb
    max_slope = args.max_slope
    region_min_size = args.region_min_size

    if args.auto_cell_size:
        cell_size = _auto_cell_size(vertices)
        cell_height = round(cell_size * 0.5, 3)
        print(f"  Auto cell_size={cell_size}, cell_height={cell_height}")

    if args.adaptive or args.auto_agent_params:
        ap = _auto_agent_params(vertices)
        agent_height = ap["agent_height"]
        agent_radius = ap["agent_radius"]
        agent_max_climb = ap["agent_max_climb"]
        print(f"  Auto agent: height={agent_height}, radius={agent_radius}, climb={agent_max_climb}")

    if args.adaptive:
        adj = _adaptive_params(
            vertices,
            faces,
            base_params={
                "agent_height": agent_height,
                "agent_radius": agent_radius,
                "agent_max_climb": agent_max_climb,
            },
            base_cell_size=cell_size if args.auto_cell_size else None,
        )
        agent_radius = adj["agent_radius"]
        max_slope = adj["agent_max_slope"]
        region_min_size = adj["region_min_size"]
        cell_size = adj["cell_size"]
        cell_height = adj["cell_height"]
        print(
            f"  Adaptive: profile={adj['walkable_profile']}, "
            f"walkable_ratio={adj['walkable_ratio']:.1%}, "
            f"radius={agent_radius}, max_slope={max_slope}, "
            f"region_min={region_min_size}, cell_size={cell_size}"
        )

    print("\nStarting JVM with recast4j...")
    _start_jvm()

    print("Building navmesh...")
    result = build_navmesh(
        vertices,
        faces,
        cell_size=cell_size,
        cell_height=cell_height,
        agent_height=agent_height,
        agent_radius=agent_radius,
        agent_max_climb=agent_max_climb,
        agent_max_slope=max_slope,
        region_min_size=region_min_size,
    )

    if not result.get("success"):
        print(f"ERROR: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)

    m = result["mesh"]
    print(f"\nNavmesh built: {m['npolys']} polys, {m['nverts']} verts")

    out_path = Path(args.out) if args.out else DEFAULT_OUT_DIR / f"{obj_path.stem}-navmesh-debug.obj"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    export_navmesh_to_obj(
        result["verts"],
        result["polys"],
        out_path,
        include_edges=not args.no_edges,
        name=obj_path.stem,
    )
    print(f"Debug OBJ: {out_path}")


if __name__ == "__main__":
    main()
