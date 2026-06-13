"""Orphan-process guard for ``RiftAssetDumper.exe`` invocations.

The RIFT asset dumper holds 2-3 GB of live-archive data when it runs, and a
crashed or interrupted Codebuff session can leave child ``RiftAssetDumper.exe``
processes behind. Spawning a new one alongside the orphans makes the system
swap-thrash and the new process usually fails with OOM or hangs.

This module provides a best-effort detector and a small CLI gate so any
long-running script that spawns the dumper (the workflow orchestrator and the
FT-2 bulk exporter) can refuse to start when orphans are present and emit a
clear remediation message.

Detection paths (in order):
    1. ``tasklist /FI "IMAGENAME eq RiftAssetDumper.exe" /FO CSV /NH`` on Windows
    2. ``pgrep -x RiftAssetDumper`` on POSIX
    3. Best-effort: any probe failure returns 0 so the guard degrades to a
       no-op rather than blocking legitimate workflows on hostile environments.

The CSV parsing uses :mod:`csv` so localized columns like ``"1,234 K"`` are
parsed correctly.
"""

from __future__ import annotations

import csv
import io
import subprocess
import sys


def _count_tasklist_csv_rows(stdout: str) -> int:
    """Count ``RiftAssetDumper.exe`` rows in ``tasklist /FO CSV`` output.

    Skips blank lines, the ``INFO: No tasks are running`` line, and rows
    whose image name does not start with ``riftassetdumper`` (case-insensitive).
    Uses :mod:`csv` so localized columns like ``"1,234 K"`` are parsed
    correctly.
    """
    count = 0
    for line in stdout.splitlines():
        if not line.strip():
            continue
        if "no tasks are running" in line.lower():
            continue
        for row in csv.reader(io.StringIO(line)):
            if row and row[0].lower().startswith("riftassetdumper"):
                count += 1
    return count


def _count_running_riftassetdumper_processes(
    *,
    platform_name: str | None = None,
) -> int:
    """Return the number of running ``RiftAssetDumper`` processes (best-effort).

    Uses ``tasklist`` on Windows or ``pgrep`` on POSIX. The function is
    intentionally forgiving: a probe failure returns 0 so the guard degrades
    to a no-op rather than blocking legitimate workflows on hostile
    environments.
    """
    if platform_name is None:
        platform_name = sys.platform
    if platform_name.startswith("win"):
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq RiftAssetDumper.exe", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except OSError, subprocess.SubprocessError:
            return 0
        return _count_tasklist_csv_rows(result.stdout)
    try:
        result = subprocess.run(
            ["pgrep", "-x", "RiftAssetDumper"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except OSError, subprocess.SubprocessError, FileNotFoundError:
        return 0
    return sum(1 for line in result.stdout.splitlines() if line.strip())


def _orphan_process_guard(*, force: bool, threshold: int = 1) -> int:
    """Refuse to spawn a new ``RiftAssetDumper`` if orphans are present.

    Returns the count of running ``RiftAssetDumper`` processes (which is
    below ``threshold`` when the caller may proceed). When the count is
    at or above ``threshold`` and ``force`` is not set, prints an
    explanatory error to stderr and exits the process with status 2.

    The caller is expected to invoke this after CLI parsing and before
    spawning any long-running subprocess. Read-only inspection commands
    should bypass the guard (see ``_ORPHAN_GUARD_BYPASS_COMMANDS`` in
    ``rift_workflow.py`` or the bulk-pipeline equivalent).
    """
    count = _count_running_riftassetdumper_processes()
    if count < threshold:
        return count
    if force:
        print(
            f"WARNING: {count} RiftAssetDumper process(es) already running. "
            "--force-orphan-guard set; proceeding anyway.",
            file=sys.stderr,
        )
        return count
    print(
        f"ERROR: Found {count} RiftAssetDumper process(es) already running. "
        "These are likely orphans from a previous Codebuff session and "
        "would compete for the 26 GB live archive.",
        file=sys.stderr,
    )
    print(
        "Refusing to spawn a new one. Reclaim the memory with:\n"
        "    Get-Process RiftAssetDumper | Stop-Process -Force\n"
        "or pass --force-orphan-guard to override.",
        file=sys.stderr,
    )
    sys.exit(2)
    return count  # unreachable, kept for type checkers
