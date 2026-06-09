#!/usr/bin/env python3
"""FT-2.2: Bulk NIF → OBJ export driver for RiftFlythrough.

Implements the design in `docs/roadmap/ft-designs/ft2.1-bulk-export-driver-design.md`.

Reads the nif-mesh-binding inventory (or a file of asset IDs), invokes the C#
`decode-nif-geometry --export-geometry` command per NIF, collects OBJs into
`Assets/build/flythrough/objs/<hash>.obj`, and writes per-OBJ sidecar manifests
plus a per-run manifest with resume semantics.

Usage:
    python scripts/bulk_export_for_flythrough.py run --limit 50
    python scripts/bulk_export_for_flythrough.py run --mesh-size-families 297,305 --resume
    python scripts/bulk_export_for_flythrough.py run --dry-run --asset-ids abc,def
    python scripts/bulk_export_for_flythrough.py status
    python scripts/bulk_export_for_flythrough.py verify --limit 5
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = REPO_ROOT / "Exports" / "nif-mesh-binding-inventory.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "Assets" / "build" / "flythrough" / "objs"
DEFAULT_MANIFEST = REPO_ROOT / "Assets" / "build" / "flythrough" / "bulk-export-manifest.json"
DEFAULT_DOTNET_PROJECT = REPO_ROOT / "src" / "RiftAssetDumper" / "RiftAssetDumper.csproj"
DEFAULT_LIVE_ROOT = Path("C:/Program Files (x86)/Glyph/Games/RIFT/Live")

ASSET_ID_RE = re.compile(r"^[0-9a-f]{16}$", re.IGNORECASE)

log = logging.getLogger("bulk_export_for_flythrough")


# =============================================================================
# Dataclasses
# =============================================================================


@dataclasses.dataclass
class ExportProgress:
    """Per-asset progress snapshot — passed to the on_progress callback."""

    total: int
    completed: int
    failed: int
    skipped: int
    current_id: str | None


@dataclasses.dataclass
class BulkExportResult:
    """Return value of bulk_export_for_flythrough()."""

    stats: dict[str, int]
    manifest_path: Path
    per_obj_dir: Path
    duration_sec: float
    errors: list[dict[str, Any]]


# =============================================================================
# Helpers
# =============================================================================


def _now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z")


def _now() -> float:
    return time.time()


def _file_sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically: write to temp file, fsync, rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


# =============================================================================
# Inventory + input loading
# =============================================================================


def load_asset_ids_from_inventory(inventory_path: Path) -> list[str]:
    """Read nif-mesh-binding-inventory.json and return unique 16-char hex asset IDs."""
    if not inventory_path.exists():
        raise FileNotFoundError(f"Inventory not found: {inventory_path}")
    with open(inventory_path, encoding="utf-8-sig") as f:
        data = json.load(f)
    seen: set[str] = set()
    out: list[str] = []
    rows: list[dict[str, Any]] = []
    if isinstance(data, list):
        rows = [r for r in data if isinstance(r, dict)]
    elif isinstance(data, dict):
        for key in ("Meshes", "Blocks", "NiMeshBlocks", "Entries", "Rows", "Signatures"):
            value = data.get(key)
            if isinstance(value, list) and value and isinstance(value[0], dict):
                rows = value
                break
        if not rows:
            for value in data.values():
                if isinstance(value, list):
                    rows.extend(r for r in value if isinstance(r, dict))
    for row in rows:
        for k in ("AssetId", "AssetIdPrefix", "Id", "NifHash", "IdPrefix"):
            value = row.get(k)
            if isinstance(value, str) and ASSET_ID_RE.match(value):
                key = value.lower()
                if key not in seen:
                    seen.add(key)
                    out.append(key)
                break
    return out


def load_asset_ids_from_file(path: Path) -> list[str]:
    """Read one asset ID per line; supports `#` comments and blank lines."""
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    out: list[str] = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            candidate = line.split()[0].lower()
            if not ASSET_ID_RE.match(candidate):
                log.warning("skipping invalid asset id: %s", candidate)
                continue
            out.append(candidate)
    return out


def filter_by_mesh_size(
    asset_ids: list[str],
    inventory_path: Path,
    families: set[int] | None,
) -> list[str]:
    """Return asset IDs whose MeshSize is in the requested families.

    If families is None or empty, returns the input unchanged. If inventory is
    missing or has no mesh-size field, returns the input unchanged (with a log).
    """
    if not families:
        return asset_ids
    if not inventory_path.exists():
        log.warning("inventory missing; cannot filter by mesh size: %s", inventory_path)
        return asset_ids
    with open(inventory_path, encoding="utf-8-sig") as f:
        data = json.load(f)
    rows: list[dict[str, Any]] = []
    if isinstance(data, list):
        rows = [r for r in data if isinstance(r, dict)]
    elif isinstance(data, dict):
        for key in ("Meshes", "Blocks", "NiMeshBlocks", "Entries", "Rows", "Signatures"):
            value = data.get(key)
            if isinstance(value, list) and value and isinstance(value[0], dict):
                rows = value
                break
        if not rows:
            for value in data.values():
                if isinstance(value, list):
                    rows.extend(r for r in value if isinstance(r, dict))
    mesh_size_by_id: dict[str, int] = {}
    for row in rows:
        for k in ("AssetId", "AssetIdPrefix", "Id", "NifHash", "IdPrefix"):
            v = row.get(k)
            if isinstance(v, str) and ASSET_ID_RE.match(v):
                for ms_k in ("MeshSize", "meshSize", "MeshBlockSize", "Size"):
                    ms = row.get(ms_k)
                    if isinstance(ms, int):
                        mesh_size_by_id[v.lower()] = ms
                break
    out: list[str] = []
    for aid in asset_ids:
        ms = mesh_size_by_id.get(aid)
        if ms is None or ms in families:
            out.append(aid)
    log.info("filter_by_mesh_size: %d -> %d (families=%s)", len(asset_ids), len(out), sorted(families))
    return out


# =============================================================================
# Subprocess invocation
# =============================================================================


def run_decode_geometry(
    asset_id: str,
    *,
    project: Path,
    root: Path,
    timeout_sec: int,
) -> tuple[bool, str, str, float]:
    """Run `dotnet run --project ... --no-build -- decode-nif-geometry --id <id> --export-obj`.

    Returns (success, stdout_tail, stderr_tail, elapsed_sec).
    """
    args = [
        "dotnet",
        "run",
        "--project",
        str(project),
        "--no-build",
        "--",
        "decode-nif-geometry",
        "--id",
        asset_id,
        "--export-obj",
        "--root",
        str(root),
    ]
    start = _now()
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        return False, "", f"TIMEOUT after {timeout_sec}s", _now() - start
    except Exception as exc:  # pragma: no cover - defensive
        return False, "", f"ERROR: {exc}", _now() - start
    elapsed = _now() - start
    return (
        result.returncode == 0,
        (result.stdout or "")[-500:],
        (result.stderr or "")[-500:],
        elapsed,
    )


# =============================================================================
# Manifest I/O
# =============================================================================


def _read_existing_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.exists():
        return {
            "SchemaVersion": "flythrough-bulk-export-manifest/v1",
            "GeneratedAt": _now_iso(),
            "Stats": {
                "candidates": 0,
                "exported": 0,
                "failed": 0,
                "skipped": 0,
                "deduped": 0,
                "total_bytes": 0,
            },
            "Entries": [],
        }
    try:
        with open(manifest_path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Corrupt manifest at {manifest_path}: {exc}") from exc


def _index_existing_entries(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for entry in manifest.get("Entries", []):
        if not isinstance(entry, dict):
            continue
        aid = entry.get("nif_hash")
        if isinstance(aid, str):
            out[aid.lower()] = entry
    return out


def _write_manifest(manifest_path: Path, manifest: dict[str, Any]) -> None:
    manifest["GeneratedAt"] = _now_iso()
    _atomic_write_json(manifest_path, manifest)


def _write_obj_sidecar(obj_path: Path, entry: dict[str, Any]) -> Path:
    sidecar = obj_path.with_suffix(".obj.manifest.json")
    payload = {
        "SchemaVersion": "flythrough-obj-sidecar/v1",
        "nif_hash": entry["nif_hash"],
        "obj_filename": obj_path.name,
        "mesh_block": entry.get("mesh_block", 0),
        "mesh_size": entry.get("mesh_size"),
        "vertex_count": entry.get("vertex_count", 0),
        "face_count": entry.get("face_count", 0),
        "export_timestamp": entry.get("exported_at", _now_iso()),
        "export_command": entry.get("command", ""),
        "obj_sha1": entry.get("obj_sha1"),
        "obj_bytes": entry.get("obj_bytes", 0),
    }
    _atomic_write_json(sidecar, payload)
    return sidecar


# =============================================================================
# Core function
# =============================================================================


def bulk_export_for_flythrough(
    *,
    asset_ids: list[str],
    output_dir: Path,
    manifest_path: Path,
    project: Path,
    root: Path,
    timeout_sec: int = 120,
    skip_on_error: bool = True,
    resume: bool = False,
    dry_run: bool = False,
    skip_build: bool = True,
    on_progress: Callable[[ExportProgress], None] | None = None,
) -> BulkExportResult:
    """Export OBJs for the given asset IDs through the C# decode-nif-geometry CLI.

    See `docs/roadmap/ft-designs/ft2.1-bulk-export-driver-design.md` for the full contract.
    """
    start = _now()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = _read_existing_manifest(manifest_path)
    manifest["Stats"] = manifest.get("Stats", {})
    manifest["Entries"] = manifest.get("Entries", [])
    existing_index = _index_existing_entries(manifest) if resume else {}

    if not skip_build and not dry_run:
        if not shutil.which("dotnet"):
            raise RuntimeError("dotnet not on PATH; cannot build")
        log.info("building .NET project (this may take ~30s)...")
        rc = subprocess.run(
            ["dotnet", "build", str(project), "--nologo"],
            capture_output=True,
            text=True,
            timeout=300,
        ).returncode
        if rc != 0:
            raise RuntimeError(f"dotnet build failed with rc={rc}")

    stats: dict[str, int] = {
        "candidates": len(asset_ids),
        "exported": 0,
        "failed": 0,
        "skipped": 0,
        "deduped": 0,
        "total_bytes": 0,
    }
    seen_sha1: dict[str, str] = {}  # sha1 -> first nif_hash
    errors: list[dict[str, Any]] = []
    total = len(asset_ids)

    for idx, asset_id in enumerate(asset_ids):
        if on_progress is not None:
            on_progress(
                ExportProgress(
                    total=total,
                    completed=stats["exported"],
                    failed=stats["failed"],
                    skipped=stats["skipped"],
                    current_id=asset_id,
                )
            )

        # Resume: skip if already exported in a prior run
        if asset_id in existing_index:
            prior = existing_index[asset_id]
            if prior.get("status") == "exported" and prior.get("obj_path"):
                obj_path = output_dir / prior["obj_path"]
                if obj_path.exists() and obj_path.stat().st_size > 0:
                    stats["skipped"] += 1
                    log.info("[%d/%d] skip %s (already exported)", idx + 1, total, asset_id)
                    continue
            # Else: stale entry, fall through and re-process

        if dry_run:
            log.info("[%d/%d] [DRY] would export %s", idx + 1, total, asset_id)
            stats["skipped"] += 1
            continue

        log.info("[%d/%d] exporting %s...", idx + 1, total, asset_id)
        ok, stdout_tail, stderr_tail, elapsed = run_decode_geometry(
            asset_id, project=project, root=root, timeout_sec=timeout_sec
        )

        # Find the OBJ file (decode-nif-geometry writes to <output>/decode-nif-geometry-<id>/*.obj)
        # We accept any .obj under output_dir whose full path contains the asset_id.
        # (decode-nif-geometry puts the id in the parent dir name, not the filename.)
        candidate: list[Path] = []
        for path in output_dir.rglob("*.obj"):
            try:
                rel = path.relative_to(output_dir)
            except ValueError:
                continue
            if asset_id.lower() in str(rel).lower():
                candidate.append(path)
        obj_path = candidate[0] if candidate else None
        if not ok or obj_path is None or not obj_path.exists() or obj_path.stat().st_size == 0:
            err = {
                "id": asset_id,
                "error": stderr_tail or "no obj produced",
                "stdout": stdout_tail,
            }
            errors.append(err)
            stats["failed"] += 1
            log.warning("[%d/%d] FAIL %s: %s", idx + 1, total, asset_id, err["error"])
            if not skip_on_error:
                break
            continue

        # Compute SHA1 for dedup
        try:
            obj_sha1 = _file_sha1(obj_path)
            obj_bytes = obj_path.stat().st_size
        except OSError as exc:
            errors.append({"id": asset_id, "error": f"stat/sha1 failed: {exc}"})
            stats["failed"] += 1
            continue

        # Dedup by SHA1 (link, not copy, when same content already exists)
        status = "exported"
        if obj_sha1 in seen_sha1:
            first_hash = seen_sha1[obj_sha1]
            try:
                # Replace the just-written file with a hardlink to the first
                obj_path.unlink()
                target = output_dir / f"{first_hash[:8]}_dedup_link.obj"
                if not target.exists():
                    # Find the prior file by its entry
                    prior_entry = existing_index.get(first_hash) or next(
                        (e for e in manifest["Entries"] if e.get("obj_sha1") == obj_sha1),
                        None,
                    )
                    if prior_entry and prior_entry.get("obj_path"):
                        prior_obj = output_dir / prior_entry["obj_path"]
                        if prior_obj.exists():
                            os.link(prior_obj, target)
                obj_path = target
            except OSError:
                # Fall back to copy
                target = output_dir / f"{first_hash[:8]}_dedup_copy.obj"
                shutil.copy2(obj_path, target)
                obj_path = target
            stats["deduped"] += 1
            status = "deduped"
        else:
            seen_sha1[obj_sha1] = asset_id
            stats["exported"] += 1
            stats["total_bytes"] += obj_bytes

        # Build entry
        entry = {
            "nif_hash": asset_id,
            "mesh_block": 0,
            "mesh_size": None,
            "status": status,
            "obj_path": obj_path.name,
            "obj_sha1": obj_sha1,
            "obj_bytes": obj_bytes,
            "export_duration_sec": round(elapsed, 1),
            "exported_at": _now_iso(),
            "command": f"decode-nif-geometry --id {asset_id} --export-obj",
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
        }
        manifest["Entries"].append(entry)
        manifest["Stats"] = stats
        _write_manifest(manifest_path, manifest)
        _write_obj_sidecar(obj_path, entry)

    duration = _now() - start
    manifest["Stats"] = stats
    manifest["DurationSec"] = round(duration, 1)
    _write_manifest(manifest_path, manifest)

    return BulkExportResult(
        stats=stats,
        manifest_path=manifest_path,
        per_obj_dir=output_dir,
        duration_sec=duration,
        errors=errors[:100],
    )


# =============================================================================
# CLI
# =============================================================================


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bulk_export_for_flythrough",
        description="FT-2: Bulk NIF→OBJ export driver for RiftFlythrough.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    common.add_argument("--input-file", type=Path, default=None)
    common.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    common.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    common.add_argument("--project", type=Path, default=DEFAULT_DOTNET_PROJECT)
    common.add_argument("--root", type=Path, default=DEFAULT_LIVE_ROOT)

    # run
    run_p = sub.add_parser("run", parents=[common], help="Run a fresh export (or resume)")
    run_p.add_argument("--limit", type=int, default=50)
    run_p.add_argument("--mesh-size-families", default="")
    run_p.add_argument("--asset-ids", default="")
    run_p.add_argument("--dry-run", action="store_true")
    run_p.add_argument("--skip-build", action="store_true")
    run_p.add_argument("--timeout", type=int, default=120)
    run_p.add_argument("--skip-on-error", dest="skip_on_error", action="store_true", default=True)
    run_p.add_argument("--no-skip-on-error", dest="skip_on_error", action="store_false")
    run_p.add_argument("--resume", action="store_true")
    run_p.add_argument("--workers", type=int, default=1)
    run_p.add_argument("--randomize", action="store_true")

    # status
    status_p = sub.add_parser("status", parents=[common], help="Show current state")
    status_p.add_argument("--json", action="store_true")

    # verify
    verify_p = sub.add_parser("verify", parents=[common], help="Re-run decode on already-exported OBJs")
    verify_p.add_argument("--limit", type=int, default=10)

    # clean
    clean_p = sub.add_parser("clean", parents=[common], help="Remove all OBJs and manifest")
    clean_p.add_argument("--yes", action="store_true", help="Skip confirmation prompt")

    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    if args.input_file:
        asset_ids = load_asset_ids_from_file(args.input_file)
    elif args.asset_ids:
        asset_ids = [a.strip().lower() for a in args.asset_ids.split(",") if a.strip()]
    else:
        asset_ids = load_asset_ids_from_inventory(args.inventory)

    families: set[int] = set()
    if args.mesh_size_families:
        families = {int(x.strip()) for x in args.mesh_size_families.split(",") if x.strip()}
        asset_ids = filter_by_mesh_size(asset_ids, args.inventory, families)

    if args.randomize:
        import random

        random.shuffle(asset_ids)
    if args.limit > 0:
        asset_ids = asset_ids[: args.limit]

    log.info("FT-2 run: %d asset_ids (families=%s, limit=%d)", len(asset_ids), sorted(families), args.limit)

    def _on_progress(p: ExportProgress) -> None:
        log.info(
            "progress: %d/%d done (%d failed, %d skipped) current=%s",
            p.completed + p.skipped,
            p.total,
            p.failed,
            p.skipped,
            p.current_id,
        )

    result = bulk_export_for_flythrough(
        asset_ids=asset_ids,
        output_dir=args.output_dir,
        manifest_path=args.manifest,
        project=args.project,
        root=args.root,
        timeout_sec=args.timeout,
        skip_on_error=args.skip_on_error,
        resume=args.resume,
        dry_run=args.dry_run,
        skip_build=args.skip_build,
        on_progress=_on_progress,
    )
    log.info("FT-2 done: %s in %.1fs", result.stats, result.duration_sec)
    if result.errors:
        log.warning("FT-2 had %d errors (first 100 shown in manifest)", len(result.errors))
    return 0 if result.stats["failed"] == 0 or args.dry_run else 1


def _cmd_status(args: argparse.Namespace) -> int:
    if not args.manifest.exists():
        print(f"No manifest at {args.manifest}; nothing to report.")
        return 0
    with open(args.manifest, encoding="utf-8") as f:
        manifest = json.load(f)
    if args.json:
        print(json.dumps(manifest, indent=2))
        return 0
    stats = manifest.get("Stats", {})
    entries = manifest.get("Entries", [])
    print(f"Manifest: {args.manifest}")
    print(f"Schema:   {manifest.get('SchemaVersion', '?')}")
    print(f"Generated: {manifest.get('GeneratedAt', '?')}")
    print(f"Duration: {manifest.get('DurationSec', '?')}s")
    print()
    print(f"Candidates: {stats.get('candidates', 0)}")
    print(f"Exported:   {stats.get('exported', 0)}")
    print(f"Failed:     {stats.get('failed', 0)}")
    print(f"Skipped:    {stats.get('skipped', 0)}")
    print(f"Deduped:    {stats.get('deduped', 0)}")
    print(f"Total bytes: {stats.get('total_bytes', 0):,}")
    print(f"Entries:    {len(entries)}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    if not args.manifest.exists():
        print(f"No manifest at {args.manifest}; cannot verify.")
        return 1
    with open(args.manifest, encoding="utf-8") as f:
        manifest = json.load(f)
    entries = [e for e in manifest.get("Entries", []) if e.get("status") == "exported"]
    if args.limit > 0:
        entries = entries[: args.limit]
    print(f"Verifying {len(entries)} entries...")
    drift = 0
    for entry in entries:
        obj_path = args.output_dir / entry["obj_path"]
        if not obj_path.exists():
            print(f"  MISSING: {obj_path}")
            drift += 1
            continue
        actual_sha1 = _file_sha1(obj_path)
        expected = entry.get("obj_sha1")
        if actual_sha1 != expected:
            print(f"  DRIFT: {obj_path.name} expected={expected[:8]} actual={actual_sha1[:8]}")
            drift += 1
    print(f"Verify: {len(entries) - drift}/{len(entries)} OK, {drift} drift/missing")
    return 0 if drift == 0 else 1


def _cmd_clean(args: argparse.Namespace) -> int:
    if not args.yes:
        confirm = input(f"Delete {args.output_dir} and {args.manifest}? [y/N] ")
        if confirm.lower() != "y":
            print("Aborted.")
            return 1
    if args.output_dir.exists():
        shutil.rmtree(args.output_dir)
        print(f"Removed {args.output_dir}")
    if args.manifest.exists():
        args.manifest.unlink()
        print(f"Removed {args.manifest}")
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    parser = _build_parser()
    args = parser.parse_args()
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "status":
        return _cmd_status(args)
    if args.command == "verify":
        return _cmd_verify(args)
    if args.command == "clean":
        return _cmd_clean(args)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
