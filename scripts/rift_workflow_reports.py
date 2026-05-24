#!/usr/bin/env python3
"""RIFT asset workflow report generators — ported from Invoke-RiftAssetWorkflow.ps1.

Contains:
- show_report_summary()          — JSON report summary (8 mode branches)
- semantic_hint_cross_tab()      — NIF semantic hint cross-tabulation
- discovery_workbench()          — Discovery workbench runner + validator

All functions use the utility layer from rift_workflow_utils.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.rift_workflow_utils import (  # noqa: E402
    checked_run,
    format_markdown_cell,
    format_nif_usage_access,
    format_proof_review_summary,
    format_vector_sample,
    json_array_count_or_dash,
    json_double_or_none,
    json_value_or_dash,
    load_json_report,
    measure_sum_or_zero,
    safe_int,
    semantic_hint_bucket,
    semantic_hint_primary_model,
    top_text,
)

# ============================================================================
# Show-ReportSummary — mirrors the PS switch($ModeName) block
# ============================================================================


def _show_asset_signatures(report: dict[str, Any]) -> None:
    """Show summary for AssetSignatures / AssetSemanticIndex modes."""
    entries = report.get("Entries")
    entry_count = len(entries) if isinstance(entries, list) else 0

    print(
        f"schema={report.get('SchemaVersion', '?')} "
        f"inspected={report.get('InspectedPayloads', '?')} "
        f"failed={report.get('Failed', '?')} "
        f"entries={entry_count}"
    )

    filters = report.get("SemanticCategoryFilters")
    if filters and isinstance(filters, list) and filters:
        print(f"Semantic filters: {', '.join(str(f) for f in filters)}")

    type_counts = report.get("TypeCounts")
    if type_counts and isinstance(type_counts, list):
        print(
            "Types: "
            + top_text(
                type_counts,
                lambda g: f"{json_value_or_dash(g, 'Value')}={json_value_or_dash(g, 'Count')}",
                10,
            )
        )

    semantic_cats = report.get("SemanticCategoryCounts")
    if semantic_cats and isinstance(semantic_cats, list):
        print(
            "Semantic categories: "
            + top_text(
                semantic_cats,
                lambda g: f"{json_value_or_dash(g, 'Value')}={json_value_or_dash(g, 'Count')}",
                10,
            )
        )

    sig_groups = report.get("SignatureGroups")
    if sig_groups and isinstance(sig_groups, list):
        print(
            "Top signatures: "
            + top_text(
                sig_groups,
                lambda g: (
                    f"{json_value_or_dash(g, 'Type')} "
                    f"{json_value_or_dash(g, 'First16')} "
                    f"count={json_value_or_dash(g, 'Count')} "
                    f"size={json_value_or_dash(g, 'MinSize')}.."
                    f"{json_value_or_dash(g, 'MaxSize')} "
                    f"magic={json_value_or_dash(g, 'MagicLabel')}"
                ),
                8,
            )
        )

    # XML groups
    xml_groups = [
        g
        for g in (sig_groups or [])
        if isinstance(g, dict)
        and g.get("XmlTagCounts")
        and isinstance(g["XmlTagCounts"], list)
        and len(g["XmlTagCounts"]) > 0
    ]
    if xml_groups:
        print(
            "XML tag families: "
            + top_text(
                xml_groups,
                lambda g: (
                    f"{json_value_or_dash(g, 'Type')}:"
                    + top_text(
                        g["XmlTagCounts"],
                        lambda c: f"{json_value_or_dash(c, 'Value')}="
                        f"{json_value_or_dash(c, 'Count')}",
                        5,
                    )
                ),
                5,
            )
        )
        print(
            "XML attribute families: "
            + top_text(
                xml_groups,
                lambda g: (
                    f"{json_value_or_dash(g, 'Type')}:"
                    + top_text(
                        g["XmlAttributeCounts"],
                        lambda c: f"{json_value_or_dash(c, 'Value')}="
                        f"{json_value_or_dash(c, 'Count')}",
                        5,
                    )
                ),
                5,
            )
        )

    # XML parse statuses
    xml_status_groups = [
        g
        for g in (sig_groups or [])
        if isinstance(g, dict)
        and g.get("XmlParseStatusCounts")
        and isinstance(g["XmlParseStatusCounts"], list)
        and len(g["XmlParseStatusCounts"]) > 0
    ]
    if xml_status_groups:
        print(
            "XML parse statuses: "
            + top_text(
                xml_status_groups,
                lambda g: (
                    f"{json_value_or_dash(g, 'Type')}:"
                    + top_text(
                        g["XmlParseStatusCounts"],
                        lambda c: f"{json_value_or_dash(c, 'Value')}="
                        f"{json_value_or_dash(c, 'Count')}",
                        5,
                    )
                ),
                5,
            )
        )

    # XML parse warnings
    xml_warning_groups = [
        g
        for g in (sig_groups or [])
        if isinstance(g, dict)
        and g.get("XmlParseWarningCounts")
        and isinstance(g["XmlParseWarningCounts"], list)
        and len(g["XmlParseWarningCounts"]) > 0
    ]
    if xml_warning_groups:
        print(
            "XML parse warnings: "
            + top_text(
                xml_warning_groups,
                lambda g: (
                    f"{json_value_or_dash(g, 'Type')}:"
                    + top_text(
                        g["XmlParseWarningCounts"],
                        lambda c: f"{json_value_or_dash(c, 'Value')}="
                        f"{json_value_or_dash(c, 'Count')}",
                        5,
                    )
                ),
                5,
            )
        )


def _show_mesh_bindings(report: dict[str, Any]) -> None:
    """Show summary for MeshBindings mode."""
    print(
        f"NIF payloads={json_value_or_dash(report, 'NifPayloads')} "
        f"meshBlocks={json_value_or_dash(report, 'MeshBlocks')} "
        f"links={json_value_or_dash(report, 'CandidateLinks')} "
        f"ghidraLayout={json_value_or_dash(report, 'GhidraStyleLayoutValidStreamBodies')} "
        f"shifted={json_value_or_dash(report, 'LegacyOffsetShiftedStreamBodies')} "
        f"roleDeltas={json_value_or_dash(report, 'GhidraRoleDeltaStreamBodies')} "
        f"pairMeshes={json_value_or_dash(report, 'PairCompatibleMeshes')} "
        f"pairLinks={json_value_or_dash(report, 'PairCompatibleLinks')} "
        f"ghidraPairMeshes={json_value_or_dash(report, 'GhidraPairCompatibleMeshes')} "
        f"ghidraPairLinks={json_value_or_dash(report, 'GhidraPairCompatibleLinks')} "
        f"sharedPairs={json_value_or_dash(report, 'GhidraSharedPairings')} "
        f"legacyOnlyPairs={json_value_or_dash(report, 'LegacyOnlyPairings')} "
        f"ghidraOnlyPairs={json_value_or_dash(report, 'GhidraOnlyPairings')}"
    )

    role_groups = report.get("RoleGroups")
    if role_groups and isinstance(role_groups, list):
        print(
            "Top roles: "
            + top_text(
                role_groups,
                lambda g: f"{json_value_or_dash(g, 'Role')}={json_value_or_dash(g, 'Count')}",
            )
        )

    usage_access_roles = report.get("TopUsageAccessRoles")
    if usage_access_roles and isinstance(usage_access_roles, list):
        print(
            "Top usage/access roles: "
            + top_text(
                usage_access_roles,
                lambda g: (
                    f"{format_nif_usage_access(g)} "
                    f"{json_value_or_dash(g, 'Role')}="
                    f"{json_value_or_dash(g, 'Count')}"
                ),
                8,
            )
        )

    ghidra_role_deltas = report.get("TopGhidraRoleDeltas")
    if ghidra_role_deltas and isinstance(ghidra_role_deltas, list):
        print(
            "Top Ghidra role deltas: "
            + top_text(
                ghidra_role_deltas,
                lambda g: (
                    f"meshSize={json_value_or_dash(g, 'MeshSize')} "
                    f"payload={json_value_or_dash(g, 'DeclaredPayloadBytes')} "
                    f"{format_nif_usage_access(g)} "
                    f"{json_value_or_dash(g, 'LegacyRole')}->"
                    f"{json_value_or_dash(g, 'GhidraRole')}="
                    f"{json_value_or_dash(g, 'Count')} "
                    f"c={json_value_or_dash(g, 'AverageLegacyConfidence')}->"
                    f"{json_value_or_dash(g, 'AverageGhidraConfidence')}"
                ),
                8,
            )
        )

    position_siblings = report.get("TopPositionSourceSiblings")
    if position_siblings and isinstance(position_siblings, list):
        print(
            "Top position source sibling groups: "
            + top_text(
                position_siblings,
                lambda g: (
                    f"{json_value_or_dash(g, 'IdPrefix')} "
                    f"block#{json_value_or_dash(g, 'TargetBlockIndex')} "
                    f"payload={json_value_or_dash(g, 'DeclaredPayloadBytes')} "
                    f"{format_nif_usage_access(g)} "
                    f"count={json_value_or_dash(g, 'Count')} "
                    f"meshes={','.join(str(i) for i in (g.get('MeshBlockIndices') or [])[:4])} "
                    f"offsets={','.join(str(o) for o in (g.get('MeshPayloadOffsets') or [])[:4])}"
                ),
                5,
            )
        )

    residual_target = report.get("ResidualTargetMeshSizes")
    if residual_target and isinstance(residual_target, list):
        print(
            "Residual target mesh sizes: "
            + top_text(
                residual_target,
                lambda g: (
                    f"meshSize={json_value_or_dash(g, 'MeshSize')} "
                    f"meshes={json_value_or_dash(g, 'MeshBlockCount')} "
                    f"residuals={json_value_or_dash(g, 'ResidualStreamCount')} "
                    f"patterns={json_value_or_dash(g, 'ResidualPatternCount')}"
                ),
                10,
            )
        )

    residual_streams = report.get("TopResidualStreams")
    if residual_streams and isinstance(residual_streams, list):
        print(
            "Top residual streams (target mesh sizes, known geometry/sentinel roles removed): "
            + top_text(
                residual_streams,
                lambda g: (
                    f"meshSize={json_value_or_dash(g, 'MeshSize')} "
                    f"count={json_value_or_dash(g, 'Count')} "
                    f"stream@{json_value_or_dash(g, 'MeshPayloadOffset')} "
                    f"payload={json_value_or_dash(g, 'DeclaredPayloadBytes')} "
                    f"{format_nif_usage_access(g)} "
                    f"{json_value_or_dash(g, 'Role')} "
                    f"c={json_value_or_dash(g, 'RoleConfidence')} "
                    f"string={json_value_or_dash(g, 'StringValue')} "
                    f"ror3=v{json_value_or_dash(g, 'RotatedFloat3VectorCount')} "
                    f"finite={json_value_or_dash(g, 'RotatedFloat3FiniteVectorRatio')} "
                    f"plausible={json_value_or_dash(g, 'RotatedFloat3PlausibleValueRatio')} "
                    f"extent={json_value_or_dash(g, 'RotatedFloat3MaxExtent')} "
                    f"first16={json_value_or_dash(g, 'BodyFirst16')}"
                ),
                8,
            )
        )

    # Position role groups
    if role_groups and isinstance(role_groups, list):
        position_groups = [
            g
            for g in role_groups
            if isinstance(g, dict)
            and str(json_value_or_dash(g, "Role")) == "position-float3-ror1-lead"
        ]
        if position_groups:
            pos_role = position_groups[0]
            mesh_sizes = pos_role.get("MeshSizes")
            if mesh_sizes and isinstance(mesh_sizes, list):
                print(
                    "Position stream lead mesh sizes: "
                    + top_text(
                        mesh_sizes,
                        lambda g: f"meshSize={json_value_or_dash(g, 'Size')}:{json_value_or_dash(g, 'Count')}",
                        10,
                    )
                )
            payload_sizes = pos_role.get("DeclaredPayloadSizes")
            if payload_sizes and isinstance(payload_sizes, list):
                print(
                    "Position stream lead payload sizes: "
                    + top_text(
                        payload_sizes,
                        lambda g: f"payload={json_value_or_dash(g, 'Size')}:{json_value_or_dash(g, 'Count')}",
                        10,
                    )
                )
            samples = pos_role.get("Samples")
            if samples and isinstance(samples, list):
                print(
                    "Position stream lead samples: "
                    + top_text(
                        samples,
                        lambda s: (
                            f"{json_value_or_dash(s, 'IdPrefix')} "
                            f"meshSize={json_value_or_dash(s, 'MeshSize')} "
                            f"mesh=#{json_value_or_dash(s, 'MeshBlockIndex')} "
                            f"stream@{json_value_or_dash(s.get('Stream', {}), 'MeshPayloadOffset')}/"
                            f"#{json_value_or_dash(s.get('Stream', {}), 'TargetBlockIndex')} "
                            f"payload={json_value_or_dash(s.get('Stream', {}), 'DeclaredPayloadBytes')} "
                            f"{format_nif_usage_access(s.get('Stream', {}))}"
                        ),
                        5,
                    )
                )

    top_pairings = report.get("TopPairings")
    if top_pairings and isinstance(top_pairings, list):
        print(
            "Top pairings: "
            + top_text(
                top_pairings,
                lambda g: (
                    f"meshSize={json_value_or_dash(g, 'MeshSize')} "
                    f"count={json_value_or_dash(g, 'Count')} "
                    f"index[{format_nif_usage_access(g, 'IndexDataStreamUsage', 'IndexDataStreamAccess')}] "
                    f"{json_value_or_dash(g, 'IndexRole')}->"
                    f"vertex[{format_nif_usage_access(g, 'VertexDataStreamUsage', 'VertexDataStreamAccess')}] "
                    f"{json_value_or_dash(g, 'VertexRole')} "
                    f"v={json_value_or_dash(g, 'VertexCount')} "
                    f"max={json_value_or_dash(g, 'MaxIndexObserved')} "
                    f"pairs={json_value_or_dash(g, 'IndexPairCount')} "
                    f"list={json_value_or_dash(g, 'TriangleListTriangleCount')} "
                    f"strip={json_value_or_dash(g, 'TriangleStripWindowCount')} "
                    f"cov={json_value_or_dash(g, 'MaxIndexCoverageRatio')}"
                ),
            )
        )

    top_ghidra_pairings = report.get("TopGhidraPairings")
    if top_ghidra_pairings and isinstance(top_ghidra_pairings, list):
        print(
            "Top Ghidra pairings: "
            + top_text(
                top_ghidra_pairings,
                lambda g: (
                    f"meshSize={json_value_or_dash(g, 'MeshSize')} "
                    f"count={json_value_or_dash(g, 'Count')} "
                    f"index[{format_nif_usage_access(g, 'IndexDataStreamUsage', 'IndexDataStreamAccess')}] "
                    f"{json_value_or_dash(g, 'IndexRole')}->"
                    f"vertex[{format_nif_usage_access(g, 'VertexDataStreamUsage', 'VertexDataStreamAccess')}] "
                    f"{json_value_or_dash(g, 'VertexRole')} "
                    f"v={json_value_or_dash(g, 'VertexCount')} "
                    f"max={json_value_or_dash(g, 'MaxIndexObserved')} "
                    f"pairs={json_value_or_dash(g, 'IndexPairCount')} "
                    f"list={json_value_or_dash(g, 'TriangleListTriangleCount')} "
                    f"strip={json_value_or_dash(g, 'TriangleStripWindowCount')} "
                    f"cov={json_value_or_dash(g, 'MaxIndexCoverageRatio')}"
                ),
            )
        )

    top_ghidra_pairing_comparisons = report.get("TopGhidraPairingComparisons")
    if top_ghidra_pairing_comparisons and isinstance(top_ghidra_pairing_comparisons, list):
        print(
            "Top Ghidra pairing comparisons: "
            + top_text(
                top_ghidra_pairing_comparisons,
                lambda g: (
                    f"{json_value_or_dash(g, 'Status')} "
                    f"meshSize={json_value_or_dash(g, 'MeshSize')} "
                    f"count={json_value_or_dash(g, 'Count')} "
                    f"legacy={json_value_or_dash(g, 'LegacyIndexRole')}->"
                    f"{json_value_or_dash(g, 'LegacyVertexRole')} "
                    f"ghidra={json_value_or_dash(g, 'GhidraIndexRole')}->"
                    f"{json_value_or_dash(g, 'GhidraVertexRole')} "
                    f"c={json_value_or_dash(g, 'AverageLegacyConfidence')}->"
                    f"{json_value_or_dash(g, 'AverageGhidraConfidence')}"
                ),
            )
        )

    top_ghidra_pairing_review_findings = report.get("TopGhidraPairingReviewFindings")
    if top_ghidra_pairing_review_findings and isinstance(
        top_ghidra_pairing_review_findings, list
    ):
        print(
            "Top Ghidra pairing review findings: "
            + top_text(
                top_ghidra_pairing_review_findings,
                lambda g: (
                    f"{json_value_or_dash(g, 'ReviewKind')} "
                    f"p={json_value_or_dash(g, 'Priority')} "
                    f"meshSize={json_value_or_dash(g, 'MeshSize')} "
                    f"count={json_value_or_dash(g, 'Count')} "
                    f"legacy={json_value_or_dash(g, 'LegacyIndexRole')}->"
                    f"{json_value_or_dash(g, 'LegacyVertexRole')}"
                    f"({json_value_or_dash(g, 'LegacyVertexSemanticClass')}) "
                    f"ghidra={json_value_or_dash(g, 'GhidraIndexRole')}->"
                    f"{json_value_or_dash(g, 'GhidraVertexRole')}"
                    f"({json_value_or_dash(g, 'GhidraVertexSemanticClass')}) "
                    f"c={json_value_or_dash(g, 'AverageLegacyConfidence')}->"
                    f"{json_value_or_dash(g, 'AverageGhidraConfidence')} "
                    f"delta={json_value_or_dash(g, 'AverageConfidenceDelta')}"
                ),
            )
        )

    top_attr_sets = report.get("TopAttributeSets")
    if top_attr_sets and isinstance(top_attr_sets, list):
        print(
            "Top attribute sets: "
            + top_text(
                top_attr_sets,
                lambda g: (
                    f"meshSize={json_value_or_dash(g, 'MeshSize')} "
                    f"count={json_value_or_dash(g, 'Count')} "
                    f"p={json_value_or_dash(g, 'PositionDeclaredPayloadBytes')}/"
                    f"n={json_value_or_dash(g, 'NormalDeclaredPayloadBytes')}/"
                    f"uv={json_value_or_dash(g, 'UvDeclaredPayloadBytes')} "
                    f"v={json_value_or_dash(g, 'VertexCount')} "
                    f"topology={json_value_or_dash(g.get('Topology', {}), 'PrimaryTopology')}"
                ),
            )
        )

    top_attr_topologies = report.get("TopAttributeTopologies")
    if top_attr_topologies and isinstance(top_attr_topologies, list):
        print(
            "Top attribute topologies: "
            + top_text(
                top_attr_topologies,
                lambda g: (
                    f"{json_value_or_dash(g, 'Topology')} "
                    f"v={json_value_or_dash(g, 'VertexCount')} "
                    f"count={json_value_or_dash(g, 'Count')} "
                    f"list={json_value_or_dash(g, 'TriangleListTriangleCount')} "
                    f"strip={json_value_or_dash(g, 'TriangleStripTriangleCount')} "
                    f"quad={json_value_or_dash(g, 'QuadListQuadCount')}"
                ),
            )
        )

    top_attr_extras = report.get("TopAttributeExtraStreams")
    if top_attr_extras and isinstance(top_attr_extras, list):
        print(
            "Top attribute extras: "
            + top_text(
                top_attr_extras,
                lambda g: (
                    f"{json_value_or_dash(g, 'Topology')} "
                    f"v={json_value_or_dash(g, 'VertexCount')} "
                    f"extra@{json_value_or_dash(g, 'ExtraMeshPayloadOffset')} "
                    f"payload={json_value_or_dash(g, 'ExtraDeclaredPayloadBytes')} "
                    f"{json_value_or_dash(g, 'ExtraRole')} "
                    f"count={json_value_or_dash(g, 'Count')} "
                    f"fit={json_value_or_dash(g, 'FitSummary')}"
                ),
            )
        )

    fitness = report.get("TopAttributeExtraMappingFitness")
    if fitness and isinstance(fitness, list):
        print(
            "Top attribute extra mapping fitness: "
            + top_text(
                fitness,
                lambda g: (
                    f"meshSize={json_value_or_dash(g, 'MeshSize')} "
                    f"v={json_value_or_dash(g, 'VertexCount')} "
                    f"extra@{json_value_or_dash(g, 'ExtraMeshPayloadOffset')} "
                    f"{json_value_or_dash(g, 'ExtraRole')} "
                    f"count={json_value_or_dash(g, 'Count')} "
                    f"prefer={json_value_or_dash(g, 'PreferredMapping')} "
                    f"raw={json_value_or_dash(g, 'RawZeroBasedPreferredCount')} "
                    f"sub1={json_value_or_dash(g, 'SubtractOnePreferredCount')} "
                    f"avgDelta={json_value_or_dash(g, 'AverageMedianMaxEdgeDelta')} "
                    f"segDelta={json_value_or_dash(g, 'AverageSegmentedMedianMaxEdgeDelta')} "
                    f"normGap={json_value_or_dash(g, 'AverageSegmentedMedianNormalDeltaGap')} "
                    f"uvGap={json_value_or_dash(g, 'AverageSegmentedMedianUvDeltaGap')} "
                    f"areaGap={json_value_or_dash(g, 'AverageSegmentedMedianTriangleAreaGap')} "
                    f"proofSwitches="
                    f"{json_value_or_dash(g, 'AverageRawFirstSegmentDominantPlaneSwitchCount')}/"
                    f"{json_value_or_dash(g, 'AverageSubtractOneFirstSegmentDominantPlaneSwitchCount')} "
                    f"signSwitches="
                    f"{json_value_or_dash(g, 'AverageRawFirstSegmentDominantSignedAreaSignSwitchCount')}/"
                    f"{json_value_or_dash(g, 'AverageSubtractOneFirstSegmentDominantSignedAreaSignSwitchCount')} "
                    f"parityBreaks="
                    f"{json_value_or_dash(g, 'AverageRawFirstSegmentNonAlternatingParityTransitionCount')}/"
                    f"{json_value_or_dash(g, 'AverageSubtractOneFirstSegmentNonAlternatingParityTransitionCount')} "
                    f"segments={json_value_or_dash(g, 'AverageSegmentCount')} "
                    f"droppedCross={json_value_or_dash(g, 'AverageDroppedCrossSegmentWindowCount')} "
                    f"strip={json_value_or_dash(g, 'DominantStripStructureHint')} "
                    f"bridges={json_value_or_dash(g, 'AverageMirroredBridgeCount')} "
                    f"sentinels={json_value_or_dash(g, 'SentinelRestartValueCountTotal')}"
                ),
            )
        )


def _show_mesh_probe(report: dict[str, Any]) -> None:
    """Show summary for MeshProbe mode."""
    print(
        f"version={json_value_or_dash(report, 'NifVersion')} "
        f"meshes={json_value_or_dash(report, 'MeshBlockCount')} "
        f"emitted={json_value_or_dash(report, 'MeshesEmitted')} "
        f"links={json_value_or_dash(report, 'CandidateLinks')} "
        f"pairings={json_value_or_dash(report, 'Pairings')} "
        f"ghidraPairings={json_value_or_dash(report, 'GhidraPairings')} "
        f"attributeSets={json_value_or_dash(report, 'AttributeSets')}"
    )

    meshes = report.get("Meshes")
    if meshes and isinstance(meshes, list):
        for mesh in meshes[:3]:
            print(
                f"Mesh #{json_value_or_dash(mesh, 'MeshBlockIndex')} "
                f"size={json_value_or_dash(mesh, 'MeshSize')} "
                f"streams={len(mesh.get('Streams') or [])} "
                f"pairings={len(mesh.get('Pairings') or [])} "
                f"ghidraPairings={len(mesh.get('GhidraPairings') or [])} "
                f"attributeSets={len(mesh.get('AttributeSets') or [])} "
                f"payloadWindows={len(mesh.get('PayloadWindows') or [])}"
            )

            streams = mesh.get("Streams")
            if streams and isinstance(streams, list):
                print(
                    "  roles: "
                    + top_text(
                        streams,
                        lambda s: (
                            f"@{json_value_or_dash(s, 'MeshPayloadOffset')}->"
                            f"#{json_value_or_dash(s, 'TargetBlockIndex')} "
                            f"payload={json_value_or_dash(s, 'DeclaredPayloadBytes')} "
                            f"{json_value_or_dash(s.get('RoleStats', {}), 'PrimaryRole')} "
                            f"c={json_value_or_dash(s.get('RoleStats', {}), 'Confidence')}"
                        ),
                        8,
                    )
                )

            pairings = mesh.get("Pairings")
            if pairings and isinstance(pairings, list):
                print(
                    "  pairings: "
                    + top_text(
                        pairings,
                        lambda p: (
                            f"index@{json_value_or_dash(p, 'IndexMeshPayloadOffset')}/"
                            f"#{json_value_or_dash(p, 'IndexBlockIndex')} "
                            f"max={json_value_or_dash(p, 'IndexMax')} -> "
                            f"stream@{json_value_or_dash(p, 'VertexMeshPayloadOffset')}/"
                            f"#{json_value_or_dash(p, 'VertexBlockIndex')} "
                            f"v={json_value_or_dash(p, 'VertexCount')}"
                        ),
                        5,
                    )
                )

            ghidra_pairings = mesh.get("GhidraPairings")
            if ghidra_pairings and isinstance(ghidra_pairings, list):
                print(
                    "  ghidra pairings: "
                    + top_text(
                        ghidra_pairings,
                        lambda p: (
                            f"candidateOnly={json_value_or_dash(p, 'CandidateOnly')} "
                            f"index@{json_value_or_dash(p, 'IndexMeshPayloadOffset')}/"
                            f"#{json_value_or_dash(p, 'IndexBlockIndex')} "
                            f"{json_value_or_dash(p, 'IndexRole')} "
                            f"max={json_value_or_dash(p, 'IndexMax')} -> "
                            f"stream@{json_value_or_dash(p, 'VertexMeshPayloadOffset')}/"
                            f"#{json_value_or_dash(p, 'VertexBlockIndex')} "
                            f"{json_value_or_dash(p, 'VertexRole')} "
                            f"v={json_value_or_dash(p, 'VertexCount')} "
                            f"posReview={json_value_or_dash(p.get('VertexPositionBoundsReview', {}), 'PassesBasicReview')} "
                            f"extent={json_value_or_dash(p.get('VertexPositionBoundsReview', {}), 'MaxExtent')} "
                            f"normalReview={json_value_or_dash(p.get('VertexNormalVectorReview', {}), 'PassesBasicReview')} "
                            f"nearUnit={json_value_or_dash(p.get('VertexNormalVectorReview', {}), 'NearUnitVectorRatio')} "
                            f"uvReview={json_value_or_dash(p.get('VertexUvRangeReview', {}), 'PassesBasicReview')} "
                            f"uvRange={json_value_or_dash(p.get('VertexUvRangeReview', {}), 'UvRangeRatio')}"
                        ),
                        5,
                    )
                )

            attr_sets = mesh.get("AttributeSets")
            if attr_sets and isinstance(attr_sets, list):
                print(
                    "  attributes: "
                    + top_text(
                        attr_sets,
                        lambda a: (
                            f"p@{json_value_or_dash(a, 'PositionMeshPayloadOffset')}/"
                            f"#{json_value_or_dash(a, 'PositionBlockIndex')} "
                            f"n@{json_value_or_dash(a, 'NormalMeshPayloadOffset')}/"
                            f"#{json_value_or_dash(a, 'NormalBlockIndex')} "
                            f"uv@{json_value_or_dash(a, 'UvMeshPayloadOffset')}/"
                            f"#{json_value_or_dash(a, 'UvBlockIndex')} "
                            f"v={json_value_or_dash(a, 'VertexCount')} "
                            f"topology={json_value_or_dash(a.get('Topology', {}), 'PrimaryTopology')} "
                            f"extras={len(a.get('ExtraStreams') or [])}"
                        ),
                        5,
                    )
                )

                for attr_set in attr_sets[:2]:
                    extras = attr_set.get("ExtraStreams")
                    if extras and isinstance(extras, list):
                        print(
                            "  attribute extras: "
                            + top_text(
                                extras,
                                lambda e: (
                                    f"@{json_value_or_dash(e, 'MeshPayloadOffset')}/"
                                    f"#{json_value_or_dash(e, 'BlockIndex')} "
                                    f"payload={json_value_or_dash(e, 'DeclaredPayloadBytes')} "
                                    f"{json_value_or_dash(e, 'Role')} "
                                    f"fit={json_value_or_dash(e, 'FitSummary')}"
                                ),
                                5,
                            )
                        )

            payload_windows = mesh.get("PayloadWindows")
            if payload_windows and isinstance(payload_windows, list):
                print(
                    "  payload windows: "
                    + top_text(
                        payload_windows,
                        lambda w: (
                            f"@{json_value_or_dash(w, 'PayloadOffset')} "
                            f"bytes={json_value_or_dash(w, 'ByteLength')} "
                            f"{json_value_or_dash(w, 'Role')} "
                            f"v={json_value_or_dash(w, 'VertexCount')}"
                        ),
                        5,
                    )
                )


def _show_attribute_extra_probe(report: dict[str, Any]) -> None:
    """Show summary for AttributeExtraProbe mode."""
    print(
        f"version={json_value_or_dash(report, 'NifVersion')} "
        f"mesh=#{json_value_or_dash(report, 'MeshBlockIndex')} "
        f"size={json_value_or_dash(report, 'MeshSize')} "
        f"attributeSets={json_value_or_dash(report, 'AttributeSets')} "
        f"extra@{json_value_or_dash(report, 'ExtraMeshPayloadOffset')} "
        f"matches={json_value_or_dash(report, 'Matches')}"
    )

    extras = report.get("ExtraStreams")
    if extras and isinstance(extras, list):
        for extra in extras[:3]:
            print(
                f"  extra @{json_value_or_dash(extra, 'ExtraMeshPayloadOffset')}/"
                f"#{json_value_or_dash(extra, 'ExtraBlockIndex')} "
                f"payload={json_value_or_dash(extra, 'ExtraDeclaredPayloadBytes')} "
                f"header={json_value_or_dash(extra, 'HeaderBytes')} "
                f"role={json_value_or_dash(extra, 'Role')} "
                f"fit={json_value_or_dash(extra, 'FitSummary')}"
            )
            print(f"    first64={json_value_or_dash(extra, 'BodyFirst64')}")

            top_bytes = extra.get("ByteHistogramTop")
            if top_bytes and isinstance(top_bytes, list):
                print(
                    "    top bytes: "
                    + top_text(
                        top_bytes,
                        lambda h: f"{json_value_or_dash(h, 'Hex')}x{json_value_or_dash(h, 'Count')}",
                        8,
                    )
                )

            index_compat = extra.get("IndexCompatibility")
            if index_compat and isinstance(index_compat, dict):
                print(
                    f"    index: {json_value_or_dash(index_compat, 'CandidateTopology')} "
                    f"min={json_value_or_dash(index_compat, 'MinIndex')} "
                    f"max={json_value_or_dash(index_compat, 'MaxIndex')} "
                    f"distinct={json_value_or_dash(index_compat, 'DistinctIndexCount')} "
                    f"withinVertexCount={json_value_or_dash(index_compat, 'MaxIndexWithinVertexCount')} "
                    f"maxCoverage={json_value_or_dash(index_compat, 'MaxIndexCoverageRatio')} "
                    f"distinctCoverage={json_value_or_dash(index_compat, 'DistinctIndexCoverageRatio')} "
                    f"usesZero={json_value_or_dash(index_compat, 'UsesZeroIndex')} "
                    f"baseHint={json_value_or_dash(index_compat, 'IndexBaseHint')}"
                )
                print(
                    f"    strip: nondegenerate="
                    f"{json_value_or_dash(index_compat, 'TriangleStripNonDegenerateWindowCount')}/"
                    f"{json_value_or_dash(index_compat, 'TriangleStripWindowCount')} "
                    f"stripDegenerate={json_value_or_dash(index_compat, 'TriangleStripDegenerateRatio')} "
                    f"fixedTripleDegenerate={json_value_or_dash(index_compat, 'DegenerateTriangleRatio')}"
                )

                strip_struct = index_compat.get("StripStructure")
                if strip_struct and isinstance(strip_struct, dict):
                    print(
                        f"    strip structure: {json_value_or_dash(strip_struct, 'Hint')} "
                        f"degRuns={json_value_or_dash(strip_struct, 'DegenerateRunCount')} "
                        f"maxDegRun={json_value_or_dash(strip_struct, 'MaxDegenerateRunLength')} "
                        f"nonDegRuns={json_value_or_dash(strip_struct, 'NonDegenerateRunCount')} "
                        f"maxNonDegRun={json_value_or_dash(strip_struct, 'MaxNonDegenerateRunLength')} "
                        f"adjacentRepeats={json_value_or_dash(strip_struct, 'AdjacentRepeatCount')} "
                        f"mirroredBridges={json_value_or_dash(strip_struct, 'MirroredAdjacentRepeatBridgeCount')} "
                        f"sentinels={json_value_or_dash(strip_struct, 'SentinelRestartValueCount')} "
                        f"zeroValues={json_value_or_dash(strip_struct, 'ZeroIndexValueCount')}"
                    )

                mappings = index_compat.get("MappingCandidates")
                if mappings and isinstance(mappings, list):
                    print(
                        "    mappings: "
                        + top_text(
                            mappings,
                            lambda m: (
                                f"{json_value_or_dash(m, 'Name')} "
                                f"valid={json_value_or_dash(m, 'ValidForVertexCount')} "
                                f"offset={json_value_or_dash(m, 'IndexOffset')} "
                                f"range={json_value_or_dash(m, 'MappedMinIndex')}.."
                                f"{json_value_or_dash(m, 'MappedMaxIndex')} "
                                f"referenced={json_value_or_dash(m, 'ReferencedVertexCount')} "
                                f"missing={json_value_or_dash(m, 'MissingVertexCount')} "
                                f"missingSample={','.join(str(s) for s in (m.get('MissingVertexSamples') or [])[:4])}"
                            ),
                            4,
                        )
                    )

            pos_samples = extra.get("PositionVertexSamples")
            if pos_samples and isinstance(pos_samples, list):
                print(
                    "    position samples: "
                    + top_text(pos_samples, format_vector_sample, 6)
                )

            norm_samples = extra.get("NormalVertexSamples")
            if norm_samples and isinstance(norm_samples, list):
                print(
                    "    normal samples: "
                    + top_text(norm_samples, format_vector_sample, 6)
                )

            uv_samples = extra.get("UvVertexSamples")
            if uv_samples and isinstance(uv_samples, list):
                print(
                    "    uv samples: "
                    + top_text(uv_samples, format_vector_sample, 6)
                )

            fit_values = extra.get("MappingPositionFitness")
            if fit_values and isinstance(fit_values, list) and fit_values:
                print(
                    "    position fit: "
                    + top_text(
                        fit_values,
                        lambda f: (
                            f"{json_value_or_dash(f, 'MappingName')} "
                            f"finite={json_value_or_dash(f, 'FiniteTriangleWindowCount')}/"
                            f"{json_value_or_dash(f, 'NonDegenerateTriangleWindowCount')} "
                            f"medianMax={json_value_or_dash(f, 'MedianMaxEdge')} "
                            f"segs={json_value_or_dash(f, 'SegmentCount')} "
                            f"segFinite={json_value_or_dash(f, 'SegmentedFiniteTriangleWindowCount')}/"
                            f"{json_value_or_dash(f, 'SegmentedTriangleWindowCount')} "
                            f"segMedian={json_value_or_dash(f, 'SegmentedMedianMaxEdge')} "
                            f"normMedian={json_value_or_dash(f, 'SegmentedMedianNormalDelta')} "
                            f"uvMedian={json_value_or_dash(f, 'SegmentedMedianUvDelta')} "
                            f"areaMedian={json_value_or_dash(f, 'SegmentedMedianTriangleArea')} "
                            f"nearZeroArea={json_value_or_dash(f, 'SegmentedNearZeroTriangleAreaCount')} "
                            f"firstSegTriangles={json_array_count_or_dash(f, 'FirstSegmentTriangles')} "
                            f"{format_proof_review_summary(f)} "
                            f"droppedDeg={json_value_or_dash(f, 'DroppedDegenerateWindowCount')} "
                            f"droppedCross={json_value_or_dash(f, 'DroppedCrossSegmentWindowCount')}"
                        ),
                        4,
                    )
                )

            views = extra.get("GroupedViews")
            if views and isinstance(views, list):
                print(
                    "    views: "
                    + top_text(
                        views,
                        lambda v: (
                            f"{json_value_or_dash(v, 'Name')} "
                            f"slots={json_value_or_dash(v, 'SlotCount')} "
                            f"bytes={json_value_or_dash(v, 'BytesPerSlot')} "
                            f"exact={json_value_or_dash(v, 'ExactFit')} "
                            f"rem={json_value_or_dash(v, 'RemainderBytes')}"
                        ),
                        4,
                    )
                )


def _show_simple_inventory(report: dict[str, Any], mode: str) -> None:
    """Show summary for MeshStreams, IndexCandidates, StreamEndianness, StreamBodies."""
    if mode == "MeshStreams":
        print(
            f"NIF payloads={json_value_or_dash(report, 'NifPayloads')} "
            f"meshBlocks={json_value_or_dash(report, 'MeshBlocks')} "
            f"links={json_value_or_dash(report, 'CandidateLinks')} "
            f"ambiguous={json_value_or_dash(report, 'AmbiguousCandidateLinks')}"
        )
        offsets = report.get("OffsetGroups")
        if offsets and isinstance(offsets, list):
            print(
                "Top offsets: "
                + top_text(
                    offsets,
                    lambda g: f"@{json_value_or_dash(g, 'PayloadOffset')}={json_value_or_dash(g, 'Count')}",
                )
            )
        patterns = report.get("TopPatterns")
        if patterns and isinstance(patterns, list):
            print(
                "Top patterns: "
                + top_text(
                    patterns,
                    lambda g: f"meshSize={json_value_or_dash(g, 'MeshSize')} count={json_value_or_dash(g, 'Count')}",
                )
            )

    elif mode == "IndexCandidates":
        print(
            f"NIF payloads={json_value_or_dash(report, 'NifPayloads')} "
            f"streams={json_value_or_dash(report, 'DataStreamBlocks')} "
            f"beLeads={json_value_or_dash(report, 'BigEndianLeadBodies')} "
            f"beTri={json_value_or_dash(report, 'BigEndianTriangleAlignedBodies')} "
            f"stripLess={json_value_or_dash(report, 'TriangleStripLessDegenerateBodies')}"
        )
        classes = report.get("ClassGroups")
        if classes and isinstance(classes, list):
            print(
                "Top classes: "
                + top_text(
                    classes,
                    lambda g: f"{json_value_or_dash(g, 'Classification')}={json_value_or_dash(g, 'Count')}",
                )
            )
        be_sigs = report.get("TopBigEndianIndexSignatures")
        if be_sigs and isinstance(be_sigs, list):
            print(
                "Top BE signatures: "
                + top_text(
                    be_sigs,
                    lambda g: (
                        f"payload={json_value_or_dash(g, 'DeclaredPayloadBytes')} "
                        f"count={json_value_or_dash(g, 'Count')} "
                        f"first16={json_value_or_dash(g, 'PayloadFirst16')}"
                    ),
                )
            )

    elif mode == "StreamEndianness":
        print(
            f"NIF payloads={json_value_or_dash(report, 'NifPayloads')} "
            f"evenBodies={json_value_or_dash(report, 'EvenLengthBodies')}"
        )
        classes = report.get("ClassGroups")
        if classes and isinstance(classes, list):
            print(
                "Top classes: "
                + top_text(
                    classes,
                    lambda g: f"{json_value_or_dash(g, 'Classification')}={json_value_or_dash(g, 'Count')}",
                )
            )

    elif mode == "StreamBodies":
        print(
            f"NIF payloads={json_value_or_dash(report, 'NifPayloads')} "
            f"validBodies={json_value_or_dash(report, 'ValidStreamBodies')} "
            f"invalid={json_value_or_dash(report, 'InvalidStreamBodies')} "
            f"ghidraLayout={json_value_or_dash(report, 'GhidraStyleLayoutValidStreamBodies')} "
            f"shifted={json_value_or_dash(report, 'LegacyOffsetShiftedStreamBodies')} "
            f"classDeltas={json_value_or_dash(report, 'GhidraClassificationDeltaStreamBodies')}"
        )
        sizes = report.get("PayloadSizeGroups")
        if sizes and isinstance(sizes, list):
            print(
                "Top sizes: "
                + top_text(
                    sizes,
                    lambda g: f"payload={json_value_or_dash(g, 'DeclaredPayloadBytes')} count={json_value_or_dash(g, 'Count')}",
                )
            )
        sigs = report.get("TopBodySignatures")
        if sigs and isinstance(sigs, list):
            print(
                "Top signatures: "
                + top_text(
                    sigs,
                    lambda g: (
                        f"payload={json_value_or_dash(g, 'DeclaredPayloadBytes')} "
                        f"count={json_value_or_dash(g, 'Count')} "
                        f"first16={json_value_or_dash(g, 'PayloadFirst16')}"
                    ),
                )
            )


# Main dispatcher


def show_report_summary(mode_name: str, report_path: str) -> None:
    """Display a human-readable summary of a JSON report.

    Mirrors: PS Show-ReportSummary -ModeName $modeName -Path $path
    """
    try:
        report = load_json_report(report_path)
    except (FileNotFoundError, ValueError):
        print(f"No report found: {report_path}", file=sys.stderr)
        return

    print(f"\n--- {mode_name} summary: {report_path}")

    if mode_name in ("AssetSignatures", "AssetSemanticIndex"):
        _show_asset_signatures(report)
    elif mode_name == "MeshBindings":
        _show_mesh_bindings(report)
    elif mode_name == "MeshProbe":
        _show_mesh_probe(report)
    elif mode_name == "AttributeExtraProbe":
        _show_attribute_extra_probe(report)
    elif mode_name in (
        "MeshStreams",
        "IndexCandidates",
        "StreamEndianness",
        "StreamBodies",
    ):
        _show_simple_inventory(report, mode_name)
    else:
        print(f"  (no summary handler for mode: {mode_name})")


# ============================================================================
# Semantic Hint Cross-tab
# ============================================================================


def _new_semantic_hint_entry_row(entry: dict[str, Any], job: str) -> dict[str, Any]:
    """Build a cross-tab row for one semantic hint entry.

    Mirrors: PS New-SemanticHintEntryRow
    """
    model = semantic_hint_primary_model(entry)
    name_candidates = entry.get("NameCandidates") or []
    texture_count = len(
        [n for n in name_candidates if isinstance(n, str) and n.endswith(".dds")]
    )
    categories = entry.get("SemanticCategories") or []
    return {
        "Job": job,
        "AssetIdPrefix": str(entry.get("AssetIdPrefix", "")),
        "ArchiveName": str(entry.get("ArchiveName", "")),
        "EntryIndex": int(entry.get("EntryIndex", 0)),
        "Size": int(entry.get("UnpackedSize", 0)),
        "Bucket": semantic_hint_bucket(model),
        "PrimaryModel": model,
        "TextureCount": texture_count,
        "Categories": ",".join(str(c) for c in categories),
    }


def semantic_hint_cross_tab(out_dir: str) -> None:
    """Generate semantic hint cross-tabulation from matrix output.

    Reads actor-object, map-zone, and waypoint-poi semantic hint JSON files
    from discovery-matrix/nif-semantic-hints/ and produces:
      - nif-semantic-hint-crosstab.json
      - nif-semantic-hint-crosstab.md

    Mirrors: PS Invoke-SemanticHintCrossTab
    """
    matrix_dir = Path(out_dir) / "discovery-matrix" / "nif-semantic-hints"
    actor_path = matrix_dir / "semantic-nif-actor-object.json"
    map_path = matrix_dir / "semantic-nif-map-zone.json"
    poi_path = matrix_dir / "semantic-nif-waypoint-poi.json"

    for required_path in (actor_path, map_path, poi_path):
        if not required_path.exists():
            raise FileNotFoundError(
                f"SemanticHintCrossTab failed: required matrix output is missing: {required_path}"
            )

    actor_data = load_json_report(str(actor_path))
    map_data = load_json_report(str(map_path))
    poi_data = load_json_report(str(poi_path))

    actor_entries = actor_data.get("Entries") or []
    map_entries = map_data.get("Entries") or []
    poi_entries = poi_data.get("Entries") or []

    # Build rows
    rows: list[dict[str, Any]] = []
    for entry in actor_entries:
        rows.append(_new_semantic_hint_entry_row(entry, "hint:actor-object"))
    for entry in map_entries:
        rows.append(_new_semantic_hint_entry_row(entry, "hint:map-zone"))

    # Overlap
    actor_ids = {str(e.get("AssetIdPrefix", "")) for e in actor_entries}
    map_ids = {str(e.get("AssetIdPrefix", "")) for e in map_entries}
    overlap_ids = sorted(actor_ids & map_ids)

    # Bucket rows
    bucket_groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        bucket = row["Bucket"]
        bucket_groups.setdefault(bucket, []).append(row)

    bucket_rows = sorted(
        [
            {
                "Bucket": bucket,
                "Count": len(group),
                "Jobs": ",".join(sorted({r["Job"] for r in group})),
                "SampleIds": ",".join(
                    [r["AssetIdPrefix"] for r in group[:5]]
                ),
            }
            for bucket, group in bucket_groups.items()
        ],
        key=lambda b: (-safe_int(b["Count"]), b["Bucket"]),
    )

    # Overlap rows
    overlap_rows = sorted(
        [r for r in rows if r["AssetIdPrefix"] in overlap_ids],
        key=lambda r: (r["AssetIdPrefix"], r["Job"]),
    )

    # JSON output
    summary: dict[str, Any] = {
        "Schema": "nif-semantic-hint-crosstab/v1",
        "CandidateOnly": True,
        "SourceDirectory": str(matrix_dir),
        "ActorObjectEntries": len(actor_entries),
        "MapZoneEntries": len(map_entries),
        "WaypointPoiEntries": len(poi_entries),
        "ActorMapOverlapEntries": len(overlap_ids),
        "Buckets": bucket_rows,
        "OverlapRows": overlap_rows,
        "Interpretation": (
            "Static NIF semantic hints only. Use as ranking/search context; "
            "do not promote runtime truth or geometry/export readiness."
        ),
    }

    json_path = matrix_dir / "nif-semantic-hint-crosstab.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # Markdown output
    md_lines: list[str] = [
        "# NIF Semantic Hint Cross-tab",
        "",
        "Hint-only cross-tab from bounded `nif-semantic-hints` matrix output. "
        "This is static asset search/ranking context only.",
        "",
        (
            f"Summary: actor/object entries={len(actor_entries)}; "
            f"map-zone entries={len(map_entries)}; "
            f"waypoint/POI entries={len(poi_entries)}; "
            f"actor/map overlap={len(overlap_ids)}."
        ),
        "",
        "## Buckets",
        "",
        "| Bucket | Count | Jobs | Sample IDs |",
        "|---|---:|---|---|",
    ]
    for bucket in bucket_rows:
        md_lines.append(
            f"| {format_markdown_cell(bucket['Bucket'])} "
            f"| {format_markdown_cell(bucket['Count'])} "
            f"| {format_markdown_cell(bucket['Jobs'])} "
            f"| {format_markdown_cell(bucket['SampleIds'])} |"
        )

    md_lines += [
        "",
        "## Actor/map overlap",
        "",
        "| ID | Job | Archive | Entry | Size | Bucket | Primary model | Textures |",
        "|---|---|---|---:|---:|---|---|---:|",
    ]
    for row in overlap_rows:
        md_lines.append(
            f"| {format_markdown_cell(row['AssetIdPrefix'])} "
            f"| {format_markdown_cell(row['Job'])} "
            f"| {format_markdown_cell(row['ArchiveName'])} "
            f"| {format_markdown_cell(row['EntryIndex'])} "
            f"| {format_markdown_cell(row['Size'])} "
            f"| {format_markdown_cell(row['Bucket'])} "
            f"| {format_markdown_cell(row['PrimaryModel'])} "
            f"| {format_markdown_cell(row['TextureCount'])} |"
        )

    md_lines += [
        "",
        "Interpretation: semantic hints can prioritize offline inspection, "
        "but they do not prove runtime identity, geometry roles, or export readiness.",
    ]

    md_path = matrix_dir / "nif-semantic-hint-crosstab.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print("\n--- SemanticHintCrossTab")
    print(
        f"actor/object entries={len(actor_entries)}; "
        f"map-zone entries={len(map_entries)}; "
        f"waypoint/POI entries={len(poi_entries)}; "
        f"actor/map overlap={len(overlap_ids)}"
    )
    print(f"SemanticHintCrossTab JSON: {json_path}")
    print(f"SemanticHintCrossTab markdown: {md_path}")
    print("SemanticHintCrossTab passed: semantic hints remain candidate-only ranking context.")


# ============================================================================
# Discovery Workbench
# ============================================================================


# ============================================================================
# GhidraPairingReviewReport
# ============================================================================


def ghidra_pairing_review_report(
    report_path: str | Path,
    out_dir: str | Path | None = None,
    take: int = 25,
) -> None:
    """Write a compact candidate-only report for Ghidra pairing review findings."""
    report = load_json_report(report_path)

    groups_raw = report.get("TopGhidraPairingReviewFindings")
    if not groups_raw or not isinstance(groups_raw, list):
        raise ValueError(
            "GhidraPairingReviewReport failed: TopGhidraPairingReviewFindings "
            "is missing or empty in mesh-binding inventory."
        )

    output_dir = Path(out_dir) if out_dir is not None else Path(report_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    def _first_sample(group: dict[str, Any]) -> dict[str, Any]:
        samples = group.get("Samples")
        if isinstance(samples, list) and samples and isinstance(samples[0], dict):
            return samples[0]
        return {}

    def _pairing(sample: dict[str, Any], key: str) -> dict[str, Any]:
        pairing = sample.get(key)
        return pairing if isinstance(pairing, dict) else {}

    def _role_pair(pairing: dict[str, Any]) -> str:
        index_role = json_value_or_dash(pairing, "IndexRole")
        vertex_role = json_value_or_dash(pairing, "VertexRole")
        return f"{index_role}->{vertex_role}"

    findings: list[dict[str, Any]] = []
    for ordinal, group_obj in enumerate(groups_raw[:take], start=1):
        if not isinstance(group_obj, dict):
            continue
        sample = _first_sample(group_obj)
        legacy_pairing = _pairing(sample, "LegacyPairing")
        ghidra_pairing = _pairing(sample, "GhidraPairing")
        chosen_pairing = ghidra_pairing or legacy_pairing
        finding = {
            "Rank": ordinal,
            "CandidateOnly": True,
            "ReviewKind": json_value_or_dash(group_obj, "ReviewKind"),
            "Priority": json_value_or_dash(group_obj, "Priority"),
            "MeshSize": json_value_or_dash(group_obj, "MeshSize"),
            "Count": json_value_or_dash(group_obj, "Count"),
            "LegacyRoles": _role_pair(legacy_pairing) if legacy_pairing else "-",
            "GhidraRoles": _role_pair(ghidra_pairing) if ghidra_pairing else "-",
            "LegacyVertexSemanticClass": json_value_or_dash(
                group_obj, "LegacyVertexSemanticClass"
            ),
            "GhidraVertexSemanticClass": json_value_or_dash(
                group_obj, "GhidraVertexSemanticClass"
            ),
            "AverageLegacyConfidence": json_value_or_dash(
                group_obj, "AverageLegacyConfidence"
            ),
            "AverageGhidraConfidence": json_value_or_dash(
                group_obj, "AverageGhidraConfidence"
            ),
            "AverageConfidenceDelta": json_value_or_dash(
                group_obj, "AverageConfidenceDelta"
            ),
            "SampleIdPrefix": json_value_or_dash(sample, "IdPrefix"),
            "SampleMeshBlockIndex": json_value_or_dash(sample, "MeshBlockIndex"),
            "SampleIndexOffset": json_value_or_dash(
                chosen_pairing, "IndexMeshPayloadOffset"
            ),
            "SampleIndexBlock": json_value_or_dash(chosen_pairing, "IndexBlockIndex"),
            "SampleVertexOffset": json_value_or_dash(
                chosen_pairing, "VertexMeshPayloadOffset"
            ),
            "SampleVertexBlock": json_value_or_dash(chosen_pairing, "VertexBlockIndex"),
            "LegacyIndexBodyFirst16": json_value_or_dash(
                legacy_pairing, "IndexBodyFirst16"
            ),
            "LegacyVertexBodyFirst16": json_value_or_dash(
                legacy_pairing, "VertexBodyFirst16"
            ),
            "GhidraIndexBodyFirst16": json_value_or_dash(
                ghidra_pairing, "IndexBodyFirst16"
            ),
            "GhidraVertexBodyFirst16": json_value_or_dash(
                ghidra_pairing, "VertexBodyFirst16"
            ),
        }
        finding["ProbeCommand"] = (
            "python scripts/rift_workflow.py mesh-probe "
            f"--id {finding['SampleIdPrefix']} "
            f"--mesh-block {finding['SampleMeshBlockIndex']} "
            "--skip-build"
        )
        findings.append(finding)

    if not findings:
        raise ValueError(
            "GhidraPairingReviewReport failed: no valid review findings were found."
        )

    kind_counts: dict[str, int] = {}
    for finding in findings:
        kind = str(finding["ReviewKind"])
        kind_counts[kind] = kind_counts.get(kind, 0) + 1

    output = {
        "SchemaVersion": "ghidra-pairing-review/v1",
        "CandidateOnly": True,
        "SourceReport": str(report_path),
        "TotalReviewFindingsInSource": len(groups_raw),
        "EmittedFindings": len(findings),
        "KindCounts": kind_counts,
        "PairingCounts": {
            "Shared": report.get("GhidraSharedPairings"),
            "LegacyOnly": report.get("LegacyOnlyPairings"),
            "GhidraOnly": report.get("GhidraOnlyPairings"),
        },
        "Findings": findings,
    }

    json_path = output_dir / "ghidra-pairing-review-report.json"
    md_path = output_dir / "ghidra-pairing-review-report.md"
    json_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    md_lines = [
        "# Ghidra pairing review report",
        "",
        "Candidate-only: yes. This report ranks review targets and does not promote "
        "parser/export behavior.",
        "",
        f"- Source report: `{format_markdown_cell(report_path)}`",
        f"- Emitted findings: {len(findings)}",
        f"- Kind counts: {', '.join(f'{k}={v}' for k, v in sorted(kind_counts.items()))}",
        f"- Pairing overlap: shared={json_value_or_dash(output['PairingCounts'], 'Shared')} "
        f"legacyOnly={json_value_or_dash(output['PairingCounts'], 'LegacyOnly')} "
        f"ghidraOnly={json_value_or_dash(output['PairingCounts'], 'GhidraOnly')}",
        "",
        "| Rank | Kind | Mesh size | Count | Legacy roles | Ghidra roles | Classes | Sample | First bytes |",
        "|---:|---|---:|---:|---|---|---|---|---|",
    ]
    for finding in findings:
        classes = (
            f"{finding['LegacyVertexSemanticClass']}->{finding['GhidraVertexSemanticClass']}"
        )
        sample = (
            f"{finding['SampleIdPrefix']} mesh#{finding['SampleMeshBlockIndex']} "
            f"index@{finding['SampleIndexOffset']}/#{finding['SampleIndexBlock']} "
            f"vertex@{finding['SampleVertexOffset']}/#{finding['SampleVertexBlock']}"
        )
        first_bytes = (
            f"L[{finding['LegacyIndexBodyFirst16']}|{finding['LegacyVertexBodyFirst16']}] "
            f"G[{finding['GhidraIndexBodyFirst16']}|{finding['GhidraVertexBodyFirst16']}]"
        )
        md_lines.append(
            f"| {finding['Rank']} "
            f"| {format_markdown_cell(finding['ReviewKind'])} "
            f"| {format_markdown_cell(finding['MeshSize'])} "
            f"| {format_markdown_cell(finding['Count'])} "
            f"| {format_markdown_cell(finding['LegacyRoles'])} "
            f"| {format_markdown_cell(finding['GhidraRoles'])} "
            f"| {format_markdown_cell(classes)} "
            f"| {format_markdown_cell(sample)} "
            f"| {format_markdown_cell(first_bytes)} |"
        )
    md_lines += [
        "",
        "Next use: run the probe command from the JSON row for a selected sample, "
        "then compare its legacy and Ghidra body bytes before changing any decoder behavior.",
    ]
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"GhidraPairingReviewReport JSON: {json_path}")
    print(f"GhidraPairingReviewReport markdown: {md_path}")
    print(
        "GhidraPairingReviewReport passed: review findings remain candidate-only "
        "and export behavior was not changed."
    )


# ============================================================================
# GhidraAttributeCandidateReport
# ============================================================================


def ghidra_attribute_candidate_report(
    review_report_path: str | Path,
    out_dir: str | Path | None = None,
) -> None:
    """Group Ghidra-only review ranks into candidate attribute families."""
    review_path = Path(review_report_path)
    report = load_json_report(review_path)
    findings_raw = report.get("Findings")
    if not isinstance(findings_raw, list) or not findings_raw:
        raise ValueError("GhidraAttributeCandidateReport failed: Findings is missing or empty.")

    output_dir = Path(out_dir) if out_dir is not None else review_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    rank_probe_root = output_dir / "ghidra-review-rank-probes"

    def _desired_vertex_role(finding: dict[str, Any]) -> str:
        roles = str(finding.get("GhidraRoles", ""))
        return roles.split("->", 1)[1] if "->" in roles else roles

    def _semantic(finding: dict[str, Any]) -> str:
        semantic = str(finding.get("GhidraVertexSemanticClass", "-"))
        if semantic not in ("-", "missing"):
            return semantic
        role = _desired_vertex_role(finding)
        if role.startswith("position-"):
            return "position"
        if role.startswith("normal-"):
            return "normal"
        if role.startswith("uv-"):
            return "uv"
        if "repeated-pattern" in role:
            return "noise"
        return "other"

    def _load_probe_pairing(finding: dict[str, Any]) -> dict[str, Any]:
        rank = safe_int(finding.get("Rank"))
        asset_id = str(finding.get("SampleIdPrefix", ""))
        probe_path = rank_probe_root / f"rank{rank:02d}" / f"probe-nif-mesh-{asset_id}.json"
        if not probe_path.exists():
            return {}
        probe = load_json_report(probe_path)
        meshes = probe.get("Meshes")
        if not isinstance(meshes, list) or not meshes:
            return {}
        pairings = meshes[0].get("GhidraPairings")
        if not isinstance(pairings, list):
            return {}
        desired_role = _desired_vertex_role(finding)
        desired_vertex_offset = safe_int(finding.get("SampleVertexOffset"))
        desired_index_offset = safe_int(finding.get("SampleIndexOffset"))
        for pairing in pairings:
            if (
                isinstance(pairing, dict)
                and str(pairing.get("VertexRole", "")) == desired_role
                and safe_int(pairing.get("VertexMeshPayloadOffset")) == desired_vertex_offset
                and safe_int(pairing.get("IndexMeshPayloadOffset")) == desired_index_offset
            ):
                return pairing
        for pairing in pairings:
            if isinstance(pairing, dict) and str(pairing.get("VertexRole", "")) == desired_role:
                return pairing
        return {}

    def _review_summary(semantic: str, pairing: dict[str, Any]) -> dict[str, Any]:
        if semantic == "position":
            review = pairing.get("VertexPositionBoundsReview")
            metric_name = "MaxExtent"
        elif semantic == "normal":
            review = pairing.get("VertexNormalVectorReview")
            metric_name = "NearUnitVectorRatio"
        elif semantic == "uv":
            review = pairing.get("VertexUvRangeReview")
            metric_name = "UvRangeRatio"
        else:
            review = None
            metric_name = "-"
        if not isinstance(review, dict):
            return {
                "ProbeBacked": bool(pairing),
                "ReviewPresent": False,
                "PassesBasicReview": "-",
                "MetricName": metric_name,
                "MetricValue": "-",
                "MissReasons": [],
            }
        miss_reasons = review.get("MissReasons")
        return {
            "ProbeBacked": True,
            "ReviewPresent": True,
            "PassesBasicReview": json_value_or_dash(review, "PassesBasicReview"),
            "MetricName": metric_name,
            "MetricValue": json_value_or_dash(review, metric_name),
            "MissReasons": miss_reasons if isinstance(miss_reasons, list) else [],
        }

    evidence_rows: list[dict[str, Any]] = []
    groups: dict[str, dict[str, Any]] = {}
    for raw in findings_raw:
        if not isinstance(raw, dict) or str(raw.get("ReviewKind", "")) != "ghidra-only":
            continue
        asset_id = str(raw.get("SampleIdPrefix", ""))
        mesh_block = safe_int(raw.get("SampleMeshBlockIndex"))
        semantic = _semantic(raw)
        pairing = _load_probe_pairing(raw)
        review = _review_summary(semantic, pairing)
        row = {
            "Rank": safe_int(raw.get("Rank")),
            "Count": safe_int(raw.get("Count")),
            "SampleIdPrefix": asset_id,
            "SampleMeshBlockIndex": mesh_block,
            "GhidraRoles": raw.get("GhidraRoles", "-"),
            "GhidraVertexSemanticClass": semantic,
            **review,
        }
        evidence_rows.append(row)
        key = f"{asset_id}|mesh#{mesh_block}"
        group = groups.setdefault(
            key,
            {
                "SampleIdPrefix": asset_id,
                "SampleMeshBlockIndex": mesh_block,
                "Ranks": [],
                "TotalCount": 0,
                "Semantics": [],
                "Evidence": [],
            },
        )
        group["Ranks"].append(row["Rank"])
        group["TotalCount"] += row["Count"]
        if semantic not in group["Semantics"]:
            group["Semantics"].append(semantic)
        group["Evidence"].append(row)

    if not evidence_rows:
        raise ValueError("GhidraAttributeCandidateReport failed: no ghidra-only findings were found.")

    for group in groups.values():
        semantics = set(group["Semantics"])
        group["HasPosition"] = "position" in semantics
        group["HasNormal"] = "normal" in semantics
        group["HasUv"] = "uv" in semantics
        group["HasRejectedNoise"] = bool(semantics & {"noise", "other"})
        group["CompletePositionNormalUvCandidate"] = (
            group["HasPosition"] and group["HasNormal"] and group["HasUv"]
        )
        if group["HasPosition"] and group["HasNormal"]:
            decision = "position-normal partial; needs UV/group proof"
        elif group["HasPosition"] and group["HasUv"]:
            decision = "position-UV partial; needs normal/group proof"
        elif group["HasPosition"]:
            decision = "position-only candidate; needs companions"
        elif group["HasNormal"]:
            decision = "normal-only candidate; needs companions"
        elif group["HasUv"]:
            decision = "UV-only candidate; needs companions"
        else:
            decision = "noise/other only; keep rejected"
        group["InitialDecision"] = decision
        group["Ranks"] = sorted(group["Ranks"])
        group["Semantics"] = sorted(group["Semantics"])

    summary = {
        "GhidraOnlyGroups": len(evidence_rows),
        "GhidraOnlyPairingsCovered": sum(row["Count"] for row in evidence_rows),
        "GroupedSampleMeshes": len(groups),
        "CompletePositionNormalUvCandidateGroups": sum(
            1 for group in groups.values() if group["CompletePositionNormalUvCandidate"]
        ),
        "ProbeBackedRanks": sum(1 for row in evidence_rows if row["ProbeBacked"]),
        "PositionReviewPassGroups": sum(
            1 for row in evidence_rows if row["GhidraVertexSemanticClass"] == "position" and row["PassesBasicReview"] is True
        ),
        "NormalReviewPassGroups": sum(
            1 for row in evidence_rows if row["GhidraVertexSemanticClass"] == "normal" and row["PassesBasicReview"] is True
        ),
        "UvReviewPassGroups": sum(
            1 for row in evidence_rows if row["GhidraVertexSemanticClass"] == "uv" and row["PassesBasicReview"] is True
        ),
        "UvReviewFailGroups": sum(
            1 for row in evidence_rows if row["GhidraVertexSemanticClass"] == "uv" and row["PassesBasicReview"] is False
        ),
        "RejectedNoiseGroups": sum(
            1 for row in evidence_rows if row["GhidraVertexSemanticClass"] in ("noise", "other")
        ),
    }

    groups_output: list[dict[str, Any]] = sorted(
        groups.values(),
        key=lambda group: (
            not group["HasPosition"],
            not group["HasNormal"],
            not group["HasUv"],
            str(group["SampleIdPrefix"]),
            safe_int(group["SampleMeshBlockIndex"]),
        ),
    )

    output = {
        "SchemaVersion": "ghidra-attribute-candidate-report/v1",
        "CandidateOnly": True,
        "SourceReviewReport": str(review_path),
        "RankProbeRoot": str(rank_probe_root),
        "Summary": summary,
        "Groups": groups_output,
        "EvidenceRows": sorted(evidence_rows, key=lambda row: row["Rank"]),
    }

    json_path = output_dir / "ghidra-attribute-candidate-report.json"
    md_path = output_dir / "ghidra-attribute-candidate-report.md"
    json_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    md_lines = [
        "# Ghidra attribute candidate report",
        "",
        "Candidate-only: yes. This grouped triage report does not promote parser/export behavior.",
        "",
        f"- Ghidra-only groups: {summary['GhidraOnlyGroups']}",
        f"- Ghidra-only pairings covered: {summary['GhidraOnlyPairingsCovered']}",
        f"- Grouped sample meshes: {summary['GroupedSampleMeshes']}",
        f"- Complete position/normal/UV candidate groups: {summary['CompletePositionNormalUvCandidateGroups']}",
        f"- Probe-backed ranks: {summary['ProbeBackedRanks']}",
        f"- Position/normal/UV pass groups: {summary['PositionReviewPassGroups']}/{summary['NormalReviewPassGroups']}/{summary['UvReviewPassGroups']}",
        f"- UV review fail groups: {summary['UvReviewFailGroups']}",
        "",
        "| Sample | Ranks | Count | Semantics | Decision |",
        "|---|---:|---:|---|---|",
    ]
    for group in groups_output:
        sample = f"{group['SampleIdPrefix']} mesh#{group['SampleMeshBlockIndex']}"
        ranks = ",".join(str(rank) for rank in group["Ranks"])
        semantics = ",".join(group["Semantics"])
        md_lines.append(
            f"| {format_markdown_cell(sample)} "
            f"| {format_markdown_cell(ranks)} "
            f"| {group['TotalCount']} "
            f"| {format_markdown_cell(semantics)} "
            f"| {format_markdown_cell(group['InitialDecision'])} |"
        )
    md_lines += [
        "",
        "Promotion note: keep `ghidra-pairing-non-export-guard` passing; this report is not an exporter input.",
    ]
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"GhidraAttributeCandidateReport JSON: {json_path}")
    print(f"GhidraAttributeCandidateReport markdown: {md_path}")
    print("GhidraAttributeCandidateReport passed: grouped candidate evidence remains report-only.")


# ============================================================================
# PositionSourceSiblingFamilyReport  (inventory-level)
# ============================================================================


def position_source_sibling_family_report(report_path: str | Path) -> None:
    """Cross-tabulate TopPositionSourceSiblings into ranked families.

    Groups sibling source rows by (MeshSize, MeshBlocks, MeshPayloadOffsets),
    derives aggregate metrics (evidence groups, total links, distinct IDs,
    target blocks, payloads, roles), assigns a candidate-only decision, and
    guards five known repeated sibling source families with exact assertions.

    Generates position-source-sibling-family-report.json and .md reports.

    Mirrors: Invoke-PositionSourceSiblingFamilyReport
    """
    report = load_json_report(report_path)

    groups_raw = report.get("TopPositionSourceSiblings")
    if not groups_raw or not isinstance(groups_raw, list) or len(groups_raw) == 0:
        raise ValueError(
            "PositionSourceSiblingFamilyReport failed: TopPositionSourceSiblings "
            "is missing or empty in mesh-binding inventory."
        )
    groups: list[dict[str, Any]] = groups_raw

    # --- Decision function (hardcoded known families) ---

    def _get_family_decision(
        mesh_size: int, mesh_blocks: str, mesh_offsets: str
    ) -> str:
        """Assign a candidate-only decision for a known family.

        Mirrors: Get-PositionSourceSiblingFamilyDecision
        """
        if (
            mesh_size == 305
            and mesh_blocks == "mesh#7, mesh#27"
            and mesh_offsets == "stream@188"
        ):
            return "repeated meshSize=305 source-binding family; candidate-only probe queue"
        if (
            mesh_size == 321
            and mesh_blocks == "mesh#7, mesh#31"
            and mesh_offsets == "stream@204"
        ):
            return "repeated meshSize=321 source-binding family; candidate-only probe queue"
        if (
            mesh_size == 329
            and mesh_blocks == "mesh#7, mesh#34"
            and mesh_offsets == "stream@212"
        ):
            return "repeated meshSize=329 source-binding family; candidate-only probe queue"
        if mesh_size == 325 and mesh_blocks == "mesh#6, mesh#30":
            return "known shifted sibling position-source clue; candidate-only"
        if mesh_size == 329 and mesh_blocks == "mesh#6, mesh#31":
            return "known shifted sibling position-source clue; candidate-only"
        return "candidate-only follow-up"

    # --- Build source rows ---

    source_rows: list[dict[str, object]] = []
    for group in groups:
        if not isinstance(group, dict):
            continue

        mesh_size_entries = group.get("MeshSizes")
        if not mesh_size_entries or not isinstance(mesh_size_entries, list) or len(mesh_size_entries) == 0:
            continue

        # Find dominant mesh size (largest count, smallest size on tie)
        dominant = sorted(
            mesh_size_entries,
            key=lambda e: (
                -safe_int(e.get("Count", 0) if isinstance(e, dict) else 0),
                safe_int(e.get("Size", 0) if isinstance(e, dict) else 0),
            ),
        )
        if not dominant:
            continue
        dominant_size = safe_int(dominant[0].get("Size", 0))

        mesh_blocks_raw = group.get("MeshBlockIndices") or []
        mesh_blocks = sorted(safe_int(mb) for mb in mesh_blocks_raw)
        mesh_offsets_raw = group.get("MeshPayloadOffsets") or []
        mesh_offsets = sorted(safe_int(mo) for mo in mesh_offsets_raw)

        if len(mesh_blocks) < 2 or len(mesh_offsets) == 0:
            continue

        source_rows.append({
            "MeshSize": dominant_size,
            "MeshBlocks": ", ".join(f"mesh#{mb}" for mb in mesh_blocks),
            "MeshPayloadOffsets": ", ".join(f"stream@{mo}" for mo in mesh_offsets),
            "TargetBlock": safe_int(json_value_or_dash(group, "TargetBlockIndex")),
            "Payload": safe_int(json_value_or_dash(group, "DeclaredPayloadBytes")),
            "IdPrefix": str(json_value_or_dash(group, "IdPrefix")),
            "Count": safe_int(json_value_or_dash(group, "Count")),
            "UsageAccess": (
                f"{json_value_or_dash(group, 'DataStreamUsage')}/"
                f"{json_value_or_dash(group, 'DataStreamAccess')}"
            ),
            "Role": str(json_value_or_dash(group, "Role")),
        })

    if not source_rows:
        raise ValueError(
            "PositionSourceSiblingFamilyReport failed: no sibling family source "
            "rows could be derived from TopPositionSourceSiblings."
        )

    # --- Build family rows (group by MeshSize, MeshBlocks, MeshPayloadOffsets) ---

    # Group key functions
    def _row_key(r: dict[str, object]) -> tuple[int, str, str]:
        return (
            int(r["MeshSize"]),
            str(r["MeshBlocks"]),
            str(r["MeshPayloadOffsets"]),
        )

    # Group rows by key
    family_groups_raw: dict[tuple[int, str, str], list[dict[str, object]]] = {}
    for row in source_rows:
        key = _row_key(row)
        family_groups_raw.setdefault(key, []).append(row)

    family_rows: list[dict[str, object]] = []
    for _, fam_rows in family_groups_raw.items():
        first = fam_rows[0]

        # Aggregate unique values
        target_blocks = sorted(set(int(r["TargetBlock"]) for r in fam_rows))
        payloads = sorted(set(int(r["Payload"]) for r in fam_rows))
        ids = sorted(set(str(r["IdPrefix"]) for r in fam_rows))
        usage_access_set = sorted(set(str(r["UsageAccess"]) for r in fam_rows))
        roles_set = sorted(set(str(r["Role"]) for r in fam_rows))
        total_links = sum(int(r["Count"]) for r in fam_rows)

        family_rows.append({
            "MeshSize": int(first["MeshSize"]),
            "MeshBlocks": str(first["MeshBlocks"]),
            "MeshPayloadOffsets": str(first["MeshPayloadOffsets"]),
            "EvidenceGroups": len(fam_rows),
            "TotalStreamLinks": total_links,
            "DistinctIds": len(ids),
            "TargetBlocks": ", ".join(f"block#{tb}" for tb in target_blocks),
            "PayloadBytes": ", ".join(str(p) for p in payloads),
            "RepresentativeIds": ", ".join(ids[:8]),
            "UsageAccess": ", ".join(usage_access_set),
            "Roles": ", ".join(roles_set),
            "Decision": _get_family_decision(
                int(first["MeshSize"]),
                str(first["MeshBlocks"]),
                str(first["MeshPayloadOffsets"]),
            ),
        })

    # Sort family rows: EvidenceGroups desc, MeshSize asc, MeshBlocks, MeshPayloadOffsets
    family_rows.sort(
        key=lambda r: (
            -int(r["EvidenceGroups"]),
            int(r["MeshSize"]),
            str(r["MeshBlocks"]),
            str(r["MeshPayloadOffsets"]),
        )
    )

    # --- Guard five known families ---

    def _assert_family(
        mesh_size: int,
        mesh_blocks: str,
        mesh_offsets: str,
        min_evidence_groups: int,
        expected_target_blocks: str,
        expected_id_prefix: str = "",
    ) -> dict[str, object]:
        """Assert a known sibling source family is present with expected shape.

        Mirrors: Assert-PositionSourceSiblingFamily
        """
        ctx = f"meshSize={mesh_size} {mesh_blocks} {mesh_offsets}"
        matches = [
            r for r in family_rows
            if int(r["MeshSize"]) == mesh_size
            and str(r["MeshBlocks"]) == mesh_blocks
            and str(r["MeshPayloadOffsets"]) == mesh_offsets
        ]
        if len(matches) != 1:
            raise ValueError(
                f"PositionSourceSiblingFamilyReport failed: expected one family "
                f"{ctx}, found {len(matches)}."
            )
        row = matches[0]

        evidence = int(row["EvidenceGroups"])
        if evidence < min_evidence_groups:
            raise ValueError(
                f"PositionSourceSiblingFamilyReport failed: {ctx} evidence groups "
                f"dropped below {min_evidence_groups} (actual {evidence})."
            )

        target_blocks = str(row["TargetBlocks"])
        if target_blocks != expected_target_blocks:
            raise ValueError(
                f"PositionSourceSiblingFamilyReport failed: {ctx} target blocks "
                f"changed from {expected_target_blocks} to {target_blocks}."
            )

        if expected_id_prefix:
            rep_ids = str(row["RepresentativeIds"])
            if expected_id_prefix not in rep_ids:
                raise ValueError(
                    f"PositionSourceSiblingFamilyReport failed: {ctx} no longer "
                    f"includes expected sample {expected_id_prefix}."
                )

        return row

    _guarded_families: list[dict[str, object]] = [
        _assert_family(329, "mesh#7, mesh#34", "stream@212", 20, "block#28"),
        _assert_family(305, "mesh#7, mesh#27", "stream@188", 10, "block#21"),
        _assert_family(321, "mesh#7, mesh#31", "stream@204", 8, "block#25"),
        _assert_family(
            325, "mesh#6, mesh#30", "stream@292, stream@296", 1, "block#24",
            "e3de1077a37d0337",
        ),
        _assert_family(
            329, "mesh#6, mesh#31", "stream@296", 1, "block#25",
            "8e01613d7ce9e297",
        ),
    ]

    # --- Write JSON + markdown reports ---
    report_dir = Path(report_path).parent
    json_path = report_dir / "position-source-sibling-family-report.json"
    md_path = report_dir / "position-source-sibling-family-report.md"

    summary: dict[str, Any] = {
        "Schema": "position-source-sibling-family-report/v1",
        "CandidateOnly": True,
        "SourceReport": str(report_path),
        "Families": family_rows,
        "GuardedFamilies": [
            {
                "MeshSize": 329,
                "MeshBlocks": "mesh#7, mesh#34",
                "MeshPayloadOffsets": "stream@212",
                "MinimumEvidenceGroups": 20,
                "ExpectedTargetBlocks": "block#28",
            },
            {
                "MeshSize": 305,
                "MeshBlocks": "mesh#7, mesh#27",
                "MeshPayloadOffsets": "stream@188",
                "MinimumEvidenceGroups": 10,
                "ExpectedTargetBlocks": "block#21",
            },
            {
                "MeshSize": 321,
                "MeshBlocks": "mesh#7, mesh#31",
                "MeshPayloadOffsets": "stream@204",
                "MinimumEvidenceGroups": 8,
                "ExpectedTargetBlocks": "block#25",
            },
            {
                "MeshSize": 325,
                "MeshBlocks": "mesh#6, mesh#30",
                "MeshPayloadOffsets": "stream@292, stream@296",
                "MinimumEvidenceGroups": 1,
                "ExpectedTargetBlocks": "block#24",
                "ExpectedIdPrefix": "e3de1077a37d0337",
            },
            {
                "MeshSize": 329,
                "MeshBlocks": "mesh#6, mesh#31",
                "MeshPayloadOffsets": "stream@296",
                "MinimumEvidenceGroups": 1,
                "ExpectedTargetBlocks": "block#25",
                "ExpectedIdPrefix": "8e01613d7ce9e297",
            },
        ],
        "Interpretation": (
            "Candidate-only cross-tab over parser-derived TopPositionSourceSiblings. "
            "Repeated sibling source families help choose probes but do not promote "
            "geometry truth or export readiness."
        ),
    }
    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md_lines: list[str] = [
        "# Position Source Sibling Family Report",
        "",
        "Candidate-only family cross-tab over parser-derived `TopPositionSourceSiblings` from the mesh-binding inventory.",
        "",
        "Generated under ignored `Exports/`; do not stage generated discovery output.",
        "",
        "| Mesh size | Mesh blocks | Stream offsets | Groups | Links | IDs | Target blocks | Payload bytes | Representative IDs | Decision |",
        "|---:|---|---|---:|---:|---:|---|---|---|---|",
    ]
    for row in family_rows:
        md_lines.append(
            f"| {format_markdown_cell(row['MeshSize'])} "
            f"| {format_markdown_cell(row['MeshBlocks'])} "
            f"| {format_markdown_cell(row['MeshPayloadOffsets'])} "
            f"| {format_markdown_cell(row['EvidenceGroups'])} "
            f"| {format_markdown_cell(row['TotalStreamLinks'])} "
            f"| {format_markdown_cell(row['DistinctIds'])} "
            f"| {format_markdown_cell(row['TargetBlocks'])} "
            f"| {format_markdown_cell(row['PayloadBytes'])} "
            f"| {format_markdown_cell(row['RepresentativeIds'])} "
            f"| {format_markdown_cell(row['Decision'])} |"
        )
    md_lines += [
        "",
        "Interpretation: repeated sibling position sources are search/ranking evidence only. "
        "Normal/UV agreement, topology/index proof, sane bounds, repeated-family proof, "
        "and proof guards still gate any future truth promotion.",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    # --- Console output ---
    print("\n--- PositionSourceSiblingFamilyReport candidate-only family cross-tab")
    print(
        f"{'MeshSize':<10} {'MeshBlocks':<20} {'Offsets':<28} "
        f"{'Groups':>7} {'Links':>7} {'IDs':>5} {'TargetBlocks':<16} {'Decision'}"
    )
    print("-" * 130)
    for row in family_rows:
        print(
            f"{row['MeshSize']:<10} {str(row['MeshBlocks']):<20} "
            f"{str(row['MeshPayloadOffsets']):<28} "
            f"{row['EvidenceGroups']:>7} {row['TotalStreamLinks']:>7} "
            f"{row['DistinctIds']:>5} {str(row['TargetBlocks']):<16} "
            f"{row['Decision']}"
        )
    print(f"PositionSourceSiblingFamilyReport JSON: {json_path}")
    print(f"PositionSourceSiblingFamilyReport markdown: {md_path}")
    print(
        "PositionSourceSiblingFamilyReport passed: repeated sibling source families "
        "stayed candidate-only ranking evidence."
    )


# ============================================================================
# PositionSourceGapReport  (inventory-level)
# ============================================================================


def _get_position_lead_count_for_mesh_size(
    position_role: dict[str, Any], mesh_size: int
) -> int:
    """Count position leads for a given mesh size from the role group.

    Mirrors: Get-PositionLeadCountForMeshSize
    """
    mesh_sizes = position_role.get("MeshSizes")
    if not mesh_sizes or not isinstance(mesh_sizes, list):
        return 0
    for ms in mesh_sizes:
        if isinstance(ms, dict) and safe_int(ms.get("Size", 0)) == mesh_size:
            return safe_int(ms.get("Count", 0))
    return 0


def _get_position_gap_decision(
    mesh_size: int,
    position_lead_count: int,
    topology_pairing_count: float,
    residual_stream_count: int,
    residual_position_candidate_rows: int,
    attribute_set_count: int,
) -> str:
    """Assign a candidate-only decision for a mesh-size gap row.

    Mirrors: Get-PositionGapDecision
    """
    if mesh_size == 305 and residual_position_candidate_rows >= 5:
        return "residual-position-candidate-family"

    if (
        mesh_size == 325
        and topology_pairing_count >= 300
        and position_lead_count <= 5
        and residual_stream_count == 0
    ):
        return "topology-rich sparse-position singleton lead"

    if mesh_size == 297 and attribute_set_count >= 4:
        return "topology-proof anchor; residual singleton follow-up only"

    if (
        mesh_size == 329
        and attribute_set_count >= 20
        and residual_stream_count >= 40
    ):
        return "attribute-rich family; residual side-streams low-signal"

    if mesh_size in (321, 329) and topology_pairing_count >= 100:
        return "topology-rich family; residual side-streams low-signal"

    return "context-only"


def position_source_gap_report(report_path: str | Path) -> None:
    """Rank topology-rich mesh families where position-source evidence is sparse.

    Loads the mesh-binding inventory, extracts position role groups, top pairings,
    attribute sets, and residual targets/streams across five target mesh sizes
    (297, 305, 321, 325, 329), and assigns gap decisions.

    Guards meshSize=325 (topology-rich gap profile) and meshSize=305 (residual
    position candidates >= 5) with continuing assertions.

    Generates position-source-gap-report.json and .md reports.

    Mirrors: Invoke-PositionSourceGapReport
    """
    report = load_json_report(report_path)

    role_groups = report.get("RoleGroups")
    top_pairings_raw = report.get("TopPairings")
    attribute_sets_raw = report.get("TopAttributeSets")
    residual_targets_raw = report.get("ResidualTargetMeshSizes")
    residual_streams_raw = report.get("TopResidualStreams")

    if (
        not role_groups
        or not isinstance(role_groups, list)
        or len(role_groups) == 0
        or not top_pairings_raw
        or not isinstance(top_pairings_raw, list)
        or len(top_pairings_raw) == 0
        or not attribute_sets_raw
        or not isinstance(attribute_sets_raw, list)
        or len(attribute_sets_raw) == 0
        or not residual_targets_raw
        or not isinstance(residual_targets_raw, list)
        or len(residual_targets_raw) == 0
    ):
        raise ValueError(
            "PositionSourceGapReport failed: MeshBindings report is missing "
            "role, pairing, attribute-set, or residual target data."
        )

    top_pairings: list[dict[str, Any]] = top_pairings_raw
    attribute_sets: list[dict[str, Any]] = attribute_sets_raw
    residual_targets: list[dict[str, Any]] = residual_targets_raw
    residual_streams: list[dict[str, Any]] = residual_streams_raw or []

    # --- Find position-float3-ror1-lead role group ---

    position_role_matches = [
        g
        for g in role_groups
        if isinstance(g, dict)
        and str(json_value_or_dash(g, "Role")) == "position-float3-ror1-lead"
    ]
    if len(position_role_matches) != 1:
        raise ValueError(
            "PositionSourceGapReport failed: expected one "
            f"position-float3-ror1-lead role group, found {len(position_role_matches)}."
        )
    position_role = position_role_matches[0]

    # --- Build rows for each target mesh size ---

    target_mesh_sizes = [297, 305, 321, 325, 329]
    rows: list[dict[str, object]] = []

    for mesh_size in target_mesh_sizes:
        # Pairings filtered by mesh_size and index-* role
        pairings = [
            p for p in top_pairings
            if isinstance(p, dict)
            and safe_int(p.get("MeshSize", 0)) == mesh_size
            and str(json_value_or_dash(p, "IndexRole")).startswith("index-")
        ]
        attribute_rows = [
            a for a in attribute_sets
            if isinstance(a, dict)
            and safe_int(a.get("MeshSize", 0)) == mesh_size
        ]
        residual_target = [
            rt for rt in residual_targets
            if isinstance(rt, dict)
            and safe_int(rt.get("MeshSize", 0)) == mesh_size
        ]
        residual_target_first = residual_target[0] if residual_target else {}

        mesh_residual_rows = [
            rs for rs in residual_streams
            if isinstance(rs, dict)
            and safe_int(rs.get("MeshSize", 0)) == mesh_size
        ]
        residual_position_candidate_rows = [
            r for r in mesh_residual_rows
            if str(json_value_or_dash(r, "StringValue")) == "POSITION"
            and json_double_or_none(r, "RotatedFloat3PlausibleValueRatio") is not None
            and (json_double_or_none(r, "RotatedFloat3PlausibleValueRatio") or 0.0) >= 0.80
        ]

        position_lead_count = _get_position_lead_count_for_mesh_size(
            position_role, mesh_size
        )

        # Position samples (top 4)
        position_samples = []
        if isinstance(position_role, dict):
            samples = position_role.get("Samples")
            if samples and isinstance(samples, list):
                for s in samples:
                    if isinstance(s, dict) and safe_int(s.get("MeshSize", 0)) == mesh_size:
                        stream = s.get("Stream", {})
                        position_samples.append(
                            f"{json_value_or_dash(s, 'IdPrefix')}:"
                            f"mesh#{json_value_or_dash(s, 'MeshBlockIndex')}:"
                            f"stream@{json_value_or_dash(stream, 'MeshPayloadOffset')}/"
                            f"#{json_value_or_dash(stream, 'TargetBlockIndex')}:"
                            f"payload={json_value_or_dash(stream, 'DeclaredPayloadBytes')}"
                        )
                        if len(position_samples) >= 4:
                            break

        pairing_count = measure_sum_or_zero(pairings, "Count")
        normal_pairing_count = measure_sum_or_zero(
            [
                p for p in pairings
                if str(json_value_or_dash(p, "VertexRole")).startswith("normal")
            ],
            "Count",
        )
        uv_pairing_count = measure_sum_or_zero(
            [
                p for p in pairings
                if str(json_value_or_dash(p, "VertexRole")).startswith("uv")
            ],
            "Count",
        )
        position_pairing_count = measure_sum_or_zero(
            [
                p for p in pairings
                if str(json_value_or_dash(p, "VertexRole")).startswith("position")
            ],
            "Count",
        )

        # Topology hints (top 4 by count desc, vertex count desc)
        sorted_attr = sorted(
            attribute_rows,
            key=lambda a: (
                -safe_int(a.get("Count", 0)),
                -safe_int(a.get("VertexCount", 0)),
            ),
        )
        topology_hints = []
        for a in sorted_attr[:4]:
            topo = a.get("Topology", {})
            topology_hints.append(
                f"v={json_value_or_dash(a, 'VertexCount')} "
                f"count={json_value_or_dash(a, 'Count')} "
                f"{json_value_or_dash(topo, 'PrimaryTopology') if isinstance(topo, dict) else '-'}"
            )

        # Residual hints (top 4 by count desc, payload asc)
        sorted_residual = sorted(
            mesh_residual_rows,
            key=lambda r: (
                -safe_int(r.get("Count", 0)),
                safe_int(r.get("DeclaredPayloadBytes", 0)),
            ),
        )
        residual_hints = []
        for r in sorted_residual[:4]:
            residual_hints.append(
                f"stream@{json_value_or_dash(r, 'MeshPayloadOffset')} "
                f"payload={json_value_or_dash(r, 'DeclaredPayloadBytes')} "
                f"{json_value_or_dash(r, 'StringValue')} "
                f"plausible={json_value_or_dash(r, 'RotatedFloat3PlausibleValueRatio')}"
            )

        residual_stream_count = (
            safe_int(residual_target_first.get("ResidualStreamCount", 0))
            if residual_target_first
            else 0
        )
        decision = _get_position_gap_decision(
            mesh_size=mesh_size,
            position_lead_count=position_lead_count,
            topology_pairing_count=pairing_count,
            residual_stream_count=residual_stream_count,
            residual_position_candidate_rows=len(residual_position_candidate_rows),
            attribute_set_count=len(attribute_rows),
        )

        rows.append({
            "MeshSize": mesh_size,
            "PositionLeadCount": position_lead_count,
            "TopPairingRows": len(pairings),
            "TopologyPairingCount": pairing_count,
            "NormalPairingCount": normal_pairing_count,
            "UvPairingCount": uv_pairing_count,
            "PositionPairingCount": position_pairing_count,
            "AttributeSetRows": len(attribute_rows),
            "ResidualStreamCount": residual_stream_count,
            "ResidualPositionCandidateRows": len(residual_position_candidate_rows),
            "Decision": decision,
            "PositionSamples": " | ".join(position_samples) if position_samples else "-",
            "TopologyHints": " | ".join(topology_hints) if topology_hints else "-",
            "ResidualHints": " | ".join(residual_hints) if residual_hints else "-",
        })

    # --- Guard assertions ---

    mesh325_rows = [r for r in rows if r["MeshSize"] == 325]
    if not mesh325_rows:
        raise ValueError(
            "PositionSourceGapReport failed: no meshSize=325 row found."
        )
    mesh325 = mesh325_rows[0]
    if (
        int(mesh325["TopologyPairingCount"]) < 300
        or int(mesh325["ResidualStreamCount"]) != 0
    ):
        raise ValueError(
            "PositionSourceGapReport failed: meshSize=325 no longer matches the "
            "topology-rich residual-empty gap profile; review before reranking."
        )

    mesh305_rows = [r for r in rows if r["MeshSize"] == 305]
    if not mesh305_rows:
        raise ValueError(
            "PositionSourceGapReport failed: no meshSize=305 row found."
        )
    mesh305 = mesh305_rows[0]
    if int(mesh305["ResidualPositionCandidateRows"]) < 5:
        raise ValueError(
            "PositionSourceGapReport failed: meshSize=305 residual-position "
            f"candidate rows dropped below 5 "
            f"({mesh305['ResidualPositionCandidateRows']})."
        )

    # --- Output ---

    report_dir = Path(report_path).parent
    json_path = report_dir / "position-source-gap-report.json"
    md_path = report_dir / "position-source-gap-report.md"

    summary: dict[str, Any] = {
        "Schema": "position-source-gap-report/v1",
        "CandidateOnly": True,
        "SourceReport": str(report_path),
        "TargetMeshSizes": target_mesh_sizes,
        "Rows": sorted(rows, key=lambda r: int(r["MeshSize"])),
        "Interpretation": (
            "Candidate-only ranking report for position-source search gaps. "
            "Does not promote geometry truth, topology truth, or export readiness."
        ),
    }
    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md_lines: list[str] = [
        "# Position Source Gap Report",
        "",
        "Candidate-only ranking report for topology-rich mesh families where "
        "position-source evidence is sparse, residual-only, or side-stream/noise.",
        "",
        "Generated under ignored `Exports/`; do not stage generated discovery output.",
        "",
        "| Mesh size | Position leads | Pairing count | Normal pairs | UV pairs | "
        "Attribute rows | Residuals | Residual POSITION candidates | Decision |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in sorted(rows, key=lambda r: int(r["MeshSize"])):
        md_lines.append(
            f"| {format_markdown_cell(row['MeshSize'])} "
            f"| {format_markdown_cell(row['PositionLeadCount'])} "
            f"| {format_markdown_cell(row['TopologyPairingCount'])} "
            f"| {format_markdown_cell(row['NormalPairingCount'])} "
            f"| {format_markdown_cell(row['UvPairingCount'])} "
            f"| {format_markdown_cell(row['AttributeSetRows'])} "
            f"| {format_markdown_cell(row['ResidualStreamCount'])} "
            f"| {format_markdown_cell(row['ResidualPositionCandidateRows'])} "
            f"| {format_markdown_cell(row['Decision'])} |"
        )

    md_lines += [
        "",
        "## Topology and residual hints",
        "",
        "| Mesh size | Position samples | Topology hints | Residual hints |",
        "|---:|---|---|---|",
    ]
    for row in sorted(rows, key=lambda r: int(r["MeshSize"])):
        md_lines.append(
            f"| {format_markdown_cell(row['MeshSize'])} "
            f"| {format_markdown_cell(row['PositionSamples'])} "
            f"| {format_markdown_cell(row['TopologyHints'])} "
            f"| {format_markdown_cell(row['ResidualHints'])} |"
        )

    md_lines += [
        "",
        "Interpretation: use this to prioritize offline parser/probe work only. "
        "Do not treat sparse position leads, residual streams, or semantic hints "
        "as export-ready geometry truth.",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    # --- Console output ---
    print("\n--- PositionSourceGapReport candidate-only position-source gap ranking")
    print(
        f"{'MeshSize':<10} {'PosLeads':>9} {'Pairing':>9} {'Normal':>9} "
        f"{'UV':>9} {'AttrRows':>9} {'Residuals':>10} {'ResPosCand':>12} {'Decision'}"
    )
    print("-" * 120)
    for row in sorted(rows, key=lambda r: int(r["MeshSize"])):
        print(
            f"{row['MeshSize']:<10} {row['PositionLeadCount']:>9} "
            f"{row['TopologyPairingCount']:>9} {row['NormalPairingCount']:>9} "
            f"{row['UvPairingCount']:>9} {row['AttributeSetRows']:>9} "
            f"{row['ResidualStreamCount']:>10} {row['ResidualPositionCandidateRows']:>12} "
            f"{row['Decision']}"
        )
    print(f"PositionSourceGapReport JSON: {json_path}")
    print(f"PositionSourceGapReport markdown: {md_path}")
    print(
        "PositionSourceGapReport passed: topology-rich families are ranked "
        "without promoting geometry/export truth."
    )


# ============================================================================
# ResidualPositionClassifierReport  (inventory-level)
# ============================================================================


def _format_residual_float3_prefix(
    prefix_items: list[dict[str, Any]], take: int = 2
) -> str:
    """Format vector prefix samples for display.

    Mirrors: Format-ResidualFloat3Prefix
    """
    if not prefix_items:
        return "-"
    parts: list[str] = []
    for item in prefix_items[:take]:
        parts.append(
            f"v{json_value_or_dash(item, 'Index')}="
            f"({json_value_or_dash(item, 'X')},"
            f"{json_value_or_dash(item, 'Y')},"
            f"{json_value_or_dash(item, 'Z')})"
        )
    return "; ".join(parts) if parts else "-"


def residual_position_classifier_report(report_path: str | Path) -> None:
    """Candidate-only strict classifier dry-run for meshSize=305 stream@188 POSITION residuals.

    Loads the mesh-binding inventory, filters for meshSize=305 stream@188
    StringValue=POSITION usage=1 access=19 residual leads, extracts strict
    classifier review data, builds sample-level rows, cross-tabulates by
    payload and ID/mesh pairs, and generates representative stream-body
    probe commands.

    Guards: strict classifier passes = 0, same paired (mesh#7+mesh#27) rows >= 8,
    divergent paired rows = 0, candidate guard rows >= 3.

    Generates residual-position-classifier-report.json/.md and
    residual-position-family-crosstab.json/.md reports.

    Mirrors: Invoke-ResidualPositionClassifierReport
    """
    report = load_json_report(report_path)

    residual_streams_raw = report.get("TopResidualStreams")
    if (
        not residual_streams_raw
        or not isinstance(residual_streams_raw, list)
        or len(residual_streams_raw) == 0
    ):
        raise ValueError(
            "ResidualPositionClassifierReport failed: TopResidualStreams "
            "is missing from mesh-binding inventory."
        )
    streams: list[dict[str, Any]] = residual_streams_raw

    # --- Filter target leads (meshSize=305 stream@188 POSITION usage=1 access=19) ---

    target_leads = [
        s
        for s in streams
        if safe_int(s.get("MeshSize", 0)) == 305
        and safe_int(s.get("MeshPayloadOffset", 0)) == 188
        and str(json_value_or_dash(s, "StringValue")) == "POSITION"
        and str(json_value_or_dash(s, "DataStreamUsage")) == "1"
        and str(json_value_or_dash(s, "DataStreamAccess")) == "19"
    ]
    if len(target_leads) == 0:
        raise ValueError(
            "ResidualPositionClassifierReport failed: no meshSize=305 "
            "stream@188 POSITION usage=1 access=19 residual leads were found."
        )

    # --- Build sample rows and summary rows ---

    sample_rows: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []

    for lead in target_leads:
        # Strict classifier review
        review = lead.get("StrictRotatedFloat3PositionClassifierReview")
        if review is None or not isinstance(review, dict):
            review = {}

        miss_reasons_val = review.get("MissReasons")
        miss_reasons = (
            "; ".join(str(m) for m in miss_reasons_val)
            if isinstance(miss_reasons_val, list)
            else "-"
        )

        strict_pass = bool(review.get("PassesStrictClassifier", False))

        max_plausible_threshold_raw = review.get(
            "MaxPlausibleValueRatioThresholdForThisSample"
        )
        max_plausible_threshold: float | None = None
        if max_plausible_threshold_raw is not None:
            try:
                max_plausible_threshold = float(max_plausible_threshold_raw)
            except (ValueError, TypeError):
                max_plausible_threshold = None

        # Samples
        samples_raw = lead.get("Samples")
        samples: list[dict[str, Any]] = (
            samples_raw if isinstance(samples_raw, list) else []
        )

        sample_ids_list = sorted(
            {
                f"{json_value_or_dash(s, 'IdPrefix')}:mesh#{json_value_or_dash(s, 'MeshBlockIndex')}"
                for s in samples[:8]
                if isinstance(s, dict)
            }
        )
        sample_ids = ",".join(sample_ids_list) if sample_ids_list else "-"

        sample_meshes_list = sorted(
            {
                f"mesh#{json_value_or_dash(s, 'MeshBlockIndex')}"
                for s in samples
                if isinstance(s, dict)
            }
        )
        sample_meshes = ",".join(sample_meshes_list) if sample_meshes_list else "-"

        archive_names_set = sorted(
            {
                str(json_value_or_dash(s, "ArchiveName"))
                for s in samples
                if isinstance(s, dict)
            }
        )
        archive_count = len(archive_names_set)

        # Build lead sample rows
        lead_sample_rows: list[dict[str, object]] = []
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            stream = sample.get("Stream")
            if stream is None or not isinstance(stream, dict):
                stream = {}
            role_stats = stream.get("RoleStats")
            if role_stats is None or not isinstance(role_stats, dict):
                role_stats = {}
            rotated_float3_stats = role_stats.get("RotatedFloat3Stats")
            if rotated_float3_stats is None or not isinstance(
                rotated_float3_stats, dict
            ):
                rotated_float3_stats = {}
            prefix_raw = rotated_float3_stats.get("Prefix")
            prefix: list[dict[str, Any]] = (
                prefix_raw if isinstance(prefix_raw, list) else []
            )

            lead_sample_rows.append({
                "Payload": safe_int(lead.get("DeclaredPayloadBytes", 0)),
                "IdPrefix": str(json_value_or_dash(sample, "IdPrefix")),
                "ArchiveName": str(json_value_or_dash(sample, "ArchiveName")),
                "EntryIndex": safe_int(sample.get("EntryIndex", 0)),
                "ManifestEntryIndex": json_value_or_dash(sample, "ManifestEntryIndex"),
                "MeshBlock": f"mesh#{json_value_or_dash(sample, 'MeshBlockIndex')}",
                "MeshBlockIndex": safe_int(sample.get("MeshBlockIndex", 0)),
                "StreamBlock": f"#{json_value_or_dash(stream, 'TargetBlockIndex')}",
                "StreamBlockIndex": safe_int(stream.get("TargetBlockIndex", 0)),
                "TargetSize": json_value_or_dash(stream, "TargetSize"),
                "HeaderBytes": json_value_or_dash(stream, "HeaderBytes"),
                "BodyFirst16": str(json_value_or_dash(stream, "BodyFirst16")),
                "VectorCount": json_value_or_dash(rotated_float3_stats, "VectorCount"),
                "Finite": json_double_or_none(
                    rotated_float3_stats, "FiniteVectorRatio"
                ),
                "Plausible": json_double_or_none(
                    rotated_float3_stats, "PlausibleValueRatio"
                ),
                "NonZero": json_double_or_none(
                    rotated_float3_stats, "NonZeroVectorRatio"
                ),
                "Extent": json_double_or_none(
                    rotated_float3_stats, "MaxExtent"
                ),
                "Prefix": _format_residual_float3_prefix(prefix, take=2),
                "StrictPass": strict_pass,
                "MissReasons": miss_reasons,
            })

        sample_rows.extend(lead_sample_rows)

        rows.append({
            "MeshSize": safe_int(lead.get("MeshSize", 305)),
            "Stream": f"stream@{json_value_or_dash(lead, 'MeshPayloadOffset')}",
            "Payload": safe_int(lead.get("DeclaredPayloadBytes", 0)),
            "Count": safe_int(lead.get("Count", 0)),
            "SampleCount": len(samples),
            "ArchiveCount": archive_count,
            "SampleMeshes": sample_meshes,
            "SampleIds": sample_ids,
            "VectorCount": json_value_or_dash(lead, "RotatedFloat3VectorCount"),
            "Finite": json_double_or_none(lead, "RotatedFloat3FiniteVectorRatio"),
            "Plausible": json_double_or_none(
                lead, "RotatedFloat3PlausibleValueRatio"
            ),
            "NonZero": json_double_or_none(
                lead, "RotatedFloat3NonZeroVectorRatio"
            ),
            "Extent": json_double_or_none(lead, "RotatedFloat3MaxExtent"),
            "StrictPass": strict_pass,
            "MaxPlausibleThresholdForSample": max_plausible_threshold,
            "MissReasons": miss_reasons,
        })

    # --- Guard rows (Plausible >= 0.80, MaxPlausibleThresholdForSample not None) ---

    guard_rows = [
        r
        for r in rows
        if r["MaxPlausibleThresholdForSample"] is not None
        and r["Plausible"] is not None
        and float(r["Plausible"]) >= 0.80
    ]
    if len(guard_rows) < 3:
        raise ValueError(
            "ResidualPositionClassifierReport failed: expected at least three "
            "target residual leads that can support a candidate-only "
            f"plausible>=0.80 guard, found {len(guard_rows)}."
        )

    min_plausible = min(
        float(r["Plausible"])
        for r in guard_rows
        if r["Plausible"] is not None
    )
    max_plausible = max(
        float(r["Plausible"])
        for r in guard_rows
        if r["Plausible"] is not None
    )
    strict_pass_count = sum(1 for r in rows if r["StrictPass"])

    # --- ID / mesh-block pairing analysis ---

    # Group sample_rows by (Payload, IdPrefix)
    id_mesh_groups: dict[tuple[int, str], list[dict[str, object]]] = {}
    for sr in sample_rows:
        key = (int(sr["Payload"]), str(sr["IdPrefix"]))
        id_mesh_groups.setdefault(key, []).append(sr)

    id_mesh_rows: list[dict[str, object]] = []
    for (payload, id_prefix), group_items in id_mesh_groups.items():
        mesh_blocks_set = sorted(
            {str(item["MeshBlock"]) for item in group_items}
        )
        stream_blocks_set = sorted(
            {str(item["StreamBlock"]) for item in group_items}
        )
        body_first16_set = sorted(
            {str(item["BodyFirst16"]) for item in group_items}
        )
        prefix_set = sorted(
            {str(item["Prefix"]) for item in group_items}
        )

        has_mesh7 = "mesh#7" in mesh_blocks_set
        has_mesh27 = "mesh#27" in mesh_blocks_set

        if has_mesh7 and has_mesh27:
            pair_status = "mesh#7+mesh#27"
        elif len(mesh_blocks_set) > 1:
            pair_status = "multi-mesh"
        else:
            pair_status = "single-mesh"

        stream_blocks_match = len(stream_blocks_set) == 1
        body_first16_matches = len(body_first16_set) == 1
        prefixes_match = len(prefix_set) == 1

        if (
            pair_status == "mesh#7+mesh#27"
            and stream_blocks_match
            and body_first16_matches
            and prefixes_match
        ):
            pair_comparison = "paired-mesh-same-stream-body-prefix"
        elif pair_status == "mesh#7+mesh#27":
            pair_comparison = "paired-mesh-different-stream-evidence"
        else:
            pair_comparison = pair_status

        first = group_items[0]
        id_mesh_rows.append({
            "Payload": payload,
            "IdPrefix": id_prefix,
            "SampleCount": len(group_items),
            "MeshBlocks": ",".join(mesh_blocks_set),
            "PairStatus": pair_status,
            "PairComparison": pair_comparison,
            "StreamBlocksMatch": stream_blocks_match,
            "BodyFirst16Matches": body_first16_matches,
            "PrefixesMatch": prefixes_match,
            "ArchiveNames": ",".join(
                sorted({str(item["ArchiveName"]) for item in group_items})
            ),
            "EntryIndices": ",".join(
                sorted({str(item["EntryIndex"]) for item in group_items})
            ),
            "StreamBlocks": ",".join(stream_blocks_set),
            "BodyFirst16": ",".join(body_first16_set),
            "Prefixes": " || ".join(prefix_set[:3]),
            "Plausible": first["Plausible"],
            "Extent": first["Extent"],
            "StrictPass": first["StrictPass"],
            "MissReasons": str(first["MissReasons"]),
        })

    # --- Payload summary ---

    payload_groups: dict[int, list[dict[str, object]]] = {}
    for sr in sample_rows:
        p = int(sr["Payload"])
        payload_groups.setdefault(p, []).append(sr)

    payload_rows: list[dict[str, object]] = []
    for payload, p_items in payload_groups.items():
        p_id_mesh_rows = [
            r for r in id_mesh_rows if int(r["Payload"]) == payload
        ]
        mesh7_and27_count = sum(
            1 for r in p_id_mesh_rows
            if str(r["PairStatus"]) == "mesh#7+mesh#27"
        )
        single_mesh_count = sum(
            1 for r in p_id_mesh_rows
            if str(r["PairStatus"]) == "single-mesh"
        )
        candidate_guard = any(
            r for r in guard_rows if int(r["Payload"]) == payload
        )
        p_strict_passes = sum(
            1 for item in p_items if item["StrictPass"]
        )

        first_p = p_items[0]
        payload_rows.append({
            "Payload": payload,
            "SampleCount": len(p_items),
            "IdCount": len({str(item["IdPrefix"]) for item in p_items}),
            "MeshBlocks": ",".join(
                sorted({str(item["MeshBlock"]) for item in p_items})
            ),
            "Mesh7And27IdCount": mesh7_and27_count,
            "SingleMeshIdCount": single_mesh_count,
            "CandidateGuard": candidate_guard,
            "StrictPassCount": p_strict_passes,
            "Plausible": first_p["Plausible"],
            "Extent": first_p["Extent"],
            "MissReasons": str(first_p["MissReasons"]),
        })

    # --- Same/different paired rows ---

    same_paired_rows = [
        r
        for r in id_mesh_rows
        if str(r["PairComparison"]) == "paired-mesh-same-stream-body-prefix"
    ]
    different_paired_rows = [
        r
        for r in id_mesh_rows
        if str(r["PairComparison"]) == "paired-mesh-different-stream-evidence"
    ]

    # --- Representative probe rows ---

    # Group same_paired_rows by Payload
    rep_payload_groups: dict[int, list[dict[str, object]]] = {}
    for spr in same_paired_rows:
        p = int(spr["Payload"])
        rep_payload_groups.setdefault(p, []).append(spr)

    representative_probe_rows: list[dict[str, object]] = []
    report_dir = Path(report_path).parent
    project_path = REPO_ROOT / "src" / "RiftAssetDumper" / "RiftAssetDumper.csproj"
    root_path = REPO_ROOT / "Source"

    for payload, spr_items in sorted(rep_payload_groups.items()):
        # Pick first by sorted IdPrefix
        spr_items.sort(key=lambda r: str(r["IdPrefix"]))
        id_row = spr_items[0]

        # Find a mesh#7 sample for this payload/id
        mesh7_samples = [
            sr
            for sr in sample_rows
            if int(sr["Payload"]) == payload
            and str(sr["IdPrefix"]) == str(id_row["IdPrefix"])
            and int(sr["MeshBlockIndex"]) == 7
        ]
        if mesh7_samples:
            selected = mesh7_samples[0]
        else:
            # Fallback: any sample for this payload/id
            fallback = [
                sr
                for sr in sample_rows
                if int(sr["Payload"]) == payload
                and str(sr["IdPrefix"]) == str(id_row["IdPrefix"])
            ]
            if not fallback:
                continue
            selected = fallback[0]

        stream_block_num = str(selected["StreamBlock"]).lstrip("#")
        out_path = (
            report_dir
            / f"probe-residual-position-payload{selected['Payload']}-"
            f"{selected['IdPrefix']}-stream{stream_block_num}.json"
        )
        dotnet_cmd = (
            f'dotnet run --project "{project_path}" -- '
            f'probe-nif-stream-body --root "{root_path}" '
            f"--id {selected['IdPrefix']} "
            f"--stream-block {stream_block_num} "
            f'--out "{out_path}"'
        )
        representative_probe_rows.append({
            "Payload": int(selected["Payload"]),
            "IdPrefix": str(selected["IdPrefix"]),
            "MeshBlock": str(selected["MeshBlock"]),
            "StreamBlock": f"#{stream_block_num}",
            "BodyFirst16": str(selected["BodyFirst16"]),
            "Prefix": str(selected["Prefix"]),
            "OutPath": str(out_path),
            "Command": dotnet_cmd,
        })

    # --- Guard assertions ---

    if strict_pass_count != 0:
        raise ValueError(
            "ResidualPositionClassifierReport failed: expected this residual "
            "lane to remain candidate-only with 0 strict classifier passes, "
            f"found {strict_pass_count}."
        )

    if len(same_paired_rows) < 8:
        raise ValueError(
            "ResidualPositionClassifierReport failed: expected at least 8 "
            "mesh#7+mesh#27 paired rows with matching stream/body/prefix "
            f"evidence, found {len(same_paired_rows)}."
        )

    if len(different_paired_rows) != 0:
        raise ValueError(
            "ResidualPositionClassifierReport failed: found "
            f"{len(different_paired_rows)} paired mesh rows with divergent "
            "stream/body/prefix evidence."
        )

    # --- Console output ---

    print(
        "\n--- ResidualPositionClassifierReport candidate-only strict "
        "classifier dry-run"
    )
    print(
        "Strict role classifier remains: VectorCount>=3, "
        "FiniteVectorRatio>=0.95, PlausibleValueRatio>=0.95, "
        "MaxExtent>=0.0001, NonZeroVectorRatio>=0.50."
    )
    print(
        "Candidate report threshold: keep repeated residual leads at "
        "PlausibleValueRatio>=0.80 as ranking evidence only; do not "
        "promote parser roles."
    )

    # Print summary table
    sorted_rows = sorted(rows, key=lambda r: (int(r["Payload"]), int(r["Count"])))
    print(
        f"{'Payload':>8} {'Count':>6} {'Samples':>8} {'Archives':>9} "
        f"{'Meshes':<30} {'Vectors':>9} {'Finite':>8} {'Plausible':>10} "
        f"{'NonZero':>8} {'Extent':>10} {'Strict':>7} {'Thresh':>10} {'Misses'}"
    )
    print("-" * 150)
    for row in sorted_rows:
        threshold_str = (
            f"{row['MaxPlausibleThresholdForSample']:.4f}"
            if row["MaxPlausibleThresholdForSample"] is not None
            else "-"
        )
        finite_str = (
            f"{row['Finite']:.4f}" if row["Finite"] is not None else "-"
        )
        plausible_str = (
            f"{row['Plausible']:.4f}"
            if row["Plausible"] is not None
            else "-"
        )
        nonzero_str = (
            f"{row['NonZero']:.4f}"
            if row["NonZero"] is not None
            else "-"
        )
        extent_str = (
            f"{row['Extent']:.4f}" if row["Extent"] is not None else "-"
        )
        print(
            f"{row['Payload']:>8} {row['Count']:>6} {row['SampleCount']:>8} "
            f"{row['ArchiveCount']:>9} {str(row['SampleMeshes']):<30} "
            f"{str(row['VectorCount']):>9} {finite_str:>8} {plausible_str:>10} "
            f"{nonzero_str:>8} {extent_str:>10} "
            f"{str(row['StrictPass']):>7} {threshold_str:>10} "
            f"{row['MissReasons']}"
        )

    print("\nStrict classifier miss reasons by payload:")
    for row in sorted_rows:
        threshold_text = (
            f"{row['MaxPlausibleThresholdForSample']:.4f}"
            if row["MaxPlausibleThresholdForSample"] is not None
            else "-"
        )
        print(
            f"  payload={row['Payload']} count={row['Count']}: "
            f"misses=[{row['MissReasons']}] "
            f"maxPlausibleThresholdForSample={threshold_text}"
        )

    print("\nTarget sample repetition context:")
    for row in sorted_rows:
        print(
            f"  payload={row['Payload']} samples={row['SampleCount']} "
            f"archives={row['ArchiveCount']} meshes={row['SampleMeshes']} "
            f"ids={row['SampleIds']}"
        )

    # --- Write JSON + Markdown output ---

    classifier_json_path = report_dir / "residual-position-classifier-report.json"
    classifier_md_path = report_dir / "residual-position-classifier-report.md"

    classifier_report: dict[str, Any] = {
        "Schema": "residual-position-classifier-report/v1",
        "CandidateOnly": True,
        "Target": "meshSize=305 stream@188 StringValue=POSITION usage=1 access=19",
        "SourceReport": str(report_path),
        "StrictClassifierRole": "position-float3-ror1-lead",
        "StrictClassifierThresholds": {
            "VectorCount": ">= 3",
            "FiniteVectorRatio": ">= 0.95",
            "PlausibleValueRatio": ">= 0.95",
            "MaxExtent": ">= 0.0001",
            "NonZeroVectorRatio": ">= 0.50",
        },
        "Summary": {
            "TargetRows": len(rows),
            "StrictPassRows": strict_pass_count,
            "CandidateGuardRows": len(guard_rows),
            "MinCandidatePlausible": min_plausible,
            "MaxCandidatePlausible": max_plausible,
        },
        "Rows": sorted_rows,
        "CandidateGuardRows": sorted(
            guard_rows, key=lambda r: (int(r["Payload"]), int(r["Count"]))
        ),
        "Interpretation": (
            "Strict classifier miss report only. Repeated bounded-position-like "
            "rows remain candidate-only and do not promote parser roles, "
            "geometry truth, or export readiness."
        ),
    }
    classifier_json_path.write_text(
        json.dumps(classifier_report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md_lines: list[str] = [
        "# Residual Position Classifier Report",
        "",
        "Candidate-only dry-run for `meshSize=305 stream@188 StringValue=POSITION usage=1 access=19`.",
        "",
        "Strict `position-float3-ror1-lead` classifier remains unchanged:",
        "",
        "```text",
        "VectorCount >= 3",
        "FiniteVectorRatio >= 0.95",
        "PlausibleValueRatio >= 0.95",
        "MaxExtent >= 0.0001",
        "NonZeroVectorRatio >= 0.50",
        "```",
        "",
        (
            f"Summary: target rows={len(rows)}, strict-pass={strict_pass_count}, "
            f"candidate-guard rows={len(guard_rows)}, "
            f"plausible range={min_plausible:.4f}..{max_plausible:.4f}."
        ),
        "",
        "| Payload | Count | Samples | Archives | Meshes | VectorCount | Finite | Plausible | NonZero | Extent | StrictPass | Max plausible threshold | Miss reasons | Sample IDs |",
        "|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---:|---|---|",
    ]
    for row in sorted_rows:
        threshold_md = (
            f"{row['MaxPlausibleThresholdForSample']:.4f}"
            if row["MaxPlausibleThresholdForSample"] is not None
            else "-"
        )
        md_lines.append(
            f"| {format_markdown_cell(row['Payload'])} "
            f"| {format_markdown_cell(row['Count'])} "
            f"| {format_markdown_cell(row['SampleCount'])} "
            f"| {format_markdown_cell(row['ArchiveCount'])} "
            f"| {format_markdown_cell(row['SampleMeshes'])} "
            f"| {format_markdown_cell(row['VectorCount'])} "
            f"| {format_markdown_cell(row['Finite'])} "
            f"| {format_markdown_cell(row['Plausible'])} "
            f"| {format_markdown_cell(row['NonZero'])} "
            f"| {format_markdown_cell(row['Extent'])} "
            f"| {format_markdown_cell(row['StrictPass'])} "
            f"| {format_markdown_cell(threshold_md)} "
            f"| {format_markdown_cell(row['MissReasons'])} "
            f"| {format_markdown_cell(row['SampleIds'])} |"
        )
    md_lines += [
        "",
        "Interpretation: repeated bounded-position-like rows remain below the "
        "strict plausible-ratio role threshold. Treat this as candidate-only "
        "ranking evidence, not promoted geometry truth.",
    ]
    classifier_md_path.write_text("\n".join(md_lines), encoding="utf-8")

    # --- Family cross-tab ---

    crosstab_json_path = report_dir / "residual-position-family-crosstab.json"
    crosstab_md_path = report_dir / "residual-position-family-crosstab.md"

    crosstab: dict[str, Any] = {
        "Schema": "residual-position-family-crosstab/v1",
        "CandidateOnly": True,
        "Target": "meshSize=305 stream@188 StringValue=POSITION usage=1 access=19",
        "SourceReport": str(report_path),
        "StrictClassifierRole": "position-float3-ror1-lead",
        "StrictClassifierThresholds": {
            "VectorCount": ">= 3",
            "FiniteVectorRatio": ">= 0.95",
            "PlausibleValueRatio": ">= 0.95",
            "MaxExtent": ">= 0.0001",
            "NonZeroVectorRatio": ">= 0.50",
        },
        "Summary": {
            "TargetRows": len(rows),
            "SampleRows": len(sample_rows),
            "StrictPassRows": strict_pass_count,
            "CandidateGuardRows": len(guard_rows),
            "Mesh7And27IdRows": sum(
                1 for r in id_mesh_rows
                if str(r["PairStatus"]) == "mesh#7+mesh#27"
            ),
            "Mesh7And27SameStreamBodyPrefixRows": len(same_paired_rows),
            "SingleMeshIdRows": sum(
                1 for r in id_mesh_rows
                if str(r["PairStatus"]) == "single-mesh"
            ),
            "MinCandidatePlausible": min_plausible,
            "MaxCandidatePlausible": max_plausible,
        },
        "PayloadSummary": sorted(
            payload_rows, key=lambda r: int(r["Payload"])
        ),
        "IdMeshPairs": sorted(
            id_mesh_rows,
            key=lambda r: (int(r["Payload"]), str(r["IdPrefix"])),
        ),
        "RepresentativeProbeCommands": sorted(
            representative_probe_rows,
            key=lambda r: (int(r["Payload"]), str(r["IdPrefix"])),
        ),
        "SampleRows": sorted(
            sample_rows,
            key=lambda r: (
                int(r["Payload"]),
                str(r["IdPrefix"]),
                int(r["MeshBlockIndex"]),
            ),
        ),
        "Interpretation": (
            "Candidate-only ranking context for repeated residual "
            "POSITION-like rows; this does not promote parser role, "
            "geometry truth, or export readiness."
        ),
    }
    crosstab_json_path.write_text(
        json.dumps(crosstab, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    sorted_payload_rows = sorted(payload_rows, key=lambda r: int(r["Payload"]))
    sorted_id_mesh = sorted(
        id_mesh_rows,
        key=lambda r: (int(r["Payload"]), str(r["IdPrefix"])),
    )
    sorted_rep_probes = sorted(
        representative_probe_rows,
        key=lambda r: (int(r["Payload"]), str(r["IdPrefix"])),
    )

    family_md_lines: list[str] = [
        "# Residual Position Family Cross-tab",
        "",
        "Candidate-only grouping for `meshSize=305 stream@188 StringValue=POSITION usage=1 access=19`.",
        "",
        "This report is generated under ignored `Exports/` and is not commit material.",
        "",
        "## Payload summary",
        "",
        "| Payload | Samples | IDs | Mesh blocks | mesh#7+mesh#27 IDs | Single-mesh IDs | Candidate guard | Plausible | Extent | Miss reasons |",
        "|---:|---:|---:|---|---:|---:|---|---:|---:|---|",
    ]
    for row in sorted_payload_rows:
        family_md_lines.append(
            f"| {format_markdown_cell(row['Payload'])} "
            f"| {format_markdown_cell(row['SampleCount'])} "
            f"| {format_markdown_cell(row['IdCount'])} "
            f"| {format_markdown_cell(row['MeshBlocks'])} "
            f"| {format_markdown_cell(row['Mesh7And27IdCount'])} "
            f"| {format_markdown_cell(row['SingleMeshIdCount'])} "
            f"| {format_markdown_cell(row['CandidateGuard'])} "
            f"| {format_markdown_cell(row['Plausible'])} "
            f"| {format_markdown_cell(row['Extent'])} "
            f"| {format_markdown_cell(row['MissReasons'])} |"
        )
    family_md_lines += [
        "",
        "## ID / mesh-block repetition",
        "",
        "| Payload | ID | Samples | Mesh blocks | Pair status | Pair comparison | Stream blocks | Body match | Prefix match | Plausible | Extent | Prefix sample |",
        "|---:|---|---:|---|---|---|---|---|---|---:|---:|---|",
    ]
    for row in sorted_id_mesh:
        family_md_lines.append(
            f"| {format_markdown_cell(row['Payload'])} "
            f"| {format_markdown_cell(row['IdPrefix'])} "
            f"| {format_markdown_cell(row['SampleCount'])} "
            f"| {format_markdown_cell(row['MeshBlocks'])} "
            f"| {format_markdown_cell(row['PairStatus'])} "
            f"| {format_markdown_cell(row['PairComparison'])} "
            f"| {format_markdown_cell(row['StreamBlocks'])} "
            f"| {format_markdown_cell(row['BodyFirst16Matches'])} "
            f"| {format_markdown_cell(row['PrefixesMatch'])} "
            f"| {format_markdown_cell(row['Plausible'])} "
            f"| {format_markdown_cell(row['Extent'])} "
            f"| {format_markdown_cell(row['Prefixes'])} |"
        )
    family_md_lines += [
        "",
        "## Representative stream-body probe commands",
        "",
        "One representative `mesh#7` sample per repeated candidate payload. "
        "These commands write ignored JSON under `Exports/`.",
        "",
        "| Payload | ID | Mesh | Stream block | Body first16 | Prefix sample | Command |",
        "|---:|---|---|---|---|---|---|",
    ]
    for row in sorted_rep_probes:
        family_md_lines.append(
            f"| {format_markdown_cell(row['Payload'])} "
            f"| {format_markdown_cell(row['IdPrefix'])} "
            f"| {format_markdown_cell(row['MeshBlock'])} "
            f"| {format_markdown_cell(row['StreamBlock'])} "
            f"| {format_markdown_cell(row['BodyFirst16'])} "
            f"| {format_markdown_cell(row['Prefix'])} "
            f"| `{format_markdown_cell(row['Command'])}` |"
        )
    family_md_lines += [
        "",
        "Interpretation: `mesh#7+mesh#27` repetition strengthens this as a "
        "family-ranking lead, but all rows remain below strict parser role "
        "promotion. Keep candidate-only.",
    ]
    crosstab_md_path.write_text("\n".join(family_md_lines), encoding="utf-8")

    # --- Final console summary ---

    print(f"ResidualPositionClassifierReport JSON: {classifier_json_path}")
    print(f"ResidualPositionClassifierReport markdown: {classifier_md_path}")
    print(f"ResidualPositionFamilyCrossTab JSON: {crosstab_json_path}")
    print(f"ResidualPositionFamilyCrossTab markdown: {crosstab_md_path}")
    print(
        f"ResidualPositionFamilyCrossTab guard: same paired "
        f"stream/body/prefix rows={len(same_paired_rows)}, "
        f"divergent paired rows=0, strict passes=0."
    )
    print(
        f"ResidualPositionClassifierReport: target rows={len(rows)}, "
        f"strict-pass={strict_pass_count}, "
        f"candidate-guard rows={len(guard_rows)}, "
        f"plausible range={min_plausible:.4f}..{max_plausible:.4f}."
    )
    print(
        "ResidualPositionClassifierReport passed: strict classifier misses "
        "are explained without changing role promotion or proof guards."
    )


# ============================================================================
# Discovery Workbench
# ============================================================================


def discovery_workbench(repo_root: str, out_dir: str, privacy_scan: bool = False) -> None:
    """Run the discovery workbench Python script and validate output.

    Mirrors: PS Invoke-DiscoveryWorkbench
    """
    workbench_script = Path(repo_root) / "scripts" / "discovery_workbench.py"
    if not workbench_script.exists():
        raise FileNotFoundError(
            f"DiscoveryWorkbench failed: missing helper script {workbench_script}"
        )

    python_args = [str(workbench_script), "--root", str(repo_root), "--exports", str(out_dir)]
    if privacy_scan:
        python_args.append("--privacy-scan")

    print("\n--- DiscoveryWorkbench candidate-only ranked workbench")
    print(f"python {' '.join(python_args)}")
    result = subprocess.run(
        [sys.executable, *python_args],
        capture_output=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"DiscoveryWorkbench failed: python exited with {result.returncode}."
        )

    out_path = Path(out_dir)
    scoreboard_path = out_path / "discovery-workbench-scoreboard.json"
    scoreboard_md_path = out_path / "discovery-workbench-scoreboard.md"
    queue_path = out_path / "discovery-next-probe-queue.json"
    queue_md_path = out_path / "discovery-next-probe-queue.md"

    for required_path in (scoreboard_path, scoreboard_md_path, queue_path, queue_md_path):
        if not required_path.exists():
            raise FileNotFoundError(
                f"DiscoveryWorkbench failed: expected output missing: {required_path}"
            )

    scoreboard = load_json_report(str(scoreboard_path))
    if scoreboard.get("CandidateOnly") is not True:
        raise ValueError(
            "DiscoveryWorkbench failed: scoreboard CandidateOnly flag is not true."
        )

    candidates = scoreboard.get("Candidates") or []
    non_candidate_rows = [
        c for c in candidates if c.get("CandidateOnly") is not True
    ]
    if non_candidate_rows:
        raise ValueError(
            f"DiscoveryWorkbench failed: non-candidate rows found ({len(non_candidate_rows)})."
        )

    cross_checks = scoreboard.get("CrossChecks") or []
    non_candidate_checks = [
        c for c in cross_checks if c.get("CandidateOnly") is not True
    ]
    if non_candidate_checks:
        raise ValueError(
            f"DiscoveryWorkbench failed: non-candidate cross-check rows found ({len(non_candidate_checks)})."
        )

    if candidates:
        top = min(candidates, key=lambda c: c.get("Rank", 0))
        print(
            f"Top candidate: rank={top.get('Rank')}; "
            f"score={top.get('Score')}; "
            f"id={top.get('CandidateId')}; "
            f"title={top.get('Title')}"
        )

    print(f"DiscoveryWorkbench scoreboard JSON: {scoreboard_path}")
    print(f"DiscoveryWorkbench scoreboard markdown: {scoreboard_md_path}")
    print(f"DiscoveryWorkbench queue JSON: {queue_path}")
    print(f"DiscoveryWorkbench queue markdown: {queue_md_path}")
    print("DiscoveryWorkbench passed: generated candidate-only scoreboard and next-probe queue.")



# ============================================================================
# PositionSourceSibling probe helpers (shared by all sibling probe reports)
# ============================================================================


def _format_position_source_stream_list(streams):
    """Format a list of stream summary dicts for display.

    Mirrors: Format-PositionSourceStreamList
    """
    from scripts.rift_workflow_utils import json_value_or_dash
    items = []
    for s in streams:
        items.append(
            f"@{json_value_or_dash(s, 'MeshPayloadOffset')}/"
            f"#{json_value_or_dash(s, 'TargetBlockIndex')} "
            f"payload={json_value_or_dash(s, 'Payload')} "
            f"{json_value_or_dash(s, 'Role')}"
        )
    return ' | '.join(items) if items else 'none'


def _get_position_source_sibling_unique_count(rows, key):
    """Count unique values of a property across rows.

    Mirrors: Get-PositionSourceSiblingUniqueCount
    """
    return len({str(r.get(key, '')) for r in rows})

def _new_position_source_sibling_probe_row(spec):
    """Build a probe row from a sibling probe spec (with Path).

    Mirrors: New-PositionSourceSiblingProbeRow
    """
    path = str(spec["Path"])
    if not Path(path).exists():
        raise FileNotFoundError(
            f"PositionSourceSiblingProbeReport failed: probe report not found: {path}"
        )

    report = load_json_report(path)
    mesh_block = int(spec["MeshBlock"])

    meshes = report.get("Meshes") or []
    mesh_entries = [
        m for m in meshes
        if isinstance(m, dict) and safe_int(m.get("MeshBlockIndex", -1)) == mesh_block
    ]
    if len(mesh_entries) != 1:
        raise ValueError(
            f"PositionSourceSiblingProbeReport failed: expected exactly one "
            f"mesh#{mesh_block} entry in {path}, found {len(mesh_entries)}."
        )

    mesh = mesh_entries[0]
    attr_sets = mesh.get("AttributeSets") or []
    if len(attr_sets) != 1:
        raise ValueError(
            f"PositionSourceSiblingProbeReport failed: expected exactly one "
            f"attribute-set row for {spec.get('Id')} mesh#{mesh_block}, "
            f"found {len(attr_sets)}."
        )

    attr = attr_sets[0]
    pairings_val = mesh.get("Pairings")
    extra_val = attr.get("ExtraStreams")
    pairing_count = len(pairings_val) if isinstance(pairings_val, list) else 0
    extra_count = len(extra_val) if isinstance(extra_val, list) else 0
    topology = attr.get("Topology") or {}

    return {
        "Pair": str(spec["Pair"]),
        "PairLabel": str(spec.get("PairLabel", "")),
        "Id": str(spec["Id"]),
        "MeshBlock": mesh_block,
        "MeshSize": safe_int(json_value_or_dash(attr, "MeshSize")),
        "VertexCount": safe_int(json_value_or_dash(attr, "VertexCount")),
        "PrimaryTopology": str(
            json_value_or_dash(topology, "PrimaryTopology")
            if isinstance(topology, dict)
            else "-"
        ),
        "TopologyConfidence": safe_int(
            json_value_or_dash(topology, "Confidence")
            if isinstance(topology, dict)
            else 0
        ),
        "PositionMeshPayloadOffset": safe_int(
            json_value_or_dash(attr, "PositionMeshPayloadOffset")
        ),
        "PositionBlockIndex": safe_int(
            json_value_or_dash(attr, "PositionBlockIndex")
        ),
        "PositionDeclaredPayloadBytes": safe_int(
            json_value_or_dash(attr, "PositionDeclaredPayloadBytes")
        ),
        "PositionDataStreamUsage": str(
            json_value_or_dash(attr, "PositionDataStreamUsage")
        ),
        "PositionDataStreamAccess": str(
            json_value_or_dash(attr, "PositionDataStreamAccess")
        ),
        "PositionRole": str(json_value_or_dash(attr, "PositionRole")),
        "NormalMeshPayloadOffset": safe_int(
            json_value_or_dash(attr, "NormalMeshPayloadOffset")
        ),
        "NormalBlockIndex": safe_int(
            json_value_or_dash(attr, "NormalBlockIndex")
        ),
        "NormalDeclaredPayloadBytes": safe_int(
            json_value_or_dash(attr, "NormalDeclaredPayloadBytes")
        ),
        "UvMeshPayloadOffset": safe_int(
            json_value_or_dash(attr, "UvMeshPayloadOffset")
        ),
        "UvBlockIndex": safe_int(json_value_or_dash(attr, "UvBlockIndex")),
        "UvDeclaredPayloadBytes": safe_int(
            json_value_or_dash(attr, "UvDeclaredPayloadBytes")
        ),
        "PairingCount": pairing_count,
        "ExtraStreamCount": extra_count,
        "ProbePath": path,
    }


def _new_position_source_representative_probe_row(spec):
    """Build a representative summary row from a probe spec (with Path).

    Mirrors: New-PositionSourceRepresentativeProbeRow
    """
    path = str(spec["Path"])
    if not Path(path).exists():
        raise FileNotFoundError(
            f"PositionSourceSiblingRepresentativeProbeReport failed: "
            f"probe report not found: {path}"
        )

    report = load_json_report(path)
    mesh_block = int(spec["MeshBlock"])

    meshes = report.get("Meshes") or []
    mesh_entries = [
        m for m in meshes
        if isinstance(m, dict) and safe_int(m.get("MeshBlockIndex", -1)) == mesh_block
    ]
    if len(mesh_entries) != 1:
        raise ValueError(
            f"PositionSourceSiblingRepresentativeProbeReport failed: expected "
            f"exactly one mesh#{mesh_block} entry in {path}, "
            f"found {len(mesh_entries)}."
        )

    mesh = mesh_entries[0]
    attr_sets = mesh.get("AttributeSets") or []
    streams = mesh.get("Streams") or []

    # Classify streams
    def _stream_role(stream):
        role_stats = stream.get("RoleStats") or {}
        return str(role_stats.get("PrimaryRole", ""))

    position_streams = [s for s in streams if "position-float3" in _stream_role(s)]
    normal_streams = [s for s in streams if _stream_role(s).startswith("normal")]
    uv_streams = [s for s in streams if _stream_role(s).startswith("uv")]
    side_streams = [
        s for s in streams
        if not _stream_role(s).startswith("position-float3")
        and not _stream_role(s).startswith("normal")
        and not _stream_role(s).startswith("uv")
    ]

    def _stream_summary(s):
        return {
            "MeshPayloadOffset": safe_int(s.get("MeshPayloadOffset", 0)),
            "TargetBlockIndex": safe_int(s.get("TargetBlockIndex", 0)),
            "Payload": safe_int(s.get("DeclaredPayloadBytes", 0)),
            "Role": _stream_role(s),
        }

    attribute_summary = "none"
    if attr_sets:
        attr = attr_sets[0]
        extras_count = (
            len(attr.get("ExtraStreams"))
            if isinstance(attr.get("ExtraStreams"), list)
            else 0
        )
        topo = attr.get("Topology") or {}
        attribute_summary = (
            f"v={json_value_or_dash(attr, 'VertexCount')} "
            f"p@{json_value_or_dash(attr, 'PositionMeshPayloadOffset')}/"
            f"#{json_value_or_dash(attr, 'PositionBlockIndex')} "
            f"n@{json_value_or_dash(attr, 'NormalMeshPayloadOffset')}/"
            f"#{json_value_or_dash(attr, 'NormalBlockIndex')} "
            f"uv@{json_value_or_dash(attr, 'UvMeshPayloadOffset')}/"
            f"#{json_value_or_dash(attr, 'UvBlockIndex')} "
            f"topology={json_value_or_dash(topo, 'PrimaryTopology') if isinstance(topo, dict) else '-'} "
            f"extras={extras_count}"
        )

    return {
        "Pair": str(spec["Pair"]),
        "PairLabel": str(spec.get("PairLabel", "")),
        "Id": str(spec["Id"]),
        "MeshBlock": mesh_block,
        "MeshSize": safe_int(json_value_or_dash(mesh, "MeshSize")),
        "PositionStreams": [_stream_summary(s) for s in position_streams],
        "NormalStreams": [_stream_summary(s) for s in normal_streams],
        "UvStreams": [_stream_summary(s) for s in uv_streams],
        "SideStreams": [_stream_summary(s) for s in side_streams],
        "AttributeSetCount": len(attr_sets),
        "AttributeSummary": attribute_summary,
        "ProbePath": path,
    }

# ============================================================================
# PositionSourceSiblingProbeReport (orchestrator)
# ============================================================================


def position_source_sibling_probe_report(probe_specs):
    """Build candidate-only probe comparison from position-source sibling probes.

    Loads probe JSON for each spec, groups by Pair, validates sibling
    mesh has no attribute-set binding, computes uniqueness metrics, and
    writes JSON + MD reports.

    Mirrors: Invoke-PositionSourceSiblingProbeReport
    """
    import json
    from pathlib import Path

    rows = [
        _new_position_source_sibling_probe_row(spec)
        for spec in probe_specs
    ]

    # Group by Pair
    pair_groups = {}
    for row in rows:
        pair_key = str(row["Pair"])
        pair_groups.setdefault(pair_key, []).append(row)

    # Validate and build pair summaries
    pair_summaries = []
    for pair_key, pair_rows in sorted(pair_groups.items()):
        pair_rows_sorted = sorted(
            pair_rows, key=lambda r: int(r["MeshBlock"])
        )
        if len(pair_rows_sorted) != 2:
            raise ValueError(
                f"PositionSourceSiblingProbeReport failed: pair '{pair_key}' "
                f"expected exactly two probes, found {len(pair_rows_sorted)}."
            )

        primary = pair_rows_sorted[0]
        sibling = pair_rows_sorted[1]

        if int(primary["AttributeSetCount"]) < 1:
            raise ValueError(
                f"PositionSourceSiblingProbeReport failed: pair '{pair_key}' "
                f"primary mesh no longer has a complete attribute set."
            )

        if int(sibling["AttributeSetCount"]) != 0:
            raise ValueError(
                f"PositionSourceSiblingProbeReport failed: pair '{pair_key}' "
                f"sibling mesh unexpectedly gained a complete attribute set; "
                f"review before keeping the old interpretation."
            )

        # Check shared position stream
        if int(primary["PositionBlockIndex"]) != int(sibling["PositionBlockIndex"]):
            raise ValueError(
                f"PositionSourceSiblingProbeReport failed: pair '{pair_key}' "
                f"position stream block mismatch."
            )

        if int(primary["PositionDeclaredPayloadBytes"]) != int(sibling["PositionDeclaredPayloadBytes"]):
            raise ValueError(
                f"PositionSourceSiblingProbeReport failed: pair '{pair_key}' "
                f"position payload size mismatch."
            )

        pair_summaries.append({
            "Pair": pair_key,
            "PairLabel": str(primary["PairLabel"]),
            "Id": str(primary["Id"]),
            "MeshBlocks": f"mesh#{primary['MeshBlock']}, mesh#{sibling['MeshBlock']}",
            "MeshSizes": f"{primary['MeshSize']}, {sibling['MeshSize']}",
            "VertexCounts": f"{primary['VertexCount']}, {sibling['VertexCount']}",
            "SharedPositionBlock": (
                f"block#{primary['PositionBlockIndex']} "
                f"payload={primary['PositionDeclaredPayloadBytes']} "
                f"offsets=@{primary['PositionMeshPayloadOffset']}/"
                f"@{sibling['PositionMeshPayloadOffset']}"
            ),
            "PositionUsageAccess": (
                f"{primary['PositionDataStreamUsage']}/"
                f"{primary['PositionDataStreamAccess']}"
            ),
            "PrimaryTopology": str(primary["PrimaryTopology"]),
            "SiblingTopology": str(sibling["PrimaryTopology"]),
            "UniqueVertexCounts": _get_position_source_sibling_unique_count(
                pair_rows_sorted, "VertexCount"
            ),
            "UniqueMeshSizes": _get_position_source_sibling_unique_count(
                pair_rows_sorted, "MeshSize"
            ),
            "Decision": (
                "shared position source repeats, but sibling lacks complete "
                "attribute-set binding; candidate-only follow-up"
            ),
        })

    # Sort pair summaries
    pair_summaries.sort(key=lambda ps: str(ps["Pair"]))

    # Determine output directory from first spec
    first_spec = probe_specs[0]
    report_dir = Path(first_spec["Path"]).parent

    json_path = report_dir / "position-source-sibling-probe-report.json"
    md_path = report_dir / "position-source-sibling-probe-report.md"

    summary = {
        "Schema": "position-source-sibling-probe-report/v1",
        "CandidateOnly": True,
        "PairSummaries": pair_summaries,
        "ProbeRows": sorted(
            rows, key=lambda r: (str(r["Pair"]), int(r["MeshBlock"]))
        ),
        "Interpretation": (
            "Candidate-only comparison of parser-derived position-source "
            "sibling leads for shifted-position (meshSize 325/329) and "
            "repeated-position (meshSize 329) families. Shared position "
            "sources are search evidence only; missing sibling attribute "
            "sets keep these below geometry/export truth."
        ),
    }
    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md_lines = [
        "# Position Source Sibling Probe Report",
        "",
        "Candidate-only comparison of parser-derived position-source "
        "sibling leads for shifted-position and repeated-position families.",
        "",
        "Generated under ignored `Exports/`; do not stage generated discovery output.",
        "",
        "| Family | ID | Meshes | Mesh sizes | Vertex counts | "
        "Shared position | Usage/access | Primary topology | Sibling topology | Decision |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for ps_item in pair_summaries:
        md_lines.append(
            f"| {format_markdown_cell(ps_item['PairLabel'])} "
            f"| {format_markdown_cell(ps_item['Id'])} "
            f"| {format_markdown_cell(ps_item['MeshBlocks'])} "
            f"| {format_markdown_cell(ps_item['MeshSizes'])} "
            f"| {format_markdown_cell(ps_item['VertexCounts'])} "
            f"| {format_markdown_cell(ps_item['SharedPositionBlock'])} "
            f"| {format_markdown_cell(ps_item['PositionUsageAccess'])} "
            f"| {format_markdown_cell(ps_item['PrimaryTopology'])} "
            f"| {format_markdown_cell(ps_item['SiblingTopology'])} "
            f"| {format_markdown_cell(ps_item['Decision'])} |"
        )
    md_lines += [
        "",
        "Interpretation: these probes support source-binding search priorities only. "
        "Mesh siblings repeat the same position stream, but the sibling mesh "
        "lacks a full position+normal+UV attribute-set binding, so no role, "
        "topology, geometry, or OBJ/export truth is promoted.",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print("\n--- PositionSourceSiblingProbeReport candidate-only sibling probes")
    print(
        f"{'PairLabel':<45} {'Id':<18} {'MeshBlocks':<22} "
        f"{'MeshSizes':<12} {'SharedPosition'}"
    )
    print("-" * 140)
    for ps_item in pair_summaries:
        print(
            f"{str(ps_item['PairLabel']):<45} {str(ps_item['Id']):<18} "
            f"{str(ps_item['MeshBlocks']):<22} {str(ps_item['MeshSizes']):<12} "
            f"{ps_item['SharedPositionBlock']}"
        )
    print(f"PositionSourceSiblingProbeReport JSON: {json_path}")
    print(f"PositionSourceSiblingProbeReport markdown: {md_path}")
    print(
        "PositionSourceSiblingProbeReport passed: sibling source leads "
        "stayed candidate-only."
    )

# ============================================================================
# PositionSourceSiblingRepresentativeProbeReport
# ============================================================================


def position_source_sibling_representative_probe_report(probe_specs):
    """Build representative sibling probe comparison for meshSize 305/321/329.

    Loads probe JSON for each spec, groups by Pair, validates shared
    position streams, checks sibling lacks attribute-set binding, and
    writes JSON + MD reports.

    Mirrors: Invoke-PositionSourceSiblingRepresentativeProbeReport
    """
    import json
    from pathlib import Path

    rows = [
        _new_position_source_representative_probe_row(spec)
        for spec in probe_specs
    ]

    # Group by Pair
    pair_groups = {}
    for row in rows:
        pair_key = str(row["Pair"])
        pair_groups.setdefault(pair_key, []).append(row)

    pair_summaries = []
    for pair_key, pair_rows in sorted(pair_groups.items()):
        pair_rows_sorted = sorted(
            pair_rows, key=lambda r: int(r["MeshBlock"])
        )
        if len(pair_rows_sorted) != 2:
            raise ValueError(
                f"PositionSourceSiblingRepresentativeProbeReport failed: "
                f"pair '{pair_key}' expected exactly two probes, "
                f"found {len(pair_rows_sorted)}."
            )

        left = pair_rows_sorted[0]
        right = pair_rows_sorted[1]

        # Find shared position streams
        left_pos = left.get("PositionStreams") or []
        right_pos = right.get("PositionStreams") or []
        shared_positions = []
        for lp in left_pos:
            for rp in right_pos:
                if isinstance(lp, dict) and isinstance(rp, dict):
                    if int(lp.get("TargetBlockIndex", -1)) == int(rp.get("TargetBlockIndex", -1)) and int(lp.get("Payload", -1)) == int(rp.get("Payload", -1)):
                        shared_positions.append({
                            "TargetBlockIndex": int(lp["TargetBlockIndex"]),
                            "Payload": int(lp["Payload"]),
                            "MeshPayloadOffsets": [
                                int(lp["MeshPayloadOffset"]),
                                int(rp["MeshPayloadOffset"]),
                            ],
                        })

        if not shared_positions:
            raise ValueError(
                f"PositionSourceSiblingRepresentativeProbeReport failed: "
                f"pair '{pair_key}' has no shared position stream block/payload."
            )

        if int(left["AttributeSetCount"]) < 1:
            raise ValueError(
                f"PositionSourceSiblingRepresentativeProbeReport failed: "
                f"pair '{pair_key}' primary mesh no longer has a complete "
                f"attribute set."
            )

        if int(right["AttributeSetCount"]) != 0:
            raise ValueError(
                f"PositionSourceSiblingRepresentativeProbeReport failed: "
                f"pair '{pair_key}' sibling mesh unexpectedly gained a "
                f"complete attribute set; review before keeping the old "
                f"interpretation."
            )

        def _shared_pos_summary(sp):
            offsets = sp.get("MeshPayloadOffsets")
            if isinstance(offsets, list):
                offset_str = "/".join(f"@{int(o)}" for o in offsets)
            else:
                offset_str = "?"
            return f"block#{sp['TargetBlockIndex']} payload={sp['Payload']} offsets={offset_str}"

        shared_pos_str = " | ".join(
            _shared_pos_summary(sp) for sp in shared_positions
        )

        def _cast_streams(raw):
            if isinstance(raw, list):
                return [s for s in raw if isinstance(s, dict)]
            return []

        left_pos_streams = left.get("PositionStreams") or []
        left_norm_streams = left.get("NormalStreams") or []
        left_uv_streams = left.get("UvStreams") or []
        left_side_streams = left.get("SideStreams") or []
        right_pos_streams = right.get("PositionStreams") or []
        right_norm_streams = right.get("NormalStreams") or []
        right_uv_streams = right.get("UvStreams") or []
        right_side_streams = right.get("SideStreams") or []

        primary_summary = (
            f"mesh#{left['MeshBlock']} attr={left['AttributeSummary']}; "
            f"pos={_format_position_source_stream_list(_cast_streams(left_pos_streams))}; "
            f"normal={_format_position_source_stream_list(_cast_streams(left_norm_streams))}; "
            f"uv={_format_position_source_stream_list(_cast_streams(left_uv_streams))}; "
            f"side={_format_position_source_stream_list(_cast_streams(left_side_streams))}"
        )
        sibling_summary = (
            f"mesh#{right['MeshBlock']} attr={right['AttributeSummary']}; "
            f"pos={_format_position_source_stream_list(_cast_streams(right_pos_streams))}; "
            f"normal={_format_position_source_stream_list(_cast_streams(right_norm_streams))}; "
            f"uv={_format_position_source_stream_list(_cast_streams(right_uv_streams))}; "
            f"side={_format_position_source_stream_list(_cast_streams(right_side_streams))}"
        )

        pair_summaries.append({
            "Pair": pair_key,
            "PairLabel": str(left["PairLabel"]),
            "Id": str(left["Id"]),
            "MeshBlocks": f"mesh#{left['MeshBlock']}, mesh#{right['MeshBlock']}",
            "MeshSizes": f"{left['MeshSize']}, {right['MeshSize']}",
            "SharedPositionStreams": shared_pos_str,
            "PrimaryMeshSummary": primary_summary,
            "SiblingMeshSummary": sibling_summary,
            "Decision": (
                "shared position source repeats, but sibling lacks complete "
                "attribute-set binding; candidate-only follow-up"
            ),
        })

    pair_summaries.sort(key=lambda ps: str(ps["Pair"]))

    first_spec = probe_specs[0]
    report_dir = Path(first_spec["Path"]).parent

    json_path = report_dir / "position-source-sibling-representative-probe-comparison.json"
    md_path = report_dir / "position-source-sibling-representative-probe-comparison.md"

    summary = {
        "Schema": "position-source-sibling-representative-probe-comparison/v1",
        "CandidateOnly": True,
        "PairSummaries": pair_summaries,
        "ProbeRows": sorted(
            rows, key=lambda r: (str(r["Pair"]), int(r["MeshBlock"]))
        ),
        "Interpretation": (
            "Representative parser-derived sibling probes for meshSize "
            "305/321/329. Shared position sources are search evidence only; "
            "missing sibling attribute sets keep these below geometry/export truth."
        ),
    }
    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md_lines = [
        "# Position Source Sibling Representative Probe Comparison",
        "",
        "Candidate-only comparison of representative parser-derived sibling "
        "leads for meshSize `305`, `321`, and `329`.",
        "",
        "Generated under ignored `Exports/`; do not stage generated discovery output.",
        "",
        "| Family | ID | Meshes | Mesh sizes | Shared position | "
        "Primary mesh summary | Sibling mesh summary | Decision |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for ps_item in pair_summaries:
        md_lines.append(
            f"| {format_markdown_cell(ps_item['PairLabel'])} "
            f"| {format_markdown_cell(ps_item['Id'])} "
            f"| {format_markdown_cell(ps_item['MeshBlocks'])} "
            f"| {format_markdown_cell(ps_item['MeshSizes'])} "
            f"| {format_markdown_cell(ps_item['SharedPositionStreams'])} "
            f"| {format_markdown_cell(ps_item['PrimaryMeshSummary'])} "
            f"| {format_markdown_cell(ps_item['SiblingMeshSummary'])} "
            f"| {format_markdown_cell(ps_item['Decision'])} |"
        )
    md_lines += [
        "",
        "Interpretation: these probes support source-binding search priorities only. "
        "Mesh siblings repeat the same position stream, but the sibling mesh "
        "lacks a full position+normal+UV attribute-set binding, so no role, "
        "topology, geometry, or OBJ/export truth is promoted.",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print("\n--- PositionSourceSiblingRepresentativeProbeReport candidate-only "
          "representative sibling probes")
    print(
        f"{'PairLabel':<45} {'Id':<18} {'MeshBlocks':<22} "
        f"{'MeshSizes':<12} {'SharedPosition'} {'Decision'}"
    )
    print("-" * 150)
    for ps_item in pair_summaries:
        print(
            f"{str(ps_item['PairLabel']):<45} {str(ps_item['Id']):<18} "
            f"{str(ps_item['MeshBlocks']):<22} {str(ps_item['MeshSizes']):<12} "
            f"{str(ps_item['SharedPositionStreams'])[:50]}... "
            f"{ps_item['Decision']}"
        )
    print(f"PositionSourceSiblingRepresentativeProbeReport JSON: {json_path}")
    print(f"PositionSourceSiblingRepresentativeProbeReport markdown: {md_path}")
    print(
        "PositionSourceSiblingRepresentativeProbeReport passed: representative "
        "sibling source leads stayed candidate-only."
    )


# ============================================================================
# PositionSourceSiblingSecondaryProbeReport
# ============================================================================


def position_source_sibling_secondary_probe_report(probe_specs):
    """Build secondary sibling probe spot-check for meshSize 305/321/329.

    Loads probe JSON for each spec, groups by Pair, validates shared
    position streams, checks ExpectedAttributeSetCount, and writes
    JSON + MD reports.

    Mirrors: Invoke-PositionSourceSiblingSecondaryProbeReport
    """
    import json
    from pathlib import Path

    rows = [
        _new_position_source_representative_probe_row(spec)
        for spec in probe_specs
    ]

    # Group by Pair
    pair_groups = {}
    for row in rows:
        pair_key = str(row["Pair"])
        pair_groups.setdefault(pair_key, []).append(row)

    pair_summaries = []
    for pair_key, pair_rows in sorted(pair_groups.items()):
        pair_rows_sorted = sorted(
            pair_rows, key=lambda r: int(r["MeshBlock"])
        )
        if len(pair_rows_sorted) != 2:
            raise ValueError(
                f"PositionSourceSiblingSecondaryProbeReport failed: "
                f"pair '{pair_key}' expected exactly two probes, "
                f"found {len(pair_rows_sorted)}."
            )

        left = pair_rows_sorted[0]
        right = pair_rows_sorted[1]

        # Find shared position streams
        left_pos = left.get("PositionStreams") or []
        right_pos = right.get("PositionStreams") or []
        shared_positions = []
        for lp in left_pos:
            for rp in right_pos:
                if isinstance(lp, dict) and isinstance(rp, dict):
                    if int(lp.get("TargetBlockIndex", -1)) == int(rp.get("TargetBlockIndex", -1)) and int(lp.get("Payload", -1)) == int(rp.get("Payload", -1)):
                        shared_positions.append({
                            "TargetBlockIndex": int(lp["TargetBlockIndex"]),
                            "Payload": int(lp["Payload"]),
                            "MeshPayloadOffsets": [
                                int(lp["MeshPayloadOffset"]),
                                int(rp["MeshPayloadOffset"]),
                            ],
                        })

        if not shared_positions:
            raise ValueError(
                f"PositionSourceSiblingSecondaryProbeReport failed: "
                f"pair '{pair_key}' has no shared position stream block/payload."
            )

        # Validate ExpectedAttributeSetCount
        for row in pair_rows_sorted:
            row_id = str(row["Id"])
            row_mesh = int(row["MeshBlock"])
            matching_specs = [
                s for s in probe_specs
                if str(s.get("Pair")) == pair_key
                and str(s.get("Id")) == row_id
                and int(s.get("MeshBlock", -1)) == row_mesh
            ]
            if len(matching_specs) != 1:
                raise ValueError(
                    f"PositionSourceSiblingSecondaryProbeReport failed: "
                    f"expected one spec for {row_id} mesh#{row_mesh}, "
                    f"found {len(matching_specs)}."
                )
            expected = int(matching_specs[0].get("ExpectedAttributeSetCount", -1))
            actual = int(row["AttributeSetCount"])
            if actual != expected:
                raise ValueError(
                    f"PositionSourceSiblingSecondaryProbeReport failed: "
                    f"{row_id} mesh#{row_mesh} expected {expected} complete "
                    f"attribute sets, found {actual}."
                )

        def _shared_pos_summary(sp):
            offsets = sp.get("MeshPayloadOffsets")
            if isinstance(offsets, list):
                offset_str = "/".join(f"@{int(o)}" for o in offsets)
            else:
                offset_str = "?"
            return f"block#{sp['TargetBlockIndex']} payload={sp['Payload']} offsets={offset_str}"

        shared_pos_str = " | ".join(
            _shared_pos_summary(sp) for sp in shared_positions
        )

        def _cast_streams(raw):
            if isinstance(raw, list):
                return [s for s in raw if isinstance(s, dict)]
            return []

        left_pos_streams = left.get("PositionStreams") or []
        left_norm_streams = left.get("NormalStreams") or []
        left_uv_streams = left.get("UvStreams") or []
        left_side_streams = left.get("SideStreams") or []
        right_pos_streams = right.get("PositionStreams") or []
        right_norm_streams = right.get("NormalStreams") or []
        right_uv_streams = right.get("UvStreams") or []
        right_side_streams = right.get("SideStreams") or []

        primary_summary = (
            f"mesh#{left['MeshBlock']} attr={left['AttributeSummary']}; "
            f"pos={_format_position_source_stream_list(_cast_streams(left_pos_streams))}; "
            f"normal={_format_position_source_stream_list(_cast_streams(left_norm_streams))}; "
            f"uv={_format_position_source_stream_list(_cast_streams(left_uv_streams))}; "
            f"side={_format_position_source_stream_list(_cast_streams(left_side_streams))}"
        )
        sibling_summary = (
            f"mesh#{right['MeshBlock']} attr={right['AttributeSummary']}; "
            f"pos={_format_position_source_stream_list(_cast_streams(right_pos_streams))}; "
            f"normal={_format_position_source_stream_list(_cast_streams(right_norm_streams))}; "
            f"uv={_format_position_source_stream_list(_cast_streams(right_uv_streams))}; "
            f"side={_format_position_source_stream_list(_cast_streams(right_side_streams))}"
        )

        attr_set_counts = (
            f"mesh#{left['MeshBlock']}={left['AttributeSetCount']}, "
            f"mesh#{right['MeshBlock']}={right['AttributeSetCount']}"
        )

        pair_summaries.append({
            "Pair": pair_key,
            "PairLabel": str(left["PairLabel"]),
            "Id": str(left["Id"]),
            "MeshBlocks": f"mesh#{left['MeshBlock']}, mesh#{right['MeshBlock']}",
            "MeshSizes": f"{left['MeshSize']}, {right['MeshSize']}",
            "AttributeSetCounts": attr_set_counts,
            "SharedPositionStreams": shared_pos_str,
            "PrimaryMeshSummary": primary_summary,
            "SiblingMeshSummary": sibling_summary,
            "Decision": (
                "secondary sibling spot-check stayed candidate-only; "
                "attribute-set availability is evidence, not geometry truth"
            ),
        })

    pair_summaries.sort(key=lambda ps: str(ps["Pair"]))

    first_spec = probe_specs[0]
    report_dir = Path(first_spec["Path"]).parent

    json_path = report_dir / "position-source-sibling-secondary-probe-comparison.json"
    md_path = report_dir / "position-source-sibling-secondary-probe-comparison.md"

    summary = {
        "Schema": "position-source-sibling-secondary-probe-comparison/v1",
        "CandidateOnly": True,
        "PairSummaries": pair_summaries,
        "ProbeRows": sorted(
            rows, key=lambda r: (str(r["Pair"]), int(r["MeshBlock"]))
        ),
        "Interpretation": (
            "Secondary sibling-family spot checks for meshSize 305/321/329. "
            "Shared position sources remain source-binding search evidence only; "
            "observed attribute-set availability is guarded without promoting "
            "geometry/export truth."
        ),
    }
    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md_lines = [
        "# Position Source Sibling Secondary Probe Comparison",
        "",
        "Candidate-only comparison of secondary parser-derived sibling "
        "leads for meshSize `305`, `321`, and `329`.",
        "",
        "Generated under ignored `Exports/`; do not stage generated discovery output.",
        "",
        "| Family | ID | Meshes | Mesh sizes | Attribute sets | "
        "Shared position | Primary mesh summary | Sibling mesh summary | Decision |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for ps_item in pair_summaries:
        md_lines.append(
            f"| {format_markdown_cell(ps_item['PairLabel'])} "
            f"| {format_markdown_cell(ps_item['Id'])} "
            f"| {format_markdown_cell(ps_item['MeshBlocks'])} "
            f"| {format_markdown_cell(ps_item['MeshSizes'])} "
            f"| {format_markdown_cell(ps_item['AttributeSetCounts'])} "
            f"| {format_markdown_cell(ps_item['SharedPositionStreams'])} "
            f"| {format_markdown_cell(ps_item['PrimaryMeshSummary'])} "
            f"| {format_markdown_cell(ps_item['SiblingMeshSummary'])} "
            f"| {format_markdown_cell(ps_item['Decision'])} |"
        )
    md_lines += [
        "",
        "Interpretation: these secondary probes check whether the representative "
        "sibling pattern repeats. They remain candidate-only because shared "
        "position streams do not by themselves prove complete position+normal+UV "
        "binding, topology truth, geometry truth, or OBJ/export readiness.",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print("\n--- PositionSourceSiblingSecondaryProbeReport candidate-only "
          "secondary sibling probes")
    print(
        f"{'PairLabel':<45} {'Id':<18} {'MeshBlocks':<22} "
        f"{'MeshSizes':<12} {'AttrSets':<18} {'SharedPosition'} {'Decision'}"
    )
    print("-" * 160)
    for ps_item in pair_summaries:
        print(
            f"{str(ps_item['PairLabel']):<45} {str(ps_item['Id']):<18} "
            f"{str(ps_item['MeshBlocks']):<22} {str(ps_item['MeshSizes']):<12} "
            f"{str(ps_item['AttributeSetCounts']):<18} "
            f"{str(ps_item['SharedPositionStreams'])[:40]}... "
            f"{ps_item['Decision']}"
        )
    print(f"PositionSourceSiblingSecondaryProbeReport JSON: {json_path}")
    print(f"PositionSourceSiblingSecondaryProbeReport markdown: {md_path}")
    print(
        "PositionSourceSiblingSecondaryProbeReport passed: secondary sibling "
        "source leads stayed candidate-only."
    )


# ============================================================================
# PositionSourceSiblingExtraPositionReport
# ============================================================================


def position_source_sibling_extra_position_report(probe_specs):
    """Build meshSize=329 mesh#34 extra position stream report.

    Loads probe JSON for each spec, checks mesh#7/mesh#34 pairing,
    validates extra @304/#57 position stream on mesh#34, and writes
    JSON + MD reports.

    Mirrors: Invoke-PositionSourceSiblingExtraPositionReport
    """
    import json
    from pathlib import Path

    rows = [
        _new_position_source_representative_probe_row(spec)
        for spec in probe_specs
    ]

    # Group by Pair
    pair_groups = {}
    for row in rows:
        pair_key = str(row["Pair"])
        pair_groups.setdefault(pair_key, []).append(row)

    pair_summaries = []
    for pair_key, pair_rows in sorted(pair_groups.items()):
        pair_rows_sorted = sorted(
            pair_rows, key=lambda r: int(r["MeshBlock"])
        )
        if len(pair_rows_sorted) != 2:
            raise ValueError(
                f"PositionSourceSiblingExtraPositionReport failed: "
                f"pair '{pair_key}' expected exactly two probes, "
                f"found {len(pair_rows_sorted)}."
            )

        primary_list = [r for r in pair_rows_sorted if int(r["MeshBlock"]) == 7]
        sibling_list = [r for r in pair_rows_sorted if int(r["MeshBlock"]) == 34]
        if len(primary_list) != 1 or len(sibling_list) != 1:
            raise ValueError(
                f"PositionSourceSiblingExtraPositionReport failed: "
                f"pair '{pair_key}' expected mesh#7 and mesh#34 rows."
            )

        primary = primary_list[0]
        sibling = sibling_list[0]

        if int(primary["AttributeSetCount"]) != 1:
            raise ValueError(
                f"PositionSourceSiblingExtraPositionReport failed: "
                f"{primary['Id']} mesh#7 expected one complete attribute set, "
                f"found {primary['AttributeSetCount']}."
            )

        if int(sibling["AttributeSetCount"]) != 0:
            raise ValueError(
                f"PositionSourceSiblingExtraPositionReport failed: "
                f"{sibling['Id']} mesh#34 unexpectedly has complete attribute "
                f"sets; review before keeping the old interpretation."
            )

        # Find shared primary position (block#28)
        primary_pos = primary.get("PositionStreams") or []
        sibling_pos = sibling.get("PositionStreams") or []
        shared_primary = []
        for lp in primary_pos:
            for rp in sibling_pos:
                if isinstance(lp, dict) and isinstance(rp, dict):
                    if int(lp.get("TargetBlockIndex", -1)) == 28 and int(rp.get("TargetBlockIndex", -1)) == 28 and int(lp.get("Payload", -1)) == int(rp.get("Payload", -1)):
                        shared_primary.append({
                            "TargetBlockIndex": 28,
                            "Payload": int(lp["Payload"]),
                            "MeshPayloadOffsets": [
                                int(lp["MeshPayloadOffset"]),
                                int(rp["MeshPayloadOffset"]),
                            ],
                        })

        if not shared_primary:
            raise ValueError(
                f"PositionSourceSiblingExtraPositionReport failed: "
                f"pair '{pair_key}' no longer shares meshSize=329 primary "
                f"position stream block#28."
            )

        # Find extra position stream on sibling (mesh#34): @304/#57, role=position-float3-ror1-lead
        extra_position_streams = [
            sp for sp in sibling_pos
            if isinstance(sp, dict)
            and int(sp.get("MeshPayloadOffset", -1)) == 304
            and int(sp.get("TargetBlockIndex", -1)) == 57
            and str(sp.get("Role", "")) == "position-float3-ror1-lead"
        ]
        if len(extra_position_streams) != 1:
            raise ValueError(
                f"PositionSourceSiblingExtraPositionReport failed: "
                f"{sibling['Id']} mesh#34 expected one extra position-like "
                f"stream at @304/#57, found {len(extra_position_streams)}."
            )

        # Check sibling has no UV streams
        sibling_uv = sibling.get("UvStreams") or []
        uv_count = len(sibling_uv) if isinstance(sibling_uv, list) else 0
        if uv_count != 0:
            raise ValueError(
                f"PositionSourceSiblingExtraPositionReport failed: "
                f"{sibling['Id']} mesh#34 unexpectedly has UV stream "
                f"candidates; review source-binding interpretation."
            )

        def _shared_pos_summary(sp):
            offsets = sp.get("MeshPayloadOffsets")
            if isinstance(offsets, list):
                offset_str = "/".join(f"@{int(o)}" for o in offsets)
            else:
                offset_str = "?"
            return f"block#{sp['TargetBlockIndex']} payload={sp['Payload']} offsets={offset_str}"

        shared_primary_str = " | ".join(
            _shared_pos_summary(sp) for sp in shared_primary
        )

        extra_pos_item = extra_position_streams[0]
        mesh34_extra_str = (
            f"@{extra_pos_item.get('MeshPayloadOffset')}/"
            f"#{extra_pos_item.get('TargetBlockIndex')} "
            f"payload={extra_pos_item.get('Payload')} "
            f"{extra_pos_item.get('Role')}"
        )

        def _cast_streams(raw):
            if isinstance(raw, list):
                return [s for s in raw if isinstance(s, dict)]
            return []

        primary_pos_streams = primary.get("PositionStreams") or []
        primary_norm_streams = primary.get("NormalStreams") or []
        primary_uv_streams = primary.get("UvStreams") or []
        primary_side_streams = primary.get("SideStreams") or []
        sibling_pos_streams = sibling.get("PositionStreams") or []
        sibling_norm_streams = sibling.get("NormalStreams") or []
        sibling_uv_streams = sibling.get("UvStreams") or []
        sibling_side_streams = sibling.get("SideStreams") or []

        mesh7_summary = (
            f"mesh#7 attr={primary['AttributeSummary']}; "
            f"pos={_format_position_source_stream_list(_cast_streams(primary_pos_streams))}; "
            f"normal={_format_position_source_stream_list(_cast_streams(primary_norm_streams))}; "
            f"uv={_format_position_source_stream_list(_cast_streams(primary_uv_streams))}; "
            f"side={_format_position_source_stream_list(_cast_streams(primary_side_streams))}"
        )
        mesh34_summary = (
            f"mesh#34 attr={sibling['AttributeSummary']}; "
            f"pos={_format_position_source_stream_list(_cast_streams(sibling_pos_streams))}; "
            f"normal={_format_position_source_stream_list(_cast_streams(sibling_norm_streams))}; "
            f"uv={_format_position_source_stream_list(_cast_streams(sibling_uv_streams))}; "
            f"side={_format_position_source_stream_list(_cast_streams(sibling_side_streams))}"
        )

        pair_summaries.append({
            "Pair": pair_key,
            "PairLabel": str(primary["PairLabel"]),
            "Id": str(primary["Id"]),
            "SharedPrimaryPosition": shared_primary_str,
            "Mesh34ExtraPosition": mesh34_extra_str,
            "Mesh7Summary": mesh7_summary,
            "Mesh34Summary": mesh34_summary,
            "Decision": (
                "mesh#34 extra @304/#57 position-like stream repeats; "
                "candidate-only source-binding oddity, not geometry truth"
            ),
        })

    pair_summaries.sort(key=lambda ps: str(ps["Pair"]))

    first_spec = probe_specs[0]
    report_dir = Path(first_spec["Path"]).parent

    json_path = report_dir / "position-source-sibling-extra-position-report.json"
    md_path = report_dir / "position-source-sibling-extra-position-report.md"

    summary = {
        "Schema": "position-source-sibling-extra-position-report/v1",
        "CandidateOnly": True,
        "PairSummaries": pair_summaries,
        "ProbeRows": sorted(
            rows, key=lambda r: (str(r["Pair"]), int(r["MeshBlock"]))
        ),
        "Interpretation": (
            "Focused meshSize=329 mesh#7/#34 report for the repeated mesh#34 "
            "@304/#57 position-like stream. This is source-binding search "
            "evidence only and does not promote geometry/export truth."
        ),
    }
    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md_lines = [
        "# Position Source Sibling Extra Position Report",
        "",
        "Candidate-only meshSize `329` mesh `#7/#34` report for repeated sibling "
        "mesh `#34` extra position-like stream `@304/#57`.",
        "",
        "Generated under ignored `Exports/`; do not stage generated discovery output.",
        "",
        "| ID | Shared primary position | mesh#34 extra position | "
        "mesh#7 summary | mesh#34 summary | Decision |",
        "|---|---|---|---|---|---|",
    ]
    for ps_item in pair_summaries:
        md_lines.append(
            f"| {format_markdown_cell(ps_item['Id'])} "
            f"| {format_markdown_cell(ps_item['SharedPrimaryPosition'])} "
            f"| {format_markdown_cell(ps_item['Mesh34ExtraPosition'])} "
            f"| {format_markdown_cell(ps_item['Mesh7Summary'])} "
            f"| {format_markdown_cell(ps_item['Mesh34Summary'])} "
            f"| {format_markdown_cell(ps_item['Decision'])} |"
        )
    md_lines += [
        "",
        "Interpretation: the repeated `@304/#57` stream is a useful source-binding "
        "clue for meshSize `329`, but mesh `#34` still lacks complete attribute-set "
        "binding. Keep this separate from residual-stream truth and do not use it "
        "for OBJ/export promotion.",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print("\n--- PositionSourceSiblingExtraPositionReport candidate-only "
          "mesh#34 extra position stream")
    print(
        f"{'Id':<18} {'SharedPrimaryPosition':<50} "
        f"{'Mesh34Extra':<50} {'Decision'}"
    )
    print("-" * 150)
    for ps_item in pair_summaries:
        print(
            f"{str(ps_item['Id']):<18} "
            f"{str(ps_item['SharedPrimaryPosition']):<50} "
            f"{str(ps_item['Mesh34ExtraPosition']):<50} "
            f"{ps_item['Decision']}"
        )
    print(f"PositionSourceSiblingExtraPositionReport JSON: {json_path}")
    print(f"PositionSourceSiblingExtraPositionReport markdown: {md_path}")
    print(
        "PositionSourceSiblingExtraPositionReport passed: mesh#34 extra "
        "position-like stream stayed candidate-only."
    )

# ============================================================================
# ResidualPositionClusterProbeReport  (focused cluster probes)
# ============================================================================


def _get_hex_byte_array(hex_str: str) -> list[int]:
    """Convert a hex string to a list of integer byte values.

    Mirrors: Get-HexByteArray
    """
    if not hex_str or not hex_str.strip():
        return []
    clean = hex_str.strip()
    if len(clean) % 2 != 0 or not all(c in "0123456789abcdefABCDEF" for c in clean):
        return []
    return [int(clean[i : i + 2], 16) for i in range(0, len(clean), 2)]


def _get_hex_byte_comparison(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, object]:
    """Compare StreamBodyFirst128 hex bytes between a row and its baseline.

    Mirrors: Get-HexByteComparison
    """
    row_bytes = _get_hex_byte_array(str(row.get("StreamBodyFirst128", "")))
    baseline_bytes = _get_hex_byte_array(str(baseline.get("StreamBodyFirst128", "")))
    compared = min(len(row_bytes), len(baseline_bytes))
    prefix = 0
    diff = 0
    for i in range(compared):
        if row_bytes[i] == baseline_bytes[i]:
            if prefix == i:
                prefix += 1
        else:
            diff += 1

    length_delta = int(row.get("StreamByteLength", 0)) - int(baseline.get("StreamByteLength", 0))
    diff_ratio = round(diff / compared, 4) if compared > 0 else None

    stream_class = str(row.get("Classification", ""))
    classifier_plausible = json_double_or_none(row, "ClassifierPlausible")
    packed_review = (
        stream_class == "uint16-compatible-body"
        and classifier_plausible is not None
        and classifier_plausible >= 0.8
        and row.get("ClassifierStrictPass") is False
        and safe_int(row.get("AttributeSetTotal", 0)) == 0
        and safe_int(row.get("PairingTotal", 0)) == 0
    )

    return {
        "Payload": safe_int(row.get("Payload", 0)),
        "BaselinePayload": safe_int(baseline.get("Payload", 0)),
        "BodyFirst16": str(row.get("BodyFirst16", "")),
        "ComparedBytes": compared,
        "CommonPrefixBytes": prefix,
        "DiffBytes": diff,
        "DiffRatio": diff_ratio,
        "StreamByteLength": safe_int(row.get("StreamByteLength", 0)),
        "BaselineStreamByteLength": safe_int(baseline.get("StreamByteLength", 0)),
        "StreamByteLengthDelta": length_delta,
        "PreferredStrides": str(row.get("PreferredStrideSummary", "")),
        "PackedOrQuantizedReview": packed_review,
        "Decision": (
            "packed/quantized-position hypothesis needs parser proof; candidate-only"
            if packed_review
            else "candidate-only byte-layout evidence"
        ),
    }


def _get_optional_cluster_report(
    out_dir: Path, file_name: str, missing_reports: list[str]
) -> dict[str, Any] | None:
    """Load an optional source report, logging missing paths.

    Mirrors: Get-OptionalClusterReport
    """
    path = out_dir / file_name
    if not path.exists():
        print(
            f"ResidualPositionClusterProbeReport note: optional source report "
            f"is missing: {path}",
            file=sys.stderr,
        )
        missing_reports.append(file_name)
        return None
    return load_json_report(str(path))


def _get_cluster_source_report_status(out_dir: Path, file_name: str) -> dict[str, object]:
    """Return status info for an optional source report.

    Mirrors: Get-ClusterSourceReportStatus
    """
    path = out_dir / file_name
    if not path.exists():
        return {
            "FileName": file_name,
            "Path": str(path),
            "Exists": False,
            "LastWriteTimeUtc": None,
            "Note": "missing; enrichment omitted and candidate-only boundary preserved",
        }
    stat = path.stat()
    return {
        "FileName": file_name,
        "Path": str(path),
        "Exists": True,
        "LastWriteTimeUtc": stat.st_mtime,
        "Note": "used for candidate-only enrichment",
    }


def _get_cluster_mesh_row(spec: dict[str, Any], path: str) -> dict[str, object]:
    """Extract a mesh row from a probe JSON for a given spec.

    Mirrors: Get-ClusterMeshRow
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(
            f"ResidualPositionClusterProbeReport failed: mesh probe output missing: {path}"
        )

    report = load_json_report(path)
    meshes = report.get("Meshes") or []
    mesh_entries = [
        m
        for m in meshes
        if isinstance(m, dict)
        and safe_int(m.get("MeshBlockIndex", -1)) == safe_int(spec.get("MeshBlock", -1))
    ]
    if len(mesh_entries) != 1:
        raise ValueError(
            f"ResidualPositionClusterProbeReport failed: expected one "
            f"mesh#{spec.get('MeshBlock')} row in {path}, "
            f"found {len(mesh_entries)}."
        )

    mesh = mesh_entries[0]
    links = mesh.get("Streams") or []
    target_links = [
        ln
        for ln in links
        if isinstance(ln, dict)
        and safe_int(ln.get("MeshPayloadOffset", -1)) == safe_int(spec.get("MeshPayloadOffset", -1))
        and safe_int(ln.get("TargetBlockIndex", -1)) == safe_int(spec.get("StreamBlock", -1))
    ]
    if len(target_links) != 1:
        raise ValueError(
            f"ResidualPositionClusterProbeReport failed: expected one "
            f"stream@{spec.get('MeshPayloadOffset')}->#{spec.get('StreamBlock')} "
            f"row for {spec.get('Id')} mesh#{spec.get('MeshBlock')}, "
            f"found {len(target_links)}."
        )

    link = target_links[0]
    attribute_sets = mesh.get("AttributeSets") or []
    pairings = mesh.get("Pairings") or []
    attribute_set_count = len(attribute_sets) if isinstance(attribute_sets, list) else 0
    pairing_count = len(pairings) if isinstance(pairings, list) else 0

    role_stats = link.get("RoleStats") or {}

    return {
        "Payload": safe_int(spec.get("Payload", 0)),
        "Id": str(spec.get("Id", "")),
        "MeshBlock": safe_int(spec.get("MeshBlock", 0)),
        "MeshSize": safe_int(json_value_or_dash(mesh, "MeshSize")),
        "MeshPayloadOffset": safe_int(json_value_or_dash(link, "MeshPayloadOffset")),
        "TargetBlock": safe_int(json_value_or_dash(link, "TargetBlockIndex")),
        "StreamPayload": safe_int(json_value_or_dash(link, "DeclaredPayloadBytes")),
        "StringValue": str(json_value_or_dash(link, "StringValue")),
        "Role": str(json_value_or_dash(role_stats, "PrimaryRole")),
        "Confidence": safe_int(json_value_or_dash(role_stats, "Confidence")),
        "AttributeSetCount": attribute_set_count,
        "PairingCount": pairing_count,
        "ReviewRequired": (attribute_set_count > 0 or pairing_count > 0),
        "Decision": (
            "review-required; focused evidence changed but remains candidate-only"
            if (attribute_set_count > 0 or pairing_count > 0)
            else "candidate-only; no complete geometry binding"
        ),
        "OutputPath": path,
    }


def _get_cluster_stream_row(spec: dict[str, Any], path: str) -> dict[str, object]:
    """Extract a stream row from a stream-body probe JSON for a given spec.

    Mirrors: Get-ClusterStreamRow
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(
            f"ResidualPositionClusterProbeReport failed: stream-body output missing: {path}"
        )

    report = load_json_report(path)
    stream_bodies = report.get("StreamBodies") or []
    stream_entries = [
        s
        for s in stream_bodies
        if isinstance(s, dict)
        and safe_int(s.get("BlockIndex", -1)) == safe_int(spec.get("StreamBlock", -1))
    ]
    if len(stream_entries) != 1:
        raise ValueError(
            f"ResidualPositionClusterProbeReport failed: expected one stream body "
            f"#{spec.get('StreamBlock')} row in {path}, "
            f"found {len(stream_entries)}."
        )

    stream = stream_entries[0]
    stats = stream.get("Stats") or {}
    preferred_stride_candidates = stream.get("PreferredStrideCandidates") or []
    if preferred_stride_candidates and isinstance(preferred_stride_candidates, list):
        preferred_stride_summary = ",".join(
            f"{json_value_or_dash(sc, 'Stride')}x{json_value_or_dash(sc, 'Count')}"
            for sc in preferred_stride_candidates[:6]
            if isinstance(sc, dict)
        )
    else:
        preferred_stride_summary = "-"

    u16_triples = stream.get("UInt16TriplesPrefix") or []
    u16_triples_count = len(u16_triples)
    u16_triples_summary = "-"
    u16_triples_structure = stream.get("UInt16TriplesStructure")

    if u16_triples_count >= 2 and isinstance(u16_triples, list):
        a_vals = [safe_int(t.get("A", 0)) for t in u16_triples if isinstance(t, dict)]
        b_vals = [safe_int(t.get("B", 0)) for t in u16_triples if isinstance(t, dict)]
        c_vals = [safe_int(t.get("C", 0)) for t in u16_triples if isinstance(t, dict)]
        if a_vals:
            u16_triples_summary = (
                f"A={min(a_vals)}..{max(a_vals)} "
                f"B={min(b_vals)}..{max(b_vals)} "
                f"C={min(c_vals)}..{max(c_vals)}"
            )

    return {
        "Payload": safe_int(spec.get("Payload", 0)),
        "Id": str(spec.get("Id", "")),
        "StreamBlock": safe_int(spec.get("StreamBlock", 0)),
        "DeclaredPayloadBytes": safe_int(json_value_or_dash(stream, "DeclaredPayloadBytes")),
        "Classification": str(json_value_or_dash(stats, "Classification")),
        "BodyFirst16": str(json_value_or_dash(stats, "First16")),
        "BodyFirst128": str(stream.get("BodyFirst128", "")),
        "ByteLength": safe_int(json_value_or_dash(stats, "ByteLength")),
        "PreferredStrideSummary": preferred_stride_summary,
        "UInt16TriplesCount": u16_triples_count,
        "UInt16TriplesSummary": u16_triples_summary,
        "FiniteFloat32Count": safe_int(json_value_or_dash(stats, "FiniteFloat32Count")),
        "PlausibleFloat32Count": safe_int(json_value_or_dash(stats, "PlausibleFloat32Count")),
        "UInt16Distinct": safe_int(json_value_or_dash(stats, "UInt16Distinct")),
        "UInt16TriplesStructureFamily": (
            str(u16_triples_structure.get("StructuralFamily", "-"))
            if isinstance(u16_triples_structure, dict)
            else "-"
        ),
        "UInt16TriplesMagic43606": (
            bool(u16_triples_structure.get("Magic43606Found", False))
            if isinstance(u16_triples_structure, dict)
            else False
        ),
        "UInt16TriplesAlternation": (
            bool(u16_triples_structure.get("AlternationDetected", False))
            if isinstance(u16_triples_structure, dict)
            else False
        ),
        "UInt16TriplesInterpretation": (
            str(u16_triples_structure.get("Interpretation", "-"))
            if isinstance(u16_triples_structure, dict)
            else "-"
        ),
        "OutputPath": path,
    }


def residual_position_cluster_probe_report(
    probe_specs: list[dict[str, Any]],
    out_dir: str | Path,
    project: str | Path,
    root: str | Path,
) -> None:
    """Focused residual cluster probe report for meshSize=305 stream@188.

    For each probe spec:
      1. Runs probe-nif-stream-body to get stream body data
      2. Runs probe-nif-mesh for mesh#7 and mesh#27 to get mesh data
    Then combines with optional source reports (classifier, family cross-tab,
    sibling family) to build candidate-only payload rows, byte-layout
    comparisons, and attribute-binding search rows.

    Guards:
      - No row claims export readiness or promoted geometry truth
      - Payload 288 baseline row must be present

    Generates residual-position-cluster-probe-report.json and .md.

    Mirrors: Invoke-ResidualPositionClusterProbeReport
    """
    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)
    project_path = Path(project)
    root_path = Path(root)

    missing_source_reports: list[str] = []

    # --- Load optional source reports ---

    classifier_report = _get_optional_cluster_report(
        out_dir_path, "residual-position-classifier-report.json", missing_source_reports
    )
    family_cross_tab_report = _get_optional_cluster_report(
        out_dir_path, "residual-position-family-crosstab.json", missing_source_reports
    )
    sibling_family_report = _get_optional_cluster_report(
        out_dir_path, "position-source-sibling-family-report.json", missing_source_reports
    )

    source_report_statuses = [
        _get_cluster_source_report_status(
            out_dir_path, "residual-position-classifier-report.json"
        ),
        _get_cluster_source_report_status(
            out_dir_path, "residual-position-family-crosstab.json"
        ),
        _get_cluster_source_report_status(
            out_dir_path, "position-source-sibling-family-report.json"
        ),
    ]

    classifier_rows: list[dict[str, Any]] = []
    if classifier_report and isinstance(classifier_report, dict):
        classifier_rows_raw = classifier_report.get("Rows")
        if isinstance(classifier_rows_raw, list):
            classifier_rows = classifier_rows_raw

    family_payload_rows: list[dict[str, Any]] = []
    if family_cross_tab_report and isinstance(family_cross_tab_report, dict):
        family_payload_rows_raw = family_cross_tab_report.get("PayloadSummary")
        if isinstance(family_payload_rows_raw, list):
            family_payload_rows = family_payload_rows_raw

    sibling_families: list[dict[str, Any]] = []
    if sibling_family_report and isinstance(sibling_family_report, dict):
        sibling_families_raw = sibling_family_report.get("Families")
        if isinstance(sibling_families_raw, list):
            sibling_families = sibling_families_raw

    # Find mesh305 sibling family
    mesh305_sibling_family = None
    for sf in sibling_families:
        if (
            isinstance(sf, dict)
            and safe_int(sf.get("MeshSize", 0)) == 305
            and str(sf.get("MeshBlocks", "")) == "mesh#7, mesh#27"
            and str(sf.get("MeshPayloadOffsets", "")) == "stream@188"
        ):
            mesh305_sibling_family = sf
            break

    # --- Run probes and build stream/mesh rows ---

    stream_rows: list[dict[str, object]] = []
    mesh_rows: list[dict[str, object]] = []

    sorted_specs = sorted(probe_specs, key=lambda s: safe_int(s.get("Payload", 0)))

    for spec in sorted_specs:
        payload = safe_int(spec.get("Payload", 0))
        spec_id = str(spec.get("Id", ""))
        stream_block = safe_int(spec.get("StreamBlock", 0))

        # Stream body probe
        stream_path = (
            out_dir_path
            / f"probe-residual-position-payload{payload}-{spec_id}-stream{stream_block}.json"
        )
        stream_args = [
            "run",
            "--project",
            str(project_path),
            "--",
            "probe-nif-stream-body",
            "--root",
            str(root_path),
            "--id",
            spec_id,
            "--stream-block",
            str(stream_block),
            "--out",
            str(stream_path),
        ]
        checked_run(
            f"ResidualPositionClusterProbeReport payload {payload} stream body",
            stream_args,
        )
        stream_rows.append(_get_cluster_stream_row(spec, str(stream_path)))

        # Mesh probes for mesh#7 and mesh#27
        for mesh_block in (7, 27):
            mesh_path = (
                out_dir_path / f"probe-nif-mesh-{spec_id}-mesh{mesh_block}.json"
            )
            mesh_args = [
                "run",
                "--project",
                str(project_path),
                "--",
                "probe-nif-mesh",
                "--root",
                str(root_path),
                "--id",
                spec_id,
                "--mesh-block",
                str(mesh_block),
                "--out",
                str(mesh_path),
            ]
            checked_run(
                f"ResidualPositionClusterProbeReport payload {payload} mesh#{mesh_block}",
                mesh_args,
            )
            mesh_spec = {
                "Payload": payload,
                "Id": spec_id,
                "MeshBlock": mesh_block,
                "MeshPayloadOffset": safe_int(spec.get("MeshPayloadOffset", 0)),
                "StreamBlock": stream_block,
            }
            mesh_rows.append(_get_cluster_mesh_row(mesh_spec, str(mesh_path)))

    # --- Build payload rows ---

    from itertools import groupby

    payload_rows: list[dict[str, object]] = []
    sorted_mesh_rows = sorted(mesh_rows, key=lambda r: safe_int(r.get("Payload", 0)))

    for payload_val, group_items_iter in groupby(
        sorted_mesh_rows, key=lambda r: safe_int(r.get("Payload", 0))
    ):
        items = list(group_items_iter)
        first = items[0]

        # Find matching stream row
        stream_matches = [
            sr for sr in stream_rows if safe_int(sr.get("Payload", 0)) == payload_val
        ]
        stream = stream_matches[0] if stream_matches else {}

        # Find matching classifier and family rows
        classifier_match = [
            cr
            for cr in classifier_rows
            if isinstance(cr, dict)
            and safe_int(cr.get("Payload", 0)) == payload_val
        ]
        classifier = classifier_match[0] if classifier_match else None

        family_match = [
            fr
            for fr in family_payload_rows
            if isinstance(fr, dict)
            and safe_int(fr.get("Payload", 0)) == payload_val
        ]
        family = family_match[0] if family_match else None

        strict_pass = (
            bool(json_value_or_dash(classifier, "StrictPass"))
            if classifier
            else None
        )
        candidate_guard = (
            bool(json_value_or_dash(family, "CandidateGuard"))
            if family
            else None
        )

        classifier_plausible = (
            json_double_or_none(classifier, "Plausible") if classifier else None
        )
        classifier_max_threshold = (
            json_double_or_none(classifier, "MaxPlausibleThresholdForSample")
            if classifier
            else None
        )
        classifier_miss_reasons = (
            str(json_value_or_dash(classifier, "MissReasons"))
            if classifier
            else "-"
        )

        mesh_blocks_list = ",".join(
            sorted(
                f"mesh#{safe_int(m.get('MeshBlock', 0))}" for m in items
            )
        )
        mesh_roles_list = "; ".join(
            sorted(
                f"mesh#{safe_int(m.get('MeshBlock', 0))}={m.get('Role', '-')}"
                for m in items
            )
        )
        attribute_set_total = sum(
            safe_int(m.get("AttributeSetCount", 0)) for m in items
        )
        pairing_total = sum(safe_int(m.get("PairingCount", 0)) for m in items)
        review_required = any(
            m.get("ReviewRequired", False) for m in items
        )

        sibling_family_evidence = (
            safe_int(mesh305_sibling_family.get("EvidenceGroups", 0))
            if mesh305_sibling_family
            else 0
        )
        sibling_family_links = (
            safe_int(mesh305_sibling_family.get("TotalStreamLinks", 0))
            if mesh305_sibling_family
            else 0
        )
        sibling_family_ids = (
            safe_int(mesh305_sibling_family.get("DistinctIds", 0))
            if mesh305_sibling_family
            else 0
        )
        sibling_family_targets = (
            str(mesh305_sibling_family.get("TargetBlocks", "-"))
            if mesh305_sibling_family
            else "-"
        )

        payload_rows.append({
            "Payload": payload_val,
            "Id": str(first.get("Id", "")),
            "StreamBlock": safe_int(stream.get("StreamBlock", 0)),
            "StreamClassification": str(stream.get("Classification", "")),
            "BodyFirst16": str(stream.get("BodyFirst16", "")),
            "StreamBodyFirst128": str(stream.get("BodyFirst128", "")),
            "StreamByteLength": safe_int(stream.get("ByteLength", 0)),
            "PreferredStrideSummary": str(
                stream.get("PreferredStrideSummary", "")
            ),
            "UInt16TriplesCount": safe_int(
                stream.get("UInt16TriplesCount", 0)
            ),
            "UInt16TriplesSummary": str(
                stream.get("UInt16TriplesSummary", "")
            ),
            "UInt16TriplesAlternation": bool(
                stream.get("UInt16TriplesAlternation", False)
            ),
            "UInt16TriplesMagic43606": bool(
                stream.get("UInt16TriplesMagic43606", False)
            ),
            "UInt16TriplesStructureFamily": str(
                stream.get("UInt16TriplesStructureFamily", "")
            ),
            "UInt16TriplesInterpretation": str(
                stream.get("UInt16TriplesInterpretation", "")
            ),
            "ClassifierPlausible": classifier_plausible,
            "ClassifierStrictPass": strict_pass,
            "ClassifierMissReasons": classifier_miss_reasons,
            "ClassifierMaxPlausibleThresholdForSample": classifier_max_threshold,
            "ResidualFamilySampleCount": (
                safe_int(family.get("SampleCount", 0)) if family else 0
            ),
            "ResidualFamilyIdCount": (
                safe_int(family.get("IdCount", 0)) if family else 0
            ),
            "ResidualFamilyMesh7And27IdCount": (
                safe_int(family.get("Mesh7And27IdCount", 0)) if family else 0
            ),
            "ResidualFamilyCandidateGuard": candidate_guard,
            "SiblingFamilyEvidenceGroups": sibling_family_evidence,
            "SiblingFamilyTotalStreamLinks": sibling_family_links,
            "SiblingFamilyDistinctIds": sibling_family_ids,
            "SiblingFamilyTargetBlocks": sibling_family_targets,
            "MeshBlocks": mesh_blocks_list,
            "MeshRoles": mesh_roles_list,
            "AttributeSetTotal": attribute_set_total,
            "PairingTotal": pairing_total,
            "ReviewRequired": review_required,
            "ExportReady": False,
            "GeometryTruthPromoted": False,
            "Decision": (
                "review-required; keep candidate-only until guards agree"
                if review_required
                else "candidate-only; no complete geometry binding"
            ),
        })

    # --- Guard: no export readiness or promoted truth ---

    review_rows = [r for r in payload_rows if r.get("ReviewRequired")]
    unsafe_promotion_rows = [
        r for r in payload_rows if r.get("ExportReady") or r.get("GeometryTruthPromoted")
    ]
    if unsafe_promotion_rows:
        raise ValueError(
            "ResidualPositionClusterProbeReport failed: cluster rows must never "
            "claim export readiness or promoted geometry truth."
        )

    # --- Guard: payload 288 baseline ---

    baseline_rows = [r for r in payload_rows if safe_int(r.get("Payload", 0)) == 288]
    if len(baseline_rows) != 1:
        raise ValueError(
            "ResidualPositionClusterProbeReport failed: expected payload 288 "
            f"baseline row for byte-layout comparison, found {len(baseline_rows)}."
        )

    # --- Build body comparison rows ---

    sorted_payload_rows = sorted(
        payload_rows, key=lambda r: safe_int(r.get("Payload", 0))
    )
    baseline = baseline_rows[0]
    body_comparison_rows = [
        _get_hex_byte_comparison(row, baseline) for row in sorted_payload_rows
    ]

    # --- Build attribute binding search rows ---

    attribute_binding_search_rows = [
        {
            "Payload": safe_int(r.get("Payload", 0)),
            "MeshBlocks": str(r.get("MeshBlocks", "")),
            "AttributeSetTotal": safe_int(r.get("AttributeSetTotal", 0)),
            "PairingTotal": safe_int(r.get("PairingTotal", 0)),
            "CompleteBindingFound": (
                safe_int(r.get("AttributeSetTotal", 0)) > 0
                and safe_int(r.get("PairingTotal", 0)) > 0
            ),
            "Decision": (
                "review-required; possible complete binding evidence changed"
                if (
                    safe_int(r.get("AttributeSetTotal", 0)) > 0
                    and safe_int(r.get("PairingTotal", 0)) > 0
                )
                else "no complete focused attribute/index binding found"
            ),
        }
        for r in sorted_payload_rows
    ]

    # --- Build UInt16 triples structure summary ---

    u16_structural_families = [
        {
            "Payload": safe_int(r.get("Payload", 0)),
            "Alternation": bool(r.get("UInt16TriplesAlternation", False)),
            "Magic43606": bool(r.get("UInt16TriplesMagic43606", False)),
            "StructuralFamily": str(r.get("UInt16TriplesStructureFamily", "")),
            "Interpretation": str(r.get("UInt16TriplesInterpretation", "")),
        }
        for r in sorted_payload_rows
    ]
    magic_43606_payloads = sorted(
        [
            safe_int(r.get("Payload", 0))
            for r in sorted_payload_rows
            if r.get("UInt16TriplesMagic43606")
        ]
    )
    alternating_payloads = sorted(
        [
            safe_int(r.get("Payload", 0))
            for r in sorted_payload_rows
            if r.get("UInt16TriplesAlternation")
        ]
    )

    # --- Write JSON output ---

    report_json_path = out_dir_path / "residual-position-cluster-probe-report.json"
    report_md_path = out_dir_path / "residual-position-cluster-probe-report.md"

    report_output: dict[str, Any] = {
        "Schema": "residual-position-cluster-probe-report/v1",
        "CandidateOnly": True,
        "Target": "meshSize=305 stream@188 StringValue=POSITION usage=1 access=19",
        "StrictClassifierThresholdUnchanged": True,
        "ExportPromotion": "blocked",
        "ExportReadinessAssertion": "blocked-for-all-rows",
        "SourceReports": {
            "ResidualClassifier": str(
                out_dir_path / "residual-position-classifier-report.json"
            ),
            "ResidualFamilyCrossTab": str(
                out_dir_path / "residual-position-family-crosstab.json"
            ),
            "PositionSourceSiblingFamily": str(
                out_dir_path / "position-source-sibling-family-report.json"
            ),
        },
        "SourceReportStatuses": source_report_statuses,
        "MissingSourceReports": missing_source_reports,
        "BoundaryNotes": [
            "meshSize=305 stream@188 remains candidate-only search evidence",
            "meshSize=329 @304/#57 remains separate source-binding evidence only",
            "strict residual classifier threshold remains 0.95",
            "OBJ/export remains blocked",
        ],
        "Mesh305SiblingFamily": mesh305_sibling_family,
        "PayloadRows": sorted_payload_rows,
        "BodyComparisonRows": body_comparison_rows,
        "FocusedAttributeBindingSearchRows": attribute_binding_search_rows,
        "StreamRows": sorted(
            stream_rows, key=lambda r: safe_int(r.get("Payload", 0))
        ),
        "MeshRows": sorted(
            mesh_rows,
            key=lambda r: (safe_int(r.get("Payload", 0)), safe_int(r.get("MeshBlock", 0))),
        ),
        "UInt16TriplesStructureSummary": {
            "StructuralFamilies": u16_structural_families,
            "Magic43606Payloads": magic_43606_payloads,
            "AlternatingPayloads": alternating_payloads,
            "Interpretation": (
                "UInt16 triples prefix structural analysis is ranking evidence only; "
                "does not promote roles, geometry, or export readiness."
            ),
        },
        "Interpretation": (
            "Focused residual-cluster probe report only. Do not promote parser "
            "roles, geometry truth, or OBJ/export readiness from this report."
        ),
    }
    report_json_path.write_text(
        json.dumps(report_output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # --- Write Markdown output ---

    md_lines: list[str] = [
        "# Residual Position Cluster Probe Report",
        "",
        "Candidate-only focused probe report for "
        "`meshSize=305 stream@188 StringValue=POSITION usage=1 access=19`.",
        "",
        "| Payload | ID | Plausible | Strict pass | Candidate guard | "
        "Residual IDs | Sibling family | Stream body classifier | "
        "Mesh roles | Attribute sets | Pairings | Decision |",
        "|---:|---|---:|---|---|---:|---|---|---|---:|---:|---|",
    ]
    for row in sorted_payload_rows:
        sibling_summary = "-"
        eg = safe_int(row.get("SiblingFamilyEvidenceGroups", 0))
        if eg > 0:
            sibling_summary = (
                f"groups={eg}; "
                f"links={row.get('SiblingFamilyTotalStreamLinks', 0)}; "
                f"ids={row.get('SiblingFamilyDistinctIds', 0)}; "
                f"target={row.get('SiblingFamilyTargetBlocks', '-')}"
            )

        plausible_str = (
            f"{row['ClassifierPlausible']:.4f}"
            if row.get("ClassifierPlausible") is not None
            else "-"
        )

        md_lines.append(
            f"| {format_markdown_cell(row['Payload'])} "
            f"| {format_markdown_cell(row['Id'])} "
            f"| {plausible_str} "
            f"| {format_markdown_cell(row['ClassifierStrictPass'])} "
            f"| {format_markdown_cell(row['ResidualFamilyCandidateGuard'])} "
            f"| {format_markdown_cell(row['ResidualFamilyIdCount'])} "
            f"| {format_markdown_cell(sibling_summary)} "
            f"| {format_markdown_cell(row['StreamClassification'])} "
            f"| {format_markdown_cell(row['MeshRoles'])} "
            f"| {format_markdown_cell(row['AttributeSetTotal'])} "
            f"| {format_markdown_cell(row['PairingTotal'])} "
            f"| {format_markdown_cell(row['Decision'])} |"
        )

    md_lines += [
        "",
        "## Byte-layout comparison against payload 288",
        "",
        "| Payload | Common prefix bytes | Diff bytes / compared | "
        "Length delta | Preferred strides | Packed/quantized review | Decision |",
        "|---:|---:|---:|---:|---|---|---|",
    ]
    for comp_row in body_comparison_rows:
        diff_str = (
            f"{comp_row['DiffBytes']}/{comp_row['ComparedBytes']}"
            if comp_row['ComparedBytes'] > 0
            else "-"
        )
        md_lines.append(
            f"| {format_markdown_cell(comp_row['Payload'])} "
            f"| {format_markdown_cell(comp_row['CommonPrefixBytes'])} "
            f"| {diff_str} "
            f"| {format_markdown_cell(comp_row['StreamByteLengthDelta'])} "
            f"| {format_markdown_cell(comp_row['PreferredStrides'])} "
            f"| {format_markdown_cell(comp_row['PackedOrQuantizedReview'])} "
            f"| {format_markdown_cell(comp_row['Decision'])} |"
        )

    md_lines += [
        "",
        "## UInt16 triples prefix structure",
        "",
        "Even/odd alternation analysis of the first 16 UInt16 triples "
        "in the stream body. Magic constant 43606 (0xAA56) on even-C "
        "indicates the packed-position ternary alternating pattern.",
        "",
        "| Payload | Alternation | Magic 43606 | Structural family | Interpretation |",
        "|---:|---|---|---|---|",
    ]
    for u16fam in u16_structural_families:
        md_lines.append(
            f"| {format_markdown_cell(u16fam['Payload'])} "
            f"| {format_markdown_cell(u16fam['Alternation'])} "
            f"| {format_markdown_cell(u16fam['Magic43606'])} "
            f"| {format_markdown_cell(u16fam['StructuralFamily'])} "
            f"| {format_markdown_cell(u16fam['Interpretation'])} |"
        )

    md_lines += [
        "",
        "## Focused attribute/index binding search",
        "",
        "| Payload | Mesh blocks | Attribute sets | Pairings | "
        "Complete binding found | Decision |",
        "|---:|---|---:|---:|---|---|",
    ]
    for ab_row in attribute_binding_search_rows:
        md_lines.append(
            f"| {format_markdown_cell(ab_row['Payload'])} "
            f"| {format_markdown_cell(ab_row['MeshBlocks'])} "
            f"| {format_markdown_cell(ab_row['AttributeSetTotal'])} "
            f"| {format_markdown_cell(ab_row['PairingTotal'])} "
            f"| {format_markdown_cell(ab_row['CompleteBindingFound'])} "
            f"| {format_markdown_cell(ab_row['Decision'])} |"
        )

    md_lines += [
        "",
        "## Source report freshness",
        "",
        "| Source report | Exists | Last write UTC | Note |",
        "|---|---|---|---|",
    ]
    for src_status in source_report_statuses:
        md_lines.append(
            f"| {format_markdown_cell(src_status['FileName'])} "
            f"| {format_markdown_cell(src_status['Exists'])} "
            f"| {format_markdown_cell(src_status['LastWriteTimeUtc'])} "
            f"| {format_markdown_cell(src_status['Note'])} |"
        )

    md_lines += [
        "",
        "Boundary notes: `meshSize=329 @304/#57` remains separate source-binding "
        "evidence only; strict residual classifier threshold remains `0.95`; "
        "OBJ/export remains blocked.",
        "",
        "Interpretation: this report compares repeated residual payload clusters "
        "against focused mesh#7/mesh#27 probes. It is search evidence only; "
        "strict classifier thresholds and export gates remain unchanged.",
    ]
    report_md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    # --- Console output ---

    print(
        "\n--- ResidualPositionClusterProbeReport candidate-only "
        "residual cluster probes"
    )
    print(
        f"{'Payload':>8} {'Id':<18} {'Plausible':>10} {'Strict':>7} "
        f"{'Guard':>7} {'ResIDs':>6} {'Sibling':<30} {'Attr':>5} "
        f"{'Pairs':>6} {'Decision'}"
    )
    print("-" * 140)
    for row in sorted_payload_rows:
        plausible_str = (
            f"{row['ClassifierPlausible']:.4f}"
            if row.get("ClassifierPlausible") is not None
            else "-"
        )
        sibling_summary_short = "-"
        eg = safe_int(row.get("SiblingFamilyEvidenceGroups", 0))
        if eg > 0:
            sibling_summary_short = f"grp={eg}"
        print(
            f"{row['Payload']:>8} {str(row['Id']):<18} {plausible_str:>10} "
            f"{str(row['ClassifierStrictPass']):>7} "
            f"{str(row['ResidualFamilyCandidateGuard']):>7} "
            f"{row['ResidualFamilyIdCount']:>6} {sibling_summary_short:<30} "
            f"{row['AttributeSetTotal']:>5} {row['PairingTotal']:>6} "
            f"{row['Decision']}"
        )
    print(f"ResidualPositionClusterProbeReport JSON: {report_json_path}")
    print(f"ResidualPositionClusterProbeReport markdown: {report_md_path}")
    if review_rows:
        print(
            f"ResidualPositionClusterProbeReport review-required rows: "
            f"{len(review_rows)}. Candidate-only boundary preserved.",
            file=sys.stderr,
        )
    print(
        "ResidualPositionClusterProbeReport passed: strict thresholds "
        "unchanged and OBJ/export remains blocked."
    )
