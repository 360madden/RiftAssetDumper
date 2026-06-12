#!/usr/bin/env python3
"""Cycle 2 Plan orchestrator — Scene Manifest & World Reconstruction.

Reads/writes `Assets/build/cycle-2/.state.json` to track phase progress.
Provides subcommands: status, step (--next / --id), complete, v4-done.

Mirrors the structure of `scripts/flythrough_plan.py` but adds V4 Pro block
tracking and a cohort-aware validation gate.

Usage:
    python scripts/cycle_2_plan.py status
    python scripts/cycle_2_plan.py step --next
    python scripts/cycle_2_plan.py step --id C2-5.3
    python scripts/cycle_2_plan.py complete --id C2-5.3 --evidence path/to/evidence
    python scripts/cycle_2_plan.py v4-done --id C2-V4P1 --output path/to/v4-pro-output.md
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger("cycle_2_plan")

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = REPO_ROOT / "build" / "cycle-2" / ".state.json"

# ASCII-safe status icons (emoji can break on Windows cp1252 consoles)
_ICONS: dict[str, str] = {
    "done": "[DONE]",
    "in_progress": "[BUSY]",
    "pending": "[----]",
    "blocked": "[FAIL]",
    "paused": "[PAUS]",
    "failed": "[FAIL]",
    "killed": "[KILL]",
    "unknown": "[????]",
}

# Step dependency order: all steps in execution order (M3 + V4 Pro interleaved).
# C2-2.5 and C2-3.5 (M3 implements V4 Pro decisions) come AFTER C2-V4P1, matching
# the plan's narrative flow: data prep (2.1-2.4, 3.1-3.4) -> V4 Pro block 1 ->
# M3 implementation (2.5, 3.5) -> next phase.
STEP_ORDER: list[str] = [
    # C2-1 Bootstrap
    "C2-1.1",
    "C2-1.2",
    "C2-1.3",
    "C2-1.4",
    "C2-1.5",
    # C2-2 Transform data (M3 data prep)
    "C2-2.1",
    "C2-2.2",
    "C2-2.3",
    "C2-2.4",
    # C2-3 Coordinate data (M3 data prep)
    "C2-3.1",
    "C2-3.2",
    "C2-3.3",
    "C2-3.4",
    # V4 Pro Block 1
    "C2-V4P1",
    # M3 implements V4 Pro's transform + coordinate decisions
    "C2-2.5",
    "C2-3.5",
    # C2-4 Material closure
    "C2-4.1",
    "C2-4.2",
    "C2-4.3",
    "C2-4.4",
    "C2-4.5",
    # V4 Pro Block 3 (conditional)
    "C2-V4P3",
    # C2-5 Schema prep
    "C2-5.1",
    "C2-5.2",
    "C2-5.3",
    "C2-5.4",
    "C2-5.5",
    # V4 Pro Block 2
    "C2-V4P2",
    # C2-6 Batch reconstruction
    "C2-6.1",
    "C2-6.2",
    "C2-6.3",
    "C2-6.4",
    "C2-6.5",
    # C2-7 Consumer validation
    "C2-7.1",
    "C2-7.2",
    "C2-7.3",
    "C2-7.4",
    "C2-7.5",
    # C2-8 Scale-out
    "C2-8.1",
    "C2-8.2",
    "C2-8.3",
    "C2-8.4",
    "C2-8.5",
    # V4 Pro Block 4
    "C2-V4P4",
    # C2-9 Validation
    "C2-9.1",
    "C2-9.2",
    "C2-9.3",
    "C2-9.4",
    "C2-9.5",
    # V4 Pro Block 5
    "C2-V4P5",
]

V4_PRO_BLOCK_IDS: set[str] = {"C2-V4P1", "C2-V4P2", "C2-V4P3", "C2-V4P4", "C2-V4P5"}
CONDITIONAL_V4_BLOCKS: set[str] = {"C2-V4P3"}  # Only fires if closure 50-79%
V4_SESSION_LIMIT = 5

PHASES: list[str] = [f"C2-{n}" for n in range(1, 10)]

# Explicit phase membership: maps each phase to its complete step list, REGARDLESS
# of where those steps appear in STEP_ORDER. This decouples "phase membership" from
# "execution order" so that late-binding steps (e.g., C2-2.5 and C2-3.5 which are
# "implement V4 Pro's decisions" and come AFTER C2-V4P1 in STEP_ORDER) are still
# recognized as belonging to their original phase. cmd_complete uses this for
# phase-advancement checks; if a phase has late-binding steps, they are not skipped
# silently.
PHASE_STEPS: dict[str, list[str]] = {
    "C2-1": ["C2-1.1", "C2-1.2", "C2-1.3", "C2-1.4", "C2-1.5"],
    "C2-2": ["C2-2.1", "C2-2.2", "C2-2.3", "C2-2.4", "C2-2.5"],
    "C2-3": ["C2-3.1", "C2-3.2", "C2-3.3", "C2-3.4", "C2-3.5"],
    "C2-4": ["C2-4.1", "C2-4.2", "C2-4.3", "C2-4.4", "C2-4.5"],
    "C2-5": ["C2-5.1", "C2-5.2", "C2-5.3", "C2-5.4", "C2-5.5"],
    "C2-6": ["C2-6.1", "C2-6.2", "C2-6.3", "C2-6.4", "C2-6.5"],
    "C2-7": ["C2-7.1", "C2-7.2", "C2-7.3", "C2-7.4", "C2-7.5"],
    "C2-8": ["C2-8.1", "C2-8.2", "C2-8.3", "C2-8.4", "C2-8.5"],
    "C2-9": ["C2-9.1", "C2-9.2", "C2-9.3", "C2-9.4", "C2-9.5"],
}


def _now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z")


def _default_state() -> dict[str, Any]:
    """Return a fresh default state with all steps pending."""
    return {
        "plan": "cycle-2-scene-manifest-plan",
        "version": "0.2",
        "current_phase": "C2-1",
        "current_step": "C2-1.1",
        "phase_status": {p: "pending" for p in PHASES},
        "step_status": {},
        "v4_pro_blocks": {
            block_id: {
                "status": "pending",
                "used_at": None,
                "output_path": None,
                "conditional": block_id in CONDITIONAL_V4_BLOCKS,
            }
            for block_id in sorted(V4_PRO_BLOCK_IDS)
        },
        "v4_pro_sessions_used": 0,
        "v4_pro_session_limit": V4_SESSION_LIMIT,
        "plan_status": "draft",
        "last_handoff": None,
        "last_updated": _now_iso(),
        "blocked_reason": None,
    }


def load_state(state_path: Path = DEFAULT_STATE) -> dict[str, Any]:
    """Load the plan state, returning an empty default if missing."""
    if not state_path.exists():
        return _default_state()
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any], state_path: Path = DEFAULT_STATE) -> None:
    """Atomically save the state with an updated timestamp."""
    state["last_updated"] = _now_iso()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp.replace(state_path)


def find_next_step(state: dict[str, Any]) -> str | None:
    """Return the first step that is pending or in_progress (resume signal), including V4 Pro blocks."""
    step_status = state.get("step_status", {})
    v4_blocks = state.get("v4_pro_blocks", {})
    for step in STEP_ORDER:
        if step in V4_PRO_BLOCK_IDS:
            # Skip conditional V4 blocks unless they were explicitly activated
            if step in CONDITIONAL_V4_BLOCKS and not v4_blocks.get(step, {}).get("activated", False):
                continue
            block_status = v4_blocks.get(step, {}).get("status", "pending")
            # Return pending or in_progress V4 blocks (in_progress = "resume me")
            if block_status in ("pending", "in_progress"):
                return step
        else:
            status = step_status.get(step, "pending")
            if status not in ("done", "failed", "killed"):
                return step
    return None


def resolve_phase(step_id: str) -> str:
    """Extract phase from step id: 'C2-4.3' -> 'C2-4'; 'C2-V4P1' -> 'C2-V4P1'."""
    if step_id.startswith("C2-V4P"):
        return step_id
    parts = step_id.split(".")
    return parts[0] if parts else step_id


def is_v4_block(step_id: str) -> bool:
    """Return True if the step is a V4 Pro block."""
    return step_id in V4_PRO_BLOCK_IDS


def activate_conditional_v4_block(state: dict[str, Any], block_id: str) -> None:
    """Mark a conditional V4 Pro block as activated (e.g. C2-V4P3 when closure is 50-79%)."""
    block = state["v4_pro_blocks"].setdefault(block_id, {})
    block["activated"] = True
    block["status"] = "pending"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cycle_2_plan",
        description="Cycle 2 (Scene Manifest & World Reconstruction) orchestrator",
    )
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE, help="Path to .state.json")
    sub = parser.add_subparsers(dest="command", required=True)

    # status
    sub.add_parser("status", help="Show current plan state")

    # step
    step_p = sub.add_parser("step", help="Activate a step")
    step_group = step_p.add_mutually_exclusive_group(required=True)
    step_group.add_argument("--next", action="store_true", help="Activate the next pending step")
    step_group.add_argument("--id", type=str, dest="step_id", help="Activate a specific step (e.g., C2-5.3)")

    # complete
    comp_p = sub.add_parser("complete", help="Mark a step as done")
    comp_p.add_argument("--id", type=str, dest="step_id", required=True, help="Step to mark done (e.g., C2-5.3)")
    comp_p.add_argument("--evidence", type=str, default=None, help="Path to evidence file")

    # v4-done (mark a V4 Pro block complete)
    v4_p = sub.add_parser("v4-done", help="Mark a V4 Pro block as done (after switching back to M3)")
    v4_p.add_argument("--id", type=str, dest="step_id", required=True, help="V4 Pro block to mark done (e.g., C2-V4P1)")
    v4_p.add_argument("--output", type=str, required=True, help="Path to the V4 Pro output decision doc")

    # kill (mark the cycle as killed)
    kill_p = sub.add_parser("kill", help="Kill the cycle (e.g. closure rate <50%%)")
    kill_p.add_argument("--reason", type=str, required=True, help="Why the cycle was killed")

    # v4-activate (activate a conditional V4 Pro block, e.g. C2-V4P3 when closure is 50-79%)
    v4a_p = sub.add_parser("v4-activate", help="Activate a conditional V4 Pro block")
    v4a_p.add_argument("--id", type=str, dest="step_id", required=True, help="V4 Pro block to activate (e.g., C2-V4P3)")

    return parser


def cmd_status(args: argparse.Namespace) -> int:
    state = load_state(args.state)
    print(f"Plan:    {state['plan']} v{state['version']}")
    print(f"Status:  {state.get('plan_status', '?')}")
    print(f"Current: {state['current_phase']} / {state['current_step']}")
    print(f"V4 Pro:  {state.get('v4_pro_sessions_used', 0)}/{state.get('v4_pro_session_limit', 5)} sessions used")
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

    print("V4 Pro blocks:")
    for bid in sorted(state.get("v4_pro_blocks", {}).keys()):
        b = state["v4_pro_blocks"][bid]
        st = b.get("status", "pending")
        icon = _ICONS.get(st, _ICONS["unknown"])
        cond = " (conditional)" if b.get("conditional") else ""
        used = b.get("used_at") or "-"
        print(f"  {icon} {bid}: {st}{cond} (used_at={used})")
    print()

    print("Step status (non-pending only):")
    step_status = state.get("step_status", {})
    shown = 0
    for step in STEP_ORDER:
        if step in V4_PRO_BLOCK_IDS:
            continue  # V4 blocks shown above
        st = step_status.get(step, "pending")
        if st in ("done", "failed", "killed", "in_progress"):
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
        if step_id not in STEP_ORDER:
            print(f"ERROR: unknown step '{step_id}'. Valid steps:")
            for s in STEP_ORDER:
                print(f"  {s}")
            return 1

    phase = resolve_phase(step_id)

    if is_v4_block(step_id):
        state["v4_pro_blocks"][step_id]["status"] = "in_progress"
        state["current_step"] = step_id
        # Don't change current_phase for V4 blocks
    else:
        state["step_status"][step_id] = "in_progress"
        state["current_phase"] = phase
        state["current_step"] = step_id
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
    if is_v4_block(step_id):
        print(f"ERROR: '{step_id}' is a V4 Pro block. Use 'v4-done' instead.")
        return 1

    phase = resolve_phase(step_id)
    state["step_status"][step_id] = "done"
    state["current_step"] = step_id
    state["last_handoff"] = f"docs/handoffs/{_now_iso()[:10]}-cycle-2-{phase.lower()}-exit.md"

    # Check if all main steps in this phase are done. Use PHASE_STEPS (explicit
    # membership) rather than scanning STEP_ORDER, so late-binding steps like
    # C2-2.5 / C2-3.5 (which appear after C2-V4P1 in STEP_ORDER) are not
    # silently skipped.
    phase_steps = PHASE_STEPS.get(phase, [])
    all_done = all(state["step_status"].get(s) == "done" for s in phase_steps)
    if all_done:
        state["phase_status"][phase] = "done"
        # Advance to next phase
        phase_num = int(phase.split("-")[1])
        next_phase = f"C2-{phase_num + 1}"
        if next_phase in state["phase_status"]:
            state["current_phase"] = next_phase
            # Find first step of next phase (first non-V4 step in STEP_ORDER
            # whose prefix matches the next phase)
            next_steps = [s for s in STEP_ORDER if s.startswith(next_phase + ".") and not is_v4_block(s)]
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
        next_phase = f"C2-{phase_num + 1}"
        print(f"Advanced to: {next_phase}")
    return 0


def cmd_v4_done(args: argparse.Namespace) -> int:
    state = load_state(args.state)
    block_id = args.step_id

    if block_id not in V4_PRO_BLOCK_IDS:
        print(f"ERROR: '{block_id}' is not a V4 Pro block. Valid V4 Pro blocks: {sorted(V4_PRO_BLOCK_IDS)}")
        return 1

    sessions_used = state.get("v4_pro_sessions_used", 0)
    if sessions_used >= V4_SESSION_LIMIT:
        print(f"ERROR: V4 Pro session limit reached ({V4_SESSION_LIMIT}). Cannot use more.")
        return 1

    output_path = REPO_ROOT / args.output
    if not output_path.exists():
        print(f"ERROR: V4 Pro output not found: {output_path}")
        return 1

    state["v4_pro_blocks"][block_id]["status"] = "done"
    state["v4_pro_blocks"][block_id]["used_at"] = _now_iso()
    state["v4_pro_blocks"][block_id]["output_path"] = str(output_path.relative_to(REPO_ROOT))
    state["v4_pro_sessions_used"] = sessions_used + 1
    state["current_step"] = block_id

    save_state(state, args.state)
    print(f"V4 Pro block done: {block_id}")
    print(f"Output:           {output_path}")
    print(f"Sessions used:    {state['v4_pro_sessions_used']}/{V4_SESSION_LIMIT}")
    return 0


def cmd_kill(args: argparse.Namespace) -> int:
    state = load_state(args.state)
    state["plan_status"] = "killed"
    state["blocked_reason"] = args.reason
    # Mark the current step + phase as killed so the resume markers are unambiguous
    if state.get("current_step"):
        if is_v4_block(state["current_step"]):
            state["v4_pro_blocks"][state["current_step"]]["status"] = "killed"
        else:
            state["step_status"][state["current_step"]] = "killed"
    if state.get("current_phase"):
        state["phase_status"][state["current_phase"]] = "killed"
    # Handoff path is conventional; the doc itself is for the user to write
    state["last_handoff"] = f"docs/handoffs/{_now_iso()[:10]}-cycle-2-killed.md"
    save_state(state, args.state)
    print(f"Cycle KILLED: {args.reason}")
    print(f"State:        {args.state}")
    print(f"Handoff:      {state['last_handoff']} (write this file with the kill rationale)")
    return 0


def cmd_v4_activate(args: argparse.Namespace) -> int:
    state = load_state(args.state)
    block_id = args.step_id

    if block_id not in V4_PRO_BLOCK_IDS:
        print(f"ERROR: '{block_id}' is not a V4 Pro block. Valid V4 Pro blocks: {sorted(V4_PRO_BLOCK_IDS)}")
        return 1
    if block_id not in CONDITIONAL_V4_BLOCKS:
        print(f"ERROR: '{block_id}' is not a conditional V4 Pro block. No activation needed.")
        print(f"Conditional blocks: {sorted(CONDITIONAL_V4_BLOCKS)}")
        return 1
    if state["v4_pro_blocks"][block_id].get("activated"):
        print(f"INFO: '{block_id}' is already activated.")
        return 0

    activate_conditional_v4_block(state, block_id)
    save_state(state, args.state)
    print(f"Activated: {block_id} (will now appear in --next)")
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
    if args.command == "v4-done":
        return cmd_v4_done(args)
    if args.command == "kill":
        return cmd_kill(args)
    if args.command == "v4-activate":
        return cmd_v4_activate(args)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
