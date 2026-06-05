"""
Phase 16: Build Concrete Sibling Pairing Map

For each MeshSize that has both float2 and float3 position meshes,
identify concrete sibling pairs (float2 source → float3 Z-source).

Uses the proven brace-counting streaming parser from analyze_z_source.py.
"""

import json
from collections import defaultdict


def extract_str_val(line):
    line = line.strip().rstrip(",")
    if ': "' in line:
        parts = line.split(': "', 1)
        return parts[1].rstrip('"')
    return None


def extract_int_val(line):
    line = line.strip().rstrip(",")
    if ": " in line:
        parts = line.split(": ", 1)
        return parts[1].strip()
    return None


# Load OBJ manifest
with open("Exports/obj-manifest-stage18.json", encoding="utf-8") as f:
    manifest = json.load(f)
obj_ids = set()
for entry in manifest["entries"]:
    obj_ids.add(entry["id"][:16])

print(f"OBJ IDs: {len(obj_ids)} unique")
print()

# ============================================================
# PASS 1: Collect ALL meshes with position roles
# Using line-by-line accumulation (IdPrefix appears before PrimaryRole)
# ============================================================

current_id = ""
current_mb = ""
current_role = ""
current_dgr = ""
current_meshsize = ""
current_payload = ""
current_body16 = ""
current_archive = ""
current_entry = ""

# Group by MeshSize: meshsize -> list of stream records
all_position_streams: defaultdict[str, list[dict]] = defaultdict(list)

with open("Exports/phase14-refreshed-inventory.jsonl", "rb") as f:
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

    # Only process position streams from OBJ IDs
    if current_id in obj_ids and "position" in current_role and current_meshsize:
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
            }
        )
        # Reset role to avoid double-counting within same record
        current_role = ""

print("Position streams collected by MeshSize:")
for ms in sorted(all_position_streams.keys(), key=lambda x: int(x) if x.isdigit() else 0):
    streams = all_position_streams[ms]
    f2 = sum(1 for s in streams if "float2" in s["dgr"])
    f3 = sum(1 for s in streams if "float3" in s["dgr"])
    print(f"  MeshSize={ms}: {len(streams)} total ({f2} float2, {f3} float3)")

# ============================================================
# PASS 2: Build sibling pairing map for shared MeshSizes
# ============================================================

shared_sizes = [
    ms
    for ms in all_position_streams
    if any("float2" in s["dgr"] for s in all_position_streams[ms])
    and any("float3" in s["dgr"] for s in all_position_streams[ms])
]

print(f"\nShared MeshSizes (float2 AND float3): {sorted(shared_sizes, key=lambda x: int(x) if x.isdigit() else 0)}")

print(f"\n{'=' * 80}")
print("CONCRETE SIBLING PAIRING MAP")
print(f"{'=' * 80}\n")

ms_pair_total = 0

for ms in sorted(shared_sizes, key=lambda x: int(x) if x.isdigit() else 0):
    streams = all_position_streams[ms]

    # Separate float2 and float3 meshes
    f2_meshes = [s for s in streams if "float2" in s["dgr"]]
    f3_meshes = [s for s in streams if "float3" in s["dgr"]]

    # Deduplicate by (id, mb) — one mesh may have multiple position records
    seen_f2: set[tuple[str, str]] = set()
    unique_f2: list[dict] = []
    for s in f2_meshes:
        key = (s["id"], s["mb"])
        if key not in seen_f2:
            seen_f2.add(key)
            unique_f2.append(s)

    seen_f3: set[tuple[str, str]] = set()
    unique_f3: list[dict] = []
    for s in f3_meshes:
        key = (s["id"], s["mb"])
        if key not in seen_f3:
            seen_f3.add(key)
            unique_f3.append(s)

    print(f"=== MeshSize {ms}: {len(unique_f2)} float2, {len(unique_f3)} float3 ===")

    # Group by archive for proximity analysis
    archive_groups: dict[str, dict[str, list]] = {}
    for mesh_list, dtype in [(unique_f2, "float2"), (unique_f3, "float3")]:
        for m in mesh_list:
            arch = m["archive"] or "unknown"
            if arch not in archive_groups:
                archive_groups[arch] = {"float2": [], "float3": []}
            archive_groups[arch][dtype].append(m)

    # For each archive, find possible sibling pairs
    pair_count = 0
    for arch, groups in sorted(archive_groups.items()):
        f2_in_arch = groups["float2"]
        f3_in_arch = groups["float3"]

        if f2_in_arch and f3_in_arch:
            # Sort by entry index for proximity matching
            f2_sorted = sorted(f2_in_arch, key=lambda x: int(x["entry"] or "0"))
            f3_sorted = sorted(f3_in_arch, key=lambda x: int(x["entry"] or "0"))

            # Simple greedy pairing: match by entry index proximity
            for f2_m in f2_sorted:
                f2_entry = int(f2_m["entry"] or "0")

                # Find nearest float3 entry
                best_f3 = None
                best_dist = float("inf")
                for f3_m in f3_sorted:
                    f3_entry = int(f3_m["entry"] or "0")
                    dist = abs(f2_entry - f3_entry)
                    if dist < best_dist:
                        best_dist = dist
                        best_f3 = f3_m

                if best_f3 and best_dist < 100:  # within 100 entries = strong proximity
                    pair_count += 1
                    print(f"  Pair #{pair_count}:")
                    print(f"    FLOAT2: {f2_m['id'][:16]} MB={f2_m['mb']} entry={f2_entry} payload={f2_m['payload']}")
                    print(
                        f"    FLOAT3: {best_f3['id'][:16]} MB={best_f3['mb']} entry={f3_entry} payload={best_f3['payload']}"
                    )
                    print(f"    Archive: {arch}, distance={best_dist}")
                    # Show body16 if available
                    if f2_m.get("body16"):
                        print(f"    F2 body16: {f2_m['body16'][:40]}")
                    if best_f3.get("body16"):
                        print(f"    F3 body16: {best_f3['body16'][:40]}")
                    print()

            # If we couldn't pair all, note it
            unpaired = len(f2_sorted) - pair_count
            if unpaired > 0:
                print(f"  ({unpaired} float2 meshes unpaired in {arch})")

    if pair_count == 0:
        print(f"  No archive-close pairs found across {len(archive_groups)} archives")
    print()
    ms_pair_total += pair_count

# ============================================================
# SUMMARY
# ============================================================

total_pairs = ms_pair_total

print(f"{'=' * 80}")
print("SIBLING PAIRING SUMMARY")
print(f"{'=' * 80}")
print(f"\nShared MeshSizes with both float2 and float3: {len(shared_sizes)}")
print(f"Total concrete sibling pairs (archive-close): {total_pairs}")
print()
print("Key insight: Sibling meshes share the same archive and have")
print("nearby entry indices. The float2 mesh provides XY data; the")
print("float3 mesh provides the missing Z. The OBJ exporter pairs")
print("them via NifPositionSourceSiblingAccumulator to produce full")
print("3D vertex data.")
