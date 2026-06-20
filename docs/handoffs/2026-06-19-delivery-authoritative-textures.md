# Delivery-Authoritative Textures — Session Handoff

**Date:** 2026-06-19
**Phase:** Consumer visual fidelity — make the Assets→RiftFlythrough delivery authoritative
**Status:** ✅ COMPLETE — Phase A (producer) + Phase B (consumer overlay) shipped; all gates green

---

## Why this mattered

The v0.8 delivery JSON shipped 404 NIF-confirmed `linked_textures`, but:

1. **Never consumed** — no RiftFlythrough JS read `linked_textures`. The consumer rebuilt its texture map from a *separate* source (`nif-texture-links.jsonl`) into `texture_map.js` (691 entries). The two representations drifted independently.
2. **Dead absolute Windows paths** in every entry (`obj_path`/`world_json`) — unreadable in a browser **and** a violation of the AGENTS.md privacy rule.
3. **Builder fragility** — `vv0.1` markdown typo, zero tests, never run in CI. Hand-built, drifted silently.

The NIF-confirmed texture linkage the Assets repo is proud of was shipped over the wire and thrown away.

---

## What shipped

### Phase A — Producer hardening (`scripts/build_riftflythrough_delivery.py` v0.1 → v0.2)

| Change | Detail |
|---|---|
| 🔒 Path policy | Removed absolute Windows paths from emitted JSON. Per-entry `obj_path`/`world_json` → `asset_id` + relative `obj_mesh` hint. Hard guard aborts if any `[A-Za-z]:\` leaks into output. |
| 🎨 `linked_texture_urls` | Resolves raw `linked_textures` basenames against the consumer's `textures/converted/` inventory into the consumer-consumable form `world.js` expects: `[{pattern, url}]` with `url = textures/converted/<file>.png`. Raw list kept for provenance. |
| 🐛 Typo fix | Markdown producer line rendered `vv0.1` (doubled `v`) → now `v0.2`. |
| 📝 Version | `PRODUCER_VERSION` v0.1 → v0.2; `SchemaVersion` unchanged (`riftflythrough-delivery/v1` — wire shape stays `asset_id`-keyed). |
| ✅ Tests | New `tests/test_build_riftflythrough_delivery.py` (5 tests): `--help` smoke, build smoke, no-absolute-paths regex sweep, wire contract (schema/version/url-shape/pattern=asset_id), non-empty URL resolution. |

**Resolution result:** 404/404 raw links resolved to URLs (100%), across 153 assets. The first entry's resolved URLs exactly match `texture_map.js` line 6-7 — the producer-side resolution is byte-identical to the consumer's independent path. ✅

> **Path note:** input path construction `REPO_ROOT/"Assets"/…` reaching the canonical nested `Assets/Assets/` data tree was confirmed **correct, not a bug** — only the *emitted* output paths were the privacy/portability problem.

### Phase B — Consumer overlay (RiftFlythrough repo)

| File | Change |
|---|---|
| `js/texture_loader.js` (new) | IIFE mirroring `transform_loader.js`: non-blocking fetch of `riftflythrough-delivery.json`, builds `Map<nifHash, url[]>`, exposes `RiftTextureLoader.urlsFor()` (async) + `urlsForSync()` (peek). Graceful fallback: on fetch/parse failure the overlay stays empty = zero regression. |
| `js/world.js` | `textureMapUrls()` (line ~358) now consults the delivery overlay **first** (delivery-authoritative), falling back to `TEXTURE_MAP` where the delivery has no entry or before it settles. +6 lines, no signature change. |
| `flythrough.html` | One `<script src="js/texture_loader.js">` tag after `texture_map.js`, before `transform_loader.js`. |
| `js/riftflythrough-delivery.json` | Regenerated v0.2 (404 resolved URLs, path-clean) copied in. |

**Merge policy:** delivery-first for the 153 consumer-ready assets; `TEXTURE_MAP` (691 entries/212 assets) still serves the 64 non-consumer-ready hashes. No coverage lost.

---

## Validation

| Gate | Result |
|---|---|
| Assets pytest (full) | **473/473 ✅** |
| Assets ruff check (scripts+tests) | ✅ clean |
| Assets ruff format | ✅ already formatted |
| Assets mypy (builder) | ✅ no issues |
| Consumer `node --check` (texture_loader.js) | ✅ SYNTAX OK |
| Consumer `check_js.py` | ✅ **35/35** modules |
| Consumer `check.py` (HTML + JS) | ✅; ⚠️ 1 pre-existing FAIL = `validate_obj` on `merged.obj` (214 normal-index OOB — source-export data issue, **unrelated to this work**) |
| Delivery JSON path sweep | ✅ 0 drive-letter paths, 0 backslashes |
| Delivery JSON wire contract | ✅ 404 URLs, all `textures/converted/...`, all patterns 16-hex |

---

## Commits / staging

**Assets repo** (uncommitted at handoff — review before commit):
- `scripts/build_riftflythrough_delivery.py` (modified)
- `tests/test_build_riftflythrough_delivery.py` (new)

**RiftFlythrough repo** (uncommitted at handoff):
- `js/texture_loader.js` (new)
- `js/world.js` (modified — `textureMapUrls`)
- `flythrough.html` (modified — one script tag)
- `js/riftflythrough-delivery.json` (regenerated v0.2)

> `Exports/` output is gitignored — the rebuilt stage8 JSON is local-only, not staged.

---

## What remains uncertain

- **Live visual confirmation** not captured in this session (would need a browser run + screenshot). The overlay's `console.log` line (`delivery overlay: N hashes, M textures authoritative`) is the runtime proof point. Pre-existing `merged.obj` validate_obj failures (214 OOB normal indices) are the larger, separate fidelity blocker.
- **Timing robustness**: overlay fetch (193KB) starts at page-init; texture discovery runs after `merged.obj` (2.5MB) loads. Near-certain to settle first, but on a very cold/slow network `urlsForSync` may return null on first pass → pure `TEXTURE_MAP` fallback (no regression, just no delivery preference that frame).

---

## Next best actions (priority order)

1. 🔴 **Visual smoke**: open `flythrough.html`, confirm console shows `delivery overlay: 153 hashes, 404 textures authoritative` and texture stat ≥ baseline; capture before/after.
2. 🟠 **Commit both repos** (Assets: builder+test; RiftFlythrough: overlay+html+world+delivery) after high-reasoning review per the routing policy.
3. 🟠 **Re-measure true texture coverage** to replace the stale "11.8%" figure in RiftFlythrough `SESSION_HANDOFF`.
4. 🟡 **Close the 153↔217 gap**: extend delivery `linked_texture_urls` to the 64 non-consumer-ready assets (point-only / textureless) so the overlay covers the full set.
5. 🟡 **Add builder to CI** (`.github/workflows/ci.yml`) so the delivery JSON is rebuilt + path-gate validated on every push.
6. 🟡 **Diff & reconcile** delivery `linked_textures` vs `nif-texture-links.jsonl` into a single source of truth; consider deprecating the consumer's independent `build_texture_map.py` path.
7. 🟢 **Pick up Discovery Cycle 3 frontier**: lighthouse `b89ced7d511388d2` has 17/27 NiMesh blocks unexplored — a named landmark directly addresses "not a recognizable RIFT environment".
8. 🟢 **Pipeline integration**: the 27 new Cycle-3 OBJs (meshSize 297/321) aren't in `flythrough-index.json` or scene manifests yet, so they can't reach the consumer.
9. 🟢 Add `delivery_validation_guard()` to `scripts/rift_workflow_guards.py` for stronger local enforcement.
10. 🟢 Surface per-asset texture coverage (red/amber/green) in the delivery markdown report.
