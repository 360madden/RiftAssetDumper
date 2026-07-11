"""validate_navmesh.py — Navmesh validation suite for Phase 1.

Loads a navmesh build JSON (from build_navmesh.py) and validates:
  - Poly count > 0
  - All polys have ≥3 vertices
  - No degenerate polys (area < epsilon)
  - Bounding box matches expected zone bounds
  - Max poly edge length ≤ threshold
  - All polys have at least one neighbor (no isolated islands)

Outputs a validation JSON with pass/fail per check.

Usage:
  python scripts/validate_navmesh.py --navmesh <navmesh-build.json>
      [--obj <zone-obj>] [--max-edge 50.0] [--out <validation.json>]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# Ensure project root is on sys.path for scripts.* imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

DEFAULT_OUT_DIR = _PROJECT_ROOT / "Exports" / "navmesh-phase1"


def _edge_length(v0: list[float], v1: list[float]) -> float:
    """Compute Euclidean distance between two 3D points."""
    return math.sqrt((v0[0] - v1[0]) ** 2 + (v0[1] - v1[1]) ** 2 + (v0[2] - v1[2]) ** 2)


def _poly_area(verts: list[list[float]], poly: list[int]) -> float:
    """Compute the area of a polygon (fan-triangulated)."""
    if len(poly) < 3:
        return 0.0
    total = 0.0
    for j in range(1, len(poly) - 1):
        v0 = verts[poly[0]]
        v1 = verts[poly[j]]
        v2 = verts[poly[j + 1]]
        # Triangle area via cross product
        ux, uy, uz = v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]
        vx, vy, vz = v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]
        cross_mag = math.sqrt((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2)
        total += 0.5 * cross_mag
    return total


def _build_adjacency(polys: list[list[int]]) -> dict[int, set[int]]:
    """Build poly-to-poly adjacency from shared vertices.

    Two polys are neighbors if they share ≥2 vertices (shared edge).
    """
    # Map vertex → set of poly indices
    vert_to_polys: dict[int, set[int]] = {}
    for pi, poly in enumerate(polys):
        for vi in poly:
            vert_to_polys.setdefault(vi, set()).add(pi)

    adjacency: dict[int, set[int]] = {i: set() for i in range(len(polys))}
    for pi, poly in enumerate(polys):
        vert_set = set(poly)
        for vi in vert_set:
            for pj in vert_to_polys.get(vi, set()):
                if pj <= pi:
                    continue
                # Check if they share ≥2 vertices (an edge)
                shared = vert_set & set(polys[pj])
                if len(shared) >= 2:
                    adjacency[pi].add(pj)
                    adjacency[pj].add(pi)

    return adjacency


def _find_isolated_polys(adjacency: dict[int, set[int]], poly_count: int) -> list[int]:
    """Find polys with no neighbors (isolated islands)."""
    return [i for i in range(poly_count) if len(adjacency.get(i, set())) == 0]


def _connected_components(adjacency: dict[int, set[int]], poly_count: int) -> list[int]:
    """Find connected components via flood-fill. Returns component sizes."""
    visited: set[int] = set()
    components: list[int] = []

    for start in range(poly_count):
        if start in visited:
            continue
        size = 0
        queue = [start]
        visited.add(start)
        while queue:
            pi = queue.pop()
            size += 1
            for neighbor in adjacency.get(pi, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        components.append(size)

    components.sort(reverse=True)
    return components


def validate_navmesh(
    navmesh: dict,
    *,
    zone_obj_path: Path | None = None,
    max_edge_length: float = 50.0,
    min_poly_area: float = 1e-8,
) -> dict:
    """Validate a navmesh build result.

    Args:
        navmesh: Navmesh build dict from build_navmesh.py.
        zone_obj_path: Optional zone OBJ to check bounds match.
        max_edge_length: Maximum allowed poly edge length in world units.
        min_poly_area: Minimum allowed poly area (degenerate check).

    Returns:
        Validation dict with per-check pass/fail and summary.
    """
    checks: list[dict] = []
    all_pass = True

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal all_pass
        checks.append({"check": name, "pass": passed, "detail": detail})
        if not passed:
            all_pass = False

    # Load full navmesh data (polys + verts are in the dict if loaded from file)
    polys = navmesh.get("polys", [])
    verts = navmesh.get("verts", [])
    mesh_info = navmesh.get("mesh", {})

    # If this is a summary-only JSON (no polys/verts), check what we can
    if not polys:
        npolys = mesh_info.get("npolys", 0)
        check("poly_count_gt_zero", npolys > 0, f"npolys={npolys}")
        check(
            "walkable_polys_gt_zero",
            mesh_info.get("walkable_polys", 0) > 0,
            f"walkable_polys={mesh_info.get('walkable_polys', 0)}",
        )
        return {
            "valid": all_pass,
            "checks": checks,
            "mesh_info": mesh_info,
            "note": "Summary-only JSON — poly-level checks skipped (no polys/verts arrays)",
        }

    npolys = len(polys)
    nverts = len(verts)

    # Check 1: Poly count > 0
    check("poly_count_gt_zero", npolys > 0, f"npolys={npolys}")

    # Check 2: All polys have ≥3 vertices
    bad_polys = [i for i, p in enumerate(polys) if len(p) < 3]
    check(
        "all_polys_min_3_verts",
        len(bad_polys) == 0,
        f"{len(bad_polys)} polys with <3 verts" if bad_polys else f"all {npolys} polys have ≥3 verts",
    )

    # Check 3: No degenerate polys
    degenerate = []
    for i, poly in enumerate(polys):
        if len(poly) >= 3:
            area = _poly_area(verts, poly)
            if area < min_poly_area:
                degenerate.append({"poly": i, "area": area})
    check(
        "no_degenerate_polys",
        len(degenerate) == 0,
        f"{len(degenerate)} degenerate polys" if degenerate else "all polys have area > epsilon",
    )

    # Check 4: Max poly edge length
    max_edge = 0.0
    long_edges = []
    for pi, poly in enumerate(polys):
        for j in range(len(poly)):
            v0 = verts[poly[j]]
            v1 = verts[poly[(j + 1) % len(poly)]]
            elen = _edge_length(v0, v1)
            if elen > max_edge:
                max_edge = elen
            if elen > max_edge_length:
                long_edges.append({"poly": pi, "edge": j, "length": round(elen, 2)})
    check(
        "max_edge_length_ok",
        len(long_edges) == 0,
        f"max_edge={max_edge:.1f}, threshold={max_edge_length}, {len(long_edges)} long edges"
        if long_edges
        else f"max_edge={max_edge:.1f}, threshold={max_edge_length}",
    )

    # Check 5: Bounding box
    if verts:
        min_x = min(v[0] for v in verts)
        max_x = max(v[0] for v in verts)
        min_y = min(v[1] for v in verts)
        max_y = max(v[1] for v in verts)
        min_z = min(v[2] for v in verts)
        max_z = max(v[2] for v in verts)
        bounds = {
            "min": [round(min_x, 2), round(min_y, 2), round(min_z, 2)],
            "max": [round(max_x, 2), round(max_y, 2), round(max_z, 2)],
            "extent": [round(max_x - min_x, 2), round(max_y - min_y, 2), round(max_z - min_z, 2)],
        }
        check("bounding_box_valid", bounds["extent"][0] > 0 and bounds["extent"][2] > 0, f"extent={bounds['extent']}")
    else:
        bounds = None
        check("bounding_box_valid", False, "no vertices")

    # Check 6: Adjacency / isolated polys
    adjacency = _build_adjacency(polys)
    isolated = _find_isolated_polys(adjacency, npolys)
    check(
        "no_isolated_polys",
        len(isolated) == 0,
        f"{len(isolated)} isolated polys (no neighbors)" if isolated else "all polys have ≥1 neighbor",
    )

    # Check 7: Connected components
    components = _connected_components(adjacency, npolys)
    check(
        "single_connected_component",
        len(components) == 1,
        f"{len(components)} components: {components[:10]}" if len(components) > 1 else "1 component",
    )

    # Zone bounds comparison if provided
    zone_bounds = None
    if zone_obj_path and zone_obj_path.exists():
        from scripts.navmesh_phase0_feasibility import parse_obj

        zv, _ = parse_obj(zone_obj_path)
        if zv:
            zmin_x = min(v[0] for v in zv)
            zmax_x = max(v[0] for v in zv)
            zmin_z = min(v[2] for v in zv)
            zmax_z = max(v[2] for v in zv)
            zone_bounds = {
                "min_x": round(zmin_x, 2),
                "max_x": round(zmax_x, 2),
                "min_z": round(zmin_z, 2),
                "max_z": round(zmax_z, 2),
            }
            if bounds:
                # Navmesh should be within or equal to zone bounds
                within = (
                    bounds["min"][0] >= zmin_x - 1.0
                    and bounds["max"][0] <= zmax_x + 1.0
                    and bounds["min"][2] >= zmin_z - 1.0
                    and bounds["max"][2] <= zmax_z + 1.0
                )
                check(
                    "navmesh_within_zone_bounds",
                    within,
                    f"navmesh X[{bounds['min'][0]}..{bounds['max'][0]}] vs zone X[{zmin_x:.1f}..{zmax_x:.1f}]",
                )

    return {
        "valid": all_pass,
        "checks": checks,
        "summary": {
            "npolys": npolys,
            "nverts": nverts,
            "walkable_polys": mesh_info.get("walkable_polys", 0),
            "isolated_polys": len(isolated),
            "connected_components": len(components),
            "component_sizes": components[:20],
            "max_edge_length": round(max_edge, 2),
            "degenerate_count": len(degenerate),
            "bounds": bounds,
            "zone_bounds": zone_bounds,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Navmesh validation suite")
    parser.add_argument("--navmesh", required=True, help="Path to navmesh build JSON")
    parser.add_argument("--obj", default=None, help="Optional zone OBJ for bounds comparison")
    parser.add_argument("--max-edge", type=float, default=50.0, help="Max allowed poly edge length")
    parser.add_argument("--out", default=None, help="Output validation JSON path")
    args = parser.parse_args()

    navmesh_path = Path(args.navmesh)
    if not navmesh_path.exists():
        print(f"ERROR: navmesh JSON not found: {navmesh_path}", file=sys.stderr)
        sys.exit(1)

    with open(navmesh_path, encoding="utf-8") as f:
        navmesh = json.load(f)

    # If the summary JSON doesn't have polys/verts, try loading from a full dump
    if not navmesh.get("polys"):
        print("Note: navmesh JSON is summary-only (no poly/vert arrays). Running summary checks.")

    result = validate_navmesh(
        navmesh,
        zone_obj_path=Path(args.obj) if args.obj else None,
        max_edge_length=args.max_edge,
    )

    print("=== Navmesh Validation ===\n")
    for c in result["checks"]:
        status = "PASS" if c["pass"] else "FAIL"
        print(f"  {status} {c['check']}: {c['detail']}")

    print(f"\n{'ALL CHECKS PASSED' if result['valid'] else 'VALIDATION FAILED'}")

    s = result.get("summary", {})
    if s:
        print("\nSummary:")
        print(f"  Polys: {s.get('npolys', '?')}")
        print(f"  Walkable: {s.get('walkable_polys', '?')}")
        print(f"  Isolated: {s.get('isolated_polys', 0)}")
        print(f"  Components: {s.get('connected_components', '?')}")
        if s.get("component_sizes"):
            print(f"  Component sizes: {s['component_sizes'][:10]}")
        print(f"  Max edge: {s.get('max_edge_length', '?')}")

    out_path = Path(args.out) if args.out else DEFAULT_OUT_DIR / "navmesh-validation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nValidation report: {out_path}")

    if not result["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
