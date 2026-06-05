# Index Stream Family Map

**Last Updated**: 2026-06 (Phase 37 — 12 probes resolved 3 new families: MS=267, MS=297, MS=330; unknowns 79→66)

**Purpose**: Reference table mapping which mesh blocks in each MeshSize family carry index streams (producing faced OBJs) vs those that only carry vertex data (producing position-only OBJs via sibling pairing).

---

## Master Table

| MeshSize | MB | Faced | PosOnly | %Faced | Index Stream? | Notes |
|---|---|---|---|---|---|---|
| 240 | 6 | 1 | 0 | 100% | ✅ Yes | @264-indexed, 80v/78f |
| 267 | 10 | 1 | 0 | 100% | ✅ Yes | New family (Phase 37); 2f/5v, index stream present |
| 276 | 17 | 1 | 0 | 100% | ✅ Yes | New family (Phase 36); 71f/50v, index stream present |
| 297 | 6 | 2 | 0 | 100% | ✅ Yes | New family (Phase 37); 82f/64v + 118f/95v, index stream present |
| 330 | 6 | 1 | 0 | 100% | ✅ Yes | New family (Phase 37); 14f/16v, index stream present |
| 354 | 6 | 1 | 0 | 100% | ✅ Yes | New family (Phase 36); 22f/24v, index stream present |
| 301 | 6 | 24 | 0 | 100% | ✅ Yes | Canonical faced block (Phase 37: +6 IDs confirmed) |
| 301 | 7 | 1 | 0 | 100% | ✅ Yes | Single asset, may be special case |
| 301 | 25 | 1 | 0 | 100% | ✅ Yes | Phase 37; 3f/6v, index stream present |
| 305 | 6 | 11 | 0 | 100% | ✅ Yes | Primary faced block for 305 |
| 305 | 7 | 0 | 16 | 0% | ❌ No | Float2 sibling pair (no index; float3 MB=7 probe confirmed pos-only) |
| 305 | 27 | 0 | 12 | 0% | ❌ No | Float3 sibling pair (no index) |
| 305 | 45 | 4 | 3 | 57% | ⚠️ Mixed | Faced=10-18v; pos=5v (degenerate) |
| 305 | 46 | 1 | 0 | 100% | ✅ Yes | Single asset with index stream |
| 309 | 6 | 16 | 0 | 100% | ✅ Yes | Canonical faced block (float3 probe added 1) |
| 321 | 6 | 16 | 0 | 100% | ✅ Yes | Expanded via 414-face cluster (9 inferred IDs, Phase 35.5) |
| 321 | 7 | 0 | 1 | 0% | ❌ No | MB=7 has NO index stream (Phase 30) |
| 325 | 6 | 45 | 0 | 100% | ✅ Yes | Canonical faced block (Phase 37: +1 ID confirmed) |
| 325 | 31 | 2 | 0 | 100% | ✅ Yes | New MB data point (Phase 35); 18f/20v, 2 IDs, index stream present |
| 329 | 6 | 0 | 2 | 0% | ❌ No | **No index stream at any MB** |
| 345 | 6 | 3 | 0 | 100% | ✅ Yes | 2 unique IDs, all faced |
| 361 | 6 | 1 | 0 | 100% | ✅ Yes | New family (from probe) |
| 365 | 9 | 1 | 0 | 100% | ✅ Yes | MB=9 has index (464 faces) |
| 370 | 66 | 0 | 1 | 0% | ❌ No | Position-only (6v, no index) |

| 389 | 6 | 0 | 2 | 0% | ❌ No | **No index stream at any MB** (float3 probe confirmed) |
| 465 | 7 | 1 | 0 | 100% | ✅ Yes | **MB=7 IS faced** (69 faces, 23v — Phase 30!) |
| 465 | 8 | 0 | 17 | 0% | ❌ No | No index stream at MB=8 |

---

## Key Findings

### Families with 100% faced OBJs (have index streams)
These MeshSizes have mesh blocks carrying `index-u16be-strip-lead` streams:

| MeshSize | Faced MBs | Total Faced |
|---|---|---|
| 240 | 6 | 1 |
| 267 | 10 | 1 | New! Cluster probe (Phase 37) |
| 276 | 17 | 1 | New! Cluster probe (Phase 36) |
| 297 | 6 | 2 | New! Cluster probe (Phase 37) |
| 301 | 6, 7 | 25 | Canonical faced family |
| 305 | 6, 45, 46 | 16 | Mixed family |
| 309 | 6 | 16 |
| 321 | 6 | 16 | Expanded via 414-face cluster |
| 325 | 6, 31 | 47 | Canonical faced + new MB=31 |
| 330 | 6 | 1 | New! Cluster probe (Phase 37) |
| 345 | 6 | 3 |
| 354 | 6 | 1 | New! Cluster probe (Phase 36) |
| 361 | 6 | 1 |
| 365 | 9 | 1 |
| 465 | 7 | 1 | MB=7 IS faced (69f, 23v) |

### Families with 0% faced OBJs (no index streams)
These MeshSizes lack index streams entirely — all OBJs are position-only:

| MeshSize | MBs | Total PosOnly | Notes |
|---|---|---|---|
| 321 | 7 | 1 | MB=7 has no index stream (Phase 30) |
| 329 | 6 | 2 | Float2 sibling pair |
| 370 | 66 | 1 | 6 vertices, auxiliary? |
| 389 | 6 | 2 | Single entry (float3 probe confirmed) |
| 465 | 8 | 17 | Largest pos-only family (but MB=7 IS faced!) |

### Mixed family: MeshSize 305
The only MeshSize with both faced and position-only mesh blocks:

| Mesh Block | Behavior | Root Cause |
|---|---|---|
| MB=6 | Always faced (11/11) | Has index stream |
| MB=45 | 57% faced (4/7) | 3 pos-only have only 5v (degenerate) |
| MB=46 | Always faced (1/1) | Has index stream |
| MB=7 | Always pos-only (15/15) | Float2 sibling pair, no index |
| MB=27 | Always pos-only (12/12) | Float3 sibling pair, no index |

### Root Cause: MB=6 is the canonical geometry block
MB=6 carries index streams for MeshSizes **240-361** but stops at **329 and 389**:

- **Index stream present**: MB=6 in MeshSize 240, 267, 276, 297, 301, 305, 309, 321, 325, 330, 345, 354, 361, 365
- **No index stream**: MB=6 in MeshSize 329, 389

This suggests a transition point around MeshSize 329+ where mesh blocks switch from explicit-indexed geometry to float2+float3 sibling-paired encoding.

### Phase 30 Discovery: MS=465 MB=7 IS faced
Previously believed to be 0% faced, MS=465 **can** produce faced OBJs at MB=7 (69 faces, 23 vertices).
The position-only MB=8 entries (17 IDs) are the float2 sibling-paired blocks.

### Phase 30 Discovery: MS=321 MB=7 is position-only
While MS=321 MB=6 is 100% faced (7 IDs), MB=7 has no index stream.
This means not all MB=7 blocks carry index streams — it depends on the MeshSize.

---

## Probe Methodology

The findings are based on:
1. Export manifest data (268 OBJs, 182 unique asset IDs)
2. Direct `probe-nif-mesh` on representative assets at specific mesh blocks
3. Phase 19 sibling pairing map cross-reference
4. Phase 30 float3 batch export (9 IDs exported, 6 produced faced OBJs)

Assets probed or batch-exported:
- `0603cce7cee15eb8` MB=6 (MeshSize 240, @264-indexed)
- `1674fb283ce86d95` MB=45 vs MB=7 (MeshSize 305, faced vs pos-only)
- `6c6aae2cda8aebcf` MB=6 (MeshSize 361, 414-face family)
- `7fc596b8c4f6f643` MB=9 (MeshSize 365, 464-face family)
- `3720e6179d344ae0` MB=8 (MeshSize 465, position-only)
- `b2691b19bc1886f3` MB=66 (MeshSize 370, position-only)
- Float3 batch (Phase 30): 9 IDs, 6 faced + 3 pos-only
