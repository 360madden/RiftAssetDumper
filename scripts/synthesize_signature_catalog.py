#!/usr/bin/env python3
"""Synthesize the formal Phase 2 binary-signature catalog.

Reads the Phase 1 target manifest, Phase 2 cluster signature candidates,
and the ModRM scan report, then produces a schema-compliant
``rift-x64-signature-catalog.json`` at ``Exports/binary-phase2/``.

Output conforms to ``docs/schemas/binary-signatures-v1.schema.json``.

Usage::

    python scripts/synthesize_signature_catalog.py
    python scripts/synthesize_signature_catalog.py --validate
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _derive_pointer_resolution(anchor_name: str, sig_hex: str) -> dict[str, Any]:
    """Heuristic: classify a cluster signature by its likely pointer resolution method."""
    # vtable-dispatch: zero-wildcard, pure opcode sequence
    if anchor_name == "vtable-dispatch":
        return {
            "Method": "vtable_dispatch",
            "InstructionOffsetToPointer": 0,
            "PointerByteCount": 0,
            "Notes": "No pointer to resolve — this is a C++ virtual dispatch gate. Anchor here, then trace the calling convention to find the concrete struct offset.",
        }
    # Clusters with 4 wildcards: likely have a disp32 (player offset) or rel32
    if "?? ?? ?? ??" in sig_hex:
        return {
            "Method": "direct_register_offset",
            "InstructionOffsetToPointer": 0,
            "PointerByteCount": 0,
            "Notes": "Cluster contains ModRM [base+disp32] instructions with player offsets. Resolve by finding the base register's value at the call site.",
        }
    # Default: no known pointer resolution
    return {
        "Method": "none",
        "InstructionOffsetToPointer": 0,
        "PointerByteCount": 0,
        "Notes": "Pointer resolution not yet determined for this anchor. Run Ghidra FunctionSiteSurvey to map the containing function.",
    }


def synthesize_catalog(
    *,
    target_manifest_path: Path | None = None,
    candidates_path: Path | None = None,
    modrm_scan_path: Path | None = None,
) -> dict[str, Any]:
    """Synthesize the combined binary-signature catalog from Phase 1 + Phase 2 data."""

    # Load binary version info from Phase 1 target manifest
    target_manifest_path = target_manifest_path or (
        REPO_ROOT / "Exports" / "binary-phase1" / "riftreader-target-manifest.json"
    )
    candidates_path = candidates_path or (REPO_ROOT / "Exports" / "binary-phase2" / "signature-candidates.json")
    modrm_scan_path = modrm_scan_path or (REPO_ROOT / "Exports" / "binary-phase1" / "modrm-memory-access-scan.json")

    binary_version: dict[str, Any] = {
        "PEFileVersion": "1781782683",
        "PETimestamp": 1781782683,
        "PETimestampUTC": "2026-06-18T11:38:03Z",
        "FileSizeBytes": 59937216,
    }

    if target_manifest_path.exists():
        manifest = _load_json(target_manifest_path)
        bv = manifest.get("binary_version", {})
        if bv:
            binary_version = {
                "PEFileVersion": str(bv.get("pe_timestamp", "20.6.0.0")),
                "PETimestamp": bv.get("pe_timestamp", 0),
                "PETimestampUTC": bv.get("pe_timestamp_utc", ""),
                "FileSizeBytes": bv.get("file_size_bytes", 0),
            }

    # Load cluster signatures from Phase 2
    anchors: list[dict[str, Any]] = []
    unique_count = 0
    non_unique_count = 0
    tier1_count = 0

    if candidates_path.exists():
        candidates = _load_json(candidates_path)
        for idx, c in enumerate(candidates.get("candidates", [])):
            name = c.get("name") or c.get("cluster") or f"anchor-{idx:02d}"
            sig_hex = c.get("sig_hex", "")
            is_unique = c.get("status") == "UNIQUE"
            if is_unique:
                unique_count += 1
            else:
                non_unique_count += 1

            stability_tier = c.get("stability_tier", 2)
            if stability_tier == 1:
                tier1_count += 1

            anchor: dict[str, Any] = {
                "Name": name,
                "StabilityTier": stability_tier,
                "Description": c.get("description", ""),
                "SignatureHex": sig_hex,
                "SignatureLength": c.get("sig_len")
                or max(len(sig_hex.replace(" ", "").replace("?", "")) // 2 + sig_hex.count("?") // 2, 1),
                "WildcardCount": c.get("wildcard_count", 0),
                "EntryVA": c.get("entry_va", ""),
                "ClusterVA": c.get("cluster_va", ""),
                "UniquenessVerified": is_unique,
                "DiscoveryMethod": "modrm-cluster-heuristic",
                "PointerResolution": _derive_pointer_resolution(name, sig_hex),
                "HitCount": 0,
                "PlayerCoordinateScore": 0.0,
            }

            if not is_unique:
                anchor["FallbackStrategy"] = (
                    "Non-unique signature — requires xref scanning or caller anchoring. "
                    "Do not use for direct scanning without additional context."
                )

            anchors.append(anchor)

    # Enrich with ModRM cluster metadata if available
    if modrm_scan_path.exists():
        modrm = _load_json(modrm_scan_path)
        for cluster in modrm.get("top_clusters", []):
            sig_data = cluster.get("candidate_signature", {})
            sig_hex = sig_data.get("sig_hex", "")

            # Match by signature hex to existing anchor
            for anchor in anchors:
                if anchor["SignatureHex"] == sig_hex:
                    anchor["HitCount"] = cluster.get("hit_count", 0)
                    anchor["BaseRegisterCounts"] = cluster.get("base_register_counts", {})
                    anchor["TargetOffsets"] = sorted(cluster.get("target_offset_counts", {}).keys())
                    break

    # Add LocalPlayerBase struct layout from Phase 1 manifest
    if target_manifest_path.exists():
        manifest = _load_json(target_manifest_path)
        for target in manifest.get("targets", []):
            if target.get("anchor_name") == "LocalPlayerBase":
                fields = target.get("fields", [])
                if fields:
                    struct_fields: list[dict[str, Any]] = []
                    for f in fields:
                        struct_fields.append(
                            {
                                "Offset": f.get("offset", 0),
                                "OffsetHex": f.get("offset_hex", "0x0"),
                                "Name": f.get("name", ""),
                                "Type": f.get("type", "float32"),
                                "Confidence": f.get("confidence", "inferred"),
                            }
                        )
                    # Attach to the first Tier-1 anchor (vtable-dispatch)
                    for anchor in anchors:
                        if anchor["StabilityTier"] == 1 and not anchor.get("StructLayout"):
                            anchor["StructLayout"] = {
                                "Description": "LocalPlayer coordinate and facing struct (from RiftReader validated offsets)",
                                "Fields": struct_fields,
                            }
                            break

    return {
        "SchemaVersion": "binary-signatures/v1",
        "BinaryTarget": "rift_x64.exe",
        "BinaryVersion": binary_version,
        "ImageBase": "0x140000000",
        "TextSection": {
            "VirtualAddress": "0x1000",
            "RawSize": 0,
        },
        "ExtractedAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "WildcardPolicy": (
            "Relative addresses (E8/E9 call/jump rel32, 8B/05 RIP-relative disp32), "
            "ModRM [reg+disp32] displacements, and embedded absolute addresses are "
            "masked as ??. Opcode bytes and register encodings are preserved."
        ),
        "CandidateOnly": True,
        "Provenance": {
            "DiscoveryMethod": "modrm-cluster-heuristic",
            "ValidationMethod": "full-binary-uniqueness-scan",
            "ModRMScannerVersion": "modrm-memory-access-scan/v1",
            "SignatureMatchVersion": "signature-match-report/v1",
        },
        "Anchors": anchors,
        "Summary": {
            "TotalAnchors": len(anchors),
            "UniqueSignatures": unique_count,
            "NonUniqueSignatures": non_unique_count,
            "StabilityTier1Count": tier1_count,
            "StabilityTier2Count": len(anchors) - tier1_count,
            "StabilityTier3Count": 0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "Exports" / "binary-phase2" / "rift-x64-signature-catalog.json",
        help="Output path for the synthesized catalog.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Also validate the output against the schema.",
    )
    parser.add_argument(
        "--target-manifest",
        type=Path,
        default=None,
        help="Override path to riftreader-target-manifest.json.",
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=None,
        help="Override path to signature-candidates.json.",
    )
    parser.add_argument(
        "--modrm-scan",
        type=Path,
        default=None,
        help="Override path to modrm-memory-access-scan.json.",
    )
    args = parser.parse_args(argv)

    catalog = synthesize_catalog(
        target_manifest_path=args.target_manifest,
        candidates_path=args.candidates,
        modrm_scan_path=args.modrm_scan,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"==> Synthesized {catalog['Summary']['TotalAnchors']} anchors to {args.out}")
    print(f"    Unique: {catalog['Summary']['UniqueSignatures']}")
    print(f"    Non-unique: {catalog['Summary']['NonUniqueSignatures']}")
    print(f"    Tier-1: {catalog['Summary']['StabilityTier1Count']}")

    if args.validate:
        schema_path = REPO_ROOT / "docs" / "schemas" / "binary-signatures-v1.schema.json"
        if not schema_path.exists():
            print(f"WARNING: Schema not found at {schema_path}", file=sys.stderr)
            return 1
        schema = _load_json(schema_path)
        # Lightweight structural validation (no full JSON Schema validator)
        if catalog.get("SchemaVersion") != schema.get("properties", {}).get("SchemaVersion", {}).get("const"):
            print("ERROR: SchemaVersion mismatch", file=sys.stderr)
            return 1
        if not isinstance(catalog.get("Anchors"), list) or len(catalog["Anchors"]) == 0:
            print("ERROR: Anchors must be a non-empty array", file=sys.stderr)
            return 1
        for i, anchor in enumerate(catalog["Anchors"]):
            for req in ("Name", "StabilityTier", "SignatureHex", "SignatureLength", "UniquenessVerified"):
                if req not in anchor:
                    print(f"ERROR: anchor[{i}] missing required field '{req}'", file=sys.stderr)
                    return 1
        print("==> Schema validation: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
