"""
Phase 30: Batch Export Float3 — export the float3 side of sibling pairs

The float3 meshes in each sibling pair carry full XYZ position data and
potentially index streams. Exporting them directly (not paired as a Z-source)
should produce faced OBJs for MeshSizes where MB=6/7 has index streams.

Targets 9 unexported float3 IDs from the Phase 19 pairing map.

Usage:
    python scripts/batch_export_float3.py [--skip-build] [--dry-run] [--output-dir PATH]
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
    result = subprocess.run(["dotnet", "build", SOLUTION, "--nologo"], capture_output=True, text=True, timeout=120)
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
    """Run decode-nif-geometry for one float3 mesh (with --export-obj for faced output)."""
    asset_out = os.path.join(out_dir, f"decode-nif-geometry-{asset_id}")
    cmd = [
        "dotnet",
        "run",
        "--project",
        "src/RiftAssetDumper/RiftAssetDumper.csproj",
        "--no-build",
        "--",
        "decode-nif-geometry",
        "--id",
        asset_id,
        "--mesh-block",
        str(mesh_block),
        "--experimental-position-source",
        "--export-obj",
        "--root",
        project_root,
        "--out",
        asset_out,
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
    print("PHASE 30: BATCH EXPORT FLOAT3 — EXPORT FLOAT3 SIDE OF SIBLING PAIRS")
    print(SEP)

    # Parse args
    skip_build = "--skip-build" in sys.argv
    dry_run = "--dry-run" in sys.argv
    project_root = "C:/Program Files (x86)/Glyph/Games/RIFT/Live"
    out_dir = "Exports/float3-exports"
    for i, arg in enumerate(sys.argv):
        if arg == "--root" and i + 1 < len(sys.argv):
            project_root = sys.argv[i + 1]
        if arg == "--output-dir" and i + 1 < len(sys.argv):
            out_dir = sys.argv[i + 1]

    # Load pairing map
    if not os.path.exists(PAIRING_MAP_PATH):
        print(f"ERROR: Pairing map not found: {PAIRING_MAP_PATH}")
        return 1

    with open(str(REPO_ROOT / PAIRING_MAP_PATH), encoding="utf-8") as f:
        pairing_map = json.load(f)

    pairs = pairing_map.get("pairs", [])

    # Find unexported float3 IDs by cross-referencing with manifest
    manifest_path = REPO_ROOT / "Exports" / "export-manifest.json"
    exported_ids = set()
    if manifest_path.exists():
        with open(str(manifest_path), encoding="utf-8") as f:
            manifest = json.load(f)
        for e in manifest.get("entries", []):
            aid = e.get("asset_id")
            if aid:
                exported_ids.add(aid)

    # Build unique float3 targets (id, mb, meshsize) that are NOT already exported
    float3_targets: dict = {}  # id -> (mb, meshsize, count_pairs)
    for p in pairs:
        f3_id = p.get("float3_id")
        f3_mb = p.get("float3_mb")
        ms = p.get("meshsize")
        if f3_id and f3_id not in exported_ids:
            if f3_id not in float3_targets:
                float3_targets[f3_id] = {"mb": f3_mb, "meshsize": ms, "count": 0}
            float3_targets[f3_id]["count"] += 1

    print(f"\nFound {len(float3_targets)} unexported float3 targets:")
    for fid, info in sorted(float3_targets.items()):
        print(f"  {fid}: MB={info['mb']}, MS={info['meshsize']}, {info['count']} pair(s)")

    if not float3_targets:
        print("\nAll float3 IDs already exported. Nothing to do.")
        return 0

    # Ensure output directory exists
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    # Build project if needed
    if not build_project(skip_build):
        return 1

    # Export each float3 target
    results: list[dict] = []

    for fid, info in sorted(float3_targets.items()):
        mb = info["mb"]
        ms = info["meshsize"]

        if dry_run:
            print(f"\n  [DRY RUN] Would export: {fid} MB={mb} (MS={ms})")
            results.append({"id": fid, "mb": mb, "dry_run": True})
            continue

        print(f"\n  Exporting: {fid[:16]} MB={mb} MS={ms}", end=" ")
        sys.stdout.flush()

        result = run_decode_geometry(
            asset_id=fid,
            mesh_block=mb,
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
        print(f"\n  Dry run: {len(results)} float3 IDs would be exported")
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
        print("\n  Failed float3 IDs:")
        for fail in failures:
            print(
                f"    {fail['id'][:16]} MB={fail['mb']}: {fail.get('error', 'exit=' + str(fail.get('returncode', '?')))}"
            )

    print(SEP)
    print("DONE")

    return len(failures)


if __name__ == "__main__":
    sys.exit(main())
