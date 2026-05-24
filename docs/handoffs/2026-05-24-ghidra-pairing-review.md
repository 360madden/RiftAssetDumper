# Ghidra pairing review handoff — 2026-05-24

## Status

Implemented a candidate-only review surface for Ghidra-aligned mesh pairing gaps.

Default parser/export/OBJ behavior remains unchanged. The new fields rank evidence for human review only; they do not promote Ghidra roles into attribute-set or export logic.

## What changed

- Added `TopGhidraPairingReviewFindings` to `inventory-nif-mesh-bindings` JSON.
- Review findings are ranked by priority:
  1. `ghidra-only` pairings — links that exist in the Ghidra-aligned sidecar path but not the legacy/default path.
  2. `vertex-semantic-change` shared pairings — same mesh/index/vertex stream identity, but the vertex semantic class changes between legacy and Ghidra role interpretation.
- Added semantic-class grouping for pairing roles:
  - `index`
  - `position`
  - `normal`
  - `uv`
  - `color`
  - `side-channel`
  - `unknown`
  - `other`
  - `missing`
- Pairing samples now include first-byte evidence for both index and vertex streams:
  - target block first bytes,
  - body bytes used by the current pairing path,
  - Ghidra-aligned body bytes when present.
- Python `mesh-bindings` summaries now print the new review findings.
- Added regression coverage for the Python summary output and C# semantic-class helper.

## Validation evidence

Command:

```powershell
python scripts/rift_workflow.py mesh-bindings --limit 25 --skip-build
```

Result:

| Metric | Result |
|---|---:|
| NIF payloads | 5,111 |
| NiMesh blocks | 5,507 |
| Candidate stream links | 11,564 |
| Ghidra-style layout valid stream bodies | 11,564 |
| Ghidra role deltas | 10,880 |
| Legacy pair-compatible meshes | 1,949 |
| Legacy pair-compatible links | 4,199 |
| Ghidra pair-compatible meshes | 1,972 |
| Ghidra pair-compatible links | 4,259 |
| Shared pairings | 4,195 |
| Legacy-only pairings | 4 |
| Ghidra-only pairings | 64 |

Top review findings from the copied-set proof run:

| Kind | Priority | Mesh size | Count | Ghidra roles | Semantic class |
|---|---:|---:|---:|---|---|
| `ghidra-only` | 1 | 301 | 14 | `index-u16le-lead -> normal-float3-lead` | normal |
| `ghidra-only` | 1 | 301 | 14 | `index-u16le-lead -> position-float3-lead` | position |
| `ghidra-only` | 1 | 301 | 14 | `index-u16le-lead -> u32-repeated-pattern-body` | other |
| `ghidra-only` | 1 | 305 | 6 | `index-u16le-lead -> uv-float2-lead` | uv |
| `ghidra-only` | 1 | 305 | 3 | `index-u16le-lead -> position-float3-lead` | position |

The limited report retained 25 review groups: 14 `ghidra-only` groups and 11 `vertex-semantic-change` groups.

## Interpretation

The strongest immediate review target is not export promotion. It is sample-level inspection of the 64 Ghidra-only links and then the high-count shared rows where legacy UV/normal classifications become Ghidra position/other classifications.

Because the Ghidra-only groups include position, normal, UV, and `other` vertex classes, the ranking is useful for triage but still not sufficient to change default role or attribute-set behavior.

## Remaining unwired pieces

- No export, OBJ, or guard behavior consumes `TopGhidraPairingReviewFindings`.
- Attribute-set logic still uses legacy/default roles.
- Workflow-level `ghidra-pairing-review-report` now expands review findings into ignored JSON/Markdown triage output; no deeper byte/float/vector focused probe exists yet.
- No promotable whitelist exists for Ghidra semantic transitions.

## Recommended next milestone

Add a small candidate-only focused probe command for one review finding/sample:

- accept mesh id/block and stream offsets from a review sample,
- print legacy vs Ghidra first bytes and role stats side by side,
- include decoded float/vector/index summaries where applicable,
- keep generated output under ignored `Exports/`,
- do not modify export behavior.

Follow-up started: `docs/handoffs/2026-05-24-ghidra-pairing-review-report.md`.
