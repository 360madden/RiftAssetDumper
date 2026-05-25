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
    ghidra-pairing-non-export-guard — fail-closed static guard for candidate-only Ghidra pairings
    ghidra-pairing-review-report — inventory + Ghidra pairing review report
    ghidra-attribute-candidate-report — group Ghidra-only review rows by sample mesh
    ghidra-attribute-candidate-guard — grouped Ghidra candidate baseline guard
    ghidra-review-rank-probes — batch mesh-probe focused Ghidra review ranks
    ghidra-review-rank-probes-summary — summarize ignored Ghidra review-rank probe manifests
    ghidra-workflow-guard-suite — run Ghidra target, NiDataStream promotion, and attribute guards
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
    tools-status                 — show configured third-party reverse-engineering tools
    ghidra-dry-run               — verify Ghidra/JDK registry wiring without launching Ghidra
    ghidra-run                   — run Ghidra headless through the repo workflow guard
    ghidra-function-site-target-guard — validate tracked FunctionSiteSurvey target safety
    ghidra-function-site-status  — show ignored report/summary status for FunctionSiteSurvey targets
    ghidra-function-site-survey  — run/list serialized FunctionSiteSurvey targets
    ghidra-summarize             — summarize FunctionSiteSurvey JSON from ignored Ghidra reports
    nidatastream-evidence-status — list ignored local NiDataStream/Ghidra evidence artifact timestamps
    nidatastream-promotion-status — show post-Stage-18 NiDataStream promotion gates
    nidatastream-promotion-dashboard — write compact Markdown dashboard for promotion gates
    nidatastream-promotion-preflight — run dashboard + Ghidra/NiDataStream promotion guard suite
    nidatastream-parser-field-proof-guard — fail closed on premature NiDataStream parser/export promotion
    nidatastream-parser-export-non-consumption-guard — ensure candidate NiDataStream/Ghidra evidence stays report-only
    nidatastream-descriptor-proof-status — candidate-only descriptor helper evidence status
    nidatastream-descriptor-sample-compare — compare descriptor proof with copied-sample byte evidence
    nidatastream-layout          — read-only NiDataStream layout report/validator
    all                          — run mesh-bindings, mesh-streams, index-candidates, stream-endianness, stream-bodies
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
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
    ghidra_attribute_candidate_guard,
    ghidra_pairing_non_export_guard,
    nidatastream_parser_export_non_consumption_guard,
    position_source_sibling_lead_guard,
    residual_lead_guard,
    usage_access_correlation_guard,
)
from scripts.rift_workflow_reports import (  # noqa: E402
    discovery_workbench,
    ghidra_attribute_candidate_report,
    ghidra_pairing_review_report,
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
    format_markdown_cell,
    generated_output_guard,
    load_json_report,
    load_tools_config,
    show_tools_status,
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
    "ghidra-pairing-non-export-guard": {
        "dotnet": "",
        "base": "",
    },
    "residual-position-classifier-report": {
        "dotnet": "inventory-nif-mesh-bindings",
        "base": "nif-mesh-binding-inventory",
    },
    "ghidra-pairing-review-report": {
        "dotnet": "inventory-nif-mesh-bindings",
        "base": "nif-mesh-binding-inventory",
    },
    "ghidra-attribute-candidate-report": {
        "dotnet": "",
        "base": "",
    },
    "ghidra-attribute-candidate-guard": {
        "dotnet": "",
        "base": "",
    },
    "ghidra-review-rank-probes": {
        "dotnet": "",
        "base": "",
    },
    "ghidra-review-rank-probes-summary": {
        "dotnet": "",
        "base": "",
    },
    "ghidra-workflow-guard-suite": {
        "dotnet": "",
        "base": "",
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
    "tools-status": {
        "dotnet": "",
        "base": "",
    },
    "ghidra-dry-run": {
        "dotnet": "",
        "base": "",
    },
    "ghidra-run": {
        "dotnet": "",
        "base": "",
    },
    "ghidra-function-site-target-guard": {
        "dotnet": "",
        "base": "",
    },
    "ghidra-function-site-status": {
        "dotnet": "",
        "base": "",
    },
    "ghidra-function-site-survey": {
        "dotnet": "",
        "base": "",
    },
    "ghidra-summarize": {
        "dotnet": "",
        "base": "",
    },
    "nidatastream-promotion-status": {
        "dotnet": "",
        "base": "",
    },
    "nidatastream-evidence-status": {
        "dotnet": "",
        "base": "",
    },
    "nidatastream-promotion-dashboard": {
        "dotnet": "",
        "base": "",
    },
    "nidatastream-promotion-preflight": {
        "dotnet": "",
        "base": "",
    },
    "nidatastream-parser-field-proof-guard": {
        "dotnet": "",
        "base": "",
    },
    "nidatastream-parser-export-non-consumption-guard": {
        "dotnet": "",
        "base": "",
    },
    "nidatastream-descriptor-proof-status": {
        "dotnet": "",
        "base": "",
    },
    "nidatastream-descriptor-sample-compare": {
        "dotnet": "",
        "base": "",
    },
    "nidatastream-layout": {
        "dotnet": "",
        "base": "nidatastream-layout-report",
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
    "GhidraPairingNonExportGuard": "ghidra-pairing-non-export-guard",
    "GhidraPairingReviewReport": "ghidra-pairing-review-report",
    "GhidraAttributeCandidateReport": "ghidra-attribute-candidate-report",
    "GhidraAttributeCandidateGuard": "ghidra-attribute-candidate-guard",
    "GhidraReviewRankProbes": "ghidra-review-rank-probes",
    "GhidraReviewRankProbesSummary": "ghidra-review-rank-probes-summary",
    "GhidraWorkflowGuardSuite": "ghidra-workflow-guard-suite",
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
    "ToolsStatus": "tools-status",
    "GhidraDryRun": "ghidra-dry-run",
    "GhidraRun": "ghidra-run",
    "GhidraFunctionSiteTargetGuard": "ghidra-function-site-target-guard",
    "GhidraFunctionSiteStatus": "ghidra-function-site-status",
    "GhidraFunctionSiteSurvey": "ghidra-function-site-survey",
    "GhidraSummarize": "ghidra-summarize",
    "NiDataStreamEvidenceStatus": "nidatastream-evidence-status",
    "NiDataStreamPromotionStatus": "nidatastream-promotion-status",
    "NiDataStreamPromotionDashboard": "nidatastream-promotion-dashboard",
    "NiDataStreamPromotionPreflight": "nidatastream-promotion-preflight",
    "NiDataStreamParserFieldProofGuard": "nidatastream-parser-field-proof-guard",
    "NiDataStreamParserExportNonConsumptionGuard": "nidatastream-parser-export-non-consumption-guard",
    "NiDataStreamDescriptorProofStatus": "nidatastream-descriptor-proof-status",
    "NiDataStreamDescriptorSampleCompare": "nidatastream-descriptor-sample-compare",
    "NiDataStreamLayout": "nidatastream-layout",
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


def _ghidra_project_dir_arg(args: argparse.Namespace) -> Path:
    """Return the Ghidra project directory, defaulting to ignored Exports/."""
    return Path(args.ghidra_project_dir) if args.ghidra_project_dir else DEFAULT_OUT / "ghidra-projects"


def _ghidra_script_args_arg(args: argparse.Namespace) -> list[str] | None:
    """Return repeated Ghidra post-script args, normalized for ghidra_runner."""
    script_args = args.ghidra_script_arg or []
    return script_args if script_args else None


def _json_int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _apply_mesh_probe_review_rank(args: argparse.Namespace) -> None:
    """Resolve mesh-probe --review-rank N through the Ghidra review report."""
    if args.review_rank <= 0:
        return

    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    review_path = out_dir / "ghidra-pairing-review-report.json"
    if not review_path.exists():
        inventory_path = out_dir / "nif-mesh-binding-inventory.json"
        if not inventory_path.exists():
            print(
                "ERROR: mesh-probe --review-rank requires an existing "
                "ghidra-pairing-review-report.json or nif-mesh-binding-inventory.json.\n"
                f"  Expected report: {review_path}\n"
                f"  Expected inventory: {inventory_path}\n"
                "  Run: python scripts/rift_workflow.py ghidra-pairing-review-report --quick",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"mesh-probe --review-rank: building review report from existing inventory {inventory_path}")
        ghidra_pairing_review_report(str(inventory_path), out_dir, take=args.limit)

    report = load_json_report(str(review_path))
    findings = report.get("Findings")
    if not isinstance(findings, list):
        print(f"ERROR: review report has no Findings array: {review_path}", file=sys.stderr)
        sys.exit(1)

    selected = next(
        (
            finding
            for finding in findings
            if isinstance(finding, dict) and _json_int_or_none(finding.get("Rank")) == args.review_rank
        ),
        None,
    )
    if selected is None:
        available = [
            str(rank)
            for finding in findings
            if isinstance(finding, dict)
            for rank in [_json_int_or_none(finding.get("Rank"))]
            if rank is not None
        ]
        print(
            f"ERROR: review rank {args.review_rank} not found in {review_path}. "
            f"Available ranks: {', '.join(available) if available else 'none'}",
            file=sys.stderr,
        )
        sys.exit(1)

    asset_id_raw = selected.get("SampleIdPrefix")
    mesh_block = _json_int_or_none(selected.get("SampleMeshBlockIndex"))
    asset_id = asset_id_raw if isinstance(asset_id_raw, str) else ""
    if not asset_id or mesh_block is None:
        print(
            f"ERROR: review rank {args.review_rank} is missing SampleIdPrefix/SampleMeshBlockIndex.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.id and args.id.lower() != asset_id.lower():
        print(
            f"ERROR: --id {args.id} conflicts with review rank {args.review_rank} sample {asset_id}.",
            file=sys.stderr,
        )
        sys.exit(1)
    if args.mesh_block >= 0 and args.mesh_block != mesh_block:
        print(
            f"ERROR: --mesh-block {args.mesh_block} conflicts with review rank "
            f"{args.review_rank} sample mesh block {mesh_block}.",
            file=sys.stderr,
        )
        sys.exit(1)

    args.id = asset_id
    args.mesh_block = mesh_block
    print(
        f"mesh-probe --review-rank {args.review_rank}: "
        f"id={asset_id} meshBlock={mesh_block} "
        f"kind={selected.get('ReviewKind', '-')}"
    )


def _ensure_ghidra_pairing_review_report(
    out_dir: Path,
    limit: int,
    consumer: str = "Ghidra pairing review workflow",
) -> Path:
    """Return a Ghidra pairing review report, rebuilding it from inventory if needed."""
    review_path = out_dir / "ghidra-pairing-review-report.json"
    if review_path.exists():
        return review_path

    inventory_path = out_dir / "nif-mesh-binding-inventory.json"
    if not inventory_path.exists():
        raise ValueError(
            f"{consumer} requires an existing "
            "ghidra-pairing-review-report.json or nif-mesh-binding-inventory.json.\n"
            f"  Expected report: {review_path}\n"
            f"  Expected inventory: {inventory_path}\n"
            "  Run: python scripts/rift_workflow.py ghidra-pairing-review-report --quick --limit 25"
        )

    print(f"ghidra-review-rank-probes: building review report from existing inventory {inventory_path}")
    ghidra_pairing_review_report(str(inventory_path), out_dir, take=limit)
    return review_path


def _ensure_ghidra_attribute_candidate_report(
    out_dir: Path,
    limit: int,
    consumer: str = "Ghidra attribute candidate workflow",
) -> Path:
    """Return a grouped Ghidra attribute candidate report, rebuilding it if needed."""
    report_path = out_dir / "ghidra-attribute-candidate-report.json"
    if report_path.exists():
        return report_path

    review_path = _ensure_ghidra_pairing_review_report(out_dir, limit, consumer)
    ghidra_attribute_candidate_report(review_path, out_dir)
    return report_path


def _slugify_review_kind(review_kind: str) -> str:
    """Return a filesystem-safe slug for review-kind specific generated files."""
    return "-".join(part for part in "".join(
        char.lower() if char.isalnum() else "-" for char in review_kind
    ).split("-") if part) or "all"


def _run_ghidra_review_rank_probes(args: argparse.Namespace) -> None:
    """Batch-refresh ignored mesh-probe JSON for ranked Ghidra review findings."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    review_report_limit = args.review_report_limit if args.review_report_limit > 0 else args.limit
    review_path = _ensure_ghidra_pairing_review_report(out_dir, review_report_limit, "ghidra-review-rank-probes")
    report = load_json_report(str(review_path))
    findings = report.get("Findings")
    if not isinstance(findings, list):
        raise ValueError(f"Ghidra review report has no Findings array: {review_path}")

    review_kind = str(args.review_kind or "ghidra-only")
    selected: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        if review_kind.lower() != "all" and str(finding.get("ReviewKind", "")) != review_kind:
            continue
        rank = _json_int_or_none(finding.get("Rank"))
        asset_id = finding.get("SampleIdPrefix")
        mesh_block = _json_int_or_none(finding.get("SampleMeshBlockIndex"))
        if rank is None or not isinstance(asset_id, str) or mesh_block is None:
            continue
        selected.append(finding)

    selected.sort(key=lambda finding: _json_int_or_none(finding.get("Rank")) or 0)
    if args.limit > 0:
        selected = selected[: args.limit]
    if not selected:
        raise ValueError(f"No review findings matched ReviewKind={review_kind!r} in {review_path}.")

    if not args.skip_build:
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION
        if solution.exists():
            checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

    probe_root = out_dir / "ghidra-review-rank-probes"
    probe_root.mkdir(parents=True, exist_ok=True)
    project = Path(args.project) if args.project else DEFAULT_PROJECT
    root = Path(args.root) if args.root else DEFAULT_ROOT

    print(
        f"ghidra-review-rank-probes: probing {len(selected)} finding(s) "
        f"from {review_path} into {probe_root}"
    )
    results: list[dict[str, object]] = []
    for finding in selected:
        rank = _json_int_or_none(finding.get("Rank"))
        asset_id = str(finding.get("SampleIdPrefix"))
        mesh_block = _json_int_or_none(finding.get("SampleMeshBlockIndex"))
        if rank is None or mesh_block is None:
            continue
        rank_dir = probe_root / f"rank{rank:02d}"
        output_path = rank_dir / f"probe-nif-mesh-{asset_id}.json"
        print(
            f"\n--- rank {rank}: id={asset_id} meshBlock={mesh_block} "
            f"kind={finding.get('ReviewKind', '-')}"
        )
        _run_dotnet_and_summarize(
            command="mesh-probe",
            out_dir=rank_dir,
            project=project,
            root=root,
            smoke_max_total=args.smoke_max_total,
            limit=args.limit,
            asset_id=asset_id,
            mesh_block=mesh_block,
            extra_offset=-1,
            asset_type="",
            semantic_categories=[],
            full=args.full,
        )
        results.append(
            {
                "Rank": rank,
                "ReviewKind": str(finding.get("ReviewKind", "-")),
                "SampleIdPrefix": asset_id,
                "SampleMeshBlockIndex": mesh_block,
                "GhidraRoles": str(finding.get("GhidraRoles", "-")),
                "OutputJson": str(output_path),
            }
        )

    manifest = {
        "SchemaVersion": "ghidra-review-rank-probes-manifest/v1",
        "CandidateOnly": True,
        "GeneratedAt": datetime.now().isoformat(),
        "SourceReviewReport": str(review_path),
        "ProbeRoot": str(probe_root),
        "ReviewKindFilter": review_kind,
        "SelectedCount": len(results),
        "ReviewReportLimit": review_report_limit,
        "Results": results,
    }
    manifest_slug = _slugify_review_kind(review_kind)
    manifest_json = probe_root / f"manifest-{manifest_slug}.json"
    manifest_json.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    latest_manifest_json = probe_root / "manifest.json"
    latest_manifest_json.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    md_lines = [
        "# Ghidra review-rank probe manifest",
        "",
        "Candidate-only: yes. These probe outputs are ignored workflow evidence, not parser/export inputs.",
        "",
        f"- Source review report: `{review_path}`",
        f"- Review kind filter: `{review_kind}`",
        f"- Selected ranks: `{len(results)}`",
        "",
        "| Rank | Kind | Sample | Mesh | Roles | Output |",
        "|---:|---|---|---:|---|---|",
    ]
    for result in results:
        md_lines.append(
            f"| {result['Rank']} "
            f"| {result['ReviewKind']} "
            f"| `{result['SampleIdPrefix']}` "
            f"| {result['SampleMeshBlockIndex']} "
            f"| `{result['GhidraRoles']}` "
            f"| `{Path(str(result['OutputJson'])).name}` |"
        )
    manifest_md = probe_root / f"manifest-{manifest_slug}.md"
    manifest_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    latest_manifest_md = probe_root / "manifest.md"
    latest_manifest_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"GhidraReviewRankProbes manifest JSON: {manifest_json}")
    print(f"GhidraReviewRankProbes manifest markdown: {manifest_md}")
    print("GhidraReviewRankProbes passed: focused probe outputs remain under ignored Exports/.")


def _run_ghidra_review_rank_probes_summary(args: argparse.Namespace) -> None:
    """Summarize ignored per-kind Ghidra review-rank probe manifests."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    probe_root = out_dir / "ghidra-review-rank-probes"
    kind_filter = str(args.review_kind or "all").lower()
    if not probe_root.exists():
        print(
            "ERROR: ghidra-review-rank-probes-summary requires existing ignored probe manifests.\n"
            f"  Expected probe root: {probe_root}\n"
            "  Run: python scripts/rift_workflow.py ghidra-review-rank-probes --limit 14 --skip-build",
            file=sys.stderr,
        )
        sys.exit(1)

    manifest_paths = sorted(path for path in probe_root.glob("manifest-*.json") if path.name != "manifest.json")
    if not manifest_paths and (probe_root / "manifest.json").exists():
        manifest_paths = [probe_root / "manifest.json"]
    if not manifest_paths:
        print(
            "ERROR: ghidra-review-rank-probes-summary found no manifest JSON files.\n"
            f"  Expected files like: {probe_root / 'manifest-ghidra-only.json'}",
            file=sys.stderr,
        )
        sys.exit(1)

    review_kind_summaries: list[dict[str, object]] = []
    total_selected = 0
    for manifest_path in manifest_paths:
        manifest = load_json_report(str(manifest_path))
        review_kind = str(manifest.get("ReviewKindFilter", "-"))
        if kind_filter != "all" and review_kind.lower() != kind_filter:
            continue
        results = manifest.get("Results")
        if not isinstance(results, list):
            print(f"ERROR: manifest {manifest_path} is missing a Results array.", file=sys.stderr)
            sys.exit(1)

        role_counts: dict[str, int] = {}
        ranks: list[int] = []
        sample_meshes: list[str] = []
        for result in results:
            if not isinstance(result, dict):
                continue
            rank = _json_int_or_none(result.get("Rank"))
            mesh_block = _json_int_or_none(result.get("SampleMeshBlockIndex"))
            sample_id = str(result.get("SampleIdPrefix", "-"))
            role = str(result.get("GhidraRoles", "-"))
            role_counts[role] = role_counts.get(role, 0) + 1
            if rank is not None:
                ranks.append(rank)
            if sample_id != "-" and mesh_block is not None:
                sample_meshes.append(f"{sample_id}#mesh{mesh_block}")

        selected_count = len(results)
        total_selected += selected_count
        review_kind_summaries.append(
            {
                "ReviewKind": review_kind,
                "ManifestPath": str(manifest_path),
                "SelectedCount": selected_count,
                "Ranks": sorted(ranks),
                "SampleMeshes": sorted(set(sample_meshes)),
                "GhidraRoleCounts": dict(sorted(role_counts.items())),
            }
        )

    if not review_kind_summaries:
        print(
            f"ERROR: no ghidra-review-rank-probes manifests matched --review-kind {kind_filter}.",
            file=sys.stderr,
        )
        sys.exit(1)

    summary = {
        "SchemaVersion": "ghidra-review-rank-probes-summary/v1",
        "CandidateOnly": True,
        "GeneratedAt": datetime.now().isoformat(),
        "ProbeRoot": str(probe_root),
        "ReviewKindFilter": kind_filter,
        "ManifestCount": len(review_kind_summaries),
        "SelectedCountTotal": total_selected,
        "ReviewKinds": review_kind_summaries,
    }
    summary_slug = _slugify_review_kind(kind_filter)
    summary_json = probe_root / f"summary-{summary_slug}.json"
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (probe_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md_lines = [
        "# Ghidra review-rank probe summary",
        "",
        "Candidate-only: yes. This summarizes ignored probe manifests and does not feed parser/export behavior.",
        "",
        f"- Probe root: `{probe_root}`",
        f"- Review kind filter: `{kind_filter}`",
        f"- Manifests summarized: `{len(review_kind_summaries)}`",
        f"- Selected rows total: `{total_selected}`",
        "",
        "| Kind | Rows | Ranks | Top roles |",
        "|---|---:|---|---|",
    ]
    for item in review_kind_summaries:
        role_counts_obj = item.get("GhidraRoleCounts", {})
        top_roles = ""
        if isinstance(role_counts_obj, dict):
            top_roles = ", ".join(f"{role}={count}" for role, count in list(role_counts_obj.items())[:5])
        ranks_obj = item.get("Ranks", [])
        ranks_text = ""
        if isinstance(ranks_obj, list):
            ranks_text = ",".join(str(rank) for rank in ranks_obj)
        md_lines.append(
            f"| {item['ReviewKind']} | {item['SelectedCount']} | `{ranks_text}` | `{top_roles}` |"
        )
    summary_md = probe_root / f"summary-{summary_slug}.md"
    summary_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    (probe_root / "summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"GhidraReviewRankProbesSummary JSON: {summary_json}")
    print(f"GhidraReviewRankProbesSummary markdown: {summary_md}")
    print("GhidraReviewRankProbesSummary passed: summary output remains under ignored Exports/.")


def _run_ghidra_workflow_guard_suite(args: argparse.Namespace) -> None:
    """Run Ghidra workflow promotion brakes together."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    print("--- GhidraWorkflowGuardSuite")
    _guard_ghidra_function_site_targets(_ghidra_function_site_targets_path(args))
    _run_nidatastream_parser_field_proof_guard(args)
    report_path = _ensure_ghidra_attribute_candidate_report(out_dir, args.limit)
    ghidra_attribute_candidate_guard(report_path)
    print("GhidraWorkflowGuardSuite passed: Ghidra evidence remains candidate-only/report-only.")


def _print_ghidra_result(result: subprocess.CompletedProcess[str]) -> None:
    """Print bounded Ghidra output and fail closed on script/runtime errors."""
    from scripts.ghidra_runner import _has_ghidra_script_error

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


def _as_string_list(value: Any) -> list[str]:
    """Return a JSON value as a string list."""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _load_ghidra_function_site_targets(path: Path) -> dict[str, Any]:
    """Load the tracked FunctionSiteSurvey target registry."""
    if not path.exists():
        print(f"ERROR: Ghidra FunctionSiteSurvey target registry not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = load_json_report(str(path))
    targets = data.get("Targets")
    if not isinstance(targets, list):
        print(f"ERROR: Ghidra FunctionSiteSurvey target registry has no Targets array: {path}", file=sys.stderr)
        sys.exit(1)
    return data


def _ghidra_function_site_targets_path(args: argparse.Namespace) -> Path:
    """Return the FunctionSiteSurvey target registry path."""
    return Path(args.ghidra_targets_file) if args.ghidra_targets_file else REPO_ROOT / "docs" / "ghidra-function-site-targets.json"


def _ghidra_ignored_report_path_error(value: Any, field_name: str, expected_suffix: str) -> str | None:
    """Return an error when a registry output path can escape ignored Ghidra reports."""
    if not isinstance(value, str) or not value.strip():
        return f"{field_name} must be a non-empty string."

    path_text = value.strip()
    if "\\" in path_text:
        return f"{field_name} must use forward slashes only: {path_text}"
    if path_text.endswith("/"):
        return f"{field_name} must name a file, not a directory: {path_text}"
    if not path_text.startswith("Exports/ghidra-reports/"):
        return f"{field_name} must stay under ignored Exports/ghidra-reports/: {path_text}"
    if not path_text.endswith(expected_suffix):
        return f"{field_name} must end with {expected_suffix}: {path_text}"

    posix_path = PurePosixPath(path_text)
    windows_path = PureWindowsPath(path_text)
    if posix_path.is_absolute() or windows_path.is_absolute() or windows_path.drive:
        return f"{field_name} must be repo-relative, not absolute or drive-qualified: {path_text}"
    if any(part in {"", ".", ".."} for part in posix_path.parts):
        return f"{field_name} must not contain empty, current-dir, or parent-dir segments: {path_text}"
    if len(posix_path.parts) < 3:
        return f"{field_name} must include a file name under Exports/ghidra-reports/: {path_text}"
    return None


def _guard_ghidra_function_site_targets(registry_path: Path, *, quiet: bool = False) -> dict[str, Any]:
    """Fail closed when the FunctionSiteSurvey registry can write unsafe output paths."""
    registry = _load_ghidra_function_site_targets(registry_path)
    errors: list[str] = []

    if registry.get("SchemaVersion") != "ghidra-function-site-targets/v1":
        errors.append("registry SchemaVersion must be ghidra-function-site-targets/v1.")
    if registry.get("CandidateOnly") is not True:
        errors.append("registry CandidateOnly must be true.")

    seen_keys: set[str] = set()
    seen_report_paths: set[str] = set()
    seen_summary_paths: set[str] = set()
    targets = registry.get("Targets", [])
    if not isinstance(targets, list) or not targets:
        errors.append("registry Targets must be a non-empty array.")
        targets = []

    for index, target in enumerate(targets, start=1):
        context = f"target #{index}"
        if not isinstance(target, dict):
            errors.append(f"{context} must be an object.")
            continue

        key = target.get("Key")
        if not isinstance(key, str) or not key:
            errors.append(f"{context} Key must be a non-empty string.")
            key_text = context
        else:
            key_text = key
            if key in seen_keys:
                errors.append(f"duplicate target Key: {key}")
            seen_keys.add(key)

        address = target.get("Address")
        if not isinstance(address, str) or not address.startswith("0x"):
            errors.append(f"{key_text} Address must be a hex string starting with 0x.")

        report_path = target.get("ReportPath")
        report_error = _ghidra_ignored_report_path_error(report_path, f"{key_text} ReportPath", ".json")
        if report_error:
            errors.append(report_error)
        elif isinstance(report_path, str):
            if report_path in seen_report_paths:
                errors.append(f"duplicate ReportPath: {report_path}")
            seen_report_paths.add(report_path)

        summary_path = target.get("SummaryPath")
        summary_error = _ghidra_ignored_report_path_error(summary_path, f"{key_text} SummaryPath", ".md")
        if summary_error:
            errors.append(summary_error)
        elif isinstance(summary_path, str):
            if summary_path in seen_summary_paths:
                errors.append(f"duplicate SummaryPath: {summary_path}")
            seen_summary_paths.add(summary_path)
            if summary_path == report_path:
                errors.append(f"{key_text} SummaryPath must not equal ReportPath.")

        terms = target.get("SummaryTerms")
        if not isinstance(terms, list) or any(not isinstance(term, str) or not term for term in terms):
            errors.append(f"{key_text} SummaryTerms must be an array of non-empty strings.")

        description = target.get("Description")
        if not isinstance(description, str) or not description:
            errors.append(f"{key_text} Description must be a non-empty string.")

    if errors:
        details = "\n  - ".join(errors)
        raise ValueError(f"GhidraFunctionSiteTargetGuard failed for {registry_path}:\n  - {details}")

    if not quiet:
        print("--- GhidraFunctionSiteTargetGuard")
        print(f"Registry: {registry_path}")
        print(f"Targets: {len(targets)}")
        print("Candidate-only: true")
        print("Output root: Exports/ghidra-reports/")
        print("GhidraFunctionSiteTargetGuard passed: report/summary paths remain ignored, repo-relative, and unique.")
    return registry


def _run_ghidra_function_site_target_guard(args: argparse.Namespace) -> None:
    """Validate FunctionSiteSurvey registry safety."""
    _guard_ghidra_function_site_targets(_ghidra_function_site_targets_path(args))


def _ghidra_function_site_target_list_payload(registry: dict[str, Any]) -> dict[str, Any]:
    """Return a machine-readable FunctionSiteSurvey target list."""
    targets = [target for target in registry.get("Targets", []) if isinstance(target, dict)]
    return {
        "SchemaVersion": "ghidra-function-site-target-list/v1",
        "CandidateOnly": registry.get("CandidateOnly") is True,
        "DefaultProjectName": registry.get("DefaultProjectName", ""),
        "DefaultProcess": registry.get("DefaultProcess", ""),
        "DefaultScript": registry.get("DefaultScript", ""),
        "DefaultNoAnalysis": registry.get("DefaultNoAnalysis", False),
        "DefaultKeepProject": registry.get("DefaultKeepProject", False),
        "DefaultTimeoutSeconds": registry.get("DefaultTimeoutSeconds", 0),
        "TargetCount": len(targets),
        "Targets": [
            {
                "Key": str(target.get("Key", "")),
                "Address": str(target.get("Address", "")),
                "ReportPath": str(target.get("ReportPath", "")),
                "SummaryPath": str(target.get("SummaryPath", "")),
                "SummaryTerms": _as_string_list(target.get("SummaryTerms")),
                "Description": str(target.get("Description", "")),
            }
            for target in targets
        ],
    }


def _file_status_payload(path_text: str) -> dict[str, Any]:
    """Return existence/size/mtime metadata for a repo-relative file path."""
    path = REPO_ROOT / path_text
    if not path.exists():
        return {
            "Path": path_text,
            "Exists": False,
            "Bytes": 0,
            "MtimeUtc": "",
        }
    stat = path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC).replace(microsecond=0)
    return {
        "Path": path_text,
        "Exists": True,
        "Bytes": stat.st_size,
        "MtimeUtc": mtime.isoformat().replace("+00:00", "Z"),
    }


def _display_path(path: Path) -> str:
    """Return a repo-relative path when possible, redacting user-profile paths otherwise."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        text = str(resolved)
        home = str(Path.home())
        if text.lower().startswith(home.lower()):
            return "%USERPROFILE%" + text[len(home) :]
        return text


def _artifact_status(key: str, role: str, path: Path) -> dict[str, Any]:
    """Return a small repo-safe status record for a local ignored evidence artifact."""
    exists = path.exists()
    modified_utc: str | None = None
    size_bytes: int | None = None
    if exists:
        stat = path.stat()
        modified_utc = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat().replace("+00:00", "Z")
        size_bytes = stat.st_size
    return {
        "Key": key,
        "Role": role,
        "Path": _display_path(path),
        "Exists": exists,
        "ModifiedUtc": modified_utc,
        "SizeBytes": size_bytes,
    }


def _ghidra_function_site_status_payload(registry_path: Path) -> dict[str, Any]:
    """Return report/summary existence status for all safe FunctionSiteSurvey targets."""
    registry = _guard_ghidra_function_site_targets(registry_path, quiet=True)
    targets = [target for target in registry.get("Targets", []) if isinstance(target, dict)]
    status_targets = []
    for target in targets:
        report_path = str(target.get("ReportPath", ""))
        summary_path = str(target.get("SummaryPath", ""))
        report_status = _file_status_payload(report_path)
        summary_status = _file_status_payload(summary_path)
        status_targets.append(
            {
                "Key": str(target.get("Key", "")),
                "Address": str(target.get("Address", "")),
                "Report": report_status,
                "Summary": summary_status,
                "EvidenceReady": bool(report_status["Exists"]) and bool(summary_status["Exists"]),
            }
        )
    return {
        "SchemaVersion": "ghidra-function-site-status/v1",
        "CandidateOnly": True,
        "Registry": str(registry_path),
        "TargetCount": len(status_targets),
        "EvidenceReadyCount": sum(1 for item in status_targets if item["EvidenceReady"]),
        "Targets": status_targets,
    }


def _run_ghidra_function_site_status(args: argparse.Namespace) -> None:
    """Show report/summary existence status for FunctionSiteSurvey targets."""
    status = _ghidra_function_site_status_payload(_ghidra_function_site_targets_path(args))
    if args.list_json:
        print(json.dumps(status, indent=2))
        return

    print("--- GhidraFunctionSiteStatus")
    print(f"Registry: {status['Registry']}")
    print(f"Targets: {status['TargetCount']}")
    print(f"Evidence-ready targets: {status['EvidenceReadyCount']}")
    print("")
    print(f"{'Key':38} {'Report':8} {'Summary':8} {'Bytes':>10}")
    print(f"{'-' * 38} {'-' * 8} {'-' * 8} {'-' * 10}")
    for target in status["Targets"]:
        report = target["Report"]
        summary = target["Summary"]
        bytes_total = int(report["Bytes"]) + int(summary["Bytes"])
        report_mark = "yes" if report["Exists"] else "no"
        summary_mark = "yes" if summary["Exists"] else "no"
        print(f"{target['Key']:38} {report_mark:8} {summary_mark:8} {bytes_total:10}")


def _nidatastream_gate(
    key: str,
    state: str,
    blocks_promotion: bool,
    required_proof: str,
    evidence: str,
    command: str,
) -> dict[str, Any]:
    """Build one NiDataStream parser-field promotion gate row."""
    return {
        "Key": key,
        "State": state,
        "BlocksPromotion": blocks_promotion,
        "RequiredProof": required_proof,
        "Evidence": evidence,
        "Command": command,
    }


DESCRIPTOR_PROOF_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "nidatastream-loadbinary": {
        "RequiredCalls": ["1411821f0", "141181770", "1411817c0"],
        "RequiredDataRefs": [],
        "RequiredTerms": [],
        "EvidenceRole": "LoadBinary calls all tracked descriptor helper/builders.",
    },
    "nidatastream-descriptor-helper": {
        "RequiredCalls": ["141182280"],
        "RequiredDataRefs": ["143358be0", "143358be4", "143358be8"],
        "RequiredTerms": ["* 0xc"],
        "EvidenceRole": "Descriptor helper reads 12-byte descriptor table fields and calls the format-size helper.",
    },
    "nidatastream-descriptor-builder-1770": {
        "RequiredCalls": [],
        "RequiredDataRefs": ["143358be0", "143358be4", "143358b01"],
        "RequiredTerms": ["* 0xc"],
        "EvidenceRole": "Builder checks descriptor table flag/count-class fields and sentinel/default data.",
    },
    "nidatastream-descriptor-builder-17c0": {
        "RequiredCalls": ["141182280"],
        "RequiredDataRefs": ["143358be0", "143358be8", "143358b04"],
        "RequiredTerms": ["* 0xc"],
        "EvidenceRole": "Builder checks descriptor table flag/format fields and calls the format-size helper.",
    },
}


DESCRIPTOR_CANDIDATE_FIELD_MAP = [
    {
        "Field": "descriptor-table-stride",
        "PromotionStatus": "candidate-only",
        "StaticTableStrideBytes": 12,
        "StreamDescriptorRecordStatus": "not-mapped-to-parser-field",
        "Evidence": "Descriptor helpers index the candidate table with a 0xc-byte stride.",
        "EvidenceTargets": [
            "nidatastream-descriptor-helper",
            "nidatastream-descriptor-builder-1770",
            "nidatastream-descriptor-builder-17c0",
        ],
    },
    {
        "Field": "descriptor-enable-or-special-flag",
        "DataAddress": "143358be0",
        "PromotionStatus": "candidate-only",
        "StaticTableOffsetBytes": 0,
        "StaticTableStrideBytes": 12,
        "StreamDescriptorRecordStatus": "not-mapped-to-parser-field",
        "Evidence": "Helpers branch on DAT_143358be0 before choosing special/default handling.",
        "EvidenceTargets": [
            "nidatastream-descriptor-helper",
            "nidatastream-descriptor-builder-1770",
            "nidatastream-descriptor-builder-17c0",
        ],
    },
    {
        "Field": "descriptor-component-class",
        "DataAddress": "143358be4",
        "PromotionStatus": "candidate-only",
        "StaticTableOffsetBytes": 4,
        "StaticTableStrideBytes": 12,
        "StreamDescriptorRecordStatus": "not-mapped-to-parser-field",
        "Evidence": "Helpers use DAT_143358be4 to derive component/class count candidates.",
        "EvidenceTargets": [
            "nidatastream-descriptor-helper",
            "nidatastream-descriptor-builder-1770",
        ],
    },
    {
        "Field": "descriptor-format-size-lookup",
        "DataAddress": "143358be8",
        "PromotionStatus": "candidate-only",
        "StaticTableOffsetBytes": 8,
        "StaticTableStrideBytes": 12,
        "StreamDescriptorRecordStatus": "not-mapped-to-parser-field",
        "Evidence": "Helpers pass DAT_143358be8 values to FUN_141182280 for size/format mapping.",
        "EvidenceTargets": [
            "nidatastream-descriptor-helper",
            "nidatastream-descriptor-builder-17c0",
        ],
    },
]


SAMPLE_BYTE_UNIFORMITY_REQUIREMENTS = [
    {
        "Key": "payload-prefix-bytes",
        "Source": "TopPayloadPrefixBytes",
        "ExpectedValue": 28,
        "Meaning": "Ghidra-aligned payload begins after a 28-byte descriptor/prefix region.",
    },
    {
        "Key": "payload-trailer-bytes",
        "Source": "TopPayloadTrailerBytes",
        "ExpectedValue": 1,
        "Meaning": "Ghidra-aligned declared payload leaves a 1-byte trailing flag.",
    },
    {
        "Key": "trailing-flag",
        "Source": "TopTrailingFlags",
        "ExpectedValue": 1,
        "Meaning": "The copied sample corpus currently exposes a uniform trailing flag value.",
    },
    {
        "Key": "legacy-offset-minus-ghidra-offset",
        "Source": "TopLegacyOffsetMinusGhidraOffset",
        "ExpectedValue": 1,
        "Meaning": "The legacy parser body offset is one byte later than the Ghidra-aligned payload offset.",
    },
    {
        "Key": "pair-count",
        "Source": "TopPairCounts",
        "ExpectedValue": 1,
        "Meaning": "The selected copied sample corpus has one pair record per observed NiDataStream block.",
    },
    {
        "Key": "descriptor-count",
        "Source": "TopDescriptorCounts",
        "ExpectedValue": 1,
        "Meaning": "The selected copied sample corpus has one descriptor record per observed NiDataStream block.",
    },
]


DESCRIPTOR_BYTE_ORDER_REQUIREMENTS = [
    {
        "Key": "second-u32",
        "Source": "TopSecondUInt32",
        "ExpectedValue": 0,
        "OffsetBytes": 4,
        "WidthBytes": 4,
        "Encoding": "uint32-le",
        "Meaning": "The currently observed copied-sample corpus carries a zero second uint32 before pair records.",
    },
    {
        "Key": "pair-count",
        "Source": "TopPairCounts",
        "ExpectedValue": 1,
        "OffsetBytes": 8,
        "WidthBytes": 4,
        "Encoding": "uint32-le",
        "Meaning": "Pair count appears immediately after declared payload bytes and the second uint32.",
    },
    {
        "Key": "pair-record-offset",
        "Source": "TopPairRecordOffsets",
        "ExpectedValue": 12,
        "OffsetBytes": 12,
        "WidthBytes": 8,
        "Encoding": "byte-record",
        "Meaning": "The first pair record starts at byte offset 12 in the NiDataStream block payload.",
    },
    {
        "Key": "descriptor-count-offset",
        "Source": "TopDescriptorCountOffsets",
        "ExpectedValue": 20,
        "OffsetBytes": 20,
        "WidthBytes": 4,
        "Encoding": "uint32-le",
        "Meaning": "Descriptor count follows one 8-byte pair record at byte offset 20.",
    },
    {
        "Key": "descriptor-count",
        "Source": "TopDescriptorCounts",
        "ExpectedValue": 1,
        "OffsetBytes": 20,
        "WidthBytes": 4,
        "Encoding": "uint32-le",
        "Meaning": "The selected copied-sample corpus has one descriptor record per observed NiDataStream block.",
    },
    {
        "Key": "descriptor-record-offset",
        "Source": "TopDescriptorRecordOffsets",
        "ExpectedValue": 24,
        "OffsetBytes": 24,
        "WidthBytes": 4,
        "Encoding": "byte-record",
        "Meaning": "The first descriptor record starts at byte offset 24 in the NiDataStream block payload.",
    },
    {
        "Key": "payload-prefix-bytes",
        "Source": "TopPayloadPrefixBytes",
        "ExpectedValue": 28,
        "OffsetBytes": 28,
        "WidthBytes": 0,
        "Encoding": "payload-start",
        "Meaning": "Declared payload starts at byte offset 28 after descriptor/pair prefix fields.",
    },
]


def _report_path_from_target(target: dict[str, Any]) -> Path:
    """Return the repo-rooted ignored report path for a FunctionSiteSurvey target."""
    return REPO_ROOT / str(target.get("ReportPath", ""))


def _hex_without_prefix(value: str) -> str:
    """Normalize a hex address token to lower-case without 0x."""
    return value.lower().removeprefix("0x")


def _report_call_targets(report: dict[str, Any]) -> set[str]:
    """Return normalized call target addresses from a FunctionSiteSurvey report."""
    calls = report.get("callsFromFunction")
    if not isinstance(calls, list):
        return set()
    targets: set[str] = set()
    for call in calls:
        if not isinstance(call, dict):
            continue
        target = call.get("calleeEntry") or call.get("to")
        if isinstance(target, str) and target:
            targets.add(_hex_without_prefix(target))
    return targets


def _report_data_ref_targets(report: dict[str, Any]) -> set[str]:
    """Return normalized data reference targets from a FunctionSiteSurvey report."""
    refs = report.get("dataRefsFromFunction")
    if not isinstance(refs, list):
        return set()
    targets: set[str] = set()
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        target = ref.get("to")
        if isinstance(target, str) and target:
            targets.add(_hex_without_prefix(target))
    return targets


def _report_decompile_text(report: dict[str, Any]) -> str:
    """Return decompiler text from a FunctionSiteSurvey report."""
    decompile = report.get("decompile")
    if not isinstance(decompile, dict):
        return ""
    text = decompile.get("c")
    return text if isinstance(text, str) else ""


def _report_decompile_completed(report: dict[str, Any]) -> bool:
    """Return whether the report says decompilation completed."""
    decompile = report.get("decompile")
    return isinstance(decompile, dict) and decompile.get("completed") is True


def _descriptor_target_status(target: dict[str, Any], requirements: dict[str, Any]) -> dict[str, Any]:
    """Build descriptor-helper evidence status for one FunctionSiteSurvey target."""
    key = str(target.get("Key", ""))
    report_path_text = str(target.get("ReportPath", ""))
    report_path = _report_path_from_target(target)
    report_exists = bool(report_path_text) and report_path.exists()
    required_calls = _as_string_list(requirements.get("RequiredCalls"))
    required_data_refs = _as_string_list(requirements.get("RequiredDataRefs"))
    required_terms = _as_string_list(requirements.get("RequiredTerms"))
    base = {
        "Key": key,
        "ReportPath": report_path_text,
        "Exists": report_exists,
        "FunctionEntry": "",
        "DecompileCompleted": False,
        "RequiredCalls": required_calls,
        "MissingCalls": required_calls,
        "RequiredDataRefs": required_data_refs,
        "MissingDataRefs": required_data_refs,
        "RequiredTerms": required_terms,
        "MissingTerms": required_terms,
        "EvidenceReady": False,
        "EvidenceRole": str(requirements.get("EvidenceRole", "")),
        "Error": "",
    }
    if not report_exists:
        return base
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        base["Error"] = str(exc)
        return base

    function = report.get("function")
    function_entry = str(function.get("entry", "")) if isinstance(function, dict) else ""
    calls = _report_call_targets(report)
    data_refs = _report_data_ref_targets(report)
    decompile_text = _report_decompile_text(report)
    missing_calls = [address for address in required_calls if _hex_without_prefix(address) not in calls]
    missing_data_refs = [address for address in required_data_refs if _hex_without_prefix(address) not in data_refs]
    missing_terms = [term for term in required_terms if term not in decompile_text]
    decompile_completed = _report_decompile_completed(report)
    evidence_ready = decompile_completed and not missing_calls and not missing_data_refs and not missing_terms
    base.update(
        {
            "FunctionEntry": function_entry,
            "DecompileCompleted": decompile_completed,
            "MissingCalls": missing_calls,
            "MissingDataRefs": missing_data_refs,
            "MissingTerms": missing_terms,
            "EvidenceReady": evidence_ready,
        }
    )
    return base


def _nidatastream_descriptor_proof_status_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Return candidate-only descriptor helper evidence status from local FunctionSiteSurvey reports."""
    registry = _guard_ghidra_function_site_targets(_ghidra_function_site_targets_path(args), quiet=True)
    targets = [target for target in registry.get("Targets", []) if isinstance(target, dict)]
    by_key = {str(target.get("Key", "")): target for target in targets}
    target_statuses = [
        _descriptor_target_status(by_key.get(key, {"Key": key}), requirements)
        for key, requirements in DESCRIPTOR_PROOF_REQUIREMENTS.items()
    ]
    ready_count = sum(1 for target in target_statuses if target["EvidenceReady"])
    return {
        "SchemaVersion": "nidatastream-descriptor-proof-status/v1",
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "RequiredTargetCount": len(target_statuses),
        "EvidenceReadyCount": ready_count,
        "AllRequiredEvidenceReady": ready_count == len(target_statuses),
        "Targets": target_statuses,
        "CandidateFieldMap": DESCRIPTOR_CANDIDATE_FIELD_MAP,
        "NextAction": "Use descriptor status as candidate evidence only; pair it with sample-byte and pairing-impact proof before parser/export promotion.",
    }


def _print_nidatastream_descriptor_proof_status(status: dict[str, Any]) -> None:
    """Print descriptor helper evidence status."""
    print("--- NiDataStreamDescriptorProofStatus")
    print(f"Evidence-ready targets: {status['EvidenceReadyCount']}/{status['RequiredTargetCount']}")
    print(f"Field-order promoted: {str(status['FieldOrderPromoted']).lower()}")
    print("")
    print(f"{'Target':42} {'Ready':7} {'Function':14} Missing")
    print(f"{'-' * 42} {'-' * 7} {'-' * 14} {'-' * 40}")
    for target in status["Targets"]:
        missing = []
        for key in ("MissingCalls", "MissingDataRefs", "MissingTerms"):
            values = target.get(key)
            if isinstance(values, list) and values:
                missing.append(f"{key}={','.join(str(value) for value in values)}")
        print(
            f"{target['Key']:42} "
            f"{'yes' if target['EvidenceReady'] else 'no':7} "
            f"{target['FunctionEntry'] or '-':14} "
            f"{'; '.join(missing) if missing else '-'}"
        )
    print("")
    print(f"Next action: {status['NextAction']}")


def _run_nidatastream_descriptor_proof_status(args: argparse.Namespace) -> None:
    """Show candidate-only NiDataStream descriptor helper evidence status."""
    status = _nidatastream_descriptor_proof_status_payload(args)
    if args.list_json:
        print(json.dumps(status, indent=2))
        return
    _print_nidatastream_descriptor_proof_status(status)


def _repo_or_absolute_path(path_text: str) -> Path:
    """Return a registry/output path as an absolute local Path."""
    path = Path(path_text)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _nidatastream_evidence_status_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Return local ignored evidence artifact existence/timestamp status."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    registry = _guard_ghidra_function_site_targets(_ghidra_function_site_targets_path(args), quiet=True)
    artifacts: list[dict[str, Any]] = [
        _artifact_status(
            "nidatastream-promotion-dashboard-json",
            "promotion-dashboard",
            out_dir / "nidatastream-promotion-dashboard.json",
        ),
        _artifact_status(
            "nidatastream-promotion-dashboard-markdown",
            "promotion-dashboard",
            out_dir / "nidatastream-promotion-dashboard.md",
        ),
        _artifact_status(
            "nidatastream-layout-report-json",
            "sample-byte-layout",
            out_dir / "nidatastream-layout-report.json",
        ),
        _artifact_status(
            "nidatastream-layout-report-markdown",
            "sample-byte-layout",
            out_dir / "nidatastream-layout-report.md",
        ),
        _artifact_status(
            "nidatastream-descriptor-sample-compare-json",
            "descriptor-sample-compare",
            out_dir / "nidatastream-descriptor-sample-compare.json",
        ),
        _artifact_status(
            "nidatastream-descriptor-sample-compare-markdown",
            "descriptor-sample-compare",
            out_dir / "nidatastream-descriptor-sample-compare.md",
        ),
        _artifact_status(
            "ghidra-attribute-candidate-report-json",
            "pairing-impact",
            out_dir / "ghidra-attribute-candidate-report.json",
        ),
        _artifact_status(
            "ghidra-attribute-candidate-report-markdown",
            "pairing-impact",
            out_dir / "ghidra-attribute-candidate-report.md",
        ),
        _artifact_status(
            "ghidra-pairing-review-report-json",
            "pairing-review",
            out_dir / "ghidra-pairing-review-report.json",
        ),
        _artifact_status(
            "ghidra-pairing-review-report-markdown",
            "pairing-review",
            out_dir / "ghidra-pairing-review-report.md",
        ),
    ]
    for target in registry.get("Targets", []):
        if not isinstance(target, dict):
            continue
        key = _slugify_review_kind(str(target.get("Key", "")))
        report_path = str(target.get("ReportPath", ""))
        summary_path = str(target.get("SummaryPath", ""))
        if report_path:
            artifacts.append(
                _artifact_status(
                    f"function-site-{key}-report",
                    "function-site-report",
                    _repo_or_absolute_path(report_path),
                )
            )
        if summary_path:
            artifacts.append(
                _artifact_status(
                    f"function-site-{key}-summary",
                    "function-site-summary",
                    _repo_or_absolute_path(summary_path),
                )
            )

    existing_count = sum(1 for artifact in artifacts if artifact["Exists"])
    return {
        "SchemaVersion": "nidatastream-evidence-status/v1",
        "CandidateOnly": True,
        "GeneratedAtUtc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "ArtifactCount": len(artifacts),
        "ExistingCount": existing_count,
        "MissingCount": len(artifacts) - existing_count,
        "Artifacts": artifacts,
    }


def _print_nidatastream_evidence_status(status: dict[str, Any]) -> None:
    """Print local ignored evidence artifact status."""
    print("--- NiDataStreamEvidenceStatus")
    print(
        "Artifacts: "
        f"{status['ExistingCount']}/{status['ArtifactCount']} present "
        f"({status['MissingCount']} missing)"
    )
    print()
    print(f"{'Key':48} {'Exists':6} {'ModifiedUtc':22} Path")
    print(f"{'-' * 48} {'-' * 6} {'-' * 22} {'-' * 40}")
    for artifact in status["Artifacts"]:
        modified = artifact["ModifiedUtc"] or "-"
        print(f"{artifact['Key'][:48]:48} {str(artifact['Exists']).lower():6} {modified[:22]:22} {artifact['Path']}")
    print("NiDataStreamEvidenceStatus passed: artifact paths are report-only/candidate evidence.")


def _run_nidatastream_evidence_status(args: argparse.Namespace) -> None:
    """Show ignored local NiDataStream/Ghidra evidence artifact timestamps."""
    status = _nidatastream_evidence_status_payload(args)
    if args.list_json:
        print(json.dumps(status, indent=2))
        return
    _print_nidatastream_evidence_status(status)


def _nidatastream_layout_report_status(args: argparse.Namespace) -> dict[str, Any]:
    """Return status for the ignored local NiDataStream layout report, if present."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    report_path = out_dir / "nidatastream-layout-report.json"
    status = {
        "Path": _display_path(report_path),
        "Exists": report_path.exists(),
        "Schema": "",
        "FilesScanned": 0,
        "FilesParsed": 0,
        "NiDataStreamBlocks": 0,
        "GhidraStyleLayoutValidBlocks": 0,
        "LegacyOffsetShiftedBlocks": 0,
        "AllBlocksGhidraStyleValid": False,
        "Error": "",
    }
    if not report_path.exists():
        return status
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        status["Error"] = str(exc)
        return status
    if not isinstance(report, dict):
        status["Error"] = "layout report root must be a JSON object"
        return status

    blocks = _json_int_or_none(report.get("NiDataStreamBlocks")) or 0
    valid_blocks = _json_int_or_none(report.get("GhidraStyleLayoutValidBlocks")) or 0
    status.update(
        {
            "Schema": str(report.get("Schema", "")),
            "FilesScanned": _json_int_or_none(report.get("FilesScanned")) or 0,
            "FilesParsed": _json_int_or_none(report.get("FilesParsed")) or 0,
            "NiDataStreamBlocks": blocks,
            "GhidraStyleLayoutValidBlocks": valid_blocks,
            "LegacyOffsetShiftedBlocks": _json_int_or_none(report.get("LegacyOffsetShiftedBlocks")) or 0,
            "AllBlocksGhidraStyleValid": blocks > 0 and blocks == valid_blocks,
        }
    )
    return status


def _read_nidatastream_layout_report(args: argparse.Namespace) -> tuple[dict[str, Any] | None, str]:
    """Read the ignored local NiDataStream layout report for comparison surfaces."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    report_path = out_dir / "nidatastream-layout-report.json"
    if not report_path.exists():
        return None, ""
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, str(exc)
    if not isinstance(report, dict):
        return None, "layout report root must be a JSON object"
    return report, ""


def _counter_uniformity_check(
    report: dict[str, Any] | None,
    requirement: dict[str, Any],
    expected_block_count: int,
) -> dict[str, Any]:
    """Return one sample-byte top-counter uniformity check."""
    source = str(requirement["Source"])
    rows_value = report.get(source) if report else None
    rows = rows_value if isinstance(rows_value, list) else []
    first_row = rows[0] if rows and isinstance(rows[0], dict) else {}
    observed_value = first_row.get("Value")
    observed_count = _json_int_or_none(first_row.get("Count")) or 0
    observed_integer = _json_int_or_none(observed_value)
    expected_value = int(requirement["ExpectedValue"])
    uniform = expected_block_count > 0 and len(rows) == 1 and observed_count == expected_block_count
    matches_expected = uniform and observed_integer == expected_value
    return {
        "Key": str(requirement["Key"]),
        "Source": source,
        "ExpectedValue": expected_value,
        "ObservedValue": observed_value,
        "ObservedInteger": observed_integer,
        "ObservedCount": observed_count,
        "ExpectedBlockCount": expected_block_count,
        "RowsSeen": len(rows),
        "Uniform": uniform,
        "MatchesExpected": matches_expected,
        "Meaning": str(requirement["Meaning"]),
    }


def _nidatastream_sample_byte_uniformity_summary(
    layout_report: dict[str, Any] | None,
    layout_status: dict[str, Any],
) -> dict[str, Any]:
    """Summarize whether ignored sample-byte counters match the current Ghidra-aligned hypothesis."""
    expected_block_count = int(layout_status.get("NiDataStreamBlocks", 0))
    checks = [
        _counter_uniformity_check(layout_report, requirement, expected_block_count)
        for requirement in SAMPLE_BYTE_UNIFORMITY_REQUIREMENTS
    ]
    passed_count = sum(1 for check in checks if check["MatchesExpected"])
    return {
        "CheckCount": len(checks),
        "PassedCount": passed_count,
        "AllExpectedValuesUniform": expected_block_count > 0 and passed_count == len(checks),
        "Checks": checks,
    }


def _top_counter_rows(report: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    """Return top counter rows from a layout report as dictionaries."""
    rows_value = report.get(key) if report else None
    if not isinstance(rows_value, list):
        return []
    return [row for row in rows_value if isinstance(row, dict)]


def _nidatastream_descriptor_byte_order_proof(
    layout_report: dict[str, Any] | None,
    layout_status: dict[str, Any],
) -> dict[str, Any]:
    """Summarize exact candidate byte offsets for the observed descriptor/pair prefix."""
    expected_block_count = int(layout_status.get("NiDataStreamBlocks", 0))
    checks = []
    for requirement in DESCRIPTOR_BYTE_ORDER_REQUIREMENTS:
        check = _counter_uniformity_check(layout_report, requirement, expected_block_count)
        check.update(
            {
                "OffsetBytes": int(requirement["OffsetBytes"]),
                "WidthBytes": int(requirement["WidthBytes"]),
                "Encoding": str(requirement["Encoding"]),
            }
        )
        checks.append(check)
    passed_count = sum(1 for check in checks if check["MatchesExpected"])
    return {
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "CheckCount": len(checks),
        "PassedCount": passed_count,
        "AllExpectedFieldsUniform": expected_block_count > 0 and passed_count == len(checks),
        "Checks": checks,
        "TopFirstPairRecordBytes": _top_counter_rows(layout_report, "TopFirstPairRecordBytes"),
        "TopFirstDescriptorRecordBytes": _top_counter_rows(layout_report, "TopFirstDescriptorRecordBytes"),
        "Interpretation": (
            "Candidate byte-order proof only: offsets are from copied sample bytes and Ghidra-aligned "
            "descriptor-helper evidence, but descriptor semantics are not parser/export truth."
        ),
    }


def _nidatastream_sample_corpus_status(layout_report: dict[str, Any] | None) -> dict[str, Any]:
    """Return report-local corpus metadata for the copied/extracted sample evidence."""
    warnings = layout_report.get("Warnings") if layout_report else None
    samples = layout_report.get("ShiftedSamples") if layout_report else None
    return {
        "Root": str(layout_report.get("Root", "")) if layout_report else "",
        "MaxFiles": layout_report.get("MaxFiles") if layout_report else None,
        "FilesScanned": _json_int_or_none(layout_report.get("FilesScanned")) or 0 if layout_report else 0,
        "FilesParsed": _json_int_or_none(layout_report.get("FilesParsed")) or 0 if layout_report else 0,
        "FilesWithNiDataStreamBlocks": (
            _json_int_or_none(layout_report.get("FilesWithNiDataStreamBlocks")) or 0 if layout_report else 0
        ),
        "ParseErrorCount": _json_int_or_none(layout_report.get("ParseErrorCount")) or 0 if layout_report else 0,
        "ShiftedSampleCount": len(samples) if isinstance(samples, list) else 0,
        "WarningCount": len(warnings) if isinstance(warnings, list) else 0,
    }


def _nidatastream_descriptor_sample_compare_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Return a candidate-only descriptor/static-proof vs sample-byte comparison report."""
    descriptor_status = _nidatastream_descriptor_proof_status_payload(args)
    layout_status = _nidatastream_layout_report_status(args)
    layout_report, layout_error = _read_nidatastream_layout_report(args)
    if layout_error and not layout_status["Error"]:
        layout_status["Error"] = layout_error
    sample_corpus_status = _nidatastream_sample_corpus_status(layout_report)
    sample_summary = _nidatastream_sample_byte_uniformity_summary(layout_report, layout_status)
    byte_order_proof = _nidatastream_descriptor_byte_order_proof(layout_report, layout_status)
    descriptor_sample_evidence_ready = (
        bool(descriptor_status["AllRequiredEvidenceReady"])
        and bool(layout_status["AllBlocksGhidraStyleValid"])
        and bool(sample_summary["AllExpectedValuesUniform"])
        and bool(byte_order_proof["AllExpectedFieldsUniform"])
    )
    promotion_status = _nidatastream_promotion_status_payload(args)
    blockers: list[str] = []
    if not descriptor_status["AllRequiredEvidenceReady"]:
        blockers.append("descriptor-helper-evidence-incomplete")
    if layout_status["Error"]:
        blockers.append("sample-byte-layout-report-invalid")
    elif not layout_status["AllBlocksGhidraStyleValid"]:
        blockers.append("sample-byte-layout-not-ghidra-style-valid")
    if not sample_summary["AllExpectedValuesUniform"]:
        blockers.append("sample-byte-uniformity-incomplete")
    if not byte_order_proof["AllExpectedFieldsUniform"]:
        blockers.append("descriptor-byte-order-incomplete")
    if not descriptor_status["FieldOrderPromoted"]:
        blockers.append("field-order-promoted-false")
    if not promotion_status["ParserExportPromotionAllowed"]:
        blockers.append("parser-export-promotion-locked")

    return {
        "SchemaVersion": "nidatastream-descriptor-sample-compare/v1",
        "CandidateOnly": True,
        "ParserExportPromotionAllowed": False,
        "FieldOrderPromoted": False,
        "DescriptorAndSampleEvidenceReady": descriptor_sample_evidence_ready,
        "DescriptorStatus": {
            "SchemaVersion": descriptor_status["SchemaVersion"],
            "RequiredTargetCount": descriptor_status["RequiredTargetCount"],
            "EvidenceReadyCount": descriptor_status["EvidenceReadyCount"],
            "AllRequiredEvidenceReady": descriptor_status["AllRequiredEvidenceReady"],
            "FieldOrderPromoted": descriptor_status["FieldOrderPromoted"],
        },
        "LayoutReportStatus": layout_status,
        "SampleCorpusStatus": sample_corpus_status,
        "SampleByteSummary": sample_summary,
        "DescriptorByteOrderProof": byte_order_proof,
        "CandidateFieldMap": descriptor_status["CandidateFieldMap"],
        "PromotionGateBlockers": promotion_status["Blockers"],
        "BlockerCount": len(blockers),
        "Blockers": blockers,
        "Decision": (
            "Descriptor and copied-sample byte evidence may be used as candidate sidecar evidence only; "
            "parser/export behavior remains unchanged."
        ),
        "NextAction": (
            "Use this comparison to focus a narrow parser-field proof patch only after descriptor field order, "
            "sample-byte corpus coverage, pairing impact, and negative fixtures are ready together."
        ),
    }


def _nidatastream_descriptor_sample_compare_markdown(report: dict[str, Any]) -> str:
    """Build Markdown for the descriptor/sample-byte comparison report."""
    descriptor = report["DescriptorStatus"]
    layout = report["LayoutReportStatus"]
    corpus = report["SampleCorpusStatus"]
    sample = report["SampleByteSummary"]
    byte_order = report["DescriptorByteOrderProof"]
    field_map = report["CandidateFieldMap"]
    lines = [
        "# NiDataStream descriptor/sample-byte comparison",
        "",
        f"- Candidate-only: **{str(report['CandidateOnly']).lower()}**",
        f"- Parser/export promotion allowed: **{str(report['ParserExportPromotionAllowed']).lower()}**",
        f"- Field order promoted: **{str(report['FieldOrderPromoted']).lower()}**",
        (
            "- Descriptor + sample evidence ready: "
            f"**{str(report['DescriptorAndSampleEvidenceReady']).lower()}**"
        ),
        f"- Blocking items: **{format_markdown_cell(report['BlockerCount'])}**",
        "",
        "## Evidence snapshot",
        "",
        "| Evidence lane | Status |",
        "|---|---:|",
        (
            "| Descriptor helper targets ready | "
            f"{format_markdown_cell(descriptor['EvidenceReadyCount'])}/"
            f"{format_markdown_cell(descriptor['RequiredTargetCount'])} |"
        ),
        (
            "| Ghidra-style-valid sample blocks | "
            f"{format_markdown_cell(layout['GhidraStyleLayoutValidBlocks'])}/"
            f"{format_markdown_cell(layout['NiDataStreamBlocks'])} |"
        ),
        (
            "| Sample corpus files parsed | "
            f"{format_markdown_cell(corpus['FilesParsed'])}/"
            f"{format_markdown_cell(corpus['FilesScanned'])} |"
        ),
        (
            "| Uniform sample-byte checks | "
            f"{format_markdown_cell(sample['PassedCount'])}/"
            f"{format_markdown_cell(sample['CheckCount'])} |"
        ),
        (
            "| Descriptor byte-order checks | "
            f"{format_markdown_cell(byte_order['PassedCount'])}/"
            f"{format_markdown_cell(byte_order['CheckCount'])} |"
        ),
        "",
        "## Sample-byte uniformity checks",
        "",
        "| Check | Expected | Observed | Count | Uniform | Match |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for check in sample["Checks"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(check["Key"]),
                    format_markdown_cell(check["ExpectedValue"]),
                    format_markdown_cell(check["ObservedValue"]),
                    f"{format_markdown_cell(check['ObservedCount'])}/{format_markdown_cell(check['ExpectedBlockCount'])}",
                    format_markdown_cell(str(check["Uniform"]).lower()),
                    format_markdown_cell(str(check["MatchesExpected"]).lower()),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Descriptor byte-order proof",
            "",
            "| Check | Offset | Width | Encoding | Expected | Observed | Count | Match |",
            "|---|---:|---:|---|---:|---:|---:|---:|",
        ]
    )
    for check in byte_order["Checks"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(check["Key"]),
                    format_markdown_cell(check["OffsetBytes"]),
                    format_markdown_cell(check["WidthBytes"]),
                    format_markdown_cell(check["Encoding"]),
                    format_markdown_cell(check["ExpectedValue"]),
                    format_markdown_cell(check["ObservedValue"]),
                    f"{format_markdown_cell(check['ObservedCount'])}/{format_markdown_cell(check['ExpectedBlockCount'])}",
                    format_markdown_cell(str(check["MatchesExpected"]).lower()),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Candidate descriptor field map",
            "",
            "| Field | Data address | Static table offset | Static table stride | Promotion | Evidence |",
            "|---|---|---:|---:|---|---|",
        ]
    )
    for field in field_map:
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(field.get("Field")),
                    format_markdown_cell(field.get("DataAddress", "-")),
                    format_markdown_cell(field.get("StaticTableOffsetBytes", "-")),
                    format_markdown_cell(field.get("StaticTableStrideBytes", "-")),
                    format_markdown_cell(field.get("PromotionStatus", "-")),
                    format_markdown_cell(field.get("Evidence")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Current decision",
            "",
            report["Decision"],
            "",
            "## Blockers",
            "",
        ]
    )
    for blocker in report["Blockers"]:
        lines.append(f"- {format_markdown_cell(blocker)}")
    lines.extend(["", f"Next action: {report['NextAction']}", ""])
    return "\n".join(lines)


def _write_nidatastream_descriptor_sample_compare(
    report: dict[str, Any],
    args: argparse.Namespace,
) -> tuple[Path, Path]:
    """Write ignored descriptor/sample-byte comparison JSON/Markdown files."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "nidatastream-descriptor-sample-compare.json"
    markdown_path = out_dir / "nidatastream-descriptor-sample-compare.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_path.write_text(_nidatastream_descriptor_sample_compare_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _print_nidatastream_descriptor_sample_compare(report: dict[str, Any]) -> None:
    """Print a concise descriptor/sample-byte comparison summary."""
    descriptor = report["DescriptorStatus"]
    layout = report["LayoutReportStatus"]
    corpus = report["SampleCorpusStatus"]
    sample = report["SampleByteSummary"]
    byte_order = report["DescriptorByteOrderProof"]
    print("--- NiDataStreamDescriptorSampleCompare")
    print(
        "Descriptor helper evidence-ready targets: "
        f"{descriptor['EvidenceReadyCount']}/{descriptor['RequiredTargetCount']}"
    )
    print(
        "Ghidra-style-valid sample blocks: "
        f"{layout['GhidraStyleLayoutValidBlocks']}/{layout['NiDataStreamBlocks']}"
    )
    print(f"Sample corpus files parsed: {corpus['FilesParsed']}/{corpus['FilesScanned']}")
    print(f"Uniform sample-byte checks: {sample['PassedCount']}/{sample['CheckCount']}")
    print(f"Descriptor byte-order checks: {byte_order['PassedCount']}/{byte_order['CheckCount']}")
    print(f"Candidate field-map entries: {len(report['CandidateFieldMap'])}")
    print(f"Descriptor + sample evidence ready: {str(report['DescriptorAndSampleEvidenceReady']).lower()}")
    print(f"Parser/export promotion allowed: {str(report['ParserExportPromotionAllowed']).lower()}")
    print(f"Blocking items: {report['BlockerCount']}")
    print("")
    print(f"{'Check':36} {'Expected':8} {'Observed':8} {'Count':13} {'Match':6}")
    print(f"{'-' * 36} {'-' * 8} {'-' * 8} {'-' * 13} {'-' * 6}")
    for check in sample["Checks"]:
        observed = "-" if check["ObservedValue"] is None else str(check["ObservedValue"])
        print(
            f"{check['Key']:36} "
            f"{check['ExpectedValue']!s:8} "
            f"{observed[:8]:8} "
            f"{check['ObservedCount']}/{check['ExpectedBlockCount']:<11} "
            f"{str(check['MatchesExpected']).lower():6}"
        )
    print("")
    print(f"{'Byte-order check':36} {'Offset':6} {'Expected':8} {'Observed':8} {'Match':6}")
    print(f"{'-' * 36} {'-' * 6} {'-' * 8} {'-' * 8} {'-' * 6}")
    for check in byte_order["Checks"]:
        observed = "-" if check["ObservedValue"] is None else str(check["ObservedValue"])
        print(
            f"{check['Key']:36} "
            f"{check['OffsetBytes']!s:6} "
            f"{check['ExpectedValue']!s:8} "
            f"{observed[:8]:8} "
            f"{str(check['MatchesExpected']).lower():6}"
        )
    print("")
    print(f"Decision: {report['Decision']}")
    print(f"Next action: {report['NextAction']}")


def _run_nidatastream_descriptor_sample_compare(args: argparse.Namespace) -> None:
    """Write or list candidate-only descriptor/sample-byte comparison evidence."""
    report = _nidatastream_descriptor_sample_compare_payload(args)
    if args.list_json:
        print(json.dumps(report, indent=2))
        return
    json_path, markdown_path = _write_nidatastream_descriptor_sample_compare(report, args)
    _print_nidatastream_descriptor_sample_compare(report)
    print(f"NiDataStreamDescriptorSampleCompare JSON: {json_path}")
    print(f"NiDataStreamDescriptorSampleCompare markdown: {markdown_path}")
    print("NiDataStreamDescriptorSampleCompare passed: comparison remains candidate-only/report-only.")


def _ghidra_attribute_candidate_report_status(args: argparse.Namespace) -> dict[str, Any]:
    """Return status for the ignored Ghidra attribute candidate report, if present."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    report_path = out_dir / "ghidra-attribute-candidate-report.json"
    status = {
        "Path": _display_path(report_path),
        "Exists": report_path.exists(),
        "SchemaVersion": "",
        "GhidraOnlyGroups": 0,
        "GhidraOnlyPairingsCovered": 0,
        "GroupedSampleMeshes": 0,
        "CompletePositionNormalUvCandidateGroups": 0,
        "ProbeBackedRanks": 0,
        "RejectedNoiseGroups": 0,
        "GuardBaselinePass": False,
        "Error": "",
    }
    if not report_path.exists():
        return status
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        status["Error"] = str(exc)
        return status
    summary = report.get("Summary") if isinstance(report.get("Summary"), dict) else {}
    complete_groups = _json_int_or_none(summary.get("CompletePositionNormalUvCandidateGroups")) or 0
    status.update(
        {
            "SchemaVersion": str(report.get("SchemaVersion", "")),
            "GhidraOnlyGroups": _json_int_or_none(summary.get("GhidraOnlyGroups")) or 0,
            "GhidraOnlyPairingsCovered": _json_int_or_none(summary.get("GhidraOnlyPairingsCovered")) or 0,
            "GroupedSampleMeshes": _json_int_or_none(summary.get("GroupedSampleMeshes")) or 0,
            "CompletePositionNormalUvCandidateGroups": complete_groups,
            "ProbeBackedRanks": _json_int_or_none(summary.get("ProbeBackedRanks")) or 0,
            "RejectedNoiseGroups": _json_int_or_none(summary.get("RejectedNoiseGroups")) or 0,
            "GuardBaselinePass": complete_groups == 0,
        }
    )
    return status


def _nidatastream_descriptor_field_map_status(descriptor_status: dict[str, Any]) -> dict[str, Any]:
    """Summarize candidate descriptor field-map promotion readiness for dashboard/status output."""
    field_map_value = descriptor_status.get("CandidateFieldMap")
    field_map = [field for field in field_map_value if isinstance(field, dict)] if isinstance(field_map_value, list) else []
    candidate_only_count = sum(1 for field in field_map if field.get("PromotionStatus") == "candidate-only")
    static_offset_count = sum(1 for field in field_map if "StaticTableOffsetBytes" in field)
    stream_mapped_count = sum(
        1
        for field in field_map
        if field.get("StreamDescriptorRecordStatus") not in (None, "", "not-mapped-to-parser-field")
    )
    stride_values = {
        field.get("StaticTableStrideBytes")
        for field in field_map
        if isinstance(field.get("StaticTableStrideBytes"), int)
    }
    return {
        "FieldMapCount": len(field_map),
        "CandidateOnlyEntryCount": candidate_only_count,
        "StaticTableOffsetCount": static_offset_count,
        "StaticTableStrideBytes": next(iter(stride_values)) if len(stride_values) == 1 else None,
        "StreamDescriptorRecordMappedCount": stream_mapped_count,
        "StreamDescriptorRecordMapped": stream_mapped_count > 0,
    }


def _nidatastream_promotion_status_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Return the current post-Stage-18 NiDataStream parser/export promotion gate state."""
    registry_path = _ghidra_function_site_targets_path(args)
    function_status = _ghidra_function_site_status_payload(registry_path)
    target_count = int(function_status.get("TargetCount", 0))
    ready_count = int(function_status.get("EvidenceReadyCount", 0))
    evidence_ready = target_count > 0 and ready_count == target_count
    evidence_state = "pass" if evidence_ready else "blocked"
    evidence_text = (
        f"{ready_count}/{target_count} FunctionSiteSurvey targets have ignored local JSON reports and Markdown summaries."
    )
    descriptor_status = _nidatastream_descriptor_proof_status_payload(args)
    field_map_status = _nidatastream_descriptor_field_map_status(descriptor_status)
    descriptor_ready = bool(descriptor_status["AllRequiredEvidenceReady"])
    descriptor_state = "candidate" if descriptor_ready else "blocked"
    descriptor_evidence = (
        f"{descriptor_status['EvidenceReadyCount']}/{descriptor_status['RequiredTargetCount']} descriptor helper "
        "reports satisfy call/data-ref/decompile-term evidence; "
        f"static field-map entries {field_map_status['CandidateOnlyEntryCount']}/{field_map_status['FieldMapCount']}; "
        "stream descriptor record semantics remain unmapped."
    )
    layout_status = _nidatastream_layout_report_status(args)
    layout_report, layout_error = _read_nidatastream_layout_report(args)
    if layout_error and not layout_status["Error"]:
        layout_status["Error"] = layout_error
    sample_corpus_status = _nidatastream_sample_corpus_status(layout_report)
    sample_summary = _nidatastream_sample_byte_uniformity_summary(layout_report, layout_status)
    byte_order_proof = _nidatastream_descriptor_byte_order_proof(layout_report, layout_status)
    descriptor_sample_ready = (
        descriptor_ready
        and bool(layout_status["AllBlocksGhidraStyleValid"])
        and bool(sample_summary["AllExpectedValuesUniform"])
        and bool(byte_order_proof["AllExpectedFieldsUniform"])
    )
    layout_blocks = int(layout_status["NiDataStreamBlocks"])
    layout_valid_blocks = int(layout_status["GhidraStyleLayoutValidBlocks"])
    if layout_status["Error"]:
        sample_state = "blocked"
        sample_evidence = f"Local NiDataStream layout report could not be parsed: {layout_status['Error']}"
    elif layout_status["Exists"]:
        sample_evidence_ready = (
            bool(layout_status["AllBlocksGhidraStyleValid"])
            and bool(sample_summary["AllExpectedValuesUniform"])
            and bool(byte_order_proof["AllExpectedFieldsUniform"])
        )
        sample_state = "candidate" if sample_evidence_ready else "blocked"
        sample_evidence = (
            f"Local layout report {layout_status['Path']} has {layout_valid_blocks}/{layout_blocks} "
            "Ghidra-style-valid NiDataStream blocks; "
            f"sample checks {sample_summary['PassedCount']}/{sample_summary['CheckCount']}; "
            f"byte-order checks {byte_order_proof['PassedCount']}/{byte_order_proof['CheckCount']}; "
            "still report-only."
        )
    else:
        sample_state = "blocked"
        sample_evidence = "No ignored local nidatastream-layout-report.json exists yet."
    pairing_status = _ghidra_attribute_candidate_report_status(args)
    if pairing_status["Error"]:
        pairing_state = "blocked"
        pairing_evidence = f"Local Ghidra attribute candidate report could not be parsed: {pairing_status['Error']}"
    elif pairing_status["Exists"]:
        pairing_state = "candidate" if pairing_status["GuardBaselinePass"] else "blocked"
        pairing_evidence = (
            f"Local attribute candidate report has {pairing_status['CompletePositionNormalUvCandidateGroups']} "
            "complete position+normal+UV Ghidra-only groups "
            f"across {pairing_status['GhidraOnlyGroups']} Ghidra-only group(s); still candidate-only."
        )
    else:
        pairing_state = "blocked"
        pairing_evidence = "No ignored local ghidra-attribute-candidate-report.json exists yet."

    gates = [
        _nidatastream_gate(
            "target-registry-safety",
            "pass",
            False,
            "FunctionSiteSurvey targets are candidate-only, unique, and write only repo-relative ignored reports.",
            "Target registry guard validates tracked docs/ghidra-function-site-targets.json.",
            "python scripts/rift_workflow.py ghidra-function-site-target-guard",
        ),
        _nidatastream_gate(
            "ghidra-evidence-availability",
            evidence_state,
            not evidence_ready,
            "Every cited FunctionSiteSurvey target has a local ignored JSON report and Markdown summary.",
            evidence_text,
            "python scripts/rift_workflow.py ghidra-function-site-status --list-json",
        ),
        _nidatastream_gate(
            "descriptor-field-order-proof",
            descriptor_state,
            True,
            "Descriptor helper/builders prove concrete count/order/format/component byte mapping, not only names.",
            descriptor_evidence,
            "python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json",
        ),
        _nidatastream_gate(
            "sample-byte-agreement",
            sample_state,
            True,
            "Copied/extracted NIF samples agree with the proposed Ghidra-aligned prefix/payload/trailer interpretation.",
            sample_evidence,
            "python scripts/rift_workflow.py nidatastream-layout --root Extracted --full",
        ),
        _nidatastream_gate(
            "pairing-impact-proof",
            pairing_state,
            True,
            "A field interpretation change must not promote noise/sentinel rows and must be reviewed by grouped candidate guards.",
            pairing_evidence,
            "python scripts/rift_workflow.py ghidra-attribute-candidate-guard",
        ),
        _nidatastream_gate(
            "export-isolation",
            "pass",
            False,
            "Ghidra evidence is not consumed by decode/export paths.",
            "nidatastream-parser-field-proof-guard is part of ghidra-workflow-guard-suite and invokes pairing plus NiDataStream parser/export non-consumption guards.",
            "python scripts/rift_workflow.py ghidra-workflow-guard-suite --skip-build",
        ),
        _nidatastream_gate(
            "narrow-parser-patch",
            "blocked",
            True,
            "Any parser-field change is isolated, regression-tested, and reviewed before exporter use.",
            "No NiDataStream parser/export behavior has been changed in the Ghidra proof lane.",
            "future guarded C#/Python tests",
        ),
    ]
    blockers = [str(gate["Key"]) for gate in gates if bool(gate["BlocksPromotion"])]
    return {
        "SchemaVersion": "nidatastream-promotion-status/v1",
        "CandidateOnly": True,
        "HistoricalStage": "Stage 18 complete",
        "CurrentLane": "post-Stage-18 Ghidra/NiDataStream proof-guard hardening",
        "FunctionSiteTargetStatus": {
            "TargetCount": target_count,
            "EvidenceReadyCount": ready_count,
            "EvidenceReady": evidence_ready,
        },
        "DescriptorReportStatus": {
            "SchemaVersion": descriptor_status["SchemaVersion"],
            "RequiredTargetCount": descriptor_status["RequiredTargetCount"],
            "EvidenceReadyCount": descriptor_status["EvidenceReadyCount"],
            "AllRequiredEvidenceReady": descriptor_status["AllRequiredEvidenceReady"],
            "FieldOrderPromoted": descriptor_status["FieldOrderPromoted"],
        },
        "DescriptorFieldMapStatus": field_map_status,
        "LayoutReportStatus": layout_status,
        "DescriptorSampleCompareStatus": {
            "SampleCorpusRoot": sample_corpus_status["Root"],
            "FilesScanned": sample_corpus_status["FilesScanned"],
            "FilesParsed": sample_corpus_status["FilesParsed"],
            "ParseErrorCount": sample_corpus_status["ParseErrorCount"],
            "SampleByteCheckCount": sample_summary["CheckCount"],
            "SampleBytePassedCount": sample_summary["PassedCount"],
            "AllSampleBytesUniform": sample_summary["AllExpectedValuesUniform"],
            "ByteOrderCheckCount": byte_order_proof["CheckCount"],
            "ByteOrderPassedCount": byte_order_proof["PassedCount"],
            "AllByteOrderFieldsUniform": byte_order_proof["AllExpectedFieldsUniform"],
            "DescriptorAndSampleEvidenceReady": descriptor_sample_ready,
        },
        "PairingImpactStatus": pairing_status,
        "ParserExportPromotionAllowed": False,
        "BlockerCount": len(blockers),
        "Blockers": blockers,
        "Gates": gates,
        "NextAction": "Add executable sample-byte and descriptor-field proof before any NiDataStream parser/export promotion.",
    }


def _print_nidatastream_promotion_status(status: dict[str, Any]) -> None:
    """Print a human-readable NiDataStream parser-field promotion status."""
    target_status = status["FunctionSiteTargetStatus"]
    descriptor_status = status["DescriptorReportStatus"]
    field_map_status = status["DescriptorFieldMapStatus"]
    layout_status = status["LayoutReportStatus"]
    compare_status = status["DescriptorSampleCompareStatus"]
    pairing_status = status["PairingImpactStatus"]
    print("--- NiDataStreamPromotionStatus")
    print(f"Historical stage: {status['HistoricalStage']}")
    print(f"Current lane: {status['CurrentLane']}")
    print(
        "FunctionSite evidence-ready targets: "
        f"{target_status['EvidenceReadyCount']}/{target_status['TargetCount']}"
    )
    print(
        "Descriptor helper evidence-ready targets: "
        f"{descriptor_status['EvidenceReadyCount']}/{descriptor_status['RequiredTargetCount']}"
    )
    print(
        "Descriptor field map: "
        f"candidate entries {field_map_status['CandidateOnlyEntryCount']}/{field_map_status['FieldMapCount']}; "
        f"stream record mapped={str(field_map_status['StreamDescriptorRecordMapped']).lower()}"
    )
    layout_mark = "yes" if layout_status["Exists"] else "no"
    print(
        "NiDataStream layout report: "
        f"{layout_mark}; Ghidra-style-valid blocks "
        f"{layout_status['GhidraStyleLayoutValidBlocks']}/{layout_status['NiDataStreamBlocks']}"
    )
    print(
        "Descriptor/sample compare: "
        f"sample checks {compare_status['SampleBytePassedCount']}/{compare_status['SampleByteCheckCount']}; "
        f"byte-order checks {compare_status['ByteOrderPassedCount']}/{compare_status['ByteOrderCheckCount']}; "
        f"ready={str(compare_status['DescriptorAndSampleEvidenceReady']).lower()}"
    )
    pairing_mark = "yes" if pairing_status["Exists"] else "no"
    print(
        "Ghidra attribute candidate report: "
        f"{pairing_mark}; complete P+N+UV groups "
        f"{pairing_status['CompletePositionNormalUvCandidateGroups']}"
    )
    print(f"Parser/export promotion allowed: {str(status['ParserExportPromotionAllowed']).lower()}")
    print(f"Blocking gates: {status['BlockerCount']}")
    print("")
    print(f"{'Gate':34} {'State':10} {'Blocks':7} Evidence")
    print(f"{'-' * 34} {'-' * 10} {'-' * 7} {'-' * 40}")
    for gate in status["Gates"]:
        blocks = "yes" if gate["BlocksPromotion"] else "no"
        print(f"{gate['Key']:34} {gate['State']:10} {blocks:7} {gate['Evidence']}")
    print("")
    print(f"Next action: {status['NextAction']}")


def _run_nidatastream_promotion_status(args: argparse.Namespace) -> None:
    """Show post-Stage-18 NiDataStream parser/export promotion gates."""
    status = _nidatastream_promotion_status_payload(args)
    if args.list_json:
        print(json.dumps(status, indent=2))
        return
    _print_nidatastream_promotion_status(status)


def _nidatastream_promotion_dashboard_markdown(status: dict[str, Any]) -> str:
    """Build a compact Markdown dashboard for current NiDataStream promotion gates."""
    function_status = status["FunctionSiteTargetStatus"]
    descriptor_status = status["DescriptorReportStatus"]
    field_map_status = status["DescriptorFieldMapStatus"]
    layout_status = status["LayoutReportStatus"]
    compare_status = status["DescriptorSampleCompareStatus"]
    pairing_status = status["PairingImpactStatus"]
    lines = [
        "# NiDataStream promotion dashboard",
        "",
        f"- Historical stage: **{format_markdown_cell(status['HistoricalStage'])}**",
        f"- Current lane: **{format_markdown_cell(status['CurrentLane'])}**",
        f"- Candidate-only: **{str(status['CandidateOnly']).lower()}**",
        f"- Parser/export promotion allowed: **{str(status['ParserExportPromotionAllowed']).lower()}**",
        f"- Blocking gates: **{format_markdown_cell(status['BlockerCount'])}**",
        "",
        "## Evidence snapshot",
        "",
        "| Evidence lane | Status |",
        "|---|---:|",
        (
            "| FunctionSite evidence-ready targets | "
            f"{format_markdown_cell(function_status['EvidenceReadyCount'])}/"
            f"{format_markdown_cell(function_status['TargetCount'])} |"
        ),
        (
            "| Descriptor helper evidence-ready targets | "
            f"{format_markdown_cell(descriptor_status['EvidenceReadyCount'])}/"
            f"{format_markdown_cell(descriptor_status['RequiredTargetCount'])} |"
        ),
        (
            "| Descriptor field order promoted | "
            f"{format_markdown_cell(str(descriptor_status['FieldOrderPromoted']).lower())} |"
        ),
        (
            "| Descriptor candidate field-map entries | "
            f"{format_markdown_cell(field_map_status['CandidateOnlyEntryCount'])}/"
            f"{format_markdown_cell(field_map_status['FieldMapCount'])} |"
        ),
        (
            "| Stream descriptor record mapped | "
            f"{format_markdown_cell(str(field_map_status['StreamDescriptorRecordMapped']).lower())} |"
        ),
        (
            "| Layout Ghidra-style-valid blocks | "
            f"{format_markdown_cell(layout_status['GhidraStyleLayoutValidBlocks'])}/"
            f"{format_markdown_cell(layout_status['NiDataStreamBlocks'])} |"
        ),
        (
            "| Sample corpus files parsed | "
            f"{format_markdown_cell(compare_status['FilesParsed'])}/"
            f"{format_markdown_cell(compare_status['FilesScanned'])} |"
        ),
        (
            "| Descriptor/sample byte checks | "
            f"{format_markdown_cell(compare_status['SampleBytePassedCount'])}/"
            f"{format_markdown_cell(compare_status['SampleByteCheckCount'])} |"
        ),
        (
            "| Descriptor byte-order checks | "
            f"{format_markdown_cell(compare_status['ByteOrderPassedCount'])}/"
            f"{format_markdown_cell(compare_status['ByteOrderCheckCount'])} |"
        ),
        (
            "| Descriptor/sample evidence ready | "
            f"{format_markdown_cell(str(compare_status['DescriptorAndSampleEvidenceReady']).lower())} |"
        ),
        (
            "| Complete Ghidra-only P+N+UV groups | "
            f"{format_markdown_cell(pairing_status['CompletePositionNormalUvCandidateGroups'])} |"
        ),
        (
            "| Ghidra-only candidate groups | "
            f"{format_markdown_cell(pairing_status['GhidraOnlyGroups'])} |"
        ),
        "",
        "## Gate table",
        "",
        "| Gate | State | Blocks promotion | Evidence | Command |",
        "|---|---|---:|---|---|",
    ]
    for gate in status["Gates"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(gate.get("Key")),
                    format_markdown_cell(gate.get("State")),
                    format_markdown_cell(str(gate.get("BlocksPromotion")).lower()),
                    format_markdown_cell(gate.get("Evidence")),
                    format_markdown_cell(gate.get("Command")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Current decision",
            "",
            (
                "Parser/export behavior remains unchanged. Ghidra evidence is useful candidate evidence, "
                "but v1 promotion remains locked off until descriptor, sample-byte, pairing-impact, and "
                "narrow parser-patch proof all pass together."
            ),
            "",
            f"Next action: {status['NextAction']}",
            "",
        ]
    )
    return "\n".join(lines)


def _run_nidatastream_promotion_dashboard(args: argparse.Namespace) -> None:
    """Write a compact ignored Markdown/JSON dashboard for NiDataStream promotion gates."""
    status = _nidatastream_promotion_status_payload(args)
    json_path, markdown_path = _write_nidatastream_promotion_dashboard(status, args)
    print(f"NiDataStreamPromotionDashboard JSON: {json_path}")
    print(f"NiDataStreamPromotionDashboard markdown: {markdown_path}")
    print("NiDataStreamPromotionDashboard passed: dashboard remains candidate-only/report-only.")


def _write_nidatastream_promotion_dashboard(
    status: dict[str, Any],
    args: argparse.Namespace,
) -> tuple[Path, Path]:
    """Write ignored NiDataStream promotion dashboard JSON/Markdown files."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "nidatastream-promotion-dashboard.json"
    markdown_path = out_dir / "nidatastream-promotion-dashboard.md"
    json_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    markdown_path.write_text(_nidatastream_promotion_dashboard_markdown(status), encoding="utf-8")
    return json_path, markdown_path


def _run_nidatastream_promotion_preflight(args: argparse.Namespace) -> None:
    """Run the practical pre-parser/export promotion brake sequence."""
    print("--- NiDataStreamPromotionPreflight")
    status = _nidatastream_promotion_status_payload(args)
    _print_nidatastream_promotion_status(status)
    json_path, markdown_path = _write_nidatastream_promotion_dashboard(status, args)
    print(f"\nPreflight dashboard JSON: {json_path}")
    print(f"Preflight dashboard markdown: {markdown_path}")
    compare = _nidatastream_descriptor_sample_compare_payload(args)
    compare_json_path, compare_markdown_path = _write_nidatastream_descriptor_sample_compare(compare, args)
    print(f"Preflight descriptor/sample compare JSON: {compare_json_path}")
    print(f"Preflight descriptor/sample compare markdown: {compare_markdown_path}")
    print(
        "Preflight descriptor/sample compare: "
        f"descriptor+sample-ready={str(compare['DescriptorAndSampleEvidenceReady']).lower()} "
        f"blockers={compare['BlockerCount']}"
    )
    print()
    _print_nidatastream_evidence_status(_nidatastream_evidence_status_payload(args))
    _run_ghidra_workflow_guard_suite(args)
    print("\n--- Final GeneratedOutputGuard")
    generated_output_guard()
    print(
        "NiDataStreamPromotionPreflight passed: dashboard, descriptor/sample compare, "
        "promotion brakes, Ghidra guard suite, and output safety passed."
    )


def _run_nidatastream_parser_field_proof_guard(args: argparse.Namespace) -> None:
    """Fail closed on premature NiDataStream parser/export promotion."""
    print("--- NiDataStreamParserFieldProofGuard")
    status = _nidatastream_promotion_status_payload(args)
    ghidra_pairing_non_export_guard()
    nidatastream_parser_export_non_consumption_guard()
    if status["ParserExportPromotionAllowed"]:
        print(
            "ERROR: NiDataStream parser/export promotion is marked allowed before this guard has a "
            "positive promotion-proof implementation.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(
        "NiDataStreamParserFieldProofGuard passed: parser/export promotion remains blocked "
        f"by {status['BlockerCount']} gate(s)."
    )


def _print_ghidra_function_site_targets(registry: dict[str, Any]) -> None:
    """Print available FunctionSiteSurvey targets."""
    print("Available Ghidra FunctionSiteSurvey targets:")
    for target in registry.get("Targets", []):
        if not isinstance(target, dict):
            continue
        print(f"  {target.get('Key', '-'):32} {target.get('Address', '-'):14} {target.get('Description', '-')}")


def _run_ghidra_function_site_survey(args: argparse.Namespace) -> None:
    """Run or print a serialized Ghidra FunctionSiteSurvey target from the registry."""
    registry_path = _ghidra_function_site_targets_path(args)
    registry = _load_ghidra_function_site_targets(registry_path)
    if args.list_json:
        print(json.dumps(_ghidra_function_site_target_list_payload(registry), indent=2))
        return

    target_key = str(args.ghidra_target or "")
    if not target_key:
        _print_ghidra_function_site_targets(registry)
        print("\nUse --ghidra-target <key> to print commands, or add --ghidra-execute to run one serialized target.")
        return

    targets = [target for target in registry["Targets"] if isinstance(target, dict)]
    target = next((item for item in targets if str(item.get("Key", "")) == target_key), None)
    if target is None:
        print(f"ERROR: unknown Ghidra FunctionSiteSurvey target: {target_key}", file=sys.stderr)
        _print_ghidra_function_site_targets(registry)
        sys.exit(1)

    project_name = (
        args.ghidra_project_name
        if args.ghidra_project_name != "TempProject"
        else str(registry.get("DefaultProjectName", args.ghidra_project_name))
    )
    process_path = args.ghidra_process or str(registry.get("DefaultProcess", "rift_x64.exe"))
    script = args.ghidra_script or str(registry.get("DefaultScript", "scripts/ghidra/FunctionSiteSurvey.java"))
    timeout_seconds = args.ghidra_timeout or int(registry.get("DefaultTimeoutSeconds", 900))
    analyze = not (args.ghidra_no_analysis or bool(registry.get("DefaultNoAnalysis", False)))
    keep_project = args.ghidra_keep_project or bool(registry.get("DefaultKeepProject", False))
    project_dir = _ghidra_project_dir_arg(args)
    address = str(target.get("Address", ""))
    report_path = str(target.get("ReportPath", ""))
    summary_path = str(target.get("SummaryPath", ""))
    terms = _as_string_list(target.get("SummaryTerms"))
    if not address or not report_path:
        print(f"ERROR: target {target_key} must define Address and ReportPath.", file=sys.stderr)
        sys.exit(1)

    run_command = [
        "python",
        "scripts/rift_workflow.py",
        "ghidra-run",
        "--ghidra-project-name",
        project_name,
        "--ghidra-process",
        process_path,
        "--ghidra-timeout",
        str(timeout_seconds),
        "--ghidra-script",
        script,
        "--ghidra-script-arg",
        address,
        "--ghidra-script-arg",
        report_path,
    ]
    if not analyze:
        run_command.append("--ghidra-no-analysis")
    if keep_project:
        run_command.append("--ghidra-keep-project")

    summarize_command = [
        "python",
        "scripts/rift_workflow.py",
        "ghidra-summarize",
        "--ghidra-report",
        report_path,
    ]
    if summary_path:
        summarize_command += ["--ghidra-summary-out", summary_path]
    for term in terms:
        summarize_command += ["--ghidra-summary-term", term]

    print(f"GhidraFunctionSiteSurvey target: {target_key}")
    print(f"Description: {target.get('Description', '-')}")
    print(f"Address: {address}")
    print(f"Report: {report_path}")
    if summary_path:
        print(f"Summary: {summary_path}")
    print("\nRun command:")
    print(" ".join(run_command))
    print("\nSummary command:")
    print(" ".join(summarize_command))

    if not args.ghidra_execute:
        print("\nDry-run only. Add --ghidra-execute to run this serialized target.")
        return

    from scripts.ghidra_report_summary import summarize_file
    from scripts.ghidra_runner import run_ghidra_headless

    report_file = Path(report_path)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    if summary_path:
        Path(summary_path).parent.mkdir(parents=True, exist_ok=True)
    result = run_ghidra_headless(
        project_dir=project_dir,
        project_name=project_name,
        process_path=process_path,
        script=script,
        script_args=[address, report_path],
        analyze=analyze,
        delete_project=not keep_project,
        timeout_seconds=timeout_seconds,
    )
    _print_ghidra_result(result)
    summarize_file(
        report_path,
        output_path=summary_path or None,
        terms=terms,
        max_items=args.ghidra_summary_max_items,
        max_matches=args.ghidra_summary_max_matches,
    )
    if summary_path:
        print(f"Wrote Ghidra summary: {summary_path}")


def _run_command(args: argparse.Namespace) -> None:
    """Main command router."""
    command: str = args.command
    if args.review_rank > 0 and command != "mesh-probe":
        print("ERROR: --review-rank is only supported with mesh-probe.", file=sys.stderr)
        sys.exit(1)

    # --- Pure-Python modes (no C# at all) ---

    if command == "generated-output-guard":
        generated_output_guard()
        return

    if command == "ghidra-pairing-non-export-guard":
        ghidra_pairing_non_export_guard()
        return

    if command == "nidatastream-parser-export-non-consumption-guard":
        nidatastream_parser_export_non_consumption_guard()
        return

    if command == "ghidra-attribute-candidate-report":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        review_path = out_dir / "ghidra-pairing-review-report.json"
        if not review_path.exists():
            inventory_path = out_dir / "nif-mesh-binding-inventory.json"
            if not inventory_path.exists():
                print(
                    "ERROR: ghidra-attribute-candidate-report requires an existing "
                    "ghidra-pairing-review-report.json or nif-mesh-binding-inventory.json.\n"
                    f"  Expected report: {review_path}\n"
                    f"  Expected inventory: {inventory_path}\n"
                    "  Run: python scripts/rift_workflow.py ghidra-pairing-review-report --quick --limit 25",
                    file=sys.stderr,
                )
                sys.exit(1)
            ghidra_pairing_review_report(str(inventory_path), out_dir, take=args.limit)
        ghidra_attribute_candidate_report(review_path, out_dir)
        return

    if command == "ghidra-attribute-candidate-guard":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        try:
            report_path = _ensure_ghidra_attribute_candidate_report(out_dir, args.limit)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        ghidra_attribute_candidate_guard(report_path)
        return

    if command == "ghidra-review-rank-probes":
        _run_ghidra_review_rank_probes(args)
        return

    if command == "ghidra-review-rank-probes-summary":
        _run_ghidra_review_rank_probes_summary(args)
        return

    if command == "ghidra-workflow-guard-suite":
        _run_ghidra_workflow_guard_suite(args)
        return

    if command == "tools-status":
        show_tools_status(load_tools_config())
        return

    if command == "ghidra-dry-run":
        from scripts.ghidra_runner import dry_run_ghidra_headless

        dry_run_ghidra_headless(
            project_dir=_ghidra_project_dir_arg(args),
            project_name=args.ghidra_project_name,
            import_path=args.ghidra_import or None,
            process_path=args.ghidra_process or None,
            script=args.ghidra_script or None,
            script_args=_ghidra_script_args_arg(args),
            script_path=args.ghidra_script_path or None,
            analyze=not args.ghidra_no_analysis,
            keep_project=args.ghidra_keep_project,
            timeout_seconds=args.ghidra_timeout,
        )
        return

    if command == "ghidra-run":
        from scripts.ghidra_runner import run_ghidra_headless

        result = run_ghidra_headless(
            project_dir=_ghidra_project_dir_arg(args),
            project_name=args.ghidra_project_name,
            import_path=args.ghidra_import or None,
            process_path=args.ghidra_process or None,
            script=args.ghidra_script or None,
            script_args=_ghidra_script_args_arg(args),
            script_path=args.ghidra_script_path or None,
            analyze=not args.ghidra_no_analysis,
            delete_project=not args.ghidra_keep_project,
            timeout_seconds=args.ghidra_timeout,
        )
        _print_ghidra_result(result)
        return

    if command == "ghidra-function-site-target-guard":
        _run_ghidra_function_site_target_guard(args)
        return

    if command == "ghidra-function-site-status":
        _run_ghidra_function_site_status(args)
        return

    if command == "ghidra-function-site-survey":
        _run_ghidra_function_site_survey(args)
        return

    if command == "ghidra-summarize":
        if not args.ghidra_report:
            print("ERROR: ghidra-summarize requires --ghidra-report <FunctionSiteSurvey.json>", file=sys.stderr)
            sys.exit(1)

        from scripts.ghidra_report_summary import summarize_file

        markdown = summarize_file(
            args.ghidra_report,
            output_path=args.ghidra_summary_out or None,
            terms=args.ghidra_summary_term,
            max_items=args.ghidra_summary_max_items,
            max_matches=args.ghidra_summary_max_matches,
        )
        if args.ghidra_summary_out:
            print(f"Wrote Ghidra summary: {args.ghidra_summary_out}")
        else:
            print(markdown, end="")
        return

    if command == "nidatastream-promotion-status":
        _run_nidatastream_promotion_status(args)
        return

    if command == "nidatastream-evidence-status":
        _run_nidatastream_evidence_status(args)
        return

    if command == "nidatastream-promotion-dashboard":
        _run_nidatastream_promotion_dashboard(args)
        return

    if command == "nidatastream-promotion-preflight":
        _run_nidatastream_promotion_preflight(args)
        return

    if command == "nidatastream-parser-field-proof-guard":
        _run_nidatastream_parser_field_proof_guard(args)
        return

    if command == "nidatastream-descriptor-proof-status":
        _run_nidatastream_descriptor_proof_status(args)
        return

    if command == "nidatastream-descriptor-sample-compare":
        _run_nidatastream_descriptor_sample_compare(args)
        return

    if command == "nidatastream-layout":
        from scripts.nidatastream_layout_report import build_report, write_report

        scan_root = Path(args.root) if args.root else REPO_ROOT / "Extracted"
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        max_files = None if args.full else args.limit
        report = build_report(scan_root, max_files=max_files, sample_limit=50)
        json_path, markdown_path = write_report(report, out_dir)
        print(
            "NiDataStreamLayout: "
            f"files={report['FilesScanned']} parsed={report['FilesParsed']} "
            f"blocks={report['NiDataStreamBlocks']} "
            f"ghidraStyleValid={report['GhidraStyleLayoutValidBlocks']} "
            f"legacyOffsetShifted={report['LegacyOffsetShiftedBlocks']}"
        )
        print(f"NiDataStreamLayout JSON: {json_path}")
        print(f"NiDataStreamLayout markdown: {markdown_path}")
        print("NiDataStreamLayout passed: report is candidate-only/read-only; decoder behavior was not changed.")
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

    # --- GhidraPairingReviewReport: inventory + Python report ---

    if command == "ghidra-pairing-review-report":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        project = Path(args.project) if args.project else DEFAULT_PROJECT
        root = Path(args.root) if args.root else DEFAULT_ROOT
        solution = Path(args.solution) if args.solution else DEFAULT_SOLUTION

        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "nif-mesh-binding-inventory.json"
        if args.quick:
            if not out_path.exists():
                print(
                    "ERROR: ghidra-pairing-review-report --quick requires an "
                    "existing mesh-binding inventory.\n"
                    f"  Run 'python scripts/rift_workflow.py mesh-bindings --full' first.\n"
                    f"  Expected: {out_path}",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            if not args.skip_build and solution.exists():
                checked_run("dotnet build (solution)", ["build", str(solution), "--nologo"])

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
            checked_run("ghidra-pairing-review-report (inventory)", dotnet_args)

        ghidra_pairing_review_report(str(out_path), out_dir, take=args.limit)
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

        # --- Step 5: Guards (usage-access-correlation, residual-lead, position-source-sibling-lead, ghidra isolation) ---

        print()
        print("  -- Step 5/7: Proof Guards --")

        guard_results: list[dict[str, str | bool]] = []
        guard_tasks = [
            ("usage-access-correlation-guard", lambda: usage_access_correlation_guard(str(inventory_path))),
            ("residual-lead-guard", lambda: residual_lead_guard(str(inventory_path))),
            ("position-source-sibling-lead-guard", lambda: position_source_sibling_lead_guard(str(inventory_path))),
            ("ghidra-pairing-non-export-guard", ghidra_pairing_non_export_guard),
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

    if command == "mesh-probe":
        _apply_mesh_probe_review_rank(args)

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
            vertex_count: int = int(entry_item["v"])
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
        total_bytes = sum(int(r.get("objBytes", 0)) for r in results)
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
  python scripts/rift_workflow.py mesh-probe --review-rank 2 --skip-build
  python scripts/rift_workflow.py ghidra-review-rank-probes --limit 14 --skip-build
  python scripts/rift_workflow.py ghidra-review-rank-probes-summary --review-kind all
  python scripts/rift_workflow.py asset-signatures --smoke-max-total 500
  python scripts/rift_workflow.py semantic-hint-crosstab
  python scripts/rift_workflow.py all --full
  python scripts/rift_workflow.py decode-geometry --id c841eb9a0ed1c95e --mesh-block 6
  python scripts/rift_workflow.py decode-geometry --id c841eb9a0ed1c95e --mesh-block 6 --experimental-position-source --full
  python scripts/rift_workflow.py triage-fallback-candidates --full
  python scripts/rift_workflow.py tools-status
  python scripts/rift_workflow.py ghidra-dry-run
  python scripts/rift_workflow.py ghidra-run --ghidra-process rift_x64.exe --ghidra-no-analysis --ghidra-keep-project
  python scripts/rift_workflow.py ghidra-function-site-target-guard
  python scripts/rift_workflow.py ghidra-function-site-status --list-json
  python scripts/rift_workflow.py ghidra-function-site-survey --ghidra-target nidatastream-loadbinary
  python scripts/rift_workflow.py ghidra-summarize --ghidra-report Exports/ghidra-reports/twad_site_survey.json --ghidra-summary-term TWAD
  python scripts/rift_workflow.py nidatastream-evidence-status --list-json
  python scripts/rift_workflow.py nidatastream-promotion-status --list-json
  python scripts/rift_workflow.py nidatastream-promotion-dashboard
  python scripts/rift_workflow.py nidatastream-promotion-preflight
  python scripts/rift_workflow.py nidatastream-parser-field-proof-guard
  python scripts/rift_workflow.py nidatastream-parser-export-non-consumption-guard
  python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json
  python scripts/rift_workflow.py nidatastream-descriptor-sample-compare
  python scripts/rift_workflow.py ghidra-pairing-non-export-guard
  python scripts/rift_workflow.py ghidra-pairing-review-report --quick
  python scripts/rift_workflow.py ghidra-attribute-candidate-report
  python scripts/rift_workflow.py ghidra-attribute-candidate-guard
  python scripts/rift_workflow.py ghidra-workflow-guard-suite
  python scripts/rift_workflow.py nidatastream-layout --root Extracted --full
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
        "--review-rank",
        type=int,
        default=0,
        help="For mesh-probe, resolve --id/--mesh-block from ghidra-pairing-review-report rank",
    )
    parser.add_argument(
        "--review-kind",
        default=None,
        help=(
            "ReviewKind filter for Ghidra review-rank workflows "
            "(probes default: ghidra-only; summary default: all)"
        ),
    )
    parser.add_argument(
        "--review-report-limit",
        type=int,
        default=100,
        help="Finding limit when rebuilding ghidra-pairing-review-report for review-rank workflows (default: 100)",
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
    parser.add_argument(
        "--list-json",
        action="store_true",
        help="Print machine-readable JSON for supported listing/status commands",
    )
    parser.add_argument(
        "--ghidra-project-dir",
        default="",
        help=f"Ghidra project directory (default: {DEFAULT_OUT / 'ghidra-projects'})",
    )
    parser.add_argument(
        "--ghidra-project-name",
        default="TempProject",
        help="Ghidra project name (default: TempProject)",
    )
    parser.add_argument(
        "--ghidra-import",
        default="",
        help="Binary/DLL to import into Ghidra for ghidra-run/ghidra-dry-run",
    )
    parser.add_argument(
        "--ghidra-process",
        default="",
        help="Existing program name/path in the Ghidra project for ghidra-run/ghidra-dry-run",
    )
    parser.add_argument(
        "--ghidra-script",
        default="",
        help="Ghidra post-script path/name for ghidra-run/ghidra-dry-run",
    )
    parser.add_argument(
        "--ghidra-script-path",
        default="",
        help="Additional Ghidra script search path for ghidra-run/ghidra-dry-run",
    )
    parser.add_argument(
        "--ghidra-script-arg",
        action="append",
        default=[],
        help="Argument passed to the Ghidra post-script; repeat for multiple args",
    )
    parser.add_argument(
        "--ghidra-no-analysis",
        action="store_true",
        help="Pass -noanalysis for Ghidra script-only reruns",
    )
    parser.add_argument(
        "--ghidra-keep-project",
        action="store_true",
        help="Keep the Ghidra project after ghidra-run",
    )
    parser.add_argument(
        "--ghidra-timeout",
        type=int,
        default=900,
        help="Max seconds to wait for Ghidra (default: 900; use 14400 for full first-pass analysis)",
    )
    parser.add_argument(
        "--ghidra-target",
        default="",
        help="Named FunctionSiteSurvey target from docs/ghidra-function-site-targets.json",
    )
    parser.add_argument(
        "--ghidra-targets-file",
        default="",
        help="Optional FunctionSiteSurvey target registry override",
    )
    parser.add_argument(
        "--ghidra-execute",
        action="store_true",
        help="Run a named ghidra-function-site-survey target; without this flag the command prints a dry-run plan",
    )
    parser.add_argument(
        "--ghidra-report",
        default="",
        help="FunctionSiteSurvey JSON report for ghidra-summarize",
    )
    parser.add_argument(
        "--ghidra-summary-out",
        default="",
        help="Optional Markdown output path for ghidra-summarize",
    )
    parser.add_argument(
        "--ghidra-summary-term",
        action="append",
        default=[],
        help="Decompile term to show in ghidra-summarize; repeat for multiple terms",
    )
    parser.add_argument(
        "--ghidra-summary-max-items",
        type=int,
        default=8,
        help="Max rows per ghidra-summarize reference table (default: 8)",
    )
    parser.add_argument(
        "--ghidra-summary-max-matches",
        type=int,
        default=12,
        help="Max decompile matches for ghidra-summarize (default: 12)",
    )

    args = parser.parse_args()

    # Normalize: "--no-smoke" is equivalent to "--full" (for backward compat with old PS flags)
    if args.no_smoke:
        args.full = True

    list_json_commands = {
        "ghidra-function-site-survey",
        "ghidra-function-site-status",
        "nidatastream-evidence-status",
        "nidatastream-promotion-status",
        "nidatastream-descriptor-proof-status",
        "nidatastream-descriptor-sample-compare",
    }
    if args.list_json and args.command not in list_json_commands:
        print(
            "ERROR: --list-json is only supported with ghidra-function-site-survey, "
            "ghidra-function-site-status, nidatastream-evidence-status, "
            "nidatastream-promotion-status, nidatastream-descriptor-proof-status, "
            "and nidatastream-descriptor-sample-compare.",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Safety guard: always run generated_output_guard first ---
    if not args.list_json:
        print("\n--- GeneratedOutputGuard (Python)")
    try:
        if args.list_json:
            with contextlib.redirect_stdout(io.StringIO()):
                generated_output_guard()
        else:
            generated_output_guard()
    except Exception as exc:
        print(f"\nGeneratedOutputGuard FAILED: {exc}", file=sys.stderr)
        sys.exit(1)

    if not args.list_json:
        print(f"\n==> {args.command} (Python)")

    try:
        _run_command(args)
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
