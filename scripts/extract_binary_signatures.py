#!/usr/bin/env python3
"""Phase 6 pipeline orchestrator for the binary-signature database.

Reads the Phase 2 byte-signature catalog and (optionally) the Phase 3 struct-layout
catalog from the live-archive workspace, then synthesizes the unified Phase 5
database via ``scripts.synthesize_unified_signature_db``. Validates both
inputs + the output against their respective schemas.

This is the "single command" entry point that consolidates the Phase 2→5
pipeline so a Ghidra re-extraction produces an updated unified DB without
running three separate scripts manually.

Usage::

    # Default paths
    python scripts/extract_binary_signatures.py

    # Customize inputs and validate against schemas at every step
    python scripts/extract_binary_signatures.py \\
        --phase2-catalog Exports/binary-phase2/rift-x64-signature-catalog.json \\
        --phase3-catalog Exports/binary-phase3/struct-layout-catalog.json \\
        --out Exports/binary-phase5/rift-x64-signature-database.json \\
        --validate-only

Exit codes:
    0 — success (extract + validate)
    1 — schema validation failure on input
    2 — synthesis failure (empty Anchors, IO error, etc.)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import scripts.synthesize_unified_signature_db as synth  # noqa: E402

UNIFIED_DB_SCHEMA = "binary-signatures/v1"
STRUCT_LAYOUT_SCHEMA = "struct-layout-catalog/v1"
PHASE2_SCHEMA = "binary-signatures/v1"

EXTRACTION_MANIFEST_SCHEMA = "binary-extraction-manifest/v1"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((REPO_ROOT / "docs" / "schemas" / name).read_text(encoding="utf-8"))


def validate_against_schema(doc: dict[str, Any], schema_path: Path, *, label: str) -> list[str]:
    """Return a list of validation error messages (empty on success)."""
    try:
        import jsonschema
    except ImportError:
        # jsonschema not installed: emit a WARNING so CI on minimal installs
        # doesn't silently ship schema-broken artifacts. The fallback only
        # verifies SchemaVersion const + Anchors[]/Structs[] presence — does
        # NOT guarantee full schema conformance.
        print(
            f"WARNING: jsonschema unavailable; {label} falling back to structural minimum check",
            file=sys.stderr,
        )
        expected = schema_path.read_text(encoding="utf-8")
        schema = json.loads(expected)
        const = schema.get("properties", {}).get("SchemaVersion", {}).get("const")
        actual = doc.get("SchemaVersion")
        if const and actual != const:
            return [f"{label}: SchemaVersion mismatch (got {actual!r}, expected {const!r})"]
        if not isinstance(doc.get("Anchors", doc.get("Structs")), list):
            return [f"{label}: missing Anchors[]/Structs[]"]
        return []
    try:
        jsonschema.validate(doc, _load_json(schema_path), format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)
    except jsonschema.ValidationError as exc:
        return [f"{label}: {exc.message} at {'/'.join(str(p) for p in exc.path)}"]
    return []


def extract(
    *,
    phase2_catalog_path: Path,
    phase3_catalog_path: Path | None,
    out_path: Path,
    validate_only: bool,
) -> dict[str, Any]:
    """Run the full Phase 2→5 extraction pipeline. Returns the extraction manifest dict."""

    manifest_lines: list[str] = ["==> Phase 6 extraction pipeline"]
    manifest_lines.append(f"    Phase 2 catalog: {phase2_catalog_path}")
    manifest_lines.append(f"    Phase 3 catalog: {phase3_catalog_path or '(skipped)'}")
    manifest_lines.append(f"    Output: {out_path}")

    # Step 1 — validate Phase 2 input
    if not phase2_catalog_path.exists():
        raise FileNotFoundError(f"Phase 2 catalog not found: {phase2_catalog_path}")
    phase2_doc = _load_json(phase2_catalog_path)
    p2_errors = validate_against_schema(
        phase2_doc, REPO_ROOT / "docs" / "schemas" / "binary-signatures-v1.schema.json", label="phase2"
    )
    if p2_errors:
        print("\n".join(p2_errors), file=sys.stderr)
        raise SystemExit(1)

    # Step 2 — validate Phase 3 input (optional)
    phase3_doc: dict[str, Any] | None = None
    if phase3_catalog_path and phase3_catalog_path.is_file():
        phase3_doc = _load_json(phase3_catalog_path)
        p3_errors = validate_against_schema(
            phase3_doc,
            REPO_ROOT / "docs" / "schemas" / "struct-layout-catalog-v1.schema.json",
            label="phase3",
        )
        if p3_errors:
            print("\n".join(p3_errors), file=sys.stderr)
            raise SystemExit(1)

    # Step 3 — synthesize the unified DB
    unified_db = synth.synthesize_database(
        phase2_catalog_path=phase2_catalog_path,
        phase3_catalog_path=phase3_catalog_path if phase3_catalog_path and phase3_catalog_path.is_file() else None,
    )

    # Step 4 — validate the synthesized unified DB
    out_errors = validate_against_schema(
        unified_db, REPO_ROOT / "docs" / "schemas" / "binary-signatures-v1.schema.json", label="unified"
    )
    if out_errors:
        print("\n".join(out_errors), file=sys.stderr)
        raise SystemExit(1)

    summary = unified_db["Summary"]
    manifest_lines.append(f"    Anchors: {summary['TotalAnchors']} (unique={summary['UniqueSignatures']})")
    manifest_lines.append(
        f"    Tiers: 1={summary['StabilityTier1Count']}, 2={summary['StabilityTier2Count']}, 3={summary['StabilityTier3Count']}"
    )
    manifest_lines.append(f"    AttachedStructCount: {summary['AttachedStructCount']}")
    if validate_only:
        manifest_lines.append("    (validate-only: output not written)")
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(unified_db, indent=2), encoding="utf-8")
        manifest_lines.append(f"    Wrote: {out_path}")

    manifest = {
        "SchemaVersion": EXTRACTION_MANIFEST_SCHEMA,
        "ExtractedAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Inputs": {
            "Phase2Catalog": str(phase2_catalog_path),
            "Phase3Catalog": str(phase3_catalog_path or "") or None,
            "BinaryVersion": unified_db.get("BinaryVersion"),
        },
        "Output": {
            "Path": str(out_path),
            "SchemaVersion": unified_db["SchemaVersion"],
            "Written": not validate_only,
        },
        "Summary": summary,
        "CandidateOnly": unified_db["CandidateOnly"],
    }
    if not validate_only:
        manifest_path = out_path.with_name(f"{out_path.stem}.extraction-manifest.json")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        manifest_lines.append(f"    Manifest: {manifest_path}")

    print("\n".join(manifest_lines))
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--phase2-catalog",
        type=Path,
        default=REPO_ROOT / "Exports" / "binary-phase2" / "rift-x64-signature-catalog.json",
        help="Path to the Phase 2 signature catalog.",
    )
    parser.add_argument(
        "--phase3-catalog",
        type=Path,
        default=REPO_ROOT / "Exports" / "binary-phase3" / "struct-layout-catalog.json",
        help="Path to the Phase 3 struct layout catalog (optional). Pass an empty string to skip.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "Exports" / "binary-phase5" / "rift-x64-signature-database.json",
        help="Output path for the synthesized unified DB.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Run only the schema validations; do not write the output.",
    )
    args = parser.parse_args(argv)

    try:
        extract(
            phase2_catalog_path=args.phase2_catalog,
            phase3_catalog_path=args.phase3_catalog,
            out_path=args.out,
            validate_only=args.validate_only,
        )
    except SystemExit:
        raise
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (KeyError, ValueError) as exc:
        print(f"ERROR: synthesis failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
