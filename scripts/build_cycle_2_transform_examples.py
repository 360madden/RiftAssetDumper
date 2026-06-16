#!/usr/bin/env python3
"""Build C2-2.1 transform examples from the current Cycle 2 cohort.

Reads:
  - `Assets/Exports/discovery-plan/cycle-2/stage1/cohort.json`
  - `Assets/build/flythrough/objs/worlds/*.world.json`

Writes:
  - `Assets/Exports/discovery-plan/cycle-2/stage2/transform-examples.json`

This is intentionally a small evidence refresher for C2-2.4. It reuses the
same transform accumulator as `build_world_placed_merge.py` so transform truth
does not drift between exporter code, cohort evidence, and schema docs.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from build_world_placed_merge import IDENTITY_ROTATION, _compute_world_transform  # noqa: E402

DEFAULT_COHORT = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage1" / "cohort.json"
DEFAULT_WORLDS = REPO_ROOT / "Assets" / "build" / "flythrough" / "objs" / "worlds"
DEFAULT_OUT = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage2" / "transform-examples.json"
TOLERANCE = 1e-6


def _now_date() -> str:
    return datetime.now(UTC).date().isoformat()


def _asset_base_id(asset_id: str) -> str:
    """Normalize cohort IDs; non-identity rows currently carry a `.world` suffix."""
    return asset_id[:-6] if asset_id.endswith(".world") else asset_id


def _is_identity(translation: list[float], rotation: list[float], scale: float) -> bool:
    return (
        all(abs(v) < TOLERANCE for v in translation)
        and all(abs(a - b) < TOLERANCE for a, b in zip(rotation, IDENTITY_ROTATION, strict=True))
        and abs(scale - 1.0) < TOLERANCE
    )


def _all_finite(values: list[float]) -> bool:
    return all(math.isfinite(v) for v in values)


def _round_vector(values: list[float]) -> list[float]:
    return [round(float(v), 6) for v in values]


def _translation_magnitude(values: list[float]) -> float:
    return math.sqrt(sum(v * v for v in values))


def _entry_for(cohort_entry: dict[str, Any], worlds_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    raw_asset_id = str(cohort_entry["asset_id"])
    asset_id = _asset_base_id(raw_asset_id)
    world_path = worlds_dir / f"{asset_id}.world.json"
    if not world_path.exists():
        return None, str(world_path)

    world = json.loads(world_path.read_text(encoding="utf-8-sig"))
    translation, rotation, scale = _compute_world_transform(world)
    finite = _all_finite(translation + rotation + [scale])
    identity = _is_identity(translation, rotation, scale)
    rotation_max_delta = max(abs(a - b) for a, b in zip(rotation, IDENTITY_ROTATION, strict=True))

    return (
        {
            "asset_id": asset_id,
            "raw_cohort_asset_id": raw_asset_id,
            "family": cohort_entry.get("family"),
            "mesh_size": cohort_entry.get("mesh_size"),
            "node_count": world.get("NodeCount", cohort_entry.get("node_count")),
            "mesh_count": world.get("MeshCount", cohort_entry.get("mesh_count")),
            "world_json": world_path.name,
            "world_translation": _round_vector(translation),
            "world_scale": round(float(scale), 6),
            "rotation_max_delta": round(float(rotation_max_delta), 6),
            "is_identity_transform": identity,
            "all_fields_finite": finite,
        },
        None,
    )


def _full_scale_check(worlds_dir: Path) -> dict[str, Any]:
    scales: list[float] = []
    for path in sorted(worlds_dir.glob("*.world.json")):
        world = json.loads(path.read_text(encoding="utf-8-sig"))
        _, _, scale = _compute_world_transform(world)
        scales.append(float(scale))
    return {
        "count": len(scales),
        "min": min(scales) if scales else None,
        "max": max(scales) if scales else None,
        "all_unity_within_tolerance": all(abs(scale - 1.0) < TOLERANCE for scale in scales),
        "note": "All flythrough world.json scale values are checked with the production accumulator.",
    }


def build_transform_examples(cohort_path: Path, worlds_dir: Path) -> dict[str, Any]:
    if not cohort_path.exists():
        raise FileNotFoundError(f"cohort not found: {cohort_path}")
    if not worlds_dir.exists():
        raise FileNotFoundError(f"worlds dir not found: {worlds_dir}")

    cohort_data = json.loads(cohort_path.read_text(encoding="utf-8-sig"))
    cohort = cohort_data.get("cohort", [])

    available: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    for entry in cohort:
        example, missing_path = _entry_for(entry, worlds_dir)
        if example is None:
            missing.append({"asset_id": str(entry.get("asset_id")), "expected_world_json": str(missing_path)})
        else:
            available.append(example)

    non_identity = [entry for entry in available if not entry["is_identity_transform"]]
    identity = [entry for entry in available if entry["is_identity_transform"]]
    max_translation = max((_translation_magnitude(entry["world_translation"]) for entry in available), default=0.0)
    family_counts = dict(Counter(str(entry.get("family")) for entry in available))

    return {
        "plan": "cycle-2",
        "step": "C2-2.1",
        "generated_at": _now_date(),
        "cohort_source": str(cohort_path),
        "worlds_source": str(worlds_dir),
        "cohort_size": len(cohort),
        "available_count": len(available),
        "missing_count": len(missing),
        "finite_count": sum(1 for entry in available if entry["all_fields_finite"]),
        "identity_count": len(identity),
        "non_identity_count": len(non_identity),
        "method": "scale -> rotate -> translate accumulator (matches build_world_placed_merge.py)",
        "tolerance": TOLERANCE,
        "family_counts": family_counts,
        "data_source": (
            "Direct walk of the current v0.3 cohort world.json files with the same "
            "Scale -> Rotate -> Translate accumulator used by scripts/build_world_placed_merge.py."
        ),
        "full_217_scale_check": _full_scale_check(worlds_dir),
        "non_identity_examples": non_identity,
        "identity_examples": identity,
        "missing_examples": missing,
        "summary": {
            "non_identity_translation_assets": sum(
                1 for entry in non_identity if any(abs(v) >= TOLERANCE for v in entry["world_translation"])
            ),
            "non_identity_rotation_only_assets": sum(
                1
                for entry in non_identity
                if all(abs(v) < TOLERANCE for v in entry["world_translation"])
                and entry["rotation_max_delta"] >= TOLERANCE
            ),
            "total_non_identity_assets": len(non_identity),
            "identity_assets": len(identity),
            "max_translation_magnitude": round(max_translation, 6),
            "all_scales_unity": all(abs(entry["world_scale"] - 1.0) < TOLERANCE for entry in available),
            "all_fields_finite": all(entry["all_fields_finite"] for entry in available),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="build_cycle_2_transform_examples",
        description="Refresh C2-2.1 transform examples from the current Cycle 2 cohort.",
    )
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT, help="cohort.json path")
    parser.add_argument("--worlds", type=Path, default=DEFAULT_WORLDS, help="worlds/ directory")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="transform-examples.json output path")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON to stdout instead of writing")
    args = parser.parse_args()

    output = build_transform_examples(args.cohort, args.worlds)
    text = json.dumps(output, indent=2) + "\n"
    if args.dry_run:
        print(text, end="")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
