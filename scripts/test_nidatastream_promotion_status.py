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


def check_validation_error(desc: str, payload: dict[str, Any], schema: dict[str, Any]) -> None:
    global failed
    try:
        jsonschema.validate(payload, schema)
        print(f"  FAIL: {desc} no validation error")
        failed += 1
    except jsonschema.ValidationError:
        print(f"  PASS: {desc}")


print("=== NiDataStream evidence status ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    out_dir = temp_path / "Exports"
    report_dir = out_dir / "ghidra-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "nidatastream-promotion-dashboard.json").write_text("{}", encoding="utf-8")
    (out_dir / "nidatastream-layout-report.json").write_text("{}", encoding="utf-8")
    (report_dir / "test-target.json").write_text("{}", encoding="utf-8")
    (report_dir / "test-target.md").write_text("# test\n", encoding="utf-8")
    targets_file = temp_path / "targets.json"
    targets_file.write_text(
        json.dumps(
            {
                "SchemaVersion": "ghidra-function-site-targets/v1",
                "CandidateOnly": True,
                "Targets": [
                    {
                        "Key": "nidatastream-test-target",
                        "Address": "0x141186980",
                        "ReportPath": "Exports/ghidra-reports/test-target.json",
                        "SummaryPath": "Exports/ghidra-reports/test-target.md",
                        "SummaryTerms": ["NiDataStream"],
                        "Description": "test target",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    evidence_output = io.StringIO()
    with (
        patch.object(
            sys,
            "argv",
            [
                "rift_workflow.py",
                "nidatastream-evidence-status",
                "--out",
                str(out_dir),
                "--ghidra-targets-file",
                str(targets_file),
                "--list-json",
            ],
        ),
        patch("scripts.rift_workflow.REPO_ROOT", temp_path),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(evidence_output),
    ):
        rift_workflow.main()
evidence_status = json.loads(evidence_output.getvalue())
evidence_schema = json.loads(Path("docs/schemas/nidatastream-evidence-status-v1.schema.json").read_text(encoding="utf-8"))
jsonschema.validate(evidence_status, evidence_schema)
print("  PASS: evidence status schema validation")
check("evidence schema", evidence_status["SchemaVersion"], "nidatastream-evidence-status/v1")
check("evidence candidate-only", evidence_status["CandidateOnly"], True)
check("evidence artifact count", evidence_status["ArtifactCount"], 10)
check("evidence existing count", evidence_status["ExistingCount"], 4)
target_report = next(artifact for artifact in evidence_status["Artifacts"] if artifact["Key"] == "function-site-nidatastream-test-target-report")
check("evidence report path redacted/repo-relative", target_report["Path"], "Exports/ghidra-reports/test-target.json")
check("evidence report modified timestamp", target_report["ModifiedUtc"] is not None, True)


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
    promoted_dashboard = json.loads(json.dumps(dashboard_status))
    promoted_dashboard["ParserExportPromotionAllowed"] = True
    check_validation_error("dashboard JSON rejects parser/export promotion", promoted_dashboard, status_schema)
    field_promoted_dashboard = json.loads(json.dumps(dashboard_status))
    field_promoted_dashboard["DescriptorReportStatus"]["FieldOrderPromoted"] = True
    check_validation_error("dashboard JSON rejects descriptor field promotion", field_promoted_dashboard, status_schema)
    non_candidate_dashboard = json.loads(json.dumps(dashboard_status))
    non_candidate_dashboard["CandidateOnly"] = False
    check_validation_error("dashboard JSON rejects non-candidate output", non_candidate_dashboard, status_schema)
    check_contains("dashboard markdown title", dashboard_md.read_text(encoding="utf-8"), "# NiDataStream promotion dashboard")
    check_contains("dashboard console", dashboard_output.getvalue(), "candidate-only/report-only")

print("=== NiDataStream promotion preflight ===")
with TemporaryDirectory() as temp_dir:
    preflight_output = io.StringIO()
    preflight_calls = {"guard_suite": False, "generated_output_guard": 0}

    def fake_generated_output_guard() -> None:
        preflight_calls["generated_output_guard"] += 1
        print("fake generated-output guard")

    def fake_guard_suite(args: Any) -> None:
        preflight_calls["guard_suite"] = True
        print(f"fake guard suite out={args.out}")

    with (
        patch.object(sys, "argv", ["rift_workflow.py", "nidatastream-promotion-preflight", "--out", temp_dir]),
        patch("scripts.rift_workflow.generated_output_guard", side_effect=fake_generated_output_guard),
        patch("scripts.rift_workflow._run_ghidra_workflow_guard_suite", side_effect=fake_guard_suite),
        redirect_stdout(preflight_output),
    ):
        rift_workflow.main()
    check("preflight dashboard json written", (Path(temp_dir) / "nidatastream-promotion-dashboard.json").exists(), True)
    check("preflight dashboard markdown written", (Path(temp_dir) / "nidatastream-promotion-dashboard.md").exists(), True)
    check("preflight runs guard suite", preflight_calls["guard_suite"], True)
    check("preflight runs initial and final generated-output guards", preflight_calls["generated_output_guard"], 2)
    check_contains("preflight console", preflight_output.getvalue(), "NiDataStreamPromotionPreflight passed")

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
