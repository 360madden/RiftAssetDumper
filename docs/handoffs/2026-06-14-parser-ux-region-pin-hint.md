# 2026-06-14 — Parser UX: better hint when --scan-region-base is set without a target process

**Date**: 2026-06-14
**Type**: Non-blocking UX follow-up
**Scope**: One-line improvement to a single parser error message in RiftReader.
**Status**: Proposal only. No code change. Not blocking any live-read chain.
**Originating handoff**: `docs/handoffs/2026-06-13-phase3-bounded-triplet-invocation.md` (parser widening commit, code-review round 2 follow-up).

## Context

When the parser in `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Cli\ReaderOptionsParser.cs` rejects an invocation that sets `--scan-region-base` or `--scan-region-size` without also specifying `--pid` or `--process-name`, it currently emits a generic message:

```csharp
// ReaderOptionsParser.cs, line 1961
if (processId.HasValue == !string.IsNullOrWhiteSpace(processName))
{
    return ReaderOptionsParseResult.Fail("Specify either --pid or --process-name.", UsageText);
}
```

This message is correct but unhelpful when the user has *also* set `--scan-region-base` or `--scan-region-size`, because in that case the user's intent is unambiguous: they want to read memory at a specific address, and that read is meaningless without a target process. The user has to read the parser code (or trial-and-error) to realise the missing identifier is the reason for the failure.

The follow-up was flagged in the code-reviewer sign-off of the parser widening commit (the change that lifted the region-flags restriction from `--scan-float-triplet` only to `--scan-float-triplet`, `--scan-string`, and `--scan-module-pattern`). The new test `Parse_AcceptsStringScanWithScanRegion` exposed the issue when a missing `--process-name` caused the parser to reject the otherwise-valid combination, surfacing the unhelpful message.

## Proposal

One-line change to the error message. If the user has set `--scan-region-base` or `--scan-region-size` (both `ScanRegionBase.HasValue` and `ScanRegionSize.HasValue` may be set independently — either alone is enough to imply region pinning), append a hint to the error message that the missing process identifier is required specifically because the read is region-pinned.

Proposed new message:

```text
Specify either --pid or --process-name. (Required when --scan-region-base or --scan-region-size is set, since region pinning has no target process to read from.)
```

The implementation is a single-string conditional: detect whether any of `ScanRegionBase` or `ScanRegionSize` is set on the parsed `ReaderOptions` and branch the error message text accordingly. No new validation logic, no new error codes, no schema change.

## Acceptance criteria

1. When `--scan-region-base` is set without `--pid`/`--process-name`, the parser emits the augmented message above.
2. When `--scan-region-size` is set without `--pid`/`--process-name`, the parser emits the augmented message above.
3. When both are set without `--pid`/`--process-name`, the parser emits the augmented message above.
4. When neither is set and `--pid`/`--process-name` is missing, the parser emits the original short message (`"Specify either --pid or --process-name."`) — i.e. no behaviour change for callers who never use region pinning.
5. New xUnit test in `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\Cli\ReaderOptionsParserTests.cs` covers each of (1), (2), and (3); existing test `Parse_RejectsPidOrProcessName` (or equivalent) is updated to assert the short message for the no-region case.
6. All other tests still pass (current baseline: 25/25 in `ReaderOptionsParserTests`; 25+N where N is the new test count after the change).

## Files to change

- `reader/RiftReader.Reader/Cli/ReaderOptionsParser.cs` — modify the `ReaderOptionsParseResult.Fail` call at line 1961 to branch on `ScanRegionBase.HasValue || ScanRegionSize.HasValue`.
- `reader/RiftReader.Reader.Tests/Cli/ReaderOptionsParserTests.cs` — add 3 new tests covering the region-set cases; update the existing rejection test to assert the short message for the no-region case.

## Test impact

- 3 new tests added; 1 existing test updated to assert the short-message variant.
- Expected new baseline: 28/28 in `ReaderOptionsParserTests` (was 25/25 after the parser widening commit).
- Full RiftReader test suite: ~28/28 in `ReaderOptionsParserTests` + the rest of the suite unchanged.

## Out of scope

- No other parser error messages are touched.
- No CLI help text (`UsageText`) changes — the hint is inline in the failure message only.
- No new error codes or result types.
- No live-read chain gating. The change ships in a follow-up docs commit after the Step 49 status decision (PASS or FAIL) is recorded, so the live-read tooling is not in flux during the decision window.

## Schedule

**Trigger event**: One of the following commits lands (both close the §8.4 status-update path):

- `docs: phase3 PASS — step49 status-update to open-positive-live-confirmed` (the §8.4 PASS handoff commit), or
- `docs: phase3 FAIL — step49 stays closed-negative-current-live-state` (the §8.4 FAIL handoff commit)

**Post-trigger sequencing**:

1. After the §8.4 decision commit lands on `main`, the parser UX follow-up becomes unblocked.
2. Implement the one-line change to `ReaderOptionsParser.cs` line 1961 and the 4 test changes in `ReaderOptionsParserTests.cs`.
3. Run `dotnet build RiftReader.slnx --nologo` and `dotnet test reader/RiftReader.Reader.Tests/RiftReader.Reader.Tests.csproj --nologo --filter "FullyQualifiedName~ReaderOptionsParserTests"` — expect 28/28 pass.
4. Run `dotnet format RiftReader.slnx --verify-no-changes` to confirm formatting compliance.
5. Commit message: `reader: hint at missing process identifier when --scan-region-base is set`
6. Single docs/reader commit (no batching with other follow-ups unless they share a release line).

**Conflict-avoidance rationale** (carried from the §8.4 status-update path): The live-read tooling (`RiftReader` CLI + the four `--scan-float-triplet` invocations + the Step 49 status decision) must not be in flux during the decision window. The parser UX change touches the same error site that surfaces during live-read argument validation, so any behaviour drift in the error message would change what the operator sees in the failure path. Holding the change until after the §8.4 commit eliminates that risk.

**Watch-for**: the §8.4 decision commit is not yet on `main`. The follow-up stays dormant in the handoffs directory until the trigger fires. No reminder or alarm is needed — the next handoff (PASS or FAIL) will reference this file by its filename in its "Out of scope" or "Related follow-ups" section.

## Related follow-ups

- **§8.4 PASS handoff template** (pre-staged): `docs/handoffs/2026-06-14-phase3-pass-step49-status-update.md` — closing this trigger fires the parser UX fix.
- **§8.4 FAIL handoff template** (pre-staged): `docs/handoffs/2026-06-14-phase3-fail-step49-stays-closed.md` — closing this trigger (Mode A or Mode B) also fires the parser UX fix; the failure-mode branch only changes the FAIL record's commit pattern, not the trigger relationship.
- **m3 follow-up batch cross-ref** (deferred side): `docs/handoffs/2026-06-13-m3-safe-followup-batch.md` §"Deferred items" — one-line cross-reference row added 2026-06-14 pointing back at this handoff.
- **Parser widening commit** (originating): the prior commit that lifted the region-flags restriction from `--scan-float-triplet` only to the three-mode set; the code-reviewer sign-off in round 2 flagged the missing UX hint.

## Filename-deviation protocol

If at Phase 3 invocation time the operator's `--output` paths deviate from the §5.1 `phase3-bounded-triplet-<UTC>-vN.json` recipe, the operator pastes back either the four actual paths (`ACTUAL_PHASE3_FILENAMES: v0 = ..., v1 = ..., v2 = ..., v3 = ...`) or a shared prefix pattern (`PREFIX_PATTERN = <pattern>`), and the AI applies a one-line patch to `docs/handoffs/2026-06-14-phase3-fail-mode-b-surrogate-lead.md` line 16 — the only direct filename-pattern reference in the §8.4 chain. The per-vertex tables in the PASS/FAIL templates use `TBD` placeholders anchored on the v0–v3 row labels, so the per-vertex mapping is immune to filename deviation. The patch and the §8.4 decision fill land atomically in the same commit, with no cross-reference chain repair needed because the §8.4 templates are still DRAFT, unfilled, and uncommitted at the time of any deviation.

## Decision log

- 2026-06-14: Filed as a non-blocking UX follow-up. Originated in the parser widening commit code-review (round 2). Not blocking the Phase 1/2/3 invocation chain. Scheduled in a separate docs commit after the §8.4 Step 49 status-update path completes. Cross-references added to the §8.4 PASS/FAIL templates and the m3 follow-up batch.
