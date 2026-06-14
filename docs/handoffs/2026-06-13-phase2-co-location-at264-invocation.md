# Phase 2 invocation handoff — co-location @264/#15 prefix scan

Date: 2026-06-13
Author: Buffy (planning only; no live read executed)
Companions: `docs/handoffs/2026-06-13-scoped-live-scan-asset-load-proof.md`,
`docs/handoffs/2026-06-13-phase1-live-read-invocation.md`,
`docs/handoffs/2026-06-13-operator-load-state-target-assets.md`,
`docs/handoffs/2026-06-13-phase3-bounded-triplet-invocation.md` (downstream)

## TL;DR

| Field | Value |
|---|---|
| Phase | **2 of 3** in the scoped-scan plan (gated on Phase 1 PASS) |
| Purpose | Prove the asset's geometry representation is co-resident with the asset ID hit from Phase 1. |
| Provider (preferred) | `RiftReader.Reader` at `C:/RIFT MODDING/RiftReader/scripts/run-reader.cmd` |
| Provider (fallback) | Local Python `scan-live-memory` scaffold (uses `kernel32.ReadProcessMemory` with `process_query_limited_information \| process_vm_read`) |
| Process name | `rift_x64.exe` (only allowed target) |
| Patterns (1) | `stage5_step48_at264_index_strip_prefix` (`00010002000200010003000400050006`, 16 bytes) — the existing Step 48 target, re-used unchanged |
| Co-location rule | @264 prefix within ±4 MiB of any Phase 1 asset-ID hit = co-resident (proceed to Phase 3). Outside that band = different asset (close weak-positive). 0 hits = representation unproven (close negative). |
| Output directory | `Exports/discovery-plan/stage5-live/` (gitignored, schema-validated) |
| Output JSON | `Exports/discovery-plan/stage5-live/phase2-at264-co-location-<UTC>.json` |
| Output Markdown | `Exports/discovery-plan/stage5-live/phase2-at264-co-location-<UTC>.md` |
| Region pinning | **Not available in either provider** — RiftReader `--scan-module-pattern` and the local scanner scaffold both run a full-process pattern scan bounded only by the existing `Limits`. Co-location is established by **operator-side address cross-reference** between the Phase 1 hit and the Phase 2 hit, not by a scanner-level region constraint. |
| Dry-run status | **PASS** (Phase 0 plan validated against `live-memory-scan-plan-v1.schema.json` with `ExecutionAllowed: false` + `LiveProcessReadExecuted: false`; refusal-reason: `dry-run-only-no-live-read-requested`) |
| Live read executed | **false** (this handoff does not execute) |

## 0. Gate to Phase 2

Phase 2 is only reached if **Phase 1 returned ≥1 hit for at least one of the two
asset IDs** (`6fc01704d4a509d5` or `caa9a88e94ec8db0`). If Phase 1 returned
0 hits, Phase 2 is skipped and the operator closes negative for this load
state per §7.2 of the Phase 1 invocation handoff. There is no point
scanning for the @264 prefix if the asset itself is not loaded.

## 1. Why this is a separate gate

Per `docs/live-memory-readonly-safety-boundary.md` §"Actual live-read execution
gate", the live read requires six pre-disclosed items: exact command, exact
PID, exact patterns, output paths, scan byte/region/time limits, and
generated-output guard status. Phase 2 carries forward the same gate; the
only changes versus Phase 1 are the pattern, the output filenames, and the
operator-side cross-reference rule.

## 2. Exact invocation

### 2.1 Preferred provider: `RiftReader.Reader`

```text
cd C:/RIFT MODDING/RiftReader
C:/RIFT MODDING/RiftReader/scripts/run-reader.cmd ^
  --process-name rift_x64 ^
  --scan-module-pattern "00 01 00 02 00 02 00 01 00 03 00 04 00 05 00 06" ^
  --scan-context 16 ^
  --max-hits 8 ^
  --output "C:/RIFT MODDING/Assets/Exports/discovery-plan/stage5-live/phase2-at264-co-location-<UTC>.json"
```

Notes on the flag choice:

- `--scan-module-pattern` accepts the space-separated `aa bb ?? cc` form for
  AOB / byte-pattern scans. The Step 48 / Phase 2 pattern is a fixed
  16-byte sequence (no `??` wildcards), so a literal byte list is
  sufficient and matches the Step 48 precedent.
- `--scan-context 16` reports 16 bytes of context around each match, which
  is the same as the pattern width. Larger context (e.g. 64) is acceptable
  but produces larger output files.
- `--max-hits 8` bounds the matches per `--scan-module-pattern` invocation.
  The expected count under normal load is 1-2 (the @264 prefix is
  asset-specific; a high count would be a noise signal and should be
  investigated before Phase 3).
- The `--process-name rift_x64` form resolves the PID internally; the
  local Python scanner requires an explicit `--pid` because it does not
  enumerate processes.

### 2.2 Fallback provider: local Python `scan-live-memory` scaffold

```text
cd C:/RIFT MODDING/Assets
python scripts/rift_workflow.py scan-live-memory ^
  --live-pattern-file docs/live-memory-scan-targets.json ^
  --execute-live-read ^
  --experimental-live ^
  --confirm-live-read ^
  --pid <OPERATOR_SUPPLIED_PID> ^
  --max-scan-bytes 16777216 ^
  --max-matches 8 ^
  --max-regions 256 ^
  --timeout-seconds 10
```

The local scanner consumes the `label=hex` form from the manifest. The
@264 target is already present as
`stage5_step48_at264_index_strip_prefix=00010002000200010003000400050006`
so no new manifest entries are required for Phase 2.

`<OPERATOR_SUPPLIED_PID>` is the Windows PID of `rift_x64.exe`, captured by
the operator at invocation time via:

```text
tasklist /FI "IMAGENAME eq rift_x64.exe"
```

The local scanner fails closed on the same conditions as Phase 1:

| Condition | Behaviour |
|---|---|
| `pid <= 0` | raises `RuntimeError: live scan requires an explicit positive PID` |
| Process name ≠ `rift_x64.exe` | adds `target-process-must-be-rift_x64.exe` to `RefusalReasons`; `ExecutionAllowed` = `false` |
| Missing `--experimental-live` | adds `missing---experimental-live` to `RefusalReasons` |
| Missing `--confirm-live-read` | adds `missing---confirm-live-read` to `RefusalReasons` |
| Missing `--execute-live-read` | dry-run only; adds `dry-run-only-no-live-read-requested` |
| Output path outside `Exports/discovery-plan/stage5-live/` | raises `ValueError: scan-live-memory output must stay under Exports/discovery-plan/stage5-live` |

## 3. Exact pattern (re-used from Step 48, no new manifest entries)

| Label | Bytes | Hex | Role |
|---|---:|---|---|
| `stage5_step48_at264_index_strip_prefix` | 16 | `00010002000200010003000400050006` | Phase 2 primary target — UInt16BE degenerate-bridge index strip prefix for `meshSize=325` / `mesh#6` / `@264`/`#15` topology (asset-specific; the prefix is determined by the mesh's vertex connectivity, which is unique per NIF) |

This is the only pattern in the Phase 2 invocation. The two Step 50
asset-ID patterns are **not** scanned in Phase 2; they were consumed by
Phase 1.

The pattern is `PromotionStatus: "candidate-only"` and has been validated
against `docs/schemas/live-memory-scan-targets-v1.schema.json` since the
prior manifest update.

## 4. Co-location rule (operator-side cross-reference)

Neither provider exposes a region-pinning flag for pattern scans (verified
against `run-reader.cmd --help` on 2026-06-13; the local Python scaffold
mirrors this). Co-location is established by **operator-side address
arithmetic** between the Phase 1 asset-ID hit and the Phase 2 @264 prefix
hit:

```text
For each Phase 2 match at address P2:
  for each Phase 1 hit at address P1:
    distance = |P2 - P1|
    if distance <= 4 MiB (= 0x400000 = 4,194,304 bytes):
      -> co-resident: A := P2 (proceed to Phase 3)
    else:
      -> different asset (record both; do not proceed to Phase 3)
```

The 4 MiB threshold is heuristic, derived from the scoped-scan plan's
expectation that an asset's ASCII ID and its index-strip data sit in the
same general region of the asset manager / streaming buffer. It is
deliberately large enough to absorb sub-allocation drift but small enough
to exclude unrelated @264 prefixes that belong to other loaded assets.

### 4.1 Worked example (placeholder)

```text
Phase 1 hit (caa9a88e94ec8db0):  0x000001A2_B340_1000
Phase 2 hit (@264 prefix):       0x000001A2_B3C0_0800
                                 ────────────────────────
distance:                         0x0000_0000_7F_F800 = 8 MiB - 64 KiB
verdict:                          within ±4 MiB window
                                  -> co-resident, A := 0x000001A2_B3C0_0800
```

The operator captures the exact `A` value in the working notes; Phase 3
consumes it.

## 5. Exact output paths

Output paths are auto-generated by `live_memory_scanner.build_live_memory_scan_plan`
with a UTC timestamp; the local scanner writes:

```text
Exports/discovery-plan/stage5-live/live-memory-scan-<UTC>.json
Exports/discovery-plan/stage5-live/live-memory-scan-<UTC>.md
```

For the RiftReader provider, the operator is responsible for supplying
`--output`. Recommended Phase 2 filenames:

```text
Exports/discovery-plan/stage5-live/phase2-at264-co-location-<UTC>.json
Exports/discovery-plan/stage5-live/phase2-at264-co-location-<UTC>.md
```

UTC timestamp format: `YYYYMMDDTHHMMSSZ` (matches scanner convention).

The output directory is locked to `Exports/discovery-plan/stage5-live/`
(validated by the schema pattern `^Exports/discovery-plan/stage5-live(/.*)?$`)
and is gitignored.

## 6. Scan limits (re-use scanner defaults)

| Limit | Value | Reason |
|---|---:|---|
| `MaxScanBytes` | 16,777,216 (16 MiB) | Scanner default; matches the Step 48/49 baseline. The @264 prefix is 16 bytes, well within this. |
| `MaxMatchesPerPattern` | 8 | Tighter than the scanner default (32) to surface a high count as a noise signal. |
| `MaxRegions` | 256 | Scanner default. |
| `TimeoutSeconds` | 10 | Scanner default; matches prior Step 48/49 scans. |
| `ChunkBytes` | 65,536 (64 KiB) | Scanner default; buffer-overlap window. |

These limits are intentionally **the same as Phase 1** so a Phase 1 hit
and a Phase 2 hit are directly comparable (same scan envelope). The
"bounded" aspect of Phase 2 is conceptual — the ±4 MiB co-location rule —
not a scanner-level region constraint.

## 7. Operator-approval gate

This is the explicit checklist the operator must complete and sign off on
**before any Phase 2 live read is run**. No live read should be attempted
unless every box is checked. This is the most important section of this
handoff.

### 7.1 Pre-invocation prerequisites

- [ ] **Phase 1 has been executed and returned ≥1 hit for at least one asset
      ID.** Recorded in the operator's working notes (addresses + UTC
      timestamps).
- [ ] **User has read this handoff and approved the Phase 2 invocation.**
      Confirmed in chat.
- [ ] **User has read `docs/handoffs/2026-06-13-scoped-live-scan-asset-load-proof.md`
      and approved the phased design.** Confirmed in chat.
- [ ] **User has read `docs/handoffs/2026-06-13-phase1-live-read-invocation.md`
      and the operator load-state handoff.** Confirmed in chat.

### 7.2 Operator-side load state (carried forward from Phase 1)

- [ ] **Zone / subzone / character / coordinates** — same as Phase 1
      (the load state has not changed since the Phase 1 read).
- [ ] **Distance to nearest `diffuse_blank` placeable** — same as Phase 1.
- [ ] **PID** — re-captured via `tasklist /FI "IMAGENAME eq rift_x64.exe"`.
      The PID may have changed if the game was restarted between Phase 1
      and Phase 2.
- [ ] **Phase 1 hit addresses** — recorded (never committed) for the
      co-location cross-reference in §4.

### 7.3 RIFT process state

- [ ] **`rift_x64.exe` is running and stable** (same conditions as Phase 1).
- [ ] **Character is not in combat** and **not in a zone transition**.
- [ ] **No addon is actively loading or unloading assets** during the
      scan window.
- [ ] **Only one `rift_x64.exe` process exists** (zero or multiple
      candidates fail closed; the local scanner requires an explicit
      positive PID).

### 7.4 Workspace state

- [ ] **Generated-output guard passes** —
      `python scripts/rift_workflow.py generated-output-guard` returns clean.
      (Run immediately before the Phase 2 live read.)
- [ ] **No tracked file has uncommitted changes that would be lost** —
      `git status` is clean for files the operator cares about.
- [ ] **Local `scan-live-memory` dry-run still passes** — same dry-run
      command as Phase 1 (the manifest is unchanged for Phase 2) returns
      `ExecutionAllowed: false` and
      `RefusalReasons: ["dry-run-only-no-live-read-requested"]`. The only
      thing changing at invocation time is `--execute-live-read` plus
      `--max-matches 8` (Phase 2-specific) and the actual `--pid`.
- [ ] **RiftReader is available** (if using the preferred provider) —
      `scripts/run-reader.cmd --help` exits 0; `--scan-module-pattern` is
      present in the help output.
- [ ] **The four safety flags are present in the command** —
      `--execute-live-read --experimental-live --confirm-live-read --pid <PID>`
      for the local scanner; or the equivalent `RiftReader` provider
      invocation with the operator-supplied PID.
- [ ] **Output directory is `Exports/discovery-plan/stage5-live/`** and is
      gitignored (`grep -F "Exports/discovery-plan/stage5-live" .gitignore`
      returns the ignore rule).

### 7.5 Safety confirmations

- [ ] **Read-only** — no writes, no DLL injection, no remote threads, no
      hooks.
- [ ] **No input sent to the game** during the scan.
- [ ] **No full process memory dump** requested.
- [ ] **No committed live reports** — all outputs go under ignored
      `Exports/discovery-plan/stage5-live/`.
- [ ] **Privacy preserved** — no chat text, account names, or local
      user-profile paths in any committed record.
- [ ] **Tests did not attach to a live process** —
      `python scripts/test_live_memory_scanner.py` was run with
      `FixtureProcessReader` only.

### 7.6 Post-invocation

- [ ] **Output JSON + Markdown written** under
      `Exports/discovery-plan/stage5-live/`.
- [ ] **Output reviewed** for sanity (no full dumps, no user paths,
      schema-valid JSON).
- [ ] **Per-pattern match counts recorded** in the operator's working
      notes.
- [ ] **Co-location verdict recorded** (co-resident / different asset /
      0 hits) with the address arithmetic in §4 worked through in the
      working notes.
- [ ] **Phase 3 decision recorded** (proceed to Phase 3 if co-resident;
      close negative otherwise).
- [ ] **`git status` checked** to confirm no live reports were
      accidentally staged.

### 7.7 Approval signature

When all boxes above are checked, the operator types this single line into
the chat before invoking the Phase 2 live read:

```text
APPROVED: Phase 2 live read authorised against rift_x64.exe PID <PID>; gate §7.1–§7.6 complete; Phase 1 produced <N> hit(s) for <ASSET_ID_LIST>.
```

Where `<N>` is the Phase 1 hit count and `<ASSET_ID_LIST>` is a
comma-separated list of asset IDs that produced hits in Phase 1 (or
"none" if the asset-load evidence is weak-positive). The line must also
reference the Phase 1 hit addresses implicitly via the operator's working
notes; the line itself must not include the addresses (privacy + minimal
chatter).

No Phase 2 live read should be attempted without this explicit approval
line.

## 8. What to do with the result

### 8.1 @264 prefix co-resident with a Phase 1 hit (±4 MiB)

```text
Phase 2 outcome: PASS
Record the co-resident address A.
Proceed to Phase 3 (bounded triplet probe around A).
```

### 8.2 @264 prefix found but not co-resident with any Phase 1 hit

```text
Phase 2 outcome: WEAK-POSITIVE
The @264 pattern may belong to a different loaded asset (the 16-byte
prefix is short enough to collide on a small alpha).
Record both addresses; do not run Phase 3.
Consider closing negative for this load state and re-testing in a
different load condition (different zone, different time of day).
```

### 8.3 @264 prefix not found

```text
Phase 2 outcome: FAIL (representation unproven for this load state)
The asset is loaded (Phase 1 hit) but the index-strip data is not in
the same region. The representation hypothesis is unproven.
Do not run Phase 3 (the bounded probe depends on a co-resident anchor).
Capture the result and close negative for this load state.
```

### 8.4 ≥2 @264 hits with different co-location verdicts

```text
Phase 2 outcome: MIXED
Treat as Phase 2 PASS only if at least one hit is co-resident with a
Phase 1 asset-ID hit. Treat the others as §8.2 / §8.3 candidates.
```

## 9. Hard prohibitions (carried forward from `docs/live-memory-readonly-safety-boundary.md`)

- No writes to process memory.
- No DLL injection.
- No remote threads.
- No code patches or hooks.
- No suspension or resumption of game threads.
- No changes to game files.
- No input sent to the game.
- No full process memory dumps.
- No committed generated live reports.
- No local user-profile paths in tracked docs or reports.

## 10. Status

- Handoff: **DRAFT — awaiting operator approval per §7.7**.
- Tracked-file changes: **none** (planning only; no new manifest entries
  required).
- Live read executed: **false** (this handoff does not execute; the
  operator executes on approval).
- Step 48 / 49 status: **unchanged**.
- Step 50 final handoff: **unchanged** (no parser/export promotion).
- Scoped scan plan: **unchanged** from
  `docs/handoffs/2026-06-13-scoped-live-scan-asset-load-proof.md`.
- Phase 1 invocation: **fully specified** in
  `docs/handoffs/2026-06-13-phase1-live-read-invocation.md`.
- Phase 3 invocation: **fully specified** in
  `docs/handoffs/2026-06-13-phase3-bounded-triplet-invocation.md`
  (downstream gate).
- Operator load state: **undocumented** (operator must complete §4 of
  the operator load-state handoff before approval).
- RiftReader flag-name verification: **PASS** (2026-06-13) —
  `--scan-module-pattern` is the correct flag for byte/AOB scans;
  `--scan-string` (verified in the Phase 1 handoff) is the correct flag
  for ASCII string scans; no flag substitution is required.
