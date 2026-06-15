#!/usr/bin/env python3
"""Recover missing flythrough OBJ manifest paths by exact SHA-256 duplicate only.

This is intentionally conservative: it never synthesizes geometry and never
copies a similar-looking OBJ. A missing manifest path is repairable only when an
existing OBJ file under the scan roots has the exact SHA-256 recorded in
``Exports/export-manifest.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT_MANIFEST = REPO_ROOT / "Exports" / "export-manifest.json"
DEFAULT_REPORT = (
    REPO_ROOT / "Assets" / "build" / "flythrough" / "evidence" / "missing-obj-repair" / "repair-report.json"
)


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


def _to_posix(path: str | Path) -> str:
    return str(path).replace("\\", "/")


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


def repo_path_from_relative(repo_root: Path, relative: str) -> Path:
    return repo_root.joinpath(*relative.split("/"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_missing_entries(export_manifest: dict[str, Any], *, repo_root: Path) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for index, entry in enumerate(export_manifest.get("entries", [])):
        if not isinstance(entry, dict):
            continue
        rel_path = repo_relative_path(str(entry.get("path", "")), repo_root=repo_root)
        local_path = repo_path_from_relative(repo_root, rel_path)
        if local_path.exists():
            continue
        missing.append(
            {
                "manifest_index": index,
                "path": rel_path,
                "sha256": entry.get("sha256"),
                "file_size": entry.get("file_size"),
                "mesh_block": entry.get("mesh_block"),
                "vertex_count": entry.get("vertex_count", 0),
                "face_count": entry.get("face_count", 0),
                "faced": bool(entry.get("faced")),
                "export_batch": entry.get("export_batch"),
                "provenance": entry.get("provenance"),
            }
        )
    return missing


def build_sha_index(scan_roots: list[Path], *, repo_root: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for root in scan_roots:
        if not root.exists():
            continue
        for obj_path in sorted(root.rglob("*.obj")):
            rel_path = repo_relative_path(obj_path, repo_root=repo_root)
            digest = file_sha256(obj_path)
            out.setdefault(digest, []).append(rel_path)
    return out


def text_without_face_lines(path: Path, *, newline: str = "\n", extra_suffix: str = "") -> bytes:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    kept = [line for line in lines if not line.startswith("f ")]
    return (newline.join(kept) + newline + extra_suffix).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def derived_no_face_variants(
    path: Path, *, expected_sha: str | None, expected_size: int | None
) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for name, newline, extra_suffix in (
        ("no-face-lf", "\n", ""),
        ("no-face-crlf", "\r\n", ""),
        ("no-face-crlf-plus-lf", "\r\n", "\n"),
    ):
        data = text_without_face_lines(path, newline=newline, extra_suffix=extra_suffix)
        digest = sha256_bytes(data)
        variants.append(
            {
                "variant": name,
                "size": len(data),
                "sha256": digest,
                "size_delta": len(data) - expected_size if expected_size is not None else None,
                "matches_expected_sha": bool(expected_sha and digest == expected_sha),
            }
        )
    return variants


def score_candidate(entry: dict[str, Any], missing: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    for key, weight, label in (
        ("mesh_block", 4, "same-mesh-block"),
        ("vertex_count", 3, "same-vertex-count"),
        ("face_count", 2, "same-face-count"),
        ("file_size", 2, "same-file-size"),
    ):
        if entry.get(key) == missing.get(key):
            score += weight
            reasons.append(label)
    if Path(str(entry.get("path", ""))).name == Path(str(missing.get("path", ""))).name:
        score += 1
        reasons.append("same-basename")
    return score, reasons


def candidate_entries_for_missing(
    export_entries: Iterable[dict[str, Any]],
    missing: dict[str, Any],
    *,
    repo_root: Path,
    limit: int = 12,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    expected_sha = missing.get("sha256") if isinstance(missing.get("sha256"), str) else None
    expected_size = missing.get("file_size") if isinstance(missing.get("file_size"), int) else None

    for entry in export_entries:
        if not isinstance(entry, dict):
            continue
        rel_path = repo_relative_path(str(entry.get("path", "")), repo_root=repo_root)
        if rel_path == missing["path"]:
            continue
        local_path = repo_path_from_relative(repo_root, rel_path)
        if not local_path.exists():
            continue
        score, reasons = score_candidate(entry, missing)
        if score < 5:
            continue

        derived_variants = []
        if missing.get("face_count") == 0 and entry.get("face_count", 0) > 0:
            derived_variants = derived_no_face_variants(
                local_path,
                expected_sha=expected_sha,
                expected_size=expected_size,
            )

        candidates.append(
            {
                "path": rel_path,
                "asset_id": entry.get("asset_id"),
                "sha256": entry.get("sha256"),
                "file_size": entry.get("file_size"),
                "mesh_block": entry.get("mesh_block"),
                "vertex_count": entry.get("vertex_count", 0),
                "face_count": entry.get("face_count", 0),
                "faced": bool(entry.get("faced")),
                "score": score,
                "score_reasons": reasons,
                "derived_no_face_variants": derived_variants,
            }
        )

    return sorted(
        candidates,
        key=lambda row: (
            -int(row["score"]),
            abs((row.get("file_size") or 0) - (expected_size or 0)),
            str(row["path"]),
        ),
    )[:limit]


def build_repair_report(
    *,
    repo_root: Path = REPO_ROOT,
    export_manifest_path: Path = DEFAULT_EXPORT_MANIFEST,
    scan_roots: list[Path] | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    export_manifest = _load_json(export_manifest_path)
    export_entries = [entry for entry in export_manifest.get("entries", []) if isinstance(entry, dict)]
    scan_roots = scan_roots or [repo_root / "Exports", repo_root / "Assets" / "build" / "flythrough"]
    missing = manifest_missing_entries(export_manifest, repo_root=repo_root)
    sha_index = build_sha_index(scan_roots, repo_root=repo_root)

    repaired = 0
    entries: list[dict[str, Any]] = []
    for entry in missing:
        sha = entry.get("sha256")
        matches = sha_index.get(str(sha), []) if sha else []
        repair_status = "not-repairable"
        copied_from = None
        if matches:
            repair_status = "repairable-exact-sha"
            copied_from = matches[0]
            if apply:
                source = repo_path_from_relative(repo_root, copied_from)
                target = repo_path_from_relative(repo_root, entry["path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                if file_sha256(target) != sha:
                    raise RuntimeError(f"Copied file hash mismatch for {entry['path']}")
                repair_status = "repaired-exact-sha"
                repaired += 1

        entries.append(
            {
                **entry,
                "exact_sha_matches": matches,
                "similar_existing_candidates": candidate_entries_for_missing(
                    export_entries,
                    entry,
                    repo_root=repo_root,
                ),
                "repair_status": repair_status,
                "copied_from": copied_from if apply and matches else None,
            }
        )

    return {
        "schema": "flythrough-missing-obj-repair-report-v1",
        "generated_at": _now_iso(),
        "applied": apply,
        "inputs": {
            "export_manifest": repo_relative_path(export_manifest_path, repo_root=repo_root),
            "scan_roots": [repo_relative_path(root, repo_root=repo_root) for root in scan_roots],
        },
        "summary": {
            "missing_entries": len(missing),
            "repairable_exact_sha": sum(1 for entry in entries if entry["exact_sha_matches"]),
            "repaired": repaired,
            "unrepaired": len(missing) - repaired,
        },
        "entries": entries,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root.")
    parser.add_argument("--export-manifest", type=Path, default=DEFAULT_EXPORT_MANIFEST)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--scan-root", type=Path, action="append", help="Root to scan for duplicate OBJ files.")
    parser.add_argument("--apply", action="store_true", help="Copy exact SHA-256 matches into missing manifest paths.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    scan_roots = args.scan_root or [repo_root / "Exports", repo_root / "Assets" / "build" / "flythrough"]
    report = build_repair_report(
        repo_root=repo_root,
        export_manifest_path=args.export_manifest,
        scan_roots=scan_roots,
        apply=args.apply,
    )
    _write_json(args.report_out, report)
    summary = report["summary"]
    print(
        f"missing={summary['missing_entries']} repairable={summary['repairable_exact_sha']} "
        f"repaired={summary['repaired']} report={repo_relative_path(args.report_out, repo_root=repo_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
