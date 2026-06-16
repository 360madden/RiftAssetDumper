"""Build per-cohort-asset texture coverage report (C2-3.1).

Reads the C2-2 cohort (24 assets: 4 non-id + 20 distinct id) from
``Assets/Exports/discovery-plan/cycle-2/stage2/transform-examples.json``
and produces a texture-coverage matrix that combines:

- scene-manifest ``textures`` block: source-of-truth from C2-2.4
  (linked_texture_count, linked_textures, missing_texture_count,
  placeholder_texture_count);
- flythrough-index.json ``linked_textures`` list: texture data from the
  FT plan (Phase 21 / RiftFlythrough-ready linkage).

Output is written to
``Assets/Exports/discovery-plan/cycle-2/stage3/texture-coverage.{json,md}``
and a JSON report is emitted so V4P12 and M3 follow-on steps can consume it.

Conventions match ``scripts/build_scene_manifest.py``:

- honest nulls/0s/"unknown" for known-unknowns;
- ``producer`` block carries ``command`` + ``input_files`` for
  reproducibility;
- JSON Schema 2020-12 validator is shared
  (``scripts/validate_scene_manifest_schema.py``).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, NotRequired, TypedDict

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGE2_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage2"
STAGE3_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage3"
FLYTHROUGH_INDEX = REPO_ROOT / "Assets" / "build" / "flythrough" / "flythrough-index.json"

PRODUCER_VERSION = "v0.1"


# ---------- Typed output shape ----------


class CoverageEntry(TypedDict):
    asset_id: str
    cohort_kind: str  # "identity" | "non_identity"
    in_flythrough_index: bool
    scene_manifest_textures: dict[str, Any]
    flythrough_index_textures: dict[str, Any]
    coverage_status: str  # "covered" | "partial" | "textureless" | "missing-flythrough" | "missing-manifest"
    contradiction: bool  # True if scene_manifest and flythrough_index disagree on linked count
    contradiction_notes: NotRequired[str]  # populated only when contradiction is True


# ---------- Helpers ----------


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _cohort_asset_ids() -> tuple[list[str], list[str]]:
    """Return (identity_ids, non_identity_ids) from transform-examples.json."""
    t = _read_json(STAGE2_DIR / "transform-examples.json")
    identity_ids = [e.get("asset_id", e.get("id", "")) for e in t.get("identity_examples", [])]
    non_identity_ids = [e.get("asset_id", e.get("id", "")) for e in t.get("non_identity_examples", [])]
    return identity_ids, non_identity_ids


def _scene_manifest_textures(asset_id: str) -> dict[str, Any] | None:
    """Read the textures block from a scene-manifest (or None if absent)."""
    path = STAGE2_DIR / f"sample-manifest-{asset_id}.json"
    if not path.exists():
        return None
    m = _read_json(path)
    return m.get("textures") if isinstance(m.get("textures"), dict) else None


def _flythrough_index_assets() -> dict[str, dict[str, Any]] | None:
    """Return the assets dict from flythrough-index.json (key=asset_id), or None.

    Returns None (rather than {}) when the file is missing or the assets
    field is not a dict so callers can use a single ``if assets is None``
    guard, mirroring ``_scene_manifest_textures``.
    """
    if not FLYTHROUGH_INDEX.exists():
        return None
    idx = _read_json(FLYTHROUGH_INDEX)
    assets = idx.get("assets", {})
    return assets if isinstance(assets, dict) else None


def _flythrough_index_textures(
    asset_id: str, assets: dict[str, dict[str, Any]] | None
) -> dict[str, Any]:
    """Return per-asset texture stats derived from flythrough-index.json.

    When ``assets`` is None (read failure), the function still returns a
    well-shaped dict with asset_in_index=False and zero counts so callers
    can avoid special-casing at the caller site.
    """
    assets = assets or {}
    entry = assets.get(asset_id, {})
    linked = entry.get("linked_textures", [])
    if isinstance(linked, list):
        linked_count = sum(1 for x in linked if isinstance(x, str) and x)
    else:
        linked_count = 0
        linked = []
    return {
        "asset_in_index": bool(entry),
        "linked_texture_count": int(linked_count),
        "linked_textures": list(linked) if isinstance(linked, list) else [],
    }


def _coverage_status(scene_textures: dict[str, Any] | None, fly_textures: dict[str, Any]) -> str:
    """Map (scene, fly) to one of the agreed coverage_status values."""
    if scene_textures is None:
        return "missing-manifest"
    if not fly_textures["asset_in_index"]:
        return "missing-flythrough"
    scene_linked = scene_textures.get("linked_texture_count", 0)
    if scene_linked > 0:
        return "covered"
    if scene_textures.get("placeholder_texture_count", 0) > 0:
        return "partial"
    return "textureless"


def _detect_contradiction(
    scene_textures: dict[str, Any] | None, fly_textures: dict[str, Any]
) -> tuple[bool, str]:
    """Detect disagreements between scene-manifest textures and flythrough-index linked_textures."""
    if scene_textures is None or not fly_textures["asset_in_index"]:
        return False, ""
    scene_linked = scene_textures.get("linked_texture_count", 0)
    fly_linked = fly_textures["linked_texture_count"]
    if scene_linked != fly_linked:
        delta = fly_linked - scene_linked
        direction = (
            "flythrough has more textures than scene-manifest" if delta > 0
            else "scene-manifest has more textures than flythrough"
        )
        return True, (
            f"linked_texture_count mismatch: scene={scene_linked} "
            f"flythrough={fly_linked} (delta={delta:+d}; {direction})"
        )
    return False, ""


def _build_entry(
    asset_id: str, cohort_kind: str, assets: dict[str, dict[str, Any]] | None
) -> CoverageEntry:
    """Build a single CoverageEntry for the cohort matrix."""
    scene_textures = _scene_manifest_textures(asset_id)
    fly_textures = _flythrough_index_textures(asset_id, assets)
    contradiction, contradiction_notes = _detect_contradiction(scene_textures, fly_textures)
    entry: CoverageEntry = {
        "asset_id": asset_id,
        "cohort_kind": cohort_kind,
        "in_flythrough_index": fly_textures["asset_in_index"],
        "scene_manifest_textures": scene_textures or {
            "linked_texture_count": 0,
            "linked_textures": [],
            "missing_texture_count": 0,
            "placeholder_texture_count": 0,
            "_placeholder": True,
            "_reason": "scene-manifest missing; using empty/neutral markers",
        },
        "flythrough_index_textures": fly_textures,
        "coverage_status": _coverage_status(scene_textures, fly_textures),
        "contradiction": contradiction,
    }
    if contradiction_notes:
        entry["contradiction_notes"] = contradiction_notes
    return entry


def _build_coverage_summary(entries: list[CoverageEntry]) -> dict[str, int]:
    """Aggregate per-status counts and total contradiction count."""
    summary = {
        "covered": 0,
        "partial": 0,
        "textureless": 0,
        "missing-flythrough": 0,
        "missing-manifest": 0,
        "contradictions": 0,
    }
    for e in entries:
        status = e["coverage_status"]
        summary[status] = summary.get(status, 0) + 1
        if e.get("contradiction"):
            summary["contradictions"] += 1
    return summary


def build_report() -> dict[str, Any]:
    """Build the full texture-coverage report for the cohort."""
    identity_ids, non_identity_ids = _cohort_asset_ids()
    assets = _flythrough_index_assets()
    entries: list[CoverageEntry] = []
    for aid in identity_ids:
        entries.append(_build_entry(aid, "identity", assets))
    for aid in non_identity_ids:
        entries.append(_build_entry(aid, "non_identity", assets))
    summary = _build_coverage_summary(entries)
    return {
        "SchemaVersion": "texture-coverage/v1-draft",
        "generated_at": _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "producer": {
            "name": "build_texture_coverage.py",
            "version": PRODUCER_VERSION,
            "command": (
                f"python {Path(__file__).name}"
                f" --cohort {STAGE2_DIR / 'transform-examples.json'}"
                f" --flythrough-index {FLYTHROUGH_INDEX}"
            ),
            "input_files": [
                str(STAGE2_DIR / "transform-examples.json"),
                str(STAGE2_DIR) + "/sample-manifest-*.json (24 files)",
                str(FLYTHROUGH_INDEX),
            ],
        },
        "cohort_size": len(entries),
        "cohort_identity_count": len(identity_ids),
        "cohort_non_identity_count": len(non_identity_ids),
        "coverage_summary": summary,
        "entries": entries,
    }


def render_markdown(
    report: dict[str, Any],
    contradictions: list[CoverageEntry],
) -> str:
    """Render a human-readable sidecar that mirrors the JSON report."""
    lines: list[str] = []
    s = report["coverage_summary"]
    lines.append("# C2-3.1 Texture Coverage Report (draft)")
    lines.append("")
    lines.append(f"Generated: `{report['generated_at']}`  ")
    lines.append(f"Producer: `{report['producer']['name']}` (v{report['producer']['version']})  ")
    lines.append(
        f"Cohort: {report['cohort_size']} "
        f"(identity={report['cohort_identity_count']}, "
        f"non_identity={report['cohort_non_identity_count']})"
    )
    lines.append("")
    lines.append("## Coverage summary")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("|---|---:|")
    for k in (
        "covered", "partial", "textureless",
        "missing-flythrough", "missing-manifest", "contradictions",
    ):
        lines.append(f"| {k} | {s.get(k, 0)} |")
    lines.append("")
    if contradictions:
        lines.append("## Contradictions (scene-manifest vs flythrough-index)")
        lines.append("")
        lines.append("| asset_id | cohort | scene linked | flythrough linked | delta | note |")
        lines.append("|---|---|---:|---:|---:|---|")
        for c in contradictions:
            sm = c["scene_manifest_textures"]
            fi = c["flythrough_index_textures"]
            scene_n = sm.get("linked_texture_count", 0)
            fly_n = fi.get("linked_texture_count", 0)
            delta = fly_n - scene_n
            lines.append(
                f"| {c['asset_id']} | {c['cohort_kind']} | {scene_n} | {fly_n} | "
                f"{delta:+d} | {c.get('contradiction_notes', '')} |"
            )
        lines.append("")
    else:
        lines.append("## Contradictions")
        lines.append("")
        lines.append("_None detected for the 24-asset cohort._")
        lines.append("")
    lines.append("## Per-asset coverage")
    lines.append("")
    lines.append("| asset_id | cohort | status | scene linked | flythrough linked | contradiction |")
    lines.append("|---|---|---|---:|---:|---|")
    for e in report["entries"]:
        sm = e["scene_manifest_textures"]
        fi = e["flythrough_index_textures"]
        lines.append(
            f"| {e['asset_id']} | {e['cohort_kind']} | {e['coverage_status']} | "
            f"{sm.get('linked_texture_count', 0)} | {fi.get('linked_texture_count', 0)} | "
            f"{'yes' if e['contradiction'] else 'no'} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_outputs(
    report: dict[str, Any], out_dir: Path
) -> tuple[Path, Path]:
    """Write the texture-coverage report JSON + markdown sidecar to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "texture-coverage.json"
    md_path = out_dir / "texture-coverage.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8-sig")
    contradictions = [e for e in report["entries"] if e.get("contradiction")]
    md_path.write_text(render_markdown(report, contradictions), encoding="utf-8-sig")
    return json_path, md_path


def sha256(path: Path) -> str:
    """Return a 16-hex-char truncation of sha256(path.read_bytes()) for display."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


# ---------- CLI ----------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. See --help for options."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--out-dir", type=Path, default=STAGE3_DIR,
        help=f"Output directory (default: {STAGE3_DIR})",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Compute report but do not write to disk (still prints summary).",
    )
    args = p.parse_args(argv)

    report = build_report()
    if args.dry_run:
        print(f"[dry-run] cohort_size={report['cohort_size']}")
        print(f"[dry-run] cohort_identity={report['cohort_identity_count']}")
        print(f"[dry-run] cohort_non_identity={report['cohort_non_identity_count']}")
        print(f"[dry-run] summary={report['coverage_summary']}")
        contradictions = [e for e in report["entries"] if e.get("contradiction")]
        print(f"[dry-run] contradictions={len(contradictions)}")
        return 0

    json_path, md_path = write_outputs(report, args.out_dir)
    print(f"[ok] wrote {json_path} (sha256[:16]={sha256(json_path)})")
    print(f"[ok] wrote {md_path} (sha256[:16]={sha256(md_path)})")
    print(f"[ok] cohort_summary={report['coverage_summary']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
