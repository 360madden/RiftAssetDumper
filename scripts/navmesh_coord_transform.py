"""navmesh_coord_transform.py — OBJ↔live-memory coordinate transform API.

Provides the mathematical mapping between navmesh/world coordinates (derived
from extracted OBJ geometry) and live RIFT memory coordinates (read by
RiftReader).  The transform is affine:

    memory = (obj * scale * axis_mapping) + offset
    obj    = (memory - offset) / (scale * axis_mapping)

Usage as a module:
    from scripts.navmesh_coord_transform import load_transform, obj_to_memory, memory_to_obj

Usage as a CLI:
    python scripts/navmesh_coord_transform.py --transform Exports/navmesh-phase2/coord-transform.json --obj-to-mem 1.0,2.0,3.0
    python scripts/navmesh_coord_transform.py --transform Exports/navmesh-phase2/coord-transform.json --mem-to-obj 10.0,20.0,30.0
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

# ============================================================================
# Constants
# ============================================================================

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRANSFORM_PATH = REPO_ROOT / "Exports" / "navmesh-phase2" / "coord-transform.json"


# ============================================================================
# Transform I/O
# ============================================================================


def load_transform(path: str | Path) -> dict[str, Any]:
    """Load a coordinate transform from JSON.

    Args:
        path: Path to the transform JSON file.

    Returns:
        A dict with keys ``scale``, ``offset``, ``axis_mapping``,
        ``confidence_rmse``, and ``validation_tolerance``.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the JSON is malformed or missing required fields.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Transform file not found: {p}")

    data = json.loads(p.read_text(encoding="utf-8"))
    _validate_transform(data)
    return data


def save_transform(transform: dict[str, Any], path: str | Path) -> None:
    """Save a coordinate transform to JSON.

    Args:
        transform: Transform dict to serialize.
        path: Destination path.
    """
    _validate_transform(transform)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(transform, indent=2), encoding="utf-8")


def _validate_transform(data: dict[str, Any]) -> None:
    """Validate that a transform dict has the required shape."""
    required = {"scale", "offset", "axis_mapping"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Transform missing required fields: {sorted(missing)}")

    for key in required:
        value = data[key]
        if not isinstance(value, list) or len(value) != 3:
            raise ValueError(f"Transform field '{key}' must be a list of 3 floats")
        if not all(isinstance(v, (int, float)) for v in value):
            raise ValueError(f"Transform field '{key}' must contain only numbers")


# ============================================================================
# Transform math
# ============================================================================


def _to_tuple(value: list[float] | tuple[float, ...]) -> tuple[float, float, float]:
    """Convert a 3-element sequence to a tuple."""
    return (float(value[0]), float(value[1]), float(value[2]))


def obj_to_memory(
    x: float,
    y: float,
    z: float,
    transform: dict[str, Any],
) -> tuple[float, float, float]:
    """Convert OBJ/world coordinates to live memory coordinates.

    Args:
        x, y, z: OBJ coordinates.
        transform: Transform dict with ``scale``, ``offset``, ``axis_mapping``.

    Returns:
        Memory coordinates (px, py, pz).
    """
    scale = _to_tuple(transform["scale"])
    offset = _to_tuple(transform["offset"])
    axis_mapping = _to_tuple(transform["axis_mapping"])

    return (
        x * scale[0] * axis_mapping[0] + offset[0],
        y * scale[1] * axis_mapping[1] + offset[1],
        z * scale[2] * axis_mapping[2] + offset[2],
    )


def memory_to_obj(
    px: float,
    py: float,
    pz: float,
    transform: dict[str, Any],
) -> tuple[float, float, float]:
    """Convert live memory coordinates to OBJ/world coordinates.

    Args:
        px, py, pz: Memory coordinates.
        transform: Transform dict with ``scale``, ``offset``, ``axis_mapping``.

    Returns:
        OBJ coordinates (x, y, z).
    """
    scale = _to_tuple(transform["scale"])
    offset = _to_tuple(transform["offset"])
    axis_mapping = _to_tuple(transform["axis_mapping"])

    return (
        (px - offset[0]) / (scale[0] * axis_mapping[0]),
        (py - offset[1]) / (scale[1] * axis_mapping[1]),
        (pz - offset[2]) / (scale[2] * axis_mapping[2]),
    )


def compute_transform(
    samples: dict[str, Any],
    *,
    validation_tolerance: float = 0.5,
) -> dict[str, Any]:
    """Compute an affine transform from calibration samples.

    The transform is computed by least-squares fitting:

        memory = (obj * scale * axis_mapping) + offset

    Axis mapping is determined by sign of per-axis correlations.  Scale and
    offset are then solved per-axis via simple linear regression.

    Args:
        samples: Calibration samples dict with a ``landmarks`` list.  Each
            landmark has ``obj_pos`` and ``memory_pos_samples``.
        validation_tolerance: Maximum allowed RMSE for a valid transform.

    Returns:
        Transform dict ready to be saved with ``save_transform``.

    Raises:
        ValueError: if there are insufficient samples or the fit fails.
    """
    if validation_tolerance <= 0 or math.isnan(validation_tolerance):
        raise ValueError("validation_tolerance must be a positive number")

    landmarks = samples.get("landmarks", [])
    if len(landmarks) < 3:
        raise ValueError("Need at least 3 landmarks to compute a transform with meaningful RMSE/tolerance validation")

    obj_points: list[tuple[float, float, float]] = []
    mem_points: list[tuple[float, float, float]] = []

    for landmark in landmarks:
        obj_pos = landmark.get("obj_pos")
        mem_samples = landmark.get("memory_pos_samples", [])
        if not obj_pos or not mem_samples:
            raise ValueError("Each landmark must have obj_pos and memory_pos_samples")

        if len(obj_pos) != 3 or not all(isinstance(v, (int, float)) for v in obj_pos):
            raise ValueError(f"Landmark {landmark.get('id', '?')} obj_pos must be a 3-element numeric sequence")

        for sample in mem_samples:
            if len(sample) != 3 or not all(isinstance(v, (int, float)) for v in sample):
                raise ValueError(f"Landmark {landmark.get('id', '?')} has malformed memory_pos_samples entry: {sample}")

        # Average memory samples for this landmark
        avg_mem = _average_samples(mem_samples)
        obj_points.append(_to_tuple(obj_pos))
        mem_points.append(avg_mem)

    # Determine axis mapping by correlation sign
    axis_mapping = _estimate_axis_mapping(obj_points, mem_points)

    # Solve scale and offset per-axis
    scale: list[float] = [1.0, 1.0, 1.0]
    offset: list[float] = [0.0, 0.0, 0.0]
    rmse: list[float] = [0.0, 0.0, 0.0]

    for axis in range(3):
        obj_vals = [p[axis] for p in obj_points]
        mem_vals = [mem_points[i][axis] for i in range(len(mem_points))]

        # Apply axis mapping to memory values for regression
        mapped_mem_vals = [axis_mapping[axis] * v for v in mem_vals]

        try:
            s, o = _linear_regression(obj_vals, mapped_mem_vals)
        except ValueError as exc:
            raise ValueError(
                f"Axis {axis} has no variance in obj_pos across landmarks; need landmarks that differ along this axis"
            ) from exc
        scale[axis] = s
        offset[axis] = axis_mapping[axis] * o

        # Compute RMSE for this axis.  Because the regression was run on
        # mapped memory values, the forward prediction must re-apply the
        # axis_mapping: memory = axis_mapping * (scale * obj + o).
        predicted = [axis_mapping[axis] * (s * obj_vals[i] + o) for i in range(len(obj_vals))]
        rmse[axis] = _rmse(mem_vals, predicted)

    transform: dict[str, Any] = {
        "scale": scale,
        "offset": offset,
        "axis_mapping": axis_mapping,
        "confidence_rmse": rmse,
        "validation_tolerance": validation_tolerance,
    }

    # Validate the transform against the samples
    max_rmse = max(rmse)
    if max_rmse > validation_tolerance:
        raise ValueError(
            f"Transform RMSE ({max_rmse:.4f}) exceeds tolerance "
            f"({validation_tolerance:.4f}). Check calibration samples."
        )

    return transform


def _average_samples(samples: list[list[float]]) -> tuple[float, float, float]:
    """Average a list of (x, y, z) samples."""
    if not samples:
        raise ValueError("Cannot average empty sample list")
    n = len(samples)
    return (
        sum(s[0] for s in samples) / n,
        sum(s[1] for s in samples) / n,
        sum(s[2] for s in samples) / n,
    )


def _estimate_axis_mapping(
    obj_points: list[tuple[float, float, float]],
    mem_points: list[tuple[float, float, float]],
) -> list[int]:
    """Estimate axis mapping (+1 or -1) by correlation sign."""
    mapping: list[int] = [1, 1, 1]
    for axis in range(3):
        obj_vals = [p[axis] for p in obj_points]
        mem_vals = [p[axis] for p in mem_points]
        covariance = sum(
            (obj_vals[i] - sum(obj_vals) / len(obj_vals)) * (mem_vals[i] - sum(mem_vals) / len(mem_vals))
            for i in range(len(obj_vals))
        )
        if covariance < 0:
            mapping[axis] = -1
    return mapping


def _linear_regression(
    xs: list[float],
    ys: list[float],
) -> tuple[float, float]:
    """Return (slope, intercept) for y = slope * x + intercept."""
    n = len(xs)
    if n < 2:
        raise ValueError("Need at least 2 points for linear regression")

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    numerator = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    denominator = sum((xs[i] - mean_x) ** 2 for i in range(n))

    if denominator == 0:
        raise ValueError("All x values are identical; cannot compute slope")

    slope = numerator / denominator
    intercept = mean_y - slope * mean_x
    return slope, intercept


def _rmse(actual: list[float], predicted: list[float]) -> float:
    """Compute root-mean-square error between two equal-length sequences."""
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same length")
    if not actual:
        return 0.0
    return math.sqrt(sum((actual[i] - predicted[i]) ** 2 for i in range(len(actual))) / len(actual))


# ============================================================================
# CLI
# ============================================================================


def _parse_coords(s: str) -> tuple[float, float, float]:
    """Parse a comma-separated coordinate string into a 3-tuple."""
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Expected comma-separated coordinates, got: {s}")
    return (float(parts[0]), float(parts[1]), float(parts[2]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="OBJ↔live-memory coordinate transform utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
        "  python scripts/navmesh_coord_transform.py --transform coord-transform.json --obj-to-mem 1.0,2.0,3.0\n"
        "  python scripts/navmesh_coord_transform.py --transform coord-transform.json --mem-to-obj 10.0,20.0,30.0\n",
    )
    parser.add_argument(
        "--transform",
        default=str(DEFAULT_TRANSFORM_PATH),
        help=f"Path to coord-transform.json (default: {DEFAULT_TRANSFORM_PATH})",
    )
    parser.add_argument("--obj-to-mem", metavar="X,Y,Z", help="Convert OBJ coordinates to memory coordinates")
    parser.add_argument("--mem-to-obj", metavar="X,Y,Z", help="Convert memory coordinates to OBJ coordinates")
    args = parser.parse_args(argv)

    transform = load_transform(args.transform)

    if args.obj_to_mem:
        x, y, z = _parse_coords(args.obj_to_mem)
        px, py, pz = obj_to_memory(x, y, z, transform)
        print(f"{px:.4f},{py:.4f},{pz:.4f}")
        return 0

    if args.mem_to_obj:
        px, py, pz = _parse_coords(args.mem_to_obj)
        x, y, z = memory_to_obj(px, py, pz, transform)
        print(f"{x:.4f},{y:.4f},{z:.4f}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
