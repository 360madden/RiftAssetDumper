"""FT-8 closure — unified flythrough-index.json combining all FT-1..FT-7 artifacts.

This is NOT the FT-8 mod-injection bridge (that's skipped — see rationale below).
Rather, this produces a single consumable index file for RiftFlythrough that combines
all the data produced across FT-1 through FT-7.

FT-8 skip rationale: the mod-replacement bridge involves writing back to TWAD archives,
contradicting the project's read-only mandate. The plan itself marks FT-8 as optional
and safety-gated. Skipping FT-8 and producing this unified index instead is the optimal
high-value delivery for RiftFlythrough.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH = REPO_ROOT / "Assets" / "build" / "flythrough"
EXPORTS = REPO_ROOT / "Exports"

OUTPUT = FLYTHROUGH / "flythrough-index.json"


def load_json(path: Path, encoding: str = "utf-8") -> dict[str, Any]:
    """Load a JSON file, returning {} if missing."""
    if not path.exists():
        return {}
    with open(path, encoding=encoding) as f:
        return json.load(f)


def build_asset_index() -> dict[str, dict[str, Any]]:
    """Build a per-asset-id index from all available data sources."""
    index: dict[str, dict[str, Any]] = {}

    # === Export manifest (primary source) ===
    em = load_json(EXPORTS / "export-manifest.json")
    for e in em.get("entries", []):
        aid = e.get("asset_id", "")
        if not aid or len(aid) != 16:
            continue
        index.setdefault(aid, {})
        index[aid].update(
            {
                "vertex_count": e.get("vertex_count", 0),
                "face_count": e.get("face_count", 0),
                "faced": e.get("faced", False),
                "mesh_block": e.get("mesh_block"),
                "descriptor": e.get("descriptor"),
                "obj_path": e.get("path"),
                "obj_bytes": e.get("file_size"),
            }
        )

    # === Scene graph manifest (world transforms) ===
    sgm = load_json(FLYTHROUGH / "scene-graph-manifest.json", encoding="utf-8-sig")
    for e in sgm.get("entries", []):
        aid = e.get("asset_id", "")
        if not aid or len(aid) != 16:
            continue
        index.setdefault(aid, {})
        index[aid].update(
            {
                "world_json": e.get("world_json"),
                "node_count": e.get("node_count"),
                "mesh_count": e.get("mesh_count"),
                "has_transform": e.get("node_count", 0) > 1,
            }
        )

    # === LOD manifest ===
    lod = load_json(FLYTHROUGH / "lod-manifest.json")
    for aid, lod_info in lod.get("asset_lod_map", {}).items():
        if aid not in index:
            continue
        index[aid].update(
            {
                "lod_type": lod_info.get("lod_type"),
                "lod_level": lod_info.get("lod_level"),
                "lod_vertex_count": lod_info.get("vertex_count"),
            }
        )

    # === Probe meshsize lookup ===
    probe = load_json(EXPORTS / "probe-meshsize-lookup.json")
    for aid, pinfo in probe.get("entries", {}).items():
        if aid not in index:
            continue
        index[aid].update(
            {
                "mesh_size": pinfo.get("meshsize"),
                "probe_note": pinfo.get("note", ""),
            }
        )

    return index


def build_summary(asset_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Generate summary stats."""
    total = len(asset_index)
    with_world = sum(1 for v in asset_index.values() if v.get("world_json"))
    with_lod = sum(1 for v in asset_index.values() if v.get("lod_type"))
    faced = sum(1 for v in asset_index.values() if v.get("faced"))
    total_verts = sum(v.get("vertex_count", 0) for v in asset_index.values())
    total_faces = sum(v.get("face_count", 0) for v in asset_index.values())
    with_meshsize = sum(1 for v in asset_index.values() if v.get("mesh_size"))

    return {
        "total_asset_ids": total,
        "with_world_json": with_world,
        "with_lod_info": with_lod,
        "faced": faced,
        "position_only": total - faced,
        "total_vertices": total_verts,
        "total_faces": total_faces,
        "with_meshsize": with_meshsize,
        "coverages": {
            "world_json_pct": round(100 * with_world / max(1, total), 1),
            "lod_pct": round(100 * with_lod / max(1, total), 1),
            "meshsize_pct": round(100 * with_meshsize / max(1, total), 1),
        },
    }


def count_textures() -> int:
    """Count PNG textures available."""
    tex_dir = FLYTHROUGH / "textures" / "converted"
    if not tex_dir.exists():
        return 0
    return len(list(tex_dir.glob("*.png")))


def main() -> None:
    print("Building unified flythrough-index.json...")

    asset_index = build_asset_index()
    summary = build_summary(asset_index)
    texture_count = count_textures()

    manifest: dict[str, Any] = {
        "schema": "flythrough-index-v1",
        "generated": datetime.now(UTC).isoformat(),
        "plan_status": "complete",
        "ft_phases_complete": ["FT-1", "FT-2", "FT-3", "FT-4", "FT-5", "FT-6", "FT-7"],
        "ft_8_skipped": True,
        "ft_8_skip_rationale": (
            "Mod-replacement bridge involves writing back to TWAD archives, "
            "contradicting the project's read-only mandate. The plan marks FT-8 "
            "as optional and safety-gated. Skipped in favor of this unified index."
        ),
        "texture_count": texture_count,
        "summary": summary,
        "assets": asset_index,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Written: {OUTPUT} ({size_kb:.1f} KB)")
    print(f"Assets indexed: {summary['total_asset_ids']}")
    print(f"  With world.json: {summary['with_world_json']} ({summary['coverages']['world_json_pct']}%)")
    print(f"  With LOD info: {summary['with_lod_info']} ({summary['coverages']['lod_pct']}%)")
    print(f"  With MeshSize: {summary['with_meshsize']} ({summary['coverages']['meshsize_pct']}%)")
    print(f"{summary['faced']} faced + {summary['position_only']} position-only")
    print(f"{summary['total_vertices']:,} vertices, {summary['total_faces']:,} faces")
    print(f"{texture_count:,} PNG textures")


if __name__ == "__main__":
    main()
