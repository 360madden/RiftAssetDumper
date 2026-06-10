#!/usr/bin/env python3
"""FT-6 validation suite for the RiftFlythrough pipeline quality gate.

Checks:
  1. OBJ integrity — file existence, vertex/face counts, NaN, index bounds,
     negative indices, SHA256 match against export-manifest
  2. world.json completeness — every OBJ with known asset_id has a valid
     world.json in worlds/; structure validation (NodeCount, MeshCount,
     MeshesAttached, valid JSON)
  3. Cross-reference coverage — % of OBJs with world.json, gap analysis
  4. Face bounds — verify face indices are within vertex range
  5. Manifest consistency — export-manifest vs scene-graph-manifest counts

Output:
  - Summary to stdout
  - JSON report at Assets/build/flythrough/evidence/ft6.2/validation-report.json

Usage:
  python scripts/ft6_validation.py              # Full validation
  python scripts/ft6_validation.py --quick       # Skip per-OBJ face parsing
  python scripts/ft6_validation.py --json-only   # JSON output only, no stdout
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_MANIFEST_PATH = REPO_ROOT / "Exports" / "export-manifest.json"
SG_MANIFEST_PATH = REPO_ROOT / "Assets" / "build" / "flythrough" / "scene-graph-manifest.json"
WORLDS_DIR = REPO_ROOT / "Assets" / "build" / "flythrough" / "objs" / "worlds"
EVIDENCE_DIR = REPO_ROOT / "Assets" / "build" / "flythrough" / "evidence" / "ft6.2"


# ─── helpers ────────────────────────────────────────────────────────────────


def _safe_print(text: str) -> None:
    """Print, falling back to ASCII-safe replacements on encoding errors."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii", errors="replace"))


def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file. Returns empty dict on failure."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError, OSError:
        return {}


def _parse_obj_faces(text: str, v_count: int) -> tuple[int, int, bool, list[int], int]:
    """Parse face lines from OBJ text.

    Returns (face_count, max_index, bounds_ok, negative_indices, zero_count).
    """
    face_count = 0
    face_indices: list[int] = []
    for line in text.split("\n"):
        if line.startswith("f "):
            face_count += 1
            for p in line.split()[1:]:
                idx_str = p.split("/")[0]
                try:
                    face_indices.append(int(idx_str))
                except ValueError, TypeError:
                    pass

    max_idx = max(face_indices) if face_indices else -1
    neg_indices = [i for i in face_indices if i < 0]
    zero_count = sum(1 for i in face_indices if i == 0)
    bounds_ok = (max_idx <= v_count) if face_count > 0 else True

    return face_count, max_idx, bounds_ok, neg_indices, zero_count


# ─── 1. OBJ integrity ──────────────────────────────────────────────────────


def check_obj_integrity(
    entries: list[dict[str, Any]],
    quick: bool = False,
) -> dict[str, Any]:
    """Validate OBJ files referenced in the export manifest.

    Checks: file existence, vertex/face counts, NaN, index bounds,
    negative indices, SHA256 match.
    """
    total = len(entries)
    missing = 0
    sha256_mismatch = 0
    nan_count = 0
    bounds_fail = 0
    neg_index_count = 0
    zero_face_idx = 0
    total_vertices = 0
    total_faces = 0
    total_bytes = 0
    issues: list[dict[str, Any]] = []

    for _i, entry in enumerate(entries):
        path_str = entry.get("path", "")
        obj_path = Path(path_str) if path_str else None
        aid = entry.get("asset_id", "") or "unknown"

        issue: dict[str, Any] | None = None

        if not obj_path or not obj_path.exists():
            missing += 1
            issues.append(
                {
                    "asset_id": aid,
                    "mesh_block": entry.get("mesh_block", "?"),
                    "check": "objs",
                    "severity": "error",
                    "detail": f"OBJ file not found: {path_str}",
                }
            )
            continue

        obj_bytes = obj_path.stat().st_size
        total_bytes += obj_bytes

        # Quick mode: just check existence and size
        if quick:
            v_count = entry.get("vertex_count", entry.get("positions", 0)) or 0
            f_count = entry.get("face_count", entry.get("faces", 0)) or 0
            total_vertices += v_count
            total_faces += f_count
            # Hash match check
            expected_sha = entry.get("sha256", "")
            if expected_sha:
                actual_sha = hashlib.sha256(obj_path.read_bytes()).hexdigest()
                if actual_sha != expected_sha:
                    sha256_mismatch += 1
                    issues.append(
                        {
                            "asset_id": aid,
                            "mesh_block": entry.get("mesh_block", "?"),
                            "check": "hash",
                            "severity": "warning",
                            "detail": f"SHA256 mismatch: expected {expected_sha[:12]}..., got {actual_sha[:12]}...",
                        }
                    )
            continue

        # Full check: parse OBJ content (read bytes once for hash + text)
        try:
            raw_bytes = obj_path.read_bytes()
            text = raw_bytes.decode("utf-8", errors="ignore")
        except OSError:
            missing += 1
            issues.append(
                {
                    "asset_id": aid,
                    "mesh_block": entry.get("mesh_block", "?"),
                    "check": "objs",
                    "severity": "error",
                    "detail": f"Cannot read OBJ: {path_str}",
                }
            )
            continue

        # Vertex count
        v_count = text.count("\nv ") + (1 if text.startswith("v ") else 0)
        total_vertices += v_count

        # NaN check
        has_nan = "nan" in text.lower()
        if has_nan:
            nan_count += 1
            if issue is None:
                issue = {
                    "asset_id": aid,
                    "mesh_block": entry.get("mesh_block", "?"),
                    "check": "objs",
                    "severity": "error",
                    "detail": "",
                }
            issue["detail"] += " NaN in OBJ content;"

        # Face parsing (single pass for all stats)
        f_count, max_idx, bounds_ok, neg_indices, zero_count = _parse_obj_faces(text, v_count)
        total_faces += f_count

        if not bounds_ok:
            bounds_fail += 1
            if issue is None:
                issue = {
                    "asset_id": aid,
                    "mesh_block": entry.get("mesh_block", "?"),
                    "check": "objs",
                    "severity": "error",
                    "detail": "",
                }
            issue["detail"] += f" max face index {max_idx} > vertex count {v_count};"

        if neg_indices:
            neg_index_count += 1
            if issue is None:
                issue = {
                    "asset_id": aid,
                    "mesh_block": entry.get("mesh_block", "?"),
                    "check": "objs",
                    "severity": "warning",
                    "detail": "",
                }
            issue["detail"] += f" {len(neg_indices)} negative face indices;"

        if zero_count:
            zero_face_idx += 1
            if issue is None:
                issue = {
                    "asset_id": aid,
                    "mesh_block": entry.get("mesh_block", "?"),
                    "check": "objs",
                    "severity": "warning",
                    "detail": "",
                }
            issue["detail"] += f" {zero_count} zero-valued face indices (OBJ is 1-based);"

        # SHA256 check (reuse already-read bytes)
        expected_sha = entry.get("sha256", "")
        if expected_sha:
            actual_sha = hashlib.sha256(raw_bytes).hexdigest()
            if actual_sha != expected_sha:
                sha256_mismatch += 1
                if issue is None:
                    issue = {
                        "asset_id": aid,
                        "mesh_block": entry.get("mesh_block", "?"),
                        "check": "hash",
                        "severity": "warning",
                        "detail": "",
                    }
                issue["detail"] += f" SHA256 mismatch (expected {expected_sha[:12]}..., got {actual_sha[:12]}...);"

        if issue:
            issue["detail"] = issue["detail"].rstrip(";")
            issues.append(issue)

    # Summary
    errors = [i for i in issues if i.get("severity") == "error"]
    warnings = [i for i in issues if i.get("severity") == "warning"]

    return {
        "total_objs": total,
        "missing": missing,
        "present": total - missing,
        "nan_count": nan_count,
        "bounds_fail": bounds_fail,
        "neg_index_count": neg_index_count,
        "zero_face_idx": zero_face_idx,
        "sha256_mismatch": sha256_mismatch,
        "total_vertices": total_vertices,
        "total_faces": total_faces,
        "total_bytes": total_bytes,
        "errors": len(errors),
        "warnings": len(warnings),
        "issues": issues,
        "status": "pass" if not errors else "fail",
    }


# ─── 2. world.json completeness ────────────────────────────────────────────


def check_world_json_coverage(
    sg_manifest: dict[str, Any],
    deduped_ids: set[str],
) -> dict[str, Any]:
    """Check world.json coverage for OBJs with known asset IDs.

    Returns coverage stats and gap list.
    """
    sg_entries = sg_manifest.get("entries", [])
    sg_ids = {e["asset_id"] for e in sg_entries if e.get("asset_id")}

    covered = deduped_ids & sg_ids
    missing = deduped_ids - sg_ids

    return {
        "total_deduped_ids": len(deduped_ids),
        "world_json_count": len(sg_ids),
        "covered": len(covered),
        "missing_world_json": len(missing),
        "coverage_pct": round(len(covered) / len(deduped_ids) * 100, 1) if deduped_ids else 0,
        "missing_ids": sorted(missing)[:50],  # first 50 for readability
        "status": "pass" if len(missing) == 0 else "warn",
    }


def validate_world_jsons(sg_manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate each world.json: file existence, valid JSON, structure."""
    sg_entries = sg_manifest.get("entries", [])
    total = len(sg_entries)
    missing_files = 0
    invalid_json = 0
    empty_nodes = 0
    node_mesh_mismatch = 0
    issues: list[dict[str, Any]] = []

    for entry in sg_entries:
        aid = entry.get("asset_id", "unknown")
        wj_name = entry.get("world_json", f"{aid}.world.json")
        wj_path = WORLDS_DIR / wj_name

        if not wj_path.exists():
            missing_files += 1
            issues.append(
                {
                    "asset_id": aid,
                    "check": "world_json",
                    "severity": "error",
                    "detail": f"world.json missing: {wj_name}",
                }
            )
            continue

        try:
            wj = json.loads(wj_path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError) as exc:
            invalid_json += 1
            issues.append(
                {
                    "asset_id": aid,
                    "check": "world_json",
                    "severity": "error",
                    "detail": f"Invalid world.json: {exc}",
                }
            )
            continue

        nodes = wj.get("Nodes", [])
        meshes = wj.get("Meshes", [])
        nc = wj.get("NodeCount", len(nodes))
        mc = wj.get("MeshCount", len(meshes))

        if not nodes:
            empty_nodes += 1
            issues.append(
                {
                    "asset_id": aid,
                    "check": "world_json",
                    "severity": "warning",
                    "detail": "world.json has empty Nodes array",
                }
            )

        if nc < mc:
            node_mesh_mismatch += 1
            issues.append(
                {
                    "asset_id": aid,
                    "check": "world_json",
                    "severity": "warning",
                    "detail": f"NodeCount ({nc}) < MeshCount ({mc})",
                }
            )

    errors = [i for i in issues if i.get("severity") == "error"]
    warnings = [i for i in issues if i.get("severity") == "warning"]

    return {
        "total_world_jsons": total,
        "missing_files": missing_files,
        "invalid_json": invalid_json,
        "empty_nodes": empty_nodes,
        "node_mesh_mismatch": node_mesh_mismatch,
        "errors": len(errors),
        "warnings": len(warnings),
        "issues": issues,
        "status": "pass" if not errors else "fail",
    }


# ─── 3. Manifest consistency ───────────────────────────────────────────────


def check_manifest_consistency(
    export_manifest: dict[str, Any],
    sg_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Check consistency between export-manifest and scene-graph-manifest."""
    em_summary = export_manifest.get("summary", {})
    em_total = em_summary.get("total_obj_files", 0)
    em_unique = em_summary.get("total_unique_asset_ids", 0)
    em_faced = em_summary.get("faced", 0)
    em_posonly = em_summary.get("position_only", 0)
    em_verts = em_summary.get("total_vertices", 0)
    em_faces = em_summary.get("total_faces", 0)
    em_bytes_count = em_summary.get("total_bytes", 0)

    sg_total = sg_manifest.get("total_world_jsons", 0)
    sg_bytes = sg_manifest.get("total_bytes", 0)

    # Check if scene-graph coverage matches unique IDs
    em_ids = {
        e.get("asset_id", "")[:16]
        for e in export_manifest.get("entries", [])
        if e.get("asset_id") and len(e.get("asset_id", "")) == 16
    }
    sg_ids = {e.get("asset_id", "") for e in sg_manifest.get("entries", []) if e.get("asset_id")}
    gap = em_ids - sg_ids

    return {
        "export_manifest_total_objs": em_total,
        "export_manifest_unique_ids": em_unique,
        "export_manifest_faced": em_faced,
        "export_manifest_posonly": em_posonly,
        "export_manifest_vertices": em_verts,
        "export_manifest_faces": em_faces,
        "export_manifest_bytes": em_bytes_count,
        "scene_graph_world_jsons": sg_total,
        "scene_graph_bytes": sg_bytes,
        "ids_in_em_only": len(gap),
        "gap_sample": sorted(gap)[:20],
        "status": "pass" if len(gap) == 0 else "warn",
    }


# ─── main ───────────────────────────────────────────────────────────────────


def _deduplicate_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate entries by (asset_id, mesh_block), keeping the one with
    the largest file_size."""
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for e in entries:
        aid = e.get("asset_id", "") or "unknown"
        mb = str(e.get("mesh_block", "?"))
        size = int(e.get("file_size", 0) or 0)
        key = (aid, mb)
        if key not in by_key or size > int(by_key[key].get("file_size", 0) or 0):
            by_key[key] = e
    return list(by_key.values())


def run(args: argparse.Namespace) -> int:
    """Run the full validation suite."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    # Load manifests
    export_manifest = _load_json(EXPORT_MANIFEST_PATH)
    sg_manifest = _load_json(SG_MANIFEST_PATH)

    if not export_manifest:
        _safe_print("ERROR: export-manifest.json not found or empty")
        return 1
    if not sg_manifest:
        _safe_print("WARNING: scene-graph-manifest.json not found — skipping world.json checks")

    entries = export_manifest.get("entries", [])
    deduped = _deduplicate_entries(entries)
    deduped_ids = {e["asset_id"] for e in deduped if e.get("asset_id") and len(e.get("asset_id", "")) == 16}

    # ── 1. OBJ integrity ──
    if not args.quick:
        _safe_print("[BUSY] Checking OBJ integrity...")
    obj_result = check_obj_integrity(deduped, quick=args.quick)

    # ── 2. world.json ──
    coverage: dict[str, Any] = {}
    wj_result: dict[str, Any] = {}
    if sg_manifest:
        if not args.quick:
            _safe_print("[BUSY] Checking world.json coverage...")
        coverage = check_world_json_coverage(sg_manifest, deduped_ids)
        wj_result = validate_world_jsons(sg_manifest)

    # ── 3. Manifest consistency ──
    consistency: dict[str, Any] = {}
    if sg_manifest:
        consistency = check_manifest_consistency(export_manifest, sg_manifest)

    # ── Aggregate ──
    all_ok = (
        obj_result["status"] == "pass"
        and wj_result.get("status", "pass") == "pass"
        and coverage.get("status", "pass") != "fail"
        and consistency.get("status", "pass") != "fail"
    )

    report = {
        "schema": "ft6-validation-report-v1",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "overall_status": "pass" if all_ok else "warn",
        "objs": obj_result,
        "world_jsons": wj_result,
        "coverage": coverage,
        "consistency": consistency,
    }

    # Write JSON report
    report_path = EVIDENCE_DIR / "validation-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    # ── Print summary ──
    if not args.json_only:
        _safe_print("")
        _safe_print("=" * 70)
        _safe_print("  FT-6.2 Validation Suite — RiftFlythrough Quality Gate")
        _safe_print("=" * 70)
        _safe_print("")
        _safe_print("  --- OBJ Integrity ---")
        _safe_print(f"  Total (deduped):     {obj_result['total_objs']:>6}")
        _safe_print(f"  Present:             {obj_result['present']:>6}")
        _safe_print(f"  Missing:             {obj_result['missing']:>6}")
        if not args.quick:
            _safe_print(f"  Total vertices:      {obj_result['total_vertices']:>6}")
            _safe_print(f"  Total faces:         {obj_result['total_faces']:>6}")
            _safe_print(f"  Total OBJ bytes:     {obj_result['total_bytes']:>10,}")
            _safe_print(f"  NaN detected:        {obj_result['nan_count']:>6}")
            _safe_print(f"  Index bounds fail:   {obj_result['bounds_fail']:>6}")
            _safe_print(f"  Negative indices:    {obj_result['neg_index_count']:>6}")
            _safe_print(f"  Zero face indices:   {obj_result['zero_face_idx']:>6}")
            _safe_print(f"  SHA256 mismatches:   {obj_result['sha256_mismatch']:>6}")
        _safe_print(f"  OBJ status:          {'[PASS]' if obj_result['status'] == 'pass' else '[FAIL]'}")
        _safe_print("")

        if sg_manifest:
            _safe_print("  --- World.json Completeness ---")
            _safe_print(f"  Total world.jsons:   {wj_result.get('total_world_jsons', 0):>6}")
            _safe_print(f"  Missing files:       {wj_result.get('missing_files', 0):>6}")
            _safe_print(f"  Invalid JSON:        {wj_result.get('invalid_json', 0):>6}")
            _safe_print(f"  Empty nodes:         {wj_result.get('empty_nodes', 0):>6}")
            _safe_print(f"  Node<Mesh mismatch:  {wj_result.get('node_mesh_mismatch', 0):>6}")
            _safe_print(f"  WJ status:           {'[PASS]' if wj_result.get('status') == 'pass' else '[FAIL]'}")
            _safe_print("")

            _safe_print("  --- Cross-Reference Coverage ---")
            _safe_print(f"  Deduped asset IDs:   {coverage.get('total_deduped_ids', 0):>6}")
            _safe_print(f"  With world.json:     {coverage.get('covered', 0):>6}")
            _safe_print(f"  Missing world.json:  {coverage.get('missing_world_json', 0):>6}")
            _safe_print(f"  Coverage:            {coverage.get('coverage_pct', 0):>6}%")
            _safe_print("")

            _safe_print("  --- Manifest Consistency ---")
            _safe_print(f"  EM unique IDs:       {consistency.get('export_manifest_unique_ids', 0):>6}")
            _safe_print(f"  SG world.jsons:      {consistency.get('scene_graph_world_jsons', 0):>6}")
            _safe_print(f"  IDs only in EM:      {consistency.get('ids_in_em_only', 0):>6}")
            _safe_print("")

        status_icon = "[PASS]"
        if not all_ok:
            status_icon = "[WARN]"
            if obj_result["status"] == "fail" or wj_result.get("status") == "fail":
                status_icon = "[FAIL]"

        _safe_print(f"  Overall:             {status_icon}  (report: {report_path})")
        _safe_print("")

    return 0 if all_ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FT-6.2 validation suite for RiftFlythrough quality gate",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip per-OBJ face parsing (faster, less thorough)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Write JSON report only, no stdout summary",
    )
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
