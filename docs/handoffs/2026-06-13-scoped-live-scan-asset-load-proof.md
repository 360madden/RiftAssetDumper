# Scoped live-memory scan plan — target asset/load proof

Date: 2026-06-13
Author: Buffy (planning only; no live read executed)

## Why this plan exists

Step 49 closed negative (`Step49ClosureMode: closed-negative-current-live-state`,
`docs/live-memory-step49-status.json`) because expected static `mesh297 v0-v3`
triplets produced **0 hits** in both bounded candidate regions and a full-process
triplet batch. The status file flags the underlying gap explicitly:

```text
TargetAssetLoadEvidence: "not-established"
```

The Step 50 final handoff
(`docs/handoffs/2026-05-26-final-50-step-session.md`) recommends the same path
this plan formalises:

> "do not repeat broad live scans for the same static triplets until target
> asset/load evidence and representation are proven."

A full-process float3 triplet scan cannot succeed until two preconditions are
established:

1. **The target NIF asset is loaded in the live process** (a string/ID-level
   signature is resident in memory).
2. **The asset's geometry representation is raw contiguous static float3**
   (not delta-encoded, half-float, streamed, swizzled, or compressed).

Step 48 already proved the second-related signal for the `@264/#15` topology
(`step48_at264_index_strip_prefix` was found at `0x7FF78F239751` in
`rift_x64.exe`). What it did **not** prove is that the target mesh's host asset
is currently loaded as a live geometry object. That is the gap this plan closes
first.

## Scope (and non-scope)

**In scope**

- Read-only, dry-run-only planning for a 3-phase scoped live scan.
- New candidate-only target manifest entries that pre-declare the asset-load
  proof patterns.
- A dry-run command that validates the plan against
  `docs/schemas/live-memory-scan-plan-v1.schema.json` without opening a process.

**Out of scope (this document)**

- Any actual live process read. That requires a separate
  `--execute-live-read --experimental-live --confirm-live-read --pid <PID>` gate
  call from the human operator and the prerequisites below.
- Any change to `Program.cs` or the parser/export behaviour.
- Any change to `docs/live-memory-step48-status.json` or
  `docs/live-memory-step49-status.json` (those are closed results).
- Any new RiftReader work — this plan only uses the existing
  `RiftReader.Reader` and the local `scan-live-memory` scanner scaffold.

## Preconditions (must be true before any live read)

| # | Precondition | Source of truth |
|---|---|---|
| 1 | User has read this handoff and approved the scoped plan. | This document. |
| 2 | RIFT client is in a known player-loaded state (logged in, in-zone, not at character select). | Operator. |
| 3 | A specific NIF asset has been selected as the target. The default proposal is `6fc01704d4a509d5` mesh#6 (the proven @264/#15 topology anchor with 2 sibling confirmations). | `docs/discovery-plan-50.md` Step 48; `docs/current-status.md` @264 section. |
| 4 | The exact PID of `rift_x64.exe` is captured. The local scanner fails closed on `pid <= 0` or on a process name other than `rift_x64.exe`. | `scripts/live_memory_scanner.py` `build_live_memory_scan_plan`. |
| 5 | Generated-output guard passes (`scripts/rift_workflow.py` runs it before any workflow command). | `scripts/rift_workflow_utils.py`. |
| 6 | No test, CI, or fixture attaches to a live process. | `scripts/test_live_memory_scanner.py` (fixture-only). |

The hard prohibitions in
`docs/live-memory-readonly-safety-boundary.md` remain in force: no writes, no
DLL injection, no remote threads, no hooks, no full process dump, no commits
of generated live reports.

## Phase 0 — Dry-run plan (no live read)

The dry-run validates the plan against the schema and prints the exact
patterns, limits, and output paths. It does **not** open a process.

```text
python scripts/rift_workflow.py scan-live-memory \
  --live-pattern-file docs/live-memory-scan-targets.json \
  --list-json
```

The current manifest (`docs/live-memory-scan-targets.json`) contains only the
Step 48 @264 prefix target. The scoped plan adds three new candidate-only
targets (proposed schema below) so a single dry-run validates the full
asset-load proof ladder.

## Phase 1 — Asset ID string scan (proves the target asset is loaded)

The target NIF asset ID is a 16-character lowercase hex string. The RIFT client
keeps a reference table for currently loaded NIF assets (asset manager / object
table). When the target asset is loaded, the literal ASCII byte sequence of
its ID will appear in process memory.

Proposed target entry (to be added to
`docs/live-memory-scan-targets.json`):

| Field | Value |
|---|---|
| `Label` | `stage5_step50_asset_id_ascii_6fc01704d4a509d5` |
| `Step` | 50 |
| `Purpose` | Asset-load proof: detect the ASCII 16-byte NIF asset ID in live process memory. If this returns 0 hits, the target asset is not loaded; do not run Phase 3. |
| `Hex` | `36666330313730346434613530396435` (ASCII for `6fc01704d4a509d5`) |
| `ByteLength` | 16 |
| `SourceEvidence` | `docs/discovery-plan-50.md` Step 48; `docs/live-memory-step48-status.json`; `docs/handoffs/2026-05-26-final-50-step-session.md` (Next action 4). |
| `PromotionStatus` | `candidate-only` |
| `RecommendedDryRunCommand` | `python scripts/rift_workflow.py scan-live-memory --live-pattern-file docs/live-memory-scan-targets.json --list-json` |

**Sibling confirmation target** (also Step 50): the proven sibling
`caa9a88e94ec8db0` has the same mesh#6/@264/#15 topology
(`docs/current-status.md` @264 section). Its ASCII ID
(`63 61 61 39 61 38 38 65 39 34 65 63 38 64 62 30`) serves as a second positive
control.

**Interpretation rule:**

- 0 hits for either ID → the target asset is **not loaded** in the current
  live session. Do not run Phase 2 or Phase 3. Capture the result, close
  negative for this load state, and re-test in a different load condition
  (e.g. visit a zone known to use this asset).
- ≥1 hit → the asset is **likely loaded**. Record the address(es), the
  surrounding region, and proceed to Phase 2.

Limits for Phase 1 (the existing scanner defaults are appropriate; they are
fail-closed and bounded):

| Limit | Value | Reason |
|---|---:|---|
| `MaxScanBytes` | 16 MiB | The full 16-byte ASCII ID scan fits well under this; matches the scanner default. |
| `MaxMatchesPerPattern` | 8 | At most a handful of reference-table entries should match; a large count is a noise signal. |
| `MaxRegions` | 256 | Scanner default; bounds the region walk. |
| `TimeoutSeconds` | 10 | Scanner default; bounds the wall clock. |

## Phase 2 — Co-located @264 prefix scan (proves the asset's geometry data is resident)

Once Phase 1 finds the target asset ID at one or more addresses, the next
question is whether that address's memory region also contains the asset's
geometry data. The Step 48 @264/#15 index prefix
(`00 01 00 02 00 02 00 01 00 03 00 04 00 05 00 06`) is asset-specific — the
prefix is determined by the mesh's vertex connectivity, which is unique per
NIF. Its presence in the same region as the asset ID is strong evidence the
geometry is loaded.

This phase reuses the existing Step 48 target
(`stage5_step48_at264_index_strip_prefix`) without modification.

**Interpretation rule:**

- @264 prefix found within ±4 MiB of any Phase 1 hit → the asset's geometry is
  **co-resident**. Proceed to Phase 3.
- @264 prefix found but not co-located with the Phase 1 hit → the @264
  pattern may belong to a different asset (the 16-byte prefix is short
  enough to collide). Record both addresses and consider the asset-load
  evidence weak. Do not run Phase 3.
- @264 prefix not found → treat as load failure. Capture and close.

## Phase 3 — Bounded triplet probe (only after Phases 1+2 confirm)

**Only run this phase if Phases 1 and 2 both confirm the asset and its @264
prefix are co-resident.** This converts a full-process 4-vertex triplet scan
into a tightly bounded scan around the proven geometry address.

Approach:

1. From Phase 2, take the address `A` of the co-located @264 prefix.
2. Compute the bounded region: `[A - 4 MiB, A + 4 MiB]` (8 MiB total).
3. Use the RiftReader generic triplet scan:
   `--scan-float-triplet <x,y,z> --scan-region-base <address> --scan-region-size <bytes>`
   with one of the four known vertices from the static decode report for the
   target mesh.
4. If the bounded triplet probe finds the expected vertex, the representation
   hypothesis is **confirmed raw contiguous static float3**. Capture the
   results and update `docs/live-memory-step49-status.json` with a new
   `BoundedExpectedStaticBatchHitCount` value.
5. If the bounded triplet probe still finds 0 hits, the representation
   hypothesis is **rejected** for the current live state. Capture and close.

Limits for Phase 3 (tighter than the scanner defaults to enforce the
"bounded, not full-process" goal):

| Limit | Value | Reason |
|---|---:|---|
| Region base | `<A - 4 MiB>` | From Phase 2 result. |
| Region size | `8 MiB` | Tighter than the 16 MiB scanner default. |
| Max scan bytes | `8 MiB` | Matches region size; no overshoot. |
| Max matches | 16 | Same as Step 49 baseline. |
| Timeout | 10 s | Same as Step 49 baseline. |

## Why the phased design closes the Step 49 gap

| Gap in Step 49 | How this plan closes it |
|---|---|
| `TargetAssetLoadEvidence: not-established` | Phase 1 explicitly proves asset load via the 16-byte ASCII asset ID scan. |
| `mesh297 v0` 0 hits in bounded region | Phase 3 is bounded to the Phase 2-anchored region, not full-process. |
| `mesh297 v0-v3` 0 hits full-process batch | The full-process scan is replaced by a bounded scan gated on Phases 1+2. |
| Unclear representation hypothesis | Phase 2 (co-resident @264) is a positive-control representation proof. If the prefix is in the asset's region, raw float3 becomes a reasonable hypothesis. If not, the representation is different and the plan should close negative without a triplet scan. |

The plan does **not** claim that a positive Phase 3 result promotes the
parser/export behaviour. The Step 50 final handoff is already written; this
plan produces new evidence that, combined with the offline position-source
work, can be reviewed before any future promotion consideration.

## Proposed manifest diff (do not write yet — review first)

The current `docs/live-memory-scan-targets.json` is a tracked file. The
following diff is proposed but **not** written by this handoff. Review and
explicit approval are required before any tracked file is modified.

```diff
 {
   "SchemaVersion": "live-memory-scan-targets/v1",
   "CandidateOnly": true,
   "LiveReadExecuted": false,
   "Targets": [
     {
       "Label": "stage5_step48_at264_index_strip_prefix",
       "Step": 48,
       "Purpose": "Dry-run target for the @264/#15 UInt16BE degenerate-bridge index strip prefix from the original 50-step plan.",
       "Hex": "00010002000200010003000400050006",
       "ByteLength": 16,
       "SourceEvidence": [
         "docs/discovery-plan-50.md Step 48",
         "docs/current-status.md @264/#15 raw-zero-based degenerate-bridge strip evidence",
         "docs/live-memory-readonly-safety-boundary.md"
       ],
       "PromotionStatus": "candidate-only",
       "RecommendedDryRunCommand": "python scripts/rift_workflow.py scan-live-memory --live-pattern-file docs/live-memory-scan-targets.json --list-json"
+    },
+    {
+      "Label": "stage5_step50_asset_id_ascii_6fc01704d4a509d5",
+      "Step": 50,
+      "Purpose": "Asset-load proof: detect the ASCII 16-byte NIF asset ID for the proven @264/#15 topology anchor mesh in live process memory. If this returns 0 hits, the target asset is not loaded; do not run Phases 2 or 3.",
+      "Hex": "36666330313730346434613530396435",
+      "ByteLength": 16,
+      "SourceEvidence": [
+        "docs/discovery-plan-50.md Step 48",
+        "docs/live-memory-step48-status.json",
+        "docs/current-status.md @264/#15 confirmed-sibling section"
+      ],
+      "PromotionStatus": "candidate-only",
+      "RecommendedDryRunCommand": "python scripts/rift_workflow.py scan-live-memory --live-pattern-file docs/live-memory-scan-targets.json --list-json"
+    },
+    {
+      "Label": "stage5_step50_asset_id_ascii_caa9a88e94ec8db0",
+      "Step": 50,
+      "Purpose": "Sibling positive control: detect the ASCII 16-byte NIF asset ID for the proven @264/#15 sibling mesh in live process memory. Confirms the load table contains mesh#6 assets and the asset-id scan is not a single-asset coincidence.",
+      "Hex": "63616139613838653934656338646230",
+      "ByteLength": 16,
+      "SourceEvidence": [
+        "docs/discovery-plan-50.md Step 48",
+        "docs/live-memory-step48-status.json",
+        "docs/current-status.md @264/#15 confirmed-sibling section"
+      ],
+      "PromotionStatus": "candidate-only",
+      "RecommendedDryRunCommand": "python scripts/rift_workflow.py scan-live-memory --live-pattern-file docs/live-memory-scan-targets.json --list-json"
     }
   ]
 }
```

The two new targets are sibling-scoped: both have the @264/#15 topology, both
have been confirmed via offline static decode, and both are the strongest
asset-load signal available before committing to a bounded triplet probe.

## Decision tree (after the live read is authorised)

```text
Phase 1 dry-run
  └─ Plan schema valid? ── no ─> Fix manifest; do not execute.
                              │
                             yes
                              ▼
Phase 1 live read
  ├─ 0 hits for both asset IDs ───────────> Close negative (asset not loaded).
  │                                          Capture result; revisit in different zone.
  ├─ ≥1 hit for one or both asset IDs ────> Record address(es); proceed to Phase 2.
  └─ Plan refusal reason (pid, flags) ───> Resolve operator-side gate; retry.
                                          │
                                          ▼
Phase 2 (re-uses Step 48 target, no new dry-run needed)
  ├─ @264 prefix co-resident (±4 MiB of Phase 1 hit) ─> Record co-resident address A; proceed to Phase 3.
  ├─ @264 prefix found but not co-resident ────────────> Close weak-positive (different asset, representation unproven).
  └─ @264 prefix not found ───────────────────────────> Close negative (representation unproven).
                                          │
                                          ▼
Phase 3 (bounded triplet probe around A)
  ├─ ≥1 triplet hit for an expected vertex ─> Representation hypothesis CONFIRMED.
  │                                            Capture result; propose a separate decision-record handoff before any parser/export change.
  └─ 0 triplet hits ───────────────────────> Representation hypothesis REJECTED.
                                               Close negative; do not repeat without a different representation hypothesis.
```

## Open questions for the operator

1. **Zone selection.** Which in-game zone is most likely to have either
   `6fc01704d4a509d5` or `caa9a88e94ec8db0` loaded? The Step 48 evidence did
   not record the load state — only that the @264 prefix exists in the
   `rift_x64.exe` module pattern.
2. **Asset provenance.** Both IDs were derived from a copied archive probe
   (Step 48 / `@264` family). If the live load is a streaming-only asset, the
   ASCII ID may not be in resident memory. An alternate load proof (e.g. the
   archive chunk header bytes) may be needed.
3. **RiftReader availability.** The plan assumes
   `C:/RIFT MODDING/RiftReader/scripts/run-reader.cmd` is the live provider
   and that the existing `scan-live-memory` Python scaffold is the local
   dry-run/live-read path. If the provider changes, the dry-run command and
   output schema stay the same; only the live execution wrapper changes.

## Status

- Handoff: **DRAFT — awaiting operator review**.
- Tracked-file changes: **none** (manifest diff shown for review only).
- Live read executed: **false** (Phase 0 dry-run only, not run by this handoff).
- Step 49 status: **unchanged** (still `closed-negative-current-live-state`).
- Step 50 final handoff: **unchanged** (no parser/export promotion).
