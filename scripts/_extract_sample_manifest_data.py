#!/usr/bin/env python3
"""Extract sample manifest data for 07f37c99a80da009 (C2-2.4 first sample).

Prints the fields needed to populate a scene-manifest/v1 entry for one
non-identity cohort asset. Used as the data source for the first sample
manifest build.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
WORLD_JSON = REPO_ROOT / "Assets" / "build" / "flythrough" / "objs" / "worlds" / "07f37c99a80da009.world.json"
FLYTHROUGH_INDEX = REPO_ROOT / "Assets" / "build" / "flythrough" / "flythrough-index.json"
ASSET_ID = "07f37c99a80da009"


def extract_world_data() -> dict[str, Any]:
    """Pull NodeCount, MeshCount, Meshes, and the non-identity node transform."""
    w = json.loads(WORLD_JSON.read_text(encoding="utf-8-sig"))
    # The non-id node is the one whose mesh is attached to (ParentNiNodeIndex)
    meshes = w.get("Meshes", [])
    parent_idx = meshes[0]["ParentNiNodeIndex"] if meshes else -1
    # Walk nodes; find the one at index parent_idx
    nodes = w.get("Nodes", [])
    parent_node = next(
        (n for n in nodes if n.get("BlockIndex") == parent_idx),
        None,
    )
    return {
        "NifVersion": w.get("NifVersion"),
        "NodeCount": w.get("NodeCount"),
        "MeshCount": w.get("MeshCount"),
        "MeshesAttached": w.get("MeshesAttached"),
        "Meshes": meshes,
        "non_identity_node": {
            "Name": parent_node.get("Name") if parent_node else None,
            "BlockIndex": parent_node.get("BlockIndex") if parent_node else None,
            "Translation": parent_node.get("Translation") if parent_node else None,
            "Rotation": parent_node.get("Rotation") if parent_node else None,
            "Scale": parent_node.get("Scale") if parent_node else None,
        }
        if parent_node
        else None,
    }


def extract_flythrough_entry() -> dict[str, Any] | None:
    """Find the flythrough-index entry for this asset (skip non-dict entries)."""
    idx = json.loads(FLYTHROUGH_INDEX.read_text(encoding="utf-8-sig"))
    for a in idx.get("assets", []):
        if not isinstance(a, dict):
            continue
        if str(a.get("asset_id", "")).startswith(ASSET_ID):
            return a
    return None


def main() -> int:
    w = extract_world_data()
    f = extract_flythrough_entry()
    out = {
        "asset_id": ASSET_ID,
        "world": w,
        "flythrough": f,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
