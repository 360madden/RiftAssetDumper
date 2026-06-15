#!/usr/bin/env python3
"""Recover converted PNGs for DDS refs found by textureless OBJ triage.

This is a Python-first wrapper around the existing RiftAssetDumper texture
commands. It keeps the previously manual loop reproducible:

1. read the textureless triage report,
2. name-match any DDS refs that are not already converted,
3. synthesize a minimal texture-link JSONL for those matches,
4. extract matching DDS payloads from the selected live/candidate root, and
5. convert recovered DDS files to PNGs while updating converted-manifest.json.

Generated DDS/PNG/report files stay under ``Assets/build/flythrough``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dump_textures_for_flythrough import build_png_name, compute_sha1, convert_dds_to_png

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH_ROOT = REPO_ROOT / "Assets" / "build" / "flythrough"
DEFAULT_TRIAGE_REPORT = FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "textureless-triage.json"
DEFAULT_RECOVERY_ROOT = FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "recovery"
DEFAULT_CONVERTED_MANIFEST = FLYTHROUGH_ROOT / "textures" / "converted-manifest.json"
DEFAULT_CONVERTED_DIR = FLYTHROUGH_ROOT / "textures" / "converted"
DEFAULT_DDS_OUT = FLYTHROUGH_ROOT / "textures" / "linked-dds" / "textureless-triage"
DEFAULT_PROJECT = REPO_ROOT / "src" / "RiftAssetDumper" / "RiftAssetDumper.csproj"
DEFAULT_LIVE_ROOT_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Glyph\Games\RIFT\Live"),
    Path(r"C:\Program Files\Glyph\Games\RIFT\Live"),
)
ID_SUFFIX_RE = re.compile(r"_(?P<id>[0-9a-f]{16})\.dds$", re.IGNORECASE)


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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    tmp.replace(path)


def _to_posix(value: str | Path) -> str:
    return str(value).replace("\\", "/")


def repo_relative_path(path: str | Path, *, repo_root: Path = REPO_ROOT) -> str:
    raw = _to_posix(path)
    root = _to_posix(repo_root.resolve()).rstrip("/")
    if raw.lower().startswith((root + "/").lower()):
        return raw[len(root) + 1 :]
    for segment in ("Assets/build/flythrough/", "Exports/"):
        index = raw.find(segment)
        if index >= 0:
            return raw[index:]
    return raw


def texture_basename(value: str) -> str:
    return Path(value.replace("\\", "/")).name.lower()


def canonical_dds_ref(value: str) -> str:
    """Normalize DDS names, removing extractor collision suffixes."""

    name = texture_basename(value)
    return ID_SUFFIX_RE.sub(".dds", name)


def dds_refs_from_triage(report: dict[str, Any]) -> list[str]:
    refs = {
        canonical_dds_ref(ref)
        for row in report.get("rows", [])
        if isinstance(row, dict)
        for ref in row.get("row_dds_refs", [])
        if isinstance(ref, str) and ref.lower().endswith(".dds")
    }
    refs.update(
        {
            canonical_dds_ref(ref)
            for asset in report.get("assets", [])
            if isinstance(asset, dict)
            for ref in asset.get("asset_dds_refs", [])
            if isinstance(ref, str) and ref.lower().endswith(".dds")
        }
    )
    return sorted(refs)


def converted_dds_refs(converted_manifest: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for entry in converted_manifest.get("Entries", []):
        if not isinstance(entry, dict):
            continue
        original_basename = entry.get("original_basename")
        if isinstance(original_basename, str) and original_basename:
            ref = texture_basename(original_basename)
            if not ref.endswith(".dds"):
                ref += ".dds"
            refs.add(canonical_dds_ref(ref))
        png_name = entry.get("png_name")
        if isinstance(png_name, str) and png_name:
            name = texture_basename(png_name)
            if name.endswith(".png"):
                refs.add(name.removesuffix(".png") + ".dds")
    return refs


def choose_live_root(live_root: Path | None) -> Path | None:
    if live_root is not None:
        return live_root
    for candidate in DEFAULT_LIVE_ROOT_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def build_names_file(refs: list[str], path: Path) -> None:
    _write_text(path, "\n".join(refs) + ("\n" if refs else ""))


def texture_link_from_name_match(match: dict[str, Any]) -> dict[str, Any]:
    name = texture_basename(str(match["Name"]))
    return {
        "ModelArchiveName": "textureless-triage",
        "ModelEntryIndex": 0,
        "ModelIdPrefix": "textureless-triage",
        "ModelManifestEntryIndex": None,
        "ModelFilenameFnv1Hash": None,
        "ModelPakIndex": None,
        "ModelPakOffset": None,
        "NifVersion": "probe-dds-ref",
        "Reference": match["Name"],
        "ReferenceStringIndex": 0,
        "Candidate": name,
        "CandidateKind": "targeted-name-match",
        "Algorithm": match.get("Algorithm"),
        "Hash": match.get("Hash"),
        "Length": match.get("Length"),
        "Confidence": match.get("Confidence"),
        "CollisionCount": match.get("CollisionCount"),
        "TextureManifestEntryIndex": match["ManifestEntryIndex"],
        "TextureIdPrefix": match["IdPrefix"],
        "TextureFilenameFnv1Hash": match.get("Hash"),
        "TexturePakIndex": match["PakIndex"],
        "TexturePakOffset": match["PakOffset"],
        "TextureCompressedSize": match["CompressedSize"],
        "TextureSize": match["Size"],
        "TextureNameLength": match.get("ManifestNameLength"),
    }


def run_command(cmd: list[str], *, cwd: Path) -> dict[str, Any]:
    result = subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)
    return {
        "args": cmd,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def match_names(
    *,
    repo_root: Path,
    live_root: Path,
    project: Path,
    names_file: Path,
    matches_out: Path,
) -> dict[str, Any]:
    return run_command(
        [
            "dotnet",
            "run",
            "--project",
            str(project),
            "--",
            "match-names",
            "--root",
            str(live_root),
            "--names-file",
            str(names_file),
            "--out",
            str(matches_out),
            "--algorithm",
            "both",
            "--only-length-match",
            "--require-unique",
        ],
        cwd=repo_root,
    )


def extract_linked_textures(
    *,
    repo_root: Path,
    live_root: Path,
    project: Path,
    links_path: Path,
    dds_out: Path,
) -> dict[str, Any]:
    return run_command(
        [
            "dotnet",
            "run",
            "--project",
            str(project),
            "--",
            "extract-linked-textures",
            "--root",
            str(repo_root),
            "--live-root",
            str(live_root),
            "--input",
            str(links_path),
            "--out",
            str(dds_out),
        ],
        cwd=repo_root,
    )


def load_or_create_converted_manifest(converted_manifest_path: Path) -> dict[str, Any]:
    if converted_manifest_path.exists():
        return _load_json(converted_manifest_path)
    return {
        "SchemaVersion": "flythrough-converted-png-manifest/v1",
        "GeneratedAt": _now_iso(),
        "Mode": "textureless-triage-recovery",
        "Stats": {},
        "Entries": [],
    }


def convert_recovered_dds(
    *,
    dds_out: Path,
    converted_dir: Path,
    converted_manifest_path: Path,
) -> dict[str, Any]:
    manifest = load_or_create_converted_manifest(converted_manifest_path)
    entries = manifest.setdefault("Entries", [])
    existing_sha = {entry.get("sha1") for entry in entries if isinstance(entry, dict)}
    existing_refs = converted_dds_refs(manifest)
    converted = 0
    skipped_existing = 0
    failed = 0
    converted_entries: list[dict[str, Any]] = []
    recovered_dir = dds_out / "recovered"

    for dds_path in sorted(recovered_dir.glob("*.dds")):
        canonical_ref = canonical_dds_ref(dds_path.name)
        if canonical_ref in existing_refs:
            skipped_existing += 1
            continue
        sha1 = compute_sha1(dds_path)
        png_name = build_png_name(sha1, canonical_ref)
        png_path = converted_dir / png_name
        if sha1 in existing_sha and png_path.exists():
            skipped_existing += 1
            continue
        ok, decoder = convert_dds_to_png(dds_path, png_path)
        if not ok:
            failed += 1
            converted_entries.append(
                {
                    "dds": repo_relative_path(dds_path),
                    "png_name": png_name,
                    "decoder": decoder,
                    "ok": False,
                }
            )
            continue
        entry = {
            "sha1": sha1,
            "original_basename": canonical_ref.removesuffix(".dds"),
            "png_name": png_name,
            "png_path": repo_relative_path(png_path),
            "size_bytes": png_path.stat().st_size,
            "valid_png": True,
        }
        entries.append(entry)
        existing_sha.add(sha1)
        existing_refs.add(canonical_ref)
        converted += 1
        converted_entries.append({**entry, "ok": True})

    stats = manifest.setdefault("Stats", {})
    stats["textureless_triage_recovery_converted"] = stats.get("textureless_triage_recovery_converted", 0) + converted
    stats["textureless_triage_recovery_skipped_existing"] = skipped_existing
    stats["textureless_triage_recovery_failed"] = failed
    manifest["GeneratedAt"] = _now_iso()
    _write_json(converted_manifest_path, manifest)

    return {
        "recovered_dir": repo_relative_path(recovered_dir),
        "converted": converted,
        "skipped_existing": skipped_existing,
        "failed": failed,
        "converted_entries": converted_entries,
        "manifest_entries": len(entries),
    }


def recover_textureless_dds(
    *,
    repo_root: Path = REPO_ROOT,
    triage_report_path: Path = DEFAULT_TRIAGE_REPORT,
    converted_manifest_path: Path = DEFAULT_CONVERTED_MANIFEST,
    converted_dir: Path = DEFAULT_CONVERTED_DIR,
    recovery_root: Path = DEFAULT_RECOVERY_ROOT,
    dds_out: Path = DEFAULT_DDS_OUT,
    project: Path = DEFAULT_PROJECT,
    live_root: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    triage = _load_json(triage_report_path)
    converted_manifest = load_or_create_converted_manifest(converted_manifest_path)
    all_refs = dds_refs_from_triage(triage)
    converted_refs = converted_dds_refs(converted_manifest)
    target_refs = all_refs if force else [ref for ref in all_refs if ref not in converted_refs]
    names_file = recovery_root / "textureless-dds-names.txt"
    matches_out = recovery_root / "textureless-dds-name-matches.jsonl"
    links_out = recovery_root / "textureless-dds-links.jsonl"
    report_out = recovery_root / "textureless-dds-recovery-report.json"
    resolved_live_root = choose_live_root(live_root)

    report: dict[str, Any] = {
        "schema": "flythrough-textureless-dds-recovery-v1",
        "generated_at": _now_iso(),
        "inputs": {
            "triage_report": repo_relative_path(triage_report_path, repo_root=repo_root),
            "converted_manifest": repo_relative_path(converted_manifest_path, repo_root=repo_root),
            "force": force,
        },
        "summary": {
            "triage_dds_refs": len(all_refs),
            "already_converted_refs": len([ref for ref in all_refs if ref in converted_refs]),
            "target_refs": len(target_refs),
            "name_matches": 0,
            "extracted_dds": 0,
            "converted_pngs": 0,
            "skipped_existing_pngs": 0,
            "failed_conversions": 0,
        },
        "refs": {
            "all": all_refs,
            "target": target_refs,
            "already_converted": sorted(ref for ref in all_refs if ref in converted_refs),
        },
        "outputs": {
            "names_file": repo_relative_path(names_file, repo_root=repo_root),
            "matches": repo_relative_path(matches_out, repo_root=repo_root),
            "links": repo_relative_path(links_out, repo_root=repo_root),
            "dds_out": repo_relative_path(dds_out, repo_root=repo_root),
            "report": repo_relative_path(report_out, repo_root=repo_root),
        },
        "commands": [],
    }

    build_names_file(target_refs, names_file)
    if not target_refs:
        _write_json(report_out, report)
        return report
    if resolved_live_root is None:
        report["error"] = "No live root was provided and no default live root exists."
        _write_json(report_out, report)
        return report

    match_result = match_names(
        repo_root=repo_root,
        live_root=resolved_live_root,
        project=project,
        names_file=names_file,
        matches_out=matches_out,
    )
    report["commands"].append(match_result)
    if match_result["returncode"] != 0:
        report["error"] = "match-names failed"
        _write_json(report_out, report)
        return report

    matches = _read_jsonl(matches_out)
    links = [texture_link_from_name_match(match) for match in matches]
    _write_jsonl(links_out, links)
    report["summary"]["name_matches"] = len(matches)
    report["matches"] = [
        {
            "name": match.get("Name"),
            "texture_id_prefix": match.get("IdPrefix"),
            "manifest_entry_index": match.get("ManifestEntryIndex"),
            "confidence": match.get("Confidence"),
            "collision_count": match.get("CollisionCount"),
        }
        for match in matches
    ]

    if links:
        extract_result = extract_linked_textures(
            repo_root=repo_root,
            live_root=resolved_live_root,
            project=project,
            links_path=links_out,
            dds_out=dds_out,
        )
        report["commands"].append(extract_result)
        if extract_result["returncode"] != 0:
            report["error"] = "extract-linked-textures failed"
            _write_json(report_out, report)
            return report

    conversion = convert_recovered_dds(
        dds_out=dds_out,
        converted_dir=converted_dir,
        converted_manifest_path=converted_manifest_path,
    )
    report["conversion"] = conversion
    report["summary"]["extracted_dds"] = len(list((dds_out / "recovered").glob("*.dds")))
    report["summary"]["converted_pngs"] = conversion["converted"]
    report["summary"]["skipped_existing_pngs"] = conversion["skipped_existing"]
    report["summary"]["failed_conversions"] = conversion["failed"]
    _write_json(report_out, report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--triage-report", type=Path, default=DEFAULT_TRIAGE_REPORT)
    parser.add_argument("--converted-manifest", type=Path, default=DEFAULT_CONVERTED_MANIFEST)
    parser.add_argument("--converted-dir", type=Path, default=DEFAULT_CONVERTED_DIR)
    parser.add_argument("--recovery-root", type=Path, default=DEFAULT_RECOVERY_ROOT)
    parser.add_argument("--dds-out", type=Path, default=DEFAULT_DDS_OUT)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--live-root", type=Path)
    parser.add_argument("--force", action="store_true", help="Recover all triage DDS refs, including converted refs.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    report = recover_textureless_dds(
        repo_root=repo_root,
        triage_report_path=args.triage_report,
        converted_manifest_path=args.converted_manifest,
        converted_dir=args.converted_dir,
        recovery_root=args.recovery_root,
        dds_out=args.dds_out,
        project=args.project,
        live_root=args.live_root,
        force=args.force,
    )
    summary = report["summary"]
    print(
        "textureless DDS recovery: "
        f"refs={summary['triage_dds_refs']} targets={summary['target_refs']} "
        f"matches={summary['name_matches']} extracted={summary['extracted_dds']} "
        f"converted={summary['converted_pngs']} skipped={summary['skipped_existing_pngs']} "
        f"failed={summary['failed_conversions']}"
    )
    if report.get("error"):
        print(f"ERROR: {report['error']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
