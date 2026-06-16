#!/usr/bin/env python3
"""Build a scene-manifest/v1-draft entry for one cohort asset.

Reads:
  - Assets/build/flythrough/objs/worlds/<asset_id>.world.json
  - Assets/build/flythrough/flythrough-index.json
  - Assets/Exports/discovery-plan/cycle-2/stage1/cohort.json
  - Assets/Exports/discovery-plan/cycle-2/stage2/coordinate-contract.md
  - Assets/Exports/discovery-plan/cycle-2/stage2/scene-manifest-v1.draft.schema.json

Emits a scene-manifest/v1-draft JSON record following the draft schema in
`Assets/Exports/discovery-plan/cycle-2/stage2/scene-manifest-v1.draft.schema.json`.

The builder is intentionally conservative: known-unknown fields (vertex_count,
face_count, render_class, material_status, linked_textures, mesh_block) are
populated as 0/false/"unknown"/[]/null with warnings, never guessed. This keeps
the manifest honest about what is and is not yet extracted.

Usage:
    python scripts/build_scene_manifest.py --asset-id 07f37c99a80da009
    python scripts/build_scene_manifest.py --asset-id 07f37c99a80da009 --out path.json
    python scripts/build_scene_manifest.py --all-non-id   # build all 4 non-id samples

Exit codes:
    0 = manifest written (may still be not consumer_ready; see validation.warnings)
    1 = input error (missing world.json, asset_id not in cohort, etc.)
    2 = schema validation failed
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
WORLD_DIR = REPO_ROOT / "Assets" / "build" / "flythrough" / "objs" / "worlds"
OBJ_DIR = REPO_ROOT / "Assets" / "build" / "flythrough" / "objs"
FLYTHROUGH_INDEX = REPO_ROOT / "Assets" / "build" / "flythrough" / "flythrough-index.json"
COHORT_JSON = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage1" / "cohort.json"
TRANSFORM_EXAMPLES = (
    REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage2" / "transform-examples.json"
)
COORDINATE_CONTRACT = (
    REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage2" / "coordinate-contract.md"
)
SCHEMA_PATH = (
    REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage2" / "scene-manifest-v1.draft.schema.json"
)
DEFAULT_OUT_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage2"
PRODUCER_TOOL = "scripts/build_scene_manifest.py"
PRODUCER_VERSION = "v0.4"

# Schema-defined constants (mirrors coordinate-contract.md)
COORDINATE_SYSTEM: dict[str, Any] = {
    "handedness": "right",
    "up_axis": "Y",
    "forward_axis": "-Z",
    "translation_layout": "xyz",
    "rotation_layout": "row-major-3x3",
    "scale_layout": "uniform-float",
    "trs_composition": "v_world = R * (S * v_local) + T",
    "identity_tolerance": 1e-6,
}


def is_identity_transform(t: list[float] | None, r: list[float] | None, s: float | None) -> bool:
    """Return True if the transform is identity within the 1e-6 tolerance."""
    if t is None or r is None or s is None:
        return False
    if abs(s - 1.0) > COORDINATE_SYSTEM["identity_tolerance"]:
        return False
    if any(abs(x) > COORDINATE_SYSTEM["identity_tolerance"] for x in t):
        return False
    # Identity rotation: 3x3 row-major = [1,0,0, 0,1,0, 0,0,1]
    if len(r) < 9:
        return False
    expected = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    return all(abs(r[i] - expected[i]) <= COORDINATE_SYSTEM["identity_tolerance"] for i in range(9))


def load_world(asset_id: str) -> dict[str, Any]:
    """Load world.json for one asset. Raise FileNotFoundError if missing."""
    path = WORLD_DIR / f"{asset_id}.world.json"
    if not path.exists():
        raise FileNotFoundError(f"world.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_flythrough_entry(asset_id: str) -> dict[str, Any] | None:
    """Find the flythrough-index entry for one asset_id (skip non-dict entries)."""
    idx = json.loads(FLYTHROUGH_INDEX.read_text(encoding="utf-8-sig"))
    for a in idx.get("assets", []):
        if not isinstance(a, dict):
            continue
        if str(a.get("asset_id", "")).startswith(asset_id):
            return a
    return None


def load_cohort() -> list[dict[str, Any]]:
    """Load the cohort.json entry list."""
    c = json.loads(COHORT_JSON.read_text(encoding="utf-8-sig"))
    return c.get("cohort", [])


def find_non_identity_node(world: dict[str, Any]) -> dict[str, Any] | None:
    """Find the parent node of the first attached mesh (the non-id candidate).

    NOTE: Only inspects meshes[0]. Sufficient for the non-id cohort (single
    attached mesh per asset). For multi-mesh NIFs, this would need to either
    return a list of (mesh_idx, parent_node) pairs or compose transforms
    across all parent chains -- deferred until a multi-mesh cohort asset
    needs a scene manifest.
    """
    meshes = world.get("Meshes", [])
    if not meshes:
        return None
    parent_idx = meshes[0].get("ParentNiNodeIndex", -1)
    if parent_idx < 0:
        return None
    for n in world.get("Nodes", []):
        if n.get("BlockIndex") == parent_idx:
            return n
    return None


def build_geometry(asset_id: str, cohort_entry: dict[str, Any] | None) -> dict[str, Any]:
    """Build the geometry sub-record. Conservative: known-unknowns are 0/null."""
    obj_path = str(OBJ_DIR / f"{asset_id}.obj")
    mesh_size = cohort_entry.get("mesh_size") if cohort_entry else None
    has_faces = bool(cohort_entry.get("has_faces")) if cohort_entry else False
    # vertex_count / face_count require OBJ parse -- not yet wired
    # render_class requires position/faced classification -- not yet wired
    return {
        "obj_path": obj_path,
        "mesh_block": None,
        "mesh_size": mesh_size,
        "vertex_count": 0,
        "face_count": 0,
        "has_faces": has_faces,
        "render_class": "unknown",
    }


def build_world(asset_id: str, world: dict[str, Any]) -> dict[str, Any]:
    """Build the world sub-record from the loaded world.json."""
    parent_node = find_non_identity_node(world)
    if parent_node is not None:
        t = parent_node.get("Translation", [0.0, 0.0, 0.0])
        r = parent_node.get("Rotation")
        s = parent_node.get("Scale", 1.0)
        # r may be None for nodes with no rotation; treat as identity-rotation
        if r is None:
            r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        identity = is_identity_transform(t, r, s)
    else:
        t = [0.0, 0.0, 0.0]
        r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        s = 1.0
        identity = True
    return {
        "world_json": str(WORLD_DIR / f"{asset_id}.world.json"),
        "node_count": world.get("NodeCount", 0),
        "mesh_count": world.get("MeshCount", 0),
        "transform_semantics": "mesh-parent-chain",
        "coordinate_system": COORDINATE_SYSTEM,
        "world_transform_summary": {
            "translation": t,
            "rotation": r,
            "scale": s,
        },
        "world_transform_identity": identity,
    }


def build_materials(cohort_entry: dict[str, Any] | None) -> dict[str, Any]:
    """Build the materials sub-record. Conservative: status=unknown until NIF scan."""
    return {
        "material_status": "unknown",
        "texture_property_count": 0,
        "material_property_count": 0,
        "vertex_color_property_count": 0,
        "notes": [
            "material data not yet extracted from NIF - status=unknown"
            + (f" (cohort has_faces={cohort_entry.get('has_faces')})" if cohort_entry else "")
        ],
    }


def build_textures(flythrough_entry: dict[str, Any] | None) -> dict[str, Any]:
    """Build the textures sub-record. Populates from flythrough-index if available."""
    if flythrough_entry and isinstance(flythrough_entry.get("linked_textures"), list):
        linked = [str(t) for t in flythrough_entry["linked_textures"]]
        return {
            "linked_texture_count": len(linked),
            "linked_textures": linked,
            "missing_texture_count": 0,
            "placeholder_texture_count": 0,
        }
    return {
        "linked_texture_count": 0,
        "linked_textures": [],
        "missing_texture_count": 0,
        "placeholder_texture_count": 0,
    }


def build_provenance(
    asset_id: str,
    cohort_entry: dict[str, Any] | None,
    flythrough_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the provenance sub-record."""
    return {
        "cohort": str(COHORT_JSON) if COHORT_JSON.exists() else None,
        "source_nif_hash": asset_id,
        "flythrough_index_entry": str(FLYTHROUGH_INDEX) if flythrough_entry else None,
        "evidence_files": [
            str(WORLD_DIR / f"{asset_id}.world.json"),
            str(TRANSFORM_EXAMPLES),
            str(COORDINATE_CONTRACT),
        ],
    }


def build_validation(geometry: dict[str, Any], materials: dict[str, Any], textures: dict[str, Any]) -> dict[str, Any]:
    """Build the validation sub-record, computing warnings and consumer_ready flag."""
    warnings: list[str] = []
    if geometry["vertex_count"] == 0 and geometry["face_count"] == 0:
        warnings.append("vertex_count=0 and face_count=0 - geometry not yet extracted from OBJ")
    if geometry["render_class"] == "unknown":
        warnings.append("render_class=unknown - OBJ classify pass not yet run")
    if geometry["mesh_block"] is None:
        warnings.append("mesh_block=null - world.json BlockIndex not yet mapped to the locked M#N convention")
    if materials["material_status"] == "unknown":
        warnings.append("material_status=unknown - NIF material properties not yet scanned")
    if textures["linked_texture_count"] == 0:
        warnings.append("linked_textures=[] - texture linkage not yet populated")
    # consumer_ready requires: faces present, materials known, textures known, mesh_block known
    consumer_ready = (
        geometry["vertex_count"] > 0
        and geometry["face_count"] > 0
        and materials["material_status"] != "unknown"
        and textures["linked_texture_count"] > 0
        and geometry["mesh_block"] is not None
    )
    return {
        "schema_valid": True,  # set False below if validator fails
        "consumer_ready": consumer_ready,
        "warnings": warnings,
        "errors": [],
    }


def build_manifest(asset_id: str) -> dict[str, Any]:
    """Build a complete scene-manifest/v1-draft entry for one asset_id."""
    world = load_world(asset_id)
    cohort_list = load_cohort()
    cohort_entry = next(
        (e for e in cohort_list if str(e.get("asset_id", "")).startswith(asset_id)),
        None,
    )
    flythrough_entry = load_flythrough_entry(asset_id)
    geometry = build_geometry(asset_id, cohort_entry)
    world_rec = build_world(asset_id, world)
    materials = build_materials(cohort_entry)
    textures = build_textures(flythrough_entry)
    provenance = build_provenance(asset_id, cohort_entry, flythrough_entry)
    validation = build_validation(geometry, materials, textures)
    return {
        "SchemaVersion": "scene-manifest/v1-draft",
        "asset_id": asset_id,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "producer": {
            "tool": PRODUCER_TOOL,
            "version": PRODUCER_VERSION,
            "command": (f"python {PRODUCER_TOOL} --asset-id {asset_id}"),
        },
        "geometry": geometry,
        "world": world_rec,
        "materials": materials,
        "textures": textures,
        "provenance": provenance,
        "validation": validation,
    }


def validate_against_schema(manifest: dict[str, Any]) -> list[str]:
    """Validate manifest against the draft schema. Returns list of error strings (empty = valid)."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError as e:
        return [f"jsonschema not installed: {e}"]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))
    validator = Draft202012Validator(schema)
    return [f"{'/'.join(str(p) for p in err.absolute_path)}: {err.message}" for err in validator.iter_errors(manifest)]


def find_non_id_asset_ids() -> list[str]:
    """Return the 4 non-id asset IDs from transform-examples.json."""
    t = json.loads(TRANSFORM_EXAMPLES.read_text(encoding="utf-8-sig"))
    return [e.get("asset_id", e.get("id", "")) for e in t.get("non_identity_examples", [])]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build scene-manifest/v1-draft entry for one asset")
    parser.add_argument("--asset-id", help="Asset ID (16-char hex). Mutually exclusive with --all-non-id.")
    parser.add_argument("--all-non-id", action="store_true", help="Build all 4 non-id samples")
    parser.add_argument("--out", help="Output path (default: <default-out-dir>/sample-manifest-<id>.json)")
    parser.add_argument("--validate-only", action="store_true", help="Validate against schema but skip write")
    args = parser.parse_args()

    if args.all_non_id:
        asset_ids = find_non_id_asset_ids()
        if not asset_ids:
            print("ERROR: no non-id assets found in transform-examples.json", file=sys.stderr)
            return 1
    elif args.asset_id:
        asset_ids = [args.asset_id]
    else:
        parser.error("either --asset-id or --all-non-id is required")

    overall_ok = True
    for asset_id in asset_ids:
        try:
            manifest = build_manifest(asset_id)
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            overall_ok = False
            continue
        errors = validate_against_schema(manifest)
        if errors:
            manifest["validation"]["schema_valid"] = False
            manifest["validation"]["errors"] = errors
            overall_ok = False
            print(f"INVALID: {asset_id} - {len(errors)} schema error(s):", file=sys.stderr)
            for err in errors:
                print(f"  {err}", file=sys.stderr)
        if args.validate_only:
            status = "VALID" if not errors else f"INVALID ({len(errors)} errors)"
            print(f"{asset_id}: {status}, consumer_ready={manifest['validation']['consumer_ready']}")
            continue
        out_path = Path(args.out) if args.out else DEFAULT_OUT_DIR / f"sample-manifest-{asset_id}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        status = "VALID" if not errors else f"INVALID ({len(errors)} errors)"
        print(f"wrote {out_path} - {status}, consumer_ready={manifest['validation']['consumer_ready']}")
    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
