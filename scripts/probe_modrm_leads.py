#!/usr/bin/env python3
"""probe-modrm-leads: bridge static ModRM analysis to live RIFT process memory.

Loads a ``modrm-memory-access-scan/v1`` JSON report (from ``scripts/modrm_scanner.py``),
extracts wildcarded instruction signatures from the top clusters, and either:

* ``--list-json`` — prints a dry-run plan showing which clusters would be probed
  and their player-coordinate likelihood scores (no process opened).
* ``--execute-live-read`` — scans the live ``rift_x64.exe`` process for those
  signatures, confirms which clusters are present in memory, and writes
  timestamped JSON + Markdown reports under ``Exports/discovery-plan/stage5-live/``.

Safety: read-only by construction — same gates as ``scan-live-memory``.
Requires ``--experimental-live``, ``--confirm-live-read``, and an explicit ``--pid``
for live execution. Output remains under ignored ``Exports/discovery-plan/stage5-live/``.

Usage::

    python scripts/probe_modrm_leads.py --list-json
    python scripts/probe_modrm_leads.py --modrm-scan Exports/binary-phase1/modrm-memory-access-scan.json --list-json
    python scripts/probe_modrm_leads.py --execute-live-read --experimental-live --confirm-live-read --pid 12345
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.live_memory_scanner import (  # noqa: E402
    DEFAULT_MAX_MATCHES,
    DEFAULT_MAX_REGIONS,
    DEFAULT_MAX_SCAN_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    WildcardSignature,
    WindowsReadOnlyProcessReader,
    build_probe_modrm_leads_plan,
    parse_wildcard_hex,
    run_probe_modrm_leads,
    write_probe_modrm_leads_reports,
)
from scripts.rift_workflow_utils import generated_output_guard  # noqa: E402

DEFAULT_MODRM_SCAN_PATH = "Exports/binary-phase1/modrm-memory-access-scan.json"


def _print_plan(plan: dict) -> None:
    """Print a human-readable dry-run summary."""
    print("--- probe-modrm-leads dry-run")
    print(f"ModRM scan: {plan['ModRMScanPath']}")
    print(f"Clusters to probe: {plan['ClustersExtracted']}")
    print(f"Live read execution: {str(plan['ExecuteLiveRead']).lower()}")
    print(f"Execution allowed: {str(plan['ExecutionAllowed']).lower()}")
    if plan["RefusalReasons"]:
        print(f"Refusal reasons: {', '.join(plan['RefusalReasons'])}")
    print()
    print(f"{'Rank':>4} {'Score':>6} {'Hits':>4} {'RVA':>12} {'Base registers'}")
    print(f"{'-' * 4} {'-' * 6} {'-' * 4} {'-' * 12} {'-' * 30}")
    for c in plan.get("CandidateClusters", []):
        bases = ", ".join(f"{k}={v}" for k, v in c["BaseRegisterCounts"].items())
        print(f"{c['Rank']:4} {c['PlayerCoordinateScore']:6.4f} {c['HitCount']:4} {c['FirstRVA']:>12} {bases}")
    print()
    print(f"Next action: {plan['NextAction']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--modrm-scan",
        type=Path,
        default=REPO_ROOT / DEFAULT_MODRM_SCAN_PATH,
        help=f"Path to modrm-memory-access-scan JSON (default: {DEFAULT_MODRM_SCAN_PATH})",
    )
    parser.add_argument(
        "--top-clusters",
        type=int,
        default=8,
        help="Number of top clusters to probe (default 8)",
    )
    parser.add_argument("--pid", type=int, default=0, help="Target process PID (required for live read)")
    parser.add_argument(
        "--process-name",
        type=str,
        default="rift_x64.exe",
        help="Target process name (default: rift_x64.exe)",
    )
    parser.add_argument(
        "--list-json",
        action="store_true",
        help="Emit machine-readable dry-run plan JSON to stdout",
    )
    parser.add_argument(
        "--execute-live-read",
        action="store_true",
        help="Actually open/read the target process; requires explicit live safety flags",
    )
    parser.add_argument(
        "--experimental-live",
        action="store_true",
        help="Acknowledge experimental live read mode",
    )
    parser.add_argument(
        "--confirm-live-read",
        action="store_true",
        help="Second explicit confirmation for live process attach",
    )
    parser.add_argument(
        "--max-scan-bytes",
        type=int,
        default=DEFAULT_MAX_SCAN_BYTES,
        help=f"Max bytes to scan (default {DEFAULT_MAX_SCAN_BYTES})",
    )
    parser.add_argument(
        "--max-matches",
        type=int,
        default=DEFAULT_MAX_MATCHES,
        help=f"Max matches per signature (default {DEFAULT_MAX_MATCHES})",
    )
    parser.add_argument(
        "--max-regions",
        type=int,
        default=DEFAULT_MAX_REGIONS,
        help=f"Max regions to scan (default {DEFAULT_MAX_REGIONS})",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Scan timeout (default {DEFAULT_TIMEOUT_SECONDS})",
    )
    args = parser.parse_args(argv)

    # Validate modrm scan exists
    modrm_path = args.modrm_scan.resolve()
    if not modrm_path.exists():
        print(f"ERROR: modrm scan not found: {modrm_path}", file=sys.stderr)
        print(f"  Run: python scripts/modrm_scanner.py --top-clusters {args.top_clusters}", file=sys.stderr)
        return 1

    # Build the plan
    try:
        plan = build_probe_modrm_leads_plan(
            repo_root=REPO_ROOT,
            modrm_scan_path=str(args.modrm_scan.relative_to(REPO_ROOT))
            if args.modrm_scan.is_relative_to(REPO_ROOT)
            else str(args.modrm_scan),
            pid=args.pid,
            process_name=args.process_name,
            execute_live_read=args.execute_live_read,
            experimental_live=args.experimental_live,
            confirm_live_read=args.confirm_live_read,
            max_scan_bytes=args.max_scan_bytes,
            max_matches=args.max_matches,
            max_regions=args.max_regions,
            timeout_seconds=args.timeout_seconds,
            top_clusters=args.top_clusters,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.list_json:
        print(json.dumps(plan, indent=2))
        return 0

    _print_plan(plan)

    if not args.execute_live_read:
        print("probe-modrm-leads dry-run passed: no process was opened.")
        return 0

    if not plan["ExecutionAllowed"]:
        print("ERROR: live memory read refused by safety gates.", file=sys.stderr)
        return 1

    generated_output_guard()

    # Build wildcard signatures from the plan
    signatures: list[WildcardSignature] = []
    for c in plan.get("CandidateClusters", []):
        try:
            sig = parse_wildcard_hex(c["Label"], c["SigHex"])
            signatures.append(sig)
        except ValueError as exc:
            print(f"WARNING: skipping cluster {c['Label']}: {exc}", file=sys.stderr)

    if not signatures:
        print("ERROR: no valid signatures to probe", file=sys.stderr)
        return 1

    # Execute live scan
    try:
        with WindowsReadOnlyProcessReader(args.pid) as reader:
            result = run_probe_modrm_leads(plan, reader, signatures)
    except Exception as exc:
        print(f"ERROR: probe-modrm-leads live scan failed: {exc}", file=sys.stderr)
        return 1

    json_path, md_path = write_probe_modrm_leads_reports(result, REPO_ROOT)
    print(f"probe-modrm-leads wrote JSON: {json_path}")
    print(f"probe-modrm-leads wrote Markdown: {md_path}")
    print(f"Clusters confirmed: {result.get('ClustersConfirmed', 0)}/{result.get('ClustersProbed', 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
