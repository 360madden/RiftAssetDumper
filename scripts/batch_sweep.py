#!/usr/bin/env python3
"""Batch-sweep runner: find unexported index-stream meshes and export OBJs.

Reads the mesh-binding inventory, identifies meshes with index streams
that haven't been exported yet, and runs decode-nif-geometry on each.

Usage:
    python scripts/batch_sweep.py                    # Dry-run: list candidates
    python scripts/batch_sweep.py --execute          # Export all candidates
    python scripts/batch_sweep.py --execute --limit 5  # Export first 5 only
    python scripts/batch_sweep.py --summary          # Show summary of all OBJs
    python scripts/batch_sweep.py --integrity-check  # Validate all OBJs
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path("C:/Program Files (x86)/Glyph/Games/RIFT/Live")
DEFAULT_OUT = REPO_ROOT / "Exports"
DEFAULT_PROJECT = REPO_ROOT / "src" / "RiftAssetDumper" / "RiftAssetDumper.csproj"
DEFAULT_SOLUTION = REPO_ROOT / "RiftAssetDumper.slnx"
DEFAULT_INVENTORY = DEFAULT_OUT / "nif-mesh-binding-inventory.json"


# ============================================================================
# Phase 1: Candidate discovery
# ============================================================================


def discover_candidates(
    inventory_path: Path,
    exported_dir: Path,
) -> list[dict[str, Any]]:
    """Find unexported meshes that have index streams.

    Returns list of candidate dicts with keys: id, meshBlock, meshSize,
    roles, payloads.
    """
    # Get already-exported asset IDs
    exported_ids: set[str] = set()
    for d in exported_dir.glob("decode-nif-geometry-*"):
        m = re.search(r"decode-nif-geometry-([0-9a-f]{16})", d.name)
        if m:
            exported_ids.add(m.group(1))

    # Load inventory
    with open(inventory_path, encoding="utf-8-sig") as f:
        data = json.load(f)

    role_groups = data.get("RoleGroups", [])
    if not role_groups:
        print("ERROR: No RoleGroups found in inventory.", file=sys.stderr)
        return []

    # Collect unexported samples with index streams
    raw: dict[tuple[str, int], dict[str, Any]] = {}
    for rg in role_groups:
        role = rg.get("Role", "")
        if "index" not in role.lower():
            continue
        for s in rg.get("Samples", []):
            ms = s.get("MeshSize", 0)
            aid = s.get("IdPrefix", "")
            mb = s.get("MeshBlockIndex", -1)
            if not aid or aid in exported_ids:
                continue
            stream = s.get("Stream", {})
            payload = stream.get("DeclaredPayloadBytes", 0)
            key = (aid, mb)
            if key not in raw:
                raw[key] = {
                    "id": aid,
                    "meshBlock": mb,
                    "meshSize": ms,
                    "roles": [],
                    "payloads": [],
                }
            raw[key]["roles"].append(role)
            raw[key]["payloads"].append(payload)

    # Build candidate list sorted by payload (largest first = likely most faces)
    candidates = sorted(
        raw.values(),
        key=lambda c: max(c["payloads"]) if c["payloads"] else 0,
        reverse=True,
    )
    return candidates


def print_candidates(candidates: list[dict[str, Any]]) -> None:
    """Pretty-print candidate list."""
    if not candidates:
        print("No unexported candidates with index streams found.")
        return

    by_size: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for c in candidates:
        by_size[c["meshSize"]].append(c)

    print(f"\n=== {len(candidates)} unexported candidates with index streams ===")
    print()
    for ms in sorted(by_size.keys()):
        group = by_size[ms]
        roles_set = set()
        for c in group:
            roles_set.update(c["roles"])
        print(f"  meshSize={ms}: {len(group)} candidates  roles={roles_set}")
        for c in group[:4]:
            payloads = c["payloads"][:3]
            roles = c["roles"][:3]
            print(f"    {c['id']} mesh#{c['meshBlock']}  payloads={payloads}  roles={roles}")
        if len(group) > 4:
            print(f"    ... and {len(group) - 4} more")
        print()


# ============================================================================
# Phase 2: Batch export
# ============================================================================


def export_candidate(
    candidate: dict[str, Any],
    project: Path,
    root: Path,
    out_dir: Path,
    skip_build: bool = False,
) -> dict[str, Any]:
    """Run decode-nif-geometry on a single candidate. Returns result dict."""
    asset_id: str = candidate["id"]
    mesh_block: int = candidate["meshBlock"]

    out_subdir = out_dir / f"decode-nif-geometry-{asset_id}-mesh{mesh_block}"

    result: dict[str, Any] = {
        "id": asset_id,
        "meshBlock": mesh_block,
        "meshSize": candidate["meshSize"],
        "status": "unknown",
    }

    try:
        # Build if needed
        solution = REPO_ROOT / "RiftAssetDumper.slnx"
        if not skip_build and solution.exists():
            build_result = subprocess.run(
                ["dotnet", "build", str(solution), "--nologo"],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            if build_result.returncode != 0:
                result["status"] = "BUILD_FAILED"
                result["error"] = build_result.stderr[-500:] if build_result.stderr else ""
                return result

        # Run decode-nif-geometry
        dotnet_args = [
            "run",
            "--project",
            str(project),
            "--",
            "decode-nif-geometry",
            "--root",
            str(root),
            "--id",
            asset_id,
            "--mesh-block",
            str(mesh_block),
            "--experimental-position-source",
            "--write-obj",
            "--out",
            str(out_subdir),
        ]

        proc = subprocess.run(
            ["dotnet", *dotnet_args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(REPO_ROOT),
        )

        if proc.returncode != 0:
            result["status"] = "DOTNET_FAILED"
            result["error"] = proc.stderr[-500:] if proc.stderr else f"exit {proc.returncode}"
            return result

        # Find the OBJ file
        obj_dir = out_subdir / "decode-nif-geometry"
        obj_path = obj_dir / f"decode-nif-geometry-mesh{mesh_block}.obj"

        if obj_path.exists():
            obj_size = obj_path.stat().st_size
            text = obj_path.read_text(encoding="utf-8", errors="ignore")
            v_count = text.count("\nv ") + (1 if text.startswith("v ") else 0)
            f_count = text.count("\nf ") + (1 if text.startswith("f ") else 0)
            sha = hashlib.sha256(obj_path.read_bytes()).hexdigest()

            result["status"] = "OK"
            result["vertices"] = v_count
            result["faces"] = f_count
            result["objBytes"] = obj_size
            result["sha256"] = sha
            result["path"] = str(obj_path)
        else:
            result["status"] = "NO_OBJ"
            result["error"] = f"OBJ not found at {obj_path}"

    except Exception as exc:
        result["status"] = "ERROR"
        result["error"] = str(exc)

    return result


def batch_export(
    candidates: list[dict[str, Any]],
    project: Path,
    root: Path,
    out_dir: Path,
    limit: int = 0,
    skip_build: bool = False,
) -> list[dict[str, Any]]:
    """Export a batch of candidates. Returns list of result dicts."""
    if limit and limit > 0:
        candidates = candidates[:limit]

    results: list[dict[str, Any]] = []
    total = len(candidates)

    print(f"\n{'=' * 60}")
    print(f"  Batch Sweep: {total} candidates")
    print(f"{'=' * 60}\n")

    for i, candidate in enumerate(candidates):
        aid = candidate["id"]
        mb = candidate["meshBlock"]
        ms = candidate["meshSize"]
        label = f"[{i + 1}/{total}] meshSize={ms} {aid} mesh#{mb}"
        print(f"  {label} ... ", end="", flush=True)

        result = export_candidate(candidate, project, root, out_dir, skip_build)
        results.append(result)

        status = result["status"]
        if status == "OK":
            marker = "[OK]"
            extra = f"  v={result.get('vertices', 0)} f={result.get('faces', 0)}  {result.get('objBytes', 0):,}B"
        else:
            marker = "[!!]"
            extra = f"  status={status}"

        print(f"{marker}{extra}")

    # Summary
    ok_count = sum(1 for r in results if r.get("status") == "OK")
    faced_count = sum(1 for r in results if r.get("status") == "OK" and r.get("faces", 0) > 0)
    total_faces = sum(r.get("faces", 0) for r in results)

    print(f"\n{'=' * 60}")
    print("  Batch Sweep Results")
    print(f"{'=' * 60}")
    print(f"  Exported: {ok_count}/{total}")
    print(f"  Faced OBJs: {faced_count}")
    print(f"  Total new faces: {total_faces}")
    print()

    return results


# ============================================================================
# Phase 3: OBJ integrity checker
# ============================================================================


def integrity_check(exported_dir: Path) -> list[dict[str, Any]]:
    """Validate all OBJs in the exported directory.

    Checks: SHA256, index bounds, NaN, negative indices, face format.
    Returns list of issue dicts.
    """
    objs = [
        (p.stat().st_size, p) for p in exported_dir.glob("**/*.obj") if p.is_file() and "decode-nif-geometry" in str(p)
    ]

    # Deduplicate by (asset_id, mesh_block) — keep largest
    by_key: dict[tuple[str, str], tuple[int, Path]] = {}
    for size, path in objs:
        m = re.search(r"decode-nif-geometry-([0-9a-f]{16})(?:-mesh(\d+))?", str(path))
        aid = m.group(1) if m else "unknown"
        mb = m.group(2) if m and m.group(2) else "?"
        key = (aid, mb)
        if key not in by_key or size > by_key[key][0]:
            by_key[key] = (size, path)

    issues: list[dict[str, Any]] = []
    stats = {
        "totalOBJs": len(by_key),
        "facedCount": 0,
        "posOnlyCount": 0,
        "totalVertices": 0,
        "totalFaces": 0,
        "totalBytes": 0,
        "nanCount": 0,
        "boundsIssueCount": 0,
        "negIndexCount": 0,
    }

    for (aid, mb), (size, path) in sorted(by_key.items()):
        with open(path, "rb") as f:
            content = f.read()

        sha = hashlib.sha256(content).hexdigest()
        text = content.decode("utf-8", errors="ignore")

        v_count = text.count("\nv ") + (1 if text.startswith("v ") else 0)
        f_count = text.count("\nf ") + (1 if text.startswith("f ") else 0)

        stats["totalVertices"] += v_count
        stats["totalFaces"] += f_count
        stats["totalBytes"] += size
        if f_count > 0:
            stats["facedCount"] += 1
        else:
            stats["posOnlyCount"] += 1

        # Check NaN
        has_nan = "nan" in text.lower()

        # Extract face indices
        face_indices: list[int] = []
        for line in text.split("\n"):
            if line.startswith("f "):
                parts = line.split()[1:]
                for p in parts:
                    idx_str = p.split("/")[0]
                    try:
                        face_indices.append(int(idx_str))
                    except ValueError, TypeError:
                        pass

        max_idx = max(face_indices) if face_indices else -1
        neg_indices = [i for i in face_indices if i < 0]

        bounds_ok = (max_idx <= v_count) if f_count > 0 else True

        entry_issues: list[str] = []
        if has_nan:
            entry_issues.append("NaN in file")
            stats["nanCount"] += 1
        if not bounds_ok and f_count > 0:
            entry_issues.append(f"max face index {max_idx} > vertex count {v_count}")
            stats["boundsIssueCount"] += 1
        if neg_indices:
            entry_issues.append(f"{len(neg_indices)} negative face indices")
            stats["negIndexCount"] += 1

        if entry_issues:
            issues.append(
                {
                    "id": aid,
                    "meshBlock": mb,
                    "path": str(path),
                    "v": v_count,
                    "f": f_count,
                    "sha256": sha,
                    "issues": entry_issues,
                }
            )

    return issues, stats


def print_integrity_report(issues: list[dict[str, Any]], stats: dict[str, int]) -> None:
    """Pretty-print integrity report."""
    print()
    print("=" * 70)
    print("  OBJ Integrity Check")
    print("=" * 70)
    print()
    print(f"  Total OBJs:         {stats['totalOBJs']:>6}")
    print(f"  Faced:              {stats['facedCount']:>6}")
    print(f"  Position-only:      {stats['posOnlyCount']:>6}")
    print(f"  Total vertices:     {stats['totalVertices']:>6}")
    print(f"  Total faces:        {stats['totalFaces']:>6}")
    print(f"  Total bytes:        {stats['totalBytes']:>10,}")
    print()
    print(f"  NaN detected:        {stats['nanCount']}")
    print(f"  Index bounds issues: {stats['boundsIssueCount']}")
    print(f"  Negative indices:    {stats['negIndexCount']}")
    print()

    if issues:
        print(f"  ISSUES ({len(issues)}):")
        for issue in issues[:20]:
            print(f"    [!] {issue['id']} mesh#{issue['meshBlock']}  v={issue['v']} f={issue['f']}")
            for detail in issue["issues"]:
                print(f"        {detail}")
        if len(issues) > 20:
            print(f"    ... and {len(issues) - 20} more")
        print()
    else:
        print("  [OK] No structural issues found.")
        print()


# ============================================================================
# Phase 4: Full OBJ manifest builder
# ============================================================================


def build_manifest(exported_dir: Path, manifest_path: Path) -> list[dict[str, Any]]:
    """Build a complete OBJ manifest with SHA256 hashes and structural metadata."""
    objs = [
        (p.stat().st_size, p) for p in exported_dir.glob("**/*.obj") if p.is_file() and "decode-nif-geometry" in str(p)
    ]

    by_key: dict[tuple[str, str], tuple[int, Path]] = {}
    for size, path in objs:
        m = re.search(r"decode-nif-geometry-([0-9a-f]{16})(?:-mesh(\d+))?", str(path))
        aid = m.group(1) if m else "unknown"
        mb = m.group(2) if m and m.group(2) else "?"
        key = (aid, mb)
        if key not in by_key or size > by_key[key][0]:
            by_key[key] = (size, path)

    manifest: list[dict[str, Any]] = []
    total_v = 0
    total_f = 0
    total_bytes = 0
    faced = 0
    posonly = 0

    for (aid, mb), (size, path) in sorted(by_key.items()):
        with open(path, "rb") as f:
            content = f.read()
        sha = hashlib.sha256(content).hexdigest()
        text = content.decode("utf-8", errors="ignore")
        v_count = text.count("\nv ") + (1 if text.startswith("v ") else 0)
        vt_count = text.count("\nvt ") + (1 if text.startswith("vt ") else 0)
        vn_count = text.count("\nvn ") + (1 if text.startswith("vn ") else 0)
        f_count = text.count("\nf ") + (1 if text.startswith("f ") else 0)

        has_nan = "nan" in text.lower()

        face_indices: list[int] = []
        for line in text.split("\n"):
            if line.startswith("f "):
                for p in line.split()[1:]:
                    try:
                        face_indices.append(int(p.split("/")[0]))
                    except ValueError, TypeError:
                        pass

        max_idx = max(face_indices) if face_indices else -1
        bounds_ok = (max_idx <= v_count) if f_count > 0 else True

        entry = {
            "id": aid,
            "meshBlock": mb,
            "v": v_count,
            "f": f_count,
            "vt": vt_count,
            "vn": vn_count,
            "bytes": size,
            "sha256": sha,
            "hasNaN": has_nan,
            "boundsOk": bounds_ok,
            "maxFaceIdx": max_idx,
        }

        manifest.append(entry)
        total_v += v_count
        total_f += f_count
        total_bytes += size
        if f_count > 0:
            faced += 1
        else:
            posonly += 1

    manifest.sort(key=lambda x: (-x["f"], -x["v"]))

    # Write manifest
    manifest_data = {
        "schema": "obj-manifest/v1",
        "totalOBJs": len(manifest),
        "facedCount": faced,
        "posOnlyCount": posonly,
        "totalVertices": total_v,
        "totalFaces": total_f,
        "totalBytes": total_bytes,
        "entries": manifest,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    print(f"\n  Manifest written: {manifest_path}")
    print(f"  {len(manifest)} OBJs, {faced} faced, {posonly} position-only")
    print(f"  {total_v} vertices, {total_f} faces, {total_bytes:,} bytes")

    return manifest


# ============================================================================
# CLI
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RIFT batch-sweep runner and OBJ integrity checker",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute exports (default: dry-run only)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of candidates to export",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show summary of all exported OBJs",
    )
    parser.add_argument(
        "--integrity-check",
        action="store_true",
        help="Run OBJ integrity validation",
    )
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Build full OBJ manifest",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip dotnet build step",
    )
    parser.add_argument(
        "--root",
        default="",
        help=f"Source directory (default: {DEFAULT_ROOT})",
    )
    parser.add_argument(
        "--out",
        default="",
        help=f"Exports directory (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--inventory",
        default="",
        help=f"Inventory path (default: {DEFAULT_INVENTORY})",
    )

    args = parser.parse_args()

    root = Path(args.root) if args.root else DEFAULT_ROOT
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    inventory_path = Path(args.inventory) if args.inventory else DEFAULT_INVENTORY

    # Ensure inventory exists
    if not inventory_path.exists():
        print(f"ERROR: Inventory not found at {inventory_path}", file=sys.stderr)
        print("  Run: python scripts/rift_workflow.py mesh-bindings --full", file=sys.stderr)
        sys.exit(1)

    # --- Integrity check ---
    if args.integrity_check:
        print("\n--- OBJ Integrity Check ---")
        issues, stats = integrity_check(out_dir)
        print_integrity_report(issues, stats)

        # Also write manifest when doing integrity check
        manifest_path = out_dir / "obj-manifest-stage18.json"
        build_manifest(out_dir, manifest_path)

        if issues:
            sys.exit(1)
        return

    # --- Manifest ---
    if args.manifest:
        manifest_path = out_dir / "obj-manifest-stage18.json"
        build_manifest(out_dir, manifest_path)
        return

    # --- Summary ---
    if args.summary:
        issues, stats = integrity_check(out_dir)
        print_integrity_report(issues, stats)
        return

    # --- Candidate discovery (dry-run or execute) ---
    candidates = discover_candidates(inventory_path, out_dir)
    print_candidates(candidates)

    if args.execute and candidates:
        batch_export(
            candidates=candidates,
            project=DEFAULT_PROJECT,
            root=root,
            out_dir=out_dir,
            limit=args.limit,
            skip_build=args.skip_build,
        )
        # Run integrity check after export
        print("\n--- Post-export Integrity Check ---")
        issues, stats = integrity_check(out_dir)
        print_integrity_report(issues, stats)
        manifest_path = out_dir / "obj-manifest-stage18.json"
        build_manifest(out_dir, manifest_path)
    elif not args.execute:
        print("  Dry-run mode. Use --execute to export candidates.\n")


if __name__ == "__main__":
    main()
