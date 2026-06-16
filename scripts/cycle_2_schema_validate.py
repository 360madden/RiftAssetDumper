#!/usr/bin/env python3
"""Validate Cycle 2 JSON Schemas and optional manifest instances.

This helper is intentionally generic: C2-2.4 uses it to validate the draft
scene-manifest schema, and C2-4 can reuse it for locked manifest packs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def _format_error_path(parts: object) -> str:
    items = list(parts) if parts is not None else []
    return "$" if not items else "$." + ".".join(str(part) for part in items)


def validate(schema_path: Path, instance_path: Path | None = None) -> list[str]:
    try:
        from jsonschema import Draft202012Validator
        from jsonschema.exceptions import SchemaError, ValidationError
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise RuntimeError("jsonschema is required for Draft 2020-12 validation") from exc

    schema = _load_json(schema_path)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        return [f"schema invalid at {_format_error_path(exc.path)}: {exc.message}"]

    if instance_path is None:
        return []

    instance = _load_json(instance_path)
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for exc in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        err = exc
        assert isinstance(err, ValidationError)
        errors.append(f"instance invalid at {_format_error_path(err.path)}: {err.message}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="cycle_2_schema_validate",
        description="Validate a Draft 2020-12 JSON Schema and optionally a JSON instance.",
    )
    parser.add_argument("schema", type=Path, help="Path to JSON Schema")
    parser.add_argument("--instance", type=Path, default=None, help="Optional JSON instance to validate")
    args = parser.parse_args()

    try:
        errors = validate(args.schema, args.instance)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.instance:
        print(f"OK: {args.instance} validates against {args.schema}")
    else:
        print(f"OK: {args.schema} is a valid Draft 2020-12 schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
