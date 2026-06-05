# Session Handoff — 2026-06-11: First Live-Archive OBJ Export

**Commit:** `97e0f25` — `feat: first live-archive OBJ export — meshSize=362`

## Action: Live Archive MeshSize=362 OBJ Export

**First OBJ exported from live RIFT archives** — a completely new MeshSize family not present in the copied Source set.

| Metric | Value |
|--------|-------|
| Asset ID | `cf54e712ff57eaac` |
| Mesh block | #6 |
| Mesh size | **362** (new family) |
| Source archive | assets.002 (entry 1191) |
| Root | `C:/Program Files (x86)/Glyph/Games/RIFT/Live` |
| Vertices | 6,489 |
| Normals | 6,489 |
| UVs | 6,489 |
| Faces | 6,487 (fan fallback) |
| OBJ size | 776 KB |
| NaN values | 0 |
| Attribute sets | 0 (used `--experimental-position-source`) |

**OBJ path:** `Exports/decode-nif-geometry-cf54e712ff57eaac.json/decode-nif-geometry-mesh6.obj`

## Live Archive State

| Metric | Value |
|--------|-------|
| Total live archives | 244 (9× Source's 27) |
| Mesh sizes found (live scan) | 19+ (up to 417) |
| New families confirmed | 362 (exported ✅), 341 (unprobed), 357 (exists, Count=3, no ID yet) |
| meshSize=357 | Found in live-mesh-inventory-500.json TopPatterns (Count=3, no SampleAssetIdPrefix) |
| meshSize=341 | Not found in current live inventory scans |

## CI Status (All Green ✅)

| Check | Result |
|-------|:------:|
| `dotnet build` | 0 errors |
| `dotnet test` | 50/50 pass |
| `ruff check scripts/` | 0 violations |
| `mypy scripts/` | 0 errors |

## Live Inventory File Issues

Multiple live inventory JSON files have UTF-8 BOM headers that require `encoding='utf-8-sig'` to parse. The 21MB `live-mesh-inventory-500.json` contains mesh sizes up to 417 but asset IDs aren't populated in TopPatterns entries for new sizes.

## Next Steps

| Priority | Action |
|:--------:|--------|
| 1 | **Find meshSize=341 and 357 IDs** — run `python scripts/live_inventory.py --max 2000` or targeted C# probe to locate asset IDs for probing/export |
| 2 | **Export meshSize=357** once IDs found — potentially second new live-family OBJ |
| 3 | **Scale live scanning** — the 244-archive scan timed out at 10 min; consider batch scanning or parallelization |
| 4 | **meshSize=417 discovery** — live scan found mesh sizes up to 417, suggesting many more new families beyond the 3 already identified |
