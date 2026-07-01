"""classify_walkability.py — Per-asset walkability classification for navmesh generation.

Phase 0 M0.2 of the navmesh navigation roadmap.
Cross-references zone attribution, semantic hints, and archive provenance
to label each asset as walkable, potentially-walkable, or non-walkable.

Inputs:
  - Exports/semantic-phase1/fly_asset_zone_map_v2.json  (zone attribution)
  - Exports/discovery-matrix/nif-semantic-hints/semantic-nif-map-zone.json  (semantic hints)

Output:
  - Exports/navmesh-phase0/walkability-classification.json

Heuristic rules are applied in priority order; the first matching rule wins.
Confidence is tagged per asset (high / medium / low / unknown) to signal when
bounding-box shape analysis is needed for a definitive classification.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

ZONE_MAP_PATH = REPO_ROOT / "Exports" / "semantic-phase1" / "fly_asset_zone_map_v2.json"
SEMANTIC_PATH = REPO_ROOT / "Exports" / "discovery-matrix" / "nif-semantic-hints" / "semantic-nif-map-zone.json"
OUT_PATH = REPO_ROOT / "Exports" / "navmesh-phase0" / "walkability-classification.json"

# ---------------------------------------------------------------------------
# Classification heuristics
# ---------------------------------------------------------------------------


def _classify_asset(
    asset_id: str,
    zone_entry: dict | None,
    semantic_entry: dict | None,
) -> dict:
    """Classify a single asset by walkability.

    Returns a dict with:
      - asset_id, label, confidence, rationale, needs_shape_analysis
      - zone data (expansion, category, name, tuple, confidence)
      - semantic data (categories, archive)
    """
    label = "unknown"
    confidence = "unknown"
    rationale_parts: list[str] = []
    needs_shape_analysis = False

    cat = zone_entry.get("category", "") if zone_entry else ""
    name = zone_entry.get("name", "") if zone_entry else ""
    zone_conf = zone_entry.get("confidence", "unknown") if zone_entry else "unknown"
    semantic_cats = semantic_entry.get("SemanticCategories", []) if semantic_entry else []
    archive = semantic_entry.get("ArchiveName", "") if semantic_entry else ""

    # -------- Priority 1: Explicit non-walkable categories --------
    if cat == "character":
        # Characters, NPCs, players — never walkable geometry
        label = "non_walkable_character"
        confidence = "high"
        rationale_parts.append(f"Category '{cat}' — character models are not environmental geometry")
        needs_shape_analysis = False

    elif cat == "vfx":
        # Visual effects — particles, emitters, atmosphere, sky
        if name in ("atmosphere", "emitter", "model"):
            label = "non_walkable_vfx"
            confidence = "high"
            rationale_parts.append(f"Category '{cat}/{name}' — VFX assets are not walkable surfaces")
        else:
            label = "non_walkable_vfx"
            confidence = "medium"
            rationale_parts.append(f"Category '{cat}' — VFX assets presumed non-walkable")
        needs_shape_analysis = False

    # -------- Priority 2: World-object sub-classification --------
    elif cat == "world_objects":
        if name == "architecture":
            # Buildings, bridges, structural elements — likely walkable floors
            label = "walkable_structure"
            confidence = "medium"
            rationale_parts.append(
                "World-object architecture — structural elements likely have "
                "walkable floors/platforms; confirm with bounding-box shape"
            )
            needs_shape_analysis = True

        elif name == "dungeons":
            # Dungeon geometry — floors, walls, corridors
            label = "walkable_structure"
            confidence = "medium"
            rationale_parts.append(
                "World-object dungeons — likely walkable floors and corridors; confirm with bounding-box shape"
            )
            needs_shape_analysis = True

        elif name == "housing":
            # Housing assets — mix of floors, walls, roofs, decorations
            label = "potentially_walkable"
            confidence = "low"
            rationale_parts.append(
                "World-object housing — mixed floors/walls/roofs; "
                "needs bounding-box shape analysis to identify walkable surfaces"
            )
            needs_shape_analysis = True

        elif name == "nature":
            # Trees, rocks, foliage — mostly non-walkable but may include terrain
            # If from early archives (assets.00x), more likely terrain
            if archive.startswith("assets.0") and not archive.startswith("assets.00"):
                # assets.03x, assets.04x, assets.05x — world geometry
                label = "potentially_walkable"
                confidence = "low"
                rationale_parts.append(
                    "World-object nature from world-geometry archive — may include terrain; needs shape analysis"
                )
            else:
                label = "non_walkable_nature"
                confidence = "medium"
                rationale_parts.append(
                    "World-object nature — trees, rocks, foliage; "
                    "presumed non-walkable unless bounding box is wide and flat"
                )
            needs_shape_analysis = True

        elif name == "prop":
            label = "non_walkable_prop"
            confidence = "medium"
            rationale_parts.append("World-object prop — small decorative objects, not walkable surfaces")
            needs_shape_analysis = False

        else:
            # Unknown world-object name — need shape data
            label = "potentially_walkable"
            confidence = "low"
            rationale_parts.append(f"World-object '{name}' — unknown subtype; needs shape analysis")
            needs_shape_analysis = True

    # -------- Priority 3: Unknown category --------
    else:
        label = "unknown"
        confidence = "unknown"
        rationale_parts.append(f"Unknown category '{cat}'")
        needs_shape_analysis = True

    # -------- Zone confidence downgrade --------
    # Low/medium zone attribution downgrades high walkability confidence
    if zone_conf in ("low", "medium") and confidence == "high":
        confidence = "medium"
        rationale_parts.append(f"Zone confidence downgrade: zone attribution is '{zone_conf}'")

    return {
        "asset_id": asset_id,
        "label": label,
        "confidence": confidence,
        "rationale": " | ".join(rationale_parts),
        "needs_shape_analysis": needs_shape_analysis,
        "zone": {
            "expansion": zone_entry.get("expansion") if zone_entry else None,
            "category": cat or None,
            "name": name or None,
            "tuple": zone_entry.get("tuple") if zone_entry else None,
            "zone_confidence": zone_conf,
        },
        "semantic": {
            "categories": semantic_cats,
            "archive": archive or None,
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("=== Walkability Classifier — Phase 0 M0.2 ===\n")

    # Load zone map
    if not ZONE_MAP_PATH.exists():
        print(f"ERROR: Zone map not found: {ZONE_MAP_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(ZONE_MAP_PATH, encoding="utf-8") as f:
        zone_map_raw = json.load(f)
    zone_map = zone_map_raw.get("fly_asset_zone_map", {})
    print(f"Zone map: {len(zone_map)} assets")

    # Load semantic hints
    semantic_map: dict[str, dict] = {}
    if SEMANTIC_PATH.exists():
        with open(SEMANTIC_PATH, encoding="utf-8") as f:
            semantic_raw = json.load(f)
        # Map by 16-char prefix (may be subset of full 16-char hash)
        for entry in semantic_raw.get("Entries", []):
            aid = entry.get("AssetIdPrefix", "")
            if aid:
                semantic_map[aid] = entry
        print(f"Semantic hints: {len(semantic_map)} entries")
    else:
        print("Semantic hints: not found (skipping)")

    # Classify all assets from zone map
    all_ids: set[str] = set(zone_map.keys())
    # Also include any semantic-only IDs (not in zone map)
    for aid in semantic_map:
        all_ids.add(aid)

    print(f"Total unique asset IDs: {len(all_ids)}")
    print()

    classifications: list[dict] = []
    label_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    needs_shape_count = 0

    for asset_id in sorted(all_ids):
        ze = zone_map.get(asset_id)
        se = semantic_map.get(asset_id)
        c = _classify_asset(asset_id, ze, se)
        classifications.append(c)
        label_counts[c["label"]] += 1
        confidence_counts[c["confidence"]] += 1
        if c["needs_shape_analysis"]:
            needs_shape_count += 1

    # Summary
    print("=== Label Distribution ===")
    for label, count in label_counts.most_common():
        pct = count / len(classifications) * 100
        print(f"  {label}: {count} ({pct:.1f}%)")

    print()
    print("=== Confidence Distribution ===")
    for conf, count in confidence_counts.most_common():
        pct = count / len(classifications) * 100
        print(f"  {conf}: {count} ({pct:.1f}%)")

    print()
    print(f"Assets needing shape analysis: {needs_shape_count} ({needs_shape_count / len(classifications) * 100:.1f}%)")

    # Walkable summary
    walkable_labels = {"walkable_structure", "walkable_terrain", "potentially_walkable"}
    walkable_count = sum(label_counts.get(lbl, 0) for lbl in walkable_labels)
    print(f"\nPotentially walkable assets: {walkable_count} ({walkable_count / len(classifications) * 100:.1f}%)")

    # Write output
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "schema": "walkability-classification-v1",
        "generated_at": "2026-06-30",
        "summary": {
            "total_assets": len(classifications),
            "walkable_structure": label_counts.get("walkable_structure", 0),
            "walkable_terrain": label_counts.get("walkable_terrain", 0),
            "potentially_walkable": label_counts.get("potentially_walkable", 0),
            "non_walkable_character": label_counts.get("non_walkable_character", 0),
            "non_walkable_vfx": label_counts.get("non_walkable_vfx", 0),
            "non_walkable_nature": label_counts.get("non_walkable_nature", 0),
            "non_walkable_prop": label_counts.get("non_walkable_prop", 0),
            "unknown": label_counts.get("unknown", 0),
            "needs_shape_analysis": needs_shape_count,
        },
        "label_distribution": dict(label_counts.most_common()),
        "confidence_distribution": dict(confidence_counts.most_common()),
        "data_gaps": {
            "mesh_size": "MeshSize data unavailable — flythrough-index.json not built on this machine",
            "bounding_box": "Bounding-box data unavailable — OBJ files and world.json not built on this machine; rebuild flythrough pipeline for shape analysis",
            "vertex_face_counts": "Vertex/face counts unavailable — flythrough pipeline artifacts not built",
        },
        "classifications": sorted(
            classifications,
            key=lambda c: (
                # Order: walkable first, then potentially, then non-walkable
                0 if c["label"].startswith("walkable_") else 1 if c["label"] == "potentially_walkable" else 2,
                c["asset_id"],
            ),
        ),
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nWritten: {OUT_PATH}")

    # Show top walkable candidates
    print("\n=== Top Walkable Candidates ===")
    for c in sorted(
        classifications,
        key=lambda x: (0 if x["label"] == "walkable_structure" else 1 if x["label"] == "potentially_walkable" else 2,),
    )[:15]:
        z = c["zone"]
        print(f"  {c['asset_id'][:16]}  {c['label']:30s}  {z.get('tuple', '?'):45s}  conf={c['confidence']}")


if __name__ == "__main__":
    main()
