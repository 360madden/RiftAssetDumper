#!/usr/bin/env python3
"""Build a scene-manifest/v1-draft entry for one cohort asset.

Reads:
  - Assets/build/flythrough/objs/worlds/<asset_id>.world.json
  - Assets/build/flythrough/flythrough-index.json
  - Assets/Exports/discovery-plan/cycle-2/stage1/cohort.json
  - Assets/Exports/discovery-plan/cycle-2/stage2/coordinate-contract.md
  - Assets/Exports/discovery-plan/cycle-2/stage2/scene-manifest-v1.draft.schema.json

Emits a scene-manifest/v1 JSON record following the locked schema in
`Assets/Exports/discovery-plan/cycle-2/stage2/scene-manifest-v1.schema.json`.

v0.6 populates geometry fields (vertex_count, face_count, mesh_block,
mesh_size, render_class, obj_sha1) from the flythrough-index entry.
Materials remain unknown until a NIF-level material scan is wired.

Usage:
    python scripts/build_scene_manifest.py --asset-id 07f37c99a80da009
    python scripts/build_scene_manifest.py --asset-id 07f37c99a80da009 --out path.json
    python scripts/build_scene_manifest.py --all-non-id   # build all 4 non-id samples
    python scripts/build_scene_manifest.py --all-flythrough  # scale-out: build all 217 flythrough assets

Exit codes:
    0 = manifest written (may still be not consumer_ready; see validation.warnings)
    1 = input error (missing world.json, asset_id not in cohort, etc.)
    2 = schema validation failed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
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
SCHEMA_PATH = REPO_ROOT / "docs" / "schemas" / "scene-manifest-v1.schema.json"
DEFAULT_OUT_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage2"
SCALE_OUT_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage6"
MATERIAL_SCAN_RESULTS = (
    REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage3" / "material-scan-results.json"
)
PRODUCER_TOOL = "scripts/build_scene_manifest.py"
PRODUCER_VERSION = "v0.8"

_material_scan_cache: dict[str, dict[str, Any]] | None = None
_material_scan_scanned_at: str | None = None
_material_scan_loaded: bool = False

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


def load_world(asset_id: str, flythrough_entry: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load world.json for one asset. Uses flythrough-index world_json path when available.

    The flythrough-index ``world_json`` field may be a bare filename (e.g.
    ``0603cce7cee15eb8.world.json``) or an absolute path. Bare filenames are
    resolved relative to WORLD_DIR.
    """
    if flythrough_entry and isinstance(flythrough_entry.get("world_json"), str):
        wj = flythrough_entry["world_json"]
        if Path(wj).is_absolute():
            path = Path(wj)
        else:
            path = WORLD_DIR / wj
    else:
        path = WORLD_DIR / f"{asset_id}.world.json"
    if not path.exists():
        raise FileNotFoundError(f"world.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_flythrough_entry(asset_id: str) -> dict[str, Any] | None:
    """Find the flythrough-index entry for one asset_id.

    flythrough-index.json ``assets`` is a dict keyed by 16-char hex asset_id
    (the same value used as the cohort asset key). Each value carries
    ``linked_textures``, ``vertex_count``, ``face_count``, etc.

    Returns None if the index is missing, unreadable, or doesn't contain
    the requested asset_id.
    """
    try:
        idx = json.loads(FLYTHROUGH_INDEX.read_text(encoding="utf-8-sig"))
    except FileNotFoundError, json.JSONDecodeError, OSError:
        return None
    assets = idx.get("assets", {})
    if not isinstance(assets, dict):
        return None
    return assets.get(asset_id)


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


def build_geometry(
    asset_id: str,
    cohort_entry: dict[str, Any] | None,
    flythrough_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the geometry sub-record from flythrough-index (source of truth).

    Populates vertex_count, face_count, has_faces, mesh_block, mesh_size,
    and render_class from the flythrough-index entry. Falls back to cohort
    data or conservative defaults when the flythrough entry is missing.
    Computes obj_sha1 (SHA-256) from the OBJ file when it exists.
    """
    # --- obj_path ---
    if flythrough_entry and isinstance(flythrough_entry.get("obj_path"), str):
        obj_path = flythrough_entry["obj_path"]
    else:
        obj_path = str(OBJ_DIR / f"{asset_id}.obj")

    # --- vertex_count / face_count / has_faces ---
    if flythrough_entry:
        vertex_count = flythrough_entry.get("vertex_count", 0)
        face_count = flythrough_entry.get("face_count", 0)
        has_faces = bool(flythrough_entry.get("faced", False))
        mesh_block_raw = flythrough_entry.get("mesh_block")
        mesh_block = f"M#{mesh_block_raw}" if mesh_block_raw else None
        mesh_size = flythrough_entry.get("mesh_size")
    else:
        vertex_count = 0
        face_count = 0
        has_faces = bool(cohort_entry.get("has_faces")) if cohort_entry else False
        mesh_block = None
        mesh_size = cohort_entry.get("mesh_size") if cohort_entry else None

    # --- render_class ---
    if face_count > 0:
        render_class = "faced"
    elif vertex_count > 0:
        render_class = "point-only"
    else:
        render_class = "unknown"

    # --- obj_sha1 (SHA-1 hex digest, matching schema pattern ^[0-9a-f]{40}$)
    obj_sha1: str | None = None
    obj_path_obj = Path(obj_path)
    if obj_path_obj.exists():
        obj_sha1 = hashlib.sha1(obj_path_obj.read_bytes()).hexdigest()

    return {
        "obj_path": obj_path,
        "mesh_block": mesh_block,
        "mesh_size": mesh_size,
        "vertex_count": vertex_count,
        "face_count": face_count,
        "has_faces": has_faces,
        "render_class": render_class,
        "obj_sha1": obj_sha1,
    }


def build_world(
    asset_id: str,
    world: dict[str, Any],
    flythrough_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
    # Resolve world_json path: use flythrough-index if available, else construct
    if flythrough_entry and isinstance(flythrough_entry.get("world_json"), str):
        wj = flythrough_entry["world_json"]
        if Path(wj).is_absolute():
            world_json_path = wj
        else:
            world_json_path = str(WORLD_DIR / wj)
    else:
        world_json_path = str(WORLD_DIR / f"{asset_id}.world.json")
    return {
        "world_json": world_json_path,
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


def load_material_scan_results() -> tuple[dict[str, dict[str, Any]], str | None]:
    """Load the consolidated NIF material scan results (cached).

    Returns (results_dict, scanned_at_timestamp).
    Returns ({}, None) if the scan results file does not exist or is unreadable.
    """
    global _material_scan_cache, _material_scan_scanned_at, _material_scan_loaded
    if _material_scan_loaded:
        cache = _material_scan_cache if _material_scan_cache is not None else {}
        return cache, _material_scan_scanned_at
    _material_scan_loaded = True
    try:
        data = json.loads(MATERIAL_SCAN_RESULTS.read_text(encoding="utf-8-sig"))
        _material_scan_cache = data.get("results", {})
        _material_scan_scanned_at = data.get("scanned_at")
        return _material_scan_cache, _material_scan_scanned_at
    except FileNotFoundError, json.JSONDecodeError, OSError:
        _material_scan_cache = {}
        _material_scan_scanned_at = None
        return {}, None


def build_materials(
    asset_id: str,
    cohort_entry: dict[str, Any] | None,
    flythrough_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the materials sub-record.

    v0.8: prefers confirmed NIF-level material property counts from
    ``material-scan-results.json`` (populated by ``scan_nif_material_properties.py``).
    Falls back to v0.7 inference from flythrough texture linkage when scan data is
    not yet available.

    Confirmed status rules (scan data present):
    - texture_property_count > 0 → "textured"
    - material_property_count > 0 or vertex_color_property_count > 0 (no texture) → "material-or-vertex-color-only"
    - all three counts == 0 → "missing" (NIF has no material properties)

    Inference rules (scan data absent, v0.7 fallback):
    - linked_textures non-empty → "textured" (flythrough pipeline confirmed bindings)
    - faced=True but no linked_textures → "material-or-vertex-color-only"
    - otherwise → "unknown" (point-only + no textures = no material signal)
    """
    scan_results, scan_scanned_at = load_material_scan_results()
    scan = scan_results.get(asset_id)

    if scan is not None:
        # Confirmed NIF-level data
        tex_count = scan.get("texture_property_count", 0)
        mat_count = scan.get("material_property_count", 0)
        vc_count = scan.get("vertex_color_property_count", 0)
        scanned_at = scan_scanned_at  # top-level timestamp, shared by all scanned assets

        if tex_count > 0:
            material_status = "textured"
        elif mat_count > 0 or vc_count > 0:
            material_status = "material-or-vertex-color-only"
        else:
            material_status = "missing"

        nif_version = scan.get("nif_version", "")
        notes = [
            f"material_status={material_status} confirmed by NIF-level material property scan"
            f" (NiTexturingProperty={tex_count}, NiMaterialProperty={mat_count},"
            f" NiVertexColorProperty={vc_count}, nif_version={nif_version})"
        ]

        return {
            "material_status": material_status,
            "texture_property_count": tex_count,
            "material_property_count": mat_count,
            "vertex_color_property_count": vc_count,
            "scanned_at": scanned_at,
            "notes": notes,
        }

    # --- v0.7 fallback: inference from flythrough linkage ---
    if flythrough_entry:
        linked = flythrough_entry.get("linked_textures")
        has_textures = isinstance(linked, list) and len(linked) > 0
        faced = bool(flythrough_entry.get("faced", False))
        if has_textures:
            material_status = "textured"
            notes = [
                "material_status=textured inferred from flythrough texture linkage"
                " (texture bindings confirmed by pipeline);"
                " not yet confirmed by NIF-level material property scan"
            ]
        elif faced:
            material_status = "material-or-vertex-color-only"
            notes = [
                "material_status=material-or-vertex-color-only inferred from faced=True"
                " + no linked textures;"
                " not yet confirmed by NIF-level material property scan"
            ]
        else:
            material_status = "unknown"
            notes = [
                "material_status=unknown: no texture linkage and not faced; NIF material properties not yet scanned"
            ]
    else:
        material_status = "unknown"
        notes = [
            "material data not yet extracted from NIF - status=unknown"
            + (f" (cohort has_faces={cohort_entry.get('has_faces')})" if cohort_entry else "")
        ]
    return {
        "material_status": material_status,
        "texture_property_count": 0,
        "material_property_count": 0,
        "vertex_color_property_count": 0,
        "scanned_at": None,
        "notes": notes,
    }


def build_textures(flythrough_entry: dict[str, Any] | None) -> dict[str, Any]:
    """Build the textures sub-record. Populates from flythrough-index if available.

    The ``source`` field is set to ``"flythrough"`` when the flythrough-index
    entry has a linked_textures list (even if empty — the source is known).
    Falls back to ``"unknown"`` when no flythrough entry exists.
    The ``"scene"`` source value is reserved for a future NIF-level texture
    scan (scene-manifest builder does not yet read texture bindings from NIF).
    """
    if flythrough_entry and isinstance(flythrough_entry.get("linked_textures"), list):
        linked = [str(t) for t in flythrough_entry["linked_textures"]]
        return {
            "source": "flythrough",
            "linked_texture_count": len(linked),
            "linked_textures": linked,
            "missing_texture_count": 0,
            "placeholder_texture_count": 0,
        }
    return {
        "source": "unknown",
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
    """Build the validation sub-record, computing warnings and consumer_ready flag.

    v0.6: geometry fields are now populated from flythrough-index (vertex_count,
    face_count, mesh_block, mesh_size, render_class). Warnings reflect the
    actual populated state rather than hardcoded "not yet extracted" messages.
    """
    warnings: list[str] = []
    if geometry["vertex_count"] == 0:
        warnings.append("vertex_count=0 - geometry not available")
    if geometry["face_count"] == 0:
        if geometry["vertex_count"] > 0:
            warnings.append("face_count=0 (point-only asset) - no face data")
        else:
            warnings.append("face_count=0 - no face data")
    if geometry["render_class"] == "unknown":
        warnings.append("render_class=unknown - no vertex or face data")
    if geometry["mesh_block"] is None:
        warnings.append("mesh_block=null - mesh block not mapped to M#N convention")
    if materials["material_status"] == "unknown":
        warnings.append("material_status=unknown - NIF material properties not yet scanned")
    if textures["source"] == "unknown":
        warnings.append("textures.source=unknown - texture linkage not yet populated from any source")
    elif textures["linked_texture_count"] == 0:
        warnings.append("linked_textures=[] - asset has texture source but zero linked textures")
    # consumer_ready requires: faces present, materials known, textures sourced, mesh_block known
    consumer_ready = (
        geometry["vertex_count"] > 0
        and geometry["face_count"] > 0
        and geometry["has_faces"]
        and materials["material_status"] != "unknown"
        and textures["source"] != "unknown"
        and textures["linked_texture_count"] > 0
        and geometry["mesh_block"] is not None
    )
    return {
        "schema_valid": True,  # set False below if validator fails
        "consumer_ready": consumer_ready,
        "warnings": warnings,
        "errors": [],
    }


def load_all_flythrough_ids() -> list[str]:
    """Return all asset IDs from the flythrough-index assets dict."""
    try:
        idx = json.loads(FLYTHROUGH_INDEX.read_text(encoding="utf-8-sig"))
    except FileNotFoundError, json.JSONDecodeError, OSError:
        print("ERROR: cannot read flythrough-index.json", file=sys.stderr)
        return []
    assets = idx.get("assets", {})
    return sorted(assets.keys()) if isinstance(assets, dict) else []


def build_manifest(asset_id: str) -> dict[str, Any]:
    """Build a complete scene-manifest/v1-draft entry for one asset_id."""
    flythrough_entry = load_flythrough_entry(asset_id)
    world = load_world(asset_id, flythrough_entry)
    cohort_list = load_cohort()
    cohort_entry = next(
        (e for e in cohort_list if str(e.get("asset_id", "")).startswith(asset_id)),
        None,
    )
    geometry = build_geometry(asset_id, cohort_entry, flythrough_entry)
    world_rec = build_world(asset_id, world, flythrough_entry)
    materials = build_materials(asset_id, cohort_entry, flythrough_entry)
    textures = build_textures(flythrough_entry)
    provenance = build_provenance(asset_id, cohort_entry, flythrough_entry)
    validation = build_validation(geometry, materials, textures)
    return {
        "SchemaVersion": "scene-manifest/v1",
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


def find_id_asset_ids() -> list[str]:
    """Return the identity (translation == 0) asset IDs from transform-examples.json.

    Mirrors find_non_id_asset_ids so tests can lock both sides of the contrast
    in lockstep with the transform-examples source-of-truth.
    """
    t = json.loads(TRANSFORM_EXAMPLES.read_text(encoding="utf-8-sig"))
    return [e.get("asset_id", e.get("id", "")) for e in t.get("identity_examples", [])]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build scene-manifest/v1-draft entry for one asset")
    parser.add_argument("--asset-id", help="Asset ID (16-char hex). Mutually exclusive with --all-non-id.")
    parser.add_argument("--all-non-id", action="store_true", help="Build all 4 non-id samples")
    parser.add_argument(
        "--all-flythrough", action="store_true", help="Scale-out: build manifests for all flythrough-index assets"
    )
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
    elif args.all_flythrough:
        asset_ids = load_all_flythrough_ids()
        if not asset_ids:
            print("ERROR: no assets found in flythrough-index.json", file=sys.stderr)
            return 1
    else:
        parser.error("either --asset-id, --all-non-id, or --all-flythrough is required")

    overall_ok = True
    start_time = time.monotonic()
    success_count = 0
    error_count = 0
    invalid_count = 0
    for asset_id in asset_ids:
        try:
            manifest = build_manifest(asset_id)
        except FileNotFoundError as e:
            print(f"SKIP: {asset_id} - {e}", file=sys.stderr)
            error_count += 1
            overall_ok = False
            continue
        errors = validate_against_schema(manifest)
        if errors:
            manifest["validation"]["schema_valid"] = False
            manifest["validation"]["errors"] = errors
            invalid_count += 1
            overall_ok = False
            if not args.all_flythrough:
                print(f"INVALID: {asset_id} - {len(errors)} schema error(s):", file=sys.stderr)
                for err in errors:
                    print(f"  {err}", file=sys.stderr)
        else:
            success_count += 1
        if args.validate_only:
            status = "VALID" if not errors else f"INVALID ({len(errors)} errors)"
            print(f"{asset_id}: {status}, consumer_ready={manifest['validation']['consumer_ready']}")
            continue
        # For scale-out, use stage6/ directory; for individual/all-non-id, use DEFAULT_OUT_DIR or --out
        if args.all_flythrough:
            out_path = SCALE_OUT_DIR / f"manifest-{asset_id}.json"
        else:
            out_path = Path(args.out) if args.out else DEFAULT_OUT_DIR / f"sample-manifest-{asset_id}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        status = "VALID" if not errors else f"INVALID ({len(errors)} errors)"
        if not args.all_flythrough:
            print(f"wrote {out_path} - {status}, consumer_ready={manifest['validation']['consumer_ready']}")

    elapsed = time.monotonic() - start_time
    if args.all_flythrough:
        total = len(asset_ids)
        print(f"\nScale-out complete: {success_count}/{total} built, {invalid_count} invalid, {error_count} errors")
        print(f"Wall-clock: {elapsed:.1f}s ({elapsed / total:.3f}s per asset)")
        if invalid_count or error_count:
            print("(re-run with --asset-id <id> to inspect individual failures)")
    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
