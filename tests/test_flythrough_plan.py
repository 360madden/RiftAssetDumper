"""Unit tests for scripts/flythrough_plan.py — FT-5.1 / FT-5.2."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest  # noqa: F401

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from flythrough_plan import (  # noqa: E402
    STEP_ORDER,
    cmd_build,
    cmd_complete,
    cmd_status,
    cmd_step,
    find_next_step,
    load_state,
    resolve_phase,
    save_state,
)


class _FakeArgs:
    """Minimal argparse.Namespace stub for testing command handlers."""

    state: Path
    next: bool = False
    step_id: str | None = None
    evidence: str | None = None

    def __init__(self, state: Path, **kwargs: object) -> None:
        self.state = state
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_load_state_returns_default_when_missing() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        sp = Path(tmpdir) / "state.json"
        state = load_state(sp)
        assert state["plan"] == "flythrough-bridge-plan"
        assert state["current_step"] == "FT-1.1"
        assert state["phase_status"]["FT-1"] == "pending"


def test_save_and_reload_state_preserves_data() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        sp = Path(tmpdir) / "state.json"
        state = load_state(sp)
        state["phase_status"]["FT-1"] = "done"
        state["step_status"]["FT-1.1"] = "done"
        save_state(state, sp)
        reloaded = load_state(sp)
        assert reloaded["phase_status"]["FT-1"] == "done"
        assert reloaded["step_status"]["FT-1.1"] == "done"


def test_find_next_step_returns_first_pending() -> None:
    state = {
        "step_status": {
            "FT-1.1": "done",
            "FT-1.2": "done",
            "FT-1.3": "pending",
        }
    }
    assert find_next_step(state) == "FT-1.3"


def test_find_next_step_returns_none_when_all_done() -> None:
    state = {"step_status": {s: "done" for s in STEP_ORDER}}
    assert find_next_step(state) is None


def test_resolve_phase_extracts_correctly() -> None:
    assert resolve_phase("FT-4.3") == "FT-4"
    assert resolve_phase("FT-1.1") == "FT-1"
    assert resolve_phase("FT-8.5") == "FT-8"


def test_cmd_status_prints_without_crashing() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        sp = Path(tmpdir) / "state.json"
        state = load_state(sp)
        state["step_status"]["FT-1.1"] = "done"
        state["step_status"]["FT-1.2"] = "in_progress"
        state["phase_status"]["FT-1"] = "in_progress"
        save_state(state, sp)
        args = _FakeArgs(sp)
        rc = cmd_status(args)
        assert rc == 0


def test_cmd_step_next_activates_pending() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        sp = Path(tmpdir) / "state.json"
        state = load_state(sp)
        state["step_status"]["FT-1.1"] = "done"
        save_state(state, sp)
        args = _FakeArgs(sp, next=True)
        rc = cmd_step(args)
        assert rc == 0
        reloaded = load_state(sp)
        assert reloaded["current_step"] == "FT-1.2"
        assert reloaded["step_status"]["FT-1.2"] == "in_progress"


def test_cmd_step_when_all_done_returns_zero() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        sp = Path(tmpdir) / "state.json"
        state = load_state(sp)
        state["step_status"] = {s: "done" for s in STEP_ORDER}
        state["phase_status"] = {f"FT-{n}": "done" for n in range(1, 9)}
        save_state(state, sp)
        args = _FakeArgs(sp, next=True)
        rc = cmd_step(args)
        assert rc == 0


def test_cmd_step_with_id_validates() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        sp = Path(tmpdir) / "state.json"
        save_state(load_state(sp), sp)
        # Invalid step
        args = _FakeArgs(sp, step_id="FT-99.1")
        rc = cmd_step(args)
        assert rc == 1
        # Valid step
        args = _FakeArgs(sp, step_id="FT-5.1")
        rc = cmd_step(args)
        assert rc == 0
        reloaded = load_state(sp)
        assert reloaded["step_status"]["FT-5.1"] == "in_progress"


def test_cmd_complete_marks_done_and_advances_phase() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        sp = Path(tmpdir) / "state.json"
        state = load_state(sp)
        # Mark all FT-1 steps but FT-1.5 as done
        for s in ("FT-1.1", "FT-1.2", "FT-1.3", "FT-1.4"):
            state["step_status"][s] = "done"
        state["current_step"] = "FT-1.5"
        state["phase_status"]["FT-1"] = "in_progress"
        save_state(state, sp)
        # Complete FT-1.5
        args = _FakeArgs(sp, step_id="FT-1.5", evidence="docs/handoffs/test.md")
        rc = cmd_complete(args)
        assert rc == 0
        reloaded = load_state(sp)
        assert reloaded["step_status"]["FT-1.5"] == "done"
        assert reloaded["phase_status"]["FT-1"] == "done"
        assert reloaded["current_phase"] == "FT-2"


def test_cmd_complete_rejects_unknown_step() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        sp = Path(tmpdir) / "state.json"
        save_state(load_state(sp), sp)
        args = _FakeArgs(sp, step_id="FT-99.1")
        rc = cmd_complete(args)
        assert rc == 1


class _FakeArgsBuild:
    """Argparse Namespace stub for cmd_build tests."""

    state: Path
    resume: bool = False
    skip_textures: bool = False
    limit: int = 0
    timeout: int = 120

    def __init__(self, state: Path, **kwargs: object) -> None:
        self.state = state
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_cmd_build_with_skip_textures_runs_only_bulk_export(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Verify build with --skip-textures only runs bulk-export stage."""
    stages_run: list[str] = []

    def _fake_run(cmd, **_: object):  # type: ignore[no-untyped-def]
        cmd_str = " ".join(str(c) for c in cmd)
        stages_run.append(cmd_str)
        import subprocess as sp

        result = sp.CompletedProcess(cmd, 0, stdout="OK", stderr="")
        return result

    import flythrough_plan

    monkeypatch.setattr(flythrough_plan.subprocess, "run", _fake_run)
    monkeypatch.setattr(flythrough_plan.sys, "executable", "python3")

    with tempfile.TemporaryDirectory() as tmpdir:
        sp = Path(tmpdir) / "state.json"
        save_state(load_state(sp), sp)
        args = _FakeArgsBuild(sp, skip_textures=True)
        rc = cmd_build(args)
        assert rc == 0
        # Only one stage (bulk_export) should have run
        assert len(stages_run) == 1
        assert any("bulk_export_for_flythrough.py" in s for s in stages_run)
        # Verify build_stages recorded
        reloaded = load_state(sp)
        assert reloaded["build_stages"]["bulk_export"] == "done"


def test_cmd_build_resume_skips_done_stages(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Verify --resume skips already-completed stages."""
    stages_run: list[str] = []

    def _fake_run(cmd, **_: object):  # type: ignore[no-untyped-def]
        cmd_str = " ".join(str(c) for c in cmd)
        stages_run.append(cmd_str)
        import subprocess as sp

        return sp.CompletedProcess(cmd, 0, stdout="", stderr="")

    import flythrough_plan

    monkeypatch.setattr(flythrough_plan.subprocess, "run", _fake_run)
    monkeypatch.setattr(flythrough_plan.sys, "executable", "python3")

    with tempfile.TemporaryDirectory() as tmpdir:
        sp = Path(tmpdir) / "state.json"
        state = load_state(sp)
        # Mark bulk_export as already done
        state["build_stages"] = {"bulk_export": "done"}
        save_state(state, sp)
        args = _FakeArgsBuild(sp, resume=True, skip_textures=True)
        rc = cmd_build(args)
        assert rc == 0
        # No stages should have run (bulk_export already done, textures skipped)
        assert len(stages_run) == 0


def test_cmd_build_failure_sets_failed_and_returns_one(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Verify build failure records error and returns 1."""

    def _fake_run(cmd, **_: object):  # type: ignore[no-untyped-def]
        import subprocess as sp

        return sp.CompletedProcess(cmd, 1, stdout="", stderr="SIMULATED FAILURE")

    import flythrough_plan

    monkeypatch.setattr(flythrough_plan.subprocess, "run", _fake_run)
    monkeypatch.setattr(flythrough_plan.sys, "executable", "python3")

    with tempfile.TemporaryDirectory() as tmpdir:
        sp = Path(tmpdir) / "state.json"
        save_state(load_state(sp), sp)
        args = _FakeArgsBuild(sp, skip_textures=True)
        rc = cmd_build(args)
        assert rc == 1
        reloaded = load_state(sp)
        assert reloaded["build_stages"]["bulk_export"] == "failed"
        assert "bulk_export_error" in reloaded["build_stages"]


def test_cmd_build_populates_build_stages(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Verify build stages are recorded in state with full pipeline (textures + bulk)."""

    def _fake_run(cmd, **_: object):  # type: ignore[no-untyped-def]
        import subprocess as sp

        return sp.CompletedProcess(cmd, 0, stdout="", stderr="")

    import flythrough_plan

    monkeypatch.setattr(flythrough_plan.subprocess, "run", _fake_run)
    monkeypatch.setattr(flythrough_plan.sys, "executable", "python3")

    with tempfile.TemporaryDirectory() as tmpdir:
        sp = Path(tmpdir) / "state.json"
        state = load_state(sp)
        save_state(state, sp)
        args = _FakeArgsBuild(sp)
        rc = cmd_build(args)
        assert rc == 0
        reloaded = load_state(sp)
        assert "build_stages" in reloaded
        assert reloaded["build_stages"]["textures"] == "done"
        assert reloaded["build_stages"]["bulk_export"] == "done"
