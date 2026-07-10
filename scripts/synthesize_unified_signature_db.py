#!/usr/bin/env python3
"""Synthesize the Phase 5 unified binary-signature database.

Reads the Phase 2 signature catalog (anchor-level byte signatures + uniqueness
data) and the Phase 3 struct-layout catalog (struct-level field annotations,
ModRM hit counts, Ghidra findings), then produces a single consumer-facing
``rift-x64-signature-database.json`` at ``Exports/binary-phase5/``.

The output conforms to ``docs/schemas/binary-signatures-v1.schema.json`` --
no new schema is introduced. Struct layouts are attached to anchor records
that the Phase 3 catalog flags as ``SignatureAnchors``.

Usage::

    python scripts/synthesize_unified_signature_db.py
    python scripts/synthesize_unified_signature_db.py --validate
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# Canonical PascalCase mapping for Phase 3 catalog keys. Older catalogs may
# emit lowercase/camelCase keys; normalize once on load so downstream code
# only has to handle one shape.
_PHASE3_KEY_MAP: dict[str, str] = {
    "name": "Name",
    "description": "Description",
    "fields": "Fields",
    "baseregisters": "BaseRegisters",
    "totalmodrmhits": "TotalModRMHits",
    "signatureanchors": "SignatureAnchors",
    "offset": "Offset",
    "offsethex": "OffsetHex",
    "type": "Type",
    "confidence": "Confidence",
    "modrmhitcount": "ModRMHitCount",
    "riftreaderfield": "RiftReaderField",
    "notes": "Notes",
}


def _normalize_phase3_keys(obj: Any) -> Any:
    """Recursively normalize Phase 3 catalog dict keys to canonical PascalCase."""
    if isinstance(obj, dict):
        return {_PHASE3_KEY_MAP.get(k.lower(), k): _normalize_phase3_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_phase3_keys(item) for item in obj]
    return obj


def _build_enriched_struct_layout(
    *,
    struct_record: dict[str, Any],
    base_register_counts_from_phase3: dict[str, int],
    total_modrm_hits_from_phase3: int,
) -> dict[str, Any]:
    """Attach Phase 3 ModRM-hit + Notes annotations to each Phase-3 field.

    The output schema for each field is:
        { Offset, OffsetHex, Name, Type, Confidence,
          RiftReaderField, ModRMHitCount, Notes }

    The struct record owns the descriptive ``Description`` and the anchor
    catalog owns the binary signature context; we intentionally keep the
    StructLayout itself self-contained so RiftReader can consume the
    embedded StructLayout in a single anchor pass.
    """
    enriched_fields: list[dict[str, Any]] = []
    src_fields = struct_record.get("Fields", []) if isinstance(struct_record, dict) else []
    for f in src_fields:
        enriched_fields.append(
            {
                "Offset": int(f.get("Offset", 0)),
                "OffsetHex": f.get("OffsetHex", "0x0"),
                "Name": str(f.get("Name", "")),
                "Type": str(f.get("Type", "float32")),
                "Confidence": str(f.get("Confidence", "inferred")),
                "RiftReaderField": str(f.get("RiftReaderField", "")),
                "ModRMHitCount": int(f.get("ModRMHitCount", 0)),
                "Notes": str(f.get("Notes", "")),
            }
        )
    # Description: prefer struct_record.Description, then fall back to the first
    # field's Name so a struct with no top-level description still produces a
    # human-readable label.
    desc = ""
    if isinstance(struct_record, dict):
        desc = str(struct_record.get("Description") or (enriched_fields[0].get("Name", "") if enriched_fields else ""))
    return {
        "Description": desc,
        "Fields": enriched_fields,
        # Optional struct-level parsing aids; match the wider binary-signatures contract.
        "BaseRegisters": base_register_counts_from_phase3,
        "TotalModRMHits": total_modrm_hits_from_phase3,
    }


def synthesize_database(
    *,
    phase2_catalog_path: Path | None = None,
    phase3_catalog_path: Path | None = None,
) -> dict[str, Any]:
    """Merge Phase 2 + Phase 3 into a unified binary-signature database."""

    phase2_catalog_path = phase2_catalog_path or (
        REPO_ROOT / "Exports" / "binary-phase2" / "rift-x64-signature-catalog.json"
    )
    phase3_catalog_path = phase3_catalog_path or (
        REPO_ROOT / "Exports" / "binary-phase3" / "struct-layout-catalog.json"
    )

    if not phase2_catalog_path.exists():
        raise FileNotFoundError(f"Phase 2 catalog not found: {phase2_catalog_path}")
    phase2 = _load_json(phase2_catalog_path)

    # Phase 3 is optional: if absent, we still emit a valid DB using Phase 2's
    # embedded StructLayout (the vtable-dispatch anchor already has one).
    phase3_structs: list[dict[str, Any]] = []
    if phase3_catalog_path.exists():
        try:
            phase3 = _normalize_phase3_keys(_load_json(phase3_catalog_path))
            phase3_structs = list(phase3.get("Structs", []))
        except Exception as exc:
            print(
                f"WARNING: could not parse Phase 3 catalog at {phase3_catalog_path}: {exc}",
                file=sys.stderr,
            )
            phase3_structs = []

    # Defensive guard: schema requires minItems 1 on Anchors. If the
    # upstream Phase 2 catalog is empty, fail loudly rather than emitting
    # a silently-invalid DB.
    if not phase2.get("Anchors"):
        raise ValueError(
            f"Phase 2 catalog has empty Anchors[]: {phase2_catalog_path} "
            "(schema requires minItems: 1). Run synthesize_signature_catalog.py first."
        )

    # Build a struct-name -> struct-record index. Phase 3 keeps a flat list.
    struct_index: dict[str, dict[str, Any]] = {}
    # Map anchor name -> first struct name that claims it via SignatureAnchors.
    anchor_to_struct_name: dict[str, str] = {}
    for s in phase3_structs:
        if isinstance(s, dict):
            name = str(s.get("Name", ""))
            if name:
                struct_index[name] = s
                for anchor_name in s.get("SignatureAnchors", []):
                    if anchor_name not in anchor_to_struct_name:
                        anchor_to_struct_name[anchor_name] = name

    # Iterate anchors and enrich those that match a Phase 3 struct name.
    enriched_anchors: list[dict[str, Any]] = []
    attached_struct_names: set[str] = set()
    for anchor in copy.deepcopy(phase2.get("Anchors", [])):
        anchor_name = anchor.get("Name", "")
        # Prefer the explicit Phase 3 SignatureAnchors mapping.
        candidate_struct_name = anchor_to_struct_name.get(anchor_name, "")
        # Fallback for backwards compatibility with older catalogs/tests.
        if not candidate_struct_name and (
            anchor_name == "vtable-dispatch" or isinstance(anchor.get("StructLayout"), dict)
        ):
            candidate_struct_name = "LocalPlayer"
        # If we have a richer struct in Phase 3, replace the embedded layout.
        if candidate_struct_name and candidate_struct_name in struct_index:
            struct_record = struct_index[candidate_struct_name]
            base_registers = dict(struct_record.get("BaseRegisters", {}))
            total_modrm_hits = int(struct_record.get("TotalModRMHits", 0))
            anchor["StructLayout"] = _build_enriched_struct_layout(
                struct_record=struct_record,
                base_register_counts_from_phase3=base_registers,
                total_modrm_hits_from_phase3=total_modrm_hits,
            )
            attached_struct_names.add(candidate_struct_name)

        enriched_anchors.append(anchor)

    # Pull Ghidra findings from the Phase 3 catalog (corrections narrative that
    # justifies the safety-boundary contract for the LocalPlayer struct).
    # Schema enum-locks GhidraFindings to 4 known keys; surfaces unrecognized
    # keys with a WARNING rather than silently dropping them.
    schema_enum_keys = {
        "PreviousCallback0x320",
        "PreviousCallback0x328",
        "PropertyWalkerArchitecture",
        "ActualAccessPattern",
    }
    ghidra_findings: dict[str, str] = {}
    if phase3_catalog_path.exists():
        try:
            phase3_doc = _load_json(phase3_catalog_path)
            upstream_findings = phase3_doc.get("GhidraFindings", {})
            unknown_keys: list[str] = []
            for k, v in upstream_findings.items():
                if isinstance(v, str) and k in schema_enum_keys:
                    ghidra_findings[k] = v
                elif isinstance(v, str):
                    unknown_keys.append(k)
            if unknown_keys:
                print(
                    f"WARNING: dropped unknown GhidraFindings keys not in schema enum "
                    f"({sorted(unknown_keys)}). Bump schema or extend enum to preserve.",
                    file=sys.stderr,
                )
        except Exception as exc:
            # The catalog is still valid as a scanning-rule object without the
            # prose, but log a warning so the safety-boundary narrative gap
            # doesn't go unnoticed during schema validation.
            print(
                f"WARNING: could not parse GhidraFindings from {phase3_catalog_path}: {exc}",
                file=sys.stderr,
            )

    return {
        # Reuse the binary-signatures/v1 schema verbatim.
        "SchemaVersion": phase2.get("SchemaVersion", "binary-signatures/v1"),
        "BinaryTarget": phase2.get("BinaryTarget", "rift_x64.exe"),
        "BinaryVersion": phase2.get(
            "BinaryVersion",
            {
                "PEFileVersion": "0",
                "PETimestamp": 0,
                "PETimestampUTC": "",
                "FileSizeBytes": 0,
            },
        ),
        "ImageBase": phase2.get("ImageBase", "0x140000000"),
        "TextSection": phase2.get("TextSection", {"VirtualAddress": "0x1000", "RawSize": 0}),
        "ExtractedAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "WildcardPolicy": phase2.get(
            "WildcardPolicy",
            "Relative addresses (E8/E9 call/jump rel32, 8B/05 RIP-relative disp32), "
            "ModRM [reg+disp32] displacements, and embedded absolute addresses are "
            "masked as ??. Opcode bytes and register encodings are preserved.",
        ),
        "CandidateOnly": True,
        "Provenance": {
            "DiscoveryMethod": "modrm-cluster-heuristic",
            "ValidationMethod": "full-binary-uniqueness-scan",
            "ModRMScannerVersion": "modrm-memory-access-scan/v1",
            "SignatureMatchVersion": "signature-match-report/v1",
            "CrossCheckerVersion": "synthesize-unified-signature-db/v1",
            "Phase2CatalogPath": str(
                phase2_catalog_path.relative_to(REPO_ROOT)
                if phase2_catalog_path.is_relative_to(REPO_ROOT)
                else phase2_catalog_path
            ),
            "Phase3CatalogPath": str(
                phase3_catalog_path.relative_to(REPO_ROOT)
                if phase3_catalog_path.is_relative_to(REPO_ROOT)
                else phase3_catalog_path
            ),
            "GhidraFindings": ghidra_findings,
        },
        "Anchors": enriched_anchors,
        "Summary": {
            "TotalAnchors": len(enriched_anchors),
            "UniqueSignatures": sum(1 for a in enriched_anchors if a.get("UniquenessVerified")),
            "NonUniqueSignatures": sum(1 for a in enriched_anchors if not a.get("UniquenessVerified")),
            "StabilityTier1Count": sum(1 for a in enriched_anchors if a.get("StabilityTier") == 1),
            "StabilityTier2Count": sum(1 for a in enriched_anchors if a.get("StabilityTier") == 2),
            "StabilityTier3Count": sum(1 for a in enriched_anchors if a.get("StabilityTier") == 3),
            "AttachedStructCount": len(attached_struct_names),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "Exports" / "binary-phase5" / "rift-x64-signature-database.json",
        help="Output path for the unified database.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Also validate the output against binary-signatures-v1 schema.",
    )
    parser.add_argument(
        "--phase2-catalog",
        type=Path,
        default=None,
        help="Override path to rift-x64-signature-catalog.json.",
    )
    parser.add_argument(
        "--phase3-catalog",
        type=Path,
        default=None,
        help="Override path to struct-layout-catalog.json.",
    )
    args = parser.parse_args(argv)

    db = synthesize_database(
        phase2_catalog_path=args.phase2_catalog,
        phase3_catalog_path=args.phase3_catalog,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(db, indent=2), encoding="utf-8")
    s = db["Summary"]
    print(f"==> Unified DB synthesized -> {args.out}")
    print(f"    Anchors: {s['TotalAnchors']} (unique={s['UniqueSignatures']}, non-unique={s['NonUniqueSignatures']})")
    print(f"    Tiers: 1={s['StabilityTier1Count']}, 2={s['StabilityTier2Count']}, 3={s['StabilityTier3Count']}")
    print(f"    Attached struct count: {s['AttachedStructCount']}")

    if args.validate:
        schema_path = REPO_ROOT / "docs" / "schemas" / "binary-signatures-v1.schema.json"
        if not schema_path.exists():
            print(f"ERROR: Schema not found at {schema_path}", file=sys.stderr)
            return 1
        schema = _load_json(schema_path)
        try:
            import jsonschema

            jsonschema.validate(db, schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)
        except ImportError:
            print(
                "WARNING: jsonschema not installed; falling back to lightweight checks",
                file=sys.stderr,
            )
            if db.get("SchemaVersion") != schema.get("properties", {}).get("SchemaVersion", {}).get("const"):
                print("ERROR: SchemaVersion mismatch", file=sys.stderr)
                return 1
            if not isinstance(db.get("Anchors"), list) or len(db["Anchors"]) == 0:
                print("ERROR: Anchors must be a non-empty array", file=sys.stderr)
                return 1
        except jsonschema.ValidationError as exc:
            print(f"ERROR: Schema validation failed: {exc}", file=sys.stderr)
            if exc.path:
                print(f"    at: {'/'.join(str(p) for p in exc.path)}", file=sys.stderr)
            return 1
        print("==> Schema validation: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
