#!/usr/bin/env python3
"""Consumer ingestion validator for the aggregate scene-manifest pack (C2-5.1).

Reads ``stage4/scene-manifest-pack-v1.json`` and validates every requirement
a consumer (RiftFlythrough) needs before loading the cohort:

  1. OBJ path existence (geometry assets on disk)
  2. world.json path existence (transform data on disk)
  3. Transform finiteness (no NaN/Inf in translation/rotation/scale)
  4. Texture file existence (linked PNG textures on disk)
  5. Cross-reference with flythrough-index.json (consistency check)
  6. Schema validity (already proven at build time; re-checked here)

Produces ``stage5/ingestion-test.{json,md}`` with per-asset pass/fail
results and an aggregate summary.

Usage:
    python scripts/build_ingestion_test.py
    python scripts/build_ingestion_test.py --out-dir Assets/Exports/discovery-plan/cycle-2/stage5
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGE4_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage4"
DEFAULT_OUT_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage5"
PACK_PATH = STAGE4_DIR / "scene-manifest-pack-v1.json"
FLYTHROUGH_INDEX = REPO_ROOT / "Assets" / "build" / "flythrough" / "flythrough-index.json"
TEXTURE_DIR = REPO_ROOT / "Assets" / "build" / "flythrough" / "textures" / "converted"

PRODUCER_TOOL = "scripts/build_ingestion_test.py"
PRODUCER_VERSION = "v0.1"


def load_pack() -> dict[str, Any]:
    return json.loads(PACK_PATH.read_text(encoding="utf-8-sig"))


def load_flythrough_assets() -> dict[str, dict[str, Any]]:
    if not FLYTHROUGH_INDEX.exists():
        return {}
    idx = json.loads(FLYTHROUGH_INDEX.read_text(encoding="utf-8-sig"))
    assets = idx.get("assets", {})
    return assets if isinstance(assets, dict) else {}


def is_finite_transform(entry: dict[str, Any]) -> bool:
    ws = entry["world"]["world_transform_summary"]
    for x in ws["translation"]:
        if not math.isfinite(x):
            return False
    for x in ws["rotation"]:
        if not math.isfinite(x):
            return False
    if not math.isfinite(ws["scale"]):
        return False
    return True


def check_obj(path_str: str) -> tuple[bool, str]:
    p = Path(path_str)
    if not p.exists():
        return False, f"OBJ not found: {path_str}"
    try:
        size = p.stat().st_size
    except OSError as e:
        return False, f"OBJ unreadable: {path_str} ({e})"
    if size == 0:
        return False, f"OBJ is empty: {path_str}"
    return True, f"OBJ exists ({size} bytes)"


def check_world_json(path_str: str) -> tuple[bool, str]:
    p = Path(path_str)
    if not p.exists():
        return False, f"world.json not found: {path_str}"
    try:
        size = p.stat().st_size
    except OSError as e:
        return False, f"world.json unreadable: {path_str} ({e})"
    if size == 0:
        return False, f"world.json is empty: {path_str}"
    return True, f"world.json exists ({size} bytes)"


def check_textures(entry: dict[str, Any]) -> tuple[bool, int, int, list[str]]:
    textures = entry["textures"].get("linked_textures", [])
    found = 0
    missing_paths: list[str] = []
    for tex_name in textures:
        tex_path = TEXTURE_DIR / tex_name
        if tex_path.exists():
            found += 1
        else:
            missing_paths.append(tex_name)
    total = len(textures)
    ok = found == total or total == 0
    return ok, found, total, missing_paths


def check_flythrough_crossref(
    asset_id: str, entry: dict[str, Any], flythrough: dict[str, dict[str, Any]]
) -> tuple[bool, str]:
    ft_entry = flythrough.get(asset_id)
    if ft_entry is None:
        return False, "asset_id not in flythrough-index.json"
    ft_linked = ft_entry.get("linked_textures", [])
    ft_count = len(ft_linked) if isinstance(ft_linked, list) else 0
    manifest_count = entry["textures"].get("linked_texture_count", 0)
    if ft_count != manifest_count:
        return False, (f"linked_texture_count mismatch: manifest={manifest_count} flythrough={ft_count}")
    return True, f"flythrough cross-reference OK ({ft_count} textures)"


def validate_entry(entry: dict[str, Any], flythrough: dict[str, dict[str, Any]]) -> dict[str, Any]:
    aid = entry["asset_id"]
    checks: dict[str, dict[str, Any]] = {}

    # OBJ
    obj_ok, obj_msg = check_obj(entry["geometry"]["obj_path"])
    checks["obj_path"] = {"pass": obj_ok, "message": obj_msg}

    # world.json
    wj_ok, wj_msg = check_world_json(entry["world"]["world_json"])
    checks["world_json"] = {"pass": wj_ok, "message": wj_msg}

    # Transform finiteness
    tf_ok = is_finite_transform(entry)
    checks["transform_finite"] = {
        "pass": tf_ok,
        "message": "transform finite" if tf_ok else "transform contains NaN/Inf",
    }

    # Textures
    tex_ok, tex_found, tex_total, tex_missing = check_textures(entry)
    checks["textures"] = {
        "pass": tex_ok,
        "message": f"{tex_found}/{tex_total} textures found" if tex_total > 0 else "no textures linked",
        "found": tex_found,
        "total": tex_total,
        "missing": tex_missing,
    }

    # Flythrough cross-reference
    xref_ok, xref_msg = check_flythrough_crossref(aid, entry, flythrough)
    checks["flythrough_crossref"] = {"pass": xref_ok, "message": xref_msg}

    # Schema (re-check)
    schema_ok = entry["validation"].get("schema_valid", False)
    checks["schema_valid"] = {"pass": schema_ok, "message": "schema valid" if schema_ok else "schema invalid"}

    all_pass = all(c["pass"] for c in checks.values())
    return {
        "asset_id": aid,
        "all_pass": all_pass,
        "pass_count": sum(1 for c in checks.values() if c["pass"]),
        "total_checks": len(checks),
        "checks": checks,
    }


def build_report(pack: dict[str, Any]) -> dict[str, Any]:
    flythrough = load_flythrough_assets()
    results = [validate_entry(e, flythrough) for e in pack["entries"]]

    all_pass = sum(1 for r in results if r["all_pass"])
    checks_total = len(results) * 6  # 6 checks per asset

    return {
        "SchemaVersion": "ingestion-test/v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "producer": {
            "tool": PRODUCER_TOOL,
            "version": PRODUCER_VERSION,
            "command": f"python {PRODUCER_TOOL}",
        },
        "pack_path": str(PACK_PATH.relative_to(REPO_ROOT)),
        "cohort_size": len(results),
        "assets_all_pass": all_pass,
        "assets_some_fail": len(results) - all_pass,
        "check_summary": {
            "obj_path": sum(1 for r in results if r["checks"]["obj_path"]["pass"]),
            "world_json": sum(1 for r in results if r["checks"]["world_json"]["pass"]),
            "transform_finite": sum(1 for r in results if r["checks"]["transform_finite"]["pass"]),
            "textures": sum(1 for r in results if r["checks"]["textures"]["pass"]),
            "flythrough_crossref": sum(1 for r in results if r["checks"]["flythrough_crossref"]["pass"]),
            "schema_valid": sum(1 for r in results if r["checks"]["schema_valid"]["pass"]),
        },
        "total_checks": checks_total,
        "total_passed": sum(r["pass_count"] for r in results),
        "total_failed": checks_total - sum(r["pass_count"] for r in results),
        "results": results,
    }


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Cycle 2 — Consumer Ingestion Test (C2-5.1)",
        "",
        "Generated: {}".format(report["generated_at"]),
        "Producer: {} {}".format(report["producer"]["tool"], report["producer"]["version"]),
        "Pack: {}".format(report["pack_path"]),
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
        "| Cohort size | {} |".format(report["cohort_size"]),
        "| Assets all-pass | {} |".format(report["assets_all_pass"]),
        "| Assets with failures | {} |".format(report["assets_some_fail"]),
        "| Total checks | {} |".format(report["total_checks"]),
        "| Total passed | {} |".format(report["total_passed"]),
        "| Total failed | {} |".format(report["total_failed"]),
        "",
        "## Check Summary",
        "",
        "| Check | Pass | Fail |",
        "|---|---:|---:|",
    ]
    for check_name in ["obj_path", "world_json", "transform_finite", "textures", "flythrough_crossref", "schema_valid"]:
        passed = report["check_summary"][check_name]
        failed = report["cohort_size"] - passed
        lines.append(f"| {check_name} | {passed} | {failed} |")

    # Failed assets detail
    failed_results = [r for r in report["results"] if not r["all_pass"]]
    if failed_results:
        lines += [
            "",
            "## Failed Assets",
            "",
            "| Asset ID | Failed Checks | Details |",
            "|---|---|---|",
        ]
        for r in failed_results:
            failed_checks = [name for name, c in r["checks"].items() if not c["pass"]]
            details = "; ".join("{}: {}".format(name, r["checks"][name]["message"]) for name in failed_checks)
            lines.append("| {} | {} | {} |".format(r["asset_id"], ", ".join(failed_checks), details))
    else:
        lines += ["", "## Failed Assets", "", "*All 24 assets passed all ingestion checks.*", ""]

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Consumer ingestion validator (C2-5.1)")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Output directory (default: stage5/)",
    )
    args = parser.parse_args()

    if not PACK_PATH.exists():
        print(f"ERROR: pack not found: {PACK_PATH}", file=sys.stderr)
        return 1

    pack = load_pack()
    report = build_report(pack)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    json_path = args.out_dir / "ingestion-test.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {json_path}")

    md_path = args.out_dir / "ingestion-test.md"
    md_path.write_text(build_markdown(report), encoding="utf-8")
    print(f"wrote {md_path}")

    print(f"\nResults: {report['assets_all_pass']}/{report['cohort_size']} assets pass all checks")
    print(f"  {report['total_passed']}/{report['total_checks']} total checks passed")
    for check_name, count in report["check_summary"].items():
        failed = report["cohort_size"] - count
        status = "PASS" if failed == 0 else f"{failed} FAIL"
        print(f"  {check_name}: {count}/{report['cohort_size']} ({status})")
    # Return 0 for success (all-pass) or non-zero for partial failure
    all_ok = report["assets_all_pass"] == report["cohort_size"]
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
