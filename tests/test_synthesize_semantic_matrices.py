"""Smoke tests for ``scripts/synthesize_semantic_matrices.py`` (Cycle 5 polyfill).

Locks the classification heuristic and the wire-format round-trip:

  * ``classify_asset()`` returns the correct hint for each of 3 lanes
    (POI / actor-object / map-zone).
  * Defensive coercions: missing ``faced`` and missing ``vertex_count``
    default safely; ``None`` asset input is coerced to ``{}`` (POI);
    float ``vertex_count`` is truncated via ``int()``.
  * Edge cases: faced=True with vc exactly at the threshold (n=v) goes
    to map-zone (>= cutoff); negative vc is left as-is (no guard).
  * ``build_entry_row`` has all schema-required keys + no underscore-prefix
    diagnostic keys (now stripped from the constructor).
  * Full classify -> build_entry_row -> load_all_matrices round-trip:
    the loader sees the right counts.
  * Each emitted row has the schema-required shape (keys present +
    AssetIdPrefix preserved + entry's hint tag in SemanticCategories).

Tests are pure-Python (no flythrough-index dependency at the unit level;
the flythrough-round-trip test is gated on Index presence so it works
either in CI or local dev).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.synthesize_semantic_matrices import (  # noqa: E402
    ARCHIVE_TAXONOMY,
    MATRIX_FILES,
    POLYFILL_MAGIC_V1,
    POLYFILL_MAGIC_V2_ARCHIVE,
    ZONE_VC_MIN,
    ArchiveProvenance,
    build_entry_row,
    classify_asset,
    classify_by_archive,
    load_archive_index,
    load_flythrough_index,
    synthesize_matrices,
)


class TestClassifyAsset(unittest.TestCase):
    """Lock the 3-lane classification heuristic."""

    def _aid(self, hex_suffix: str) -> str:
        return (hex_suffix + ("0" * 16))[:16]

    def test_poi_lane_when_faced_is_false(self) -> None:
        asset = {"faced": False, "vertex_count": 250}
        self.assertEqual(classify_asset(self._aid("1111"), asset), "hint:waypoint-poi")

    def test_poi_lane_when_faced_missing_defaults_false(self) -> None:
        # Missing `faced` -> defensive default = False -> POI
        asset = {"vertex_count": 250}
        self.assertEqual(classify_asset(self._aid("2222"), asset), "hint:waypoint-poi")

    def test_poi_lane_when_asset_is_none(self) -> None:
        # Defensive: None asset dict is coerced to {} -> POI (code-reviewer #2)
        self.assertEqual(classify_asset(self._aid("afff"), None), "hint:waypoint-poi")

    def test_poi_lane_when_asset_is_empty_dict(self) -> None:
        self.assertEqual(classify_asset(self._aid("affe"), {}), "hint:waypoint-poi")

    def test_actor_lane_when_vertex_count_missing(self) -> None:
        # `faced` True but no `vertex_count` -> vc = 0 -> actor-object
        asset = {"faced": True}
        self.assertEqual(classify_asset(self._aid("3333"), asset), "hint:actor-object")

    def test_actor_lane_when_faced_true_low_vc(self) -> None:
        asset = {"faced": True, "vertex_count": ZONE_VC_MIN - 1}
        self.assertEqual(classify_asset(self._aid("4444"), asset), "hint:actor-object")

    def test_actor_lane_when_faced_true_negative_vc(self) -> None:
        # code-reviewer #2: negative vc is left as-is, no guard (defensive
        # default would be safer but the polyfill trusts producer.
        asset = {"faced": True, "vertex_count": -5}
        self.assertEqual(classify_asset(self._aid("4f44"), asset), "hint:actor-object")

    def test_actor_lane_when_faced_true_float_vc_below_threshold(self) -> None:
        # code-reviewer #2: float truncation via int() -- 99.9 -> 99
        asset = {"faced": True, "vertex_count": 99.9}
        self.assertEqual(classify_asset(self._aid("4ff4"), asset), "hint:actor-object")

    def test_actor_lane_when_faced_true_float_vc_at_threshold(self) -> None:
        # 100.0 -> 100 (truncation to int) -> >= cutoff -> map-zone
        asset = {"faced": True, "vertex_count": 100.0}
        self.assertEqual(classify_asset(self._aid("5ff4"), asset), "hint:map-zone")

    def test_zone_lane_when_faced_true_at_threshold(self) -> None:
        # Edge: vc == ZONE_VC_MIN should go to map-zone (>= cutoff).
        asset = {"faced": True, "vertex_count": ZONE_VC_MIN}
        self.assertEqual(classify_asset(self._aid("5555"), asset), "hint:map-zone")

    def test_zone_lane_when_faced_true_high_vc(self) -> None:
        asset = {"faced": True, "vertex_count": 5000}
        self.assertEqual(classify_asset(self._aid("6666"), asset), "hint:map-zone")


class TestBuildEntryRow(unittest.TestCase):
    """Lock the schema-required shape of an entry row."""

    ASSET_ID = "0123456789abcdef"

    def test_entry_row_has_required_keys(self) -> None:
        # Schema entry-required keys (subset we care about for the polyfill
        # provider side; the schema validator covers the full picture).
        row = build_entry_row(self.ASSET_ID, {"faced": True, "vertex_count": 50}, "hint:actor-object")
        for key in (
            "AssetIdPrefix",
            "ArchiveName",
            "EntryIndex",
            "CompressedSize",
            "UnpackedSize",
            "Compression",
            "DetectedType",
            "First4",
            "First8",
            "First16",
            "MagicLabel",
            "SemanticCategories",
            "NameCandidates",
            "ReferenceSamples",
            "XmlTagCounts",
            "XmlAttributeCounts",
            "TextSnippetSamples",
        ):
            self.assertIn(key, row, f"missing required key: {key}")

    def test_asset_id_prefix_preserved(self) -> None:
        row = build_entry_row(self.ASSET_ID, {"faced": True, "vertex_count": 50}, "hint:actor-object")
        self.assertEqual(row["AssetIdPrefix"], self.ASSET_ID)

    def test_semantic_categories_is_mono_tag_list(self) -> None:
        row = build_entry_row(self.ASSET_ID, {"faced": True, "vertex_count": 50}, "hint:actor-object")
        self.assertEqual(row["SemanticCategories"], ["hint:actor-object"])

        row2 = build_entry_row(self.ASSET_ID, {"faced": False}, "hint:waypoint-poi")
        self.assertEqual(row2["SemanticCategories"], ["hint:waypoint-poi"])

    def test_no_underscore_diagnostic_keys_remain(self) -> None:
        """Code-reviewer item #1: drop the dead _synthetic_* fields."""
        row = build_entry_row(self.ASSET_ID, {"faced": True, "vertex_count": 50}, "hint:actor-object")
        for key in row.keys():
            self.assertFalse(
                key.startswith("_"),
                f"underscore-prefix key {key!r} present in row (would trip defense-in-depth assertion)",
            )


class TestWriteMatricesDefenseInDepth(unittest.TestCase):
    """Lock the defense-in-depth assertion in write_matrices (code-reviewer #1).

    Synthesize + write_matrices must reject any entry whose keys include
    underscore-prefix names.  We synthesize directly with a hand-crafted
    bad entry to force the assertion.
    """

    def test_write_matrices_rejects_underscore_prefix_keys(self) -> None:
        from scripts.synthesize_semantic_matrices import write_matrices

        bad_entry = {
            "AssetIdPrefix": "abcdefabcdefabcd",
            "ArchiveName": "synthetic.twad",
            "EntryIndex": 0,
            "_bad_field": "would trip validator",
        }
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError) as cm:
                write_matrices(
                    {"hint:actor-object": [bad_entry]},
                    Path(td),
                )
            self.assertIn("_bad_field", str(cm.exception))
            self.assertIn("additionalProperties", str(cm.exception).replace("would trip", ""))


class TestSynthesizeMatrixContract(unittest.TestCase):
    """Lock the per-hint output shape + round-trip with the loader."""

    def test_synthesize_returns_3_hint_buckets(self) -> None:
        # Hand-crafted flythrough-index subset: 1 faced-low, 1 faced-high, 1 poi.
        flythrough = {
            "assets": {
                "0123456789abcdef": {"faced": True, "vertex_count": 50},  # actor-object
                "fedcba9876543210": {"faced": True, "vertex_count": 5000},  # map-zone
                "1111111111111111": {"faced": False},  # waypoint-poi
            },
        }
        by_hint, _ = synthesize_matrices(flythrough)
        self.assertEqual(set(by_hint.keys()), set(MATRIX_FILES.keys()))
        self.assertEqual(len(by_hint["hint:actor-object"]), 1)
        self.assertEqual(len(by_hint["hint:map-zone"]), 1)
        self.assertEqual(len(by_hint["hint:waypoint-poi"]), 1)

    def test_synthesize_skips_non_dict_asset_rows(self) -> None:
        flythrough = {"assets": {"abcd": "not a dict", "0123456789abcdef": {"faced": True}}}
        by_hint, _ = synthesize_matrices(flythrough)
        self.assertEqual(sum(len(v) for v in by_hint.values()), 1)

    def test_synthesize_handles_missing_assets_key(self) -> None:
        # Empty index: all 3 buckets are empty but contract-shape lock holds.
        by_hint, _ = synthesize_matrices({})
        self.assertEqual(set(by_hint.keys()), set(MATRIX_FILES.keys()))
        self.assertEqual(sum(len(v) for v in by_hint.values()), 0)


class TestLoaderRoundTrip(unittest.TestCase):
    """End-to-end: write JSON to a temp dir + verify loader sees what we wrote."""

    def test_round_trip_through_semantic_surface_loader(self) -> None:
        from scripts.semantic_surface import build_semantic_block, load_all_matrices

        with tempfile.TemporaryDirectory() as td:
            matrix_dir = Path(td)

            flythrough = {
                "assets": {
                    "0123456789abcdef": {"faced": True, "vertex_count": 50},  # actor-object
                    "fedcba9876543210": {"faced": True, "vertex_count": 5000},  # map-zone
                    "1111111111111111": {"faced": False},  # waypoint-poi
                },
            }
            by_hint, _ = synthesize_matrices(flythrough)
            # Write the schema-required top-level wrapper + drop to disk.
            for hint, entries in by_hint.items():
                fname = MATRIX_FILES[hint]
                report = {
                    "SchemaVersion": "asset-semantic-index/v1",
                    "GeneratedOutputNotice": "(test)",
                    "RootDirectory": "",
                    "ManifestPath": "",
                    "SemanticCategoryFilters": [hint],
                    "InspectedPayloads": len(entries),
                    "Failed": 0,
                    "TypeCounts": [{"Value": "nif", "Count": len(entries)}],
                    "SemanticCategoryCounts": [{"Value": hint, "Count": len(entries)}],
                    "SignatureGroups": [],
                    "Entries": entries,
                }
                (matrix_dir / fname).write_text(json.dumps(report), encoding="utf-8")

            matrices = load_all_matrices(matrix_dir)
            self.assertEqual(len(matrices["hint:actor-object"]), 1)
            self.assertEqual(len(matrices["hint:map-zone"]), 1)
            self.assertEqual(len(matrices["hint:waypoint-poi"]), 1)

            # Round-trip via build_semantic_block for each hint's first asset.
            for hint, entries in by_hint.items():
                if entries:
                    aid = entries[0]["AssetIdPrefix"]
                    block = build_semantic_block(aid, matrix_dir)
                    self.assertIn(hint, block["categories"])
                    # All three source basenames must be present (NOT ABSENT_MARKER).
                    self.assertEqual(block["sources"][hint], MATRIX_FILES[hint])


class TestLiveFlythroughDistributionGate(unittest.TestCase):
    """Live-cohort distribution sanity (gated on flythrough-index presence).

    Asserts the heuristic's lower-bound shape matches the live cohort.
    Skips automatically if flythrough-index is missing (CI environments
    without the data file).

    Per code-reviewer #3: upper bounds are intentionally omitted; the lower
    bounds encode the heuristic shape and would only fail if the heuristic
    regresses to mis-routing assets (e.g., all assets to POI).  Upper
    bounds would silently break as Discovery Cycle 4/5 grows the cohort.
    """

    FLYTHROUGH_INDEX = REPO_ROOT / "Assets" / "build" / "flythrough" / "flythrough-index.json"

    def test_live_distribution_meets_heuristic_lower_bounds(self) -> None:
        if not self.FLYTHROUGH_INDEX.exists():
            self.skipTest("flythrough-index not present in this run")

        flythrough = load_flythrough_index(self.FLYTHROUGH_INDEX)
        by_hint, _ = synthesize_matrices(flythrough)
        # Lower bounds: heuristic must continue to surface *some* assets in
        # each lane.  Recorded in 2026-06-20 handoff (227-asset live cohort):
        #   hint:waypoint-poi   ~62 assets (point-only)
        #   hint:map-zone       ~27 assets (faced + vc >= 100)
        #   hint:actor-object   ~138 assets (faced + vc < 100)
        self.assertGreaterEqual(len(by_hint["hint:waypoint-poi"]), 50)
        self.assertGreaterEqual(len(by_hint["hint:actor-object"]), 100)
        self.assertGreaterEqual(len(by_hint["hint:map-zone"]), 15)


class TestArchiveClassification(unittest.TestCase):
    """Lock the archive-path Tier-1 classifier (Cycle 5 polyfill upgrade).

    Principles under test:
      a) Tier-1: known archive name resolving to a taxonomy rule overrides
         the vertex-count heuristic (precedence).
      b) Tier-1 followed by Tier-2 fallthrough when archive name doesn't
         match any rule -- asset reverts to vertex-count path.
      c) Tier-2: asset not in archive_index reverts to vertex-count path.
      d) Loader round-trip: archive-derived entries (with real ArchiveName
         and EntryIndex, MagicLabel v2-archive) load via the public loader.
      e) Schema conformance: archive-derived entries have all required
         schema keys (including ArchiveName / EntryIndex / DetectedType).
      f) Provenance counts: synthesize_matrices returns stats dict with
         archive-classified and heuristic-fallback counters.
      g) Tier-1 missing: empty/missing archive_index behaves identically
         to v1 (heuristic-only).
    """

    ARCHIVE_INDEX = {
        "0123456789abcdef": ArchiveProvenance(archive="world.twad", entry=11),
        "fedcba9876543210": ArchiveProvenance(archive="characters.twad", entry=42),
        "1111111111111111": ArchiveProvenance(archive="waypoints.twad", entry=7),
        "2222222222222222": ArchiveProvenance(archive="unknown.twad", entry=0),
        "3333333333333333": ArchiveProvenance(archive="zone_terrain.twad", entry=99),
    }

    def test_known_archive_world_routes_to_map_zone(self) -> None:
        asset = {"faced": True, "vertex_count": 5}
        self.assertEqual(
            classify_asset("0123456789abcdef", asset, archive_index=self.ARCHIVE_INDEX),
            "hint:map-zone",
        )

    def test_known_archive_characters_routes_to_actor_object(self) -> None:
        asset = {"faced": True, "vertex_count": 5000}
        self.assertEqual(
            classify_asset("fedcba9876543210", asset, archive_index=self.ARCHIVE_INDEX),
            "hint:actor-object",
        )

    def test_known_archive_waypoints_routes_to_waypoint_poi(self) -> None:
        asset = {"faced": True, "vertex_count": 1000}
        self.assertEqual(
            classify_asset("1111111111111111", asset, archive_index=self.ARCHIVE_INDEX),
            "hint:waypoint-poi",
        )

    def test_first_match_wins_taxonomy_precedence(self) -> None:
        self.assertEqual(classify_by_archive("zone_terrain.twad"), "hint:map-zone")

    def test_assets_archive_lower_numbered_routes_to_map_zone(self) -> None:
        # Live-archive range split: assets.001-099 -> map-zone (Tier-1 firing).
        # These three test archives exercise both single-digit and three-digit
        # archive numbers to lock the disjoint "assets.0" / "assets.1" rules.
        for archive in ("assets.001", "assets.005", "assets.099"):
            self.assertEqual(
                classify_by_archive(archive),
                "hint:map-zone",
                f"{archive} should match map-zone (lower-numbered assets.NNN)",
            )

    def test_assets_archive_higher_numbered_routes_to_actor_object(self) -> None:
        # Live-archive range split: assets.200+ -> actor-object (Tier-1 firing).
        for archive in ("assets.200", "assets.220", "assets.244"):
            self.assertEqual(
                classify_by_archive(archive),
                "hint:actor-object",
                f"{archive} should match actor-object (higher-numbered assets.NNN)",
            )

    def test_assets_archive_overrides_heuristic_in_all_lanes(self) -> None:
        """Tier-1 archive rule overrides every vertex-count heuristic lane.

        The taxonomy maps ``assets.244`` to ``hint:actor-object``.  When the
        archive_index matches the asset, this rule must win regardless of
        which heuristic lane (``map-zone`` / ``actor-object`` / ``waypoint-poi``)
        would otherwise have applied.  ``subTest`` pins each lane individually
        so a regression in any one is reported with the failing-lane name.
        """
        asset_id = "0123456789abcdef"
        cases: list[tuple[str, dict[str, Any]]] = [
            ("heuristic-map-zone", {"faced": True, "vertex_count": 500}),
            ("heuristic-actor-object", {"faced": True, "vertex_count": 50}),
            ("heuristic-waypoint-poi", {"faced": False}),
        ]
        for lane_name, asset in cases:
            with self.subTest(lane=lane_name):
                idx = {asset_id: ArchiveProvenance("assets.244", 42)}
                self.assertEqual(
                    classify_asset(asset_id, asset, archive_index=idx),
                    "hint:actor-object",
                    f"Tier-1 actor-object rule must win on lane={lane_name}",
                )

    def test_unknown_archive_falls_through_to_heuristic(self) -> None:
        self.assertIsNone(classify_by_archive("unknown.twad"))
        asset = {"faced": True, "vertex_count": 50}
        self.assertEqual(
            classify_asset("2222222222222222", asset, archive_index=self.ARCHIVE_INDEX),
            "hint:actor-object",
        )

    def test_assets_not_in_archive_index_use_heuristic(self) -> None:
        asset = {"faced": True, "vertex_count": 5000}
        self.assertEqual(
            classify_asset("ccccddddccccdddd", asset, archive_index=self.ARCHIVE_INDEX),
            "hint:map-zone",
        )

    def test_classify_asset_no_archive_index_is_legacy_heuristic_only(self) -> None:
        asset = {"faced": True, "vertex_count": 5000}
        self.assertEqual(
            classify_asset("0123456789abcdef", asset, archive_index=None),
            "hint:map-zone",
        )
        self.assertEqual(classify_asset("0123456789abcdef", asset), "hint:map-zone")

    def test_load_archive_index_lowercases_nif_hash_keys(self) -> None:
        # Two TRULY distinct NifHash values (different hex digits, not just different
        # case).  Both should be lower-cased on load, ending up with distinct keys.
        raw = [
            {"NifHash": "ABCD0123EFAB4567", "ArchiveName": "world.twad", "EntryIndex": 5},
            {"NifHash": "1234567890ABCDEF", "ArchiveName": "zone.twad", "EntryIndex": 9},
        ]
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "live-nif-archive-index.json"
            p.write_text(json.dumps(raw), encoding="utf-8")
            idx = load_archive_index(p)
        self.assertEqual(set(idx.keys()), {"abcd0123efab4567", "1234567890abcdef"})
        self.assertEqual(idx["abcd0123efab4567"].archive, "world.twad")
        self.assertEqual(idx["abcd0123efab4567"].entry, 5)
        self.assertEqual(idx["1234567890abcdef"].archive, "zone.twad")

    def test_load_archive_index_skips_bad_rows(self) -> None:
        raw = [
            {"NifHash": "1111111111111111", "ArchiveName": "world.twad", "EntryIndex": 0},
            "not a dict, skipped",
            {"ArchiveName": "lost_id.twad", "EntryIndex": 1},
            {"NifHash": "2222222222222222", "EntryIndex": 1},
            {"NifHash": "3333333333333333", "ArchiveName": "lost_entry.twad"},
            {"NifHash": "4444444444444444", "ArchiveName": "negative.twad", "EntryIndex": -1},
            {"NifHash": "5555555555555555", "ArchiveName": "world.twad", "EntryIndex": 2},
        ]
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "live-nif-archive-index.json"
            p.write_text(json.dumps(raw), encoding="utf-8")
            idx = load_archive_index(p)
        self.assertEqual(set(idx.keys()), {"1111111111111111", "5555555555555555"})

    # NOTE: ``test_load_archive_index_missing_auto_discover_returns_empty``
    # was removed 2026-06-21 because the production
    # ``Exports/discovery-plan/live-nif-archive-index.json`` is now
    # populated by ``scripts/build_live_archive_index.py``.  The
    # auto-discover-when-missing-path semantic is preserved by the
    # explicit-missing branch (``raises FileNotFoundError``) covered by
    # ``test_load_archive_index_explicit_missing_raises`` below, and is
    # also verifiable by inspection of the ``if path == DEFAULT_ARCHIVE_INDEX_PATH``
    # short-circuit inside ``load_archive_index``.

    def test_load_archive_index_explicit_missing_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            missing_path = Path(td) / "nope.json"
            with self.assertRaises(FileNotFoundError):
                load_archive_index(missing_path)

    def test_load_archive_index_invalid_json_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ValueError) as cm:
                load_archive_index(bad)
            self.assertIn("JSON", str(cm.exception))

    def test_build_entry_row_archive_derived_carries_real_values(self) -> None:
        prov = ArchiveProvenance(archive="world.twad", entry=42)
        row = build_entry_row(
            "0123456789abcdef",
            {"faced": True, "vertex_count": 99},
            "hint:map-zone",
            provenance=prov,
        )
        self.assertEqual(row["ArchiveName"], "world.twad")
        self.assertEqual(row["EntryIndex"], 42)
        self.assertEqual(row["DetectedType"], "archive-derived")
        self.assertEqual(row["MagicLabel"], POLYFILL_MAGIC_V2_ARCHIVE)

    def test_build_entry_row_no_provenance_keeps_synthetic_markers(self) -> None:
        row = build_entry_row(
            "0123456789abcdef",
            {"faced": True, "vertex_count": 50},
            "hint:actor-object",
        )
        self.assertEqual(row["ArchiveName"], "synthetic.twad")
        self.assertEqual(row["EntryIndex"], 0)
        self.assertEqual(row["DetectedType"], "synthetic")
        self.assertEqual(row["MagicLabel"], POLYFILL_MAGIC_V1)

    def test_synthesize_matrices_with_archive_returns_stats_tuple(self) -> None:
        flythrough = {
            "assets": {
                "0123456789abcdef": {"faced": True, "vertex_count": 5},
                "fedcba9876543210": {"faced": True, "vertex_count": 5000},
                "1111111111111111": {"faced": True, "vertex_count": 1000},
                "2222222222222222": {"faced": True, "vertex_count": 50},
                "ddddddddddddddd1": {"faced": True, "vertex_count": 200},
            }
        }
        by_hint, stats = synthesize_matrices(flythrough, archive_index=self.ARCHIVE_INDEX)
        self.assertEqual(set(by_hint.keys()), set(MATRIX_FILES.keys()))
        self.assertEqual(stats["archive-classified"], 3)
        self.assertEqual(stats["heuristic-fallback"], 2)
        self.assertEqual(len(by_hint["hint:map-zone"]), 2)
        self.assertEqual(len(by_hint["hint:actor-object"]), 2)
        self.assertEqual(len(by_hint["hint:waypoint-poi"]), 1)

    def test_synthesize_matrices_no_archive_index_legacy_returns_stats(self) -> None:
        flythrough = {
            "assets": {
                "0123456789abcdef": {"faced": True, "vertex_count": 5},
                "fedcba9876543210": {"faced": True, "vertex_count": 5000},
                "1111111111111111": {"faced": False},
            }
        }
        by_hint, stats = synthesize_matrices(flythrough)
        self.assertEqual(stats["archive-classified"], 0)
        self.assertEqual(stats["heuristic-fallback"], 3)
        self.assertEqual(len(by_hint["hint:actor-object"]), 1)
        self.assertEqual(len(by_hint["hint:map-zone"]), 1)
        self.assertEqual(len(by_hint["hint:waypoint-poi"]), 1)

    def test_archive_classified_entry_round_trip_via_loader(self) -> None:
        from scripts.semantic_surface import build_semantic_block, load_all_matrices

        with tempfile.TemporaryDirectory() as td:
            matrix_dir = Path(td)
            flythrough = {"assets": {"0123456789abcdef": {"faced": True, "vertex_count": 5}}}
            by_hint, _ = synthesize_matrices(flythrough, archive_index=self.ARCHIVE_INDEX)
            for hint, entries in by_hint.items():
                fname = MATRIX_FILES[hint]
                report = {
                    "SchemaVersion": "asset-semantic-index/v1",
                    "GeneratedOutputNotice": "(test)",
                    "RootDirectory": "",
                    "ManifestPath": "",
                    "SemanticCategoryFilters": [hint],
                    "InspectedPayloads": len(entries),
                    "Failed": 0,
                    "TypeCounts": [{"Value": "nif", "Count": len(entries)}],
                    "SemanticCategoryCounts": [{"Value": hint, "Count": len(entries)}],
                    "SignatureGroups": [],
                    "Entries": entries,
                }
                (matrix_dir / fname).write_text(json.dumps(report), encoding="utf-8")
            matrices = load_all_matrices(matrix_dir)
            self.assertEqual(len(matrices["hint:map-zone"]), 1)
            block = build_semantic_block("0123456789abcdef", matrix_dir)
            self.assertIn("hint:map-zone", block["categories"])

    def test_archive_derived_entries_match_live_archive_filename_shape(self) -> None:
        """Lockdown: Tier-1 archive-derived outputs use the live-archive filename shape.

        When the ``archive_index`` contains real ``assets.NNN`` provenance
        records (mirroring the shape produced by
        ``scripts/build_live_archive_index.py``), every archive-derived entry
        must:

          a) carry ``ArchiveName`` matching ``^assets\\.\\d{3}$`` (the live shape)
          b) carry ``DetectedType == "archive-derived"`` (Tier-1 mark)
          c) carry ``MagicLabel == POLYFILL_MAGIC_V2_ARCHIVE`` (V2 marker)

        These three invariants together ensure that the polyfill's Tier-1
        path not only fires (MagicLabel V2) but actually persists the
        real archive provenance on disk.  Without all three, an audit
        that queries only one field risks the kind of false-positive that
        bit us on 2026-06-19 (verbal Tier-1-fires claim was correct, but
        the audit script queried the wrong key).
        """
        idx = {
            "0123456789abcdef": ArchiveProvenance(archive="assets.001", entry=0),
            "fedcba9876543210": ArchiveProvenance(archive="assets.100", entry=42),
            "1111111111111111": ArchiveProvenance(archive="assets.244", entry=7),
        }
        flythrough = {
            "assets": {
                "0123456789abcdef": {"faced": True, "vertex_count": 50},
                "fedcba9876543210": {"faced": True, "vertex_count": 5000},
                "1111111111111111": {"faced": False},
            }
        }
        by_hint, stats = synthesize_matrices(flythrough, archive_index=idx)
        # synthesize reported Tier-1 archive-classified count must match index size.
        self.assertEqual(stats["archive-classified"], 3)
        # Walk every produced entry and assert the 3 invariants together.
        for entries in by_hint.values():
            for row in entries:
                if row["DetectedType"] != "archive-derived":
                    continue
                self.assertEqual(row["MagicLabel"], POLYFILL_MAGIC_V2_ARCHIVE)
                self.assertRegex(row["ArchiveName"], r"^assets\.\d{3}$")
                self.assertNotEqual(row["ArchiveName"], "synthetic.twad")
                self.assertGreaterEqual(row["EntryIndex"], 0)

    def test_archive_derived_v2_label_consistent_with_provenance(self) -> None:
        """Lockdown: V2 magic label and archive provenance are tightly coupled.

        Any output entry with ``MagicLabel == POLYFILL_MAGIC_V2_ARCHIVE``
        must carry a real ``ArchiveName`` (not the synthetic placeholder)
        and ``DetectedType == "archive-derived"``.  Conversely, any entry
        with the synthetic marker (``POLYFILL_MAGIC_V1`` or
        ``ArchiveName == "synthetic.twad"``) must NOT carry the V2 label.
        Catches the failure mode where the MagicLabel is set but the
        archive provenance is left blank (or vice versa).
        """
        idx = {
            "0123456789abcdef": ArchiveProvenance(archive="assets.075", entry=11),
        }
        flythrough = {
            "assets": {
                "0123456789abcdef": {"faced": True, "vertex_count": 50},
                "cccccccccccccccc": {"faced": True, "vertex_count": 50},  # not in index
            }
        }
        by_hint, _ = synthesize_matrices(flythrough, archive_index=idx)
        all_rows = [r for entries in by_hint.values() for r in entries]
        for row in all_rows:
            if row["MagicLabel"] == POLYFILL_MAGIC_V2_ARCHIVE:
                self.assertEqual(row["DetectedType"], "archive-derived")
                self.assertNotEqual(row["ArchiveName"], "synthetic.twad")
            if row["DetectedType"] == "archive-derived":
                self.assertEqual(row["MagicLabel"], POLYFILL_MAGIC_V2_ARCHIVE)
            if row["ArchiveName"] == "synthetic.twad":
                self.assertNotEqual(row["MagicLabel"], POLYFILL_MAGIC_V2_ARCHIVE)
                self.assertEqual(row["DetectedType"], "synthetic")


class TestArchiveTaxonomyInvariants(unittest.TestCase):
    """Regression guard pinning ``ARCHIVE_TAXONOMY`` to its live-archive shape.

    Catches any duplicate-tail regression like the 2026-06-19 corruption
    where the comment-polish script accidentally re-pasted the 3 assets.N
    rules after the dict was already closed (12 ruff invalid-syntax errors).
    If ``ARCHIVE_TAXONOMY`` ever gains redundant keys, loses the assets.N
    split, or stops being a disjoint partition, this test fails closed
    before any consumer sees a wrong classification.
    """

    def test_archive_taxonomy_total_keys_is_16(self) -> None:
        # 13 original substring rules (world/zone/map/terrain/character/
        # creature/npc/prop/item/object/waypoint/script/spawn) + 3
        # assets.N rules for the live 244-archive install.
        self.assertEqual(len(ARCHIVE_TAXONOMY), 16)

    def test_archive_taxonomy_assets_n_keys_are_disjoint(self) -> None:
        # The 3 assets.N rules must exist (heuristic split for live archive).
        for needle in ("assets.0", "assets.1", "assets.2"):
            self.assertIn(needle, ARCHIVE_TAXONOMY)
        # No archive in the live range (001-244) may match two different
        # rules under first-match-wins.  Exhaustively assert disjointness.
        for n in range(1, 245):
            archive_name = f"assets.{n:03d}"
            matches = [k for k in ARCHIVE_TAXONOMY if k in archive_name]
            self.assertEqual(
                len(matches),
                1,
                f"{archive_name} matched {matches} instead of exactly 1 rule",
            )

    def test_archive_taxonomy_assets_n_split_routes_correctly(self) -> None:
        # Boundary spot-checks: each rule fires on its expected archive set.
        self.assertEqual(classify_by_archive("assets.001"), "hint:map-zone")
        self.assertEqual(classify_by_archive("assets.099"), "hint:map-zone")
        self.assertEqual(classify_by_archive("assets.100"), "hint:map-zone")
        self.assertEqual(classify_by_archive("assets.150"), "hint:map-zone")
        self.assertEqual(classify_by_archive("assets.199"), "hint:map-zone")
        self.assertEqual(classify_by_archive("assets.200"), "hint:actor-object")
        self.assertEqual(classify_by_archive("assets.244"), "hint:actor-object")

    def test_archive_taxonomy_out_of_range_archive_returns_none(self) -> None:
        # Fail-safe for hypothetical future archives beyond assets.244
        # (would match no needle and revert asset to vertex-count heuristic).
        # ``assets.999`` is a real fail-safe case (no needle matches).
        # ``unknown.twad`` is another genuine miss (no needle matches).
        # NOTE: ``assets.000`` is NOT a fail-safe case -- ``"assets.0"``
        # is a substring of ``"assets.000"`` (first 8 chars match), so
        # it routes to ``hint:map-zone``.
        self.assertIsNone(classify_by_archive("assets.999"))
        self.assertIsNone(classify_by_archive("unknown.twad"))


if __name__ == "__main__":
    unittest.main()
