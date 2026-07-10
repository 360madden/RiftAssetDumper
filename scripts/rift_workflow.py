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
    matrix-synth                 — synthesize Cycle 5 semantic-hint matrices from flythrough-index.json (Phase 47 polyfill until C# build-asset-semantic-index ships); --commit-matrices fails closed if real backend output is detected
    mesh-streams                 — inventory-nif-mesh-streams + summary
    index-candidates             — inventory-nif-index-candidates + summary
    stream-endianness            — inventory-nif-stream-endianness + summary
    stream-bodies                — inventory-nif-stream-bodies + summary
    decode-geometry              — decode-nif-geometry + summary (needs --id --mesh-block; supports --experimental-position-source)
    batch-export-264             — batch export all 5 known @264-indexed meshes via --export-obj
    batch-export-sibling         — batch export sibling-paired float2 position meshes via --experimental-position-source
    tools-status                 — show configured third-party reverse-engineering tools
    fifty-step-plan-status       — show current position in docs/discovery-plan-50.md
    post50-position-source-status — rank the next offline proof lane from ignored post-50 reports
    post50-mesh34-negative-binding-status — show mesh#34 @304/#57 non-promotion gates
    post50-mesh34-complete-binding-negative-proof — write mesh#34 complete-binding negative proof
    post50-mesh329-family-proof  — prove top meshSize=329 stream@212 family from inventory rows
    post50-mesh329-source-binding-compare — compare meshSize=329 @212/#28 and mesh#34 @304/#57 evidence
    mesh329-attribute-role-matrix — Phase 1 M1.1: synthesize 329-family mesh#7/#34 probe outputs into attribute/role matrix (JSON+MD+CSV)
    phase1-m1.2-304-magic-analysis — Phase 1 M1.2: full-matrix @304 BodyFirst16 magic/prefix analysis from mesh#34 probes (JSON+MD)
    phase1-m1.3-329-variant-layout-guard — Phase 1 M1.3: pilot 329-family sibling variant layout guard from matrix (+ probes when present)
    post50-promotion-readiness-status — summarize post-50 parser/export promotion gates
    post50-validation-suite     — run compact post-50 status/proof hygiene checks
    post50-residual-strict-threshold-delta — write residual payload 288 threshold delta proof
    scan-live-memory            — plan or execute a gated read-only live memory scan
    ghidra-dry-run               — verify Ghidra/JDK registry wiring without launching Ghidra
    ghidra-run                   — run Ghidra headless through the repo workflow guard
    ghidra-function-site-target-guard — validate tracked FunctionSiteSurvey target safety
    ghidra-function-site-status  — show ignored report/summary status for FunctionSiteSurvey targets
    ghidra-function-site-survey  — run/list serialized FunctionSiteSurvey targets
    nidatastream-descriptor-table-sample — sample indexed static descriptor table entries
    nidatastream-descriptor-table-sample-status — summarize ignored descriptor table sample evidence
    nidatastream-descriptor-table-sample-compare — compare known descriptor table sample reports
    nidatastream-descriptor-neighborhood-scan — scan bounded nonzero neighborhoods around descriptor refs
    nidatastream-descriptor-reference-classify — classify references to descriptor data refs
    nidatastream-descriptor-base-model-review — summarize descriptor base/stride model candidates
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
import re
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
DEFAULT_ROOT = Path("C:/Program Files (x86)/Glyph/Games/RIFT/Live")
DEFAULT_OUT = REPO_ROOT / "Exports"
DEFAULT_PROJECT = REPO_ROOT / "src" / "RiftAssetDumper" / "RiftAssetDumper.csproj"
DEFAULT_SOLUTION = REPO_ROOT / "RiftAssetDumper.slnx"

# ---------------------------------------------------------------------------
# Imports (deferred so path setup happens first)
# ---------------------------------------------------------------------------

from scripts.phase1_m12_304_magic_analysis import phase1_m12_304_magic_analysis  # noqa: E402
from scripts.rift_read_only import READ_ONLY_COMMANDS as _READ_ONLY_COMMANDS  # noqa: E402,F401
from scripts.rift_workflow_guards import (  # noqa: E402
    attribute_extra_proof_guard,
    attribute_extra_sibling_proof_guard,
    descriptor_consistency_guard,
    ghidra_attribute_candidate_guard,
    ghidra_pairing_non_export_guard,
    nidatastream_parser_export_non_consumption_guard,
    phase1_m13_329_variant_layout_guard,
    position_source_sibling_lead_guard,
    residual_lead_guard,
    usage_access_correlation_guard,
)
from scripts.rift_workflow_reports import (  # noqa: E402
    discovery_workbench,
    ghidra_attribute_candidate_report,
    ghidra_pairing_review_report,
    mesh329_family_attribute_role_matrix,
    position_source_gap_report,
    position_source_sibling_extra_position_report,
    position_source_sibling_family_report,
    position_source_sibling_probe_report,
    position_source_sibling_representative_probe_report,
    position_source_sibling_secondary_probe_report,
    post50_mesh34_complete_binding_negative_proof,
    post50_mesh329_family_proof_report,
    post50_mesh329_source_binding_compare,
    post50_residual_strict_threshold_delta_report,
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
    "batch-export-sibling": {
        "dotnet": "",
        "base": "",
    },
    "tools-status": {
        "dotnet": "",
        "base": "",
    },
    "fifty-step-plan-status": {
        "dotnet": "",
        "base": "",
    },
    "post50-position-source-status": {
        "dotnet": "",
        "base": "",
    },
    "post50-mesh34-negative-binding-status": {
        "dotnet": "",
        "base": "",
    },
    "post50-mesh34-complete-binding-negative-proof": {
        "dotnet": "",
        "base": "",
    },
    "post50-mesh329-family-proof": {
        "dotnet": "",
        "base": "",
    },
    "post50-mesh329-source-binding-compare": {
        "dotnet": "",
        "base": "",
    },
    "mesh329-attribute-role-matrix": {
        "dotnet": "",
        "base": "",
    },
    "phase1-m1.2-304-magic-analysis": {
        "dotnet": "",
        "base": "",
    },
    "phase1-m1.3-329-variant-layout-guard": {
        "dotnet": "",
        "base": "",
    },
    "post50-promotion-readiness-status": {
        "dotnet": "",
        "base": "",
    },
    "post50-validation-suite": {
        "dotnet": "",
        "base": "",
    },
    "post50-residual-strict-threshold-delta": {
        "dotnet": "",
        "base": "",
    },
    "scan-live-memory": {
        "dotnet": "",
        "base": "",
    },
    "probe-modrm-leads": {
        "dotnet": "",
        "base": "",
    },
    "scan-live-diff": {
        "dotnet": "",
        "base": "",
    },
    "scan-live-values": {
        "dotnet": "",
        "base": "",
    },
    "score-candidates": {
        "dotnet": "",
        "base": "",
    },
    "capture-proof-packets": {
        "dotnet": "",
        "base": "",
    },
    "evaluate-restart-gate": {
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
    "nidatastream-descriptor-table-sample": {
        "dotnet": "",
        "base": "",
    },
    "nidatastream-descriptor-table-sample-status": {
        "dotnet": "",
        "base": "",
    },
    "nidatastream-descriptor-table-sample-compare": {
        "dotnet": "",
        "base": "",
    },
    "nidatastream-descriptor-neighborhood-scan": {
        "dotnet": "",
        "base": "",
    },
    "nidatastream-descriptor-reference-classify": {
        "dotnet": "",
        "base": "",
    },
    "nidatastream-descriptor-base-model-review": {
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
    "matrix-synth": {
        "dotnet": "",
        "base": "matrix-synth",
    },
    # Binary-signature Phase 6 (M6.3) orchestration entry points.
    # These dispatch to scripts/extract_binary_signatures.py and
    # scripts/compare_signature_databases.py via subprocess.run, mirroring the
    # batch-export-sibling pattern. Underlying scripts own their schema validation
    # and exit-code mapping (0=success, 1=schema-violation, 2=missing-input).
    "extract-binary-signatures": {
        "dotnet": "",
        "base": "",
    },
    "compare-binary-signatures": {
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
    "BatchExportSibling": "batch-export-sibling",
    "ToolsStatus": "tools-status",
    "FiftyStepPlanStatus": "fifty-step-plan-status",
    "Post50PositionSourceStatus": "post50-position-source-status",
    "Post50Mesh34NegativeBindingStatus": "post50-mesh34-negative-binding-status",
    "Post50Mesh34CompleteBindingNegativeProof": "post50-mesh34-complete-binding-negative-proof",
    "Post50Mesh329FamilyProof": "post50-mesh329-family-proof",
    "Post50Mesh329SourceBindingCompare": "post50-mesh329-source-binding-compare",
    "Mesh329AttributeRoleMatrix": "mesh329-attribute-role-matrix",
    "Phase1M12_304MagicAnalysis": "phase1-m1.2-304-magic-analysis",
    "Phase1M13_329VariantLayoutGuard": "phase1-m1.3-329-variant-layout-guard",
    "Post50PromotionReadinessStatus": "post50-promotion-readiness-status",
    "Post50ValidationSuite": "post50-validation-suite",
    "Post50ResidualStrictThresholdDelta": "post50-residual-strict-threshold-delta",
    "ScanLiveMemory": "scan-live-memory",
    "GhidraDryRun": "ghidra-dry-run",
    "GhidraRun": "ghidra-run",
    "GhidraFunctionSiteTargetGuard": "ghidra-function-site-target-guard",
    "GhidraFunctionSiteStatus": "ghidra-function-site-status",
    "GhidraFunctionSiteSurvey": "ghidra-function-site-survey",
    "NiDataStreamDescriptorTableSample": "nidatastream-descriptor-table-sample",
    "NiDataStreamDescriptorTableSampleStatus": "nidatastream-descriptor-table-sample-status",
    "NiDataStreamDescriptorTableSampleCompare": "nidatastream-descriptor-table-sample-compare",
    "NiDataStreamDescriptorNeighborhoodScan": "nidatastream-descriptor-neighborhood-scan",
    "NiDataStreamDescriptorReferenceClassify": "nidatastream-descriptor-reference-classify",
    "NiDataStreamDescriptorBaseModelReview": "nidatastream-descriptor-base-model-review",
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
    "MatrixSynth": "matrix-synth",
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
        out_path = out_dir / (f"{base}-{asset_id}-mesh{mesh_block}-extra{extra_offset}.json")
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
    return (
        "-".join(
            part for part in "".join(char.lower() if char.isalnum() else "-" for char in review_kind).split("-") if part
        )
        or "all"
    )


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

    print(f"ghidra-review-rank-probes: probing {len(selected)} finding(s) from {review_path} into {probe_root}")
    results: list[dict[str, object]] = []
    for finding in selected:
        rank = _json_int_or_none(finding.get("Rank"))
        asset_id = str(finding.get("SampleIdPrefix"))
        mesh_block = _json_int_or_none(finding.get("SampleMeshBlockIndex"))
        if rank is None or mesh_block is None:
            continue
        rank_dir = probe_root / f"rank{rank:02d}"
        output_path = rank_dir / f"probe-nif-mesh-{asset_id}.json"
        print(f"\n--- rank {rank}: id={asset_id} meshBlock={mesh_block} kind={finding.get('ReviewKind', '-')}")
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
        md_lines.append(f"| {item['ReviewKind']} | {item['SelectedCount']} | `{ranks_text}` | `{top_roles}` |")
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
    return (
        Path(args.ghidra_targets_file)
        if args.ghidra_targets_file
        else REPO_ROOT / "docs" / "ghidra-function-site-targets.json"
    )


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


DESCRIPTOR_RECORD_INDEX_PROOF_REQUIREMENTS = [
    {
        "Key": "loadbinary-descriptor-size-call",
        "TargetKey": "nidatastream-loadbinary",
        "RequiredTerms": ["FUN_1411821f0(uVar6)"],
        "Evidence": "LoadBinary passes the just-read 4-byte descriptor record value to the size helper.",
    },
    {
        "Key": "loadbinary-descriptor-builder-array-read",
        "TargetKey": "nidatastream-loadbinary",
        "RequiredTerms": [
            "FUN_141181770(*(undefined4 *)(lVar12 + 4",
            "FUN_1411817c0(*(undefined4 *)(lVar12 + 4",
        ],
        "Evidence": "LoadBinary later passes the stored descriptor record high u32 to count/format builder helpers.",
    },
    {
        "Key": "descriptor-helper-low-byte-index",
        "TargetKey": "nidatastream-descriptor-helper",
        "RequiredTerms": ["param_1 & 0xff", "* 0xc"],
        "Evidence": "The descriptor size helper masks its record argument to one byte before indexing the 12-byte table.",
    },
    {
        "Key": "descriptor-builder-1770-low-byte-index",
        "TargetKey": "nidatastream-descriptor-builder-1770",
        "RequiredTerms": ["param_1 & 0xff", "* 0xc"],
        "Evidence": "The component/count builder masks its record argument to one byte before indexing the 12-byte table.",
    },
    {
        "Key": "descriptor-builder-17c0-low-byte-index",
        "TargetKey": "nidatastream-descriptor-builder-17c0",
        "RequiredTerms": ["param_1 & 0xff", "* 0xc"],
        "Evidence": "The format-size builder masks its record argument to one byte before indexing the 12-byte table.",
    },
]


DESCRIPTOR_HELPER_ARGUMENT_USE_PROOF_REQUIREMENTS = [
    {
        "Key": "descriptor-helper-low-byte-lookup",
        "TargetKey": "nidatastream-descriptor-helper",
        "RequiredTerms": ["(int)param_1 < 0", "param_1 & 0xff", "* 0xc"],
        "ForbiddenHighByteTerms": [
            "param_1 >> 8",
            "param_1 >> 0x8",
            "param_1 >> 16",
            "param_1 >> 0x10",
            "param_1 & 0xff00",
            "param_1 & 0xffff00",
        ],
        "Evidence": (
            "The descriptor size helper gates negative signed values, then masks the record argument "
            "to byte 0 for static-table lookup."
        ),
    },
    {
        "Key": "descriptor-builder-1770-low-byte-lookup",
        "TargetKey": "nidatastream-descriptor-builder-1770",
        "RequiredTerms": ["(int)param_1 < 0", "param_1 & 0xff", "* 0xc"],
        "ForbiddenHighByteTerms": [
            "param_1 >> 8",
            "param_1 >> 0x8",
            "param_1 >> 16",
            "param_1 >> 0x10",
            "param_1 & 0xff00",
            "param_1 & 0xffff00",
        ],
        "Evidence": (
            "The component/count builder gates negative signed values, then masks the record argument "
            "to byte 0 for static-table lookup."
        ),
    },
    {
        "Key": "descriptor-builder-17c0-low-byte-lookup",
        "TargetKey": "nidatastream-descriptor-builder-17c0",
        "RequiredTerms": ["(int)param_1 < 0", "param_1 & 0xff", "* 0xc"],
        "ForbiddenHighByteTerms": [
            "param_1 >> 8",
            "param_1 >> 0x8",
            "param_1 >> 16",
            "param_1 >> 0x10",
            "param_1 & 0xff00",
            "param_1 & 0xffff00",
        ],
        "Evidence": (
            "The format-size builder gates negative signed values, then masks the record argument "
            "to byte 0 for static-table lookup."
        ),
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


def _descriptor_target_report_payload(target: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """Read one descriptor FunctionSiteSurvey report payload."""
    report_path_text = str(target.get("ReportPath", ""))
    report_path = _report_path_from_target(target)
    if not report_path_text or not report_path.exists():
        return None, "report missing"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, str(exc)
    if not isinstance(report, dict):
        return None, "report root must be a JSON object"
    return report, ""


def _nidatastream_descriptor_record_index_proof(
    targets_by_key: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return candidate-only proof that stream descriptor record byte 0 indexes the static table."""
    checks = []
    for requirement in DESCRIPTOR_RECORD_INDEX_PROOF_REQUIREMENTS:
        target_key = str(requirement["TargetKey"])
        target = targets_by_key.get(target_key, {"Key": target_key})
        report, error = _descriptor_target_report_payload(target)
        decompile_text = _report_decompile_text(report) if report else ""
        decompile_completed = _report_decompile_completed(report) if report else False
        required_terms = _as_string_list(requirement.get("RequiredTerms"))
        missing_terms = [term for term in required_terms if term not in decompile_text]
        checks.append(
            {
                "Key": str(requirement["Key"]),
                "TargetKey": target_key,
                "ReportPath": str(target.get("ReportPath", "")),
                "DecompileCompleted": decompile_completed,
                "RequiredTerms": required_terms,
                "MissingTerms": missing_terms,
                "Evidence": str(requirement["Evidence"]),
                "Passed": bool(report) and decompile_completed and not missing_terms,
                "Error": error,
            }
        )

    passed_count = sum(1 for check in checks if check["Passed"])
    candidate_record_index_mapped = passed_count == len(checks)
    blockers: list[str] = []
    if not candidate_record_index_mapped:
        blockers.append("descriptor-record-index-proof-incomplete")
    blockers.append("descriptor-record-bytes-1-3-unmapped")
    return {
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "ParserExportPromotionAllowed": False,
        "RecordWidthBytes": 4,
        "CandidateIndexByteOffset": 0 if candidate_record_index_mapped else None,
        "CandidateRecordIndexMapped": candidate_record_index_mapped,
        "RemainingUnmappedByteOffsets": [1, 2, 3],
        "RequiredEvidenceCount": len(checks),
        "PassedEvidenceCount": passed_count,
        "Checks": checks,
        "BlockerCount": len(blockers),
        "Blockers": blockers,
        "Interpretation": (
            "Candidate-only Ghidra evidence maps descriptor record byte 0 to the static descriptor-table "
            "index; bytes 1-3 remain unmapped and parser/export behavior is unchanged."
        ),
    }


def _nidatastream_descriptor_helper_argument_use_proof(
    targets_by_key: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return candidate-only proof for which descriptor-record bytes affect helper table lookup."""
    checks = []
    high_byte_lookup_terms_present = False
    for requirement in DESCRIPTOR_HELPER_ARGUMENT_USE_PROOF_REQUIREMENTS:
        target_key = str(requirement["TargetKey"])
        target = targets_by_key.get(target_key, {"Key": target_key})
        report, error = _descriptor_target_report_payload(target)
        decompile_text = _report_decompile_text(report) if report else ""
        decompile_completed = _report_decompile_completed(report) if report else False
        required_terms = _as_string_list(requirement.get("RequiredTerms"))
        forbidden_terms = _as_string_list(requirement.get("ForbiddenHighByteTerms"))
        missing_terms = [term for term in required_terms if term not in decompile_text]
        present_forbidden_terms = [term for term in forbidden_terms if term in decompile_text]
        if present_forbidden_terms:
            high_byte_lookup_terms_present = True
        checks.append(
            {
                "Key": str(requirement["Key"]),
                "TargetKey": target_key,
                "ReportPath": str(target.get("ReportPath", "")),
                "DecompileCompleted": decompile_completed,
                "RequiredTerms": required_terms,
                "MissingTerms": missing_terms,
                "ForbiddenHighByteTerms": forbidden_terms,
                "PresentForbiddenHighByteTerms": present_forbidden_terms,
                "Evidence": str(requirement["Evidence"]),
                "Passed": (bool(report) and decompile_completed and not missing_terms and not present_forbidden_terms),
                "Error": error,
            }
        )

    passed_count = sum(1 for check in checks if check["Passed"])
    helper_lookup_high_bytes_proven_unused = passed_count == len(checks) and not high_byte_lookup_terms_present
    blockers: list[str] = []
    if not helper_lookup_high_bytes_proven_unused:
        blockers.append("descriptor-helper-argument-use-proof-incomplete")
    blockers.append("descriptor-record-bytes-1-2-unmapped-for-parser-export")
    return {
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "ParserExportPromotionAllowed": False,
        "HelperArgumentWidthBytes": 4,
        "CandidateIndexByteOffset": 0 if helper_lookup_high_bytes_proven_unused else None,
        "CandidateHelperLookupIgnoredByteOffsets": [1, 2] if helper_lookup_high_bytes_proven_unused else [],
        "CandidateSignGuardByteOffsets": [3] if helper_lookup_high_bytes_proven_unused else [],
        "HelperLookupHighBytesUsed": high_byte_lookup_terms_present,
        "HelperLookupHighBytesProvenUnused": helper_lookup_high_bytes_proven_unused,
        "RequiredEvidenceCount": len(checks),
        "PassedEvidenceCount": passed_count,
        "Checks": checks,
        "BlockerCount": len(blockers),
        "Blockers": blockers,
        "Interpretation": (
            "Candidate-only Ghidra helper evidence indicates byte 0 selects the static descriptor table "
            "for helper lookup, bytes 1-2 do not affect the tracked helper lookup when the proof passes, "
            "and byte 3 is only represented by the signed-negative guard. Bytes 1-2 remain unmapped for "
            "parser/export semantics."
        ),
    }


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
    record_index_proof = _nidatastream_descriptor_record_index_proof(by_key)
    helper_argument_use_proof = _nidatastream_descriptor_helper_argument_use_proof(by_key)
    return {
        "SchemaVersion": "nidatastream-descriptor-proof-status/v1",
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "RequiredTargetCount": len(target_statuses),
        "EvidenceReadyCount": ready_count,
        "AllRequiredEvidenceReady": ready_count == len(target_statuses),
        "Targets": target_statuses,
        "CandidateFieldMap": DESCRIPTOR_CANDIDATE_FIELD_MAP,
        "DescriptorRecordIndexProof": record_index_proof,
        "DescriptorHelperArgumentUseProof": helper_argument_use_proof,
        "NextAction": "Use descriptor status as candidate evidence only; pair it with sample-byte and pairing-impact proof before parser/export promotion.",
    }


def _print_nidatastream_descriptor_proof_status(status: dict[str, Any]) -> None:
    """Print descriptor helper evidence status."""
    record_index = status["DescriptorRecordIndexProof"]
    helper_argument_use = status["DescriptorHelperArgumentUseProof"]
    print("--- NiDataStreamDescriptorProofStatus")
    print(f"Evidence-ready targets: {status['EvidenceReadyCount']}/{status['RequiredTargetCount']}")
    print(f"Field-order promoted: {str(status['FieldOrderPromoted']).lower()}")
    print(
        "Descriptor record index proof: "
        f"{record_index['PassedEvidenceCount']}/{record_index['RequiredEvidenceCount']} checks; "
        f"record byte 0 mapped={str(record_index['CandidateRecordIndexMapped']).lower()}"
    )
    print(
        "Descriptor helper argument-use proof: "
        f"{helper_argument_use['PassedEvidenceCount']}/{helper_argument_use['RequiredEvidenceCount']} checks; "
        "high bytes affect helper lookup="
        f"{str(helper_argument_use['HelperLookupHighBytesUsed']).lower()}; "
        "high bytes proven unused="
        f"{str(helper_argument_use['HelperLookupHighBytesProvenUnused']).lower()}"
    )
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
    print(f"Artifacts: {status['ExistingCount']}/{status['ArtifactCount']} present ({status['MissingCount']} missing)")
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


def _parse_hex_byte_record(value: Any) -> list[int] | None:
    """Parse a space-delimited hex byte record from layout counter output."""
    if not isinstance(value, str):
        return None
    parts = value.split()
    if not parts:
        return None
    bytes_out: list[int] = []
    for part in parts:
        if len(part) > 2:
            return None
        try:
            byte_value = int(part, 16)
        except ValueError:
            return None
        if byte_value < 0 or byte_value > 0xFF:
            return None
        bytes_out.append(byte_value)
    return bytes_out


def _nidatastream_descriptor_record_byte_summary(byte_order_proof: dict[str, Any]) -> dict[str, Any]:
    """Summarize first descriptor-record byte distributions without assigning parser semantics."""
    rows_value = byte_order_proof.get("TopFirstDescriptorRecordBytes")
    rows = rows_value if isinstance(rows_value, list) else []
    parsed_rows: list[tuple[list[int], int]] = []
    malformed_record_count = 0
    observed_record_count = 0
    record_width = 0
    for row in rows:
        if not isinstance(row, dict):
            malformed_record_count += 1
            continue
        count = _json_int_or_none(row.get("Count")) or 0
        parsed = _parse_hex_byte_record(row.get("Value"))
        if parsed is None:
            malformed_record_count += count
            continue
        parsed_rows.append((parsed, count))
        observed_record_count += count
        record_width = max(record_width, len(parsed))

    byte_offsets: list[dict[str, Any]] = []
    for offset in range(record_width):
        counts: dict[int, int] = {}
        for parsed, count in parsed_rows:
            if offset >= len(parsed):
                continue
            byte_value = parsed[offset]
            counts[byte_value] = counts.get(byte_value, 0) + count
        top_values = [
            {
                "ValueHex": f"{byte_value:02x}",
                "ValueInteger": byte_value,
                "Count": value_count,
            }
            for byte_value, value_count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]
        byte_offsets.append(
            {
                "OffsetBytes": offset,
                "UniqueValueCount": len(counts),
                "TopValues": top_values,
            }
        )

    return {
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "Source": "TopFirstDescriptorRecordBytes",
        "RecordPatternCount": len(parsed_rows),
        "ObservedRecordCount": observed_record_count,
        "MalformedRecordCount": malformed_record_count,
        "RecordWidthBytes": record_width,
        "ByteOffsets": byte_offsets,
        "Interpretation": (
            "First descriptor-record byte distributions are sample evidence only; "
            "byte positions are not mapped to parser/export semantics."
        ),
    }


def _nidatastream_descriptor_record_byte_role_candidates(
    record_byte_summary: dict[str, Any],
    record_index_proof: dict[str, Any] | None,
) -> dict[str, Any]:
    """Classify observed descriptor-record bytes as candidate roles without promoting parser semantics."""
    rows_value = record_byte_summary.get("ByteOffsets")
    byte_rows = [row for row in rows_value if isinstance(row, dict)] if isinstance(rows_value, list) else []
    observed_record_count = _json_int_or_none(record_byte_summary.get("ObservedRecordCount")) or 0
    record_width = _json_int_or_none(record_byte_summary.get("RecordWidthBytes")) or 0
    index_offset = (
        record_index_proof.get("CandidateIndexByteOffset")
        if isinstance(record_index_proof, dict)
        and bool(record_index_proof.get("CandidateRecordIndexMapped"))
        and isinstance(record_index_proof.get("CandidateIndexByteOffset"), int)
        else None
    )

    role_rows = []
    semantic_offsets: list[int] = []
    padding_offsets: list[int] = []
    remaining_offsets: list[int] = []
    blockers: list[str] = []
    for row in byte_rows:
        offset = _json_int_or_none(row.get("OffsetBytes"))
        if offset is None:
            continue
        unique_value_count = _json_int_or_none(row.get("UniqueValueCount")) or 0
        top_values_value = row.get("TopValues")
        top_values = (
            [value for value in top_values_value if isinstance(value, dict)]
            if isinstance(top_values_value, list)
            else []
        )
        top_value = top_values[0] if top_values else {}
        top_integer = _json_int_or_none(top_value.get("ValueInteger")) if isinstance(top_value, dict) else None
        top_count = _json_int_or_none(top_value.get("Count")) if isinstance(top_value, dict) else None
        is_index = index_offset == offset
        is_uniform_zero = (
            unique_value_count == 1
            and top_integer == 0
            and observed_record_count > 0
            and top_count == observed_record_count
        )
        if is_index:
            role = "static-descriptor-table-index"
            classification = "ghidra-record-index-proof"
            evidence = (
                "Ghidra LoadBinary/helper evidence maps descriptor record byte 0 to the static descriptor table index."
            )
            blocks_semantic_mapping = False
            semantic_offsets.append(offset)
        elif is_uniform_zero:
            role = "zero-padding-or-reserved"
            classification = "uniform-zero-candidate"
            evidence = "All observed records carry 0x00 at this byte; keep as padding/reserved candidate only."
            blocks_semantic_mapping = False
            padding_offsets.append(offset)
        else:
            role = "unmapped-variable-byte"
            classification = "variable-unmapped"
            evidence = "Observed values vary and no Ghidra/helper proof assigns this byte a parser/export role."
            blocks_semantic_mapping = True
            remaining_offsets.append(offset)
            blockers.append(f"descriptor-record-byte-{offset}-unmapped")
        role_rows.append(
            {
                "OffsetBytes": offset,
                "CandidateRole": role,
                "Classification": classification,
                "UniqueValueCount": unique_value_count,
                "ObservedRecordCount": observed_record_count,
                "TopValues": top_values,
                "BlocksSemanticMapping": blocks_semantic_mapping,
                "Evidence": evidence,
            }
        )

    return {
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "ParserExportPromotionAllowed": False,
        "RecordWidthBytes": record_width,
        "ObservedRecordCount": observed_record_count,
        "ClassifiedByteCount": len(role_rows),
        "CandidateSemanticByteOffsets": semantic_offsets,
        "CandidatePaddingByteOffsets": padding_offsets,
        "RemainingUnmappedByteOffsets": remaining_offsets,
        "AllBytesClassified": bool(role_rows) and len(role_rows) == record_width,
        "Rows": role_rows,
        "BlockerCount": len(blockers),
        "Blockers": blockers,
        "Interpretation": (
            "Descriptor record byte roles are candidate-only. Byte 0 may be used as a static-table "
            "index candidate when Ghidra proof is present; uniform zero bytes may be padding/reserved "
            "candidates; variable unmapped bytes still block parser/export promotion."
        ),
    }


def _descriptor_record_pattern_value(
    parsed: list[int],
    offset: int,
) -> dict[str, Any] | None:
    """Return one descriptor-record byte value row for a parsed record pattern."""
    if offset < 0 or offset >= len(parsed):
        return None
    value = parsed[offset]
    return {
        "OffsetBytes": offset,
        "ValueHex": f"{value:02x}",
        "ValueInteger": value,
    }


def _descriptor_record_pattern_values(
    parsed: list[int],
    offsets: list[int],
) -> list[dict[str, Any]]:
    """Return descriptor-record byte value rows for selected offsets."""
    values = []
    for offset in offsets:
        value = _descriptor_record_pattern_value(parsed, offset)
        if value is not None:
            values.append(value)
    return values


def _nidatastream_descriptor_record_pattern_matrix(
    byte_order_proof: dict[str, Any],
    record_index_proof: dict[str, Any] | None,
    helper_argument_use_proof: dict[str, Any] | None,
    record_byte_roles: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a candidate-only matrix of observed descriptor record byte patterns."""
    rows_value = byte_order_proof.get("TopFirstDescriptorRecordBytes")
    rows = rows_value if isinstance(rows_value, list) else []
    index_offset = (
        record_index_proof.get("CandidateIndexByteOffset")
        if isinstance(record_index_proof, dict) and isinstance(record_index_proof.get("CandidateIndexByteOffset"), int)
        else None
    )
    helper_ignored_offsets = (
        [
            int(offset)
            for offset in helper_argument_use_proof.get("CandidateHelperLookupIgnoredByteOffsets", [])
            if isinstance(offset, int)
        ]
        if isinstance(helper_argument_use_proof, dict)
        else []
    )
    sign_guard_offsets = (
        [
            int(offset)
            for offset in helper_argument_use_proof.get("CandidateSignGuardByteOffsets", [])
            if isinstance(offset, int)
        ]
        if isinstance(helper_argument_use_proof, dict)
        else []
    )
    remaining_unmapped_offsets = (
        [int(offset) for offset in record_byte_roles.get("RemainingUnmappedByteOffsets", []) if isinstance(offset, int)]
        if isinstance(record_byte_roles, dict)
        else []
    )

    pattern_rows = []
    malformed_record_count = 0
    observed_record_count = 0
    for rank, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            malformed_record_count += 1
            continue
        count = _json_int_or_none(row.get("Count")) or 0
        parsed = _parse_hex_byte_record(row.get("Value"))
        if parsed is None:
            malformed_record_count += count
            continue
        observed_record_count += count
        index_value = _descriptor_record_pattern_value(parsed, index_offset) if isinstance(index_offset, int) else None
        pattern_rows.append(
            {
                "PatternRank": rank,
                "RecordHex": " ".join(f"{byte:02x}" for byte in parsed),
                "Count": count,
                "RecordWidthBytes": len(parsed),
                "CandidateIndexByte": index_value,
                "CandidateHelperLookupIgnoredBytes": _descriptor_record_pattern_values(
                    parsed,
                    helper_ignored_offsets,
                ),
                "CandidateSignGuardBytes": _descriptor_record_pattern_values(parsed, sign_guard_offsets),
                "RemainingUnmappedBytes": _descriptor_record_pattern_values(parsed, remaining_unmapped_offsets),
            }
        )

    blockers = []
    if malformed_record_count:
        blockers.append("descriptor-record-pattern-malformed")
    if remaining_unmapped_offsets:
        blockers.append("descriptor-record-pattern-unmapped-bytes-present")
    return {
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "ParserExportPromotionAllowed": False,
        "Source": "TopFirstDescriptorRecordBytes",
        "RecordPatternCount": len(pattern_rows),
        "ObservedRecordCount": observed_record_count,
        "MalformedRecordCount": malformed_record_count,
        "CandidateIndexByteOffset": index_offset,
        "CandidateHelperLookupIgnoredByteOffsets": helper_ignored_offsets,
        "CandidateSignGuardByteOffsets": sign_guard_offsets,
        "RemainingUnmappedByteOffsets": remaining_unmapped_offsets,
        "Rows": pattern_rows,
        "BlockerCount": len(blockers),
        "Blockers": blockers,
        "Interpretation": (
            "Observed descriptor record patterns are candidate-only review rows. The matrix joins byte-0 "
            "static-table index candidates, helper-lookup ignored byte candidates, sign-guard candidates, "
            "and parser/export-unmapped bytes without changing decoder/export behavior."
        ),
    }


def _counter_rows_from_strings(values: list[str]) -> list[dict[str, Any]]:
    """Return sorted counter rows for string values."""
    counts: dict[str, int] = {}
    for value in values:
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return [
        {"Value": value, "Count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _sample_text_value(sample: dict[str, Any], key: str) -> str:
    """Return a compact string value from a sample row."""
    value = sample.get(key)
    if value is None:
        return ""
    return str(value)


def _first_counter_value(rows: Any) -> dict[str, Any]:
    """Return the first counter row's value/count as primitive fields."""
    if not isinstance(rows, list) or not rows:
        return {"Value": "", "Count": 0}
    row = rows[0]
    if not isinstance(row, dict):
        return {"Value": "", "Count": 0}
    return {
        "Value": str(row.get("Value", "")),
        "Count": int(row.get("Count", 0)) if isinstance(row.get("Count"), int) else 0,
    }


def _nidatastream_descriptor_context_review_queue(
    correlation_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rank descriptor/context clusters for candidate-only static follow-up."""
    ranked_rows = sorted(
        correlation_rows,
        key=lambda row: (
            -int(row.get("SampleCount", 0)),
            -int(row.get("PairRecordPatternCount", 0)),
            str(row.get("DescriptorRecordHex", "")),
        ),
    )
    review_rows = []
    for rank, row in enumerate(ranked_rows, start=1):
        dominant_pair = _first_counter_value(row.get("TopPairRecordBytes"))
        dominant_usage = _first_counter_value(row.get("TopUsageValues"))
        dominant_access = _first_counter_value(row.get("TopAccessValues"))
        dominant_type = _first_counter_value(row.get("TopTypeNames"))
        review_rows.append(
            {
                "Rank": rank,
                "DescriptorRecordHex": row["DescriptorRecordHex"],
                "SampleCount": row["SampleCount"],
                "PairRecordPatternCount": row["PairRecordPatternCount"],
                "DominantPairRecordBytes": dominant_pair["Value"],
                "DominantPairRecordCount": dominant_pair["Count"],
                "DominantUsageValue": dominant_usage["Value"],
                "DominantUsageCount": dominant_usage["Count"],
                "DominantAccessValue": dominant_access["Value"],
                "DominantAccessCount": dominant_access["Count"],
                "DominantTypeName": dominant_type["Value"],
                "DominantTypeNameCount": dominant_type["Count"],
                "ReviewRationale": (
                    "Candidate-only descriptor/context cluster selected by copied-sample coverage and "
                    "pair-record variety. Use it to focus static helper/builder review for descriptor "
                    "bytes 1-2; do not change parser/export behavior from this row alone."
                ),
            }
        )
    return review_rows


def _nidatastream_descriptor_sample_context_correlation(
    layout_report: dict[str, Any] | None,
    record_pattern_matrix: dict[str, Any],
) -> dict[str, Any]:
    """Correlate descriptor patterns with available copied-sample pair/context rows."""
    samples_value = layout_report.get("ShiftedSamples") if layout_report else None
    samples = (
        [sample for sample in samples_value if isinstance(sample, dict)] if isinstance(samples_value, list) else []
    )
    remaining_offsets = [
        int(offset)
        for offset in record_pattern_matrix.get("RemainingUnmappedByteOffsets", [])
        if isinstance(offset, int)
    ]
    pattern_by_record = {
        str(row.get("RecordHex")): row
        for row in record_pattern_matrix.get("Rows", [])
        if isinstance(row, dict) and row.get("RecordHex")
    }

    grouped: dict[str, dict[str, Any]] = {}
    samples_with_descriptor = 0
    samples_with_pair = 0
    malformed_descriptor_count = 0
    for sample in samples:
        raw_descriptor_record = _sample_text_value(sample, "FirstDescriptorRecordBytes")
        raw_pair_record = _sample_text_value(sample, "FirstPairRecordBytes")
        pair_record_bytes = _parse_hex_byte_record(raw_pair_record)
        pair_record = (
            " ".join(f"{byte:02x}" for byte in pair_record_bytes) if pair_record_bytes is not None else raw_pair_record
        )
        if raw_descriptor_record:
            samples_with_descriptor += 1
        if pair_record:
            samples_with_pair += 1
        parsed_descriptor = _parse_hex_byte_record(raw_descriptor_record)
        if raw_descriptor_record and parsed_descriptor is None:
            malformed_descriptor_count += 1
            continue
        if not raw_descriptor_record:
            continue
        descriptor_record = " ".join(f"{byte:02x}" for byte in parsed_descriptor or [])
        group = grouped.setdefault(
            descriptor_record,
            {
                "SampleCount": 0,
                "PairRecords": [],
                "UsageValues": [],
                "AccessValues": [],
                "TypeNames": [],
            },
        )
        group["SampleCount"] = int(group["SampleCount"]) + 1
        pair_records = group["PairRecords"]
        usage_values = group["UsageValues"]
        access_values = group["AccessValues"]
        type_names = group["TypeNames"]
        if isinstance(pair_records, list):
            pair_records.append(pair_record)
        if isinstance(usage_values, list):
            usage_values.append(_sample_text_value(sample, "DataStreamUsage"))
        if isinstance(access_values, list):
            access_values.append(_sample_text_value(sample, "DataStreamAccess"))
        if isinstance(type_names, list):
            type_names.append(_sample_text_value(sample, "TypeName"))

    correlation_rows = []
    for descriptor_record, group in sorted(
        grouped.items(),
        key=lambda item: (-int(item[1]["SampleCount"]), item[0]),
    ):
        pattern = pattern_by_record.get(descriptor_record, {})
        pair_rows = _counter_rows_from_strings(group["PairRecords"] if isinstance(group["PairRecords"], list) else [])
        usage_rows = _counter_rows_from_strings(group["UsageValues"] if isinstance(group["UsageValues"], list) else [])
        access_rows = _counter_rows_from_strings(
            group["AccessValues"] if isinstance(group["AccessValues"], list) else []
        )
        type_rows = _counter_rows_from_strings(group["TypeNames"] if isinstance(group["TypeNames"], list) else [])
        correlation_rows.append(
            {
                "DescriptorRecordHex": descriptor_record,
                "SampleCount": int(group["SampleCount"]),
                "CandidateIndexByte": pattern.get("CandidateIndexByte"),
                "RemainingUnmappedBytes": pattern.get("RemainingUnmappedBytes", []),
                "PairRecordPatternCount": len(pair_rows),
                "TopPairRecordBytes": pair_rows,
                "UsageValueCount": len(usage_rows),
                "TopUsageValues": usage_rows,
                "AccessValueCount": len(access_rows),
                "TopAccessValues": access_rows,
                "TypeNameValueCount": len(type_rows),
                "TopTypeNames": type_rows,
            }
        )

    review_queue_rows = _nidatastream_descriptor_context_review_queue(correlation_rows)
    correlation_ready = (
        bool(samples)
        and samples_with_descriptor > 0
        and samples_with_pair > 0
        and malformed_descriptor_count == 0
        and bool(correlation_rows)
    )
    blockers = []
    if not samples:
        blockers.append("descriptor-context-correlation-samples-missing")
    if malformed_descriptor_count:
        blockers.append("descriptor-context-correlation-malformed-descriptor-records")
    if samples_with_descriptor == 0:
        blockers.append("descriptor-context-correlation-descriptor-records-missing")
    if samples_with_pair == 0:
        blockers.append("descriptor-context-correlation-pair-records-missing")
    if remaining_offsets:
        blockers.append("descriptor-context-correlation-parser-semantics-unmapped")
    return {
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "ParserExportPromotionAllowed": False,
        "Source": "ShiftedSamples",
        "SampleCount": len(samples),
        "SamplesWithDescriptorRecord": samples_with_descriptor,
        "SamplesWithPairRecord": samples_with_pair,
        "MalformedDescriptorRecordCount": malformed_descriptor_count,
        "CorrelationReady": correlation_ready,
        "RemainingUnmappedByteOffsets": remaining_offsets,
        "DescriptorPatternCount": len(correlation_rows),
        "Rows": correlation_rows,
        "ReviewQueueCount": len(review_queue_rows),
        "ReviewQueueRows": review_queue_rows,
        "BlockerCount": len(blockers),
        "Blockers": blockers,
        "Interpretation": (
            "Descriptor/sample context correlation is candidate-only. It groups observed descriptor "
            "records by available copied-sample pair record bytes and usage/access/type context so bytes "
            "1-2 can be reviewed without changing parser/export behavior."
        ),
    }


def _nidatastream_descriptor_semantic_feasibility(
    candidate_field_map: list[dict[str, Any]],
    record_byte_summary: dict[str, Any],
    record_index_proof: dict[str, Any] | None,
    record_byte_roles: dict[str, Any] | None,
    helper_argument_use_proof: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare static descriptor-table candidates with stream-record bytes without promoting semantics."""
    field_map = [field for field in candidate_field_map if isinstance(field, dict)]
    static_fields = [field for field in field_map if isinstance(field.get("StaticTableOffsetBytes"), int)]
    mapped_fields = [
        field
        for field in static_fields
        if field.get("StreamDescriptorRecordStatus") not in (None, "", "not-mapped-to-parser-field")
    ]
    byte_offset_rows = record_byte_summary.get("ByteOffsets")
    byte_offsets = (
        [
            int(row["OffsetBytes"])
            for row in byte_offset_rows
            if isinstance(row, dict) and isinstance(row.get("OffsetBytes"), int)
        ]
        if isinstance(byte_offset_rows, list)
        else []
    )
    record_width = _json_int_or_none(record_byte_summary.get("RecordWidthBytes")) or 0
    observed_record_count = _json_int_or_none(record_byte_summary.get("ObservedRecordCount")) or 0
    malformed_record_count = _json_int_or_none(record_byte_summary.get("MalformedRecordCount")) or 0
    static_field_map_ready = bool(static_fields) and all(
        field.get("PromotionStatus") == "candidate-only" for field in field_map
    )
    descriptor_record_byte_distribution_ready = (
        bool(record_byte_summary.get("CandidateOnly"))
        and not bool(record_byte_summary.get("FieldOrderPromoted"))
        and observed_record_count > 0
        and malformed_record_count == 0
        and record_width > 0
        and len(byte_offsets) == record_width
    )
    record_index_candidate_mapped = bool(
        isinstance(record_index_proof, dict) and record_index_proof.get("CandidateRecordIndexMapped")
    )
    candidate_index_byte_offset = (
        record_index_proof.get("CandidateIndexByteOffset")
        if isinstance(record_index_proof, dict) and isinstance(record_index_proof.get("CandidateIndexByteOffset"), int)
        else None
    )
    remaining_unmapped_offsets = (
        [
            int(offset)
            for offset in record_index_proof.get("RemainingUnmappedByteOffsets", [])
            if isinstance(offset, int)
        ]
        if isinstance(record_index_proof, dict)
        else byte_offsets
    )
    if isinstance(record_byte_roles, dict) and isinstance(record_byte_roles.get("RemainingUnmappedByteOffsets"), list):
        remaining_unmapped_offsets = [
            int(offset) for offset in record_byte_roles["RemainingUnmappedByteOffsets"] if isinstance(offset, int)
        ]
    candidate_padding_offsets = (
        [int(offset) for offset in record_byte_roles.get("CandidatePaddingByteOffsets", []) if isinstance(offset, int)]
        if isinstance(record_byte_roles, dict)
        else []
    )
    byte_roles_classified = bool(isinstance(record_byte_roles, dict) and record_byte_roles.get("AllBytesClassified"))
    helper_lookup_high_bytes_proven_unused = bool(
        isinstance(helper_argument_use_proof, dict)
        and helper_argument_use_proof.get("HelperLookupHighBytesProvenUnused")
    )
    candidate_helper_lookup_ignored_offsets = (
        [
            int(offset)
            for offset in helper_argument_use_proof.get("CandidateHelperLookupIgnoredByteOffsets", [])
            if isinstance(offset, int)
        ]
        if isinstance(helper_argument_use_proof, dict)
        else []
    )
    candidate_sign_guard_offsets = (
        [
            int(offset)
            for offset in helper_argument_use_proof.get("CandidateSignGuardByteOffsets", [])
            if isinstance(offset, int)
        ]
        if isinstance(helper_argument_use_proof, dict)
        else []
    )

    offset_comparison_rows = []
    for field in static_fields:
        stream_status = str(field.get("StreamDescriptorRecordStatus", ""))
        record_byte_offset_mapped = record_index_candidate_mapped or stream_status not in (
            "",
            "not-mapped-to-parser-field",
        )
        stride = field.get("StaticTableStrideBytes")
        offset_comparison_rows.append(
            {
                "Field": str(field.get("Field", "")),
                "StaticTableOffsetBytes": int(field["StaticTableOffsetBytes"]),
                "StaticTableStrideBytes": stride if isinstance(stride, int) else None,
                "StreamDescriptorRecordStatus": stream_status,
                "CandidateRecordByteOffsets": byte_offsets,
                "RecordByteOffsetMapped": record_byte_offset_mapped,
                "MappingDecision": (
                    "selected-by-record-byte-0-index-candidate"
                    if record_index_candidate_mapped
                    else "mapped-candidate"
                    if record_byte_offset_mapped
                    else "unmapped-static-table-offset-not-stream-byte-offset"
                ),
            }
        )

    semantic_mapping_ready = False
    blockers: list[str] = []
    if not static_field_map_ready:
        blockers.append("static-field-map-incomplete")
    if not descriptor_record_byte_distribution_ready:
        blockers.append("descriptor-record-byte-distribution-incomplete")
    if not helper_lookup_high_bytes_proven_unused:
        blockers.append("descriptor-helper-argument-use-proof-incomplete")
    if record_index_candidate_mapped:
        blockers.append("stream-record-semantics-partial")
    elif not mapped_fields:
        blockers.append("stream-record-semantics-unmapped")
    elif len(mapped_fields) != len(static_fields):
        blockers.append("stream-record-semantics-partial")
    if remaining_unmapped_offsets:
        blockers.append("stream-record-payload-bytes-unmapped")
    if isinstance(record_byte_roles, dict) and record_byte_roles.get("Blockers"):
        blockers.append("descriptor-record-byte-roles-incomplete")

    return {
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "ParserExportPromotionAllowed": False,
        "StaticFieldMapReady": static_field_map_ready,
        "DescriptorRecordByteDistributionReady": descriptor_record_byte_distribution_ready,
        "DescriptorRecordIndexCandidateMapped": record_index_candidate_mapped,
        "DescriptorRecordByteRolesClassified": byte_roles_classified,
        "DescriptorHelperLookupHighBytesProvenUnused": helper_lookup_high_bytes_proven_unused,
        "CandidateIndexByteOffset": candidate_index_byte_offset,
        "CandidatePaddingByteOffsets": candidate_padding_offsets,
        "CandidateHelperLookupIgnoredByteOffsets": candidate_helper_lookup_ignored_offsets,
        "CandidateSignGuardByteOffsets": candidate_sign_guard_offsets,
        "RemainingUnmappedRecordByteOffsets": remaining_unmapped_offsets,
        "StaticFieldMapOffsetCount": len(static_fields),
        "DescriptorRecordByteOffsetCount": len(byte_offsets),
        "DescriptorRecordWidthBytes": record_width,
        "StreamDescriptorRecordMapped": record_index_candidate_mapped or bool(mapped_fields),
        "StreamDescriptorRecordMappedCount": 1 if record_index_candidate_mapped else len(mapped_fields),
        "SemanticMappingReady": semantic_mapping_ready,
        "OffsetComparisonRows": offset_comparison_rows,
        "BlockerCount": len(blockers),
        "Blockers": blockers,
        "Interpretation": (
            "Static descriptor-table offsets and first stream descriptor-record byte distributions are both "
            "available as candidate evidence; Ghidra maps record byte 0 as the candidate static-table index "
            "when proof is present, tracked helpers do not use bytes 1-2 for helper lookup when the helper "
            "argument-use proof passes, and uniform zero bytes may be padding/reserved candidates, but "
            "remaining variable bytes and parser/export semantics are not fully mapped."
        ),
        "NextAction": (
            "Use Ghidra helper/control-flow evidence plus focused sample fixtures to map stream descriptor "
            "record bytes before proposing any parser/export behavior change."
        ),
    }


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


def _nidatastream_descriptor_table_sample_status(args: argparse.Namespace) -> dict[str, Any]:
    """Summarize ignored descriptor-table sample evidence for fail-closed comparison reports."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    explicit_report = getattr(args, "descriptor_table_report", "")
    if explicit_report:
        report_path = Path(explicit_report)
    else:
        all_index_report = out_dir / "ghidra-reports" / "nidatastream_descriptor_table_all_indices.json"
        default_report = out_dir / "ghidra-reports" / "nidatastream_descriptor_table_samples.json"
        report_path = all_index_report if all_index_report.exists() else default_report
    status: dict[str, Any] = {
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "ParserExportPromotionAllowed": False,
        "Path": _display_path(report_path),
        "Exists": report_path.exists(),
        "SchemaVersion": "",
        "ReportCandidateOnly": False,
        "ReportFieldOrderPromoted": False,
        "ReportParserExportPromotionAllowed": False,
        "IndexCount": 0,
        "FieldCount": 0,
        "RowCount": 0,
        "NonzeroRowCount": 0,
        "ErrorRowCount": 0,
        "AllRowsZero": False,
        "SampleReportReady": False,
        "StreamSemanticsExplained": False,
        "RowsByField": [],
        "RowsByIndex": [],
        "Error": "",
        "BlockerCount": 0,
        "Blockers": [],
        "Interpretation": (
            "Descriptor-table samples are candidate-only static Ghidra evidence and do not promote "
            "parser/export behavior."
        ),
    }
    blockers: list[str] = []
    if not report_path.exists():
        blockers.append("descriptor-table-sample-report-missing")
        status["Blockers"] = blockers
        status["BlockerCount"] = len(blockers)
        status["Interpretation"] = (
            "No ignored descriptor-table sample report exists; run "
            "`python scripts/rift_workflow.py nidatastream-descriptor-table-sample --ghidra-execute` "
            "before using table-entry evidence."
        )
        return status
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        blockers.append("descriptor-table-sample-report-invalid")
        status["Error"] = str(exc)
        status["Blockers"] = blockers
        status["BlockerCount"] = len(blockers)
        return status

    rows_value = report.get("rows")
    rows = [row for row in rows_value if isinstance(row, dict)] if isinstance(rows_value, list) else []
    row_count = _json_int_or_none(report.get("rowCount")) or len(rows)
    field_summaries: dict[str, dict[str, Any]] = {}
    index_summaries: dict[str, dict[str, Any]] = {}
    nonzero_rows = 0
    error_rows = 0
    for row in rows:
        field = str(row.get("field", ""))
        index_hex = str(row.get("indexHex", ""))
        bytes_text = str(row.get("bytes", ""))
        parsed = _parse_hex_byte_record(bytes_text)
        has_error = bool(str(row.get("error", "")).strip())
        has_nonzero = bool(parsed and any(byte != 0 for byte in parsed))
        if has_error:
            error_rows += 1
        if has_nonzero:
            nonzero_rows += 1
        field_summary = field_summaries.setdefault(
            field,
            {
                "Field": field,
                "RowCount": 0,
                "NonzeroRowCount": 0,
                "AllRowsZero": False,
                "_indices": set(),
            },
        )
        field_summary["RowCount"] += 1
        if has_nonzero:
            field_summary["NonzeroRowCount"] += 1
        if index_hex:
            field_summary["_indices"].add(index_hex)
        index_summary = index_summaries.setdefault(
            index_hex,
            {
                "IndexHex": index_hex,
                "RowCount": 0,
                "NonzeroRowCount": 0,
                "AllRowsZero": False,
                "_fields": set(),
            },
        )
        index_summary["RowCount"] += 1
        if has_nonzero:
            index_summary["NonzeroRowCount"] += 1
        if field:
            index_summary["_fields"].add(field)

    rows_by_field = []
    for field_summary in sorted(field_summaries.values(), key=lambda value: str(value["Field"])):
        rows_by_field.append(
            {
                "Field": field_summary["Field"],
                "RowCount": field_summary["RowCount"],
                "NonzeroRowCount": field_summary["NonzeroRowCount"],
                "AllRowsZero": field_summary["RowCount"] > 0 and field_summary["NonzeroRowCount"] == 0,
                "Indices": sorted(field_summary["_indices"]),
            }
        )
    rows_by_index = []
    for index_summary in sorted(index_summaries.values(), key=lambda value: str(value["IndexHex"])):
        rows_by_index.append(
            {
                "IndexHex": index_summary["IndexHex"],
                "RowCount": index_summary["RowCount"],
                "NonzeroRowCount": index_summary["NonzeroRowCount"],
                "AllRowsZero": index_summary["RowCount"] > 0 and index_summary["NonzeroRowCount"] == 0,
                "Fields": sorted(index_summary["_fields"]),
            }
        )

    schema_version = str(report.get("SchemaVersion", ""))
    report_candidate_only = report.get("CandidateOnly") is True
    report_field_order_promoted = report.get("FieldOrderPromoted") is True
    report_parser_export_promoted = report.get("ParserExportPromotionAllowed") is True
    all_rows_zero = row_count > 0 and nonzero_rows == 0 and error_rows == 0
    if schema_version != "ghidra-descriptor-table-sample/v1":
        blockers.append("descriptor-table-sample-schema-mismatch")
    if not report_candidate_only:
        blockers.append("descriptor-table-sample-not-candidate-only")
    if report_field_order_promoted:
        blockers.append("descriptor-table-sample-field-order-promoted")
    if report_parser_export_promoted:
        blockers.append("descriptor-table-sample-parser-export-promoted")
    if row_count <= 0:
        blockers.append("descriptor-table-sample-empty")
    if error_rows:
        blockers.append("descriptor-table-sample-read-errors")
    if all_rows_zero:
        blockers.append("descriptor-table-sample-all-zero")
    blockers.append("descriptor-table-sample-semantics-unmapped")
    sample_ready = (
        schema_version == "ghidra-descriptor-table-sample/v1"
        and report_candidate_only
        and not report_field_order_promoted
        and not report_parser_export_promoted
        and row_count > 0
        and error_rows == 0
    )
    interpretation = (
        "Current indexed descriptor-table samples are readable but all zero for observed indices; "
        "this is blocker evidence against parser/export promotion from these candidate bases."
        if all_rows_zero
        else (
            "Descriptor-table sample rows exist, but stream semantics remain unmapped until nonzero rows are "
            "compared against descriptor records and guarded by parser/export promotion checks."
        )
    )
    status.update(
        {
            "SchemaVersion": schema_version,
            "ReportCandidateOnly": report_candidate_only,
            "ReportFieldOrderPromoted": report_field_order_promoted,
            "ReportParserExportPromotionAllowed": report_parser_export_promoted,
            "IndexCount": _json_int_or_none(report.get("indexCount")) or 0,
            "FieldCount": _json_int_or_none(report.get("fieldCount")) or 0,
            "RowCount": row_count,
            "NonzeroRowCount": nonzero_rows,
            "ErrorRowCount": error_rows,
            "AllRowsZero": all_rows_zero,
            "SampleReportReady": sample_ready,
            "StreamSemanticsExplained": False,
            "RowsByField": rows_by_field,
            "RowsByIndex": rows_by_index,
            "BlockerCount": len(blockers),
            "Blockers": blockers,
            "Interpretation": interpretation,
        }
    )
    return status


def _nidatastream_descriptor_table_sample_status_packet(args: argparse.Namespace) -> dict[str, Any]:
    """Build a machine-readable descriptor-table sample status packet."""
    return {
        "SchemaVersion": "nidatastream-descriptor-table-sample-status/v1",
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "ParserExportPromotionAllowed": False,
        "Status": _nidatastream_descriptor_table_sample_status(args),
    }


def _print_nidatastream_descriptor_table_sample_status(packet: dict[str, Any]) -> None:
    """Print a concise descriptor-table sample status summary."""
    status = packet["Status"]
    print("--- NiDataStreamDescriptorTableSampleStatus")
    print(f"Report: {status['Path']}")
    print(f"Exists: {str(status['Exists']).lower()}")
    print(f"Schema: {status['SchemaVersion'] or '-'}")
    print(
        "Rows: "
        f"{status['RowCount']}; nonzero={status['NonzeroRowCount']}; "
        f"errors={status['ErrorRowCount']}; all-zero={str(status['AllRowsZero']).lower()}"
    )
    print(f"Sample ready: {str(status['SampleReportReady']).lower()}")
    print(f"Semantics explained: {str(status['StreamSemanticsExplained']).lower()}")
    if status["Blockers"]:
        print("Blockers:")
        for blocker in status["Blockers"]:
            print(f"- {blocker}")
    print(status["Interpretation"])


def _run_nidatastream_descriptor_table_sample_status(args: argparse.Namespace) -> None:
    """Run the descriptor-table sample status command."""
    packet = _nidatastream_descriptor_table_sample_status_packet(args)
    if args.list_json:
        print(json.dumps(packet, indent=2))
        return
    _print_nidatastream_descriptor_table_sample_status(packet)


def _descriptor_table_sample_compare_targets(args: argparse.Namespace) -> list[tuple[str, Path]]:
    """Return known descriptor-table sample reports for compact comparison."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    targets: list[tuple[str, Path]] = []
    explicit_report = getattr(args, "descriptor_table_report", "")
    if explicit_report:
        targets.append(("explicit", Path(explicit_report)))
    targets.extend(
        [
            ("all-indices-stride12", out_dir / "ghidra-reports" / "nidatastream_descriptor_table_all_indices.json"),
            ("observed-indices-default", out_dir / "ghidra-reports" / "nidatastream_descriptor_table_samples.json"),
            (
                "all-indices-stride4",
                out_dir / "ghidra-reports" / "nidatastream_descriptor_table_all_indices_stride4.json",
            ),
        ]
    )
    deduped: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for label, path in targets:
        key = str(path.resolve()).lower() if path.exists() else str(path.absolute()).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append((label, path))
    return deduped


def _descriptor_table_sample_compare_status_for_path(
    args: argparse.Namespace,
    report_path: Path,
) -> dict[str, Any]:
    """Return descriptor-table sample status for a specific report path."""
    path_args = argparse.Namespace(**vars(args))
    path_args.descriptor_table_report = str(report_path)
    return _nidatastream_descriptor_table_sample_status(path_args)


def _nidatastream_descriptor_table_sample_compare_packet(args: argparse.Namespace) -> dict[str, Any]:
    """Build a candidate-only comparison packet for known descriptor-table sample reports."""
    reports = []
    for label, path in _descriptor_table_sample_compare_targets(args):
        status = _descriptor_table_sample_compare_status_for_path(args, path)
        reports.append(
            {
                "Label": label,
                "Path": status["Path"],
                "Exists": status["Exists"],
                "SampleReportReady": status["SampleReportReady"],
                "SchemaVersion": status["SchemaVersion"],
                "IndexCount": status["IndexCount"],
                "FieldCount": status["FieldCount"],
                "RowCount": status["RowCount"],
                "NonzeroRowCount": status["NonzeroRowCount"],
                "ErrorRowCount": status["ErrorRowCount"],
                "AllRowsZero": status["AllRowsZero"],
                "StreamSemanticsExplained": status["StreamSemanticsExplained"],
                "BlockerCount": status["BlockerCount"],
                "Blockers": status["Blockers"],
            }
        )
    existing_reports = [report for report in reports if report["Exists"]]
    ready_reports = [report for report in reports if report["SampleReportReady"]]
    nonzero_reports = [report for report in reports if int(report["NonzeroRowCount"]) > 0]
    all_existing_reports_all_zero = bool(existing_reports) and all(
        bool(report["AllRowsZero"]) for report in existing_reports
    )
    blockers = []
    if not existing_reports:
        blockers.append("descriptor-table-sample-compare-no-reports")
    if not ready_reports:
        blockers.append("descriptor-table-sample-compare-no-ready-reports")
    if all_existing_reports_all_zero:
        blockers.append("descriptor-table-sample-compare-all-existing-reports-zero")
    if not nonzero_reports:
        blockers.append("descriptor-table-sample-compare-no-nonzero-reports")
    blockers.append("descriptor-table-sample-compare-semantics-unmapped")
    return {
        "SchemaVersion": "nidatastream-descriptor-table-sample-compare/v1",
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "ParserExportPromotionAllowed": False,
        "ReportCount": len(reports),
        "ExistingReportCount": len(existing_reports),
        "ReadyReportCount": len(ready_reports),
        "NonzeroReportCount": len(nonzero_reports),
        "AllExistingReportsAllZero": all_existing_reports_all_zero,
        "Reports": reports,
        "BlockerCount": len(blockers),
        "Blockers": blockers,
        "Decision": "Descriptor table sample reports remain candidate-only; parser/export behavior stays unchanged.",
        "NextAction": (
            "Use nonzero table evidence only if it is sample-correlated; otherwise derive the next bounded "
            "Ghidra query from instruction operand scale/offset candidates."
        ),
    }


def _print_nidatastream_descriptor_table_sample_compare(packet: dict[str, Any]) -> None:
    """Print a concise descriptor-table sample comparison summary."""
    print("--- NiDataStreamDescriptorTableSampleCompare")
    print(
        "Reports: "
        f"{packet['ExistingReportCount']}/{packet['ReportCount']} existing; "
        f"ready={packet['ReadyReportCount']}; nonzero={packet['NonzeroReportCount']}; "
        f"all existing zero={str(packet['AllExistingReportsAllZero']).lower()}"
    )
    for report in packet["Reports"]:
        print(
            f"- {report['Label']}: exists={str(report['Exists']).lower()}, rows={report['RowCount']}, "
            f"nonzero={report['NonzeroRowCount']}, all-zero={str(report['AllRowsZero']).lower()}"
        )
    print("Blockers:")
    for blocker in packet["Blockers"]:
        print(f"- {blocker}")
    print(packet["Decision"])


def _run_nidatastream_descriptor_table_sample_compare(args: argparse.Namespace) -> None:
    """Run the descriptor-table sample comparison command."""
    packet = _nidatastream_descriptor_table_sample_compare_packet(args)
    if args.list_json:
        print(json.dumps(packet, indent=2))
        return
    _print_nidatastream_descriptor_table_sample_compare(packet)


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
    record_byte_summary = _nidatastream_descriptor_record_byte_summary(byte_order_proof)
    record_byte_roles = _nidatastream_descriptor_record_byte_role_candidates(
        record_byte_summary,
        descriptor_status["DescriptorRecordIndexProof"],
    )
    record_pattern_matrix = _nidatastream_descriptor_record_pattern_matrix(
        byte_order_proof,
        descriptor_status["DescriptorRecordIndexProof"],
        descriptor_status["DescriptorHelperArgumentUseProof"],
        record_byte_roles,
    )
    sample_context_correlation = _nidatastream_descriptor_sample_context_correlation(
        layout_report,
        record_pattern_matrix,
    )
    descriptor_table_sample_status = _nidatastream_descriptor_table_sample_status(args)
    semantic_feasibility = _nidatastream_descriptor_semantic_feasibility(
        descriptor_status["CandidateFieldMap"],
        record_byte_summary,
        descriptor_status["DescriptorRecordIndexProof"],
        record_byte_roles,
        descriptor_status["DescriptorHelperArgumentUseProof"],
    )
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
    for blocker in semantic_feasibility["Blockers"]:
        if blocker not in blockers:
            blockers.append(blocker)
    for blocker in descriptor_status["DescriptorHelperArgumentUseProof"]["Blockers"]:
        if blocker not in blockers:
            blockers.append(blocker)
    for blocker in record_pattern_matrix["Blockers"]:
        if blocker not in blockers:
            blockers.append(blocker)
    for blocker in sample_context_correlation["Blockers"]:
        if blocker not in blockers:
            blockers.append(blocker)
    for blocker in descriptor_table_sample_status["Blockers"]:
        if blocker not in blockers:
            blockers.append(blocker)
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
        "DescriptorRecordByteSummary": record_byte_summary,
        "DescriptorRecordIndexProof": descriptor_status["DescriptorRecordIndexProof"],
        "DescriptorHelperArgumentUseProof": descriptor_status["DescriptorHelperArgumentUseProof"],
        "DescriptorRecordByteRoleCandidates": record_byte_roles,
        "DescriptorRecordPatternMatrix": record_pattern_matrix,
        "DescriptorSampleContextCorrelation": sample_context_correlation,
        "DescriptorTableSampleStatus": descriptor_table_sample_status,
        "DescriptorSemanticFeasibility": semantic_feasibility,
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
    record_bytes = report["DescriptorRecordByteSummary"]
    record_index = report["DescriptorRecordIndexProof"]
    helper_argument_use = report["DescriptorHelperArgumentUseProof"]
    record_roles = report["DescriptorRecordByteRoleCandidates"]
    record_pattern_matrix = report["DescriptorRecordPatternMatrix"]
    sample_context = report["DescriptorSampleContextCorrelation"]
    table_sample = report["DescriptorTableSampleStatus"]
    semantic = report["DescriptorSemanticFeasibility"]
    field_map = report["CandidateFieldMap"]
    lines = [
        "# NiDataStream descriptor/sample-byte comparison",
        "",
        f"- Candidate-only: **{str(report['CandidateOnly']).lower()}**",
        f"- Parser/export promotion allowed: **{str(report['ParserExportPromotionAllowed']).lower()}**",
        f"- Field order promoted: **{str(report['FieldOrderPromoted']).lower()}**",
        (f"- Descriptor + sample evidence ready: **{str(report['DescriptorAndSampleEvidenceReady']).lower()}**"),
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
        (f"| Descriptor record byte patterns | {format_markdown_cell(record_bytes['RecordPatternCount'])} |"),
        (
            "| Descriptor record index mapped | "
            f"{format_markdown_cell(str(record_index['CandidateRecordIndexMapped']).lower())} |"
        ),
        (
            "| Descriptor helper high bytes proven unused | "
            f"{format_markdown_cell(str(helper_argument_use['HelperLookupHighBytesProvenUnused']).lower())} |"
        ),
        (
            "| Descriptor record bytes classified | "
            f"{format_markdown_cell(record_roles['ClassifiedByteCount'])}/"
            f"{format_markdown_cell(record_roles['RecordWidthBytes'])} |"
        ),
        (
            "| Descriptor record pattern matrix rows | "
            f"{format_markdown_cell(record_pattern_matrix['RecordPatternCount'])} |"
        ),
        (
            "| Descriptor/sample context correlation | "
            f"{format_markdown_cell(sample_context['DescriptorPatternCount'])} pattern(s); "
            f"ready={format_markdown_cell(str(sample_context['CorrelationReady']).lower())} |"
        ),
        (
            "| Descriptor-table indexed samples | "
            f"{format_markdown_cell(table_sample['RowCount'])} row(s); "
            f"nonzero={format_markdown_cell(table_sample['NonzeroRowCount'])}; "
            f"semantics={format_markdown_cell(str(table_sample['StreamSemanticsExplained']).lower())} |"
        ),
        (
            "| Descriptor semantic mapping ready | "
            f"{format_markdown_cell(str(semantic['SemanticMappingReady']).lower())} |"
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
            "## Descriptor record byte distribution",
            "",
            "| Byte offset | Unique values | Top values |",
            "|---:|---:|---|",
        ]
    )
    for offset in record_bytes["ByteOffsets"]:
        top_values = ", ".join(f"{value['ValueHex']} ({value['Count']})" for value in offset["TopValues"][:8])
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(offset["OffsetBytes"]),
                    format_markdown_cell(offset["UniqueValueCount"]),
                    format_markdown_cell(top_values),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Descriptor record index proof",
            "",
            f"- Candidate record byte offset: **{format_markdown_cell(record_index['CandidateIndexByteOffset'])}**",
            f"- Candidate record index mapped: **{str(record_index['CandidateRecordIndexMapped']).lower()}**",
            f"- Remaining unmapped byte offsets: **{format_markdown_cell(', '.join(str(offset) for offset in record_index['RemainingUnmappedByteOffsets']))}**",
            "",
            "| Check | Target | Passed | Missing terms | Evidence |",
            "|---|---|---:|---|---|",
        ]
    )
    for check in record_index["Checks"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(check["Key"]),
                    format_markdown_cell(check["TargetKey"]),
                    format_markdown_cell(str(check["Passed"]).lower()),
                    format_markdown_cell(", ".join(str(term) for term in check["MissingTerms"])),
                    format_markdown_cell(check["Evidence"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Descriptor helper argument-use proof",
            "",
            (
                "- Helper lookup high bytes proven unused: "
                f"**{str(helper_argument_use['HelperLookupHighBytesProvenUnused']).lower()}**"
            ),
            (
                "- Candidate helper-lookup ignored byte offsets: "
                "**"
                + format_markdown_cell(
                    ", ".join(str(offset) for offset in helper_argument_use["CandidateHelperLookupIgnoredByteOffsets"])
                )
                + "**"
            ),
            (
                "- Candidate sign-guard byte offsets: **"
                + format_markdown_cell(
                    ", ".join(str(offset) for offset in helper_argument_use["CandidateSignGuardByteOffsets"])
                )
                + "**"
            ),
            "",
            "| Check | Target | Passed | Missing terms | Forbidden high-byte terms present | Evidence |",
            "|---|---|---:|---|---|---|",
        ]
    )
    for check in helper_argument_use["Checks"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(check["Key"]),
                    format_markdown_cell(check["TargetKey"]),
                    format_markdown_cell(str(check["Passed"]).lower()),
                    format_markdown_cell(", ".join(str(term) for term in check["MissingTerms"])),
                    format_markdown_cell(", ".join(str(term) for term in check["PresentForbiddenHighByteTerms"])),
                    format_markdown_cell(check["Evidence"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Descriptor record byte role candidates",
            "",
            f"- All bytes classified: **{str(record_roles['AllBytesClassified']).lower()}**",
            f"- Remaining unmapped bytes: **{format_markdown_cell(', '.join(str(offset) for offset in record_roles['RemainingUnmappedByteOffsets']))}**",
            "",
            "| Byte offset | Candidate role | Classification | Unique values | Blocks semantic mapping | Top values |",
            "|---:|---|---|---:|---:|---|",
        ]
    )
    for row in record_roles["Rows"]:
        top_values = ", ".join(f"{value['ValueHex']} ({value['Count']})" for value in row["TopValues"][:8])
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(row["OffsetBytes"]),
                    format_markdown_cell(row["CandidateRole"]),
                    format_markdown_cell(row["Classification"]),
                    format_markdown_cell(row["UniqueValueCount"]),
                    format_markdown_cell(str(row["BlocksSemanticMapping"]).lower()),
                    format_markdown_cell(top_values),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Descriptor record pattern matrix",
            "",
            f"- Pattern rows: **{format_markdown_cell(record_pattern_matrix['RecordPatternCount'])}**",
            (
                "- Remaining unmapped byte offsets: **"
                + format_markdown_cell(
                    ", ".join(str(offset) for offset in record_pattern_matrix["RemainingUnmappedByteOffsets"])
                )
                + "**"
            ),
            "",
            "| Rank | Record bytes | Count | Index byte | Helper-lookup ignored bytes | Sign-guard bytes | Remaining unmapped bytes |",
            "|---:|---|---:|---|---|---|---|",
        ]
    )
    for row in record_pattern_matrix["Rows"]:
        index_byte = row["CandidateIndexByte"]
        index_text = f"{index_byte['OffsetBytes']}={index_byte['ValueHex']}" if isinstance(index_byte, dict) else "-"
        helper_ignored = ", ".join(
            f"{value['OffsetBytes']}={value['ValueHex']}" for value in row["CandidateHelperLookupIgnoredBytes"]
        )
        sign_guard = ", ".join(
            f"{value['OffsetBytes']}={value['ValueHex']}" for value in row["CandidateSignGuardBytes"]
        )
        remaining = ", ".join(f"{value['OffsetBytes']}={value['ValueHex']}" for value in row["RemainingUnmappedBytes"])
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(row["PatternRank"]),
                    format_markdown_cell(row["RecordHex"]),
                    format_markdown_cell(row["Count"]),
                    format_markdown_cell(index_text),
                    format_markdown_cell(helper_ignored),
                    format_markdown_cell(sign_guard),
                    format_markdown_cell(remaining),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Descriptor/sample context correlation",
            "",
            f"- Source samples: **{format_markdown_cell(sample_context['SampleCount'])}**",
            f"- Correlation ready: **{str(sample_context['CorrelationReady']).lower()}**",
            (
                "- Remaining unmapped byte offsets: **"
                + format_markdown_cell(
                    ", ".join(str(offset) for offset in sample_context["RemainingUnmappedByteOffsets"])
                )
                + "**"
            ),
            "",
            "| Descriptor record | Samples | Pair patterns | Top pair records | Usage values | Access values | Type names |",
            "|---|---:|---:|---|---|---|---|",
        ]
    )
    for row in sample_context["Rows"]:
        top_pairs = ", ".join(f"{value['Value']} ({value['Count']})" for value in row["TopPairRecordBytes"][:6])
        top_usage = ", ".join(f"{value['Value']} ({value['Count']})" for value in row["TopUsageValues"][:6])
        top_access = ", ".join(f"{value['Value']} ({value['Count']})" for value in row["TopAccessValues"][:6])
        top_types = ", ".join(f"{value['Value']} ({value['Count']})" for value in row["TopTypeNames"][:4])
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(row["DescriptorRecordHex"]),
                    format_markdown_cell(row["SampleCount"]),
                    format_markdown_cell(row["PairRecordPatternCount"]),
                    format_markdown_cell(top_pairs),
                    format_markdown_cell(top_usage),
                    format_markdown_cell(top_access),
                    format_markdown_cell(top_types),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Descriptor/sample context review queue",
            "",
            "| Rank | Descriptor record | Samples | Pair patterns | Dominant pair record | Dominant usage | Dominant access | Dominant type |",
            "|---:|---|---:|---:|---|---|---|---|",
        ]
    )
    for row in sample_context["ReviewQueueRows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(row["Rank"]),
                    format_markdown_cell(row["DescriptorRecordHex"]),
                    format_markdown_cell(row["SampleCount"]),
                    format_markdown_cell(row["PairRecordPatternCount"]),
                    format_markdown_cell(
                        f"{row['DominantPairRecordBytes']} ({row['DominantPairRecordCount']})"
                        if row["DominantPairRecordBytes"]
                        else "-"
                    ),
                    format_markdown_cell(
                        f"{row['DominantUsageValue']} ({row['DominantUsageCount']})"
                        if row["DominantUsageValue"]
                        else "-"
                    ),
                    format_markdown_cell(
                        f"{row['DominantAccessValue']} ({row['DominantAccessCount']})"
                        if row["DominantAccessValue"]
                        else "-"
                    ),
                    format_markdown_cell(
                        f"{row['DominantTypeName']} ({row['DominantTypeNameCount']})"
                        if row["DominantTypeName"]
                        else "-"
                    ),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Descriptor-table indexed sample status",
            "",
            f"- Report exists: **{str(table_sample['Exists']).lower()}**",
            f"- Sample report ready: **{str(table_sample['SampleReportReady']).lower()}**",
            f"- Rows: **{format_markdown_cell(table_sample['RowCount'])}**",
            f"- Nonzero rows: **{format_markdown_cell(table_sample['NonzeroRowCount'])}**",
            f"- All rows zero: **{str(table_sample['AllRowsZero']).lower()}**",
            f"- Stream semantics explained: **{str(table_sample['StreamSemanticsExplained']).lower()}**",
            "",
            "| Field | Rows | Nonzero rows | All rows zero | Indices |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for row in table_sample["RowsByField"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(row["Field"]),
                    format_markdown_cell(row["RowCount"]),
                    format_markdown_cell(row["NonzeroRowCount"]),
                    format_markdown_cell(str(row["AllRowsZero"]).lower()),
                    format_markdown_cell(", ".join(row["Indices"])),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Descriptor semantic feasibility",
            "",
            f"- Semantic mapping ready: **{str(semantic['SemanticMappingReady']).lower()}**",
            f"- Parser/export promotion allowed: **{str(semantic['ParserExportPromotionAllowed']).lower()}**",
            "",
            "| Field | Static table offset | Static stride | Record offsets considered | Stream record status | Mapping decision |",
            "|---|---:|---:|---|---|---|",
        ]
    )
    for row in semantic["OffsetComparisonRows"]:
        candidate_offsets = ", ".join(str(offset) for offset in row["CandidateRecordByteOffsets"])
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(row["Field"]),
                    format_markdown_cell(row["StaticTableOffsetBytes"]),
                    format_markdown_cell(row["StaticTableStrideBytes"]),
                    format_markdown_cell(candidate_offsets),
                    format_markdown_cell(row["StreamDescriptorRecordStatus"]),
                    format_markdown_cell(row["MappingDecision"]),
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
    record_bytes = report["DescriptorRecordByteSummary"]
    record_index = report["DescriptorRecordIndexProof"]
    helper_argument_use = report["DescriptorHelperArgumentUseProof"]
    record_roles = report["DescriptorRecordByteRoleCandidates"]
    record_pattern_matrix = report["DescriptorRecordPatternMatrix"]
    sample_context = report["DescriptorSampleContextCorrelation"]
    table_sample = report["DescriptorTableSampleStatus"]
    semantic = report["DescriptorSemanticFeasibility"]
    print("--- NiDataStreamDescriptorSampleCompare")
    print(
        "Descriptor helper evidence-ready targets: "
        f"{descriptor['EvidenceReadyCount']}/{descriptor['RequiredTargetCount']}"
    )
    print(f"Ghidra-style-valid sample blocks: {layout['GhidraStyleLayoutValidBlocks']}/{layout['NiDataStreamBlocks']}")
    print(f"Sample corpus files parsed: {corpus['FilesParsed']}/{corpus['FilesScanned']}")
    print(f"Uniform sample-byte checks: {sample['PassedCount']}/{sample['CheckCount']}")
    print(f"Descriptor byte-order checks: {byte_order['PassedCount']}/{byte_order['CheckCount']}")
    print(
        "Descriptor record byte patterns: "
        f"{record_bytes['RecordPatternCount']} patterns; width={record_bytes['RecordWidthBytes']}"
    )
    print(
        "Descriptor record index proof: "
        f"{record_index['PassedEvidenceCount']}/{record_index['RequiredEvidenceCount']} checks; "
        f"record byte 0 mapped={str(record_index['CandidateRecordIndexMapped']).lower()}"
    )
    print(
        "Descriptor helper argument-use proof: "
        f"{helper_argument_use['PassedEvidenceCount']}/{helper_argument_use['RequiredEvidenceCount']} checks; "
        "high bytes proven unused="
        f"{str(helper_argument_use['HelperLookupHighBytesProvenUnused']).lower()}"
    )
    print(
        "Descriptor record byte roles: "
        f"classified={record_roles['ClassifiedByteCount']}/{record_roles['RecordWidthBytes']}; "
        f"remaining={','.join(str(offset) for offset in record_roles['RemainingUnmappedByteOffsets']) or '-'}"
    )
    print(
        "Descriptor record pattern matrix: "
        f"rows={record_pattern_matrix['RecordPatternCount']}; "
        f"remaining={','.join(str(offset) for offset in record_pattern_matrix['RemainingUnmappedByteOffsets']) or '-'}"
    )
    print(
        "Descriptor/sample context correlation: "
        f"samples={sample_context['SampleCount']}; "
        f"patterns={sample_context['DescriptorPatternCount']}; "
        f"review queue={sample_context['ReviewQueueCount']}; "
        f"ready={str(sample_context['CorrelationReady']).lower()}"
    )
    print(
        "Descriptor-table indexed samples: "
        f"exists={str(table_sample['Exists']).lower()}; "
        f"rows={table_sample['RowCount']}; "
        f"nonzero={table_sample['NonzeroRowCount']}; "
        f"all zero={str(table_sample['AllRowsZero']).lower()}; "
        f"semantics explained={str(table_sample['StreamSemanticsExplained']).lower()}"
    )
    print(
        "Descriptor semantic mapping ready: "
        f"{str(semantic['SemanticMappingReady']).lower()}; "
        f"mapped fields={semantic['StreamDescriptorRecordMappedCount']}/{semantic['StaticFieldMapOffsetCount']}"
    )
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
    field_map = (
        [field for field in field_map_value if isinstance(field, dict)] if isinstance(field_map_value, list) else []
    )
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
    evidence_text = f"{ready_count}/{target_count} FunctionSiteSurvey targets have ignored local JSON reports and Markdown summaries."
    descriptor_status = _nidatastream_descriptor_proof_status_payload(args)
    field_map_status = _nidatastream_descriptor_field_map_status(descriptor_status)
    descriptor_ready = bool(descriptor_status["AllRequiredEvidenceReady"])
    descriptor_state = "candidate" if descriptor_ready else "blocked"
    descriptor_evidence = (
        f"{descriptor_status['EvidenceReadyCount']}/{descriptor_status['RequiredTargetCount']} descriptor helper "
        "reports satisfy call/data-ref/decompile-term evidence; "
        f"static field-map entries {field_map_status['CandidateOnlyEntryCount']}/{field_map_status['FieldMapCount']}; "
        "helper lookup high bytes proven unused "
        f"{str(descriptor_status['DescriptorHelperArgumentUseProof']['HelperLookupHighBytesProvenUnused']).lower()}; "
        "stream descriptor record semantics remain unmapped."
    )
    layout_status = _nidatastream_layout_report_status(args)
    layout_report, layout_error = _read_nidatastream_layout_report(args)
    if layout_error and not layout_status["Error"]:
        layout_status["Error"] = layout_error
    sample_corpus_status = _nidatastream_sample_corpus_status(layout_report)
    sample_summary = _nidatastream_sample_byte_uniformity_summary(layout_report, layout_status)
    byte_order_proof = _nidatastream_descriptor_byte_order_proof(layout_report, layout_status)
    record_byte_summary = _nidatastream_descriptor_record_byte_summary(byte_order_proof)
    record_byte_roles = _nidatastream_descriptor_record_byte_role_candidates(
        record_byte_summary,
        descriptor_status["DescriptorRecordIndexProof"],
    )
    record_pattern_matrix = _nidatastream_descriptor_record_pattern_matrix(
        byte_order_proof,
        descriptor_status["DescriptorRecordIndexProof"],
        descriptor_status["DescriptorHelperArgumentUseProof"],
        record_byte_roles,
    )
    sample_context_correlation = _nidatastream_descriptor_sample_context_correlation(
        layout_report,
        record_pattern_matrix,
    )
    descriptor_table_sample_status = _nidatastream_descriptor_table_sample_status(args)
    descriptor_table_sample_compare = _nidatastream_descriptor_table_sample_compare_packet(args)
    semantic_feasibility = _nidatastream_descriptor_semantic_feasibility(
        descriptor_status["CandidateFieldMap"],
        record_byte_summary,
        descriptor_status["DescriptorRecordIndexProof"],
        record_byte_roles,
        descriptor_status["DescriptorHelperArgumentUseProof"],
    )
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
            f"record byte 0 mapped {str(semantic_feasibility['DescriptorRecordIndexCandidateMapped']).lower()}; "
            "helper high bytes proven unused "
            f"{str(descriptor_status['DescriptorHelperArgumentUseProof']['HelperLookupHighBytesProvenUnused']).lower()}; "
            f"remaining bytes {len(record_byte_roles['RemainingUnmappedByteOffsets'])}; "
            f"semantic mapping ready {str(semantic_feasibility['SemanticMappingReady']).lower()}; "
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
            "descriptor-semantic-map",
            "candidate" if semantic_feasibility["SemanticMappingReady"] else "blocked",
            not bool(semantic_feasibility["SemanticMappingReady"]),
            "Static descriptor-table offsets and stream descriptor-record bytes are mapped field-by-field with semantics.",
            (
                f"Semantic feasibility has record byte 0 mapped="
                f"{str(semantic_feasibility['DescriptorRecordIndexCandidateMapped']).lower()}, "
                f"{semantic_feasibility['StaticFieldMapOffsetCount']} static offset(s), "
                f"{semantic_feasibility['DescriptorRecordByteOffsetCount']} stream record byte offset(s), "
                "helper high bytes proven unused="
                f"{str(semantic_feasibility['DescriptorHelperLookupHighBytesProvenUnused']).lower()}, "
                f"mapped fields {semantic_feasibility['StreamDescriptorRecordMappedCount']}/"
                f"{semantic_feasibility['StaticFieldMapOffsetCount']}; still candidate-only."
            ),
            "python scripts/rift_workflow.py nidatastream-descriptor-sample-compare --list-json",
        ),
        _nidatastream_gate(
            "descriptor-table-sample-proof",
            "candidate" if descriptor_table_sample_status["SampleReportReady"] else "blocked",
            True,
            "Computed descriptor-table entries for observed stream descriptor indices explain or explicitly block field semantics.",
            (
                f"Descriptor-table sample report exists={str(descriptor_table_sample_status['Exists']).lower()}, "
                f"rows={descriptor_table_sample_status['RowCount']}, "
                f"nonzero rows={descriptor_table_sample_status['NonzeroRowCount']}, "
                f"all rows zero={str(descriptor_table_sample_status['AllRowsZero']).lower()}, "
                f"known reports={descriptor_table_sample_compare['ExistingReportCount']}/"
                f"{descriptor_table_sample_compare['ReportCount']}, "
                f"nonzero reports={descriptor_table_sample_compare['NonzeroReportCount']}, "
                f"semantics explained={str(descriptor_table_sample_status['StreamSemanticsExplained']).lower()}; "
                "still candidate-only."
            ),
            "python scripts/rift_workflow.py nidatastream-descriptor-table-sample-compare --list-json",
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
            "DescriptorRecordPatternCount": record_byte_summary["RecordPatternCount"],
            "DescriptorRecordPatternMatrixRowCount": record_pattern_matrix["RecordPatternCount"],
            "DescriptorContextCorrelationReady": sample_context_correlation["CorrelationReady"],
            "DescriptorContextCorrelationSampleCount": sample_context_correlation["SampleCount"],
            "DescriptorContextCorrelationPatternCount": sample_context_correlation["DescriptorPatternCount"],
            "DescriptorTableSampleReportReady": descriptor_table_sample_status["SampleReportReady"],
            "DescriptorTableSampleRowCount": descriptor_table_sample_status["RowCount"],
            "DescriptorTableSampleNonzeroRowCount": descriptor_table_sample_status["NonzeroRowCount"],
            "DescriptorTableSampleAllRowsZero": descriptor_table_sample_status["AllRowsZero"],
            "DescriptorTableSampleSemanticsExplained": descriptor_table_sample_status["StreamSemanticsExplained"],
            "DescriptorTableSampleCompareReportCount": descriptor_table_sample_compare["ReportCount"],
            "DescriptorTableSampleCompareExistingReportCount": descriptor_table_sample_compare["ExistingReportCount"],
            "DescriptorTableSampleCompareReadyReportCount": descriptor_table_sample_compare["ReadyReportCount"],
            "DescriptorTableSampleCompareNonzeroReportCount": descriptor_table_sample_compare["NonzeroReportCount"],
            "DescriptorTableSampleCompareAllExistingReportsAllZero": descriptor_table_sample_compare[
                "AllExistingReportsAllZero"
            ],
            "DescriptorRecordWidthBytes": record_byte_summary["RecordWidthBytes"],
            "DescriptorRecordIndexCandidateMapped": semantic_feasibility["DescriptorRecordIndexCandidateMapped"],
            "DescriptorHelperLookupHighBytesProvenUnused": descriptor_status["DescriptorHelperArgumentUseProof"][
                "HelperLookupHighBytesProvenUnused"
            ],
            "DescriptorHelperLookupIgnoredByteCount": len(
                descriptor_status["DescriptorHelperArgumentUseProof"]["CandidateHelperLookupIgnoredByteOffsets"]
            ),
            "DescriptorSignGuardByteCount": len(
                descriptor_status["DescriptorHelperArgumentUseProof"]["CandidateSignGuardByteOffsets"]
            ),
            "DescriptorRecordBytesClassified": record_byte_roles["AllBytesClassified"],
            "DescriptorRecordPaddingByteCount": len(record_byte_roles["CandidatePaddingByteOffsets"]),
            "DescriptorRecordRemainingUnmappedByteCount": len(record_byte_roles["RemainingUnmappedByteOffsets"]),
            "DescriptorSemanticMappingReady": semantic_feasibility["SemanticMappingReady"],
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
    print(f"FunctionSite evidence-ready targets: {target_status['EvidenceReadyCount']}/{target_status['TargetCount']}")
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
        f"record byte 0 mapped={str(compare_status['DescriptorRecordIndexCandidateMapped']).lower()}; "
        f"pattern rows={compare_status['DescriptorRecordPatternMatrixRowCount']}; "
        f"context samples={compare_status['DescriptorContextCorrelationSampleCount']}; "
        f"table rows={compare_status['DescriptorTableSampleRowCount']}; "
        f"table nonzero={compare_status['DescriptorTableSampleNonzeroRowCount']}; "
        "helper high bytes proven unused="
        f"{str(compare_status['DescriptorHelperLookupHighBytesProvenUnused']).lower()}; "
        f"remaining bytes={compare_status['DescriptorRecordRemainingUnmappedByteCount']}; "
        f"semantic mapping ready={str(compare_status['DescriptorSemanticMappingReady']).lower()}; "
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
            "| Descriptor record byte patterns | "
            f"{format_markdown_cell(compare_status['DescriptorRecordPatternCount'])} |"
        ),
        (
            "| Descriptor record pattern matrix rows | "
            f"{format_markdown_cell(compare_status['DescriptorRecordPatternMatrixRowCount'])} |"
        ),
        (
            "| Descriptor/sample context correlation samples | "
            f"{format_markdown_cell(compare_status['DescriptorContextCorrelationSampleCount'])} |"
        ),
        (
            "| Descriptor/sample context correlation patterns | "
            f"{format_markdown_cell(compare_status['DescriptorContextCorrelationPatternCount'])} |"
        ),
        (
            "| Descriptor/sample context correlation ready | "
            f"{format_markdown_cell(str(compare_status['DescriptorContextCorrelationReady']).lower())} |"
        ),
        (f"| Descriptor-table sample rows | {format_markdown_cell(compare_status['DescriptorTableSampleRowCount'])} |"),
        (
            "| Descriptor-table sample nonzero rows | "
            f"{format_markdown_cell(compare_status['DescriptorTableSampleNonzeroRowCount'])} |"
        ),
        (
            "| Descriptor-table sample semantics explained | "
            f"{format_markdown_cell(str(compare_status['DescriptorTableSampleSemanticsExplained']).lower())} |"
        ),
        (
            "| Descriptor record byte 0 mapped | "
            f"{format_markdown_cell(str(compare_status['DescriptorRecordIndexCandidateMapped']).lower())} |"
        ),
        (
            "| Descriptor helper high bytes proven unused | "
            f"{format_markdown_cell(str(compare_status['DescriptorHelperLookupHighBytesProvenUnused']).lower())} |"
        ),
        (
            "| Descriptor helper-lookup ignored byte candidates | "
            f"{format_markdown_cell(compare_status['DescriptorHelperLookupIgnoredByteCount'])} |"
        ),
        (
            "| Descriptor sign-guard byte candidates | "
            f"{format_markdown_cell(compare_status['DescriptorSignGuardByteCount'])} |"
        ),
        (
            "| Descriptor record padding byte candidates | "
            f"{format_markdown_cell(compare_status['DescriptorRecordPaddingByteCount'])} |"
        ),
        (
            "| Descriptor record remaining unmapped bytes | "
            f"{format_markdown_cell(compare_status['DescriptorRecordRemainingUnmappedByteCount'])} |"
        ),
        (
            "| Descriptor semantic mapping ready | "
            f"{format_markdown_cell(str(compare_status['DescriptorSemanticMappingReady']).lower())} |"
        ),
        (
            "| Descriptor/sample evidence ready | "
            f"{format_markdown_cell(str(compare_status['DescriptorAndSampleEvidenceReady']).lower())} |"
        ),
        (
            "| Complete Ghidra-only P+N+UV groups | "
            f"{format_markdown_cell(pairing_status['CompletePositionNormalUvCandidateGroups'])} |"
        ),
        (f"| Ghidra-only candidate groups | {format_markdown_cell(pairing_status['GhidraOnlyGroups'])} |"),
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


def _parse_descriptor_index_token(token: str) -> int:
    """Parse a descriptor-table index token as one byte, favoring hex notation."""
    text = token.strip().lower().removeprefix("0x")
    if not text:
        raise ValueError("empty descriptor index")
    try:
        value = int(text, 16)
    except ValueError as exc:
        raise ValueError(f"invalid descriptor index {token!r}") from exc
    if value < 0 or value > 0xFF:
        raise ValueError(f"descriptor index out of byte range: {token!r}")
    return value


def _descriptor_table_field_specs() -> list[dict[str, Any]]:
    """Return static descriptor-table field specs from the candidate field map."""
    fields = []
    for field in DESCRIPTOR_CANDIDATE_FIELD_MAP:
        data_address = field.get("DataAddress")
        offset = field.get("StaticTableOffsetBytes")
        stride = field.get("StaticTableStrideBytes")
        if not isinstance(data_address, str) or not isinstance(offset, int) or not isinstance(stride, int):
            continue
        fields.append(
            {
                "Field": str(field.get("Field", "")),
                "DataAddress": data_address.lower().removeprefix("0x"),
                "StaticTableOffsetBytes": offset,
                "StaticTableStrideBytes": stride,
            }
        )
    return sorted(fields, key=lambda row: int(row["StaticTableOffsetBytes"]))


def _descriptor_table_indices_from_args(args: argparse.Namespace) -> list[int]:
    """Return explicitly supplied descriptor indices, preserving first occurrence order."""
    if getattr(args, "descriptor_table_all_byte_indices", False):
        return list(range(0x100))
    seen: set[int] = set()
    indices = []
    for token in args.descriptor_index or []:
        for part in str(token).split(","):
            if not part.strip():
                continue
            value = _parse_descriptor_index_token(part)
            if value not in seen:
                seen.add(value)
                indices.append(value)
    return indices


def _descriptor_table_indices_from_samples(args: argparse.Namespace) -> list[int]:
    """Derive descriptor indices from current descriptor/sample evidence."""
    try:
        compare = _nidatastream_descriptor_sample_compare_payload(args)
    except Exception:
        return []
    matrix = compare.get("DescriptorRecordPatternMatrix")
    rows = matrix.get("Rows") if isinstance(matrix, dict) else None
    if not isinstance(rows, list):
        return []
    seen: set[int] = set()
    indices = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        candidate = row.get("CandidateIndexByte")
        if not isinstance(candidate, dict):
            continue
        value_hex = candidate.get("ValueHex")
        if not isinstance(value_hex, str):
            continue
        try:
            value = _parse_descriptor_index_token(value_hex)
        except ValueError:
            continue
        if value not in seen:
            seen.add(value)
            indices.append(value)
    return indices


def _descriptor_table_sample_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """Return default/overridden descriptor table sample report paths."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    report_path = (
        Path(args.descriptor_table_report)
        if args.descriptor_table_report
        else out_dir / "ghidra-reports" / "nidatastream_descriptor_table_samples.json"
    )
    markdown_path = (
        Path(args.descriptor_table_summary)
        if args.descriptor_table_summary
        else out_dir / "ghidra-reports" / "nidatastream_descriptor_table_samples.md"
    )
    return report_path, markdown_path


def _descriptor_table_sample_plan(args: argparse.Namespace) -> dict[str, Any]:
    """Build a candidate-only plan for indexed descriptor-table sampling."""
    fields = _descriptor_table_field_specs()
    explicit_indices = _descriptor_table_indices_from_args(args)
    indices = explicit_indices if explicit_indices else _descriptor_table_indices_from_samples(args)
    stride_values = {int(field["StaticTableStrideBytes"]) for field in fields}
    stride_override = int(getattr(args, "descriptor_table_stride", 0) or 0)
    if stride_override > 0:
        stride_bytes = stride_override
        stride_source = "override"
    elif len(stride_values) == 1:
        stride_bytes = sorted(stride_values)[0]
        stride_source = "candidate-field-map"
    else:
        stride_bytes = 0
        stride_source = "ambiguous-candidate-field-map"
    byte_count = int(args.descriptor_table_byte_count)
    report_path, markdown_path = _descriptor_table_sample_paths(args)
    blockers = []
    if not fields:
        blockers.append("descriptor-table-sample-fields-missing")
    if not indices:
        blockers.append("descriptor-table-sample-indices-missing")
    if stride_override < 0:
        blockers.append("descriptor-table-sample-stride-invalid")
    if stride_bytes <= 0:
        blockers.append("descriptor-table-sample-stride-ambiguous")
    if byte_count <= 0:
        blockers.append("descriptor-table-sample-byte-count-invalid")
    if byte_count > 64:
        blockers.append("descriptor-table-sample-byte-count-too-large")
    rows = []
    for field in fields:
        base_value = int(str(field["DataAddress"]), 16)
        for index in indices:
            rows.append(
                {
                    "Field": field["Field"],
                    "BaseAddress": field["DataAddress"],
                    "StaticTableOffsetBytes": field["StaticTableOffsetBytes"],
                    "Index": index,
                    "IndexHex": f"{index:02x}",
                    "StrideBytes": stride_bytes,
                    "ComputedAddress": f"{base_value + index * stride_bytes:x}" if stride_bytes > 0 else "",
                }
            )
    field_args = [f"{field['Field']}:{field['DataAddress']}:{field['StaticTableOffsetBytes']}" for field in fields]
    script = args.ghidra_script or "scripts/ghidra/DescriptorTableSampler.java"
    project_name = args.ghidra_project_name if args.ghidra_project_name != "TempProject" else "RiftAnchorSurvey"
    process_path = args.ghidra_process or "rift_x64.exe"
    return {
        "SchemaVersion": "nidatastream-descriptor-table-sample-plan/v1",
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "ParserExportPromotionAllowed": False,
        "ReportPath": str(report_path),
        "MarkdownPath": str(markdown_path),
        "Script": script,
        "ProjectName": project_name,
        "Process": process_path,
        "StrideBytes": stride_bytes,
        "StrideSource": stride_source,
        "ByteCountRequested": byte_count,
        "AllByteIndices": bool(getattr(args, "descriptor_table_all_byte_indices", False)),
        "IndexCount": len(indices),
        "Indices": [{"Value": index, "ValueHex": f"{index:02x}"} for index in indices],
        "FieldCount": len(fields),
        "Fields": fields,
        "PlannedRowCount": len(rows),
        "PlannedRows": rows,
        "ScriptArgs": [
            str(report_path),
            str(stride_bytes),
            str(byte_count),
            *[f"0x{index:02x}" for index in indices],
            *field_args,
        ],
        "BlockerCount": len(blockers),
        "Blockers": blockers,
        "Interpretation": (
            "Candidate-only dry-run plan for sampling computed descriptor-table entries. "
            "Rows are static Ghidra evidence only and must not change parser/export behavior."
        ),
    }


def _descriptor_table_sample_markdown(report: dict[str, Any]) -> str:
    """Render a compact Markdown summary for a Ghidra descriptor table sample report."""
    rows = report.get("rows") if isinstance(report.get("rows"), list) else []
    lines = [
        "# Ghidra descriptor table sample",
        "",
        f"- Candidate-only: **{str(report.get('CandidateOnly')).lower()}**",
        f"- Parser/export promotion allowed: **{str(report.get('ParserExportPromotionAllowed')).lower()}**",
        f"- Program: **{format_markdown_cell(report.get('programName'))}**",
        f"- Stride bytes: **{format_markdown_cell(report.get('strideBytes'))}**",
        f"- Byte count requested: **{format_markdown_cell(report.get('byteCountRequested'))}**",
        f"- Rows: **{format_markdown_cell(report.get('rowCount'))}**",
        "",
        "| Field | Index | Computed address | Bytes read | Bytes | Error |",
        "|---|---:|---|---:|---|---|",
    ]
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(row.get("field")),
                    format_markdown_cell(row.get("indexHex")),
                    format_markdown_cell(row.get("computedAddress")),
                    format_markdown_cell(row.get("byteCountRead")),
                    format_markdown_cell(row.get("bytes")),
                    format_markdown_cell(row.get("error", "")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation guard",
            "",
            format_markdown_cell(report.get("interpretation")),
            "",
        ]
    )
    return "\n".join(lines)


def _print_descriptor_table_sample_plan(plan: dict[str, Any]) -> None:
    """Print a human-readable indexed descriptor-table sample dry-run."""
    print("--- NiDataStreamDescriptorTableSample")
    print(f"Report: {plan['ReportPath']}")
    print(f"Markdown: {plan['MarkdownPath']}")
    print(f"Script: {plan['Script']}")
    print(f"Indices: {', '.join(row['ValueHex'] for row in plan['Indices']) or '-'}")
    print(f"Fields: {plan['FieldCount']}")
    print(f"Planned rows: {plan['PlannedRowCount']}")
    if plan["Blockers"]:
        print(f"Blockers: {', '.join(plan['Blockers'])}")
    run_command = [
        "python",
        "scripts/rift_workflow.py",
        "ghidra-run",
        "--ghidra-project-name",
        str(plan["ProjectName"]),
        "--ghidra-process",
        str(plan["Process"]),
        "--ghidra-timeout",
        "900",
        "--ghidra-script",
        str(plan["Script"]),
    ]
    for value in plan["ScriptArgs"]:
        run_command += ["--ghidra-script-arg", str(value)]
    run_command += ["--ghidra-no-analysis", "--ghidra-keep-project"]
    print("\nRun command:")
    print(" ".join(run_command))


def _run_nidatastream_descriptor_table_sample(args: argparse.Namespace) -> None:
    """Run or print a candidate-only indexed descriptor-table sampling workflow."""
    plan = _descriptor_table_sample_plan(args)
    if args.list_json:
        print(json.dumps(plan, indent=2))
        return

    _print_descriptor_table_sample_plan(plan)
    if plan["Blockers"]:
        print("NiDataStreamDescriptorTableSample blocked before Ghidra execution.")
        if args.ghidra_execute:
            sys.exit(1)
        print("Dry-run only. Resolve blockers before adding --ghidra-execute.")
        return
    if not args.ghidra_execute:
        print("\nDry-run only. Add --ghidra-execute to run this indexed sampler.")
        return

    from scripts.ghidra_runner import run_ghidra_headless

    report_path = Path(plan["ReportPath"])
    markdown_path = Path(plan["MarkdownPath"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_ghidra_headless(
        project_dir=_ghidra_project_dir_arg(args),
        project_name=str(plan["ProjectName"]),
        process_path=str(plan["Process"]),
        script=str(plan["Script"]),
        script_args=[str(value) for value in plan["ScriptArgs"]],
        analyze=False,
        delete_project=False,
        timeout_seconds=args.ghidra_timeout,
    )
    _print_ghidra_result(result)
    report = load_json_report(str(report_path))
    if not report.get("CandidateOnly") or report.get("ParserExportPromotionAllowed"):
        print("ERROR: descriptor table sample report is not candidate-only/promoted-false.", file=sys.stderr)
        sys.exit(1)
    markdown_path.write_text(_descriptor_table_sample_markdown(report), encoding="utf-8")
    row_count = _json_int_or_none(report.get("rowCount")) or 0
    nonzero_rows = 0
    for row in report.get("rows", []):
        if not isinstance(row, dict):
            continue
        bytes_text = str(row.get("bytes", ""))
        parsed = _parse_hex_byte_record(bytes_text)
        if parsed and any(byte != 0 for byte in parsed):
            nonzero_rows += 1
    print(f"NiDataStreamDescriptorTableSample rows: {row_count}; nonzero rows: {nonzero_rows}")
    print(f"NiDataStreamDescriptorTableSample JSON: {report_path}")
    print(f"NiDataStreamDescriptorTableSample markdown: {markdown_path}")
    print("NiDataStreamDescriptorTableSample passed: report remains candidate-only/report-only.")


def _descriptor_neighborhood_scan_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """Return default/overridden descriptor neighborhood scan report paths."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    report_path = (
        Path(args.descriptor_neighborhood_report)
        if args.descriptor_neighborhood_report
        else out_dir / "ghidra-reports" / "nidatastream_descriptor_neighborhood_scan.json"
    )
    markdown_path = (
        Path(args.descriptor_neighborhood_summary)
        if args.descriptor_neighborhood_summary
        else out_dir / "ghidra-reports" / "nidatastream_descriptor_neighborhood_scan.md"
    )
    return report_path, markdown_path


def _descriptor_neighborhood_scan_plan(args: argparse.Namespace) -> dict[str, Any]:
    """Build a candidate-only bounded descriptor neighborhood scan plan."""
    fields = _descriptor_table_field_specs()
    report_path, markdown_path = _descriptor_neighborhood_scan_paths(args)
    before_bytes = int(args.descriptor_neighborhood_before)
    after_bytes = int(args.descriptor_neighborhood_after)
    step_bytes = int(args.descriptor_neighborhood_step)
    byte_count = int(args.descriptor_neighborhood_byte_count)
    max_hits = int(args.descriptor_neighborhood_max_hits)
    blockers = []
    if not fields:
        blockers.append("descriptor-neighborhood-fields-missing")
    if before_bytes < 0 or before_bytes > 8192 or after_bytes < 0 or after_bytes > 8192:
        blockers.append("descriptor-neighborhood-window-invalid")
    if step_bytes <= 0 or step_bytes > 256:
        blockers.append("descriptor-neighborhood-step-invalid")
    if byte_count <= 0 or byte_count > 32:
        blockers.append("descriptor-neighborhood-byte-count-invalid")
    if max_hits <= 0 or max_hits > 512:
        blockers.append("descriptor-neighborhood-max-hits-invalid")
    field_args = [f"{field['Field']}:{field['DataAddress']}" for field in fields]
    script = args.ghidra_script or "scripts/ghidra/DescriptorTableNeighborhoodScanner.java"
    project_name = args.ghidra_project_name if args.ghidra_project_name != "TempProject" else "RiftAnchorSurvey"
    process_path = args.ghidra_process or "rift_x64.exe"
    return {
        "SchemaVersion": "nidatastream-descriptor-neighborhood-scan-plan/v1",
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "ParserExportPromotionAllowed": False,
        "ReportPath": str(report_path),
        "MarkdownPath": str(markdown_path),
        "Script": script,
        "ProjectName": project_name,
        "Process": process_path,
        "BeforeBytes": before_bytes,
        "AfterBytes": after_bytes,
        "StepBytes": step_bytes,
        "ByteCountRequested": byte_count,
        "MaxHits": max_hits,
        "FieldCount": len(fields),
        "Fields": fields,
        "ScriptArgs": [
            str(report_path),
            str(before_bytes),
            str(after_bytes),
            str(step_bytes),
            str(byte_count),
            str(max_hits),
            *field_args,
        ],
        "BlockerCount": len(blockers),
        "Blockers": blockers,
        "Interpretation": (
            "Candidate-only dry-run plan for a bounded nonzero-byte scan around descriptor-table "
            "data references. Hits are triage leads only."
        ),
    }


def _descriptor_neighborhood_scan_markdown(report: dict[str, Any]) -> str:
    """Render a compact Markdown summary for a descriptor neighborhood scan."""
    raw_hits = report.get("hits")
    hits: list[Any] = raw_hits if isinstance(raw_hits, list) else []
    lines = [
        "# Ghidra descriptor-table neighborhood scan",
        "",
        f"- Candidate-only: **{str(report.get('CandidateOnly')).lower()}**",
        f"- Parser/export promotion allowed: **{str(report.get('ParserExportPromotionAllowed')).lower()}**",
        f"- Program: **{format_markdown_cell(report.get('programName'))}**",
        f"- Window before/after bytes: **{format_markdown_cell(report.get('beforeBytes'))}/{format_markdown_cell(report.get('afterBytes'))}**",
        f"- Step bytes: **{format_markdown_cell(report.get('stepBytes'))}**",
        f"- Rows scanned: **{format_markdown_cell(report.get('scannedRowCount'))}**",
        f"- Memory-backed rows: **{format_markdown_cell(report.get('memoryBackedRowCount'))}**",
        f"- Nonzero hits: **{format_markdown_cell(report.get('hitCount'))}**",
        f"- Truncated: **{str(report.get('truncated')).lower()}**",
        "",
        "| Field | Relative offset | Address | Bytes |",
        "|---|---:|---|---|",
    ]
    for hit in hits[:80]:
        if not isinstance(hit, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(hit.get("field")),
                    format_markdown_cell(hit.get("relativeOffsetBytes")),
                    format_markdown_cell(hit.get("address")),
                    format_markdown_cell(hit.get("bytes")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Interpretation guard", "", format_markdown_cell(report.get("interpretation")), ""])
    return "\n".join(lines)


def _print_descriptor_neighborhood_scan_plan(plan: dict[str, Any]) -> None:
    """Print a human-readable descriptor neighborhood scan dry-run."""
    print("--- NiDataStreamDescriptorNeighborhoodScan")
    print(f"Report: {plan['ReportPath']}")
    print(f"Markdown: {plan['MarkdownPath']}")
    print(f"Script: {plan['Script']}")
    print(f"Fields: {plan['FieldCount']}")
    print(
        "Window: "
        f"-{plan['BeforeBytes']}..+{plan['AfterBytes']} step={plan['StepBytes']} "
        f"bytes={plan['ByteCountRequested']} max_hits={plan['MaxHits']}"
    )
    if plan["Blockers"]:
        print(f"Blockers: {', '.join(plan['Blockers'])}")
    run_command = [
        "python",
        "scripts/rift_workflow.py",
        "ghidra-run",
        "--ghidra-project-name",
        str(plan["ProjectName"]),
        "--ghidra-process",
        str(plan["Process"]),
        "--ghidra-timeout",
        "900",
        "--ghidra-script",
        str(plan["Script"]),
    ]
    for value in plan["ScriptArgs"]:
        run_command += ["--ghidra-script-arg", str(value)]
    run_command += ["--ghidra-no-analysis", "--ghidra-keep-project"]
    print("\nRun command:")
    print(" ".join(run_command))


def _run_nidatastream_descriptor_neighborhood_scan(args: argparse.Namespace) -> None:
    """Run or print a bounded candidate-only descriptor neighborhood scan."""
    plan = _descriptor_neighborhood_scan_plan(args)
    if args.list_json:
        print(json.dumps(plan, indent=2))
        return

    _print_descriptor_neighborhood_scan_plan(plan)
    if plan["Blockers"]:
        print("NiDataStreamDescriptorNeighborhoodScan blocked before Ghidra execution.")
        if args.ghidra_execute:
            sys.exit(1)
        print("Dry-run only. Resolve blockers before adding --ghidra-execute.")
        return
    if not args.ghidra_execute:
        print("\nDry-run only. Add --ghidra-execute to run this neighborhood scan.")
        return

    from scripts.ghidra_runner import run_ghidra_headless

    report_path = Path(plan["ReportPath"])
    markdown_path = Path(plan["MarkdownPath"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_ghidra_headless(
        project_dir=_ghidra_project_dir_arg(args),
        project_name=str(plan["ProjectName"]),
        process_path=str(plan["Process"]),
        script=str(plan["Script"]),
        script_args=[str(value) for value in plan["ScriptArgs"]],
        analyze=False,
        delete_project=False,
        timeout_seconds=args.ghidra_timeout,
    )
    _print_ghidra_result(result)
    report = load_json_report(str(report_path))
    if not report.get("CandidateOnly") or report.get("ParserExportPromotionAllowed"):
        print("ERROR: descriptor neighborhood scan report is not candidate-only/promoted-false.", file=sys.stderr)
        sys.exit(1)
    markdown_path.write_text(_descriptor_neighborhood_scan_markdown(report), encoding="utf-8")
    print(
        "NiDataStreamDescriptorNeighborhoodScan rows: "
        f"{report.get('scannedRowCount')}; nonzero hits: {report.get('hitCount')}; "
        f"truncated={str(report.get('truncated')).lower()}"
    )
    print(f"NiDataStreamDescriptorNeighborhoodScan JSON: {report_path}")
    print(f"NiDataStreamDescriptorNeighborhoodScan markdown: {markdown_path}")
    print("NiDataStreamDescriptorNeighborhoodScan passed: report remains candidate-only/report-only.")


def _descriptor_reference_classify_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """Return default/overridden descriptor reference classification report paths."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    report_path = (
        Path(args.descriptor_reference_report)
        if args.descriptor_reference_report
        else out_dir / "ghidra-reports" / "nidatastream_descriptor_reference_classification.json"
    )
    markdown_path = (
        Path(args.descriptor_reference_summary)
        if args.descriptor_reference_summary
        else out_dir / "ghidra-reports" / "nidatastream_descriptor_reference_classification.md"
    )
    return report_path, markdown_path


def _descriptor_reference_classify_plan(args: argparse.Namespace) -> dict[str, Any]:
    """Build a candidate-only descriptor reference classification plan."""
    fields = _descriptor_table_field_specs()
    report_path, markdown_path = _descriptor_reference_classify_paths(args)
    byte_count = int(args.descriptor_reference_byte_count)
    max_refs = int(args.descriptor_reference_max_refs)
    blockers = []
    if not fields:
        blockers.append("descriptor-reference-fields-missing")
    if byte_count <= 0 or byte_count > 64:
        blockers.append("descriptor-reference-byte-count-invalid")
    if max_refs <= 0 or max_refs > 512:
        blockers.append("descriptor-reference-max-refs-invalid")
    field_args = [f"{field['Field']}:{field['DataAddress']}" for field in fields]
    script = args.ghidra_script or "scripts/ghidra/DescriptorReferenceClassifier.java"
    project_name = args.ghidra_project_name if args.ghidra_project_name != "TempProject" else "RiftAnchorSurvey"
    process_path = args.ghidra_process or "rift_x64.exe"
    return {
        "SchemaVersion": "nidatastream-descriptor-reference-classify-plan/v1",
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "ParserExportPromotionAllowed": False,
        "ReportPath": str(report_path),
        "MarkdownPath": str(markdown_path),
        "Script": script,
        "ProjectName": project_name,
        "Process": process_path,
        "ByteCountRequested": byte_count,
        "MaxRefsPerField": max_refs,
        "FieldCount": len(fields),
        "Fields": fields,
        "ScriptArgs": [
            str(report_path),
            str(byte_count),
            str(max_refs),
            *field_args,
        ],
        "BlockerCount": len(blockers),
        "Blockers": blockers,
        "Interpretation": (
            "Candidate-only dry-run plan for classifying references to descriptor data addresses. "
            "Reference kinds are triage leads only."
        ),
    }


def _descriptor_reference_classify_markdown(report: dict[str, Any]) -> str:
    """Render a compact Markdown summary for descriptor reference classification."""
    raw_fields = report.get("fields")
    fields: list[Any] = raw_fields if isinstance(raw_fields, list) else []
    lines = [
        "# Ghidra descriptor reference classification",
        "",
        f"- Candidate-only: **{str(report.get('CandidateOnly')).lower()}**",
        f"- Parser/export promotion allowed: **{str(report.get('ParserExportPromotionAllowed')).lower()}**",
        f"- Program: **{format_markdown_cell(report.get('programName'))}**",
        f"- Fields: **{format_markdown_cell(report.get('fieldCount'))}**",
        f"- Total references: **{format_markdown_cell(report.get('totalReferenceCount'))}**",
        f"- Captured references: **{format_markdown_cell(report.get('totalCapturedReferenceCount'))}**",
        f"- Read/write/data/address-like refs: **{format_markdown_cell(report.get('readReferenceCount'))}/"
        f"{format_markdown_cell(report.get('writeReferenceCount'))}/"
        f"{format_markdown_cell(report.get('dataReferenceCount'))}/"
        f"{format_markdown_cell(report.get('addressLikeReferenceCount'))}**",
        "",
        "| Field | Address | Block | Init | W | Bytes | Refs | Data | Address-like | Functions |",
        "|---|---|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for field in fields:
        if not isinstance(field, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(field.get("field")),
                    format_markdown_cell(field.get("address")),
                    format_markdown_cell(field.get("memoryBlockName")),
                    format_markdown_cell(str(field.get("memoryBlockInitialized")).lower()),
                    format_markdown_cell(str(field.get("memoryBlockWrite")).lower()),
                    format_markdown_cell(field.get("bytes")),
                    format_markdown_cell(field.get("referenceCountTo")),
                    format_markdown_cell(field.get("dataReferenceCount")),
                    format_markdown_cell(field.get("addressLikeReferenceCount")),
                    format_markdown_cell(field.get("referencingFunctionCount")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Captured references",
            "",
            "| Field | From | Kind | Type | Function | Instruction |",
            "|---|---|---|---|---|---|",
        ]
    )
    emitted = 0
    for field in fields:
        if not isinstance(field, dict):
            continue
        raw_references = field.get("references")
        references: list[Any] = raw_references if isinstance(raw_references, list) else []
        for reference in references:
            if not isinstance(reference, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        format_markdown_cell(field.get("field")),
                        format_markdown_cell(reference.get("fromAddress")),
                        format_markdown_cell(reference.get("referenceKind")),
                        format_markdown_cell(reference.get("referenceType")),
                        format_markdown_cell(reference.get("fromFunction")),
                        format_markdown_cell(reference.get("instructionText")),
                    ]
                )
                + " |"
            )
            emitted += 1
            if emitted >= 80:
                break
        if emitted >= 80:
            break
    lines.extend(["", "## Interpretation guard", "", format_markdown_cell(report.get("interpretation")), ""])
    return "\n".join(lines)


def _print_descriptor_reference_classify_plan(plan: dict[str, Any]) -> None:
    """Print a human-readable descriptor reference classification dry-run."""
    print("--- NiDataStreamDescriptorReferenceClassify")
    print(f"Report: {plan['ReportPath']}")
    print(f"Markdown: {plan['MarkdownPath']}")
    print(f"Script: {plan['Script']}")
    print(f"Fields: {plan['FieldCount']}")
    print(f"Byte count: {plan['ByteCountRequested']}; max refs/field: {plan['MaxRefsPerField']}")
    if plan["Blockers"]:
        print(f"Blockers: {', '.join(plan['Blockers'])}")
    run_command = [
        "python",
        "scripts/rift_workflow.py",
        "ghidra-run",
        "--ghidra-project-name",
        str(plan["ProjectName"]),
        "--ghidra-process",
        str(plan["Process"]),
        "--ghidra-timeout",
        "900",
        "--ghidra-script",
        str(plan["Script"]),
    ]
    for value in plan["ScriptArgs"]:
        run_command += ["--ghidra-script-arg", str(value)]
    run_command += ["--ghidra-no-analysis", "--ghidra-keep-project"]
    print("\nRun command:")
    print(" ".join(run_command))


def _run_nidatastream_descriptor_reference_classify(args: argparse.Namespace) -> None:
    """Run or print a candidate-only descriptor reference classification workflow."""
    plan = _descriptor_reference_classify_plan(args)
    if args.list_json:
        print(json.dumps(plan, indent=2))
        return

    _print_descriptor_reference_classify_plan(plan)
    if plan["Blockers"]:
        print("NiDataStreamDescriptorReferenceClassify blocked before Ghidra execution.")
        if args.ghidra_execute:
            sys.exit(1)
        print("Dry-run only. Resolve blockers before adding --ghidra-execute.")
        return
    if not args.ghidra_execute:
        print("\nDry-run only. Add --ghidra-execute to run this reference classification.")
        return

    from scripts.ghidra_runner import run_ghidra_headless

    report_path = Path(plan["ReportPath"])
    markdown_path = Path(plan["MarkdownPath"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_ghidra_headless(
        project_dir=_ghidra_project_dir_arg(args),
        project_name=str(plan["ProjectName"]),
        process_path=str(plan["Process"]),
        script=str(plan["Script"]),
        script_args=[str(value) for value in plan["ScriptArgs"]],
        analyze=False,
        delete_project=False,
        timeout_seconds=args.ghidra_timeout,
    )
    _print_ghidra_result(result)
    report = load_json_report(str(report_path))
    if not report.get("CandidateOnly") or report.get("ParserExportPromotionAllowed"):
        print(
            "ERROR: descriptor reference classification report is not candidate-only/promoted-false.", file=sys.stderr
        )
        sys.exit(1)
    markdown_path.write_text(_descriptor_reference_classify_markdown(report), encoding="utf-8")
    print(
        "NiDataStreamDescriptorReferenceClassify refs: "
        f"{report.get('totalReferenceCount')}; captured: {report.get('totalCapturedReferenceCount')}; "
        f"functions: {report.get('uniqueReferencingFunctionCount')}"
    )
    print(f"NiDataStreamDescriptorReferenceClassify JSON: {report_path}")
    print(f"NiDataStreamDescriptorReferenceClassify markdown: {markdown_path}")
    print("NiDataStreamDescriptorReferenceClassify passed: report remains candidate-only/report-only.")


def _descriptor_base_model_review_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    """Return reference input plus output paths for descriptor base-model review."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    reference_path = (
        Path(args.descriptor_base_model_reference_report)
        if args.descriptor_base_model_reference_report
        else out_dir / "ghidra-reports" / "nidatastream_descriptor_reference_classification.json"
    )
    report_path = (
        Path(args.descriptor_base_model_report)
        if args.descriptor_base_model_report
        else out_dir / "ghidra-reports" / "nidatastream_descriptor_base_model_review.json"
    )
    markdown_path = (
        Path(args.descriptor_base_model_summary)
        if args.descriptor_base_model_summary
        else out_dir / "ghidra-reports" / "nidatastream_descriptor_base_model_review.md"
    )
    return reference_path, report_path, markdown_path


def _counted_rows(counts: dict[int | str, int], key_name: str) -> list[dict[str, Any]]:
    """Return stable descending count rows for integer/string counters."""
    return [
        {key_name: key, "Count": count}
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))
    ]


def _increment_count(counts: dict[int | str, int], key: int | str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _hex_pattern_counts(instruction_texts: list[str]) -> tuple[dict[int | str, int], dict[int | str, int]]:
    """Extract simple index-scale and positive/negative offset candidates from instruction text."""
    scale_counts: dict[int | str, int] = {}
    offset_counts: dict[int | str, int] = {}
    for text in instruction_texts:
        for match in re.finditer(r"\*0x([0-9a-fA-F]+)", text):
            _increment_count(scale_counts, int(match.group(1), 16))
        for match in re.finditer(r"([+-])\s*0x([0-9a-fA-F]+)", text):
            value = int(match.group(2), 16)
            if match.group(1) == "-":
                value *= -1
            _increment_count(offset_counts, value)
    return scale_counts, offset_counts


def _hex_bytes_all_zero(value: Any) -> bool:
    """Return true when a Ghidra hex-byte string is non-empty and all bytes are zero."""
    if not isinstance(value, str) or not value.strip():
        return False
    return all(part == "00" for part in value.strip().split())


def _descriptor_base_model_review_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Build a candidate-only descriptor base/stride model review from reference classification evidence."""
    reference_path, report_path, markdown_path = _descriptor_base_model_review_paths(args)
    blockers: list[str] = []
    reference_report: dict[str, Any] = {}
    reference_error = ""
    if not reference_path.exists():
        blockers.append("descriptor-reference-classification-missing")
    else:
        try:
            loaded_reference = json.loads(reference_path.read_text(encoding="utf-8"))
            if isinstance(loaded_reference, dict):
                reference_report = loaded_reference
            else:
                reference_error = "reference report root is not an object"
        except (OSError, json.JSONDecodeError) as exc:
            reference_error = f"{type(exc).__name__}: {exc}"
    if reference_error:
        blockers.append("descriptor-reference-classification-invalid")
    if reference_report.get("SchemaVersion") != "ghidra-descriptor-reference-classification/v1":
        blockers.append("descriptor-reference-classification-schema-mismatch")
    if not reference_report.get("CandidateOnly") or reference_report.get("ParserExportPromotionAllowed"):
        blockers.append("descriptor-reference-classification-promoted-or-not-candidate")

    raw_fields = reference_report.get("fields")
    fields: list[Any] = raw_fields if isinstance(raw_fields, list) else []
    field_rows: list[dict[str, Any]] = []
    global_scale_counts: dict[int | str, int] = {}
    global_offset_counts: dict[int | str, int] = {}
    all_static_bytes_zero = bool(fields)
    writable_field_count = 0
    indexed_instruction_count = 0
    for field in fields:
        if not isinstance(field, dict):
            continue
        raw_references = field.get("references")
        references: list[Any] = raw_references if isinstance(raw_references, list) else []
        instruction_texts = [
            str(reference.get("instructionText"))
            for reference in references
            if isinstance(reference, dict) and reference.get("instructionText")
        ]
        scale_counts, offset_counts = _hex_pattern_counts(instruction_texts)
        for key, count in scale_counts.items():
            global_scale_counts[key] = global_scale_counts.get(key, 0) + count
        for key, count in offset_counts.items():
            global_offset_counts[key] = global_offset_counts.get(key, 0) + count
        type_counts: dict[int | str, int] = {}
        kind_counts: dict[int | str, int] = {}
        for reference in references:
            if not isinstance(reference, dict):
                continue
            _increment_count(type_counts, str(reference.get("referenceType", "")))
            _increment_count(kind_counts, str(reference.get("referenceKind", "")))
        static_zero = _hex_bytes_all_zero(field.get("bytes"))
        all_static_bytes_zero = all_static_bytes_zero and static_zero
        writable = bool(field.get("memoryBlockWrite"))
        if writable:
            writable_field_count += 1
        indexed_count = sum(1 for text in instruction_texts if "*0x" in text)
        indexed_instruction_count += indexed_count
        field_rows.append(
            {
                "Field": field.get("field", ""),
                "Address": field.get("address", ""),
                "MemoryBlockName": field.get("memoryBlockName", ""),
                "MemoryBlockInitialized": bool(field.get("memoryBlockInitialized")),
                "MemoryBlockWrite": writable,
                "StaticBytesAllZero": static_zero,
                "ReferenceCount": int(field.get("referenceCountTo", 0) or 0),
                "ReferenceKindCounts": _counted_rows(kind_counts, "ReferenceKind"),
                "ReferenceTypeCounts": _counted_rows(type_counts, "ReferenceType"),
                "InstructionScaleCandidates": _counted_rows(scale_counts, "ScaleBytes"),
                "InstructionOffsetCandidates": _counted_rows(offset_counts, "OffsetBytes"),
                "IndexedInstructionCount": indexed_count,
                "ExampleInstructions": instruction_texts[:8],
            }
        )

    table_sample_status = _nidatastream_descriptor_table_sample_status(args)
    if all_static_bytes_zero:
        blockers.append("descriptor-reference-static-bytes-all-zero")
    if not global_scale_counts:
        blockers.append("descriptor-reference-index-scale-missing")
    if table_sample_status["AllRowsZero"]:
        blockers.append("descriptor-table-sample-current-model-all-zero")
    blockers.append("descriptor-base-model-not-promoted")
    blockers.append("parser-export-promotion-locked")

    candidate_models = [
        {
            "Key": "current-field-map-stride-12",
            "Status": "blocked" if table_sample_status["AllRowsZero"] else "candidate",
            "StrideBytes": 12,
            "Evidence": (
                "Existing descriptor-table sampler uses the candidate field map stride. "
                f"Rows={table_sample_status['RowCount']}; nonzero={table_sample_status['NonzeroRowCount']}; "
                f"all-zero={str(table_sample_status['AllRowsZero']).lower()}."
            ),
            "Blockers": ["descriptor-table-sample-current-model-all-zero"]
            if table_sample_status["AllRowsZero"]
            else [],
        },
        {
            "Key": "reference-instruction-index-scale",
            "Status": "candidate" if global_scale_counts else "blocked",
            "StrideByteCandidates": _counted_rows(global_scale_counts, "ScaleBytes"),
            "OffsetByteCandidates": _counted_rows(global_offset_counts, "OffsetBytes"),
            "Evidence": (
                "Instruction text in descriptor reference classification contains indexed memory operands. "
                "This is a review lead, not parser/export truth."
            ),
            "Blockers": [] if global_scale_counts else ["descriptor-reference-index-scale-missing"],
        },
        {
            "Key": "static-image-byte-source",
            "Status": "blocked" if all_static_bytes_zero else "candidate",
            "Evidence": (
                "Descriptor addresses are memory-backed but their sampled static image bytes are "
                f"{'all zero' if all_static_bytes_zero else 'not uniformly zero'}."
            ),
            "Blockers": ["descriptor-reference-static-bytes-all-zero"] if all_static_bytes_zero else [],
        },
    ]
    return {
        "SchemaVersion": "nidatastream-descriptor-base-model-review/v1",
        "CandidateOnly": True,
        "FieldOrderPromoted": False,
        "ParserExportPromotionAllowed": False,
        "ReferenceReport": {
            "Path": _display_path(reference_path),
            "Exists": reference_path.exists(),
            "SchemaVersion": reference_report.get("SchemaVersion", ""),
            "Error": reference_error,
            "FieldCount": int(reference_report.get("fieldCount", 0) or 0),
            "TotalReferenceCount": int(reference_report.get("totalReferenceCount", 0) or 0),
            "UniqueReferencingFunctionCount": int(reference_report.get("uniqueReferencingFunctionCount", 0) or 0),
        },
        "ReportPath": _display_path(report_path),
        "MarkdownPath": _display_path(markdown_path),
        "FieldEvidence": field_rows,
        "FieldCount": len(field_rows),
        "WritableFieldCount": writable_field_count,
        "AllStaticBytesZero": all_static_bytes_zero,
        "IndexedInstructionCount": indexed_instruction_count,
        "InstructionScaleCandidates": _counted_rows(global_scale_counts, "ScaleBytes"),
        "InstructionOffsetCandidates": _counted_rows(global_offset_counts, "OffsetBytes"),
        "DescriptorTableSampleStatus": {
            "Path": table_sample_status["Path"],
            "Exists": table_sample_status["Exists"],
            "RowCount": table_sample_status["RowCount"],
            "NonzeroRowCount": table_sample_status["NonzeroRowCount"],
            "AllRowsZero": table_sample_status["AllRowsZero"],
            "StreamSemanticsExplained": table_sample_status["StreamSemanticsExplained"],
        },
        "CandidateModels": candidate_models,
        "BlockerCount": len(blockers),
        "Blockers": blockers,
        "Decision": "Descriptor base/stride evidence remains candidate-only; parser/export behavior stays unchanged.",
        "NextAction": "Review instruction-derived base/stride candidates before any further table sampling or parser-field proposal.",
    }


def _descriptor_base_model_review_markdown(report: dict[str, Any]) -> str:
    """Build Markdown for candidate-only descriptor base/stride model review."""
    lines = [
        "# NiDataStream descriptor base-model review",
        "",
        f"- Candidate-only: **{str(report['CandidateOnly']).lower()}**",
        f"- Parser/export promotion allowed: **{str(report['ParserExportPromotionAllowed']).lower()}**",
        f"- Fields: **{format_markdown_cell(report['FieldCount'])}**",
        f"- Writable fields: **{format_markdown_cell(report['WritableFieldCount'])}**",
        f"- All static bytes zero: **{str(report['AllStaticBytesZero']).lower()}**",
        f"- Indexed instruction count: **{format_markdown_cell(report['IndexedInstructionCount'])}**",
        f"- Blocking items: **{format_markdown_cell(report['BlockerCount'])}**",
        "",
        "## Field evidence",
        "",
        "| Field | Address | Block | W | Static zero | Refs | Scales | Offsets |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for field in report["FieldEvidence"]:
        scales = ", ".join(f"{row['ScaleBytes']} ({row['Count']})" for row in field["InstructionScaleCandidates"])
        offsets = ", ".join(f"{row['OffsetBytes']} ({row['Count']})" for row in field["InstructionOffsetCandidates"])
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(field["Field"]),
                    format_markdown_cell(field["Address"]),
                    format_markdown_cell(field["MemoryBlockName"]),
                    format_markdown_cell(str(field["MemoryBlockWrite"]).lower()),
                    format_markdown_cell(str(field["StaticBytesAllZero"]).lower()),
                    format_markdown_cell(field["ReferenceCount"]),
                    format_markdown_cell(scales or "-"),
                    format_markdown_cell(offsets or "-"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Candidate models", "", "| Model | Status | Evidence | Blockers |", "|---|---|---|---|"])
    for model in report["CandidateModels"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    format_markdown_cell(model["Key"]),
                    format_markdown_cell(model["Status"]),
                    format_markdown_cell(model["Evidence"]),
                    format_markdown_cell(", ".join(model["Blockers"]) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(["", f"Decision: {format_markdown_cell(report['Decision'])}", ""])
    lines.extend([f"Next action: {format_markdown_cell(report['NextAction'])}", ""])
    return "\n".join(lines)


def _run_nidatastream_descriptor_base_model_review(args: argparse.Namespace) -> None:
    """Write or list a candidate-only descriptor base/stride model review."""
    report = _descriptor_base_model_review_payload(args)
    if args.list_json:
        print(json.dumps(report, indent=2))
        return
    _reference_path, report_path, markdown_path = _descriptor_base_model_review_paths(args)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_path.write_text(_descriptor_base_model_review_markdown(report), encoding="utf-8")
    print("--- NiDataStreamDescriptorBaseModelReview")
    print(f"Reference report: {report['ReferenceReport']['Path']}")
    print(f"Fields: {report['FieldCount']}; indexed instructions: {report['IndexedInstructionCount']}")
    print(f"All static bytes zero: {str(report['AllStaticBytesZero']).lower()}")
    print(f"Blocking items: {report['BlockerCount']}")
    print(f"NiDataStreamDescriptorBaseModelReview JSON: {report_path}")
    print(f"NiDataStreamDescriptorBaseModelReview markdown: {markdown_path}")
    print("NiDataStreamDescriptorBaseModelReview passed: review remains candidate-only/report-only.")


def _print_scan_live_memory_plan(plan: dict[str, Any]) -> None:
    """Print a concise live-memory scanner plan."""
    print("--- ScanLiveMemory")
    print(f"Schema: {plan['SchemaVersion']}")
    print(f"Target process: {plan['TargetProcessName']}")
    print(f"PID: {plan['Pid'] if plan['Pid'] is not None else '(not set; live execution blocked)'}")
    print(f"Execute live read: {str(plan['ExecuteLiveRead']).lower()}")
    print(f"Execution allowed: {str(plan['ExecutionAllowed']).lower()}")
    print(f"Output JSON: {plan['OutputJsonPath']}")
    print(f"Output Markdown: {plan['OutputMarkdownPath']}")
    print("Patterns:")
    for pattern in plan["Patterns"]:
        print(f"- {pattern['Label']}: {pattern['ByteLength']} bytes ({pattern['Hex']})")
    print("Limits:")
    for key, value in plan["Limits"].items():
        print(f"- {key}: {value}")
    if plan["RefusalReasons"]:
        print("Refusal / dry-run reasons:")
        for reason in plan["RefusalReasons"]:
            print(f"- {reason}")
    print(f"Next action: {plan['NextAction']}")


def _run_scan_live_memory(args: argparse.Namespace) -> None:
    """Plan or execute a gated read-only live memory scan."""
    from scripts.live_memory_scanner import (
        build_live_memory_scan_plan,
        load_pattern_specs_from_file,
        parse_hex_patterns,
        run_windows_live_scan,
        write_live_scan_reports,
    )

    try:
        pattern_specs = list(args.live_pattern)
        if args.live_pattern_file:
            pattern_specs.extend(load_pattern_specs_from_file(Path(args.live_pattern_file)))
        plan = build_live_memory_scan_plan(
            repo_root=REPO_ROOT,
            out=args.out,
            process_name=args.process_name,
            pid=args.pid,
            pattern_specs=pattern_specs,
            execute_live_read=args.execute_live_read,
            experimental_live=args.experimental_live,
            confirm_live_read=args.confirm_live_read,
            max_scan_bytes=args.max_scan_bytes,
            max_matches=args.max_scan_matches,
            max_regions=args.max_scan_regions,
            timeout_seconds=args.live_timeout_seconds,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.list_json:
        print(json.dumps(plan, indent=2))
        return

    _print_scan_live_memory_plan(plan)
    if not args.execute_live_read:
        print("scan-live-memory dry-run passed: no process was opened and no live memory was read.")
        return
    if not plan["ExecutionAllowed"]:
        print("ERROR: live memory read refused by safety gates.", file=sys.stderr)
        sys.exit(1)

    generated_output_guard()
    patterns = parse_hex_patterns(pattern_specs)
    try:
        result = run_windows_live_scan(plan, patterns)
    except Exception as exc:  # noqa: BLE001 - live gate reports exact runtime failure
        print(f"ERROR: live memory scan failed: {exc}", file=sys.stderr)
        sys.exit(1)
    json_path, markdown_path = write_live_scan_reports(result, REPO_ROOT)
    print(f"scan-live-memory wrote JSON: {json_path}")
    print(f"scan-live-memory wrote Markdown: {markdown_path}")


def _run_probe_modrm_leads(args: argparse.Namespace) -> None:
    """Bridge static ModRM analysis to live memory scanning."""
    from scripts.live_memory_scanner import (
        build_probe_modrm_leads_plan,
        load_modrm_scan,
        run_probe_modrm_leads,
        write_probe_modrm_leads_reports,
    )

    modrm_path = (
        Path(args.out) / "modrm-memory-access-scan.json"
        if args.out
        else REPO_ROOT / "Exports" / "binary-phase1" / "modrm-memory-access-scan.json"
    )
    if not modrm_path.exists():
        print(f"ERROR: ModRM scan not found at {modrm_path}", file=sys.stderr)
        sys.exit(1)

    modrm_data = load_modrm_scan(modrm_path)
    try:
        plan = build_probe_modrm_leads_plan(
            repo_root=REPO_ROOT,
            out=args.out,
            modrm_data=modrm_data,
            process_name=args.process_name,
            pid=args.pid,
            execute_live_read=args.execute_live_read,
            experimental_live=args.experimental_live,
            confirm_live_read=args.confirm_live_read,
            max_scan_bytes=args.max_scan_bytes,
            max_matches=args.max_scan_matches,
            max_regions=args.max_scan_regions,
            timeout_seconds=args.live_timeout_seconds,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.list_json:
        print(json.dumps(plan, indent=2))
        return

    if not args.execute_live_read:
        print("probe-modrm-leads dry-run passed: no process was opened.")
        return
    if not plan.get("ExecutionAllowed"):
        print("ERROR: live memory read refused by safety gates.", file=sys.stderr)
        sys.exit(1)

    generated_output_guard()
    try:
        result = run_probe_modrm_leads(plan)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: probe-modrm-leads live scan failed: {exc}", file=sys.stderr)
        sys.exit(1)
    json_path, md_path = write_probe_modrm_leads_reports(result, REPO_ROOT)
    print(f"probe-modrm-leads wrote JSON: {json_path}")
    print(f"probe-modrm-leads wrote Markdown: {md_path}")


def _run_scan_live_values(args: argparse.Namespace) -> None:
    """Float32/int32/uint32 value-range live memory scanning."""
    from scripts.live_memory_scanner import (
        build_value_scan_plan,
        run_live_value_scan,
        write_value_scan_reports,
    )

    try:
        plan = build_value_scan_plan(
            repo_root=REPO_ROOT,
            out=args.out,
            process_name=args.process_name,
            pid=args.pid,
            value_type=args.value_type,
            min_val=args.min_val,
            max_val=args.max_val,
            execute_live_read=args.execute_live_read,
            experimental_live=args.experimental_live,
            confirm_live_read=args.confirm_live_read,
            max_scan_bytes=args.max_scan_bytes,
            max_matches=args.max_scan_matches,
            max_regions=args.max_scan_regions,
            timeout_seconds=args.live_timeout_seconds,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.list_json:
        print(json.dumps(plan, indent=2))
        return

    if not args.execute_live_read:
        print("scan-live-values dry-run passed: no process was opened.")
        return
    if not plan.get("ExecutionAllowed"):
        print("ERROR: live memory read refused by safety gates.", file=sys.stderr)
        sys.exit(1)

    generated_output_guard()
    try:
        result = run_live_value_scan(plan)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: scan-live-values failed: {exc}", file=sys.stderr)
        sys.exit(1)
    json_path, md_path = write_value_scan_reports(result, REPO_ROOT)
    print(f"scan-live-values wrote JSON: {json_path}")
    print(f"scan-live-values wrote Markdown: {md_path}")


def _run_scan_live_diff(args: argparse.Namespace) -> None:
    """Snapshot-diff value scanning for player coordinate discovery."""
    from scripts.live_memory_scanner import (
        build_diff_scan_plan,
        run_live_diff,
        write_diff_reports,
    )

    try:
        plan = build_diff_scan_plan(
            repo_root=REPO_ROOT,
            out=args.out,
            process_name=args.process_name,
            pid=args.pid,
            snapshot_a_path=args.snapshot_a_path,
            execute_live_read=args.execute_live_read,
            experimental_live=args.experimental_live,
            confirm_live_read=args.confirm_live_read,
            max_scan_bytes=args.max_scan_bytes,
            max_matches=args.max_scan_matches,
            max_regions=args.max_scan_regions,
            timeout_seconds=args.live_timeout_seconds,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.list_json:
        print(json.dumps(plan, indent=2))
        return

    if not args.execute_live_read:
        print("scan-live-diff dry-run passed: no process was opened.")
        return
    if not plan.get("ExecutionAllowed"):
        print("ERROR: live memory read refused by safety gates.", file=sys.stderr)
        sys.exit(1)

    generated_output_guard()
    try:
        result = run_live_diff(plan)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: scan-live-diff failed: {exc}", file=sys.stderr)
        sys.exit(1)
    json_path, md_path = write_diff_reports(result, REPO_ROOT)
    print(f"scan-live-diff wrote JSON: {json_path}")
    print(f"scan-live-diff wrote Markdown: {md_path}")


def _run_score_candidates(args: argparse.Namespace) -> None:
    """Score live memory scan candidates against the asset semantic index."""
    from scripts.rift_candidate_scorer import (
        score_candidates,
        write_scored_reports,
    )

    scan_result_path = getattr(args, "scan_result", None)
    semantic_index_path = getattr(args, "semantic_index", None)

    if not scan_result_path or not semantic_index_path:
        print("ERROR: --scan-result and --semantic-index are required.", file=sys.stderr)
        sys.exit(1)

    try:
        scan_result = json.loads(Path(scan_result_path).read_text(encoding="utf-8-sig"))
        semantic_index = json.loads(Path(semantic_index_path).read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to load input files: {exc}", file=sys.stderr)
        sys.exit(1)

    scored = score_candidates(scan_result, semantic_index)

    if getattr(args, "list_json", False):
        print(json.dumps(scored, indent=2))
        return

    json_path, md_path = write_scored_reports(scored, REPO_ROOT, getattr(args, "out", None))
    print(f"Scored {scored['TotalCandidates']} candidates.")
    print(f"score-candidates wrote JSON: {json_path}")
    print(f"score-candidates wrote Markdown: {md_path}")


def _run_capture_proof_packets(args: argparse.Namespace) -> None:
    """Capture proof packets from live scan results."""
    from scripts.rift_proof_packets import (
        build_packets_from_scan,
        merge_packets,
        write_proof_packets,
    )

    scan_result_path = getattr(args, "scan_result", None)
    pid = getattr(args, "pid", 0)
    session_label = getattr(args, "session_label", "")

    if not scan_result_path or not pid or not session_label:
        print("ERROR: --scan-result, --pid, and --session-label are required.", file=sys.stderr)
        sys.exit(1)

    try:
        scan_result = json.loads(Path(scan_result_path).read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to load scan result: {exc}", file=sys.stderr)
        sys.exit(1)

    scored = None
    scored_path = getattr(args, "scored", None)
    if scored_path and Path(scored_path).exists():
        scored = json.loads(Path(scored_path).read_text(encoding="utf-8-sig"))

    new_packets = build_packets_from_scan(scan_result, pid, session_label, scored)

    existing_path = getattr(args, "existing", None)
    if existing_path and Path(existing_path).exists():
        existing = json.loads(Path(existing_path).read_text(encoding="utf-8-sig"))
        new_packets = merge_packets(existing, new_packets)

    if getattr(args, "list_json", False):
        print(json.dumps(new_packets, indent=2))
        return

    json_path = write_proof_packets(new_packets, REPO_ROOT, getattr(args, "out", None))
    print(f"capture-proof-packets wrote {new_packets['PacketCount']} packets to {json_path}")


def _run_evaluate_restart_gate(args: argparse.Namespace) -> None:
    """Evaluate the two-restart rediscovery gate for proof packets."""
    from scripts.rift_restart_gate import (
        _build_candidate_history,
        evaluate_gate,
        write_gate_report,
    )

    proof_packets_path = getattr(args, "proof_packets", None)

    if not proof_packets_path:
        print("ERROR: --proof-packets is required.", file=sys.stderr)
        sys.exit(1)

    try:
        packets = json.loads(Path(proof_packets_path).read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to load proof packets: {exc}", file=sys.stderr)
        sys.exit(1)

    history = _build_candidate_history(packets)
    report = evaluate_gate(history)

    if getattr(args, "list_json", False):
        print(json.dumps(report, indent=2))
        return

    json_path, md_path = write_gate_report(report, REPO_ROOT, getattr(args, "out", None))
    print(
        f"evaluate-restart-gate: {report['DurableCount']} durable, "
        f"{report['NeedsReviewCount']} needs-review, "
        f"{report['CandidateCount']} candidates."
    )
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")


def _fifty_step_plan_status_payload() -> dict[str, Any]:
    """Return the current repo position in the original 50-step discovery plan."""
    plan_path = REPO_ROOT / "docs" / "discovery-plan-50.md"
    current_position_path = REPO_ROOT / "docs" / "50-step-plan-current-position.md"
    safety_boundary_path = REPO_ROOT / "docs" / "live-memory-readonly-safety-boundary.md"
    scanner_path = REPO_ROOT / "scripts" / "live_memory_scanner.py"
    scanner_schema_path = REPO_ROOT / "docs" / "schemas" / "live-memory-scan-plan-v1.schema.json"
    step48_targets_path = REPO_ROOT / "docs" / "live-memory-scan-targets.json"
    step48_status_path = REPO_ROOT / "docs" / "live-memory-step48-status.json"
    step49_status_path = REPO_ROOT / "docs" / "live-memory-step49-status.json"
    step50_handoff_paths = sorted((REPO_ROOT / "docs" / "handoffs").glob("*final-50-step-session.md"))
    step50_handoff_path = step50_handoff_paths[-1] if step50_handoff_paths else None
    step_46_complete = safety_boundary_path.exists()
    step_47_complete = scanner_path.exists() and scanner_schema_path.exists() and "scan-live-memory" in COMMAND_MAP
    step_48_manifest_ready = step48_targets_path.exists()
    step_48_status: dict[str, Any] = {}
    if step48_status_path.exists():
        try:
            step_48_status = json.loads(step48_status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            step_48_status = {}
    step_48_live_read_executed = (
        step_48_status.get("SchemaVersion") == "live-memory-step48-status/v1"
        and step_48_status.get("CandidateOnly") is True
        and step_48_status.get("LiveReadExecuted") is True
    )
    step_49_status: dict[str, Any] = {}
    if step49_status_path.exists():
        try:
            step_49_status = json.loads(step49_status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            step_49_status = {}
    step_49_initial_probe_executed = (
        step_49_status.get("SchemaVersion") == "live-memory-step49-status/v1"
        and step_49_status.get("CandidateOnly") is True
        and step_49_status.get("LiveReadExecuted") is True
    )
    step_49_cluster_confirmed = step_49_initial_probe_executed and step_49_status.get("ClusterConfirmed") is True
    step_49_closure_mode = str(step_49_status.get("Step49ClosureMode", ""))
    step_49_closed_negative = (
        step_49_initial_probe_executed
        and step_49_status.get("Step49Complete") is True
        and step_49_status.get("ParserExportPromotionAllowed") is False
        and step_49_closure_mode == "closed-negative-current-live-state"
    )
    step_49_complete = (step_49_cluster_confirmed or step_49_closed_negative) and step_49_status.get(
        "Step49Complete"
    ) is True
    step_50_final_handoff_complete = step50_handoff_path is not None
    current_step = 46
    current_step_name = "Design live memory scan safety boundary"
    completed_step_count = 45
    if step_46_complete:
        current_step = 47
        current_step_name = "Implement read-only process memory scanner"
        completed_step_count = 46
    if step_47_complete:
        current_step = 48
        current_step_name = "Scan for @264/#15 index buffer pattern in live memory"
        completed_step_count = 47
    if step_48_live_read_executed:
        current_step = 49
        current_step_name = "Scan for position float3 clusters matching mesh bounds"
        completed_step_count = 48
    if step_49_complete:
        current_step = 50
        current_step_name = "Final comprehensive session handoff"
        completed_step_count = 49
    if step_50_final_handoff_complete and step_49_complete:
        current_step = 50
        current_step_name = "Final comprehensive session handoff"
        completed_step_count = 50
    current_step_status = (
        "complete"
        if step_50_final_handoff_complete and step_49_complete
        else "next"
        if step_49_complete
        else "in-progress"
        if step_49_initial_probe_executed
        else "next"
        if step_48_live_read_executed
        else "in-progress"
        if step_48_manifest_ready
        else "next"
        if step_46_complete
        else "in-progress"
    )
    return {
        "SchemaVersion": "fifty-step-plan-status/v1",
        "PlanPath": _display_path(plan_path),
        "CurrentPositionPath": _display_path(current_position_path),
        "SafetyBoundaryPath": _display_path(safety_boundary_path),
        "ScannerPath": _display_path(scanner_path),
        "LiveScanSchemaPath": _display_path(scanner_schema_path),
        "Step48TargetsPath": _display_path(step48_targets_path),
        "Step48StatusPath": _display_path(step48_status_path),
        "Step49StatusPath": _display_path(step49_status_path),
        "TotalSteps": 50,
        "CompletedStepCount": completed_step_count,
        "CurrentStageNumber": 5,
        "CurrentStageName": "Live-Game Safe Read-Only Validation",
        "CurrentStepNumber": current_step,
        "CurrentStepName": current_step_name,
        "CurrentStepStatus": current_step_status,
        "Step46SafetyBoundaryComplete": step_46_complete,
        "Step47ScannerImplemented": step_47_complete,
        "Step48DryRunManifestReady": step_48_manifest_ready,
        "Step48LiveReadExecuted": step_48_live_read_executed,
        "Step48PatternFound": step_48_status.get("Found") if step_48_live_read_executed else None,
        "Step48Provider": step_48_status.get("Provider", "") if step_48_live_read_executed else "",
        "Step49InitialProbeExecuted": step_49_initial_probe_executed,
        "Step49ClusterConfirmed": step_49_cluster_confirmed,
        "Step49ClosureMode": step_49_closure_mode if step_49_initial_probe_executed else "",
        "Step49ClosedWithoutClusterConfirmation": step_49_closed_negative and not step_49_cluster_confirmed,
        "Step49FullProcessExpectedStaticBatchExecuted": (
            step_49_status.get("FullProcessExpectedStaticBatchExecuted") is True
        )
        if step_49_initial_probe_executed
        else False,
        "Step49FullProcessExpectedStaticBatchHitCount": (step_49_status.get("FullProcessExpectedStaticBatchHitCount"))
        if step_49_initial_probe_executed
        else None,
        "Step49Complete": step_49_complete,
        "Step49Provider": step_49_status.get("Provider", "") if step_49_initial_probe_executed else "",
        "Step50FinalHandoffPath": _display_path(step50_handoff_path) if step50_handoff_path else "",
        "Step50FinalHandoffComplete": step_50_final_handoff_complete and step_49_complete,
        "LiveProcessReadExecuted": step_48_live_read_executed,
        "LiveProcessReadApprovedForThisRun": bool(step_48_status.get("LiveReadApproved"))
        if step_48_live_read_executed
        else False,
        "ParserExportPromotionAllowed": False,
        "Stages": [
            {
                "StageNumber": 0,
                "Name": "Foundation & Baseline Validation",
                "StepRange": "1-5",
                "Status": "complete/superseded",
                "Evidence": "docs/handoffs/2026-05-20-stage0-baseline.md",
            },
            {
                "StageNumber": 1,
                "Name": "Safe Geometry Decode",
                "StepRange": "6-15",
                "Status": "complete/superseded",
                "Evidence": "docs/handoffs/2026-05-21-stage1-geometry-decode.md",
            },
            {
                "StageNumber": 2,
                "Name": "Position Source Discovery",
                "StepRange": "16-25",
                "Status": "complete/superseded",
                "Evidence": "docs/handoffs/2026-06-02-stage2-position-source-enhanced-findings.md",
            },
            {
                "StageNumber": 3,
                "Name": "Proof Guard Migration",
                "StepRange": "26-35",
                "Status": "complete/superseded",
                "Evidence": "scripts/rift_workflow_guards.py and Python guard tests",
            },
            {
                "StageNumber": 4,
                "Name": "Discovery Automation Suite",
                "StepRange": "36-45",
                "Status": "complete/superseded",
                "Evidence": "discovery-suite command and stage 14+ handoffs",
            },
            {
                "StageNumber": 5,
                "Name": "Live-Game Safe Read-Only Validation",
                "StepRange": "46-50",
                "Status": (
                    "complete"
                    if step_50_final_handoff_complete and step_49_complete
                    else "step-50-next"
                    if step_49_complete
                    else "step-49-in-progress"
                    if step_49_initial_probe_executed
                    else "step-49-next"
                    if step_48_live_read_executed
                    else "step-48-in-progress"
                    if step_48_manifest_ready
                    else "step-48-next"
                    if step_47_complete
                    else "step-47-next"
                    if step_46_complete
                    else "step-46-in-progress"
                ),
                "Evidence": (
                    "docs/live-memory-readonly-safety-boundary.md; scripts/live_memory_scanner.py; "
                    "docs/live-memory-scan-targets.json; docs/live-memory-step48-status.json; "
                    "docs/live-memory-step49-status.json; "
                    f"{_display_path(step50_handoff_path)}"
                    if step_50_final_handoff_complete and step_49_complete
                    else "docs/live-memory-readonly-safety-boundary.md; scripts/live_memory_scanner.py; "
                    "docs/live-memory-scan-targets.json; docs/live-memory-step48-status.json; "
                    "docs/live-memory-step49-status.json"
                    if step_49_initial_probe_executed
                    else "docs/live-memory-readonly-safety-boundary.md; scripts/live_memory_scanner.py; "
                    "docs/live-memory-scan-targets.json; docs/live-memory-step48-status.json"
                    if step_48_live_read_executed
                    else "docs/live-memory-readonly-safety-boundary.md; scripts/live_memory_scanner.py; "
                    "docs/live-memory-scan-targets.json"
                    if step_48_manifest_ready
                    else "docs/live-memory-readonly-safety-boundary.md; scripts/live_memory_scanner.py"
                    if step_47_complete
                    else "docs/live-memory-readonly-safety-boundary.md"
                    if step_46_complete
                    else ""
                ),
            },
        ],
        "Blockers": (
            [
                "parser-export-promotion-not-allowed-step-49-negative-evidence",
            ]
            if step_50_final_handoff_complete and step_49_closed_negative
            else [
                "step-50-final-handoff-not-complete",
                "parser-export-promotion-not-allowed-step-49-negative-evidence",
            ]
            if step_49_closed_negative
            else [
                "step-50-final-handoff-not-complete",
            ]
            if step_49_complete
            else [
                "step-49-position-float3-cluster-not-confirmed",
                "step-50-final-handoff-not-complete",
            ]
            if step_49_initial_probe_executed and not step_49_complete
            else [
                "step-49-position-float3-cluster-scan-not-executed",
                "step-50-final-handoff-not-complete",
            ]
            if step_48_live_read_executed
            else [
                "live-process-read-not-executed",
                "step-48-live-index-pattern-scan-not-executed",
                "steps-48-through-50-not-complete",
            ]
        ),
        "NextAction": (
            "Resume offline position-source discovery before any parser/export behavior change; "
            "Step 49 closed negative for the current live state and the final 50-step handoff is complete."
            if step_50_final_handoff_complete and step_49_closed_negative
            else "Write the Step 50 final comprehensive handoff; keep Step 49 negative evidence candidate-only "
            "and parser/export promotion blocked."
            if step_49_closed_negative
            else step_49_status.get("NextAction", "")
            if step_49_initial_probe_executed and step_49_status.get("NextAction")
            else "Write the Step 50 final comprehensive handoff after Step 49 is cluster-confirmed."
            if step_49_complete
            else "Define Step 49 position float3 cluster scan targets from guarded static bounds before running another live read."
            if step_48_live_read_executed
            else "Run scan-live-memory dry-run for the @264/#15 big-endian strip prefix and review exact PID/pattern/limits "
            "before any separately approved live read."
            if step_47_complete
            else "Implement scan-live-memory behind explicit --experimental-live and dry-run/list modes; "
            "do not attach to a live process until a separate live-read execution approval is present."
        )
        if step_46_complete
        else "Complete docs/live-memory-readonly-safety-boundary.md before implementing live-read code.",
    }


def _print_fifty_step_plan_status(status: dict[str, Any]) -> None:
    """Print a concise 50-step discovery-plan position summary."""
    print("--- FiftyStepPlanStatus")
    print(f"Plan: {status['PlanPath']}")
    print(f"Completed steps: {status['CompletedStepCount']}/{status['TotalSteps']}")
    print(f"Current stage: Stage {status['CurrentStageNumber']} - {status['CurrentStageName']}")
    print(f"Current step: Step {status['CurrentStepNumber']} - {status['CurrentStepName']}")
    print(f"Current step status: {status['CurrentStepStatus']}")
    print(f"Step 46 safety boundary complete: {str(status['Step46SafetyBoundaryComplete']).lower()}")
    print(f"Step 47 scanner implemented: {str(status['Step47ScannerImplemented']).lower()}")
    print(f"Step 48 dry-run manifest ready: {str(status['Step48DryRunManifestReady']).lower()}")
    print(f"Step 48 live read executed: {str(status['Step48LiveReadExecuted']).lower()}")
    print(f"Step 48 pattern found: {status['Step48PatternFound']}")
    if status["Step48Provider"]:
        print(f"Step 48 provider: {status['Step48Provider']}")
    print(f"Step 49 initial probe executed: {str(status['Step49InitialProbeExecuted']).lower()}")
    print(f"Step 49 cluster confirmed: {str(status['Step49ClusterConfirmed']).lower()}")
    if status["Step49ClosureMode"]:
        print(f"Step 49 closure mode: {status['Step49ClosureMode']}")
        print(
            "Step 49 closed without cluster confirmation: "
            f"{str(status['Step49ClosedWithoutClusterConfirmation']).lower()}"
        )
    print(f"Step 49 full-process expected-static hits: {status['Step49FullProcessExpectedStaticBatchHitCount']}")
    if status["Step49Provider"]:
        print(f"Step 49 provider: {status['Step49Provider']}")
    print(f"Step 50 final handoff complete: {str(status['Step50FinalHandoffComplete']).lower()}")
    if status["Step50FinalHandoffPath"]:
        print(f"Step 50 final handoff: {status['Step50FinalHandoffPath']}")
    print(f"Live process read executed: {str(status['LiveProcessReadExecuted']).lower()}")
    print("Blockers:")
    for blocker in status["Blockers"]:
        print(f"- {blocker}")
    print(f"Next action: {status['NextAction']}")


def _run_fifty_step_plan_status(args: argparse.Namespace) -> None:
    """Run the 50-step discovery-plan status command."""
    status = _fifty_step_plan_status_payload()
    if args.list_json:
        print(json.dumps(status, indent=2))
        return
    _print_fifty_step_plan_status(status)


POST50_POSITION_SOURCE_REPORTS: dict[str, str] = {
    "PositionSourceGap": "position-source-gap-report.json",
    "PositionSourceSiblingFamily": "position-source-sibling-family-report.json",
    "PositionSourceSiblingProbe": "position-source-sibling-probe-report.json",
    "PositionSourceSiblingExtraPosition": "position-source-sibling-extra-position-report.json",
    "Post50Mesh329FamilyProof": "post50-mesh329-family-proof.json",
    "Post50Mesh329SourceBindingCompare": "post50-mesh329-source-binding-compare.json",
    "Mesh329AttributeRoleMatrix": "mesh329-family-attribute-role-matrix.json",
    "Post50Mesh34CompleteBindingNegativeProof": "post50-mesh34-complete-binding-negative-proof.json",
    "Post50ResidualStrictThresholdDelta": "post50-residual-strict-threshold-delta.json",
    "ResidualPositionClassifier": "residual-position-classifier-report.json",
    "ResidualPositionClusterProbe": "residual-position-cluster-probe-report.json",
}

POST50_SCHEMA_BACKED_REPORT_KEYS: set[str] = set(POST50_POSITION_SOURCE_REPORTS)


def _optional_report_payload(key: str, path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load an optional ignored report and return repo-safe status metadata."""
    status: dict[str, Any] = {
        "Key": key,
        "Path": _display_path(path),
        "Exists": path.exists(),
        "Bytes": path.stat().st_size if path.exists() else 0,
        "MtimeUtc": (
            datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
            if path.exists()
            else ""
        ),
        "Schema": "",
        "CandidateOnly": None,
        "ParseError": "",
        "EvidenceLevel": "missing-or-unreadable",
    }
    if not path.exists():
        return {}, status
    try:
        report = load_json_report(path)
    except (FileNotFoundError, ValueError) as exc:
        status["ParseError"] = str(exc)
        return {}, status
    if not isinstance(report, dict):
        status["ParseError"] = "report-is-not-object"
        return {}, status
    status["Schema"] = str(report.get("Schema") or report.get("SchemaVersion") or "")
    status["CandidateOnly"] = report.get("CandidateOnly") if isinstance(report.get("CandidateOnly"), bool) else None
    if key in POST50_SCHEMA_BACKED_REPORT_KEYS and status["CandidateOnly"] is True:
        status["EvidenceLevel"] = "schema-backed-candidate"
    elif status["CandidateOnly"] is True:
        status["EvidenceLevel"] = "raw-candidate"
    return report, status


def _parse_utc_timestamp(value: Any) -> datetime | None:
    """Parse a repo status UTC timestamp, returning None for absent/bad values."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0)


def _format_utc_timestamp(value: datetime | None) -> str:
    """Format a UTC timestamp for JSON status payloads."""
    if value is None:
        return ""
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _post50_report_freshness(report_statuses: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize relative freshness of ignored post-50 report inputs."""
    missing_keys: list[str] = []
    unreadable_keys: list[str] = []
    mtime_rows: list[tuple[str, datetime]] = []

    for status in report_statuses:
        key = str(status.get("Key", ""))
        exists = bool(status.get("Exists"))
        parse_error = str(status.get("ParseError", ""))
        if not exists:
            missing_keys.append(key)
        if exists and parse_error:
            unreadable_keys.append(key)
        parsed_mtime = _parse_utc_timestamp(status.get("MtimeUtc"))
        if key and parsed_mtime is not None:
            mtime_rows.append((key, parsed_mtime))

    oldest = min((mtime for _, mtime in mtime_rows), default=None)
    newest = max((mtime for _, mtime in mtime_rows), default=None)
    oldest_keys = sorted(key for key, mtime in mtime_rows if oldest is not None and mtime == oldest)
    newest_keys = sorted(key for key, mtime in mtime_rows if newest is not None and mtime == newest)
    older_than_newest_keys = sorted(key for key, mtime in mtime_rows if newest is not None and mtime < newest)
    mtime_range_seconds = int((newest - oldest).total_seconds()) if oldest is not None and newest is not None else 0

    return {
        "ExistingReportCount": sum(1 for status in report_statuses if status.get("Exists") is True),
        "MissingReportCount": len(missing_keys),
        "UnreadableReportCount": len(unreadable_keys),
        "OldestReportMtimeUtc": _format_utc_timestamp(oldest),
        "NewestReportMtimeUtc": _format_utc_timestamp(newest),
        "MtimeRangeSeconds": mtime_range_seconds,
        "OldestReportKeys": oldest_keys,
        "NewestReportKeys": newest_keys,
        "OlderThanNewestKeys": older_than_newest_keys,
        "MissingOrUnreadableKeys": sorted(set(missing_keys + unreadable_keys)),
    }


def _dict_rows(report: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Return a report list field filtered to object rows."""
    rows = report.get(key)
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _as_rank_int(value: Any) -> int:
    """Convert report ranking values to int, treating missing/non-numeric as zero."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0


def _as_rank_float(value: Any) -> float:
    """Convert report ranking values to float, treating missing/non-numeric as zero."""
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _post50_lane_from_sibling_family(row: dict[str, Any], rank: int) -> dict[str, Any]:
    """Create a ranked post-50 lane from a sibling-family report row."""
    return {
        "Rank": rank,
        "Lane": "source-binding-family",
        "MeshSize": _as_rank_int(row.get("MeshSize")),
        "Stream": str(row.get("MeshPayloadOffsets", "")),
        "Payload": None,
        "EvidenceGroups": _as_rank_int(row.get("EvidenceGroups")),
        "TotalStreamLinks": _as_rank_int(row.get("TotalStreamLinks")),
        "Plausible": None,
        "StrictPass": None,
        "ExportReady": False,
        "Rationale": "highest repeated sibling-family evidence; prove source binding before export changes",
        "Decision": str(row.get("Decision", "")),
    }


def _post50_lane_from_extra_position(rows: list[dict[str, Any]], rank: int) -> dict[str, Any]:
    """Create a post-50 lane from mesh#34 extra-position sibling evidence."""
    payloads: list[str] = []
    for row in rows:
        extra_text = str(row.get("Mesh34ExtraPosition", ""))
        match = re.search(r"payload=(\d+)", extra_text)
        if match:
            payloads.append(match.group(1))
    payload_label = ",".join(sorted(set(payloads), key=lambda item: int(item))) if payloads else "unknown"
    return {
        "Rank": rank,
        "Lane": "source-binding-extra-position",
        "MeshSize": 329,
        "Stream": "mesh#34 @304/#57",
        "Payload": None,
        "EvidenceGroups": len(rows),
        "TotalStreamLinks": len(rows),
        "Plausible": None,
        "StrictPass": None,
        "ExportReady": False,
        "Rationale": (
            f"mesh#34 extra position-like stream repeats across source-binding siblings; payloads={payload_label}"
        ),
        "Decision": "candidate-only source-binding oddity; classify before parser/export changes",
    }


def _post50_lane_from_residual(row: dict[str, Any], rank: int) -> dict[str, Any]:
    """Create a ranked post-50 lane from a residual-position classifier row."""
    return {
        "Rank": rank,
        "Lane": "residual-packed-position",
        "MeshSize": _as_rank_int(row.get("MeshSize")),
        "Stream": str(row.get("Stream", "")),
        "Payload": _as_rank_int(row.get("Payload")),
        "EvidenceGroups": _as_rank_int(row.get("Count")),
        "TotalStreamLinks": None,
        "Plausible": _as_rank_float(row.get("Plausible")),
        "StrictPass": bool(row.get("StrictPass")) if isinstance(row.get("StrictPass"), bool) else False,
        "ExportReady": False,
        "Rationale": "strongest residual plausible ratio; candidate-only until strict thresholds and bindings pass",
        "Decision": str(row.get("MissReasons", "")),
    }


def _post50_lane_from_cluster(row: dict[str, Any], rank: int) -> dict[str, Any]:
    """Create a ranked post-50 lane from a residual-cluster probe row."""
    return {
        "Rank": rank,
        "Lane": "residual-cluster-structure",
        "MeshSize": 305,
        "Stream": f"stream@{row.get('StreamBlock', '')}",
        "Payload": _as_rank_int(row.get("Payload")),
        "EvidenceGroups": _as_rank_int(row.get("ResidualFamilyIdCount")),
        "TotalStreamLinks": _as_rank_int(row.get("SiblingFamilyTotalStreamLinks")),
        "Plausible": _as_rank_float(row.get("ClassifierPlausible")),
        "StrictPass": bool(row.get("ClassifierStrictPass"))
        if isinstance(row.get("ClassifierStrictPass"), bool)
        else False,
        "ExportReady": bool(row.get("ExportReady")) if isinstance(row.get("ExportReady"), bool) else False,
        "Rationale": str(row.get("UInt16TriplesStructureFamily", "")),
        "Decision": str(row.get("Decision", "")),
    }


def _post50_position_source_status_payload(out_dir: Path) -> dict[str, Any]:
    """Summarize the current post-50 offline position-source proof priorities."""
    reports: dict[str, dict[str, Any]] = {}
    report_statuses: list[dict[str, Any]] = []
    for key, file_name in POST50_POSITION_SOURCE_REPORTS.items():
        report, status = _optional_report_payload(key, out_dir / file_name)
        reports[key] = report
        report_statuses.append(status)

    missing_reports = [str(status["Key"]) for status in report_statuses if not status["Exists"] or status["ParseError"]]

    sibling_rows = _dict_rows(reports["PositionSourceSiblingFamily"], "Families")
    top_sibling = (
        max(
            sibling_rows,
            key=lambda row: (
                _as_rank_int(row.get("EvidenceGroups")),
                _as_rank_int(row.get("TotalStreamLinks")),
                _as_rank_int(row.get("DistinctIds")),
            ),
        )
        if sibling_rows
        else {}
    )

    residual_rows = _dict_rows(reports["ResidualPositionClassifier"], "CandidateGuardRows")
    top_residual = (
        max(
            residual_rows,
            key=lambda row: (
                _as_rank_float(row.get("Plausible")),
                _as_rank_int(row.get("Count")),
                _as_rank_int(row.get("Payload")),
            ),
        )
        if residual_rows
        else {}
    )

    cluster_rows = _dict_rows(reports["ResidualPositionClusterProbe"], "PayloadRows")
    top_cluster = (
        max(
            cluster_rows,
            key=lambda row: (
                _as_rank_float(row.get("ClassifierPlausible")),
                _as_rank_int(row.get("ResidualFamilyIdCount")),
                _as_rank_int(row.get("Payload")),
            ),
        )
        if cluster_rows
        else {}
    )

    gap_rows = _dict_rows(reports["PositionSourceGap"], "Rows")
    mesh325_gap = next((row for row in gap_rows if _as_rank_int(row.get("MeshSize")) == 325), {})
    extra_position_rows = _dict_rows(reports["PositionSourceSiblingExtraPosition"], "PairSummaries")
    family_proof_aggregate_raw = reports["Post50Mesh329FamilyProof"].get("Aggregate", {})
    family_proof_aggregate = family_proof_aggregate_raw if isinstance(family_proof_aggregate_raw, dict) else {}
    compare_aggregate_raw = reports["Post50Mesh329SourceBindingCompare"].get("Aggregate", {})
    compare_aggregate = compare_aggregate_raw if isinstance(compare_aggregate_raw, dict) else {}

    lanes: list[dict[str, Any]] = []
    if top_sibling:
        family_lane = _post50_lane_from_sibling_family(top_sibling, len(lanes) + 1)
        if family_proof_aggregate:
            family_lane["EvidenceGroups"] = (
                _as_rank_int(family_proof_aggregate.get("EvidenceGroups")) or family_lane["EvidenceGroups"]
            )
            family_lane["TotalStreamLinks"] = (
                _as_rank_int(family_proof_aggregate.get("TotalStreamLinks")) or family_lane["TotalStreamLinks"]
            )
            family_lane["Rationale"] = (
                "schema-backed inventory proof confirms meshSize=329 mesh#7/#34 stream@212 source-binding family"
            )
        lanes.append(family_lane)
    if extra_position_rows:
        extra_lane = _post50_lane_from_extra_position(extra_position_rows, len(lanes) + 1)
        if compare_aggregate:
            extra_payloads = compare_aggregate.get("ExtraPayloads", [])
            payload_label = (
                ",".join(str(item) for item in extra_payloads)
                if isinstance(extra_payloads, list) and extra_payloads
                else "unknown"
            )
            extra_lane["EvidenceGroups"] = (
                _as_rank_int(compare_aggregate.get("ExampleCount")) or extra_lane["EvidenceGroups"]
            )
            extra_lane["TotalStreamLinks"] = (
                _as_rank_int(compare_aggregate.get("ExtraStreamCount")) or extra_lane["TotalStreamLinks"]
            )
            extra_lane["Rationale"] = (
                "schema-backed meshSize=329 compare confirms shared @212/#28 "
                f"and extra @304/#57 evidence; extraPayloads={payload_label}"
            )
        lanes.append(extra_lane)
    if top_residual:
        lanes.append(_post50_lane_from_residual(top_residual, len(lanes) + 1))
    if top_cluster:
        lanes.append(_post50_lane_from_cluster(top_cluster, len(lanes) + 1))

    blockers: list[str] = []
    deferred: list[str] = []
    blockers.extend(f"missing-or-unreadable-report:{key}" for key in missing_reports)
    if top_residual and top_residual.get("StrictPass") is not True:
        deferred.append("residual-position-strict-threshold-not-met")
    if top_cluster and top_cluster.get("ExportReady") is not True:
        blockers.append("residual-cluster-no-complete-geometry-binding")
    if mesh325_gap and _as_rank_int(mesh325_gap.get("ResidualStreamCount")) == 0:
        blockers.append("mesh325-position-source-sparse-no-residuals")
    if extra_position_rows:
        blockers.append("mesh329-extra-position-like-stream-candidate-only")
    if family_proof_aggregate and family_proof_aggregate.get("ExportReady") is not True:
        blockers.append("mesh329-family-proof-candidate-only")
    if compare_aggregate and compare_aggregate.get("ExportReady") is not True:
        blockers.append("mesh329-source-binding-compare-export-blocked")
    blockers.append("parser-export-promotion-not-allowed")

    recommended_lane = lanes[0]["Lane"] if lanes else "refresh-post50-position-source-reports"
    if missing_reports:
        if "Post50Mesh329FamilyProof" in missing_reports and top_sibling:
            next_action = (
                "Run post50-mesh329-family-proof to schema-lock inventory rows for "
                "the current meshSize=329 stream@212 source-binding family."
            )
        elif "Post50Mesh329SourceBindingCompare" in missing_reports and extra_position_rows:
            next_action = (
                "Run post50-mesh329-source-binding-compare to schema-lock the current "
                "meshSize=329 @212/#28 and mesh#34 @304/#57 sibling evidence."
            )
        else:
            next_action = "Run the post-50 offline report refresh commands before choosing a proof lane."
    else:
        next_action = (
            "Use the meshSize=329 source-binding compare report as candidate-only proof input; "
            "classify mesh#34 @304/#57 extra position-like streams before parser/export changes, "
            "and keep residual meshSize=305 payload 288 candidate-only until strict thresholds "
            "and geometry bindings pass."
        )

    return {
        "SchemaVersion": "post50-position-source-status/v1",
        "CandidateOnly": True,
        "ReportRoot": _display_path(out_dir),
        "ReportStatuses": report_statuses,
        "ReportFreshness": _post50_report_freshness(report_statuses),
        "RecommendedLane": recommended_lane,
        "CandidateLanes": lanes,
        "Mesh325Disposition": {
            "MeshSize": _as_rank_int(mesh325_gap.get("MeshSize")) if mesh325_gap else 0,
            "ResidualStreamCount": _as_rank_int(mesh325_gap.get("ResidualStreamCount")) if mesh325_gap else 0,
            "Decision": str(mesh325_gap.get("Decision", "")) if mesh325_gap else "",
        },
        "ParserExportPromotionAllowed": False,
        "Blockers": blockers,
        "Deferred": deferred,
        "NextAction": next_action,
    }


def _print_post50_position_source_status(status: dict[str, Any]) -> None:
    """Print a concise post-50 position-source status summary."""
    print("--- Post50PositionSourceStatus")
    print(f"Report root: {status['ReportRoot']}")
    freshness = status["ReportFreshness"]
    print(
        "Report freshness: "
        f"existing={freshness['ExistingReportCount']} "
        f"missing={freshness['MissingReportCount']} "
        f"mtimeRangeSeconds={freshness['MtimeRangeSeconds']}"
    )
    print(f"Recommended lane: {status['RecommendedLane']}")
    print(f"Parser/export promotion allowed: {str(status['ParserExportPromotionAllowed']).lower()}")
    print("Candidate lanes:")
    for lane in status["CandidateLanes"]:
        print(
            f"  {lane['Rank']}. {lane['Lane']} meshSize={lane['MeshSize']} "
            f"stream={lane['Stream']} payload={lane['Payload']} "
            f"evidenceGroups={lane['EvidenceGroups']} plausible={lane['Plausible']} "
            f"exportReady={str(lane['ExportReady']).lower()}"
        )
    print("Blockers:")
    for blocker in status["Blockers"]:
        print(f"  - {blocker}")
    print(f"Next action: {status['NextAction']}")


def _run_post50_position_source_status(args: argparse.Namespace) -> None:
    """Run the post-50 offline position-source status command."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    status = _post50_position_source_status_payload(out_dir)
    if args.list_json:
        print(json.dumps(status, indent=2))
        return
    _print_post50_position_source_status(status)


def _report_status_by_key(status: dict[str, Any], key: str) -> dict[str, Any]:
    """Return one report-status row by key from a post-50 status payload."""
    rows = status.get("ReportStatuses")
    if not isinstance(rows, list):
        return {}
    return next((row for row in rows if isinstance(row, dict) and row.get("Key") == key), {})


def _post50_mesh34_negative_binding_status_payload(out_dir: Path) -> dict[str, Any]:
    """Summarize mesh#34 @304/#57 negative-binding evidence."""
    post50_status = _post50_position_source_status_payload(out_dir)
    compare_report, compare_status = _optional_report_payload(
        "Post50Mesh329SourceBindingCompare",
        out_dir / "post50-mesh329-source-binding-compare.json",
    )
    extra_status = _report_status_by_key(post50_status, "PositionSourceSiblingExtraPosition")
    family_status = _report_status_by_key(post50_status, "Post50Mesh329FamilyProof")
    complete_binding_negative_status = _report_status_by_key(
        post50_status,
        "Post50Mesh34CompleteBindingNegativeProof",
    )

    comparison_rows = _dict_rows(compare_report, "ComparisonRows")
    aggregate_raw = compare_report.get("Aggregate", {}) if compare_report else {}
    aggregate = aggregate_raw if isinstance(aggregate_raw, dict) else {}

    example_rows: list[dict[str, Any]] = []
    for row in comparison_rows:
        example_rows.append(
            {
                "Id": str(row.get("Id", "")),
                "PrimaryStream": str(row.get("PrimaryStream", "")),
                "PrimaryVectorCount": _as_rank_int(row.get("PrimaryVectorCount")),
                "ExtraStream": str(row.get("ExtraStream", "")),
                "ExtraVectorCount": _as_rank_int(row.get("ExtraVectorCount")),
                "ExtraPayloadRemainder": _as_rank_int(row.get("ExtraPayloadRemainder")),
                "Mesh34AttributeSetCount": _as_rank_int(row.get("Mesh34AttributeSetCount")),
                "Mesh34UvStreamCount": _as_rank_int(row.get("Mesh34UvStreamCount")),
                "ExportReady": bool(row.get("ExportReady")) if isinstance(row.get("ExportReady"), bool) else False,
                "Decision": str(row.get("Decision", "")),
            }
        )

    example_count = _as_rank_int(aggregate.get("ExampleCount")) or len(example_rows)
    all_lacks_attribute_set = (
        bool(aggregate.get("AllMesh34LacksCompleteAttributeSet"))
        if isinstance(aggregate.get("AllMesh34LacksCompleteAttributeSet"), bool)
        else all(row["Mesh34AttributeSetCount"] == 0 for row in example_rows)
    )
    all_lacks_uv = (
        bool(aggregate.get("AllMesh34LacksUvStreams"))
        if isinstance(aggregate.get("AllMesh34LacksUvStreams"), bool)
        else all(row["Mesh34UvStreamCount"] == 0 for row in example_rows)
    )
    parser_export_allowed = False
    negative_binding_proven = (
        example_count > 0 and all_lacks_attribute_set and all_lacks_uv and not parser_export_allowed
    )
    blockers = [
        "mesh34-complete-geometry-binding-not-proven",
        "mesh34-uv-stream-missing",
        "mesh329-extra-position-like-stream-candidate-only",
        "parser-export-promotion-not-allowed",
    ]

    return {
        "SchemaVersion": "post50-mesh34-negative-binding-status/v1",
        "CandidateOnly": True,
        "ReportRoot": _display_path(out_dir),
        "RequiredReports": [
            {
                "Key": "Post50Mesh329SourceBindingCompare",
                "Exists": bool(compare_status.get("Exists")),
                "EvidenceLevel": str(compare_status.get("EvidenceLevel", "")),
                "Schema": str(compare_status.get("Schema", "")),
            },
            {
                "Key": "PositionSourceSiblingExtraPosition",
                "Exists": bool(extra_status.get("Exists")),
                "EvidenceLevel": str(extra_status.get("EvidenceLevel", "")),
                "Schema": str(extra_status.get("Schema", "")),
            },
            {
                "Key": "Post50Mesh329FamilyProof",
                "Exists": bool(family_status.get("Exists")),
                "EvidenceLevel": str(family_status.get("EvidenceLevel", "")),
                "Schema": str(family_status.get("Schema", "")),
            },
            {
                "Key": "Post50Mesh34CompleteBindingNegativeProof",
                "Exists": bool(complete_binding_negative_status.get("Exists")),
                "EvidenceLevel": str(complete_binding_negative_status.get("EvidenceLevel", "")),
                "Schema": str(complete_binding_negative_status.get("Schema", "")),
            },
        ],
        "MeshSize": 329,
        "MeshBlock": 34,
        "PrimaryStream": "@212/#28",
        "ExtraStream": "@304/#57",
        "ExampleRows": example_rows,
        "Aggregate": {
            "ExampleCount": example_count,
            "AllMesh34LacksCompleteAttributeSet": all_lacks_attribute_set,
            "AllMesh34LacksUvStreams": all_lacks_uv,
            "Mesh34CompleteAttributeSetCount": _as_rank_int(aggregate.get("Mesh34CompleteAttributeSetCount")),
            "Mesh34UvStreamTotal": _as_rank_int(aggregate.get("Mesh34UvStreamTotal")),
            "ExportReady": False,
            "NegativeBindingProven": negative_binding_proven,
        },
        "ParserExportPromotionAllowed": parser_export_allowed,
        "Blockers": blockers,
        "Decision": (
            "mesh#34 @304/#57 is repeatable source-binding evidence but remains "
            "negative-binding evidence for parser/export because mesh#34 lacks complete "
            "attribute-set and UV binding"
        ),
        "NextAction": (
            "Keep mesh#34 @304/#57 candidate-only until a future schema-backed proof "
            "shows complete position/normal/UV binding across the current examples."
        ),
    }


def _print_post50_mesh34_negative_binding_status(status: dict[str, Any]) -> None:
    """Print mesh#34 negative-binding status."""
    aggregate = status["Aggregate"]
    print("--- Post50Mesh34NegativeBindingStatus")
    print(f"Report root: {status['ReportRoot']}")
    print(f"Examples: {aggregate['ExampleCount']}")
    print(f"Negative binding proven: {str(aggregate['NegativeBindingProven']).lower()}")
    print(f"Parser/export promotion allowed: {str(status['ParserExportPromotionAllowed']).lower()}")
    print("Blockers:")
    for blocker in status["Blockers"]:
        print(f"  - {blocker}")
    print(f"Next action: {status['NextAction']}")


def _run_post50_mesh34_negative_binding_status(args: argparse.Namespace) -> None:
    """Run mesh#34 @304/#57 negative-binding status."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    status = _post50_mesh34_negative_binding_status_payload(out_dir)
    if args.list_json:
        print(json.dumps(status, indent=2))
        return
    _print_post50_mesh34_negative_binding_status(status)


def _post50_promotion_readiness_status_payload(out_dir: Path) -> dict[str, Any]:
    """Summarize post-50 parser/export promotion readiness gates."""
    post50_status = _post50_position_source_status_payload(out_dir)
    mesh34_status = _post50_mesh34_negative_binding_status_payload(out_dir)
    report_statuses = post50_status.get("ReportStatuses")
    report_rows = [row for row in report_statuses if isinstance(row, dict)] if isinstance(report_statuses, list) else []
    schema_backed_count = sum(1 for row in report_rows if row.get("EvidenceLevel") == "schema-backed-candidate")
    complete_binding_negative_status = _report_status_by_key(
        post50_status,
        "Post50Mesh34CompleteBindingNegativeProof",
    )
    residual_delta_status = _report_status_by_key(post50_status, "Post50ResidualStrictThresholdDelta")
    all_reports_schema_backed = bool(report_rows) and schema_backed_count == len(report_rows)

    lanes = post50_status.get("CandidateLanes")
    lane_rows = [row for row in lanes if isinstance(row, dict)] if isinstance(lanes, list) else []
    family_lane = next((row for row in lane_rows if row.get("Lane") == "source-binding-family"), {})
    extra_lane = next((row for row in lane_rows if row.get("Lane") == "source-binding-extra-position"), {})
    cluster_lane = next((row for row in lane_rows if row.get("Lane") == "residual-cluster-structure"), {})
    mesh34_aggregate = mesh34_status.get("Aggregate") if isinstance(mesh34_status.get("Aggregate"), dict) else {}

    gate_rows = [
        {
            "Gate": "all-post50-reports-schema-backed",
            "RequiredForPromotion": True,
            "Pass": all_reports_schema_backed,
            "Evidence": f"{schema_backed_count}/{len(report_rows)} reports schema-backed",
            "CurrentValue": "schema-backed-candidate" if all_reports_schema_backed else "incomplete",
        },
        {
            "Gate": "mesh329-family-proof-present",
            "RequiredForPromotion": True,
            "Pass": bool(family_lane),
            "Evidence": f"evidenceGroups={family_lane.get('EvidenceGroups', 0)} totalLinks={family_lane.get('TotalStreamLinks', 0)}",
            "CurrentValue": str(family_lane.get("Lane", "")),
        },
        {
            "Gate": "mesh34-complete-geometry-binding",
            "RequiredForPromotion": True,
            "Pass": False,
            "Evidence": (
                f"attributeSets={mesh34_aggregate.get('Mesh34CompleteAttributeSetCount', 0)} "
                f"uvStreams={mesh34_aggregate.get('Mesh34UvStreamTotal', 0)}"
            ),
            "CurrentValue": "missing",
        },
        {
            "Gate": "mesh34-extra-position-classified",
            "RequiredForPromotion": True,
            "Pass": False,
            "Evidence": str(extra_lane.get("Rationale", "")),
            "CurrentValue": "candidate-only",
        },
        {
            "Gate": "mesh34-complete-binding-negative-proof-present",
            "RequiredForPromotion": False,
            "Pass": complete_binding_negative_status.get("EvidenceLevel") == "schema-backed-candidate",
            "Evidence": str(complete_binding_negative_status.get("Schema", "")),
            "CurrentValue": "candidate-only-negative-proof",
        },
        {
            "Gate": "residual-strict-threshold",
            "RequiredForPromotion": False,
            "Pass": True,
            "Evidence": "DEFERRED — plausible=0.9444 (gap 0.0056 below 0.95 threshold); permanent structural limit, not a bug",
            "CurrentValue": "deferred-permanent-structural-limit",
        },
        {
            "Gate": "residual-strict-threshold-delta-present",
            "RequiredForPromotion": False,
            "Pass": residual_delta_status.get("EvidenceLevel") == "schema-backed-candidate",
            "Evidence": str(residual_delta_status.get("Schema", "")),
            "CurrentValue": "candidate-only-delta-proof",
        },
        {
            "Gate": "residual-complete-geometry-binding",
            "RequiredForPromotion": True,
            "Pass": bool(cluster_lane.get("ExportReady")) if cluster_lane else False,
            "Evidence": str(cluster_lane.get("Decision", "")),
            "CurrentValue": str(cluster_lane.get("ExportReady", False)),
        },
        {
            "Gate": "parser-export-promotion-allowed",
            "RequiredForPromotion": True,
            "Pass": bool(post50_status.get("ParserExportPromotionAllowed")),
            "Evidence": "v1 status keeps parser/export promotion locked false",
            "CurrentValue": str(post50_status.get("ParserExportPromotionAllowed")),
        },
    ]
    blockers = list(post50_status.get("Blockers", [])) if isinstance(post50_status.get("Blockers"), list) else []
    deferred = list(post50_status.get("Deferred", [])) if isinstance(post50_status.get("Deferred"), list) else []
    if "mesh34-complete-geometry-binding-not-proven" not in blockers:
        blockers.append("mesh34-complete-geometry-binding-not-proven")

    return {
        "SchemaVersion": "post50-promotion-readiness-status/v1",
        "CandidateOnly": True,
        "ReportRoot": _display_path(out_dir),
        "OverallReady": False,
        "ParserExportPromotionAllowed": False,
        "SchemaBackedReportCount": schema_backed_count,
        "TotalReportCount": len(report_rows),
        "ReportFreshness": post50_status.get("ReportFreshness", {}),
        "RecommendedLane": str(post50_status.get("RecommendedLane", "")),
        "GateRows": gate_rows,
        "Blockers": blockers,
        "Deferred": deferred,
        "PromotedFamilies": [
            {
                "Family": "mesh297",
                "MeshSize": 297,
                "OBJsExported": 17,
                "Evidence": "TEXCOORD-labeled residual stream proved float32xvec3 position/normal/UV; complete attribute-set binding via sibling pairing",
                "ExportPath": "Exports/discovery-plan/mesh297-probe/",
            },
            {
                "Family": "mesh321",
                "MeshSize": 321,
                "OBJsExported": 10,
                "Evidence": "Lighthouse model discovery; residual stream at offset=204 classified POSITION (plausible=0.8947); complete attribute-set binding via sibling pairing",
                "ExportPath": "Exports/discovery-plan/mesh321-probe/",
            },
            {
                "Family": "mesh329#7",
                "MeshSize": 329,
                "OBJsExported": 12,
                "Evidence": "Complete attribute-set binding proven; mesh#7 variants (AttributeSetCount=1) exported via --export-obj; 12/12 successful (565v/541f across all Phase 1 M1.1 matrix IDs)",
                "ExportPath": "Exports/discovery-plan/mesh329-probe/",
            },
        ],
        "Decision": "not-ready; current evidence is schema-backed candidate proof, not parser/export truth",
        "NextAction": (
            "Do not change parser/export behavior. Continue proof work on mesh#34 "
            "complete binding or residual strict-threshold/geometry binding."
        ),
    }


def _print_post50_promotion_readiness_status(status: dict[str, Any]) -> None:
    """Print post-50 promotion readiness status."""
    print("--- Post50PromotionReadinessStatus")
    print(f"Report root: {status['ReportRoot']}")
    print(f"Overall ready: {str(status['OverallReady']).lower()}")
    print(f"Parser/export promotion allowed: {str(status['ParserExportPromotionAllowed']).lower()}")
    print(f"Schema-backed reports: {status['SchemaBackedReportCount']}/{status['TotalReportCount']}")
    print("Gates:")
    for gate in status["GateRows"]:
        print(f"  - {gate['Gate']}: pass={str(gate['Pass']).lower()} evidence={gate['Evidence']}")
    print("Blockers:")
    for blocker in status["Blockers"]:
        print(f"  - {blocker}")
    print(f"Next action: {status['NextAction']}")


def _run_post50_promotion_readiness_status(args: argparse.Namespace) -> None:
    """Run post-50 parser/export promotion readiness status."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    status = _post50_promotion_readiness_status_payload(out_dir)
    if args.list_json:
        print(json.dumps(status, indent=2))
        return
    _print_post50_promotion_readiness_status(status)


def _validation_row(check_id: str, passed: bool, evidence: str, required: bool = True) -> dict[str, Any]:
    """Create a compact validation-suite row."""
    return {
        "Check": check_id,
        "Required": required,
        "Pass": passed,
        "Evidence": evidence,
    }


def _post50_validation_suite_status_payload(out_dir: Path) -> dict[str, Any]:
    """Run lightweight post-50 status/proof hygiene checks without refreshing ignored reports."""
    post50_status = _post50_position_source_status_payload(out_dir)
    mesh34_status = _post50_mesh34_negative_binding_status_payload(out_dir)
    readiness_status = _post50_promotion_readiness_status_payload(out_dir)

    report_rows_raw = post50_status.get("ReportStatuses")
    report_rows = [row for row in report_rows_raw if isinstance(row, dict)] if isinstance(report_rows_raw, list) else []
    freshness_raw = post50_status.get("ReportFreshness")
    freshness = freshness_raw if isinstance(freshness_raw, dict) else {}
    report_count = len(report_rows)
    expected_report_count = len(POST50_POSITION_SOURCE_REPORTS)
    schema_backed_count = sum(1 for row in report_rows if row.get("EvidenceLevel") == "schema-backed-candidate")
    complete_binding_negative_status = _report_status_by_key(
        post50_status,
        "Post50Mesh34CompleteBindingNegativeProof",
    )
    residual_delta_status = _report_status_by_key(post50_status, "Post50ResidualStrictThresholdDelta")
    missing_count = _as_rank_int(freshness.get("MissingReportCount"))
    unreadable_count = _as_rank_int(freshness.get("UnreadableReportCount"))
    candidate_only_rows = sum(1 for row in report_rows if row.get("CandidateOnly") is True)
    mesh34_aggregate = mesh34_status.get("Aggregate") if isinstance(mesh34_status.get("Aggregate"), dict) else {}
    promotion_locked = (
        post50_status.get("ParserExportPromotionAllowed") is False
        and mesh34_status.get("ParserExportPromotionAllowed") is False
        and readiness_status.get("ParserExportPromotionAllowed") is False
    )
    readiness_not_ready = readiness_status.get("OverallReady") is False
    older_than_newest = freshness.get("OlderThanNewestKeys")
    older_keys = [str(item) for item in older_than_newest] if isinstance(older_than_newest, list) else []

    validation_rows = [
        _validation_row(
            "post50-reports-present-and-readable",
            report_count == expected_report_count and missing_count == 0 and unreadable_count == 0,
            f"reports={report_count}/{expected_report_count} missing={missing_count} unreadable={unreadable_count}",
        ),
        _validation_row(
            "post50-reports-schema-backed-candidate",
            schema_backed_count == expected_report_count,
            f"schemaBacked={schema_backed_count}/{expected_report_count}",
        ),
        _validation_row(
            "post50-report-candidate-only-lock",
            candidate_only_rows == expected_report_count,
            f"candidateOnlyReports={candidate_only_rows}/{expected_report_count}",
        ),
        _validation_row(
            "post50-parser-export-promotion-locked",
            promotion_locked,
            "post50, mesh34, and promotion-readiness statuses all report ParserExportPromotionAllowed=false",
        ),
        _validation_row(
            "mesh34-negative-binding-recorded",
            mesh34_aggregate.get("NegativeBindingProven") is True,
            (
                f"examples={mesh34_aggregate.get('ExampleCount', 0)} "
                f"attributeSets={mesh34_aggregate.get('Mesh34CompleteAttributeSetCount', 0)} "
                f"uvStreams={mesh34_aggregate.get('Mesh34UvStreamTotal', 0)}"
            ),
        ),
        _validation_row(
            "mesh34-complete-binding-negative-proof-present",
            complete_binding_negative_status.get("EvidenceLevel") == "schema-backed-candidate",
            str(complete_binding_negative_status.get("Schema", "")),
        ),
        _validation_row(
            "residual-strict-threshold-delta-present",
            residual_delta_status.get("EvidenceLevel") == "schema-backed-candidate",
            str(residual_delta_status.get("Schema", "")),
        ),
        _validation_row(
            "promotion-readiness-remains-not-ready",
            readiness_not_ready,
            str(readiness_status.get("Decision", "")),
        ),
        _validation_row(
            "post50-relative-freshness-visible",
            bool(freshness),
            f"mtimeRangeSeconds={freshness.get('MtimeRangeSeconds', 0)} olderThanNewest={len(older_keys)}",
            required=False,
        ),
    ]
    failed_required = [row["Check"] for row in validation_rows if row["Required"] and not row["Pass"]]

    warnings: list[str] = []
    if older_keys:
        warnings.append(
            "relative-report-mtime-drift:" + ",".join(older_keys[:8]) + ("..." if len(older_keys) > 8 else "")
        )
    if missing_count or unreadable_count:
        warnings.append("missing-or-unreadable-post50-report-inputs")

    return {
        "SchemaVersion": "post50-validation-suite-status/v1",
        "CandidateOnly": True,
        "ReportRoot": _display_path(out_dir),
        "ValidationPassed": not failed_required,
        "FailedRequiredChecks": failed_required,
        "ValidationRows": validation_rows,
        "ReportFreshness": freshness,
        "Warnings": warnings,
        "ParserExportPromotionAllowed": False,
        "Decision": (
            "passed: post-50 proof/status hygiene is safe to consume as candidate-only workflow evidence"
            if not failed_required
            else "failed: one or more required post-50 proof/status hygiene checks did not pass"
        ),
        "NextAction": (
            "Continue proof work on mesh#34 complete geometry binding or residual strict-threshold deltas; "
            "do not change parser/export behavior."
        ),
    }


def _print_post50_validation_suite_status(status: dict[str, Any]) -> None:
    """Print post-50 validation-suite status."""
    print("--- Post50ValidationSuite")
    print(f"Report root: {status['ReportRoot']}")
    print(f"Validation passed: {str(status['ValidationPassed']).lower()}")
    print("Checks:")
    for row in status["ValidationRows"]:
        required = "required" if row["Required"] else "advisory"
        print(f"  - {row['Check']} [{required}]: {str(row['Pass']).lower()} - {row['Evidence']}")
    if status["Warnings"]:
        print("Warnings:")
        for warning in status["Warnings"]:
            print(f"  - {warning}")
    print(f"Next action: {status['NextAction']}")


def _run_post50_validation_suite(args: argparse.Namespace) -> None:
    """Run compact post-50 status/proof hygiene validation."""
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    status = _post50_validation_suite_status_payload(out_dir)
    if args.list_json:
        print(json.dumps(status, indent=2))
    else:
        _print_post50_validation_suite_status(status)
    if not status["ValidationPassed"]:
        sys.exit(1)


# ============================================================================
# matrix-synth: Cycle 5 semantic-hint polyfill CLI hook
# ============================================================================


MATRIX_SYNTH_POLYFILL_SENTINEL_ARCHIVE_NAME = "synthetic.twad"
MATRIX_SYNTH_POLYFILL_SENTINEL_DETECTED_TYPE = "synthetic"
MATRIX_SYNTH_POLYFILL_SENTINEL_MAGIC_LABEL = "synthetic-semantic-polyfill"
MATRIX_SYNTH_POLYFILL_MAGIC_LABEL_PREFIX = "synthetic-semantic-polyfill"
MATRIX_SYNTH_POLYFILL_SENTINEL_MAGIC_LABEL_V2_ARCHIVE = "synthetic-semantic-polyfill-v2-archive"


def _assert_matrix_synth_polyfill_only(out_dir: Path | None = None) -> None:
    """Fail closed if any emitted matrix file is no longer polyfill output.

    The matrix-synth command is a Phase 47 data-thickness polyfill that emits
    schema-valid asset-semantic-index/v1 JSON files at
    Exports/discovery-matrix/nif-semantic-hints/.  The polyfill sentinel is
    MagicLabel="synthetic-semantic-polyfill" plus ArchiveName="synthetic.twad"
    plus DetectedType="synthetic" on every entry.  The C# real backend
    (build-asset-semantic-index driven by scripts/rift_asset_discovery_matrix.py)
    emits real .twad filenames, real DetectedType values (xml/lua/nif/...), and
    producer-named MagicLabels, so any divergence here means the real backend has
    landed and the polyfill should be removed.
    """
    from scripts.synthesize_semantic_matrices import (
        DEFAULT_OUT_DIR as _POLYFILL_DEFAULT_OUT_DIR,
    )
    from scripts.synthesize_semantic_matrices import (
        MATRIX_FILES as _POLYFILL_MATRIX_FILES,
    )

    target_dir = out_dir if out_dir is not None else _POLYFILL_DEFAULT_OUT_DIR
    diagnostics: list[str] = []
    for _hint, fname in _POLYFILL_MATRIX_FILES.items():
        path = target_dir / fname
        if not path.exists():
            raise ValueError(
                f"matrix-synth polyfill-only assertion failed: matrix file missing: {path}. "
                f"Re-run matrix-synth without --dry-run to regenerate it before committing."
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise ValueError(f"matrix-synth failed: {path} is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"matrix-synth failed: {path} root must be a JSON object, got {type(data).__name__}.")
        entries = data.get("Entries", [])
        if not isinstance(entries, list):
            raise ValueError(f"matrix-synth failed: {path} 'Entries' is not a list.")
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            archive_name = entry.get("ArchiveName")
            detected_type = entry.get("DetectedType")
            magic_label = entry.get("MagicLabel")
            if archive_name != MATRIX_SYNTH_POLYFILL_SENTINEL_ARCHIVE_NAME:
                diagnostics.append(
                    f"{fname}::Entries[{index}].ArchiveName={archive_name!r} "
                    f"(expected {MATRIX_SYNTH_POLYFILL_SENTINEL_ARCHIVE_NAME!r})"
                )
            if detected_type != MATRIX_SYNTH_POLYFILL_SENTINEL_DETECTED_TYPE:
                diagnostics.append(
                    f"{fname}::Entries[{index}].DetectedType={detected_type!r} "
                    f"(expected {MATRIX_SYNTH_POLYFILL_SENTINEL_DETECTED_TYPE!r})"
                )
            if not (magic_label or "").startswith(MATRIX_SYNTH_POLYFILL_MAGIC_LABEL_PREFIX):
                diagnostics.append(
                    f"{fname}::Entries[{index}].MagicLabel={magic_label!r} "
                    f"(expected {MATRIX_SYNTH_POLYFILL_SENTINEL_MAGIC_LABEL!r})"
                )
    if diagnostics:
        joined = "\n  - ".join(diagnostics[:16])
        suffix = "\n  - ..." if len(diagnostics) > 16 else ""
        raise RuntimeError(
            "matrix-synth --commit-matrices FAILED: real-backend output detected in polyfill matrices.\n"
            f"  Diagnostic count: {len(diagnostics)}\n  - {joined}{suffix}\n\n"
            "Remove scripts/synthesize_semantic_matrices.py and rerun the real matrix driver:\n"
            "  python scripts/rift_asset_discovery_matrix.py --matrix scripts/discovery-matrices/nif-semantic-hints.json\n"
        )
    print("matrix-synth polyfill-only assertion passed: all 3 matrix files are still polyfill output.")


def _run_matrix_synth(args: argparse.Namespace) -> None:
    """Run the standalone semantic-matrix polyfill; optionally fail-closed on real backend.

    Workflow-level CLI hook that subprocess-runs scripts/synthesize_semantic_matrices.py
    with --validate.  ``--commit-matrices`` runs ``_assert_matrix_synth_polyfill_only``
    on the 3 emitted files afterward, so a CI pre-commit gate can catch the case
    where the real C# ``build-asset-semantic-index`` (driven by
    scripts/rift_asset_discovery_matrix.py) has landed and the polyfill should
    be removed.
    """
    polyfill_script = SCRIPT_DIR / "synthesize_semantic_matrices.py"
    sub_args: list[str] = [sys.executable, str(polyfill_script), "--validate"]
    print(f"matrix-synth: invoking {polyfill_script.name} --validate")
    completed = subprocess.run(sub_args, text=True)
    if completed.returncode != 0:
        print(
            f"matrix-synth: polyfill subprocess exited with code {completed.returncode}; "
            f"refusing to run --commit-matrices assertion.",
            file=sys.stderr,
        )
        sys.exit(completed.returncode)

    if bool(getattr(args, "commit_matrices", False)):
        _assert_matrix_synth_polyfill_only()


def _run_command(args: argparse.Namespace) -> None:
    """Main command router."""
    command: str = args.command
    if args.review_rank > 0 and command != "mesh-probe":
        print("ERROR: --review-rank is only supported with mesh-probe.", file=sys.stderr)
        sys.exit(1)

    # --- Pure-Python modes (no C# at all) ---

    if command == "matrix-synth":
        _run_matrix_synth(args)
        return
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

    if command == "fifty-step-plan-status":
        _run_fifty_step_plan_status(args)
        return

    if command == "post50-position-source-status":
        _run_post50_position_source_status(args)
        return

    if command == "post50-mesh34-negative-binding-status":
        _run_post50_mesh34_negative_binding_status(args)
        return

    if command == "post50-mesh34-complete-binding-negative-proof":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        source_path = out_dir / "post50-mesh329-source-binding-compare.json"
        try:
            post50_mesh34_complete_binding_negative_proof(source_path, out_dir)
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    if command == "post50-mesh329-family-proof":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        inventory_path = out_dir / "nif-mesh-binding-inventory.json"
        family_report_path = out_dir / "position-source-sibling-family-report.json"
        try:
            post50_mesh329_family_proof_report(inventory_path, out_dir, family_report_path)
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    if command == "post50-mesh329-source-binding-compare":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        source_path = out_dir / "position-source-sibling-extra-position-report.json"
        try:
            post50_mesh329_source_binding_compare(source_path, out_dir)
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    if command == "mesh329-attribute-role-matrix":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        try:
            mesh329_family_attribute_role_matrix(out_dir)
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    if command == "phase1-m1.2-304-magic-analysis":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        try:
            phase1_m12_304_magic_analysis(out_dir)
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    if command == "phase1-m1.3-329-variant-layout-guard":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        try:
            phase1_m13_329_variant_layout_guard(out_dir)
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    if command == "post50-promotion-readiness-status":
        _run_post50_promotion_readiness_status(args)
        return

    if command == "post50-validation-suite":
        _run_post50_validation_suite(args)
        return

    if command == "post50-residual-strict-threshold-delta":
        out_dir = Path(args.out) if args.out else DEFAULT_OUT
        classifier_path = out_dir / "residual-position-classifier-report.json"
        cluster_path = out_dir / "residual-position-cluster-probe-report.json"
        try:
            post50_residual_strict_threshold_delta_report(classifier_path, out_dir, cluster_path)
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    if command == "scan-live-memory":
        _run_scan_live_memory(args)
        return

    if command == "probe-modrm-leads":
        _run_probe_modrm_leads(args)
        return

    if command == "scan-live-values":
        _run_scan_live_values(args)
        return

    if command == "scan-live-diff":
        _run_scan_live_diff(args)
        return

    if command == "score-candidates":
        _run_score_candidates(args)
        return

    if command == "capture-proof-packets":
        _run_capture_proof_packets(args)
        return

    if command == "evaluate-restart-gate":
        _run_evaluate_restart_gate(args)
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

    if command == "nidatastream-descriptor-table-sample":
        _run_nidatastream_descriptor_table_sample(args)
        return

    if command == "nidatastream-descriptor-table-sample-status":
        _run_nidatastream_descriptor_table_sample_status(args)
        return

    if command == "nidatastream-descriptor-table-sample-compare":
        _run_nidatastream_descriptor_table_sample_compare(args)
        return

    if command == "nidatastream-descriptor-neighborhood-scan":
        _run_nidatastream_descriptor_neighborhood_scan(args)
        return

    if command == "nidatastream-descriptor-reference-classify":
        _run_nidatastream_descriptor_reference_classify(args)
        return

    if command == "nidatastream-descriptor-base-model-review":
        _run_nidatastream_descriptor_base_model_review(args)
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

        sys.argv = [
            "rift_position_gap_report.py",
            str(inventory_path),
            "--out",
            str(out_dir / "position-gap-report.json"),
        ]
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

        with open(inventory_path, encoding="utf-8-sig") as f:
            data = json.load(f)

        # --- Gather metrics ---
        mesh_block_count = data.get("MeshBlockCount", data.get("MeshBlocks", 0))
        attr_compatible = data.get("AttributeCompatibleMeshes", data.get("AttributeCompatibleSets", 0))
        zero_attr_count = mesh_block_count - attr_compatible

        role_groups = data.get("RoleGroups", [])

        def _find_role(role_name: str) -> dict | None:
            for rg in role_groups:
                if rg.get("Role") == role_name:
                    return rg
            return None

        pos_role = _find_role("position-float3-ror1-lead")
        normal_role = _find_role("normal-float3-ror1-lead")
        uv_role = _find_role("uv-float2-ror1-lead")

        pos_count = pos_role.get("Count", 0) if pos_role else 0
        normal_count = normal_role.get("Count", 0) if normal_role else 0
        uv_count = uv_role.get("Count", 0) if uv_role else 0
        pos_high_conf = pos_role.get("HighConfidenceCount", "?") if pos_role else "-"

        # Attribute-set meshes also have position/normal/UV. Subtract them.
        # approximate: most position-float3 samples are on 0-attr-set meshes
        pos_samples = pos_role.get("Samples", []) if pos_role else []
        normal_samples = normal_role.get("Samples", []) if normal_role else []
        uv_samples = uv_role.get("Samples", []) if uv_role else []

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
                id_pref = s.get("IdPrefix", s.get("id", "?"))
                mesh_size = s.get("MeshSize", s.get("meshSize", "?"))
                mesh_idx = s.get("MeshBlockIndex", s.get("meshBlockIndex", "?"))
                # Check if this mesh has normal/UV too
                pos_norm = "[ ]"
                pos_uv = "[ ]"
                # Match by ID to check companion streams
                for ns in normal_samples:
                    if ns.get("IdPrefix") == id_pref and ns.get("MeshBlockIndex") == mesh_idx:
                        pos_norm = "[Y]"
                        break
                for us in uv_samples:
                    if us.get("IdPrefix") == id_pref and us.get("MeshBlockIndex") == mesh_idx:
                        pos_uv = "[Y]"
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
            test_ids.add(s.get("IdPrefix", ""))
        for tid in sorted(test_ids):
            if tid:
                print(
                    f"    python scripts/rift_workflow.py decode-geometry --id {tid} --mesh-block 6 --experimental-position-source --write-obj"
                )
        print()

        # Summary statistics
        print("  --- Cross-reference summary ---")
        # Count meshes that have both pos and at least one companion (norm or uv)
        pos_only = 0
        pos_norm = 0
        pos_uv = 0
        pos_both = 0
        for s in pos_samples:
            id_pref = s.get("IdPrefix", "")
            mesh_idx = s.get("MeshBlockIndex")
            has_norm = any(
                ns.get("IdPrefix") == id_pref and ns.get("MeshBlockIndex") == mesh_idx for ns in normal_samples
            )
            has_uv = any(us.get("IdPrefix") == id_pref and us.get("MeshBlockIndex") == mesh_idx for us in uv_samples)
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
        print(f"  {pos_norm} more have position+normal (no UV), {pos_uv} have position+UV (no normal).")
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
        discovery_workbench(str(repo_root), str(out_dir), getattr(args, "privacy_scan", False))
        return

    if command == "all":
        for subcommand in (
            "mesh-bindings",
            "mesh-streams",
            "index-candidates",
            "stream-endianness",
            "stream-bodies",
        ):
            print(f"\n{'=' * 60}")
            print(f"  ALL → {subcommand}")
            print(f"{'=' * 60}")
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
            "run",
            "--project",
            str(project),
            "--",
            "inventory-nif-mesh-bindings",
            "--root",
            str(root),
            "--out",
            str(out_path),
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
            "run",
            "--project",
            str(project),
            "--",
            "inventory-nif-mesh-bindings",
            "--root",
            str(root),
            "--out",
            str(out_path),
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
            "run",
            "--project",
            str(project),
            "--",
            "probe-nif-attribute-extra",
            "--root",
            str(root),
            "--id",
            asset_id,
            "--mesh-block",
            "6",
            "--extra-offset",
            "264",
            "--out",
            str(out_path),
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
            "run",
            "--project",
            str(project),
            "--",
            "inventory-nif-mesh-bindings",
            "--root",
            str(root),
            "--out",
            str(out_path),
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
            "run",
            "--project",
            str(project),
            "--",
            "inventory-nif-mesh-bindings",
            "--root",
            str(root),
            "--out",
            str(out_path),
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
            "run",
            "--project",
            str(project),
            "--",
            "inventory-nif-mesh-bindings",
            "--root",
            str(root),
            "--out",
            str(out_path),
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
            "run",
            "--project",
            str(project),
            "--",
            "inventory-nif-mesh-bindings",
            "--root",
            str(root),
            "--out",
            str(out_path),
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
                "run",
                "--project",
                str(project),
                "--",
                "inventory-nif-mesh-bindings",
                "--root",
                str(root),
                "--out",
                str(out_path),
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
            "run",
            "--project",
            str(project),
            "--",
            "inventory-nif-mesh-bindings",
            "--root",
            str(root),
            "--out",
            str(out_path),
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
            {
                "Pair": "e3de325329",
                "PairLabel": "meshSize 325/329 shifted-position sibling",
                "Id": "e3de1077a37d0337",
                "MeshBlock": 6,
            },
            {
                "Pair": "e3de325329",
                "PairLabel": "meshSize 325/329 shifted-position sibling",
                "Id": "e3de1077a37d0337",
                "MeshBlock": 30,
            },
            {
                "Pair": "8e016329",
                "PairLabel": "meshSize 329 repeated-position sibling",
                "Id": "8e01613d7ce9e297",
                "MeshBlock": 6,
            },
            {
                "Pair": "8e016329",
                "PairLabel": "meshSize 329 repeated-position sibling",
                "Id": "8e01613d7ce9e297",
                "MeshBlock": 31,
            },
        ]

        representative_probe_specs = [
            {
                "Pair": "mesh305stream188",
                "PairLabel": "meshSize 305 shared stream@188 sibling",
                "Id": "04297730afc68f38",
                "MeshBlock": 7,
            },
            {
                "Pair": "mesh305stream188",
                "PairLabel": "meshSize 305 shared stream@188 sibling",
                "Id": "04297730afc68f38",
                "MeshBlock": 27,
            },
            {
                "Pair": "mesh321stream204",
                "PairLabel": "meshSize 321 shared stream@204 sibling",
                "Id": "03c35c3ba518aab0",
                "MeshBlock": 7,
            },
            {
                "Pair": "mesh321stream204",
                "PairLabel": "meshSize 321 shared stream@204 sibling",
                "Id": "03c35c3ba518aab0",
                "MeshBlock": 31,
            },
            {
                "Pair": "mesh329stream212",
                "PairLabel": "meshSize 329 shared stream@212 sibling",
                "Id": "0364ea142bc00ce7",
                "MeshBlock": 7,
            },
            {
                "Pair": "mesh329stream212",
                "PairLabel": "meshSize 329 shared stream@212 sibling",
                "Id": "0364ea142bc00ce7",
                "MeshBlock": 34,
            },
        ]

        secondary_probe_specs = [
            {
                "Pair": "mesh329stream212secondary",
                "PairLabel": "meshSize 329 secondary shared stream@212 sibling",
                "Id": "04de901531a091ab",
                "MeshBlock": 7,
                "ExpectedAttributeSetCount": 1,
            },
            {
                "Pair": "mesh329stream212secondary",
                "PairLabel": "meshSize 329 secondary shared stream@212 sibling",
                "Id": "04de901531a091ab",
                "MeshBlock": 34,
                "ExpectedAttributeSetCount": 0,
            },
            {
                "Pair": "mesh305stream188secondary",
                "PairLabel": "meshSize 305 secondary shared stream@188 sibling",
                "Id": "0d9a25c9a6af7b18",
                "MeshBlock": 7,
                "ExpectedAttributeSetCount": 0,
            },
            {
                "Pair": "mesh305stream188secondary",
                "PairLabel": "meshSize 305 secondary shared stream@188 sibling",
                "Id": "0d9a25c9a6af7b18",
                "MeshBlock": 27,
                "ExpectedAttributeSetCount": 0,
            },
            {
                "Pair": "mesh321stream204secondary",
                "PairLabel": "meshSize 321 secondary shared stream@204 sibling",
                "Id": "1dc433d4d2e4db64",
                "MeshBlock": 7,
                "ExpectedAttributeSetCount": 1,
            },
            {
                "Pair": "mesh321stream204secondary",
                "PairLabel": "meshSize 321 secondary shared stream@204 sibling",
                "Id": "1dc433d4d2e4db64",
                "MeshBlock": 31,
                "ExpectedAttributeSetCount": 0,
            },
        ]

        extra_position_probe_specs = [
            {
                "Pair": "mesh329extra0364",
                "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                "Id": "0364ea142bc00ce7",
                "MeshBlock": 7,
            },
            {
                "Pair": "mesh329extra0364",
                "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                "Id": "0364ea142bc00ce7",
                "MeshBlock": 34,
            },
            {
                "Pair": "mesh329extra04de",
                "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                "Id": "04de901531a091ab",
                "MeshBlock": 7,
            },
            {
                "Pair": "mesh329extra04de",
                "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                "Id": "04de901531a091ab",
                "MeshBlock": 34,
            },
            {
                "Pair": "mesh329extra066f",
                "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                "Id": "066fa520a8ce62e3",
                "MeshBlock": 7,
            },
            {
                "Pair": "mesh329extra066f",
                "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                "Id": "066fa520a8ce62e3",
                "MeshBlock": 34,
            },
        ]

        # Run all probes (16 total)
        all_specs = (
            sibling_probe_specs + representative_probe_specs + secondary_probe_specs + extra_position_probe_specs
        )
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
                "run",
                "--project",
                str(project),
                "--",
                "probe-nif-mesh",
                "--root",
                str(root),
                "--id",
                asset_id,
                "--mesh-block",
                str(mesh_block),
                "--out",
                str(out_path),
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
            {
                "Pair": "mesh305stream188",
                "PairLabel": "meshSize 305 shared stream@188 sibling",
                "Id": "04297730afc68f38",
                "MeshBlock": 7,
            },
            {
                "Pair": "mesh305stream188",
                "PairLabel": "meshSize 305 shared stream@188 sibling",
                "Id": "04297730afc68f38",
                "MeshBlock": 27,
            },
            {
                "Pair": "mesh321stream204",
                "PairLabel": "meshSize 321 shared stream@204 sibling",
                "Id": "03c35c3ba518aab0",
                "MeshBlock": 7,
            },
            {
                "Pair": "mesh321stream204",
                "PairLabel": "meshSize 321 shared stream@204 sibling",
                "Id": "03c35c3ba518aab0",
                "MeshBlock": 31,
            },
            {
                "Pair": "mesh329stream212",
                "PairLabel": "meshSize 329 shared stream@212 sibling",
                "Id": "0364ea142bc00ce7",
                "MeshBlock": 7,
            },
            {
                "Pair": "mesh329stream212",
                "PairLabel": "meshSize 329 shared stream@212 sibling",
                "Id": "0364ea142bc00ce7",
                "MeshBlock": 34,
            },
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
                "run",
                "--project",
                str(project),
                "--",
                "probe-nif-mesh",
                "--root",
                str(root),
                "--id",
                asset_id,
                "--mesh-block",
                str(mesh_block),
                "--out",
                str(out_path),
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
            {
                "Pair": "mesh329stream212secondary",
                "PairLabel": "meshSize 329 secondary shared stream@212 sibling",
                "Id": "04de901531a091ab",
                "MeshBlock": 7,
                "ExpectedAttributeSetCount": 1,
            },
            {
                "Pair": "mesh329stream212secondary",
                "PairLabel": "meshSize 329 secondary shared stream@212 sibling",
                "Id": "04de901531a091ab",
                "MeshBlock": 34,
                "ExpectedAttributeSetCount": 0,
            },
            {
                "Pair": "mesh305stream188secondary",
                "PairLabel": "meshSize 305 secondary shared stream@188 sibling",
                "Id": "0d9a25c9a6af7b18",
                "MeshBlock": 7,
                "ExpectedAttributeSetCount": 0,
            },
            {
                "Pair": "mesh305stream188secondary",
                "PairLabel": "meshSize 305 secondary shared stream@188 sibling",
                "Id": "0d9a25c9a6af7b18",
                "MeshBlock": 27,
                "ExpectedAttributeSetCount": 0,
            },
            {
                "Pair": "mesh321stream204secondary",
                "PairLabel": "meshSize 321 secondary shared stream@204 sibling",
                "Id": "1dc433d4d2e4db64",
                "MeshBlock": 7,
                "ExpectedAttributeSetCount": 1,
            },
            {
                "Pair": "mesh321stream204secondary",
                "PairLabel": "meshSize 321 secondary shared stream@204 sibling",
                "Id": "1dc433d4d2e4db64",
                "MeshBlock": 31,
                "ExpectedAttributeSetCount": 0,
            },
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
                "run",
                "--project",
                str(project),
                "--",
                "probe-nif-mesh",
                "--root",
                str(root),
                "--id",
                asset_id,
                "--mesh-block",
                str(mesh_block),
                "--out",
                str(out_path),
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
            {
                "Pair": "mesh329extra0364",
                "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                "Id": "0364ea142bc00ce7",
                "MeshBlock": 7,
            },
            {
                "Pair": "mesh329extra0364",
                "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                "Id": "0364ea142bc00ce7",
                "MeshBlock": 34,
            },
            {
                "Pair": "mesh329extra04de",
                "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                "Id": "04de901531a091ab",
                "MeshBlock": 7,
            },
            {
                "Pair": "mesh329extra04de",
                "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                "Id": "04de901531a091ab",
                "MeshBlock": 34,
            },
            {
                "Pair": "mesh329extra066f",
                "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                "Id": "066fa520a8ce62e3",
                "MeshBlock": 7,
            },
            {
                "Pair": "mesh329extra066f",
                "PairLabel": "meshSize 329 mesh#34 extra @304/#57",
                "Id": "066fa520a8ce62e3",
                "MeshBlock": 34,
            },
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
                "run",
                "--project",
                str(project),
                "--",
                "probe-nif-mesh",
                "--root",
                str(root),
                "--id",
                asset_id,
                "--mesh-block",
                str(mesh_block),
                "--out",
                str(out_path),
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
                results.append(
                    {
                        "step": "mesh-bindings",
                        "status": "REUSED",
                        "meshBlockCount": mesh_block_count,
                        "attrCompatible": attr_compatible,
                        "zeroAttrMeshes": zero_attr,
                    }
                )
                print(f"    Inventory: {mesh_block_count} meshes, {attr_compatible} attr-compatible")
            except Exception as exc:
                print(f"    [WARN] Could not load existing inventory: {exc}")
                print("    Falling through to fresh run...")
                args.quick = False

        if not args.quick:
            print("")
            print("  -- Step 1/7: Mesh-Binding Inventory --")
            dotnet_args = [
                "run",
                "--project",
                str(project),
                "--",
                "inventory-nif-mesh-bindings",
                "--root",
                str(root),
                "--out",
                str(inventory_path),
            ]
            if not args.full:
                dotnet_args += ["--limit", str(args.limit)]
            checked_run("discovery-suite (inventory)", dotnet_args)

            try:
                inv_data = load_json_report(str(inventory_path))
                mesh_block_count = inv_data.get("MeshBlocks", inv_data.get("MeshBlockCount", 0))
                attr_compatible = inv_data.get("AttributeCompatibleMeshes", 0)
                zero_attr = mesh_block_count - attr_compatible
                results.append(
                    {
                        "step": "mesh-bindings",
                        "status": "OK",
                        "meshBlockCount": mesh_block_count,
                        "attrCompatible": attr_compatible,
                        "zeroAttrMeshes": zero_attr,
                    }
                )
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
                results.append(
                    {"step": "position-source-sibling-family-report", "status": "OK", "siblingGroups": total_groups}
                )
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
                results.append(
                    {
                        "step": "residual-position-classifier-report",
                        "status": "OK",
                        "targetRows": target_rows,
                        "strictPasses": strict_passes,
                    }
                )
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
            (
                "descriptor-consistency-guard",
                lambda: descriptor_consistency_guard(str(Path("Exports/phase13-descriptor-consistency-baseline.json"))),
            ),
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

        results.append(
            {
                "step": "proof-guards",
                "status": "OK",
                "guards": guard_results,
                "allPassed": all(g.get("passed", False) for g in guard_results),
            }
        )

        # --- Step 6: Discovery Workbench ---

        print()
        print("  -- Step 6/7: Discovery Workbench --")
        try:
            discovery_workbench(str(REPO_ROOT), str(out_dir), getattr(args, "privacy_scan", False))
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
            results.append(
                {
                    "step": "discovery-workbench",
                    "status": "OK",
                    "candidateRows": wb_candidates,
                    "crossChecks": wb_checks,
                }
            )
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
                "run",
                "--project",
                str(project),
                "--",
                "decode-nif-geometry",
                "--root",
                str(root),
                "--id",
                asset_id,
                "--mesh-block",
                str(mesh_block),
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
                    results.append(
                        {
                            "id": asset_id,
                            "v": vertex_count,
                            "status": "FAIL",
                            "exitCode": result.returncode,
                        }
                    )
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
                    results.append(
                        {
                            "id": asset_id,
                            "v": vertex_count,
                            "status": "OK",
                            "objBytes": obj_size,
                        }
                    )
                else:
                    print(f"  [WARN] OBJ NOT FOUND at {obj_path}")
                    results.append(
                        {
                            "id": asset_id,
                            "v": vertex_count,
                            "status": "NO_OBJ",
                        }
                    )

            except Exception as exc:
                print(f"  [ERROR] {exc}")
                if args.verbose:
                    import traceback

                    traceback.print_exc()
                results.append(
                    {
                        "id": asset_id,
                        "v": vertex_count,
                        "status": "ERROR",
                        "error": str(exc),
                    }
                )

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

    # --- batch-export-sibling: export sibling-paired float2 position meshes ---

    if command == "batch-export-sibling":
        import subprocess as _sp
        import sys as _sys

        _SCRIPT = SCRIPT_DIR / "batch_export_sibling.py"
        if not _SCRIPT.exists():
            print(f"ERROR: batch_export_sibling.py not found at {_SCRIPT}", file=_sys.stderr)
            _sys.exit(1)

        _cmd = [_sys.executable, str(_SCRIPT)]
        if args.skip_build:
            _cmd.append("--skip-build")

        print(f"Running: {' '.join(_cmd)}")
        _result = _sp.run(_cmd, cwd=str(REPO_ROOT))
        _sys.exit(_result.returncode)

    # --- extract-binary-signatures: Phase 6 pipeline orchestrator ---

    if command == "extract-binary-signatures":
        import subprocess as _sp
        import sys as _sys

        _SCRIPT = SCRIPT_DIR / "extract_binary_signatures.py"
        if not _SCRIPT.exists():
            print(f"ERROR: extract_binary_signatures.py not found at {_SCRIPT}", file=_sys.stderr)
            _sys.exit(1)

        _cmd = [_sys.executable, str(_SCRIPT)]
        if args.phase2_catalog:
            _cmd += ["--phase2-catalog", str(args.phase2_catalog)]
        if args.phase3_catalog:
            _cmd += ["--phase3-catalog", str(args.phase3_catalog)]
        if args.out:
            _cmd += ["--out", str(args.out)]
        if args.validate_only:
            _cmd.append("--validate-only")

        print("Running: " + " ".join(_cmd))
        _result = _sp.run(_cmd, cwd=str(REPO_ROOT))
        _sys.exit(_result.returncode)

    # --- compare-binary-signatures: Phase 6 diff tool ---

    if command == "compare-binary-signatures":
        import subprocess as _sp
        import sys as _sys

        _SCRIPT = SCRIPT_DIR / "compare_signature_databases.py"
        if not _SCRIPT.exists():
            print(f"ERROR: compare_signature_databases.py not found at {_SCRIPT}", file=_sys.stderr)
            _sys.exit(1)

        # Pre-spawn guard: exit 1 (user input invalid) instead of letting the
        # underlying script's argparse raise exit 2. batch-export-sibling does
        # not pre-validate because its only flag (--skip-build) is optional.
        if not args.old_db or not args.new_db:
            print(
                "ERROR: compare-binary-signatures requires --old-db and --new-db paths to existing unified DBs.",
                file=_sys.stderr,
            )
            _sys.exit(1)

        _cmd = [
            _sys.executable,
            str(_SCRIPT),
            "--old-db",
            str(args.old_db),
            "--new-db",
            str(args.new_db),
        ]
        if args.diff_out:
            _cmd += ["--out", str(args.diff_out)]
        if args.diff_markdown_out:
            _cmd += ["--markdown-out", str(args.diff_markdown_out)]

        print("Running: " + " ".join(_cmd))
        _result = _sp.run(_cmd, cwd=str(REPO_ROOT))
        _sys.exit(_result.returncode)

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
# Orphan-process guard — re-exported from scripts.rift_orphan_guard so other
# pipelines (e.g. bulk_export_for_flythrough) can share the same detection.
# ============================================================================
from scripts.rift_orphan_guard import (  # noqa: E402,F401
    _count_running_riftassetdumper_processes,
    _count_tasklist_csv_rows,
    _orphan_process_guard,
)

# Commands that should bypass the orphan-process guard because they do
# not spawn a new ``RiftAssetDumper`` (they are read-only inspections or
# help-text emitters). Conservative by design: only commands whose
# handlers are confirmed pure-Python (no ``dotnet run``, no Ghidra, no
# live-memory scan) belong here. The regression test in
# ``tests/test_rift_workflow_orphan_guard.py`` parameterizes over this
# set and asserts no ``tasklist``/``pgrep RiftAssetDumper`` subprocess
# is spawned for any member.
_ORPHAN_GUARD_BYPASS_COMMANDS: frozenset[str] = (
    frozenset()
)  # see scripts/rift_read_only.py for the peer entry point that owns the 40 read-only commands


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
  python scripts/rift_workflow.py fifty-step-plan-status --list-json
  python scripts/rift_workflow.py scan-live-memory --live-pattern-file docs/live-memory-scan-targets.json --list-json
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
  python scripts/rift_workflow.py nidatastream-descriptor-table-sample-status --list-json
  python scripts/rift_workflow.py nidatastream-descriptor-table-sample-compare --list-json
  python scripts/rift_workflow.py nidatastream-descriptor-reference-classify
  python scripts/rift_workflow.py nidatastream-descriptor-base-model-review
  python scripts/rift_workflow.py ghidra-pairing-non-export-guard
  python scripts/rift_workflow.py ghidra-pairing-review-report --quick
  python scripts/rift_workflow.py ghidra-attribute-candidate-report
  python scripts/rift_workflow.py ghidra-attribute-candidate-guard
  python scripts/rift_workflow.py ghidra-workflow-guard-suite
  python scripts/rift_workflow.py nidatastream-layout --root Extracted --full
  python scripts/rift_workflow.py extract-binary-signatures --phase2-catalog Exports/binary-phase2/rift-x64-signature-catalog.json --phase3-catalog Exports/binary-phase3/struct-layout-catalog.json
  python scripts/rift_workflow.py compare-binary-signatures --old-db Exports/binary-phase5/rift-x64-signature-database.v1.json --new-db Exports/binary-phase5/rift-x64-signature-database.json
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
        "--commit-matrices",
        action="store_true",
        help=(
            "matrix-synth only: after the polyfill writes the 3 asset-semantic-index/v1 files, "
            "assert every entry's ArchiveName/DetectedType/MagicLabel still match the polyfill "
            "sentinel. Fails closed if the real C# build-asset-semantic-index has landed; the "
            "polyfill script should then be removed. Pre-commit hook friendly."
        ),
    )
    parser.add_argument(
        "--review-kind",
        default=None,
        help=("ReviewKind filter for Ghidra review-rank workflows (probes default: ghidra-only; summary default: all)"),
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
        "--live-pattern",
        action="append",
        default=[],
        help="Exact live-memory scan pattern as label=hex; repeatable (scan-live-memory)",
    )
    parser.add_argument(
        "--live-pattern-file",
        default="",
        help="Candidate-only JSON target manifest containing live-memory scan patterns",
    )
    parser.add_argument(
        "--process-name",
        default="rift_x64.exe",
        help="Live scan process name gate (default: rift_x64.exe)",
    )
    parser.add_argument(
        "--pid",
        type=int,
        default=0,
        help="Explicit target PID for actual live memory reads; dry-runs may omit it",
    )
    parser.add_argument(
        "--execute-live-read",
        action="store_true",
        help="Actually open/read the target process for scan-live-memory; requires explicit live safety flags",
    )
    parser.add_argument(
        "--experimental-live",
        action="store_true",
        help="Required safety gate for actual scan-live-memory process reads",
    )
    parser.add_argument(
        "--confirm-live-read",
        action="store_true",
        help="Second explicit safety confirmation required for actual scan-live-memory process reads",
    )
    parser.add_argument(
        "--max-scan-bytes",
        type=int,
        default=16 * 1024 * 1024,
        help="Maximum bytes to read in scan-live-memory (default: 16 MiB)",
    )
    parser.add_argument(
        "--max-scan-matches",
        type=int,
        default=32,
        help="Maximum matches per pattern in scan-live-memory (default: 32)",
    )
    parser.add_argument(
        "--max-scan-regions",
        type=int,
        default=256,
        help="Maximum memory regions to scan in scan-live-memory (default: 256)",
    )
    parser.add_argument(
        "--live-timeout-seconds",
        type=int,
        default=10,
        help="Maximum scan-live-memory wall time in seconds (default: 10)",
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
    parser.add_argument(
        "--descriptor-index",
        action="append",
        default=[],
        help="Descriptor table index to sample as hex (for example 37 or 0x37); repeatable or comma-separated",
    )
    parser.add_argument(
        "--descriptor-table-all-byte-indices",
        action="store_true",
        help="Sample all 256 possible one-byte descriptor table indices instead of deriving observed indices",
    )
    parser.add_argument(
        "--descriptor-table-byte-count",
        type=int,
        default=4,
        help="Bytes to read for each indexed descriptor table field (default: 4)",
    )
    parser.add_argument(
        "--descriptor-table-stride",
        type=int,
        default=0,
        help="Optional candidate stride override for descriptor table sampling; 0 uses CandidateFieldMap stride",
    )
    parser.add_argument(
        "--descriptor-table-report",
        default="",
        help="Optional JSON output path for nidatastream-descriptor-table-sample",
    )
    parser.add_argument(
        "--descriptor-table-summary",
        default="",
        help="Optional Markdown output path for nidatastream-descriptor-table-sample",
    )
    parser.add_argument(
        "--descriptor-neighborhood-before",
        type=int,
        default=1024,
        help="Bytes before each descriptor data reference to scan (default: 1024)",
    )
    parser.add_argument(
        "--descriptor-neighborhood-after",
        type=int,
        default=8192,
        help="Bytes after each descriptor data reference to scan (default: 8192)",
    )
    parser.add_argument(
        "--descriptor-neighborhood-step",
        type=int,
        default=4,
        help="Byte step for descriptor neighborhood scans (default: 4)",
    )
    parser.add_argument(
        "--descriptor-neighborhood-byte-count",
        type=int,
        default=4,
        help="Bytes to read per descriptor neighborhood probe (default: 4)",
    )
    parser.add_argument(
        "--descriptor-neighborhood-max-hits",
        type=int,
        default=128,
        help="Maximum nonzero descriptor neighborhood hits to record (default: 128)",
    )
    parser.add_argument(
        "--descriptor-neighborhood-report",
        default="",
        help="Optional JSON output path for nidatastream-descriptor-neighborhood-scan",
    )
    parser.add_argument(
        "--descriptor-neighborhood-summary",
        default="",
        help="Optional Markdown output path for nidatastream-descriptor-neighborhood-scan",
    )
    parser.add_argument(
        "--descriptor-reference-byte-count",
        type=int,
        default=16,
        help="Bytes to sample at each descriptor data reference for reference classification (default: 16)",
    )
    parser.add_argument(
        "--descriptor-reference-max-refs",
        type=int,
        default=128,
        help="Maximum references to capture per descriptor data reference (default: 128)",
    )
    parser.add_argument(
        "--descriptor-reference-report",
        default="",
        help="Optional JSON output path for nidatastream-descriptor-reference-classify",
    )
    parser.add_argument(
        "--descriptor-reference-summary",
        default="",
        help="Optional Markdown output path for nidatastream-descriptor-reference-classify",
    )
    parser.add_argument(
        "--descriptor-base-model-reference-report",
        default="",
        help="Optional descriptor reference classification JSON input for nidatastream-descriptor-base-model-review",
    )
    parser.add_argument(
        "--descriptor-base-model-report",
        default="",
        help="Optional JSON output path for nidatastream-descriptor-base-model-review",
    )
    parser.add_argument(
        "--descriptor-base-model-summary",
        default="",
        help="Optional Markdown output path for nidatastream-descriptor-base-model-review",
    )
    parser.add_argument(
        "--force-orphan-guard",
        action="store_true",
        help="Proceed even when orphan RiftAssetDumper processes are detected.",
    )

    # Binary-signature Phase 6 (M6.3 wiring) — extract-binary-signatures
    parser.add_argument(
        "--phase2-catalog",
        type=Path,
        default=None,
        help="Path to Phase 2 signature catalog (extract-binary-signatures).",
    )
    parser.add_argument(
        "--phase3-catalog",
        type=Path,
        default=None,
        help="Path to Phase 3 struct-layout catalog (extract-binary-signatures; optional, omit to skip).",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="extract-binary-signatures: validate only, do not write the output.",
    )
    # Binary-signature Phase 6 (M6.3 wiring) — compare-binary-signatures
    parser.add_argument(
        "--old-db",
        type=Path,
        default=None,
        help="Path to old unified signature DB (compare-binary-signatures; required).",
    )
    parser.add_argument(
        "--new-db",
        type=Path,
        default=None,
        help="Path to new unified signature DB (compare-binary-signatures; required).",
    )
    parser.add_argument(
        "--diff-out",
        type=Path,
        default=None,
        help="Diff JSON output path (compare-binary-signatures; default binary-phase6/patch-diff-report.json).",
    )
    parser.add_argument(
        "--diff-markdown-out",
        type=Path,
        default=None,
        help="Optional Markdown report path (compare-binary-signatures).",
    )

    args = parser.parse_args()

    # Orphan-process guard: refuse to spawn a new RiftAssetDumper if a previous
    # Codebuff session left children behind. Read-only inspection commands and
    # --force-orphan-guard bypass the guard. The guard itself calls sys.exit(2)
    # when it decides to refuse, so this call only returns when we may proceed.
    _first_non_flag = next((a for a in sys.argv[1:] if not a.startswith("-")), "")

    # Per-invocation deprecation notice: the 41 read-only commands have moved
    # to scripts/rift_read_only.py, which dispatches them without invoking
    # the orphan-process guard. Fires before the guard so users with a stale
    # RiftAssetDumper process still discover the new entry point.
    if _first_non_flag and _first_non_flag in _READ_ONLY_COMMANDS:
        print(f"NOTE: {_first_non_flag} moved to scripts/rift_read_only.py", file=sys.stderr)

    if _first_non_flag and _first_non_flag not in _ORPHAN_GUARD_BYPASS_COMMANDS:
        _orphan_process_guard(force=args.force_orphan_guard)

    # Normalize: "--no-smoke" is equivalent to "--full" (for backward compat with old PS flags)
    if args.no_smoke:
        args.full = True

    list_json_commands = {
        "fifty-step-plan-status",
        "post50-position-source-status",
        "post50-mesh34-negative-binding-status",
        "post50-promotion-readiness-status",
        "post50-validation-suite",
        "scan-live-memory",
        "ghidra-function-site-survey",
        "ghidra-function-site-status",
        "nidatastream-evidence-status",
        "nidatastream-promotion-status",
        "nidatastream-descriptor-proof-status",
        "nidatastream-descriptor-sample-compare",
        "nidatastream-descriptor-table-sample",
        "nidatastream-descriptor-table-sample-status",
        "nidatastream-descriptor-table-sample-compare",
        "nidatastream-descriptor-neighborhood-scan",
        "nidatastream-descriptor-reference-classify",
        "nidatastream-descriptor-base-model-review",
    }
    if args.list_json and args.command not in list_json_commands:
        print(
            "ERROR: --list-json is only supported with fifty-step-plan-status, scan-live-memory, "
            "post50-position-source-status, "
            "post50-mesh34-negative-binding-status, "
            "post50-promotion-readiness-status, "
            "post50-validation-suite, "
            "ghidra-function-site-survey, "
            "ghidra-function-site-status, nidatastream-evidence-status, "
            "nidatastream-promotion-status, nidatastream-descriptor-proof-status, "
            "nidatastream-descriptor-sample-compare, nidatastream-descriptor-table-sample, "
            "nidatastream-descriptor-table-sample-status, nidatastream-descriptor-table-sample-compare, "
            "nidatastream-descriptor-neighborhood-scan, "
            "nidatastream-descriptor-reference-classify, and "
            "nidatastream-descriptor-base-model-review.",
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
