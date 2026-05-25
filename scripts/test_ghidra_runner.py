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
