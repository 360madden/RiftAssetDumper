#!/usr/bin/env python3
"""Ported utility helpers from Invoke-RiftAssetWorkflow.ps1.

These functions are the Python equivalents of the PowerShell utility layer.
The .NET RiftAssetDumper remains the parser/source of truth; this module only
handles JSON access, formatting, guard assertions, and subprocess orchestration.

Functions are organized mirroring the PowerShell originals so cross-reference
stays low-friction.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Project root resolution (mirrors rift_asset_discovery_matrix.py convention)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]


# ============================================================================
# JSON access helpers (Get-JsonValueOrDash, Get-JsonValueOrNull, etc.)
# ============================================================================

def json_value_or_dash(obj: Any, key: str) -> Any:  # noqa: ANN401 - mirror PS flexibility
    """Safe JSON property access returning '-' when missing or None.

    Mirrors: Get-JsonValueOrDash
    """
    if obj is None:
        return "-"
    if not isinstance(obj, dict):
        return "-"
    value = obj.get(key)
    if value is None:
        return "-"
    return value


def json_value_or_none(obj: Any, key: str) -> Any:  # noqa: ANN401 - mirror PS flexibility
    """Safe JSON property access returning None when missing.

    Mirrors: Get-JsonValueOrNull
    """
    if obj is None:
        return None
    if not isinstance(obj, dict):
        return None
    return obj.get(key)


def json_double_or_none(obj: Any, key: str) -> float | None:
    """Safe floating-point access from a JSON property.

    Mirrors: Get-JsonDoubleOrNull
    """
    raw = json_value_or_none(obj, key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def measure_sum_or_zero(items: list[Any], key: str) -> float:
    """Sum a numeric property across objects; return 0.0 if absent/non-numeric.

    Mirrors: Get-MeasureSumOrZero
    """
    total = 0.0
    for item in items:
        value = json_double_or_none(item, key)
        if value is not None:
            total += value
    return total


def json_array_count_or_dash(obj: Any, key: str) -> str:
    """Return array count as string, or '-' when missing/empty.

    Mirrors: Get-JsonArrayCountOrDash
    """
    value = json_value_or_none(obj, key)
    if value is None:
        return "-"
    if isinstance(value, list):
        return str(len(value))
    return "-"


# ============================================================================
# Required / assertive JSON accessors
# ============================================================================

def required_json_value(obj: Any, key: str, context: str) -> Any:  # noqa: ANN401
    """Extract a required property, raising on absence.

    Mirrors: Get-RequiredJsonValue
    """
    if obj is None or not isinstance(obj, dict):
        raise ValueError(
            f"AttributeExtraProofGuard failed: missing {key} on {context}."
        )
    value = obj.get(key)
    if value is None:
        raise ValueError(
            f"AttributeExtraProofGuard failed: missing {key} on {context}."
        )
    return value


def required_json_number(obj: Any, key: str, context: str) -> float:
    """Extract a required numeric property.

    Rejects booleans (Python float(True)==1.0 would silently accept them).

    Mirrors: Get-RequiredJsonNumber
    """
    value = required_json_value(obj, key, context)
    if isinstance(value, bool):
        raise ValueError(
            f"AttributeExtraProofGuard failed: {key} on {context} is boolean, not numeric: {value}"
        )
    try:
        return float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"AttributeExtraProofGuard failed: {key} on {context} is not numeric: {value}"
        ) from exc


def required_json_integer(obj: Any, key: str, context: str) -> int:
    """Extract a required integer property.

    Inherits boolean rejection from required_json_number.

    Mirrors: Get-RequiredJsonInteger
    """
    value = required_json_number(obj, key, context)
    return int(value)


def required_json_boolean(obj: Any, key: str, context: str) -> bool:
    """Extract a required boolean property, rejecting non-boolean JSON values.

    Python bool('false') == True would silently accept strings,
    so we explicitly reject anything that is not a Python bool.

    Mirrors: [bool]::Parse in PowerShell (which rejects non-boolean strings).
    """
    value = required_json_value(obj, key, context)
    if not isinstance(value, bool):
        raise ValueError(
            f"AttributeExtraProofGuard failed: {key} on {context} is not boolean: {type(value).__name__} {value!r}"
        )
    return value


def usage_access_guard_integer(obj: Any, key: str, context: str) -> int:
    """Extract a required integer for UsageAccess guard assertion.

    Mirrors: Get-UsageAccessGuardInteger
    """
    if obj is None or not isinstance(obj, dict):
        raise ValueError(
            f"UsageAccessCorrelationGuard failed: {context} is missing {key}."
        )
    raw = obj.get(key)
    if raw is None:
        raise ValueError(
            f"UsageAccessCorrelationGuard failed: {context} is missing {key}."
        )
    try:
        return int(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"UsageAccessCorrelationGuard failed: {key} on {context} is not an integer: {raw}"
        ) from exc


# ============================================================================
# Guard condition assertions
# ============================================================================

def assert_proof_guard(condition: bool, message: str) -> None:
    """Raise AttributeExtraProofGuard on false condition.

    Note: condition must be a pre-validated bool; callers should use
    required_json_boolean() for JSON boolean fields before passing here.

    Mirrors: Assert-ProofGuardCondition
    """
    if not condition:
        raise ValueError(f"AttributeExtraProofGuard failed: {message}")


def assert_usage_access_guard(condition: bool, message: str) -> None:
    """Raise UsageAccessCorrelationGuard on false condition.

    Mirrors: Assert-UsageAccessGuardCondition
    """
    if not condition:
        raise ValueError(f"UsageAccessCorrelationGuard failed: {message}")


# ============================================================================
# Generated-output path guard
# ============================================================================

_GENERATED_PATH_PATTERNS = re.compile(
    r"^(Source|Extracted|Exports)/"
    r"|(^|/)(bin|obj|__pycache__)/"
    r"|\.pyc$"
)


def is_generated_output_path(path: str) -> bool:
    """Return True if path matches generated/copy/build output patterns.

    Patterns: Source/, Extracted/, Exports/, bin/, obj/, __pycache__/, .pyc

    Mirrors: Test-GeneratedOutputPath
    """
    if not path or not path.strip():
        return False
    normalized = path.replace("\\", "/")
    return bool(_GENERATED_PATH_PATTERNS.search(normalized))


def generated_output_guard(repo_root: Path | None = None) -> None:
    """Raise if any generated/built/copied paths are tracked or staged in git.

    Mirrors: Invoke-GeneratedOutputGuard
    """
    if repo_root is None:
        repo_root = REPO_ROOT

    completed = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files"],
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"GeneratedOutputGuard failed: git ls-files exited with {completed.returncode}."
        )
    tracked = completed.stdout.splitlines()

    completed = subprocess.run(
        [
            "git", "-C", str(repo_root),
            "diff", "--cached", "--name-only", "--diff-filter=ACMR",
        ],
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"GeneratedOutputGuard failed: git diff --cached exited with {completed.returncode}."
        )
    staged = completed.stdout.splitlines()

    tracked_generated = [p for p in tracked if is_generated_output_path(p)]
    staged_generated = [p for p in staged if is_generated_output_path(p)]

    if tracked_generated:
        print("Tracked generated/copy/build output paths:", file=sys.stderr)
        for path in tracked_generated[:40]:
            print(f"  {path}", file=sys.stderr)
        raise RuntimeError(
            f"GeneratedOutputGuard failed: tracked generated/copy/build output paths found ({len(tracked_generated)})."
        )

    if staged_generated:
        print("Staged generated/copy/build output paths:", file=sys.stderr)
        for path in staged_generated[:40]:
            print(f"  {path}", file=sys.stderr)
        raise RuntimeError(
            f"GeneratedOutputGuard failed: staged generated/copy/build output paths found ({len(staged_generated)})."
        )

    print(f"\n--- GeneratedOutputGuard")
    print(f"Tracked generated/copy/build output paths: {len(tracked_generated)}")
    print(f"Staged generated/copy/build output paths: {len(staged_generated)}")
    print(
        "GeneratedOutputGuard passed: Source/, Extracted/, Exports/, bin/, obj/, "
        "__pycache__, and .pyc are not tracked or staged."
    )


# ============================================================================
# Subprocess helper (Invoke-Checked)
# ============================================================================

def checked_run(label: str, args: list[str], cwd: Path | None = None) -> None:
    """Run a dotnet command, stream output, and raise on non-zero exit.

    Mirrors: Invoke-Checked (streams output live like PowerShell's & dotnet @Args).
    """
    print(f"\n==> {label}")
    cmd_str = "dotnet " + " ".join(args)
    print(cmd_str)
    result = subprocess.run(
        ["dotnet", *args],
        cwd=str(cwd) if cwd else None,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Step failed: {label} (exit {result.returncode})")


# ============================================================================
# Formatting helpers
# ============================================================================

def format_markdown_cell(value: Any) -> str:  # noqa: ANN401 - stringify anything
    """Escape pipes and return '-' for empty values for Markdown table cells.

    Mirrors: Format-WorkflowMarkdownCell
    """
    if value is None:
        return "-"
    text = str(value).strip()
    if not text:
        return "-"
    return text.replace("|", "\\|")


def top_text(
    items: list[Any],
    formatter: callable,  # type: ignore[type-arg]
    take: int = 5,
) -> str:
    """Apply formatter to first `take` items, join with ' | '.

    Mirrors: Get-TopText (does NOT filter nulls — formatter receives them).
    """
    selected = [formatter(item) for item in items[:take]]
    if not selected:
        return "none"
    return " | ".join(selected)


def format_nif_usage_access(
    obj: Any,
    usage_key: str = "DataStreamUsage",
    access_key: str = "DataStreamAccess",
) -> str:
    """Format usage/access pair as 'usage=V access=V'.

    Mirrors: Format-NifUsageAccess
    """
    usage = json_value_or_dash(obj, usage_key)
    access = json_value_or_dash(obj, access_key)
    return f"usage={usage} access={access}"


def format_vector_sample(sample: dict[str, Any]) -> str:
    """Format a vector sample into a display string.

    Produces: v0=(x,y,z) prev=... next=...
            or: v0=(x,y,z) len=...  (for normals)

    Mirrors: Format-VectorSample
    """
    components = json_value_or_dash(sample, "Components")
    if components == 2 or str(components) == "2":
        values = f"{json_value_or_dash(sample, 'X')},{json_value_or_dash(sample, 'Y')}"
    else:
        values = (
            f"{json_value_or_dash(sample, 'X')},"
            f"{json_value_or_dash(sample, 'Y')},"
            f"{json_value_or_dash(sample, 'Z')}"
        )

    attribute = str(json_value_or_dash(sample, "Attribute"))
    if attribute == "normal":
        suffix = f" len={json_value_or_dash(sample, 'VectorLength')}"
    else:
        suffix = (
            f" prev={json_value_or_dash(sample, 'PreviousDistance')}"
            f" next={json_value_or_dash(sample, 'NextDistance')}"
        )

    index = sample.get("Index", "?") if isinstance(sample, dict) else "?"
    return f"v{index}=({values}){suffix}"


def format_proof_review_summary(fitness: dict[str, Any]) -> str:
    """Format a FirstSegmentProofReview into a one-line summary.

    Mirrors: Format-ProofReviewSummary
    """
    review = fitness.get("FirstSegmentProofReview") if isinstance(fitness, dict) else None
    if review is None or not isinstance(review, dict):
        return "proofFlags=- planes=- sign=- parityBreaks=-"

    flags_raw = review.get("ReviewFlags")
    if flags_raw and isinstance(flags_raw, list):
        flags = ",".join(str(f) for f in flags_raw)
    else:
        flags = "-"

    plane_counts = review.get("DominantPlaneCounts")
    if plane_counts and isinstance(plane_counts, list):
        plane_items = [
            f"{p.get('Value', '?')}:{p.get('Count', 0)}"
            for p in plane_counts[:3]
            if isinstance(p, dict)
        ]
        planes = " | ".join(plane_items) if plane_items else "-"
    else:
        planes = "-"

    pos = json_value_or_dash(review, "PositiveDominantSignedAreaCount")
    neg = json_value_or_dash(review, "NegativeDominantSignedAreaCount")
    zero = json_value_or_dash(review, "ZeroDominantSignedAreaCount")
    parity = json_value_or_dash(review, "NonAlternatingParityTransitionCount")

    return (
        f"proofFlags={flags} planes={planes} "
        f"sign=+{pos}/-{neg}/{zero} parityBreaks={parity}"
    )


# ============================================================================
# Semantic hint helpers
# ============================================================================

def semantic_hint_primary_model(entry: dict[str, Any]) -> str:
    """Pick the primary .ma model from name candidates.

    Prefers art/project/*.ma paths.

    Mirrors: Get-SemanticHintPrimaryModel
    """
    names = entry.get("NameCandidates", []) if isinstance(entry, dict) else []
    ma_names = [str(n) for n in names if isinstance(n, str) and n.endswith(".ma")]
    art_names = [n for n in ma_names if n.startswith("art/project/")]
    if art_names:
        return art_names[0]
    if ma_names:
        return ma_names[0]
    return "-"


def semantic_hint_bucket(path: str) -> str:
    """Normalize a path into a 4-segment bucket.

    Strips z:/twn/ and art/project/ prefixes.

    Mirrors: Get-SemanticHintBucket
    """
    if not path or not path.strip() or path == "-":
        return "-"

    normalized = path.lower().replace("\\", "/")
    normalized = re.sub(r"^z:/twn/", "", normalized)
    normalized = re.sub(r"^art/project/", "", normalized)
    parts = [p for p in normalized.split("/") if p.strip()]
    if len(parts) >= 4:
        return "/".join(parts[:4])
    return "/".join(parts) if parts else "-"


# ============================================================================
# JSON load helper
# ============================================================================

def load_json_report(path: str | Path) -> dict[str, Any]:
    """Load a JSON report file, raising on missing/parse errors.

    Mirrors the common pattern: Get-Content ... -Raw | ConvertFrom-Json
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No report found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON report: {path}") from exc
