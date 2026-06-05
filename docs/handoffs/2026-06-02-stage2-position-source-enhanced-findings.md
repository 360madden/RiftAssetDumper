# Handoff: Stage 2 — Position-source enhanced: normals + UVs + `--write-obj`

**Date:** 2026-06-02  
**Parent:** `docs/handoffs/2026-06-01-stage2-position-source-probe-csharp.md`  
**Status:** ✅ Complete — build 0 errors, 6/6 tests pass, end-to-end validated

---

## What was done

### 1. C#: Extended `ExperimentalPositionSource` fallback (Program.cs)

The `decode-nif-geometry` fallback (triggered when `attributeSets.Count == 0`) now decodes **normals** and **UVs** from linked NiDataStream blocks in addition to positions.

**Key details:**

- Candidates filtered by `Role.StartsWith("normal-", StringComparison.OrdinalIgnoreCase)` and `Role.StartsWith("uv-", StringComparison.OrdinalIgnoreCase)` — safer than `Contains` to avoid false matches.
- Uses existing `BuildNifAttributeFloatVertexSamples()` with `components: 3` for normals and `components: 2` for UVs.
- Console output prints first 4 normal samples with `VectorLength` for validation, plus sample counts.
- OBJ writing appends `vn` and `vt` lines when `--write-obj` is set.
- Summary line shows `"linked-stream fallback"` instead of `"0 attribute sets"` for clarity.

**Validated on `e3de1077a37d0337` mesh#6:**

- 71 positions decoded from component #24 (`position-float3-ror1-lead`)
- 71 normals decoded from component #25 (`normal-float3-ror1-lead`)
- 71 UVs decoded from component #26 (`uv-float2-ror1-lead`)
- OBJ written with all vertex components + trivial fan faces

### 2. Python: `--write-obj` flag wiring (rift_workflow.py)

**Changes:**

- Added `write_obj: bool = False` parameter to `_run_dotnet_and_summarize()`
- Forwarded `--write-obj` to dotnet args when `write_obj=True`
- Added `--write-obj` CLI argument to `decode-geometry` command in `_run_command()`
- Passed `write_obj=args.write_obj` from handler

**Usage:**

```powershell
python scripts/rift_workflow.py decode-geometry --id e3de1077a37d0337 --mesh-block 6 --experimental-position-source --write-obj
```

### 3. Inventory: Zero-attribute mesh gap size

Full copied-set mesh-binding inventory confirms **5,455 meshes (99%)** have 0 attribute sets. This makes the `ExperimentalPositionSource` fallback critical for geometry export coverage.

---

## Validation checklist

| Check | Result |
|---|---|
| `dotnet build` | ✅ 0 errors |
| `dotnet test` (6 tests) | ✅ Pass first try |
| Code review (deepseek-flash) | ✅ Clean — no issues found |
| End-to-end: Python CLI + `--write-obj` | ✅ OBJ written at `Exports/decode-nif-geometry/decode-nif-geometry-mesh6.obj` |
| Normal VectorLength sanity | ✅ Samples show unit-length normals (~1.00) |
| Safer `StartsWith` role filtering | ✅ Applied instead of `Contains` |
| Summary line clarity | ✅ Shows "linked-stream fallback" instead of "0 attribute sets" |

---

## Known limitations (v2)

1. **Faces**: Trivial triangle fan (vertex 0 to consecutive pairs) — no index stream available in fallback mode.
2. **Single candidate**: Only the first float32 candidate per role is used; multiple are skipped.
3. **Coverage gap**: Many 0-attribute-set meshes may lack float32 position streams entirely — position discovery for the `meshSize=325` indexed family remains the stronger lead.
4. **Output path**: `--write-obj` writes OBJ to a subdirectory under the probe-report JSON path — cosmetic overlap, pre-existing.

---

## Files changed

| File | Change |
|---|---|
| `src/RiftAssetDumper/Program.cs` | Extended `ExperimentalPositionSource` fallback with normals + UVs decode and OBJ export |
| `scripts/rift_workflow.py` | Added `--write-obj` flag to `decode-geometry` command |
| `docs/current-status.md` | Updated status table, known limitations, and next steps |

---

## Next recommended steps (top 10)

1. **Run `--experimental-position-source --write-obj` on a 0-attribute-set mesh that has float32 position candidates** — verify OBJ export works on the primary (non-fallback) target mesh family.
2. **Investigate the `meshSize=325` / `@292+#23` / `@216+#25` / `@300+#29` indexed family** — this is the strongest position-source lead with proven index streams.
3. **Decode positions from `position-float3-ror1-lead` component in 1-attribute-set meshes** (210 meshes have this) — these have proven position data via the normal attribute-set path.
4. **Add a disabled experimental OBJ exporter** behind a `--export-obj` gate for the attribute-set path (not just the fallback).
5. **Scan the 5,455 zero-attribute-set meshes for any float32 position candidates** — quantify how many the fallback actually covers.
6. **Test OBJ output in external 3D viewer** (Blender, etc.) to validate visual quality.
7. **Extend `AttributeExtraProofGuard`** to catch regressions in the fallback's role-filtering and vertex-count logic.
8. **Add a focused mesh probe command** that prints attribute-set count + linked stream roles + float32 candidate summary for quick mesh triage.
9. **Consider extracting the fallback decode into a shared helper** to reduce code duplication with the attribute-set decode path.
10. **Run full mesh-binding inventory with `--full`** to refresh the zero-attribute-set coverage numbers.
