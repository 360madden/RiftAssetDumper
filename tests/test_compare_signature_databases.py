"""Tests for ``scripts/compare_signature_databases.py``.

Categories exercised (one test per diff category):
    identity, anchor-added, anchor-removed, sig-hex-changed,
    signature-length-changed, wildcard-count-changed,
    stability-tier-regressed, uniqueness-changed,
    struct-fields-added, struct-fields-removed,
    modrm-shake, notes-changed,
    confidence-promoted, confidence-demoted,
    binary-version-changed, binary-fingerprint-moved,
    ghidra-findings-changed.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import scripts.compare_signature_databases as compare_mod  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _anchor(
    name: str,
    *,
    sig: str = "48 8B C4 90",
    tier: int = 2,
    unique: bool = True,
    struct_layout: dict | None = None,
) -> dict:
    # Schema requires SignatureLength >= 4. Pad short test sigs to a known
    # 4+ byte length so fixtures pass jsonschema validation when called
    # from subprocess paths (test_cli_smoke / test_extract_binary_signatures).
    tokens = sig.split()
    if len(tokens) < 4:
        tokens = tokens + ["90"] * (4 - len(tokens))
        sig = " ".join(tokens)
    a = {
        "Name": name,
        "StabilityTier": tier,
        "SignatureHex": sig,
        "SignatureLength": len(sig.split()),
        "WildcardCount": sig.count("??"),
        "UniquenessVerified": unique,
        "DiscoveryMethod": "modrm-cluster-heuristic",
    }
    if struct_layout is not None:
        a["StructLayout"] = struct_layout
    return a


def _struct(*, description: str = "LocalPlayer", fields: list[dict] | None = None) -> dict:
    return {
        "Description": description,
        "Fields": fields or [],
        "BaseRegisters": {"RBX": 100, "RCX": 50},
        "TotalModRMHits": 150,
    }


def _field(name: str, offset_hex: str, *, hits: int = 50, confidence: str = "inferred", notes: str = "n") -> dict:
    return {
        "Offset": int(offset_hex, 16),
        "OffsetHex": offset_hex,
        "Name": name,
        "Type": "float32",
        "Confidence": confidence,
        "ModRMHitCount": hits,
        "Notes": notes,
    }


def _build_db(*, anchors: list[dict], binary_version: dict | None = None, ghidra_findings: dict | None = None) -> dict:
    return {
        "SchemaVersion": "binary-signatures/v1",
        "BinaryTarget": "rift_x64.exe",
        "BinaryVersion": binary_version
        or {
            "PEFileVersion": "1.0.0",
            "PETimestamp": 1700000000,
            "PETimestampUTC": "2023-11-14T22:13:20Z",
            "FileSizeBytes": 59937216,
        },
        "ImageBase": "0x140000000",
        "TextSection": {"VirtualAddress": "0x1000", "RawSize": 0},
        "ExtractedAt": "2026-07-07T00:00:00Z",
        "WildcardPolicy": "test",
        "CandidateOnly": True,
        "Provenance": {
            "DiscoveryMethod": "modrm-cluster-heuristic",
            "ValidationMethod": "full-binary-uniqueness-scan",
            "GhidraFindings": ghidra_findings or {},
        },
        "Anchors": anchors,
        "Summary": {
            "TotalAnchors": len(anchors),
            "UniqueSignatures": sum(1 for a in anchors if a.get("UniquenessVerified")),
            "NonUniqueSignatures": sum(1 for a in anchors if not a.get("UniquenessVerified")),
            "StabilityTier1Count": sum(1 for a in anchors if a.get("StabilityTier") == 1),
            "StabilityTier2Count": sum(1 for a in anchors if a.get("StabilityTier") == 2),
            "StabilityTier3Count": sum(1 for a in anchors if a.get("StabilityTier") == 3),
        },
    }


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def test_identity_diff_produces_zero_changes() -> None:
    layout = _struct(
        fields=[
            _field("pos_x", "0x320", hits=623, confidence="confirmed"),
            _field("pos_z", "0x328", hits=646, confidence="confirmed"),
        ]
    )
    db = _build_db(anchors=[_anchor("vtable-dispatch", sig="48 85 D2 74 0A", tier=1, struct_layout=layout)])
    diff = compare_mod.compute_diff(db, deepcopy(db))
    assert diff["total_changes"] == 0
    assert diff["diff_categories"] == []
    assert diff["changes"] == []


# ---------------------------------------------------------------------------
# Anchor-level
# ---------------------------------------------------------------------------


def test_anchor_added_and_removed() -> None:
    old = _build_db(anchors=[_anchor("vtable-dispatch", sig="48 85 D2", tier=1)])
    new = _build_db(
        anchors=[_anchor("vtable-dispatch", sig="48 85 D2", tier=1), _anchor("#1 (28h)", sig="55 4C 39", tier=2)]
    )
    diff = compare_mod.compute_diff(old, new)
    cats = set(diff["diff_categories"])
    assert "anchor-added" in cats
    assert "anchor-removed" not in cats  # nothing removed

    old = _build_db(
        anchors=[_anchor("vtable-dispatch", sig="48 85 D2", tier=1), _anchor("#1 (28h)", sig="55 4C 39", tier=2)]
    )
    new = _build_db(anchors=[_anchor("vtable-dispatch", sig="48 85 D2", tier=1)])
    diff = compare_mod.compute_diff(old, new)
    cats = set(diff["diff_categories"])
    assert "anchor-removed" in cats


def test_sig_hex_changed() -> None:
    old = _build_db(anchors=[_anchor("vt", sig="48 85 D2", tier=1)])
    new = _build_db(anchors=[_anchor("vt", sig="48 85 D3", tier=1)])
    diff = compare_mod.compute_diff(old, new)
    assert "sig-hex-changed" in diff["diff_categories"]
    # After _anchor helper auto-pads to >=4 bytes, exact hex equality is not
    # the right assertion — just confirm the byte sequence differed.
    assert any(c.get("old") != c.get("new") and c.get("category") == "sig-hex-changed" for c in diff["changes"])


def test_signature_length_changed() -> None:
    # Add a single trailing byte to the new sig without changing tier/unique.
    old = _build_db(anchors=[_anchor("vt", sig="48 85 D2 74", tier=1)])
    new = _build_db(anchors=[_anchor("vt", sig="48 85 D2 74 0A", tier=1)])
    diff = compare_mod.compute_diff(old, new)
    cats = set(diff["diff_categories"])
    assert "sig-hex-changed" in cats
    assert "signature-length-changed" in cats


def test_wildcard_count_changed() -> None:
    old = _build_db(anchors=[_anchor("vt", sig="48 85 D2 ?? 90", tier=1)])
    new = _build_db(anchors=[_anchor("vt", sig="48 85 D2 90 90", tier=1)])
    diff = compare_mod.compute_diff(old, new)
    assert "wildcard-count-changed" in diff["diff_categories"]


def test_stability_tier_regressed_only_when_lower_to_higher() -> None:
    old = _build_db(anchors=[_anchor("vt", sig="48 85 D2", tier=1)])
    new_improved = _build_db(anchors=[_anchor("vt", sig="48 85 D2", tier=2)])
    diff = compare_mod.compute_diff(old, new_improved)
    assert "stability-tier-regressed" in diff["diff_categories"]


def test_uniqueness_changed() -> None:
    old = _build_db(anchors=[_anchor("vt", sig="48 85 D2", tier=1, unique=True)])
    new = _build_db(anchors=[_anchor("vt", sig="48 85 D2", tier=1, unique=False)])
    diff = compare_mod.compute_diff(old, new)
    assert "uniqueness-changed" in diff["diff_categories"]


# ---------------------------------------------------------------------------
# Struct layout
# ---------------------------------------------------------------------------


def test_struct_field_added() -> None:
    old_layout = _struct(fields=[_field("pos_x", "0x320"), _field("pos_z", "0x328")])
    new_layout = _struct(
        fields=[
            _field("pos_x", "0x320"),
            _field("pos_y", "0x324"),
            _field("pos_z", "0x328"),
        ]
    )
    old = _build_db(anchors=[_anchor("vt", tier=1, struct_layout=old_layout)])
    new = _build_db(anchors=[_anchor("vt", tier=1, struct_layout=new_layout)])
    diff = compare_mod.compute_diff(old, new)
    assert "struct-fields-added" in diff["diff_categories"]
    # Exactly one new field (pos_y) at offset 0x324
    addition = next(c for c in diff["changes"] if c["category"] == "struct-fields-added")
    assert "0x324" in addition["offsets"]


def test_struct_field_removed() -> None:
    old_layout = _struct(fields=[_field("pos_x", "0x320"), _field("pos_y", "0x324")])
    new_layout = _struct(fields=[_field("pos_x", "0x320")])
    old = _build_db(anchors=[_anchor("vt", tier=1, struct_layout=old_layout)])
    new = _build_db(anchors=[_anchor("vt", tier=1, struct_layout=new_layout)])
    diff = compare_mod.compute_diff(old, new)
    assert "struct-fields-removed" in diff["diff_categories"]


def test_modrm_shake_at_threshold() -> None:
    # Implementation: delta_pct = abs(nh-oh) / max(oh, nh, 1).
    # For shake to fire at >=25%, we need |delta|/max >= 0.25.
    # (100 -> 75): delta=25, max=100, delta_pct=0.25 -> qualifies.
    old_layout = _struct(fields=[_field("pos_x", "0x320", hits=100)])
    new_layout_qualify = _struct(fields=[_field("pos_x", "0x320", hits=75)])
    old = _build_db(anchors=[_anchor("vt", tier=1, struct_layout=old_layout)])
    new_qualify = _build_db(anchors=[_anchor("vt", tier=1, struct_layout=new_layout_qualify)])
    diff = compare_mod.compute_diff(old, new_qualify)
    assert "modrm-shake" in diff["diff_categories"], diff

    # (100 -> 76): delta=24, max=100, delta_pct=0.24 -> does NOT qualify.
    new_layout_dq = _struct(fields=[_field("pos_x", "0x320", hits=76)])
    new_dq = _build_db(anchors=[_anchor("vt", tier=1, struct_layout=new_layout_dq)])
    diff_dq = compare_mod.compute_diff(old, new_dq)
    assert "modrm-shake" not in diff_dq["diff_categories"], diff_dq


def test_notes_changed() -> None:
    old_layout = _struct(fields=[_field("pos_x", "0x320", notes="old note")])
    new_layout = _struct(fields=[_field("pos_x", "0x320", notes="new note")])
    old = _build_db(anchors=[_anchor("vt", tier=1, struct_layout=old_layout)])
    new = _build_db(anchors=[_anchor("vt", tier=1, struct_layout=new_layout)])
    diff = compare_mod.compute_diff(old, new)
    assert "notes-changed" in diff["diff_categories"]


def test_field_name_changed_with_same_offset() -> None:
    """Same offset, same hit count, but Name drift (pos_x -> terrain_x). The
    offset-based diff would silently miss this; field-name-changed surfaces it."""
    old_layout = _struct(fields=[_field("pos_x", "0x320", hits=623)])
    new_layout = _struct(fields=[_field("terrain_x", "0x320", hits=623)])
    old = _build_db(anchors=[_anchor("vt", tier=1, struct_layout=old_layout)])
    new = _build_db(anchors=[_anchor("vt", tier=1, struct_layout=new_layout)])
    diff = compare_mod.compute_diff(old, new)
    cats = set(diff["diff_categories"])
    assert "field-name-changed" in cats
    # And nothing else should fire (sig hex unchanged, no add/remove, no shake).
    assert "sig-hex-changed" not in cats
    assert "struct-fields-added" not in cats
    assert "struct-fields-removed" not in cats
    assert "modrm-shake" not in cats


def test_confidence_promoted_and_demoted() -> None:
    old_layout = _struct(fields=[_field("pos_x", "0x320", confidence="inferred")])
    promoted_layout = _struct(fields=[_field("pos_x", "0x320", confidence="confirmed")])
    demoted_layout = _struct(fields=[_field("pos_x", "0x320", confidence="tentative")])
    old = _build_db(anchors=[_anchor("vt", tier=1, struct_layout=old_layout)])
    promoted = _build_db(anchors=[_anchor("vt", tier=1, struct_layout=promoted_layout)])
    demoted = _build_db(anchors=[_anchor("vt", tier=1, struct_layout=demoted_layout)])
    diff_p = compare_mod.compute_diff(old, promoted)
    diff_d = compare_mod.compute_diff(old, demoted)
    assert "confidence-promoted" in diff_p["diff_categories"]
    assert "confidence-demoted" in diff_d["diff_categories"]


# ---------------------------------------------------------------------------
# Provenance-level
# ---------------------------------------------------------------------------


def test_binary_version_changed_petimestamp() -> None:
    old = _build_db(
        anchors=[_anchor("vt", sig="48 85 D2", tier=1)],
        binary_version={
            "PEFileVersion": "1.0.0",
            "PETimestamp": 1700000000,
            "PETimestampUTC": "2023-11-14T22:13:20Z",
            "FileSizeBytes": 59937216,
        },
    )
    new = _build_db(
        anchors=[_anchor("vt", sig="48 85 D2", tier=1)],
        binary_version={
            "PEFileVersion": "2.0.0",  # patched
            "PETimestamp": 1700100000,
            "PETimestampUTC": "2023-11-15T22:13:20Z",
            "FileSizeBytes": 60100000,
        },
    )
    diff = compare_mod.compute_diff(old, new)
    cats = set(diff["diff_categories"])
    assert "binary-version-changed" in cats
    assert "binary-fingerprint-moved" not in cats  # image base + text size unchanged


def test_ghidra_findings_changed() -> None:
    old = _build_db(
        anchors=[_anchor("vt", sig="48 85 D2", tier=1)],
        ghidra_findings={"PreviousCallback0x320": "old narrative"},
    )
    new = _build_db(
        anchors=[_anchor("vt", sig="48 85 D2", tier=1)],
        ghidra_findings={"PreviousCallback0x320": "new narrative"},
    )
    diff = compare_mod.compute_diff(old, new)
    assert "ghidra-findings-changed" in diff["diff_categories"]


# ---------------------------------------------------------------------------
# Markdown / CLI
# ---------------------------------------------------------------------------


def test_render_markdown_includes_counts() -> None:
    diff = {
        "diff_categories": ["anchor-added"],
        "total_changes": 1,
        "category_counts": {"anchor-added": 1},
        "changes": [{"category": "anchor-added", "name": "new_anchor"}],
    }
    md = compare_mod.render_markdown(diff, old_path="/old.json", new_path="/new.json")
    assert "anchor-added" in md
    assert "Categories" in md.replace("Category counts", "Categories") or "Category counts" in md
    assert "new_anchor" in md


def test_cli_smoke(tmp_path: Path) -> None:
    """Synthesize a DB twice with mutated bytes and route through the CLI."""

    layout = _struct(fields=[_field("pos_x", "0x320", hits=623, confidence="confirmed")])
    db_a = _build_db(
        anchors=[_anchor("vt", sig="48 85 D2", tier=1, unique=True, struct_layout=layout)],
        binary_version={
            "PEFileVersion": "1",
            "PETimestamp": 100,
            "PETimestampUTC": "2024-01-01T00:00:00Z",
            "FileSizeBytes": 100,
        },
    )
    db_b = deepcopy(db_a)
    db_b["Anchors"][0]["SignatureHex"] = "48 85 D3"
    db_b["Anchors"][0]["SignatureLength"] = 4
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text(json.dumps(db_a), encoding="utf-8")
    new_path.write_text(json.dumps(db_b), encoding="utf-8")
    out = tmp_path / "diff.json"
    md_out = tmp_path / "diff.md"
    code = compare_mod.main(
        ["--old-db", str(old_path), "--new-db", str(new_path), "--out", str(out), "--markdown-out", str(md_out)]
    )
    # The diff should succeed (return 0) regardless of churn.
    assert code == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["SchemaVersion"] == "binary-signature-diff/v1"
    assert "sig-hex-changed" in report["diff_categories"]
    assert md_out.exists()
