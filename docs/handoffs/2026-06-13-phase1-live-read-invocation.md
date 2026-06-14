# Phase 1 live-read invocation handoff

Date: 2026-06-13
Author: Buffy (planning only; no live read executed)
Companions: `docs/handoffs/2026-06-13-scoped-live-scan-asset-load-proof.md`,
`docs/handoffs/2026-06-13-operator-load-state-target-assets.md`

## TL;DR

| Field | Value |
|---|---|
| Provider (preferred) | `RiftReader.Reader` at `C:/RIFT MODDING/RiftReader/scripts/run-reader.cmd` |
| Provider (fallback) | Local Python `scan-live-memory` (uses `kernel32.ReadProcessMemory` with `process_query_limited_information \| process_vm_read`) |
| Process name | `rift_x64.exe` (only allowed target) |
| Patterns (3) | `stage5_step48_at264_index_strip_prefix` (Step 48 positive control), `stage5_step50_asset_id_ascii_6fc01704d4a509d5` (Phase 1 primary), `stage5_step50_asset_id_ascii_caa9a88e94ec8db0` (Phase 1 sibling control) |
| Output directory | `Exports/discovery-plan/stage5-live/` (gitignored, schema-validated) |
| Output JSON | `Exports/discovery-plan/stage5-live/phase1-asset-id-scan-<UTC>.json` |
| Output Markdown | `Exports/discovery-plan/stage5-live/phase1-asset-id-scan-<UTC>.md` |
| Refusal-reason free | `dry-run-only-no-live-read-requested`, `missing---experimental-live`, `missing---confirm-live-read`, `missing-explicit---pid`, `target-process-must-be-rift_x64.exe` must all be absent |
| Dry-run status | **PASS** (Phase 0 plan validated against `live-memory-scan-plan-v1.schema.json` with `ExecutionAllowed: false` + `LiveProcessReadExecuted: false`; refusal-reason: `dry-run-only-no-live-read-requested`) |
| Live read executed | **false** (this handoff does not execute) |

## 1. Why this is a separate gate

Per `docs/live-memory-readonly-safety-boundary.md` §"Actual live-read execution gate":

> "Implementing the scanner is allowed under the 50-step plan, but executing it against a live process is a separate safety event.
> Before any actual live process read, the workflow must show:
>
> 1. exact command,
> 2. exact PID or process-selection behavior,
> 3. exact patterns,
> 4. output paths,
> 5. scan byte/region/time limits,
> 6. generated-output guard status.
> If those are not available, the live read must not run."

This handoff captures all six. The execution itself is still gated on the operator's signed approval (§3 below).

## 2. Exact invocation

### 2.1 Preferred provider: `RiftReader.Reader` (matches Step 48/49 precedent)

Step 48 and Step 49 both used `RiftReader.Reader` as the live provider, with the canonical command shape:

```text
scripts/run-reader.cmd --process-name rift_x64 --scan-module-pattern <pattern> --scan-module-name rift_x64.exe --scan-context 16 --json
```

```text
scripts/run-reader.cmd --process-name rift_x64 --scan-float <x> --scan-tolerance 0.001 --scan-context 48 --max-hits 16 --json
```

For Phase 1, the exact invocation (per target pattern) is:

```text
cd C:/RIFT MODDING/RiftReader
C:/RIFT MODDING/RiftReader/scripts/run-reader.cmd ^
  --process-name rift_x64 ^
  --scan-string "6fc01704d4a509d5" ^
  --scan-encoding ascii ^
  --scan-context 16 ^
  --max-hits 8 ^
  --output "C:/RIFT MODDING/Assets/Exports/discovery-plan/stage5-live/phase1-asset-id-6fc01704d4a509d5.json"
```

and (sibling control):

```text
C:/RIFT MODDING/RiftReader/scripts/run-reader.cmd ^
  --process-name rift_x64 ^
  --scan-string "caa9a88e94ec8db0" ^
  --scan-encoding ascii ^
  --scan-context 16 ^
  --max-hits 8 ^
  --output "C:/RIFT MODDING/Assets/Exports/discovery-plan/stage5-live/phase1-asset-id-caa9a88e94ec8db0.json"
```

> **Flag-name verified (2026-06-13):** `scripts/run-reader.cmd --help` confirms `--scan-string` is the correct flag for ASCII string scans (with optional `--scan-encoding ascii|utf16|both`; `ascii` is the default and is shown explicitly above for clarity). The `--scan-module-pattern "aa bb ?? cc"` flag remains the correct flag for byte/AOB scans (the Step 48 @264 prefix scan); `--scan-float`, `--scan-int32`, `--scan-double`, `--scan-float-triplet`, and `--scan-pointer` are the numeric scan variants. No flag substitution is required.
>
> **PID requirement:** RiftReader uses `--process-name rift_x64` and resolves the PID internally. The local Python scanner requires an explicit `--pid` because it does not enumerate processes. Both providers converge on `rift_x64.exe`.

### 2.2 Fallback provider: local Python `scan-live-memory` scaffold

If `RiftReader.Reader` is unavailable or the operator prefers the local scaffold, use:

```text
cd C:/RIFT MODDING/Assets
python scripts/rift_workflow.py scan-live-memory ^
  --live-pattern-file docs/live-memory-scan-targets.json ^
  --execute-live-read ^
  --experimental-live ^
  --confirm-live-read ^
  --pid <OPERATOR_SUPPLIED_PID> ^
  --max-scan-bytes 16777216 ^
  --max-matches 32 ^
  --max-regions 256 ^
  --timeout-seconds 10
```

Where `<OPERATOR_SUPPLIED_PID>` is the Windows PID of `rift_x64.exe`, captured by the operator at invocation time via:

```text
tasklist /FI "IMAGENAME eq rift_x64.exe"
```

The local scanner fails closed on:

| Condition | Behaviour |
|---|---|
| `pid <= 0` | raises `RuntimeError: live scan requires an explicit positive PID` |
| Process name ≠ `rift_x64.exe` | adds `target-process-must-be-rift_x64.exe` to `RefusalReasons`; `ExecutionAllowed` = `false` |
| Missing `--experimental-live` | adds `missing---experimental-live` to `RefusalReasons` |
| Missing `--confirm-live-read` | adds `missing---confirm-live-read` to `RefusalReasons` |
| Missing `--execute-live-read` | dry-run only; adds `dry-run-only-no-live-read-requested` |
| Output path outside `Exports/discovery-plan/stage5-live/` | raises `ValueError: scan-live-memory output must stay under Exports/discovery-plan/stage5-live` |

## 3. Exact patterns (loaded from `docs/live-memory-scan-targets.json`)

The scan plan loads three patterns. Their exact `label=hex` forms (the format the local scanner consumes) are:

```text
stage5_step48_at264_index_strip_prefix=00010002000200010003000400050006
stage5_step50_asset_id_ascii_6fc01704d4a509d5=36666330313730346434613530396435
stage5_step50_asset_id_ascii_caa9a88e94ec8db0=63616139613838653934656338646230
```

| Label | Bytes | Hex | Role |
|---|---:|---|---|
| `stage5_step48_at264_index_strip_prefix` | 16 | `00010002000200010003000400050006` | Step 48 positive control (asset-specific, known loaded: `0x7FF78F239751` in `rift_x64.exe` module) |
| `stage5_step50_asset_id_ascii_6fc01704d4a509d5` | 16 | `36666330313730346434613530396435` | Phase 1 primary target — ASCII for the NIF asset ID `6fc01704d4a509d5` |
| `stage5_step50_asset_id_ascii_caa9a88e94ec8db0` | 16 | `63616139613838653934656338646230` | Phase 1 sibling control — ASCII for the NIF asset ID `caa9a88e94ec8db0` |

The full byte pattern table (with Step 50 planning context) is in `docs/live-memory-scan-targets.json`. All three are `candidate-only`, `PromotionStatus: "candidate-only"`, validated against `docs/schemas/live-memory-scan-targets-v1.schema.json`.

## 4. Exact output paths

### 4.1 Local Python scanner

Output paths are auto-generated by `live_memory_scanner.build_live_memory_scan_plan` with a UTC timestamp:

```text
Exports/discovery-plan/stage5-live/live-memory-scan-<UTC>.json
Exports/discovery-plan/stage5-live/live-memory-scan-<UTC>.md
```

The output directory is locked to `Exports/discovery-plan/stage5-live/` (a sibling of the `rift_x64.exe` module path, so it never lands in user-profile paths or near RIFT client files). The directory is gitignored.

### 4.2 RiftReader provider

Step 48 evidence used:

```text
Exports/discovery-plan/stage5-live/phase1-asset-id-<ASSET_ID>.json
```

mirrored for the markdown summary. For Phase 1 we recommend:

```text
Exports/discovery-plan/stage5-live/phase1-asset-id-6fc01704d4a509d5-<UTC>.json
Exports/discovery-plan/stage5-live/phase1-asset-id-6fc01704d4a509d5-<UTC>.md
Exports/discovery-plan/stage5-live/phase1-asset-id-caa9a88e94ec8db0-<UTC>.json
Exports/discovery-plan/stage5-live/phase1-asset-id-caa9a88e94ec8db0-<UTC>.md
```

UTC timestamp format: `YYYYMMDDTHHMMSSZ` (matches scanner convention).

## 5. Scan limits (fixed)

| Limit | Value | Reason |
|---|---:|---|
| `MaxScanBytes` | 16,777,216 (16 MiB) | Scanner default; matches prior Step 48/49 scans. |
| `MaxMatchesPerPattern` | 32 | Scanner default; high enough for natural ref-table duplicates, low enough to bound noise. |
| `MaxRegions` | 256 | Scanner default. |
| `TimeoutSeconds` | 10 | Scanner default; matches prior Step 48/49 scans. |
| `ChunkBytes` | 65,536 (64 KiB) | Scanner default; buffer-overlap window. |

If Phase 1 returns ≥1 hit for the asset ID, Phase 2 keeps the same limits. Phase 3 (bounded triplet probe) will tighten `MaxScanBytes` to 8 MiB and pin the base address from Phase 2 — see `docs/handoffs/2026-06-13-scoped-live-scan-asset-load-proof.md`.

## 6. Operator-approval gate (the actual gate)

This is the explicit checklist the operator must complete and sign off on **before any live read is run**. No live read should be attempted unless every box is checked. This is the most important section of this handoff.

### 6.1 Pre-invocation prerequisites

- [ ] **User has read this handoff and approved the invocation.** Confirmed in chat.
- [ ] **User has read `docs/handoffs/2026-06-13-scoped-live-scan-asset-load-proof.md` and approved the scoped plan.** Confirmed in chat.
- [ ] **User has read `docs/handoffs/2026-06-13-operator-load-state-target-assets.md` and approved the load-candidate strategy.** Confirmed in chat.

### 6.2 Operator-side load state (per §4 of the operator load-state handoff)

- [ ] **Zone recorded** (e.g. "Sanctum", "Meridian", "Tempest Bay") — operator's working notes.
- [ ] **Subzone / area recorded** (e.g. "The Vault", "City Hub") — operator's working notes.
- [ ] **Character faction and name recorded** (e.g. "Guardian / redacted") — operator's working notes, never committed.
- [ ] **Approximate in-game coordinates recorded** (or "not visible" if the HUD hides them).
- [ ] **Approximate target recorded** (description of the `diffuse_blank`-textured placeable being approached, or the in-game waypoint/landmark).
- [ ] **Distance to target recorded** (estimated in-game meters; "near", "5-10m", ">20m", etc.).
- [ ] **Visual / HUD signal recorded** (cursor highlight, nameplate, `/target` confirmation, addon signal).
- [ ] **Wall-clock capture time recorded** (UTC) for the start of the scan window.

### 6.3 RIFT process state

- [ ] **`rift_x64.exe` is running and stable** (not in crash recovery, not in mid-load, not shutting down).
- [ ] **PID captured** via `tasklist /FI "IMAGENAME eq rift_x64.exe"` and pasted into a working-note (never committed).
- [ ] **Only one `rift_x64.exe` process exists** (zero or multiple candidates fail closed; the local scanner requires an explicit positive PID).
- [ ] **Character is not in combat** and **not in a zone transition** (load state is stable).
- [ ] **No addon is actively loading or unloading assets** during the scan window (avoid transient load churn).

### 6.4 Workspace state

- [ ] **Generated-output guard passes** — `python scripts/rift_workflow.py generated-output-guard` returns clean. (Run this immediately before the live read.)
- [ ] **No tracked file has uncommitted changes that would be lost** — `git status` is clean for files the operator cares about.
- [ ] **Local `scan-live-memory` dry-run passes** — `python scripts/rift_workflow.py scan-live-memory --live-pattern-file docs/live-memory-scan-targets.json --list-json` returns `ExecutionAllowed: false` and `RefusalReasons: ["dry-run-only-no-live-read-requested"]` (no other refusal reasons). This proves the plan and the four safety flags are wired correctly; the only thing changing at invocation time is `--execute-live-read` plus the actual `--pid`.
- [ ] **RiftReader is available** (if using the preferred provider) — `scripts/run-reader.cmd --help` exits 0; `--scan-string` and `--scan-encoding ascii` are present in the help output.
- [ ] **The four safety flags are present in the command** — `--execute-live-read --experimental-live --confirm-live-read --pid <PID>`. The local scanner fails closed if any is missing.
- [ ] **Output directory is `Exports/discovery-plan/stage5-live/`** and is gitignored (`grep -F "Exports/discovery-plan/stage5-live" .gitignore` returns the ignore rule).

### 6.5 Safety confirmations (per `docs/live-memory-readonly-safety-boundary.md`)

- [ ] **Read-only** — no writes, no DLL injection, no remote threads, no hooks.
- [ ] **No input sent to the game** during the scan.
- [ ] **No full process memory dump** requested.
- [ ] **No committed live reports** — all outputs go under ignored `Exports/discovery-plan/stage5-live/`.
- [ ] **Privacy preserved** — no chat text, account names, or local user-profile paths in any committed record.
- [ ] **Tests did not attach to a live process** — `python scripts/test_live_memory_scanner.py` was run with `FixtureProcessReader` only.

### 6.6 Post-invocation

- [ ] **Output JSON + Markdown written** under `Exports/discovery-plan/stage5-live/`.
- [ ] **Output reviewed** for sanity (no full dumps, no user paths, schema-valid JSON).
- [ ] **Per-pattern match counts recorded** in the operator's working notes.
- [ ] **Phase 2 decision recorded** (proceed to Phase 2 if asset ID found; close negative if 0 hits).
- [ ] **`git status` checked** to confirm no live reports were accidentally staged.

### 6.7 Approval signature

When all boxes above are checked, the operator types this single line into the chat before invoking the live read:

```text
APPROVED: Phase 1 live read authorised against rift_x64.exe PID <PID>; gate §6.1–§6.6 complete.
```

No live read should be attempted without this explicit approval line.

## 7. What to do with the result

### 7.1 ≥1 hit for at least one of the two asset IDs

```text
Phase 1 outcome: PASS
Record the address(es), the surrounding region, and proceed to Phase 2.
Phase 2 re-uses the existing Step 48 @264 prefix target and checks
co-residence with the asset ID address. See §7 of the scoped-scan handoff.
```

### 7.2 0 hits for both asset IDs

```text
Phase 1 outcome: FAIL (close negative for this load state)
The target asset is not loaded in the current live session.
Do not run Phase 2 or Phase 3.
Capture the result, close negative for this load state, and re-test
in a different load condition (different zone, or a different
diffuse_blank placeable).
```

### 7.3 ≥1 hit for one ID but not the other

```text
Phase 1 outcome: PARTIAL
The loaded asset table is asymmetric. Treat as Phase 1 PASS for the
hit ID, and treat the other as a separate load-state check.
Both IDs should normally load together (they are adjacent entries
in the same archive, assets.053 1187/1188, with identical scene
graph). An asymmetric result is diagnostic — record it and
investigate before proceeding.
```

## 8. Hard prohibitions (carried forward)

Per `docs/live-memory-readonly-safety-boundary.md` "Hard prohibitions":

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

## 9. Status

- Handoff: **DRAFT — awaiting operator approval per §6.7**.
- Tracked-file changes: **none** (planning only).
- Live read executed: **false** (this handoff does not execute; the operator executes on approval).
- Step 49 status: **unchanged** (still `closed-negative-current-live-state`).
- Step 50 final handoff: **unchanged** (no parser/export promotion).
- Scoped scan plan: **unchanged** from `docs/handoffs/2026-06-13-scoped-live-scan-asset-load-proof.md`.
- Operator load state: **undocumented** (operator must complete §4 of the operator load-state handoff before approval).
- RiftReader flag-name verification: **PASS** (2026-06-13 — `run-reader.cmd --help` confirms `--scan-string` for ASCII string scans; `--scan-encoding ascii|utf16|both` is optional and defaults to `ascii`; `--scan-module-pattern` is the correct flag for byte/AOB scans).
- Phase 2 invocation: **fully specified** in `docs/handoffs/2026-06-13-phase2-co-location-at264-invocation.md` (downstream gate; re-uses the Step 48 @264 prefix target with no new manifest entries; co-location is operator-side cross-reference, not a scanner-level region constraint).
- Phase 3 invocation: **fully specified** in `docs/handoffs/2026-06-13-phase3-bounded-triplet-invocation.md` (downstream gate; consumes v0..v3 from the offline decode report, post-filters match addresses against the Phase 2 anchor; represents the closure branch of the scoped-scan plan).
- **Full 3-phase scoped plan status:** Phase 0 dry-run PASS; Phase 1 invocation DRAFT; Phase 2 invocation DRAFT; Phase 3 invocation DRAFT. All three invocation handoffs are ready for operator review; no live read is executed until the operator types the §6.7 (Phase 1) / §7.7 (Phase 2) / §7.7 (Phase 3) APPROVED lines.
