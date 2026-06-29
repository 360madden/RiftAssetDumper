#!/usr/bin/env python3
"""Build a RiftFlythrough delivery manifest from v0.7 scene-manifest data.

Reads all stage6 scale-out manifests, filters to consumer_ready=true assets,
and produces a compact delivery JSON for the RiftFlythrough consumer.

v0.2 changes (2026-06-17) — delivery-authoritative textures:
  * Drop absolute Windows paths from the EMITTED JSON (privacy rule +
    unreadable in-browser). Per-entry `obj_path`/`world_json` replaced by
    `asset_id` + a relative `obj_mesh` hint. (Input path construction that
    reaches the canonical nested `Assets/Assets/` data tree is unchanged.)
  * Fix `vv0.1` markdown typo (leading `v` was doubled).
  * Resolve `linked_textures` basenames against the RiftFlythrough converted-PNG
    inventory and emit `linked_texture_urls` — the consumer-consumable form that
    `world.js`'s `textureMapUrls()` expects (`textures/converted/<file>.png`).
    Raw `linked_textures` kept for provenance.
  * Add a hard guard that aborts if any absolute path leaks into the output.

Usage:
    python scripts/build_riftflythrough_delivery.py
    python scripts/build_riftflythrough_delivery.py --copy-to-riftflythrough

Output:
    Assets/Exports/discovery-plan/cycle-2/stage8/riftflythrough-delivery.json
    Assets/Exports/discovery-plan/cycle-2/stage8/riftflythrough-delivery.md
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# REPO_ROOT is the Assets repo root (this script lives at scripts/…). The
# cycle-2 data tree lives under the canonical nested `Assets/Assets/…` path
# (stage6 manifests, worlds, flythrough-index all live there), so input paths
# use `REPO_ROOT/"Assets"/…` deliberately. EMITTED delivery JSON, by contrast,
# must contain no absolute paths — see _assert_no_absolute_paths().
REPO_ROOT = Path(__file__).resolve().parents[1]
CYCLE2_ROOT = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2"
STAGE6_DIR = CYCLE2_ROOT / "stage6"
STAGE8_DIR = CYCLE2_ROOT / "stage8"
RIFTFLYTHROUGH_DIR = REPO_ROOT.parent / "RiftFlythrough"  # sibling project
RIFTFLYTHROUGH_JS = RIFTFLYTHROUGH_DIR / "js"
RIFTFLYTHROUGH_TEXTURES = RIFTFLYTHROUGH_DIR / "textures" / "converted"

PRODUCER_TOOL = "scripts/build_riftflythrough_delivery.py"
PRODUCER_VERSION = "v0.6"
TEXTURE_URL_PREFIX = "textures/converted/"


def load_consumer_ready_manifests() -> list[dict[str, Any]]:
    """Load all stage6 manifests, returning only consumer_ready entries."""
    paths = sorted(STAGE6_DIR.glob("manifest-*.json"))
    entries: list[dict[str, Any]] = []
    for path in paths:
        m = json.loads(path.read_text(encoding="utf-8-sig"))
        if m["validation"]["consumer_ready"]:
            entries.append(m)
    return entries


def index_converted_textures() -> dict[str, str]:
    """Index the RiftFlythrough converted-PNG inventory by lowercased basename.

    Mirrors RiftFlythrough/build_texture_map.py's find_available_textures() so
    the delivery JSON can resolve `linked_textures` basenames into the same
    `textures/converted/<file>` URLs the consumer renderer expects.

    Returns an empty mapping when the sibling RiftFlythrough tree (or its
    textures/converted dir) is unavailable — resolution then degrades to
    basename-only emission, which the consumer can still resolve at load time.
    """
    available: dict[str, str] = {}
    if not RIFTFLYTHROUGH_TEXTURES.is_dir():
        return available
    for png in RIFTFLYTHROUGH_TEXTURES.glob("*.png"):
        available[png.name.lower()] = png.name
    return available


def resolve_texture_urls(
    asset_id: str,
    linked_textures: list[str],
    converted_index: dict[str, str],
) -> list[dict[str, str]]:
    """Resolve raw texture basenames into consumer-consumable `{pattern, url}`.

    A basename is resolved to `textures/converted/<file>` only when an exact
    (case-insensitive) match exists in the converted inventory. Unresolved
    basenames are dropped from `linked_texture_urls` but retained in the raw
    `linked_textures` list for provenance/diagnostics.
    """
    urls: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in linked_textures:
        key = raw.lower().removesuffix(".dds")
        match = converted_index.get(key) or converted_index.get(raw.lower())
        if not match:
            continue
        url = f"{TEXTURE_URL_PREFIX}{match}"
        if url in seen:
            continue
        seen.add(url)
        urls.append({"pattern": asset_id, "url": url})
    return urls


def build_delivery_entry(
    manifest: dict[str, Any],
    converted_index: dict[str, str],
) -> dict[str, Any]:
    """Extract a compact, path-free delivery entry from a full manifest."""
    g = manifest["geometry"]
    w = manifest["world"]
    t = manifest["textures"]
    asset_id = manifest["asset_id"]
    linked_textures: list[str] = list(t["linked_textures"])
    linked_texture_urls = resolve_texture_urls(asset_id, linked_textures, converted_index)
    # obj_mesh hint = last path segment of obj_path (relative, just a hint).
    obj_mesh = Path(g["obj_path"]).name if g.get("obj_path") else None
    # Cycle 5 surface: forward the typed semantic hint categories from the
    # scene manifest (hint:map-zone / hint:actor-object / hint:waypoint-poi).
    # Older manifests pre-dating Cycle 5 omit the semantic sub-record; we
    # emit an empty list in that case so the consumer can rely on the
    # field's presence.
    semantic_block = manifest.get("semantic")
    if isinstance(semantic_block, dict):
        semantic_categories = list(semantic_block.get("categories") or [])
    else:
        semantic_categories = []
    # Cycle 5.1 zone surface: forward the per-asset zone tuple + method.
    # Older manifests pre-dating Cycle 5.1 omit the zone sub-record; we
    # emit a 'unmatched' record in that case so the consumer can rely on
    # the field's presence.
    zone_block = manifest.get("zone")
    if isinstance(zone_block, dict):
        zone_tuple = zone_block.get("tuple")
        zone_expansion = zone_block.get("expansion")
        zone_category = zone_block.get("category")
        zone_name = zone_block.get("name")
        zone_method = zone_block.get("method", "unmatched")
        zone_delta = zone_block.get("delta")
        first4 = zone_block.get("first4", "")
        confidence = zone_block.get("confidence")
    else:
        zone_tuple = zone_expansion = zone_category = zone_name = None
        zone_method = "unmatched"
        zone_delta = None
        first4 = ""
        confidence = None
    return {
        "asset_id": asset_id,
        "obj_mesh": obj_mesh,
        "mesh_block": g["mesh_block"],
        "mesh_size": g["mesh_size"],
        "vertex_count": g["vertex_count"],
        "face_count": g["face_count"],
        "render_class": g["render_class"],
        "obj_sha1": g["obj_sha1"],
        "transform_identity": w["world_transform_identity"],
        "translation": w["world_transform_summary"]["translation"],
        "rotation": w["world_transform_summary"]["rotation"],
        "scale": w["world_transform_summary"]["scale"],
        "texture_source": t["source"],
        "linked_texture_count": t["linked_texture_count"],
        "linked_texture_url_count": len(linked_texture_urls),
        "linked_texture_urls": linked_texture_urls,
        "linked_textures": linked_textures,
        "semantic_categories": semantic_categories,
        "zone_tuple": zone_tuple,
        "zone_expansion": zone_expansion,
        "zone_category": zone_category,
        "zone_name": zone_name,
        "zone_method": zone_method,
        "zone_delta": zone_delta,
        "first4": first4,
        "confidence": confidence,
    }


def build_stats(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate delivery stats."""
    total_verts = sum(e["vertex_count"] for e in entries)
    total_faces = sum(e["face_count"] for e in entries)
    tex_total = sum(e["linked_texture_count"] for e in entries)
    tex_url_total = sum(e["linked_texture_url_count"] for e in entries)
    tex_assets = sum(1 for e in entries if e["linked_texture_count"] > 0)
    tex_url_assets = sum(1 for e in entries if e["linked_texture_url_count"] > 0)
    non_id = sum(1 for e in entries if not e["transform_identity"])
    mesh_families = sorted(set(e["mesh_size"] for e in entries if e["mesh_size"] is not None))
    # Cycle 5 surfaced stats: typed semantic hint distribution
    hint_distribution: dict[str, int] = {}
    tagged_assets = 0
    for e in entries:
        cats = e.get("semantic_categories") or []
        if cats:
            tagged_assets += 1
        for c in cats:
            hint_distribution[c] = hint_distribution.get(c, 0) + 1
    # Cycle 5.1 zone stats: zone-tuple distribution + method counts
    zone_distribution: dict[str, int] = {}
    zone_method_distribution: dict[str, int] = {}
    confidence_distribution: dict[str, int] = {}
    zone_tagged_assets = 0
    for e in entries:
        zt = e.get("zone_tuple")
        zm = e.get("zone_method", "unmatched")
        zc = e.get("confidence")
        zone_method_distribution[zm] = zone_method_distribution.get(zm, 0) + 1
        # Count null confidence bucket under "null" key for clarity
        conf_key = "null" if zc is None else zc
        confidence_distribution[conf_key] = confidence_distribution.get(conf_key, 0) + 1
        if zt is not None:
            zone_tagged_assets += 1
            zone_distribution[zt] = zone_distribution.get(zt, 0) + 1
    return {
        "total_assets": len(entries),
        "total_vertices": total_verts,
        "total_faces": total_faces,
        "total_linked_textures": tex_total,
        "total_linked_texture_urls": tex_url_total,
        "textured_assets": tex_assets,
        "textured_url_assets": tex_url_assets,
        "non_identity_transforms": non_id,
        "mesh_size_families": mesh_families,
        "family_count": len(mesh_families),
        # Cycle 5 fields
        "tagged_assets": tagged_assets,
        "distinct_hints": len(hint_distribution),
        "hint_distribution": hint_distribution,
        # Cycle 5.1 fields
        "zone_tagged_assets": zone_tagged_assets,
        "distinct_zones": len(zone_distribution),
        "zone_distribution": zone_distribution,
        "zone_method_distribution": zone_method_distribution,
        # Cycle 5.2 fields
        "confidence_distribution": confidence_distribution,
    }


def build_markdown(entries: list[dict[str, Any]], stats: dict[str, Any]) -> str:
    """Generate a markdown delivery report."""
    lines = [
        "# RiftFlythrough Delivery Manifest",
        "",
        f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"**Producer:** {PRODUCER_TOOL} {PRODUCER_VERSION}",
        "",
        "## What changed (v0.6)",
        "",
        "- Cycle 5.2 unifier: Renamed `zone_first4` -> `first4` and `zone_confidence` -> `confidence` in the per-asset delivery entries (and the top-level aggregate `zone_confidence_distribution` -> `confidence_distribution`) so the delivery JSON's API surface matches the canonical scene-manifest-v1 schema's nested `Zone.first4` / `Zone.confidence` directly. Producer version bumped to v0.6. Updated sibling RiftFlythrough consumer `transform_loader.js` to read the unprefixed keys. Hard break -- rely on `first4` / `confidence` from now on; the prefixed names are no longer emitted.",
        "",
        "## What changed (v0.5)",
        "",
        "- Cycle 5.2: Added `zone_confidence` (high/medium/low/null) and `zone_first4` (4-byte NIF magic, transparency-only) to per-asset zone fields. Confidence buckets: high = direct match (delta=0) or tight sibling (|delta|<=5); medium = plausible sibling (6<=|delta|<=30); low = coincidental adjacency (|delta|>30); null = unmatched. Consumers can opt out of low-confidence attributions without re-deriving the discrimination rationale (see `docs/handoffs/2026-06-28-archive-neighbor-verification.md`). First4 is recorded for transparency; the verification handoff found all 5 closest and all 3 farthest neighbors share First4 `47616d65`, so it does NOT discriminate siblings -- Entry-Index Delta is the discriminating signal.",
        "",
        "## What changed (v0.4)",
        "",
        "- Added per-asset zone fields (Cycle 5.1 surface): `zone_tuple`, `zone_expansion`, `zone_category`, `zone_name`, `zone_method` (direct/neighbor/unmatched), `zone_delta` (entry-index distance). Resolved from the hint:map-zone scan via direct match or archive-neighbor +/-150 fallback. The zone_tuple is the canonical identifier (e.g. `vanilla.world_objects.props`).",
        "",
        "## What changed (v0.3)",
        "",
        "- Added `semantic_categories: list[string]` per asset (Cycle 5 surface): typed hint tags from asset-semantic-index/v1 matrix reports (hint:map-zone / hint:actor-object / hint:waypoint-poi). Empty list when the asset appears in no matrix report.",
        "",
        "## What changed (v0.2)",
        "",
        "- Removed absolute Windows paths (`obj_path`/`world_json`) — the consumer keys off `asset_id`; absolute paths were unreadable in a browser and leaked local layout.",
        "- Added `linked_texture_urls` (NIF-confirmed basenames resolved to `textures/converted/<file>`), the form `world.js` consumes directly.",
        "- Fixed the `REPO_ROOT` double-prefix bug and the `vv0.1` typo.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Consumer-ready assets | {stats['total_assets']} |",
        f"| Total vertices | {stats['total_vertices']:,} |",
        f"| Total faces | {stats['total_faces']:,} |",
        f"| Linked textures (raw) | {stats['total_linked_textures']} ({stats['textured_assets']} assets) |",
        f"| Linked texture URLs (resolved) | {stats['total_linked_texture_urls']} ({stats['textured_url_assets']} assets) |",
        f"| Non-identity transforms | {stats['non_identity_transforms']} |",
        f"| Assets with semantic hints | {stats['tagged_assets']} ({stats['distinct_hints']} distinct tags) |",
        f"| Mesh size families | {stats['family_count']} |",
        "",
        "## Mesh Size Families",
        "",
        ", ".join(str(ms) for ms in stats["mesh_size_families"]),
        "",
        "## Semantic Hint Distribution",
        "",
        ", ".join(f"{k}={v}" for k, v in sorted(stats["hint_distribution"].items())) or "-",
        "",
        "## Per-Asset Detail",
        "",
        "| Asset ID | Mesh | Size | Vertices | Faces | TexURLs | Transform | Semantic | Zone | Conf |",
        "|---|---:|---:|---:|---:|---:|---|---|---|---|",
    ]
    for e in sorted(entries, key=lambda x: (x["render_class"], -x["face_count"])):
        aid = e["asset_id"][:8]
        mb = e["mesh_block"] or "-"
        ms = e["mesh_size"] if e["mesh_size"] is not None else "-"
        txu = e["linked_texture_url_count"]
        tf = "non-id" if not e["transform_identity"] else "id"
        sem = ",".join(e.get("semantic_categories") or []) or "-"
        zone = e.get("zone_tuple") or "-"
        conf = e.get("confidence") or "-"
        lines.append(
            f"| {aid} | {mb} | {ms} | {e['vertex_count']} | {e['face_count']} | {txu} | {tf} | {sem} | {zone} | {conf} |"
        )
    return "\n".join(lines) + "\n"


def _assert_no_absolute_paths(delivery: dict[str, Any]) -> None:
    """Fail fast if any serialized field still contains a drive-letter path.

    Run after JSON construction so the check covers the whole document.
    """
    blob = json.dumps(delivery, ensure_ascii=False)
    # A Windows absolute path always contains a drive letter + colon + backslash.
    if ":" in blob and "\\" in blob:
        # Allow the JSON `generated_at` ISO timestamp (contains ':'), which has
        # no backslash. Only a drive path has both ':' and '\\' together.
        import re

        drive_path = re.search(r"[A-Za-z]:\\\\", blob)
        if drive_path:
            msg = (
                "build_riftflythrough_delivery: absolute Windows path leaked into"
                f" delivery JSON near {drive_path.group(0)!r} — aborting."
            )
            raise AssertionError(msg)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build RiftFlythrough delivery manifest")
    parser.add_argument(
        "--copy-to-riftflythrough",
        action="store_true",
        help="Copy delivery JSON to RiftFlythrough/js/ directory",
    )
    args = parser.parse_args()

    if not STAGE6_DIR.is_dir():
        print(
            f"ERROR: stage6 manifests not found at {STAGE6_DIR}. "
            "Run the cycle-2 scale-out (build_scene_manifest.py) first.",
            file=sys.stderr,
        )
        return 1

    entries = load_consumer_ready_manifests()
    if not entries:
        print("ERROR: no consumer_ready manifests found", file=sys.stderr)
        return 1

    converted_index = index_converted_textures()
    if not converted_index:
        print(
            "WARNING: RiftFlythrough converted-PNG inventory not found at "
            f"{RIFTFLYTHROUGH_TEXTURES} — linked_texture_urls will be empty; "
            "re-run after exporting converted textures.",
            file=sys.stderr,
        )

    delivery_entries = [build_delivery_entry(m, converted_index) for m in entries]
    stats = build_stats(delivery_entries)

    STAGE8_DIR.mkdir(parents=True, exist_ok=True)

    document = {
        "SchemaVersion": "riftflythrough-delivery/v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "producer": {
            "tool": PRODUCER_TOOL,
            "version": PRODUCER_VERSION,
        },
        "summary": stats,
        "entries": delivery_entries,
    }

    # Hard guard: never emit a delivery with leaked absolute paths.
    _assert_no_absolute_paths(document)

    # Write delivery JSON
    json_path = STAGE8_DIR / "riftflythrough-delivery.json"
    json_path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Delivery JSON: {json_path} ({json_path.stat().st_size:,} bytes)")

    # Write delivery markdown
    md_path = STAGE8_DIR / "riftflythrough-delivery.md"
    md_path.write_text(build_markdown(delivery_entries, stats), encoding="utf-8")
    print(f"Delivery MD:   {md_path}")

    # Summary
    print(f"\nDelivery: {stats['total_assets']} consumer-ready assets")
    print(f"  Vertices:      {stats['total_vertices']:,}")
    print(f"  Faces:         {stats['total_faces']:,}")
    print(f"  Tex URLs:      {stats['total_linked_texture_urls']} ({stats['textured_url_assets']} assets)")
    print(f"  Tex raw:       {stats['total_linked_textures']} ({stats['textured_assets']} assets)")
    print(f"  Transforms:    {stats['non_identity_transforms']} non-identity")
    print(f"  Semantic:      {stats['tagged_assets']} tagged assets ({stats['distinct_hints']} distinct hint types)")
    print(f"  Families:      {stats['family_count']} mesh sizes")

    # Copy to RiftFlythrough
    if args.copy_to_riftflythrough:
        if not RIFTFLYTHROUGH_DIR.exists():
            print(f"\nWARNING: RiftFlythrough not found at {RIFTFLYTHROUGH_DIR}", file=sys.stderr)
            return 0
        dest = RIFTFLYTHROUGH_JS / "riftflythrough-delivery.json"
        RIFTFLYTHROUGH_JS.mkdir(parents=True, exist_ok=True)
        shutil.copy2(json_path, dest)
        print(f"\nCopied to: {dest}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
