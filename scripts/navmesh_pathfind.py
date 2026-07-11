"""navmesh_pathfind.py — Phase 3 Detour A* pathfinding on a generated navmesh.

Takes a zone-filtered world-placed OBJ, builds a navmesh (Recast → Detour),
then runs A* pathfinding between two 3D points. Exports waypoints as JSON.

The pipeline:
  1. Load OBJ geometry (vertices + faces)
  2. Build Recast polymesh + detail mesh (same as build_navmesh.py)
  3. Convert to Detour NavMesh via NavMeshBuilder.createNavMeshData
  4. Create NavMeshQuery + DefaultQueryFilter
  5. findNearestPoly for start and goal (snaps to navmesh surface)
  6. findPath (A* through polygon graph)
  7. findStraightPath (string-pulling smoothing)
  8. Export waypoints as JSON

Prerequisites:
  - pip install jpype1
  - recast-1.5.7.jar + detour-1.5.7.jar in Exports/navmesh-phase1/lib/
  - JDK 21 at C:/RIFT MODDING/Tools/jdk-21.0.11+10

Usage:
  python scripts/navmesh_pathfind.py --obj <zone-obj-path>
      --from <x>,<y>,<z> --to <x>,<y>,<z>
      [--smooth] [--out <json>]
      [--cell-size 0.5] [--agent-height 1.8] [--agent-radius 0.5]
      [--max-slope 45] [--region-min-size 8]
      [--auto-cell-size] [--auto-agent-params] [--adaptive]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path for scripts.* imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.build_navmesh import (  # noqa: E402
    DETOUR_JAR,
    RC_WALKABLE_AREA,
    RECAST_JAR,
    _adaptive_params,
    _auto_agent_params,
    _auto_cell_size,
    _start_jvm,
)
from scripts.navmesh_debug_export import (  # noqa: E402
    export_navmesh_and_path,
    export_path_to_obj,
)
from scripts.navmesh_phase0_feasibility import parse_obj  # noqa: E402

REPO_ROOT = _PROJECT_ROOT
DEFAULT_OUT_DIR = REPO_ROOT / "Exports" / "navmesh-phase3"


# ── Pure-Python helpers (testable without JVM) ───────────────────────


def parse_coords(s: str) -> tuple[float, float, float]:
    """Parse a comma-separated coordinate string into a 3-tuple.

    Args:
        s: Coordinate string like "1234.5,56.7,890.1".

    Returns:
        Tuple of (x, y, z) floats.

    Raises:
        ValueError: If the string doesn't parse to exactly 3 floats.
    """
    parts = s.strip().split(",")
    if len(parts) != 3:
        raise ValueError(f"Expected 3 comma-separated values, got {len(parts)}: '{s}'")
    x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
    return (x, y, z)


def extract_waypoints_from_straight_path(items: list) -> list[dict]:
    """Convert Detour StraightPathItem objects to JSON-serializable dicts.

    Args:
        items: List of StraightPathItem Java objects (from findStraightPath).

    Returns:
        List of dicts with 'pos' ([x,y,z]), 'flags' (int), 'poly_ref' (int).
    """
    waypoints: list[dict] = []
    for item in items:
        pos = item.getPos()
        waypoints.append(
            {
                "pos": [float(pos[0]), float(pos[1]), float(pos[2])],
                "flags": int(item.getFlags()),
                "poly_ref": int(item.getRef()),
            }
        )
    return waypoints


def compute_path_distance(waypoints: list[dict]) -> float:
    """Compute the total Euclidean distance along a waypoint path.

    Args:
        waypoints: List of dicts with 'pos' key containing [x,y,z].

    Returns:
        Total path length in world units. 0.0 if fewer than 2 waypoints.
    """
    if len(waypoints) < 2:
        return 0.0
    total = 0.0
    for i in range(len(waypoints) - 1):
        p0 = waypoints[i]["pos"]
        p1 = waypoints[i + 1]["pos"]
        total += math.sqrt((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2 + (p1[2] - p0[2]) ** 2)
    return round(total, 4)


def validate_path(waypoints: list[dict], start: tuple[float, float, float], goal: tuple[float, float, float]) -> dict:
    """Validate a path's structural properties.

    Args:
        waypoints: List of waypoint dicts with 'pos' key.
        start: Original start coordinates (x,y,z).
        goal: Original goal coordinates (x,y,z).

    Returns:
        Dict with validation checks:
          - has_waypoints: bool
          - waypoint_count: int
          - start_matches: bool (first waypoint near start)
          - goal_matches: bool (last waypoint near goal)
          - no_backward_segments: bool
          - total_distance: float
    """
    checks: dict[str, bool | int | float] = {
        "has_waypoints": len(waypoints) > 0,
        "waypoint_count": len(waypoints),
    }

    if len(waypoints) >= 2:
        first = waypoints[0]["pos"]
        last = waypoints[-1]["pos"]
        start_dist = math.sqrt((first[0] - start[0]) ** 2 + (first[1] - start[1]) ** 2 + (first[2] - start[2]) ** 2)
        goal_dist = math.sqrt((last[0] - goal[0]) ** 2 + (last[1] - goal[1]) ** 2 + (last[2] - goal[2]) ** 2)
        checks["start_matches"] = start_dist < 5.0  # Within 5 world units
        checks["goal_matches"] = goal_dist < 5.0
        checks["total_distance"] = compute_path_distance(waypoints)
    else:
        checks["start_matches"] = False
        checks["goal_matches"] = False
        checks["total_distance"] = 0.0

    # Check no backward segments (each segment should make forward progress)
    no_backward = True
    if len(waypoints) >= 3:
        total_dir = [waypoints[-1]["pos"][i] - waypoints[0]["pos"][i] for i in range(3)]
        total_len = math.sqrt(sum(d * d for d in total_dir))
        if total_len > 0.001:
            for i in range(len(waypoints) - 1):
                seg = [waypoints[i + 1]["pos"][j] - waypoints[i]["pos"][j] for j in range(3)]
                dot = sum(seg[j] * total_dir[j] for j in range(3))
                if dot < -0.01 * total_len:
                    no_backward = False
                    break
    checks["no_backward_segments"] = no_backward

    return checks


# ── JVM-dependent functions ──────────────────────────────────────────


def _build_recast_and_detour(
    vertices: list[tuple[float, float, float]],
    faces: list[list[int]],
    *,
    cell_size: float,
    cell_height: float,
    agent_height: float,
    agent_radius: float,
    agent_max_climb: float,
    agent_max_slope: float,
    region_min_size: int,
    region_merge_size: int = 20,
    edge_max_len: float = 12.0,
    edge_max_error: float = 1.3,
    verts_per_poly: int = 6,
    detail_sample_dist: float = 6.0,
    detail_sample_max_error: float = 1.0,
) -> dict:
    """Build a Recast navmesh and convert it to a Detour NavMesh.

    Returns a dict with:
      - success: bool
      - navmesh: Java NavMesh object (if success)
      - query: Java NavMeshQuery object (if success)
      - filter: Java DefaultQueryFilter object (if success)
      - npolys: int (polygon count)
      - nverts: int (vertex count)
      - bounds: dict with bmin/bmax
      - config: dict of Recast parameters used
    """
    import jpype

    # Convert to flat arrays for SimpleInputGeomProvider
    verts_flat = jpype.JFloat[len(vertices) * 3]
    for i, (x, y, z) in enumerate(vertices):
        idx = i * 3
        verts_flat[idx] = x
        verts_flat[idx + 1] = y
        verts_flat[idx + 2] = z

    indices = jpype.JInt[len(faces) * 3]
    for i, face in enumerate(faces):
        idx = i * 3
        if len(face) >= 3:
            indices[idx] = face[0]
            indices[idx + 1] = face[1]
            indices[idx + 2] = face[2]

    # Create input geometry provider
    SIP = jpype.JClass("org.recast4j.recast.geom.SimpleInputGeomProvider")
    geom_provider = SIP(verts_flat, indices)

    min_bounds = geom_provider.getMeshBoundsMin()
    max_bounds = geom_provider.getMeshBoundsMax()

    # Recast config
    AreaMod = jpype.JClass("org.recast4j.recast.AreaModification")
    RecastBuilder = jpype.JClass("org.recast4j.recast.RecastBuilder")
    RecastBuilderConfig = jpype.JClass("org.recast4j.recast.RecastBuilderConfig")
    RecastConfig = jpype.JClass("org.recast4j.recast.RecastConfig")
    RecastConstants = jpype.JClass("org.recast4j.recast.RecastConstants")

    cfg = RecastConfig(
        RecastConstants.PartitionType.WATERSHED,
        float(cell_size),
        float(cell_height),
        float(agent_height),
        float(agent_radius),
        float(agent_max_climb),
        float(agent_max_slope),
        int(region_min_size),
        int(region_merge_size),
        float(edge_max_len),
        float(edge_max_error),
        int(verts_per_poly),
        float(detail_sample_dist),
        float(detail_sample_max_error),
        AreaMod(RC_WALKABLE_AREA),
    )

    builder_config = RecastBuilderConfig(cfg, min_bounds, max_bounds)
    builder = RecastBuilder()
    recast_result = builder.build(geom_provider, builder_config)

    if recast_result is None:
        return {"success": False, "error": "RecastBuilder returned null"}

    poly_mesh = recast_result.getMesh()
    if poly_mesh is None or poly_mesh.npolys == 0:
        return {"success": False, "error": "Recast polymesh is null or empty"}

    detail_mesh = recast_result.getMeshDetail()

    npolys = int(poly_mesh.npolys)
    nverts = int(poly_mesh.nverts)
    nvp = int(poly_mesh.nvp)

    # ── Convert Recast PolyMesh → Detour NavMesh ───────────────────
    NavMeshDataCreateParams = jpype.JClass("org.recast4j.detour.NavMeshDataCreateParams")
    NavMeshBuilder = jpype.JClass("org.recast4j.detour.NavMeshBuilder")
    NavMesh = jpype.JClass("org.recast4j.detour.NavMesh")
    NavMeshQuery = jpype.JClass("org.recast4j.detour.NavMeshQuery")
    DefaultQueryFilter = jpype.JClass("org.recast4j.detour.DefaultQueryFilter")

    params = NavMeshDataCreateParams()

    # Polygon mesh data (Recast integer coordinates)
    params.verts = poly_mesh.verts
    params.vertCount = nverts
    params.polys = poly_mesh.polys
    params.polyCount = npolys
    params.nvp = nvp

    # Poly flags and areas — all polys are walkable (flag=1, area=0)
    poly_flags = jpype.JInt[npolys]
    poly_areas = jpype.JInt[npolys]
    for i in range(npolys):
        poly_flags[i] = 1  # DT_POLYFLAGS_WALK
        poly_areas[i] = 0
    params.polyFlags = poly_flags
    params.polyAreas = poly_areas

    # Detail mesh data (if available)
    if detail_mesh is not None:
        params.detailMeshes = detail_mesh.meshes
        params.detailVerts = detail_mesh.verts
        params.detailVertsCount = int(detail_mesh.nverts)
        params.detailTris = detail_mesh.tris
        params.detailTriCount = int(detail_mesh.ntris)
    else:
        params.detailMeshes = None
        params.detailVerts = None
        params.detailVertsCount = 0
        params.detailTris = None
        params.detailTriCount = 0

    # No off-mesh connections
    params.offMeshConCount = 0

    # Tile/bounds info
    params.bmin = min_bounds
    params.bmax = max_bounds
    params.walkableHeight = float(agent_height)
    params.walkableRadius = float(agent_radius)
    params.walkableClimb = float(agent_max_climb)
    params.cs = float(cell_size)
    params.ch = float(cell_height)
    params.buildBvTree = True

    # Build Detour MeshData
    mesh_data = NavMeshBuilder.createNavMeshData(params)
    if mesh_data is None:
        return {"success": False, "error": "NavMeshBuilder.createNavMeshData returned null"}

    # Create NavMesh (single-tile, keep data in memory)
    navmesh = NavMesh(mesh_data, nvp, 0)

    # Create query and filter
    query = NavMeshQuery(navmesh)
    filter = DefaultQueryFilter()

    return {
        "success": True,
        "navmesh": navmesh,
        "query": query,
        "filter": filter,
        "npolys": npolys,
        "nverts": nverts,
        "bounds": {
            "bmin": [float(min_bounds[0]), float(min_bounds[1]), float(min_bounds[2])],
            "bmax": [float(max_bounds[0]), float(max_bounds[1]), float(max_bounds[2])],
        },
        "config": {
            "cell_size": cell_size,
            "cell_height": cell_height,
            "agent_height": agent_height,
            "agent_radius": agent_radius,
            "agent_max_climb": agent_max_climb,
            "agent_max_slope": agent_max_slope,
            "region_min_size": region_min_size,
        },
    }


def find_path(
    query: Any,
    filter: Any,
    start: tuple[float, float, float],
    goal: tuple[float, float, float],
    *,
    smooth: bool = True,
    search_extents: tuple[float, float, float] = (50.0, 50.0, 50.0),
    max_straight_path_points: int = 256,
) -> dict:
    """Run A* pathfinding on a Detour NavMeshQuery.

    Args:
        query: Java NavMeshQuery object.
        filter: Java DefaultQueryFilter object.
        start: Start position (x, y, z) in OBJ/world coordinates.
        goal: Goal position (x, y, z) in OBJ/world coordinates.
        smooth: If True, run findStraightPath for string-pulled waypoints.
        search_extents: Search box half-extents for findNearestPoly.
        max_straight_path_points: Max waypoints for findStraightPath.

    Returns:
        Dict with:
          - success: bool
          - start_poly_ref: int (polygon ref for start, 0 if not found)
          - goal_poly_ref: int
          - start_pos: [x,y,z] (snapped to navmesh)
          - goal_pos: [x,y,z] (snapped to navmesh)
          - raw_path: list of int poly refs (if A* succeeded)
          - raw_path_count: int
          - waypoints: list of dicts (if smooth=True and path found)
          - waypoint_count: int
          - error: str (if failed)
    """
    import jpype

    NavMeshQuery = jpype.JClass("org.recast4j.detour.NavMeshQuery")

    # Convert positions to Java float arrays (JFloat[n] creates array, JFloat(n) creates scalar)
    start_arr = jpype.JFloat[3]
    start_arr[0], start_arr[1], start_arr[2] = start
    goal_arr = jpype.JFloat[3]
    goal_arr[0], goal_arr[1], goal_arr[2] = goal

    extents_arr = jpype.JFloat[3]
    extents_arr[0], extents_arr[1], extents_arr[2] = search_extents

    # Find nearest polygons for start and goal
    start_result = query.findNearestPoly(start_arr, extents_arr, filter)
    if start_result.failed() or start_result.result is None:
        return {"success": False, "error": "findNearestPoly failed for start position"}

    start_ref = start_result.result.getNearestRef()
    start_pos = start_result.result.getNearestPos()
    if start_ref == 0:
        return {"success": False, "error": "No polygon found near start position"}

    goal_result = query.findNearestPoly(goal_arr, extents_arr, filter)
    if goal_result.failed() or goal_result.result is None:
        return {"success": False, "error": "findNearestPoly failed for goal position"}

    goal_ref = goal_result.result.getNearestRef()
    goal_pos = goal_result.result.getNearestPos()
    if goal_ref == 0:
        return {"success": False, "error": "No polygon found near goal position"}

    # Run A* pathfinding
    path_result = query.findPath(start_ref, goal_ref, start_arr, goal_arr, filter)
    if path_result.failed():
        return {
            "success": False,
            "error": f"findPath failed: {path_result.message}",
            "start_poly_ref": int(start_ref),
            "goal_poly_ref": int(goal_ref),
        }

    path_refs = path_result.result
    if path_refs is None or len(path_refs) == 0:
        return {
            "success": False,
            "error": "findPath returned empty path (start/goal may be on disconnected components)",
            "start_poly_ref": int(start_ref),
            "goal_poly_ref": int(goal_ref),
        }

    raw_path = [int(ref) for ref in path_refs]

    result: dict = {
        "success": True,
        "start_poly_ref": int(start_ref),
        "goal_poly_ref": int(goal_ref),
        "start_pos": [float(start_pos[0]), float(start_pos[1]), float(start_pos[2])],
        "goal_pos": [float(goal_pos[0]), float(goal_pos[1]), float(goal_pos[2])],
        "raw_path": raw_path,
        "raw_path_count": len(raw_path),
    }

    # String-pulling smoothing
    if smooth:
        straight_result = query.findStraightPath(
            start_arr,
            goal_arr,
            path_refs,
            int(max_straight_path_points),
            int(NavMeshQuery.DT_STRAIGHTPATH_ALL_CROSSINGS),
        )
        if straight_result.failed() or straight_result.result is None:
            result["waypoints"] = []
            result["waypoint_count"] = 0
            result["warning"] = "findStraightPath failed — returning raw poly path only"
        else:
            waypoints = extract_waypoints_from_straight_path(list(straight_result.result))
            result["waypoints"] = waypoints
            result["waypoint_count"] = len(waypoints)
    else:
        result["waypoints"] = []
        result["waypoint_count"] = 0

    return result


# ── CLI ──────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 3 Detour A* pathfinding on a navmesh",
    )
    parser.add_argument("--obj", required=True, help="Path to OBJ file (zone-filtered)")
    parser.add_argument("--from", dest="start", required=True, help="Start position: x,y,z")
    parser.add_argument("--to", dest="goal", required=True, help="Goal position: x,y,z")
    parser.add_argument(
        "--no-smooth",
        dest="smooth",
        action="store_false",
        default=True,
        help="Skip path smoothing (default: smoothing enabled)",
    )
    parser.add_argument("--out", default=None, help="Output JSON path")
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
    parser.add_argument("--search-extent", type=float, default=50.0, help="Search box half-extent for findNearestPoly")
    parser.add_argument("--debug-obj", default=None, help="If set, write a debug OBJ of the path for visualization")
    parser.add_argument(
        "--debug-navmesh",
        action="store_true",
        help="When used with --debug-obj, also include the navmesh in the debug OBJ",
    )
    parser.add_argument("--debug-edges", action="store_true", help="Include navmesh boundary edges in the debug OBJ")
    args = parser.parse_args()

    # Parse coordinates
    try:
        start = parse_coords(args.start)
        goal = parse_coords(args.goal)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    obj_path = Path(args.obj)
    if not obj_path.exists():
        print(f"ERROR: OBJ not found: {obj_path}", file=sys.stderr)
        sys.exit(1)

    if not RECAST_JAR.exists() or not DETOUR_JAR.exists():
        print(f"ERROR: recast4j jars not found at:\n  {RECAST_JAR}\n  {DETOUR_JAR}", file=sys.stderr)
        sys.exit(1)

    # Load geometry
    print(f"Loading OBJ: {obj_path}")
    vertices, faces = parse_obj(obj_path)
    print(f"  {len(vertices)} vertices, {len(faces)} faces")

    if not vertices or not faces:
        print("ERROR: OBJ has no vertices or faces", file=sys.stderr)
        sys.exit(1)

    # Auto-calibrate parameters
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

    # Start JVM
    print("\nStarting JVM with recast4j...")
    _start_jvm()

    # Build Recast + Detour navmesh
    print("Building navmesh (Recast -> Detour)...")
    navmesh_result = _build_recast_and_detour(
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

    if not navmesh_result["success"]:
        print(f"ERROR: {navmesh_result.get('error', 'Unknown')}", file=sys.stderr)
        sys.exit(1)

    print(f"  NavMesh: {navmesh_result['npolys']} polys, {navmesh_result['nverts']} verts")
    print(f"  Bounds: {navmesh_result['bounds']}")

    # Run pathfinding
    print(f"\nPathfinding: {start} -> {goal}")
    path_result = find_path(
        navmesh_result["query"],
        navmesh_result["filter"],
        start,
        goal,
        smooth=args.smooth,
        search_extents=(args.search_extent, args.search_extent, args.search_extent),
    )

    if path_result["success"]:
        print("\nPath found!")
        print(f"  Start poly: {path_result['start_poly_ref']}")
        print(f"  Goal poly:  {path_result['goal_poly_ref']}")
        print(f"  Raw path:   {path_result['raw_path_count']} polys")
        if path_result.get("waypoint_count", 0) > 0:
            wp = path_result["waypoints"]
            print(f"  Smoothed:   {path_result['waypoint_count']} waypoints")
            dist = compute_path_distance(wp)
            print(f"  Distance:   {dist:.2f} world units")
            for i, w in enumerate(wp):
                print(f"    [{i}] ({w['pos'][0]:.2f}, {w['pos'][1]:.2f}, {w['pos'][2]:.2f}) flags={w['flags']}")
    else:
        print(f"\nPathfinding failed: {path_result.get('error', 'Unknown')}")
        if "start_poly_ref" in path_result:
            print(f"  Start poly: {path_result['start_poly_ref']}")
            print(f"  Goal poly:  {path_result['goal_poly_ref']}")

    # Write JSON
    out_path = Path(args.out) if args.out else DEFAULT_OUT_DIR / "pathfind-result.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    output: dict = {
        "start": list(start),
        "goal": list(goal),
        "navmesh": {
            "npolys": navmesh_result["npolys"],
            "nverts": navmesh_result["nverts"],
            "bounds": navmesh_result["bounds"],
            "config": navmesh_result["config"],
        },
    }
    output.update(path_result)
    if path_result["success"] and path_result.get("waypoint_count", 0) > 0:
        output["validation"] = validate_path(path_result["waypoints"], start, goal)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nReport: {out_path}")

    # Optional debug OBJ export
    if args.debug_obj:
        debug_path = Path(args.debug_obj)
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        if not path_result["success"] or path_result.get("waypoint_count", 0) == 0:
            print("WARNING: No path waypoints available; skipping debug OBJ export", file=sys.stderr)
        elif args.debug_navmesh:
            waypoints = [tuple(w["pos"]) for w in path_result["waypoints"]]
            navmesh_result = {"verts": vertices, "polys": faces}
            export_navmesh_and_path(
                navmesh_result,
                waypoints,
                debug_path,
                include_edges=args.debug_edges,
                name=obj_path.stem,
            )
            print(f"Navmesh + path debug OBJ: {debug_path}")
        else:
            waypoints = [tuple(w["pos"]) for w in path_result["waypoints"]]
            export_path_to_obj(waypoints, debug_path, name=obj_path.stem)
            print(f"Path debug OBJ: {debug_path}")


if __name__ == "__main__":
    main()
