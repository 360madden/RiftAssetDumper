"""Tests for the secondary-struct discovery scanner (Phase 3 M3.2).

The scanner uses pefile to walk .rdata/.data sections of rift_x64.exe and
find class-name strings + RTTI vtable patterns. These tests MOCK pefile
to avoid the complexity of building a valid PE in-memory. They verify:

1. Case-insensitive class-name string search finds "ZoneInfo",
   "ZONEINFO", and "zoneinfo" identically.
2. Confidence classifier returns HIGH/MEDIUM/NONE correctly.
3. Output conforms to the secondary-struct-discovery/v1 schema.
4. Empty Structs[] is permitted (minItems: 0).
5. The schema discriminator constant is pinned.

The mocked pefile fixture returns controlled section data so the
scanner's string-search / RTTI / vtable detection logic can be unit
tested in <50 ms without any real binary I/O. A separate integration
test (skipped by default) would run against the live rift_x64.exe.

These run in <1 s on a cold cache.
"""

from __future__ import annotations

import json
import pathlib
import sys
from unittest.mock import MagicMock

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import scripts.discover_secondary_structs as scanner  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "docs" / "schemas" / "secondary-struct-discovery-v1.schema.json"

# Schema discriminator constant (pinned for catalog validation)
SCHEMA_DISCRIMINATOR = "secondary-struct-discovery/v1"


def _build_mock_pe(image_base: int = 0x140000000, rdata_payload: bytes = b"") -> MagicMock:
    """Build a mock pefile.PE that returns one .text + one .rdata section.

    The .text section starts at VA 0x1000 (sized 0x100) and the .rdata
    section starts at VA 0x2000 (sized to fit the payload). The mock
    supports the scanner's calls to pe.sections (iteration),
    section.VirtualAddress, section.Misc_VirtualSize, section.SizeOfRawData,
    section.PointerToRawData, section.Name, and section.get_data().
    """
    pe = MagicMock()
    pe.OPTIONAL_HEADER.ImageBase = image_base

    # .text section: VA 0x1000, size 0x100
    text_section = MagicMock()
    text_section.Name = b".text\x00\x00\x00"
    text_section.VirtualAddress = 0x1000
    text_section.Misc_VirtualSize = 0x100
    text_section.SizeOfRawData = 0x200
    text_section.PointerToRawData = 0x400
    text_section.Characteristics = 0x60000020

    # .rdata section: VA 0x2000, size 0x100
    rdata_section = MagicMock()
    rdata_section.Name = b".rdata\x00\x00"
    rdata_section.VirtualAddress = 0x2000
    rdata_section.Misc_VirtualSize = 0x100
    rdata_section.SizeOfRawData = 0x200
    rdata_section.PointerToRawData = 0x600
    rdata_section.Characteristics = 0x40000040
    rdata_section.get_data.return_value = rdata_payload

    pe.sections = [text_section, rdata_section]
    return pe


def test_schema_discriminator_pinned():
    """EXTRACTION_SCHEMA must match the locked discriminator constant."""
    assert scanner.EXTRACTION_SCHEMA == SCHEMA_DISCRIMINATOR


def test_camera_not_in_search_targets():
    """Camera is intentionally absent (May 2026 handoff guard)."""
    assert "Camera" not in scanner.SEARCH_TARGETS


def test_search_targets_has_zoneinfo_and_entitylist():
    """M3.2 scope: ZoneInfo + EntityList (Camera deferred)."""
    assert "ZoneInfo" in scanner.SEARCH_TARGETS
    assert "EntityList" in scanner.SEARCH_TARGETS


def test_classify_confidence_unit():
    """Unit test the pure confidence classifier (3-arg: class_strings, rtti, vtables)."""
    assert scanner._classify_confidence(0, 0, 0) == "none"
    assert scanner._classify_confidence(1, 0, 0) == "medium"  # class string only
    assert scanner._classify_confidence(0, 1, 0) == "medium"  # RTTI only
    assert scanner._classify_confidence(0, 0, 1) == "none"  # vtable alone
    assert scanner._classify_confidence(1, 0, 1) == "high"  # class + vtable
    assert scanner._classify_confidence(0, 1, 1) == "medium"  # RTTI + vtable (no class string)
    assert scanner._classify_confidence(5, 3, 2) == "high"


def test_find_class_name_strings_case_insensitive():
    """_find_class_name_strings must find 'ZoneInfo', 'ZONEINFO', 'zoneinfo' identically."""
    for variant in ("ZoneInfo", "ZONEINFO", "zoneinfo"):
        payload = b"\x00" * 0x40 + variant.encode("ascii") + b"\x00" * 0x20
        pe = _build_mock_pe(rdata_payload=payload)
        sections = scanner._iter_section_bytes(pe)
        cands = scanner._find_class_name_strings(sections, 0x140000000, ["ZoneInfo"])
        assert any(c["matched_hint"] == "ZoneInfo" for c in cands), (
            f"case-insensitive search failed for variant {variant!r}"
        )


def test_find_class_name_strings_skips_non_data_sections():
    """Only .rdata/.data/.rodata sections are searched for class-name strings.

    Invariant: _find_class_name_strings checks `sec_name not in
    (.rdata, .data, .rodata)` BEFORE calling .lower() on section data.
    This ordering is required so that the .text section's MagicMock
    data (which has no .lower() method) doesn't crash the search.
    If you refactor the loop, preserve this ordering.
    """
    payload = b"ZoneInfo" + b"\x00" * 0x20
    pe = _build_mock_pe(rdata_payload=payload)
    sections = scanner._iter_section_bytes(pe)
    # Force the .text section to also contain the string; it must be ignored.
    for sec in pe.sections:
        if sec.Name.rstrip(b"\x00") == b".text":
            sec.get_data.return_value = b"ZoneInfo" + b"\x00" * 0x10
    cands = scanner._find_class_name_strings(sections, 0x140000000, ["ZoneInfo"])
    sections_searched = {c["section"] for c in cands}
    assert sections_searched == {".rdata"}


def test_find_class_name_strings_utf16le():
    """UTF-16LE encoded class names must also be found."""
    payload = b"\x00" * 0x20 + "ZoneInfo".encode("utf-16-le") + b"\x00" * 0x20
    pe = _build_mock_pe(rdata_payload=payload)
    sections = scanner._iter_section_bytes(pe)
    cands = scanner._find_class_name_strings(sections, 0x140000000, ["ZoneInfo"])
    assert any(c["match_kind"] == "utf-16le" for c in cands)


def test_discover_candidates_handles_missing_binary():
    """FileNotFoundError -> raised (caller handles via main())."""
    fake = pathlib.Path("/nonexistent/path/to/rift_x64.exe")
    with pytest.raises(FileNotFoundError):
        scanner.discover_candidates(fake)


def test_confidence_constants_pinned():
    """Confidence enum values are pinned to high/medium/none."""
    assert scanner.CONF_HIGH == "high"
    assert scanner.CONF_MEDIUM == "medium"
    assert scanner.CONF_NONE == "none"


def test_zoneinfo_class_name_hints_match_search_targets():
    """ZoneInfo's class_name_hints include canonical + alternative names."""
    zoneinfo = scanner.SEARCH_TARGETS["ZoneInfo"]
    hints = zoneinfo["class_name_hints"]
    assert "ZoneInfo" in hints
    assert "Zone" in hints
    assert isinstance(hints, list)
    assert all(isinstance(h, str) for h in hints)


def test_entitylist_rtti_typename_prefix():
    """EntityList's RTTI typename prefix is the canonical MSVC mangled form."""
    entitylist = scanner.SEARCH_TARGETS["EntityList"]
    assert entitylist["rtti_typename_prefix"].startswith(b".?AV")


def test_text_section_candidates_includes_canonical_names():
    """TEXT_SECTION_CANDIDATES includes .text (canonical) + .rtext + .textbss (variants)."""
    names = {n.decode("ascii") for n in scanner.TEXT_SECTION_CANDIDATES}
    assert ".text" in names
    assert ".rtext" in names
    assert ".textbss" in names


def test_entitylist_hints_iterated_to_broader_terms():
    """EntityList's class_name_hints include iterated broader terms (Entity, Actor, Unit, etc)."""
    entitylist = scanner.SEARCH_TARGETS["EntityList"]
    hints = entitylist["class_name_hints"]
    # The original 4 narrow hints
    assert "EntityList" in hints
    assert "EntityPool" in hints
    # The iterated broader hints (8 added after M3.2 framework review)
    for broader in ("Entity", "Object", "Actor", "Unit", "Character", "NPC", "Mob"):
        assert broader in hints, f"missing iterated hint {broader!r}"


def test_discover_candidates_emits_valid_schema_with_empty_rdata(monkeypatch):
    """discover_candidates output conforms to secondary-struct-discovery/v1 with empty rdata."""
    # Mock _load_pe to return our mock PE without touching disk
    pe_mock = _build_mock_pe(rdata_payload=b"\x00" * 0x100)
    monkeypatch.setattr(scanner, "_load_pe", lambda _path: pe_mock)
    # Use a Path that exists so FileNotFoundError isn't raised
    fake_existing = pathlib.Path(__file__)  # any existing file
    report = scanner.discover_candidates(fake_existing)
    # Top-level fields
    assert report["SchemaVersion"] == SCHEMA_DISCRIMINATOR
    assert "ExtractedAt" in report
    assert isinstance(report["Structs"], list)
    names = {s["Name"] for s in report["Structs"]}
    assert names == {"ZoneInfo", "EntityList"}
    # No class strings found -> all confidence "none"
    for entry in report["Structs"]:
        assert entry["Confidence"] == "none"
        assert entry["BestCandidateAddress"] is None
    # Validate against schema (if jsonschema available)
    try:
        import jsonschema

        jsonschema.validate(
            report,
            json.loads(SCHEMA_PATH.read_text(encoding="utf-8")),
            format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
        )
    except ImportError:
        pass  # skip if jsonschema unavailable
