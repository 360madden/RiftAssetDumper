"""Phase 3 M3.2 secondary-struct discovery scanner.

Searches ``rift_x64.exe`` for candidate vtable/RTTI addresses for the
secondary structs the M3.2 milestone targets (ZoneInfo, EntityList). Uses
``pefile`` to parse the PE structure and walk .rdata/.data for class-name
strings + nearby vtable patterns.

This is a **discovery helper**, not a definitive address provider. The
output is a list of candidate addresses with confidence scores. A Ghidra
FunctionSiteSurvey run against each top-confidence candidate is the next
step to confirm or refute each candidate.

Output schema: ``secondary-struct-discovery/v1`` (see ``EXTRACTION_SCHEMA``).

Usage::

    # Scan the live install
    python scripts/discover_secondary_structs.py

    # Scan an explicit binary + write to a custom path
    python scripts/discover_secondary_structs.py \\
        --binary "C:/path/to/rift_x64.exe" \\
        --out Exports/binary-phase3/secondary-struct-discovery.json

Exit codes:
    0 — success (regardless of whether candidates were found)
    1 — binary not found or pefile parse failure
    2 — output write failure
"""

from __future__ import annotations

import argparse
import json
import struct as _struct
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Output schema discriminator (pinned constant for catalog validation)
EXTRACTION_SCHEMA = "secondary-struct-discovery/v1"

# Default live install path (mirrors scripts/rift_workflow.py::DEFAULT_ROOT)
DEFAULT_BINARY = Path("C:/Program Files (x86)/Glyph/Games/RIFT/Live/rift_x64.exe")
DEFAULT_OUT = REPO_ROOT / "Exports" / "binary-phase3" / "secondary-struct-discovery.json"

# Phase 3 M3.2 secondary struct targets (Camera intentionally omitted — see
# docs/handoffs/2026-05-08-160739-rift-assets-semantic-python-nidatastream-handoff.md
# for the "Do not touch RiftReader_camera_feature WIP unless explicitly
# authorized" guard).
SEARCH_TARGETS: dict[str, dict[str, Any]] = {
    "ZoneInfo": {
        "class_name_hints": ["ZoneInfo", "Zone", "WorldZone", "ZoneData"],
        "vtable_marker_substrings": ["ZoneInfo", "Zone"],
        "rtti_typename_prefix": b".?AVZoneInfo",
        "description": "Per-zone data structure (zone id, name, weather, level range).",
        "evidence_basis": "modrm-memory-access-scan/v1 + string-table scan",
    },
    "EntityList": {
        "class_name_hints": [
            "EntityList",
            "EntityPool",
            "ObjectList",
            "ActorList",
            "Entity",
            "Object",
            "Actor",
            "World",
            "Unit",
            "Character",
            "NPC",
            "Mob",
        ],
        "vtable_marker_substrings": ["Entity", "Actor", "Object", "Unit"],
        "rtti_typename_prefix": b".?AVEntity",
        "description": "Live entity / actor enumeration (id, refcount, type).",
        "evidence_basis": "modrm-memory-access-scan/v1 + string-table scan",
    },
}

# .text section heuristic: addresses that point into this section are
# likely function pointers (vtable slots point to .text). pefile exposes
# each section as a SectionStructure; we check VirtualAddress ranges.
TEXT_SECTION_CANDIDATES = (b".text", b".rtext", b".textbss")

# Confidence scoring constants
CONF_HIGH = "high"  # both class-name string AND vtable pattern found within 64 bytes
CONF_MEDIUM = "medium"  # only class-name string OR only RTTI typename
CONF_NONE = "none"  # no candidates discovered

# Tuple type alias for clarity
SectionTuple = tuple[str, bytes, int, int]


def _load_pe(binary_path: Path) -> Any:
    """Load a PE file via pefile. Raises FileNotFoundError on missing path."""
    if not binary_path.exists():
        raise FileNotFoundError(f"PE binary not found: {binary_path}")
    import pefile  # pefile is declared in pyproject.toml [project].dependencies

    return pefile.PE(str(binary_path), fast_load=False)


def _iter_section_bytes(pe: Any) -> list[SectionTuple]:
    """Return a list of (section_name, data, va_start, va_size) for each section.

    va_size is the section's virtual size (or raw size as fallback). The
    4th element of the tuple is va_size rather than va_end because no
    caller needs the end address.
    """
    sections: list[SectionTuple] = []
    for section in pe.sections:
        name = section.Name.rstrip(b"\x00").decode("ascii", errors="ignore")
        data = section.get_data()
        va_start = section.VirtualAddress
        va_size = section.Misc_VirtualSize or section.SizeOfRawData
        sections.append((name, data, va_start, va_size))
    return sections


def _is_text_section(pe: Any, rva: int) -> bool:
    """Return True if the RVA falls within a code section (.text, .rtext, .textbss)."""
    for section in pe.sections:
        name = section.Name.rstrip(b"\x00")
        if name in TEXT_SECTION_CANDIDATES:
            if section.VirtualAddress <= rva < section.VirtualAddress + section.Misc_VirtualSize:
                return True
    return False


def _find_class_name_strings(sections: list[SectionTuple], image_base: int, hints: list[str]) -> list[dict[str, Any]]:
    """Search for ASCII/UTF-16LE class-name strings. Returns file-offset candidates."""
    candidates: list[dict[str, Any]] = []
    for sec_name, data, va_start, _ in sections:
        if sec_name not in (".rdata", ".data", ".rodata"):
            continue
        # Lowercase the section data once for case-insensitive search.
        # data.lower() has the same byte length as data, so va_start + idx
        # offsets remain valid for the original (mixed-case) data.
        data_lower = data.lower()
        for hint in hints:
            needle_ascii = hint.lower().encode("ascii")
            needle_wide = hint.lower().encode("utf-16-le")
            start = 0
            while True:
                idx = data_lower.find(needle_ascii, start)
                if idx == -1:
                    break
                rva = va_start + idx
                candidates.append(
                    {
                        "rva": rva,
                        "va": f"0x{image_base + rva:x}",
                        "section": sec_name,
                        "match_kind": "ascii",
                        "matched_hint": hint,
                    }
                )
                start = idx + len(needle_ascii)
            start = 0
            while True:
                idx = data_lower.find(needle_wide, start)
                if idx == -1:
                    break
                rva = va_start + idx
                candidates.append(
                    {
                        "rva": rva,
                        "va": f"0x{image_base + rva:x}",
                        "section": sec_name,
                        "match_kind": "utf-16le",
                        "matched_hint": hint,
                    }
                )
                start = idx + len(needle_wide)
    return candidates


def _find_rtti_typenames(sections: list[SectionTuple], image_base: int, prefix: bytes) -> list[dict[str, Any]]:
    """Search for RTTI TypeDescriptor name strings (e.g. .?AVZoneInfo@@)."""
    candidates: list[dict[str, Any]] = []
    for sec_name, data, va_start, _ in sections:
        if sec_name != ".rdata":
            continue
        start = 0
        while True:
            idx = data.find(prefix, start)
            if idx == -1:
                break
            # Try to read the full mangled name (null-terminated).
            end = data.find(b"\x00", idx)
            if end == -1 or end - idx > 256:
                end = idx + 64
            raw = data[idx:end]
            rva = va_start + idx
            candidates.append(
                {
                    "rva": rva,
                    "va": f"0x{image_base + rva:x}",
                    "section": sec_name,
                    "match_kind": "rtti-typename",
                    "matched_hint": raw.split(b"@@")[0].decode("ascii", errors="ignore"),
                }
            )
            start = idx + len(prefix)
    return candidates


def _find_vtable_nearby(
    pe: Any, sections: list[SectionTuple], image_base: int, ref_rva: int, window: int = 64
) -> list[dict[str, Any]]:
    """Look for vtable-shaped patterns (8-byte aligned pointers to .text) near ref_rva.

    The MSVC RTTI layout puts the vtable address ~16-32 bytes before the
    TypeDescriptor pointer. We scan a small window for 8-byte aligned
    values that resolve to .text addresses.
    """
    candidates: list[dict[str, Any]] = []
    for sec_name, data, _va_start_unused, _ in sections:
        if sec_name != ".rdata":
            continue
        # Find the file offset of ref_rva.
        ref_offset = -1
        for sec in pe.sections:
            sec_file_start = sec.PointerToRawData
            sec_file_end = sec_file_start + sec.SizeOfRawData
            if sec.VirtualAddress <= ref_rva < sec.VirtualAddress + (sec.Misc_VirtualSize or sec.SizeOfRawData):
                ref_offset = sec_file_start + (ref_rva - sec.VirtualAddress)
                break
        if ref_offset < 0:
            continue
        lo = max(0, ref_offset - window)
        hi = min(len(data), ref_offset + window)
        if lo >= hi:
            continue
        aligned_lo = lo - (lo % 8)
        for off in range(aligned_lo, hi - 7, 8):
            try:
                (candidate_rva,) = _struct.unpack_from("<Q", data, off)
            except _struct.error:
                continue
            if candidate_rva == 0 or candidate_rva > 0x7FFFFFFFFFFF:
                continue
            if not _is_text_section(pe, candidate_rva):
                continue
            # Convert the 8-byte-aligned file offset to its RVA so we can
            # report the vtable's VA (the vtable array base, which IS the
            # address of the first 8-byte slot we just read).
            vtable_va_rva = -1
            for sec in pe.sections:
                sec_file_start = sec.PointerToRawData
                sec_file_end = sec_file_start + sec.SizeOfRawData
                if sec_file_start <= off < sec_file_end:
                    vtable_va_rva = sec.VirtualAddress + (off - sec_file_start)
                    break
            if vtable_va_rva < 0:
                continue
            candidates.append(
                {
                    "vtable_va": f"0x{image_base + vtable_va_rva:x}",
                    "first_slot_va": f"0x{image_base + candidate_rva:x}",
                    "ref_distance_bytes": off - ref_offset,
                }
            )
    return candidates


def _classify_confidence(n_class_strings: int, n_rtti_typenames: int, n_vtables_nearby: int) -> str:
    """Score the overall confidence based on discovered evidence count.

    HIGH    — class-name string AND vtable-shaped pattern found nearby
    MEDIUM  — any class-name string OR any RTTI typename discovered
    NONE    — no evidence found (target likely absent from this binary)
    """
    if n_class_strings >= 1 and n_vtables_nearby >= 1:
        return CONF_HIGH
    if n_class_strings >= 1 or n_rtti_typenames >= 1:
        return CONF_MEDIUM
    return CONF_NONE


def discover_candidates(binary_path: Path) -> dict[str, Any]:
    """Run the full discovery scan against the binary. Returns the report dict."""
    pe = _load_pe(binary_path)
    image_base = pe.OPTIONAL_HEADER.ImageBase
    sections = _iter_section_bytes(pe)

    structs: list[dict[str, Any]] = []
    for struct_name, config in SEARCH_TARGETS.items():
        class_strings = _find_class_name_strings(sections, image_base, config["class_name_hints"])
        rtti_typenames = _find_rtti_typenames(sections, image_base, config["rtti_typename_prefix"])
        # For each RTTI typename, look for a vtable within ±64 bytes.
        vtable_candidates: list[dict[str, Any]] = []
        for rt in rtti_typenames:
            vtable_candidates.extend(_find_vtable_nearby(pe, sections, image_base, rt["rva"]))
        # Also try the class-string RTTI vicinity (some compilers put the
        # type name in .rdata near the vtable).
        for cs in class_strings:
            vtable_candidates.extend(_find_vtable_nearby(pe, sections, image_base, cs["rva"], window=128))

        confidence = _classify_confidence(len(class_strings), len(rtti_typenames), len(vtable_candidates))
        # Pick the best vtable candidate (closest RTTI reference).
        best_vtable: dict[str, Any] | None = None
        if vtable_candidates:
            best_vtable = min(vtable_candidates, key=lambda v: abs(v.get("ref_distance_bytes", 9999)))

        # Pick the best class-string candidate (prefer ascii over utf-16le).
        ascii_strings = [s for s in class_strings if s["match_kind"] == "ascii"]
        best_string = ascii_strings[0] if ascii_strings else (class_strings[0] if class_strings else None)

        # If we have a best vtable, that's the candidate Ghidra target.
        candidate_address: str | None = None
        if best_vtable is not None:
            candidate_address = best_vtable["vtable_va"]
        elif best_string is not None:
            candidate_address = best_string["va"]

        structs.append(
            {
                "Name": struct_name,
                "Description": config["description"],
                "EvidenceBasis": config["evidence_basis"],
                "ClassNameCandidates": class_strings[:10],  # cap output
                "RTTITypeNameCandidates": rtti_typenames[:10],
                "VTableCandidates": vtable_candidates[:10],
                "BestCandidateAddress": candidate_address,
                "Confidence": confidence,
            }
        )

    return {
        "SchemaVersion": EXTRACTION_SCHEMA,
        "BinaryTarget": binary_path.name,
        "ImageBase": f"0x{image_base:x}",
        "ExtractedAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Structs": structs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--binary",
        type=Path,
        default=DEFAULT_BINARY,
        help=f"Path to rift_x64.exe (default: {DEFAULT_BINARY}).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output JSON path (default: {DEFAULT_OUT}).",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Also validate the output against the embedded schema (if jsonschema available).",
    )
    args = parser.parse_args(argv)

    try:
        report = discover_candidates(args.binary)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: pefile parse failed on {args.binary}: {exc}", file=sys.stderr)
        return 1

    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: failed to write {args.out}: {exc}", file=sys.stderr)
        return 2

    print(f"==> Discovered {len(report['Structs'])} struct candidate(s) in {args.binary.name}")
    for entry in report["Structs"]:
        addr = entry["BestCandidateAddress"] or "(none)"
        n_class = len(entry["ClassNameCandidates"])
        n_rtti = len(entry["RTTITypeNameCandidates"])
        n_vtab = len(entry["VTableCandidates"])
        print(
            f"    {entry['Name']}: {entry['Confidence']} confidence, "
            f"best_addr={addr}, "
            f"class_strings={n_class}, rtti_typenames={n_rtti}, vtable_candidates={n_vtab}"
        )

    if args.validate:
        try:
            import jsonschema

            schema_path = REPO_ROOT / "docs" / "schemas" / "secondary-struct-discovery-v1.schema.json"
            if not schema_path.exists():
                print(f"WARNING: schema not found at {schema_path}; skipping validation", file=sys.stderr)
            else:
                jsonschema.validate(
                    report,
                    json.loads(schema_path.read_text(encoding="utf-8")),
                    format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
                )
                print("==> Schema validation: PASS")
        except ImportError:
            print("WARNING: jsonschema not installed; skipping validation", file=sys.stderr)
        except Exception as exc:
            print(f"ERROR: schema validation failed: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
