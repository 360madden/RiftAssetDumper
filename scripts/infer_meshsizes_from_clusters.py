"""
Phase 36: Infer MeshSizes from Face-Count Clusters

Reads the export manifest and probe lookup file to infer MeshSizes
for faced OBJs with unknown MeshSize, based on face-count/vertex-count/
mesh-block patterns that match known probed IDs.

Usage:
    python scripts/infer_meshsizes_from_clusters.py [--apply] [--dry-run]

    --apply     Update the probe lookup file with inferred entries
    --dry-run   Show what would be inferred without writing (default)
"""

import json
import sys
from pathlib import Path

SEP = "=" * 80
REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "Exports" / "export-manifest.json"
PROBE_LOOKUP_PATH = REPO_ROOT / "Exports" / "probe-meshsize-lookup.json"


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        print(f"ERROR: Manifest not found: {MANIFEST_PATH}")
        print("Run build_export_manifest.py first.")
        sys.exit(1)
    with open(str(MANIFEST_PATH), encoding="utf-8") as f:
        return json.load(f)


def load_probe_lookup() -> dict:
    if not PROBE_LOOKUP_PATH.exists():
        return {"entries": {}}
    with open(str(PROBE_LOOKUP_PATH), encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    do_apply = "--apply" in sys.argv

    print(SEP)
    print("PHASE 36: INFER MESHSIZES FROM FACE-COUNT CLUSTERS")
    print(SEP)

    manifest = load_manifest()
    probe_lookup = load_probe_lookup()
    probe_entries = probe_lookup.get("entries", {})
    known_ids = set(probe_entries.keys())

    entries = manifest.get("entries", [])

    # Find faced entries with unknown MeshSize
    faced_unknown = [
        e for e in entries
        if e.get("faced")
        and (not e.get("sibling_pair") or not e["sibling_pair"].get("mesh_size"))
    ]

    print(f"\nFaced unknown-MeshSize entries: {len(faced_unknown)}")

    # Load known probes as cluster templates
    known_probes = {
        aid: info
        for aid, info in probe_entries.items()
        if info.get("faced") and isinstance(info.get("meshsize"), int)
    }

    # For each known probe, find matching entries in the unknown set
    # Match based on: same mesh_block, similar face count (±5%), similar vertex count (±5%)
    matches_found = 0
    new_inferences = []

    for probe_id, probe_info in sorted(known_probes.items()):
        probe_ms = probe_info["meshsize"]
        probe_mb = str(probe_info.get("mesh_block", ""))
        if probe_mb == "inferred":
            # Skip inferred entries as templates — only use directly-probed ones
            continue
        # Find probe's manifest entry to get vertex/face counts (must match MB)
        probe_entry = next(
            (e for e in entries if e.get("asset_id") == probe_id and e.get("mesh_block") == probe_mb),
            None,
        )
        if not probe_entry:
            continue

        target_faces = probe_entry.get("faces", 0) or 0
        target_verts = probe_entry.get("vertex_count", 0)
        target_mb = probe_entry.get("mesh_block")

        if target_faces == 0 or target_verts == 0 or not target_mb:
            continue

        # Find matching unknown entries
        tolerance = 0.05  # 5% tolerance for face/vertex counts
        cluster_matches = []

        for ue in faced_unknown:
            ue_id = ue.get("asset_id")
            if not ue_id or ue_id in known_ids:
                continue

            ue_faces = ue.get("faces", 0) or 0
            ue_verts = ue.get("vertex_count", 0)
            ue_mb = ue.get("mesh_block")

            if ue_faces == 0 or ue_verts == 0 or ue_mb != target_mb:
                continue

            # Check if face/vertex counts are within tolerance
            face_diff = abs(ue_faces - target_faces) / max(target_faces, 1)
            vert_diff = abs(ue_verts - target_verts) / max(target_verts, 1)

            if face_diff <= tolerance and vert_diff <= tolerance:
                cluster_matches.append(ue_id)

        if cluster_matches:
            matches_found += 1
            new_inferences.extend(
                (uid, probe_ms, probe_id, target_faces, target_verts, target_mb)
                for uid in cluster_matches
            )

    print(f"\nCluster patterns found: {matches_found}")
    print(f"New entries that could be inferred: {len(new_inferences)}")

    if new_inferences:
        print(f"\n{'ID':>20} {'MS':>4} {'Faces':>6} {'Verts':>6} {'MB':>3} {'Matched':>20}")
        print("-" * 65)
        for uid, ms, matched_id, faces, verts, mb in sorted(new_inferences):
            print(f"{uid:>20} {ms:>4} {faces:>6} {verts:>6} {mb:>3} {matched_id:>20}")

    if do_apply and new_inferences:
        # Deduplicate by ID (keep the first inference for each ID)
        seen_ids = set(known_ids)
        added_count = 0
        for uid, ms, matched_id, faces, verts, mb in new_inferences:
            if uid not in seen_ids:
                probe_entries[uid] = {
                    "meshsize": ms,
                    "mesh_block": "inferred",
                    "faced": True,
                    "note": f"Inferred from cluster match to {matched_id} (MS={ms}, {faces}f/{verts}v/MB={mb})",
                }
                seen_ids.add(uid)
                added_count += 1

        with open(str(PROBE_LOOKUP_PATH), "w", encoding="utf-8") as f:
            json.dump(probe_lookup, f, indent=2)

        print(f"\nApplied: {added_count} new entries written to {PROBE_LOOKUP_PATH}")
    elif do_apply:
        print("\nNo new entries to apply.")

    print(f"\nTotal entries in probe lookup: {len(probe_entries)}")
    print(SEP)
    print("DONE")

    return 0


if __name__ == "__main__":
    sys.exit(main())
