#!/usr/bin/env python3
"""Phase 1 M1.2 — full-matrix @304 BodyFirst16 magic/prefix analysis from mesh#34 probes.

Reads ``Exports/mesh329-family-attribute-role-matrix.json`` for target IDs (``IDsCovered``,
or unique IDs from matrix rows when absent). For each ID, loads
``probe-nif-mesh-{id}-mesh34.json`` when present and extracts @304 / optional @212
``BodyFirst16`` from meshSize=329 mesh#34 streams.

Writes candidate-only artifacts:
- ``Exports/phase1-m1.2-@304-magic-analysis.json``
- ``Exports/phase1-m1.2-@304-magic-analysis.md``

Run directly::

    python scripts/phase1_m12_304_magic_analysis.py
    python scripts/phase1_m12_304_magic_analysis.py --out Exports

Or via workflow (same pattern as mesh329-attribute-role-matrix)::

    python scripts/rift_workflow.py phase1-m1.2-304-magic-analysis
    python scripts/rift_workflow.py phase1-m1.2-304-magic-analysis --out Exports

Reference: docs/roadmap/project-roadmap.md Phase 1 M1.2, mesh329-family matrix (M1.1).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "Exports"
MATRIX_BASENAME = "mesh329-family-attribute-role-matrix.json"
JSON_OUT_BASENAME = "phase1-m1.2-@304-magic-analysis.json"
MD_OUT_BASENAME = "phase1-m1.2-@304-magic-analysis.md"
SCHEMA = "phase1-m1.2-@304-magic-analysis/v1"
MESH_BLOCK = 34
MESH_SIZE = 329
OFFSET_304 = 304
OFFSET_212 = 212


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _normalize_hex(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower().replace(" ", "")
    if text in ("", "-"):
        return ""
    return text


def _hex_to_bytes(hex_str: str) -> list[int]:
    clean = _normalize_hex(hex_str)
    if len(clean) < 2 or len(clean) % 2:
        return []
    return [int(clean[i : i + 2], 16) for i in range(0, len(clean), 2)]


def _shared_prefix_byte_length(hex_values: list[str], max_bytes: int) -> int:
    """Longest common prefix length (bytes) shared by all non-empty hex strings, capped at max_bytes."""
    normalized = [_normalize_hex(h) for h in hex_values if _normalize_hex(h)]
    if not normalized:
        return 0
    limit = min(max_bytes, min(len(h) // 2 for h in normalized))
    for byte_len in range(limit, 0, -1):
        chars = byte_len * 2
        prefix = normalized[0][:chars]
        if len(prefix) == chars and all(h[:chars] == prefix for h in normalized):
            return byte_len
    return 0


def _has_prefix_022bc2(body_first16: str) -> bool:
    return _normalize_hex(body_first16).startswith("022bc2")


def _c2_in_byte_positions_2_5(body_first16: str) -> bool:
    """True if any byte at indices 2..5 equals 0xC2 (matches M1.2 initial analysis convention)."""
    data = _hex_to_bytes(body_first16)
    if len(data) < 6:
        return False
    return any(data[i] == 0xC2 for i in range(2, min(6, len(data))))


def _parse_id_from_probe(report: dict[str, Any], probe_path: Path) -> str:
    source = report.get("Source")
    if isinstance(source, dict):
        id_prefix = str(source.get("IdPrefix", "")).strip().lower()
        if len(id_prefix) >= 16:
            return id_prefix
    stem = probe_path.stem
    for token in stem.split("-"):
        if len(token) == 16 and all(c in "0123456789abcdef" for c in token):
            return token
    return ""


def _find_stream_body_first16(mesh: dict[str, Any], offset: int) -> dict[str, Any] | None:
    streams = mesh.get("Streams") or []
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        if int(stream.get("MeshPayloadOffset", -1)) != offset:
            continue
        role_stats = stream.get("RoleStats") or {}
        return {
            "MeshPayloadOffset": offset,
            "TargetBlockIndex": stream.get("TargetBlockIndex"),
            "DeclaredPayloadBytes": stream.get("DeclaredPayloadBytes"),
            "BodyFirst16": _normalize_hex(stream.get("BodyFirst16")),
            "Role": str(role_stats.get("PrimaryRole", "") or ""),
            "Confidence": role_stats.get("Confidence"),
        }
    return None


def _extract_mesh34_streams(probe_path: Path) -> dict[str, Any] | None:
    if not probe_path.exists():
        return None
    try:
        report = json.loads(probe_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(report, dict):
        return None
    meshes = report.get("Meshes") or []
    mesh_entries = [
        m
        for m in meshes
        if isinstance(m, dict)
        and int(m.get("MeshBlockIndex", -1)) == MESH_BLOCK
        and int(m.get("MeshSize", 0)) == MESH_SIZE
    ]
    if len(mesh_entries) != 1:
        return None
    mesh = mesh_entries[0]
    stream_304 = _find_stream_body_first16(mesh, OFFSET_304)
    if stream_304 is None or not stream_304.get("BodyFirst16"):
        return None
    stream_212 = _find_stream_body_first16(mesh, OFFSET_212)
    attr_sets = mesh.get("AttributeSets") or []
    attr_count = len(attr_sets) if isinstance(attr_sets, list) else 0
    asset_id = _parse_id_from_probe(report, probe_path)
    return {
        "Id": asset_id,
        "MeshBlock": MESH_BLOCK,
        "MeshSize": MESH_SIZE,
        "AttributeSetCount": attr_count,
        "StreamAt304": stream_304,
        "StreamAt212": stream_212,
        "ProbePath": _repo_relative(probe_path),
        "CandidateOnly": True,
    }


def _matrix_target_ids(matrix: dict[str, Any]) -> list[str]:
    covered = matrix.get("IDsCovered")
    if isinstance(covered, list) and covered:
        return sorted({str(x).strip().lower() for x in covered if str(x).strip()})
    rows = matrix.get("MatrixRows") or []
    ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if int(row.get("MeshBlock", -1)) == MESH_BLOCK:
            idv = str(row.get("Id", "")).strip().lower()
            if idv:
                ids.add(idv)
    return sorted(ids)


def _prefix_counts(hex_values: list[str], byte_len: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    chars = byte_len * 2
    for value in hex_values:
        clean = _normalize_hex(value)
        if len(clean) < chars:
            continue
        prefix = clean[:chars]
        counts[prefix] = counts.get(prefix, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def phase1_m12_304_magic_analysis(
    report_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    """Run full-matrix @304 BodyFirst16 magic/prefix analysis. Returns (json_path, md_path)."""
    from scripts.rift_workflow_utils import format_markdown_cell, load_json_report

    out_dir = Path(report_dir) if report_dir is not None else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    matrix_path = out_dir / MATRIX_BASENAME
    if not matrix_path.exists():
        raise FileNotFoundError(f"Matrix report required: {matrix_path}")

    matrix = load_json_report(matrix_path)
    if not isinstance(matrix, dict):
        raise ValueError(f"Invalid matrix JSON: {matrix_path}")

    target_ids = _matrix_target_ids(matrix)
    per_id: list[dict[str, Any]] = []
    missing_probe: list[str] = []
    missing_304: list[str] = []

    for asset_id in target_ids:
        probe_path = out_dir / f"probe-nif-mesh-{asset_id}-mesh{MESH_BLOCK}.json"
        if not probe_path.exists():
            missing_probe.append(asset_id)
            continue
        row = _extract_mesh34_streams(probe_path)
        if row is None:
            missing_304.append(asset_id)
            continue
        if not row.get("Id"):
            row["Id"] = asset_id
        body304 = row["StreamAt304"]["BodyFirst16"]
        row["HasPrefix022bc2"] = _has_prefix_022bc2(body304)
        row["C2InBytePositions2To5"] = _c2_in_byte_positions_2_5(body304)
        per_id.append(row)

    body304_hex = [r["StreamAt304"]["BodyFirst16"] for r in per_id]
    processed_ids = [r["Id"] for r in per_id]

    shared_prefix = {
        "AcrossProcessedIDs": len(per_id),
        "SharedPrefixBytes4": _shared_prefix_byte_length(body304_hex, 4),
        "SharedPrefixBytes8": _shared_prefix_byte_length(body304_hex, 8),
        "SharedPrefixBytes16": _shared_prefix_byte_length(body304_hex, 16),
        "SharedPrefixHex4": (
            body304_hex[0][:8]
            if per_id and _shared_prefix_byte_length(body304_hex, 4) == 4
            else ""
        ),
        "SharedPrefixHex8": (
            body304_hex[0][:16]
            if per_id and _shared_prefix_byte_length(body304_hex, 8) == 8
            else ""
        ),
        "SharedPrefixHex16": (
            body304_hex[0][:32]
            if per_id and _shared_prefix_byte_length(body304_hex, 16) == 16
            else ""
        ),
    }

    prefix_022bc2_count = sum(1 for r in per_id if r["HasPrefix022bc2"])
    c2_pos_2_5_count = sum(1 for r in per_id if r["C2InBytePositions2To5"])

    aggregates = {
        "MatrixIDsTargeted": len(target_ids),
        "IDsWithMesh34Probe": len(target_ids) - len(missing_probe),
        "IDsProcessed": len(per_id),
        "IDsMissingProbe": missing_probe,
        "IDsMissing304Stream": missing_304,
        "Prefix022bc2Count": prefix_022bc2_count,
        "C2InBytePositions2To5Count": c2_pos_2_5_count,
        "SharedPrefixAt304": shared_prefix,
        "Prefix4ByteCounts": _prefix_counts(body304_hex, 4),
        "Prefix8ByteCounts": _prefix_counts(body304_hex, 8),
    }

    report = {
        "Schema": SCHEMA,
        "CandidateOnly": True,
        "Phase": "Phase 1 M1.2",
        "Milestone": "M1.2",
        "MeshSize": MESH_SIZE,
        "TargetMeshBlock": MESH_BLOCK,
        "ReferenceMatrix": _repo_relative(matrix_path),
        "TargetIDs": target_ids,
        "ProcessedIDs": processed_ids,
        "PerID": per_id,
        "Aggregates": aggregates,
        "ParserExportPromotionAllowed": False,
        "Interpretation": (
            "Phase 1 M1.2 full-matrix @304 BodyFirst16 magic/prefix analysis (candidate-only). "
            "Quantifies shared hex prefixes, 022bc2 lead pattern, and 0xC2 bytes at body indices "
            "2–5 on mesh#34 @304 streams for meshSize=329 family IDs from the M1.1 matrix. "
            "Optional @212 BodyFirst16 included for contrast only; no parser/export promotion."
        ),
    }

    json_path = out_dir / JSON_OUT_BASENAME
    md_path = out_dir / MD_OUT_BASENAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    md_lines = [
        "# Phase 1 M1.2 — @304 BodyFirst16 Magic / Prefix Analysis",
        "",
        "**Candidate-only** · meshSize=329 · mesh#34 · offsets @304 (+ @212 contrast)",
        "",
        f"Schema: `{SCHEMA}`",
        f"Matrix reference: `{report['ReferenceMatrix']}`",
        f"Target IDs (matrix): **{len(target_ids)}** · Processed with @304 BodyFirst16: **{len(per_id)}**",
        "",
        "## Aggregates",
        "",
        f"- Shared prefix (all processed): **4B={shared_prefix['SharedPrefixBytes4']}** · "
        f"**8B={shared_prefix['SharedPrefixBytes8']}** · "
        f"**16B={shared_prefix['SharedPrefixBytes16']}**",
        f"- `022bc2` lead prefix on @304 BodyFirst16: **{prefix_022bc2_count}** / {len(per_id)}",
        f"- `0xC2` in byte positions 2–5: **{c2_pos_2_5_count}** / {len(per_id)}",
        "",
    ]
    if missing_probe:
        md_lines.append(f"- Missing mesh34 probe: {len(missing_probe)} ID(s)")
    if missing_304:
        md_lines.append(f"- Probe present but no @304 BodyFirst16: {len(missing_304)} ID(s)")

    md_lines += [
        "",
        "## Per-ID @304 / @212 BodyFirst16",
        "",
        "| ID | @304 BodyFirst16 | 022bc2 lead | C2 @2–5 | @304 role (c) | @212 BodyFirst16 (contrast) |",
        "|---|---|---:|---:|---|---|",
    ]
    for row in sorted(per_id, key=lambda r: r["Id"]):
        s304 = row["StreamAt304"]
        s212 = row.get("StreamAt212") or {}
        role = s304.get("Role", "")
        conf = s304.get("Confidence", "")
        role_cell = f"{role} (c={conf})" if conf not in ("", None) else role
        b212 = s212.get("BodyFirst16") or "-"
        md_lines.append(
            f"| {format_markdown_cell(row['Id'])} "
            f"| `{format_markdown_cell(s304.get('BodyFirst16', ''))}` "
            f"| {'yes' if row['HasPrefix022bc2'] else 'no'} "
            f"| {'yes' if row['C2InBytePositions2To5'] else 'no'} "
            f"| {format_markdown_cell(role_cell)} "
            f"| `{format_markdown_cell(b212)}` |"
        )
    if not per_id:
        md_lines.append("| (no processed rows) | - | - | - | - | - |")

    top4 = list(aggregates["Prefix4ByteCounts"].items())[:8]
    if top4:
        md_lines += ["", "## Top 4-byte @304 prefixes (frequency)", "", "| prefix | count |", "|---|---:|"]
        for prefix, count in top4:
            md_lines.append(f"| `{prefix}` | {count} |")

    md_lines += [
        "",
        "Generated for Phase 1 M1.2 per `docs/roadmap/project-roadmap.md`. "
        "All output candidate-only; no parser/export promotion.",
    ]
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print("\n=== Phase 1 M1.2 @304 Magic / Prefix Analysis ===")
    print(f"CandidateOnly: true | Processed IDs: {len(per_id)} / matrix targets: {len(target_ids)}")
    print(f"022bc2 lead count: {prefix_022bc2_count} | C2 @ bytes 2-5: {c2_pos_2_5_count}")
    print(
        f"Shared prefix bytes (4/8/16): "
        f"{shared_prefix['SharedPrefixBytes4']}/"
        f"{shared_prefix['SharedPrefixBytes8']}/"
        f"{shared_prefix['SharedPrefixBytes16']}"
    )
    print(f"JSON: {_repo_relative(json_path)}")
    print(f"MD:   {_repo_relative(md_path)}")

    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Report directory (default: {_repo_relative(DEFAULT_OUT)})",
    )
    args = parser.parse_args(argv)
    sys.path.insert(0, str(REPO_ROOT))
    try:
        phase1_m12_304_magic_analysis(args.out)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())