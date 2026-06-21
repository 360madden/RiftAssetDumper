"""Tests for ``scripts/semantic_surface.py`` (Cycle 5 surface) + scene-manifest / delivery integration.

Locks wire-format v0.9 (``build_scene_manifest.py``) + v0.3 (``build_riftflythrough_delivery.py``):

  * ``build_semantic_block(asset_id)`` returns ``{categories: [...], sources: {...}}``
  * Categories union across all 3 matrix files (hint:actor-object / hint:map-zone /
    hint:waypoint-poi); AssetIdPrefix is the join key, case-insensitive.
  * Scene manifest emits a ``semantic`` sub-record (always present) conforming
    to ``docs/schemas/scene-manifest-v1.schema.json``.
  * RiftFlythrough delivery entry surfaces a flat ``semantic_categories`` list.

Fixtures are pure-Python (no dotnet spawn).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_SURFACE_PATH = REPO_ROOT / "scripts" / "semantic_surface.py"
SCHEMA_PATH = REPO_ROOT / "docs" / "schemas" / "scene-manifest-v1.schema.json"


# --------------------------------------------------------------------------
# scripts.semantic_surface — loader module
# --------------------------------------------------------------------------


class TestHintsConstant(unittest.TestCase):
    """Lock the shipped hint set. Adding hints is a wire-format extension."""

    def test_hints_is_tuple_with_three_strings(self) -> None:
        from scripts.semantic_surface import HINTS

        self.assertIsInstance(HINTS, tuple)
        self.assertEqual(len(HINTS), 3)
        for h in HINTS:
            self.assertIsInstance(h, str)
            self.assertTrue(h.startswith("hint:"))

    def test_hints_contains_expected_categories(self) -> None:
        from scripts.semantic_surface import HINTS

        self.assertIn("hint:map-zone", HINTS)
        self.assertIn("hint:actor-object", HINTS)
        self.assertIn("hint:waypoint-poi", HINTS)


class TestLoadMatrixBehavior(unittest.TestCase):
    """Loader must degrade gracefully when matrix files are missing or malformed."""

    def test_load_matrix_missing_dir_returns_empty(self) -> None:
        from scripts.semantic_surface import load_matrix

        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(load_matrix("hint:map-zone", Path(td)), [])

    def test_load_matrix_malformed_json_returns_empty(self) -> None:
        from scripts.semantic_surface import load_matrix

        with tempfile.TemporaryDirectory() as td:
            matrix_dir = Path(td)
            (matrix_dir / "semantic-nif-actor-object.json").write_text("not json", encoding="utf-8")
            self.assertEqual(load_matrix("hint:actor-object", matrix_dir), [])

    def test_load_matrix_invalid_entries_shape_returns_empty(self) -> None:
        from scripts.semantic_surface import load_matrix

        with tempfile.TemporaryDirectory() as td:
            matrix_dir = Path(td)
            (matrix_dir / "semantic-nif-map-zone.json").write_text(
                json.dumps({"SchemaVersion": "asset-semantic-index/v1", "Entries": None}),
                encoding="utf-8",
            )
            self.assertEqual(load_matrix("hint:map-zone", matrix_dir), [])

    def test_load_matrix_unknown_hint_raises_value_error(self) -> None:
        from scripts.semantic_surface import load_matrix

        with self.assertRaises(ValueError):
            load_matrix("hint:not-a-real-thing")


class TestCategorizeAsset(unittest.TestCase):
    """Asset categorizer unions per-matrix hits by 16-char hex AssetIdPrefix."""

    def _seed_matrix_dir(self, td: str) -> Path:
        matrix_dir = Path(td)
        # hint:actor-object has asset 2AB83956F1E50A8F (uppercase check).
        # hint:map-zone has asset 0928F21CE4B7AE64 (alt case for ord).
        # Waypoint-poi empty.
        (matrix_dir / "semantic-nif-actor-object.json").write_text(
            json.dumps(
                {
                    "SchemaVersion": "asset-semantic-index/v1",
                    "Entries": [
                        {
                            "ArchiveName": "a.twad",
                            "AssetIdPrefix": "2AB83956F1E50A8F",
                            "EntryIndex": 0,
                            "SemanticCategories": ["asset:model", "hint:actor-object"],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (matrix_dir / "semantic-nif-map-zone.json").write_text(
            json.dumps(
                {
                    "SchemaVersion": "asset-semantic-index/v1",
                    "Entries": [
                        {
                            "ArchiveName": "b.twad",
                            "AssetIdPrefix": "0928f21ce4b7ae64",
                            "EntryIndex": 1,
                            "SemanticCategories": ["asset:model", "hint:map-zone"],
                        },
                        {
                            "ArchiveName": "c.twad",
                            "AssetIdPrefix": "2ab83956f1e50a8f",  # also hits actor
                            "EntryIndex": 2,
                            "SemanticCategories": ["asset:model", "hint:map-zone"],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (matrix_dir / "semantic-nif-waypoint-poi.json").write_text(
            json.dumps(
                {
                    "SchemaVersion": "asset-semantic-index/v1",
                    "Entries": [],
                }
            ),
            encoding="utf-8",
        )
        return matrix_dir

    def test_categorize_asset_single_hint_match(self) -> None:
        from scripts.semantic_surface import categorize_asset, load_all_matrices

        with tempfile.TemporaryDirectory() as td:
            matrices = load_all_matrices(self._seed_matrix_dir(td))
            self.assertEqual(
                categorize_asset("0928F21CE4B7AE64", matrices),
                ["hint:map-zone"],
            )

    def test_categorize_asset_multiple_hints_preserves_hints_order(self) -> None:
        from scripts.semantic_surface import categorize_asset, load_all_matrices

        with tempfile.TemporaryDirectory() as td:
            matrices = load_all_matrices(self._seed_matrix_dir(td))
            # The asset 2ab83956f1e50a8f appears in BOTH actor-object and map-zone matrices.
            result = categorize_asset("2ab83956f1e50a8f", matrices)
            self.assertEqual(set(result), {"hint:actor-object", "hint:map-zone"})
            # Order must match the HINTS tuple (canonical order, not file load order).
            from scripts.semantic_surface import HINTS

            self.assertEqual(result, [h for h in HINTS if h in result])

    def test_categorize_asset_no_match_returns_empty_list(self) -> None:
        from scripts.semantic_surface import categorize_asset, load_all_matrices

        with tempfile.TemporaryDirectory() as td:
            matrices = load_all_matrices(self._seed_matrix_dir(td))
            self.assertEqual(categorize_asset("ffffffffffffffff", matrices), [])

    def test_categorize_asset_empty_id_returns_empty(self) -> None:
        from scripts.semantic_surface import categorize_asset

        self.assertEqual(categorize_asset(""), [])

    def test_categorize_asset_default_loads_from_disk(self) -> None:
        """When called without the ``matrices`` kwarg, the loader reads from disk."""
        from scripts.semantic_surface import DEFAULT_MATRIX_DIR, categorize_asset

        # No assertions about real data; just verify the function signature
        # delegates to load_all_matrices() and returns a list.
        result = categorize_asset("ffffffffffffffff")
        self.assertIsInstance(result, list)
        # The default matrix dir is gitignored on a fresh clone; loader
        # degrades to [] either way.  We don't strictly compare to DEFAULT_MATRIX_DIR
        # here because it's a Path used at import-time.
        self.assertTrue(str(DEFAULT_MATRIX_DIR).endswith("nif-semantic-hints"))


class TestBuildSemanticBlockContract(unittest.TestCase):
    """``build_semantic_block`` is the scene-manifest injection point."""

    def test_block_shape_with_no_matrix_dir(self) -> None:
        """Empty when matrix_dir does not exist; sources map still surfaced (all ABSENT_MARKER)."""
        from scripts.semantic_surface import ABSENT_MARKER, HINTS, build_semantic_block

        with tempfile.TemporaryDirectory() as td:
            block = build_semantic_block("ffffffffffffffff", Path(td))
            self.assertEqual(set(block.keys()), {"categories", "sources"})
            self.assertEqual(block["categories"], [])
            self.assertEqual(set(block["sources"].keys()), set(HINTS))
            for hint in HINTS:
                self.assertEqual(block["sources"][hint], ABSENT_MARKER)

    def test_block_shape_with_partial_matrices(self) -> None:
        """categories lists assets that appear in any matrix; sources map shows basenames.

        Contract: ABSENT_MARKER is reserved for paths that DO NOT exist on disk.
        An existing-but-empty matrix file still emits its basename (so consumers
        can tell "scanned but no hits" apart from "not scanned at all").
        """
        from scripts.semantic_surface import build_semantic_block

        with tempfile.TemporaryDirectory() as td:
            matrix_dir = Path(td)
            (matrix_dir / "semantic-nif-actor-object.json").write_text(
                json.dumps(
                    {
                        "Entries": [
                            {
                                "ArchiveName": "a.twad",
                                "AssetIdPrefix": "abc1234567890abc",
                                "EntryIndex": 0,
                                "SemanticCategories": ["hint:actor-object"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (matrix_dir / "semantic-nif-map-zone.json").write_text(
                json.dumps({"Entries": []}), encoding="utf-8"
            )
            (matrix_dir / "semantic-nif-waypoint-poi.json").write_text(
                json.dumps({"Entries": []}), encoding="utf-8"
            )
            block = build_semantic_block("abc1234567890abc", matrix_dir)
            self.assertEqual(block["categories"], ["hint:actor-object"])
            # Source paths are basenames (filename only) so manifests stay
            # portable; the strings are unambiguous because one file maps to
            # each hint slot.
            self.assertEqual(
                block["sources"]["hint:actor-object"], "semantic-nif-actor-object.json"
            )
            # Empty-but-existing files still emit their basename (NOT ABSENT_MARKER).
            self.assertEqual(block["sources"]["hint:map-zone"], "semantic-nif-map-zone.json")
            self.assertEqual(block["sources"]["hint:waypoint-poi"], "semantic-nif-waypoint-poi.json")


# --------------------------------------------------------------------------
# Scene-manifest integration (v0.9 wire format)
# --------------------------------------------------------------------------


class TestSceneManifestSemanticInjection(unittest.TestCase):
    """``build_manifest`` injects the ``semantic`` sub-record."""

    def test_semantic_field_always_present(self) -> None:
        """Even with no matrix data available, the field is emitted (empty contract)."""
        from scripts.semantic_surface import build_semantic_block

        block = build_semantic_block("ffffffffffffffff")
        self.assertIn("categories", block)
        self.assertIn("sources", block)
        self.assertIsInstance(block["categories"], list)
        self.assertIsInstance(block["sources"], dict)

    def test_semantic_field_conforms_to_schema(self) -> None:
        """Validates the populated block against docs/schemas/scene-manifest-v1.schema.json."""
        from jsonschema import Draft202012Validator

        from scripts.semantic_surface import build_semantic_block

        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))
        semantic_def = schema["$defs"]["Semantic"]

        # Build a synthetic block via the public loader, with a known
        # matrix populated for one hint.
        with tempfile.TemporaryDirectory() as td:
            matrix_dir = Path(td)
            (matrix_dir / "semantic-nif-map-zone.json").write_text(
                json.dumps(
                    {
                        "Entries": [
                            {
                                "ArchiveName": "a.twad",
                                "AssetIdPrefix": "abc1234567890abc",
                                "EntryIndex": 0,
                                "SemanticCategories": ["hint:map-zone"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            block = build_semantic_block("abc1234567890abc", matrix_dir)
            validator = Draft202012Validator(semantic_def)
            errors = list(validator.iter_errors(block))
            self.assertEqual(errors, [], f"semantic sub-record non-conforming: {[e.message for e in errors]}")
            # The block must also satisfy the empty case against the same schema.
            empty_block = build_semantic_block("ffffffffffffffff", matrix_dir)
            empty_errors = list(validator.iter_errors(empty_block))
            self.assertEqual(empty_errors, [], f"empty semantic block non-conforming: {[e.message for e in empty_errors]}")


# --------------------------------------------------------------------------
# RiftFlythrough delivery integration (v0.3 wire format)
# --------------------------------------------------------------------------


class TestDeliverySemanticCategories(unittest.TestCase):
    """``build_delivery_entry`` surfaces ``semantic_categories`` from the scene manifest."""

    def _minimal_manifest(self, semantic: Any) -> dict[str, Any]:
        return {
            "SchemaVersion": "scene-manifest/v1",
            "asset_id": "abc1234567890abc",
            "geometry": {
                "obj_path": "/tmp/abc1234567890abc.obj",
                "mesh_block": "M#7",
                "mesh_size": 305,
                "vertex_count": 100,
                "face_count": 50,
                "has_faces": True,
                "render_class": "faced",
                "obj_sha1": "0" * 40,
            },
            "world": {
                "world_transform_summary": {
                    "translation": [0.0, 0.0, 0.0],
                    "rotation": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
                    "scale": 1.0,
                },
                "world_transform_identity": True,
            },
            "textures": {
                "source": "flythrough",
                "linked_texture_count": 0,
                "linked_textures": [],
            },
            "semantic": semantic,
        }

    def test_delivery_entry_includes_semantic_categories_from_manifest(self) -> None:
        from scripts.build_riftflythrough_delivery import build_delivery_entry

        manifest = self._minimal_manifest({"categories": ["hint:map-zone", "hint:actor-object"], "sources": {}})
        entry = build_delivery_entry(manifest, converted_index={})
        self.assertEqual(entry["semantic_categories"], ["hint:map-zone", "hint:actor-object"])

    def test_delivery_entry_handles_missing_semantic_block(self) -> None:
        """Old manifests pre-dating Cycle 5 omit semantic; consumer should see []."""
        from scripts.build_riftflythrough_delivery import build_delivery_entry

        manifest = self._minimal_manifest(None)  # no semantic key
        entry = build_delivery_entry(manifest, converted_index={})
        self.assertEqual(entry["semantic_categories"], [])

    def test_delivery_entry_handles_empty_semantic_categories(self) -> None:
        from scripts.build_riftflythrough_delivery import build_delivery_entry

        manifest = self._minimal_manifest({"categories": [], "sources": {}})
        entry = build_delivery_entry(manifest, converted_index={})
        self.assertEqual(entry["semantic_categories"], [])

    def test_build_stats_counts_tagged_assets_and_distinct_hints(self) -> None:
        from scripts.build_riftflythrough_delivery import build_stats

        entries = [
            {
                "asset_id": "a" * 16,
                "vertex_count": 10,
                "face_count": 5,
                "linked_texture_count": 0,
                "linked_texture_url_count": 0,
                "mesh_size": 305,
                "render_class": "faced",
                "transform_identity": True,
                "semantic_categories": ["hint:map-zone"],
            },
            {
                "asset_id": "b" * 16,
                "vertex_count": 20,
                "face_count": 10,
                "linked_texture_count": 1,
                "linked_texture_url_count": 1,
                "mesh_size": 305,
                "render_class": "faced",
                "transform_identity": True,
                "semantic_categories": ["hint:actor-object"],
            },
            {
                "asset_id": "c" * 16,
                "vertex_count": 0,
                "face_count": 0,
                "linked_texture_count": 0,
                "linked_texture_url_count": 0,
                "mesh_size": None,
                "render_class": "point-only",
                "transform_identity": True,
                "semantic_categories": [],
            },
        ]
        stats = build_stats(entries)
        self.assertEqual(stats["tagged_assets"], 2)
        self.assertEqual(stats["distinct_hints"], 2)
        self.assertEqual(stats["hint_distribution"], {"hint:map-zone": 1, "hint:actor-object": 1})


if __name__ == "__main__":
    unittest.main()
