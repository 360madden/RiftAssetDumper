"""Live game NIF discovery pipeline.

Usage:
    python scripts/live_inventory.py [--re-extract]

Scans the live RIFT game archives for NIF files, runs the C#
inventory pipeline, and reports @264-indexed mesh candidates.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

LIVE_ROOT = "C:/Program Files (x86)/Glyph/Games/RIFT/Live"
LIVE_NIFS = "Exports/live-nifs"
EXTRACTED = "Exports/extracted-top260"


def re_extract_with_original_names():
    """Re-extract NIFs but preserve original filenames for manifest lookup."""
    dst_root = Path(LIVE_NIFS) / "Assets"
    dst_root.mkdir(parents=True, exist_ok=True)

    copied = 0
    for bundle_dir in sorted(os.listdir(EXTRACTED)):
        bundle_path = Path(EXTRACTED) / bundle_dir / "model"
        if not bundle_path.is_dir():
            continue
        for f in os.listdir(bundle_path):
            if f.endswith(".nif"):
                src = bundle_path / f
                dst = dst_root / f
                if not dst.exists():
                    shutil.copy2(str(src), str(dst))
                    copied += 1
    print(f"Re-extracted {copied} NIF files with original names to {dst_root}")
    return copied


def run_inventory():
    """Run the C# mesh-binding inventory on the live NIFs."""
    result = subprocess.run(
        [
            "dotnet",
            "run",
            "--project",
            "src/RiftAssetDumper",
            "--no-build",
            "--",
            "inventory-nif-mesh-bindings",
            "--root",
            LIVE_NIFS,
            "--out",
            "Exports/live-mesh-binding-inventory.json",
            "--limit",
            "100",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr[-500:])
    return result.returncode == 0


def check_for_264():
    """Check the live inventory for @264 indexed meshes."""
    inv_path = Path("Exports/live-mesh-binding-inventory.json")
    if not inv_path.exists():
        print("Inventory file not found!")
        return

    with open(inv_path, encoding="utf-8-sig") as f:
        data = json.load(f)

    print("\n=== LIVE INVENTORY RESULTS ===")
    print(f"NiMesh blocks: {data.get('MeshBlockCount', '?')}")
    print(f"Attribute sets: {len(data.get('TopAttributeSets', []))}")

    # Check for @264
    fitness = data.get("TopAttributeExtraMappingFitness", [])
    found_264 = []
    for f_item in fitness:
        pattern = f_item.get("Pattern", "")
        if "@264" in pattern:
            vc = f_item.get("VertexCount", "?")
            count = f_item.get("Count", "?")
            samples = f_item.get("Samples", [])
            ids = [s.get("IdPrefix", "?") for s in samples[:5]]
            print(f"\n  @264 FOUND: vc={vc} count={count} ids={ids}")
            found_264.append({"vc": vc, "count": count, "ids": ids})

    if not found_264:
        print("\n  No @264-indexed meshes found in live-extracted set.")

    return found_264


def main():
    re_extract = "--re-extract" in sys.argv

    if re_extract:
        print("=== Re-extracting NIFs with original filenames ===")
        count = re_extract_with_original_names()
        if count == 0:
            print("No NIFs found in extracted bundles!")
            sys.exit(1)

        # Copy manifest files
        for mf in ["assets64.manifest", "manifest64.txt"]:
            shutil.copy2(f"{LIVE_ROOT}/{mf}", f"{LIVE_NIFS}/{mf}")
        print("Copied manifest files")

    print("\n=== Running C# mesh-binding inventory ===")
    success = run_inventory()

    if success:
        print("\n=== Checking for @264 candidates ===")
        check_for_264()
    else:
        print("Inventory pipeline failed - may need to rebuild")


if __name__ == "__main__":
    main()
