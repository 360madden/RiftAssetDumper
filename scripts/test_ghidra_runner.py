"""Smoke tests for ghidra_runner.py."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

sys.path.insert(0, ".")

from scripts import ghidra_runner

failed = 0


def check(desc: str, actual: Any, expected: Any) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc}  expected={expected!r}  actual={actual!r}")
        failed += 1


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

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
