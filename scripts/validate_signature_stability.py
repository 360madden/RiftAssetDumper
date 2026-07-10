#!/usr/bin/env python3
"""Validate signature stability by testing wildcard aggressiveness.

For each signature, progressively wildcard bytes to find the stability margin.
"""

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT = REPO_ROOT / "Exports" / "binary-phase2" / "signature-candidates.json"
BINARY = REPO_ROOT / "Exports" / "rift_x64.exe"
OUTPUT = REPO_ROOT / "Exports" / "binary-phase4" / "signature-stability-report.json"


def load_binary(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def parse_sig_hex(sig_hex: str) -> list[int | None]:
    """Parse signature hex string into list of bytes (None for wildcards)."""
    result = []
    for part in sig_hex.split():
        if part == "??":
            result.append(None)
        else:
            result.append(int(part, 16))
    return result


def find_matches(binary: bytes, sig_bytes: list[int | None]) -> list[int]:
    """Find all matches of a wildcarded signature in binary."""
    matches = []
    sig_len = len(sig_bytes)
    for i in range(len(binary) - sig_len + 1):
        match = True
        for j, sb in enumerate(sig_bytes):
            if sb is not None and binary[i + j] != sb:
                match = False
                break
        if match:
            matches.append(i)
    return matches


def test_stability_margin(binary: bytes, sig_hex: str, max_wildcard_additions: int = 10) -> dict[str, Any]:
    """Test how many additional wildcards can be added before losing uniqueness."""
    base_sig = parse_sig_hex(sig_hex)
    base_matches = find_matches(binary, base_sig)

    margin_test_results: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "base_sig_hex": sig_hex,
        "base_wildcard_count": sum(1 for b in base_sig if b is None),
        "base_match_count": len(base_matches),
        "base_unique": len(base_matches) == 1,
        "stability_margin": 0,
        "margin_test_results": margin_test_results,
    }

    if len(base_matches) != 1:
        result["note"] = "Base signature is not unique"
        return result

    # Test adding wildcards one at a time at different positions
    for num_added in range(1, max_wildcard_additions + 1):
        # Try wildcarding the first N non-wildcard bytes after the existing wildcards
        test_sig = list(base_sig)
        added = 0
        for k in range(len(test_sig)):
            if test_sig[k] is not None and added < num_added:
                test_sig[k] = None
                added += 1

        matches = find_matches(binary, test_sig)
        margin_test_results.append(
            {
                "additional_wildcards": num_added,
                "total_wildcards": sum(1 for b in test_sig if b is None),
                "match_count": len(matches),
                "still_unique": len(matches) == 1,
            }
        )

        if len(matches) > 1:
            result["stability_margin"] = num_added - 1
            break
    else:
        result["stability_margin"] = max_wildcard_additions

    return result


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with open(INPUT) as f:
        candidates = json.load(f)

    binary = load_binary(BINARY)
    print(f"Loaded binary: {len(binary)} bytes")
    print(f"Testing {len(candidates['candidates'])} signatures\n")

    signatures: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "SchemaVersion": "signature-stability-report/v1",
        "Generated": "2026-07-07",
        "Binary": "rift_x64.exe",
        "BinarySize": len(binary),
        "Methodology": "Progressive wildcard addition — add wildcards one at a time until uniqueness is lost",
        "Signatures": signatures,
    }

    for cand in candidates["candidates"]:
        name = cand.get("name") or cand.get("cluster", "unknown")
        sig_hex = cand["sig_hex"]
        print(f"Testing: {name} ({sig_hex[:40]}...)")

        result = test_stability_margin(binary, sig_hex)
        result["anchor_name"] = name
        result["stability_tier"] = cand.get("stability_tier", "unknown")
        result["entry_va"] = cand.get("entry_va")

        signatures.append(result)

        print(
            f"  Base wildcards: {result['base_wildcard_count']}, "
            f"Matches: {result['base_match_count']}, "
            f"Stability margin: +{result['stability_margin']} wildcards"
        )

    # Summary
    unique_count = sum(1 for s in signatures if s["base_unique"])
    avg_margin = sum(s["stability_margin"] for s in signatures) / len(signatures)

    report["Summary"] = {
        "total_signatures": len(signatures),
        "unique_at_base": unique_count,
        "average_stability_margin": round(avg_margin, 1),
        "all_unique": unique_count == len(signatures),
    }

    with open(OUTPUT, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nWrote {OUTPUT}")
    print(f"Summary: {unique_count}/{len(report['Signatures'])} unique, avg margin +{avg_margin:.1f} wildcards")


if __name__ == "__main__":
    main()
