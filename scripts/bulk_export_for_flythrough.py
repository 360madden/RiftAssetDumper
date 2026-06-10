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
DEFAULT_PROBE_LOOKUP = REPO_ROOT / "Exports" / "probe-meshsize-lookup.json"

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


def load_mesh_block_map(lookup_path: Path) -> dict[str, int]:
    """Load per-asset mesh_block from probe-meshsize-lookup.json.

    Returns {asset_id_lower: mesh_block}. Entries without mesh_block are skipped.
    """
    if not lookup_path.exists():
        log.warning("probe lookup not found; all mesh_blocks will default to 0: %s", lookup_path)
        return {}
    with open(lookup_path, encoding="utf-8-sig") as f:
        data = json.load(f)
    entries = data.get("entries", {}) if isinstance(data, dict) else {}
    out: dict[str, int] = {}
    for aid, val in entries.items():
        if isinstance(val, dict) and "mesh_block" in val:
            try:
                out[aid.lower()] = int(val["mesh_block"])
            except ValueError, TypeError:
                # Skip inferred or non-numeric mesh_block values
                continue
    log.info("loaded %d mesh_block entries from %s", len(out), lookup_path)
    return out


def load_asset_ids_from_probe_lookup(lookup_path: Path) -> list[str]:
    """Extract asset IDs from probe-meshsize-lookup.json keys.

    Each key is a 16-char hex asset ID. Only includes entries with a numeric
    mesh_block (skips "inferred" entries).
    """
    mb_map = load_mesh_block_map(lookup_path)
    return sorted(mb_map.keys())


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


def run_probe_scene_graph(
    asset_id: str,
    *,
    project: Path,
    root: Path,
    out_path: Path,
    timeout_sec: int = 60,
) -> tuple[bool, str, str, float]:
    """Run `dotnet run ... probe-nif-scene-graph` and capture the JSON output.

    Returns (success, stdout_tail, stderr_tail, elapsed_sec).
    """
    args = [
        "dotnet",
        "run",
        "--project",
        str(project),
        "--no-build",
        "--",
        "probe-nif-scene-graph",
        "--id",
        asset_id,
        "--root",
        str(root),
        "--out",
        str(out_path),
    ]
    start = _now()
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        return False, "", f"TIMEOUT after {timeout_sec}s", _now() - start
    except Exception as exc:  # pragma: no cover - defensive
        return False, "", f"ERROR: {exc}", _now() - start
    elapsed = _now() - start
    # probe-nif-scene-graph may return non-zero for benign reasons (e.g. warnings);
    # success is determined by whether the output JSON file exists and is valid.
    return (
        result.returncode == 0,
        (result.stdout or "")[-500:],
        (result.stderr or "")[-500:],
        elapsed,
    )


def run_decode_geometry(
    asset_id: str,
    *,
    project: Path,
    root: Path,
    timeout_sec: int,
    mesh_block: int = 0,
    mode: str = "export-obj",
    out_dir: Path | None = None,
) -> tuple[bool, str, str, float]:
    """Run `dotnet run ... decode-nif-geometry`.

    mode='export-obj': uses --export-obj (attribute-set @264 indexed, faced OBJs)
    mode='experimental': uses --experimental-position-source --write-obj (fan faces, pos-only fallback)
    out_dir: passed as --out <dir> to control OBJ output location

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
        "--mesh-block",
        str(mesh_block),
        "--root",
        str(root),
    ]
    if out_dir is not None:
        args.extend(["--out", str(out_dir)])
    if mode == "experimental":
        args.extend(["--experimental-position-source", "--write-obj"])
    else:
        args.append("--export-obj")
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


def _enrich_sidecar_with_scene_graph(
    sidecar_path: Path,
    sg_data: dict[str, Any],
    *,
    mesh_block: int = 0,
) -> None:
    """Enrich an FT-3 sidecar with FT-4 scene graph data (parent_node, transform).

    Finds the NiMesh with matching mesh_block in the scene graph, locates its
    parent NiNode, and copies the parent's transform into the sidecar.
    """
    if not sidecar_path.exists():
        return
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    meshes: list[dict[str, Any]] = sg_data.get("Meshes", [])
    nodes: list[dict[str, Any]] = sg_data.get("Nodes", [])

    # Find the mesh entry matching mesh_block
    mesh_info: dict[str, Any] | None = None
    for m in meshes:
        if m.get("BlockIndex") == mesh_block:
            mesh_info = m
            break
    if mesh_info is None and meshes:
        # Fallback: use first mesh with a parent
        for m in meshes:
            if m.get("ParentNiNodeIndex") is not None:
                mesh_info = m
                break

    if mesh_info is not None:
        parent_idx = mesh_info.get("ParentNiNodeIndex")
        if parent_idx is not None:
            # Find the parent NiNode
            parent_node: dict[str, Any] | None = None
            for n in nodes:
                if n.get("BlockIndex") == parent_idx:
                    parent_node = n
                    break
            if parent_node is not None:
                parent_name = parent_node.get("Name")
                if parent_name and parent_name != "SceneNode":
                    sidecar["parent_node"] = parent_name
                sidecar["transform"] = {
                    "translation": parent_node.get("Translation"),
                    "rotation": parent_node.get("Rotation"),  # 3x3 matrix row-major [r11..r33]
                    "scale": parent_node.get("Scale"),
                }

    _atomic_write_json(sidecar_path, sidecar)


def _parse_obj_stats(obj_path: Path) -> tuple[int, int]:
    """Extract vertex and face counts from an OBJ file.

    Returns (vertex_count, face_count). One-pass read, skips blank/comment lines.
    """
    v_count, f_count = 0, 0
    with open(obj_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped[0] == "v" and (len(stripped) == 1 or stripped[1] == " "):
                v_count += 1
            elif stripped[0] == "f" and (len(stripped) == 1 or stripped[1] == " "):
                f_count += 1
    return v_count, f_count


def _write_obj_sidecar(
    obj_path: Path,
    entry: dict[str, Any],
    *,
    probe_lookup: dict[str, Any] | None = None,
) -> Path:
    """Write an FT-3 asset-mesh-manifest/v1 sidecar next to the OBJ."""
    vertex_count, face_count = _parse_obj_stats(obj_path)
    nif_hash = entry["nif_hash"]

    # Probe lookup enrichment
    probe_entry: dict[str, Any] = {}
    if probe_lookup:
        probe_entry = probe_lookup.get("entries", {}).get(nif_hash, {})

    sidecar = obj_path.with_suffix(".obj.manifest.json")
    payload: dict[str, Any] = {
        "SchemaVersion": "asset-mesh-manifest/v1",
        "nif_hash": nif_hash,
        "obj_filename": obj_path.name,
        "mesh_block": entry.get("mesh_block", 0),
        "mesh_size": entry.get("mesh_size") or probe_entry.get("meshsize"),
        "vertex_count": vertex_count,
        "face_count": face_count,
        "faced": face_count > 0,
        "position_descriptor": None,
        "export_mode": entry.get("export_mode", "export-obj"),
        "export_timestamp": entry.get("exported_at", _now_iso()),
        "export_command": entry.get("command", ""),
        "obj_sha1": entry.get("obj_sha1", ""),
        "obj_bytes": entry.get("obj_bytes", 0),
        "export_duration_sec": entry.get("export_duration_sec", 0),
        "parent_node": None,
        "sibling_meshes": [],
        "linked_textures": [],
        "original_path_candidates": [],
        "bounding_box": None,
        "transform": None,
        "zone_id": None,
        "lod_index": None,
        "probe_note": probe_entry.get("note"),
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
    mesh_block_map: dict[str, int] | None = None,
    probe_lookup_data: dict[str, Any] | None = None,
    world_dir: Path | None = None,
    on_progress: Callable[[ExportProgress], None] | None = None,
) -> BulkExportResult:
    """Export OBJs for the given asset IDs through the C# decode-nif-geometry CLI.

    If world_dir is set (FT-4.4), also runs probe-nif-scene-graph per NIF,
    stores scene-graph/v1 world.json sidecars, and enriches FT-3 sidecars
    with parent_node + transform from the scene graph.

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

        mb = mesh_block_map.get(asset_id, 0) if mesh_block_map else 0

        # Mesh-block retry chain: if lookup value fails with "not found", try common alternatives
        MB_RETRY_CHAIN = [6, 7, 8, 9, 10, 27, 31, 25, 17, 0]
        tried_mb: set[int] = set()
        best_mb = mb

        def _attempt_decode(mb: int, mode: str, out_dir: Path, aid: str = asset_id) -> tuple[bool, str, str, float]:
            ok, stdout, stderr, elapsed = run_decode_geometry(
                aid, project=project, root=root, timeout_sec=timeout_sec, mesh_block=mb, mode=mode, out_dir=out_dir
            )
            return ok, stdout, stderr, elapsed

        # Try lookup value first
        tried_mb.add(best_mb)
        asset_out_dir = output_dir / f"decode-nif-geometry-{asset_id}"
        ok, stdout_tail, stderr_tail, elapsed = _attempt_decode(best_mb, "export-obj", asset_out_dir)

        # If "not found", try retry chain
        if not ok and "not found" in (stderr_tail or "").lower():
            for alt_mb in MB_RETRY_CHAIN:
                if alt_mb in tried_mb:
                    continue
                tried_mb.add(alt_mb)
                log.info("  mesh_block %d not found; trying %d...", best_mb, alt_mb)
                ok, stdout_tail, stderr_tail, retry_elapsed = _attempt_decode(alt_mb, "export-obj", asset_out_dir)
                if ok or "not found" not in (stderr_tail or "").lower():
                    best_mb = alt_mb
                    elapsed = retry_elapsed
                    break

        # Track export mode as state (not inferred from output text)
        export_mode = "export-obj"

        # Two-pass: if "no attribute sets", fall back to experimental
        if not ok and "no attribute sets" in (stderr_tail or ""):
            export_mode = "experimental"
            log.info("  no attribute sets at mb=%d; retrying with --experimental-position-source...", best_mb)
            ok, stdout_tail, stderr_tail, exp_elapsed = _attempt_decode(best_mb, "experimental", asset_out_dir)
            elapsed = exp_elapsed

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
            # Write failure entry to manifest for diagnosis
            fail_entry = {
                "nif_hash": asset_id,
                "mesh_block": best_mb,
                "status": "failed",
                "error_message": stderr_tail or "no obj produced",
                "export_duration_sec": round(elapsed, 1),
                "command": f"decode-nif-geometry --id {asset_id} --mesh-block {best_mb} --export-obj",
            }
            manifest["Entries"].append(fail_entry)
            manifest["Stats"] = stats
            _write_manifest(manifest_path, manifest)
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
            dedup_target: Path | None = None
            try:
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
                if target.exists():
                    dedup_target = target
            except OSError:
                # Fall back to copy
                target = output_dir / f"{first_hash[:8]}_dedup_copy.obj"
                shutil.copy2(obj_path, target)
                dedup_target = target
            if dedup_target is not None:
                obj_path = dedup_target
                stats["deduped"] += 1
                status = "deduped"
            else:
                # Hardlink/copy fallback: create a copy to dedup link path
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
            "mesh_block": best_mb,
            "mesh_size": None,
            "status": status,
            "export_mode": export_mode,
            "obj_path": obj_path.name,
            "obj_sha1": obj_sha1,
            "obj_bytes": obj_bytes,
            "export_duration_sec": round(elapsed, 1),
            "exported_at": _now_iso(),
            "command": f"decode-nif-geometry --id {asset_id} --mesh-block {best_mb} --export-obj",
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
        }
        manifest["Entries"].append(entry)
        manifest["Stats"] = stats
        _write_manifest(manifest_path, manifest)
        sidecar_path = _write_obj_sidecar(obj_path, entry, probe_lookup=probe_lookup_data)

        # FT-4.4: optionally run scene graph probe and enrich sidecar
        if world_dir is not None:
            world_dir.mkdir(parents=True, exist_ok=True)
            world_json = world_dir / f"{asset_id}.world.json"
            sg_ok, sg_out, sg_err, sg_elapsed = run_probe_scene_graph(
                asset_id,
                project=project,
                root=root,
                out_path=world_json,
                timeout_sec=min(timeout_sec, 60),
            )
            if sg_ok and world_json.exists() and world_json.stat().st_size > 0:
                try:
                    sg_data = json.loads(world_json.read_text(encoding="utf-8-sig"))
                    sg_data["SchemaVersion"] = "scene-graph/v1"
                    sg_data["nif_hash"] = asset_id
                    sg_data["generated_at"] = _now_iso()
                    sg_data["probe_command"] = f"probe-nif-scene-graph --id {asset_id}"
                    _atomic_write_json(world_json, sg_data)

                    # Enrich FT-3 sidecar with scene-graph data
                    _enrich_sidecar_with_scene_graph(sidecar_path, sg_data, mesh_block=best_mb)
                    log.info(
                        "  scene-graph: %d nodes, %d meshes", sg_data.get("NodeCount", 0), sg_data.get("MeshCount", 0)
                    )
                except (json.JSONDecodeError, KeyError, OSError) as exc:
                    log.warning("  scene-graph parse failed for %s: %s", asset_id, exc)
            else:
                log.warning("  scene-graph probe failed for %s: %s", asset_id, sg_err[:120] if sg_err else "no output")

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
    run_p.add_argument(
        "--use-probe-lookup",
        action="store_true",
        help="Use probe-meshsize-lookup.json keys as asset ID list (guarantees known mesh_block)",
    )
    run_p.add_argument("--dry-run", action="store_true")
    run_p.add_argument("--skip-build", action="store_true")
    run_p.add_argument("--timeout", type=int, default=120)
    run_p.add_argument("--skip-on-error", dest="skip_on_error", action="store_true", default=True)
    run_p.add_argument("--no-skip-on-error", dest="skip_on_error", action="store_false")
    run_p.add_argument("--resume", action="store_true")
    run_p.add_argument("--workers", type=int, default=1)
    run_p.add_argument("--randomize", action="store_true")
    run_p.add_argument(
        "--scene-graph",
        action="store_true",
        help="FT-4.4: Run probe-nif-scene-graph per NIF and store world.json sidecars",
    )
    run_p.add_argument(
        "--world-dir",
        type=Path,
        default=None,
        help="Directory for world.json scene graph output (default: <output-dir>/worlds)",
    )

    # status
    status_p = sub.add_parser("status", parents=[common], help="Show current state")
    status_p.add_argument("--json", action="store_true")

    # verify
    verify_p = sub.add_parser("verify", parents=[common], help="Re-run decode on already-exported OBJs")
    verify_p.add_argument("--limit", type=int, default=10)

    # clean
    clean_p = sub.add_parser("clean", parents=[common], help="Remove all OBJs and manifest")
    clean_p.add_argument("--yes", action="store_true", help="Skip confirmation prompt")

    # scene-graph-only (FT-4.6)
    sgo_p = sub.add_parser(
        "scene-graph-only",
        parents=[common],
        help="FT-4.6: Run scene graph probes on already-exported OBJs (skips export)",
    )
    sgo_p.add_argument("--limit", type=int, default=0, help="Max NIFs to process (0=all)")
    sgo_p.add_argument("--timeout", type=int, default=60)
    sgo_p.add_argument(
        "--world-dir", type=Path, default=None, help="Directory for world.json output (default: <output-dir>/worlds)"
    )

    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    # Load mesh-block lookup from existing probe data (loaded once, used for mesh_block resolution)
    mesh_block_map: dict[str, int] = load_mesh_block_map(DEFAULT_PROBE_LOOKUP)

    if args.input_file:
        asset_ids = load_asset_ids_from_file(args.input_file)
    elif args.asset_ids:
        asset_ids = [a.strip().lower() for a in args.asset_ids.split(",") if a.strip()]
    elif args.use_probe_lookup:
        asset_ids = sorted(mesh_block_map.keys())
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

    # Load full probe lookup for sidecar enrichment
    probe_lookup_data: dict[str, Any] | None = None
    if args.use_probe_lookup:
        try:
            with open(DEFAULT_PROBE_LOOKUP, encoding="utf-8-sig") as f:
                probe_lookup_data = json.load(f)
        except Exception as exc:
            log.warning("could not load probe lookup for sidecar enrichment: %s", exc)

    # FT-4.4: resolve world.json output directory
    world_dir: Path | None = None
    if args.scene_graph:
        world_dir = args.world_dir or (args.output_dir / "worlds")
        log.info("FT-4.4 scene-graph enabled; world.json → %s", world_dir)

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
        mesh_block_map=mesh_block_map,
        probe_lookup_data=probe_lookup_data,
        world_dir=world_dir,
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


def _cmd_scene_graph_only(args: argparse.Namespace) -> int:
    """FT-4.6: Run scene graph probes on already-exported OBJs only.

    Reads the existing manifest, finds all exported/deduped entries,
    runs probe-nif-scene-graph on each, writes world.json, and
    enriches the FT-3 sidecar with parent_node + transform.
    """
    if not args.manifest.exists():
        log.error("No manifest at %s; run 'bulk_export_for_flythrough.py run' first.", args.manifest)
        return 1

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    entries = [
        e for e in manifest.get("Entries", []) if e.get("status") in ("exported", "deduped") and e.get("obj_path")
    ]
    if args.limit > 0:
        entries = entries[: args.limit]

    world_dir = args.world_dir or (args.output_dir / "worlds")
    world_dir.mkdir(parents=True, exist_ok=True)

    log.info("FT-4.6 scene-graph-only: %d entries → %s", len(entries), world_dir)

    enriched, failed, skipped = 0, 0, 0
    for idx, entry in enumerate(entries):
        nif_hash = entry["nif_hash"]
        mesh_block = entry.get("mesh_block", 0)
        obj_path = args.output_dir / entry["obj_path"]
        sidecar_path = obj_path.with_suffix(".obj.manifest.json")

        # Skip if already enriched
        if sidecar_path.exists():
            try:
                sc = json.loads(sidecar_path.read_text(encoding="utf-8"))
                if sc.get("transform") is not None:
                    skipped += 1
                    log.info("[%d/%d] skip %s (already enriched)", idx + 1, len(entries), nif_hash)
                    continue
            except json.JSONDecodeError, OSError:
                pass  # Corrupt sidecar — re-probe

        world_json = world_dir / f"{nif_hash}.world.json"
        sg_ok, sg_out, sg_err, sg_elapsed = run_probe_scene_graph(
            nif_hash,
            project=args.project,
            root=args.root,
            out_path=world_json,
            timeout_sec=args.timeout,
        )
        if not sg_ok or not world_json.exists() or world_json.stat().st_size == 0:
            failed += 1
            log.warning("[%d/%d] FAIL %s: %s", idx + 1, len(entries), nif_hash, sg_err[:120] if sg_err else "no output")
            continue

        try:
            sg_data = json.loads(world_json.read_text(encoding="utf-8-sig"))
            sg_data["SchemaVersion"] = "scene-graph/v1"
            sg_data["nif_hash"] = nif_hash
            sg_data["generated_at"] = _now_iso()
            sg_data["probe_command"] = f"probe-nif-scene-graph --id {nif_hash}"
            _atomic_write_json(world_json, sg_data)

            # Write FT-3 sidecar if OBJ exists (may not if manifest references lost file)
            if obj_path.exists():
                if not sidecar_path.exists():
                    _write_obj_sidecar(obj_path, entry)
                _enrich_sidecar_with_scene_graph(sidecar_path, sg_data, mesh_block=mesh_block)

            enriched += 1
            log.info(
                "[%d/%d] OK %s: %d nodes, %d meshes (%.1fs)",
                idx + 1,
                len(entries),
                nif_hash,
                sg_data.get("NodeCount", 0),
                sg_data.get("MeshCount", 0),
                sg_elapsed,
            )
        except (json.JSONDecodeError, KeyError, OSError) as exc:
            failed += 1
            log.warning("[%d/%d] PARSE %s: %s", idx + 1, len(entries), nif_hash, exc)

    log.info("FT-4.6 done: %d enriched, %d failed, %d skipped", enriched, failed, skipped)
    return 0 if failed == 0 else 1


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
    if args.command == "scene-graph-only":
        return _cmd_scene_graph_only(args)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
