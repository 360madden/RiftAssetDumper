"""Unit tests for FT-7.2 LOD variant detector."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

import ft7_lod_detector as f7  # noqa: E402

# ── _sibling_key ──────────────────────────────────────────────


def test_sibling_key_dict() -> None:
    result = f7._sibling_key({"mesh_size": 280, "note": "resolved via probe lookup pattern (MB=7,"})
    assert result == "ms=280|note=resolved via probe lookup pattern (MB=7,"


def test_sibling_key_dict_long_note_truncates() -> None:
    result = f7._sibling_key({"mesh_size": 305, "note": "a" * 80})
    assert result == f"ms=305|note={'a' * 40}"


def test_sibling_key_string() -> None:
    result = f7._sibling_key("plain_string")
    assert result == "plain_string"


def test_sibling_key_empty() -> None:
    result = f7._sibling_key("")
    assert result == ""


# ── enrich_with_meshsize ──────────────────────────────────────


def test_enrich_empty_entries() -> None:
    result = f7.enrich_with_meshsize([], {})
    assert result == []


def test_enrich_no_lookup_match() -> None:
    entries: list[dict[str, Any]] = [{"asset_id": "abcd1234abcd1234", "vertex_count": 10}]
    result = f7.enrich_with_meshsize(entries, {})
    assert result[0]["mesh_size"] is None
    assert result[0]["probe_mesh_block"] is None


def test_enrich_with_lookup_match() -> None:
    entries: list[dict[str, Any]] = [{"asset_id": "0603cce7cee15eb8", "vertex_count": 80}]
    lookup = {"0603cce7cee15eb8": {"meshsize": 240, "mesh_block": 6, "faced": True, "note": "@264 index stream"}}
    result = f7.enrich_with_meshsize(entries, lookup)
    assert result[0]["mesh_size"] == 240
    assert result[0]["probe_mesh_block"] == 6
    assert result[0]["probe_note"] == "@264 index stream"


def test_enrich_preserves_existing_meshsize() -> None:
    entries: list[dict[str, Any]] = [{"asset_id": "abcd1234abcd1234", "mesh_size": 999, "vertex_count": 10}]
    result = f7.enrich_with_meshsize(entries, {})
    assert result[0]["mesh_size"] == 999


# ── detect_same_nif_lod ───────────────────────────────────────


def test_same_nif_lod_empty() -> None:
    result = f7.detect_same_nif_lod([])
    assert result == []


def test_same_nif_lod_single_entry() -> None:
    entries: list[dict[str, Any]] = [{"asset_id": "abcd1234abcd1234", "mesh_block": 6, "vertex_count": 100}]
    result = f7.detect_same_nif_lod(entries)
    assert result == []


def test_same_nif_lod_no_significant_reduction() -> None:
    """Two meshes same NIF but only 1.1x reduction — not classified as LOD."""
    entries: list[dict[str, Any]] = [
        {"asset_id": "abcd1234abcd1234", "mesh_block": 6, "vertex_count": 100, "face_count": 98, "faced": True},
        {"asset_id": "abcd1234abcd1234", "mesh_block": 7, "vertex_count": 90, "face_count": 88, "faced": True},
    ]
    result = f7.detect_same_nif_lod(entries)
    assert result == []


def test_same_nif_lod_clear_chain() -> None:
    entries: list[dict[str, Any]] = [
        {"asset_id": "abcd1234abcd1234", "mesh_block": 6, "vertex_count": 6489, "face_count": 6487, "faced": True},
        {"asset_id": "abcd1234abcd1234", "mesh_block": 107, "vertex_count": 41, "face_count": 39, "faced": True},
    ]
    result = f7.detect_same_nif_lod(entries)
    assert len(result) == 1
    assert result[0]["asset_id"] == "abcd1234abcd1234"
    assert result[0]["levels"] == 2
    assert result[0]["vertex_staircase"] == [6489, 41]
    assert result[0]["reduction_ratio"] > 100


# ── detect_meshsize_family_lod ────────────────────────────────


def test_meshsize_family_empty() -> None:
    result = f7.detect_meshsize_family_lod([])
    assert result == []


def test_meshsize_family_single_entry() -> None:
    entries: list[dict[str, Any]] = [{"mesh_size": 301, "vertex_count": 100, "face_count": 98, "faced": True}]
    result = f7.detect_meshsize_family_lod(entries)
    assert result == []


def test_meshsize_family_with_staircase() -> None:
    """7 entries with distinct vertex counts should score high."""
    entries: list[dict[str, Any]] = [
        {"mesh_size": 301, "vertex_count": 90, "face_count": 88, "faced": True},
        {"mesh_size": 301, "vertex_count": 87, "face_count": 85, "faced": True},
        {"mesh_size": 301, "vertex_count": 72, "face_count": 70, "faced": True},
        {"mesh_size": 301, "vertex_count": 72, "face_count": 70, "faced": True},
        {"mesh_size": 301, "vertex_count": 54, "face_count": 52, "faced": True},
        {"mesh_size": 301, "vertex_count": 9, "face_count": 7, "faced": True},
        {"mesh_size": 301, "vertex_count": 6, "face_count": 4, "faced": True},
    ]
    result = f7.detect_meshsize_family_lod(entries)
    assert len(result) == 1
    assert result[0]["mesh_size"] == 301
    assert result[0]["lod_score"] >= 0.7
    assert len(result[0]["levels"]) >= 3


def test_meshsize_family_below_threshold() -> None:
    """Only 2 entries with same vertex count — should be below threshold."""
    entries: list[dict[str, Any]] = [
        {"mesh_size": 999, "vertex_count": 50, "face_count": 48, "faced": True},
        {"mesh_size": 999, "vertex_count": 50, "face_count": 48, "faced": True},
    ]
    result = f7.detect_meshsize_family_lod(entries)
    assert result == []


# ── detect_descriptor_lod ─────────────────────────────────────


def test_descriptor_lod_empty() -> None:
    result = f7.detect_descriptor_lod([])
    assert result == []


def test_descriptor_lod_vec3_vec2_siblings() -> None:
    entries: list[dict[str, Any]] = [
        {
            "sibling_pair": {"mesh_size": 305},
            "descriptor": "float32xvec3 (position/normal/UV vertex data)",
            "vertex_count": 148,
            "asset_id": "aaaabbbbccccdddd",
        },
        {
            "sibling_pair": {"mesh_size": 305},
            "descriptor": "float32xvec2 (UV coordinates)",
            "vertex_count": 48,
            "asset_id": "eeeeffffgggghhhh",
        },
    ]
    result = f7.detect_descriptor_lod(entries)
    assert len(result) == 1
    assert "descriptor-sibling" in result[0]["lod_type"]


def test_descriptor_lod_no_descriptor_variety() -> None:
    entries: list[dict[str, Any]] = [
        {
            "sibling_pair": {"mesh_size": 305},
            "descriptor": "float32xvec3 (position/normal/UV vertex data)",
            "vertex_count": 148,
            "asset_id": "aaaabbbbccccdddd",
        },
        {
            "sibling_pair": {"mesh_size": 305},
            "descriptor": "float32xvec3 (position/normal/UV vertex data)",
            "vertex_count": 48,
            "asset_id": "eeeeffffgggghhhh",
        },
    ]
    result = f7.detect_descriptor_lod(entries)
    assert result == []


# ── build_lod_manifest ────────────────────────────────────────


def test_build_manifest_empty() -> None:
    manifest = f7.build_lod_manifest([], [], [], [])
    stats = manifest["stats"]
    assert stats["same_nif_lod_chains"] == 0
    assert stats["meshsize_family_lod_groups"] == 0
    assert stats["assets_with_lod_info"] == 0


def test_build_manifest_with_data() -> None:
    same_nif = [
        {
            "asset_id": "abcd1234abcd1234",
            "lod_type": "same-nif",
            "levels": 2,
            "entries": [
                {
                    "mesh_block": 6,
                    "vertex_count": 100,
                    "face_count": 98,
                    "faced": True,
                    "mesh_size": 300,
                    "descriptor": "float32xvec3",
                    "lod_level": 0,
                },
                {
                    "mesh_block": 107,
                    "vertex_count": 10,
                    "face_count": 8,
                    "faced": True,
                    "mesh_size": 300,
                    "descriptor": "float32xvec3",
                    "lod_level": 1,
                },
            ],
            "vertex_staircase": [100, 10],
            "reduction_ratio": 10.0,
        }
    ]
    families = [
        {
            "mesh_size": 301,
            "lod_type": "meshsize-family",
            "lod_score": 0.7,
            "signals": ["step staircase"],
            "total_meshes": 3,
            "faced_count": 3,
            "pos_only_count": 0,
            "levels": [
                {"vertex_count": 90, "lod_level": 0, "count": 1, "faced_count": 1, "asset_ids": ["xyz1"]},
                {"vertex_count": 6, "lod_level": 1, "count": 2, "faced_count": 2, "asset_ids": ["xyz2", "xyz3"]},
            ],
        }
    ]
    enriched: list[dict[str, Any]] = [
        {"asset_id": "abcd1234abcd1234"},
        {"asset_id": "xyz1"},
        {"asset_id": "xyz2"},
        {"asset_id": "xyz3"},
    ]
    manifest = f7.build_lod_manifest(same_nif, families, [], enriched)
    stats = manifest["stats"]
    assert stats["same_nif_lod_chains"] == 1
    assert stats["assets_with_lod_info"] == 4  # 1 same-nif + 3 family


def test_meshsize_family_with_duplicates() -> None:
    """Duplicate asset_ids within a level should be deduplicated."""
    entries: list[dict[str, Any]] = [
        {"mesh_size": 301, "vertex_count": 72, "face_count": 70, "faced": True, "asset_id": "dup1"},
        {"mesh_size": 301, "vertex_count": 72, "face_count": 70, "faced": True, "asset_id": "dup1"},
        {"mesh_size": 301, "vertex_count": 6, "face_count": 4, "faced": True, "asset_id": "dup2"},
        {"mesh_size": 301, "vertex_count": 6, "face_count": 4, "faced": True, "asset_id": "dup2"},
    ]
    result = f7.detect_meshsize_family_lod(entries)
    assert len(result) == 1
    for level in result[0]["levels"]:
        # Each level should have unique asset_ids
        assert len(level["asset_ids"]) == len(set(level["asset_ids"]))


def test_generate_report_contains_keywords() -> None:
    manifest = f7.build_lod_manifest([], [], [], [])
    report = f7.generate_report(manifest)
    assert "FT-7.2" in report
    assert "SAME-NIF LOD" in report
    assert "MESHSIZE-FAMILY" in report
    assert "SUMMARY" in report
