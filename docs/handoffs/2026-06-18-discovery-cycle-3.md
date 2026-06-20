# Discovery Cycle 3 — Session Handoff

**Date**: 2026-06-18
**Status**: ✅ COMPLETE — 27 OBJs from 2 untapped families, 9/9 guards, 531/531 tests
**Commits**: 6 discovery commits + guard recalibration

## What Shipped

| Commit | What |
|--------|------|
| `a499fa0` | **Guard recalibration**: `load_large_json_keys()` streaming loader; 3 guards recalibrated for live archive; 9/9 PASS |
| `f6081ac` | **meshSize=297 TEXCOORD**: misclassified `float32xvec3` discovered; 9 single-block OBJs |
| `3b31989` | **meshSize=297 multi-block**: 6 blocks of `9f32d26c425ed264` decoded (#6/#27/#45/#59/#76/#90) |
| `82a9b09` | **meshSize=297 complete**: `0910220376b18d36` block #7 (38,957v — largest single-block); all 8 blocks of 9f32d2 (#103, #117) |
| `d96cbf1` | **meshSize=321 lighthouse**: `b89ced7d511388d2` (A_E_lighthouse_01.ma), 10/27 blocks decoded |

## Discovery Totals

| Family | OBJs | Vertices | Faces | Issues |
|--------|-----:|--------:|------:|-------:|
| meshSize=297 | 17 | 55,805 | 55,795 | 0 |
| meshSize=321 | 10 | 9,570 | 9,550 | 0 |
| **Total** | **27** | **65,375** | **65,345** | **0** |

## Key Assets

- `0910220376b18d36` #7 — **38,957v/38,955f** (largest single-block export)
- `9f32d26c425ed264` — 8 NiMesh blocks (#6/#27/#45/#59/#76/#90/#103/#117), 16,666v/16,650f
- `b89ced7d511388d2` — lighthouse, 27 NiMesh, 522 blocks; 10 decoded (#11/#41/#55/#68/#92/#110/#159/#189/#425/#505)

## State at Handoff

| Check | Result |
|--------|--------|
| pytest | 475/475 |
| dotnet test | 56/56 |
| ruff | 0 errors |
| mypy | 0 errors |
| 9/9 proof guards | PASS |
| Git | clean |
| CI (`d96cbf1`) | running |

## Discovery Frontier (exhausted)

| Family | Lead | Verdict |
|--------|------|--------|
| meshSize=297 @24 TEXCOORD | ✅ 17 OBJs |
| meshSize=305 @0 glow | ❌ Degenerate |
| meshSize=321 @204 POSITION | ✅ 10 OBJs |
| meshSize=325 | ❌ No leads |
| meshSize=329 @212 | ❌ Degenerate |

## Known Gaps

- **Lighthouse**: 17/27 NiMesh blocks unexplored (`b89ced7d511388d2`)
- **meshSize=297**: 364/374 mesh blocks in family unexplored (only blocks #6/#7 probed)
- **Pipeline integration**: meshSize=297 & 321 not in `flythrough-index.json`, `probe-meshsize-lookup.json`, or scene manifests

## Resumption

```bash
# Quality baseline
python -m pytest tests/ scripts/ -q
dotnet test RiftAssetDumper.slnx --nologo
python -m ruff check scripts/

# Exhaust lighthouse
for mb in <remaining_27_blocks>; do
  dotnet run --project src/RiftAssetDumper -- decode-nif-geometry \
    --id b89ced7d511388d2 --mesh-block $mb \
    --experimental-position-source --write-obj --out Exports/...
done

# Regenerate inventory (5-10 min live scan)
python scripts/rift_workflow.py inventory-nif-mesh-bindings --full

# All 9 guards
python scripts/rift_workflow.py guard-sweep --full
```

## Key Files

| Path | Contents |
|------|----------|
| `docs/handoffs/2026-06-18-mesh297-discovery.md` | Per-asset 297 breakdown |
| `Exports/discovery-plan/mesh297-probe/` | 17 OBJs |
| `Exports/discovery-plan/mesh321-probe/` | 10 OBJs |
| `Exports/discovery-plan/glow-probe/` | Degenerate glow (dead end) |
| `Exports/discovery-plan/mesh329-check/` | Degenerate 329 (dead end) |
| `scripts/rift_workflow_utils.py` | `load_large_json_keys()` — streaming JSON extractor |
| `scripts/rift_workflow_guards.py` | 3 guards recalibrated for live-archive |
