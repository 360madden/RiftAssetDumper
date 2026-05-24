# Ghidra-only review rank 1-14 probe handoff — 2026-05-24

## Status

Completed focused probes for all current Ghidra-only review groups.

Important boundary: this remains **candidate-only**. No parser/export/OBJ behavior was promoted.

## Coverage

The current mesh-binding inventory reports:

| Pairing bucket | Count |
|---|---:|
| Shared legacy/Ghidra pairings | 4,195 |
| Legacy-only pairings | 4 |
| Ghidra-only pairings | 64 |

`TopGhidraPairingReviewFindings` contains 14 `ghidra-only` groups. Their `Count` values sum to all 64 Ghidra-only pairings, so ranks 1-14 cover the current Ghidra-only queue.

## Commands run

```powershell
python scripts/rift_workflow.py ghidra-pairing-review-report --quick --limit 25
python scripts/rift_workflow.py mesh-probe --review-rank 1 --skip-build
python scripts/rift_workflow.py mesh-probe --review-rank 2 --skip-build
# ...
python scripts/rift_workflow.py mesh-probe --review-rank 14 --skip-build
```

For JSON-backed review, the probes were also run into ignored rank-specific folders under `Exports/ghidra-review-rank-probes/`.

## Probe triage table

| Rank | Count | Desired role | Sample | Probe evidence | Initial triage |
|---:|---:|---|---|---|---|
| 1 | 14 | `index-u16le-lead->normal-float3-lead` | `25f30ec90608eab7 mesh#7` | ghidra=3, match=yes, max=7, v=8, conf=55 | candidate normal companion; needs normal-vector proof |
| 2 | 14 | `index-u16le-lead->position-float3-lead` | `25f30ec90608eab7 mesh#7` | ghidra=3, match=yes, max=7, v=8, conf=55, posReview=True, extent=0.985711 | candidate position; bounds pass |
| 3 | 14 | `index-u16le-lead->u32-repeated-pattern-body` | `25f30ec90608eab7 mesh#7` | ghidra=3, match=yes, max=7, v=8, conf=35 | likely noise/repeated-pattern; keep rejected |
| 4 | 6 | `index-u16le-lead->uv-float2-lead` | `cabc6ebf8a7ede5b mesh#45` | ghidra=3, match=yes, max=7, v=8, conf=55 | candidate UV companion; needs UV-range proof |
| 5 | 3 | `index-u16le-lead->position-float3-lead` | `cabc6ebf8a7ede5b mesh#45` | ghidra=3, match=yes, max=7, v=8, conf=55, posReview=True, extent=15.590966 | candidate position; bounds pass |
| 6 | 2 | `index-u16le-lead->uv-float2-ror1-lead` | `e21df228cbc5851d mesh#6` | ghidra=2, match=yes, max=7, v=8, conf=55 | candidate UV companion; needs UV-range proof |
| 7 | 2 | `index-u16le-lead->uv-float2-ror1-lead` | `cabc6ebf8a7ede5b mesh#45` | ghidra=3, match=yes, max=7, v=8, conf=55 | candidate UV companion; needs UV-range proof |
| 8 | 2 | `index-u16le-lead->normal-float3-lead` | `a5e25bb93626ea8c mesh#7` | ghidra=2, match=yes, max=7, v=8, conf=55 | candidate normal companion; needs normal-vector proof |
| 9 | 2 | `index-u16le-lead->position-float3-lead` | `a5e25bb93626ea8c mesh#7` | ghidra=2, match=yes, max=7, v=8, conf=55, posReview=True, extent=11.506897 | candidate position; bounds pass |
| 10 | 1 | `index-u16le-lead->normal-float3-lead` | `c8dcc07010e2642b mesh#6` | ghidra=1, match=yes, max=293, v=294, conf=55 | candidate normal companion; needs normal-vector proof |
| 11 | 1 | `index-u16le-lead->uv-float2-lead` | `18e0926347a7c51c mesh#6` | ghidra=1, match=yes, max=7, v=8, conf=55 | candidate UV companion; needs UV-range proof |
| 12 | 1 | `index-u16le-lead->uv-float2-ror1-lead` | `a5e25bb93626ea8c mesh#34` | ghidra=3, match=yes, max=7, v=27, conf=45 | candidate UV companion; weaker coverage; needs UV-range proof |
| 13 | 1 | `index-u16le-lead->position-float3-lead` | `d6e7cb59dab746cf mesh#6` | ghidra=2, match=yes, max=7, v=8, conf=55, posReview=True, extent=6.701327 | candidate position; bounds pass |
| 14 | 1 | `index-u16le-lead->u32-repeated-pattern-body` | `d6e7cb59dab746cf mesh#6` | ghidra=2, match=yes, max=7, v=8, conf=35 | likely noise/repeated-pattern; keep rejected |

## Interpretation

- Position-like Ghidra-only ranks with current basic bounds pass: **2, 5, 9, 13**.
- Normal-like companion ranks: **1, 8, 10**.
- UV-like companion ranks: **4, 6, 7, 11, 12**.
- Repeated-pattern/noise ranks to keep rejected unless future evidence says otherwise: **3, 14**.

The repeated `index-u16le-lead` / `maxIndex < vertexCount` pattern is promising as a discovery lead, but confidence is still low/moderate and no normal/UV proof guard exists yet. The next safe step is proof reporting, not exporter promotion.

## Remaining before any promotion

- Add normal-vector and UV-range review fields comparable to the current position bounds review.
- Add group-level proof that position/normal/UV companions form a coherent attribute set across repeated samples.
- Keep `ghidra-pairing-non-export-guard` passing.
- Do not route `GhidraPairings` into `DecodeNifGeometry`, `FindNifMeshAttributeSets`, or OBJ export.
