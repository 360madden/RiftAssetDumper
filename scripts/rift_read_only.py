#!/usr/bin/env python3
"""RIFT asset workflow — read-only entry point.

Peer to ``scripts/rift_workflow.py``. This module is a thin wrapper that
re-uses ``rift_workflow._run_command()`` for dispatch. The 40 read-only
commands remain defined in ``rift_workflow.py``'s ``_run_command()`` for
backward compatibility, but this entry point skips the orphan-process guard
(read-only by construction — none of the 40 commands spawn ``dotnet`` or
``RiftAssetDumper``).

The 33 spawner commands remain on ``rift_workflow.py`` and continue to be
protected by the orphan-process guard. After the refactor, the
``_ORPHAN_GUARD_BYPASS_COMMANDS`` set in ``rift_workflow.py`` is empty
(0 members), so the guard fires for every command on that entry point.

Design notes:

* No orphan-process guard — all 40 commands are read-only by construction.
* Re-uses ``rift_workflow._run_command()`` for dispatch — no handler logic
  is duplicated. The 40 commands stay in ``rift_workflow.py`` for backward
  compatibility; this module just provides a guard-free entry point.
* The 40 commands are a strict subset of the previous
  ``_ORPHAN_GUARD_BYPASS_COMMANDS`` set, minus the two CLI meta tokens
  ``--help`` and ``-h`` (handled by argparse before any dispatch).
* This module imports ``rift_workflow`` lazily inside ``main()`` to avoid
  any module-load-time cost on the spawner path.

Usage:
    python scripts/rift_read_only.py <command> [options]

Example:
    python scripts/rift_read_only.py tools-status
    python scripts/rift_read_only.py ghidra-summarize --ghidra-report Exports/ghidra-reports/site.json
    python scripts/rift_read_only.py discovery-workbench
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path boilerplate
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Read-only command set
# ---------------------------------------------------------------------------

# The 40 commands this entry point dispatches. This set is a strict subset of
# the previous rift_workflow._ORPHAN_GUARD_BYPASS_COMMANDS, minus the CLI meta
# tokens `--help` and `-h` (handled by argparse before any dispatch).
READ_ONLY_COMMANDS: frozenset[str] = frozenset(
    {
        # Tooling inspection (2)
        "tools-status",
        "ghidra-dry-run",
        # Ghidra read-only guards/reports (8)
        "ghidra-pairing-non-export-guard",
        "ghidra-attribute-candidate-report",
        "ghidra-attribute-candidate-guard",
        "ghidra-workflow-guard-suite",
        "ghidra-function-site-target-guard",
        "ghidra-function-site-status",
        "ghidra-summarize",
        "ghidra-review-rank-probes-summary",
        # Plan / post-50 read-only status (12)
        "fifty-step-plan-status",
        "post50-position-source-status",
        "post50-mesh34-negative-binding-status",
        "post50-mesh34-complete-binding-negative-proof",
        "post50-mesh329-family-proof",
        "post50-mesh329-source-binding-compare",
        "mesh329-attribute-role-matrix",
        "phase1-m1.2-304-magic-analysis",
        "phase1-m1.3-329-variant-layout-guard",
        "post50-promotion-readiness-status",
        "post50-validation-suite",
        "post50-residual-strict-threshold-delta",
        # Python-only analysis reports (5)
        "position-gap-report",
        "triage-fallback-candidates",
        "semantic-hint-crosstab",
        "discovery-workbench",
        "generated-output-guard",
        # NiDataStream read-only status/evidence (13)
        "nidatastream-descriptor-table-sample",
        "nidatastream-descriptor-table-sample-status",
        "nidatastream-descriptor-table-sample-compare",
        "nidatastream-descriptor-neighborhood-scan",
        "nidatastream-descriptor-reference-classify",
        "nidatastream-descriptor-base-model-review",
        "nidatastream-descriptor-proof-status",
        "nidatastream-descriptor-sample-compare",
        "nidatastream-evidence-status",
        "nidatastream-promotion-status",
        "nidatastream-promotion-dashboard",
        "nidatastream-parser-field-proof-guard",
        "nidatastream-parser-export-non-consumption-guard",
        "nidatastream-layout",
    }
)


# ===========================================================================
# Argparse — mirrors rift_workflow.py for the 40 read-only commands
# ===========================================================================


def _build_parser() -> argparse.ArgumentParser:
    """Build the read-only command parser.

    This parser mirrors ``rift_workflow.py``'s parser for the 40 read-only
    commands. It restricts the ``command`` choices to ``READ_ONLY_COMMANDS``
    and omits fields that are only used by spawner commands.
    """
    parser = argparse.ArgumentParser(
        prog="rift_read_only",
        description=(
            "RIFT asset workflow — read-only entry point. "
            "40 commands that analyze ignored reports and guards. "
            "No C# spawns, no orphan-process guard."
        ),
        epilog=(
            "Examples:\n"
            "  python scripts/rift_read_only.py tools-status\n"
            "  python scripts/rift_read_only.py ghidra-summarize --ghidra-report Exports/ghidra-reports/site.json\n"
            "  python scripts/rift_read_only.py discovery-workbench\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=sorted(READ_ONLY_COMMANDS),
        help="Read-only command to run.",
    )
    # Common output paths
    parser.add_argument("--out", type=Path, default=None, help="Output directory (default: Exports/).")
    parser.add_argument("--root", type=Path, default=None, help="RIFT live archive root.")
    parser.add_argument("--project", type=Path, default=None, help="Path to RiftAssetDumper.csproj.")
    parser.add_argument("--solution", type=Path, default=None, help="Path to RiftAssetDumper.slnx.")
    parser.add_argument("--limit", type=int, default=25, help="Row limit for inventory-driven reports.")
    parser.add_argument(
        "--smoke-max-total",
        type=int,
        default=20,
        help="Smoke-test cap for inventory builds.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the implicit dotnet build step (used by review-rank probes).",
    )
    parser.add_argument("--full", action="store_true", help="Run the full inventory (no --limit).")
    parser.add_argument("--quick", action="store_true", help="Reuse existing inventory if present.")
    parser.add_argument("--verbose", action="store_true", help="Verbose output.")
    parser.add_argument(
        "--list-json",
        action="store_true",
        help="Emit machine-readable JSON to stdout (where supported).",
    )

    # Mesh probe / decode (used by some read-only reports that probe meshes)
    parser.add_argument("--id", default="", help="Asset ID (hex).")
    parser.add_argument("--mesh-block", type=int, default=-1, help="Mesh block index.")
    parser.add_argument("--extra-offset", type=int, default=-1, help="Extra stream offset.")
    parser.add_argument("--type", default="", help="Asset type filter.")
    parser.add_argument(
        "--semantic-category",
        action="append",
        default=[],
        help="Semantic category filter (repeatable).",
    )
    parser.add_argument(
        "--experimental-position-source",
        action="store_true",
        help="Use experimental position source (not applicable for read-only commands).",
    )
    parser.add_argument("--write-obj", action="store_true", help="Write OBJ (not applicable).")
    parser.add_argument("--export-obj", action="store_true", help="Export OBJ (not applicable).")
    parser.add_argument("--review-rank", type=int, default=0, help="Review rank to resolve.")
    parser.add_argument("--review-kind", default="", help="Review kind filter.")
    parser.add_argument(
        "--review-report-limit",
        type=int,
        default=0,
        help="Limit for the review report (0 = use --limit).",
    )

    # Ghidra
    parser.add_argument("--ghidra-import", default="", help="Path to import into Ghidra.")
    parser.add_argument("--ghidra-process", default="", help="Process path for Ghidra analysis.")
    parser.add_argument("--ghidra-script", default="", help="Ghidra post-script name.")
    parser.add_argument(
        "--ghidra-script-arg",
        action="append",
        default=[],
        help="Argument for the Ghidra post-script (repeatable).",
    )
    parser.add_argument(
        "--ghidra-script-path",
        default="",
        help="Filesystem path to a Ghidra post-script.",
    )
    parser.add_argument("--ghidra-project-name", default="", help="Ghidra project name.")
    parser.add_argument("--ghidra-project-dir", default="", help="Ghidra project directory.")
    parser.add_argument(
        "--ghidra-no-analysis",
        action="store_true",
        help="Skip Ghidra auto-analysis (faster dry runs).",
    )
    parser.add_argument(
        "--ghidra-keep-project",
        action="store_true",
        help="Keep the Ghidra project on disk after the run.",
    )
    parser.add_argument(
        "--ghidra-timeout",
        type=int,
        default=900,
        help="Ghidra headless timeout in seconds.",
    )
    parser.add_argument(
        "--ghidra-targets-file",
        default="",
        help="Path to the FunctionSiteSurvey target registry JSON.",
    )
    parser.add_argument(
        "--ghidra-report",
        default="",
        help="Path to a FunctionSiteSurvey report JSON (for ghidra-summarize).",
    )

    return parser


# ===========================================================================
# Main
# ===========================================================================


def main(argv: list[str] | None = None) -> None:
    """Read-only entry point. No orphan-process guard.

    Imports ``rift_workflow`` lazily to avoid any module-load-time cost on
    the spawner path. Dispatches to ``rift_workflow._run_command()`` which
    contains the actual handler logic for all 40 read-only commands.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Lazy import: rift_workflow is only needed when a read-only command runs.
    from scripts import rift_workflow as rw

    rw._run_command(args)


if __name__ == "__main__":
    main()
