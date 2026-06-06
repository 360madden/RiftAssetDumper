"""
Phase 49: Batch Export Position-Only — export all pos-only OBJs with fan fallback faces

Uses the triangle fan fallback (--experimental-position-source --write-obj) to generate
approximate fan faces for all 84 position-only OBJs across 11 MeshSize families.

Usage:
    python scripts/batch_export_pos_only.py [--skip-build] [--dry-run] [--families FAMILIES]
                                            [--output-dir PATH] [--limit N]

    --families: comma-separated list of MeshSizes to export (e.g., "193,197,214")
    --limit: max number of OBJs to export (for testing)
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SEP = "=" * 80
REPO_ROOT = Path(__file__).resolve().parents[1]
SOLUTION = REPO_ROOT / "RiftAssetDumper.slnx"
MANIFEST_PATH = REPO_ROOT / "Exports" / "export-manifest.json"
PROBE_LOOKUP_PATH = REPO_ROOT / "Exports" / "probe-meshsize-lookup.json"

# Regex to extract 16-char hex asset ID from OBJ file paths
_ASSET_ID_RE = re.compile(r"([0-9a-f]{16})", re.IGNORECASE)


def build_project(skip_build: bool) -> bool:
    if skip_build:
        return True
    print("\nBuilding .NET project...")
    result = subprocess.run(
        ["dotnet", "build", str(SOLUTION), "--nologo"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        print("BUILD FAILED:")
        print(result.stderr[-500:] if result.stderr else "Unknown error")
        return False
    print("Build OK")
    return True


def load_manifest() -> dict:
    with open(str(MANIFEST_PATH), encoding="utf-8") as f:
        return json.load(f)


def load_probe_lookup() -> dict:
    if PROBE_LOOKUP_PATH.exists():
        with open(str(PROBE_LOOKUP_PATH), encoding="utf-8") as f:
            return json.load(f)
    return {}


def extract_asset_id(path: str) -> str | None:
    """Extract the first 16-char hex asset ID from a file path."""
    m = _ASSET_ID_RE.search(path)
    return m.group(1).lower() if m else None


def get_pos_only_targets(
    limit: int | None = None,
    families_filter: set[int] | None = None,
) -> list[dict]:
    """Get all position-only targets from export manifest and probe lookup."""
    manifest = load_manifest()
    probe_lookup = load_probe_lookup()

    entries = manifest.get("entries", [])
    targets: list[dict] = []

    for entry in entries:
        # Extract asset ID from path
        path = entry.get("path", "")
        aid = entry.get("asset_id") or extract_asset_id(path)
        if not aid:
            continue

        # Determine if position-only: faces == 0
        faces = entry.get("faces", 0) or entry.get("face_count", 0) or 0
        if faces > 0:
            continue

        # Get mesh block (stored as string in manifest)
        mesh_block_str = entry.get("mesh_block")
        if not mesh_block_str:
            continue
        try:
            mesh_block = int(mesh_block_str)
        except ValueError, TypeError:
            continue

        # Get mesh size from sibling_pair (or other fields)
        mesh_size = None
        pair = entry.get("sibling_pair")
        if isinstance(pair, dict):
            mesh_size = pair.get("mesh_size")
        if mesh_size is None:
            mesh_size = entry.get("mesh_size")

        # Apply families filter
        if families_filter and (mesh_size is None or mesh_size not in families_filter):
            continue

        # Override mesh_block from probe lookup if available
        if probe_lookup:
            p_entry = probe_lookup.get("entries", {}).get(aid, {})
            p_mb = p_entry.get("mesh_block")
            if p_mb is not None:
                try:
                    p_mb_int = int(p_mb)
                    if p_mb_int != mesh_block:
                        print(f"    [debug] {aid[:16]}: manifest MB={mesh_block} overridden by probe MB={p_mb_int}")
                        mesh_block = p_mb_int
                except ValueError, TypeError:
                    pass

        targets.append(
            {
                "id": aid,
                "mesh_size": mesh_size,
                "mesh_block": mesh_block,
            }
        )

    # Deduplicate by (id, mesh_block)
    seen: set[tuple[str, int]] = set()
    unique: list[dict] = []
    for t in targets:
        key = (t["id"], t["mesh_block"])
        if key not in seen:
            seen.add(key)
            unique.append(t)

    # Sort by mesh size then id
    unique.sort(key=lambda t: (t["mesh_size"] or 0, t["id"]))

    if limit:
        unique = unique[:limit]

    return unique


def export_mesh(
    asset_id: str,
    mesh_block: int,
    mesh_size: int | None,
    project_root: str,
    out_dir: str,
    dry_run: bool = False,
) -> dict:
    """Export one pos-only mesh with fan fallback faces."""
    asset_out = os.path.join(out_dir, f"posonly-{asset_id}-mb{mesh_block}")
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
        "--write-obj",
        "--root",
        project_root,
        "--out",
        asset_out,
    ]

    if dry_run:
        return {"id": asset_id, "mb": mesh_block, "mesh_size": mesh_size, "dry_run": True}

    start = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        elapsed = time.time() - start
        success = result.returncode == 0

        # Extract face count from stderr or stdout
        # (e.g., "generated 28 fallback fan faces from 30 vertices")
        face_count = 0
        for output in [result.stdout or "", result.stderr or ""]:
            for line in output.split("\n"):
                line_lower = line.lower().strip()
                m = re.search(r"(\d+)\s+fallback fan faces", line_lower)
                if m:
                    face_count = int(m.group(1))
                    break
            if face_count > 0:
                break

        return {
            "id": asset_id,
            "mb": mesh_block,
            "mesh_size": mesh_size,
            "success": success,
            "elapsed": round(elapsed, 1),
            "face_count": face_count,
            "stdout": result.stdout[-500:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"id": asset_id, "mb": mesh_block, "mesh_size": mesh_size, "success": False, "error": "TIMEOUT"}
    except Exception as e:
        return {"id": asset_id, "mb": mesh_block, "mesh_size": mesh_size, "success": False, "error": str(e)}


def main() -> int:
    print(SEP)
    print("PHASE 49: BATCH EXPORT POSITION-ONLY OBJs (FAN FALLBACK FACES)")
    print(SEP)

    # Parse args
    skip_build = "--skip-build" in sys.argv
    dry_run = "--dry-run" in sys.argv
    limit: int | None = None
    families_filter: set[int] | None = None
    project_root = str(REPO_ROOT / "Source")
    out_dir = "Exports/posonly-fan-exports"

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--skip-build":
            skip_build = True
        elif args[i] == "--dry-run":
            dry_run = True
        elif args[i] == "--root" and i + 1 < len(args):
            project_root = args[i + 1]
            i += 1
        elif args[i] == "--output-dir" and i + 1 < len(args):
            out_dir = args[i + 1]
            i += 1
        elif args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 1
        elif args[i] == "--families" and i + 1 < len(args):
            families_filter = set(int(x.strip()) for x in args[i + 1].split(","))
            i += 1
        i += 1

    # Load pos-only targets
    targets = get_pos_only_targets(limit=limit, families_filter=families_filter)

    if not targets:
        print("\nNo position-only targets found. Check export-manifest.json.")
        return 0

    # Group by mesh size for summary
    by_ms: dict[int, list[dict]] = {}
    for t in targets:
        ms = t["mesh_size"] or 0
        by_ms.setdefault(ms, []).append(t)

    print(f"\nFound {len(targets)} pos-only OBJs across {len(by_ms)} families:")
    for ms in sorted(by_ms):
        print(f"  MS={ms}: {len(by_ms[ms])} OBJs")
    print()

    if dry_run:
        print("DRY RUN — no exports will be performed")
        return 0

    # Build project
    if not build_project(skip_build):
        return 1

    # Ensure output directory exists
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    # Export each target
    results: list[dict] = []
    total = len(targets)

    for idx, target in enumerate(targets, 1):
        aid = target["id"]
        mb = target["mesh_block"]
        ms = target["mesh_size"]

        print(f"  [{idx}/{total}] {aid[:16]} MB={mb} MS={ms} ...", end=" ")
        sys.stdout.flush()

        result = export_mesh(
            asset_id=aid,
            mesh_block=mb,
            mesh_size=ms,
            project_root=project_root,
            out_dir=out_dir,
        )
        results.append(result)

        if result.get("success"):
            faces = result.get("face_count", 0)
            elapsed = result.get("elapsed", "?")
            print(f"OK ({faces}f, {elapsed}s)")
        else:
            err = result.get("error", f"exit={result.get('returncode', '?')}")
            print(f"FAILED ({err})")

    # Summary
    print(f"\n{SEP}")
    print("EXPORT RESULTS")
    print(SEP)

    successes = [r for r in results if r.get("success")]
    failures = [r for r in results if not r.get("success")]
    total_faces = sum(r.get("face_count", 0) for r in successes)
    faced_count = sum(1 for r in successes if r.get("face_count", 0) > 0)

    print(f"\n  Total attempted: {len(results)}")
    print(f"  Succeeded: {len(successes)}")
    print(f"  Failed: {len(failures)}")
    print(f"  OBJs with fan faces: {faced_count}")
    print(f"  Total fan faces generated: {total_faces}")

    if successes:
        avg_time = sum(r.get("elapsed", 0) for r in successes) / len(successes)
        print(f"  Avg export time: {avg_time:.1f}s {SEP}")
        print(f"  Output dir: {os.path.abspath(out_dir)}")

    # Per-family breakdown (mesh_size is now in each result)
    if successes:
        print("\n  Per-family breakdown:")
        family_stats: dict[int, dict] = {}
        for r in successes:
            ms = r.get("mesh_size") or 0
            stats = family_stats.setdefault(ms, {"total": 0, "with_faces": 0, "faces": 0})
            stats["total"] += 1
            if r.get("face_count", 0) > 0:
                stats["with_faces"] += 1
                stats["faces"] += r["face_count"]

        for ms in sorted(family_stats):
            s = family_stats[ms]
            print(f"    MS={ms}: {s['with_faces']}/{s['total']} with faces, {s['faces']} total faces")

    if failures:
        print("\n  Failed IDs:")
        for fail in failures:
            print(f"    {fail['id'][:16]} MB={fail['mb']}: {fail.get('error', '?')}")

    # Write results JSON
    results_path = os.path.join(out_dir, "batch-results.json")
    summary = {
        "total_attempted": len(results),
        "total_succeeded": len(successes),
        "total_failed": len(failures),
        "total_faces_generated": total_faces,
        "objs_with_faces": faced_count,
        "per_family": {str(ms): stats for ms, stats in sorted(family_stats.items())},
        "failures": [{"id": f["id"], "mb": f["mb"], "error": f.get("error", "?")} for f in failures],
    }
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Results written to: {results_path}")

    print("DONE")

    return len(failures)


if __name__ == "__main__":
    sys.exit(main())
