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


def promotion_status_for_out(out_dir: Path) -> dict[str, Any]:
    output = io.StringIO()
    with (
        patch.object(
            sys, "argv", ["rift_workflow.py", "nidatastream-promotion-status", "--out", str(out_dir), "--list-json"]
        ),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(output),
    ):
        rift_workflow.main()
    return json.loads(output.getvalue())


def minimal_layout_report(blocks: int = 2) -> dict[str, Any]:
    def counter(value: int) -> list[dict[str, int]]:
        return [{"Value": value, "Count": blocks}]

    return {
        "Schema": "nidatastream-layout-report/v1",
        "Root": "Extracted",
        "FilesScanned": 1,
        "FilesParsed": 1,
        "FilesWithNiDataStreamBlocks": 1,
        "ParseErrorCount": 0,
        "NiDataStreamBlocks": blocks,
        "GhidraStyleLayoutValidBlocks": blocks,
        "LegacyOffsetShiftedBlocks": blocks,
        "TopPayloadPrefixBytes": counter(28),
        "TopPayloadTrailerBytes": counter(1),
        "TopTrailingFlags": counter(1),
        "TopLegacyOffsetMinusGhidraOffset": counter(1),
        "TopSecondUInt32": counter(0),
        "TopPairCounts": counter(1),
        "TopPairRecordOffsets": counter(12),
        "TopFirstPairRecordBytes": [],
        "TopDescriptorCounts": counter(1),
        "TopDescriptorCountOffsets": counter(20),
        "TopDescriptorRecordOffsets": counter(24),
        "TopFirstDescriptorRecordBytes": [],
        "ShiftedSamples": [],
        "Warnings": [],
    }


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
evidence_schema = json.loads(
    Path("docs/schemas/nidatastream-evidence-status-v1.schema.json").read_text(encoding="utf-8")
)
jsonschema.validate(evidence_status, evidence_schema)
print("  PASS: evidence status schema validation")
check("evidence schema", evidence_status["SchemaVersion"], "nidatastream-evidence-status/v1")
check("evidence candidate-only", evidence_status["CandidateOnly"], True)
check("evidence artifact count", evidence_status["ArtifactCount"], 12)
check("evidence existing count", evidence_status["ExistingCount"], 4)
target_report = next(
    artifact
    for artifact in evidence_status["Artifacts"]
    if artifact["Key"] == "function-site-nidatastream-test-target-report"
)
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
status_schema = json.loads(
    Path("docs/schemas/nidatastream-promotion-status-v1.schema.json").read_text(encoding="utf-8")
)
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
check("descriptor field map status present", "DescriptorFieldMapStatus" in status, True)
check("descriptor field map entry count", status["DescriptorFieldMapStatus"]["FieldMapCount"], 4)
check("descriptor field map static offset count", status["DescriptorFieldMapStatus"]["StaticTableOffsetCount"], 3)
check("stream descriptor record not mapped", status["DescriptorFieldMapStatus"]["StreamDescriptorRecordMapped"], False)
check("layout report status present", "LayoutReportStatus" in status, True)
check(
    "layout report all-valid flag is boolean",
    isinstance(status["LayoutReportStatus"]["AllBlocksGhidraStyleValid"], bool),
    True,
)
check("descriptor/sample compare status present", "DescriptorSampleCompareStatus" in status, True)
check(
    "descriptor/sample evidence ready flag is boolean",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorAndSampleEvidenceReady"], bool),
    True,
)
check(
    "descriptor/sample byte-order flag is boolean",
    isinstance(status["DescriptorSampleCompareStatus"]["AllByteOrderFieldsUniform"], bool),
    True,
)
check(
    "descriptor semantic mapping remains blocked",
    status["DescriptorSampleCompareStatus"]["DescriptorSemanticMappingReady"],
    False,
)
check(
    "descriptor record index candidate mapped",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorRecordIndexCandidateMapped"], bool),
    True,
)
check(
    "descriptor helper high bytes proof flag is boolean",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorHelperLookupHighBytesProvenUnused"], bool),
    True,
)
check(
    "descriptor helper ignored byte count is numeric",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorHelperLookupIgnoredByteCount"], int),
    True,
)
check(
    "descriptor sign guard byte count is numeric",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorSignGuardByteCount"], int),
    True,
)
check(
    "descriptor record bytes classified flag is boolean",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorRecordBytesClassified"], bool),
    True,
)
check(
    "descriptor record padding count is numeric",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorRecordPaddingByteCount"], int),
    True,
)
check(
    "descriptor record remaining unmapped count is numeric",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorRecordRemainingUnmappedByteCount"], int),
    True,
)
check(
    "descriptor record pattern count is numeric",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorRecordPatternCount"], int),
    True,
)
check(
    "descriptor record pattern matrix row count is numeric",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorRecordPatternMatrixRowCount"], int),
    True,
)
check(
    "descriptor context correlation ready flag is boolean",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorContextCorrelationReady"], bool),
    True,
)
check(
    "descriptor context correlation sample count is numeric",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorContextCorrelationSampleCount"], int),
    True,
)
check(
    "descriptor context correlation pattern count is numeric",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorContextCorrelationPatternCount"], int),
    True,
)
check(
    "descriptor table sample report ready flag is boolean",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorTableSampleReportReady"], bool),
    True,
)
check(
    "descriptor table sample row count is numeric",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorTableSampleRowCount"], int),
    True,
)
check(
    "descriptor table sample nonzero row count is numeric",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorTableSampleNonzeroRowCount"], int),
    True,
)
check(
    "descriptor table sample all-zero flag is boolean",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorTableSampleAllRowsZero"], bool),
    True,
)
check(
    "descriptor table sample semantics explained flag is false",
    status["DescriptorSampleCompareStatus"]["DescriptorTableSampleSemanticsExplained"],
    False,
)
check(
    "descriptor table sample compare report count is numeric",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorTableSampleCompareReportCount"], int),
    True,
)
check(
    "descriptor table sample compare existing count is numeric",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorTableSampleCompareExistingReportCount"], int),
    True,
)
check(
    "descriptor table sample compare ready count is numeric",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorTableSampleCompareReadyReportCount"], int),
    True,
)
check(
    "descriptor table sample compare nonzero count is numeric",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorTableSampleCompareNonzeroReportCount"], int),
    True,
)
check(
    "descriptor table sample compare all-zero flag is boolean",
    isinstance(status["DescriptorSampleCompareStatus"]["DescriptorTableSampleCompareAllExistingReportsAllZero"], bool),
    True,
)
semantic_gate = next(gate for gate in status["Gates"] if gate["Key"] == "descriptor-semantic-map")
check("descriptor semantic gate blocks promotion", semantic_gate["State"], "blocked")
table_sample_gate = next(gate for gate in status["Gates"] if gate["Key"] == "descriptor-table-sample-proof")
check("descriptor table sample gate blocks promotion", table_sample_gate["BlocksPromotion"], True)
check("pairing impact status present", "PairingImpactStatus" in status, True)
check(
    "pairing baseline pass flag is boolean", isinstance(status["PairingImpactStatus"]["GuardBaselinePass"], bool), True
)
missing_compare_status = json.loads(json.dumps(status))
del missing_compare_status["DescriptorSampleCompareStatus"]
check_validation_error(
    "promotion status rejects missing descriptor/sample compare status", missing_compare_status, status_schema
)
string_ready_status = json.loads(json.dumps(status))
string_ready_status["DescriptorSampleCompareStatus"]["DescriptorAndSampleEvidenceReady"] = "true"
check_validation_error(
    "promotion status rejects string descriptor/sample ready flag", string_ready_status, status_schema
)
semantic_ready_status = json.loads(json.dumps(status))
semantic_ready_status["DescriptorSampleCompareStatus"]["DescriptorSemanticMappingReady"] = True
check_validation_error("promotion status rejects semantic mapping promotion", semantic_ready_status, status_schema)
table_sample_semantics_status = json.loads(json.dumps(status))
table_sample_semantics_status["DescriptorSampleCompareStatus"]["DescriptorTableSampleSemanticsExplained"] = True
check_validation_error(
    "promotion status rejects table sample semantic promotion", table_sample_semantics_status, status_schema
)
string_index_status = json.loads(json.dumps(status))
string_index_status["DescriptorSampleCompareStatus"]["DescriptorRecordIndexCandidateMapped"] = "true"
check_validation_error("promotion status rejects string record index mapped flag", string_index_status, status_schema)
string_helper_high_bytes_status = json.loads(json.dumps(status))
string_helper_high_bytes_status["DescriptorSampleCompareStatus"]["DescriptorHelperLookupHighBytesProvenUnused"] = "true"
check_validation_error(
    "promotion status rejects string helper high bytes proof flag",
    string_helper_high_bytes_status,
    status_schema,
)
string_classified_status = json.loads(json.dumps(status))
string_classified_status["DescriptorSampleCompareStatus"]["DescriptorRecordBytesClassified"] = "false"
check_validation_error(
    "promotion status rejects string record bytes classified flag", string_classified_status, status_schema
)
string_context_ready_status = json.loads(json.dumps(status))
string_context_ready_status["DescriptorSampleCompareStatus"]["DescriptorContextCorrelationReady"] = "true"
check_validation_error(
    "promotion status rejects string descriptor context correlation ready flag",
    string_context_ready_status,
    status_schema,
)
string_stream_map_status = json.loads(json.dumps(status))
string_stream_map_status["DescriptorFieldMapStatus"]["StreamDescriptorRecordMapped"] = "false"
check_validation_error(
    "promotion status rejects string stream-record mapped flag", string_stream_map_status, status_schema
)

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
        patch.object(
            sys, "argv", ["rift_workflow.py", "nidatastream-promotion-status", "--out", temp_dir, "--list-json"]
        ),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(negative_output),
    ):
        rift_workflow.main()
negative_status = json.loads(negative_output.getvalue())
jsonschema.validate(negative_status, status_schema)
pairing_status = negative_status["PairingImpactStatus"]
check("negative pairing baseline fails", pairing_status["GuardBaselinePass"], False)
check("negative pairing complete groups", pairing_status["CompletePositionNormalUvCandidateGroups"], 1)
missing_layout_compare = negative_status["DescriptorSampleCompareStatus"]
check("missing layout sample checks pass count", missing_layout_compare["SampleBytePassedCount"], 0)
check("missing layout byte-order checks pass count", missing_layout_compare["ByteOrderPassedCount"], 0)
check(
    "missing layout record index mapped flag is boolean",
    isinstance(missing_layout_compare["DescriptorRecordIndexCandidateMapped"], bool),
    True,
)
check(
    "missing layout helper high bytes proof flag is boolean",
    isinstance(missing_layout_compare["DescriptorHelperLookupHighBytesProvenUnused"], bool),
    True,
)
check(
    "missing layout record roles classified flag is boolean",
    isinstance(missing_layout_compare["DescriptorRecordBytesClassified"], bool),
    True,
)
check(
    "missing layout context correlation ready flag is boolean",
    isinstance(missing_layout_compare["DescriptorContextCorrelationReady"], bool),
    True,
)
check(
    "missing layout context correlation samples", missing_layout_compare["DescriptorContextCorrelationSampleCount"], 0
)
check(
    "missing layout context correlation patterns", missing_layout_compare["DescriptorContextCorrelationPatternCount"], 0
)
check(
    "missing layout descriptor semantic mapping false", missing_layout_compare["DescriptorSemanticMappingReady"], False
)
check("missing layout descriptor/sample ready false", missing_layout_compare["DescriptorAndSampleEvidenceReady"], False)
pairing_gate = next(gate for gate in negative_status["Gates"] if gate["Key"] == "pairing-impact-proof")
check("negative pairing gate blocked", pairing_gate["State"], "blocked")

print("=== NiDataStream descriptor/sample status edge fixtures ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    (temp_path / "nidatastream-layout-report.json").write_text("{bad json", encoding="utf-8")
    corrupt_status = promotion_status_for_out(temp_path)
jsonschema.validate(corrupt_status, status_schema)
print("  PASS: corrupt layout status schema validation")
check("corrupt layout report error captured", bool(corrupt_status["LayoutReportStatus"]["Error"]), True)
check(
    "corrupt layout descriptor/sample ready false",
    corrupt_status["DescriptorSampleCompareStatus"]["DescriptorAndSampleEvidenceReady"],
    False,
)
corrupt_sample_gate = next(gate for gate in corrupt_status["Gates"] if gate["Key"] == "sample-byte-agreement")
check("corrupt layout sample gate blocked", corrupt_sample_gate["State"], "blocked")

with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    (temp_path / "nidatastream-layout-report.json").write_text(json.dumps([]), encoding="utf-8")
    non_object_status = promotion_status_for_out(temp_path)
jsonschema.validate(non_object_status, status_schema)
print("  PASS: non-object layout status schema validation")
check(
    "non-object layout report error captured",
    non_object_status["LayoutReportStatus"]["Error"],
    "layout report root must be a JSON object",
)
check(
    "non-object layout descriptor/sample ready false",
    non_object_status["DescriptorSampleCompareStatus"]["DescriptorAndSampleEvidenceReady"],
    False,
)

with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    partial_report = minimal_layout_report()
    partial_report["TopPayloadPrefixBytes"] = [{"Value": 28, "Count": 1}]
    (temp_path / "nidatastream-layout-report.json").write_text(json.dumps(partial_report), encoding="utf-8")
    partial_status = promotion_status_for_out(temp_path)
jsonschema.validate(partial_status, status_schema)
print("  PASS: partial descriptor/sample status schema validation")
partial_compare = partial_status["DescriptorSampleCompareStatus"]
check("partial sample byte checks fail closed", partial_compare["AllSampleBytesUniform"], False)
check("partial byte-order checks fail closed", partial_compare["AllByteOrderFieldsUniform"], False)
check("partial descriptor/sample ready false", partial_compare["DescriptorAndSampleEvidenceReady"], False)
partial_sample_gate = next(gate for gate in partial_status["Gates"] if gate["Key"] == "sample-byte-agreement")
check("partial descriptor/sample sample gate blocked", partial_sample_gate["State"], "blocked")

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
    dashboard_markdown = dashboard_md.read_text(encoding="utf-8")
    check_contains("dashboard markdown title", dashboard_markdown, "# NiDataStream promotion dashboard")
    check_contains("dashboard markdown field-map status", dashboard_markdown, "Descriptor candidate field-map entries")
    check_contains("dashboard markdown stream record status", dashboard_markdown, "Stream descriptor record mapped")
    check_contains("dashboard markdown byte-order status", dashboard_markdown, "Descriptor byte-order checks")
    check_contains(
        "dashboard markdown pattern matrix status", dashboard_markdown, "Descriptor record pattern matrix rows"
    )
    check_contains(
        "dashboard markdown context correlation samples",
        dashboard_markdown,
        "Descriptor/sample context correlation samples",
    )
    check_contains(
        "dashboard markdown context correlation ready",
        dashboard_markdown,
        "Descriptor/sample context correlation ready",
    )
    check_contains("dashboard markdown table sample rows", dashboard_markdown, "Descriptor-table sample rows")
    check_contains(
        "dashboard markdown table sample semantics",
        dashboard_markdown,
        "Descriptor-table sample semantics explained",
    )
    check_contains("dashboard markdown record index status", dashboard_markdown, "Descriptor record byte 0 mapped")
    check_contains(
        "dashboard markdown helper high bytes status",
        dashboard_markdown,
        "Descriptor helper high bytes proven unused",
    )
    check_contains(
        "dashboard markdown padding byte status", dashboard_markdown, "Descriptor record padding byte candidates"
    )
    check_contains(
        "dashboard markdown remaining byte status", dashboard_markdown, "Descriptor record remaining unmapped bytes"
    )
    check_contains("dashboard markdown semantic status", dashboard_markdown, "Descriptor semantic mapping ready")
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
    check(
        "preflight dashboard markdown written", (Path(temp_dir) / "nidatastream-promotion-dashboard.md").exists(), True
    )
    check(
        "preflight descriptor/sample json written",
        (Path(temp_dir) / "nidatastream-descriptor-sample-compare.json").exists(),
        True,
    )
    check(
        "preflight descriptor/sample markdown written",
        (Path(temp_dir) / "nidatastream-descriptor-sample-compare.md").exists(),
        True,
    )
    check("preflight runs guard suite", preflight_calls["guard_suite"], True)
    check("preflight runs initial and final generated-output guards", preflight_calls["generated_output_guard"], 2)
    check_contains(
        "preflight descriptor/sample compare", preflight_output.getvalue(), "Preflight descriptor/sample compare"
    )
    check_contains("preflight evidence status", preflight_output.getvalue(), "NiDataStreamEvidenceStatus")
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
