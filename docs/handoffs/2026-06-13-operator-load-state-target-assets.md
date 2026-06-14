# Operator load-state handoff — 6fc01704d4a509d5 & caa9a88e94ec8db0

Date: 2026-06-13
Author: Buffy (research only; no live read executed)
Companion: `docs/handoffs/2026-06-13-scoped-live-scan-asset-load-proof.md`

## TL;DR

| Field | Value |
|---|---|
| Target assets | `6fc01704d4a509d5` (mesh#6, vertex_count=128, face_count=318) and `caa9a88e94ec8db0` (mesh#6, vertex_count=128, face_count=318) |
| Mesh topology | `meshSize=325`, mesh block 6, `@264` index stream (`index-u16be-strip-lead`, raw-zero-based preferred) — the proven anchor family from Step 48 |
| Texture | `a6ad5487db2f8532` → `diffuse_blank.png` (4×4 DXT1 white) — a generic invisible/utility texture |
| Flythrough subset | **Both are in the 217-asset flythrough subset** with full scene-graph + world.json coverage (100% world_json_pct). |
| Source archive | `assets.053`, entry `1187` (`6fc01704...`) and entry `1188` (`caa9a88e...`) — adjacent entries in the same archive. |
| Known load state | **No per-asset zone map exists in the project.** Project data has world transforms (Scale×Rotate×Translate) but no zone identifier. Zone must be derived from the in-game position by the operator at scan time. |
| Recommended load | In a zone where `diffuse_blank` placeable items are visibly common (e.g. Sanctum / Meridian capital cities, or any player hub with many decorative placeables). The exact zone is not constrained by project data. |
| Live read executed | **false** — Phase 0 dry-run validated plan only. |

## 1. Project-side evidence (read-only, gitignored artifacts)

Both target assets are in the project's `Assets/build/flythrough/` index files (gitignored generated output, but read for context only).

### 1.1 `flythrough-index.json` (summary)

| Asset | vertex_count | face_count | mesh_block | mesh_size | lod_type | lod_level | has_transform | linked_textures |
|---|---:|---:|---:|---:|---|---:|---|---|
| `6fc01704d4a509d5` | 128 | 318 | 6 | 325 | meshsize-family | 1 | false | `a6ad5487_diffuse_blank.png` |
| `caa9a88e94ec8db0` | 128 | 318 | 6 | 325 | meshsize-family | 1 | false | `a6ad5487_diffuse_blank.png` |

Both share the same `vertex_count`, `face_count`, `mesh_block`, `mesh_size`, `lod_type`, `lod_level`, and texture.

### 1.2 `scene-graph-manifest.json` (summary)

| Asset | world_json | node_count | mesh_count | meshes_attached | bytes | root_scale | child_count |
|---|---|---:|---:|---:|---:|---:|---:|
| `6fc01704d4a509d5` | `6fc01704d4a509d5.world.json` | 1 | 1 | 1 | 1340 | 1 | 5 |
| `caa9a88e94ec8db0` | `caa9a88e94ec8db0.world.json` | 1 | 1 | 1 | 1340 | 1 | 5 |

Both have a minimal scene graph: 1 root node, 1 mesh attached, `root_scale=1`, 5 children. The 1,340-byte `world.json` size matches the canonical "single-NiNode + 5 child refs" pattern seen across the 217-asset flythrough set.

### 1.3 `lod-manifest.json` (MS=325 LOD level 1 cluster)

```
vertex_count: 128, lod_level: 1, count: 4, faced_count_at_level: 4
asset_ids: 6fc01704d4a509d5, caa9a88e94ec8db0
```

Only the two target assets are listed at this LOD level in the export, though the `count: 4` field implies two additional meshes may exist in the same NIF (counted but not exposed in the asset-id list — likely the same IDs duplicated across mesh blocks within the NIF or a manifest display artefact).

### 1.4 Texture-link evidence (`flythrough-texture-links.jsonl`)

```text
caa9a88e94ec8db0 → assets.053 entry 1188 → diffuse_blank.dds (a6ad5487db2f8532, assets.002 entry 1435)
6fc01704d4a509d5 → assets.053 entry 1187 → diffuse_blank.dds (a6ad5487db2f8532, assets.002 entry 1435)
```

Both link to the same texture asset. The texture is a **4×4 DXT1 white texture** — a generic invisible/utility texture used across the project for placeable items that are not meant to render with normal diffuse maps.

### 1.5 `Assets/build/flythrough/flythrough-texture-links.jsonl` and the `diffuse_blank` family

The `diffuse_blank` texture is shared with these other flythrough assets (sample):

| Asset | vertex_count | mesh_block | mesh_size | has_transform |
|---|---:|---:|---:|---|
| `0603cce7cee15eb8` | 80 | 6 | 240 | false |
| `0668793335b29149` | 9 | 6 | 301 | false |
| `084c1e91726a2aea` | 24 | 6 | 276 | false |
| `07f37c99a80da009` | 50 | 17 | 276 | true |
| `0d9a25c9a6af7b18` | 22 | 27 | 325 | true |
| `2c85cfa17543443b` | 50 | 17 | 276 | true |
| `3de9c1236fe20520` | 95 | 6 | 297 | false |
| `593ea328978bde38` | 50 | 17 | 276 | true |
| `dfa4b4fccd826b59` | 64 | 6 | 297 | false |
| **`6fc01704d4a509d5`** | **128** | **6** | **325** | **false** |
| **`caa9a88e94ec8db0`** | **128** | **6** | **325** | **false** |

Most `diffuse_blank` items are small (4-95v) decorative placeables. The two targets are noticeably larger (128v, 318 strip faces) — a 1.3×–14× size jump over the rest of the family. This is the strongest signal that **6fc0/caa9 are utility meshes (likely collision, light, or volume) rather than visible decorations** — they need real geometry but no diffuse texture.

### 1.6 `Assets/build/flythrough/known-non-identity-transform-ids.txt` (cycle-2 evidence)

The prior cycle-2 analysis (2026-06-08) recorded `caa9a88e94ec8db0` in `known-non-identity-transform-ids.txt`. This is a single-archive fragment under `Exports/discovery-plan/cycle-2/stage1/artifacts/`, not part of the current flythrough set. It records that at one point, `caa9`'s world transform was non-identity, which is consistent with a placed utility object (not a fixed origin decoration). It does **not** indicate a zone.

### 1.7 `world.json` content (read for proof, not for zone)

The `world.json` for both assets is 1,340 bytes, identical structure to all other 1-NiNode + 5-child entries in the flythrough set. It contains a `Scale`, `Rotate`, and `Translate` per `scripts/build_world_placed_merge.py` (which accumulates these into a final world transform). It does **not** contain a zone ID, a waypoint ID, or any human-readable location label.

## 2. The "zone" problem

The project data does not map asset IDs to in-game zones. The world transform gives a position in the game world's coordinate space, but the zone is determined by the in-game world partition (the same `(x, y, z)` can be in different zones depending on the active world map).

To prove a target asset/load condition, the operator must select a zone known to contain the asset and verify load by some out-of-band signal. The project cannot tell us which zone that is.

## 3. Best-available load candidates (operator must pick)

Since the project has no per-asset zone map, the load state must be established by operator knowledge of RIFT. The strongest available leads, in order of preference:

### 3.1 Preferred: any zone with a `diffuse_blank` placeable visible

The `diffuse_blank` texture is the dominant marker for this asset family. A zone where the operator can visually see and approach a `diffuse_blank`-textured decoration is the highest-probability load condition.

Practical operator instructions:

1. Log in to a RIFT character.
2. Travel to any of: Sanctum (Guardian), Meridian (Defiant), the planar shard hubs, or any capital city with many decorative placeables.
3. Approach any decorative object with a flat white appearance.
4. Stand within 5–10 in-game meters of the object so the mesh is in the streaming set.
5. Confirm the target is loaded by any out-of-band signal (e.g. the Gnomish RIFT UI hover, addon, or the asset name visible via the in-game `/target` macro or a `DevTool`-class addon).
6. Capture the operator-side state: zone name, character name, subzone/area name, in-game coordinates, distance to the object.

### 3.2 Acceptable fallback: a placeable-dense zone

If the visual hunt in 3.1 is impractical, any zone with a high density of decorative placeables is acceptable. Examples from operator experience in RIFT:

- Sanctum (Guardian capital)
- Meridian (Defiant capital)
- Tempest Bay (Sanhok refuge)
- Any large planar shard hub
- Any sliver / dungeon entrance with decoration around it

### 3.3 Worst case: pick a zone and accept the negative result

If 3.1 and 3.2 both fail, the operator can still authorise the live read in any in-zone state. The Phase 1 scan may return 0 hits (asset not loaded in that zone), which is a **valid negative result** — it just means the operator needs to try a different zone. The plan explicitly handles 0-hit as a closure branch:

> "0 hits for either ID → the target asset is **not loaded** in the current live session. Do not run Phase 2 or Phase 3. Capture the result, close negative for this load state, and re-test in a different load condition."

So the worst case is not a wasted scan; it is a zone-by-zone binary search. Each scan takes ~10s (the scanner default `TimeoutSeconds`) and is bounded at 16 MiB.

## 4. Operator-side load-state template

Before authorising the live read, the operator should capture and record:

| Field | Example / Notes |
|---|---|
| Zone | e.g. "Sanctum", "Meridian", "Tempest Bay" |
| Subzone / Area | e.g. "The Vault", "City Hub" |
| Character name | (redact for any committed records) |
| Character faction | Guardian / Defiant |
| Coordinates | in-game `(x, y, z)` if visible |
| Approximate target | description or `/target` name |
| Distance to target | in-game meters |
| Object visible | yes / no / partially |
| HUD/UI signal | any confirmation the asset is loaded (e.g. cursor highlight, nameplate) |
| Phase 1 scan time | record start/end wall-clock |
| Phase 1 outcome | pass (≥1 hit) / fail (0 hits) |
| Phase 2 outcome (if Phase 1 passes) | co-resident / not co-resident |
| Phase 3 outcome (if Phase 2 confirms) | representation confirmed / rejected |

This template is not committed; it is for the operator's working notes.

## 5. Hard prohibitions (carried forward from `docs/live-memory-readonly-safety-boundary.md`)

| # | Prohibition |
|---|---|
| 1 | No writes, DLL injection, remote threads, hooks, or process suspension. |
| 2 | No input sent to the game during the scan. |
| 3 | No full process memory dumps. |
| 4 | No committed live reports. |
| 5 | Output stays under ignored `Exports/discovery-plan/stage5-live/`. |
| 6 | Test/fixture paths must not attach to a live process. |
| 7 | Privacy: no chat text, account names, or local user-profile paths in any committed report. |

## 6. What the operator should NOT do

- **Do not run the live read in a high-traffic zone** (Sanctum at peak hours) where the asset set is dynamic and scan noise is high. The scanner is bounded (16 MiB / 256 regions / 10s), but a busy zone adds unrelated match noise.
- **Do not run the live read while the character is in combat or moving.** Static load conditions are easier to interpret than transient ones.
- **Do not run the live read while an addon is actively loading or unloading assets.** Addon-driven asset churn can produce false matches.
- **Do not assume the asset is loaded because the operator is "in the right zone"**. The Phase 1 scan result (0 vs ≥1 hit) is the proof, not the operator's intuition.

## 7. Live-read execution (not in scope for this handoff)

The actual live read requires the operator to invoke the scanner with all four safety flags. The exact invocation is **out of scope for this handoff** and will be documented in a separate "Authorise Phase 1 live read" handoff that the user requested as a followup. The dry-run command that validates the plan schema is already passing:

```text
python scripts/rift_workflow.py scan-live-memory \
  --live-pattern-file docs/live-memory-scan-targets.json \
  --list-json
```

Live execution will require the additional flags `--execute-live-read --experimental-live --confirm-live-read --pid <PID>` and the operator's pre-recorded load state from §4.

## 8. Status

- Handoff: **DRAFT — awaiting operator load-state capture and zone selection**.
- Tracked-file changes: **none** (research only).
- Live read executed: **false** (Phase 0 dry-run was run by the prior handoff, plan validated).
- Step 49 status: **unchanged** (still `closed-negative-current-live-state`).
- Step 50 final handoff: **unchanged** (no parser/export promotion).
- The scoped scan plan: **unchanged** from `docs/handoffs/2026-06-13-scoped-live-scan-asset-load-proof.md`.
