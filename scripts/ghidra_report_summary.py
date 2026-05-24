#!/usr/bin/env python3
"""Summarize Ghidra FunctionSiteSurvey JSON reports.

The JSON reports are intentionally generated under ignored Exports/ paths and
can be large because they include decompiler output. This helper creates a
small reviewable Markdown summary without making the static-analysis evidence
look like parser truth.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

USER_PROFILE_PATH_RE = re.compile(r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s\"']+")


def redact_user_profile_paths(value: str) -> str:
    """Replace Windows user-profile roots with a stable placeholder."""
    return USER_PROFILE_PATH_RE.sub("%USERPROFILE%", value)


def markdown_cell(value: Any) -> str:
    """Format a safe one-line Markdown table cell."""
    if value is None:
        return "-"
    text = redact_user_profile_paths(str(value)).replace("\r", " ").replace("\n", " ").strip()
    if not text:
        return "-"
    return text.replace("|", "\\|")


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _decompile_lines(report: Mapping[str, Any]) -> list[str]:
    decompile = _as_mapping(report.get("decompile"))
    c_text = decompile.get("c")
    if not isinstance(c_text, str):
        return []
    return redact_user_profile_paths(c_text).splitlines()


def _append_key_value_table(lines: list[str], rows: Iterable[tuple[str, Any]]) -> None:
    lines.extend(["| Field | Value |", "|---|---|"])
    for key, value in rows:
        lines.append(f"| {markdown_cell(key)} | {markdown_cell(value)} |")


def _append_reference_table(
    lines: list[str],
    title: str,
    rows: Sequence[Any],
    columns: Sequence[tuple[str, str]],
    max_items: int,
) -> None:
    lines.extend(["", f"## {title}", ""])
    if not rows:
        lines.append("None recorded.")
        return

    header = "| " + " | ".join(label for label, _ in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    lines.extend([header, separator])
    for row_value in rows[:max_items]:
        row = _as_mapping(row_value)
        cells = [markdown_cell(row.get(key)) for _, key in columns]
        lines.append("| " + " | ".join(cells) + " |")

    if len(rows) > max_items:
        lines.append("")
        lines.append(f"_Showing {max_items} of {len(rows)} rows._")


def _matching_decompile_lines(lines: Sequence[str], terms: Sequence[str], max_matches: int) -> list[tuple[int, str]]:
    if not terms or not lines:
        return []
    lowered_terms = [term.lower() for term in terms if term.strip()]
    if not lowered_terms:
        return []

    matches: list[tuple[int, str]] = []
    for line_number, line in enumerate(lines, start=1):
        lowered_line = line.lower()
        if any(term in lowered_line for term in lowered_terms):
            matches.append((line_number, line.rstrip()))
            if len(matches) >= max_matches:
                break
    return matches


def summarize_report(
    report: Mapping[str, Any],
    *,
    terms: Sequence[str] = (),
    max_items: int = 8,
    max_matches: int = 12,
) -> str:
    """Return a compact Markdown summary for a FunctionSiteSurvey report."""
    function = report.get("function")
    function_map = _as_mapping(function)
    callers = _as_list(report.get("callers"))
    calls = _as_list(report.get("callsFromFunction"))
    data_refs = _as_list(report.get("dataRefsFromFunction"))
    instructions = _as_list(report.get("functionInstructions"))
    near_target = _as_list(report.get("instructionsNearTarget"))
    decompile = _as_mapping(report.get("decompile"))
    c_lines = _decompile_lines(report)

    title_target = report.get("targetAddress", "unknown")
    function_name = function_map.get("name") or "no containing function"
    lines = [f"# Ghidra FunctionSiteSurvey summary - {markdown_cell(title_target)}", ""]

    _append_key_value_table(
        lines,
        [
            ("Program", report.get("programName")),
            ("Image base", report.get("imageBase")),
            ("Target address", report.get("targetAddress")),
            ("Function", function_name),
            ("Entry", function_map.get("entry")),
            ("Signature", function_map.get("signature")),
            ("Body", _format_body(function_map)),
            ("Parameter count", function_map.get("parameterCount")),
            ("Return type", function_map.get("returnType")),
            ("Instructions near target", len(near_target)),
            ("Function instructions captured", len(instructions)),
            ("Caller refs captured", len(callers)),
            ("Call refs from function captured", len(calls)),
            ("Data refs from function captured", len(data_refs)),
            ("Decompile completed", decompile.get("completed")),
            ("Decompile error", decompile.get("errorMessage")),
        ],
    )

    if function is None:
        lines.extend(["", "No containing function was found for the target address."])
        return "\n".join(lines) + "\n"

    _append_reference_table(
        lines,
        "Callers / refs to function entry",
        callers,
        [
            ("From", "from"),
            ("Type", "type"),
            ("Caller", "caller"),
            ("Caller entry", "callerEntry"),
        ],
        max_items,
    )
    _append_reference_table(
        lines,
        "Calls from function",
        calls,
        [
            ("From", "from"),
            ("To", "to"),
            ("Type", "type"),
            ("Callee", "callee"),
            ("Callee entry", "calleeEntry"),
        ],
        max_items,
    )
    _append_reference_table(
        lines,
        "Data refs from function",
        data_refs,
        [
            ("From", "from"),
            ("To", "to"),
            ("Type", "type"),
        ],
        max_items,
    )

    lines.extend(["", "## Decompile matches", ""])
    matches = _matching_decompile_lines(c_lines, terms, max_matches)
    if terms:
        lines.append(f"Terms: {', '.join(markdown_cell(term) for term in terms)}")
        lines.append("")
    if matches:
        for line_number, text in matches:
            lines.append(f"- L{line_number}: `{markdown_cell(text)}`")
        if len(matches) == max_matches:
            lines.append(f"- _Stopped after {max_matches} matches._")
    elif terms:
        lines.append("No matching decompile lines found.")
    elif c_lines:
        lines.append("No terms supplied. Use `--ghidra-summary-term` to extract targeted decompile lines.")
    else:
        lines.append("No decompiler C text captured.")

    lines.extend(
        [
            "",
            "## Interpretation guard",
            "",
            "This is static Ghidra evidence only. Do not promote parser behavior, export readiness, or runtime truth from this summary without byte-level parser tests/proof guards.",
        ]
    )
    return "\n".join(lines) + "\n"


def _format_body(function: Mapping[str, Any]) -> str:
    body_min = function.get("bodyMin")
    body_max = function.get("bodyMax")
    body_num = function.get("bodyNumAddresses")
    if body_min is None and body_max is None:
        return "-"
    return f"{body_min}..{body_max} ({body_num} addresses)"


def load_report(path: str | Path) -> Mapping[str, Any]:
    """Load a FunctionSiteSurvey JSON report."""
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, Mapping):
        raise ValueError(f"Expected a JSON object report in {path}")
    return data


def summarize_file(
    input_path: str | Path,
    *,
    output_path: str | Path | None = None,
    terms: Sequence[str] = (),
    max_items: int = 8,
    max_matches: int = 12,
) -> str:
    """Summarize a report file and optionally write Markdown to disk."""
    report = load_report(input_path)
    markdown = summarize_report(report, terms=terms, max_items=max_items, max_matches=max_matches)
    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown, encoding="utf-8")
    return markdown


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize a Ghidra FunctionSiteSurvey JSON report.")
    parser.add_argument("report", help="FunctionSiteSurvey JSON report path")
    parser.add_argument("--out", default="", help="Optional Markdown output path")
    parser.add_argument("--term", action="append", default=[], help="Decompile term to show matching lines; repeatable")
    parser.add_argument("--max-items", type=int, default=8, help="Max rows per reference table (default: 8)")
    parser.add_argument("--max-matches", type=int, default=12, help="Max decompile matches (default: 12)")
    args = parser.parse_args(argv)

    markdown = summarize_file(
        args.report,
        output_path=args.out or None,
        terms=args.term,
        max_items=args.max_items,
        max_matches=args.max_matches,
    )
    if args.out:
        print(f"Wrote Ghidra summary: {Path(args.out)}")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
