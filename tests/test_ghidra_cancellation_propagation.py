"""Verify ``ScalarOffsetSearcher.java`` re-throws user cancellation and folds
prev-context + next-context walk failures into ONE summary printerr line per
hit.

Static-analysis fixture only — Ghidra's analyzeHeadless cannot run in CI, so we
read the ``.java`` source as text and lock the structural patterns that prove
both F4 review nits' intent. Anchoring INVERTED: each narrowing-position test
finds the cancel-narrowing ``catch (CancelledException ce)`` itself (the
structural marker we actually care about) and asserts it appears AFTER the
relevant walk's loop entry. This is robust against future loop-body growth —
the catch declaration line is short and stable, while the prev/next-walk loop
bodies are currently ~1200 chars and may grow further as the script evolves.

The two CI-blocking behaviors this fixture locks down:

    1. **Cancellation propagation (F4 nit #1).** A user-initiated cancel
       (``monitor.setCancelled(true)``) that surfaces as a ``CancelledException``
       mid-context-walk must NOT be silently logged. It must be explicitly
       re-thrown so the framework's cancellation flow can drain cleanup work.
       The pre-cycle-5.3.2 plain ``catch (Exception)`` block treated cancellation
       as just-another-exception and froze the script run.

    2. **Per-hit summary line (F4 nit #2).** When BOTH prev-context and
       next-context walks fail on the same hit, there should be exactly ONE
       printerr line summarizing both failures — not two separate lines. This
       bounds per-offset noise regardless of hit count, so the script's
       stderr output stays tractable even with thousands of hits.

Test strategy: read ``scripts/ghidra/ScalarOffsetSearcher.java`` as text,
verify the structural patterns that prove both behaviors. No Ghidra runtime
needed; no Java-mock-via-Python needed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

JAVA_FILE = Path(__file__).resolve().parents[1] / "scripts" / "ghidra" / "ScalarOffsetSearcher.java"

# Cached source — read once at module import. Empty if file is missing so the
# fixture can still report a clear assertion failure below.
JAVA_SOURCE_CACHE: str = JAVA_FILE.read_text(encoding="utf-8") if JAVA_FILE.exists() else ""

# Match a CancelledException catch+rethrow pair regardless of variable name.
# Captures the bound variable so we can assert `throw <var>;` re-throws the
# SAME variable the catch bound. Allows one level of nested braces so a
# `try { ... } finally { throw ce; }` refactor still matches.
_CANCEL_RETHROW_PATTERN = re.compile(
    r"catch\s*\(\s*CancelledException\s+(\w+)\s*\)"  # catch (CancelledException VAR)
    r"\s*\{(?:[^{}]|\{[^{}]*\})*?"  # { ... one-level-nested ok ...
    r"throw\s+"  # throw
    r"\1"  # ... VAR (same var the catch bound)
    r"\s*;"  # ...;
)

# Match the String.join summary call with the contextWarnings accumulator.
_SUMMARY_JOIN_PATTERN = re.compile(r"String\.join\(\s*\".*?\"\s*,\s*contextWarnings\s*\)")

# Anchor phrases used by the narrowing-position tests below. Stable identifiers
# in the current Java source; if a refactor renames any of these, the test
# that depends on it will fail loudly with a clear message.
ANCHOR_PREV_WALK_LOOP_ENTRY = "Address prevAddr = addr;"  # inside prev-walk try-block
ANCHOR_NEXT_WALK_LOOP_ENTRY = "Address nextAddr = addr;"  # inside next-walk try-block
ANCHOR_BYTES_FETCH_CALL = "currentProgram.getMemory().getBytes("  # mem-read call site


def _first_catch_rethrow_after(source: str, anchor_idx: int) -> tuple[str, str] | None:
    """Return (bound_var_name, throw_phrase) for the FIRST cancel-catch after ``anchor_idx``.

    Returns ``None`` if no such catch+throw pair is found in the source after
    the anchor. The bound var name is captured so we can re-show it in
    assertion failure messages without leaking through a regex group.
    """
    catch_idx = source.find("catch (CancelledException", anchor_idx)
    if catch_idx < 0:
        return None
    # Take a bounded window AFTER the catch declaration to look for the rethrow.
    # The catch block is a few lines of code in the current shape; a 600-char
    # window is plenty without crossing into unrelated code.
    catch_window_end = min(catch_idx + 600, len(source))
    catch_window = source[catch_idx:catch_window_end]
    match = _CANCEL_RETHROW_PATTERN.search(catch_window)
    if match is None:
        return None
    return match.group(1), "throw " + match.group(1) + ";"


@pytest.fixture(scope="module")
def java_source() -> str:
    """Read the ScalarOffsetSearcher.java file under test."""
    assert JAVA_SOURCE_CACHE, f"missing or empty Java source: {JAVA_FILE}"
    return JAVA_SOURCE_CACHE


# ---------------------------------------------------------------------------
# F4 nit #1: cancellation propagation
# ---------------------------------------------------------------------------


def test_cancelled_exception_import_present(java_source: str) -> None:
    """Required import for the new exception narrowing to compile."""
    assert "import ghidra.util.exception.CancelledException;" in java_source, (
        "Missing `import ghidra.util.exception.CancelledException;` — required by F4 nit #1: "
        "the new explicit catch (CancelledException ce) blocks must have this import to compile."
    )


def test_cancellation_rethrown_in_prev_context_walk(java_source: str) -> None:
    """The cancel-narrowing catch must appear AFTER the prev-walk loop entry.

    Inverted-anchor design: search FOR the cancel-catch (the marker we care
    about) and verify it's after ``Address prevAddr = addr;``. Robust against
    future loop-body growth.
    """
    prev_loop_idx = java_source.find(ANCHOR_PREV_WALK_LOOP_ENTRY)
    assert prev_loop_idx >= 0, (
        f"Prev-context-walk anchor `{ANCHOR_PREV_WALK_LOOP_ENTRY}` not found — "
        f"the prev-walk loop may have been refactored out of existence."
    )
    rethrow = _first_catch_rethrow_after(java_source, prev_loop_idx)
    assert rethrow is not None, (
        f"F4 nit #1: prev-context walk missing `catch (CancelledException <var>) "
        f"{{ throw <var>; }}` rethrow after `{ANCHOR_PREV_WALK_LOOP_ENTRY}`. "
        f"The cancel-narrowing was either dropped or moved out of the per-hit region."
    )


def test_cancellation_rethrown_in_next_context_walk(java_source: str) -> None:
    """The cancel-narrowing catch must appear AFTER the next-walk loop entry."""
    next_loop_idx = java_source.find(ANCHOR_NEXT_WALK_LOOP_ENTRY)
    assert next_loop_idx >= 0, f"Next-context-walk anchor `{ANCHOR_NEXT_WALK_LOOP_ENTRY}` not found."
    rethrow = _first_catch_rethrow_after(java_source, next_loop_idx)
    assert rethrow is not None, (
        f"F4 nit #1: next-context walk missing `catch (CancelledException <var>) "
        f"{{ throw <var>; }}` rethrow after `{ANCHOR_NEXT_WALK_LOOP_ENTRY}`. "
        f"The cancel-narrowing was either dropped or moved out of the per-hit region."
    )


def test_cancellation_rethrown_in_bytes_fetch(java_source: str) -> None:
    """Bytes-fetch must also narrow cancellation — same rule as the context walks.

    Without this narrowing, a cancel during ``currentProgram.getMemory().getBytes(...)``
    would be silently swallowed (sets ``instructionBytes=""`` and the loop continues),
    re-introducing the latent cancel-log-and-swallow bug at a third site.
    """
    bf_idx = java_source.find(ANCHOR_BYTES_FETCH_CALL)
    assert bf_idx >= 0, (
        f"Bytes-fetch call site `{ANCHOR_BYTES_FETCH_CALL}` not found — "
        f"the per-hit bytes decoder may have been refactored to a different API."
    )
    rethrow = _first_catch_rethrow_after(java_source, bf_idx)
    assert rethrow is not None, (
        f"F4 nit #1: bytes-fetch missing `catch (CancelledException <var>) "
        f"{{ throw <var>; }}` rethrow after `{ANCHOR_BYTES_FETCH_CALL}`. "
        f"Same propagation rule as the context walks; without it, cancel during "
        f"getBytes() is silently swallowed."
    )


def test_cancellation_narrowings_appear_in_source_order(java_source: str) -> None:
    """The 3 cancel-narrowing catches must appear in source-relative walk order.

    Disambiguation invariant: the forward-anchored proximity tests above would
    each independently pass if a malformed file re-uses a single cancel-catch.
    This single test refuses that: each catch must appear in the expected
    position relative to the others AND to its assigned walk's loop entry.

    Source-relative expected order (lexicographically):
        bytes-fetch call site
            < bytes-fetch cancel-catch
            < prev-walk loop entry
            < prev-walk cancel-catch
            < next-walk loop entry
            < next-walk cancel-catch
    """
    bf_call = java_source.find(ANCHOR_BYTES_FETCH_CALL)
    bf_catch = java_source.find("catch (CancelledException", bf_call) if bf_call >= 0 else -1
    prev_loop = java_source.find(ANCHOR_PREV_WALK_LOOP_ENTRY)
    prev_catch = java_source.find("catch (CancelledException", prev_loop) if prev_loop >= 0 else -1
    next_loop = java_source.find(ANCHOR_NEXT_WALK_LOOP_ENTRY)
    next_catch = java_source.find("catch (CancelledException", next_loop) if next_loop >= 0 else -1

    assert bf_call >= 0 and bf_catch >= bf_call, "bytes-fetch call/anchor missing"
    assert prev_loop >= 0 and prev_catch >= prev_loop, "prev-walk loop/catch missing"
    assert next_loop >= 0 and next_catch >= next_loop, "next-walk loop/catch missing"

    # All three catches must be distinct positions, in source order
    # (bytes-fetch first because it's earlier in the file than the per-hit walks).
    assert bf_catch < prev_catch < next_catch, (
        f"F4 nit #1: catch ordering invariant violated. Expected "
        f"bytes-fetch catch < prev-walk catch < next-walk catch. "
        f"Got offsets bytes_fetch_catch={bf_catch}, "
        f"prev_walk_catch={prev_catch}, next_walk_catch={next_catch}. "
        f"A malformed file (e.g., one that re-uses a single cancel-catch) would "
        f"satisfy the forward-anchored proximity tests in isolation but fail this guard."
    )


# ---------------------------------------------------------------------------
# F4 nit #2: per-hit folded summary line
# ---------------------------------------------------------------------------


def test_context_warnings_accumulator_present(java_source: str) -> None:
    """Per-hit accumulator variable must exist so we can fold failures."""
    assert "contextWarnings" in java_source, (
        "F4 nit #2: must fold prev+next context-walk failures into ONE summary line per hit. "
        "Expected a `contextWarnings` accumulator (List<String>) in the per-hit region."
    )


def test_summary_line_uses_string_join(java_source: str) -> None:
    """The per-hit summary must `String.join` the accumulated fragments."""
    assert _SUMMARY_JOIN_PATTERN.search(java_source) is not None, (
        'F4 nit #2: the per-hit summary printerr must use `String.join("...", contextWarnings)` '
        "to merge prev+next failure messages into one line. Pattern not found."
    )


def test_old_inline_walk_printerrs_removed(java_source: str) -> None:
    """Old per-failure inline printerrs must not be reintroduced.

    These exact strings appeared in the pre-cycle-5.3.2 file and would re-emerge
    if a refactor splits the summary back into two per-walk calls.
    """
    assert "failed to walk previous context" not in java_source, (
        "F4 nit #2 regression: the per-failure inline printerr for the prev walk must NOT "
        "be reintroduced. Both prev+next walk failures are now folded into one per-hit summary."
    )
    assert "failed to walk next context" not in java_source, (
        "F4 nit #2 regression: the per-failure inline printerr for the next walk must NOT "
        "be reintroduced. Both prev+next walk failures are now folded into one per-hit summary."
    )


def test_summary_distinguishes_prev_and_next(java_source: str) -> None:
    """The fragments added by the two walkers must be distinguishable when joined."""
    assert "previous:" in java_source, (
        "F4 nit #2: expected the prev-walk failure fragment to be tagged `previous:` so the "
        "summary line clearly distinguishes which walk failed."
    )
    assert "next:" in java_source, (
        "F4 nit #2: expected the next-walk failure fragment to be tagged `next:` so the "
        "summary line clearly distinguishes which walk failed."
    )


def test_per_hit_printerr_uses_full_discriminator_prefix(java_source: str) -> None:
    """The summary printerr must reference the full discriminator-tag prefix."""
    assert "scalar-offset-search partial context" in java_source, (
        "F4 nit #2: expected the per-hit summary printerr to start with "
        "`WARN: scalar-offset-search partial context at <addr> ...`. "
        "Without the full discriminator-tag prefix, downstream tooling that "
        "greps the summary line will silently miss."
    )
