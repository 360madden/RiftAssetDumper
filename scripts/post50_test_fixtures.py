"""Shared minimal fixtures for POST50 status tests."""

from __future__ import annotations

from typing import Any


def minimal_mesh329_attribute_role_matrix_report() -> dict[str, Any]:
    """Return the minimal candidate-only mesh329 attribute-role matrix fixture."""
    return {
        "Schema": "329-family-attribute-role-matrix/v1",
        "CandidateOnly": True,
        "MeshSize": 329,
        "TargetMeshBlocks": [7, 34],
        "IDsCovered": [],
        "ProbeCount": 0,
        "MatrixRows": [],
        "PairComparisons": [],
        "PatternQuantification": {
            "IDsWithBothProbes": 0,
            "IDsWithMesh7Attr1": 0,
            "IDsWithMesh34Attr0": 0,
            "IDsWithMesh34_304ScoredAsPosition": 0,
            "IDsWithMesh7UVPresent": 0,
            "IDsWithMesh34UVAbsent": 0,
            "ConsistentPatterns": [],
            "QuantifiedNotes": {},
        },
        "Interpretation": "minimal test fixture",
        "ParserExportPromotionAllowed": False,
    }
