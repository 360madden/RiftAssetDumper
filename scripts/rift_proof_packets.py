#!/usr/bin/env python3
"""Proof packets — capture and validate runtime evidence packets.

A proof packet records that a live candidate address was successfully read back
with expected labels/sizes in a specific session. Packets are session-scoped
until they survive the two-restart rediscovery gate.

Usage:
    python scripts/rift_proof_packets.py \\
        --scan-result Exports/discovery-plan/stage5-live/live-memory-scan-*.json \\
        --pid 12345 \\
        --session-label "2026-07-09-run1" \\
        --out Exports/discovery-plan/stage5-live/proof-packets.json

Safety: Read-only. No process writes. All outputs under Exports/ (ignored).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "proof-packets/v1"


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def _packet_id(address: str, session_label: str, pid: int) -> str:
    """Deterministic packet ID from address + session + PID."""
    raw = f"{address}:{session_label}:{pid}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def build_proof_packet(
    address: str,
    region_base: str,
    snippet_hex: str,
    pattern_label: str,
    pid: int,
    session_label: str,
    score: int | None = None,
    asset_categories: list[str] | None = None,
    asset_names: list[str] | None = None,
) -> dict[str, Any]:
    """Build a single proof packet for a live candidate observation."""
    now = datetime.now(UTC).isoformat()
    packet_id = _packet_id(address, session_label, pid)

    return {
        "PacketId": packet_id,
        "SchemaVersion": SCHEMA_VERSION,
        "CreatedAt": now,
        "Address": address,
        "RegionBase": region_base,
        "SnippetHex": snippet_hex,
        "PatternLabel": pattern_label,
        "Pid": pid,
        "SessionLabel": session_label,
        "MachineHash": _machine_hash(),
        "Score": score,
        "AssetCategories": asset_categories or [],
        "AssetNames": asset_names or [],
        "ReadbackVerified": False,
        "RestartCount": 0,
        "Status": "candidate",
    }


def _machine_hash() -> str:
    """Stable machine identifier (hostname hash) — no PII stored."""
    hostname = os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "unknown"))
    return hashlib.sha256(hostname.encode()).hexdigest()[:12]


def build_packets_from_scan(
    scan_result: dict[str, Any],
    pid: int,
    session_label: str,
    scored: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build proof packets from a live scan result, optionally enriched with scores."""
    scored_map: dict[str, dict[str, Any]] = {}
    if scored:
        for c in scored.get("Candidates", []):
            scored_map[c["Address"]] = c

    packets: list[dict[str, Any]] = []
    scan_data = scan_result.get("ScanResult", scan_result)

    for pattern_row in scan_data.get("PatternResults", []):
        label = pattern_row.get("Label", "")
        for match in pattern_row.get("Matches", []):
            address = match.get("Address", "")
            sc = scored_map.get(address, {})

            packet = build_proof_packet(
                address=address,
                region_base=match.get("RegionBase", ""),
                snippet_hex=match.get("SnippetHex", ""),
                pattern_label=label,
                pid=pid,
                session_label=session_label,
                score=sc.get("TotalScore"),
                asset_categories=sc.get("AssetCategories", []),
                asset_names=sc.get("AssetNames", []),
            )
            packets.append(packet)

    return {
        "SchemaVersion": SCHEMA_VERSION,
        "SessionLabel": session_label,
        "Pid": pid,
        "MachineHash": _machine_hash(),
        "CreatedAt": datetime.now(UTC).isoformat(),
        "PacketCount": len(packets),
        "Packets": packets,
    }


def merge_packets(
    existing: dict[str, Any] | None,
    new_packets: dict[str, Any],
) -> dict[str, Any]:
    """Merge new proof packets with existing, preserving restart counts."""
    if existing is None:
        return new_packets

    existing_by_id: dict[str, dict[str, Any]] = {}
    for p in existing.get("Packets", []):
        existing_by_id[p["PacketId"]] = p

    merged = 0
    for p in new_packets.get("Packets", []):
        pid = p["PacketId"]
        if pid in existing_by_id:
            old = existing_by_id[pid]
            p["RestartCount"] = old.get("RestartCount", 0)
            p["ReadbackVerified"] = old.get("ReadbackVerified", False)
            p["Status"] = old.get("Status", "candidate")
            merged += 1
        existing_by_id[pid] = p

    result = dict(new_packets)
    result["Packets"] = list(existing_by_id.values())
    result["PacketCount"] = len(result["Packets"])
    result["MergedFromPrevious"] = merged
    return result


def write_proof_packets(packets: dict[str, Any], repo_root: Path, out_dir: Path | None = None) -> Path:
    """Write proof packets JSON."""
    if out_dir is None:
        out_dir = repo_root / "Exports" / "discovery-plan" / "stage5-live"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "proof-packets.json"
    json_path.write_text(json.dumps(packets, indent=2), encoding="utf-8")
    return json_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Capture proof packets from live scan results.")
    parser.add_argument(
        "--scan-result",
        type=Path,
        required=True,
        help="Path to live scan result JSON.",
    )
    parser.add_argument(
        "--pid",
        type=int,
        required=True,
        help="Target process PID.",
    )
    parser.add_argument(
        "--session-label",
        type=str,
        required=True,
        help="Label for this scan session (e.g. 2026-07-09-run1).",
    )
    parser.add_argument(
        "--scored",
        type=Path,
        default=None,
        help="Optional scored-candidates JSON for enrichment.",
    )
    parser.add_argument(
        "--existing",
        type=Path,
        default=None,
        help="Existing proof-packets.json to merge into.",
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

    scan_result = _load_json(args.scan_result)
    scored = _load_json(args.scored) if args.scored else None

    new_packets = build_packets_from_scan(scan_result, args.pid, args.session_label, scored)

    if args.existing and args.existing.exists():
        existing = _load_json(args.existing)
        new_packets = merge_packets(existing, new_packets)

    if args.list_json:
        print(json.dumps(new_packets, indent=2))
        return

    json_path = write_proof_packets(new_packets, REPO_ROOT, args.out)
    print(f"Wrote {new_packets['PacketCount']} proof packets to {json_path}")


if __name__ == "__main__":
    main()
