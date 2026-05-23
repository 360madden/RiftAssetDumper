# Session Handoff — Half-Float Investigation + Live Archive Expansion

**Date:** 2026-06-09  \
**Previous:** Stage 18 (batch-sweep runner, 94 OBJs, candidate exhaustion)

## Summary

Two parallel investigations completed: (1) **half-float stream@188 decode analysis** confirmed interleaved position+control data but reached dead end for clean export (candidate-only, below 0.95 threshold), and (2) **live archive expansion** discovered 244 archives (9× Source's 27) with completely new mesh sizes (341, 357, 362) not present in the copied set. A live probe confirmed meshSize=362 with valid normals, UVs, and position data — a new export candidate family.

## 1. Half-Float Stream@188 Investigation

### What was done

- Extracted full 192-byte stream body (block 21) from asset `04297730afc68f38` (meshSize=305)
- Decoded all 96 uint16 values as IEEE 754 half-float using struct.unpack('e')
- Analyzed 0xAA56 (43606) marker pattern across 8 occurrences
- Built and ran custom analysis script (`scripts/investigate_half_float.py`)
- Cross-validated against sibling mesh `014e1ff60d8508f1`

### Key findings

| Metric | Value |
|--------|-------|
| **Payload** | 192 bytes = 96 uint16 = 96 half-floats |
| **Vertex layout** | 16 vertices × 12 bytes (6 half-floats) — fits perfectly |
| **0xAA56 markers** | 8 occurrences at indices [26, 32, 38, 44, 74, 80, 86, 92] |
| **Marker spacing** | Regular: spacing of 6, with one gap of 30 (between halves) |
| **Finite values** | 92/96 finite, 4 NaN |
| **Plausible positions** | 87/92 (94.6%) in [-1000, 1000] |
| **Plausible range** | [-8.76, 17.02] — very tight, game-appropriate |
| **Structural family** | `u16-ternary-mixed-c` with interleaved even/odd triple pattern |

### The interleaving pattern

The 192 bytes are structured as **16 triples × 6 bytes = 96 bytes per half** (two structurally identical halves):

- **Even triples** → A+B are position-like, **C is NaN/0xAA56** — these are the problem
- **Odd triples** → A+B vary, C=65 (near-zero as half-float) — metadata/control channel

### Verdict

**Dead end for clean export.** The data IS half-float but **interleaved with control/metadata bytes** in specific columns. 94.6% plausible-position rate is a stronger signal than float32 decode (0%), but the NaN/outlier values in C-column of even triples confirm this isn't clean homogeneous position data. All 8 candidate rows failed strict classifier (below 0.95 threshold). Classified as **candidate-only** — no C# decoder port justified.

### Sibling validation

Confirmed same pattern in secondary sibling `014e1ff60d8508f1` (288 bytes = 24 triples). Secondary sibling `0d9a25c9a6af7b18` was different — it has 264-byte float32 positions that already work with the existing decoder.

## 2. Live Archive Expansion — Highest ROI Discovery

### Archive comparison

| Metric | Source (copied) | Live (full) | Delta |
|--------|:---------------:|:-----------:|:-----:|
| Archives | 27 | **244** | **9×** |
| NIF entries | 5,511 | 825 sampled | — |
| NiMesh blocks | 5,507 | 152 sampled | — |
| Mesh sizes | 16 sizes (max 354) | **19+ sizes** (max 362+) | +3+ new |
| Unique mesh sizes | 297, 301, 305, 321, 325, 329... | Same + **341, 357, 362** | **New families** |

### Live archive type breakdown (2,408 entries sampled)

| Type | Count |
|------|:-----:|
| DDS (textures) | 953 |
| NIF (models) | 825 |
| BIN (binary data) | 360 |
| RIFF (audio) | 213 |
| JPG (images) | 52 |
| TXT | 4 |
| XML | 1 |

### New mesh sizes discovered (not in Source)

| Mesh Size | Role/Context | Export Potential |
|:---------:|:-----------:|:----------------:|
| 341 | unseen role group | 🟡 Unprobed |
| 357 | unseen role group | 🟡 Unprobed |
| **362** | normal-float3-ror1-lead, uv-float2-ror1-lead, position-float3-ror1-lead | **🟢 CONFIRMED** |

### Live probe: cf54e712ff57eaac (mesh block 6, meshSize=362)

| Property | Value |
|----------|-------|
| Source archive | assets.002 (entry 1191) |
| Mesh size | **362** (not in Source) |
| Total NIF blocks | 32 (1 NiMesh + 31 other) |
| Attribute sets | 0 |
| Pairings | 0 |
| Candidate links | 3 |

**Stream layout:**

| Stream | Role | Vertices | Bytes | Confidence |
|--------|------|:--------:|:-----:|:----------:|
| offset 232 | `normal-float3-ror1-lead` | 6,489 | 77,897 | 85% (unit-length confirmed) |
| offset 308 | `position-float3-ror1-lead` | 41 | 492 | 75% (finite bounds, extent=3.0763) |
| offset 316 | `uv-float2-ror1-lead` | 6,489 | 51,941 | 80% (UV-range confirmed) |

**Key evidence:** The normal stream has **NearUnitVectorRatio=1.0** (6,489/6,489 unit-length normals). The position stream has finite nonzero bounds with extent=3.0763 (game-appropriate scale). The UV stream has perfect UV-range ratios. This is a **viable 0-attribute-set export candidate** via `--experimental-position-source`.

## 3. Inventory structure caveats

- The full mesh inventory against live root **timed out after 10 minutes** at 244-archive scan
- All live slot data comes from 50-entry smoke test (`--max-total 50`) or 100-entry scan
- The live manifest (`assets64.manifest`) is nearly identical to Source's (48 bytes diff) — same game version
- **244 archives × ~10,000 entries each ≈ 2.4M total entries** in live — vastly larger than Source's 40K

## 4. Investigation scripts (scratch, to be cleaned)

| Script | Purpose | Status |
|--------|---------|:------:|
| `scripts/investigate_half_float.py` | Half-float decode + marker analysis | 🔴 Scratch (remove) |
| `scripts/investigate_half_float_summary.py` | Summary visualizer | 🔴 Scratch (remove) |

## CI Status

| Check | Result |
|-------|:------:|
| `dotnet build` | 0 errors ✅ |
| `ruff check scripts/` | 89 violations (investigation scripts only) ❌ |
| `mypy scripts/` | Not checked |
| Python tests (56) | 56/56 ✅ |

## Blockers & Decisions

| # | Blocker | Priority | Resolution |
|---|---------|:--------:|------------|
| 1 | **Half-float stream@188**: Interleaved control bytes prevent clean export | 🟤 Superceded | **No further investigation warranted** — dead end confirmed |
| 2 | **Live inventory timeout**: Full scan of 244 archives takes 10+ min | 🟡 Medium | Use `--max-total 500` for targeted probes; batch scanning needed |
| 3 | **New mesh sizes (341, 357)**: Existence confirmed but unprobed | 🟢 High | Probe these from live root in next session |
| 4 | **Live root access**: Requires read-only `C:/Program Files (x86)/Glyph/Games/RIFT/Live` | 🟢 Available | Ready for expansion |

## Optimal Next Steps

| Priority | Action | Expected ROI |
|:--------:|--------|:------------:|
| 1️⃣ | Probe meshSize=341 and meshSize=357 assets from live root | Uncover new export families |
| 2️⃣ | Run `--experimental-position-source` decode on cf54 mesh block 6 (meshSize=362) | First export from live archives |
| 3️⃣ | Batch prob all live NiMesh blocks to catalog complete mesh size distribution | Comprehensive live inventory |
| 4️⃣ | Evaluate if manifest-copy approach works for live archive expansion | Scale to full extraction |

## Key numbers summary

```
Source archives: 27
Live archives: 244 (9×)
Source NiMesh: 5,507
Live NiMesh (sample): 152+
New mesh sizes: 341, 357, 362
Confident new exports: 1 (meshSize=362)
Half-float dead-end: confirmed
```

## Files changed this session

| File | Change | Description |
|------|:------:|-------------|
| `scripts/investigate_half_float.py` | +NEW | Half-float decode investigation (scratch) |
| `scripts/investigate_half_float_summary.py` | +NEW | Summary visualizer (scratch) |
| `docs/handoffs/2026-06-09-half-float-investigation-live-expansion.md` | +NEW | This handoff document |
| `Exports/stream-body-305-0429-s21.json` | +NEW | Stream body probe data |
| `Exports/live-probe-cf54-mesh6.json` | +NEW | Live mesh probe data |
| `Exports/live-mesh-fast.json` | +NEW | Live mesh inventory (50-entries) |
