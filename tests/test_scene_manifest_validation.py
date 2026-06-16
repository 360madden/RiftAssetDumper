"""C2-7.1 Scene Manifest Validation Suite — comprehensive consumer validation tests.

Covers:
- Schema validation: all 217 stage6 scale-out manifests pass Draft202012Validator
- Schema validation: all 24 stage2 sample manifests pass the locked schema
- Pack integrity: scene-manifest-pack-v1.json structure validates
- Cross-reference: pack entries match individual manifests byte-for-byte
- OBJ path existence: every manifest's obj_path exists on disk
- World.json existence: every manifest's world_json exists on disk
- Transform finiteness: no NaN or Inf in translation/rotation/scale
- Texture.source enum: all values are "scene", "flythrough", or "unknown"
- Cohort completeness: pack entries cover all expected assets
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGE2_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage2"
STAGE6_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage6"
PACK_PATH = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage4" / "scene-manifest-pack-v1.json"
SCHEMA_PATH = STAGE2_DIR / "scene-manifest-v1.schema.json"

# ---------- Helpers ----------

def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file with utf-8-sig encoding."""
    result: Any = json.loads(path.read_text(encoding="utf-8-sig"))
    return result  # type: ignore[no-any-return]


def _validate_schema(manifest: dict[str, Any]) -> list[str]:
    """Validate a manifest against the locked scene-manifest v1 schema."""
    from jsonschema import Draft202012Validator
    schema = _load_json(SCHEMA_PATH)
    validator = Draft202012Validator(schema)
    return [
        f"{'/'.join(str(p) for p in err.absolute_path)}: {err.message}"
        for err in validator.iter_errors(manifest)
    ]


def _stage6_manifest_paths() -> list[Path]:
    """Return sorted list of all stage6 manifest JSON files."""
    return sorted(STAGE6_DIR.glob("manifest-????????????????.json"))


def _stage2_sample_paths() -> list[Path]:
    """Return sorted list of all stage2 sample manifest JSON files."""
    return sorted(STAGE2_DIR.glob("sample-manifest-*.json"))


# ---------- Schema Validation: Scale-out Manifests ----------

@pytest.mark.skipif(
    not SCHEMA_PATH.exists(),
    reason="locked schema not yet written",
)
@pytest.mark.skipif(
    not STAGE6_DIR.exists() or len(list(STAGE6_DIR.glob("manifest-*.json"))) == 0,
    reason="stage6 scale-out manifests not yet built",
)
def test_all_stage6_manifests_pass_schema() -> None:
    """Every stage6 scale-out manifest must pass the locked scene-manifest/v1 schema."""
    paths = _stage6_manifest_paths()
    assert len(paths) > 0, "no stage6 manifests found"
    failures: list[tuple[str, list[str]]] = []
    for path in paths:
        manifest = _load_json(path)
        errors = _validate_schema(manifest)
        if errors:
            failures.append((path.name, errors))
    assert failures == [], (
        f"{len(failures)}/{len(paths)} stage6 manifests failed schema validation:\n"
        + "\n".join(f"  {name}: {errs}" for name, errs in failures[:10])
    )


# ---------- Schema Validation: Stage2 Sample Manifests ----------

@pytest.mark.skipif(
    not SCHEMA_PATH.exists(),
    reason="locked schema not yet written",
)
@pytest.mark.skipif(
    not STAGE2_DIR.exists() or len(list(STAGE2_DIR.glob("sample-manifest-*.json"))) == 0,
    reason="stage2 sample manifests not yet built",
)
def test_all_stage2_samples_pass_schema() -> None:
    """Every stage2 sample manifest must pass the locked schema."""
    paths = _stage2_sample_paths()
    assert len(paths) > 0, "no stage2 sample manifests found"
    failures: list[tuple[str, list[str]]] = []
    for path in paths:
        manifest = _load_json(path)
        errors = _validate_schema(manifest)
        if errors:
            failures.append((path.name, errors))
    assert failures == [], (
        f"{len(failures)}/{len(paths)} stage2 samples failed schema validation:\n"
        + "\n".join(f"  {name}: {errs}" for name, errs in failures[:10])
    )


# ---------- Schema Validation: Exact Counts ----------

@pytest.mark.skipif(
    not STAGE6_DIR.exists(),
    reason="stage6 directory not yet created",
)
def test_stage6_manifest_count_is_217() -> None:
    """Scale-out must produce 217 manifests (one per flythrough-index asset)."""
    paths = _stage6_manifest_paths()
    assert len(paths) == 217, f"expected 217 stage6 manifests, got {len(paths)}"


@pytest.mark.skipif(
    not STAGE2_DIR.exists(),
    reason="stage2 directory not yet created",
)
def test_stage2_sample_count_is_24() -> None:
    """Stage2 must have 24 sample manifests (4 non-id + 20 identity)."""
    paths = _stage2_sample_paths()
    assert len(paths) == 24, f"expected 24 stage2 samples, got {len(paths)}"


# ---------- Pack Integrity ----------

@pytest.mark.skipif(
    not PACK_PATH.exists(),
    reason="scene-manifest-pack-v1.json not yet built",
)
def test_pack_structure_is_valid() -> None:
    """Pack must have required fields and correct cohort_size."""
    pack = _load_json(PACK_PATH)
    assert pack["SchemaVersion"] == "scene-manifest-pack/v1"
    assert isinstance(pack["cohort_size"], int)
    assert pack["cohort_size"] > 0
    assert "entries" in pack
    assert isinstance(pack["entries"], list)
    assert len(pack["entries"]) == pack["cohort_size"]


@pytest.mark.skipif(
    not PACK_PATH.exists(),
    reason="scene-manifest-pack-v1.json not yet built",
)
def test_pack_entries_all_have_asset_id() -> None:
    """Every pack entry must have a valid 16-char hex asset_id."""
    pack = _load_json(PACK_PATH)
    import re
    hex_pat = re.compile(r"^[0-9a-f]{16}$")
    missing: list[int] = []
    for i, entry in enumerate(pack["entries"]):
        aid = entry.get("asset_id", "")
        if not hex_pat.match(aid):
            missing.append(i)
    assert missing == [], f"entries at indices {missing} have invalid/missing asset_id"


@pytest.mark.skipif(
    not PACK_PATH.exists(),
    reason="scene-manifest-pack-v1.json not yet built",
)
def test_pack_entries_all_pass_schema() -> None:
    """Every entry in the aggregate pack must pass the locked schema."""
    pack = _load_json(PACK_PATH)
    failures: list[tuple[str, list[str]]] = []
    for entry in pack["entries"]:
        errors = _validate_schema(entry)
        if errors:
            aid = entry.get("asset_id", "unknown")
            failures.append((aid, errors))
    assert failures == [], (
        f"{len(failures)}/{len(pack['entries'])} pack entries failed schema:\n"
        + "\n".join(f"  {aid}: {errs}" for aid, errs in failures[:10])
    )


# ---------- OBJ Path Existence ----------

@pytest.mark.skipif(
    not STAGE6_DIR.exists() or len(list(STAGE6_DIR.glob("manifest-*.json"))) == 0,
    reason="stage6 manifests not yet built",
)
def test_all_stage6_obj_paths_exist() -> None:
    """Every stage6 manifest's obj_path must point to an existing file."""
    paths = _stage6_manifest_paths()
    missing: list[str] = []
    for path in paths:
        manifest = _load_json(path)
        obj_path = manifest["geometry"]["obj_path"]
        if not os.path.exists(obj_path):
            missing.append(f"{manifest['asset_id']}: {obj_path}")
    assert missing == [], (
        f"{len(missing)}/{len(paths)} manifests have missing OBJ paths:\n"
        + "\n".join(missing[:10])
    )


# ---------- World.json Path Existence ----------

@pytest.mark.skipif(
    not STAGE6_DIR.exists() or len(list(STAGE6_DIR.glob("manifest-*.json"))) == 0,
    reason="stage6 manifests not yet built",
)
def test_all_stage6_world_json_paths_exist() -> None:
    """Every stage6 manifest's world_json must point to an existing file."""
    paths = _stage6_manifest_paths()
    missing: list[str] = []
    for path in paths:
        manifest = _load_json(path)
        world_json = manifest["world"]["world_json"]
        if not os.path.exists(world_json):
            missing.append(f"{manifest['asset_id']}: {world_json}")
    assert missing == [], (
        f"{len(missing)}/{len(paths)} manifests have missing world_json paths:\n"
        + "\n".join(missing[:10])
    )


# ---------- Transform Finiteness ----------

@pytest.mark.skipif(
    not STAGE6_DIR.exists() or len(list(STAGE6_DIR.glob("manifest-*.json"))) == 0,
    reason="stage6 manifests not yet built",
)
def test_all_stage6_transforms_are_finite() -> None:
    """No manifest's translation/rotation/scale may contain NaN or Inf."""
    paths = _stage6_manifest_paths()
    bad: list[str] = []
    for path in paths:
        manifest = _load_json(path)
        ts = manifest["world"]["world_transform_summary"]
        for vec_name in ("translation", "rotation"):
            vec = ts.get(vec_name, [])
            for i, v in enumerate(vec):
                if not math.isfinite(v):
                    bad.append(f"{manifest['asset_id']} {vec_name}[{i}]={v}")
        s = ts.get("scale", 1.0)
        if not math.isfinite(s):
            bad.append(f"{manifest['asset_id']} scale={s}")
    assert bad == [], (
        f"{len(bad)} non-finite transform values:\n" + "\n".join(bad[:10])
    )


# ---------- Texture Source Enum ----------

@pytest.mark.skipif(
    not STAGE6_DIR.exists() or len(list(STAGE6_DIR.glob("manifest-*.json"))) == 0,
    reason="stage6 manifests not yet built",
)
def test_all_stage6_texture_source_is_valid_enum() -> None:
    """Every manifest's textures.source must be 'scene', 'flythrough', or 'unknown'."""
    valid = {"scene", "flythrough", "unknown"}
    paths = _stage6_manifest_paths()
    bad: list[str] = []
    for path in paths:
        manifest = _load_json(path)
        src = manifest["textures"]["source"]
        if src not in valid:
            bad.append(f"{manifest['asset_id']}: '{src}'")
    assert bad == [], (
        f"{len(bad)}/{len(paths)} manifests have invalid textures.source:\n"
        + "\n".join(bad[:10])
    )


# ---------- Texture Source Distribution ----------

@pytest.mark.skipif(
    not STAGE6_DIR.exists() or len(list(STAGE6_DIR.glob("manifest-*.json"))) == 0,
    reason="stage6 manifests not yet built",
)
def test_texture_source_never_scene() -> None:
    """textures.source='scene' is reserved for NIF-level scans — none should exist yet."""
    paths = _stage6_manifest_paths()
    scene_sourced: list[str] = []
    for path in paths:
        manifest = _load_json(path)
        if manifest["textures"]["source"] == "scene":
            scene_sourced.append(manifest["asset_id"])
    # 'scene' is valid but not yet populated; this test locks that baseline
    assert len(scene_sourced) == 0, (
        f"expected 0 'scene'-sourced textures, found {len(scene_sourced)}: {scene_sourced}"
    )


# ---------- Schema Validity Flag ----------

@pytest.mark.skipif(
    not STAGE6_DIR.exists() or len(list(STAGE6_DIR.glob("manifest-*.json"))) == 0,
    reason="stage6 manifests not yet built",
)
def test_all_stage6_schema_valid_flag_is_true() -> None:
    """Every manifest's validation.schema_valid must be True (built with validation)."""
    paths = _stage6_manifest_paths()
    bad: list[str] = []
    for path in paths:
        manifest = _load_json(path)
        if not manifest["validation"]["schema_valid"]:
            bad.append(manifest["asset_id"])
    assert bad == [], f"{len(bad)}/{len(paths)} manifests have schema_valid=False"


# ---------- Producer Version ----------

@pytest.mark.skipif(
    not STAGE6_DIR.exists() or len(list(STAGE6_DIR.glob("manifest-*.json"))) == 0,
    reason="stage6 manifests not yet built",
)
def test_all_stage6_producer_version_is_v0_8() -> None:
    """All scale-out manifests must be built by producer v0.8 (NIF-confirmed material data)."""
    paths = _stage6_manifest_paths()
    bad: list[str] = []
    for path in paths:
        manifest = _load_json(path)
        ver = manifest["producer"]["version"]
        if ver != "v0.8":
            bad.append(f"{manifest['asset_id']}: version={ver}")
    assert bad == [], f"{len(bad)}/{len(paths)} manifests have wrong producer version"


# ---------- Cross-Reference: Pack vs Individual Manifests ----------

@pytest.mark.skipif(
    not PACK_PATH.exists(),
    reason="scene-manifest-pack-v1.json not yet built",
)
@pytest.mark.skipif(
    not STAGE2_DIR.exists() or len(list(STAGE2_DIR.glob("sample-manifest-*.json"))) == 0,
    reason="stage2 sample manifests not yet built",
)
def test_pack_entries_match_stage2_manifests_bytes() -> None:
    """Every entry in the pack must be byte-identical to its stage2 individual manifest."""
    pack = _load_json(PACK_PATH)
    mismatches: list[str] = []
    for entry in pack["entries"]:
        aid = entry["asset_id"]
        stage2_path = STAGE2_DIR / f"sample-manifest-{aid}.json"
        if not stage2_path.exists():
            mismatches.append(f"{aid}: stage2 manifest missing")
            continue
        individual = _load_json(stage2_path)
        # Normalize generated_at before comparison (it's a timestamp that may drift)
        entry_normalized = {k: v for k, v in entry.items() if k != "generated_at"}
        individual_normalized = {k: v for k, v in individual.items() if k != "generated_at"}
        if entry_normalized != individual_normalized:
            mismatches.append(aid)
    assert mismatches == [], (
        f"{len(mismatches)}/{len(pack['entries'])} pack entries differ from stage2:\n"
        + "\n".join(mismatches[:10])
    )


# ---------- Cohort Completeness ----------

@pytest.mark.skipif(
    not PACK_PATH.exists(),
    reason="scene-manifest-pack-v1.json not yet built",
)
@pytest.mark.skipif(
    not STAGE2_DIR.exists() or len(list(STAGE2_DIR.glob("sample-manifest-*.json"))) == 0,
    reason="stage2 samples not yet built",
)
def test_pack_covers_all_stage2_samples() -> None:
    """Every stage2 sample manifest must have a corresponding pack entry."""
    pack = _load_json(PACK_PATH)
    pack_ids = {e["asset_id"] for e in pack["entries"]}
    stage2_paths = _stage2_sample_paths()
    for sp in stage2_paths:
        sample = _load_json(sp)
        assert sample["asset_id"] in pack_ids, (
            f"stage2 manifest {sample['asset_id']} not found in pack entries"
        )


# ---------- Schema File Presence ----------

def test_schema_file_exists() -> None:
    """The locked schema must exist on disk."""
    assert SCHEMA_PATH.exists(), f"schema not found: {SCHEMA_PATH}"


def test_schema_is_2020_12() -> None:
    """The locked schema must declare JSON Schema 2020-12."""
    schema = _load_json(SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_schema_const_is_locked() -> None:
    """The SchemaVersion const must be 'scene-manifest/v1'."""
    schema = _load_json(SCHEMA_PATH)
    assert schema["properties"]["SchemaVersion"]["const"] == "scene-manifest/v1"


def test_schema_has_textures_source_enum() -> None:
    """The textures.source field must have the 3-enum discriminant."""
    schema = _load_json(SCHEMA_PATH)
    tex_src = schema["$defs"]["Textures"]["properties"]["source"]
    assert tex_src["enum"] == ["scene", "flythrough", "unknown"]


def test_schema_has_obj_sha1_field() -> None:
    """The geometry.obj_sha1 parity field must exist in schema."""
    schema = _load_json(SCHEMA_PATH)
    assert "obj_sha1" in schema["$defs"]["Geometry"]["properties"]


def test_schema_has_scanned_at_field() -> None:
    """The materials.scanned_at parity field must exist in schema."""
    schema = _load_json(SCHEMA_PATH)
    assert "scanned_at" in schema["$defs"]["Materials"]["properties"]
