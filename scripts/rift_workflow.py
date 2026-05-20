#!/usr/bin/env python3
"""RIFT asset workflow orchestrator — Python entry point for all workflow commands.

Replaces the main dispatch block in Invoke-RiftAssetWorkflow.ps1.
Delegates C# CLI commands via checked_run() and report/guard functions via
rift_workflow_reports.

Usage:
    python scripts/rift_workflow.py <command> [options]

Commands (kebab-case):
    asset-signatures             — inventory-asset-signatures + summary
    asset-semantic-index         — build-asset-semantic-index + summary
    mesh-bindings                — inventory-nif-mesh-bindings + summary
    mesh-probe                   — probe-nif-mesh + summary (needs --id --mesh-block)
    attribute-extra-probe        — probe-nif-attribute-extra + summary
    attribute-extra-proof-guard  — inventory + guard assertion
    attribute-extra-sibling-proof-guard — sibling probes + guard
    usage-access-correlation-guard — inventory + guard
    residual-lead-guard          — inventory + residual guard
    residual-position-classifier-report — inventory + report
    residual-position-cluster-probe-report — cluster probe
    position-source-gap-report   — inventory + gap report
    position-source-sibling-lead-guard — inventory + sibling guard
    position-source-sibling-family-report — inventory + family report
    position-source-sibling-probe-report — multi-probe + report
    position-source-sibling-representative-probe-report — representative probe
    position-source-sibling-secondary-probe-report — secondary probe
    position-source-sibling-extra-position-report — extra position probe
    semantic-hint-crosstab       — Python cross-tabulation
    discovery-workbench          — Python workbench
    generated-output-guard       — guard only, no C#
    mesh-streams                 — inventory-nif-mesh-streams + summary
    index-candidates             — inventory-nif-index-candidates + summary
    stream-endianness            — inventory-nif-stream-endianness + summary
    stream-bodies                — inventory-nif-stream-bodies + summary
    all                          — run mesh-bindings, mesh-streams, index-candidates, stream-endianness, stream-bodies
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path boilerplate
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

# Default paths (mirrors PS $Root, $Out, $Project, $Solution)
DEFAULT_ROOT = REPO_ROOT / "Source"
DEFAULT_OUT = REPO_ROOT / "Exports"
DEFAULT_PROJECT = REPO_ROOT / "src" / "RiftAssetDumper" / "RiftAssetDumper.csproj"
DEFAULT_SOLUTION = REPO_ROOT / "RiftAssetDumper.slnx"

# ---------------------------------------------------------------------------
# Imports (deferred so path setup happens first)
# ---------------------------------------------------------------------------

from scripts.rift_workflow_utils import (  # noqa: E402
    checked_run,
    generated_output_guard,
)
from scripts.rift_workflow_reports import (  # noqa: E402
    discovery_workbench,
    semantic_hint_cross_tab,
    show_report_summary,
)

# ============================================================================
# Command map — mirrors $commandMap in PowerShell
# ============================================================================

# Each entry: (dotnet_command, base_name, needs_id, needs_mesh_block, needs_extra_offset)
# dotnet_command is empty for pure-Python modes.

COMMAND_MAP: dict[str, dict[str, Any]] = {
    "asset-signatures": {
        "dotnet": "inventory-asset-signatures",
        "base": "asset-signature-inventory",
    },
    "asset-semantic-index": {
        "dotnet": "build-asset-semantic-index",
        "base": "asset-semantic-index",
    },
    "mesh-bindings": {
        "dotnet": "inventory-nif-mesh-bindings",
        "base": "nif-mesh-binding-inventory",
    },
    "mesh-probe": {
        "dotnet": "probe-nif-mesh",
        "base": "probe-nif-mesh",
        "needs_id": True,
        "needs_mesh_block": True,
    },
    "attribute-extra-probe": {
        "dotnet": "probe-nif-attribute-extra",
        "base": "probe-nif-attribute-extra",
        "needs_id": True,
        "needs_mesh_block": True,
        "needs_extra_offset": True,
    },
    "attribute-extra-proof-guard": {
        "dotnet": "inventory-nif-mesh-bindings",
        "base": "nif-mesh-binding-inventory",
    },
    "attribute-extra-sibling-proof-guard": {
        "dotnet": "probe-nif-attribute-extra",
        "base": "probe-nif-attribute-extra",
    },
    "usage-access-correlation-guard": {
        "dotnet": "inventory-nif-mesh-bindings",
        "base": "nif-mesh-binding-inventory",
    },
    "residual-lead-guard": {
        "dotnet": "inventory-nif-mesh-bindings",
        "base": "nif-mesh-binding-inventory",
    },
    "residual-position-classifier-report": {
        "dotnet": "inventory-nif-mesh-bindings",
        "base": "nif-mesh-binding-inventory",
    },
    "residual-position-cluster-probe-report": {
        "dotnet": "",  # multi-step; handled separately
        "base": "",
    },
    "position-source-gap-report": {
        "dotnet": "inventory-nif-mesh-bindings",
        "base": "nif-mesh-binding-inventory",
    },
    "position-source-sibling-lead-guard": {
        "dotnet": "inventory-nif-mesh-bindings",
        "base": "nif-mesh-binding-inventory",
    },
    "position-source-sibling-family-report": {
        "dotnet": "inventory-nif-mesh-bindings",
        "base": "nif-mesh-binding-inventory",
    },
    "position-source-sibling-probe-report": {
        "dotnet": "probe-nif-mesh",
        "base": "probe-nif-mesh",
    },
    "position-source-sibling-representative-probe-report": {
        "dotnet": "probe-nif-mesh",
        "base": "probe-nif-mesh",
    },
    "position-source-sibling-secondary-probe-report": {
        "dotnet": "probe-nif-mesh",
        "base": "probe-nif-mesh",
    },
    "position-source-sibling-extra-position-report": {
        "dotnet": "probe-nif-mesh",
        "base": "probe-nif-mesh",
    },
    "semantic-hint-crosstab": {
        "dotnet": "",
        "base": "",
    },
    "discovery-workbench": {
        "dotnet": "",
        "base": "",
    },
    "generated-output-guard": {
        "dotnet": "",
        "base": "",
    },
    "mesh-streams": {
        "dotnet": "inventory-nif-mesh-streams",
        "base": "nif-mesh-stream-inventory",
    },
    "index-candidates": {
        "dotnet": "inventory-nif-index-candidates",
        "base": "nif-index-candidate-inventory",
    },
    "stream-endianness": {
        "dotnet": "inventory-nif-stream-endianness",
        "base": "nif-stream-endianness-inventory",
    },
    "stream-bodies": {
        "dotnet": "inventory-nif-stream-bodies",
        "base": "nif-stream-body-inventory",
    },
}


# ============================================================================
# Mode name mapping — PowerShell mode name → kebab-case command name
# ============================================================================

PS_MODE_TO_COMMAND: dict[str, str] = {
    "AssetSignatures": "asset-signatures",
    "AssetSemanticIndex": "asset-semantic-index",
    "MeshBindings": "mesh-bindings",
    "MeshProbe": "mesh-probe",
    "AttributeExtraProbe": "attribute-extra-probe",
    "AttributeExtraProofGuard": "attribute-extra-proof-guard",
    "AttributeExtraSiblingProofGuard": "attribute-extra-sibling-proof-guard",
    "UsageAccessCorrelationGuard": "usage-access-correlation-guard",
    "ResidualLeadGuard": "residual-lead-guard",
    "ResidualPositionClassifierReport": "residual-position-classifier-report",
    "ResidualPositionClusterProbeReport": "residual-position-cluster-probe-report",
    "PositionSourceGapReport": "position-source-gap-report",
    "PositionSourceSiblingLeadGuard": "position-source-sibling-lead-guard",
    "PositionSourceSiblingFamilyReport": "position-source-sibling-family-report",
    "PositionSourceSiblingProbeReport": "position-source-sibling-probe-report",
    "PositionSourceSiblingRepresentativeProbeReport": "position-source-sibling-representative-probe-report",
    "PositionSourceSiblingSecondaryProbeReport": "position-source-sibling-secondary-probe-report",
    "PositionSourceSiblingExtraPositionReport": "position-source-sibling-extra-position-report",
    "DiscoveryWorkbench": "discovery-workbench",
    "GeneratedOutputGuard": "generated-output-guard",
    "SemanticHintCrossTab": "semantic-hint-crosstab",
    "MeshStreams": "mesh-streams",
    "IndexCandidates": "index-candidates",
    "StreamEndianness": "stream-endianness",
    "StreamBodies": "stream-bodies",
    "All": "all",
}


# ============================================================================
# Command routing
# ============================================================================


def _get_summary_mode_name(command: str) -> str:
    """Map command to Show-ReportSummary mode name (mirrors PS $ModeName)."""
    mapping: dict[str, str] = {
        "asset-signatures": "AssetSignatures",
        "asset-semantic-index": "AssetSemanticIndex",
        "mesh-bindings": "MeshBindings",
        "mesh-probe": "MeshProbe",
        "attribute-extra-probe": "AttributeExtraProbe",
        "mesh-streams": "MeshStreams",
        "index-candidates": "IndexCandidates",
        "stream-endianness": "StreamEndianness",
        "stream-bodies": "StreamBodies",
    }
    return mapping.get(command, command)


def _run_dotnet_and_summarize(
    command: str,
    out_dir: Path,
    project: Path,
    root: Path,
    smoke_max_total: int,
    limit: int,
    asset_id: str,
    mesh_block: int,
    extra_offset: int,
    asset_type: str,
    semantic_categories: list[str],
    full: bool,
) -> None:
    """Run dotnet command and show report summary."""
    entry = COMMAND_MAP[command]
    dotnet_command = entry["dotnet"]
    base = entry["base"]

    if not dotnet_command:
        raise ValueError(f"Command {command} has no dotnet command; use a different handler.")

    out_dir.mkdir(parents=True, exist_ok=True)

    # Build dotnet args
    dotnet_args: list[str] = ["run", "--project", str(project), "--", dotnet_command]

    # Add common options
    dotnet_args += ["--root", str(root)]

    if full:
        pass  # Full means no --limit or --smoke-max-total
    else:
        if dotnet_command.startswith("inventory-"):
            dotnet_args += ["--limit", str(limit)]
        elif dotnet_command.startswith("build-"):
            dotnet_args += ["--smoke-max-total", str(smoke_max_total)]

    if asset_id:
        dotnet_args += ["--id", asset_id]
    if mesh_block >= 0:
        dotnet_args += ["--mesh-block", str(mesh_block)]
    if extra_offset >= 0:
        dotnet_args += ["--extra-offset", str(extra_offset)]
    if asset_type:
        dotnet_args += ["--type", asset_type]
    for cat in semantic_categories:
        if cat:
            dotnet_args += ["--semantic-category", cat]

    # Output path
    if extra_offset >= 0:
        out_path = out_dir / (
            f"{base}-{asset_id}-mesh{mesh_block}-extra{extra_offset}.json"
        )
    elif asset_id:
        out_path = out_dir / f"{base}-{asset_id}.json"
    elif asset_type:
        out_path = out_dir / f"{base}-{asset_type}.json"
    else:
        out_path = out_dir / f"{base}.json"
    dotnet_args += ["--out", str(out_path)]

    # Run it
    label = command
    if asset_id:
        label = f"{command} {asset_id}"
    checked_run(label, dotnet_args)

    # Show summary
    mode_name = _get_summary_mode_name(command)
    show_report_summary(mode_name, str(out_path))


def _run_command(args: argparse.Namespace) -> None:
    """Main command router."""
    command: str = args.command

    # --- Pure-Python modes (no C# at all) ---

    if command == "generated-output-guard":
        generated_output_guard()
        return

    if command == "semantic-hint-crosstab":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        semantic_hint_cross_tab(str(out_dir))
        return

    if command == "discovery-workbench":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        repo_root = Path(args.root) if args.root else REPO_ROOT
        discovery_workbench(str(repo_root), str(out_dir), args.privacy_scan)
        return

    if command == "all":
        for subcommand in (
            "mesh-bindings",
            "mesh-streams",
            "index-candidates",
            "stream-endianness",
            "stream-bodies",
        ):
            print(f"\n{'='*60}")
            print(f"  ALL → {subcommand}")
            print(f"{'='*60}")
            _run_dotnet_and_summarize(
                command=subcommand,
                out_dir=Path(args.out) if args.out else DEFAULT_OUT,
                project=Path(args.project) if args.project else DEFAULT_PROJECT,
                root=Path(args.root) if args.root else DEFAULT_ROOT,
                smoke_max_total=args.smoke_max_total,
                limit=args.limit,
                asset_id=args.id or "",
                mesh_block=args.mesh_block,
                extra_offset=args.extra_offset,
                asset_type=args.type or "",
                semantic_categories=args.semantic_category or [],
                full=args.full,
            )
        return

    # --- Complex multi-step modes (ported incrementally) ---

    # These commands need their guard/report functions ported from PowerShell.
    # Until then, they fall through to a "not yet ported" message.
    complex_modes = {
        "attribute-extra-proof-guard",
        "attribute-extra-sibling-proof-guard",
        "usage-access-correlation-guard",
        "residual-lead-guard",
        "residual-position-classifier-report",
        "residual-position-cluster-probe-report",
        "position-source-gap-report",
        "position-source-sibling-lead-guard",
        "position-source-sibling-family-report",
        "position-source-sibling-probe-report",
        "position-source-sibling-representative-probe-report",
        "position-source-sibling-secondary-probe-report",
        "position-source-sibling-extra-position-report",
    }

    if command in complex_modes:
        print(
            f"\n⚠  Command '{command}' has not been ported from PowerShell yet.",
            file=sys.stderr,
        )
        print(
            "   The original PowerShell script (Invoke-RiftAssetWorkflow.ps1) is still available.",
            file=sys.stderr,
        )
        print(
            f"   Run: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Invoke-RiftAssetWorkflow.ps1 -Mode {command}",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Simple C# command + show_report_summary modes ---

    entry = COMMAND_MAP.get(command)
    if entry is None:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(f"Available: {', '.join(sorted(COMMAND_MAP))}", file=sys.stderr)
        sys.exit(1)

    # Validate required args
    if entry.get("needs_id") and not args.id:
        print(f"ERROR: '{command}' requires --id <16hex>", file=sys.stderr)
        sys.exit(1)
    if entry.get("needs_mesh_block") and args.mesh_block < 0:
        print(f"ERROR: '{command}' requires --mesh-block <index>", file=sys.stderr)
        sys.exit(1)
    if entry.get("needs_extra_offset") and args.extra_offset < 0:
        print(f"ERROR: '{command}' requires --extra-offset <offset>", file=sys.stderr)
        sys.exit(1)

    # Optional dotnet build step (unless --skip-build)
    if not args.skip_build:
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION
        if solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

    _run_dotnet_and_summarize(
        command=command,
        out_dir=Path(args.out) if args.out else DEFAULT_OUT,
        project=Path(args.project) if args.project else DEFAULT_PROJECT,
        root=Path(args.root) if args.root else DEFAULT_ROOT,
        smoke_max_total=args.smoke_max_total,
        limit=args.limit,
        asset_id=args.id or "",
        mesh_block=args.mesh_block,
        extra_offset=args.extra_offset,
        asset_type=args.type or "",
        semantic_categories=args.semantic_category or [],
        full=args.full,
    )


# ============================================================================
# CLI
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RIFT asset workflow orchestrator (Python)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/rift_workflow.py mesh-bindings
  python scripts/rift_workflow.py mesh-bindings --full
  python scripts/rift_workflow.py mesh-probe --id c841eb9a0ed1c95e --mesh-block 6
  python scripts/rift_workflow.py asset-signatures --smoke-max-total 500
  python scripts/rift_workflow.py semantic-hint-crosstab
  python scripts/rift_workflow.py all --full
        """,
    )
    parser.add_argument(
        "command",
        help="Workflow command to run",
        choices=sorted(COMMAND_MAP) + ["all"],
    )
    parser.add_argument(
        "--root",
        default="",
        help=f"Source directory (default: {DEFAULT_ROOT})",
    )
    parser.add_argument(
        "--out",
        default="",
        help=f"Output directory (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--project",
        default="",
        help=f"C# project path (default: {DEFAULT_PROJECT})",
    )
    parser.add_argument(
        "--solution",
        default="",
        help=f"Solution path for dotnet build step (default: {DEFAULT_SOLUTION})",
    )
    parser.add_argument(
        "--smoke-max-total",
        type=int,
        default=100,
        help="Max entries for smoke mode (default: 100)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Limit for inventory commands (default: 100)",
    )
    parser.add_argument(
        "--id",
        default="",
        help="Asset ID for probe commands (16 hex chars)",
    )
    parser.add_argument(
        "--mesh-block",
        type=int,
        default=-1,
        help="Mesh block index for probe commands",
    )
    parser.add_argument(
        "--extra-offset",
        type=int,
        default=-1,
        help="Extra stream offset for attribute-extra-probe",
    )
    parser.add_argument(
        "--type",
        dest="type",
        default="",
        help="Asset type filter for asset-semantic-index",
    )
    parser.add_argument(
        "--semantic-category",
        action="append",
        default=[],
        help="Semantic category filter (repeatable)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full scan (no smoke/limit)",
    )
    parser.add_argument(
        "--no-smoke",
        action="store_true",
        help="Skip smoke limiting (alias for --full)",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip dotnet build step",
    )
    parser.add_argument(
        "--privacy-scan",
        action="store_true",
        help="Enable privacy scan (discovery-workbench)",
    )

    args = parser.parse_args()

    # Normalize: "--no-smoke" is equivalent to "--full" (for backward compat with old PS flags)
    if args.no_smoke:
        args.full = True

    # --- Safety guard: always run generated_output_guard first ---
    print("\n--- GeneratedOutputGuard (Python)")
    try:
        generated_output_guard()
    except Exception as exc:
        print(f"\nGeneratedOutputGuard FAILED: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\n==> {args.command} (Python)")

    try:
        _run_command(args)
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
