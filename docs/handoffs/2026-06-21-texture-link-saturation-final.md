# Texture-Link Saturation — Closure Handoff

**Date**: 2026-06-21
**Status**: ✅ TEXTURE-LINK WORK COMPLETE — full-archive rescan yields 0 new entries; baseline confirmed saturated.
**Commits**: 8a9d862 (dedup-merge utility), c060c98 (cycle-3 ingest growth), 3203326 (cycle-3 ingest).

## Saturation Finding (Verified)

The 779-line `flythrough-texture-links.jsonl` baseline covers **all reachable texture references for the 227-asset flythrough subset**. A full-archive rescan (264,065 payloads, 703,092 raw links, 81,341 unique models, 16-min scan) produced **0 new entries** when run through the additive dedup-merge utility. This is the **terminal state** for the texture-link posture.

**Implication**: Texture-link promotion is no longer the bottleneck for `consumer_ready` growth. The remaining 9 unresolved assets (no `linked_textures`) are geometry-gated (`has_obj=no`), not texture-gated.

## Final State Metrics

| Metric | Value | Source |
|--------|------:|--------|
| Flythrough assets | 227 | `flythrough-index.json` |
| `consumer_ready` | 159 | stage6 manifests |
| `linked_textures` populated | 218 | flythrough-index |
| Non-identity world transforms | 5 | delivery JSON (`transform_identity: false`) |
| MeshSize families | 19 | delivery JSON |
| Texture links (JSONL) | 779 | flythrough-texture-links.jsonl |

## 9 Unresolved Assets (Final)

| Asset ID | mesh_size | tex_props | mesh_block | Resolution |
|----------|----------:|----------:|-----------:|------------|
| 0d1c9c5d9073ce22 | — | 1 | — | geometry gate (no OBJ) |
| 0e0c61ad75d2af1e | 193 | 0 | 7 | decoration geometry (final) |
| 1601c1f75e0a6022 | 272 | 0 | 6 | decoration geometry (final) |
| 1e8d2bcc6546b548 | 197 | 0 | 17 | decoration geometry (final) |
| 2581c6d1c4ee35b8 | — | 1 | — | geometry gate (no OBJ) |
| 35ca1d9dbad6d245 | 193 | 0 | 7 | decoration geometry (final) |
| b5dc665faa848f85 | 214 | 0 | 12 | decoration geometry (final) |
| cfbd6bffb7620092 | — | 1 | — | geometry gate (no OBJ) |
| e383643b31af4ff2 | — | 1 | — | geometry gate (no OBJ) |

**Resolution pattern**: 5 of 9 are confirmed decoration geometry (tex_props=0, no material/target); 4 of 9 have `NiTexturingProperty=1` in their NIF but no resolvable DDS reference paths, and they're also failing the geometry gate (no OBJ exported). All 9 satisfy the project's "terminal decoration / textureless" designation.

## Scripts Shipped This Thread

| Script | Role | Tests |
|--------|------|-------|
| `scripts/_merge_full_scan_links.py` | Additive dedup-merge utility for future cycle runs | `tests/test_merge_full_scan_links.py` (6 tests) |
| `tests/test_link_flythrough_textures_bom.py` | BOM-tolerance contract lock | 2 tests |

## Known Boundary Conditions

- **C# writer emits per-asset JSONL files each prefixed with UTF-8 BOM.** Concatenating them directly corrupts JSONL parsing. The dedup-merge utility strips BOMs globally; the ingest path strips them per-line.
- **Source/ copied-set baseline (deleted 2026-06-06)** was used to seed the original 713-line texture JSONL. All post-cycle-3 work has been merged onto the live-archive baseline (now 779 lines).
- **`small-i` flythrough subset** (227 assets) is the only scope for `consumer_ready` validation. Texture links for the broader 81,341 unique models exist in the raw scan output but are not promoted (out of scope).

## Next-Direction Hypotheses (Out of Scope for This Thread)

These are **candidates only** — not pre-committed. Each carries its own ROI/cost analysis:

1. **Geometry gap expansion**: probe the 9 unresolved geometry-gated assets for alternate mesh-block combinations. Bounded universe, uncertain outcome.
2. **LOD variant expansion**: push 193/217 → 217/217 FT-7 classification. Metadata fidelity, not consumer_readiness.
3. **Cycle 4 bootstrap**: fresh discovery framing on a new signal axis. High risk, high potential.

## Reproduction

```bash
# Verify current state
python -m pytest tests/test_merge_full_scan_links.py tests/test_link_flythrough_textures_bom.py -q --tb=short
python scripts/rift_workflow.py scene-manifest-validation-guard

# If a future cycle adds a new flythrough asset, re-run the saturation probe:
python scripts/_merge_full_scan_links.py --dry-run  # should print "[warn] 0 added" if still saturated
```
