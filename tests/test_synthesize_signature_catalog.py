"""Tests for ``scripts/synthesize_signature_catalog.py`` — schema conformance and output structure."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def schema() -> dict:
    """Load the binary-signatures-v1 schema."""
    schema_path = REPO_ROOT / "docs" / "schemas" / "binary-signatures-v1.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog() -> dict:
    """Load the synthesized catalog (requires prior pipeline run)."""
    catalog_path = REPO_ROOT / "Exports" / "binary-phase2" / "rift-x64-signature-catalog.json"
    if not catalog_path.exists():
        pytest.skip("Catalog not found — run synthesize_signature_catalog.py first")
    return json.loads(catalog_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Schema conformance
# ---------------------------------------------------------------------------


class TestSchemaConformance:
    """Full jsonschema validation of the synthesized catalog."""

    def test_catalog_validates_against_schema(self, catalog: dict, schema: dict) -> None:
        """The synthesized catalog must pass full jsonschema validation."""
        jsonschema = pytest.importorskip("jsonschema")
        jsonschema.validate(
            catalog,
            schema,
            format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
        )

    def test_schema_version_matches(self, catalog: dict) -> None:
        """SchemaVersion must be exactly 'binary-signatures/v1'."""
        assert catalog["SchemaVersion"] == "binary-signatures/v1"

    def test_candidate_only_is_true(self, catalog: dict) -> None:
        """CandidateOnly must be true for all catalogs."""
        assert catalog["CandidateOnly"] is True

    def test_anchors_non_empty(self, catalog: dict) -> None:
        """Anchors array must contain at least one entry."""
        assert isinstance(catalog["Anchors"], list)
        assert len(catalog["Anchors"]) > 0


class TestAnchorStructure:
    """Per-anchor field validation."""

    def test_all_anchors_have_required_fields(self, catalog: dict) -> None:
        """Every anchor must have Name, StabilityTier, SignatureHex, SignatureLength, UniquenessVerified, DiscoveryMethod."""
        required = {"Name", "StabilityTier", "SignatureHex", "SignatureLength", "UniquenessVerified", "DiscoveryMethod"}
        for i, anchor in enumerate(catalog["Anchors"]):
            missing = required - set(anchor.keys())
            assert not missing, f"anchor[{i}] ({anchor.get('Name', '?')}) missing: {missing}"

    def test_stability_tiers_in_range(self, catalog: dict) -> None:
        """StabilityTier must be 1, 2, or 3."""
        for anchor in catalog["Anchors"]:
            tier = anchor["StabilityTier"]
            assert 1 <= tier <= 3, f"{anchor['Name']}: StabilityTier={tier} out of range"

    def test_signature_hex_format(self, catalog: dict) -> None:
        """SignatureHex must be space-separated hex bytes with optional ?? wildcards."""
        for anchor in catalog["Anchors"]:
            sig = anchor["SignatureHex"]
            assert sig, f"{anchor['Name']}: empty SignatureHex"
            tokens = sig.split()
            assert len(tokens) >= 4, f"{anchor['Name']}: SignatureHex too short ({len(tokens)} bytes)"
            for token in tokens:
                assert len(token) == 2, f"{anchor['Name']}: invalid token {token!r}"
                if token != "??":
                    int(token, 16)  # must be valid hex

    def test_unique_anchors_have_no_fallback(self, catalog: dict) -> None:
        """UniquenessVerified=True anchors should not have a FallbackStrategy."""
        for anchor in catalog["Anchors"]:
            if anchor["UniquenessVerified"]:
                assert "FallbackStrategy" not in anchor, (
                    f"{anchor['Name']}: unique anchor should not have FallbackStrategy"
                )

    def test_non_unique_anchors_have_fallback(self, catalog: dict) -> None:
        """UniquenessVerified=False anchors must have a FallbackStrategy."""
        for anchor in catalog["Anchors"]:
            if not anchor["UniquenessVerified"]:
                assert "FallbackStrategy" in anchor, f"{anchor['Name']}: non-unique anchor missing FallbackStrategy"


class TestSummaryConsistency:
    """Summary counts must be consistent with the Anchors array."""

    def test_total_anchors_matches_array_length(self, catalog: dict) -> None:
        assert catalog["Summary"]["TotalAnchors"] == len(catalog["Anchors"])

    def test_unique_count_matches(self, catalog: dict) -> None:
        actual = sum(1 for a in catalog["Anchors"] if a["UniquenessVerified"])
        assert catalog["Summary"]["UniqueSignatures"] == actual

    def test_non_unique_count_matches(self, catalog: dict) -> None:
        actual = sum(1 for a in catalog["Anchors"] if not a["UniquenessVerified"])
        assert catalog["Summary"]["NonUniqueSignatures"] == actual

    def test_tier_counts_sum_to_total(self, catalog: dict) -> None:
        s = catalog["Summary"]
        assert s["StabilityTier1Count"] + s["StabilityTier2Count"] + s["StabilityTier3Count"] == s["TotalAnchors"]
