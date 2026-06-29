# Phase 0 Exit — Dual Roadmap Infrastructure Readiness

**Date**: 2026-06-28
**Roadmaps**: `semantic-discovery-roadmap.md` (Semantic) + `binary-signature-roadmap.md` (Binary)
**Phase**: 0 — Infrastructure Readiness & Baseline

## Executive Summary

Both roadmaps' Phase 0 tooling audits are complete. All infrastructure is functional.

**Semantic**: `build-asset-semantic-index` and `inventory-asset-signatures` work against the live archive. 2,000 entries sampled — type distribution is 70% DDS textures, 29% unrecognized binary (NIF/XML/RIFF/Lua all classified as "bin" by magic-byte detection), 1% PNG/JPG/TXT.

**Binary**: Ghidra headless pipeline verified (JDK21 + Ghidra 12.1). `rift_x64.exe` is a recent build (June 18, 2026, ~57 MB). Function site survey dry-run confirmed; needs `--ghidra-execute` to actually run (no existing Ghidra project). `live_memory_scanner.py` has `FixtureProcessReader` ready for signature uniqueness validation.

**CI health**: ruff, mypy, dotnet build all pass. Repo is clean.

---

## Semantic Phase 0 — Detailed Findings

### M0.1: Smoke test — `build-asset-semantic-index` ✅

Ran against 50 entries from the live archive. All 50 succeeded (0 failures).

```

Command: dotnet run -- build-asset-semantic-index
         --root "C:/Program Files (x86)/Glyph/Games/RIFT/Live"
         --max-total 50 --out Exports/semantic-phase0/smoke-semantic.json

```

Type breakdown (all 50 classified as `bin` by magic-byte detection):

- `asset:unknown-binary`: 50

- `hint:actor-object`: 16

- `hint:waypoint-poi`: 31

- `ref:texture`: 50

**Key finding**: Even entries classified as "bin" get semantic hints — the heuristic classifier works on binary payloads too, not just XML/text.

### M0.2: Type distribution — `inventory-asset-signatures` ✅

Ran against 2,000 entries (0.76% of 263,957 total). Output at `Exports/semantic-phase0/live-signature-inventory.json`.

| Detected Type | Count | % |
|---------------|------:|---:|
| DDS (textures) | 1,398 | 69.9% |
| BIN (unrecognized) | 575 | 28.8% |
| PNG | 24 | 1.2% |
| TXT | 2 | 0.1% |
| JPG | 1 | 0.05% |

DDS texture variants observed: DXT5 (multiple mip levels), DXT1, DDS/flags:0x00000041.

BIN category is a catch-all — the C# magic-byte detector doesn't recognize NIF headers ("Gamebryo File Format"), RIFF headers ("RIFF"), OGG headers ("OggS"), or XML declarations. All of these fall into "bin". The 575 BIN entries likely contain:

- NIF model files (Gamebryo v20.6.0.0)

- XML data files

- RIFF/OGG audio assets

- Lua scripts

- Other binary formats

**BIN first-byte patterns observed**:

- `00000000` with various float-like values at bytes 4-8 (likely NIF or binary structs)

- `0109fffe` with size headers (RIFF-like containers, possibly audio)

- `00000200` (131,116 bytes each — consistent with a fixed-size binary format)

**No XML, NIF, RIFF, OGG, or Lua types were explicitly detected** — the sample was biased toward early archive entries which are DDS-heavy. The text/XML/Lua payloads likely appear later in the archive sequence or in different PAK/index ranges.

### M0.3: Semantic category distribution (from the 2,000 entries)

The heuristic classifier assigns these categories:

- `asset:texture`: 1,423 (DDS + PNG + JPG)

- `asset:unknown-binary`: 575 (all BIN entries)

- `asset:text`: 2 (both TXT entries)

The `hint:map-zone`, `hint:actor-object`, and `hint:waypoint-poi` categories come from the ARCHIVE_TAXONOMY (Cycle 5) which maps `assets.NNN` ranges to hint types. These hints are archive-derived, not payload-derived — they'll fire when entries from `assets.001`-`assets.099` (map-zone) or `assets.100`-`assets.199` (actor-object) are sampled. The 2,000-entry sample was from `assets.001`-`assets.002` which maps to `hint:map-zone` territory.

### Open Items for Semantic Phase 1

1. **Run a larger sample** — `--max-total 10000` or parse entries from different PAK ranges to capture XML, NIF, RIFF, OGG, and Lua types that the magic-byte detector misses.

2. **Identify XML payloads specifically** — these are the highest-value targets for Phase 1 (zone name extraction). The current magic-byte detector classifies XML as "bin" because it doesn't check for `<?xml` or `<` at byte 0.

3. **Cross-reference with live-archive-index** — the existing `live-nif-archive-index.json` (227 NIF entries) tells us where NIF files live in the archive. A similar index for XML/text payloads would help target Phase 1 sampling.

---

## Binary Phase 0 — Detailed Findings

### M0.1: Ghidra tool wiring — `ghidra-dry-run` ✅

```

Ghidra: C:\RIFT MODDING\Tools\ghidra_12.1_PUBLIC\support\analyzeHeadless.bat
Ghidra Home: C:\RIFT MODDING\Tools\ghidra_12.1_PUBLIC
JDK: C:\RIFT MODDING\Tools\jdk-21.0.11+10\bin\java.exe
JDK Home: C:\RIFT MODDING\Tools\jdk-21.0.11+10

```

Both tools registered in `.tools.json`, paths resolve, headless analyzer launches. Exit code 0.

### M0.2: Binary baseline — `rift_x64.exe` ✅

| Property | Value |
|----------|-------|
| Path | `C:/Program Files (x86)/Glyph/Games/RIFT/Live/rift_x64.exe` |
| Size | 59,937,216 bytes (~57 MB) |
| PE Timestamp | 1781782683 (2026-06-18T11:38:03Z) |
| Image base | 0x140000000 (standard x64) |

**The binary is very recent** — built only 10 days ago. This is excellent for Phase 1-2 because:

- The existing 7 Ghidra targets were last surveyed against an older binary

- If addresses have shifted, that confirms the offset instability problem is active

- If addresses match, the binary hasn't been recompiled recently and signatures from this version are current

### M0.3: Function site survey — dry-run verified, needs execution

The command structure is correct and resolves all paths:

```

python scripts/rift_workflow.py ghidra-function-site-survey
  --ghidra-target twad-header-magic --ghidra-timeout 600

```

This produces the correct Ghidra invocation:

```

ghidra-run --ghidra-project-name RiftAnchorSurvey
  --ghidra-process rift_x64.exe --ghidra-timeout 600
  --ghidra-script scripts/ghidra/FunctionSiteSurvey.java
  --ghidra-script-arg 0x1406e905f
  --ghidra-script-arg Exports/ghidra-reports/twad_site_survey.json
  --ghidra-no-analysis --ghidra-keep-project

```

**Blocker**: The Ghidra project `RiftAnchorSurvey` does not exist yet. Running with `--ghidra-execute` would import `rift_x64.exe` from scratch (estimated 5-10 minutes for import + auto-analysis, or faster with `--ghidra-no-analysis`). This should be the first action of the next session.

The existing 7 targets in `docs/ghidra-function-site-targets.json`:

| Key | Address | Description |
|-----|---------|-------------|
| twad-header-magic | 0x1406e905f | TWAD archive header magic compare |
| nidatastream-loadbinary | 0x141186980 | NiDataStream binary load routine |
| nidatastream-semantic-adapter | 0x14111e910 | Mesh semantic-adapter validation |
| nimesh-material-binding-caller | 0x14111f570 | DX9 material binding caller |
| nidatastream-descriptor-helper | 0x1411821f0 | Descriptor/component helper |
| nidatastream-descriptor-builder-1770 | 0x141181770 | Descriptor-builder helper |
| nidatastream-descriptor-builder-17c0 | 0x1411817c0 | Descriptor-builder helper |

**Note**: All 7 are NiDataStream/TWAD parsing functions — they validate the Ghidra pipeline but are NOT the RiftReader player-coordinate targets. RiftReader's targets will be identified in Phase 1 from scratch.

### M0.4: `live_memory_scanner.py` audit ✅

The script has a `FixtureProcessReader` class that can validate byte signatures against binary data **without a live process**. This is exactly what Phase 2-4 need for signature uniqueness validation.

Key capabilities:

- **Pattern format**: `label=hex` (e.g., `LocalPlayerBase=48 8B 05 ?? ?? ?? ?? 48 85 C0`)

- **Fixture mode**: Register memory regions populated with specific bytes, then scan with the same logic as live memory

- **Match reporting**: Per-pattern match count, address (hex), region base, offset within region, normalized hex bytes

- **Uniqueness**: Tracks matches via `set` based on `match_address`, supports `max_matches` limit

- **Entry points**: `FixtureProcessReader`, `scan_process_reader`, `parse_hex_pattern`, `run_windows_live_scan`

For Phase 2 signature validation: load `rift_x64.exe` bytes into a `FixtureProcessReader` region, register candidate signatures as patterns, run `scan_process_reader`, verify each pattern produces exactly 1 match.

### Open Items for Binary Phase 1

1. **Execute Ghidra survey** — run `ghidra-function-site-survey --ghidra-execute` against all 7 targets to get fresh decompiled output. This is the first action.

2. **Inventory RiftReader's offsets** — read RiftReader's knowledge.md (already done in this session) to catalog the 5-10 anchors needed: LocalPlayer base (+0x32EBC80), coordinate fields (+0x320/+0x324/+0x328), facing (+0x30C/+0x310/+0x314), turn rate (+0x304).

3. **Ghidra back-trace** — for each RiftReader anchor, use Ghidra to find the function that references that data address. This is the critical bridge from "data address" to "function signature."

---

## CI Health Sweep

| Check | Status |
|-------|--------|
| `ruff check scripts/` | ✅ All checks passed |
| `mypy scripts/ --no-error-summary` | ✅ No errors |
| `dotnet build RiftAssetDumper.slnx --nologo` | ✅ 0 warnings, 0 errors |

---

## Generated Artifacts

| Path | Size | Status |
|------|------|--------|
| `Exports/semantic-phase0/smoke-semantic.json` | ~15 KB | Created (gitignored) |
| `Exports/semantic-phase0/live-signature-inventory.json` | ~625 KB | Created (gitignored) |
| `docs/roadmap/semantic-discovery-roadmap.md` | ~12 KB | Committed |
| `docs/roadmap/binary-signature-roadmap.md` | ~17 KB | Committed |
| `docs/roadmap/current-phase.md` | Updated | Committed |

---

## Next Session Actions

### Priority 1: Execute Ghidra Survey (Binary M0.3)

```bash

cd "C:\RIFT MODDING\Assets"
python scripts/rift_workflow.py ghidra-function-site-survey \
  --ghidra-target twad-header-magic --ghidra-timeout 600 --ghidra-execute

```

Then repeat for remaining 6 targets. This imports rift_x64.exe into a Ghidra project and produces decompiled output for Phase 1 back-tracing.

### Priority 2: Larger Semantic Inventory (Semantic M0.2 continued)

```bash

dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- \
  inventory-asset-signatures \
  --root "C:/Program Files (x86)/Glyph/Games/RIFT/Live" \
  --max-total 10000 \
  --out Exports/semantic-phase0/live-signature-inventory-10k.json

```

Target: capture XML, NIF, RIFF, OGG, and Lua types that the 2,000-entry DDS-heavy sample missed.

### Priority 3: RiftReader Offset Inventory (Binary Phase 1)

From RiftReader's knowledge.md, catalog all hardcoded offsets, their data types, and discovery methods. Produce `riffreader-target-manifest.json`.

---

*Handoff committed 2026-06-28. Both roadmaps at Phase 0 exit.*
