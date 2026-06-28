# 2026-06-27 Flythrough Rebuild & mesh305 payload=624 Dead-End

## Flythrough rebuild (mesh329#7 integration)

mesh329#7 batch export (commit `6473001`) added 12 faced OBJs (565v/541f). The flythrough pipeline was rebuilt to consume them:

| Step | Action |
|------|--------|
| world.json | Generated via `probe-nif-scene-graph` for all 12 assets |
| OBJ copy | 12 OBJs → `Assets/build/flythrough/objs/<id>.obj` |
| export-manifest | 12 new entries added (350→362) |
| flythrough-index.json | Rebuilt via `ft8_final_manifest.py`, patched with mesh_size/world_json/node+mesh counts |
| world-placed-merged.obj | Rebuilt via `build_world_placed_merge.py` |

**Result:** flythrough-index.json: **229 assets** (167 faced, mesh329: 15). world-placed-merged.obj: **18,048v/24,257f**, 0 NaN, 0 negative indices, 2.65MB. Clean merge — all 12 mesh329#7 OBJs integrated.

All flythrough build artifacts are under gitignored `Assets/build/` and `Exports/` — no commit needed.

## mesh305 payload=624 dead-end confirmation

| Aspect | Finding |
|--------|---------|
| Gap report | `ror3PlausibleRatio=0.9487`, `ror3VectorCount=52`, `ror3FiniteRatio=1` |
| Role | `uint16-compatible-body` (confidence=25) |
| Stream | `stream@0`, `string=glow` label (material/effect property) |
| bodyFirst16 float32 | Denormal garbage: `-9.26e-05`, `1.78e-38`, `1.76e-38`, `-9.22e-05` |
| 0xAA56 magic | **Absent** — different from stream@188 dead ends |
| Verdict | **Dead end.** Float32 decode produces subnormal garbage (e-38 range). The `string=glow` label confirms material/effect metadata, not vertex position. |

All mesh305 residual leads are confirmed dead. No further investigation warranted.

## Current state

- 3 proven families: mesh297 (17), mesh321 (10), mesh329#7 (12) = **39 OBJs**
- Flythrough consumer artifacts rebuilt and ready
- residual-strict-threshold DEFERRED (permanent blocker)
- Position gap closed
