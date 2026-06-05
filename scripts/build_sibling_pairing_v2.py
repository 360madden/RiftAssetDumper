"""
Phase 19: Comprehensive Sibling Pairing Database

Builds a comprehensive sibling pairing database by:
1. Scanning ALL position streams (not just OBJ-exported ones)
2. Detecting float2 positions via DescriptorGuidedRole (descriptor-float2-uv)
3. Detecting float3 positions via DescriptorGuidedRole or role naming
4. Building archive-proximity sibling pairs for ALL shared MeshSizes
5. Cross-referencing pairings across the full copied set
6. Writing structured JSON output to Exports/ for reuse

Archive proximity is a heuristic: greedy nearest-entry matching within each
archive, so some float3 meshes may be paired with multiple float2 meshes (1:N).
DIST=0 pairs (same archive entry) are the strongest evidence.

Usage: python scripts/build_sibling_pairing_v2.py
Output: stdout analysis + Exports/phase19-sibling-pairing-map.json
"""

import json
import os
import sys
from collections import defaultdict

SEP = "=" * 80
INVENTORY_PATH = "Exports/phase14-refreshed-inventory.jsonl"
OUTPUT_PATH = "Exports/phase19-sibling-pairing-map.json"


def extract_str_val(line: str) -> str | None:
    line = line.strip().rstrip(",")
    if ': "' in line:
        parts = line.split(': "', 1)
        return parts[1].rstrip('"')
    return None


def extract_int_val(line: str) -> str | None:
    line = line.strip().rstrip(",")
    if ": " in line:
        parts = line.split(": ", 1)
        return parts[1].strip()
    return None


def main() -> int:
    print(SEP)
    print("PHASE 18/19: COMPREHENSIVE SIBLING PAIRING DATABASE")
    print(SEP)

    # State machine
    current_id = ""
    current_mb = ""
    current_role = ""
    current_dgr = ""
    current_meshsize = ""
    current_payload = ""
    current_body16 = ""
    current_archive = ""
    current_entry = ""

    all_position_streams: dict[str, list[dict]] = defaultdict(list)

    with open(INVENTORY_PATH, "rb") as f:
        raw = f.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    raw_lines: list[bytes] = raw.split(b"\r\n")

    print(f"Processing {len(raw_lines)} lines...")

    for line_bytes in raw_lines:
        line = line_bytes.decode("utf-8", errors="replace")
        stripped = line.strip()

        if stripped.startswith('"IdPrefix":'):
            val = extract_str_val(stripped)
            if val:
                current_id = val
        elif stripped.startswith('"MeshBlockIndex":'):
            val = extract_int_val(stripped)
            if val:
                current_mb = val
        elif stripped.startswith('"PrimaryRole":'):
            val = extract_str_val(stripped)
            if val:
                current_role = val
        elif stripped.startswith('"DescriptorGuidedRole":'):
            val = extract_str_val(stripped)
            if val:
                current_dgr = val
        elif stripped.startswith('"MeshSize":'):
            val = extract_int_val(stripped)
            if val:
                current_meshsize = val
        elif stripped.startswith('"DeclaredPayloadBytes":'):
            val = extract_int_val(stripped)
            if val:
                current_payload = val
        elif stripped.startswith('"BodyFirst16":'):
            val = extract_str_val(stripped)
            if val:
                current_body16 = val
        elif stripped.startswith('"ArchiveName":'):
            val = extract_str_val(stripped)
            if val:
                current_archive = val
        elif stripped.startswith('"EntryIndex":'):
            val = extract_int_val(stripped)
            if val:
                current_entry = val

        if current_id and "position" in current_role and current_meshsize:
            is_f2 = "float2" in current_dgr
            is_f3 = "float3" in current_dgr
            all_position_streams[current_meshsize].append(
                {
                    "id": current_id,
                    "mb": current_mb,
                    "role": current_role,
                    "dgr": current_dgr,
                    "meshsize": current_meshsize,
                    "payload": current_payload,
                    "body16": current_body16,
                    "archive": current_archive,
                    "entry": current_entry,
                    "pos_type": "float2" if is_f2 else ("float3" if is_f3 else "other"),
                }
            )
            current_role = ""

    print()
    print("Position streams collected by MeshSize:")
    total_f2 = 0
    total_f3 = 0
    for ms in sorted(all_position_streams.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        streams = all_position_streams[ms]
        f2 = sum(1 for s in streams if s["pos_type"] == "float2")
        f3 = sum(1 for s in streams if s["pos_type"] == "float3")
        total_f2 += f2
        total_f3 += f3
        if f2 > 0 or f3 > 0:
            print(f"  MeshSize={ms}: {len(streams)} total ({f2} float2, {f3} float3)")

    print(f"\n  TOTALS: {len(all_position_streams)} MeshSizes, {total_f2} float2, {total_f3} float3")

    # PASS 2: Shared MeshSizes
    shared_sizes = [
        ms
        for ms in all_position_streams
        if any(s["pos_type"] == "float2" for s in all_position_streams[ms])
        and any(s["pos_type"] == "float3" for s in all_position_streams[ms])
    ]
    print(f"\nShared MeshSizes (have BOTH float2 AND float3): {len(shared_sizes)}")
    for ms in sorted(shared_sizes, key=lambda x: int(x) if x.isdigit() else 0):
        streams = all_position_streams[ms]
        f2 = sum(1 for s in streams if s["pos_type"] == "float2")
        f3 = sum(1 for s in streams if s["pos_type"] == "float3")
        print(f"  MeshSize {ms}: {f2} float2, {f3} float3")

    # PASS 3: Build sibling pairing map
    print(f"\n{SEP}")
    print("COMPREHENSIVE SIBLING PAIRING MAP (FULL INVENTORY)")
    print(SEP)

    total_pairs = 0
    dist0_pairs = 0
    total_f2_meshes = 0
    total_f3_meshes = 0
    all_pairs: list[dict] = []

    for ms in sorted(shared_sizes, key=lambda x: int(x) if x.isdigit() else 0):
        streams = all_position_streams[ms]
        f2_meshes = [s for s in streams if s["pos_type"] == "float2"]
        f3_meshes = [s for s in streams if s["pos_type"] == "float3"]

        # Deduplicate
        seen_f2: set[tuple[str, str, str]] = set()
        unique_f2: list[dict] = []
        for s in f2_meshes:
            key = (s["id"], s["mb"], s["archive"])
            if key not in seen_f2:
                seen_f2.add(key)
                unique_f2.append(s)

        seen_f3: set[tuple[str, str, str]] = set()
        unique_f3: list[dict] = []
        for s in f3_meshes:
            key = (s["id"], s["mb"], s["archive"])
            if key not in seen_f3:
                seen_f3.add(key)
                unique_f3.append(s)

        print(f"\n--- MeshSize {ms}: {len(unique_f2)} float2, {len(unique_f3)} float3 ---")
        total_f2_meshes += len(unique_f2)
        total_f3_meshes += len(unique_f3)

        archive_groups: dict[str, dict[str, list]] = defaultdict(lambda: {"float2": [], "float3": []})
        for m in unique_f2:
            archive_groups[m["archive"] or "unknown"]["float2"].append(m)
        for m in unique_f3:
            archive_groups[m["archive"] or "unknown"]["float3"].append(m)

        ms_pairs = 0
        ms_dist0 = 0
        for arch, groups in sorted(archive_groups.items()):
            f2_in_arch = groups["float2"]
            f3_in_arch = groups["float3"]
            if not f2_in_arch or not f3_in_arch:
                continue

            f2_sorted = sorted(f2_in_arch, key=lambda x: int(x["entry"] or "0"))
            f3_sorted = sorted(f3_in_arch, key=lambda x: int(x["entry"] or "0"))

            for f2_m in f2_sorted:
                f2_entry = int(f2_m["entry"] or "0")
                best_f3 = None
                best_dist = float("inf")
                for f3_m in f3_sorted:
                    f3_entry = int(f3_m["entry"] or "0")
                    dist = abs(f2_entry - f3_entry)
                    if dist < best_dist:
                        best_dist = dist
                        best_f3 = f3_m

                if best_f3 and best_dist < 100:
                    ms_pairs += 1
                    total_pairs += 1
                    f3_entry = int(best_f3["entry"] or "0")
                    is_dist0 = best_dist == 0
                    if is_dist0:
                        ms_dist0 += 1
                        dist0_pairs += 1

                    tag = " (SAME ENTRY)" if is_dist0 else ""
                    print(f"  Pair #{ms_pairs}:{tag}")
                    print(f"    FLOAT2: {f2_m['id'][:16]} MB={f2_m['mb']} entry={f2_entry}")
                    print(f"    FLOAT3: {best_f3['id'][:16]} MB={best_f3['mb']} entry={f3_entry}")
                    print(f"    Archive: {arch}, distance={best_dist}")
                    if f2_m.get("body16"):
                        print(f"    F2 first16: {f2_m['body16'][:40]}")
                    if best_f3.get("body16"):
                        print(f"    F3 first16: {best_f3['body16'][:40]}")

                    all_pairs.append(
                        {
                            "meshsize": int(ms),
                            "archive": arch,
                            "distance": best_dist,
                            "float2_id": f2_m["id"][:16],
                            "float2_mb": int(f2_m["mb"] or "0"),
                            "float2_entry": f2_entry,
                            "float2_payload": f2_m.get("payload", ""),
                            "float2_body16": (f2_m.get("body16", "") or "")[:40],
                            "float3_id": best_f3["id"][:16],
                            "float3_mb": int(best_f3["mb"] or "0"),
                            "float3_entry": f3_entry,
                            "float3_payload": best_f3.get("payload", ""),
                            "float3_body16": (best_f3.get("body16", "") or "")[:40],
                        }
                    )

        if ms_pairs == 0:
            print("  No archive-close pairs found")
            for arch, groups in sorted(archive_groups.items()):
                f2_in_arch = groups["float2"]
                f3_in_arch = groups["float3"]
                if f2_in_arch and not f3_in_arch:
                    print(f"  Float2 only in {arch}: {len(f2_in_arch)} meshes")
                if f3_in_arch and not f2_in_arch:
                    print(f"  Float3 only in {arch}: {len(f3_in_arch)} meshes")
        else:
            print(f"  [{ms_pairs} pairs, {ms_dist0} DIST=0 (same entry)]")

    # PASS 4: NIF-level sibling groups
    print(f"\n{SEP}")
    print("NIF-LEVEL SIBLING GROUP ANALYSIS")
    print(SEP)

    nif_groups: dict[str, list[dict]] = defaultdict(list)
    for _ms, streams in all_position_streams.items():
        for s in streams:
            nif_groups[s["id"]].append(s)

    multi_mesh_nifs = 0
    cross_type_nifs = 0
    cross_type_details: list[dict] = []

    for nif_id, records in nif_groups.items():
        if len(records) < 2:
            continue
        mesh_blocks = set(r["mb"] for r in records)
        if len(mesh_blocks) < 2:
            continue
        multi_mesh_nifs += 1
        types_in_nif = set(r["pos_type"] for r in records)
        if "float2" in types_in_nif and "float3" in types_in_nif:
            cross_type_nifs += 1
            entries = [
                {
                    "mb": r["mb"],
                    "pos_type": r["pos_type"],
                    "role": r["role"][:30],
                    "dgr": r["dgr"],
                    "meshsize": r["meshsize"],
                }
                for r in sorted(records, key=lambda x: int(x["mb"] or "0"))
            ]
            cross_type_details.append({"nif_id": nif_id[:16], "entries": entries})
            print(f"\n  NIF={nif_id[:16]} has BOTH float2 and float3 position streams:")
            for e in entries:
                print(f"    MB={e['mb']} type={e['pos_type']} role={e['role'][:30]} dgr={e['dgr']} ms={e['meshsize']}")

    print(f"\n  NIF files with multiple position-stream mesh blocks: {multi_mesh_nifs}")
    print(f"  NIF files with BOTH float2 and float3: {cross_type_nifs}")

    # Write JSON output
    output = {
        "schema": "phase19-sibling-pairing-map-v1",
        "generated_output_notice": "Generated from local copied RIFT assets. Keep under ignored Exports/.",
        "summary": {
            "mesh_sizes_scanned": len(all_position_streams),
            "shared_mesh_sizes": len(shared_sizes),
            "shared_mesh_sizes_list": sorted(shared_sizes, key=lambda x: int(x) if x.isdigit() else 0),
            "total_float2_meshes": total_f2_meshes,
            "total_float3_meshes": total_f3_meshes,
            "total_archive_close_pairs": total_pairs,
            "total_dist0_pairs": dist0_pairs,
            "nif_multi_block_meshes": multi_mesh_nifs,
            "nif_cross_type_meshes": cross_type_nifs,
        },
        "pairs": all_pairs,
        "cross_type_nifs": cross_type_details,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH) or ".", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Wrote JSON output: {OUTPUT_PATH}")

    # SUMMARY
    print(f"\n{SEP}")
    print("SUMMARY")
    print(SEP)
    print(f"  MeshSizes scanned: {len(all_position_streams)}")
    print(f"  Shared MeshSizes (float2+float3): {len(shared_sizes)}")
    print(f"  Total float2 position meshes: {total_f2_meshes}")
    print(f"  Total float3 position meshes: {total_f3_meshes}")
    print(f"  Total archive-close sibling pairs: {total_pairs}")
    print(f"    DIST=0 (same entry): {dist0_pairs}")
    print(f"    DIST=1-99 (archive-close): {total_pairs - dist0_pairs}")
    print(f"  NIF files with multiple position mesh blocks: {multi_mesh_nifs}")
    print(f"  NIF files with cross-type (f2+f3): {cross_type_nifs}")
    print(f"  JSON output: {OUTPUT_PATH}")
    print(SEP)
    print("DONE")

    return 0


if __name__ == "__main__":
    sys.exit(main())
