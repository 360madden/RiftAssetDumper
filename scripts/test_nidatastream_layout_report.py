"""Smoke tests for nidatastream_layout_report.py."""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

import jsonschema

sys.path.insert(0, ".")

from scripts import rift_workflow
from scripts.nidatastream_layout_report import analyze_nif, build_report, report_to_markdown, write_report

failed = 0


def check(desc: str, actual: Any, expected: Any) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc}  expected={expected!r}  actual={actual!r}")
        failed += 1


def make_test_nif(path: Path) -> None:
    type_name = b"NiDataStream\x011\x0119"
    declared_payload = b"\xfe\xff\x3f\xc1\xbc\x82\x7c\x3e"
    payload = b"".join(
        [
            struct.pack("<I", len(declared_payload)),
            struct.pack("<I", 123),
            struct.pack("<I", 1),  # pair count
            struct.pack("<II", 4, 5),
            struct.pack("<I", 1),  # descriptor count
            struct.pack("<I", 0xAA),
            declared_payload,
            b"\x01",  # trailing flag
        ]
    )
    header = b"Gamebryo File Format, Version 20.6.5.0\n" + b"".join(
        [
            struct.pack("<I", 0x14020007),  # version
            b"\x01",  # little endian
            struct.pack("<I", 0),  # user version
            struct.pack("<I", 1),  # block count
            struct.pack("<H", 1),  # block type count
            struct.pack("<I", len(type_name)),
            type_name,
            struct.pack("<H", 0),  # block type index
            struct.pack("<I", len(payload)),
            struct.pack("<I", 0),  # string count
            struct.pack("<I", 0),  # max string length
            struct.pack("<I", 0),  # group count
        ]
    )
    path.write_bytes(header + payload)


print("=== NiDataStream layout report ===")
layout_schema = json.loads(Path("docs/schemas/nidatastream-layout-report-v1.schema.json").read_text(encoding="utf-8"))
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    nif_path = temp_path / "sample.nif"
    make_test_nif(nif_path)

    nif_report = analyze_nif(nif_path)
    blocks = nif_report["NiDataStreamBlocks"]
    check("one datastream block", len(blocks), 1)
    block = blocks[0]
    check("declared payload", block["DeclaredPayloadBytes"], 8)
    check("legacy offset", block["LegacyPayloadOffset"], 29)
    check("ghidra offset", block["PayloadPrefixBytes"], 28)
    check("trailer bytes", block["PayloadTrailerBytes"], 1)
    check("trailing flag", block["TrailingFlag"], 1)
    check("legacy shift", block["LegacyOffsetMinusGhidraOffset"], 1)
    check("ghidra valid", block["GhidraStyleLayoutValid"], True)

    report = build_report(temp_path, max_files=None)
    jsonschema.validate(report, layout_schema)
    print("  PASS: layout report schema validation")
    check("report block count", report["NiDataStreamBlocks"], 1)
    check("report valid count", report["GhidraStyleLayoutValidBlocks"], 1)
    check("report shifted count", report["LegacyOffsetShiftedBlocks"], 1)
    markdown = report_to_markdown(report)
    check("markdown mentions shift", "Legacy offset shifted blocks" in markdown, True)

    json_path, markdown_path = write_report(report, temp_path / "out")
    check("json written", json_path.exists(), True)
    check("markdown written", markdown_path.exists(), True)

    workflow_out = temp_path / "workflow-out"
    workflow_argv = [
        "rift_workflow.py",
        "nidatastream-layout",
        "--root",
        str(temp_path),
        "--out",
        str(workflow_out),
        "--full",
    ]
    with (
        patch.object(sys, "argv", workflow_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
    ):
        rift_workflow.main()
    workflow_report = workflow_out / "nidatastream-layout-report.json"
    check("workflow report created", workflow_report.exists(), True)
    jsonschema.validate(json.loads(workflow_report.read_text(encoding="utf-8")), layout_schema)
    print("  PASS: workflow report schema validation")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
