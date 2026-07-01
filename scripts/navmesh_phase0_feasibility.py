"""navmesh_phase0_feasibility.py — Pure-Python navmesh feasibility analyzer.

Phase 0 of the navmesh navigation roadmap (docs/roadmap/navmesh-navigation-roadmap.md).
Answers the core question: can Recast-like algorithms produce a usable navmesh from
RIFT geometry?

Without RecastNavigation compiled, this provides a fast pure-Python proxy:
  - Parse OBJ (vertices + faces)
  - Classify triangles by slope (walkable vs. too-steep)
  - Project walkable triangles onto a 2D XZ grid
  - Find connected walkable regions via flood-fill
  - Report: total walkable area, largest contiguous region, coverage

Usage:
  python scripts/navmesh_phase0_feasibility.py [--obj <path>] [--cell-size <m>]
      [--max-slope <deg>] [--agent-height <m>] [--agent-radius <m>]
      [--max-climb <m>] [--out <json>] [--debug-obj <path>]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import deque
from pathlib import Path

# ---------------------------------------------------------------------------
# OBJ parser
# ---------------------------------------------------------------------------


def parse_obj(path: Path) -> tuple[list[tuple[float, float, float]], list[list[int]]]:
    """Parse a Wavefront OBJ file, returning (vertices, faces).

    Vertices are (x, y, z) float triples, 1-indexed.
    Faces are lists of 0-indexed vertex indices (triangles only, v1/vt1/vn1 format
    is accepted but only the vertex index is kept).
    """
    vertices: list[tuple[float, float, float]] = []
    faces: list[list[int]] = []

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if parts[0] == "v":
                vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif parts[0] == "f":
                indices: list[int] = []
                for token in parts[1:]:
                    # Handles "v", "v/vt", "v/vt/vn", "v//vn"
                    vi = int(token.split("/")[0])
                    # OBJ is 1-indexed; negative indices are relative to end
                    if vi < 0:
                        vi = len(vertices) + vi + 1
                    vi -= 1  # convert to 0-indexed
                    indices.append(vi)
                if len(indices) == 3:
                    faces.append(indices)

    return vertices, faces


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def triangle_normal(
    v0: tuple[float, float, float],
    v1: tuple[float, float, float],
    v2: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Compute the unnormalized face normal of triangle (v0, v1, v2)."""
    u = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
    v = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
    nx = u[1] * v[2] - u[2] * v[1]
    ny = u[2] * v[0] - u[0] * v[2]
    nz = u[0] * v[1] - u[1] * v[0]
    return (nx, ny, nz)


def normalize(v: tuple[float, float, float]) -> tuple[float, float, float]:
    """Normalize a 3D vector."""
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length == 0.0:
        return (0.0, 0.0, 0.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def slope_angle(normal: tuple[float, float, float]) -> float:
    """Return the slope angle in degrees (0 = perfectly horizontal, 90 = vertical).

    The normal is expected to be normalized. We compute the angle between
    the normal and the world-up vector (0, 1, 0) for Gamebryo/Y-up convention.
    """
    dot = abs(normal[1])  # Y component = cos(angle from horizontal)
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(math.acos(dot))


def triangle_area(
    v0: tuple[float, float, float],
    v1: tuple[float, float, float],
    v2: tuple[float, float, float],
) -> float:
    """Compute the area of a 3D triangle using the cross-product magnitude."""
    u = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
    v = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
    cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    return 0.5 * math.sqrt(cross[0] ** 2 + cross[1] ** 2 + cross[2] ** 2)


def triangle_xz_bounds(
    v0: tuple[float, float, float],
    v1: tuple[float, float, float],
    v2: tuple[float, float, float],
) -> tuple[float, float, float, float]:
    """Return (min_x, min_z, max_x, max_z) for the triangle."""
    min_x = min(v0[0], v1[0], v2[0])
    max_x = max(v0[0], v1[0], v2[0])
    min_z = min(v0[2], v1[2], v2[2])
    max_z = max(v0[2], v1[2], v2[2])
    return (min_x, min_z, max_x, max_z)


def point_in_triangle_xz(
    px: float,
    pz: float,
    v0: tuple[float, float, float],
    v1: tuple[float, float, float],
    v2: tuple[float, float, float],
) -> bool:
    """Test if point (px, pz) is inside the XZ projection of triangle (v0,v1,v2).

    Uses barycentric coordinates in 2D (XZ plane).
    """
    # 2D vectors
    x0, z0 = v0[0], v0[2]
    x1, z1 = v1[0], v1[2]
    x2, z2 = v2[0], v2[2]

    # Compute barycentric coordinates
    denom = (z1 - z2) * (x0 - x2) + (x2 - x1) * (z0 - z2)
    if abs(denom) < 1e-12:
        return False
    a = ((z1 - z2) * (px - x2) + (x2 - x1) * (pz - z2)) / denom
    b = ((z2 - z0) * (px - x2) + (x0 - x2) * (pz - z2)) / denom
    c = 1.0 - a - b
    return a >= -1e-10 and b >= -1e-10 and c >= -1e-10


# ---------------------------------------------------------------------------
# Grid-based walkability analysis
# ---------------------------------------------------------------------------


class Grid2D:
    """A 2D integer grid for walkability analysis."""

    def __init__(
        self,
        min_x: float,
        min_z: float,
        max_x: float,
        max_z: float,
        cell_size: float,
    ):
        self.min_x = min_x
        self.min_z = min_z
        self.cell_size = cell_size
        self.cols = max(1, int(math.ceil((max_x - min_x) / cell_size)))
        self.rows = max(1, int(math.ceil((max_z - min_z) / cell_size)))
        # 0 = empty, 1 = walkable
        self.cells: list[int] = [0] * (self.cols * self.rows)

    def _idx(self, col: int, row: int) -> int:
        return row * self.cols + col

    def world_to_cell(self, x: float, z: float) -> tuple[int, int]:
        """Convert world XZ to (col, row)."""
        col = int((x - self.min_x) / self.cell_size)
        row = int((z - self.min_z) / self.cell_size)
        col = max(0, min(self.cols - 1, col))
        row = max(0, min(self.rows - 1, row))
        return col, row

    def cell_to_world(self, col: int, row: int) -> tuple[float, float]:
        """Convert (col, row) to world XZ (cell center)."""
        return (
            self.min_x + (col + 0.5) * self.cell_size,
            self.min_z + (row + 0.5) * self.cell_size,
        )

    def mark_walkable(self, col: int, row: int) -> None:
        """Mark a cell as walkable."""
        if 0 <= col < self.cols and 0 <= row < self.rows:
            self.cells[self._idx(col, row)] = 1

    def is_walkable(self, col: int, row: int) -> bool:
        """Check if a cell is walkable."""
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return self.cells[self._idx(col, row)] == 1
        return False

    def walkable_count(self) -> int:
        """Return total number of walkable cells."""
        return sum(1 for c in self.cells if c == 1)

    def rasterize_triangle(
        self,
        v0: tuple[float, float, float],
        v1: tuple[float, float, float],
        v2: tuple[float, float, float],
    ) -> int:
        """Rasterize a triangle onto the grid. Returns count of cells marked."""
        min_x, min_z, max_x, max_z = triangle_xz_bounds(v0, v1, v2)
        c0, r0 = self.world_to_cell(min_x, min_z)
        c1, r1 = self.world_to_cell(max_x, max_z)
        count = 0
        for col in range(c0, c1 + 1):
            for row in range(r0, r1 + 1):
                if self.is_walkable(col, row):
                    continue
                cx, cz = self.cell_to_world(col, row)
                if point_in_triangle_xz(cx, cz, v0, v1, v2):
                    self.mark_walkable(col, row)
                    count += 1
        return count

    def find_connected_components(self) -> list[int]:
        """Find connected walkable components via 4-way flood-fill.

        Returns list of component sizes (cell counts).
        """
        visited: set[int] = set()
        components: list[int] = []

        for start_idx in range(len(self.cells)):
            if self.cells[start_idx] != 1 or start_idx in visited:
                continue

            # Flood-fill
            size = 0
            queue: deque[int] = deque([start_idx])
            visited.add(start_idx)

            while queue:
                idx = queue.popleft()
                size += 1
                col = idx % self.cols
                row = idx // self.cols

                # 4-way neighbors
                for dc, dr in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    nc, nr = col + dc, row + dr
                    nidx = self._idx(nc, nr)
                    if 0 <= nc < self.cols and 0 <= nr < self.rows and self.cells[nidx] == 1 and nidx not in visited:
                        visited.add(nidx)
                        queue.append(nidx)

            if size > 0:
                components.append(size)

        components.sort(reverse=True)
        return components


# ---------------------------------------------------------------------------
# Debug OBJ export
# ---------------------------------------------------------------------------


def write_debug_obj(
    path: Path,
    walkable_tris: list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]],
    non_walkable_tris: list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]],
) -> None:
    """Write a debug OBJ with walkable (green) and non-walkable (red) faces.

    Uses per-face materials for visualization in a 3D viewer.
    """
    all_verts: list[tuple[float, float, float]] = []
    walkable_faces: list[tuple[int, int, int]] = []
    non_walkable_faces: list[tuple[int, int, int]] = []

    def add_vertex(v: tuple[float, float, float]) -> int:
        all_verts.append(v)
        return len(all_verts)

    for v0, v1, v2 in walkable_tris:
        i0, i1, i2 = add_vertex(v0), add_vertex(v1), add_vertex(v2)
        walkable_faces.append((i0, i1, i2))

    for v0, v1, v2 in non_walkable_tris:
        i0, i1, i2 = add_vertex(v0), add_vertex(v1), add_vertex(v2)
        non_walkable_faces.append((i0, i1, i2))

    with open(path, "w", encoding="utf-8") as f:
        f.write("# Navmesh Phase 0 debug OBJ\n")
        f.write(f"# Walkable (green): {len(walkable_tris)} faces\n")
        f.write(f"# Non-walkable (red): {len(non_walkable_tris)} faces\n")

        for v in all_verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        f.write("usemtl walkable\n")
        for i0, i1, i2 in walkable_faces:
            f.write(f"f {i0} {i1} {i2}\n")

        f.write("usemtl non_walkable\n")
        for i0, i1, i2 in non_walkable_faces:
            f.write(f"f {i0} {i1} {i2}\n")


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------


def analyze_obj(
    path: Path,
    cell_size: float = 0.5,
    max_slope: float = 45.0,
    debug_obj: Path | None = None,
) -> dict:
    """Analyze an OBJ file for navmesh feasibility.

    Args:
        path: Path to OBJ file.
        cell_size: Grid cell size in world units.
        max_slope: Maximum walkable slope in degrees.
        debug_obj: If set, write a color-coded OBJ for visualization.

    Returns:
        Dict with walkability statistics.
    """
    vertices, faces = parse_obj(path)

    # Classify triangles
    walkable_tris: list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]] = []
    non_walkable_tris: list[
        tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
    ] = []
    total_area = 0.0
    walkable_area = 0.0

    # Compute global XZ bounds
    if not vertices:
        return {"error": "No vertices found", "file": str(path)}

    min_x = min(v[0] for v in vertices)
    max_x = max(v[0] for v in vertices)
    min_z = min(v[2] for v in vertices)
    max_z = max(v[2] for v in vertices)
    min_y = min(v[1] for v in vertices)
    max_y = max(v[1] for v in vertices)

    for face in faces:
        if len(face) != 3:
            continue
        v0, v1, v2 = vertices[face[0]], vertices[face[1]], vertices[face[2]]
        normal = normalize(triangle_normal(v0, v1, v2))
        slope = slope_angle(normal)
        area = triangle_area(v0, v1, v2)
        total_area += area

        if slope <= max_slope:
            walkable_tris.append((v0, v1, v2))
            walkable_area += area
        else:
            non_walkable_tris.append((v0, v1, v2))

    # Build 2D grid
    grid = Grid2D(min_x - cell_size, min_z - cell_size, max_x + cell_size, max_z + cell_size, cell_size)

    cells_rasterized = 0
    for v0, v1, v2 in walkable_tris:
        cells_rasterized += grid.rasterize_triangle(v0, v1, v2)

    # Find connected components
    components = grid.find_connected_components()
    largest_component = components[0] if components else 0
    component_count = len(components)

    # Compute coverage stats
    total_cells = grid.cols * grid.rows
    walkable_cells = grid.walkable_count()
    coverage_pct = (walkable_cells / total_cells * 100) if total_cells > 0 else 0.0

    # Build result
    result: dict = {
        "file": str(path),
        "bounds": {
            "x": [min_x, max_x],
            "y": [min_y, max_y],
            "z": [min_z, max_z],
        },
        "geometry": {
            "vertex_count": len(vertices),
            "face_count": len(faces),
            "total_area": round(total_area, 4),
            "walkable_area": round(walkable_area, 4),
            "walkable_face_count": len(walkable_tris),
            "non_walkable_face_count": len(non_walkable_tris),
            "walkable_pct": round(walkable_area / total_area * 100, 1) if total_area > 0 else 0.0,
        },
        "grid": {
            "cell_size": cell_size,
            "cols": grid.cols,
            "rows": grid.rows,
            "total_cells": total_cells,
            "walkable_cells": walkable_cells,
            "coverage_pct": round(coverage_pct, 1),
        },
        "connectivity": {
            "component_count": component_count,
            "largest_component_cells": largest_component,
            "largest_component_area": round(largest_component * cell_size * cell_size, 2),
            "all_component_sizes": components[:20],  # Top 20
        },
        "parameters": {
            "cell_size": cell_size,
            "max_slope_deg": max_slope,
        },
        "feasibility": _assess_feasibility(
            walkable_area=walkable_area,
            walkable_pct=walkable_area / total_area * 100 if total_area > 0 else 0,
            component_count=component_count,
            largest_component_cells=largest_component,
            coverage_pct=coverage_pct,
            bounds_area=(max_x - min_x) * (max_z - min_z),
        ),
    }

    # Debug OBJ
    if debug_obj:
        debug_obj = Path(debug_obj)
        debug_obj.parent.mkdir(parents=True, exist_ok=True)
        write_debug_obj(debug_obj, walkable_tris, non_walkable_tris)
        result["debug_obj"] = str(debug_obj)

    return result


def _assess_feasibility(
    *,
    walkable_area: float,
    walkable_pct: float,
    component_count: int,
    largest_component_cells: int,
    coverage_pct: float,
    bounds_area: float,
) -> dict:
    """Assess navmesh feasibility from the computed statistics.

    This is a heuristic assessment — it does NOT replace a proper Recast run.
    It answers the Phase 0 question: should we invest in building Recast?
    """
    signals: list[str] = []
    concerns: list[str] = []

    # Walkable surface exists?
    if walkable_area > 0.0:
        signals.append(f"Has walkable surfaces ({walkable_area:.1f} sq units, {walkable_pct:.1f}% of total area)")
    else:
        concerns.append("No walkable surfaces found — all faces exceed max slope")

    # Large contiguous regions?
    if largest_component_cells >= 10:
        signals.append(f"Largest contiguous walkable region: {largest_component_cells} cells")
    elif largest_component_cells > 0:
        concerns.append(
            f"Largest contiguous region is small ({largest_component_cells} cells) — may produce fragmented navmesh"
        )
    else:
        concerns.append("No connected walkable regions (isolated cells only)")

    # Multiple components?
    if component_count == 1:
        signals.append("Single connected walkable region — ideal for navmesh")
    elif component_count <= 5:
        concerns.append(f"{component_count} disconnected walkable regions — may need off-mesh connections")
    else:
        concerns.append(f"{component_count} disconnected regions — highly fragmented geometry")

    # Coverage
    if coverage_pct >= 5.0:
        signals.append(f"Walkable cells cover {coverage_pct:.1f}% of bounding rectangle")
    else:
        concerns.append(f"Low coverage ({coverage_pct:.1f}%) — geometry may be sparse")

    # Bounds area sanity
    if bounds_area < 1.0:
        concerns.append(f"Very small bounds area ({bounds_area:.1f} sq units) — mesh may be a single small object")

    # Overall verdict
    strong_signals = len(signals) >= 3 and len(concerns) <= 2
    verdict = (
        "PROMISING"
        if strong_signals and not concerns
        else "PROMISING_WITH_CAVEATS"
        if strong_signals
        else "NEEDS_INVESTIGATION"
        if signals
        else "BLOCKED"
    )

    return {
        "verdict": verdict,
        "signals": signals,
        "concerns": concerns,
        "recommendation": _recommendation(verdict),
    }


def _recommendation(verdict: str) -> str:
    if verdict == "PROMISING":
        return (
            "Strong walkability signals. Proceed with Phase 0 M0.3 (terrain vs. structure gap) "
            "and prepare for Phase 1 (Recast pipeline)."
        )
    elif verdict == "PROMISING_WITH_CAVEATS":
        return (
            "Walkable surfaces exist but have caveats. Proceed with Phase 0 but investigate "
            "the concerns listed. May need geometry filtering or zone-specific navmesh."
        )
    elif verdict == "NEEDS_INVESTIGATION":
        return (
            "Some walkable surfaces found but insufficient for confident navmesh. "
            "Need more geometry samples (export additional OBJs from larger structural assets) "
            "before Go/No-Go decision."
        )
    else:
        return (
            "No walkable surfaces found in this mesh. Try additional OBJs with different "
            "geometry (larger structural assets, terrain pieces). If none produce walkable "
            "surfaces, navmesh from NIF geometry may not be viable."
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 0 navmesh feasibility analyzer (pure Python)",
    )
    parser.add_argument(
        "--obj",
        default="Exports/decode-nif-geometry/decode-nif-geometry-mesh6.obj",
        help="Path to OBJ file (default: Exports/decode-nif-geometry/decode-nif-geometry-mesh6.obj)",
    )
    parser.add_argument(
        "--cell-size",
        type=float,
        default=0.5,
        help="Grid cell size in world units (default: 0.5)",
    )
    parser.add_argument(
        "--max-slope",
        type=float,
        default=45.0,
        help="Maximum walkable slope in degrees (default: 45)",
    )
    parser.add_argument(
        "--out",
        default="Exports/navmesh-phase0/feasibility-report.json",
        help="Output JSON path (default: Exports/navmesh-phase0/feasibility-report.json)",
    )
    parser.add_argument(
        "--debug-obj",
        default=None,
        help="If set, write a color-coded debug OBJ for visualization",
    )
    args = parser.parse_args()

    obj_path = Path(args.obj)
    if not obj_path.exists():
        print(f"ERROR: OBJ file not found: {obj_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing: {obj_path}")
    print(f"  Cell size: {args.cell_size}")
    print(f"  Max slope: {args.max_slope}°")
    print()

    debug_obj = Path(args.debug_obj) if args.debug_obj else None
    result = analyze_obj(
        obj_path,
        cell_size=args.cell_size,
        max_slope=args.max_slope,
        debug_obj=debug_obj,
    )

    # Print summary
    g = result.get("geometry", {})
    gr = result.get("grid", {})
    c = result.get("connectivity", {})
    f = result.get("feasibility", {})

    print(f"Geometry: {g.get('vertex_count', 0)} vertices, {g.get('face_count', 0)} faces")
    print(f"  Total area: {g.get('total_area', 0):.1f} sq units")
    print(f"  Walkable: {g.get('walkable_face_count', 0)} faces ({g.get('walkable_pct', 0):.1f}% of area)")
    print()
    print(f"Grid: {gr.get('cols', 0)}×{gr.get('rows', 0)} = {gr.get('total_cells', 0)} cells")
    print(f"  Walkable cells: {gr.get('walkable_cells', 0)} ({gr.get('coverage_pct', 0):.1f}%)")
    print()
    print(f"Connectivity: {c.get('component_count', 0)} connected regions")
    print(f"  Largest: {c.get('largest_component_cells', 0)} cells ({c.get('largest_component_area', 0):.1f} sq units)")
    comps = c.get("all_component_sizes", [])
    if len(comps) > 1:
        print(f"  Top components: {comps[:10]}")
    print()
    print(f"Verdict: {f.get('verdict', 'UNKNOWN')}")
    for s in f.get("signals", []):
        print(f"  [+] {s}")
    for con in f.get("concerns", []):
        print(f"  [!] {con}")
    print()
    print(f"Recommendation: {f.get('recommendation', '')}")

    # Write JSON
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2, default=str)
    print(f"\nReport written to: {out_path}")


if __name__ == "__main__":
    main()
