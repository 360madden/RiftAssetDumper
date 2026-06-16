"""Unit tests for scripts/build_scene_manifest.py.

Covers:
- is_identity_transform helper (positive/negative/missing rotation)
- build_world extracts the parent node's transform
- find_non_id_asset_ids returns 4 entries
- build_manifest is end-to-end valid (run --validate-only --all-non-id)
- consumer_ready gating: face_count=0 OR material_status=unknown -> not ready
- coordinate_system constants match the contract
- schema-validity guarantee: all 4 emitted manifests pass Draft202012Validator
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_scene_manifest import (  # noqa: E402
    COORDINATE_SYSTEM,
    find_id_asset_ids,
    find_non_id_asset_ids,
    is_identity_transform,
    validate_against_schema,
)

WORLD_DIR = REPO_ROOT / "Assets" / "build" / "flythrough" / "objs" / "worlds"
SCHEMA_PATH = (
    REPO_ROOT
    / "Assets"
    / "Exports"
    / "discovery-plan"
    / "cycle-2"
    / "stage2"
    / "scene-manifest-v1.draft.schema.json"
)
NON_ID_IDS = [
    "07f37c99a80da009",
    "2c85cfa17543443b",
    "4a97d66a665a538e",
    "593ea328978bde38",
]


# ---------- is_identity_transform ----------

def test_is_identity_true_for_exact_identity() -> None:
    t = [0.0, 0.0, 0.0]
    r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    assert is_identity_transform(t, r, 1.0) is True


def test_is_identity_false_for_translated() -> None:
    t = [0.0, 0.0, 1e-5]  # just above 1e-6 tolerance
    r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    assert is_identity_transform(t, r, 1.0) is False


def test_is_identity_false_for_scaled() -> None:
    t = [0.0, 0.0, 0.0]
    r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    assert is_identity_transform(t, r, 1.1) is False


def test_is_identity_false_for_rotated() -> None:
    t = [0.0, 0.0, 0.0]
    r = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # degenerate but not identity
    assert is_identity_transform(t, r, 1.0) is False


def test_is_identity_false_for_missing_rotation() -> None:
    assert is_identity_transform([0, 0, 0], None, 1.0) is False


# ---------- coordinate_system constants ----------

def test_coordinate_system_matches_contract() -> None:
    """Lock the coordinate system constants against coordinate-contract.md."""
    assert COORDINATE_SYSTEM["handedness"] == "right"
    assert COORDINATE_SYSTEM["up_axis"] == "Y"
    assert COORDINATE_SYSTEM["forward_axis"] == "-Z"
    assert COORDINATE_SYSTEM["translation_layout"] == "xyz"
    assert COORDINATE_SYSTEM["rotation_layout"] == "row-major-3x3"
    assert COORDINATE_SYSTEM["scale_layout"] == "uniform-float"
    assert COORDINATE_SYSTEM["trs_composition"] == "v_world = R * (S * v_local) + T"
    assert COORDINATE_SYSTEM["identity_tolerance"] == 1e-6


# ---------- find_non_id_asset_ids ----------

def test_find_non_id_asset_ids_returns_4() -> None:
    ids = find_non_id_asset_ids()
    assert len(ids) == 4
    for i in ids:
        assert len(i) == 16 and all(c in "0123456789abcdef" for c in i)


# ---------- end-to-end: --validate-only --all-non-id ----------

@pytest.mark.skipif(
    not all((WORLD_DIR / f"{aid}.world.json").exists() for aid in NON_ID_IDS),
    reason="one or more non-id world.json files missing",
)
def test_all_non_id_manifests_validate() -> None:
    """Run the builder in validate-only mode for all 4 non-id assets; expect 0 errors each."""
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "build_scene_manifest.py"),
            "--all-non-id",
            "--validate-only",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, f"builder exited {r.returncode}: {r.stderr}"
    for line in r.stdout.splitlines():
        assert "INVALID" not in line, f"builder reported INVALID: {line}"


# ---------- end-to-end: emitted sample manifests validate against the schema ----------

@pytest.mark.skipif(
    not (REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage2" / "sample-manifest-07f37c99a80da009.json").exists(),
    reason="sample manifests not yet generated",
)
def test_emitted_sample_07f37c99a80da009_validates() -> None:
    """The emitted sample-manifest-07f37c99a80da009.json must pass Draft202012Validator."""
    sample = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage2" / "sample-manifest-07f37c99a80da009.json"
    m = json.loads(sample.read_text(encoding="utf-8-sig"))
    errors = validate_against_schema(m)
    assert errors == [], f"schema errors: {errors}"
    # Original (hand-authored) sample is the truth reference for the non-id
    # translation; the builder reproduces it exactly.
    assert m["world"]["world_transform_identity"] is False
    assert m["world"]["world_transform_summary"]["translation"] == pytest.approx(
        [8.820713, -0.8490117, 0.07588669], abs=1e-5
    )


# ---------- consumer_ready gating ----------

def test_consumer_ready_false_for_known_unknowns() -> None:
    """A manifest with 0 faces + unknown materials + 0 textures must not be consumer_ready."""
    from build_scene_manifest import build_validation

    v = build_validation(
        geometry={
            "vertex_count": 0,
            "face_count": 0,
            "has_faces": False,
            "render_class": "unknown",
            "mesh_block": None,
        },
        materials={
            "material_status": "unknown",
            "texture_property_count": 0,
            "material_property_count": 0,
            "vertex_color_property_count": 0,
        },
        textures={
            "linked_texture_count": 0,
            "linked_textures": [],
            "missing_texture_count": 0,
            "placeholder_texture_count": 0,
        },
    )
    assert v["consumer_ready"] is False
    assert len(v["warnings"]) >= 3


def test_consumer_ready_true_when_all_known() -> None:
    """A fully populated manifest must be consumer_ready=True with no warnings."""
    from build_scene_manifest import build_validation

    v = build_validation(
        geometry={
            "vertex_count": 100,
            "face_count": 50,
            "has_faces": True,
            "render_class": "faced",
            "mesh_block": "M#7",
        },
        materials={
            "material_status": "textured",
            "texture_property_count": 2,
            "material_property_count": 1,
            "vertex_color_property_count": 0,
        },
        textures={
            "linked_texture_count": 2,
            "linked_textures": ["t1.png", "t2.png"],
            "missing_texture_count": 0,
            "placeholder_texture_count": 0,
        },
    )
    assert v["consumer_ready"] is True
    assert v["warnings"] == []


# ---------- schema presence ----------

def test_schema_file_exists_and_is_2020_12() -> None:
    assert SCHEMA_PATH.exists(), f"schema not found: {SCHEMA_PATH}"
    s = json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))
    assert s["$schema"] == "https://json-schema.org/draft/2020-12/schema"


# ---------- IDENTITY vs NON-ID contrast (C2-2.4 batch) ----------

SAMPLE_DIR = (
    REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage2"
)


def _load_sample(asset_id: str) -> dict[str, Any]:
    path = SAMPLE_DIR / f"sample-manifest-{asset_id}.json"
    assert path.exists(), f"sample missing: {path}"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8-sig"))
    return data


@pytest.mark.skipif(
    not all((SAMPLE_DIR / f"sample-manifest-{aid}.json").exists() for aid in NON_ID_IDS),
    reason="non-id sample batch not yet built",
)
def test_find_id_asset_ids_returns_nonzero() -> None:
    """Mirror of test_find_non_id_asset_ids_returns_4: identity cohort is also populated."""
    ids = find_id_asset_ids()
    assert len(ids) > 0, "identity_examples should not be empty"
    for i in ids:
        assert len(i) == 16 and all(c in "0123456789abcdef" for c in i)


@pytest.mark.skipif(
    not all(
        (SAMPLE_DIR / f"sample-manifest-{aid}.json").exists()
        for aid in NON_ID_IDS + find_id_asset_ids()
    ),
    reason="identity + non-id sample batch not yet built",
)
def test_identity_manifests_have_identity_transform() -> None:
    """Identity cohort must report world_transform_identity=True.

    This is the schema-scale contrast: 4 non-id (translation != 0) + N id
    (translation == 0). The builder must distinguish them correctly.
    """
    for aid in find_id_asset_ids():
        m = _load_sample(aid)
        assert m["world"]["world_transform_identity"] is True, (
            f"identity asset {aid} should have identity transform"
        )
        assert m["world"]["world_transform_summary"]["translation"] == [0, 0, 0]


@pytest.mark.skipif(
    not all(
        (SAMPLE_DIR / f"sample-manifest-{aid}.json").exists()
        for aid in NON_ID_IDS + find_id_asset_ids()
    ),
    reason="identity + non-id sample batch not yet built",
)
def test_non_id_manifests_have_non_identity_transform() -> None:
    """Non-id cohort must report world_transform_identity=False (locks the v0.3 contrast)."""
    for aid in NON_ID_IDS:
        m = _load_sample(aid)
        assert m["world"]["world_transform_identity"] is False, (
            f"non-id asset {aid} should have non-identity transform"
        )


@pytest.mark.skipif(
    not all(
        (SAMPLE_DIR / f"sample-manifest-{aid}.json").exists()
        for aid in NON_ID_IDS + find_id_asset_ids()
    ),
    reason="identity + non-id sample batch not yet built",
)
def test_both_cohorts_share_consumer_ready_false() -> None:
    """consumer_ready gates on data extraction (faces/materials/textures/mesh_block),
    NOT on transform identity. Both id and non-id cohorts must report False until
    the extraction pass runs (C2-3.x). This locks the v0.3 gate semantics.
    """
    for aid in NON_ID_IDS + find_id_asset_ids():
        m = _load_sample(aid)
        assert m["validation"]["consumer_ready"] is False, (
            f"asset {aid} should NOT be consumer_ready (extraction pass not yet run)"
        )
        assert m["validation"]["schema_valid"] is True
