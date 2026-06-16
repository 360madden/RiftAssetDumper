#!/usr/bin/env python3
"""Build a RiftFlythrough delivery manifest from v0.7 scene-manifest data.

Reads all stage6 scale-out manifests, filters to consumer_ready=true assets,
and produces a compact delivery JSON for the RiftFlythrough consumer.

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

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGE6_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage6"
STAGE8_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage8"
RIFTFLYTHROUGH_DIR = REPO_ROOT.parent / "RiftFlythrough"  # sibling project
RIFTFLYTHROUGH_JS = RIFTFLYTHROUGH_DIR / "js"

PRODUCER_TOOL = "scripts/build_riftflythrough_delivery.py"
PRODUCER_VERSION = "v0.1"


def load_consumer_ready_manifests() -> list[dict[str, Any]]:
    """Load all stage6 manifests, returning only consumer_ready entries."""
    paths = sorted(STAGE6_DIR.glob("manifest-*.json"))
    entries: list[dict[str, Any]] = []
    for path in paths:
        m = json.loads(path.read_text(encoding="utf-8-sig"))
        if m["validation"]["consumer_ready"]:
            entries.append(m)
    return entries


def build_delivery_entry(manifest: dict[str, Any]) -> dict[str, Any]:
    """Extract a compact delivery entry from a full manifest."""
    g = manifest["geometry"]
    w = manifest["world"]
    t = manifest["textures"]
    return {
        "asset_id": manifest["asset_id"],
        "obj_path": g["obj_path"],
        "world_json": w["world_json"],
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
        "linked_textures": t["linked_textures"],
    }


def build_stats(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate delivery stats."""
    total_verts = sum(e["vertex_count"] for e in entries)
    total_faces = sum(e["face_count"] for e in entries)
    tex_total = sum(e["linked_texture_count"] for e in entries)
    tex_assets = sum(1 for e in entries if e["linked_texture_count"] > 0)
    non_id = sum(1 for e in entries if not e["transform_identity"])
    mesh_families = sorted(set(e["mesh_size"] for e in entries if e["mesh_size"] is not None))
    return {
        "total_assets": len(entries),
        "total_vertices": total_verts,
        "total_faces": total_faces,
        "total_linked_textures": tex_total,
        "textured_assets": tex_assets,
        "non_identity_transforms": non_id,
        "mesh_size_families": mesh_families,
        "family_count": len(mesh_families),
    }


def build_markdown(entries: list[dict[str, Any]], stats: dict[str, Any]) -> str:
    """Generate a markdown delivery report."""
    lines = [
        "# RiftFlythrough Delivery Manifest",
        "",
        f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"**Producer:** {PRODUCER_TOOL} v{PRODUCER_VERSION}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Consumer-ready assets | {stats['total_assets']} |",
        f"| Total vertices | {stats['total_vertices']:,} |",
        f"| Total faces | {stats['total_faces']:,} |",
        f"| Linked textures | {stats['total_linked_textures']} ({stats['textured_assets']} assets) |",
        f"| Non-identity transforms | {stats['non_identity_transforms']} |",
        f"| Mesh size families | {stats['family_count']} |",
        "",
        "## Mesh Size Families",
        "",
        ", ".join(str(ms) for ms in stats["mesh_size_families"]),
        "",
        "## Per-Asset Detail",
        "",
        "| Asset ID | Mesh | Size | Vertices | Faces | Textures | Transform |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for e in sorted(entries, key=lambda x: (x["render_class"], -x["face_count"])):
        aid = e["asset_id"][:8]
        mb = e["mesh_block"] or "-"
        ms = e["mesh_size"] if e["mesh_size"] is not None else "-"
        tx = e["linked_texture_count"]
        tf = "non-id" if not e["transform_identity"] else "id"
        lines.append(f"| {aid} | {mb} | {ms} | {e['vertex_count']} | {e['face_count']} | {tx} | {tf} |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build RiftFlythrough delivery manifest")
    parser.add_argument(
        "--copy-to-riftflythrough",
        action="store_true",
        help="Copy delivery JSON to RiftFlythrough/js/ directory",
    )
    args = parser.parse_args()

    entries = load_consumer_ready_manifests()
    if not entries:
        print("ERROR: no consumer_ready manifests found", file=sys.stderr)
        return 1

    delivery = [build_delivery_entry(m) for m in entries]
    stats = build_stats(delivery)

    STAGE8_DIR.mkdir(parents=True, exist_ok=True)

    # Write delivery JSON
    json_path = STAGE8_DIR / "riftflythrough-delivery.json"
    json_path.write_text(
        json.dumps(
            {
                "SchemaVersion": "riftflythrough-delivery/v1",
                "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "producer": {
                    "tool": PRODUCER_TOOL,
                    "version": PRODUCER_VERSION,
                },
                "summary": stats,
                "entries": delivery,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Delivery JSON: {json_path} ({json_path.stat().st_size:,} bytes)")

    # Write delivery markdown
    md_path = STAGE8_DIR / "riftflythrough-delivery.md"
    md_path.write_text(build_markdown(delivery, stats), encoding="utf-8")
    print(f"Delivery MD:   {md_path}")

    # Summary
    print(f"\nDelivery: {stats['total_assets']} consumer-ready assets")
    print(f"  Vertices: {stats['total_vertices']:,}")
    print(f"  Faces:    {stats['total_faces']:,}")
    print(f"  Textures: {stats['total_linked_textures']} ({stats['textured_assets']} assets)")
    print(f"  Transforms: {stats['non_identity_transforms']} non-identity")
    print(f"  Families: {stats['family_count']} mesh sizes")

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
