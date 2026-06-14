"""Validate the gated live-memory scanner scaffold without live process access."""

from __future__ import annotations

import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import jsonschema

sys.path.insert(0, ".")

from scripts import rift_workflow
from scripts.live_memory_scanner import (
    SCAN_CHUNK_SIZE,
    FixtureProcessReader,
    build_live_memory_scan_plan,
    load_pattern_specs_from_file,
    parse_hex_pattern,
    parse_hex_patterns,
    scan_process_reader,
)

failed = 0
schema = json.loads(Path("docs/schemas/live-memory-scan-plan-v1.schema.json").read_text(encoding="utf-8"))
target_schema = json.loads(Path("docs/schemas/live-memory-scan-targets-v1.schema.json").read_text(encoding="utf-8"))


def check(desc: str, actual: object, expected: object) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} expected={expected!r} actual={actual!r}")
        failed += 1


def check_true(desc: str, condition: bool) -> None:
    global failed
    if condition:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc}")
        failed += 1


def check_raises(desc: str, fn: object) -> None:
    global failed
    try:
        fn()
    except Exception:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} did not raise")
        failed += 1


print("=== hex pattern parser ===")
pattern = parse_hex_pattern("twad_magic=54 57 41 44")
check("pattern label", pattern.label, "twad_magic")
check("pattern hex", pattern.normalized_hex, "54574144")
check_raises("pattern requires label", lambda: parse_hex_pattern("54574144"))
check_raises("duplicate labels rejected", lambda: parse_hex_patterns(["a=00", "a=01"]))

print("=== target manifest ===")
target_manifest = json.loads(Path("docs/live-memory-scan-targets.json").read_text(encoding="utf-8"))
jsonschema.validate(target_manifest, target_schema)
manifest_specs = load_pattern_specs_from_file(Path("docs/live-memory-scan-targets.json"))
expected_manifest_specs = [
    "stage5_step48_at264_index_strip_prefix=00010002000200010003000400050006",
    "stage5_step50_asset_id_ascii_6fc01704d4a509d5=36666330313730346434613530396435",
    "stage5_step50_asset_id_ascii_caa9a88e94ec8db0=63616139613838653934656338646230",
]
check("manifest target count", len(manifest_specs), len(expected_manifest_specs))
check(
    "manifest patterns",
    manifest_specs,
    expected_manifest_specs,
)
check("manifest candidate-only", target_manifest["CandidateOnly"], True)
check("manifest live read not executed", target_manifest["LiveReadExecuted"], False)

print("=== dry-run plan schema ===")
plan = build_live_memory_scan_plan(
    repo_root=Path(".").resolve(),
    out="",
    process_name="rift_x64.exe",
    pid=0,
    pattern_specs=["twad_magic=54574144"],
    execute_live_read=False,
    experimental_live=False,
    confirm_live_read=False,
    max_scan_bytes=1024,
    max_matches=3,
    max_regions=2,
    timeout_seconds=5,
)
jsonschema.validate(plan, schema)
check("dry run does not execute", plan["LiveProcessReadExecuted"], False)
check("dry run execution blocked", plan["ExecutionAllowed"], False)
check_true("dry run refusal noted", "dry-run-only-no-live-read-requested" in plan["RefusalReasons"])
check("output directory is ignored live lane", plan["OutputDirectory"], "Exports/discovery-plan/stage5-live")
check_raises(
    "output cannot leave ignored live lane",
    lambda: build_live_memory_scan_plan(
        repo_root=Path(".").resolve(),
        out="Exports/not-stage5-live",
        process_name="rift_x64.exe",
        pid=0,
        pattern_specs=["x=00"],
        execute_live_read=False,
        experimental_live=False,
        confirm_live_read=False,
        max_scan_bytes=1,
        max_matches=1,
        max_regions=1,
        timeout_seconds=1,
    ),
)

print("=== CLI list-json plan ===")
output = StringIO()
with (
    patch.object(
        sys,
        "argv",
        [
            "rift_workflow.py",
            "scan-live-memory",
            "--live-pattern-file",
            "docs/live-memory-scan-targets.json",
            "--list-json",
        ],
    ),
    redirect_stdout(output),
):
    rift_workflow.main()
cli_plan = json.loads(output.getvalue())
jsonschema.validate(cli_plan, schema)
check("CLI schema version", cli_plan["SchemaVersion"], "live-memory-scan-plan/v1")
check("CLI list-json does not execute", cli_plan["LiveProcessReadExecuted"], False)
check("CLI loaded manifest pattern", cli_plan["Patterns"][0]["Label"], "stage5_step48_at264_index_strip_prefix")
check("CLI loaded manifest target count", len(cli_plan["Patterns"]), len(expected_manifest_specs))

print("=== fixture scan core ===")
fixture = FixtureProcessReader([(0x1000, (b"A" * (SCAN_CHUNK_SIZE - 2)) + b"\xde\xad\xbe\xef" + b"B" * 16, "fixture")])
scan = scan_process_reader(
    fixture,
    [parse_hex_pattern("boundary=DEADBEEF")],
    max_scan_bytes=SCAN_CHUNK_SIZE + 32,
    max_matches=5,
    max_regions=1,
    timeout_seconds=5,
)
check("fixture match count", scan["PatternResults"][0]["MatchCount"], 1)
check(
    "fixture cross-chunk address",
    scan["PatternResults"][0]["Matches"][0]["Address"],
    f"0x{0x1000 + SCAN_CHUNK_SIZE - 2:X}",
)
check("fixture scan not timed out", scan["TimedOut"], False)

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
