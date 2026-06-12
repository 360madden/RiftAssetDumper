#!/usr/bin/env python3
"""C2-1.1 baseline runner.

Runs the 13 completion-baseline checks defined in
``docs/roadmap/cycle-2-scene-manifest-plan.md`` (step C2-1.1):

* dotnet build
* dotnet test
* pytest tests/
* ruff check scripts/
* mypy scripts/ --no-error-summary
* 8 proof guards (attribute-extra, attribute-extra-sibling,
  usage-access-correlation, position-source-sibling-lead, residual-lead,
  ghidra-function-site-target, ghidra-pairing-non-export,
  ghidra-attribute-candidate)

For each check we capture: return code, wall-clock seconds, start/end
ISO-8601 UTC timestamps, and the first 40 lines of stdout + stderr.
Results are written to ``Assets/Exports/discovery-plan/cycle-2/stage1/baseline/baseline.json``.

Idempotent: re-running overwrites ``baseline.json``. Does NOT mutate
``.state.json`` (use ``python scripts/cycle_2_plan.py complete`` for that).

Exit code: 0 if all checks green, 1 otherwise. Printed to stdout.

Usage:
    python scripts/run_cycle_2_baseline.py            # default: fast baseline (9 checks, <5 min)
    python scripts/run_cycle_2_baseline.py --full     # all 13 checks incl. 4 slow guards (5+ hours)
    python scripts/run_cycle_2_baseline.py --output <path>  # override output path

Default (fast) mode:
- Skips the 4 slow full-inventory guards (attribute-extra-proof-guard,
  usage-access-correlation-guard, position-source-sibling-lead-guard,
  residual-lead-guard) — each takes 60+ min on the current 264K-payload
  live archive.
- Skips the attribute-extra-sibling-proof-guard (mesh-specific: requires
  --id and --mesh-block; not a project-wide check).
- Captures 8 project-wide checks: dotnet-build, dotnet-test, pytest, ruff,
  mypy, ghidra-function-site-target-guard, ghidra-pairing-non-export-guard,
  ghidra-attribute-candidate-guard.

Use --full for the complete 13-check sweep (intended for background / overnight
runs). The slow-guard evidence is then captured in the same baseline.json
under the same schema.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger("c2_baseline")

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "Exports" / "discovery-plan" / "cycle-2" / "stage1" / "baseline" / "baseline.json"
PYTHON = sys.executable

# Per-check timeout. 4 of the 8 proof guards do full-inventory work and
# historically take 600-1200s on a warm cache. Build/test/lint are fast.
TIMEOUT_BUILD = 300
TIMEOUT_TEST = 600
TIMEOUT_LINT = 180
TIMEOUT_PROOF = 1700  # 4 slow guards
TIMEOUT_FAST_GUARD = 300


def _now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z")


def _git_head() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def _truncate(text: str, lines: int = 20) -> str:
    """Keep first 20 + last 20 lines. Guard output prints PASS/FAIL at the tail;
    head-only truncation would drop the verdict.
    """
    if not text:
        return ""
    out_lines = text.splitlines()
    if len(out_lines) <= lines * 2:
        return "\n".join(out_lines)
    head = out_lines[:lines]
    tail = out_lines[-lines:]
    return "\n".join(head) + "\n... [truncated] ...\n" + "\n".join(tail)


def _run_check(name: str, cmd: list[str], timeout: float) -> dict[str, Any]:
    """Run a check via subprocess; capture return code, timing, truncated output."""
    start = _now_iso()
    t0 = _dt.datetime.now(_dt.UTC)
    log.info("[%s] starting: %s", name, " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        rc = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as e:
        rc = -1
        # text=True always gives str|None, never bytes
        stdout = e.stdout or ""
        stderr = f"TIMEOUT after {timeout}s\n" + (e.stderr or "")
    except Exception as e:  # noqa: BLE001
        rc = -2
        stdout = ""
        stderr = f"ERROR: {type(e).__name__}: {e}"
    elapsed = (_dt.datetime.now(_dt.UTC) - t0).total_seconds()
    end = _now_iso()
    passed = rc == 0
    log.info("[%s] %s in %.1fs (rc=%d)", name, "PASS" if passed else "FAIL", elapsed, rc)
    return {
        "name": name,
        "command": cmd,
        "returncode": rc,
        "passed": passed,
        "elapsed_seconds": round(elapsed, 2),
        "started_at": start,
        "ended_at": end,
        "stdout_head": _truncate(stdout),
        "stderr_head": _truncate(stderr),
    }


def _check_definitions(quick: bool) -> list[tuple[str, list[str], float]]:
    """Return [(name, command, timeout), ...] for all 13 baseline checks."""
    guards_full = [
        (
            "attribute-extra-proof-guard",
            [PYTHON, "scripts/rift_workflow.py", "attribute-extra-proof-guard", "--full", "--skip-build"],
            TIMEOUT_PROOF,
        ),
        (
            "attribute-extra-sibling-proof-guard",
            [PYTHON, "scripts/rift_workflow.py", "attribute-extra-sibling-proof-guard", "--full", "--skip-build"],
            TIMEOUT_FAST_GUARD,
        ),
        (
            "usage-access-correlation-guard",
            [PYTHON, "scripts/rift_workflow.py", "usage-access-correlation-guard", "--full", "--skip-build"],
            TIMEOUT_PROOF,
        ),
        (
            "position-source-sibling-lead-guard",
            [PYTHON, "scripts/rift_workflow.py", "position-source-sibling-lead-guard", "--full", "--skip-build"],
            TIMEOUT_PROOF,
        ),
        (
            "residual-lead-guard",
            [PYTHON, "scripts/rift_workflow.py", "residual-lead-guard", "--full", "--skip-build"],
            TIMEOUT_PROOF,
        ),
        (
            "ghidra-function-site-target-guard",
            [PYTHON, "scripts/rift_workflow.py", "ghidra-function-site-target-guard", "--full", "--skip-build"],
            TIMEOUT_FAST_GUARD,
        ),
        (
            "ghidra-pairing-non-export-guard",
            [PYTHON, "scripts/rift_workflow.py", "ghidra-pairing-non-export-guard", "--full", "--skip-build"],
            TIMEOUT_FAST_GUARD,
        ),
        (
            "ghidra-attribute-candidate-guard",
            [PYTHON, "scripts/rift_workflow.py", "ghidra-attribute-candidate-guard", "--full", "--skip-build"],
            TIMEOUT_FAST_GUARD,
        ),
    ]
    build_test_lint = [
        (
            "dotnet-build",
            ["dotnet", "build", "RiftAssetDumper.slnx", "--nologo"],
            TIMEOUT_BUILD,
        ),
        (
            "dotnet-test",
            ["dotnet", "test", "RiftAssetDumper.slnx", "--nologo", "--no-build"],
            TIMEOUT_TEST,
        ),
        (
            "pytest",
            [PYTHON, "-m", "pytest", "tests/", "-q", "--tb=line"],
            TIMEOUT_TEST,
        ),
        (
            "ruff",
            ["ruff", "check", "scripts/", "tests/"],
            TIMEOUT_LINT,
        ),
        (
            "mypy",
            [PYTHON, "-m", "mypy", "scripts/", "tests/", "--no-error-summary"],
            TIMEOUT_LINT,
        ),
    ]
    if quick:
        # --quick / default: skip the 4 slow full-inventory guards AND the
        # mesh-specific sibling guard (which requires --id --mesh-block and
        # is not a project-wide check).
        guards_full = [g for g in guards_full if g[2] < TIMEOUT_PROOF]
        guards_full = [g for g in guards_full if g[0] != "attribute-extra-sibling-proof-guard"]
    return build_test_lint + guards_full


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ap = argparse.ArgumentParser(description="C2-1.1 baseline runner")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path")
    ap.add_argument(
        "--quick",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip the 4 slow full-inventory guards + the mesh-specific sibling guard (default: True). Use --no-quick to run them.",
    )
    ap.add_argument(
        "--full",
        dest="quick",
        action="store_false",
        help="Run the complete 13-check sweep (incl. 4 slow guards + sibling guard). Takes 5+ hours.",
    )
    args = ap.parse_args()

    checks = _check_definitions(args.quick)
    log.info("Running %d checks (quick=%s)", len(checks), args.quick)
    results = [_run_check(name, cmd, timeout) for (name, cmd, timeout) in checks]
    all_green = all(r["passed"] for r in results)
    n_pass = sum(1 for r in results if r["passed"])
    n_fail = len(results) - n_pass

    payload = {
        "schema": "cycle-2-baseline/v1",
        "step": "C2-1.1",
        "plan": "cycle-2-scene-manifest-plan",
        "plan_version": "0.2",
        "generated_at": _now_iso(),
        "generated_by": "scripts/run_cycle_2_baseline.py",
        "git_head": _git_head(),
        "host": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "executable": sys.executable,
        },
        "summary": {
            "total": len(results),
            "passed": n_pass,
            "failed": n_fail,
            "all_green": all_green,
        },
        "checks": results,
    }

    out_path: Path = args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    log.info("Wrote %s", out_path)

    # Print a one-line status table for visibility
    print()
    print(f"{'Check':<48} {'Status':<6} {'Time':>8}")
    print("-" * 64)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"{r['name']:<48} {status:<6} {r['elapsed_seconds']:>7.1f}s")
    print("-" * 64)
    print(f"{'TOTAL':<48} {n_pass}/{len(results)} pass   all_green={all_green}")
    return 0 if all_green else 1


if __name__ == "__main__":
    sys.exit(main())
