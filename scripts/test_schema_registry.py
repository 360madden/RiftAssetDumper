"""Validate tracked JSON schemas and durable tracked JSON docs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import jsonschema

failed = 0


def check(desc: str, actual: Any, expected: Any) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} expected={expected!r} actual={actual!r}")
        failed += 1


def check_raises_no(desc: str, fn: Any) -> None:
    global failed
    try:
        fn()
        print(f"  PASS: {desc}")
    except Exception as exc:  # noqa: BLE001 - smoke test reports schema/doc path context
        print(f"  FAIL: {desc}: {exc}")
        failed += 1


def load_json(path: Path) -> dict[str, Any]:
    # utf-8-sig tolerates files saved with a BOM (e.g. some editors re-add
    # it on save). Mirrors scripts/rift_workflow_utils.py::load_json_report.
    return json.loads(path.read_text(encoding="utf-8-sig"))


print("=== tracked JSON schemas ===")
schema_dir = Path("docs/schemas")
schema_paths = sorted(schema_dir.glob("*.schema.json"))
check("schema count", len(schema_paths) >= 1, True)

schemas: dict[str, dict[str, Any]] = {}
for schema_path in schema_paths:
    schema = load_json(schema_path)
    schemas[schema_path.name] = schema
    check(f"{schema_path.name} has $schema", "$schema" in schema, True)
    check(f"{schema_path.name} has $id", "$id" in schema, True)
    check(f"{schema_path.name} has title", "title" in schema, True)
    check_raises_no(
        f"{schema_path.name} is Draft 2020-12-valid",
        lambda schema=schema: jsonschema.Draft202012Validator.check_schema(schema),
    )

print("=== tracked JSON docs ===")
target_registry = load_json(Path("docs/ghidra-function-site-targets.json"))
target_schema = schemas["ghidra-function-site-targets-v1.schema.json"]
check_raises_no(
    "ghidra-function-site-targets.json validates",
    lambda: jsonschema.validate(target_registry, target_schema),
)
check("target registry candidate-only", target_registry.get("CandidateOnly"), True)
check("target registry schema version", target_registry.get("SchemaVersion"), "ghidra-function-site-targets/v1")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
