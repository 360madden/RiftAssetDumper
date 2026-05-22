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
    PositionSourceGapReport     — inventory + gap report
    position-gap-report        — Python gap analysis (needs existing inventory)
    triage-fallback-candidates — List 0-attribute-set meshes with float32 position/normal/UV candidates from existing inventory
    position-source-sibling-lead-guard — inventory + sibling guard
    position-source-sibling-family-report — inventory + family report
    position-source-sibling-probe-report — multi-probe + report
    position-source-sibling-representative-probe-report — representative probe
    position-source-sibling-secondary-probe-report — secondary probe
    position-source-sibling-extra-position-report — extra position probe
    semantic-hint-crosstab       — Python cross-tabulation
    discovery-workbench          — Python workbench
    generated-output-guard       — guard only, no C#
    discovery-suite              — unified pipeline: build → inventory → position reports → guards → summary (supports --quick)
    mesh-streams                 — inventory-nif-mesh-streams + summary
    index-candidates             — inventory-nif-index-candidates + summary
    stream-endianness            — inventory-nif-stream-endianness + summary
    stream-bodies                — inventory-nif-stream-bodies + summary
    decode-geometry              — decode-nif-geometry + summary (needs --id --mesh-block; supports --experimental-position-source)
    batch-export-264             — batch export all 5 known @264-indexed meshes via --export-obj
    all                          — run mesh-bindings, mesh-streams, index-candidates, stream-endianness, stream-bodies
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
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

from scripts.rift_workflow_guards import (  # noqa: E402
    attribute_extra_proof_guard,
    attribute_extra_sibling_proof_guard,
    position_source_sibling_lead_guard,
    residual_lead_guard,
    usage_access_correlation_guard,
)
from scripts.rift_workflow_reports import (  # noqa: E402
    discovery_workbench,
    position_source_gap_report,
    position_source_sibling_extra_position_report,
    position_source_sibling_family_report,
    position_source_sibling_probe_report,
    position_source_sibling_representative_probe_report,
    position_source_sibling_secondary_probe_report,
    residual_position_classifier_report,
    residual_position_cluster_probe_report,
    semantic_hint_cross_tab,
    show_report_summary,
)
from scripts.rift_workflow_utils import (  # noqa: E402
    checked_run,
    generated_output_guard,
    load_json_report,
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
    # Guard commands below are routed manually in _run_command() (run C# + Python
    # assertion), so their COMMAND_MAP entries are documentation-only.
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
    "position-gap-report": {
        "dotnet": "",
        "base": "nif-mesh-binding-inventory",
    },
    "triage-fallback-candidates": {
        "dotnet": "",
        "base": "nif-mesh-binding-inventory",
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
    "decode-geometry": {
        "dotnet": "decode-nif-geometry",
        "base": "decode-nif-geometry",
        "needs_id": True,
        "needs_mesh_block": True,
    },
    "batch-export-264": {
        "dotnet": "",
        "base": "",
    },
    "discovery-suite": {
        "dotnet": "",
        "base": "",
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
    "position-gap-report": "position-gap-report",
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
    "DecodeGeometry": "decode-geometry",
    "BatchExport264": "batch-export-264",
    "DiscoverySuite": "discovery-suite",
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
        "decode-geometry": "DecodeGeometry",
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
    experimental_position_source: bool = False,
    write_obj: bool = False,
    export_obj: bool = False,
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
    if experimental_position_source:
        dotnet_args += ["--experimental-position-source"]
    if write_obj:
        dotnet_args += ["--write-obj"]
    if export_obj:
        dotnet_args += ["--export-obj"]
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

    if command == "position-gap-report":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        inventory_path = out_dir / "nif-mesh-binding-inventory.json"
        if not inventory_path.exists():
            print(
                "ERROR: position-gap-report requires an existing mesh-binding inventory.\n"
                f"  Run 'python scripts/rift_workflow.py mesh-bindings --full' first.\n"
                f"  Expected: {inventory_path}",
                file=sys.stderr,
            )
            sys.exit(1)
        from scripts.rift_position_gap_report import main as gap_report_main
        sys.argv = ["rift_position_gap_report.py", str(inventory_path), "--out", str(out_dir / "position-gap-report.json")]
        sys.exit(gap_report_main())

    if command == "triage-fallback-candidates":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        inventory_path = out_dir / "nif-mesh-binding-inventory.json"
        if not inventory_path.exists():
            print(
                "ERROR: triage-fallback-candidates requires an existing mesh-binding inventory.\n"
                f"  Run 'python scripts/rift_workflow.py mesh-bindings --full' first.\n"
                f"  Expected: {inventory_path}",
                file=sys.stderr,
            )
            sys.exit(1)

        with open(inventory_path, encoding='utf-8-sig') as f:
            data = json.load(f)

        # --- Gather metrics ---
        mesh_block_count = data.get('MeshBlockCount', data.get('MeshBlocks', 0))
        attr_compatible = data.get('AttributeCompatibleMeshes', data.get('AttributeCompatibleSets', 0))
        zero_attr_count = mesh_block_count - attr_compatible

        role_groups = data.get('RoleGroups', [])

        def _find_role(role_name: str) -> dict | None:
            for rg in role_groups:
                if rg.get('Role') == role_name:
                    return rg
            return None

        pos_role = _find_role('position-float3-ror1-lead')
        normal_role = _find_role('normal-float3-ror1-lead')
        uv_role = _find_role('uv-float2-ror1-lead')

        pos_count = pos_role.get('Count', 0) if pos_role else 0
        normal_count = normal_role.get('Count', 0) if normal_role else 0
        uv_count = uv_role.get('Count', 0) if uv_role else 0
        pos_high_conf = pos_role.get('HighConfidenceCount', '?') if pos_role else '-'

        # Attribute-set meshes also have position/normal/UV. Subtract them.
        # approximate: most position-float3 samples are on 0-attr-set meshes
        pos_samples = (pos_role.get('Samples', []) if pos_role else [])
        normal_samples = (normal_role.get('Samples', []) if normal_role else [])
        uv_samples = (uv_role.get('Samples', []) if uv_role else [])

        # --- Display summary ---
        print()
        print("=" * 70)
        print("  Triage: Fallback Candidates (0-Attribute-Set Meshes with Float32 Streams)")
        print("=" * 70)
        print()
        print(f"  Total NiMesh blocks:     {mesh_block_count:>6}")
        print(f"  Attribute-compatible:     {attr_compatible:>6}")
        print(f"  0-attribute-set meshes:  {zero_attr_count:>6}")
        print()
        print("  --- Float32 candidates across ALL meshes ---")
        print(f"  position-float3-ror1-lead: {pos_count:>5} (high confidence: {pos_high_conf})")
        print(f"  normal-float3-ror1-lead:   {normal_count:>5}")
        print(f"  uv-float2-ror1-lead:       {uv_count:>5}")
        print()

        # Show top 0-attr-set meshes with position float32 candidates
        print("  --- Top 0-attr-set meshes with position-float3 candidates ---")
        if pos_samples:
            printed = 0
            for s in pos_samples:
                id_pref = s.get('IdPrefix', s.get('id', '?'))
                mesh_size = s.get('MeshSize', s.get('meshSize', '?'))
                mesh_idx = s.get('MeshBlockIndex', s.get('meshBlockIndex', '?'))
                # Check if this mesh has normal/UV too
                pos_norm = '[ ]'
                pos_uv = '[ ]'
                # Match by ID to check companion streams
                for ns in normal_samples:
                    if ns.get('IdPrefix') == id_pref and ns.get('MeshBlockIndex') == mesh_idx:
                        pos_norm = '[Y]'
                        break
                for us in uv_samples:
                    if us.get('IdPrefix') == id_pref and us.get('MeshBlockIndex') == mesh_idx:
                        pos_uv = '[Y]'
                        break
                print(f"    ID={id_pref} mesh#{mesh_idx} size={mesh_size}  norm={pos_norm} uv={pos_uv}")
                printed += 1
                if printed >= 16:
                    remaining = len(pos_samples) - printed
                    if remaining > 0:
                        print(f"    ... and {remaining} more")
                    break
        else:
            print("    (none)")

        print()
        print("  --- Quick test commands ---")
        test_ids = set()
        for s in pos_samples[:8]:
            test_ids.add(s.get('IdPrefix', ''))
        for tid in sorted(test_ids):
            if tid:
                print(f"    python scripts/rift_workflow.py decode-geometry --id {tid} --mesh-block 6 --experimental-position-source --write-obj")
        print()

        # Summary statistics
        print("  --- Cross-reference summary ---")
        # Count meshes that have both pos and at least one companion (norm or uv)
        pos_only = 0
        pos_norm = 0
        pos_uv = 0
        pos_both = 0
        for s in pos_samples:
            id_pref = s.get('IdPrefix', '')
            mesh_idx = s.get('MeshBlockIndex')
            has_norm = any(
                ns.get('IdPrefix') == id_pref and ns.get('MeshBlockIndex') == mesh_idx
                for ns in normal_samples
            )
            has_uv = any(
                us.get('IdPrefix') == id_pref and us.get('MeshBlockIndex') == mesh_idx
                for us in uv_samples
            )
            if has_norm and has_uv:
                pos_both += 1
            elif has_norm:
                pos_norm += 1
            elif has_uv:
                pos_uv += 1
            else:
                pos_only += 1

        print(f"    Position only:                   {pos_only:>4}")
        print(f"    Position + Normal:               {pos_norm:>4}")
        print(f"    Position + UV:                   {pos_uv:>4}")
        print(f"    Position + Normal + UV:          {pos_both:>4}")
        print(f"    Total position-candidate meshes: {pos_count:>4}")
        print()
        print(f"  Interpretation: {pos_both} meshes have full position+normal+UV float32 streams")
        print("  and can be decoded with --experimental-position-source.")
        print(f"  {pos_norm} more have position+normal (no UV), "
              f"{pos_uv} have position+UV (no normal).")
        print(f"  These are concentrated across {len(pos_samples)} unique sample entries")
        print("  from the full mesh-binding inventory.")
        print()
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

    # --- UsageAccessCorrelationGuard: inventory + Python guard assertion ---

    if command == "usage-access-correlation-guard":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        # Build (unless --skip-build)
        if not args.skip_build and solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

        # Run full mesh-binding inventory
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "nif-mesh-binding-inventory.json"
        dotnet_args: list[str] = [
            "run", "--project", str(project), "--",
            "inventory-nif-mesh-bindings",
            "--root", str(root),
            "--out", str(out_path),
        ]
        if args.full:
            pass  # full scan
        else:
            dotnet_args += ["--limit", str(args.limit)]
        checked_run("usage-access-correlation-guard (inventory)", dotnet_args)

        # Run guard assertion
        usage_access_correlation_guard(str(out_path))
        return

    # --- AttributeExtraProofGuard: inventory + Python guard assertion ---

    if command == "attribute-extra-proof-guard":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        # Build (unless --skip-build)
        if not args.skip_build and solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

        # Run full mesh-binding inventory
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "nif-mesh-binding-inventory.json"
        dotnet_args: list[str] = [
            "run", "--project", str(project), "--",
            "inventory-nif-mesh-bindings",
            "--root", str(root),
            "--out", str(out_path),
        ]
        if args.full:
            pass  # full scan
        else:
            dotnet_args += ["--limit", str(args.limit)]
        checked_run("attribute-extra-proof-guard (inventory)", dotnet_args)

        # Run guard assertion
        attribute_extra_proof_guard(str(out_path))
        return

    # --- AttributeExtraSiblingProofGuard: probe + Python guard assertion ---

    if command == "attribute-extra-sibling-proof-guard":
        if not args.id:
            print(
                "ERROR: 'attribute-extra-sibling-proof-guard' requires --id <16hex>",
                file=sys.stderr,
            )
            print(
                "  Known sibling IDs: 6fc01704d4a509d5, caa9a88e94ec8db0",
                file=sys.stderr,
            )
            sys.exit(1)

        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        # Build (unless --skip-build)
        if not args.skip_build and solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

        # Run probe-nif-attribute-extra for the given asset
        asset_id = args.id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"probe-nif-attribute-extra-{asset_id}-mesh6-extra264.json"
        dotnet_args = [
            "run", "--project", str(project), "--",
            "probe-nif-attribute-extra",
            "--root", str(root),
            "--id", asset_id,
            "--mesh-block", "6",
            "--extra-offset", "264",
            "--out", str(out_path),
        ]
        checked_run(f"attribute-extra-sibling-proof-guard {asset_id}", dotnet_args)

        # Run guard assertion
        attribute_extra_sibling_proof_guard(str(out_path), asset_id)
        return

    # --- PositionSourceSiblingLeadGuard: inventory + Python guard assertion ---

    if command == "position-source-sibling-lead-guard":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        # Build (unless --skip-build)
        if not args.skip_build and solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

        # Run full mesh-binding inventory
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "nif-mesh-binding-inventory.json"
        dotnet_args: list[str] = [
            "run", "--project", str(project), "--",
            "inventory-nif-mesh-bindings",
            "--root", str(root),
            "--out", str(out_path),
        ]
        if args.full:
            pass  # full scan
        else:
            dotnet_args += ["--limit", str(args.limit)]
        checked_run("position-source-sibling-lead-guard (inventory)", dotnet_args)

        # Run guard assertion
        position_source_sibling_lead_guard(str(out_path))
        return

    # --- ResidualLeadGuard: inventory + Python guard assertion

    if command == "residual-lead-guard":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        # Build (unless --skip-build)
        if not args.skip_build and solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

        # Run full mesh-binding inventory
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "nif-mesh-binding-inventory.json"
        dotnet_args: list[str] = [
            "run", "--project", str(project), "--",
            "inventory-nif-mesh-bindings",
            "--root", str(root),
            "--out", str(out_path),
        ]
        if args.full:
            pass  # full scan
        else:
            dotnet_args += ["--limit", str(args.limit)]
        checked_run("residual-lead-guard (inventory)", dotnet_args)

        # Run guard assertion
        residual_lead_guard(str(out_path))
        return

    # --- PositionSourceSiblingFamilyReport: inventory + Python report

    if command == "position-source-sibling-family-report":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        # Build (unless --skip-build)
        if not args.skip_build and solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

        # Run full mesh-binding inventory
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "nif-mesh-binding-inventory.json"
        dotnet_args: list[str] = [
            "run", "--project", str(project), "--",
            "inventory-nif-mesh-bindings",
            "--root", str(root),
            "--out", str(out_path),
        ]
        if args.full:
            pass  # full scan
        else:
            dotnet_args += ["--limit", str(args.limit)]
        checked_run("position-source-sibling-family-report (inventory)", dotnet_args)

        # Run report assertion
        position_source_sibling_family_report(str(out_path))
        return

    # --- ResidualPositionClassifierReport: inventory + Python report ---

    if command == "residual-position-classifier-report":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        # Build (unless --skip-build)
        if not args.skip_build and solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

        # Run full mesh-binding inventory
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "nif-mesh-binding-inventory.json"
        dotnet_args: list[str] = [
            "run", "--project", str(project), "--",
            "inventory-nif-mesh-bindings",
            "--root", str(root),
            "--out", str(out_path),
        ]
        if args.full:
            pass  # full scan
        else:
            dotnet_args += ["--limit", str(args.limit)]
        checked_run("residual-position-classifier-report (inventory)", dotnet_args)

        # Run report
        residual_position_classifier_report(str(out_path))
        return

    # --- PositionSourceGapReport: inventory + Python report ---

    if command == "position-source-gap-report":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        # Build (unless --skip-build)
        if not args.skip_build and solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

        # Run full mesh-binding inventory
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "nif-mesh-binding-inventory.json"
        dotnet_args: list[str] = [
            "run", "--project", str(project), "--",
            "inventory-nif-mesh-bindings",
            "--root", str(root),
            "--out", str(out_path),
        ]
        if args.full:
            pass  # full scan
        else:
            dotnet_args += ["--limit", str(args.limit)]
        checked_run("position-source-gap-report (inventory)", dotnet_args)

        # Run report
        position_source_gap_report(str(out_path))
        return

    # --- PositionSourceSiblingProbeReport: multi-probe orchestrator ---

    if command == "position-source-sibling-probe-report":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        # Build (unless --skip-build)
        if not args.skip_build and solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

        out_dir.mkdir(parents=True, exist_ok=True)

        sibling_probe_specs = [
            {"Pair": "e3de325329", "PairLabel": "meshSize 325/329 shifted-position sibling", "Id": "e3de1077a37d0337", "MeshBlock": 6},
            {"Pair": "e3de325329", "PairLabel": "meshSize 325/329 shifted-position sibling", "Id": "e3de1077a37d0337", "MeshBlock": 30},
            {"Pair": "8e016329", "PairLabel": "meshSize 329 repeated-position sibling", "Id": "8e01613d7ce9e297", "MeshBlock": 6},
            {"Pair": "8e016329", "PairLabel": "meshSize 329 repeated-position sibling", "Id": "8e01613d7ce9e297", "MeshBlock": 31},
        ]

        representative_probe_specs = [
            {"Pair": "mesh305stream188", "PairLabel": "meshSize 305 shared stream@188 sibling", "Id": "04297730afc68f38", "MeshBlock": 7},
            {"Pair": "mesh305stream188", "PairLabel": "meshSize 305 shared stream@188 sibling", "Id": "04297730afc68f38", "MeshBlock": 27},
            {"Pair": "mesh321stream204", "PairLabel": "meshSize 321 shared stream@204 sibling", "Id": "03c35c3ba518aab0", "MeshBlock": 7},
            {"Pair": "mesh321stream204", "PairLabel": "meshSize 321 shared stream@204 sibling", "Id": "03c35c3ba518aab0", "MeshBlock": 31},
            {"Pair": "mesh329stream212", "PairLabel": "meshSize 329 shared stream@212 sibling", "Id": "0364ea142bc00ce7", "MeshBlock": 7},
            {"Pair": "mesh329stream212", "PairLabel": "meshSize 329 shared stream@212 sibling", "Id": "0364ea142bc00ce7", "MeshBlock": 34},
        ]

        secondary_probe_specs = [
            {"Pair": "mesh329stream212secondary", "PairLabel": "meshSize 329 secondary shared stream@212 sibling", "Id": "04de901531a091ab", "MeshBlock": 7, "ExpectedAttributeSetCount": 1},
            {"Pair": "mesh329stream212secondary", "PairLabel": "meshSize 329 secondary shared stream@212 sibling", "Id": "04de901531a091ab", "MeshBlock": 34, "ExpectedAttributeSetCount": 0},
            {"Pair": "mesh305stream188secondary", "PairLabel": "meshSize 305 secondary shared stream@188 sibling", "Id": "0d9a25c9a6af7b18", "MeshBlock": 7, "ExpectedAttributeSetCount": 0},
            {"Pair": "mesh305stream188secondary", "PairLabel": "meshSize 305 secondary shared stream@188 sibling", "Id": "0d9a25c9a6af7b18", "MeshBlock": 27, "ExpectedAttributeSetCount": 0},
            {"Pair": "mesh321stream204secondary", "PairLabel": "meshSize 321 secondary shared stream@204 sibling", "Id": "1dc433d4d2e4db64", "MeshBlock": 7, "ExpectedAttributeSetCount": 1},
            {"Pair": "mesh321stream204secondary", "PairLabel": "meshSize 321 secondary shared stream@204 sibling", "Id": "1dc433d4d2e4db64", "MeshBlock": 31, "ExpectedAttributeSetCount": 0},
        ]

        extra_position_probe_specs = [
            {"Pair": "mesh329extra0364", "PairLabel": "meshSize 329 mesh#34 extra @304/#57", "Id": "0364ea142bc00ce7", "MeshBlock": 7},
            {"Pair": "mesh329extra0364", "PairLabel": "meshSize 329 mesh#34 extra @304/#57", "Id": "0364ea142bc00ce7", "MeshBlock": 34},
            {"Pair": "mesh329extra04de", "PairLabel": "meshSize 329 mesh#34 extra @304/#57", "Id": "04de901531a091ab", "MeshBlock": 7},
            {"Pair": "mesh329extra04de", "PairLabel": "meshSize 329 mesh#34 extra @304/#57", "Id": "04de901531a091ab", "MeshBlock": 34},
            {"Pair": "mesh329extra066f", "PairLabel": "meshSize 329 mesh#34 extra @304/#57", "Id": "066fa520a8ce62e3", "MeshBlock": 7},
            {"Pair": "mesh329extra066f", "PairLabel": "meshSize 329 mesh#34 extra @304/#57", "Id": "066fa520a8ce62e3", "MeshBlock": 34},
        ]

        # Run all probes (16 total)
        all_specs = sibling_probe_specs + representative_probe_specs + secondary_probe_specs + extra_position_probe_specs
        seen = set()
        for spec in all_specs:
            asset_id = spec["Id"]
            mesh_block = spec["MeshBlock"]
            key = (asset_id, mesh_block)
            if key in seen:
                continue
            seen.add(key)

            out_path = out_dir / f"probe-nif-mesh-{asset_id}-mesh{mesh_block}.json"
            dotnet_args = [
                "run", "--project", str(project), "--",
                "probe-nif-mesh",
                "--root", str(root),
                "--id", asset_id,
                "--mesh-block", str(mesh_block),
                "--out", str(out_path),
            ]
            label = f"probe-nif-mesh {asset_id} mesh#{mesh_block}"
            checked_run(label, dotnet_args)

        # Add Path to each spec (report functions need it to load probe JSON)
        for spec in all_specs:
            spec["Path"] = str(out_dir / f"probe-nif-mesh-{spec['Id']}-mesh{spec['MeshBlock']}.json")

        # Run all sub-reports via the orchestrator
        position_source_sibling_probe_report(sibling_probe_specs)
        position_source_sibling_representative_probe_report(representative_probe_specs)
        position_source_sibling_secondary_probe_report(secondary_probe_specs)
        position_source_sibling_extra_position_report(extra_position_probe_specs)
        return

    # --- PositionSourceSiblingRepresentativeProbeReport ---

    if command == "position-source-sibling-representative-probe-report":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        if not args.skip_build and solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

        out_dir.mkdir(parents=True, exist_ok=True)

        representative_probe_specs = [
            {"Pair": "mesh305stream188", "PairLabel": "meshSize 305 shared stream@188 sibling", "Id": "04297730afc68f38", "MeshBlock": 7},
            {"Pair": "mesh305stream188", "PairLabel": "meshSize 305 shared stream@188 sibling", "Id": "04297730afc68f38", "MeshBlock": 27},
            {"Pair": "mesh321stream204", "PairLabel": "meshSize 321 shared stream@204 sibling", "Id": "03c35c3ba518aab0", "MeshBlock": 7},
            {"Pair": "mesh321stream204", "PairLabel": "meshSize 321 shared stream@204 sibling", "Id": "03c35c3ba518aab0", "MeshBlock": 31},
            {"Pair": "mesh329stream212", "PairLabel": "meshSize 329 shared stream@212 sibling", "Id": "0364ea142bc00ce7", "MeshBlock": 7},
            {"Pair": "mesh329stream212", "PairLabel": "meshSize 329 shared stream@212 sibling", "Id": "0364ea142bc00ce7", "MeshBlock": 34},
        ]

        seen = set()
        for spec in representative_probe_specs:
            asset_id = spec["Id"]
            mesh_block = spec["MeshBlock"]
            key = (asset_id, mesh_block)
            if key in seen:
                continue
            seen.add(key)

            out_path = out_dir / f"probe-nif-mesh-{asset_id}-mesh{mesh_block}.json"
            dotnet_args = [
                "run", "--project", str(project), "--",
                "probe-nif-mesh",
                "--root", str(root),
                "--id", asset_id,
                "--mesh-block", str(mesh_block),
                "--out", str(out_path),
            ]
            checked_run(f"probe-nif-mesh {asset_id} mesh#{mesh_block}", dotnet_args)

        # Add Path to each spec
        for spec in representative_probe_specs:
            spec["Path"] = str(out_dir / f"probe-nif-mesh-{spec['Id']}-mesh{spec['MeshBlock']}.json")

        position_source_sibling_representative_probe_report(representative_probe_specs)
        return

    # --- PositionSourceSiblingSecondaryProbeReport ---

    if command == "position-source-sibling-secondary-probe-report":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        if not args.skip_build and solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

        out_dir.mkdir(parents=True, exist_ok=True)

        secondary_probe_specs = [
            {"Pair": "mesh329stream212secondary", "PairLabel": "meshSize 329 secondary shared stream@212 sibling", "Id": "04de901531a091ab", "MeshBlock": 7, "ExpectedAttributeSetCount": 1},
            {"Pair": "mesh329stream212secondary", "PairLabel": "meshSize 329 secondary shared stream@212 sibling", "Id": "04de901531a091ab", "MeshBlock": 34, "ExpectedAttributeSetCount": 0},
            {"Pair": "mesh305stream188secondary", "PairLabel": "meshSize 305 secondary shared stream@188 sibling", "Id": "0d9a25c9a6af7b18", "MeshBlock": 7, "ExpectedAttributeSetCount": 0},
            {"Pair": "mesh305stream188secondary", "PairLabel": "meshSize 305 secondary shared stream@188 sibling", "Id": "0d9a25c9a6af7b18", "MeshBlock": 27, "ExpectedAttributeSetCount": 0},
            {"Pair": "mesh321stream204secondary", "PairLabel": "meshSize 321 secondary shared stream@204 sibling", "Id": "1dc433d4d2e4db64", "MeshBlock": 7, "ExpectedAttributeSetCount": 1},
            {"Pair": "mesh321stream204secondary", "PairLabel": "meshSize 321 secondary shared stream@204 sibling", "Id": "1dc433d4d2e4db64", "MeshBlock": 31, "ExpectedAttributeSetCount": 0},
        ]

        seen = set()
        for spec in secondary_probe_specs:
            asset_id = spec["Id"]
            mesh_block = spec["MeshBlock"]
            key = (asset_id, mesh_block)
            if key in seen:
                continue
            seen.add(key)

            out_path = out_dir / f"probe-nif-mesh-{asset_id}-mesh{mesh_block}.json"
            dotnet_args = [
                "run", "--project", str(project), "--",
                "probe-nif-mesh",
                "--root", str(root),
                "--id", asset_id,
                "--mesh-block", str(mesh_block),
                "--out", str(out_path),
            ]
            checked_run(f"probe-nif-mesh {asset_id} mesh#{mesh_block}", dotnet_args)

        # Add Path to each spec
        for spec in secondary_probe_specs:
            spec["Path"] = str(out_dir / f"probe-nif-mesh-{spec['Id']}-mesh{spec['MeshBlock']}.json")

        position_source_sibling_secondary_probe_report(secondary_probe_specs)
        return

    # --- PositionSourceSiblingExtraPositionReport ---

    if command == "position-source-sibling-extra-position-report":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        if not args.skip_build and solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

        out_dir.mkdir(parents=True, exist_ok=True)

        extra_position_probe_specs = [
            {"Pair": "mesh329extra0364", "PairLabel": "meshSize 329 mesh#34 extra @304/#57", "Id": "0364ea142bc00ce7", "MeshBlock": 7},
            {"Pair": "mesh329extra0364", "PairLabel": "meshSize 329 mesh#34 extra @304/#57", "Id": "0364ea142bc00ce7", "MeshBlock": 34},
            {"Pair": "mesh329extra04de", "PairLabel": "meshSize 329 mesh#34 extra @304/#57", "Id": "04de901531a091ab", "MeshBlock": 7},
            {"Pair": "mesh329extra04de", "PairLabel": "meshSize 329 mesh#34 extra @304/#57", "Id": "04de901531a091ab", "MeshBlock": 34},
            {"Pair": "mesh329extra066f", "PairLabel": "meshSize 329 mesh#34 extra @304/#57", "Id": "066fa520a8ce62e3", "MeshBlock": 7},
            {"Pair": "mesh329extra066f", "PairLabel": "meshSize 329 mesh#34 extra @304/#57", "Id": "066fa520a8ce62e3", "MeshBlock": 34},
        ]

        seen = set()
        for spec in extra_position_probe_specs:
            asset_id = spec["Id"]
            mesh_block = spec["MeshBlock"]
            key = (asset_id, mesh_block)
            if key in seen:
                continue
            seen.add(key)

            out_path = out_dir / f"probe-nif-mesh-{asset_id}-mesh{mesh_block}.json"
            dotnet_args = [
                "run", "--project", str(project), "--",
                "probe-nif-mesh",
                "--root", str(root),
                "--id", asset_id,
                "--mesh-block", str(mesh_block),
                "--out", str(out_path),
            ]
            checked_run(f"probe-nif-mesh {asset_id} mesh#{mesh_block}", dotnet_args)

        # Add Path to each spec
        for spec in extra_position_probe_specs:
            spec["Path"] = str(out_dir / f"probe-nif-mesh-{spec['Id']}-mesh{spec['MeshBlock']}.json")

        position_source_sibling_extra_position_report(extra_position_probe_specs)
        return

    # --- ResidualPositionClusterProbeReport: multi-probe orchestrator ---

    if command == "residual-position-cluster-probe-report":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        # Build (unless --skip-build)
        if not args.skip_build and solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

        out_dir.mkdir(parents=True, exist_ok=True)

        cluster_probe_specs = [
            {"Payload": 96, "Id": "75cea2f2254e8a76", "StreamBlock": 21, "MeshPayloadOffset": 188},
            {"Payload": 180, "Id": "14924c7e9f7f03a9", "StreamBlock": 21, "MeshPayloadOffset": 188},
            {"Payload": 192, "Id": "5a4f390f196037c6", "StreamBlock": 21, "MeshPayloadOffset": 188},
            {"Payload": 288, "Id": "014e1ff60d8508f1", "StreamBlock": 21, "MeshPayloadOffset": 188},
            {"Payload": 396, "Id": "b4de91a46cb7d4bc", "StreamBlock": 21, "MeshPayloadOffset": 188},
        ]

        # Run the cluster probe report (handles all C# probes internally)
        residual_position_cluster_probe_report(
            cluster_probe_specs,
            out_dir,
            project,
            root,
        )
        return

    # --- Complex multi-step modes (ported incrementally) ---

    # These commands need their guard/report functions ported from PowerShell.
    # Until then, they fall through to a "not yet ported" message.
    complex_modes: set[str] = set()

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

    # --- DiscoverySuite: unified pipeline orchestrator ---

    if command == "discovery-suite":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        # Build (unless --skip-build)
        if not args.skip_build and solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

        out_dir.mkdir(parents=True, exist_ok=True)
        inventory_path = out_dir / "nif-mesh-binding-inventory.json"

        start_time = datetime.now()
        print()
        print("=" * 70)
        print("  Discovery Suite — Unified Pipeline")
        print("=" * 70)
        print()

        results: list[dict[str, str | int | float | bool]] = []

        # --- Step 1: Mesh-binding inventory (or reuse if --quick) ---

        if args.quick and inventory_path.exists():
            print("  [--quick] Reusing existing mesh-binding inventory...")
            try:
                existing_data = load_json_report(str(inventory_path))
                mesh_block_count = existing_data.get("MeshBlocks", existing_data.get("MeshBlockCount", 0))
                attr_compatible = existing_data.get("AttributeCompatibleMeshes", 0)
                zero_attr = mesh_block_count - attr_compatible
                results.append({
                    "step": "mesh-bindings",
                    "status": "REUSED",
                    "meshBlockCount": mesh_block_count,
                    "attrCompatible": attr_compatible,
                    "zeroAttrMeshes": zero_attr,
                })
                print(f"    Inventory: {mesh_block_count} meshes, {attr_compatible} attr-compatible")
            except Exception as exc:
                print(f"    [WARN] Could not load existing inventory: {exc}")
                print("    Falling through to fresh run...")
                args.quick = False

        if not args.quick:
            print("")
            print("  -- Step 1/7: Mesh-Binding Inventory --")
            dotnet_args = [
                "run", "--project", str(project), "--",
                "inventory-nif-mesh-bindings",
                "--root", str(root),
                "--out", str(inventory_path),
            ]
            if not args.full:
                dotnet_args += ["--limit", str(args.limit)]
            checked_run("discovery-suite (inventory)", dotnet_args)

            try:
                inv_data = load_json_report(str(inventory_path))
                mesh_block_count = inv_data.get("MeshBlocks", inv_data.get("MeshBlockCount", 0))
                attr_compatible = inv_data.get("AttributeCompatibleMeshes", 0)
                zero_attr = mesh_block_count - attr_compatible
                results.append({
                    "step": "mesh-bindings",
                    "status": "OK",
                    "meshBlockCount": mesh_block_count,
                    "attrCompatible": attr_compatible,
                    "zeroAttrMeshes": zero_attr,
                })
            except Exception as exc:
                print(f"  [WARN] Could not parse inventory: {exc}")
                results.append({"step": "mesh-bindings", "status": "PARSE_ERROR"})

        # --- Step 2: Position-source gap report ---

        print()
        print("  -- Step 2/7: Position-Source Gap Report --")
        try:
            position_source_gap_report(str(inventory_path))
            gap_report_path = out_dir / "position-source-gap-report.json"
            if gap_report_path.exists():
                gap_data = load_json_report(str(gap_report_path))
                gap_families = gap_data.get("TotalFamilies", gap_data.get("Families", []))
                gap_count = len(gap_families) if isinstance(gap_families, list) else gap_families
                results.append({"step": "position-source-gap-report", "status": "OK", "gapFamilies": gap_count})
            else:
                results.append({"step": "position-source-gap-report", "status": "OK"})
        except Exception as exc:
            print(f"  [WARN] Position-source gap report failed: {exc}")
            results.append({"step": "position-source-gap-report", "status": "FAILED"})

        # --- Step 3: Position-source sibling family report ---

        print()
        print("  -- Step 3/7: Position-Source Sibling Family Report --")
        try:
            position_source_sibling_family_report(str(inventory_path))
            family_report_path = out_dir / "position-source-sibling-family-report.json"
            if family_report_path.exists():
                family_data = load_json_report(str(family_report_path))
                sibling_families = family_data.get("Families", [])
                total_groups = len(sibling_families) if isinstance(sibling_families, list) else 0
                results.append({"step": "position-source-sibling-family-report", "status": "OK", "siblingGroups": total_groups})
            else:
                results.append({"step": "position-source-sibling-family-report", "status": "OK"})
        except Exception as exc:
            print(f"  [WARN] Sibling family report failed: {exc}")
            results.append({"step": "position-source-sibling-family-report", "status": "FAILED"})

        # --- Step 4: Residual position classifier report ---

        print()
        print("  -- Step 4/7: Residual Position Classifier Report --")
        try:
            residual_position_classifier_report(str(inventory_path))
            classifier_report_path = out_dir / "residual-position-classifier-report.json"
            if classifier_report_path.exists():
                classifier_data = load_json_report(str(classifier_report_path))
                target_rows = len(classifier_data.get("Rows", []))
                strict_passes = sum(1 for r in classifier_data.get("Rows", []) if r.get("Strict"))
                results.append({
                    "step": "residual-position-classifier-report",
                    "status": "OK",
                    "targetRows": target_rows,
                    "strictPasses": strict_passes,
                })
            else:
                results.append({"step": "residual-position-classifier-report", "status": "OK"})
        except Exception as exc:
            print(f"  [WARN] Residual classifier report failed: {exc}")
            results.append({"step": "residual-position-classifier-report", "status": "FAILED"})

        # --- Step 5: Guards (usage-access-correlation, residual-lead, position-source-sibling-lead) ---

        print()
        print("  -- Step 5/7: Proof Guards --")

        guard_results: list[dict[str, str | bool]] = []
        guard_tasks = [
            ("usage-access-correlation-guard", lambda: usage_access_correlation_guard(str(inventory_path))),
            ("residual-lead-guard", lambda: residual_lead_guard(str(inventory_path))),
            ("position-source-sibling-lead-guard", lambda: position_source_sibling_lead_guard(str(inventory_path))),
        ]
        for guard_name, guard_fn in guard_tasks:
            try:
                print(f"    Running {guard_name}...")
                guard_fn()
                guard_results.append({"guard": guard_name, "passed": True})
                print(f"    {guard_name}: PASSED")
            except AssertionError as exc:
                print(f"    {guard_name}: FAILED - {exc}")
                guard_results.append({"guard": guard_name, "passed": False, "detail": str(exc)})
            except Exception as exc:
                print(f"    {guard_name}: ERROR - {exc}")
                guard_results.append({"guard": guard_name, "passed": False, "detail": str(exc)})

        results.append({
            "step": "proof-guards",
            "status": "OK",
            "guards": guard_results,
            "allPassed": all(g.get("passed", False) for g in guard_results),
        })

        # --- Step 6: Discovery Workbench ---

        print()
        print("  -- Step 6/7: Discovery Workbench --")
        try:
            discovery_workbench(str(REPO_ROOT), str(out_dir), getattr(args, 'privacy_scan', False))
            wb_scoreboard = out_dir / "discovery-workbench-scoreboard.json"
            wb_queue = out_dir / "discovery-next-probe-queue.json"
            wb_seen = wb_scoreboard.exists()
            wb_queue_seen = wb_queue.exists()
            wb_candidates = 0
            wb_checks = 0
            if wb_seen:
                try:
                    wb_data = load_json_report(str(wb_scoreboard))
                    wb_candidates = len(wb_data.get("Candidates", []))
                    wb_checks = len(wb_data.get("CrossChecks", []))
                except Exception:
                    pass
            results.append({
                "step": "discovery-workbench",
                "status": "OK",
                "candidateRows": wb_candidates,
                "crossChecks": wb_checks,
            })
            print(f"    Scoreboard: {wb_candidates} candidates, {wb_checks} cross-checks")
            if wb_queue_seen:
                print(f"    Probe queue: {wb_queue}")
        except Exception as exc:
            print(f"  [WARN] Discovery workbench failed: {exc}")
            results.append({"step": "discovery-workbench", "status": "FAILED"})

        # --- Step 7: Summary report ---

        print()
        print("  -- Step 7/7: Discovery Suite Summary --")

        elapsed = (datetime.now() - start_time).total_seconds()

        print()
        print("  +--------------------------------------------------------------+")
        print("  |                 DISCOVERY SUITE SUMMARY                     |")
        print("  +--------------------------------------------------------------+")
        print()
        print(f"  Duration: {elapsed:.1f}s")
        print(f"  Quick mode: {'yes' if args.quick else 'no'}")
        print(f"  Full scan: {'yes' if args.full else 'no'}")
        print()

        for r in results:
            step_name = r.get("step", "?")
            status = r.get("status", "?")
            status_marker = "[OK]" if status == "OK" else "[!!]" if status in ("FAILED",) else "[..]"
            summary_parts = []

            if "meshBlockCount" in r:
                summary_parts.append(f"{r['meshBlockCount']} meshes")
            if "attrCompatible" in r:
                summary_parts.append(f"{r['attrCompatible']} attr-compat")
            if "gapFamilies" in r:
                summary_parts.append(f"{r['gapFamilies']} gap families")
            if "siblingGroups" in r:
                summary_parts.append(f"{r['siblingGroups']} sibling groups")
            if "targetRows" in r:
                summary_parts.append(f"{r['targetRows']} targets")
            if "strictPasses" in r:
                summary_parts.append(f"{r['strictPasses']} strict passes")
            if r.get("step") == "proof-guards":
                guard_count = len(r.get("guards", []))
                passed_count = sum(1 for g in r.get("guards", []) if g.get("passed"))
                summary_parts.append(f"{passed_count}/{guard_count} guards passed")
            if "candidateRows" in r:
                summary_parts.append(f"{r['candidateRows']} candidates")
            if "crossChecks" in r:
                summary_parts.append(f"{r['crossChecks']} cross-checks")

            summary_str = ", ".join(summary_parts) if summary_parts else ""
            print(f"    {status_marker} {step_name}  {summary_str}")

        print()
        print(f"  Total steps: {len(results)}")
        all_ok = all(r.get("status") in ("OK", "REUSED") for r in results)
        if all_ok:
            print("  Overall: [OK] ALL STEPS COMPLETED SUCCESSFULLY")
        else:
            failed_steps = [r.get("step", "?") for r in results if r.get("status") not in ("OK", "REUSED")]
            print(f"  Overall: [WARN] {len(failed_steps)} step(s) had issues: {', '.join(failed_steps)}")
        print()

        # Write structured summary JSON
        summary_data = {
            "schema": "rift-discovery-suite/v1",
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": elapsed,
            "quick_mode": args.quick,
            "full_scan": args.full,
            "results": results,
        }
        summary_path = out_dir / "discovery-suite-summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2)
        print(f"  Structured summary: {summary_path}")
        print()
        return

    # --- Simple C# command + show_report_summary modes ---

    entry = COMMAND_MAP.get(command)
    if entry is None:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(f"Available: {', '.join(sorted(COMMAND_MAP))}", file=sys.stderr)
        sys.exit(1)

    # --- decode-geometry: needs --id and --mesh-block; passes --experimental-position-source ---

    if command == "decode-geometry":
        if not args.id:
            print("ERROR: 'decode-geometry' requires --id <16hex>", file=sys.stderr)
            sys.exit(1)
        if args.mesh_block < 0:
            print("ERROR: 'decode-geometry' requires --mesh-block <n>", file=sys.stderr)
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
            experimental_position_source=args.experimental_position_source,
            write_obj=args.write_obj,
            export_obj=args.export_obj,
        )
        return

    # --- batch-export-264: export all @264-indexed meshes via --export-obj ---

    if command == "batch-export-264":
        _KNOWN_264_IDS: list[dict[str, int | str]] = [
            {"id": "6fc01704d4a509d5", "v": 128},
            {"id": "caa9a88e94ec8db0", "v": 128},
            {"id": "dfa4b4fccd826b59", "v": 64},
            {"id": "0603cce7cee15eb8", "v": 80},
            {"id": "3de9c1236fe20520", "v": 95},
        ]

        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        # Build (unless --skip-build)
        if not args.skip_build and solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

        out_dir.mkdir(parents=True, exist_ok=True)

        results: list[dict[str, object]] = []
        mesh_block = args.mesh_block if args.mesh_block >= 0 else 6

        print()
        print("=" * 70)
        print("  Batch Export: @264 Indexed OBJs")
        print("=" * 70)
        print()
        print(f"  Mesh block:  {mesh_block}")
        print(f"  Output dir:  {out_dir}")
        print(f"  Asset count: {len(_KNOWN_264_IDS)}")
        print()

        for entry_item in _KNOWN_264_IDS:
            asset_id: str = str(entry_item["id"])
            vertex_count: int = int(entry_item["v"])  # type: ignore[arg-type]
            label = f"export-obj {asset_id} (v={vertex_count})"

            dotnet_args: list[str] = [
                "run", "--project", str(project), "--",
                "decode-nif-geometry",
                "--root", str(root),
                "--id", asset_id,
                "--mesh-block", str(mesh_block),
                "--export-obj",
            ]

            # Output path: use a directory (no file extension) so ResolveOutputPath
            # treats it as a directory, and the OBJ lands at {outDir}/decode-nif-geometry-mesh6.obj
            out_dir_path = out_dir / f"decode-nif-geometry-{asset_id}"
            dotnet_args += ["--out", str(out_dir_path)]

            print(f"\n{'-' * 60}")
            print(f"  {label}")
            print(f"{'-' * 60}")

            try:
                result = subprocess.run(
                    ["dotnet", *dotnet_args],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=str(REPO_ROOT),
                )

                if result.returncode != 0:
                    print(f"  FAILED (exit code {result.returncode})")
                    if result.stderr:
                        stderr_lines = result.stderr.strip().splitlines()
                        for line in stderr_lines[-8:]:
                            print(f"    {line}")
                    results.append({
                        "id": asset_id,
                        "v": vertex_count,
                        "status": "FAIL",
                        "exitCode": result.returncode,
                    })
                    continue

                # Show dotnet output in verbose mode
                if args.verbose and result.stdout:
                    for line in result.stdout.strip().splitlines():
                        print(f"    {line}")

                # Check OBJ was produced — ResolveOutputPath nests into a
                # "decode-nif-geometry" subdirectory when --out is a dir.
                obj_path = out_dir_path / "decode-nif-geometry" / f"decode-nif-geometry-mesh{mesh_block}.obj"
                obj_exists = obj_path.exists()
                obj_size = obj_path.stat().st_size if obj_exists else 0

                if obj_exists and obj_size > 0:
                    print(f"  [OK] OBJ written: {obj_path.name} ({obj_size:,} bytes)")
                    results.append({
                        "id": asset_id,
                        "v": vertex_count,
                        "status": "OK",
                        "objBytes": obj_size,
                    })
                else:
                    print(f"  [WARN] OBJ NOT FOUND at {obj_path}")
                    results.append({
                        "id": asset_id,
                        "v": vertex_count,
                        "status": "NO_OBJ",
                    })

            except Exception as exc:
                print(f"  [ERROR] {exc}")
                if args.verbose:
                    import traceback
                    traceback.print_exc()
                results.append({
                    "id": asset_id,
                    "v": vertex_count,
                    "status": "ERROR",
                    "error": str(exc),
                })

        # --- Summary ---
        print()
        print("=" * 70)
        print("  Batch Export Summary")
        print("=" * 70)
        ok_count = sum(1 for r in results if r.get("status") == "OK")
        fail_count = sum(1 for r in results if r.get("status") != "OK")
        total_bytes = sum(int(r.get("objBytes", 0)) for r in results)  # type: ignore[arg-type]
        print(f"  Passed: {ok_count}/{len(results)}")
        print(f"  Failed: {fail_count}/{len(results)}")
        print(f"  Total OBJ bytes: {total_bytes:,}")
        print()
        for r_item in results:
            sid = r_item.get("id", "?")
            sv = r_item.get("v", "?")
            sstatus = r_item.get("status", "?")
            sobj = int(r_item.get("objBytes", 0))
            marker = "[OK]" if sstatus == "OK" else "[!!]"
            print(f"  {marker} {sid}  v={sv}  status={sstatus}  obj={sobj:,}B")
        print()
        return

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
  python scripts/rift_workflow.py decode-geometry --id c841eb9a0ed1c95e --mesh-block 6
  python scripts/rift_workflow.py decode-geometry --id c841eb9a0ed1c95e --mesh-block 6 --experimental-position-source --full
  python scripts/rift_workflow.py triage-fallback-candidates --full
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
        "--experimental-position-source",
        action="store_true",
        help="Enable experimental position-source fallback for decode-geometry",
    )
    parser.add_argument(
        "--write-obj",
        action="store_true",
        help="Write OBJ file (decode-geometry)",
    )
    parser.add_argument(
        "--export-obj",
        action="store_true",
        help="Enable experimental @264 indexed OBJ export (attribute-set path)",
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
        "--quick",
        action="store_true",
        help="Skip inventory re-run, reuse existing data (discovery-suite)",
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
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full dotnet output for batch commands",
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
