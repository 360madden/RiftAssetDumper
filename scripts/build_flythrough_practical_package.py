#!/usr/bin/env python3
"""Build the practical 350-entry flythrough OBJ/MTL review package.

This orchestrates the generated artifacts that make the 350 OBJ set usable
downstream while preserving truth boundaries:

* one explicit source substitution for the missing no-ID OBJ row,
* explicit visual texture fallbacks for still-unrecovered DDS refs,
* the 350-row OBJ/texture manifest and per-row bundle,
* OBJ/MTL smoke evidence,
* one combined portable OBJ/MTL package, and
* a local HTML triage gallery with substitution/fallback labels.

Generated outputs stay under ``Assets/build/flythrough`` and must not be
committed.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from build_flythrough_combined_obj_package import build_combined_obj_package
from build_flythrough_obj_texture_manifest import (
    build_manifest,
    load_source_substitutions,
    load_texture_fallbacks,
    verify_bundle,
    write_bundle,
    write_csv,
)
from build_flythrough_texture_triage_gallery import render_gallery
from smoke_flythrough_obj_texture_bundle import render_markdown as render_smoke_markdown
from smoke_flythrough_obj_texture_bundle import smoke_bundle

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH_ROOT = REPO_ROOT / "Assets" / "build" / "flythrough"

DEFAULT_REDRIVE_MANIFEST = FLYTHROUGH_ROOT / "evidence" / "missing-obj-repair" / "bulk-redrive-failed-manifest.json"
DEFAULT_REDRIVE_OUTPUT_DIR = FLYTHROUGH_ROOT / "evidence" / "missing-obj-repair" / "bulk-redrive-failed-objs"
DEFAULT_SOURCE_SUBSTITUTIONS = FLYTHROUGH_ROOT / "evidence" / "missing-obj-repair" / "source-substitutions.json"
DEFAULT_TEXTURELESS_TRIAGE = FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "textureless-triage.json"
DEFAULT_TEXTURE_RECOVERY_REPORT = (
    FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "recovery" / "textureless-dds-recovery-report.json"
)
DEFAULT_TEXTURE_FALLBACKS = FLYTHROUGH_ROOT / "evidence" / "textureless-assets" / "recovery" / "texture-fallbacks.json"

DEFAULT_MANIFEST_OUT = FLYTHROUGH_ROOT / "flythrough-obj-texture-manifest-practical-350-texture-fallbacks.json"
DEFAULT_CSV_OUT = FLYTHROUGH_ROOT / "flythrough-obj-texture-manifest-practical-350-texture-fallbacks.csv"
DEFAULT_BUNDLE_ROOT = FLYTHROUGH_ROOT / "obj-texture-bundle-practical-350-texture-fallbacks"
DEFAULT_SMOKE_JSON = FLYTHROUGH_ROOT / "evidence" / "practical-350-texture-fallbacks" / "obj-texture-bundle-smoke.json"
DEFAULT_SMOKE_MD = FLYTHROUGH_ROOT / "evidence" / "practical-350-texture-fallbacks" / "OBJ_TEXTURE_BUNDLE_SMOKE.md"
DEFAULT_COMBINED_ROOT = FLYTHROUGH_ROOT / "combined-obj-package-practical-350-texture-fallbacks"
DEFAULT_GALLERY_OUT = FLYTHROUGH_ROOT / "texture-triage-gallery-practical-350-texture-fallbacks" / "index.html"
DEFAULT_BUILD_REPORT = (
    FLYTHROUGH_ROOT / "evidence" / "practical-350-texture-fallbacks" / "practical-package-build-report.json"
)

DEFAULT_MISSING_MANIFEST_INDEX = 121
DEFAULT_MISSING_ORIGINAL_SOURCE_OBJ = "Exports/Exports/decode-nif-geometry/decode-nif-geometry-mesh17.obj"
DEFAULT_SOURCE_CANDIDATE_ASSET_ID = "07f37c99a80da009"


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
    for segment in ("Assets/build/flythrough/", "Exports/"):
        index = raw.find(segment)
        if index >= 0:
            return raw[index:]
    return raw


def repo_path_from_relative(repo_root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        return path
    return repo_root.joinpath(*_to_posix(relative).split("/"))


def build_source_substitution_payload(
    *,
    repo_root: Path,
    redrive_manifest_path: Path,
    redrive_output_dir: Path,
    manifest_index: int = DEFAULT_MISSING_MANIFEST_INDEX,
    original_source_obj: str = DEFAULT_MISSING_ORIGINAL_SOURCE_OBJ,
    candidate_asset_id: str = DEFAULT_SOURCE_CANDIDATE_ASSET_ID,
) -> dict[str, Any]:
    redrive_manifest = _load_json(redrive_manifest_path)
    redrive_entry = next(
        (
            entry
            for entry in redrive_manifest.get("Entries", [])
            if entry.get("nif_hash") == candidate_asset_id and entry.get("status") == "exported"
        ),
        None,
    )
    if redrive_entry is None:
        raise FileNotFoundError(f"No exported redrive entry for {candidate_asset_id} in {redrive_manifest_path}")
    replacement_source = redrive_output_dir / str(redrive_entry["obj_path"])
    if not replacement_source.exists():
        raise FileNotFoundError(f"Redrive OBJ candidate is missing: {replacement_source}")

    return {
        "schema": "flythrough-source-substitutions-v1",
        "generated_at": _now_iso(),
        "purpose": "Practical downstream access only; does not promote exact recovered source truth.",
        "entries": [
            {
                "manifest_index": manifest_index,
                "original_source_obj": original_source_obj,
                "replacement_source_obj": repo_relative_path(replacement_source, repo_root=repo_root),
                "candidate_asset_id": candidate_asset_id,
                "evidence_manifest": repo_relative_path(redrive_manifest_path, repo_root=repo_root),
                "review_status": "candidate-practical-access",
                "durable_truth": False,
                "reason": (
                    "High-similarity mesh17 candidate materialized by linked-stream fallback; "
                    "exact SHA repair remains unproven."
                ),
            }
        ],
    }


def target_ref_to_manifest_indices(triage_report: dict[str, Any]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for row in triage_report.get("rows", []):
        if not isinstance(row, dict) or not isinstance(row.get("manifest_index"), int):
            continue
        for ref in row.get("row_dds_refs", []):
            if isinstance(ref, str) and ref:
                out.setdefault(ref.lower(), []).append(int(row["manifest_index"]))
    return out


def build_texture_fallback_payload(
    *,
    triage_report_path: Path,
    recovery_report_path: Path,
) -> dict[str, Any]:
    triage = _load_json(triage_report_path)
    recovery = _load_json(recovery_report_path)
    refs_to_indices = target_ref_to_manifest_indices(triage)

    entries: list[dict[str, Any]] = []
    for target_ref, candidates in sorted(recovery.get("visual_fallback_candidates", {}).items()):
        if not candidates:
            continue
        manifest_indices = refs_to_indices.get(str(target_ref).lower(), [])
        if not manifest_indices:
            continue
        candidate = candidates[0]
        for manifest_index in manifest_indices:
            entries.append(
                {
                    "manifest_index": manifest_index,
                    "target_dds_ref": target_ref,
                    "replacement_dds_ref": candidate.get("dds_ref"),
                    "replacement_png_name": candidate.get("png_name"),
                    "replacement_png_path": candidate.get("png_path"),
                    "score": candidate.get("score"),
                    "reasons": candidate.get("reasons", []),
                    "review_status": "visual-fallback",
                    "durable_truth": False,
                    "evidence_report": repo_relative_path(recovery_report_path),
                    "reason": (
                        "Top visual fallback candidate from missing exact DDS recovery report; "
                        "exact DDS name match remains unavailable."
                    ),
                }
            )

    return {
        "schema": "flythrough-texture-fallbacks-v1",
        "generated_at": _now_iso(),
        "purpose": "Practical downstream visual fallback only; does not promote exact recovered DDS truth.",
        "entries": entries,
    }


def build_practical_package(
    *,
    repo_root: Path = REPO_ROOT,
    redrive_manifest_path: Path = DEFAULT_REDRIVE_MANIFEST,
    redrive_output_dir: Path = DEFAULT_REDRIVE_OUTPUT_DIR,
    source_substitutions_out: Path = DEFAULT_SOURCE_SUBSTITUTIONS,
    textureless_triage_path: Path = DEFAULT_TEXTURELESS_TRIAGE,
    texture_recovery_report_path: Path = DEFAULT_TEXTURE_RECOVERY_REPORT,
    texture_fallbacks_out: Path = DEFAULT_TEXTURE_FALLBACKS,
    manifest_out: Path = DEFAULT_MANIFEST_OUT,
    csv_out: Path = DEFAULT_CSV_OUT,
    bundle_root: Path = DEFAULT_BUNDLE_ROOT,
    smoke_json_out: Path = DEFAULT_SMOKE_JSON,
    smoke_markdown_out: Path = DEFAULT_SMOKE_MD,
    combined_root: Path = DEFAULT_COMBINED_ROOT,
    gallery_out: Path = DEFAULT_GALLERY_OUT,
    build_report_out: Path = DEFAULT_BUILD_REPORT,
    max_gallery_cards: int = 400,
) -> dict[str, Any]:
    source_substitution_payload = build_source_substitution_payload(
        repo_root=repo_root,
        redrive_manifest_path=redrive_manifest_path,
        redrive_output_dir=redrive_output_dir,
    )
    _write_json(source_substitutions_out, source_substitution_payload)

    texture_fallback_payload = build_texture_fallback_payload(
        triage_report_path=textureless_triage_path,
        recovery_report_path=texture_recovery_report_path,
    )
    _write_json(texture_fallbacks_out, texture_fallback_payload)

    manifest = build_manifest(
        repo_root=repo_root,
        bundle_root=bundle_root,
        allow_single_candidate_materials=True,
        allow_common_candidate_materials=True,
        allow_textureless_triage_materials=True,
        materialize_untextured=True,
        source_substitutions=load_source_substitutions(source_substitutions_out, repo_root=repo_root),
        texture_fallbacks=load_texture_fallbacks(texture_fallbacks_out, repo_root=repo_root),
    )
    _write_json(manifest_out, manifest)
    write_csv(csv_out, manifest)

    bundle_write = write_bundle(manifest, repo_root=repo_root, bundle_root=bundle_root)
    manifest["summary"]["bundle_write"] = bundle_write
    bundle_verify = verify_bundle(manifest, repo_root=repo_root)
    manifest["summary"]["bundle_verify"] = bundle_verify
    _write_json(manifest_out, manifest)

    smoke_report = smoke_bundle(repo_root=repo_root, manifest_path=manifest_out)
    _write_json(smoke_json_out, smoke_report)
    _write_text(smoke_markdown_out, render_smoke_markdown(smoke_report))

    combined_report = build_combined_obj_package(
        repo_root=repo_root,
        manifest_path=manifest_out,
        obj_out=combined_root / "combined.obj",
        mtl_out=combined_root / "combined.mtl",
        report_out=combined_root / "combined-obj-package-report.json",
        markdown_out=combined_root / "COMBINED_OBJ_PACKAGE.md",
    )

    gallery_html = render_gallery(manifest, html_out=gallery_out, repo_root=repo_root, max_cards=max_gallery_cards)
    _write_text(gallery_out, gallery_html)

    report = {
        "schema": "flythrough-practical-package-build-report-v1",
        "generated_at": _now_iso(),
        "inputs": {
            "redrive_manifest": repo_relative_path(redrive_manifest_path, repo_root=repo_root),
            "redrive_output_dir": repo_relative_path(redrive_output_dir, repo_root=repo_root),
            "textureless_triage": repo_relative_path(textureless_triage_path, repo_root=repo_root),
            "texture_recovery_report": repo_relative_path(texture_recovery_report_path, repo_root=repo_root),
        },
        "outputs": {
            "source_substitutions": repo_relative_path(source_substitutions_out, repo_root=repo_root),
            "texture_fallbacks": repo_relative_path(texture_fallbacks_out, repo_root=repo_root),
            "manifest": repo_relative_path(manifest_out, repo_root=repo_root),
            "csv": repo_relative_path(csv_out, repo_root=repo_root),
            "bundle_root": repo_relative_path(bundle_root, repo_root=repo_root),
            "smoke_json": repo_relative_path(smoke_json_out, repo_root=repo_root),
            "smoke_markdown": repo_relative_path(smoke_markdown_out, repo_root=repo_root),
            "combined_report": repo_relative_path(
                combined_root / "combined-obj-package-report.json", repo_root=repo_root
            ),
            "combined_markdown": repo_relative_path(combined_root / "COMBINED_OBJ_PACKAGE.md", repo_root=repo_root),
            "gallery": repo_relative_path(gallery_out, repo_root=repo_root),
        },
        "summary": {
            "manifest_entries": manifest["summary"]["total_entries"],
            "materializable_entries": manifest["summary"]["materializable_entries"],
            "source_substituted_entries": manifest["summary"]["source_substituted_entries"],
            "texture_fallback_refs": manifest["summary"]["texture_fallback_refs"],
            "bundle_verify_pass": bundle_verify["pass"],
            "smoke_pass": smoke_report["summary"]["pass"],
            "combined_entries": combined_report["summary"]["combined_entries"],
            "combined_skipped_entries": combined_report["summary"]["skipped_entries"],
            "combined_verify_pass": combined_report["summary"]["verify_pass"],
            "gallery_exists": gallery_out.exists(),
        },
    }
    _write_json(build_report_out, report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--redrive-manifest", type=Path, default=DEFAULT_REDRIVE_MANIFEST)
    parser.add_argument("--redrive-output-dir", type=Path, default=DEFAULT_REDRIVE_OUTPUT_DIR)
    parser.add_argument("--source-substitutions-out", type=Path, default=DEFAULT_SOURCE_SUBSTITUTIONS)
    parser.add_argument("--textureless-triage", type=Path, default=DEFAULT_TEXTURELESS_TRIAGE)
    parser.add_argument("--texture-recovery-report", type=Path, default=DEFAULT_TEXTURE_RECOVERY_REPORT)
    parser.add_argument("--texture-fallbacks-out", type=Path, default=DEFAULT_TEXTURE_FALLBACKS)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST_OUT)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV_OUT)
    parser.add_argument("--bundle-root", type=Path, default=DEFAULT_BUNDLE_ROOT)
    parser.add_argument("--smoke-json-out", type=Path, default=DEFAULT_SMOKE_JSON)
    parser.add_argument("--smoke-markdown-out", type=Path, default=DEFAULT_SMOKE_MD)
    parser.add_argument("--combined-root", type=Path, default=DEFAULT_COMBINED_ROOT)
    parser.add_argument("--gallery-out", type=Path, default=DEFAULT_GALLERY_OUT)
    parser.add_argument("--build-report-out", type=Path, default=DEFAULT_BUILD_REPORT)
    parser.add_argument("--max-gallery-cards", type=int, default=400)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    report = build_practical_package(
        repo_root=repo_root,
        redrive_manifest_path=args.redrive_manifest,
        redrive_output_dir=args.redrive_output_dir,
        source_substitutions_out=args.source_substitutions_out,
        textureless_triage_path=args.textureless_triage,
        texture_recovery_report_path=args.texture_recovery_report,
        texture_fallbacks_out=args.texture_fallbacks_out,
        manifest_out=args.manifest_out,
        csv_out=args.csv_out,
        bundle_root=args.bundle_root,
        smoke_json_out=args.smoke_json_out,
        smoke_markdown_out=args.smoke_markdown_out,
        combined_root=args.combined_root,
        gallery_out=args.gallery_out,
        build_report_out=args.build_report_out,
        max_gallery_cards=args.max_gallery_cards,
    )
    summary = report["summary"]
    print(
        "practical package: "
        f"entries={summary['materializable_entries']}/{summary['manifest_entries']} "
        f"source_substitutions={summary['source_substituted_entries']} "
        f"texture_fallback_refs={summary['texture_fallback_refs']} "
        f"bundle={summary['bundle_verify_pass']} smoke={summary['smoke_pass']} "
        f"combined={summary['combined_entries']} skipped={summary['combined_skipped_entries']} "
        f"gallery={summary['gallery_exists']}"
    )
    return (
        0
        if all(
            [
                summary["materializable_entries"] == summary["manifest_entries"],
                summary["bundle_verify_pass"],
                summary["smoke_pass"],
                summary["combined_verify_pass"],
                summary["combined_skipped_entries"] == 0,
                summary["gallery_exists"],
            ]
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
