#!/usr/bin/env python3
"""Build the Cycle 2 cohort (C2-1.4) from the flythrough index + live world.jsons.

Reads:
  - `Assets/build/flythrough/flythrough-index.json` (217-asset manifest)
  - `Assets/build/flythrough/objs/worlds/*.world.json` (per-asset scene graphs)

Writes:
  - `Assets/Exports/discovery-plan/cycle-2/stage1/cohort.json`

Selection rules (deterministic; see `cohort.md` for rationale):

1. **Non-identity transform** (4): walk every `world.json`, compute the
   accumulated world transform via the same Scale → Rotate → Translate
   accumulator as `scripts/build_world_placed_merge.py`, and flag any
   asset whose transform deviates from identity (translation any component
   > 1e-6, OR rotation != 3x3 identity, OR scale != 1.0 ± 1e-6).
2. **Per-family selection** (top 4 MeshSize families: 325, 305, 329, 321):
   take the first 5 (or family-size, whichever is smaller) alphabetically-
   sorted members of each family.
3. **Edge cases** (3 hand-picked): high scene-graph complexity (multi-mesh,
   MB-variant, orphan-mesh regression).
4. **Pos-only no-texture** (1 subsampled): one of the 5 unresolvable
   textureless assets, intentionally subsampled to keep cohort size in band.

Target size: ~25 assets (was 39; trimmed per C2 plan v0.3 optimization to
fit V4 Pro 1-page briefs). The 4 non-id + ~18 family + 3 edge + 1 pos-only
= 26 with current MeshSize family sizes.

The output is byte-stable for an unchanged `flythrough-index.json`. Run this
any time the index changes; the cohort is regenerated in one pass.

Usage:
    python scripts/build_cycle_2_cohort.py
    python scripts/build_cycle_2_cohort.py --dry-run
    python scripts/build_cycle_2_cohort.py --out <path>
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Reuse the canonical transform accumulator from the production script (per
# project rule: "Always reuse helper functions... Don't reimplement what
# already exists"). The underscore-prefixed name is OK to import here because
# both scripts are first-party Assets-repo code in the same package.
_REPO_ROOT_FALLBACK = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT_FALLBACK / "Assets" / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_FALLBACK / "Assets" / "scripts"))
from build_world_placed_merge import (  # noqa: E402
    IDENTITY_ROTATION,
    _compute_world_transform,
)

log = logging.getLogger("build_cycle_2_cohort")

# Project layout: this script lives at `<workspace>/Assets/scripts/build_cycle_2_cohort.py`,
# so `parents[2]` is the workspace root (`C:\RIFT MODDING`) and `REPO_ROOT / "Assets" / ...`
# resolves to `<workspace>/Assets/...` which is the project root + the actual data location.
# The data files (flythrough-index.json, world.jsons) live at this doubled path because
# the project is rooted at `C:\RIFT MODDING\Assets` (the "Assets" repo) but the data was
# historically generated under `<workspace>/Assets/Assets/build/...`.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX = REPO_ROOT / "Assets" / "Assets" / "build" / "flythrough" / "flythrough-index.json"
DEFAULT_WORLDS = REPO_ROOT / "Assets" / "Assets" / "build" / "flythrough" / "objs" / "worlds"
DEFAULT_SCENE_GRAPH_MANIFEST = REPO_ROOT / "Assets" / "Assets" / "build" / "flythrough" / "scene-graph-manifest.json"
DEFAULT_OUT = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage1" / "cohort.json"

NON_IDENTITY_TOLERANCE = 1e-6
IDENTITY_TRANSLATION: list[float] = [0, 0, 0]
TOP_FAMILIES: list[int] = [325, 305, 329, 321]
FAMILY_TAKE = 5
EDGE_CASES: list[tuple[str, str, str]] = [
    ("1ecdbaf5a2576ba5", "multi-mesh-11", "11-mesh NIF (Guardian_fe_room) - max meshes in cohort"),
    ("42024b768fcd2e2b", "mb-variant", "MeshSize 305 with MB=6 (float2) + MB=34 (float3) - proven Z-source pair"),
    ("6fc01704d4a509d5", "orphan-mesh-test", "Single-mesh NIF in TestOrphanMeshResolution regression test"),
]
POS_ONLY_NO_TEXTURE: list[str] = [
    "0e0c61ad75d2af1e",  # 1 of 5 unresolvable textureless assets (subsampled)
]

# The 4 known non-identity-transform assets are the most informative
# cohort members, but neither `flythrough-index.json` nor
# `scene-graph-manifest.json` carries their `mesh_size` field. Their values
# were determined empirically during the C2-1.2 walk and recorded in
# `Assets/Exports/discovery-plan/cycle-2/stage1/artifacts/artifacts.md`.
# These overrides let the cohort carry correct MeshSize metadata for the 4
# most-stratified-by-family members.
MESH_SIZE_OVERRIDES: dict[str, int] = {
    "07f37c99a80da009": 305,
    "2c85cfa17543443b": 305,
    "4a97d66a665a538e": 240,
    "593ea328978bde38": 305,
}


def _is_identity(t: list[float], r: list[float], s: float) -> bool:
    return (
        all(abs(v) < NON_IDENTITY_TOLERANCE for v in t)
        and list(r) == IDENTITY_ROTATION
        and abs(s - 1.0) < NON_IDENTITY_TOLERANCE
    )


def find_non_identity_assets(worlds_dir: Path) -> list[str]:
    """Walk every world.json and return assets whose world transform is non-identity."""
    if not worlds_dir.exists():
        raise FileNotFoundError(f"worlds_dir not found: {worlds_dir}")
    non_id: list[str] = []
    for p in sorted(worlds_dir.glob("*.world.json")):
        wj = json.loads(p.read_text(encoding="utf-8-sig"))
        t, r, s = _compute_world_transform(wj)
        if not _is_identity(t, r, s):
            non_id.append(p.stem)
    return non_id


def build_cohort(
    flythrough: dict[str, Any],
    non_id_ids: list[str],
    scene_graph_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the cohort JSON-serializable dict.

    Args:
        flythrough: the parsed flythrough-index.json contents.
        non_id_ids: asset IDs whose world transform is non-identity.
        scene_graph_manifest: optional parsed scene-graph-manifest.json; when
            provided, missing fields (mesh_size, node_count, mesh_count,
            world_json) on cohort entries are filled in from this manifest.
            This is the durable fallback for the 4 non-id assets, which
            `flythrough-index.json` does not always populate.
    """
    assets: dict[str, dict[str, Any]] = flythrough.get("assets", {})
    asset_ids = set(assets.keys())

    # Build a per-asset fallback table from the scene-graph manifest.
    sg_lookup: dict[str, dict[str, Any]] = {}
    if scene_graph_manifest:
        for entry in scene_graph_manifest.get("entries", []):
            aid = entry.get("asset_id")
            if aid:
                sg_lookup[aid] = entry

    by_family: dict[int, list[str]] = collections.defaultdict(list)
    for aid, data in assets.items():
        ms = data.get("mesh_size") or MESH_SIZE_OVERRIDES.get(aid) or sg_lookup.get(aid, {}).get("mesh_size", 0)
        if ms:
            by_family[ms].append(aid)

    cohort: list[dict[str, Any]] = []

    # Stratum 1: non-identity transform
    # The non-id IDs come from the live world.jsons, so they're always valid
    # asset IDs in the flythrough subset. If a non-id ID is NOT in assets
    # (e.g., flythrough-index.json was rebuilt and the asset was dropped), we
    # log a warning but still keep the entry with null metadata so the cohort
    # surfaces the data drift rather than silently dropping the asset.
    for aid in non_id_ids:
        present = aid in asset_ids
        if not present:
            log.warning("non-id asset %s not in flythrough-index.json; keeping with null metadata", aid)
        cohort.append(
            {
                "asset_id": aid,
                "family": "non-identity-transform",
                "why": "Known non-identity world transform (C2-1.2 walk)",
            }
        )

    # Stratum 2: top MeshSize families
    for ms in TOP_FAMILIES:
        members = sorted(by_family.get(ms, []))[:FAMILY_TAKE]
        for aid in members:
            cohort.append(
                {
                    "asset_id": aid,
                    "family": f"meshsize-{ms}",
                    "why": f"Top-{len(by_family[ms])} MeshSize {ms} family asset (first {len(members)} alphabetical)",
                }
            )

    # Stratum 3: edge cases
    for aid, fam, why in EDGE_CASES:
        cohort.append({"asset_id": aid, "family": fam, "why": why})

    # Stratum 4: pos-only no-texture (1 of 5 unresolvable, intentionally subsampled)
    for aid in POS_ONLY_NO_TEXTURE:
        cohort.append(
            {
                "asset_id": aid,
                "family": "pos-only-no-texture",
                "why": "Pos-only OBJ; one of 5 unresolvable textureless assets (subsampled to keep cohort size in 30-50 band)",
            }
        )
        break  # always take exactly 1

    # Enrich each cohort entry with metadata from flythrough-index.json, with
    # fallback to the scene-graph manifest for fields the index doesn't carry.
    #
    # Field provenance (post-enrichment):
    #   - mesh_size: from flythrough-index.json when present, else null. The
    #     scene-graph manifest does NOT carry mesh_size (it carries node_count
    #     and mesh_count instead); for the 4 non-id assets, mesh_size stays
    #     null. Downstream code can compute mesh_size from the OBJ's vertex
    #     count, or look it up from `Exports/meshsize-lookup.json` /
    #     `scripts/infer_meshsizes.py` output if needed.
    #   - node_count, mesh_count: from the scene-graph manifest (authoritative).
    #   - world_json, obj_path, has_faces: best-effort; null when not in index.
    #   - metadata_source: a string reporting which sources contributed.
    for entry in cohort:
        aid = entry["asset_id"]
        a = assets.get(aid, {})
        sg = sg_lookup.get(aid, {})
        # mesh_size precedence: flythrough-index > MESH_SIZE_OVERRIDES (for
        # the 4 non-id assets) > null. The scene-graph manifest does NOT
        # carry mesh_size.
        entry["mesh_size"] = a.get("mesh_size") or MESH_SIZE_OVERRIDES.get(aid)
        entry["world_json"] = a.get("world_json") or sg.get("world_json") or f"{aid}.world.json"
        entry["obj_path"] = a.get("obj_path", "")
        entry["has_faces"] = bool(a.get("faced", False))
        lt = a.get("linked_textures", [])
        entry["linked_texture_count"] = len(lt) if isinstance(lt, list) else 0
        entry["node_count"] = sg.get("node_count")
        entry["mesh_count"] = sg.get("mesh_count")
        entry["present_in_index"] = aid in asset_ids
        entry["metadata_source"] = (
            "flythrough-index+scene-graph-manifest"
            if (a and sg)
            else (
                "flythrough-index+MESH_SIZE_OVERRIDE+scene-graph-manifest"
                if (MESH_SIZE_OVERRIDES.get(aid) and sg)
                else (
                    "flythrough-index"
                    if a
                    else "scene-graph-manifest-only+MESH_SIZE_OVERRIDE"
                    if MESH_SIZE_OVERRIDES.get(aid)
                    else "scene-graph-manifest-only"
                )
            )
        )

    family_counts = dict(collections.Counter(e["family"] for e in cohort))
    return {
        "plan": "cycle-2",
        "step": "C2-1.4",
        "script": "scripts/build_cycle_2_cohort.py",
        "reproducibility": "byte-stable for unchanged flythrough-index.json + world.jsons",
        "cohort_size": len(cohort),
        "family_counts": family_counts,
        "top_families_requested": TOP_FAMILIES,
        "family_take_per_family": FAMILY_TAKE,
        "edge_case_count": len(EDGE_CASES),
        "pos_only_subsample_count": 1,
        "non_identity_count": len(non_id_ids),
        "target_band": "20-30",
        "rationale": (
            "Curated subset of ~25 assets spanning the non-identity transform "
            "assets (4), top 4 MeshSize families (325, 305, 329, 321) at 5 each "
            "(capped at family size), 3 edge cases, and 1 pos-only no-texture "
            "subsample. Sized for V4 Pro 1-page briefs (was 39 in C2 plan v0.2; "
            "trimmed in v0.3). Used for C2-2..C2-8 analysis and validation. The "
            "cohort is a working subset, not durable truth; C2-6 produces per-"
            "asset manifests which are the durable cycle 2 output."
        ),
        "cohort": cohort,
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(
        prog="build_cycle_2_cohort",
        description="Build the C2-1.4 cohort from the flythrough index + live world.jsons",
    )
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX, help="flythrough-index.json path")
    parser.add_argument("--worlds", type=Path, default=DEFAULT_WORLDS, help="worlds/ directory")
    parser.add_argument(
        "--scene-graph-manifest",
        type=Path,
        default=DEFAULT_SCENE_GRAPH_MANIFEST,
        help="scene-graph-manifest.json path (for mesh_size fallback)",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="cohort.json output path")
    parser.add_argument("--dry-run", action="store_true", help="Print summary, do not write")
    args = parser.parse_args()

    if not args.index.exists():
        log.error("index not found: %s", args.index)
        return 1

    flythrough = json.loads(args.index.read_text(encoding="utf-8-sig"))
    assets = flythrough.get("assets", {})
    log.info("loaded %d assets from %s", len(assets), args.index)

    scene_graph_manifest: dict[str, Any] | None = None
    if args.scene_graph_manifest and args.scene_graph_manifest.exists():
        scene_graph_manifest = json.loads(args.scene_graph_manifest.read_text(encoding="utf-8-sig"))
        log.info("loaded scene-graph-manifest with %d entries", len(scene_graph_manifest.get("entries", [])))
    else:
        log.warning("scene-graph-manifest not found at %s; mesh_size fallback disabled", args.scene_graph_manifest)

    non_id = find_non_identity_assets(args.worlds)
    log.info("found %d non-identity transform assets", len(non_id))
    for aid in non_id:
        log.info("  non-id: %s", aid)

    cohort_data = build_cohort(flythrough, non_id, scene_graph_manifest)
    log.info("cohort size: %d", cohort_data["cohort_size"])
    log.info("family counts: %s", cohort_data["family_counts"])

    if args.dry_run:
        print(json.dumps(cohort_data, indent=2))
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(cohort_data, indent=2) + "\n", encoding="utf-8")
    log.info("wrote %s", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
