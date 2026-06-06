"""
Phase 31: Batch Export MB=6 — export canonical faced geometry block for all float2 IDs

MB=6 is the canonical faced geometry block across MeshSizes 240-361.
36 float2 IDs in the pairing map are missing MB=6 exports (they were only
exported at their sibling-paired float2 mesh blocks like MB=7, 27, 8).

Targets:
  - MS=301 MB=6: 1 ID (likely faced — MS=301 MB=6 is 100% faced)
  - MS=305 MB=6: 20 IDs (likely faced — MS=305 MB=6 is 100% faced)
  - MS=465 MB=6: 15 IDs (unknown — no MB=6 data for MS=465 yet)

Usage:
    python scripts/batch_export_mb6.py [--skip-build] [--dry-run] [--output-dir PATH]
"""

import json
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
    """Run decode-nif-geometry for one asset at MB=6 with --export-obj."""
    asset_out = str(out_dir / f"decode-nif-geometry-{asset_id}")
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
        return {"id": asset_id, "mb": mesh_block, "dry_run": True}

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
    print("PHASE 31: BATCH EXPORT MB=6 — CANONICAL FACED GEOMETRY BLOCK")
    print(SEP)

    # Parse args
    skip_build = "--skip-build" in sys.argv
    dry_run = "--dry-run" in sys.argv
    project_root = "C:/Program Files (x86)/Glyph/Games/RIFT/Live"
    out_dir = REPO_ROOT / "Exports" / "mb6-exports"
    for i, arg in enumerate(sys.argv):
        if arg == "--root" and i + 1 < len(sys.argv):
            project_root = sys.argv[i + 1]
        if arg == "--output-dir" and i + 1 < len(sys.argv):
            out_dir = Path(sys.argv[i + 1])

    # Load pairing map
    pairing_map_path = REPO_ROOT / PAIRING_MAP_PATH
    if not pairing_map_path.exists():
        print(f"ERROR: Pairing map not found: {pairing_map_path}")
        return 1

    with open(str(pairing_map_path), encoding="utf-8") as f:
        pairing_map = json.load(f)

    pairs = pairing_map.get("pairs", [])

    # Build float2 info
    float2_info = {}
    for p in pairs:
        f2_id = p.get("float2_id")
        ms = p.get("meshsize")
        if f2_id and f2_id not in float2_info:
            float2_info[f2_id] = {"ms": ms, "pairs": 0}
        if f2_id:
            float2_info[f2_id]["pairs"] += 1

    # Check which float2 IDs already have MB=6 exports
    manifest_path = REPO_ROOT / "Exports" / "export-manifest.json"
    mb6_exported = set()
    if manifest_path.exists():
        with open(str(manifest_path), encoding="utf-8") as f:
            manifest = json.load(f)
        for e in manifest.get("entries", []):
            aid = e.get("asset_id")
            mb = e.get("mesh_block")
            if aid and mb == "6":
                mb6_exported.add(aid)

    # Find missing MB=6 targets
    targets = {}
    for fid, info in sorted(float2_info.items()):
        if fid not in mb6_exported:
            targets[fid] = info

    print(f"\nFound {len(targets)} float2 IDs missing MB=6 exports:")
    for ms in sorted(set(t["ms"] for t in targets.values())):
        count = sum(1 for t in targets.values() if t["ms"] == ms)
        print(f"  MS={ms}: {count} IDs")

    if not targets:
        print("\nAll float2 IDs already have MB=6 exports. Nothing to do.")
        return 0

    # Ensure output directory exists
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build project if needed
    if not build_project(skip_build):
        return 1

    # Export each target at MB=6
    results: list[dict] = []

    for fid, info in sorted(targets.items()):
        ms = info["ms"]

        if dry_run:
            print(f"\n  [DRY RUN] Would export: {fid} MB=6 (MS={ms})")
            results.append({"id": fid, "mb": 6, "dry_run": True})
            continue

        print(f"\n  Exporting: {fid[:16]} MB=6 MS={ms}", end=" ")
        sys.stdout.flush()

        result = run_decode_geometry(
            asset_id=fid,
            mesh_block=6,
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
        print(f"\n  Dry run: {len(results)} IDs would be exported at MB=6")
        return 0

    successes = [r for r in results if r.get("success")]
    failures = [r for r in results if not r.get("success")]

    print(f"\n  Total attempted: {len(results)}")
    print(f"  Succeeded: {len(successes)}")
    print(f"  Failed: {len(failures)}")

    if successes:
        avg_time = sum(r.get("elapsed", 0) for r in successes) / len(successes)
        print(f"  Avg export time: {avg_time:.1f}s")
        print(f"  Output dir: {out_dir}")

    if failures:
        print("\n  Failed IDs:")
        for fail in failures:
            print(
                f"    {fail['id'][:16]} MB={fail['mb']}: {fail.get('error', 'exit=' + str(fail.get('returncode', '?')))}"
            )

    print(SEP)
    print("DONE")

    return len(failures)


if __name__ == "__main__":
    sys.exit(main())
