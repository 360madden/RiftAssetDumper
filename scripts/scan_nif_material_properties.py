#!/usr/bin/env python3
"""Scan NIF material properties for cohort assets using ``probe-nif`` CLI.

Runs ``dotnet run -- probe-nif`` for each asset, extracts property block counts
(NiTexturingProperty, NiMaterialProperty, NiVertexColorProperty), and writes a
consolidated ``material-scan-results.json`` to feed ``build_scene_manifest.py``.

Output schema: ``nif-material-scan-results/v1``
  - ``scanned_at``: ISO 8601 UTC timestamp
  - ``results``: dict keyed by asset_id → per-asset property counts

Usage:
    python scripts/scan_nif_material_properties.py --cohort-only        # 24 assets
    python scripts/scan_nif_material_properties.py --limit 10 --resume  # partial, skip existing
    python scripts/scan_nif_material_properties.py                      # all flythrough-index assets (217)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
COHORT_JSON = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage1" / "cohort.json"
FLYTHROUGH_INDEX = REPO_ROOT / "Assets" / "build" / "flythrough" / "flythrough-index.json"
DEFAULT_OUT = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage3" / "material-scan-results.json"
LIVE_ROOT = "C:/Program Files (x86)/Glyph/Games/RIFT/Live"
DOTNET_PROJECT = "src/RiftAssetDumper"
SCHEMA_VERSION = "nif-material-scan-results/v1"

# Block type names to count (normalized for case-insensitive matching)
PROPERTY_BLOCK_NAMES = {
    "nitexturingproperty": "texture_property_count",
    "nimaterialproperty": "material_property_count",
    "nivertexcolorproperty": "vertex_color_property_count",
}


def load_cohort_ids() -> list[str]:
    """Return unique asset IDs from cohort.json, stripped of any suffix.

    Some cohort entries carry a ``.world`` suffix (non-identity transform assets).
    The probe-nif CLI expects a 16-char hex ID prefix, so suffixes are stripped.
    """
    c = json.loads(COHORT_JSON.read_text(encoding="utf-8-sig"))
    seen: set[str] = set()
    ids: list[str] = []
    for e in c.get("cohort", []):
        raw = str(e["asset_id"])
        # Strip known suffixes
        for suffix in (".world",):
            if raw.endswith(suffix):
                raw = raw[: -len(suffix)]
                break
        if raw not in seen:
            seen.add(raw)
            ids.append(raw)
    return ids


def load_flythrough_ids() -> list[str]:
    """Return all asset IDs from flythrough-index.json."""
    idx = json.loads(FLYTHROUGH_INDEX.read_text(encoding="utf-8-sig"))
    return sorted(str(k) for k in idx.get("assets", {}).keys())


def load_existing_results(path: Path) -> dict[str, dict[str, Any]]:
    """Load previously scanned results for --resume."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return dict(data.get("results", {}))
    except Exception:
        return {}


def probe_one(asset_id: str, out_dir: Path) -> dict[str, Any] | None:
    """Run ``probe-nif`` for one asset and return the parsed JSON output.

    The CLI writes ``nif-probe.json`` into *out_dir*.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "dotnet",
        "run",
        "--project",
        str(REPO_ROOT / DOTNET_PROJECT),
        "--",
        "probe-nif",
        "--root",
        LIVE_ROOT,
        "--id",
        asset_id,
        "--out",
        str(out_dir),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(REPO_ROOT),
        )
        if result.returncode != 0:
            stderr_tail = result.stderr.strip()[-300:] if result.stderr else "(no stderr)"
            print(f"  ERROR: exit {result.returncode}: {stderr_tail}", file=sys.stderr)
            return None
    except subprocess.TimeoutExpired:
        print("  TIMEOUT", file=sys.stderr)
        return None
    except OSError as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return None

    probe_json = out_dir / "nif-probe.json"
    if not probe_json.exists():
        print("  ERROR: no output JSON", file=sys.stderr)
        return None

    try:
        return json.loads(probe_json.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ERROR: cannot parse JSON: {e}", file=sys.stderr)
        return None


def extract_property_counts(probe: dict[str, Any]) -> dict[str, Any]:
    """Extract material property counts from a ``probe-nif`` JSON result."""
    header = probe.get("Header", {})
    block_types: list[dict[str, Any]] = header.get("BlockTypes", [])

    counts: dict[str, int] = {
        "texture_property_count": 0,
        "material_property_count": 0,
        "vertex_color_property_count": 0,
    }

    for bt in block_types:
        name = bt.get("NormalizedName", bt.get("Name", "")).lower()
        usage = bt.get("UsageCount", 0)
        if name in PROPERTY_BLOCK_NAMES:
            counts[PROPERTY_BLOCK_NAMES[name]] = usage

    return {
        **counts,
        "nif_block_count": header.get("BlockCount", 0),
        "nif_version": str(header.get("VersionText", header.get("Version", ""))),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan NIF material properties via probe-nif CLI",
    )
    parser.add_argument(
        "--cohort-only",
        action="store_true",
        help="Only scan 24 cohort assets (default: all flythrough-index assets)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of assets to scan",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip assets already present in the output file",
    )
    parser.add_argument(
        "--out",
        help=f"Output path (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()

    # --- Determine asset IDs ---
    if args.cohort_only:
        ids = load_cohort_ids()
    else:
        ids = load_flythrough_ids()

    if args.limit > 0:
        ids = ids[: args.limit]

    # --- Load existing results for resume ---
    out_path = Path(args.out) if args.out else DEFAULT_OUT
    existing = load_existing_results(out_path) if args.resume else {}

    to_scan = [aid for aid in ids if aid not in existing]
    print(
        f"Assets: {len(ids)} total, {len(to_scan)} to scan, "
        f"{len(existing)} already scanned (resume={'on' if args.resume else 'off'})",
    )

    if not to_scan:
        print("Nothing to scan.")
        return 0

    # --- Scan ---
    results: dict[str, dict[str, Any]] = dict(existing)
    start_time = time.monotonic()
    success = 0
    failed = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for i, aid in enumerate(to_scan):
            print(f"[{i + 1}/{len(to_scan)}] {aid}...", end=" ", flush=True)
            asset_out = tmp / aid
            probe = probe_one(aid, asset_out)
            if probe is None:
                failed += 1
                print("FAILED")
                continue

            counts = extract_property_counts(probe)
            results[aid] = counts
            success += 1
            tex = counts["texture_property_count"]
            mat = counts["material_property_count"]
            vc = counts["vertex_color_property_count"]
            blocks = counts["nif_block_count"]
            print(f"tex={tex} mat={mat} vc={vc} blocks={blocks}")

    elapsed = time.monotonic() - start_time

    # --- Write consolidated results ---
    report: dict[str, Any] = {
        "SchemaVersion": SCHEMA_VERSION,
        "scanned_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": len(results),
        "results": results,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"\nDone: {success} scanned, {failed} failed, {elapsed:.1f}s")
    print(f"Output: {out_path}")

    # Print summary stats
    tex_nonzero = sum(1 for r in results.values() if r["texture_property_count"] > 0)
    mat_nonzero = sum(1 for r in results.values() if r["material_property_count"] > 0)
    vc_nonzero = sum(1 for r in results.values() if r["vertex_color_property_count"] > 0)
    print(f"NiTexturingProperty  >0: {tex_nonzero}/{len(results)}")
    print(f"NiMaterialProperty   >0: {mat_nonzero}/{len(results)}")
    print(f"NiVertexColorProperty>0: {vc_nonzero}/{len(results)}")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
