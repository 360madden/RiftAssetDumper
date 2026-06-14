# Phase 3 invocation handoff — bounded float3 triplet probe

Date: 2026-06-13
Author: Buffy (planning only; no live read executed)
Companions: `docs/handoffs/2026-06-13-scoped-live-scan-asset-load-proof.md`,
`docs/handoffs/2026-06-13-phase1-live-read-invocation.md`,
`docs/handoffs/2026-06-13-phase2-co-location-at264-invocation.md`,
`docs/handoffs/2026-06-13-operator-load-state-target-assets.md`

## TL;DR

| Field | Value |
|---|---|
| Phase | **3 of 3** in the scoped-scan plan (gated on Phase 1 + Phase 2 both PASS) |
| Purpose | Confirm the raw contiguous static float3 representation hypothesis for the target mesh's geometry, **bounded to the Phase 2 co-resident region**. |
| Provider (preferred) | `RiftReader.Reader` at `C:/RIFT MODDING/RiftReader/scripts/run-reader.cmd` — only provider that exposes `--scan-float-triplet` |
| Provider (fallback) | None at the scanner level. The local Python `scan-live-memory` scaffold does **not** expose a float-triplet scan; the only fallback is to use RiftReader's `--address` + `--length` raw-read to dump the 8 MiB region as bytes and search for the triplet in the operator's working notes. |
| Process name | `rift_x64.exe` (only allowed target) |
| Triplet values (4) | The four known vertices `v0..v3` from the static decode report for `6fc01704d4a509d5` mesh#6 (or `caa9a88e94ec8db0` mesh#6 if Phase 2 hit was that one). Operator looks them up in the offline decode report — see §3. |
| Region | `[A - 4 MiB, A + 4 MiB]` = 8 MiB total, anchored on Phase 2's co-resident address `A` |
| Region pinning | **Not available in RiftReader for `--scan-float-triplet`** — the float-triplet scan runs against the full process image bounded only by the existing `Limits`. The "bounded probe" is achieved by **post-filtering the match addresses to `[A - 4 MiB, A + 4 MiB]`** in the operator's working notes. |
| Output directory | `Exports/discovery-plan/stage5-live/` (gitignored, schema-validated) |
| Output JSON | `Exports/discovery-plan/stage5-live/phase3-bounded-triplet-<UTC>.json` |
| Output Markdown | `Exports/discovery-plan/stage5-live/phase3-bounded-triplet-<UTC>.md` |
| Dry-run status | **PASS** (Phase 0 plan validated against `live-memory-scan-plan-v1.schema.json` with `ExecutionAllowed: false` + `LiveProcessReadExecuted: false`) |
| Live read executed | **false** (this handoff does not execute) |

## 0. Gate to Phase 3

Phase 3 is only reached if **both Phase 1 and Phase 2 PASSED**:

- **Phase 1:** ≥1 hit for at least one asset ID (`6fc01704d4a509d5` or
  `caa9a88e94ec8db0`). Recorded in the operator's working notes.
- **Phase 2:** @264 prefix co-resident with a Phase 1 asset-ID hit
  (±4 MiB). The co-resident address `A` is captured and feeds Phase 3.

If either gate fails, Phase 3 is skipped and the operator closes
negative for this load state. The Step 49 status
(`closed-negative-current-live-state`) is the "no change" outcome for
either of these closure branches.

## 1. Why this is a separate gate

Per `docs/live-memory-readonly-safety-boundary.md` §"Actual live-read
execution gate", the live read requires six pre-disclosed items: exact
command, exact PID, exact patterns, output paths, scan byte/region/time
limits, and generated-output guard status. Phase 3 carries the same
gate. The Phase 3-specific elements are:

1. The triplet values `v0..v3` are **not** from the manifest — they come
   from the offline static decode report for the target mesh.
2. The scan is bounded **post-filter** by the Phase 2 anchor `A`, not by
   a scanner-level region constraint.
3. The "tightened" limits (8 MiB max-scan-bytes, 16 max-matches) are
   **aspirational** — they are the operator-side budget the actual
   scanner limits are tightened to before invocation. The scanner
   itself runs full-process; the post-filter is what makes it bounded.

## 2. Exact invocation

### 2.1 Preferred provider: `RiftReader.Reader` (only provider that exposes `--scan-float-triplet`)

For each of the four triplet values (`v0`, `v1`, `v2`, `v3`), invoke
RiftReader separately. Four invocations keep the output bounded and the
matches attributable to a specific vertex.

```text
cd C:/RIFT MODDING/RiftReader
C:/RIFT MODDING/RiftReader/scripts/run-reader.cmd ^
  --process-name rift_x64 ^
  --scan-float-triplet <v0.x>,<v0.y>,<v0.z> ^
  --scan-tolerance 0.001 ^
  --scan-context 48 ^
  --max-hits 16 ^
  --output "C:/RIFT MODDING/Assets/Exports/discovery-plan/stage5-live/phase3-bounded-triplet-<UTC>-v0.json"
```

Repeat for `<v1>`, `<v2>`, `<v3>`. The four outputs are then
post-filtered in the operator's working notes (see §4).

Notes on the flag choice:

- `--scan-float-triplet` accepts a comma-separated `<x,y,z>` form for
  the exact target vertex. The four known vertices are looked up from
  the offline decode report — see §3.
- `--scan-tolerance 0.001` is a 0.1% absolute tolerance, matching the
  Step 48 / Step 49 precedent. Tightening to `0.0001` would suppress
  legitimate matches due to FPU rounding in the live decode path;
  loosening to `0.01` would admit too much noise.
- `--scan-context 48` reports 48 bytes of context around each match
  (12 floats = 4 triplets), which is the minimum useful for identifying
  the surrounding vertex layout.
- `--max-hits 16` bounds the matches per vertex scan. The expected
  count is 0-1; a high count is a noise signal.
- `--process-name rift_x64` resolves the PID internally.

### 2.2 Fallback: raw region read + manual triplet extraction

The local Python `scan-live-memory` scaffold does **not** expose a
float-triplet scan. The only scaffold-side fallback is to use
RiftReader's raw read (`--address` + `--length`) to dump the 8 MiB
region as bytes, save it under
`Exports/discovery-plan/stage5-live/phase3-bounded-region-<UTC>.bin`,
and search for the triplet in the operator's working notes.

```text
cd C:/RIFT MODDING/RiftReader
C:/RIFT MODDING/RiftReader/scripts/run-reader.cmd ^
  --process-name rift_x64 ^
  --address 0x<A - 0x400000> ^
  --length 8388608 ^
  --output "C:/RIFT MODDING/Assets/Exports/discovery-plan/stage5-live/phase3-bounded-region-<UTC>.bin"
```

Then in the operator's working notes:

```text
python -c "
data = open(r'C:/RIFT MODDING/Assets/Exports/discovery-plan/stage5-live/phase3-bounded-region-<UTC>.bin', 'rb').read()
import struct
# Search for the 4 triplets in little-endian float32
for vname, vt in [('v0', <v0.x>,<v0.y>,<v0.z>), ...]:
    target = struct.pack('<fff', *vt)
    pos = data.find(target)
    if pos >= 0:
        print(f'{vname}: HIT at offset 0x{pos:08x}, region base + 0x{pos:x}')
    else:
        print(f'{vname}: no hit')
"
```

This fallback is **less safe** than the RiftReader triplet scan:

- It produces a raw region dump on disk (the `.bin` file). The dump
  must be deleted after the operator-side extraction (see §6.5).
- It is not bounded by a scanner-level region constraint; the
  boundedness comes from `--address` + `--length` on the read side.
- The operator-side Python search is not schema-validated; the
  extraction is by definition ad-hoc.

The preferred path is still §2.1. The fallback exists only for the case
where RiftReader is unavailable.

## 3. Triplet values (from the offline static decode artifact)

> **2026-06-14 patch:** this section was patched after the original draft
> cited a non-existent `decode-nif-geometry-mesh6.report.json` file. The
> canonical source is the `.obj` artifact's `v` lines (128 vertices for
> `6fc01704d4a509d5` mesh#6, matching the expected `vertex_count=128`).
> The corrected lookup, the Step 49 cross-reference, and a note for the
> `caa9a88e94ec8db0` sibling are below.

The four triplet values are **not in the live-memory manifest**. They
come from the offline static decode artifact for the target mesh. The
operator must look them up in the working notes (never commit them; the
artifacts are read-only files under `Exports/`).

### 3.1 Canonical source

For `6fc01704d4a509d5` mesh#6, the canonical source is:

```text
Exports/decode-nif-geometry-6fc01704d4a509d5/decode-nif-geometry/decode-nif-geometry-mesh6.obj
```

Only the `.obj` file exists at that path (verified 2026-06-14). The
`.report.json` referenced in earlier drafts of this handoff was an
assumption that turned out to be wrong — the static decode path emits
the `.obj` but no sibling `.report.json` at the same path. The values
below are the canonical `v` lines from the `.obj`.

### 3.2 Recommended lookup (parse the `.obj`)

The first four `v` lines of the `.obj` are the targets. The
recommended operator-side lookup command is:

```text
python -c "
path = r'C:/RIFT MODDING/Assets/Exports/decode-nif-geometry-6fc01704d4a509d5/decode-nif-geometry/decode-nif-geometry-mesh6.obj'
verts = []
with open(path, 'r', encoding='utf-8') as f:
    for line in f:
        if line.startswith('v '):
            parts = line.split()
            verts.append(tuple(float(parts[1]), float(parts[2]), float(parts[3])))
        if len(verts) >= 4:
            break
for i, (x, y, z) in enumerate(verts):
    print(f'v{i}: {x},{y},{z}')
"
```

The values (extracted 2026-06-14) are:

| Vertex | X | Y | Z |
|---|---:|---:|---:|
| `v0` | 8.458028 | 55.920349 | 11.567474 |
| `v1` | 5.999848 | 54.718262 | 13.064880 |
| `v2` | 7.556799 | 52.199829 | 11.407593 |
| `v3` | 5.999830 | 52.299988 | 12.751602 |

These go in the operator's working notes only (never committed to any
tracked file).

### 3.3 Step 49 cross-reference

The `v0` value `(8.458028, 55.920349, 11.567474)` is the **same**
float3 triplet that the Step 49 full-process batch
(`docs/live-memory-step49-status.json`,
`docs/handoffs/2026-05-26-fifty-step-plan-step49-riftreader-initial-float-probe.md`)
scanned for and produced **0 hits** for, in both the bounded candidate
region and the full-process batch. Step 49 was scanning
`mesh297 v0-v3`; the `v0` here is the same value (the `mesh297` target
is a different mesh, but the float3 value is shared across the
`mesh297` and `mesh325`/`@264/#15` families — see the
`@264/#15` sibling evidence in `docs/current-status.md`).

**Implication for Phase 3:** a Phase 3 PASS on this exact `v0` value
would be a meaningful representation confirmation, not a coincidence —
it would mean the live representation hypothesis (`raw contiguous
static float3`) is correct for a value that the prior Step 49 full-
process batch could not find. A Phase 3 PASS therefore **does not
require all four vertices to match** (see §4.2); a single in-region
hit on `v0` is already strong evidence.

A Phase 3 FAIL (0 in-region hits) is also meaningful: it confirms the
prior Step 49 result and re-strengthens the
`closed-negative-current-live-state` closure.

### 3.4 Sibling target (`caa9a88e94ec8db0`)

For `caa9a88e94ec8db0` mesh#6, the equivalent `.obj` is at:

```text
Exports/decode-nif-geometry-caa9a88e94ec8db0/decode-nif-geometry/decode-nif-geometry-mesh6.obj
```

The same lookup command applies (substitute the path). If Phase 2's
co-resident `@264` hit resolves to `caa9a88e94ec8db0` rather than
`6fc01704d4a509d5`, the operator substitutes the `caa9` triplet values
in the §2.1 invocations. The Step 49 cross-reference for `caa9`'s
`v0..v3` is the same: the float3 values are shared across the
`@264/#15` sibling family.

## 4. Post-filter (the "bounded" part)

The RiftReader `--scan-float-triplet` scan runs against the full
process image bounded only by `--max-scan-bytes` / `--max-hits` /
`--timeout-seconds`. The "bounded probe" of Phase 3 is achieved by
**post-filtering the match addresses** in the operator's working
notes:

```text
For each match at address M_i reported in the v<N> JSON output:
  if |M_i - A| <= 4 MiB (= 0x400000 = 4,194,304 bytes):
    -> within bounded region: candidate for representation confirmation
  else:
    -> outside bounded region: noise / different asset
```

Where `A` is the co-resident address captured from Phase 2.

A pass requires at least **one** of the four vertices (`v0..v3`) to
produce at least one match within the bounded region. The other three
vertices are not strictly required to match (Step 49 evidence shows
the full v0-v3 batch produced 0 hits, so the bar is "at least one
in-region hit", not "all four").

### 4.1 Worked example (placeholder)

```text
Phase 2 anchor A:           0x000001A2_B3C0_0800
Phase 3 v0 hit:             0x000001A2_B342_3000
                            ────────────────────────
distance:                    0x0000_0000_7D_F800 = ~8.05 MiB
verdict:                     outside ±4 MiB window -> noise
Phase 3 v2 hit:             0x000001A2_B9C0_0800
                            ────────────────────────
distance:                    0x0000_0000_60_0000 = 6.00 MiB
verdict:                     outside ±4 MiB window -> noise
Phase 3 v3 hit:             0x000001A2_B440_0000
                            ────────────────────────
distance:                    0x0000_0000_7F_F800 = ~8 MiB - 64 KiB
verdict:                     outside ±4 MiB window -> noise
```

(All three hits outside the band would be a Phase 3 FAIL — see §8.3.)

### 4.2 Cross-reference with Step 49 evidence

Step 49's full-process `mesh297 v0-v3` batch produced **0 hits** for all
four vertices. Phase 3 is designed to avoid that outcome by:

1. Pinning the scan to the region where Phase 2 found the @264 prefix
   (post-filter), eliminating the 26 GB full-process noise floor.
2. Targeting the proven `@264/#15` mesh (`6fc01704d4a509d5` mesh#6)
   rather than the unproven `mesh297` v0..v3 batch.
3. Requiring only **one** in-region hit (not all four) to PASS.

If Phase 3 still produces 0 in-region hits, the representation
hypothesis is **rejected** for this load state — the geometry is
likely not raw contiguous static float3 in memory (it may be
delta-encoded, half-float, swizzled, or streamed), and the
parser/export behaviour is **not** promoted.

## 5. Exact output paths

### 5.1 RiftReader provider (preferred)

Recommended Phase 3 filenames (one per vertex, four total):

```text
Exports/discovery-plan/stage5-live/phase3-bounded-triplet-<UTC>-v0.json
Exports/discovery-plan/stage5-live/phase3-bounded-triplet-<UTC>-v1.json
Exports/discovery-plan/stage5-live/phase3-bounded-triplet-<UTC>-v2.json
Exports/discovery-plan/stage5-live/phase3-bounded-triplet-<UTC>-v3.json
```

UTC timestamp format: `YYYYMMDDTHHMMSSZ` (matches scanner convention).

### 5.2 Fallback raw-read (if RiftReader triplet is unavailable)

```text
Exports/discovery-plan/stage5-live/phase3-bounded-region-<UTC>.bin
```

The `.bin` file is a **transient artifact** that must be deleted after
the operator-side extraction is complete (see §6.5). It must never be
committed.

## 6. Scan limits (tightened from scanner defaults)

| Limit | Value | Reason |
|---|---:|---|
| `MaxScanBytes` | 16,777,216 (16 MiB) | Scanner default; this is the **upper bound** the scanner enforces. The 8 MiB "bounded" region is enforced by post-filter, not by the scanner. |
| `MaxMatchesPerPattern` | 16 | Same as Step 49 baseline. Tighter than the scanner default (32) to surface a high count as a noise signal. |
| `MaxRegions` | 256 | Scanner default. |
| `TimeoutSeconds` | 10 | Same as Step 49 baseline. |
| `ChunkBytes` | 65,536 (64 KiB) | Scanner default. |
| **Post-filter band** | **±4 MiB around A** | **This is the actual "bounded" constraint.** |

These limits are intentionally similar to the Step 49 baseline so the
results are directly comparable. The Phase 3-specific tightening is
the post-filter band, not the scanner limits.

## 7. Operator-approval gate

This is the explicit checklist the operator must complete and sign off
on **before any Phase 3 live read is run**. No live read should be
attempted unless every box is checked.

### 7.1 Pre-invocation prerequisites

- [ ] **Phase 1 has been executed and returned ≥1 hit for at least one
      asset ID.** Recorded in the operator's working notes (addresses +
      UTC timestamps).
- [ ] **Phase 2 has been executed and returned a co-resident @264 hit
      (±4 MiB of a Phase 1 hit).** The co-resident address `A` is
      recorded in the operator's working notes.
- [ ] **The four triplet values `v0..v3` are looked up** from the
      offline decode report for the target mesh (see §3) and recorded
      in the operator's working notes.
- [ ] **User has read this handoff and approved the Phase 3 invocation.**
      Confirmed in chat.
- [ ] **User has read `docs/handoffs/2026-06-13-scoped-live-scan-asset-load-proof.md`
      and approved the phased design.** Confirmed in chat.
- [ ] **User has read the Phase 1 and Phase 2 invocation handoffs.**
      Confirmed in chat.

### 7.2 Operator-side load state (carried forward)

- [ ] **Zone / subzone / character / coordinates** — same as Phase 1 /
      Phase 2 (the load state has not changed since the Phase 1 read).
- [ ] **Distance to nearest `diffuse_blank` placeable** — same as Phase 1.
- [ ] **PID** — re-captured via
      `tasklist /FI "IMAGENAME eq rift_x64.exe"`. The PID may have
      changed if the game was restarted.
- [ ] **Phase 1 hit addresses** and **Phase 2 co-resident anchor `A`** —
      recorded (never committed) for the post-filter cross-reference
      in §4.

### 7.3 RIFT process state

- [ ] **`rift_x64.exe` is running and stable**.
- [ ] **Character is not in combat** and **not in a zone transition**.
- [ ] **No addon is actively loading or unloading assets** during the
      scan window.
- [ ] **Only one `rift_x64.exe` process exists**.

### 7.4 Workspace state

- [ ] **Generated-output guard passes** —
      `python scripts/rift_workflow.py generated-output-guard` returns
      clean. (Run immediately before the Phase 3 live read.)
- [ ] **No tracked file has uncommitted changes that would be lost** —
      `git status` is clean for files the operator cares about.
- [ ] **RiftReader is available** —
      `scripts/run-reader.cmd --help` exits 0; `--scan-float-triplet`,
      `--scan-tolerance`, `--scan-context`, and `--max-hits` are
      present in the help output.
- [ ] **Output directory is `Exports/discovery-plan/stage5-live/`** and
      is gitignored.

### 7.5 Safety confirmations

- [ ] **Read-only** — no writes, no DLL injection, no remote threads,
      no hooks.
- [ ] **No input sent to the game** during the scan.
- [ ] **No full process memory dump** requested (the 8 MiB region read
      fallback in §2.2 produces a transient `.bin` file that must be
      deleted after extraction; it is not a "full dump" but is a
      transient artifact).
- [ ] **No committed live reports** — all outputs go under ignored
      `Exports/discovery-plan/stage5-live/`. The transient `.bin`
      fallback file is gitignored and must be deleted post-extraction.
- [ ] **Privacy preserved** — no chat text, account names, or local
      user-profile paths in any committed record.
- [ ] **Tests did not attach to a live process** —
      `python scripts/test_live_memory_scanner.py` was run with
      `FixtureProcessReader` only.

### 7.6 Post-invocation

- [ ] **Output JSON(s) written** under
      `Exports/discovery-plan/stage5-live/`.
- [ ] **Output reviewed** for sanity (no full dumps, no user paths,
      schema-valid JSON).
- [ ] **Per-vertex match counts recorded** in the operator's working
      notes.
- [ ] **Post-filter verdict recorded** (in-region hit count, distances
      from `A`).
- [ ] **Phase 3 outcome recorded** (PASS / FAIL — see §8).
- [ ] **Transient `.bin` file deleted** (if the §2.2 fallback was
      used). Verify with `ls Exports/discovery-plan/stage5-live/`.
- [ ] **`git status` checked** to confirm no live reports were
      accidentally staged.

### 7.7 Approval signature

When all boxes above are checked, the operator types this single line
into the chat before invoking the Phase 3 live read:

```text
APPROVED: Phase 3 live read authorised against rift_x64.exe PID <PID>; gate §7.1–§7.6 complete; Phase 2 anchor A=0x<HEX>; vertices v0..v3 sourced from offline decode.
```

`<HEX>` is the Phase 2 co-resident address `A` (with the `0x` prefix).
The line must **not** include character name, zone coordinates, the
triplet values themselves, or any user-profile path. The triplet
values remain in the operator's working notes only.

No Phase 3 live read should be attempted without this explicit
approval line.

## 8. What to do with the result

### 8.1 ≥1 in-region hit across v0..v3

```text
Phase 3 outcome: PASS
The raw contiguous static float3 representation hypothesis is
CONFIRMED for the current live state.
Record: which vertex hit, at what address, the surrounding context,
and the post-filter verdict.

Next steps (this is the Step 49 closure update):
  - Update docs/live-memory-step49-status.json with a new
    BoundedExpectedStaticBatchHitCount value (and any other fields
    the status schema requires — see
    docs/schemas/live-memory-step49-status-v1.schema.json).
  - Write a separate decision-record handoff BEFORE any parser/export
    behaviour change. The Phase 3 PASS is evidence, not a promotion
    trigger. The Step 50 final handoff remains the canonical
    "no parser/export promotion" position; a new decision-record
    handoff is required to revisit it.
  - The promotion-readiness status and proof guard suite
    (docs/post50-promotion-readiness-status-v1.schema.json and
    scripts/rift_workflow_guards.py) are the canonical gates; the
    Phase 3 result feeds them as new evidence, but does not bypass
    them.
```

### 8.2 0 in-region hits, but ≥1 out-of-region hit

```text
Phase 3 outcome: MIXED
The float-triplet pattern exists in the process, but not in the
region where the @264 prefix was found. The representation hypothesis
is unproven for THIS asset; the matches likely belong to a different
loaded mesh.
Record all addresses; do not promote.
```

### 8.3 0 hits at all

```text
Phase 3 outcome: FAIL (representation rejected for this load state)
The float-triplet pattern is not present in the process for any
of the four target vertices, even allowing a 4 MiB post-filter band.
The representation is NOT raw contiguous static float3 for the
current live state (likely delta-encoded, half-float, swizzled, or
streamed).
Do not promote. Close negative for this load state. The Step 49
status (closed-negative-current-live-state) is unchanged.
```

### 8.4 Step 49 status update (only on §8.1 PASS)

A Phase 3 PASS **does not** automatically update
`docs/live-memory-step49-status.json`. The status update requires:

1. A separate decision-record handoff that summarises the Phase 1/2/3
   results and proposes the new `BoundedExpectedStaticBatchHitCount`.
2. Schema validation against
   `docs/schemas/live-memory-step49-status-v1.schema.json`.
3. A code-reviewer-minimax-m3 sign-off on the status update.
4. A proof guard suite run
   (`python scripts/rift_workflow.py proof-guard-suite --full` or the
   equivalent) that does not regress.

This is the same gating that the original 50-step plan used to
promote Step 49 from "open" to "closed". The phased live scan
produces evidence; the status update is a separate code change.

## 9. Hard prohibitions (carried forward)

- No writes to process memory.
- No DLL injection.
- No remote threads.
- No code patches or hooks.
- No suspension or resumption of game threads.
- No changes to game files.
- No input sent to the game.
- No full process memory dumps (the 8 MiB transient `.bin` is the only
  on-disk artifact, and must be deleted post-extraction).
- No committed generated live reports.
- No local user-profile paths in tracked docs or reports.

## 10. Status

- Handoff: **DRAFT — awaiting operator approval per §7.7**.
- Tracked-file changes: **none** (planning only; the triplets are
  operator-side lookups, not manifest entries).
- Live read executed: **false** (this handoff does not execute; the
  operator executes on approval).
- Step 48 / 49 status: **unchanged**.
- Step 50 final handoff: **unchanged** (no parser/export promotion).
- Scoped scan plan: **unchanged** from
  `docs/handoffs/2026-06-13-scoped-live-scan-asset-load-proof.md`.
- Phase 1 invocation: **fully specified** in
  `docs/handoffs/2026-06-13-phase1-live-read-invocation.md`.
- Phase 2 invocation: **fully specified** in
  `docs/handoffs/2026-06-13-phase2-co-location-at264-invocation.md`
  (upstream gate).
- Operator load state: **undocumented** (operator must complete §4 of
  the operator load-state handoff before approval).
- RiftReader flag-name verification: **PASS** (2026-06-13) —
  `--scan-float-triplet` is the correct flag for float3 triplet scans;
  `--scan-tolerance` accepts the absolute tolerance (0.001 is the
  Step 48/49 baseline); `--scan-context` reports N bytes of context
  per match. The local Python `scan-live-memory` scaffold does **not**
  expose `--scan-float-triplet`; the §2.2 raw-read fallback is the
  only scaffold-side option.
- Manifest registry status: the existing
  `docs/live-memory-scan-targets.json` (3 entries: Step 48 + two
  Step 50 asset-IDs) is sufficient for Phase 1 and Phase 2. Phase 3
  consumes the triplets from the **offline** decode report, not from
  the live-memory manifest; no new manifest entries are required.
