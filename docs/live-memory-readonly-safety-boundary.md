# Live memory read-only safety boundary

Date: 2026-05-26

This document completes Step 46 of `docs/discovery-plan-50.md`: design the live memory scan safety boundary.

## Scope

The only allowed live-process action for the 50-step plan is bounded, read-only validation against the RIFT client process.

Allowed target:

- `rift_x64.exe` only.

Preferred scanner provider:

- Use RiftReader.Reader (`C:/RIFT MODDING/RiftReader/scripts/run-reader.cmd`) for live reads when it already exposes the needed scan mode.
- Assets-local scanner code is a dry-run contract/fallback lane, not the preferred live-read provider.

Allowed access intent:

- Read-only pattern validation for known static discoveries:
  - known NIF asset IDs,
  - known index-buffer byte prefixes,
  - bounded float3 vertex-cluster probes derived from static decode reports.

## Hard prohibitions

The live validation lane must never do any of the following:

- write process memory,
- inject DLLs,
- create remote threads,
- patch code,
- install hooks,
- suspend or resume game threads,
- change game files,
- send input to the game,
- dump full process memory,
- commit generated live reports,
- store private local user-profile paths in tracked docs or reports.

## Required implementation gates

Any future `scan-live-memory` implementation must be guarded by all of these controls:

| Gate | Requirement |
|---|---|
| Explicit command | A dedicated command such as `scan-live-memory`; no hidden live reads from other workflow commands. |
| Experimental flag | Require `--experimental-live`. |
| Confirmation flag | Require a second explicit confirmation flag for actual live attach/read execution. |
| Dry run | Support a dry-run/list mode that prints planned target, patterns, output paths, and limits without opening a process. |
| PID targeting | Prefer explicit `--pid`; automatic process selection must fail closed on zero or multiple candidates. |
| Access rights | Request only query/read rights required for `ReadProcessMemory`; never request write/operation rights. |
| Region filtering | Scan only committed readable memory regions; skip guard/no-access/image-incompatible regions unless explicitly justified in code comments. |
| Bounds | Require max bytes, max matches, max regions, and timeout limits. |
| Output namespace | Write only under ignored `Exports/discovery-plan/stage5-live/`. |
| Privacy | Redact local usernames and user-profile paths; do not include long raw memory dumps. |
| Tests | Unit tests must use fixtures or mocked process readers; CI must not attach to a live process. |

## Output policy

Live validation output remains ignored/generated evidence.

Required output directory:

```text
Exports/discovery-plan/stage5-live/
```

Allowed output shape:

- JSON summary with:
  - schema version,
  - command-line safety flags,
  - target process name and PID,
  - scan limits,
  - pattern labels,
  - match counts,
  - bounded match addresses,
  - short bounded byte snippets only when needed for proof.
- Markdown summary with the same high-level evidence.

Disallowed output:

- full memory dumps,
- large contiguous memory extracts,
- credentials, tokens, account names, chat text, or local user-profile paths,
- copied/generated game assets.

## Step 47 entry criteria

Step 47 may start only after this boundary is present and tests are designed around a non-live process-reader abstraction.

Step 47 implementation delivered a gated Python workflow command; future refinements must preserve:

1. A dry-run/list mode.
2. Parser/validator for `label=hex` patterns.
3. A process-reader interface with fixture-backed tests.
4. Generated-output guard coverage before actual execution.
5. No live process attach in tests or CI.

## Actual live-read execution gate

Implementing the scanner is allowed under the 50-step plan, but executing it against a live process is a separate safety event.

Before any actual live process read, the workflow must show:

1. exact command,
2. exact PID or process-selection behavior,
3. exact patterns,
4. output paths,
5. scan byte/region/time limits,
6. generated-output guard status.

If those are not available, the live read must not run.
