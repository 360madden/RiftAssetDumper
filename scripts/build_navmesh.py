"""build_navmesh.py — Phase 1 navmesh build pipeline using recast4j.

Takes a zone-filtered world-placed OBJ, runs the full Recast pipeline via
recast4j (Java port via jpype1), and produces a navmesh JSON + debug OBJ
for visualization.

Agent parameters are calibrated for world-scale RIFT geometry (coordinate
range ~3000 units). The default cell_size is derived from the geometry
bounding box to avoid 0-poly outputs on meshes of varying scale.

Prerequisites:
  - pip install jpype1
  - recast-1.5.7.jar + detour-1.5.7.jar in Exports/navmesh-phase1/lib/
  - JDK 21 at C:/RIFT MODDING/Tools/jdk-21.0.11+10

Usage:
  python scripts/build_navmesh.py --obj <zone-obj-path>
      [--cell-size 0.5] [--cell-height 0.25] [--agent-height 1.8]
      [--agent-radius 0.5] [--max-climb 0.5] [--max-slope 45]
      [--region-min-size 8] [--out <json>] [--debug-obj <path>]
      [--auto-cell-size] [--auto-agent-params] [--adaptive]

The --adaptive flag runs a slope-based feasibility analysis on the geometry
first, then adjusts agent_radius, max_slope, and region_min_size based on the
walkable face ratio:
  - High walkable (>=30%): standard params (no adjustment)
  - Mid walkable (10-29%): reduced agent_radius, 50deg max_slope, region_min=4
  - Low walkable (<10%): minimal agent_radius (0.05), 60deg max_slope, region_min=1
This prevents the 0-polys failure mode on steep geometry (e.g. ep2 architecture).

The --aggressive-adaptive flag implies --adaptive and uses the low_walkable
profile (60deg max_slope, 0.05 agent_radius) for mid_walkable zones (10-29%)
instead of the default mid_walkable profile. This maximizes polygon coverage
at the cost of including steep surfaces as walkable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path for scripts.* imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.navmesh_phase0_feasibility import (  # noqa: E402
    normalize,
    parse_obj,
    slope_angle,
    triangle_normal,
)

REPO_ROOT = _PROJECT_ROOT
RECAST_JAR = REPO_ROOT / "Exports" / "navmesh-phase1" / "lib" / "recast-1.5.7.jar"
DETOUR_JAR = REPO_ROOT / "Exports" / "navmesh-phase1" / "lib" / "detour-1.5.7.jar"
JDK_PATH = "C:/RIFT MODDING/Tools/jdk-21.0.11+10"
RC_WALKABLE_AREA = 63  # 0x3F — Recast standard walkable area
DEFAULT_OUT_DIR = REPO_ROOT / "Exports" / "navmesh-phase1"


def _start_jvm() -> None:
    """Start the JVM with recast4j jars on the classpath."""
    import jpype

    if jpype.isJVMStarted():
        return

    jvm_path = Path(JDK_PATH) / "bin" / "server" / "jvm.dll"
    if not jvm_path.exists():
        print(f"ERROR: JVM not found at {jvm_path}", file=sys.stderr)
        sys.exit(1)

    classpath = str(RECAST_JAR) + ";" + str(DETOUR_JAR)
    jpype.startJVM(
        str(jvm_path),
        classpath=[classpath],
        convertStrings=True,
    )


def _auto_cell_size(vertices: list[tuple[float, float, float]]) -> float:
    """Auto-calibrate cell_size from geometry bounding box.

    Rule: cell_size = max_extent / 200, clamped to [0.1, 2.0].
    This ensures the voxel grid is ~200 cells across the largest dimension,
    which is a good balance between resolution and performance for Recast.
    """
    if not vertices:
        return 0.5

    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    max_extent = max(
        max(xs) - min(xs),
        max(ys) - min(ys),
        max(zs) - min(zs),
    )
    cell = max_extent / 200.0
    return max(0.1, min(2.0, round(cell, 3)))


def _auto_agent_params(vertices: list[tuple[float, float, float]]) -> dict[str, float]:
    """Auto-calibrate agent parameters from geometry scale.

    For world-scale RIFT geometry (3000+ units), agent_height should be
    proportional to the geometry scale. A reasonable heuristic:
    agent_height = max(1.8, extent_y * 0.01), agent_radius = agent_height * 0.3.
    """
    if not vertices:
        return {"agent_height": 1.8, "agent_radius": 0.5, "agent_max_climb": 0.5}

    ys = [v[1] for v in vertices]
    extent_y = max(ys) - min(ys)

    agent_height = max(1.8, min(extent_y * 0.01, 10.0))
    agent_radius = max(0.3, agent_height * 0.3)
    agent_max_climb = max(0.3, agent_height * 0.25)

    return {
        "agent_height": round(agent_height, 2),
        "agent_radius": round(agent_radius, 2),
        "agent_max_climb": round(agent_max_climb, 2),
    }


def _compute_walkable_ratio(
    vertices: list[tuple[float, float, float]],
    faces: list[list[int]],
    max_slope: float = 45.0,
) -> dict[str, float | int]:
    """Compute the walkable face ratio of geometry.

    Uses the same slope classification as navmesh_phase0_feasibility.py:
    a face is walkable if its normal slope angle is <= max_slope.

    Returns a dict with:
      - walkable_faces: count of faces with slope <= max_slope
      - total_faces: total face count
      - walkable_ratio: walkable_faces / total_faces (0.0–1.0)
      - steep_ratio: 1.0 - walkable_ratio
    """
    if not faces:
        return {"walkable_faces": 0, "total_faces": 0, "walkable_ratio": 0.0, "steep_ratio": 0.0}

    walkable = 0
    for face in faces:
        if len(face) != 3:
            continue
        v0, v1, v2 = vertices[face[0]], vertices[face[1]], vertices[face[2]]
        normal = normalize(triangle_normal(v0, v1, v2))
        slope = slope_angle(normal)
        if slope <= max_slope:
            walkable += 1

    total = len(faces)
    ratio = walkable / total if total > 0 else 0.0
    return {
        "walkable_faces": walkable,
        "total_faces": total,
        "walkable_ratio": round(ratio, 4),
        "steep_ratio": round(1.0 - ratio, 4),
    }


def _adaptive_params(
    vertices: list[tuple[float, float, float]],
    faces: list[list[int]],
    base_params: dict[str, float] | None = None,
    base_cell_size: float | None = None,
    aggressive: bool = False,
) -> dict[str, float | int | str]:
    """Adaptively calibrate Recast parameters based on geometry walkability.

    Runs the slope-based feasibility analysis to compute the walkable face
    ratio, then adjusts agent_radius, max_slope, region_min_size, and cell_size:

      Walkable ratio >= 0.30 (high):  standard params (no adjustment)
      Walkable ratio 0.10–0.29 (mid):  reduced agent_radius, smaller regions, finer cells
      Walkable ratio <  0.10 (low):   minimal agent_radius, wider slope, tiny regions, finest cells

    When aggressive=True, mid_walkable zones (10-29%) use the low_walkable
    profile (60deg max_slope, minimal agent_radius=0.05, finest cells) to
    maximize polygon coverage on steep geometry. This trades walkability
    realism for navmesh completeness.

    The thresholds are calibrated from the two validated RIFT zones:
      - ep1 dungeons (~30-50% walkable) → standard params, 9 polys
      - ep2 architecture (17.5% walkable) → needs agent_radius=0.05, max_slope=60°, cell_size=0.1

    Args:
        vertices: OBJ vertex list.
        faces: OBJ face list (triangles).
        base_params: Optional base agent params (from _auto_agent_params).
                     If None, computed from vertices.
        base_cell_size: Optional base cell_size to adjust. If None, auto-computed.
        aggressive: If True, use low_walkable params for mid_walkable zones.

    Returns:
        Dict with adapted agent_radius, agent_max_slope, region_min_size,
        cell_size, cell_height, plus the walkability analysis used for the decision.
    """
    if base_params is None:
        base_params = _auto_agent_params(vertices)
    if base_cell_size is None:
        base_cell_size = _auto_cell_size(vertices)

    # Analyze walkability at the standard 45° threshold
    analysis = _compute_walkable_ratio(vertices, faces, max_slope=45.0)
    ratio = analysis["walkable_ratio"]

    # Start from base params
    agent_radius = base_params["agent_radius"]
    agent_max_slope = 45.0
    region_min_size = 8
    cell_size = base_cell_size
    profile = "high_walkable"

    if ratio < 0.10 or (aggressive and ratio < 0.30):
        # Very low walkable ratio (or aggressive mode on mid ratio):
        # geometry is mostly walls/steep surfaces.
        # Use minimal erosion, wider slope, tiny regions, and finest cell resolution.
        agent_radius = min(0.1, max(0.05, base_params["agent_radius"] * 0.1))
        agent_max_slope = 60.0
        region_min_size = 1
        cell_size = max(0.05, base_cell_size * 0.3)
        profile = "low_walkable" if ratio < 0.10 else "mid_walkable_aggressive"
    elif ratio < 0.30:
        # Moderate walkable ratio: reduce erosion, slightly wider slope, smaller regions.
        agent_radius = min(0.3, max(0.1, base_params["agent_radius"] * 0.2))
        agent_max_slope = 50.0
        region_min_size = 4
        cell_size = max(0.1, base_cell_size * 0.5)
        profile = "mid_walkable"
    # else: high walkable ratio — standard params are fine

    cell_height = round(cell_size * 0.5, 3)

    return {
        "agent_radius": round(agent_radius, 3),
        "agent_max_slope": agent_max_slope,
        "region_min_size": region_min_size,
        "cell_size": round(cell_size, 3),
        "cell_height": cell_height,
        "walkable_profile": profile,
        "walkable_ratio": ratio,
        "walkable_faces": analysis["walkable_faces"],
        "total_faces": analysis["total_faces"],
    }


def build_navmesh(
    vertices: list[tuple[float, float, float]],
    faces: list[list[int]],
    *,
    cell_size: float = 0.5,
    cell_height: float = 0.25,
    agent_height: float = 1.8,
    agent_radius: float = 0.5,
    agent_max_climb: float = 0.5,
    agent_max_slope: float = 45.0,
    region_min_size: int = 8,
    region_merge_size: int = 20,
    edge_max_len: float = 12.0,
    edge_max_error: float = 1.3,
    verts_per_poly: int = 6,
    detail_sample_dist: float = 6.0,
    detail_sample_max_error: float = 1.0,
) -> dict:
    """Build a navmesh from vertex/face arrays using recast4j.

    Uses SimpleInputGeomProvider for geometry and the non-tiled
    RecastConfig constructor from recast4j v1.5.7.

    Returns a dict with success status, mesh info, and polygon data.
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

    # Use provider's own bounds
    min_bounds = geom_provider.getMeshBoundsMin()
    max_bounds = geom_provider.getMeshBoundsMax()

    # Recast config — use JClass consistently (avoids needing jpype.imports)
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

    # Build
    builder = RecastBuilder()
    result = builder.build(geom_provider, builder_config)

    if result is None:
        return {"success": False, "error": "RecastBuilder returned null result"}

    # Extract polymesh data (public fields, not getters)
    mesh = result.getMesh()
    if mesh is None:
        return {"success": False, "error": "RecastBuilderResult.getMesh() returned null"}

    nvp = mesh.nvp
    npolys = mesh.npolys
    nverts = mesh.nverts
    polys_arr = mesh.polys
    verts_arr = mesh.verts
    regs_arr = mesh.regs

    # Extract polymesh vertices (integer coords, need to convert to world coords)
    # Recast stores vertices as integers: world = bmin + vert * cell_size
    bmin = min_bounds
    vert_list = []
    for i in range(nverts):
        base = i * 3
        vx = bmin[0] + float(verts_arr[base]) * cell_size
        vy = bmin[1] + float(verts_arr[base + 1]) * cell_height
        vz = bmin[2] + float(verts_arr[base + 2]) * cell_size
        vert_list.append([round(vx, 4), round(vy, 4), round(vz, 4)])

    # Extract polygons
    poly_list = []
    for i in range(npolys):
        base = i * nvp * 2
        poly_verts = []
        for j in range(nvp):
            vi = polys_arr[base + j]
            if vi == 0xFFFF:
                break
            poly_verts.append(int(vi))
        poly_list.append(poly_verts)

    # Count walkable polygons
    walkable_polys = sum(1 for i in range(npolys) if regs_arr[i] != 0)

    # Extract detail mesh
    detail_mesh = result.getMeshDetail()
    detail_tri_count = 0
    detail_vert_count = 0
    if detail_mesh is not None:
        detail_tri_count = int(detail_mesh.ntris) if hasattr(detail_mesh, "ntris") else len(detail_mesh.tris) // 4
        detail_vert_count = int(detail_mesh.nverts) if hasattr(detail_mesh, "nverts") else len(detail_mesh.verts) // 3

    return {
        "success": True,
        "mesh": {
            "npolys": int(npolys),
            "nverts": int(nverts),
            "nvp": int(nvp),
            "walkable_polys": int(walkable_polys),
            "detail_tris": detail_tri_count,
            "detail_verts": detail_vert_count,
        },
        "polys": poly_list,
        "verts": vert_list,
        "config": {
            "cell_size": cell_size,
            "cell_height": cell_height,
            "agent_height": agent_height,
            "agent_radius": agent_radius,
            "agent_max_climb": agent_max_climb,
            "agent_max_slope": agent_max_slope,
            "region_min_size": region_min_size,
            "region_merge_size": region_merge_size,
            "edge_max_len": edge_max_len,
            "edge_max_error": edge_max_error,
            "verts_per_poly": verts_per_poly,
            "detail_sample_dist": detail_sample_dist,
            "detail_sample_max_error": detail_sample_max_error,
        },
        "bounds": {
            "bmin": [float(bmin[0]), float(bmin[1]), float(bmin[2])],
            "bmax": [float(max_bounds[0]), float(max_bounds[1]), float(max_bounds[2])],
        },
    }


def export_navmesh_obj(result: dict, out_path: Path) -> None:
    """Export navmesh polygons as a debug OBJ for visualization."""
    verts = result.get("verts", [])
    polys = result.get("polys", [])

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Navmesh debug OBJ — generated by build_navmesh.py\n")
        f.write(f"# Polymesh: {len(polys)} polys, {len(verts)} verts\n")

        for v in verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        f.write("o navmesh\n")
        for poly in polys:
            if len(poly) >= 3:
                # Fan-triangulate polygons
                for j in range(1, len(poly) - 1):
                    f.write(f"f {poly[0] + 1} {poly[j] + 1} {poly[j + 1] + 1}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 1 navmesh build pipeline (recast4j)",
    )
    parser.add_argument("--obj", required=True, help="Path to OBJ file (zone-filtered or individual)")
    parser.add_argument("--cell-size", type=float, default=0.5)
    parser.add_argument("--cell-height", type=float, default=0.25)
    parser.add_argument("--agent-height", type=float, default=1.8)
    parser.add_argument("--agent-radius", type=float, default=0.5)
    parser.add_argument("--max-climb", type=float, default=0.5)
    parser.add_argument("--max-slope", type=float, default=45.0)
    parser.add_argument("--region-min-size", type=int, default=8)
    parser.add_argument("--auto-cell-size", action="store_true", help="Auto-calibrate cell_size from geometry bounds")
    parser.add_argument(
        "--auto-agent-params", action="store_true", help="Auto-calibrate agent params from geometry scale"
    )
    parser.add_argument(
        "--adaptive",
        action="store_true",
        help="Adaptively adjust agent_radius, max_slope, and region_min_size based on walkable face ratio. Implies --auto-agent-params.",
    )
    parser.add_argument(
        "--aggressive-adaptive",
        action="store_true",
        help="Use low_walkable profile (60deg slope, 0.05 radius) for mid_walkable zones to maximize poly coverage. Implies --adaptive.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output JSON path (default: Exports/navmesh-phase1/navmesh-build.json)",
    )
    parser.add_argument("--debug-obj", default=None, help="If set, write a debug OBJ for visualization")
    args = parser.parse_args()

    obj_path = Path(args.obj)
    if not obj_path.exists():
        print(f"ERROR: OBJ not found: {obj_path}", file=sys.stderr)
        sys.exit(1)

    if not RECAST_JAR.exists() or not DETOUR_JAR.exists():
        print(
            f"ERROR: recast4j jars not found at:\n  {RECAST_JAR}\n  {DETOUR_JAR}\n"
            f"Download them:\n"
            f"  curl -L -o {RECAST_JAR} https://repo1.maven.org/maven2/org/recast4j/recast/1.5.7/recast-1.5.7.jar\n"
            f"  curl -L -o {DETOUR_JAR} https://repo1.maven.org/maven2/org/recast4j/detour/1.5.7/detour-1.5.7.jar",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load geometry
    print(f"Loading OBJ: {obj_path}")
    vertices, faces = parse_obj(obj_path)
    print(f"  {len(vertices)} vertices, {len(faces)} faces")

    if not vertices:
        print("ERROR: No vertices in OBJ", file=sys.stderr)
        sys.exit(1)

    if not faces:
        print("ERROR: No faces in OBJ — cannot build navmesh from point-only geometry", file=sys.stderr)
        sys.exit(1)

    # Compute bounds
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    print(f"  Bounds: X[{min(xs):.1f}..{max(xs):.1f}] Y[{min(ys):.1f}..{max(ys):.1f}] Z[{min(zs):.1f}..{max(zs):.1f}]")

    # Auto-calibrate if requested
    cell_size = args.cell_size
    cell_height = args.cell_height
    agent_height = args.agent_height
    agent_radius = args.agent_radius
    agent_max_climb = args.max_climb

    if args.auto_cell_size:
        cell_size = _auto_cell_size(vertices)
        cell_height = round(cell_size * 0.5, 3)
        print(f"  Auto cell_size={cell_size}, cell_height={cell_height}")

    if args.adaptive or args.aggressive_adaptive or args.auto_agent_params:
        ap = _auto_agent_params(vertices)
        agent_height = ap["agent_height"]
        agent_radius = ap["agent_radius"]
        agent_max_climb = ap["agent_max_climb"]
        print(f"  Auto agent: height={agent_height}, radius={agent_radius}, climb={agent_max_climb}")

    # Adaptive parameter adjustment based on walkable face ratio
    max_slope = args.max_slope
    region_min_size = args.region_min_size

    if args.adaptive or args.aggressive_adaptive:
        adj = _adaptive_params(
            vertices,
            faces,
            base_params={
                "agent_height": agent_height,
                "agent_radius": agent_radius,
                "agent_max_climb": agent_max_climb,
            },
            base_cell_size=cell_size if args.auto_cell_size else None,
            aggressive=args.aggressive_adaptive,
        )
        agent_radius = adj["agent_radius"]
        max_slope = adj["agent_max_slope"]
        region_min_size = adj["region_min_size"]
        # Adaptive also adjusts cell_size for low/mid walkable zones
        cell_size = adj["cell_size"]
        cell_height = adj["cell_height"]
        print(
            f"  Adaptive: profile={adj['walkable_profile']}, "
            f"walkable_ratio={adj['walkable_ratio']:.1%} ({adj['walkable_faces']}/{adj['total_faces']} faces), "
            f"adjusted radius={agent_radius}, max_slope={max_slope}, "
            f"region_min={region_min_size}, cell_size={cell_size}"
        )

    # Start JVM and build
    print("\nStarting JVM with recast4j...")
    _start_jvm()

    print("Building navmesh...")
    print(
        f"  cell_size={cell_size}, cell_height={cell_height}, "
        f"agent_height={agent_height}, agent_radius={agent_radius}, "
        f"max_slope={max_slope}, region_min={region_min_size}"
    )

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

    if result["success"]:
        m = result["mesh"]
        print("\nNavmesh built successfully!")
        print(f"  Polys: {m['npolys']} ({m['walkable_polys']} walkable)")
        print(f"  Verts: {m['nverts']}")
        print(f"  Max verts/poly: {m['nvp']}")
        if m["detail_tris"]:
            print(f"  Detail tris: {m['detail_tris']}, detail verts: {m['detail_verts']}")
    else:
        print(f"\nERROR: {result.get('error', 'Unknown error')}")
        sys.exit(1)

    # Debug OBJ
    if args.debug_obj:
        dbg = Path(args.debug_obj)
        dbg.parent.mkdir(parents=True, exist_ok=True)
        export_navmesh_obj(result, dbg)
        print(f"Debug OBJ: {dbg}")

    # Write JSON (exclude large poly/vert arrays to keep it small)
    out_path = Path(args.out) if args.out else DEFAULT_OUT_DIR / "navmesh-build.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {k: v for k, v in result.items() if k not in ("polys", "verts")}
    serializable["poly_count"] = len(result.get("polys", []))
    serializable["vert_count"] = len(result.get("verts", []))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, default=str)
    print(f"Report: {out_path}")


if __name__ == "__main__":
    main()
