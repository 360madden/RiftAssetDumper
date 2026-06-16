"""Smoke tests for `scripts/validate_scene_manifest_schema.py` (C2-2.4 acceptance)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "validate_scene_manifest_schema.py"
SCHEMA = (
    REPO_ROOT
    / "Assets"
    / "Exports"
    / "discovery-plan"
    / "cycle-2"
    / "stage2"
    / "scene-manifest-v1.draft.schema.json"
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO_ROOT),
    )


def test_script_exists() -> None:
    """The validator script must exist at the canonical path."""
    assert SCRIPT.exists()


def test_help_exits_zero() -> None:
    """--help must exit 0 and describe the script."""
    r = _run("--help")
    assert r.returncode == 0, f"--help returned {r.returncode}: {r.stderr}"
    assert "scene-manifest-v1" in r.stdout or "scene-manifest" in r.stdout


def test_default_schema_validates_as_draft_2020_12() -> None:
    """Default invocation (no args) must validate the committed draft schema.

    This is the C2-2.4 acceptance criterion: schema validates as draft JSON
    Schema 2020-12.
    """
    r = _run()
    assert r.returncode == 0, f"default run returned {r.returncode}: {r.stderr}"
    assert "schema valid as JSON Schema 2020-12" in r.stdout


def test_explicit_schema_path_validates() -> None:
    """--schema pointing at the committed draft must validate."""
    r = _run("--schema", str(SCHEMA))
    assert r.returncode == 0, r.stderr
    assert "schema valid as JSON Schema 2020-12" in r.stdout


def test_missing_schema_returns_code_2() -> None:
    """Nonexistent --schema path must return code 2 (input error)."""
    r = _run("--schema", "does/not/exist.schema.json")
    assert r.returncode == 2
    assert "not found" in r.stderr.lower()


def test_missing_fixture_returns_code_2(tmp_path: Path) -> None:
    """Nonexistent --fixture path must return code 2 (input error)."""
    r = _run("--fixture", str(tmp_path / "absent.json"))
    assert r.returncode == 2
    assert "not found" in r.stderr.lower()


def _valid_instance() -> dict[str, object]:
    """Build a minimal valid manifest instance (all required fields populated)."""
    return {
        "SchemaVersion": "scene-manifest/v1-draft",
        "asset_id": "07f37c99a80da009",
        "generated_at": "2026-06-15T00:00:00Z",
        "producer": {"tool": "rift-asset-dumper", "version": "v0.3"},
        "geometry": {
            "obj_path": "objs/07f37c99a80da009.obj",
            "vertex_count": 100,
            "face_count": 50,
            "has_faces": True,
            "render_class": "faced",
        },
        "world": {
            "world_json": "objs/worlds/07f37c99a80da009.world.json",
            "node_count": 5,
            "mesh_count": 1,
            "transform_semantics": "mesh-parent-chain",
            "coordinate_system": {
                "handedness": "right",
                "up_axis": "Y",
                "forward_axis": "-Z",
                "translation_layout": "xyz",
                "rotation_layout": "row-major-3x3",
                "scale_layout": "uniform-float",
                "trs_composition": "v_world = R * (S * v_local) + T",
                "identity_tolerance": 1e-6,
            },
            "world_transform_summary": {
                "translation": [0.0, 0.0, 0.0],
                "rotation": [1, 0, 0, 0, 1, 0, 0, 0, 1],
                "scale": 1.0,
            },
            "world_transform_identity": True,
        },
        "materials": {
            "material_status": "textured",
            "texture_property_count": 1,
            "material_property_count": 0,
            "vertex_color_property_count": 0,
            "notes": [],
        },
        "textures": {
            "linked_texture_count": 1,
            "linked_textures": ["texture1.png"],
            "missing_texture_count": 0,
            "placeholder_texture_count": 0,
        },
        "provenance": {
            "cohort": "stage1/cohort.json",
            "source_nif_hash": "07f37c99a80da009",
            "flythrough_index_entry": "objs/07f37c99a80da009",
            "evidence_files": [],
        },
        "validation": {
            "schema_valid": True,
            "consumer_ready": True,
            "warnings": [],
            "errors": [],
        },
    }


def test_valid_fixture_passes(tmp_path: Path) -> None:
    """A fully-populated valid manifest fixture must pass validation."""
    fixture = tmp_path / "valid.json"
    fixture.write_text(json.dumps(_valid_instance()), encoding="utf-8")
    r = _run("--fixture", str(fixture))
    assert r.returncode == 0, f"valid fixture returned {r.returncode}: {r.stderr}"
    assert "fixture valid" in r.stdout


def test_invalid_fixture_missing_required_fields(tmp_path: Path) -> None:
    """A fixture missing required fields must fail validation with code 1."""
    fixture = tmp_path / "invalid.json"
    fixture.write_text(json.dumps({"asset_id": "07f37c99a80da009"}), encoding="utf-8")
    r = _run("--fixture", str(fixture))
    assert r.returncode == 1
    assert "fixture invalid" in r.stderr


def test_invalid_fixture_wrong_render_class(tmp_path: Path) -> None:
    """A fixture with an invalid render_class enum must fail validation."""
    instance = _valid_instance()
    assert isinstance(instance["geometry"], dict)
    instance["geometry"]["render_class"] = "not-a-real-class"
    fixture = tmp_path / "bad_enum.json"
    fixture.write_text(json.dumps(instance), encoding="utf-8")
    r = _run("--fixture", str(fixture))
    assert r.returncode == 1
    assert "fixture invalid" in r.stderr


def test_invalid_fixture_bad_asset_id_pattern(tmp_path: Path) -> None:
    """A fixture with a non-hex asset_id must fail the pattern check."""
    instance = _valid_instance()
    instance["asset_id"] = "not-hex"
    fixture = tmp_path / "bad_pattern.json"
    fixture.write_text(json.dumps(instance), encoding="utf-8")
    r = _run("--fixture", str(fixture))
    assert r.returncode == 1
    assert "fixture invalid" in r.stderr


def test_malformed_fixture_json_returns_code_1(tmp_path: Path) -> None:
    """A fixture with invalid JSON must fail with the documented error format.

    The validator distinguishes parse failures (JSONDecodeError) from schema
    violations; both surface as exit code 1 with a clear message. This locks
    the contract that the validator never crashes with an uncaught exception
    on a malformed fixture.
    """
    fixture = tmp_path / "malformed.json"
    fixture.write_text("{not valid json", encoding="utf-8")
    r = _run("--fixture", str(fixture))
    assert r.returncode == 1
    assert "invalid JSON" in r.stderr
