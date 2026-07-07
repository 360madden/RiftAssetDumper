"""Tests for the data-driven multi-struct synthesizer (Phase 3 M3.2 framework).

The M3.2 refactor of `scripts/synthesize_struct_layout.py` generalizes the
LocalPlayer-only synth into a `STRUCT_DEFINITIONS` model that emits
LocalPlayer (8 fields, status=shipped) + ZoneInfo + EntityList (empty
Fields, status=pending). These tests pin the contract:

1. LocalPlayer fields are preserved verbatim from M3.1 (byte-for-byte
   offsets, names, types, notes).
2. ZoneInfo + EntityList emit with `Status: "pending"` and empty Fields[].
3. The schema (`minItems: 0` + new `Status` enum) accepts both
   populated and empty-Fields structs.
4. The confidence model is applied consistently across all structs.
5. With no ModRM scan input, all hit counts default to 0 + confidence
   drops to "tentative".

These run in <1 s on a cold cache using synthetic fixtures.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import scripts.synthesize_struct_layout as synth  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "docs" / "schemas" / "struct-layout-catalog-v1.schema.json"

# Schema discriminator constant (pinned for catalog validation)
SCHEMA_DISCRIMINATOR = "struct-layout-catalog/v1"


def _minimal_modrm_scan(by_offset: dict[str, int] | None = None) -> dict:
    """Tiny ModRM scan fixture — total_matches + by_offset map."""
    if by_offset is None:
        by_offset = {"0x320": 623, "0x328": 646, "0x310": 566, "0x304": 35}
    return {
        "SchemaVersion": "modrm-memory-access-scan/v1",
        "total_matches": sum(by_offset.values()) or 1,
        "by_base_register": {"rbx": 727, "rcx": 508},
        "by_offset": by_offset,
    }


def _empty_signature_catalog() -> dict:
    """Empty Phase 2 catalog fixture."""
    return {
        "SchemaVersion": "binary-signatures/v1",
        "Anchors": [],
    }


def _validate(catalog: dict) -> None:
    """Run jsonschema validation. Skip if jsonschema is unavailable."""
    try:
        import jsonschema

        jsonschema.validate(
            catalog,
            json.loads(SCHEMA_PATH.read_text(encoding="utf-8")),
            format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
        )
    except ImportError:
        # Fallback: structural minimum check
        if catalog.get("SchemaVersion") != SCHEMA_DISCRIMINATOR:
            raise AssertionError("SchemaVersion mismatch") from None
        if not isinstance(catalog.get("Structs"), list) or len(catalog["Structs"]) == 0:
            raise AssertionError("Structs must be a non-empty array") from None


def _write_fixtures(tmp: str, modrm: dict, sig: dict) -> tuple[pathlib.Path, pathlib.Path]:
    modrm_path = pathlib.Path(tmp) / "modrm.json"
    sig_path = pathlib.Path(tmp) / "sig.json"
    modrm_path.write_text(json.dumps(modrm), encoding="utf-8")
    sig_path.write_text(json.dumps(sig), encoding="utf-8")
    return modrm_path, sig_path


def test_schema_discriminator_pinned():
    """The output SchemaVersion must match the locked discriminator constant."""
    with tempfile.TemporaryDirectory() as tmp:
        modrm_path, sig_path = _write_fixtures(tmp, _minimal_modrm_scan(), _empty_signature_catalog())
        catalog = synth.synthesize_catalog(modrm_scan_path=modrm_path, signature_catalog_path=sig_path)
    assert catalog["SchemaVersion"] == SCHEMA_DISCRIMINATOR


def test_struct_definitions_has_three_entries():
    """M3.2 framework ships 3 structs: LocalPlayer + ZoneInfo + EntityList (Camera-deferred)."""
    names = [s["Name"] for s in synth.STRUCT_DEFINITIONS]
    assert names == ["LocalPlayer", "ZoneInfo", "EntityList"]


def test_localplayer_status_shipped():
    """LocalPlayer is shipped (M3.1 verified); its 8 fields are real."""
    localplayer = next(s for s in synth.STRUCT_DEFINITIONS if s["Name"] == "LocalPlayer")
    assert localplayer["Status"] == "shipped"
    assert len(localplayer["Fields"]) == 8


def test_zoneinfo_status_pending_with_empty_fields():
    """ZoneInfo is pending M3.2 Ghidra; Fields[] is empty."""
    zoneinfo = next(s for s in synth.STRUCT_DEFINITIONS if s["Name"] == "ZoneInfo")
    assert zoneinfo["Status"] == "pending"
    assert zoneinfo["Fields"] == []


def test_entitylist_status_pending_with_empty_fields():
    """EntityList is pending M3.2 Ghidra; Fields[] is empty."""
    entitylist = next(s for s in synth.STRUCT_DEFINITIONS if s["Name"] == "EntityList")
    assert entitylist["Status"] == "pending"
    assert entitylist["Fields"] == []


def test_localplayer_field_offsets_preserved_verbatim():
    """LocalPlayer field offsets/names/types must not drift from M3.1."""
    localplayer = next(s for s in synth.STRUCT_DEFINITIONS if s["Name"] == "LocalPlayer")
    field_map = {f["OffsetHex"]: f for f in localplayer["Fields"]}
    # Pin the 8 known offsets
    expected = {
        "0x304": ("turn_rate", "float32"),
        "0x30C": ("facing_x", "float32"),
        "0x310": ("facing_y", "float32"),
        "0x314": ("facing_z", "float32"),
        "0x31C": ("unknown_float_31c", "float32"),
        "0x320": ("pos_x", "float32"),
        "0x324": ("pos_y", "float32"),
        "0x328": ("pos_z", "float32"),
    }
    for offset_hex, (name, ftype) in expected.items():
        assert offset_hex in field_map, f"offset {offset_hex} missing from LocalPlayer"
        assert field_map[offset_hex]["Name"] == name
        assert field_map[offset_hex]["Type"] == ftype


def test_synthesize_emits_three_structs_in_order():
    """synthesize_catalog emits LocalPlayer, ZoneInfo, EntityList in that order."""
    with tempfile.TemporaryDirectory() as tmp:
        modrm_path, sig_path = _write_fixtures(tmp, _minimal_modrm_scan(), _empty_signature_catalog())
        catalog = synth.synthesize_catalog(modrm_scan_path=modrm_path, signature_catalog_path=sig_path)
    names = [s["Name"] for s in catalog["Structs"]]
    assert names == ["LocalPlayer", "ZoneInfo", "EntityList"]
    statuses = [s["Status"] for s in catalog["Structs"]]
    assert statuses == ["shipped", "pending", "pending"]


def test_synthesize_emits_status_field_per_struct():
    """Each struct in the catalog has a Status field."""
    with tempfile.TemporaryDirectory() as tmp:
        modrm_path, sig_path = _write_fixtures(tmp, _minimal_modrm_scan(), _empty_signature_catalog())
        catalog = synth.synthesize_catalog(modrm_scan_path=modrm_path, signature_catalog_path=sig_path)
    for struct in catalog["Structs"]:
        assert "Status" in struct
        assert struct["Status"] in ("pending", "in_progress", "shipped")


def test_synthesize_empty_fields_round_trips_schema():
    """The relaxed schema (minItems: 0) accepts ZoneInfo/EntityList with empty Fields[]."""
    with tempfile.TemporaryDirectory() as tmp:
        modrm_path, sig_path = _write_fixtures(tmp, _minimal_modrm_scan(), _empty_signature_catalog())
        catalog = synth.synthesize_catalog(modrm_scan_path=modrm_path, signature_catalog_path=sig_path)
    _validate(catalog)  # raises if schema rejects


def test_confidence_confirmed_when_high_hits_with_riftreader_field():
    """hit_count > 100 AND has RiftReaderField -> 'confirmed'."""
    by_offset = {"0x320": 200}
    with tempfile.TemporaryDirectory() as tmp:
        modrm_path, sig_path = _write_fixtures(tmp, _minimal_modrm_scan(by_offset), _empty_signature_catalog())
        catalog = synth.synthesize_catalog(modrm_scan_path=modrm_path, signature_catalog_path=sig_path)
    pos_x = next(f for f in catalog["Structs"][0]["Fields"] if f["Name"] == "pos_x")
    assert pos_x["Confidence"] == "confirmed"
    assert pos_x["ModRMHitCount"] == 200


def test_confidence_inferred_when_low_hits_with_riftreader_field():
    """0 < hit_count <= 100 AND has RiftReaderField -> 'inferred'."""
    by_offset = {"0x304": 35}  # turn_rate: low hits
    with tempfile.TemporaryDirectory() as tmp:
        modrm_path, sig_path = _write_fixtures(tmp, _minimal_modrm_scan(by_offset), _empty_signature_catalog())
        catalog = synth.synthesize_catalog(modrm_scan_path=modrm_path, signature_catalog_path=sig_path)
    turn_rate = next(f for f in catalog["Structs"][0]["Fields"] if f["Name"] == "turn_rate")
    assert turn_rate["Confidence"] == "inferred"


def test_confidence_tentative_when_no_hits():
    """hit_count == 0 -> 'tentative'."""
    with tempfile.TemporaryDirectory() as tmp:
        modrm_path, sig_path = _write_fixtures(tmp, _minimal_modrm_scan({}), _empty_signature_catalog())
        catalog = synth.synthesize_catalog(modrm_scan_path=modrm_path, signature_catalog_path=sig_path)
    # All LocalPlayer fields should be tentative
    for field in catalog["Structs"][0]["Fields"]:
        assert field["Confidence"] == "tentative"
        assert field["ModRMHitCount"] == 0


def test_classify_confidence_unit():
    """Unit test the pure confidence classifier (2-arg signature)."""
    # hit_count=0, no riftreader_field -> tentative (mapped to "tentative" string in synth)
    assert synth._classify_confidence(0, False) == "tentative"
    # hit_count=0, has riftreader_field -> tentative (no ModRM evidence)
    assert synth._classify_confidence(0, True) == "tentative"
    # 0 < hit_count <= 100, has riftreader_field -> inferred
    assert synth._classify_confidence(50, True) == "inferred"
    # 0 < hit_count <= 100, no riftreader_field -> inferred
    assert synth._classify_confidence(50, False) == "inferred"
    # hit_count > 100, has riftreader_field -> confirmed
    assert synth._classify_confidence(200, True) == "confirmed"
    # hit_count > 100, no riftreader_field -> inferred (no riftreader validation)
    assert synth._classify_confidence(200, False) == "inferred"
    # Boundary: exactly 100 hits + riftreader -> inferred (threshold is >100)
    assert synth._classify_confidence(100, True) == "inferred"
    # Boundary: 101 hits + riftreader -> confirmed
    assert synth._classify_confidence(101, True) == "confirmed"
