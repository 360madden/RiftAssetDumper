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
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.rift_workflow_utils import (  # noqa: E402
    format_markdown_cell,
    format_nif_usage_access,
    format_proof_review_summary,
    format_vector_sample,
    json_array_count_or_dash,
    json_value_or_dash,
    json_value_or_none,
    load_json_report,
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
        f"pairMeshes={json_value_or_dash(report, 'PairCompatibleMeshes')} "
        f"pairLinks={json_value_or_dash(report, 'PairCompatibleLinks')}"
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
            f"invalid={json_value_or_dash(report, 'InvalidStreamBodies')}"
        )
        sizes = report.get("SizeGroups")
        if sizes and isinstance(sizes, list):
            print(
                "Top sizes: "
                + top_text(
                    sizes,
                    lambda g: f"payload={json_value_or_dash(g, 'DeclaredPayloadBytes')} count={json_value_or_dash(g, 'Count')}",
                )
            )
        sigs = report.get("TopSignatures")
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
    except (FileNotFoundError, ValueError) as exc:
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
        key=lambda b: (-b["Count"], b["Bucket"]),
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
