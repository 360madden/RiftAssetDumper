#!/usr/bin/env python3
"""FT-5.1: Flythrough Bridge Plan orchestrator.

Reads/writes `Assets/build/flythrough/.state.json` to track phase progress.
Provides subcommands: status, step (--next / --id), complete, build.

Usage:
    python scripts/flythrough_plan.py status
    python scripts/flythrough_plan.py step --next
    python scripts/flythrough_plan.py step --id FT-5.1
    python scripts/flythrough_plan.py complete --id FT-5.1 --evidence path/to/evidence
    python scripts/flythrough_plan.py build [--resume] [--skip-textures]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger("flythrough_plan")

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = REPO_ROOT / "Assets" / "build" / "flythrough" / ".state.json"

# ASCII-safe status icons (emoji can break on Windows cp1252 consoles)
_ICONS: dict[str, str] = {
    "done": "[DONE]",
    "in_progress": "[BUSY]",
    "pending": "[----]",
    "blocked": "[FAIL]",
    "paused": "[PAUS]",
    "failed": "[FAIL]",
    "unknown": "[????]",
}

# Step dependency order: all steps in execution order
STEP_ORDER: list[str] = [
    # FT-1
    "FT-1.1",
    "FT-1.2",
    "FT-1.3",
    "FT-1.4",
    "FT-1.5",
    # FT-2
    "FT-2.1",
    "FT-2.2",
    "FT-2.3",
    "FT-2.4",
    "FT-2.5",
    # FT-3
    "FT-3.1",
    "FT-3.2",
    "FT-3.3",
    "FT-3.4",
    # FT-4 (keystone)
    "FT-4.1",
    "FT-4.2",
    "FT-4.3",
    "FT-4.4",
    "FT-4.5",
    "FT-4.6",
    # FT-5
    "FT-5.1",
    "FT-5.2",
    "FT-5.3",
    "FT-5.4",
    # FT-6
    "FT-6.1",
    "FT-6.2",
    "FT-6.3",
    # FT-7
    "FT-7.1",
    "FT-7.2",
    "FT-7.3",
    # FT-8 (optional, gated)
    "FT-8.1",
    "FT-8.2",
    "FT-8.3",
    "FT-8.4",
    "FT-8.5",
]


def _now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z")


def load_state(state_path: Path = DEFAULT_STATE) -> dict[str, Any]:
    """Load the plan state, returning an empty default if missing."""
    if not state_path.exists():
        return {
            "plan": "flythrough-bridge-plan",
            "version": "2.0",
            "current_phase": "FT-1",
            "current_step": "FT-1.1",
            "phase_status": {f"FT-{n}": "pending" for n in range(1, 9)},
            "step_status": {},
            "step_status_failed": {},
            "last_handoff": None,
            "last_updated": _now_iso(),
            "build_hash": None,
            "blocked_reason": None,
        }
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any], state_path: Path = DEFAULT_STATE) -> None:
    state["last_updated"] = _now_iso()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp.replace(state_path)


def find_next_step(state: dict[str, Any]) -> str | None:
    """Return the first step in STEP_ORDER that is not 'done' and not 'failed'."""
    step_status = state.get("step_status", {})
    for step in STEP_ORDER:
        status = step_status.get(step, "pending")
        if status not in ("done", "failed", "in_progress"):
            return step
    return None


def resolve_phase(step_id: str) -> str:
    """Extract phase from step id: 'FT-4.3' → 'FT-4'."""
    parts = step_id.split(".")
    return parts[0] if parts else step_id


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flythrough_plan",
        description="FT-5: Flythrough Bridge Plan orchestrator",
    )
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE, help="Path to .state.json")
    sub = parser.add_subparsers(dest="command", required=True)

    # status
    sub.add_parser("status", help="Show current plan state")

    # step
    step_p = sub.add_parser("step", help="Activate a step")
    step_group = step_p.add_mutually_exclusive_group(required=True)
    step_group.add_argument("--next", action="store_true", help="Activate the next pending step")
    step_group.add_argument("--id", type=str, dest="step_id", help="Activate a specific step (e.g., FT-5.1)")

    # complete
    comp_p = sub.add_parser("complete", help="Mark a step as done")
    comp_p.add_argument("--id", type=str, dest="step_id", required=True, help="Step to mark done (e.g., FT-5.1)")
    comp_p.add_argument("--evidence", type=str, default=None, help="Path to evidence file")

    # build (FT-5.2)
    build_p = sub.add_parser("build", help="Run the full flythrough build pipeline")
    build_p.add_argument("--resume", action="store_true", help="Resume from last incomplete stage")
    build_p.add_argument("--skip-textures", action="store_true", help="Skip texture conversion stage")
    build_p.add_argument("--limit", type=int, default=0, help="Limit NIFs in bulk export (0=all in probe lookup)")
    build_p.add_argument("--timeout", type=int, default=120, help="Timeout per NIF in seconds")

    return parser


def cmd_status(args: argparse.Namespace) -> int:
    state = load_state(args.state)
    print(f"Plan:    {state['plan']} v{state['version']}")
    print(f"Current: {state['current_phase']} / {state['current_step']}")
    print(f"Updated: {state.get('last_updated', '?')}")
    if state.get("blocked_reason"):
        print(f"BLOCKED: {state['blocked_reason']}")
    print()
    print("Phase status:")
    for ph in sorted(state.get("phase_status", {}).keys()):
        st = state["phase_status"][ph]
        icon = _ICONS.get(st, _ICONS["unknown"])
        print(f"  {icon} {ph}: {st}")
    print()
    print("Step status (non-pending only):")
    step_status = state.get("step_status", {})
    shown = 0
    for step in STEP_ORDER:
        st = step_status.get(step, "pending")
        if st in ("done", "failed", "in_progress"):
            icon = _ICONS.get(st, _ICONS["unknown"])
            print(f"  {icon} {step}: {st}")
            shown += 1
    if shown == 0:
        print("  (all steps pending)")
    print()
    next_step = find_next_step(state)
    if next_step:
        print(f"Next step: {next_step}")
    else:
        print("All steps complete!")
    return 0


def cmd_step(args: argparse.Namespace) -> int:
    state = load_state(args.state)

    if args.next:
        step_id = find_next_step(state)
        if step_id is None:
            print("All steps complete — nothing to do.")
            return 0
    else:
        step_id = args.step_id
        # Validate step exists
        if step_id not in STEP_ORDER:
            print(f"ERROR: unknown step '{step_id}'. Valid steps:")
            for s in STEP_ORDER:
                print(f"  {s}")
            return 1

    phase = resolve_phase(step_id)
    state["current_phase"] = phase
    state["current_step"] = step_id
    state["step_status"][step_id] = "in_progress"
    if state["phase_status"].get(phase) == "pending":
        state["phase_status"][phase] = "in_progress"
    state["blocked_reason"] = None
    save_state(state, args.state)

    print(f"Activated: {step_id} ({phase})")
    print(f"State:     {args.state}")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    state = load_state(args.state)
    step_id = args.step_id

    if step_id not in STEP_ORDER:
        print(f"ERROR: unknown step '{step_id}'.")
        return 1

    phase = resolve_phase(step_id)
    state["step_status"][step_id] = "done"
    state["current_step"] = step_id
    state["last_handoff"] = f"docs/handoffs/{_now_iso()[:10]}-{phase.lower()}-exit.md"

    # Check if all steps in this phase are done
    phase_steps = [s for s in STEP_ORDER if s.startswith(phase + ".")]
    all_done = all(state["step_status"].get(s) == "done" for s in phase_steps)
    if all_done:
        state["phase_status"][phase] = "done"
        # Advance to next phase
        phase_num = int(phase.split("-")[1])
        next_phase = f"FT-{phase_num + 1}"
        if next_phase in state["phase_status"]:
            state["current_phase"] = next_phase
            # Find first step of next phase
            next_steps = [s for s in STEP_ORDER if s.startswith(next_phase + ".")]
            if next_steps:
                state["current_step"] = next_steps[0]

    if args.evidence:
        evidence_path = REPO_ROOT / args.evidence
        if evidence_path.exists():
            print(f"Evidence: {evidence_path}")
        else:
            print(f"Warning: evidence path not found: {evidence_path}")

    save_state(state, args.state)
    print(f"Completed: {step_id}")
    if all_done:
        print(f"Phase {phase} is now DONE")
        next_phase = f"FT-{phase_num + 1}"
        print(f"Advanced to: {next_phase}")
    return 0


def _run_stage(name: str, cmd: list[str], timeout_sec: int = 600) -> tuple[bool, str]:
    """Run a pipeline stage subprocess. Returns (success, output_tail)."""
    log.info("--- STAGE: %s ---", name)
    log.info("  cmd: %s", " ".join(cmd))
    t0 = _dt.datetime.now(_dt.UTC)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout_sec}s"
    except Exception as exc:
        return False, f"ERROR: {exc}"
    elapsed = (_dt.datetime.now(_dt.UTC) - t0).total_seconds()
    out = (result.stdout or "")[-500:]
    err = (result.stderr or "")[-500:]
    ok = result.returncode == 0
    if ok:
        log.info("  OK (%.1fs)", elapsed)
    else:
        log.error("  FAILED (rc=%d, %.1fs): %s", result.returncode, elapsed, err[:200])
    return ok, (out + "\n" + err)[:500]


def cmd_build(args: argparse.Namespace) -> int:
    """Run the full FT pipeline: textures → bulk export + scene graph → validation."""
    state = load_state(args.state)

    # On fresh (non-resume) builds, clear previous build stages
    if not args.resume:
        state["build_stages"] = {}

    build_stages: dict[str, Any] = state.setdefault("build_stages", {})
    stages: list[tuple[str, list[str]]] = []

    # Stage 1: Textures (FT-1)
    if not args.skip_textures:
        textures_cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "dump_textures_for_flythrough.py"),
        ]
        stages.append(("textures", textures_cmd))

    # Stage 2: Bulk export + scene graph (FT-2/3/4)
    bulk_cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "bulk_export_for_flythrough.py"),
        "run",
        "--use-probe-lookup",
        "--scene-graph",
        "--skip-build",
        f"--timeout={args.timeout}",
    ]
    if args.limit > 0:
        bulk_cmd.append(f"--limit={args.limit}")
    stages.append(("bulk_export", bulk_cmd))

    # Execute stages with resume support
    completed = 0
    failed_stage: str | None = None
    for stage_name, cmd in stages:
        if args.resume and build_stages.get(stage_name) == "done":
            log.info("SKIP %s (already done)", stage_name)
            completed += 1
            continue

        build_stages[stage_name] = "in_progress"
        save_state(state, args.state)

        ok, out_tail = _run_stage(stage_name, cmd)
        if not ok:
            build_stages[stage_name] = "failed"
            build_stages[f"{stage_name}_error"] = out_tail[:200]
            save_state(state, args.state)
            failed_stage = stage_name
            break

        build_stages[stage_name] = "done"
        save_state(state, args.state)
        completed += 1

    # Summary
    print()
    print(f"Build stages: {completed}/{len(stages)} completed")
    for stage_name, _cmd in stages:
        st = build_stages.get(stage_name, "pending")
        icon = _ICONS.get(st, _ICONS["unknown"])
        print(f"  {icon} {stage_name}: {st}")

    if failed_stage:
        print(f"\nBuild failed at: {failed_stage}")
        print("Fix the issue and re-run with --resume to continue.")
        return 1

    print("\nBuild complete")
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    parser = _build_parser()
    args = parser.parse_args()
    if args.command == "status":
        return cmd_status(args)
    if args.command == "step":
        return cmd_step(args)
    if args.command == "complete":
        return cmd_complete(args)
    if args.command == "build":
        return cmd_build(args)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
