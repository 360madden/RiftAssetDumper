"""Tests for ``scripts/synthesize_unified_signature_db.py``.

Validates that the unified Phase 5 DB synthesis:
1. Re-uses the binary-signatures/v1 schema (no new schema introduced)
2. Preserves every Phase 2 anchor (no anchors dropped)
3. Enriches matching anchors with Phase 3 struct layout including
   ModRMHitCount and Notes
4. Recomputes the Summary block consistently with the anchors array
5. Tolerates a missing Phase 3 catalog by emitting a still-schema-valid DB
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.synthesize_unified_signature_db as synth  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(
        (REPO_ROOT / "docs" / "schemas" / "binary-signatures-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture(scope="module")
def phase2_catalog() -> dict:
    path = REPO_ROOT / "Exports" / "binary-phase2" / "rift-x64-signature-catalog.json"
    if not path.exists():
        pytest.skip("Phase 2 catalog not found — run synthesize_signature_catalog.py first")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def phase3_catalog() -> dict:
    path = REPO_ROOT / "Exports" / "binary-phase3" / "struct-layout-catalog.json"
    if not path.exists():
        pytest.skip("Phase 3 catalog not found — run synthesize_struct_layout.py first")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_catalog(tmp_path: Path, phase2: dict, phase3: dict | None) -> tuple[Path, Path | None]:
    p2 = tmp_path / "phase2.json"
    p2.write_text(json.dumps(phase2), encoding="utf-8")
    p3 = None
    if phase3 is not None:
        p3 = tmp_path / "phase3.json"
        p3.write_text(json.dumps(phase3), encoding="utf-8")
    return p2, p3


# ---------------------------------------------------------------------------
# Schema conformance
# ---------------------------------------------------------------------------


class TestSchemaConformance:
    def test_unified_db_validates_against_schema(self, schema: dict) -> None:
        jsonschema = pytest.importorskip("jsonschema")
        db = synth.synthesize_database()
        jsonschema.validate(
            db, schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
        )

    def test_schema_version_matches_binary_signatures_v1(self) -> None:
        db = synth.synthesize_database()
        assert db["SchemaVersion"] == "binary-signatures/v1"

    def test_candidate_only_is_true(self) -> None:
        db = synth.synthesize_database()
        assert db["CandidateOnly"] is True

    def test_anchors_non_empty(self) -> None:
        db = synth.synthesize_database()
        assert isinstance(db["Anchors"], list)
        assert len(db["Anchors"]) >= 1


# ---------------------------------------------------------------------------
# Merge invariants
# ---------------------------------------------------------------------------


class TestMergeInvariants:
    def test_phase2_anchors_preserved(
        self, tmp_path: Path, phase2_catalog: dict, phase3_catalog: dict
    ) -> None:
        p2, p3 = _write_catalog(tmp_path, phase2_catalog, phase3_catalog)
        db = synth.synthesize_database(phase2_catalog_path=p2, phase3_catalog_path=p3)
        original_names = {a["Name"] for a in phase2_catalog["Anchors"]}
        emitted_names = {a["Name"] for a in db["Anchors"]}
        assert emitted_names == original_names

    def test_summary_matches_anchors_array(self) -> None:
        db = synth.synthesize_database()
        s = db["Summary"]
        assert s["TotalAnchors"] == len(db["Anchors"])
        unique_actual = sum(1 for a in db["Anchors"] if a.get("UniquenessVerified"))
        assert s["UniqueSignatures"] == unique_actual
        tier1 = sum(1 for a in db["Anchors"] if a.get("StabilityTier") == 1)
        tier2 = sum(1 for a in db["Anchors"] if a.get("StabilityTier") == 2)
        tier3 = sum(1 for a in db["Anchors"] if a.get("StabilityTier") == 3)
        assert s["StabilityTier1Count"] + s["StabilityTier2Count"] + s["StabilityTier3Count"] == s["TotalAnchors"]
        assert (s["StabilityTier1Count"], s["StabilityTier2Count"], s["StabilityTier3Count"]) == (
            tier1,
            tier2,
            tier3,
        )


# ---------------------------------------------------------------------------
# Phase 3 enrichment
# ---------------------------------------------------------------------------


class TestPhase3Enrichment:
    def test_vtable_dispatch_anchor_has_struct_layout_with_phase3_fields(
        self, tmp_path: Path, phase2_catalog: dict, phase3_catalog: dict
    ) -> None:
        p2, p3 = _write_catalog(tmp_path, phase2_catalog, phase3_catalog)
        db = synth.synthesize_database(phase2_catalog_path=p2, phase3_catalog_path=p3)
        vtable = next((a for a in db["Anchors"] if a["Name"] == "vtable-dispatch"), None)
        assert vtable is not None, "vtable-dispatch anchor missing"
        struct_layout = vtable.get("StructLayout")
        assert struct_layout is not None, "vtable-dispatch must carry a StructLayout"
        field_names = [f["Name"] for f in struct_layout["Fields"]]
        # Phase 3's 8-field LocalPlayer includes unknown_float_31c which Phase 2 lacked.
        assert "unknown_float_31c" in field_names, "Phase 3 field not threaded through"
        assert "pos_x" in field_names and "pos_z" in field_names

    def test_modrm_hit_count_populated(self, tmp_path: Path, phase2_catalog: dict, phase3_catalog: dict) -> None:
        p2, p3 = _write_catalog(tmp_path, phase2_catalog, phase3_catalog)
        db = synth.synthesize_database(phase2_catalog_path=p2, phase3_catalog_path=p3)
        vtable = next(a for a in db["Anchors"] if a["Name"] == "vtable-dispatch")
        for field in vtable["StructLayout"]["Fields"]:
            assert "ModRMHitCount" in field, f"Field {field['Name']} missing ModRMHitCount"
            assert field["ModRMHitCount"] >= 0
        # The highest-hit field is pos_z (646) per the Phase 3 catalog.
        pos_z = next(f for f in vtable["StructLayout"]["Fields"] if f["Name"] == "pos_z")
        assert pos_z["ModRMHitCount"] >= 500, "pos_z hit count should be high"

    def test_notes_carried_through(self, tmp_path: Path, phase2_catalog: dict, phase3_catalog: dict) -> None:
        p2, p3 = _write_catalog(tmp_path, phase2_catalog, phase3_catalog)
        db = synth.synthesize_database(phase2_catalog_path=p2, phase3_catalog_path=p3)
        vtable = next(a for a in db["Anchors"] if a["Name"] == "vtable-dispatch")
        for field in vtable["StructLayout"]["Fields"]:
            assert "Notes" in field, f"Field {field['Name']} missing Notes"

    def test_struct_layout_struct_keys_present_when_phase3_available(
        self, tmp_path: Path, phase2_catalog: dict, phase3_catalog: dict
    ) -> None:
        p2, p3 = _write_catalog(tmp_path, phase2_catalog, phase3_catalog)
        db = synth.synthesize_database(phase2_catalog_path=p2, phase3_catalog_path=p3)
        vtable = next(a for a in db["Anchors"] if a["Name"] == "vtable-dispatch")
        sl = vtable["StructLayout"]
        # These struct-level keys are populated from Phase 3; verify they exist
        # when the Phase 3 catalog was supplied.
        assert "BaseRegisters" in sl
        assert "TotalModRMHits" in sl
        assert sl["TotalModRMHits"] > 0


# ---------------------------------------------------------------------------
# Missing-input resilience
# ---------------------------------------------------------------------------


class TestMissingPhase3:
    def test_missing_phase3_emits_schema_valid_db(
        self, tmp_path: Path, phase2_catalog: dict, schema: dict
    ) -> None:
        p2, _ = _write_catalog(tmp_path, phase2_catalog, phase3=None)
        db = synth.synthesize_database(
            phase2_catalog_path=p2,
            phase3_catalog_path=tmp_path / "missing.json",
        )
        jsonschema = pytest.importorskip("jsonschema")
        jsonschema.validate(
            db, schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
        )

    def test_missing_phase3_keeps_phase2_struct_layout(
        self, tmp_path: Path, phase2_catalog: dict
    ) -> None:
        p2, _ = _write_catalog(tmp_path, phase2_catalog, phase3=None)
        db = synth.synthesize_database(
            phase2_catalog_path=p2,
            phase3_catalog_path=tmp_path / "missing.json",
        )
        vtable = next(a for a in db["Anchors"] if a["Name"] == "vtable-dispatch")
        # Without Phase 3, we preserve whatever the Phase 2 embed happened to carry.
        assert vtable.get("StructLayout") is not None
        assert len(vtable["StructLayout"]["Fields"]) >= 1


# ---------------------------------------------------------------------------
# Provenance / metadata
# ---------------------------------------------------------------------------


class TestProvenanceMetadata:
    def test_phase2_path_recorded(
        self, tmp_path: Path, phase2_catalog: dict, phase3_catalog: dict
    ) -> None:
        p2, p3 = _write_catalog(tmp_path, phase2_catalog, phase3_catalog)
        db = synth.synthesize_database(phase2_catalog_path=p2, phase3_catalog_path=p3)
        prov = db["Provenance"]
        assert "Phase2CatalogPath" in prov
        assert "Phase3CatalogPath" in prov
        assert prov["CrossCheckerVersion"].startswith("synthesize-unified-signature-db")

    def test_extracted_at_is_iso8601(self) -> None:
        db = synth.synthesize_database()
        ts = db["ExtractedAt"]
        # ISO-8601 UTC: "YYYY-MM-DDTHH:MM:SSZ"
        assert ts.endswith("Z"), f"ExtractedAt must end with 'Z': {ts}"
        assert "T" in ts and "-" in ts

    def test_ghidra_findings_enum_keys_when_phase3_available(
        self, tmp_path: Path, phase2_catalog: dict, phase3_catalog: dict
    ) -> None:
        """The Provenance.GhidraFindings dict, when populated, must be enum-locked:
        it cannot introduce keys beyond the 4 known ones documented in the schema.
        """
        p2, p3 = _write_catalog(tmp_path, phase2_catalog, phase3_catalog)
        db = synth.synthesize_database(phase2_catalog_path=p2, phase3_catalog_path=p3)
        gf = db["Provenance"].get("GhidraFindings", {})
        # Schema enumerates exactly 4 keys. Robustness: synth may legitimately
        # accept MORE upstream Phase 3 keys, in which case the schema validation
        # surface is a documented upgrade path. The phase 3 fixtures we use here
        # carry exactly the 4 known enum-locked keys.
        schema = json.loads(
            (REPO_ROOT / "docs" / "schemas" / "binary-signatures-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        enum_keys = set(schema["properties"]["Provenance"]["properties"]["GhidraFindings"]["properties"].keys())
        # Sanity: the schema locks to the 4 known keys.
        assert enum_keys == {
            "PreviousCallback0x320",
            "PreviousCallback0x328",
            "PropertyWalkerArchitecture",
            "ActualAccessPattern",
        }
        # Whatever the synth emits, the keys present in the dict must be a
        # subset of the enum (or empty when the Phase 3 fixture has no
        # GhidraFindings, which is the common case for older test fixtures).
        assert set(gf.keys()) <= enum_keys

    def test_ghidra_findings_absent_when_phase3_missing(
        self, tmp_path: Path, phase2_catalog: dict
    ) -> None:
        """Without a Phase 3 catalog, Provenance.GhidraFindings must be an
        empty dict (or absent) and must still pass schema validation
        (the field is optional in the schema)."""
        p2, _ = _write_catalog(tmp_path, phase2_catalog, phase3=None)
        db = synth.synthesize_database(
            phase2_catalog_path=p2,
            phase3_catalog_path=tmp_path / "missing.json",
        )
        gf = db["Provenance"].get("GhidraFindings", {})
        # Either absent or empty; we never invent data we don't have.
        assert gf == {}, f"Without Phase 3 catalog, GhidraFindings must be empty (got {gf!r})"


# ---------------------------------------------------------------------------
# Defensive guards
# ---------------------------------------------------------------------------


class TestDefensiveGuards:
    def test_empty_phase2_anchors_raises(self, tmp_path: Path) -> None:
        """An empty Anchors[] would fail schema validation (minItems: 1).
        The synth must raise ValueError loudly rather than emit a silently
        invalid DB. This guards against upstream catalog regressions."""
        empty_p2 = {
            "SchemaVersion": "binary-signatures/v1",
            "BinaryTarget": "rift_x64.exe",
            "BinaryVersion": {
                "PEFileVersion": "0",
                "PETimestamp": 0,
                "PETimestampUTC": "",
                "FileSizeBytes": 0,
            },
            "ImageBase": "0x140000000",
            "WildcardPolicy": "test",
            "CandidateOnly": True,
            "Anchors": [],
            "Summary": {
                "TotalAnchors": 0,
                "UniqueSignatures": 0,
                "NonUniqueSignatures": 0,
                "StabilityTier1Count": 0,
                "StabilityTier2Count": 0,
                "StabilityTier3Count": 0,
            },
            "Provenance": {},
        }
        p2 = tmp_path / "empty_phase2.json"
        p2.write_text(json.dumps(empty_p2), encoding="utf-8")
        with pytest.raises(ValueError, match="empty Anchors"):
            synth.synthesize_database(
                phase2_catalog_path=p2,
                phase3_catalog_path=tmp_path / "missing.json",
            )


# ---------------------------------------------------------------------------
# Concurrency / immutability
# ---------------------------------------------------------------------------


class TestInputIsolation:
    def test_phase2_catalog_not_mutated(
        self, tmp_path: Path, phase2_catalog: dict, phase3_catalog: dict
    ) -> None:
        p2, p3 = _write_catalog(tmp_path, phase2_catalog, phase3_catalog)
        snapshot = deepcopy(phase2_catalog)
        synth.synthesize_database(phase2_catalog_path=p2, phase3_catalog_path=p3)
        assert phase2_catalog == snapshot, "Phase 2 catalog must not be mutated"
