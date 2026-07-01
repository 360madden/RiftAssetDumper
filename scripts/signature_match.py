#!/usr/bin/env python3
"""Validate byte signatures from a binary-signature catalog against ``.text``.

Companion to ``scripts/modrm_scanner.py``. Reads a signature catalog
(such as ``Exports/binary-phase2/signature-candidates.json``), translates
each ``sig_hex`` string with ``??`` wildcards into a bytes regex, and
reports how many times each signature appears in a chosen ``.text``
buffer.

Flagship use case is verifying the 8 hand-extracted signatures in the
binary-signature-roadmap candidate catalog are each unique (appear
exactly once) in the live ``rift_x64.exe`` ``.text`` section.

Wildcard rules (mirror ``Exports/binary-phase2/signature-candidates.json``):
    * Space-separated hex digits in ``sig_hex`` are the literal bytes.
    * ``??`` is a wildcard that matches any byte (``re.DOTALL`` semantics
      not needed — byte-pattern only).
    * All other whitespace is collapsed to a single separator.

Algorithm:
    1. Parse sig_hex into byte anchors + wildcard runs.
    2. For each signature, compile a bytes regex via ``re.compile``.
    3. ``re.finditer`` over the .text buffer per signature.
    4. Emit a JSON report with per-sig count and uniqueness verdict.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.modrm_scanner import (  # noqa: E402
    SCHEMA_VERSION as SCANNER_SCHEMA,
)
from scripts.modrm_scanner import (  # noqa: E402
    read_text_section_bytes,
)

SCHEMA_VERSION = "signature-match-report/v1"
WILDCARD_TOKEN = "??"
HEX_BYTE_PATTERN = re.compile(r"^[0-9A-Fa-f]{2}$")


@dataclass
class SignatureResult:
    """Per-signature validation result."""

    name: str
    sig_hex: str
    signature_length: int
    wildcard_count: int
    match_count: int
    unique: bool
    first_match_offset: int | None = None
    first_match_rva: str | None = None


@dataclass
class SignatureMatchReport:
    catalog_path: str = ""
    binary_path: str = ""
    text_size_bytes: int = 0
    text_rva_base: str = "0x0"
    schema: str = SCHEMA_VERSION
    results: list[SignatureResult] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


def parse_signature(sig_hex: str) -> tuple[bytes, int, int]:
    """Parse a wildcarded sig_hex string into a compiled bytes regex pattern.

    Returns a tuple of (regex_bytes, signature_length_bytes, wildcard_count).
    """
    tokens = sig_hex.split()
    pattern_parts: list[bytes] = []
    wildcard_count = 0
    length = 0
    for token in tokens:
        if token == WILDCARD_TOKEN:
            pattern_parts.append(b".")
            wildcard_count += 1
        elif HEX_BYTE_PATTERN.match(token):
            pattern_parts.append(re.escape(bytes([int(token, 16)])))
        else:
            raise ValueError(f"Invalid sig_hex token: {token!r} (whole: {sig_hex!r})")
        length += 1
    return b"".join(pattern_parts), length, wildcard_count


def match_signature(text: bytes, sig_hex: str) -> tuple[int, int | None]:
    """Count occurrences of the signature in ``text``.

    Returns (count, first_offset). All matches must be byte-anchored —
    we don't allow patterns to slide relative to the buffer start.
    """
    pattern_bytes, _, _ = parse_signature(sig_hex)
    compiled = re.compile(pattern_bytes, flags=re.DOTALL)
    matches = list(compiled.finditer(text))
    first_offset = matches[0].start() if matches else None
    return len(matches), first_offset


def validate_catalog(
    catalog: Mapping[str, Any],
    text: bytes,
    *,
    text_rva_base: int,
) -> SignatureMatchReport:
    """Validate every candidate signature against ``text`` and emit a report."""
    candidates = catalog.get("candidates", [])
    if not isinstance(candidates, list):
        raise ValueError("catalog must have a 'candidates' list")
    results: list[SignatureResult] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            continue
        sig_hex = str(candidate.get("sig_hex", ""))
        name = str(candidate.get("name") or candidate.get("cluster") or f"candidate_{index}")
        _, length, wc = parse_signature(sig_hex)
        count, first_offset = match_signature(text, sig_hex)
        first_rva = f"0x{text_rva_base + first_offset:X}" if first_offset is not None else None
        results.append(
            SignatureResult(
                name=name,
                sig_hex=sig_hex,
                signature_length=length,
                wildcard_count=wc,
                match_count=count,
                unique=(count == 1),
                first_match_offset=first_offset,
                first_match_rva=first_rva,
            )
        )
    unique_count = sum(1 for r in results if r.unique)
    return SignatureMatchReport(
        catalog_path=str(catalog.get("path", "?")),
        text_size_bytes=len(text),
        text_rva_base=f"0x{text_rva_base:X}",
        results=results,
        summary={
            "total": len(results),
            "unique": unique_count,
            "non_unique": len(results) - unique_count,
        },
    )


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def report_to_dict(report: SignatureMatchReport) -> dict[str, Any]:
    return {
        "schema": report.schema,
        "catalog_path": report.catalog_path,
        "binary_path": report.binary_path,
        "text_size_bytes": report.text_size_bytes,
        "text_rva_base": report.text_rva_base,
        "summary": report.summary,
        "results": [
            {
                "name": r.name,
                "sig_hex": r.sig_hex,
                "signature_length_bytes": r.signature_length,
                "wildcard_count": r.wildcard_count,
                "match_count": r.match_count,
                "unique": r.unique,
                "first_match_offset_in_text": r.first_match_offset,
                "first_match_rva": r.first_match_rva,
            }
            for r in report.results
        ],
        "interpretation": (
            'Byte-signature uniqueness check. "unique = True" means the '
            "wildcarded signature appears exactly once in the .text buffer "
            f"(scanned with the {SCANNER_SCHEMA} scanner PE parser)."
        ),
        "candidate_only": True,
    }


def report_to_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Signature match report",
        "",
        f"Schema: `{report.get('schema')}`",
        f"Catalog: `{report.get('catalog_path')}`",
        f"Binary: `{report.get('binary_path')}`",
        f"Text RVA base: `{report.get('text_rva_base')}`",
        f"Text size: `{report.get('text_size_bytes'):,}` bytes",
        "",
        "## Summary",
        "",
        f"- Total signatures: **{report['summary']['total']}**",
        f"- Unique (1 match): **{report['summary']['unique']}**",
        f"- Non-unique (>1 matches): **{report['summary']['non_unique']}**",
        "",
        "## Per-signature results",
        "",
        "| Name | Sig length | Wildcards | Matches | Unique | First RVA | Sig |",
        "|---|---:|---:|---:|:---:|---|---|",
    ]
    for r in report["results"]:
        first_rva = r["first_match_rva"] if r["first_match_rva"] else "-"
        sig_label = r["sig_hex"][:64] + ("..." if len(r["sig_hex"]) > 64 else "")
        lines.append(
            f"| {r['name']} | {r['signature_length_bytes']} | "
            f"{r['wildcard_count']} | {r['match_count']} | "
            f"{'YES' if r['unique'] else 'NO'} | {first_rva} | "
            f"`{sig_label}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            str(report.get("interpretation", "Read-only validation report.")),
        ]
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--catalog",
        type=Path,
        default=REPO_ROOT / "Exports" / "binary-phase2" / "signature-candidates.json",
        help="Path to signature-candidates.json (or any matching catalog)",
    )
    parser.add_argument(
        "--binary",
        type=str,
        default=r"C:/Program Files (x86)/Glyph/Games/RIFT/Live/rift_x64.exe",
        help="Path to the PE binary (default: rift_x64.exe in RIFT Live install)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "Exports" / "binary-phase2",
        help="Output directory (default: Exports/binary-phase2)",
    )
    args = parser.parse_args(argv)

    catalog_path = args.catalog.resolve()
    if not catalog_path.exists():
        print(f"ERROR: catalog not found: {catalog_path}", file=sys.stderr)
        return 1
    binary_path = Path(args.binary).resolve()
    if not binary_path.exists():
        print(f"ERROR: binary not found: {binary_path}", file=sys.stderr)
        return 1

    catalog: dict[str, Any] = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog.setdefault("path", str(catalog_path))
    binary_data = binary_path.read_bytes()
    text_bytes, text_section = read_text_section_bytes(binary_data)
    print(f"==> Catalog: {catalog_path}")
    print(f"==> Binary: {binary_path} ({binary_path.stat().st_size:,} bytes)")
    print(f"==> .text:  {text_section.raw_size:,} bytes at RVA 0x{text_section.virtual_address:X}")

    report = validate_catalog(catalog, text_bytes, text_rva_base=text_section.virtual_address)
    report.binary_path = str(binary_path)
    report.catalog_path = str(catalog_path)

    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / "signature-match-report.json"
    md_path = args.out / "signature-match-report.md"
    json_path.write_text(json.dumps(report_to_dict(report), indent=2), encoding="utf-8")
    md_path.write_text(report_to_markdown(report_to_dict(report)), encoding="utf-8")
    print(f"==> JSON:   {json_path}")
    print(f"==> MD:     {md_path}")
    print(f"==> Summary: {report.summary['unique']}/{report.summary['total']} unique")
    if report.summary["non_unique"] > 0:
        print(
            f"WARNING: {report.summary['non_unique']} non-unique signatures "
            f"(expected in wilderness but report flags them)",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
