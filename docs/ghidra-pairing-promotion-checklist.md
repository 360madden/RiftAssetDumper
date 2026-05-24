# Ghidra pairing promotion checklist

Status: **candidate-only**. Ghidra pairing evidence is useful for triage, but it must not drive geometry decode, OBJ export, or durable parser truth until this checklist passes.

## Current workflow commands

```powershell
python scripts/rift_workflow.py ghidra-pairing-review-report --quick --limit 25
python scripts/rift_workflow.py mesh-probe --review-rank 2 --skip-build
python scripts/rift_workflow.py ghidra-pairing-non-export-guard
```

The review report schema is documented at:

```text
docs/schemas/ghidra-pairing-review-v1.schema.json
docs/schemas/ghidra-attribute-candidate-v1.schema.json
```

## Hard promotion gates

| Gate | Requirement |
|---|---|
| Candidate-only marker | Every Ghidra sidecar path remains `CandidateOnly=true` until promotion. |
| Export isolation | `python scripts/rift_workflow.py ghidra-pairing-non-export-guard` passes. |
| Generated-output safety | `python scripts/rift_workflow.py generated-output-guard` passes before commit. |
| Review queue | `TopGhidraPairingReviewFindings` remains the primary queue; do not cherry-pick one row into export behavior without checking its family. |
| Focused probe | Each candidate family has at least one `mesh-probe --review-rank N --skip-build` JSON/console review. |
| Index proof | Index stream stats show sane max/distinct/degenerate behavior and `IndexMax < VertexCount`. |
| Vector proof | Position candidates pass finite/plausible/nonzero/extent checks and include sample vectors. |
| Semantic proof | Position, normal, and UV roles agree with body bytes and usage/access metadata across multiple samples. |
| Negative proof | Known noise/sentinel/repeated-pattern rows remain down-ranked or explicitly rejected. |
| Tests | Python workflow tests, C# tests, ruff, mypy, and `git diff --check` pass. |

## Promotion sequence

1. **Triage only**: use `ghidra-pairing-review-report` and `mesh-probe --review-rank N`.
2. **Evidence patch**: add read-only JSON/console evidence; keep export behavior unchanged.
3. **Proof guard patch**: add or update guards so bad Ghidra promotion fails closed.
4. **Parser patch**: only after guards exist, change parser role logic in the smallest possible place.
5. **Exporter patch**: only after parser truth is proven and export-specific guards pass.

## Current top review queue

As of the latest local report on 2026-05-24, the inventory reports:

- shared legacy/Ghidra pairings: `4,195`
- legacy-only pairings: `4`
- Ghidra-only pairings: `64`
- `ghidra-only` review groups: `14`, covering all `64` Ghidra-only pairings

Full Ghidra-only probe coverage is documented in `docs/handoffs/2026-05-24-ghidra-only-rank-1-14-probes.md`.

Top emitted review ranks:

| Rank | Kind | Count | Ghidra roles | Class | Sample | Probe |
|---:|---|---:|---|---|---|---|
| 1 | ghidra-only | 14 | `index-u16le-lead->normal-float3-lead` | missing->normal | `25f30ec90608eab7` mesh#7 | `mesh-probe --review-rank 1 --skip-build` |
| 2 | ghidra-only | 14 | `index-u16le-lead->position-float3-lead` | missing->position | `25f30ec90608eab7` mesh#7 | `mesh-probe --review-rank 2 --skip-build` |
| 3 | ghidra-only | 14 | `index-u16le-lead->u32-repeated-pattern-body` | missing->other | `25f30ec90608eab7` mesh#7 | `mesh-probe --review-rank 3 --skip-build` |
| 4 | ghidra-only | 6 | `index-u16le-lead->uv-float2-lead` | missing->uv | `cabc6ebf8a7ede5b` mesh#45 | `mesh-probe --review-rank 4 --skip-build` |
| 5 | ghidra-only | 3 | `index-u16le-lead->position-float3-lead` | missing->position | `cabc6ebf8a7ede5b` mesh#45 | `mesh-probe --review-rank 5 --skip-build` |
| 6 | ghidra-only | 2 | `index-u16le-lead->uv-float2-ror1-lead` | missing->uv | `e21df228cbc5851d` mesh#6 | `mesh-probe --review-rank 6 --skip-build` |
| 7 | ghidra-only | 2 | `index-u16le-lead->uv-float2-ror1-lead` | missing->uv | `cabc6ebf8a7ede5b` mesh#45 | `mesh-probe --review-rank 7 --skip-build` |
| 8 | ghidra-only | 2 | `index-u16le-lead->normal-float3-lead` | missing->normal | `a5e25bb93626ea8c` mesh#7 | `mesh-probe --review-rank 8 --skip-build` |
| 9 | ghidra-only | 2 | `index-u16le-lead->position-float3-lead` | missing->position | `a5e25bb93626ea8c` mesh#7 | `mesh-probe --review-rank 9 --skip-build` |
| 10 | ghidra-only | 1 | `index-u16le-lead->normal-float3-lead` | missing->normal | `c8dcc07010e2642b` mesh#6 | `mesh-probe --review-rank 10 --skip-build` |

## Explicit non-goals until promotion

- Do not feed `GhidraPairings` into `DecodeNifGeometry`.
- Do not feed Ghidra sidecar streams into `FindNifMeshAttributeSets`.
- Do not use Ghidra-only pairings for OBJ/export.
- Do not weaken existing generated-output or proof guards to make a candidate pass.
