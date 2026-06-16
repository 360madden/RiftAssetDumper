#!/usr/bin/env python3
"""Validate the scene-manifest-v1 draft schema (Cycle 2 C2-2.4 acceptance).

C2-2.4 requires the scene-manifest-v1 draft schema to validate as JSON Schema
2020-12. This script provides a programmatic check so the acceptance criterion
is machine-verifiable (not just visual inspection).

Usage:
    python scripts/validate_scene_manifest_schema.py [--schema <path>] [--fixture <path>]

Exit codes:
    0 - schema (and optional fixture) valid
    1 - schema or fixture invalid
    2 - input file not found

Checks:
    1. Schema validates as JSON Schema 2020-12 meta-schema
       (Draft202012Validator.check_schema)
    2. Optional: validate a manifest fixture against the schema
       (Draft202012Validator.iter_errors)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

DEFAULT_SCHEMA_PATH = Path("Assets/Exports/discovery-plan/cycle-2/stage2/scene-manifest-v1.draft.schema.json")


def load_schema(path: Path) -> dict[str, Any]:
    """Load a JSON schema file with UTF-8 BOM tolerance."""
    with path.open(encoding="utf-8-sig") as f:
        result: dict[str, Any] = json.load(f)
        return result


def validate_schema(schema: dict[str, Any]) -> tuple[bool, str]:
    """Check schema is a valid Draft 2020-12 meta-schema.

    Returns (ok, message). On failure, message contains the underlying error.
    """
    try:
        Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as e:
        return False, f"schema invalid: {e.message}"
    return True, "schema valid as JSON Schema 2020-12"


def validate_fixture(schema: dict[str, Any], fixture_path: Path) -> tuple[bool, list[str]]:
    """Validate a manifest fixture instance against the schema.

    Returns (ok, errors). On success, errors is empty. On malformed JSON,
    returns (False, [<error message>]) so callers can distinguish parse
    failures from schema violations and emit the documented exit code 2.
    """
    try:
        with fixture_path.open(encoding="utf-8-sig") as f:
            instance = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"invalid JSON: {e}"]
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if not errors:
        return True, []
    formatted = [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]
    return False, formatted


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser (extracted for testability)."""
    parser = argparse.ArgumentParser(
        description="Validate the scene-manifest-v1 draft schema (C2-2.4 acceptance).",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help=(f"Path to scene-manifest-v1 draft schema (default: {DEFAULT_SCHEMA_PATH})"),
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="Optional: path to a manifest fixture to validate against the schema",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.schema.exists():
        print(f"error: schema not found: {args.schema}", file=sys.stderr)
        return 2

    schema = load_schema(args.schema)
    ok, msg = validate_schema(schema)
    print(msg)
    if not ok:
        return 1

    if args.fixture is not None:
        if not args.fixture.exists():
            print(f"error: fixture not found: {args.fixture}", file=sys.stderr)
            return 2
        fixture_ok, errors = validate_fixture(schema, args.fixture)
        if fixture_ok:
            print(f"fixture valid: {args.fixture}")
            return 0
        print(f"fixture invalid: {args.fixture}", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
