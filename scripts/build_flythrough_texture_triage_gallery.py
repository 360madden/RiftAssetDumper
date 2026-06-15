#!/usr/bin/env python3
"""Build a local HTML triage gallery for flythrough OBJ/texture coverage.

The OBJ/MTL bundle is useful only if humans can quickly inspect what is
materialized and what is still missing. This script renders a generated,
gitignored HTML report from ``flythrough-obj-texture-manifest*.json`` with:

* summary counts,
* materialized OBJ/MTL cards with texture previews, and
* a focused table for remaining non-materialized rows.
"""

from __future__ import annotations

import argparse
import html
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FLYTHROUGH_ROOT = REPO_ROOT / "Assets" / "build" / "flythrough"
DEFAULT_MANIFEST = FLYTHROUGH_ROOT / "flythrough-obj-texture-manifest-full-available.json"
FALLBACK_MANIFESTS = [
    FLYTHROUGH_ROOT / "flythrough-obj-texture-manifest-candidate-textures.json",
    FLYTHROUGH_ROOT / "flythrough-obj-texture-manifest.json",
]
DEFAULT_OUT = FLYTHROUGH_ROOT / "texture-triage-gallery" / "index.html"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _to_posix(value: str | Path) -> str:
    return str(value).replace("\\", "/")


def repo_path_from_relative(repo_root: Path, relative: str) -> Path:
    return repo_root.joinpath(*relative.split("/"))


def relative_link(target_repo_relative: str | None, *, html_out: Path, repo_root: Path) -> str | None:
    if not target_repo_relative:
        return None
    target = repo_path_from_relative(repo_root, target_repo_relative)
    return _to_posix(os.path.relpath(target, html_out.parent))


def choose_preview_texture(entry: dict[str, Any]) -> dict[str, Any] | None:
    linked = entry.get("linked_textures") or []
    if not linked:
        return None
    chosen_diffuse = (entry.get("chosen_material_textures") or {}).get("diffuse")
    if chosen_diffuse:
        for texture in linked:
            if texture.get("name") == chosen_diffuse:
                return texture
    for role in ("diffuse", "emissive", "specular", "normal", "alpha", "mask", "unknown"):
        for texture in linked:
            if texture.get("role") == role:
                return texture
    return linked[0]


def non_materialized_reason(entry: dict[str, Any]) -> str:
    if not entry.get("source_exists"):
        return "missing-source-obj"
    if not entry.get("linked_texture_count"):
        if entry.get("asset_id"):
            return "asset-without-linked-textures"
        if entry.get("candidate_status") == "no-geometry-signature-match":
            return "idless-no-candidate"
        return "no-linked-textures"
    return "not-materialized"


def build_gallery_model(manifest: dict[str, Any]) -> dict[str, Any]:
    entries = manifest.get("entries", [])
    materialized = [entry for entry in entries if entry.get("materializable")]
    remaining = [entry for entry in entries if not entry.get("materializable")]
    texture_sources = Counter(entry.get("texture_source") or "none" for entry in materialized)
    remaining_reasons = Counter(non_materialized_reason(entry) for entry in remaining)
    roles = Counter(
        texture.get("role") or "unknown" for entry in materialized for texture in entry.get("linked_textures", [])
    )
    source_substitutions = [entry for entry in materialized if isinstance(entry.get("source_substitution"), dict)]
    texture_fallback_entries = [entry for entry in materialized if entry.get("texture_fallbacks")]
    texture_fallback_refs = [
        fallback
        for entry in texture_fallback_entries
        for fallback in entry.get("texture_fallbacks", [])
        if isinstance(fallback, dict)
    ]
    return {
        "summary": manifest.get("summary", {}),
        "entries": entries,
        "materialized": materialized,
        "remaining": remaining,
        "texture_sources": dict(sorted(texture_sources.items())),
        "remaining_reasons": dict(sorted(remaining_reasons.items())),
        "texture_roles": dict(sorted(roles.items())),
        "source_substitutions": source_substitutions,
        "texture_fallback_entries": texture_fallback_entries,
        "texture_fallback_refs": texture_fallback_refs,
    }


def _pill(label: str, value: Any) -> str:
    return f'<span class="pill"><strong>{_esc(label)}</strong> {_esc(value)}</span>'


def _summary_html(model: dict[str, Any]) -> str:
    summary = model["summary"]
    verify = summary.get("bundle_verify", {})
    parts = [
        _pill("total", summary.get("total_entries")),
        _pill("materialized", summary.get("materializable_entries")),
        _pill("remaining", len(model["remaining"])),
        _pill("single-candidate", summary.get("single_candidate_materialized_entries", 0)),
        _pill("common-candidate", summary.get("common_candidate_materialized_entries", 0)),
        _pill("source substitutions", summary.get("source_substituted_entries", 0)),
        _pill("texture fallback refs", summary.get("texture_fallback_refs", 0)),
        _pill("verify", "pass" if verify.get("pass") else "not-run"),
        _pill("missing textures", verify.get("missing_texture_refs_count", "n/a")),
    ]
    return "\n".join(parts)


def _counter_table(title: str, values: dict[str, int]) -> str:
    rows = "\n".join(
        f'<tr><td>{_esc(key)}</td><td class="num">{_esc(value)}</td></tr>' for key, value in values.items()
    )
    return f"""
<section>
  <h2>{_esc(title)}</h2>
  <table>
    <thead><tr><th>Bucket</th><th>Count</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>
"""


def _materialized_card(entry: dict[str, Any], *, html_out: Path, repo_root: Path) -> str:
    preview = choose_preview_texture(entry)
    image_html = '<div class="no-preview">no preview</div>'
    if preview and preview.get("path"):
        href = relative_link(preview["path"], html_out=html_out, repo_root=repo_root)
        image_html = f'<a href="{_esc(href)}"><img src="{_esc(href)}" alt="{_esc(preview.get("name"))}"></a>'

    obj_href = relative_link(entry.get("bundled_obj"), html_out=html_out, repo_root=repo_root)
    mtl_href = relative_link(entry.get("bundled_mtl"), html_out=html_out, repo_root=repo_root)
    textures = ", ".join(texture.get("name", "") for texture in entry.get("linked_textures", [])[:4])
    if entry.get("linked_texture_count", 0) > 4:
        textures += f", +{entry['linked_texture_count'] - 4} more"
    badges = []
    source_substitution = entry.get("source_substitution")
    if isinstance(source_substitution, dict):
        badges.append(
            _pill(
                "source substitute",
                f"{source_substitution.get('review_status') or source_substitution.get('status')}; "
                f"durable={source_substitution.get('durable_truth')}",
            )
        )
    texture_fallbacks = [fallback for fallback in entry.get("texture_fallbacks", []) if isinstance(fallback, dict)]
    if texture_fallbacks:
        badges.append(_pill("texture fallbacks", f"{len(texture_fallbacks)}; durable=false"))
    badges_html = f'<p class="badges">{" ".join(badges)}</p>' if badges else ""
    card_classes = ["card", f"source-{entry.get('texture_source') or 'none'}"]
    if source_substitution:
        card_classes.append("has-source-substitution")
    if texture_fallbacks:
        card_classes.append("has-texture-fallback")

    return f"""
<article class="{_esc(" ".join(card_classes))}">
  <div class="thumb">{image_html}</div>
  <div class="meta">
    <h3>#{_esc(entry.get("manifest_index"))} {_esc(entry.get("asset_id") or "id-less")}</h3>
    <p>{_pill("source", entry.get("texture_source"))} {_pill("textures", entry.get("linked_texture_count"))}</p>
    {badges_html}
    <p class="small">{_esc(textures)}</p>
    <p><a href="{_esc(obj_href)}">OBJ</a> · <a href="{_esc(mtl_href)}">MTL</a></p>
  </div>
</article>
"""


def _remaining_row(entry: dict[str, Any]) -> str:
    candidates = ", ".join(entry.get("candidate_asset_ids") or [])
    return f"""
<tr>
  <td class="num">{_esc(entry.get("manifest_index"))}</td>
  <td><code>{_esc(entry.get("source_obj"))}</code></td>
  <td>{_esc(non_materialized_reason(entry))}</td>
  <td>{_esc(entry.get("asset_id") or "")}</td>
  <td>{_esc(candidates)}</td>
  <td>{_esc(entry.get("candidate_status") or "")}</td>
</tr>
"""


def _source_substitution_table(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return ""
    rows = []
    for entry in entries:
        substitution = entry.get("source_substitution") or {}
        rows.append(
            f"""
<tr>
  <td class="num">{_esc(entry.get("manifest_index"))}</td>
  <td><code>{_esc(entry.get("original_source_obj") or substitution.get("replaces_source_obj"))}</code></td>
  <td><code>{_esc(substitution.get("replacement_source_obj") or entry.get("source_obj"))}</code></td>
  <td>{_esc(substitution.get("candidate_asset_id") or "")}</td>
  <td>{_esc(substitution.get("durable_truth"))}</td>
</tr>
"""
        )
    return f"""
<section>
  <h2>Practical source substitutions ({len(entries)})</h2>
  <p class="small">These rows improve access but do not claim exact source recovery unless durable truth is true.</p>
  <table>
    <thead><tr><th>#</th><th>Original source</th><th>Replacement source</th><th>Candidate asset</th><th>Durable truth</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</section>
"""


def _texture_fallback_table(entries: list[dict[str, Any]]) -> str:
    rows = []
    for entry in entries:
        for fallback in entry.get("texture_fallbacks", []):
            if not isinstance(fallback, dict):
                continue
            rows.append(
                f"""
<tr>
  <td class="num">{_esc(entry.get("manifest_index"))}</td>
  <td>{_esc(entry.get("asset_id") or "")}</td>
  <td><code>{_esc(fallback.get("target_dds_ref"))}</code></td>
  <td><code>{_esc(fallback.get("replacement_dds_ref") or "")}</code></td>
  <td>{_esc(fallback.get("replacement_png_name") or "")}</td>
  <td>{_esc(fallback.get("durable_truth"))}</td>
</tr>
"""
            )
    if not rows:
        return ""
    return f"""
<section>
  <h2>Practical texture fallbacks ({len(rows)})</h2>
  <p class="small">These PNGs are visual substitutes for review/import usability; exact DDS recovery remains separate unless durable truth is true.</p>
  <table>
    <thead><tr><th>#</th><th>Asset ID</th><th>Missing DDS ref</th><th>Replacement DDS ref</th><th>Replacement PNG</th><th>Durable truth</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</section>
"""


def render_gallery(manifest: dict[str, Any], *, html_out: Path, repo_root: Path, max_cards: int = 400) -> str:
    model = build_gallery_model(manifest)
    cards = "\n".join(
        _materialized_card(entry, html_out=html_out, repo_root=repo_root) for entry in model["materialized"][:max_cards]
    )
    remaining_rows = "\n".join(_remaining_row(entry) for entry in model["remaining"])
    summary = manifest.get("summary", {})

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Flythrough OBJ Texture Triage</title>
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; background: #111827; color: #e5e7eb; }}
    header {{ padding: 24px; background: #020617; border-bottom: 1px solid #334155; }}
    main {{ padding: 24px; }}
    a {{ color: #93c5fd; }}
    code {{ color: #fca5a5; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0 28px; }}
    th, td {{ border-bottom: 1px solid #334155; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ color: #bfdbfe; }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .pill {{ display: inline-block; margin: 4px 6px 4px 0; padding: 4px 8px; border-radius: 999px; background: #1f2937; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }}
    .card {{ display: grid; grid-template-columns: 92px 1fr; gap: 12px; padding: 12px; background: #1f2937; border: 1px solid #374151; border-radius: 12px; }}
    .card.has-source-substitution, .card.has-texture-fallback {{ border-color: #f59e0b; box-shadow: 0 0 0 1px rgba(245, 158, 11, .25); }}
    .card h3 {{ margin: 0 0 8px; font-size: 15px; }}
    .card p {{ margin: 6px 0; }}
    .thumb {{ width: 92px; height: 92px; background: #0f172a; border-radius: 8px; display: grid; place-items: center; overflow: hidden; }}
    .thumb img {{ max-width: 92px; max-height: 92px; image-rendering: auto; }}
    .no-preview {{ color: #94a3b8; font-size: 12px; text-align: center; }}
    .small {{ color: #cbd5e1; font-size: 12px; overflow-wrap: anywhere; }}
    .badges .pill {{ background: #78350f; color: #fde68a; }}
  </style>
</head>
<body>
  <header>
    <h1>Flythrough OBJ Texture Triage</h1>
    <p>Generated {_esc(_now_iso())} from schema <code>{_esc(manifest.get("schema"))}</code>.</p>
    <div>{_summary_html(model)}</div>
  </header>
  <main>
    {_counter_table("Texture sources", model["texture_sources"])}
    {_counter_table("Remaining gap reasons", model["remaining_reasons"])}
    {_counter_table("Texture roles in materialized rows", model["texture_roles"])}
    {_source_substitution_table(model["source_substitutions"])}
    {_texture_fallback_table(model["texture_fallback_entries"])}

    <section>
      <h2>Remaining non-materialized rows ({len(model["remaining"])})</h2>
      <table>
        <thead><tr><th>#</th><th>Source OBJ</th><th>Reason</th><th>Asset ID</th><th>Candidates</th><th>Candidate status</th></tr></thead>
        <tbody>{remaining_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>Materialized preview cards ({min(len(model["materialized"]), max_cards)} of {len(model["materialized"])})</h2>
      <p class="small">Bundle root: <code>{_esc(summary.get("bundle_root"))}</code></p>
      <div class="grid">{cards}</div>
    </section>
  </main>
</body>
</html>
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root.")
    parser.add_argument("--manifest", type=Path, default=None, help="Input OBJ texture manifest JSON.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output HTML path.")
    parser.add_argument("--max-cards", type=int, default=400, help="Maximum materialized cards to render.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    manifest_path = args.manifest
    if manifest_path is None:
        manifest_path = next(
            (path for path in [DEFAULT_MANIFEST, *FALLBACK_MANIFESTS] if path.exists()), DEFAULT_MANIFEST
        )
    manifest = _load_json(manifest_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        render_gallery(manifest, html_out=args.out, repo_root=repo_root, max_cards=args.max_cards),
        encoding="utf-8",
        newline="\n",
    )
    model = build_gallery_model(manifest)
    print(
        f"wrote {_to_posix(os.path.relpath(args.out, repo_root))} "
        f"materialized={len(model['materialized'])} remaining={len(model['remaining'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
