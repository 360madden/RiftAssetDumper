"""navmesh_calibration_capture.py — Capture landmarks and compute the OBJ↔memory transform.

This script is the NM-2 (Coordinate System Alignment) entry point.  It reads
or creates calibration landmark samples, computes the affine transform, and
writes ``coord-transform.json``.

When the game is running, use ``--live`` to read the current player position
from RiftReader and append it to a landmark's memory samples.  When the game is
not running, ``--stub`` generates deterministic synthetic samples for testing.

Examples:
    # Generate a stub calibration dataset and compute transform
    python scripts/navmesh_calibration_capture.py --stub --out Exports/navmesh-phase2/coord-transform.json

    # Add a live sample to an existing calibration file
    python scripts/navmesh_calibration_capture.py --live --landmark ep1_statue_base --samples Exports/navmesh-phase2/calibration-samples.json

    # Compute transform from existing samples
    python scripts/navmesh_calibration_capture.py --samples Exports/navmesh-phase2/calibration-samples.json --compute
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.navmesh_coord_transform import (
    DEFAULT_TRANSFORM_PATH,
    compute_transform,
    save_transform,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLES_PATH = REPO_ROOT / "Exports" / "navmesh-phase2" / "calibration-samples.json"


def _load_or_create_samples(path: Path) -> dict[str, Any]:
    """Load existing calibration samples or return an empty container."""
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if "landmarks" not in data:
            data["landmarks"] = []
        return data
    return {"landmarks": []}


def _save_samples(samples: dict[str, Any], path: Path) -> None:
    """Persist calibration samples to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(samples, indent=2), encoding="utf-8")


def _find_landmark(samples: dict[str, Any], landmark_id: str) -> dict[str, Any] | None:
    """Return an existing landmark by id or None."""
    for landmark in samples.get("landmarks", []):
        if landmark.get("id") == landmark_id:
            return landmark
    return None


def _generate_stub_samples() -> dict[str, Any]:
    """Generate deterministic stub calibration samples for offline testing.

    The stub uses a known transform (scale=10, offset=[0, 5, 0], no axis flip)
    so tests can verify round-trip correctness without live memory.
    """
    landmarks = [
        {
            "id": "ep1_origin",
            "obj_pos": [0.0, 0.0, 0.0],
            "memory_pos_samples": [[0.0, 5.0, 0.0]],
        },
        {
            "id": "ep1_east_10",
            "obj_pos": [10.0, 0.0, 0.0],
            "memory_pos_samples": [[100.0, 5.0, 0.0]],
        },
        {
            "id": "ep1_north_5",
            "obj_pos": [0.0, 0.0, 5.0],
            "memory_pos_samples": [[0.0, 5.0, 50.0]],
        },
        {
            "id": "ep1_up_2",
            "obj_pos": [0.0, 2.0, 0.0],
            "memory_pos_samples": [[0.0, 25.0, 0.0]],
        },
    ]
    return {"landmarks": landmarks}


# Known offsets from binary signature analysis.  These are stable for the
# current game client but should be refreshed from the signature database if
# the client ever changes.
LOCAL_PLAYER_OFFSET = 0x32EBC80
PLAYER_FIELD_OFFSETS = {
    "pos_x": 0x320,
    "pos_y": 0x324,
    "pos_z": 0x328,
}


def _read_live_position() -> tuple[float, float, float]:
    """Read the current player position from live memory.

    Raises:
        RuntimeError: if the game process is not available.
    """
    try:
        from scripts.rift_memory_scanner import RIFTMemoryScanner
    except ImportError as exc:
        raise RuntimeError("RIFTMemoryScanner not available; ensure the game client tools are installed") from exc

    with RIFTMemoryScanner() as scanner:
        if not scanner.find_process("rift_x64.exe"):
            raise RuntimeError("Failed to find RIFT process; is the game running?")

        if not scanner.open_process():
            raise RuntimeError("Failed to open RIFT process; try running as Administrator")

        if not scanner.find_module():
            raise RuntimeError("Failed to locate RIFT module base")

        addr = scanner.module_base + LOCAL_PLAYER_OFFSET
        ptr = scanner.read_pointer(addr)
        if ptr is None:
            raise RuntimeError("Failed to read LocalPlayer pointer")

        values: list[float] = []
        for name, offset in PLAYER_FIELD_OFFSETS.items():
            value = scanner.read_float(ptr + offset)
            if value is None:
                raise RuntimeError(f"Failed to read player {name} from live memory")
            values.append(value)

        return (values[0], values[1], values[2])


def add_landmark(
    samples: dict[str, Any],
    landmark_id: str,
    obj_pos: tuple[float, float, float],
    mem_pos: tuple[float, float, float],
) -> dict[str, Any]:
    """Add or update a landmark in the calibration samples.

    Args:
        samples: Calibration samples dict.
        landmark_id: Unique identifier for the landmark.
        obj_pos: OBJ/world coordinates.
        mem_pos: Live memory coordinates.

    Returns:
        The updated samples dict.
    """
    landmark = _find_landmark(samples, landmark_id)
    if landmark is None:
        landmark = {"id": landmark_id, "obj_pos": list(obj_pos), "memory_pos_samples": []}
        samples["landmarks"].append(landmark)

    landmark["obj_pos"] = list(obj_pos)
    landmark["memory_pos_samples"].append(list(mem_pos))
    return samples


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture navmesh calibration landmarks and compute the OBJ↔memory transform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
        "  python scripts/navmesh_calibration_capture.py --stub --out Exports/navmesh-phase2/coord-transform.json\n"
        "  python scripts/navmesh_calibration_capture.py --live --landmark ep1_statue_base --samples calibration-samples.json\n"
        "  python scripts/navmesh_calibration_capture.py --samples calibration-samples.json --compute\n",
    )
    parser.add_argument("--samples", default=str(DEFAULT_SAMPLES_PATH), help="Path to calibration-samples.json")
    parser.add_argument("--out", default=str(DEFAULT_TRANSFORM_PATH), help="Output path for coord-transform.json")
    parser.add_argument("--landmark", help="Landmark id (required with --live)")
    parser.add_argument("--obj-pos", help="OBJ position as x,y,z (required with --live)")
    parser.add_argument(
        "--stub",
        action="store_true",
        help="Generate deterministic stub samples and compute transform",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Read current player position from live memory and append to a landmark",
    )
    parser.add_argument(
        "--compute",
        action="store_true",
        help="Compute and save transform from existing samples",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.5,
        help="Maximum allowed RMSE for a valid transform (default: 0.5)",
    )
    args = parser.parse_args(argv)

    samples_path = Path(args.samples)

    if args.stub:
        samples = _generate_stub_samples()
        _save_samples(samples, samples_path)
        transform = compute_transform(samples, validation_tolerance=args.tolerance)
        save_transform(transform, args.out)
        print(f"Stub calibration saved to {samples_path}")
        print(f"Transform saved to {args.out}")
        print(f"  scale={transform['scale']}")
        print(f"  offset={transform['offset']}")
        print(f"  axis_mapping={transform['axis_mapping']}")
        print(f"  confidence_rmse={transform['confidence_rmse']}")
        return 0

    if args.live:
        if not args.landmark or not args.obj_pos:
            parser.error("--live requires --landmark and --obj-pos")
        parts = [v.strip() for v in args.obj_pos.split(",")]
        if len(parts) != 3:
            parser.error("--obj-pos must be three comma-separated numbers like 1.0,2.0,3.0")
        try:
            obj_pos = tuple(float(v) for v in parts)
        except ValueError:
            parser.error("--obj-pos must contain numeric values")

        mem_pos = _read_live_position()
        samples = _load_or_create_samples(samples_path)
        add_landmark(samples, args.landmark, obj_pos, mem_pos)
        _save_samples(samples, samples_path)
        print(f"Added live sample for '{args.landmark}': obj={obj_pos} mem={mem_pos}")
        return 0

    if args.compute:
        samples = _load_or_create_samples(samples_path)
        if not samples.get("landmarks"):
            print(f"No landmarks found in {samples_path}", file=sys.stderr)
            return 1
        transform = compute_transform(samples, validation_tolerance=args.tolerance)
        save_transform(transform, args.out)
        print(f"Transform saved to {args.out}")
        print(f"  scale={transform['scale']}")
        print(f"  offset={transform['offset']}")
        print(f"  axis_mapping={transform['axis_mapping']}")
        print(f"  confidence_rmse={transform['confidence_rmse']}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
