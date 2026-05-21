#!/usr/bin/env python3
"""Position Source Gap Report — Stage 2, Step 16 of the 50-step discovery plan.

Reads nif-mesh-binding-inventory.json and produces a structured gap report
identifying which indexed mesh families have proven normals+UVs but are
missing proven position streams.

Output: position-gap-report.json (under Exports/).

Usage:
    python scripts/rift_position_gap_report.py <inventory-json-path> [--out <output-path>]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ============================================================================
# JSON access helpers
# ============================================================================


def safe_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def safe_int(value: Any, default: int = 0) -> int:
    if value is None or value == "-":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ============================================================================
# Gap analysis
# ============================================================================


def load_inventory(path: str) -> dict[str, Any]:
    """Load and validate the nif-mesh-binding-inventory.json."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Inventory not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Inventory is not a JSON object")
    return data


def classify_attribute_set(
    attr_set: dict[str, Any],
) -> dict[str, Any]:
    """Classify a single attribute-set group as having position, missing position, etc.

    Returns a dict with keys:
      - meshSize, vertexCount, count
      - hasPosition, hasNormal, hasUv
      - positionPayload, normalPayload, uvPayload
      - positionStatus: "proven" | "missing" | "partial"
      - topology, confidence, samples
    """
    mesh_size = safe_int(attr_set.get("MeshSize"))
    vertex_count = safe_int(attr_set.get("VertexCount"))
    count = safe_int(attr_set.get("Count"))
    pos_bytes = safe_get(attr_set, "PositionDeclaredPayloadBytes")
    norm_bytes = safe_get(attr_set, "NormalDeclaredPayloadBytes")
    uv_bytes = safe_get(attr_set, "UvDeclaredPayloadBytes")
    topology = safe_get(attr_set, "Topology", {})
    avg_conf = safe_get(attr_set, "AverageConfidence", 0.0)
    samples = safe_get(attr_set, "Samples", [])

    has_position = pos_bytes is not None
    has_normal = norm_bytes is not None
    has_uv = uv_bytes is not None

    if has_position:
        # Validate expected payload: 12 bytes per float32 * vertexCount
        expected_pos_bytes = vertex_count * 12
        pos_ok = safe_int(pos_bytes) == expected_pos_bytes
        status = "proven" if pos_ok else "partial"
    else:
        status = "missing"

    return {
        "meshSize": mesh_size,
        "vertexCount": vertex_count,
        "count": count,
        "hasPosition": has_position,
        "hasNormal": has_normal,
        "hasUv": has_uv,
        "positionStatus": status,
        "positionDeclaredPayloadBytes": pos_bytes,
        "normalDeclaredPayloadBytes": norm_bytes,
        "uvDeclaredPayloadBytes": uv_bytes,
        "primaryTopology": safe_get(topology, "PrimaryTopology", "-"),
        "triangleListTriangles": safe_get(topology, "TriangleListTriangleCount"),
        "triangleStripTriangles": safe_get(topology, "TriangleStripTriangleCount"),
        "averageConfidence": avg_conf,
        "sampleCount": len(samples) if isinstance(samples, list) else 0,
        "samples": samples[:5] if isinstance(samples, list) else [],
    }


def analyze_gaps(data: dict[str, Any]) -> dict[str, Any]:
    """Main gap analysis entry point."""
    # --- 1. Attribute set analysis ---
    attr_sets_raw = safe_get(data, "TopAttributeSets", [])
    classified = [classify_attribute_set(s) for s in attr_sets_raw]

    # Group by attribute profile (which components are present)
    profile_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in classified:
        if s["hasPosition"] and s["hasNormal"] and s["hasUv"]:
            key = "position+normal+uv"
        elif s["hasNormal"] and s["hasUv"] and not s["hasPosition"]:
            key = "normal+uv (NO position)"
        elif s["hasPosition"] and s["hasUv"] and not s["hasNormal"]:
            key = "position+uv (NO normal)"
        elif s["hasPosition"] and s["hasNormal"] and not s["hasUv"]:
            key = "position+normal (NO uv)"
        elif s["hasPosition"] and not s["hasNormal"] and not s["hasUv"]:
            key = "position ONLY"
        elif not s["hasPosition"] and s["hasNormal"] and not s["hasUv"]:
            key = "normal ONLY"
        elif not s["hasPosition"] and not s["hasNormal"] and s["hasUv"]:
            key = "uv ONLY"
        else:
            key = "other"
        profile_groups[key].append(s)

    # --- 2. Position candidate group analysis ---
    role_groups_raw = safe_get(data, "RoleGroups", [])
    position_role_counts: dict[str, int] = {}
    position_role_mesh_sizes: dict[str, list[dict[str, int]]] = defaultdict(list)
    for rg in role_groups_raw:
        role = safe_get(rg, "Role", "")
        if "position" in role.lower():
            count = safe_int(rg.get("Count"))
            position_role_counts[role] = count
            mesh_sizes_raw = safe_get(rg, "MeshSizes", [])
            for ms in mesh_sizes_raw:
                sz = safe_int(ms.get("Size"))
                cnt = safe_int(ms.get("Count"))
                position_role_mesh_sizes[role].append({"meshSize": sz, "count": cnt})

    # --- 3. Position source sibling analysis ---
    siblings_raw = safe_get(data, "TopPositionSourceSiblings", [])
    sibling_families: list[dict[str, Any]] = []
    for sib in siblings_raw:
        sibling_families.append({
            "pattern": safe_get(sib, "Pattern"),
            "idPrefix": safe_get(sib, "IdPrefix"),
            "targetBlockIndex": safe_get(sib, "TargetBlockIndex"),
            "declaredPayloadBytes": safe_get(sib, "DeclaredPayloadBytes"),
            "usage": safe_get(sib, "DataStreamUsage"),
            "access": safe_get(sib, "DataStreamAccess"),
            "count": safe_int(sib.get("Count")),
            "distinctMeshes": safe_int(sib.get("DistinctMeshBlocks")),
            "meshBlockIndices": safe_get(sib, "MeshBlockIndices", []),
            "meshPayloadOffsets": safe_get(sib, "MeshPayloadOffsets", []),
        })

    # --- 4. Residual target analysis ---
    residual_targets_raw = safe_get(data, "ResidualTargetMeshSizes", [])
    residual_targets: list[dict[str, Any]] = []
    for rt in residual_targets_raw:
        residual_targets.append({
            "meshSize": safe_int(rt.get("MeshSize")),
            "meshBlockCount": safe_int(rt.get("MeshBlockCount")),
            "nifPayloads": safe_int(rt.get("NifPayloads")),
            "residualStreamCount": safe_int(rt.get("ResidualStreamCount")),
            "residualPatternCount": safe_int(rt.get("ResidualPatternCount")),
        })

    # --- 5. Top residual streams (candidate position leads) ---
    residual_streams_raw = safe_get(data, "TopResidualStreams", [])
    residual_streams: list[dict[str, Any]] = []
    for rs in residual_streams_raw:
        residual_streams.append({
            "meshSize": safe_int(rs.get("MeshSize")),
            "pattern": safe_get(rs, "Pattern"),
            "meshPayloadOffset": safe_get(rs, "MeshPayloadOffset"),
            "declaredPayloadBytes": safe_get(rs, "DeclaredPayloadBytes"),
            "usage": safe_get(rs, "DataStreamUsage"),
            "access": safe_get(rs, "DataStreamAccess"),
            "role": safe_get(rs, "Role"),
            "roleConfidence": safe_get(rs, "RoleConfidence"),
            "count": safe_int(rs.get("Count")),
            "ror3VectorCount": safe_get(rs, "RotatedFloat3VectorCount"),
            "ror3FiniteRatio": safe_get(rs, "RotatedFloat3FiniteVectorRatio"),
            "ror3PlausibleRatio": safe_get(rs, "RotatedFloat3PlausibleValueRatio"),
            "ror3MaxExtent": safe_get(rs, "RotatedFloat3MaxExtent"),
            "bodyFirst16": safe_get(rs, "BodyFirst16"),
        })

    # --- 6. Position-source gap analysis: meshes with normals+UVs but no positions ---
    gap_families = sorted(
        [s for s in classified if s["hasNormal"] and s["hasUv"] and not s["hasPosition"]],
        key=lambda s: (-s["count"], s["meshSize"], s["vertexCount"]),
    )

    # --- 7. Position-lead mesh size cross-reference ---
    # For each mesh size that has position leads, list it
    position_lead_mesh_sizes: dict[int, int] = {}
    for _role, sizes in position_role_mesh_sizes.items():
        for entry in sizes:
            sz = entry["meshSize"]
            cnt = entry["count"]
            position_lead_mesh_sizes[sz] = position_lead_mesh_sizes.get(sz, 0) + cnt

    # --- 8. Build the gap summary ---
    all_attribute_mesh_sizes = set(s["meshSize"] for s in classified)
    position_lead_sizes = set(position_lead_mesh_sizes.keys())
    gap_mesh_sizes = set(s["meshSize"] for s in gap_families)
    normal_or_uv_mesh_sizes = set(
        s["meshSize"] for s in classified
        if (s["hasNormal"] or s["hasUv"]) and not s["hasPosition"]
    )

    return {
        "schema": "rift-position-gap-report/v1",
        "generatedAtUtc": datetime.now(UTC).isoformat(),
        "interpretation": (
            "Gap analysis: identifies mesh families with proven normals/UVs "
            "but missing position streams. This is the blocking gap for model export. "
            "Position stream candidates may exist in unlinked NiDataStream blocks, "
            "neighbor-block payload windows, or as UInt16-packed indexed streams."
        ),
        "summary": {
            "totalAttributeSetGroups": len(classified),
            "totalGapFamilies": len(gap_families),
            "meshSizesWithAttributeSets": sorted(all_attribute_mesh_sizes),
            "meshSizesWithPositionLeads": sorted(position_lead_sizes),
            "meshSizesMissingPosition": sorted(gap_mesh_sizes),
            "meshSizesMissingPositionButHaveNormalOrUv": sorted(normal_or_uv_mesh_sizes),
        },
        "profileBreakdown": {
            profile: {
                "count": len(items),
                "meshSizes": sorted(set(s["meshSize"] for s in items)),
                "totalMeshes": sum(s["count"] for s in items),
            }
            for profile, items in sorted(profile_groups.items())
        },
        "gapFamilies": gap_families,
        "positionRoleCounts": position_role_counts,
        "positionRoleMeshSizes": dict(position_role_mesh_sizes),
        "positionSourceSiblings": {
            "totalGroups": len(sibling_families),
            "groups": sibling_families,
        },
        "residualTargets": residual_targets,
        "residualStreams": residual_streams,
        "topResidualByMeshSize": [
            {"meshSize": sz, "streams": sorted(
                [rs for rs in residual_streams if rs["meshSize"] == sz],
                key=lambda x: -x["count"]
            )[:5]}
            for sz in sorted(set(rs["meshSize"] for rs in residual_streams))
        ],
        "recommendations": _generate_recommendations(
            gap_families, position_lead_mesh_sizes, residual_streams, sibling_families
        ),
    }


def _generate_recommendations(
    gap_families: list[dict[str, Any]],
    position_lead_sizes: dict[int, int],
    residual_streams: list[dict[str, Any]],
    sibling_families: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate ranked recommendations for next discovery steps."""
    recs: list[dict[str, Any]] = []

    # Check if there are any gap families at all
    if not gap_families:
        recs.append({
            "priority": "info",
            "action": "No gap families found — all indexed mesh families with normals/UVs also have positions.",
            "rationale": "The position gap may have been closed by a previous round of discovery.",
        })
        return recs

    # Rank gap families by count descending
    top_gaps = gap_families[:5]
    for i, gf in enumerate(top_gaps):
        priority = "high" if i == 0 else "medium"
        mesh_size = gf["meshSize"]
        vertex_count = gf["vertexCount"]
        count = gf["count"]

        # Check if this mesh size already has some position leads elsewhere
        has_other_position_leads = mesh_size in position_lead_sizes
        lead_info = ""
        if has_other_position_leads:
            lead_info = f" (some position leads exist in this mesh-size group: {position_lead_sizes[mesh_size]})"

        # Check if there are residual stream candidates for this mesh size
        matching_residuals = [rs for rs in residual_streams if rs["meshSize"] == mesh_size]
        residual_hint = ""
        if matching_residuals:
            top_r = matching_residuals[0]
            ror3_plausible = top_r.get("ror3PlausibleRatio")
            if ror3_plausible and isinstance(ror3_plausible, (int, float)) and ror3_plausible > 0.5:
                residual_hint = (
                    f" Residual stream @{top_r['meshPayloadOffset']} "
                    f"payload={top_r['declaredPayloadBytes']} "
                    f"has plausible float3 data (ratio={ror3_plausible:.2f})."
                )
            else:
                residual_hint = (
                    f" Residual stream @{top_r['meshPayloadOffset']} "
                    f"payload={top_r['declaredPayloadBytes']} "
                    f"exists but plausibility is low."
                )

        # Check sibling groups for this mesh size
        matching_siblings = [s for s in sibling_families if s["count"] >= 2]
        sibling_hint = ""
        if matching_siblings:
            found_same_size = any(s.get("pattern", "").startswith(str(mesh_size)) for s in matching_siblings)
            if found_same_size:
                sibling_hint = " Position-source sibling groups exist for this size family."

        sample_ids = ", ".join(
            str(s.get("IdPrefix", "?")) for s in (gf.get("samples") or [])[:3]
        )
        recs.append({
            "priority": priority,
            "action": (
                f"meshSize={mesh_size} v={vertex_count} count={count} — "
                f"probe position-less meshes for inline float3 data or orphan stream candidates."
                f"{lead_info}{residual_hint}{sibling_hint}"
            ),
            "sampleIds": sample_ids or "-",
            "rationale": (
                f"Top gap family: {count} meshes with normals+UVs but no position stream. "
                f"Vertex count {vertex_count} suggests expected position payload = {vertex_count * 12} bytes (float32 x3)."
            ),
        })

    # Check residual streams for promising leads
    promising_residuals = [
        rs for rs in residual_streams
        if isinstance(rs.get("ror3PlausibleRatio"), (int, float))
        and rs["ror3PlausibleRatio"] > 0.7
    ]
    if promising_residuals:
        top_r = promising_residuals[0]
        recs.append({
            "priority": "high",
            "action": (
                f"meshSize={top_r['meshSize']} residual stream @{top_r['meshPayloadOffset']} "
                f"payload={top_r['declaredPayloadBytes']} — plausible float3 position candidate "
                f"(ratio={top_r['ror3PlausibleRatio']:.2f}, extent={top_r['ror3MaxExtent']})."
            ),
            "sampleIds": "-",
            "rationale": (
                "Highest plausibility residual stream. This is the most promising "
                "position lead outside the proven attribute-set inventory. "
                "Requires focused mesh probe to confirm geometry role."
            ),
        })

    # Sibling group recommendations
    high_count_siblings = [s for s in sibling_families if s["count"] >= 5]
    if high_count_siblings:
        top_sib = high_count_siblings[0]
        recs.append({
            "priority": "medium",
            "action": (
                f"Pattern '{top_sib['pattern']}' ({top_sib['count']} meshes, "
                f"{top_sib['distinctMeshes']} distinct) — repeated position-source sibling "
                f"at block#{top_sib['targetBlockIndex']} payload={top_sib['declaredPayloadBytes']}."
            ),
            "sampleIds": top_sib.get("idPrefix", "-"),
            "rationale": (
                "Repeated sibling binding across multiple meshes suggests this stream "
                "may contain position data, but needs per-mesh probe validation."
            ),
        })

    if not recs:
        recs.append({
            "priority": "info",
            "action": "No actionable recommendations from current inventory.",
            "rationale": "All positions may already be discovered; run a full inventory to confirm.",
        })

    return recs


# ============================================================================
# Output
# ============================================================================


def write_report(report: dict[str, Any], output_path: str) -> None:
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Position gap report written: {p}")


def print_human_summary(report: dict[str, Any]) -> None:
    """Print a human-readable summary of the gap report."""
    summary = report.get("summary", {})
    profile = report.get("profileBreakdown", {})

    print()
    print("=" * 72)
    print("  POSITION SOURCE GAP REPORT — Stage 2, Step 16")
    print("=" * 72)
    print()

    print(f"  Attribute set groups:           {summary.get('totalAttributeSetGroups', 0)}")
    print(f"  Mesh sizes with attr sets:      {summary.get('meshSizesWithAttributeSets', [])}")
    print(f"  Mesh sizes with position leads: {summary.get('meshSizesWithPositionLeads', [])}")
    print(f"  Gap families (no position):     {summary.get('meshSizesMissingPosition', [])}")
    print()

    # Profile breakdown
    print("  Attribute set profiles:")
    for profile_name, info in sorted(profile.items()):
        print(f"    {profile_name:40s}  count={info['count']:3d}  meshes={info['totalMeshes']:5d}  sizes={info['meshSizes']}")
    print()

    # Gap families (top 10)
    gaps = report.get("gapFamilies", [])
    if gaps:
        print("  Top gap families (normals+UVs proven, positions MISSING):")
        print(f"  {'MeshSize':>8s}  {'VtxCount':>8s}  {'Count':>6s}  {'Topology':>18s}  {'PosPayload':>10s}  {'NormPayload':>10s}  {'UVPayload':>10s}  {'Confidence':>9s}")
        print(f"  {'-'*8}  {'-'*8}  {'-'*6}  {'-'*18}  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*9}")
        for gf in gaps[:15]:
            print(f"  {gf['meshSize']:>8d}  {gf['vertexCount']:>8d}  {gf['count']:>6d}  {gf['primaryTopology']:>18s}  {str(gf['positionDeclaredPayloadBytes'] or '-'):>10s}  {str(gf['normalDeclaredPayloadBytes'] or '-'):>10s}  {str(gf['uvDeclaredPayloadBytes'] or '-'):>10s}  {gf['averageConfidence']:>9.1f}")
        print()

    # Residual streams (position-like candidates)
    residuals = report.get("residualStreams", [])
    if residuals:
        print("  Residual streams (position-like candidates, top 10 by plausibility):")
        sorted_res = sorted(
            [r for r in residuals if r.get("ror3PlausibleRatio") is not None],
            key=lambda r: -r["ror3PlausibleRatio"],
        )
        if sorted_res:
            print(f"  {'MeshSize':>8s}  {'Payload':>8s}  {'Count':>6s}  {'Plausible':>9s}  {'Extent':>8s}  {'Finite':>7s}  {'Role':>24s}")
            print(f"  {'-'*8}  {'-'*8}  {'-'*6}  {'-'*9}  {'-'*8}  {'-'*7}  {'-'*24}")
            for rs in sorted_res[:10]:
                print(f"  {rs['meshSize']:>8d}  {str(rs['declaredPayloadBytes'] or '-'):>8s}  {rs['count']:>6d}  {rs['ror3PlausibleRatio']:>9.3f}  {str(rs['ror3MaxExtent'] or '-'):>8s}  {str(rs['ror3FiniteRatio'] or '-'):>7s}  {str(rs.get('role', '-')):>24s}")
        else:
            print("    (no residual streams have float3 plausibility data)")
        print()

    # Position source siblings
    siblings = report.get("positionSourceSiblings", {})
    sib_groups = siblings.get("groups", [])
    if sib_groups:
        print("  Position source sibling groups (top 10 by count):")
        sorted_sibs = sorted(sib_groups, key=lambda s: -s["count"])
        print(f"  {'Count':>6s}  {'Distinct':>8s}  {'TargetBlock':>11s}  {'Payload':>8s}  {'Usage':>16s}  {'Access':>16s}  {'First offsets'}")
        print(f"  {'-'*6}  {'-'*8}  {'-'*11}  {'-'*8}  {'-'*16}  {'-'*16}  {'-'*20}")
        for sib in sorted_sibs[:10]:
            offsets = ", ".join(str(o) for o in (sib.get("meshPayloadOffsets") or [])[:4])
            print(f"  {sib['count']:>6d}  {sib['distinctMeshes']:>8d}  block#{sib['targetBlockIndex']:>5d}  {str(sib['declaredPayloadBytes'] or '-'):>8s}  {str(sib.get('usage', '-')):>16s}  {str(sib.get('access', '-')):>16s}  {offsets}")
        print()

    # Recommendations
    recs = report.get("recommendations", [])
    if recs:
        print("  Recommendations:")
        for i, rec in enumerate(recs, 1):
            print(f"    {i}. [{rec.get('priority', 'info').upper()}] {rec.get('action', '')}")
            print(f"       Rationale: {rec.get('rationale', '')}")
            if rec.get("sampleIds") and rec["sampleIds"] != "-":
                print(f"       Sample IDs: {rec['sampleIds']}")
            print()

    print("=" * 72)
    print()


# ============================================================================
# CLI
# ============================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Position Source Gap Report — identify mesh families missing position streams.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "inventory",
        help="Path to nif-mesh-binding-inventory.json",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Output path for gap report JSON (default: <inventory-dir>/position-gap-report.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    inventory_path = Path(args.inventory)
    if not inventory_path.exists():
        print(f"ERROR: inventory not found: {inventory_path}", file=sys.stderr)
        return 1

    output_path = Path(args.out) if args.out else (
        inventory_path.parent / "position-gap-report.json"
    )

    try:
        data = load_inventory(str(inventory_path))
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: failed to load inventory: {exc}", file=sys.stderr)
        return 1

    report = analyze_gaps(data)
    write_report(report, str(output_path))
    print_human_summary(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
