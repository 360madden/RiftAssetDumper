"""
Phase 21: Sibling-Aware Batch OBJ Export

Reads the Phase 19 sibling pairing map and exports OBJs for float2 position
meshes using their paired float3 sibling as the Z-source.

Uses `decode-nif-geometry --experimental-position-source` for each float2 mesh
in DIST=0 pairs (strongest evidence of same-entry sibling pairing).

Usage:
    python scripts/batch_export_sibling.py [--skip-build] [--dry-run] [--output-dir PATH]
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

SEP = "=" * 80
REPO_ROOT = Path(__file__).resolve().parents[1]
PAIRING_MAP_PATH = "Exports/phase19-sibling-pairing-map.json"
SOLUTION = REPO_ROOT / "RiftAssetDumper.slnx"


def build_project(skip_build: bool) -> bool:
    if skip_build:
        return True
    print("\nBuilding .NET project...")
    result = subprocess.run(
        ["dotnet", "build", SOLUTION, "--nologo"],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        print("BUILD FAILED:")
        print(result.stderr[-500:] if result.stderr else "Unknown error")
        return False
    print("Build OK")
    return True


def run_decode_geometry(
    asset_id: str,
    mesh_block: int,
    project_root: str,
    out_dir: str,
    dry_run: bool = False,
) -> dict:
    """Run decode-nif-geometry with experimental-position-source for one mesh."""
    # Use unique per-asset output directory to avoid overwrites (matches batch-export-264 convention)
    asset_out = os.path.join(out_dir, f"decode-nif-geometry-{asset_id}")
    cmd = [
        "dotnet", "run", "--project", "src/RiftAssetDumper/RiftAssetDumper.csproj",
        "--no-build", "--",
        "decode-nif-geometry",
        "--id", asset_id,
        "--mesh-block", str(mesh_block),
        "--experimental-position-source",
        "--export-obj",
        "--root", project_root,
        "--out", asset_out,
    ]

    if dry_run:
        return {"id": asset_id, "mb": mesh_block, "dry_run": True, "cmd": " ".join(cmd)}

    start = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        elapsed = time.time() - start
        success = result.returncode == 0
        return {
            "id": asset_id,
            "mb": mesh_block,
            "success": success,
            "elapsed": round(elapsed, 1),
            "stdout_last": result.stdout[-300:] if result.stdout else "",
            "stderr_last": result.stderr[-300:] if result.stderr else "",
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"id": asset_id, "mb": mesh_block, "success": False, "error": "TIMEOUT"}
    except Exception as e:
        return {"id": asset_id, "mb": mesh_block, "success": False, "error": str(e)}


def main() -> int:
    print(SEP)
    print("PHASE 22: SIBLING-AWARE BATCH OBJ EXPORT")
    print(SEP)

    # Parse args
    skip_build = "--skip-build" in sys.argv
    dry_run = "--dry-run" in sys.argv
    project_root = str(REPO_ROOT / "Source")
    out_dir = "Exports/obj-exports"
    for i, arg in enumerate(sys.argv):
        if arg == "--root" and i + 1 < len(sys.argv):
            project_root = sys.argv[i + 1]
        if arg == "--output-dir" and i + 1 < len(sys.argv):
            out_dir = sys.argv[i + 1]

    # Load pairing map
    if not os.path.exists(PAIRING_MAP_PATH):
        print(f"ERROR: Pairing map not found: {PAIRING_MAP_PATH}")
        print("Run build_sibling_pairing_v2.py first to generate it.")
        return 1

    with open(str(REPO_ROOT / PAIRING_MAP_PATH), encoding="utf-8") as f:
        pairing_map = json.load(f)

    pairs = pairing_map.get("pairs", [])
    summary = pairing_map.get("summary", {})

    print(f"\nLoaded {len(pairs)} sibling pairs from pairing map")
    print(f"  DIST=0 pairs: {summary.get('total_dist0_pairs', 0)}")
    print(f"  Float2 meshes: {summary.get('total_float2_meshes', 0)}")
    print(f"  Float3 meshes: {summary.get('total_float3_meshes', 0)}")

    # Ensure output directory exists
    os.makedirs(out_dir, exist_ok=True)

    # Build project if needed
    if not build_project(skip_build):
        return 1

    # Select pairs to export - start with DIST=0 pairs (strongest evidence)
    dist0_pairs = [p for p in pairs if p.get("distance") == 0]

    print(f"\nExporting {len(dist0_pairs)} DIST=0 pairs...")

    results: list[dict] = []

    for pair in dist0_pairs:
        if dry_run:
            print(f"\n  [DRY RUN] Would export: {pair['float2_id']} MB={pair['float2_mb']}")
            print(f"    (paired with float3 MB={pair['float3_mb']} in {pair['archive']})")
            results.append({
                "id": pair["float2_id"],
                "mb": pair["float2_mb"],
                "dry_run": True,
            })
            continue

        print(f"\n  Exporting: {pair['float2_id'][:16]} MB={pair['float2_mb']}", end=" ")
        print(f"(paired with MB={pair['float3_mb']}, archive={pair['archive']})", end=" ")
        sys.stdout.flush()

        result = run_decode_geometry(
            asset_id=pair["float2_id"],
            mesh_block=pair["float2_mb"],
            project_root=project_root,
            out_dir=out_dir,
        )
        results.append(result)

        if result.get("success"):
            print(f"OK ({result.get('elapsed', '?')}s)")
        else:
            print("FAILED")
            stderr = result.get("stderr_last", "")
            if stderr:
                lines = [line for line in stderr.split("\n") if line.strip()]
                last_line = lines[-1] if lines else "?"
                print(f"    Error: {last_line[:100]}")

    # Summary
    print(f"\n{SEP}")
    print("EXPORT RESULTS")
    print(SEP)

    if dry_run:
        print(f"\n  Dry run: {len(results)} pairs would be exported")
        print("  Run without --dry-run to execute")

        # Also show what would happen with distance>0 pairs
        dist_other = [p for p in pairs if p.get("distance", 999) > 0 and p.get("distance", 999) < 100]
        f2_ids = set(p["float2_id"] for p in dist0_pairs)
        total_f2 = len(f2_ids)
        print(f"\n  Total DIST=0 pair IDs: {total_f2}")
        print(f"  Remaining distance>0 pairs: {len(dist_other)}")
        return 0

    successes = [r for r in results if r.get("success")]
    failures = [r for r in results if not r.get("success")]

    print(f"\n  Total attempted: {len(results)}")
    print(f"  Succeeded: {len(successes)}")
    print(f"  Failed: {len(failures)}")

    if successes:
        avg_time = sum(r.get("elapsed", 0) for r in successes) / len(successes)
        print(f"  Avg export time: {avg_time:.1f}s")
        print(f"  Output dir: {os.path.abspath(out_dir)}")

    if failures:
        print("\n  Failed pairs:")
        for fail in failures:
            print(f"    {fail['id'][:16]} MB={fail['mb']}: {fail.get('error', 'exit=' + str(fail.get('returncode', '?')))}")

    print(SEP)
    print("DONE")

    return len(failures)


if __name__ == "__main__":
    sys.exit(main())
