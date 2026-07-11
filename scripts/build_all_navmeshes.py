"""build_all_navmeshes.py — NM-6 M6.1 batch navmesh generator.

Iterates eligible zones (>=5 walkable assets per flythrough-index.zone.tuple
intersected with walkability-classification labels), invokes the existing
single-zone pipeline (extract_zone_geometry -> build_navmesh -> validate_navmesh)
via subprocess for each zone with fail-isolation, then aggregates results into
Exports/navmesh-phase6/navmesh-index.json (schema: navmesh-index-v1).

Why subprocess (not direct function calls):
  - The single-zone scripts each own their CLI, JVM bring-up, and argument
    handling. Duplicating that here doubles maintenance surface.
  - Subprocess invocation mirrors how `bulk_export_for_flythrough.py` (FT-2)
    orchestrated the per-asset pipeline, keeping the orchestration pattern
    consistent across NM and Flythrough lanes.
  - Failures in JVM startup, Recast build failures, or schema-validation
    errors are surfaced as non-zero exit codes per zone (fail-isolation).

Schema for the index doc is at docs/schemas/navmesh-index-v1.schema.json.
The fields `connected_zones` (M6.2 adjacency hook) and the `bounds` block
(M6.3 cross-zone routing hook) are pre-wired but empty until M6.2/M6.3.

Usage:
  python scripts/build_all_navmeshes.py run                       # full batch
  python scripts/build_all_navmeshes.py status                    # print index summary
  python scripts/build_all_navmeshes.py run --zones ep1.world_objects.dungeons
  python scripts/build_all_navmeshes.py run --min-walkable 3      # override threshold
  python scripts/build_all_navmeshes.py run --validate-schema     # jsonschema check
"""

from __future__ import annotations

__all__ = [
    # Public constants -- paths and locked schema values
    "FLY_INDEX",
    "INDEX_PATH",
    "PHASE6_DIR",
    "SCHEMA_VERSION",
    "WALK_PATH",
    "WALKABLE_LABELS",
    "ZONES_SUBDIR",
    # Internal helpers (used by build_index_doc, main flow, and tests)
    "_print_status",
    "_run_batch",
    "_run_step",
    "_slugify",
    "_tail",
    "_validate_against_schema",
    "_write_partial",
    "_zone_dir",
    # Public call surface
    "build_index_doc",
    "build_one_zone",
    "compute_zone_counts",
    "load_flythrough_index",
    "load_walkability",
    "main",
    "select_eligible_zones",
    # Re-exported so tests can monkeypatch subprocess.run via bam.subprocess.run.
    "subprocess",
]

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path so scripts.* imports work when invoked as `python scripts/...`
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.rift_workflow_utils import load_json_report  # noqa: E402

REPO_ROOT = _PROJECT_ROOT
FLY_INDEX = REPO_ROOT / "Assets" / "build" / "flythrough" / "flythrough-index.json"
WALK_PATH = REPO_ROOT / "Exports" / "navmesh-phase0" / "walkability-classification.json"
PHASE6_DIR = REPO_ROOT / "Exports" / "navmesh-phase6"
ZONES_SUBDIR = "zones"
INDEX_PATH = PHASE6_DIR / "navmesh-index.json"

# Walkable labels used for eligibility + downstream filter (locked in schema).
WALKABLE_LABELS: frozenset[str] = frozenset(
    {
        "walkable_structure",
        "walkable_terrain",
        "walkable_floor",
        "walkable_platform",
        "potentially_walkable",
    }
)
SCHEMA_VERSION = "navmesh-index-v1"
DEFAULT_MIN_WALKABLE = 5

# Pipeline scripts (CWD must be REPO_ROOT so scripts/ imports resolve in subprocesses).
_PYTHON = sys.executable
_EXTRACT_SCRIPT = "scripts/extract_zone_geometry.py"
_BUILD_SCRIPT = "scripts/build_navmesh.py"
_VALIDATE_SCRIPT = "scripts/validate_navmesh.py"


def _slugify(zone_tuple: str) -> str:
    """Mirror extract_zone_geometry._slugify so output paths line up."""
    import re

    return re.sub(r"[^a-zA-Z0-9]+", "-", zone_tuple).strip("-")


def _zone_dir(slug: str) -> Path:
    """Exports/navmesh-phase6/zones/<slug>/ — every per-zone artifact lives here."""
    return PHASE6_DIR / ZONES_SUBDIR / slug


def load_flythrough_index(path: Path = FLY_INDEX) -> dict[str, Any]:
    """Read flythrough-index.json; raise FileNotFoundError if missing."""
    if not path.exists():
        raise FileNotFoundError(f"flythrough-index.json not found: {path}")
    return load_json_report(path)


def load_walkability(path: Path = WALK_PATH) -> dict[str, str]:
    """Return asset_id -> label. Returns {} if the file is missing or malformed."""
    if not path.exists():
        return {}
    try:
        data = load_json_report(path)
    except (ValueError, json.JSONDecodeError) as e:
        print(
            f"[M6.1] WARN: walkability file at {path} is malformed/invalid; treating as empty (err={e})",
            file=sys.stderr,
        )
        return {}
    classifications = data.get("classifications") if isinstance(data, dict) else None
    if not isinstance(classifications, list):
        print(
            f"[M6.1] WARN: walkability file at {path} has no 'classifications' list; treating as empty",
            file=sys.stderr,
        )
        return {}
    out: dict[str, str] = {}
    for entry in classifications:
        if not isinstance(entry, dict):
            continue
        aid = entry.get("asset_id")
        label = entry.get("label")
        if isinstance(aid, str) and isinstance(label, str):
            out[aid] = label
    return out


def compute_zone_counts(
    fly_index: dict[str, Any],
    walk_by_aid: dict[str, str],
) -> tuple[Counter, Counter, list[str]]:
    """Group flythrough-index assets by zone.tuple and count walkable vs total.

    Returns:
        walkable_counts: zone_tuple -> #assets with a walkable label
        total_counts: zone_tuple -> #assets (any walkability status)
        missing_walk_assets: sorted list of asset_ids in flythrough-index that
            have no entry in walkability-classification.json (for diagnostics)
    """
    assets = fly_index.get("assets", {})
    walkable_counts: Counter = Counter()
    total_counts: Counter = Counter()
    missing: list[str] = []
    for aid, data in assets.items():
        if not isinstance(data, dict):
            continue
        zone = data.get("zone", {})
        if not isinstance(zone, dict):
            continue
        zone_tuple = zone.get("tuple")
        if not isinstance(zone_tuple, str) or not zone_tuple:
            continue
        total_counts[zone_tuple] += 1
        label = walk_by_aid.get(aid)
        if label is None:
            missing.append(aid)
            continue
        if label in WALKABLE_LABELS:
            walkable_counts[zone_tuple] += 1
    return walkable_counts, total_counts, sorted(missing)


def select_eligible_zones(
    walkable_counts: Counter,
    *,
    min_walkable: int = DEFAULT_MIN_WALKABLE,
) -> list[str]:
    """Return zone.tuple values whose walkable-asset count >= min_walkable, sorted alphabetically."""
    return sorted(t for t, c in walkable_counts.items() if c >= min_walkable)


def _run_step(
    args: list[str],
    *,
    cwd: Path = REPO_ROOT,
    timeout_s: int = 600,
) -> tuple[int, str, str]:
    """Run a subprocess step and capture stdout/stderr. Returns (rc, stdout, stderr).

    We do NOT raise on non-zero return codes -- the caller treats failure as a
    per-zone failure (status='failed') and continues the batch.
    """
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return int(proc.returncode), proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or "", (e.stderr or "") + f"\n[TIMEOUT after {timeout_s}s]"
    except FileNotFoundError as e:
        return 127, "", f"[executable not found: {e}]"


_STDOUT_TAIL_LINES = 30


def _tail(text: str, n: int = _STDOUT_TAIL_LINES) -> str:
    """Return the last n non-empty lines of `text` (used for failure diagnostics)."""
    if not text:
        return ""
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-n:])


def build_one_zone(
    zone_tuple: str,
    *,
    min_walkable: int = DEFAULT_MIN_WALKABLE,
    walkable_counts: Counter | None = None,
    total_counts: Counter | None = None,
    timeout_s: int = 600,
) -> dict[str, Any]:
    """Drive the extract -> build -> validate pipeline for a single zone.

    Returns a per-zone entry dict suitable for navmesh-index.json. Failures
    at any stage are captured in 'failure' (never raise), leaving the caller
    free to continue the batch.
    """
    slug = _slugify(zone_tuple)
    zdir = _zone_dir(slug)
    zdir.mkdir(parents=True, exist_ok=True)

    obj_path = zdir / "input.obj"
    meta_path = zdir / "input.metadata.json"
    build_path = zdir / "navmesh-build.json"
    val_path = zdir / "navmesh-validation.json"

    walkable = walkable_counts.get(zone_tuple, 0) if walkable_counts else 0
    total = total_counts.get(zone_tuple, 0) if total_counts else 0

    entry: dict[str, Any] = {
        "status": "failed",  # promoted to 'built' on success
        "slug": slug,
        "walkable_asset_count": walkable,
        "total_asset_count": total,
        "connected_zones": [],  # M6.2 hook
    }

    # --- Stage 1: extract_zone_geometry ---
    extract_args = [
        _PYTHON,
        _EXTRACT_SCRIPT,
        "--zone",
        zone_tuple,
        "--walkable-only",
        "--out",
        str(obj_path),
        "--out-meta",
        str(meta_path),
    ]
    rc, stdout, stderr = _run_step(extract_args, timeout_s=timeout_s)
    if rc != 0:
        entry["failure"] = {
            "stage": "extract",
            "message": (stderr or "extract_zone_geometry failed").strip().splitlines()[-1][:500],
            "returncode": rc,
            "stdout_tail": _tail(stdout),
            "stderr_tail": _tail(stderr),
        }
        _write_partial(obj_path, meta_path)
        return entry

    if not obj_path.exists():
        entry["failure"] = {
            "stage": "extract",
            "message": f"extract_zone_geometry succeeded but OBJ missing at {obj_path}",
            "returncode": rc,
            "stdout_tail": _tail(stdout),
            "stderr_tail": _tail(stderr),
        }
        return entry

    entry["obj_path"] = str(obj_path.relative_to(REPO_ROOT))

    # --- Stage 2: build_navmesh ---
    build_args = [
        _PYTHON,
        _BUILD_SCRIPT,
        "--obj",
        str(obj_path),
        "--adaptive",
        "--auto-cell-size",
        "--auto-agent-params",
        "--out",
        str(build_path),
    ]
    rc, stdout, stderr = _run_step(build_args, timeout_s=timeout_s)
    if rc != 0 or not build_path.exists():
        entry["failure"] = {
            "stage": "build",
            "message": (stderr or "build_navmesh failed").strip().splitlines()[-1][:500],
            "returncode": rc,
            "stdout_tail": _tail(stdout),
            "stderr_tail": _tail(stderr),
        }
        return entry

    entry["navmesh_json_path"] = str(build_path.relative_to(REPO_ROOT))

    # --- Stage 3: validate_navmesh ---
    val_args = [
        _PYTHON,
        _VALIDATE_SCRIPT,
        "--navmesh",
        str(build_path),
        "--obj",
        str(obj_path),
        "--out",
        str(val_path),
    ]
    rc, stdout, stderr = _run_step(val_args, timeout_s=timeout_s)
    if rc != 0 or not val_path.exists():
        entry["failure"] = {
            "stage": "validate",
            "message": (stderr or "validate_navmesh failed").strip().splitlines()[-1][:500],
            "returncode": rc,
            "stdout_tail": _tail(stdout),
            "stderr_tail": _tail(stderr),
        }
        return entry

    entry["validation_path"] = str(val_path.relative_to(REPO_ROOT))

    # Parse both reports for the stats/bounds block on the index entry.
    try:
        build_report = load_json_report(build_path)
        val_report = load_json_report(val_path)
    except (ValueError, json.JSONDecodeError) as e:
        entry["failure"] = {
            "stage": "validate",
            "message": f"could not parse produced JSON: {e}",
            "returncode": 0,
            "stdout_tail": "",
            "stderr_tail": "",
        }
        return entry

    stats: dict[str, Any] = {
        "poly_count": int(build_report.get("poly_count", 0) or build_report.get("mesh", {}).get("npolys", 0) or 0),
        "walkable_polys": int(build_report.get("mesh", {}).get("walkable_polys", 0) or 0),
        "vert_count": int(build_report.get("vert_count", 0) or build_report.get("mesh", {}).get("nverts", 0) or 0),
        "isolated_polys": int(val_report.get("summary", {}).get("isolated_polys", 0) or 0),
        "connected_components": int(val_report.get("summary", {}).get("connected_components", 0) or 0),
        "max_edge_length": float(val_report.get("summary", {}).get("max_edge_length", 0.0) or 0.0),
    }
    entry["stats"] = stats

    bounds = build_report.get("bounds")
    if isinstance(bounds, dict) and isinstance(bounds.get("bmin"), list) and isinstance(bounds.get("bmax"), list):
        entry["bounds"] = {
            "bmin": list(bounds["bmin"]),
            "bmax": list(bounds["bmax"]),
        }
    elif isinstance(val_report.get("summary", {}).get("bounds"), dict):
        # validate_navmesh fills subset; only emit if 3-element axes present.
        vb = val_report["summary"]["bounds"]
        if (
            isinstance(vb.get("min"), list)
            and len(vb["min"]) == 3
            and isinstance(vb.get("max"), list)
            and len(vb["max"]) == 3
        ):
            entry["bounds"] = {"bmin": list(vb["min"]), "bmax": list(vb["max"])}

    # Promote to 'built' ONLY if validation report is fully valid.
    if val_report.get("valid") is True:
        entry["status"] = "built"
        entry.pop("failure", None)
    else:
        entry["status"] = "failed"
        failed_checks = [c.get("check") for c in val_report.get("checks", []) if not c.get("pass")]
        entry["failure"] = {
            "stage": "validate",
            "message": f"validation reported invalid; failed checks: {failed_checks}",
            "returncode": rc,
            "stdout_tail": "",
            "stderr_tail": "",
        }

    return entry


def _write_partial(obj_path: Path, meta_path: Path) -> None:
    """Best-effort cleanup marker when extract succeeds but build fails."""
    try:
        if obj_path.exists():
            obj_path.write_text("# partial: build stage failed\n", encoding="utf-8")
    except OSError:
        pass


def build_index_doc(
    *,
    eligible: list[str],
    skipped: Counter,
    built_entries: dict[str, dict[str, Any]],
    min_walkable: int,
    skipped_reasons: dict[str, str] | None = None,
    total_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Assemble the navmesh-index.json shape, sorted for stable diffs.

    skipped_reasons is the per-zone skip-reason categorization populated by
    main(). When omitted, a default of "low_walkable_count" / "no_walkable_assets"
    is inferred from the count itself so independent unit tests retain forwards
    compat without passing the dict explicitly.

    total_counts is the flythrough-index asset-count per zone so M6.2 can
    re-evaluate skipped zones without re-running compute_zone_counts. When
    omitted, skipped entries carry total_asset_count=0 (legacy default).
    """
    zones_doc: dict[str, dict[str, Any]] = {}

    built_zones = 0
    failed_zones = 0
    reasons = skipped_reasons or {}
    totals = total_counts or {}

    # Eligible zones: ordered alphabetically; built entries first.
    for zt in sorted(eligible):
        ent = built_entries.get(zt, {"status": "failed", "slug": _slugify(zt)})
        # Always carry the asset counts even on failure for diagnostics.
        ent.setdefault("walkable_asset_count", 0)
        ent.setdefault("total_asset_count", totals.get(zt, 0))
        ent.setdefault("connected_zones", [])
        zones_doc[zt] = ent
        if ent.get("status") == "built":
            built_zones += 1
        else:
            failed_zones += 1

    # Skipped zones (below threshold or missing data) — broken out so M6.2
    # can re-evaluate them with confidence that nothing was silently dropped.
    for zt in sorted(skipped):
        reason = reasons.get(zt)
        if reason is None:
            # Fallback when called outside main() (e.g., tests).
            reason = "no_walkable_assets" if skipped[zt] == 0 else "low_walkable_count"
        zones_doc[zt] = {
            "status": "skipped",
            "slug": _slugify(zt),
            "walkable_asset_count": skipped[zt],
            "total_asset_count": totals.get(zt, 0),
            "skip_reason": reason,
            "connected_zones": [],
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": {
            "eligible_zones": len(eligible),
            "built_zones": built_zones,
            "failed_zones": failed_zones,
            "skipped_zones": len(skipped),
            "walkable_labels": sorted(WALKABLE_LABELS),
            "min_walkable_assets": min_walkable,
        },
        "zones": zones_doc,
    }


def _run_batch(
    eligible: list[str],
    walkable_counts: Counter,
    total_counts: Counter,
    *,
    min_walkable: int,
    timeout_s: int,
) -> dict[str, dict[str, Any]]:
    """Sequentially run build_one_zone for each eligible zone and gather entries."""
    out: dict[str, dict[str, Any]] = {}
    for zt in eligible:
        print(f"[M6.1] zone {zt}: starting (walkable={walkable_counts.get(zt, 0)})")
        entry = build_one_zone(
            zt,
            min_walkable=min_walkable,
            walkable_counts=walkable_counts,
            total_counts=total_counts,
            timeout_s=timeout_s,
        )
        status = entry.get("status", "failed")
        if status == "built":
            polys = entry.get("stats", {}).get("poly_count", 0)
            walkable_polys = entry.get("stats", {}).get("walkable_polys", 0)
            print(f"[M6.1] zone {zt}: BUILT ({polys} polys, {walkable_polys} walkable)")
        else:
            fail = entry.get("failure", {})
            print(
                f"[M6.1] zone {zt}: FAILED at stage={fail.get('stage')} "
                f"rc={fail.get('returncode')}: {fail.get('message', '')}"
            )
        out[zt] = entry
    return out


def _print_status(index_path: Path) -> int:
    """Print summary stats from the on-disk index; exit 0 if found, 1 otherwise."""
    if not index_path.exists():
        print(f"ERROR: index not found at {index_path}", file=sys.stderr)
        return 1
    data = load_json_report(index_path)
    summary = data.get("summary", {})
    print(f"Index: {index_path}")
    print(f"Schema: {data.get('schema_version', '?')}")
    print(f"Generated: {data.get('generated_at', '?')}")
    print(
        f"  Eligible: {summary.get('eligible_zones', 0)}, "
        f"Built: {summary.get('built_zones', 0)}, "
        f"Failed: {summary.get('failed_zones', 0)}, "
        f"Skipped: {summary.get('skipped_zones', 0)}"
    )
    print(f"  Walkable labels: {', '.join(summary.get('walkable_labels', []))}")
    print(f"  Min walkable threshold: {summary.get('min_walkable_assets', '?')}")
    print()
    print("Zones:")
    for zt in sorted(data.get("zones", {}).keys()):
        ent = data["zones"][zt]
        st = ent.get("status", "?")
        walk = ent.get("walkable_asset_count", 0)
        if st == "built":
            polys = ent.get("stats", {}).get("poly_count", 0)
            print(f"  [BUILT]   {zt:45s} walkable={walk:3d} polys={polys}")
        elif st == "failed":
            fail = ent.get("failure", {}).get("stage", "?")
            print(f"  [FAILED]  {zt:45s} walkable={walk:3d} stage={fail}")
        else:
            reason = ent.get("skip_reason", "")
            print(f"  [SKIPPED] {zt:45s} walkable={walk:3d} {reason}")
    return 0


def _validate_against_schema(index_path: Path) -> int:
    """Lightweight self-check vs the on-disk JSON Schema (no jsonschema dep).

    We do the cheapest gates — required top-level keys + per-zone required
    fields + enum bindings — so CI does not need a `jsonschema` runtime dep
    just for an index-doc validator. If a richer check is ever required,
    swap in `jsonschema.validate(instance, schema)`.
    """
    if not index_path.exists():
        print(f"ERROR: index not found at {index_path}", file=sys.stderr)
        return 1
    try:
        data = load_json_report(index_path)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        return 1

    errs: list[str] = []
    if data.get("schema_version") != SCHEMA_VERSION:
        errs.append(f"schema_version={data.get('schema_version')!r} != {SCHEMA_VERSION!r}")
    for key in ("generated_at", "summary", "zones"):
        if key not in data:
            errs.append(f"missing top-level key: {key!r}")
    summary = data.get("summary", {})
    for key in (
        "eligible_zones",
        "built_zones",
        "failed_zones",
        "skipped_zones",
        "walkable_labels",
        "min_walkable_assets",
    ):
        if key not in summary:
            errs.append(f"missing summary key: {key!r}")
    if not isinstance(summary.get("walkable_labels"), list) or sorted(summary["walkable_labels"]) != sorted(
        WALKABLE_LABELS
    ):
        errs.append("walkable_labels must equal sorted(WALKABLE_LABELS)")

    valid_status = {"built", "failed", "skipped"}
    valid_stages = {"extract", "build", "validate", "preflight"}
    for zt, ent in data.get("zones", {}).items():
        if ent.get("status") not in valid_status:
            errs.append(f"zone {zt!r}: invalid status {ent.get('status')!r}")
        for f in ("slug", "walkable_asset_count", "total_asset_count"):
            if f not in ent:
                errs.append(f"zone {zt!r}: missing {f!r}")
        # Bounds consistency: assert bmin[i] <= bmax[i] for every axis if present.
        b = ent.get("bounds")
        if isinstance(b, dict):
            bmin, bmax = b.get("bmin"), b.get("bmax")
            if isinstance(bmin, list) and isinstance(bmax, list) and len(bmin) == 3 and len(bmax) == 3:
                try:
                    for axis, (lo, hi) in enumerate(zip(bmin, bmax, strict=True)):
                        if float(lo) > float(hi):
                            errs.append(
                                f"zone {zt!r}: bounds axis {axis} inverted (bmin[{axis}]={lo} > bmax[{axis}]={hi})"
                            )
                except TypeError, ValueError:
                    errs.append(f"zone {zt!r}: bounds non-numeric")
        # Skip_reason must use the schema-locked enum if present.
        sr = ent.get("skip_reason")
        if sr is not None and sr not in {
            "low_walkable_count",
            "no_walkable_assets",
            "not_in_flythrough_index",
        }:
            errs.append(f"zone {zt!r}: skip_reason={sr!r} not in enum [low_walkable_count, no_walkable_assets]")
        # connected_zones items must (a) reference keys in `zones` (sibling)
        # and (b) match the zone.tuple shape regex (cheap gate mirrors schema).
        cz = ent.get("connected_zones")
        if cz is not None:
            keys = set(data.get("zones", {}).keys())
            import re as _re

            for cz_item in cz:
                if cz_item not in keys:
                    errs.append(f"zone {zt!r}: connected_zones entry {cz_item!r} is not a sibling zone.tuple")
                elif not _re.fullmatch(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$", cz_item):
                    errs.append(f"zone {zt!r}: connected_zones entry {cz_item!r} does not match zone.tuple shape regex")
        if ent.get("status") == "failed":
            fail = ent.get("failure")
            if not isinstance(fail, dict) or "stage" not in fail or "message" not in fail:
                errs.append(f"zone {zt!r} (failed): missing failure.stage/message")
            elif fail.get("stage") not in valid_stages:
                errs.append(f"zone {zt!r} (failed): stage={fail.get('stage')!r} not in valid_stages")

    if errs:
        for e in errs:
            print(f"  SCHEMA-FAIL: {e}", file=sys.stderr)
        return 1
    print(f"Schema check passed ({len(data.get('zones', {}))} zones).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="NM-6 M6.1 batch navmesh generator — orchestrates extract→build→validate across all eligible zones.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Run the batch and write navmesh-index.json")
    p_run.add_argument(
        "--zones",
        nargs="*",
        default=None,
        help="If set, restrict the batch to these specific zone.tuple values (still subject to eligibility).",
    )
    p_run.add_argument(
        "--min-walkable",
        type=int,
        default=DEFAULT_MIN_WALKABLE,
        help=f"Minimum walkable-asset count per zone to qualify (default: {DEFAULT_MIN_WALKABLE}).",
    )
    p_run.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Per-zone subprocess timeout in seconds (default: 600).",
    )

    sub.add_parser("status", help="Print a summary of the on-disk index")
    sub.add_parser("check-schema", help="Validate the on-disk index against the v1 schema gates")

    args = parser.parse_args(argv)

    if args.cmd == "status":
        return _print_status(INDEX_PATH)
    if args.cmd == "check-schema":
        return _validate_against_schema(INDEX_PATH)

    # cmd == 'run' ------------------------------------------------------------
    fly_index = load_flythrough_index()
    walk_by_aid = load_walkability()
    walkable_counts, total_counts, missing_walk = compute_zone_counts(fly_index, walk_by_aid)

    preflight_eligible = select_eligible_zones(walkable_counts, min_walkable=args.min_walkable)
    if args.zones:
        wanted = set(args.zones)
        eligible = [z for z in preflight_eligible if z in wanted]
        skipped_outside = sorted(wanted - set(preflight_eligible))
        if skipped_outside:
            print(
                f"[M6.1] note: {len(skipped_outside)} requested zone(s) did not pass eligibility filter: "
                f"{skipped_outside[:5]}{'...' if len(skipped_outside) > 5 else ''}"
            )
    else:
        eligible = preflight_eligible
        skipped_outside = []

    # Skipped: categorize each absent-from-eligible zone with a stable skip_reason
    # so M6.2 can re-evaluate the eligibility logic without losing diagnostic data.
    skipped_dict: Counter = Counter()
    skipped_reason: dict[str, str] = {}

    # (a) Zone.tuples that are in walkability counts but below the threshold.
    for zt, c in walkable_counts.items():
        if c >= args.min_walkable:
            continue
        skipped_dict[zt] = c
        skipped_reason[zt] = "no_walkable_assets" if c == 0 else "low_walkable_count"

    # (b) Zones in flythrough-index with assets but NO walkability labels.
    for zt, c in total_counts.items():
        if zt not in walkable_counts and c > 0 and zt not in skipped_dict:
            skipped_dict[zt] = 0
            skipped_reason[zt] = "no_walkable_assets"

    # (c) --zones requested but completely absent from flythrough-index.
    # Surface these so M6.2 knows the user's intent (wasn't silently dropped).
    for zt in skipped_outside:
        if zt not in skipped_dict:
            skipped_dict[zt] = 0
            skipped_reason[zt] = "not_in_flythrough_index"

    print(
        f"[M6.1] preflight: {len(walkable_counts)} zones with walkable classifications; "
        f"{len(eligible)} eligible (walkable>={args.min_walkable}); threshold={args.min_walkable}; "
        f"missing-walkability={len(missing_walk)} assets"
    )

    if not eligible:
        print("[M6.1] no eligible zones — writing empty index.")
        built_entries: dict[str, dict[str, Any]] = {}
    else:
        os.makedirs(PHASE6_DIR, exist_ok=True)
        built_entries = _run_batch(
            eligible,
            walkable_counts,
            total_counts,
            min_walkable=args.min_walkable,
            timeout_s=args.timeout,
        )

    index_doc = build_index_doc(
        eligible=eligible,
        skipped=skipped_dict,
        skipped_reasons=skipped_reason,
        built_entries=built_entries,
        min_walkable=args.min_walkable,
        total_counts=dict(total_counts),
    )

    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index_doc, f, indent=2, default=str, sort_keys=False)

    s = index_doc["summary"]
    print(
        f"[M6.1] DONE — index at {INDEX_PATH}: eligible={s['eligible_zones']} "
        f"built={s['built_zones']} failed={s['failed_zones']} skipped={s['skipped_zones']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
