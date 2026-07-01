"""analyze_obb_shape.py — Oriented bounding-box shape analyzer for navmesh Phase 0.

Computes per-OBJ bounding box dimensions and height/width ratios to
discriminate floors (flat, wide) from walls (tall, thin) and structures
(cubic). Cross-validates shape labels against the slope-based walkability
verdicts from navmesh_phase0_feasibility.py.

Inputs:
  - Directory of OBJ files
  - Walkability classification JSON (optional, for cross-reference)
  - Feasibility reports directory (optional, for cross-validation)

Output:
  - Exports/navmesh-phase0/shape-analysis.json

Thresholds (calibrated from 10 exported RIFT meshes):
  - h/w < 0.2  → floor (very flat, e.g., mesh107 at h/w=0.043)
  - h/w 0.2-0.5 → platform (mostly flat, e.g., mesh83 at h/w=0.366)
  - h/w 0.5-1.5 → structure (cubic/mixed, e.g., mesh37 at h/w=0.999)
  - h/w >= 1.5  → wall_pillar (tall and thin)
  - w/h > 10    → override to floor (extremely wide relative to height)

Known limitation: Some meshes exported via --experimental-position-source
appear unit-cube normalized (2.0x2.0x2.0 at 6,489 vertices). These are
flagged as `shape_quality: "normalized_unit_cube"` and the shape label is
marked low-confidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "Exports" / "navmesh-phase0" / "shape-analysis.json"


# ---------------------------------------------------------------------------
# OBJ parsing
# ---------------------------------------------------------------------------


def parse_obj_bounds(obj_path: Path) -> dict | None:
    """Parse an OBJ file and return bounding box + vertex/face counts.

    Returns None if the file can't be read or has no vertices.
    """
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    vcount = 0
    fcount = 0

    try:
        with open(obj_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("v "):
                    parts = line.split()
                    if len(parts) < 4:
                        continue
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    min_x, max_x = min(min_x, x), max(max_x, x)
                    min_y, max_y = min(min_y, y), max(max_y, y)
                    min_z, max_z = min(min_z, z), max(max_z, z)
                    vcount += 1
                elif line.startswith("f "):
                    fcount += 1
    except OSError as exc:
        print(f"  WARNING: Cannot read {obj_path}: {exc}", file=sys.stderr)
        return None

    if vcount == 0:
        return None

    dx = max_x - min_x
    dy = max_y - min_y
    dz = max_z - min_z

    try:
        rel_path = str(obj_path.relative_to(REPO_ROOT))
    except ValueError:
        rel_path = str(obj_path.resolve())
    return {
        "path": rel_path,
        "filename": obj_path.name,
        "vertex_count": vcount,
        "face_count": fcount,
        "bbox": {
            "min": [round(min_x, 4), round(min_y, 4), round(min_z, 4)],
            "max": [round(max_x, 4), round(max_y, 4), round(max_z, 4)],
            "dx": round(dx, 4),
            "dy": round(dy, 4),
            "dz": round(dz, 4),
        },
    }


# ---------------------------------------------------------------------------
# Shape classification
# ---------------------------------------------------------------------------


def classify_shape(bounds: dict) -> dict:
    """Classify a mesh by its bounding-box shape.

    Uses height/width ratio (h/w) and width/height ratio (w/h) to
    discriminate floors, platforms, structures, and walls.
    """
    dx = bounds["bbox"]["dx"]
    dy = bounds["bbox"]["dy"]
    dz = bounds["bbox"]["dz"]

    # Use the larger of dx/dz as "width" (horizontal extent)
    width = max(dx, dz)
    height = dy

    # Avoid division by zero
    safe_width = max(width, 0.001)
    safe_height = max(height, 0.001)

    hw_ratio = height / safe_width  # < 1 = flat, > 1 = tall
    wh_ratio = safe_width / safe_height  # > 1 = wide, < 1 = tall

    # Detect unit-cube normalization: when a mesh with many vertices
    # has an exact or near-exact unit-cube bounding box, the dumper's
    # experimental-position-source likely normalized coordinates.
    is_unit_cube = (abs(dx - 2.0) < 0.01 and abs(dy - 2.0) < 0.01 and abs(dz - 2.0) < 0.01) or (
        abs(dx - 1.0) < 0.01 and abs(dy - 1.0) < 0.01 and abs(dz - 1.0) < 0.01
    )
    shape_quality = "normalized_unit_cube" if is_unit_cube else "raw"

    # Classify by height/width ratio
    if wh_ratio > 10.0:
        shape_label = "floor"
        shape_confidence = "high" if not is_unit_cube else "low"
    elif hw_ratio < 0.2:
        shape_label = "floor"
        shape_confidence = "high" if not is_unit_cube else "low"
    elif 0.2 <= hw_ratio < 0.5:
        shape_label = "platform"
        shape_confidence = "medium" if not is_unit_cube else "low"
    elif 0.5 <= hw_ratio < 1.5:
        shape_label = "structure"
        shape_confidence = "medium" if not is_unit_cube else "low"
    else:
        shape_label = "wall_pillar"
        shape_confidence = "high" if not is_unit_cube else "low"

    # Downgrade all confidence if unit-cube normalized
    if is_unit_cube:
        shape_confidence = "low"
        shape_quality = "normalized_unit_cube"

    return {
        "shape_label": shape_label,
        "shape_confidence": shape_confidence,
        "shape_quality": shape_quality,
        "hw_ratio": round(hw_ratio, 4),
        "wh_ratio": round(wh_ratio, 1),
        "is_unit_cube": is_unit_cube,
    }


# ---------------------------------------------------------------------------
# Cross-validation with feasibility verdicts
# ---------------------------------------------------------------------------


def cross_validate(
    shape: dict,
    feasibility_reports_dir: Path | None,
) -> dict | None:
    """Find the feasibility report for this mesh and compare verdicts.

    Matches by OBJ path components (mesh number + parent directory) to avoid
    collisions when different assets export to the same mesh block number.

    Returns cross-validation dict or None if no matching report found.
    """
    if feasibility_reports_dir is None:
        return None

    filename = shape["filename"]
    obj_path = shape.get("path", "")
    stem = Path(filename).stem  # e.g., "decode-nif-geometry-mesh83"

    # Extract mesh number from stem
    parts = stem.split("mesh")
    mesh_num = parts[-1] if len(parts) == 2 else ""

    # Try directory-aware match first (e.g., *nature-housing*mesh83*)
    if obj_path:
        # Extract parent directory from the relative path
        parent_dir = Path(obj_path).parent.name
        if parent_dir and parent_dir not in ("decode-nif-geometry", "."):
            # Directory-aware: only match reports in the same logical group
            dir_pattern = f"*{parent_dir}*mesh{mesh_num}*.json"
            matches = list(feasibility_reports_dir.glob(dir_pattern))
            if matches:
                report_path = matches[0].resolve()
                try:
                    with open(report_path, encoding="utf-8") as f:
                        report = json.load(f)
                except OSError, json.JSONDecodeError:
                    return None
                try:
                    rel_path = str(report_path.relative_to(REPO_ROOT))
                except ValueError:
                    rel_path = str(report_path)
                return {
                    "report_path": rel_path,
                    "slope_verdict": report.get("feasibility", {}).get("verdict"),
                    "walkable_cells": report.get("geometry", {}).get("walkable_cells"),
                    "walkable_pct": report.get("geometry", {}).get("walkable_pct"),
                    "largest_component_cells": report.get("connectivity", {}).get("largest_component_cells"),
                    "num_components": report.get("connectivity", {}).get("num_components"),
                }

    # Fallback: mesh-number-only pattern
    pattern = f"*{stem}.json"
    matches = list(feasibility_reports_dir.glob(pattern))
    if not matches:
        # Try broader: look for any report referencing this mesh name
        broader = f"*mesh{stem.split('mesh')[-1]}*.json" if "mesh" in stem else None
        if broader:
            # Extract just the number: decode-nif-geometry-mesh83 → 83
            parts = stem.split("mesh")
            if len(parts) == 2:
                broader = f"*mesh{parts[1]}*.json"
                matches = list(feasibility_reports_dir.glob(broader))

    if not matches:
        return None

    report_path = matches[0].resolve()  # Make absolute for safe relative_to
    try:
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
    except OSError, json.JSONDecodeError:
        return None

    try:
        rel_path = str(report_path.relative_to(REPO_ROOT))
    except ValueError:
        rel_path = str(report_path)
    return {
        "report_path": rel_path,
        "slope_verdict": report.get("feasibility", {}).get("verdict"),
        "walkable_cells": report.get("geometry", {}).get("walkable_cells"),
        "walkable_pct": report.get("geometry", {}).get("walkable_pct"),
        "largest_component_cells": report.get("connectivity", {}).get("largest_component_cells"),
        "num_components": report.get("connectivity", {}).get("num_components"),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze OBJ bounding-box shapes for wall/floor discrimination")
    parser.add_argument(
        "--obj-dir",
        default=str(REPO_ROOT / "Exports" / "navmesh-phase0" / "objs" / "decode-nif-geometry"),
        help="Directory of OBJ files to analyze",
    )
    parser.add_argument(
        "--feasibility-dir",
        default=str(REPO_ROOT / "Exports" / "navmesh-phase0"),
        help="Directory of feasibility reports for cross-validation",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help="Output JSON path",
    )
    args = parser.parse_args()

    obj_dir = Path(args.obj_dir)
    if not obj_dir.is_dir():
        print(f"ERROR: OBJ directory not found: {obj_dir}", file=sys.stderr)
        sys.exit(1)

    # Find all OBJs recursively
    obj_paths = sorted(obj_dir.rglob("*.obj"))
    if not obj_paths:
        print(f"ERROR: No OBJ files found in {obj_dir}", file=sys.stderr)
        sys.exit(1)

    print("=== Shape Analysis ===\n")
    print(f"OBJ directory: {obj_dir}")
    print(f"Found {len(obj_paths)} OBJ files\n")

    # Parse and classify each OBJ
    results: list[dict] = []
    shape_counts: Counter[str] = Counter()
    unit_cube_count = 0

    for obj_path in obj_paths:
        bounds = parse_obj_bounds(obj_path)
        if bounds is None:
            continue

        shape = classify_shape(bounds)
        shape_counts[shape["shape_label"]] += 1
        if shape["is_unit_cube"]:
            unit_cube_count += 1

        # Cross-validate with feasibility report
        feas_dir = Path(args.feasibility_dir) if args.feasibility_dir else None
        xv = cross_validate(bounds, feas_dir)

        entry = {
            **bounds,
            **shape,
        }
        if xv:
            entry["cross_validation"] = xv

        results.append(entry)

    # Summary
    print("=== Shape Label Distribution ===")
    for label, count in shape_counts.most_common():
        pct = count / len(results) * 100
        print(f"  {label}: {count} ({pct:.1f}%)")

    print(f"\nUnit-cube normalized: {unit_cube_count}/{len(results)} ({unit_cube_count / len(results) * 100:.1f}%)")

    # Compute cross-validation agreement
    agreement_count = 0
    disagreement_count = 0
    unknown_count = 0
    for r in results:
        xv = r.get("cross_validation")
        if xv is None:
            unknown_count += 1
            continue
        sv = xv.get("slope_verdict")
        sl = r["shape_label"]
        # Floors and platforms should be PROMISING or PROMISING_WITH_CAVEATS
        # Walls and structures may be either
        if sl in ("floor", "platform") and sv in ("PROMISING", "PROMISING_WITH_CAVEATS"):
            agreement_count += 1
        elif sl == "wall_pillar" and sv == "BLOCKED":
            agreement_count += 1
        elif sl == "structure" and sv != "BLOCKED":
            agreement_count += 1  # Structures can be walkable or not — neutral
        else:
            disagreement_count += 1

    if unknown_count < len(results):
        total_with_xv = len(results) - unknown_count
        print("\n=== Cross-Validation (shape vs. slope) ===")
        print(f"  With feasibility reports: {total_with_xv}/{len(results)}")
        print(f"  Agreement: {agreement_count}/{total_with_xv} ({agreement_count / max(total_with_xv, 1) * 100:.1f}%)")
        print(f"  Disagreement: {disagreement_count}/{total_with_xv}")
        if unknown_count:
            print(f"  No feasibility report: {unknown_count}/{len(results)}")

    # Show per-mesh results
    print("\n=== Per-Mesh Results ===")
    print(
        f"{'OBJ':45s} {'V':>6s} {'F':>6s} {'dx':>8s} {'dy':>8s} {'dz':>8s} "
        f"{'h/w':>7s} {'w/h':>7s} {'shape':>14s} {'quality':>22s}"
    )
    print("-" * 150)
    for r in results:
        b = r["bbox"]
        print(
            f"{r['filename']:45s} {r['vertex_count']:>6d} {r['face_count']:>6d} "
            f"{b['dx']:>8.1f} {b['dy']:>8.1f} {b['dz']:>8.1f} "
            f"{r['hw_ratio']:>7.3f} {r['wh_ratio']:>7.1f} "
            f"{r['shape_label']:>14s} {r['shape_quality']:>22s}"
        )

    # Write output
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "schema": "shape-analysis-v1",
        "generated_at": "2026-06-30",
        "summary": {
            "total_objs": len(results),
            "unit_cube_normalized": unit_cube_count,
            "unit_cube_pct": round(unit_cube_count / max(len(results), 1) * 100, 1),
            "shape_distribution": dict(shape_counts.most_common()),
            "cross_validation": {
                "agreement": agreement_count,
                "disagreement": disagreement_count,
                "unknown": unknown_count,
            },
        },
        "results": results,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
