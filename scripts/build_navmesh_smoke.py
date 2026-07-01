"""build_navmesh_smoke.py — Phase 1 recast4j smoke test: OBJ → navmesh.

Uses jpype1 to bridge Python to recast4j (Java port of Recast/Detour).
Loads an OBJ file, passes geometry to Recast, builds a navigation mesh,
and exports the navmesh polygons as a debug OBJ for visualization.

Supports --debug-recast mode that runs the full Recast pipeline step-by-step
and dumps intermediate state (heightfield, compact heightfield) to JSON
for diagnosing 0-polys failures.

Prerequisites:
  - pip install jpype1
  - recast-1.5.7.jar and detour-1.5.7.jar in Exports/navmesh-phase1/lib/
  - JDK 21 at C:/RIFT MODDING/Tools/jdk-21.0.11+10

Usage:
  python scripts/build_navmesh_smoke.py --obj <path> [--cell-size 0.3]
      [--cell-height 0.2] [--agent-height 2.0] [--agent-radius 0.6]
      [--max-climb 0.9] [--max-slope 45] [--region-min-size 8]
      [--out <json>] [--debug-obj <path>] [--debug-recast <json>]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path for scripts.* imports
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import jpype  # noqa: E402 (must follow sys.path setup)
import jpype.imports  # noqa: E402, F401

from scripts.navmesh_phase0_feasibility import parse_obj  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
RECAST_JAR = REPO_ROOT / "Exports" / "navmesh-phase1" / "lib" / "recast-1.5.7.jar"
DETOUR_JAR = REPO_ROOT / "Exports" / "navmesh-phase1" / "lib" / "detour-1.5.7.jar"
JDK_PATH = "C:/RIFT MODDING/Tools/jdk-21.0.11+10"


def _start_jvm() -> None:
    """Start the JVM with recast4j jars on the classpath."""
    if jpype.isJVMStarted():
        return

    jvm_path = Path(JDK_PATH) / "bin" / "server" / "jvm.dll"
    if not jvm_path.exists():
        print(f"ERROR: JVM not found at {jvm_path}", file=sys.stderr)
        print("Set JAVA_HOME or install JDK 21 at C:/RIFT MODDING/Tools/jdk-21.0.11+10", file=sys.stderr)
        sys.exit(1)

    classpath = str(RECAST_JAR) + ";" + str(DETOUR_JAR)

    jpype.startJVM(
        str(jvm_path),
        classpath=[classpath],
        convertStrings=True,
    )


def _dump_heightfield(hf: jpype.JObject, label: str) -> dict:
    """Dump Heightfield state as a JSON-serializable dict."""
    w = hf.width
    h = hf.height
    spans = hf.spans
    # Count spans per cell
    grid = []
    total_spans = 0
    empty_cells = 0
    occupied_cells = 0
    min_span_count = 9999
    max_span_count = 0
    for y in range(h):
        row = []
        for x in range(w):
            count = 0
            span = spans[y * w + x]
            while span is not None:
                count += 1
                total_spans += 1
                span = span.next
            row.append(count)
            if count == 0:
                empty_cells += 1
            else:
                occupied_cells += 1
                min_span_count = min(min_span_count, count)
                max_span_count = max(max_span_count, count)
        grid.append(row)
    return {
        "label": label,
        "width": w,
        "height": h,
        "cell_size": hf.cs,
        "cell_height": hf.ch,
        "bmin": [hf.bmin[0], hf.bmin[1], hf.bmin[2]],
        "bmax": [hf.bmax[0], hf.bmax[1], hf.bmax[2]],
        "total_spans": total_spans,
        "empty_cells": empty_cells,
        "occupied_cells": occupied_cells,
        "min_spans_per_cell": min_span_count if occupied_cells > 0 else 0,
        "max_spans_per_cell": max_span_count if occupied_cells > 0 else 0,
        "grid": grid,
    }


def _dump_compact_heightfield(chf: jpype.JObject, label: str) -> dict:
    """Dump CompactHeightfield state as a JSON-serializable dict."""
    w = chf.width
    h = chf.height
    cells = chf.cells
    areas = chf.areas
    total_spans = chf.spanCount
    # Count walkable vs unwalkable cells and spans
    unwalkable_cells = 0
    walkable_cells = 0
    empty_cells = 0
    unwalkable_spans = 0
    walkable_spans = 0
    area_grid = []
    for y in range(h):
        row = []
        for x in range(w):
            cell = cells[y * w + x]
            if cell.count == 0:
                empty_cells += 1
                row.append(-1)
                continue
            # Check first span area for this cell
            span_idx = cell.index
            span_area = areas[span_idx]
            row.append(int(span_area))
            # Count all spans in this cell
            for s in range(cell.count):
                sa = areas[cell.index + s]
                if sa == 0:
                    unwalkable_spans += 1
                else:
                    walkable_spans += 1
            if span_area == 0:
                unwalkable_cells += 1
            else:
                walkable_cells += 1
        area_grid.append(row)
    return {
        "label": label,
        "width": w,
        "height": h,
        "cell_size": chf.cs,
        "cell_height": chf.ch,
        "total_spans": total_spans,
        "empty_cells": empty_cells,
        "unwalkable_cells": unwalkable_cells,
        "walkable_cells": walkable_cells,
        "unwalkable_spans": unwalkable_spans,
        "walkable_spans": walkable_spans,
        "max_regions": chf.maxRegions,
        "area_grid": area_grid,
    }


def _build_navmesh_debug(
    vertices: list[tuple[float, float, float]],
    faces: list[list[int]],
    cell_size: float = 0.3,
    cell_height: float = 0.2,
    agent_height: float = 2.0,
    agent_radius: float = 0.6,
    agent_max_climb: float = 0.9,
    agent_max_slope: float = 45.0,
    region_min_size: int = 8,
    region_merge_size: int = 20,
    edge_max_len: float = 12.0,
    edge_max_error: float = 1.3,
    verts_per_poly: int = 6,
    detail_sample_dist: float = 6.0,
    detail_sample_max_error: float = 1.0,
) -> tuple[dict | None, list[dict]]:
    """Run recast4j pipeline step-by-step, dumping intermediate state.

    Returns (result, debug_steps). debug_steps contains Heightfield and
    CompactHeightfield dumps at each stage.
    """
    debug_steps: list[dict] = []

    # Convert to flat arrays
    verts_flat = jpype.JFloat[len(vertices) * 3]
    for i, (x, y, z) in enumerate(vertices):
        idx = i * 3
        verts_flat[idx] = x
        verts_flat[idx + 1] = y
        verts_flat[idx + 2] = z

    indices = jpype.JInt[len(faces) * 3]
    tris = jpype.JInt[len(faces) * 3]
    for i, face in enumerate(faces):
        idx = i * 3
        if len(face) >= 3:
            indices[idx] = face[0]
            indices[idx + 1] = face[1]
            indices[idx + 2] = face[2]
            tris[idx] = face[0]
            tris[idx + 1] = face[1]
            tris[idx + 2] = face[2]

    SIP = jpype.JClass("org.recast4j.recast.geom.SimpleInputGeomProvider")
    geom = SIP(verts_flat, indices)

    # Import Java classes
    RecastConfig = jpype.JClass("org.recast4j.recast.RecastConfig")
    RecastBuilderConfig = jpype.JClass("org.recast4j.recast.RecastBuilderConfig")
    RecastConstants = jpype.JClass("org.recast4j.recast.RecastConstants")
    RecastVoxelization = jpype.JClass("org.recast4j.recast.RecastVoxelization")
    RecastFilter = jpype.JClass("org.recast4j.recast.RecastFilter")
    RecastCompact = jpype.JClass("org.recast4j.recast.RecastCompact")
    RecastArea = jpype.JClass("org.recast4j.recast.RecastArea")
    RecastRegion = jpype.JClass("org.recast4j.recast.RecastRegion")
    RecastContour = jpype.JClass("org.recast4j.recast.RecastContour")
    RecastMesh = jpype.JClass("org.recast4j.recast.RecastMesh")
    RecastMeshDetail = jpype.JClass("org.recast4j.recast.RecastMeshDetail")
    Telemetry = jpype.JClass("org.recast4j.recast.Telemetry")
    AreaMod = jpype.JClass("org.recast4j.recast.AreaModification")

    telemetry = Telemetry()

    # Step 1: Create RecastConfig
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
        AreaMod(0),
    )

    # Step 2: Calculate grid size and create Heightfield
    walkable_height = int(jpype.java.lang.Math.ceil(agent_height / cell_height))
    walkable_climb = int(jpype.java.lang.Math.floor(agent_max_climb / cell_height))
    walkable_radius = int(jpype.java.lang.Math.ceil(agent_radius / cell_size))
    border_size = walkable_radius + 3

    debug_steps.append(
        {
            "stage": "0_calc",
            "walkable_height_cells": walkable_height,
            "walkable_climb_cells": walkable_climb,
            "walkable_radius_cells": walkable_radius,
            "border_size": border_size,
            "cell_size": cell_size,
            "cell_height": cell_height,
            "agent_height": agent_height,
            "agent_radius": agent_radius,
            "agent_max_climb": agent_max_climb,
            "agent_max_slope": agent_max_slope,
            "region_min_size": region_min_size,
            "region_merge_size": region_merge_size,
        }
    )

    # Create heightfield (needs RecastBuilderConfig, not RecastConfig)
    builder_cfg = RecastBuilderConfig(cfg, geom.getMeshBoundsMin(), geom.getMeshBoundsMax())
    hf = RecastVoxelization.buildSolidHeightfield(geom, builder_cfg, telemetry)
    if hf is None:
        return None, debug_steps + [{"stage": "1_heightfield", "error": "null"}]

    debug_steps.append(_dump_heightfield(hf, "1_heightfield_raw"))

    # Step 3: Filter walkable spans
    RecastFilter.filterLowHangingWalkableObstacles(telemetry, walkable_climb, hf)
    debug_steps.append(_dump_heightfield(hf, "2_after_low_hanging"))

    RecastFilter.filterLedgeSpans(telemetry, walkable_height, walkable_climb, hf)
    debug_steps.append(_dump_heightfield(hf, "3_after_ledge"))

    RecastFilter.filterWalkableLowHeightSpans(telemetry, walkable_height, hf)
    debug_steps.append(_dump_heightfield(hf, "4_after_low_height"))

    # Step 4: Build compact heightfield
    chf = RecastCompact.buildCompactHeightfield(telemetry, walkable_height, walkable_climb, hf)
    if chf is None:
        return None, debug_steps + [{"stage": "5_compact", "error": "null"}]
    debug_steps.append(_dump_compact_heightfield(chf, "5_compact_raw"))

    # Step 5: Erode walkable area
    RecastArea.erodeWalkableArea(telemetry, walkable_radius, chf)
    debug_steps.append(_dump_compact_heightfield(chf, "6_after_erosion"))

    # Step 6: Build distance field
    _ = RecastRegion.buildDistanceField(telemetry, chf)
    debug_steps.append(_dump_compact_heightfield(chf, "7_distance_field"))

    # Step 7: Build regions
    min_region_area = region_min_size * region_min_size
    RecastRegion.buildRegions(telemetry, chf, border_size, min_region_area)
    debug_steps.append(_dump_compact_heightfield(chf, "8_regions"))

    # Step 8: Build contours
    build_flags = 1  # CONTOUR_TESS_WALL_EDGES
    contour_set = RecastContour.buildContours(telemetry, chf, edge_max_error, int(edge_max_len), build_flags)
    if contour_set is None:
        debug_steps.append({"stage": "9_contours", "error": "null"})
        return None, debug_steps
    nconts = contour_set.conts.size() if contour_set.conts else 0
    debug_steps.append(
        {
            "stage": "9_contours",
            "nconts": nconts,
            "bmin": [contour_set.bmin[0], contour_set.bmin[1], contour_set.bmin[2]],
            "cs": contour_set.cs,
            "ch": contour_set.ch,
        }
    )

    if nconts == 0:
        debug_steps.append({"stage": "ABORT", "reason": "0 contours"})
        return None, debug_steps

    # Step 9: Build polymesh
    poly_mesh = RecastMesh.buildPolyMesh(telemetry, contour_set, verts_per_poly)
    if poly_mesh is None:
        debug_steps.append({"stage": "10_polymesh", "error": "null"})
        return None, debug_steps
    debug_steps.append(
        {"stage": "10_polymesh", "npolys": poly_mesh.npolys, "nverts": poly_mesh.nverts, "nvp": poly_mesh.nvp}
    )

    # Step 10: Build detail mesh
    detail_mesh = RecastMeshDetail.buildPolyMeshDetail(
        telemetry, poly_mesh, chf, detail_sample_dist, detail_sample_max_error
    )

    # Extract result directly (RecastBuilderResult constructor is non-public)
    mesh = poly_mesh
    nvp = mesh.nvp
    npolys = mesh.npolys
    nverts = mesh.nverts
    polys_arr = mesh.polys
    verts_arr = mesh.verts
    regs_arr = mesh.regs

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

    vert_list = []
    for i in range(nverts):
        base = i * 3
        vert_list.append(
            [
                float(verts_arr[base]),
                float(verts_arr[base + 1]),
                float(verts_arr[base + 2]),
            ]
        )

    detail_tris = []
    detail_verts = []
    if detail_mesh is not None:
        dtris = detail_mesh.tris
        dverts = detail_mesh.verts
        for i in range(dtris.size // 4):
            base = i * 4
            detail_tris.append(
                [
                    dtris[base],
                    dtris[base + 1],
                    dtris[base + 2],
                    dtris[base + 3],
                ]
            )
        for i in range(dverts.size // 3):
            base = i * 3
            detail_verts.append(
                [
                    dverts[base],
                    dverts[base + 1],
                    dverts[base + 2],
                ]
            )

    walkable_polys = sum(1 for i in range(npolys) if regs_arr[i] != 0)

    navmesh_result = {
        "success": True,
        "mesh": {
            "npolys": npolys,
            "nverts": nverts,
            "nvp": nvp,
            "walkable_polys": walkable_polys,
        },
        "polys": poly_list,
        "verts": vert_list,
        "detail_tris": detail_tris,
        "detail_verts": detail_verts,
        "config": {
            "cell_size": cell_size,
            "cell_height": cell_height,
            "agent_height": agent_height,
            "agent_radius": agent_radius,
            "agent_max_climb": agent_max_climb,
            "agent_max_slope": agent_max_slope,
        },
    }

    return navmesh_result, debug_steps


def build_navmesh(
    vertices: list[tuple[float, float, float]],
    faces: list[list[int]],
    cell_size: float = 0.3,
    cell_height: float = 0.2,
    agent_height: float = 2.0,
    agent_radius: float = 0.6,
    agent_max_climb: float = 0.9,
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
    """
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

    # Create input geometry provider (computes its own bounds from vertices)
    SIP = jpype.JClass("org.recast4j.recast.geom.SimpleInputGeomProvider")
    geom_provider = SIP(verts_flat, indices)

    # Use provider's own bounds (matching recast4j test suite pattern)
    min_bounds = geom_provider.getMeshBoundsMin()
    max_bounds = geom_provider.getMeshBoundsMax()

    # RecastConfig non-tiled constructor (from recast4j source):
    #   RecastConfig(PartitionType, cellSize, cellHeight,
    #     agentHeight, agentRadius, agentMaxClimb, agentMaxSlope,
    #     regionMinSize, regionMergeSize, edgeMaxLen, edgeMaxError,
    #     vertsPerPoly, detailSampleDist, detailSampleMaxError,
    #     AreaModification)
    AreaMod = jpype.JClass("org.recast4j.recast.AreaModification")
    from org.recast4j.recast import (
        RecastBuilder,
        RecastBuilderConfig,
        RecastConfig,
        RecastConstants,
    )

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
        AreaMod(0),
    )

    builder_config = RecastBuilderConfig(cfg, min_bounds, max_bounds)

    # Build
    builder = RecastBuilder()
    result = builder.build(geom_provider, builder_config)

    if result is None:
        return {
            "success": False,
            "error": "RecastBuilder returned null result",
        }

    # Extract polymesh data (public fields, not getters)
    mesh = result.getMesh()
    if mesh is None:
        return {
            "success": False,
            "error": "RecastBuilderResult.getMesh() returned null",
        }
    nvp = mesh.nvp  # max verts per poly
    npolys = mesh.npolys
    nverts = mesh.nverts
    polys_arr = mesh.polys  # int[]
    verts_arr = mesh.verts  # int[]
    regs_arr = mesh.regs  # int[]

    # Extract detailed mesh if available
    detail_mesh = result.getMeshDetail()
    detail_tris = []
    detail_verts = []
    if detail_mesh is not None:
        dtris = detail_mesh.tris  # int[]
        dverts = detail_mesh.verts  # float[]
        for i in range(dtris.size // 4):
            base = i * 4
            detail_tris.append(
                [
                    dtris[base],
                    dtris[base + 1],
                    dtris[base + 2],
                    dtris[base + 3],
                ]
            )
        for i in range(dverts.size // 3):
            base = i * 3
            detail_verts.append(
                [
                    dverts[base],
                    dverts[base + 1],
                    dverts[base + 2],
                ]
            )

    # Convert polymesh to Python lists for serialization
    # polys layout: [maxpolys * 2 * nvp] — pairs of (vertIndex, neighborIndex)
    poly_list = []
    for i in range(npolys):
        base = i * nvp * 2
        poly_verts = []
        for j in range(nvp):
            vi = polys_arr[base + j]
            if vi == 0xFFFF:  # Recast sentinel for unused slot
                break
            poly_verts.append(int(vi))
        poly_list.append(poly_verts)

    # verts layout: [nverts * 3] — x,y,z as integers
    vert_list = []
    for i in range(nverts):
        base = i * 3
        vert_list.append(
            [
                float(verts_arr[base]),
                float(verts_arr[base + 1]),
                float(verts_arr[base + 2]),
            ]
        )

    # Count walkable polygons (regs[i] != 0 means walkable)
    walkable_polys = sum(1 for i in range(npolys) if regs_arr[i] != 0)

    return {
        "success": True,
        "mesh": {
            "npolys": npolys,
            "nverts": nverts,
            "nvp": nvp,
            "walkable_polys": walkable_polys,
        },
        "polys": poly_list,
        "verts": vert_list,
        "detail_tris": detail_tris,
        "detail_verts": detail_verts,
        "config": {
            "cell_size": cell_size,
            "cell_height": cell_height,
            "agent_height": agent_height,
            "agent_radius": agent_radius,
            "agent_max_climb": agent_max_climb,
            "agent_max_slope": agent_max_slope,
        },
    }


def export_navmesh_obj(result: dict, out_path: Path) -> None:
    """Export navmesh polygons as a debug OBJ for visualization."""
    verts = result.get("verts", [])
    polys = result.get("polys", [])
    detail_verts = result.get("detail_verts", [])
    detail_tris = result.get("detail_tris", [])

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Navmesh Phase 1 debug OBJ\n")
        f.write(f"# Polymesh: {len(polys)} polys, {len(verts)} verts\n")
        f.write(f"# Detail mesh: {len(detail_tris)} tris, {len(detail_verts)} verts\n")

        # Write polymesh vertices
        for v in verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        # Write detail mesh vertices (with offset)
        detail_offset = len(verts)
        for v in detail_verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        # Write polymesh faces (1-indexed for OBJ)
        f.write("usemtl navmesh\n")
        for poly in polys:
            if len(poly) >= 3:
                # Triangulate polygon (fan from first vertex)
                for j in range(1, len(poly) - 1):
                    f.write(f"f {poly[0] + 1} {poly[j] + 1} {poly[j + 1] + 1}\n")

        # Write detail mesh faces
        if detail_tris:
            f.write("usemtl detail\n")
            for tri in detail_tris:
                if len(tri) >= 3:
                    f.write(
                        f"f {tri[0] + detail_offset + 1} {tri[1] + detail_offset + 1} {tri[2] + detail_offset + 1}\n"
                    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1 recast4j navmesh smoke test")
    parser.add_argument("--obj", required=True, help="Path to OBJ file")
    parser.add_argument("--cell-size", type=float, default=0.3)
    parser.add_argument("--cell-height", type=float, default=0.2)
    parser.add_argument("--agent-height", type=float, default=2.0)
    parser.add_argument("--agent-radius", type=float, default=0.6)
    parser.add_argument("--max-climb", type=float, default=0.9)
    parser.add_argument("--max-slope", type=float, default=45.0)
    parser.add_argument("--region-min-size", type=int, default=8)
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "Exports" / "navmesh-phase1" / "navmesh-smoke.json"),
    )
    parser.add_argument("--debug-obj", default=None)
    parser.add_argument(
        "--debug-recast", default=None, help="Write intermediate Recast state (heightfield grids, etc.) to JSON"
    )
    args = parser.parse_args()

    obj_path = Path(args.obj)
    if not obj_path.exists():
        print(f"ERROR: OBJ not found: {obj_path}", file=sys.stderr)
        sys.exit(1)

    if not RECAST_JAR.exists() or not DETOUR_JAR.exists():
        print(
            f"ERROR: recast4j jars not found. Download them first:\n"
            f"  curl -L -o {RECAST_JAR} "
            f"https://repo1.maven.org/maven2/org/recast4j/recast/1.5.7/recast-1.5.7.jar\n"
            f"  curl -L -o {DETOUR_JAR} "
            f"https://repo1.maven.org/maven2/org/recast4j/detour/1.5.7/detour-1.5.7.jar",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Starting JVM with recast4j...")
    _start_jvm()

    print(f"Loading OBJ: {obj_path}")
    vertices, faces = parse_obj(obj_path)
    print(f"  {len(vertices)} vertices, {len(faces)} faces")

    # Compute mesh bounds for info
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    print(
        f"  Mesh bounds: X[{min(xs):.3f}..{max(xs):.3f}] "
        f"Y[{min(ys):.3f}..{max(ys):.3f}] Z[{min(zs):.3f}..{max(zs):.3f}]"
    )
    vert_extent = max(ys) - min(ys)
    print(f"  Vertical extent: {vert_extent:.3f}")

    if args.debug_recast:
        # Debug mode: step-by-step with intermediate dumps
        print("Building navmesh (DEBUG mode — step-by-step pipeline)...\n")
        result, debug_steps = _build_navmesh_debug(
            vertices,
            faces,
            cell_size=args.cell_size,
            cell_height=args.cell_height,
            agent_height=args.agent_height,
            agent_radius=args.agent_radius,
            agent_max_climb=args.max_climb,
            agent_max_slope=args.max_slope,
            region_min_size=args.region_min_size,
        )

        # Print step summaries
        for step in debug_steps:
            stage = step.get("stage", "?")
            if "grid" in step:
                occupied = step["occupied_cells"]
                empty = step["empty_cells"]
                total = occupied + empty
                total_spans = step.get("total_spans", 0)
                print(f"  [{stage}] {occupied}/{total} cells occupied, {total_spans} spans, {empty} empty")
            elif "walkable_cells" in step:
                w = step["walkable_cells"]
                u = step["unwalkable_cells"]
                e = step["empty_cells"]
                ws = step["walkable_spans"]
                us = step["unwalkable_spans"]
                print(
                    f"  [{stage}] {w} walkable, {u} unwalkable, {e} empty cells | {ws} walkable, {us} unwalkable spans"
                )
            elif "nconts" in step:
                print(f"  [{stage}] {step['nconts']} contours")
            elif "npolys" in step:
                print(f"  [{stage}] {step['npolys']} polys, {step['nverts']} verts")
            elif "reason" in step:
                print(f"  [{stage}] ABORTED: {step['reason']}")
            elif "error" in step:
                print(f"  [{stage}] ERROR: {step['error']}")
            else:
                # Stage 0 calculation
                print(
                    f"  [{stage}] walkable_height={step.get('walkable_height_cells', '?')}, "
                    f"walkable_radius={step.get('walkable_radius_cells', '?')}, "
                    f"border={step.get('border_size', '?')}"
                )

        # Save debug state
        debug_path = Path(args.debug_recast)
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(debug_steps, f, indent=2, default=str)
        print(f"\nDebug state: {debug_path}")

        if result is None or not result.get("success"):
            print("\nPipeline failed — see debug state for where it died.")
            sys.exit(1)
    else:
        # Fast path: single build call
        print("Building navmesh...")
        result = build_navmesh(
            vertices,
            faces,
            cell_size=args.cell_size,
            cell_height=args.cell_height,
            agent_height=args.agent_height,
            agent_radius=args.agent_radius,
            agent_max_climb=args.max_climb,
            agent_max_slope=args.max_slope,
            region_min_size=args.region_min_size,
        )

    if result["success"]:
        m = result["mesh"]
        print("Navmesh built successfully!")
        print(f"  Polys: {m['npolys']} ({m['walkable_polys']} walkable)")
        print(f"  Verts: {m['nverts']}")
        print(f"  Max verts/poly: {m['nvp']}")
        detail_tris = result.get("detail_tris", [])
        if detail_tris:
            print(f"  Detail tris: {len(detail_tris)}")
    else:
        print(f"ERROR: {result.get('error', 'Unknown error')}")
        sys.exit(1)

    # Debug OBJ
    if args.debug_obj:
        dbg = Path(args.debug_obj)
        dbg.parent.mkdir(parents=True, exist_ok=True)
        export_navmesh_obj(result, dbg)
        print(f"Debug OBJ: {dbg}")

    # Write JSON
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Remove large arrays from JSON to keep it small
    serializable = {k: v for k, v in result.items() if k not in ("polys", "verts", "detail_tris", "detail_verts")}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, default=str)
    print(f"Report: {out_path}")


if __name__ == "__main__":
    main()
