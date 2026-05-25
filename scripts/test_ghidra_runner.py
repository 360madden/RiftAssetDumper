"""Smoke tests for ghidra_runner.py."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

import jsonschema

sys.path.insert(0, ".")

from scripts import ghidra_runner, rift_workflow

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


def check_raises(desc: str, fn: Any, expected_text: str) -> None:
    global failed
    try:
        fn()
        print(f"  FAIL: {desc}  no exception raised")
        failed += 1
    except Exception as exc:  # noqa: BLE001 - smoke-test helper checks failure text
        if expected_text in str(exc):
            print(f"  PASS: {desc}")
        else:
            print(f"  FAIL: {desc}  missing={expected_text!r} actual={exc!r}")
            failed += 1


def parse_json_object(text: str) -> dict[str, Any]:
    return json.loads(text)


print("=== Ghidra environment ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    java_home = temp_path / "jdk"
    java_bin = java_home / "bin"
    java_exe = java_bin / "java.exe"
    ghidra_home = temp_path / "ghidra"
    ghidra_bat = ghidra_home / "support" / "analyzeHeadless.bat"
    script_file = temp_path / "scripts" / "RiftAnchorSurvey.java"
    script_file.parent.mkdir()
    script_file.write_text("// test\n", encoding="utf-8")

    config = {
        "tools": {
            "ghidra": {
                "installed": True,
                "resolved_path": str(ghidra_bat),
                "home": str(ghidra_home),
            },
            "jdk21": {
                "installed": True,
                "resolved_path": str(java_exe),
                "home": str(java_home),
            },
        }
    }

    captured: dict[str, Any] = {}
    project_dir = temp_path / "projects"

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env")
        return subprocess.CompletedProcess(cmd, 0, "ok", "")

    with (
        patch("scripts.ghidra_runner.load_tools_config", return_value=config),
        patch("scripts.ghidra_runner.subprocess.run", side_effect=fake_run),
    ):
        result = ghidra_runner.run_ghidra_headless(
            project_dir=project_dir,
            project_name="EnvTest",
            process_path="rift_x64.exe",
            script=script_file,
            script_args=[str(temp_path / "report.json")],
            analyze=False,
            timeout_seconds=1,
        )

    check("subprocess return code", result.returncode, 0)
    check("project dir created", project_dir.is_dir(), True)
    env = captured["env"]
    check("JAVA_HOME exported", env["JAVA_HOME"], str(java_home))
    path_key = "Path" if "Path" in env else "PATH"
    first_path_entry = env[path_key].split(os.pathsep)[0]
    check("JDK bin prepended to PATH", first_path_entry, str(java_bin.resolve()))
    cmd = captured["cmd"]
    check("process mode used", "-process" in cmd and "rift_x64.exe" in cmd, True)
    check("noanalysis used", "-noanalysis" in cmd, True)
    check("scriptPath inferred", "-scriptPath" in cmd and str(temp_path / "scripts") in cmd, True)
    check("script uses discoverable name", "RiftAnchorSurvey.java" in cmd, True)

print("=== Ghidra script errors ===")
ok_result = subprocess.CompletedProcess(["ghidra"], 0, "ok", "")
script_error_result = subprocess.CompletedProcess(["ghidra"], 0, "REPORT SCRIPT ERROR: bad script", "")
stderr_script_error_result = subprocess.CompletedProcess(["ghidra"], 0, "", "REPORT SCRIPT ERROR: bad script")
check("normal output has no script error", ghidra_runner._has_ghidra_script_error(ok_result), False)
check("stdout script error detected", ghidra_runner._has_ghidra_script_error(script_error_result), True)
check("stderr script error detected", ghidra_runner._has_ghidra_script_error(stderr_script_error_result), True)

print("=== rift_workflow ghidra-run routing ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    project_dir = temp_path / "projects"
    script_file = temp_path / "scripts" / "FunctionSiteSurvey.java"
    report_file = temp_path / "reports" / "twad.json"
    script_file.parent.mkdir()
    report_file.parent.mkdir()
    script_file.write_text("// test\n", encoding="utf-8")

    captured: dict[str, Any] = {}

    def fake_ghidra_run(**kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(["ghidra"], 0, "ok", "")

    workflow_argv = [
        "rift_workflow.py",
        "ghidra-run",
        "--ghidra-project-dir",
        str(project_dir),
        "--ghidra-project-name",
        "RiftAnchorSurvey",
        "--ghidra-process",
        "rift_x64.exe",
        "--ghidra-script",
        str(script_file),
        "--ghidra-script-arg",
        "0x1406e905f",
        "--ghidra-script-arg",
        str(report_file),
        "--ghidra-no-analysis",
        "--ghidra-keep-project",
        "--ghidra-timeout",
        "14400",
    ]

    with (
        patch.object(sys, "argv", workflow_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        patch("scripts.ghidra_runner.run_ghidra_headless", side_effect=fake_ghidra_run),
    ):
        rift_workflow.main()

    check("workflow project dir forwarded", captured["project_dir"], project_dir)
    check("workflow project name forwarded", captured["project_name"], "RiftAnchorSurvey")
    check("workflow process forwarded", captured["process_path"], "rift_x64.exe")
    check("workflow script forwarded", captured["script"], str(script_file))
    check("workflow script args forwarded", captured["script_args"], ["0x1406e905f", str(report_file)])
    check("workflow no-analysis forwarded", captured["analyze"], False)
    check("workflow keep-project forwarded", captured["delete_project"], False)
    check("workflow timeout forwarded", captured["timeout_seconds"], 14400)

print("=== rift_workflow ghidra-function-site-survey routing ===")
target_schema = json.loads(Path("docs/schemas/ghidra-function-site-targets-v1.schema.json").read_text(encoding="utf-8"))
target_registry = json.loads(Path("docs/ghidra-function-site-targets.json").read_text(encoding="utf-8"))
jsonschema.validate(target_registry, target_schema)
check("function survey target registry schema", target_registry["SchemaVersion"], "ghidra-function-site-targets/v1")
guarded_registry = rift_workflow._guard_ghidra_function_site_targets(Path("docs/ghidra-function-site-targets.json"))
check("function survey target guard count", len(guarded_registry["Targets"]), len(target_registry["Targets"]))
guard_output = io.StringIO()
with (
    patch.object(sys, "argv", ["rift_workflow.py", "ghidra-function-site-target-guard"]),
    patch("scripts.rift_workflow.generated_output_guard"),
    redirect_stdout(guard_output),
):
    rift_workflow.main()
check_contains("function survey target guard command", guard_output.getvalue(), "GhidraFunctionSiteTargetGuard passed")
list_output = io.StringIO()
with (
    patch.object(sys, "argv", ["rift_workflow.py", "ghidra-function-site-survey", "--list-json"]),
    patch("scripts.rift_workflow.generated_output_guard"),
    redirect_stdout(list_output),
):
    rift_workflow.main()
list_payload = parse_json_object(list_output.getvalue())
check("function survey list-json schema", list_payload["SchemaVersion"], "ghidra-function-site-target-list/v1")
check("function survey list-json count", list_payload["TargetCount"], len(target_registry["Targets"]))
target_list_schema = json.loads(
    Path("docs/schemas/ghidra-function-site-target-list-v1.schema.json").read_text(encoding="utf-8")
)
jsonschema.validate(list_payload, target_list_schema)
print("  PASS: function survey list-json schema validation")
status_output = io.StringIO()
with (
    patch.object(sys, "argv", ["rift_workflow.py", "ghidra-function-site-status", "--list-json"]),
    patch("scripts.rift_workflow.generated_output_guard"),
    redirect_stdout(status_output),
):
    rift_workflow.main()
status_payload = parse_json_object(status_output.getvalue())
check("function survey status schema", status_payload["SchemaVersion"], "ghidra-function-site-status/v1")
check("function survey status count", status_payload["TargetCount"], len(target_registry["Targets"]))
target_status_schema = json.loads(
    Path("docs/schemas/ghidra-function-site-status-v1.schema.json").read_text(encoding="utf-8")
)
jsonschema.validate(status_payload, target_status_schema)
print("  PASS: function survey status schema validation")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    script_file = temp_path / "FunctionSiteSurvey.java"
    report_file = temp_path / "reports" / "target.json"
    summary_file = temp_path / "reports" / "target.md"
    targets_file = temp_path / "targets.json"
    script_file.write_text("// test\n", encoding="utf-8")
    targets_file.write_text(
        json.dumps(
            {
                "SchemaVersion": "ghidra-function-site-targets/v1",
                "CandidateOnly": True,
                "DefaultProjectName": "RiftAnchorSurvey",
                "DefaultProcess": "rift_x64.exe",
                "DefaultScript": str(script_file),
                "DefaultNoAnalysis": True,
                "DefaultKeepProject": True,
                "DefaultTimeoutSeconds": 900,
                "Targets": [
                    {
                        "Key": "test-target",
                        "Address": "0x141186980",
                        "ReportPath": str(report_file),
                        "SummaryPath": str(summary_file),
                        "SummaryTerms": ["NiDataStream", "LoadBinary"],
                        "Description": "test target",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    dry_run_argv = [
        "rift_workflow.py",
        "ghidra-function-site-survey",
        "--ghidra-targets-file",
        str(targets_file),
        "--ghidra-target",
        "test-target",
    ]
    dry_run_output = io.StringIO()
    with (
        patch.object(sys, "argv", dry_run_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(dry_run_output),
    ):
        rift_workflow.main()
    dry_run_text = dry_run_output.getvalue()
    check_contains("function survey dry-run target", dry_run_text, "GhidraFunctionSiteSurvey target: test-target")
    check_contains("function survey dry-run run command", dry_run_text, "ghidra-run")
    check_contains("function survey dry-run summary command", dry_run_text, "ghidra-summarize")

    captured_run: dict[str, Any] = {}
    captured_summary: dict[str, Any] = {}

    def fake_function_site_run(**kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured_run.update(kwargs)
        return subprocess.CompletedProcess(["ghidra"], 0, "ok", "")

    def fake_summarize_file(input_path: str, **kwargs: Any) -> str:
        captured_summary["input_path"] = input_path
        captured_summary.update(kwargs)
        return "# summary\n"

    execute_argv = dry_run_argv + ["--ghidra-execute"]
    with (
        patch.object(sys, "argv", execute_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        patch("scripts.ghidra_runner.run_ghidra_headless", side_effect=fake_function_site_run),
        patch("scripts.ghidra_report_summary.summarize_file", side_effect=fake_summarize_file),
    ):
        rift_workflow.main()

    check("function survey process forwarded", captured_run["process_path"], "rift_x64.exe")
    check("function survey script forwarded", captured_run["script"], str(script_file))
    check("function survey args forwarded", captured_run["script_args"], ["0x141186980", str(report_file)])
    check("function survey default no-analysis", captured_run["analyze"], False)
    check("function survey default keep-project", captured_run["delete_project"], False)
    check("function survey summary input", captured_summary["input_path"], str(report_file))
    check("function survey summary output", captured_summary["output_path"], str(summary_file))
    check("function survey terms", captured_summary["terms"], ["NiDataStream", "LoadBinary"])

print("=== rift_workflow NiDataStream descriptor table sampler routing ===")
descriptor_sample_schema = json.loads(
    Path("docs/schemas/ghidra-descriptor-table-sample-v1.schema.json").read_text(encoding="utf-8")
)
descriptor_neighborhood_schema = json.loads(
    Path("docs/schemas/ghidra-descriptor-table-neighborhood-scan-v1.schema.json").read_text(encoding="utf-8")
)
descriptor_reference_schema = json.loads(
    Path("docs/schemas/ghidra-descriptor-reference-classification-v1.schema.json").read_text(encoding="utf-8")
)
descriptor_base_model_schema = json.loads(
    Path("docs/schemas/nidatastream-descriptor-base-model-review-v1.schema.json").read_text(encoding="utf-8")
)
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    report_file = temp_path / "reports" / "descriptor-table.json"
    summary_file = temp_path / "reports" / "descriptor-table.md"
    project_dir = temp_path / "projects"
    list_output = io.StringIO()
    list_argv = [
        "rift_workflow.py",
        "nidatastream-descriptor-table-sample",
        "--descriptor-index",
        "37,36",
        "--descriptor-table-report",
        str(report_file),
        "--descriptor-table-summary",
        str(summary_file),
        "--list-json",
    ]
    with (
        patch.object(sys, "argv", list_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(list_output),
    ):
        rift_workflow.main()
    sample_plan = parse_json_object(list_output.getvalue())
    check("descriptor table sample plan schema", sample_plan["SchemaVersion"], "nidatastream-descriptor-table-sample-plan/v1")
    check("descriptor table sample plan index count", sample_plan["IndexCount"], 2)
    check("descriptor table sample first index value", sample_plan["Indices"][0]["Value"], 55)
    check("descriptor table sample second index value", sample_plan["Indices"][1]["Value"], 54)
    check("descriptor table sample plan field count", sample_plan["FieldCount"], 3)
    check("descriptor table sample plan rows", sample_plan["PlannedRowCount"], 6)
    check("descriptor table sample plan candidate-only", sample_plan["CandidateOnly"], True)

    all_indices_output = io.StringIO()
    all_indices_argv = [
        "rift_workflow.py",
        "nidatastream-descriptor-table-sample",
        "--descriptor-table-all-byte-indices",
        "--descriptor-table-report",
        str(report_file),
        "--descriptor-table-summary",
        str(summary_file),
        "--list-json",
    ]
    with (
        patch.object(sys, "argv", all_indices_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(all_indices_output),
    ):
        rift_workflow.main()
    all_indices_plan = parse_json_object(all_indices_output.getvalue())
    check("descriptor table sample all-index flag", all_indices_plan["AllByteIndices"], True)
    check("descriptor table sample all-index count", all_indices_plan["IndexCount"], 256)
    check("descriptor table sample all-index first", all_indices_plan["Indices"][0]["ValueHex"], "00")
    check("descriptor table sample all-index last", all_indices_plan["Indices"][-1]["ValueHex"], "ff")
    check("descriptor table sample all-index rows", all_indices_plan["PlannedRowCount"], 768)

    blocked_output = io.StringIO()
    blocked_argv = [
        *list_argv[:-1],
        "--descriptor-table-byte-count",
        "65",
        "--list-json",
    ]
    with (
        patch.object(sys, "argv", blocked_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(blocked_output),
    ):
        rift_workflow.main()
    blocked_plan = parse_json_object(blocked_output.getvalue())
    check_contains(
        "descriptor table sample byte-count blocker",
        ",".join(blocked_plan["Blockers"]),
        "descriptor-table-sample-byte-count-too-large",
    )

    dry_run_output = io.StringIO()
    dry_run_argv = list_argv[:-1]
    with (
        patch.object(sys, "argv", dry_run_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(dry_run_output),
    ):
        rift_workflow.main()
    check_contains("descriptor table sample dry-run title", dry_run_output.getvalue(), "NiDataStreamDescriptorTableSample")
    check_contains("descriptor table sample dry-run command", dry_run_output.getvalue(), "DescriptorTableSampler.java")

    captured_sample: dict[str, Any] = {}

    def fake_descriptor_table_run(**kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured_sample.update(kwargs)
        output_path = Path(kwargs["script_args"][0])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "SchemaVersion": "ghidra-descriptor-table-sample/v1",
                    "CandidateOnly": True,
                    "FieldOrderPromoted": False,
                    "ParserExportPromotionAllowed": False,
                    "programName": "rift_x64.exe",
                    "imageBase": "140000000",
                    "strideBytes": 12,
                    "byteCountRequested": 4,
                    "indexCount": 2,
                    "fieldCount": 3,
                    "rowCount": 1,
                    "rows": [
                        {
                            "field": "descriptor-component-class",
                            "baseAddress": "143358be4",
                            "staticTableOffsetBytes": 4,
                            "index": 55,
                            "indexHex": "37",
                            "strideBytes": 12,
                            "byteCountRequested": 4,
                            "computedAddress": "143358e78",
                            "byteCountRead": 4,
                            "bytes": "01 02 03 04",
                        }
                    ],
                    "interpretation": "candidate-only test fixture",
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(["ghidra"], 0, "ok", "")

    execute_argv = dry_run_argv + ["--ghidra-project-dir", str(project_dir), "--ghidra-execute"]
    with (
        patch.object(sys, "argv", execute_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        patch("scripts.ghidra_runner.run_ghidra_headless", side_effect=fake_descriptor_table_run),
    ):
        rift_workflow.main()

    descriptor_report = json.loads(report_file.read_text(encoding="utf-8"))
    jsonschema.validate(descriptor_report, descriptor_sample_schema)
    print("  PASS: descriptor table sample report schema validation")
    check("descriptor table sample script", captured_sample["script"], "scripts/ghidra/DescriptorTableSampler.java")
    check("descriptor table sample args report", captured_sample["script_args"][0], str(report_file))
    check("descriptor table sample first index arg", captured_sample["script_args"][3], "0x37")
    check("descriptor table sample second index arg", captured_sample["script_args"][4], "0x36")
    check("descriptor table sample no-analysis", captured_sample["analyze"], False)
    check("descriptor table sample keeps project", captured_sample["delete_project"], False)
    check("descriptor table sample markdown written", summary_file.exists(), True)

print("=== rift_workflow NiDataStream descriptor neighborhood scan routing ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    report_file = temp_path / "reports" / "descriptor-neighborhood.json"
    summary_file = temp_path / "reports" / "descriptor-neighborhood.md"
    project_dir = temp_path / "projects"
    list_output = io.StringIO()
    list_argv = [
        "rift_workflow.py",
        "nidatastream-descriptor-neighborhood-scan",
        "--descriptor-neighborhood-before",
        "16",
        "--descriptor-neighborhood-after",
        "32",
        "--descriptor-neighborhood-report",
        str(report_file),
        "--descriptor-neighborhood-summary",
        str(summary_file),
        "--list-json",
    ]
    with (
        patch.object(sys, "argv", list_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(list_output),
    ):
        rift_workflow.main()
    neighborhood_plan = parse_json_object(list_output.getvalue())
    check(
        "descriptor neighborhood scan plan schema",
        neighborhood_plan["SchemaVersion"],
        "nidatastream-descriptor-neighborhood-scan-plan/v1",
    )
    check("descriptor neighborhood scan plan field count", neighborhood_plan["FieldCount"], 3)
    check("descriptor neighborhood scan plan before", neighborhood_plan["BeforeBytes"], 16)
    check("descriptor neighborhood scan plan after", neighborhood_plan["AfterBytes"], 32)
    check("descriptor neighborhood scan candidate-only", neighborhood_plan["CandidateOnly"], True)

    captured_scan: dict[str, Any] = {}

    def fake_descriptor_neighborhood_run(**kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured_scan.update(kwargs)
        output_path = Path(kwargs["script_args"][0])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "SchemaVersion": "ghidra-descriptor-table-neighborhood-scan/v1",
                    "CandidateOnly": True,
                    "FieldOrderPromoted": False,
                    "ParserExportPromotionAllowed": False,
                    "programName": "rift_x64.exe",
                    "imageBase": "140000000",
                    "beforeBytes": 16,
                    "afterBytes": 32,
                    "stepBytes": 4,
                    "byteCountRequested": 4,
                    "maxHits": 128,
                    "fieldCount": 3,
                    "scannedRowCount": 39,
                    "memoryBackedRowCount": 39,
                    "skippedRowCount": 0,
                    "hitCount": 1,
                    "truncated": False,
                    "hits": [
                        {
                            "field": "descriptor-component-class",
                            "baseAddress": "143358be4",
                            "relativeOffsetBytes": -4,
                            "address": "143358be0",
                            "byteCountRead": 4,
                            "bytes": "01 02 03 04",
                        }
                    ],
                    "interpretation": "candidate-only test fixture",
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(["ghidra"], 0, "ok", "")

    execute_argv = list_argv[:-1] + ["--ghidra-project-dir", str(project_dir), "--ghidra-execute"]
    with (
        patch.object(sys, "argv", execute_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        patch("scripts.ghidra_runner.run_ghidra_headless", side_effect=fake_descriptor_neighborhood_run),
    ):
        rift_workflow.main()

    neighborhood_report = json.loads(report_file.read_text(encoding="utf-8"))
    jsonschema.validate(neighborhood_report, descriptor_neighborhood_schema)
    print("  PASS: descriptor neighborhood scan report schema validation")
    check("descriptor neighborhood scan script", captured_scan["script"], "scripts/ghidra/DescriptorTableNeighborhoodScanner.java")
    check("descriptor neighborhood scan args report", captured_scan["script_args"][0], str(report_file))
    check("descriptor neighborhood scan before arg", captured_scan["script_args"][1], "16")
    check("descriptor neighborhood scan after arg", captured_scan["script_args"][2], "32")
    check("descriptor neighborhood scan markdown written", summary_file.exists(), True)

print("=== rift_workflow NiDataStream descriptor reference classification routing ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    report_file = temp_path / "reports" / "descriptor-reference.json"
    summary_file = temp_path / "reports" / "descriptor-reference.md"
    project_dir = temp_path / "projects"
    list_output = io.StringIO()
    list_argv = [
        "rift_workflow.py",
        "nidatastream-descriptor-reference-classify",
        "--descriptor-reference-byte-count",
        "8",
        "--descriptor-reference-max-refs",
        "4",
        "--descriptor-reference-report",
        str(report_file),
        "--descriptor-reference-summary",
        str(summary_file),
        "--list-json",
    ]
    with (
        patch.object(sys, "argv", list_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(list_output),
    ):
        rift_workflow.main()
    reference_plan = parse_json_object(list_output.getvalue())
    check(
        "descriptor reference classify plan schema",
        reference_plan["SchemaVersion"],
        "nidatastream-descriptor-reference-classify-plan/v1",
    )
    check("descriptor reference classify plan field count", reference_plan["FieldCount"], 3)
    check("descriptor reference classify plan byte count", reference_plan["ByteCountRequested"], 8)
    check("descriptor reference classify max refs", reference_plan["MaxRefsPerField"], 4)
    check("descriptor reference classify candidate-only", reference_plan["CandidateOnly"], True)

    captured_reference: dict[str, Any] = {}

    def fake_descriptor_reference_run(**kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured_reference.update(kwargs)
        output_path = Path(kwargs["script_args"][0])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "SchemaVersion": "ghidra-descriptor-reference-classification/v1",
                    "CandidateOnly": True,
                    "FieldOrderPromoted": False,
                    "ParserExportPromotionAllowed": False,
                    "programName": "rift_x64.exe",
                    "imageBase": "140000000",
                    "byteCountRequested": 8,
                    "maxRefsPerField": 4,
                    "fieldCount": 1,
                    "fields": [
                        {
                            "field": "descriptor-component-class",
                            "address": "143358be4",
                            "addressValid": True,
                            "memoryBacked": True,
                            "memoryBlockName": ".data",
                            "memoryBlockStart": "143300000",
                            "memoryBlockEnd": "1433fffff",
                            "memoryBlockSize": 1048576,
                            "memoryBlockInitialized": True,
                            "memoryBlockLoaded": True,
                            "memoryBlockRead": True,
                            "memoryBlockWrite": True,
                            "memoryBlockExecute": False,
                            "memoryBlockVolatile": False,
                            "memoryBlockArtificial": False,
                            "memoryBlockType": "DEFAULT",
                            "memoryBlockSourceName": "rift_x64.exe",
                            "byteCountRead": 8,
                            "bytes": "00 00 00 00 00 00 00 00",
                            "symbolCount": 1,
                            "symbols": [
                                {
                                    "name": "DAT_143358be4",
                                    "type": "LABEL",
                                    "source": "DEFAULT",
                                    "primary": True,
                                    "dynamic": True,
                                }
                            ],
                            "referenceCountTo": 1,
                            "capturedReferenceCount": 1,
                            "referencesTruncated": False,
                            "readReferenceCount": 1,
                            "writeReferenceCount": 0,
                            "dataReferenceCount": 1,
                            "addressLikeReferenceCount": 0,
                            "flowReferenceCount": 0,
                            "referencingFunctionCount": 1,
                            "references": [
                                {
                                    "fromAddress": "141182242",
                                    "toAddress": "143358be4",
                                    "operandIndex": 1,
                                    "referenceType": "READ",
                                    "referenceKind": "read",
                                    "source": "ANALYSIS",
                                    "primary": True,
                                    "data": True,
                                    "read": True,
                                    "write": False,
                                    "flow": False,
                                    "call": False,
                                    "jump": False,
                                    "computed": False,
                                    "indirect": False,
                                    "memoryReference": True,
                                    "offsetReference": False,
                                    "shiftedReference": False,
                                    "externalReference": False,
                                    "operandReference": True,
                                    "mnemonicReference": False,
                                    "fromFunction": "FUN_1411821f0",
                                    "fromFunctionEntry": "1411821f0",
                                    "fromFunctionSignature": "undefined FUN_1411821f0(void)",
                                    "instructionAddress": "141182242",
                                    "instructionMnemonic": "MOV",
                                    "instructionText": "MOV EAX,dword ptr [RAX + RCX*0x4 + 0x4]",
                                    "instructionBytes": "8b 05 00 00 00 00",
                                }
                            ],
                        }
                    ],
                    "totalReferenceCount": 1,
                    "totalCapturedReferenceCount": 1,
                    "fieldWithReferencesCount": 1,
                    "readReferenceCount": 1,
                    "writeReferenceCount": 0,
                    "dataReferenceCount": 1,
                    "addressLikeReferenceCount": 0,
                    "uniqueReferencingFunctionCount": 1,
                    "interpretation": "candidate-only test fixture",
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(["ghidra"], 0, "ok", "")

    execute_argv = list_argv[:-1] + ["--ghidra-project-dir", str(project_dir), "--ghidra-execute"]
    with (
        patch.object(sys, "argv", execute_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        patch("scripts.ghidra_runner.run_ghidra_headless", side_effect=fake_descriptor_reference_run),
    ):
        rift_workflow.main()

    reference_report = json.loads(report_file.read_text(encoding="utf-8"))
    jsonschema.validate(reference_report, descriptor_reference_schema)
    print("  PASS: descriptor reference classification report schema validation")
    check("descriptor reference classify script", captured_reference["script"], "scripts/ghidra/DescriptorReferenceClassifier.java")
    check("descriptor reference classify args report", captured_reference["script_args"][0], str(report_file))
    check("descriptor reference classify byte-count arg", captured_reference["script_args"][1], "8")
    check("descriptor reference classify max refs arg", captured_reference["script_args"][2], "4")
    check("descriptor reference classify markdown written", summary_file.exists(), True)

    base_model_report = temp_path / "reports" / "descriptor-base-model.json"
    base_model_summary = temp_path / "reports" / "descriptor-base-model.md"
    base_model_output = io.StringIO()
    base_model_argv = [
        "rift_workflow.py",
        "nidatastream-descriptor-base-model-review",
        "--out",
        str(temp_path),
        "--descriptor-base-model-reference-report",
        str(report_file),
        "--descriptor-base-model-report",
        str(base_model_report),
        "--descriptor-base-model-summary",
        str(base_model_summary),
        "--list-json",
    ]
    with (
        patch.object(sys, "argv", base_model_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(base_model_output),
    ):
        rift_workflow.main()
    base_model = parse_json_object(base_model_output.getvalue())
    jsonschema.validate(base_model, descriptor_base_model_schema)
    print("  PASS: descriptor base model review schema validation")
    check("descriptor base model schema", base_model["SchemaVersion"], "nidatastream-descriptor-base-model-review/v1")
    check("descriptor base model scale", base_model["InstructionScaleCandidates"][0]["ScaleBytes"], 4)
    check("descriptor base model candidate-only", base_model["CandidateOnly"], True)

    with (
        patch.object(sys, "argv", base_model_argv[:-1]),
        patch("scripts.rift_workflow.generated_output_guard"),
    ):
        rift_workflow.main()
    check("descriptor base model JSON written", base_model_report.exists(), True)
    check("descriptor base model markdown written", base_model_summary.exists(), True)

with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    bad_targets_file = temp_path / "bad-targets.json"
    bad_registry = dict(target_registry)
    bad_registry["Targets"] = [
        {
            "Key": "unsafe-target",
            "Address": "0x141186980",
            "ReportPath": "Exports/ghidra-reports/../unsafe.json",
            "SummaryPath": "Exports/ghidra-reports/unsafe.md",
            "SummaryTerms": ["NiDataStream"],
            "Description": "unsafe path target",
        }
    ]
    bad_targets_file.write_text(json.dumps(bad_registry), encoding="utf-8")
    check_raises(
        "function survey target guard rejects parent traversal",
        lambda: rift_workflow._guard_ghidra_function_site_targets(bad_targets_file),
        "parent-dir",
    )

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
