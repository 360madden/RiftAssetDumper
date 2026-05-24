#!/usr/bin/env python3
"""Convenience wrapper for running Ghidra headless with the correct JDK.

Automatically resolves Java and Ghidra paths from .tools.json so AI agents
can invoke Ghidra without manually specifying paths.

Usage:
    python scripts/ghidra_runner.py --help
    python scripts/ghidra_runner.py --project /tmp/ghidra_proj --import some.dll
    python scripts/ghidra_runner.py --script my_script.java
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Ensure parent is on path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.rift_workflow_utils import load_tools_config  # noqa: E402

DEFAULT_TIMEOUT_SECONDS = 900


def _resolve_tool(config: dict[str, Any], name: str) -> tuple[str, str]:
    """Resolve tool path and home from config, raising on missing install."""
    tools = config.get("tools", {})
    tool = tools.get(name)
    if not tool or not isinstance(tool, dict):
        raise RuntimeError(
            f"Tool '{name}' not found in .tools.json. "
            "Run 'python scripts/rift_workflow.py tools-status' to inspect configured tools."
        )
    if not tool.get("installed"):
        resolved_path = tool.get("resolved_path", "")
        raise RuntimeError(
            f"Tool '{name}' is not installed. Expected at: {resolved_path or tool.get('path', '?')}"
        )
    resolved = tool.get("resolved_path", "")
    home = tool.get("home", "")
    if home:
        # Resolve home relative to REPO_ROOT if it's a relative path
        home_path = Path(home)
        if not home_path.is_absolute():
            home_path = (REPO_ROOT / home).resolve()
        home = str(home_path)
    return resolved, home


def _build_ghidra_env(java_path: str, java_home: str) -> dict[str, str]:
    """Build an environment where Ghidra can find the configured JDK."""
    env = os.environ.copy()
    if java_home:
        env["JAVA_HOME"] = java_home

    java_bin = str(Path(java_path).resolve().parent) if java_path else ""
    if java_bin:
        path_key = "Path" if "Path" in env else "PATH"
        current_path = env.get(path_key, "")
        env[path_key] = os.pathsep.join([java_bin, current_path]) if current_path else java_bin

    return env


def _has_ghidra_script_error(result: subprocess.CompletedProcess[str]) -> bool:
    """Return True when Ghidra reports script failure despite exit code 0."""
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    return "REPORT SCRIPT ERROR" in output


def run_ghidra_headless(
    project_dir: str | Path,
    project_name: str = "TempProject",
    import_path: str | None = None,
    process_path: str | None = None,
    script: str | Path | None = None,
    script_args: list[str] | None = None,
    script_path: str | Path | None = None,
    analyze: bool = True,
    delete_project: bool = True,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess:
    """Run Ghidra in headless mode with automatic JDK resolution.

    Args:
        project_dir: Directory to create/open the Ghidra project in.
        project_name: Name for the Ghidra project.
        import_path: Optional path to a binary/DLL to import.
        process_path: Optional existing project file to process.
        script: Optional Python script to run post-import.
        script_args: Optional list of args to pass to the script.
        script_path: Optional additional Ghidra script search path.
        analyze: If False, pass -noanalysis.
        delete_project: If True, pass -deleteProject to clean up.
        timeout_seconds: Max seconds to wait for Ghidra.

    Returns:
        subprocess.CompletedProcess with stdout/stderr.

    Raises:
        RuntimeError: If Ghidra or JDK are not installed.
        subprocess.TimeoutExpired: If Ghidra takes too long (first launch is slow).
    """
    config = load_tools_config()
    ghidra_path, ghidra_home = _resolve_tool(config, "ghidra")
    java_path, java_home = _resolve_tool(config, "jdk21")
    env = _build_ghidra_env(java_path, java_home)
    Path(project_dir).mkdir(parents=True, exist_ok=True)

    # Build the command
    cmd = [ghidra_path, str(project_dir), project_name]

    if import_path and process_path:
        raise ValueError("Use either import_path or process_path, not both.")

    if import_path:
        cmd += ["-import", str(import_path)]
    elif process_path:
        cmd += ["-process", str(process_path)]

    if not analyze:
        cmd.append("-noanalysis")

    if script:
        script_arg = str(script)
        if script_path:
            cmd += ["-scriptPath", str(script_path)]
        else:
            script_file = Path(script)
            if script_file.exists():
                cmd += ["-scriptPath", str(script_file.parent)]
                script_arg = script_file.name
        cmd += ["-postScript", script_arg]
        if script_args:
            cmd += script_args

    if delete_project:
        cmd.append("-deleteProject")

    print(f"\n==> Ghidra headless: {' '.join(str(a) for a in cmd)}")
    print(f"    JAVA_HOME: {java_home}")
    print(f"    Timeout: {timeout_seconds}s")
    print()

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        env=env,
    )

    return result


def dry_run_ghidra_headless(
    project_dir: str | Path | None = None,
    project_name: str = "TempProject",
    import_path: str | None = None,
    process_path: str | None = None,
    script: str | None = None,
    script_args: list[str] | None = None,
    script_path: str | None = None,
    analyze: bool = True,
    keep_project: bool = False,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> None:
    """Print resolved Ghidra/JDK settings without launching Ghidra."""
    if project_dir is None:
        project_dir = REPO_ROOT / "Exports" / "ghidra-projects"

    config = load_tools_config()
    ghidra_path, ghidra_home = _resolve_tool(config, "ghidra")
    java_path, java_home = _resolve_tool(config, "jdk21")

    print(f"Ghidra:     {ghidra_path}")
    print(f"Ghidra home: {ghidra_home}")
    print(f"JDK:        {java_path}")
    print(f"JDK home:   {java_home}")
    print(f"Project:    {project_dir}/{project_name}")
    if import_path:
        print(f"Import:     {import_path}")
    if process_path:
        print(f"Process:    {process_path}")
    if script:
        print(f"Script:     {script} {script_args or []}")
    if script_path:
        print(f"Script path: {script_path}")
    if not analyze:
        print("Analysis:   disabled (-noanalysis)")
    if keep_project:
        print("Keep project: yes")
    print(f"Timeout:    {timeout_seconds}s")
    print()
    print("Dry-run: use the command above to run manually.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Ghidra headless with automatic JDK resolution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--project-dir",
        default=str(REPO_ROOT / "Exports" / "ghidra-projects"),
        help="Directory for the Ghidra project (default: Exports/ghidra-projects)",
    )
    parser.add_argument(
        "--project-name",
        default="TempProject",
        help="Ghidra project name (default: TempProject)",
    )
    parser.add_argument(
        "--import",
        dest="import_path",
        default=None,
        help="Binary/DLL to import into Ghidra",
    )
    parser.add_argument(
        "--process",
        dest="process_path",
        default=None,
        help="Existing project file to process",
    )
    parser.add_argument(
        "--script",
        default=None,
        help="Ghidra post-script to run post-import; Java scripts are the proven path for this repo",
    )
    parser.add_argument(
        "--script-path",
        default=None,
        help="Additional Ghidra script search path",
    )
    parser.add_argument(
        "--script-args",
        nargs=argparse.REMAINDER,
        default=[],
        help="Additional args passed to the script; must be the final runner option",
    )
    parser.add_argument(
        "--keep-project",
        action="store_true",
        help="Don't delete the Ghidra project after analysis",
    )
    parser.add_argument(
        "--no-analysis",
        action="store_true",
        help="Pass -noanalysis to skip auto-analysis",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Max seconds to wait for Ghidra (default: {DEFAULT_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be run without executing",
    )

    args = parser.parse_args()

    if args.dry_run:
        try:
            dry_run_ghidra_headless(
                project_dir=args.project_dir,
                project_name=args.project_name,
                import_path=args.import_path,
                process_path=args.process_path,
                script=args.script,
                script_args=args.script_args,
                script_path=args.script_path,
                analyze=not args.no_analysis,
                keep_project=args.keep_project,
                timeout_seconds=args.timeout,
            )
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    try:
        result = run_ghidra_headless(
            project_dir=args.project_dir,
            project_name=args.project_name,
            import_path=args.import_path,
            process_path=args.process_path,
            script=args.script,
            script_args=args.script_args if args.script_args else None,
            script_path=args.script_path,
            analyze=not args.no_analysis,
            delete_project=not args.keep_project,
            timeout_seconds=args.timeout,
        )

        print(f"Exit code: {result.returncode}")
        if result.stdout:
            print("--- stdout ---")
            print(result.stdout[:5000])
        if result.stderr:
            print("--- stderr ---")
            print(result.stderr[:5000])

        script_error = _has_ghidra_script_error(result)

        if result.returncode != 0 or script_error:
            if script_error and result.returncode == 0:
                print("\nGhidra reported a script error despite exit code 0", file=sys.stderr)
            print(f"\nGhidra exited with code {result.returncode}", file=sys.stderr)
            sys.exit(result.returncode or 1)

        print("\nGhidra headless completed successfully.")

    except FileNotFoundError as exc:
        print(f"ERROR: Ghidra executable not found: {exc}", file=sys.stderr)
        print("Run 'python scripts/rift_workflow.py tools-status' to verify installation.", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(
            f"ERROR: Ghidra timed out after {args.timeout}s. "
            "First launch is slow (2-5 min). Try increasing --timeout.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
