"""FT-7.2 LOD Variant Detector — Flythrough Bridge.

Cross-references the export manifest (350 OBJs) with probe-meshsize-lookup (176 mesh-size
mappings) to detect Level-of-Detail variants across three axes:

1. **Same-NIF LOD**: Same asset_id, multiple mesh_blocks, decreasing vertex counts
2. **MeshSize-family LOD**: Same mesh_size, different asset_ids, vertex-count staircases
3. **Descriptor-based LOD**: float32xvec3 (high-detail) vs float32xvec2 (low-detail) siblings

Generates a LOD manifest JSON consumable by RiftFlythrough for Phase 21 LOD/zone work.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_MANIFEST = REPO_ROOT / "Exports" / "export-manifest.json"
PROBE_LOOKUP = REPO_ROOT / "Exports" / "probe-meshsize-lookup.json"
SCENE_GRAPH_MANIFEST = REPO_ROOT / "Assets" / "build" / "flythrough" / "scene-graph-manifest.json"
OUT_DIR = REPO_ROOT / "Assets" / "build" / "flythrough" / "evidence" / "ft7.2"
LOD_MANIFEST_OUT = REPO_ROOT / "Assets" / "build" / "flythrough" / "lod-manifest.json"
LOD_REPORT_OUT = OUT_DIR / "lod-report.json"


def load_export_manifest() -> list[dict[str, Any]]:
    """Load export-manifest.json entries."""
    if not EXPORT_MANIFEST.exists():
        print(f"ERROR: {EXPORT_MANIFEST} not found", file=sys.stderr)
        sys.exit(1)
    with open(EXPORT_MANIFEST, encoding="utf-8") as f:
        em = json.load(f)
    entries = em.get("entries", [])
    print(f"Loaded {len(entries)} entries from export-manifest")
    return entries


def load_probe_lookup() -> dict[str, dict[str, Any]]:
    """Load probe-meshsize-lookup.json, mapping asset_id -> {meshsize, mesh_block, faced, note}."""
    if not PROBE_LOOKUP.exists():
        print(f"WARNING: {PROBE_LOOKUP} not found — skipping mesh-size enrichment")
        return {}
    with open(PROBE_LOOKUP, encoding="utf-8") as f:
        pl = json.load(f)
    entries = pl.get("entries", {})
    print(f"Loaded {len(entries)} entries from probe-meshsize-lookup")
    return entries


def load_scene_graph_manifest() -> dict[str, Any]:
    """Load scene-graph-manifest.json for world.json metadata."""
    if not SCENE_GRAPH_MANIFEST.exists():
        print(f"WARNING: {SCENE_GRAPH_MANIFEST} not found")
        return {}
    with open(SCENE_GRAPH_MANIFEST, encoding="utf-8-sig") as f:
        sgm = json.load(f)
    print(f"Loaded scene-graph-manifest with {len(sgm.get('entries', sgm.get('manifests', {})))} entries")
    return sgm


def enrich_with_meshsize(
    entries: list[dict[str, Any]],
    probe_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Add mesh_size, probe_mesh_block, and probe_note from probe lookup to export entries."""
    enriched: list[dict[str, Any]] = []
    matched = 0
    for e in entries:
        aid = e.get("asset_id", "")
        if aid and aid in probe_lookup:
            pl = probe_lookup[aid]
            e = dict(e)
            e["mesh_size"] = pl.get("meshsize")
            e["probe_mesh_block"] = pl.get("mesh_block")
            e["probe_note"] = pl.get("note", "")
            matched += 1
        else:
            e = dict(e)
            e["mesh_size"] = e.get("mesh_size")  # preserve if already set
            e["probe_mesh_block"] = None
            e["probe_note"] = ""
        enriched.append(e)
    print(f"Mesh-size enriched: {matched}/{len(enriched)} entries (from probe lookup)")
    return enriched


def detect_same_nif_lod(enriched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect LOD chains within the same NIF (same asset_id, different mesh_blocks)."""
    by_aid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in enriched:
        aid = e.get("asset_id", "")
        if aid and len(aid) == 16:
            by_aid[aid].append(e)

    lod_chains: list[dict[str, Any]] = []
    for aid, meshes in by_aid.items():
        if len(meshes) < 2:
            continue
        # Sort by vertex_count descending (high detail first)
        sorted_meshes = sorted(meshes, key=lambda x: x.get("vertex_count", 0), reverse=True)
        vcs = [m.get("vertex_count", 0) for m in sorted_meshes]

        # LOD requires at least 2x reduction in vertex count
        if vcs[0] > max(1, vcs[-1]) * 2:
            chain = {
                "asset_id": aid,
                "lod_type": "same-nif",
                "levels": len(sorted_meshes),
                "entries": [
                    {
                        "mesh_block": m.get("mesh_block"),
                        "vertex_count": m.get("vertex_count"),
                        "face_count": m.get("face_count"),
                        "faced": m.get("faced"),
                        "mesh_size": m.get("mesh_size"),
                        "descriptor": m.get("descriptor"),
                        "lod_level": i,
                    }
                    for i, m in enumerate(sorted_meshes)
                ],
                "vertex_staircase": vcs,
                "reduction_ratio": vcs[0] / max(1, vcs[-1]),
            }
            lod_chains.append(chain)

    print(f"Same-NIF LOD chains: {len(lod_chains)}")
    return lod_chains


def detect_meshsize_family_lod(enriched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect LOD within MeshSize families (same mesh_size, different NIFs, vertex-count staircases)."""
    by_ms: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for e in enriched:
        ms = e.get("mesh_size")
        if ms is not None and ms > 0:
            by_ms[ms].append(e)

    family_lods: list[dict[str, Any]] = []
    for ms, meshes in sorted(by_ms.items()):
        if len(meshes) < 2:
            continue

        vcs = sorted(set(m.get("vertex_count", 0) for m in meshes if m.get("vertex_count", 0) > 0))
        faced_count = sum(1 for m in meshes if m.get("faced"))
        pos_only = len(meshes) - faced_count

        # Score LOD likelihood based on several signals
        signals: list[str] = []
        lod_score = 0.0

        # Signal 1: Multiple distinct vertex counts (staircase)
        if len(vcs) >= 3:
            signals.append(f"{len(vcs)}-step vertex staircase")
            lod_score += 0.4
        elif len(vcs) == 2 and vcs[-1] > vcs[0] * 1.5:
            signals.append("2-step vertex staircase")
            lod_score += 0.3

        # Signal 2: Mix of faced and position-only
        if faced_count > 0 and pos_only > 0:
            ratio = faced_count / max(1, pos_only)
            signals.append(f"mixed faced({faced_count})/pos-only({pos_only}) ratio={ratio:.2f}")
            if 0.1 <= ratio <= 10.0:
                lod_score += 0.3

        # Signal 3: Large family (many entries implies many detail levels)
        if len(meshes) >= 5:
            signals.append(f"large family ({len(meshes)} entries)")
            lod_score += 0.15

        # Signal 4: Multiple distinct face counts
        fcs = sorted(set(m.get("face_count", 0) for m in meshes if m.get("face_count", 0) > 0))
        if len(fcs) >= 3:
            signals.append(f"{len(fcs)}-step face staircase")
            lod_score += 0.15

        if lod_score >= 0.3:  # minimum threshold
            # Build level entries grouped by vertex count
            by_vc: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for m in meshes:
                vc = m.get("vertex_count", 0)
                by_vc[vc].append(m)

            levels = []
            for level_idx, (vc, level_meshes) in enumerate(sorted(by_vc.items(), reverse=True)):
                levels.append(
                    {
                        "vertex_count": vc,
                        "lod_level": level_idx,
                        "count": len(level_meshes),
                        "faced_count": sum(1 for m in level_meshes if m.get("faced")),
                        "asset_ids": list(
                            dict.fromkeys(m.get("asset_id", "") for m in level_meshes if m.get("asset_id", ""))
                        ),
                    }
                )

            family_lods.append(
                {
                    "mesh_size": ms,
                    "lod_type": "meshsize-family",
                    "lod_score": round(lod_score, 3),
                    "signals": signals,
                    "total_meshes": len(meshes),
                    "faced_count": faced_count,
                    "pos_only_count": pos_only,
                    "levels": levels,
                }
            )

    print(f"MeshSize-family LOD groups: {len(family_lods)}")
    return family_lods


def _sibling_key(sp: Any) -> str:
    """Normalize sibling_pair to a hashable string key."""
    if isinstance(sp, dict):
        ms = sp.get("mesh_size", "")
        note = sp.get("note", "")
        return f"ms={ms}|note={note[:40]}"
    return str(sp)


def detect_descriptor_lod(enriched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect LOD via descriptor changes: float32xvec3 (high) vs float32xvec2 (low)."""
    by_sibling: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in enriched:
        sp = e.get("sibling_pair", "")
        if sp:
            key = _sibling_key(sp)
            by_sibling[key].append(e)

    descriptor_lods: list[dict[str, Any]] = []
    for sp_key, meshes in by_sibling.items():
        if len(meshes) < 2:
            continue
        descs = set(m.get("descriptor", "") for m in meshes)
        if (
            len(descs) >= 2
            and "float32xvec3 (position/normal/UV vertex data)" in descs
            and "float32xvec2 (UV coordinates)" in descs
        ):
            # vec3 = higher detail, vec2 = lower detail
            vcs = [m.get("vertex_count", 0) for m in meshes]
            if max(vcs) > min(vcs) * 1.3:
                descriptor_lods.append(
                    {
                        "sibling_pair": sp_key,
                        "lod_type": "descriptor-sibling",
                        "descriptors": list(descs),
                        "vertex_counts": sorted(vcs, reverse=True),
                        "asset_ids": [m.get("asset_id", "") for m in meshes],
                    }
                )

    print(f"Descriptor-based LOD groups: {len(descriptor_lods)}")
    return descriptor_lods


def build_lod_manifest(
    same_nif: list[dict[str, Any]],
    meshsize_families: list[dict[str, Any]],
    descriptor_lods: list[dict[str, Any]],
    enriched: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a LOD manifest JSON consumable by RiftFlythrough."""
    # Build a per-asset LOD mapping
    asset_lod_map: dict[str, dict[str, Any]] = {}

    # From same-NIF chains
    for chain in same_nif:
        aid = chain["asset_id"]
        asset_lod_map[aid] = {
            "lod_type": "same-nif",
            "lod_levels": chain["levels"],
            "vertex_staircase": chain["vertex_staircase"],
            "reduction_ratio": chain["reduction_ratio"],
            "mesh_blocks": [e["mesh_block"] for e in chain["entries"]],
        }

    # From MeshSize families
    for family in meshsize_families:
        ms = family["mesh_size"]
        for level in family["levels"]:
            for aid in level["asset_ids"]:
                if aid and aid not in asset_lod_map:
                    asset_lod_map[aid] = {
                        "lod_type": "meshsize-family",
                        "mesh_size": ms,
                        "lod_level": level["lod_level"],
                        "vertex_count": level["vertex_count"],
                        "faced_count_at_level": level["faced_count"],
                    }

    # Count stats
    stats = {
        "total_exported_objs": len(enriched),
        "unique_asset_ids": len(set(e.get("asset_id", "") for e in enriched if e.get("asset_id"))),
        "with_meshsize": sum(1 for e in enriched if e.get("mesh_size") is not None),
        "unique_meshsizes": len(set(e.get("mesh_size") for e in enriched if e.get("mesh_size") is not None)),
        "same_nif_lod_chains": len(same_nif),
        "meshsize_family_lod_groups": len(meshsize_families),
        "descriptor_lod_groups": len(descriptor_lods),
        "assets_with_lod_info": len(asset_lod_map),
        "same_nif_lod_assets": sum(c["levels"] for c in same_nif),
    }

    return {
        "schema": "lod-manifest-v1",
        "generated": datetime.now(UTC).isoformat(),
        "plan_phase": "FT-7.2",
        "stats": stats,
        "same_nif_lod": same_nif,
        "meshsize_family_lod": [f for f in meshsize_families if f["lod_score"] >= 0.4],
        "meshsize_family_lod_low_confidence": [f for f in meshsize_families if f["lod_score"] < 0.4],
        "descriptor_lod": descriptor_lods,
        "asset_lod_map": asset_lod_map,
    }


def generate_report(lod_manifest: dict[str, Any]) -> str:
    """Generate a human-readable LOD report."""
    stats = lod_manifest["stats"]
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("FT-7.2 LOD Variant Detection Report")
    lines.append("=" * 72)
    lines.append(f"Generated: {lod_manifest['generated']}")
    lines.append(f"Total exported OBJs: {stats['total_exported_objs']}")
    lines.append(f"Unique asset IDs: {stats['unique_asset_ids']}")
    lines.append(f"With MeshSize data: {stats['with_meshsize']}")
    lines.append(f"Unique MeshSizes: {stats['unique_meshsizes']}")
    lines.append("")

    # Same-NIF LOD
    lines.append("-" * 72)
    lines.append(f"SAME-NIF LOD CHAINS: {stats['same_nif_lod_chains']}")
    lines.append("-" * 72)
    for chain in lod_manifest["same_nif_lod"]:
        aid = chain["asset_id"]
        levels = chain["levels"]
        vcs = chain["vertex_staircase"]
        ratio = chain["reduction_ratio"]
        lines.append(f"  {aid}: {levels} LOD levels, {vcs[0]}→{vcs[-1]} verts ({ratio:.0f}x reduction)")
        for e in chain["entries"]:
            lines.append(
                f"    LOD{e['lod_level']}: MB={e['mesh_block']} V={e['vertex_count']} F={e['face_count']} faced={e['faced']}"
            )

    # MeshSize family LOD (high confidence)
    high_conf = lod_manifest["meshsize_family_lod"]
    low_conf = lod_manifest["meshsize_family_lod_low_confidence"]
    lines.append("")
    lines.append("-" * 72)
    lines.append(f"MESHSIZE-FAMILY LOD GROUPS (high confidence, score>=0.4): {len(high_conf)}")
    lines.append("-" * 72)
    for family in high_conf:
        ms = family["mesh_size"]
        score = family["lod_score"]
        signals = "; ".join(family["signals"])
        lines.append(f"  MeshSize={ms}: score={score:.2f} [{signals}]")
        for level in family["levels"]:
            lines.append(
                f"    LOD{level['lod_level']}: V={level['vertex_count']} count={level['count']} faced={level['faced_count']}"
            )

    lines.append("")
    lines.append("-" * 72)
    lines.append(f"MESHSIZE-FAMILY LOD GROUPS (low confidence, score<0.4): {len(low_conf)}")
    lines.append("-" * 72)
    for family in low_conf:
        ms = family["mesh_size"]
        score = family["lod_score"]
        signals = "; ".join(family["signals"])
        lines.append(f"  MeshSize={ms}: score={score:.2f} [{signals}]")

    # Descriptor LOD
    lines.append("")
    lines.append("-" * 72)
    lines.append(f"DESCRIPTOR-BASED LOD GROUPS: {stats['descriptor_lod_groups']}")
    lines.append("-" * 72)
    for dl in lod_manifest["descriptor_lod"]:
        lines.append(f"  sibling_pair={dl['sibling_pair']}: descs={dl['descriptors']} vcs={dl['vertex_counts']}")

    # Summary
    lines.append("")
    lines.append("=" * 72)
    lines.append(f"SUMMARY: {stats['assets_with_lod_info']} assets have LOD info")
    lines.append(
        f"  Same-NIF LOD: {stats['same_nif_lod_assets']} mesh instances across {stats['same_nif_lod_chains']} chains"
    )
    lines.append("  MeshSize-family LOD: {} groups".format(stats["meshsize_family_lod_groups"]))
    lines.append("  Descriptor LOD: {} groups".format(stats["descriptor_lod_groups"]))
    lines.append("=" * 72)

    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("FT-7.2 LOD Variant Detector")
    print("=" * 40)

    # Load data
    entries = load_export_manifest()
    probe_lookup = load_probe_lookup()
    _sgm = load_scene_graph_manifest()

    # Enrich with mesh_size
    enriched = enrich_with_meshsize(entries, probe_lookup)

    # Detect LOD patterns
    same_nif = detect_same_nif_lod(enriched)
    meshsize_families = detect_meshsize_family_lod(enriched)
    descriptor_lods = detect_descriptor_lod(enriched)

    # Build manifest
    lod_manifest = build_lod_manifest(same_nif, meshsize_families, descriptor_lods, enriched)

    # Write outputs
    with open(LOD_MANIFEST_OUT, "w", encoding="utf-8") as f:
        json.dump(lod_manifest, f, indent=2, default=str)
    print(f"LOD manifest written: {LOD_MANIFEST_OUT}")

    report = generate_report(lod_manifest)
    LOD_REPORT_OUT.write_text(report, encoding="utf-8")
    print(f"LOD report written: {LOD_REPORT_OUT}")

    # Print summary
    stats = lod_manifest["stats"]
    print()
    print("Results:")
    print(f"  Same-NIF LOD chains: {stats['same_nif_lod_chains']}")
    print(
        f"  MeshSize-family LOD groups: {stats['meshsize_family_lod_groups']} ({len(lod_manifest['meshsize_family_lod'])} high-confidence)"
    )
    print(f"  Descriptor LOD groups: {stats['descriptor_lod_groups']}")
    print(f"  Assets with LOD info: {stats['assets_with_lod_info']}")


if __name__ == "__main__":
    main()
