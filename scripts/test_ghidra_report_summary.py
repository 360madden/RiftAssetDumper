"""Smoke tests for ghidra_report_summary.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

sys.path.insert(0, ".")

from scripts import rift_workflow
from scripts.ghidra_report_summary import redact_user_profile_paths, summarize_file, summarize_report

failed = 0


def check(desc: str, actual: Any, expected: Any) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc}  expected={expected!r}  actual={actual!r}")
        failed += 1


def check_contains(desc: str, text: str, expected: str) -> None:
    global failed
    if expected in text:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc}  missing={expected!r}")
        failed += 1


sample_report = {
    "targetAddress": "141186980",
    "programName": "rift_x64.exe",
    "imageBase": "140000000",
    "function": {
        "name": "FUN_141186980",
        "entry": "141186980",
        "signature": "undefined FUN_141186980(void)",
        "bodyMin": "141186980",
        "bodyMax": "141186f4b",
        "bodyNumAddresses": 1484,
        "parameterCount": 0,
        "returnType": "undefined",
    },
    "instructionsNearTarget": [{"address": "141186980", "target": True, "mnemonic": "PUSH", "opStr": "PUSH RBP", "bytes": "55", "refsFrom": []}],
    "functionInstructions": [{"address": "141186980", "target": False, "mnemonic": "PUSH", "opStr": "PUSH RBP", "bytes": "55", "refsFrom": []}],
    "callers": [
        {
            "from": "141111111",
            "type": "DATA",
            "caller": "FUN_141111000",
            "callerEntry": "141111000",
            "callerSignature": "undefined FUN_141111000(void)",
        }
    ],
    "callsFromFunction": [
        {
            "from": "141186a00",
            "to": "1411821f0",
            "type": "UNCONDITIONAL_CALL",
            "callee": "FUN_1411821f0",
            "calleeEntry": "1411821f0",
            "calleeSignature": "undefined FUN_1411821f0(void)",
        }
    ],
    "dataRefsFromFunction": [{"from": "141186c00", "to": "142000000", "type": "DATA"}],
    "dataRefByteSamples": [
        {
            "address": "142000000",
            "byteCountRequested": 32,
            "byteCountRead": 4,
            "bytes": "37 04 03 00",
        }
    ],
    "decompile": {
        "completed": True,
        "errorMessage": "",
        "c": "void FUN_141186980(void) {\n  // C:\\Users\\example\\Desktop\\local.txt\n  log(\"NiDataStream::LoadBinary\");\n}\n",
    },
}


print("=== Ghidra FunctionSiteSurvey summarizer ===")
summary = summarize_report(sample_report, terms=["NiDataStream", "Desktop"], max_items=4, max_matches=4)
check_contains("summary title", summary, "# Ghidra FunctionSiteSurvey summary")
check_contains("function shown", summary, "FUN_141186980")
check_contains("caller count shown", summary, "| Caller refs captured | 1 |")
check_contains("data ref byte sample count shown", summary, "| Data ref byte samples captured | 1 |")
check_contains("callee shown", summary, "FUN_1411821f0")
check_contains("data ref byte sample shown", summary, "37 04 03 00")
check_contains("term match shown", summary, "NiDataStream::LoadBinary")
check("profile redaction", redact_user_profile_paths(r"C:\Users\example\Desktop\local.txt"), r"%USERPROFILE%\Desktop\local.txt")
check_contains("profile redacted in summary", summary, r"%USERPROFILE%\Desktop\local.txt")

print("=== File summary ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    report_path = temp_path / "report.json"
    out_path = temp_path / "summary.md"
    report_path.write_text(json.dumps(sample_report), encoding="utf-8")
    written = summarize_file(report_path, output_path=out_path, terms=["LoadBinary"])
    check("summary file created", out_path.exists(), True)
    check("returned text equals file", written, out_path.read_text(encoding="utf-8"))

    workflow_out = temp_path / "workflow-summary.md"
    workflow_argv = [
        "rift_workflow.py",
        "ghidra-summarize",
        "--ghidra-report",
        str(report_path),
        "--ghidra-summary-out",
        str(workflow_out),
        "--ghidra-summary-term",
        "LoadBinary",
    ]
    with (
        patch.object(sys, "argv", workflow_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
    ):
        rift_workflow.main()
    check("workflow summary created", workflow_out.exists(), True)
    check_contains("workflow summary content", workflow_out.read_text(encoding="utf-8"), "NiDataStream::LoadBinary")

print("=== No function report ===")
no_function = {
    "targetAddress": "140000000",
    "programName": "rift_x64.exe",
    "imageBase": "140000000",
    "function": None,
}
no_function_summary = summarize_report(no_function)
check_contains("no function explained", no_function_summary, "No containing function was found")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
