#!/usr/bin/env python3
"""Restart gate — validate that candidates survive the two-restart rediscovery gate.

Reads proof packets from multiple sessions and determines which candidates
have been rediscovered after restart(s). A candidate becomes "durable" only
when it has been observed in at least 2 independent sessions with different PIDs.

Usage:
    python scripts/rift_restart_gate.py \\
        --proof-packets Exports/discovery-plan/stage5-live/proof-packets.json \\
        --out Exports/discovery-plan/stage5-live/restart-gate-report.json

Safety: Read-only. No process attachment. All outputs under Exports/ (ignored).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "restart-gate/v1"

# Promotion thresholds
MIN_RESTART_COUNT = 2
MIN_UNIQUE_SESSIONS = 2
MIN_UNIQUE_PIDS = 2


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def _candidate_key(packet: dict[str, Any]) -> str:
    """Stable key for a candidate across sessions (pattern label + snippet)."""
    return f"{packet.get('PatternLabel', '')}:{packet.get('SnippetHex', '')}"


def _build_candidate_history(
    packets: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Group proof packets by candidate key, building a history across sessions."""
    history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in packets.get("Packets", []):
        key = _candidate_key(p)
        history[key].append(p)
    return dict(history)


def evaluate_gate(history: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Evaluate restart-gate status for each candidate.

    A candidate passes the gate when:
    - RestartCount >= 2 (observed in at least 2 sessions)
    - Unique session labels >= 2
    - Unique PIDs >= 2 (different process instances)
    """
    candidates: list[dict[str, Any]] = []

    for key, observations in history.items():
        unique_sessions = {o.get("SessionLabel", "") for o in observations}
        unique_pids = {o.get("Pid", 0) for o in observations}
        restart_count = max(o.get("RestartCount", 0) for o in observations)
        latest = max(observations, key=lambda o: o.get("CreatedAt", ""))

        # Determine gate status
        gate_pass = (
            restart_count >= MIN_RESTART_COUNT
            and len(unique_sessions) >= MIN_UNIQUE_SESSIONS
            and len(unique_pids) >= MIN_UNIQUE_PIDS
        )

        status = "durable" if gate_pass else "candidate"
        if gate_pass:
            # Check additional safety: must have score > 0 and asset categories
            score_val = latest.get("Score") or 0
            if score_val <= 0 and not latest.get("AssetCategories"):
                status = "needs-review"
                gate_pass = False

        candidates.append(
            {
                "CandidateKey": key,
                "Status": status,
                "GatePassed": gate_pass,
                "RestartCount": restart_count,
                "UniqueSessions": len(unique_sessions),
                "UniquePIDs": len(unique_pids),
                "SessionLabels": sorted(unique_sessions),
                "Pids": sorted(unique_pids),
                "ObservationCount": len(observations),
                "FirstSeen": min(o.get("CreatedAt", "") for o in observations),
                "LastSeen": latest.get("CreatedAt", ""),
                "Address": latest.get("Address", ""),
                "PatternLabel": latest.get("PatternLabel", ""),
                "Score": latest.get("Score") or 0,
                "AssetCategories": latest.get("AssetCategories", []),
                "AssetNames": latest.get("AssetNames", []),
            }
        )

    candidates.sort(key=lambda c: (not c["GatePassed"], -(c.get("Score") or 0)))

    durable = [c for c in candidates if c["Status"] == "durable"]
    needs_review = [c for c in candidates if c["Status"] == "needs-review"]
    candidates_remaining = [c for c in candidates if c["Status"] == "candidate"]

    return {
        "SchemaVersion": SCHEMA_VERSION,
        "EvaluatedAt": datetime.now(UTC).isoformat(),
        "TotalCandidates": len(candidates),
        "DurableCount": len(durable),
        "NeedsReviewCount": len(needs_review),
        "CandidateCount": len(candidates_remaining),
        "GateThresholds": {
            "MinRestartCount": MIN_RESTART_COUNT,
            "MinUniqueSessions": MIN_UNIQUE_SESSIONS,
            "MinUniquePIDs": MIN_UNIQUE_PIDS,
        },
        "Durable": durable,
        "NeedsReview": needs_review,
        "Candidates": candidates_remaining,
        "AllCandidates": candidates,
    }


def write_gate_report(report: dict[str, Any], repo_root: Path, out_dir: Path | None = None) -> tuple[Path, Path]:
    """Write restart-gate JSON and Markdown reports."""
    if out_dir is None:
        out_dir = repo_root / "Exports" / "discovery-plan" / "stage5-live"
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = out_dir / f"restart-gate-report-{ts}.json"
    md_path = out_dir / f"restart-gate-report-{ts}.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Restart gate report",
        "",
        f"SchemaVersion: `{report['SchemaVersion']}`",
        f"TotalCandidates: `{report['TotalCandidates']}`",
        f"Durable: `{report['DurableCount']}`",
        f"NeedsReview: `{report['NeedsReviewCount']}`",
        f"Candidates: `{report['CandidateCount']}`",
        "",
        "## Gate thresholds",
        "",
        f"- MinRestartCount: `{report['GateThresholds']['MinRestartCount']}`",
        f"- MinUniqueSessions: `{report['GateThresholds']['MinUniqueSessions']}`",
        f"- MinUniquePIDs: `{report['GateThresholds']['MinUniquePIDs']}`",
        "",
    ]

    if report["Durable"]:
        lines.extend(
            [
                "## Durable candidates (gate passed)",
                "",
                "| Address | Score | Restarts | Sessions | PIDs | Pattern | Categories |",
                "|---------|-------|----------|----------|------|---------|------------|",
            ]
        )
        for c in report["Durable"]:
            cats = ", ".join(c.get("AssetCategories", [])[:3]) or "—"
            lines.append(
                f"| `{c['Address']}` | {c.get('Score', '—')} "
                f"| {c['RestartCount']} | {c['UniqueSessions']} "
                f"| {c['UniquePIDs']} | `{c['PatternLabel']}` | {cats} |"
            )
        lines.append("")

    if report["NeedsReview"]:
        lines.extend(
            [
                "## Needs review (gate partial, no asset backing)",
                "",
                "| Address | Restarts | Sessions | PIDs | Pattern |",
                "|---------|----------|----------|------|---------|",
            ]
        )
        for c in report["NeedsReview"]:
            lines.append(
                f"| `{c['Address']}` | {c['RestartCount']} "
                f"| {c['UniqueSessions']} | {c['UniquePIDs']} "
                f"| `{c['PatternLabel']}` |"
            )
        lines.append("")

    if report["Candidates"]:
        lines.extend(
            [
                "## Candidates (not yet at gate threshold)",
                "",
            ]
        )
        for c in report["Candidates"][:20]:
            lines.append(
                f"- `{c['Address']}` — {c['RestartCount']} restarts, "
                f"{c['UniqueSessions']} sessions, `{c['PatternLabel']}`"
            )
        if len(report["Candidates"]) > 20:
            lines.append(f"- ... and {len(report['Candidates']) - 20} more")
        lines.append("")

    lines.extend(
        [
            "",
            "> Durable status requires two independent restarts with different PIDs. "
            "All addresses remain leads until promoted by guard review.",
            "",
        ]
    )

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate the two-restart rediscovery gate for proof packets.")
    parser.add_argument(
        "--proof-packets",
        type=Path,
        required=True,
        help="Path to proof-packets.json.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory (default: Exports/discovery-plan/stage5-live/).",
    )
    parser.add_argument(
        "--list-json",
        action="store_true",
        help="Emit machine-readable JSON to stdout.",
    )
    args = parser.parse_args(argv)

    packets = _load_json(args.proof_packets)
    history = _build_candidate_history(packets)
    report = evaluate_gate(history)

    if args.list_json:
        print(json.dumps(report, indent=2))
        return

    json_path, md_path = write_gate_report(report, REPO_ROOT, args.out)
    print(
        f"Gate evaluation: {report['DurableCount']} durable, "
        f"{report['NeedsReviewCount']} needs-review, "
        f"{report['CandidateCount']} candidates."
    )
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
