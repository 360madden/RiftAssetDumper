#!/usr/bin/env python3
"""Refresh targeted NIF mesh probes for textureless flythrough OBJ rows.

The textureless triage report can only recover DDS references from probe JSON
that already exists under ``Exports/``. This helper closes that evidence gap by
running focused ``probe-nif-mesh`` calls for full-available manifest rows that
still use neutral or probe-derived materials.

Generated probes and reports stay under ignored ``Exports/`` and
``Assets/build/flythrough`` paths.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from triage_flythrough_textureless_assets import extract_dds_refs, probe_refs_for_mesh

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH_ROOT = REPO_ROOT / "Assets" / "build" / "flythrough"
DEFAULT_MANIFEST = FLYTHROUGH_ROOT / "flythrough-obj-texture-manifest-full-available.json"
DEFAULT_REPORT = FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "probe-refresh-report.json"
DEFAULT_MARKDOWN = FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "PROBE_REFRESH.md"
DEFAULT_PROJECT = REPO_ROOT / "src" / "RiftAssetDumper" / "RiftAssetDumper.csproj"
DEFAULT_LIVE_ROOT_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Glyph\Games\RIFT\Live"),
    Path(r"C:\Program Files\Glyph\Games\RIFT\Live"),
)
TEXTURELESS_TEXTURE_SOURCES = {"untextured-neutral", "textureless-triage-probe"}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    tmp.replace(path)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def _to_posix(value: str | Path) -> str:
    return str(value).replace("\\", "/")


def repo_relative_path(path: str | Path, *, repo_root: Path = REPO_ROOT) -> str:
    raw = _to_posix(path)
    root = _to_posix(repo_root.resolve()).rstrip("/")
    if raw.lower().startswith((root + "/").lower()):
        return raw[len(root) + 1 :]
    for segment in ("Exports/", "Assets/build/flythrough/"):
        index = raw.find(segment)
        if index >= 0:
            return raw[index:]
    return raw


def choose_live_root(live_root: Path | None) -> Path | None:
    if live_root is not None:
        return live_root
    for candidate in DEFAULT_LIVE_ROOT_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def probe_output_path(repo_root: Path, asset_id: str, mesh_block: str) -> Path:
    return repo_root / "Exports" / f"probe-nif-mesh-{asset_id}-mesh{mesh_block}.json"


def select_probe_targets(
    manifest: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
    refresh_existing: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return unique asset/mesh probe targets from textureless-scope rows."""

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    stats = {
        "textureless_scope_rows": 0,
        "rows_without_asset_id": 0,
        "rows_without_mesh_block": 0,
        "duplicate_target_rows": 0,
    }

    for entry in manifest.get("entries", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("texture_source") not in TEXTURELESS_TEXTURE_SOURCES:
            continue
        stats["textureless_scope_rows"] += 1

        asset_id = entry.get("asset_id")
        mesh_block_value = entry.get("mesh_block")
        if not isinstance(asset_id, str) or not asset_id:
            stats["rows_without_asset_id"] += 1
            continue
        if mesh_block_value is None:
            stats["rows_without_mesh_block"] += 1
            continue

        mesh_block = str(mesh_block_value)
        key = (asset_id.lower(), mesh_block)
        output = probe_output_path(repo_root, asset_id.lower(), mesh_block)
        target = grouped.get(key)
        if target is None:
            grouped[key] = {
                "asset_id": asset_id.lower(),
                "mesh_block": mesh_block,
                "output": output,
                "manifest_indices": [entry.get("manifest_index")],
                "source_objs": [entry.get("source_obj")],
                "texture_sources": sorted({str(entry.get("texture_source"))}),
            }
            continue

        stats["duplicate_target_rows"] += 1
        target["manifest_indices"].append(entry.get("manifest_index"))
        target["source_objs"].append(entry.get("source_obj"))
        target["texture_sources"] = sorted(set(target["texture_sources"]) | {str(entry.get("texture_source"))})

    targets: list[dict[str, Any]] = []
    for target in grouped.values():
        output: Path = target["output"]
        exists = output.exists()
        target["output_exists_before"] = exists
        target["planned_action"] = "refresh" if refresh_existing or not exists else "skip-existing"
        targets.append(target)

    return sorted(targets, key=lambda row: (row["asset_id"], int(row["mesh_block"]))), stats


def summarize_probe_file(path: Path, mesh_block: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "probe_exists": False,
            "mesh_dds_refs": [],
            "asset_dds_refs": [],
            "meshes_emitted": None,
            "candidate_links": None,
            "pairings": None,
            "attribute_sets": None,
        }
    try:
        probe = _load_json(path)
    except OSError, json.JSONDecodeError:
        return {
            "probe_exists": True,
            "probe_parse_error": True,
            "mesh_dds_refs": [],
            "asset_dds_refs": [],
            "meshes_emitted": None,
            "candidate_links": None,
            "pairings": None,
            "attribute_sets": None,
        }

    mesh_refs = probe_refs_for_mesh(probe, mesh_block)
    asset_refs = extract_dds_refs(probe)
    return {
        "probe_exists": True,
        "mesh_dds_refs": mesh_refs,
        "asset_dds_refs": asset_refs,
        "meshes_emitted": probe.get("MeshesEmitted"),
        "candidate_links": _count_or_value(probe.get("CandidateLinks")),
        "pairings": _count_or_value(probe.get("Pairings")),
        "attribute_sets": _count_or_value(probe.get("AttributeSets")),
    }


def _count_or_value(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, (list, dict, tuple, set)):
        return len(value)
    return None


def display_command(cmd: list[str], *, repo_root: Path) -> list[str]:
    displayed: list[str] = []
    for part in cmd:
        path = Path(part)
        try:
            displayed.append(repo_relative_path(path, repo_root=repo_root) if path.is_absolute() else part)
        except OSError:
            displayed.append(part)
    return displayed


def run_probe_command(
    *,
    repo_root: Path,
    live_root: Path,
    project: Path,
    asset_id: str,
    mesh_block: str,
    output: Path,
) -> dict[str, Any]:
    cmd = [
        "dotnet",
        "run",
        "--project",
        str(project),
        "--",
        "probe-nif-mesh",
        "--root",
        str(live_root),
        "--id",
        asset_id,
        "--mesh-block",
        mesh_block,
        "--out",
        str(output),
    ]
    result = subprocess.run(cmd, cwd=repo_root, check=False, capture_output=True, text=True)
    return {
        "args": display_command(cmd, repo_root=repo_root),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def build_probe_refresh_report(
    *,
    repo_root: Path = REPO_ROOT,
    manifest_path: Path = DEFAULT_MANIFEST,
    live_root: Path | None = None,
    project: Path = DEFAULT_PROJECT,
    refresh_existing: bool = False,
    dry_run: bool = False,
    max_targets: int | None = None,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    selected_live_root = choose_live_root(live_root)
    targets, selection_stats = select_probe_targets(
        manifest,
        repo_root=repo_root,
        refresh_existing=refresh_existing,
    )
    if max_targets is not None:
        targets = targets[:max_targets]

    target_reports: list[dict[str, Any]] = []
    command_reports: list[dict[str, Any]] = []
    for target in targets:
        output: Path = target["output"]
        action = target["planned_action"]
        command_report: dict[str, Any] | None = None
        status = "skipped-existing" if action == "skip-existing" else "planned"

        if action != "skip-existing" and not dry_run:
            if selected_live_root is None:
                status = "blocked-no-live-root"
            else:
                command_report = run_probe_command(
                    repo_root=repo_root,
                    live_root=selected_live_root,
                    project=project,
                    asset_id=target["asset_id"],
                    mesh_block=target["mesh_block"],
                    output=output,
                )
                command_reports.append(command_report)
                status = "succeeded" if command_report["returncode"] == 0 and output.exists() else "failed"

        probe_summary = summarize_probe_file(output, target["mesh_block"])
        target_reports.append(
            {
                "asset_id": target["asset_id"],
                "mesh_block": target["mesh_block"],
                "manifest_indices": target["manifest_indices"],
                "source_objs": target["source_objs"],
                "texture_sources": target["texture_sources"],
                "output": repo_relative_path(output, repo_root=repo_root),
                "output_exists_before": target["output_exists_before"],
                "action": action,
                "status": status,
                **probe_summary,
                "command": command_report,
            }
        )

    status_counts: dict[str, int] = defaultdict(int)
    unique_mesh_refs: set[str] = set()
    unique_asset_refs: set[str] = set()
    for target in target_reports:
        status_counts[str(target["status"])] += 1
        unique_mesh_refs.update(target.get("mesh_dds_refs", []))
        unique_asset_refs.update(target.get("asset_dds_refs", []))

    return {
        "schema": "flythrough-textureless-probe-refresh-v1",
        "generated_at": _now_iso(),
        "inputs": {
            "manifest": repo_relative_path(manifest_path, repo_root=repo_root),
            "live_root": str(selected_live_root) if selected_live_root else None,
            "project": repo_relative_path(project, repo_root=repo_root),
            "refresh_existing": refresh_existing,
            "dry_run": dry_run,
            "max_targets": max_targets,
        },
        "summary": {
            **selection_stats,
            "unique_probe_targets": len(targets),
            "status_counts": dict(sorted(status_counts.items())),
            "targets_with_mesh_dds_refs": sum(1 for target in target_reports if target.get("mesh_dds_refs")),
            "unique_mesh_dds_refs": len(unique_mesh_refs),
            "unique_asset_dds_refs": len(unique_asset_refs),
            "commands_run": len(command_reports),
            "live_root_available": selected_live_root is not None,
        },
        "targets": target_reports,
        "commands": command_reports,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    status_counts = summary.get("status_counts", {})
    lines = [
        "# Flythrough Textureless Mesh Probe Refresh",
        "",
        f"**Generated**: {report['generated_at']}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Textureless-scope rows | {summary['textureless_scope_rows']} |",
        f"| Unique asset/mesh probe targets | {summary['unique_probe_targets']} |",
        f"| Rows without asset ID | {summary['rows_without_asset_id']} |",
        f"| Commands run | {summary['commands_run']} |",
        f"| Targets with mesh-level DDS refs | {summary['targets_with_mesh_dds_refs']} |",
        f"| Unique mesh-level DDS refs | {summary['unique_mesh_dds_refs']} |",
        "",
        "## Target status",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    for status, count in status_counts.items():
        lines.append(f"| {status} | {count} |")

    lines.extend(["", "## Probe targets", ""])
    for target in report["targets"]:
        refs = target.get("mesh_dds_refs", [])
        lines.append(
            f"- `{target['asset_id']}` mesh={target['mesh_block']} "
            f"rows={target['manifest_indices']} status={target['status']} "
            f"refs={', '.join(f'`{ref}`' for ref in refs) if refs else 'none'}"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--live-root", type=Path, help="Live RIFT root to read for targeted probes.")
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--refresh-existing", action="store_true", help="Re-run probes even when output exists.")
    parser.add_argument("--dry-run", action="store_true", help="Write the report without running dotnet probes.")
    parser.add_argument("--max-targets", type=int, help="Limit targets for a bounded refresh.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    report = build_probe_refresh_report(
        repo_root=repo_root,
        manifest_path=args.manifest,
        live_root=args.live_root,
        project=args.project,
        refresh_existing=args.refresh_existing,
        dry_run=args.dry_run,
        max_targets=args.max_targets,
    )
    _write_json(args.report_out, report)
    _write_text(args.markdown_out, render_markdown(report))
    summary = report["summary"]
    print(
        "textureless probe refresh: "
        f"targets={summary['unique_probe_targets']} commands={summary['commands_run']} "
        f"mesh_ref_targets={summary['targets_with_mesh_dds_refs']} "
        f"unique_mesh_refs={summary['unique_mesh_dds_refs']} "
        f"statuses={summary['status_counts']}"
    )
    return 1 if summary["status_counts"].get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
