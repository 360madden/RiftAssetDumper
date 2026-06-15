#!/usr/bin/env python3
"""Triage flythrough OBJ rows that still lack real texture links.

The full-available bundle can neutral-materialize every existing OBJ, but
neutral materials are not recovered texture coverage. This script scans probe
JSON evidence for latent ``*.dds`` strings on those neutral rows so the next
texture-extraction pass can target concrete names instead of broad guessing.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH_ROOT = REPO_ROOT / "Assets" / "build" / "flythrough"
DEFAULT_MANIFEST = FLYTHROUGH_ROOT / "flythrough-obj-texture-manifest-full-available.json"
DEFAULT_CONVERTED_MANIFEST = FLYTHROUGH_ROOT / "textures" / "converted-manifest.json"
DEFAULT_JSON_OUT = FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "textureless-triage.json"
DEFAULT_MARKDOWN_OUT = FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "TEXTURELESS_TRIAGE.md"
DEFAULT_NAME_MATCHES = REPO_ROOT / "Exports" / "nif-reference-name-matches.jsonl"
DEFAULT_TEXTURE_LINKS = REPO_ROOT / "Exports" / "nif-texture-links.jsonl"

DDS_RE = re.compile(r"[\w./\\:-]+\.dds", re.IGNORECASE)
TEXTURELESS_TRIAGE_TEXTURE_SOURCES = {"untextured-neutral", "textureless-triage-probe"}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


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


def texture_basename(value: str) -> str:
    return Path(value.replace("\\", "/")).name.lower()


def extract_dds_refs(value: Any) -> list[str]:
    refs: set[str] = set()
    if isinstance(value, str):
        refs.update(texture_basename(match) for match in DDS_RE.findall(value))
    elif isinstance(value, list):
        for item in value:
            refs.update(extract_dds_refs(item))
    elif isinstance(value, dict):
        for item in value.values():
            refs.update(extract_dds_refs(item))
    return sorted(refs)


def converted_texture_basenames(converted_manifest_path: Path = DEFAULT_CONVERTED_MANIFEST) -> set[str]:
    if not converted_manifest_path.exists():
        return set()
    manifest = _load_json(converted_manifest_path)
    names: set[str] = set()
    for entry in manifest.get("Entries", []):
        if not isinstance(entry, dict):
            continue
        for key in ("original_basename", "png_name", "png_path"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                name = texture_basename(value)
                names.add(name)
                if "." not in name:
                    names.add(name + ".dds")
                if name.endswith(".png"):
                    names.add(name.removesuffix(".png") + ".dds")
    return names


def _dedupe_catalog_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for match in matches:
        key = (
            match.get("source"),
            match.get("texture_id_prefix"),
            match.get("texture_manifest_entry_index"),
            match.get("candidate"),
        )
        deduped[key] = match
    return sorted(
        deduped.values(),
        key=lambda row: (
            str(row.get("source") or ""),
            str(row.get("texture_id_prefix") or ""),
            str(row.get("candidate") or ""),
        ),
    )


def load_texture_catalog(
    *,
    name_matches_path: Path = DEFAULT_NAME_MATCHES,
    texture_links_path: Path = DEFAULT_TEXTURE_LINKS,
    repo_root: Path = REPO_ROOT,
) -> dict[str, list[dict[str, Any]]]:
    """Build exact DDS basename -> global texture catalog matches."""
    catalog: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in _read_jsonl(name_matches_path):
        name = row.get("Name")
        if not isinstance(name, str) or not name.lower().endswith(".dds"):
            continue
        catalog[texture_basename(name)].append(
            {
                "source": "nif-reference-name-matches",
                "source_path": repo_relative_path(name_matches_path, repo_root=repo_root),
                "candidate": texture_basename(name),
                "texture_id_prefix": row.get("IdPrefix"),
                "texture_manifest_entry_index": row.get("ManifestEntryIndex"),
                "texture_pak_index": row.get("PakIndex"),
                "texture_pak_offset": row.get("PakOffset"),
                "texture_compressed_size": row.get("CompressedSize"),
                "texture_size": row.get("Size"),
                "confidence": row.get("Confidence"),
                "collision_count": row.get("CollisionCount"),
                "is_unique_hash_match": row.get("IsUniqueHashMatch"),
            }
        )

    for row in _read_jsonl(texture_links_path):
        candidate = row.get("Candidate")
        if not isinstance(candidate, str) or not candidate.lower().endswith(".dds"):
            continue
        catalog[texture_basename(candidate)].append(
            {
                "source": "nif-texture-links",
                "source_path": repo_relative_path(texture_links_path, repo_root=repo_root),
                "candidate": texture_basename(candidate),
                "model_id_prefix": row.get("ModelIdPrefix"),
                "texture_id_prefix": row.get("TextureIdPrefix"),
                "texture_manifest_entry_index": row.get("TextureManifestEntryIndex"),
                "texture_pak_index": row.get("TexturePakIndex"),
                "texture_pak_offset": row.get("TexturePakOffset"),
                "texture_compressed_size": row.get("TextureCompressedSize"),
                "texture_size": row.get("TextureSize"),
                "confidence": row.get("Confidence"),
                "collision_count": row.get("CollisionCount"),
            }
        )

    return {ref: _dedupe_catalog_matches(matches) for ref, matches in catalog.items()}


def probe_files_for_asset(asset_id: str, *, exports_root: Path) -> list[Path]:
    return sorted(exports_root.glob(f"probe-nif-mesh-{asset_id}*.json"))


def probe_refs_for_mesh(probe: dict[str, Any], mesh_block: str | int | None) -> list[str]:
    if mesh_block is None:
        return extract_dds_refs(probe)
    try:
        mesh_index = int(mesh_block)
    except TypeError, ValueError:
        return extract_dds_refs(probe)

    refs: set[str] = set()
    for mesh in probe.get("Meshes", []):
        if isinstance(mesh, dict) and mesh.get("MeshBlockIndex") == mesh_index:
            refs.update(extract_dds_refs(mesh))
    return sorted(refs)


def build_textureless_triage(
    *,
    repo_root: Path = REPO_ROOT,
    manifest_path: Path = DEFAULT_MANIFEST,
    converted_manifest_path: Path = DEFAULT_CONVERTED_MANIFEST,
    name_matches_path: Path = DEFAULT_NAME_MATCHES,
    texture_links_path: Path = DEFAULT_TEXTURE_LINKS,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    converted_names = converted_texture_basenames(converted_manifest_path)
    texture_catalog = load_texture_catalog(
        name_matches_path=name_matches_path,
        texture_links_path=texture_links_path,
        repo_root=repo_root,
    )
    exports_root = repo_root / "Exports"

    neutral_rows = [
        entry
        for entry in manifest.get("entries", [])
        if entry.get("texture_source") in TEXTURELESS_TRIAGE_TEXTURE_SOURCES
    ]
    asset_refs: dict[str, set[str]] = defaultdict(set)
    row_reports: list[dict[str, Any]] = []

    for entry in neutral_rows:
        asset_id = entry.get("asset_id")
        mesh_block = entry.get("mesh_block")
        row_refs: set[str] = set()
        asset_probe_files: list[str] = []
        mesh_probe_files: list[str] = []

        if isinstance(asset_id, str) and asset_id:
            for probe_file in probe_files_for_asset(asset_id, exports_root=exports_root):
                asset_probe_files.append(repo_relative_path(probe_file, repo_root=repo_root))
                try:
                    probe = _load_json(probe_file)
                except OSError, json.JSONDecodeError:
                    continue
                refs = extract_dds_refs(probe)
                asset_refs[asset_id].update(refs)
                mesh_refs = probe_refs_for_mesh(probe, mesh_block)
                if mesh_refs:
                    mesh_probe_files.append(repo_relative_path(probe_file, repo_root=repo_root))
                    row_refs.update(mesh_refs)

        row_reports.append(
            {
                "manifest_index": entry.get("manifest_index"),
                "source_obj": entry.get("source_obj"),
                "asset_id": asset_id,
                "mesh_block": mesh_block,
                "texture_source": entry.get("texture_source"),
                "vertex_count": entry.get("vertex_count", 0),
                "face_count": entry.get("face_count", 0),
                "asset_probe_files": sorted(set(asset_probe_files)),
                "mesh_probe_files": sorted(set(mesh_probe_files)),
                "row_dds_refs": sorted(row_refs),
                "row_dds_refs_present_in_converted": sorted(ref for ref in row_refs if ref in converted_names),
                "row_dds_refs_missing_from_converted": sorted(ref for ref in row_refs if ref not in converted_names),
            }
        )

    asset_reports = []
    for asset_id, refs in sorted(asset_refs.items()):
        asset_reports.append(
            {
                "asset_id": asset_id,
                "asset_dds_refs": sorted(refs),
                "asset_dds_refs_present_in_converted": sorted(ref for ref in refs if ref in converted_names),
                "asset_dds_refs_missing_from_converted": sorted(ref for ref in refs if ref not in converted_names),
            }
        )

    rows_with_refs = [row for row in row_reports if row["row_dds_refs"]]
    assets_with_refs = [asset for asset in asset_reports if asset["asset_dds_refs"]]
    unique_refs = sorted({ref for asset in asset_reports for ref in asset["asset_dds_refs"]})
    dds_reference_status = [
        {
            "dds_ref": ref,
            "present_in_converted": ref in converted_names,
            "catalog_match_count": len(texture_catalog.get(ref, [])),
            "catalog_matches": texture_catalog.get(ref, []),
        }
        for ref in unique_refs
    ]
    missing_converted_refs = [ref for ref in unique_refs if ref not in converted_names]

    return {
        "schema": "flythrough-textureless-asset-triage-v1",
        "generated_at": _now_iso(),
        "inputs": {
            "manifest": repo_relative_path(manifest_path, repo_root=repo_root),
            "converted_manifest": repo_relative_path(converted_manifest_path, repo_root=repo_root),
            "name_matches": repo_relative_path(name_matches_path, repo_root=repo_root),
            "texture_links": repo_relative_path(texture_links_path, repo_root=repo_root),
        },
        "summary": {
            "neutral_rows": len(neutral_rows),
            "neutral_rows_with_mesh_dds_refs": len(rows_with_refs),
            "neutral_asset_ids": len({entry.get("asset_id") for entry in neutral_rows if entry.get("asset_id")}),
            "neutral_asset_ids_with_any_dds_refs": len(assets_with_refs),
            "unique_dds_refs": len(unique_refs),
            "unique_dds_refs_present_in_converted": len([ref for ref in unique_refs if ref in converted_names]),
            "unique_dds_refs_missing_from_converted": len([ref for ref in unique_refs if ref not in converted_names]),
            "unique_dds_refs_with_catalog_match": len([ref for ref in unique_refs if texture_catalog.get(ref)]),
            "unique_dds_refs_without_catalog_match": len([ref for ref in unique_refs if not texture_catalog.get(ref)]),
            "missing_converted_dds_refs_with_catalog_match": len(
                [ref for ref in missing_converted_refs if texture_catalog.get(ref)]
            ),
            "missing_converted_dds_refs_without_catalog_match": len(
                [ref for ref in missing_converted_refs if not texture_catalog.get(ref)]
            ),
        },
        "assets": asset_reports,
        "dds_reference_status": dds_reference_status,
        "rows": row_reports,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Flythrough Textureless Asset Triage",
        "",
        f"**Generated**: {report['generated_at']}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Textureless-scope rows | {summary['neutral_rows']} |",
        f"| Rows with mesh-level DDS refs | {summary['neutral_rows_with_mesh_dds_refs']} |",
        f"| Neutral asset IDs | {summary['neutral_asset_ids']} |",
        f"| Neutral asset IDs with any DDS refs | {summary['neutral_asset_ids_with_any_dds_refs']} |",
        f"| Unique DDS refs found | {summary['unique_dds_refs']} |",
        f"| Unique DDS refs already converted | {summary['unique_dds_refs_present_in_converted']} |",
        f"| Unique DDS refs missing from converted PNGs | {summary['unique_dds_refs_missing_from_converted']} |",
        f"| Unique DDS refs with global catalog matches | {summary['unique_dds_refs_with_catalog_match']} |",
        f"| Missing converted DDS refs with catalog matches | {summary['missing_converted_dds_refs_with_catalog_match']} |",
        "",
        "## Asset-level DDS references",
        "",
    ]
    for asset in report["assets"]:
        refs = asset["asset_dds_refs"]
        if not refs:
            continue
        missing = asset["asset_dds_refs_missing_from_converted"]
        lines.append(f"- `{asset['asset_id']}`: {', '.join(f'`{ref}`' for ref in refs)}")
        if missing:
            lines.append(f"  - Missing converted PNGs for: {', '.join(f'`{ref}`' for ref in missing)}")
    if not any(asset["asset_dds_refs"] for asset in report["assets"]):
        lines.append("- No DDS refs found in available probe evidence.")

    lines.extend(
        [
            "",
            "## Global texture catalog recovery hints",
            "",
            "| DDS ref | Converted? | Catalog matches | Best texture ID | Source |",
            "|---|---:|---:|---|---|",
        ]
    )
    for status in report.get("dds_reference_status", []):
        matches = status.get("catalog_matches", [])
        best_match = matches[0] if matches else {}
        lines.append(
            f"| `{status['dds_ref']}` | {'yes' if status['present_in_converted'] else 'no'} | "
            f"{status['catalog_match_count']} | `{best_match.get('texture_id_prefix') or 'n/a'}` | "
            f"{best_match.get('source') or 'n/a'} |"
        )
    if not report.get("dds_reference_status"):
        lines.append("| _none_ | n/a | 0 | n/a | n/a |")

    lines.extend(["", "## Textureless-scope rows", ""])
    for row in report["rows"]:
        refs = row["row_dds_refs"]
        lines.append(
            f"- #{row['manifest_index']} `{row['source_obj']}` asset=`{row.get('asset_id')}` "
            f"mesh={row.get('mesh_block')} source={row.get('texture_source')} "
            f"refs={', '.join(f'`{ref}`' for ref in refs) if refs else 'none'}"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--converted-manifest", type=Path, default=DEFAULT_CONVERTED_MANIFEST)
    parser.add_argument("--name-matches", type=Path, default=DEFAULT_NAME_MATCHES)
    parser.add_argument("--texture-links", type=Path, default=DEFAULT_TEXTURE_LINKS)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    report = build_textureless_triage(
        repo_root=repo_root,
        manifest_path=args.manifest,
        converted_manifest_path=args.converted_manifest,
        name_matches_path=args.name_matches,
        texture_links_path=args.texture_links,
    )
    _write_json(args.json_out, report)
    _write_text(args.markdown_out, render_markdown(report))
    summary = report["summary"]
    print(
        "textureless triage: "
        f"rows={summary['neutral_rows']} row_refs={summary['neutral_rows_with_mesh_dds_refs']} "
        f"assets_with_refs={summary['neutral_asset_ids_with_any_dds_refs']} "
        f"unique_refs={summary['unique_dds_refs']} "
        f"missing_converted={summary['unique_dds_refs_missing_from_converted']} "
        f"catalog_matches={summary['missing_converted_dds_refs_with_catalog_match']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
