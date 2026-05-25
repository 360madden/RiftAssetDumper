"""Smoke tests for NiDataStream parser/export promotion gate workflow."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

import jsonschema

sys.path.insert(0, ".")

from scripts import rift_workflow

failed = 0


def check(desc: str, actual: Any, expected: Any) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} expected={expected!r} actual={actual!r}")
        failed += 1


def check_contains(desc: str, text: str, expected: str) -> None:
    global failed
    if expected in text:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} missing={expected!r}")
        failed += 1


def check_raises(desc: str, fn: Any, expected_text: str) -> None:
    global failed
    stderr = io.StringIO()
    try:
        with redirect_stderr(stderr):
            fn()
        print(f"  FAIL: {desc} no exception raised")
        failed += 1
    except SystemExit:
        error_text = stderr.getvalue()
        if expected_text in error_text:
            print(f"  PASS: {desc}")
        else:
            print(f"  FAIL: {desc} missing={expected_text!r} stderr={error_text!r}")
            failed += 1


print("=== NiDataStream promotion status ===")
status_output = io.StringIO()
with (
    patch.object(sys, "argv", ["rift_workflow.py", "nidatastream-promotion-status", "--list-json"]),
    patch("scripts.rift_workflow.generated_output_guard"),
    redirect_stdout(status_output),
):
    rift_workflow.main()
status = json.loads(status_output.getvalue())
status_schema = json.loads(Path("docs/schemas/nidatastream-promotion-status-v1.schema.json").read_text(encoding="utf-8"))
jsonschema.validate(status, status_schema)
print("  PASS: promotion status schema validation")
check("promotion status schema", status["SchemaVersion"], "nidatastream-promotion-status/v1")
check("promotion status candidate-only", status["CandidateOnly"], True)
check("historical stage", status["HistoricalStage"], "Stage 18 complete")
check("promotion blocked", status["ParserExportPromotionAllowed"], False)
check("has blocking gates", status["BlockerCount"] > 0, True)
check_contains("promotion lane", status["CurrentLane"], "post-Stage-18")
check("descriptor report status present", "DescriptorReportStatus" in status, True)
check("descriptor field order not promoted", status["DescriptorReportStatus"]["FieldOrderPromoted"], False)
check("layout report status present", "LayoutReportStatus" in status, True)
check("layout report all-valid flag is boolean", isinstance(status["LayoutReportStatus"]["AllBlocksGhidraStyleValid"], bool), True)
check("pairing impact status present", "PairingImpactStatus" in status, True)
check("pairing baseline pass flag is boolean", isinstance(status["PairingImpactStatus"]["GuardBaselinePass"], bool), True)

print("=== NiDataStream pairing impact negative fixture ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    (temp_path / "ghidra-attribute-candidate-report.json").write_text(
        json.dumps(
            {
                "SchemaVersion": "ghidra-attribute-candidate-report/v1",
                "CandidateOnly": True,
                "Summary": {
                    "GhidraOnlyGroups": 1,
                    "GhidraOnlyPairingsCovered": 3,
                    "GroupedSampleMeshes": 1,
                    "CompletePositionNormalUvCandidateGroups": 1,
                    "ProbeBackedRanks": 1,
                    "RejectedNoiseGroups": 0,
                },
                "Groups": [],
            }
        ),
        encoding="utf-8",
    )
    negative_output = io.StringIO()
    with (
        patch.object(sys, "argv", ["rift_workflow.py", "nidatastream-promotion-status", "--out", temp_dir, "--list-json"]),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(negative_output),
    ):
        rift_workflow.main()
negative_status = json.loads(negative_output.getvalue())
jsonschema.validate(negative_status, status_schema)
pairing_status = negative_status["PairingImpactStatus"]
check("negative pairing baseline fails", pairing_status["GuardBaselinePass"], False)
check("negative pairing complete groups", pairing_status["CompletePositionNormalUvCandidateGroups"], 1)
pairing_gate = next(gate for gate in negative_status["Gates"] if gate["Key"] == "pairing-impact-proof")
check("negative pairing gate blocked", pairing_gate["State"], "blocked")

print("=== NiDataStream promotion dashboard ===")
with TemporaryDirectory() as temp_dir:
    dashboard_output = io.StringIO()
    with (
        patch.object(sys, "argv", ["rift_workflow.py", "nidatastream-promotion-dashboard", "--out", temp_dir]),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(dashboard_output),
    ):
        rift_workflow.main()
    dashboard_json = Path(temp_dir) / "nidatastream-promotion-dashboard.json"
    dashboard_md = Path(temp_dir) / "nidatastream-promotion-dashboard.md"
    check("dashboard json written", dashboard_json.exists(), True)
    check("dashboard markdown written", dashboard_md.exists(), True)
    dashboard_status = json.loads(dashboard_json.read_text(encoding="utf-8"))
    jsonschema.validate(dashboard_status, status_schema)
    print("  PASS: dashboard JSON schema validation")
    check_contains("dashboard markdown title", dashboard_md.read_text(encoding="utf-8"), "# NiDataStream promotion dashboard")
    check_contains("dashboard console", dashboard_output.getvalue(), "candidate-only/report-only")

print("=== NiDataStream parser-field proof guard ===")
guard_output = io.StringIO()
called = {"non_export": False}


def fake_non_export_guard() -> None:
    called["non_export"] = True
    print("fake non-export guard")


with (
    patch.object(sys, "argv", ["rift_workflow.py", "nidatastream-parser-field-proof-guard"]),
    patch("scripts.rift_workflow.generated_output_guard"),
    patch("scripts.rift_workflow.ghidra_pairing_non_export_guard", side_effect=fake_non_export_guard),
    redirect_stdout(guard_output),
):
    rift_workflow.main()
check("proof guard runs non-export guard", called["non_export"], True)
check_contains("proof guard blocked", guard_output.getvalue(), "parser/export promotion remains blocked")

print("=== --list-json routing safety ===")
with patch.object(sys, "argv", ["rift_workflow.py", "generated-output-guard", "--list-json"]):
    check_raises("unsupported list-json fails closed", rift_workflow.main, "--list-json is only supported")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
