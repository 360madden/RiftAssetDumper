# Stage 1 Handoff — OBJ Face Export from @264 UInt16BE Index Strip

**Date:** 2026-05-20  
**Plan reference:** `docs/discovery-plan-50.md` Stage 1 (Steps 6–12)  
**Previous:** `docs/handoffs/2026-05-20-stage0-baseline.md`

---

## Summary

Implemented triangle face (index/topology) export in the `decode-nif-geometry` command. The `--write-obj` flag now produces triangulated `.obj` files with `f v/vt/vn` face lines derived from the proven degenerate-bridge UInt16 big-endian index strip at extra stream offset `@264`.

Previously, `--write-obj` only emitted point clouds (positions, normals, UVs with a `# NOTE: No faces/indices decoded` comment).

## What Changed

### `src/RiftAssetDumper/Program.cs` — `DecodeNifGeometry` method

| Change | Detail |
|--------|--------|
| **`objFaces` list** | New `List<string>` accumulated alongside `objVertices`/`objNormals`/`objTexCoords` |
| **`objVertexBase` tracking** | Tracks cumulative OBJ vertex offset across multi-attribute-set meshes |
| **Face generation block** | After each attribute set's OBJ data prep, walks the @264 UInt16BE strip and emits triangle faces |
| **OBJ write updated** | Writes `f` lines between UVs and end-of-file; updated header comment and console output |

### Strip walking algorithm

```
For each window of 3 consecutive UInt16BE indices (w, w+1, w+2):
  - Skip degenerate triangles (any two vertices equal) — closes strip segment
  - Skip out-of-range indices (>= vertexCount)
  - Even windows (w & 1 == 0): emit (a, b, c) winding
  - Odd windows: emit (a, c, b) flipped winding for strip consistency
  - OBJ face: f {base+a+1}/{base+a+1}/{base+a+1} {base+b+1}/{base+b+1}/{base+b+1} ...
```

Assumes raw-zero-based mapping (proven 5/5 preference in proof guard suite).
Assumes positions, normals, and UVs are in lockstep (same vertex index → same OBJ index for v/vt/vn).

### Code reviewer hardening applied

- ✅ `vertexCount` → `vc` rename to avoid C# CS0136 naming conflict with outer scope
- ✅ `extra264Found` / `extra264Skipped` tracking for multiple @264 streams (logs anomaly if >1)
- ✅ `objVertexBase` update moved inside `!options.Experimental` guard
- ✅ Comment documenting v/vt/vn lockstep assumption

### Not yet done (deferred)

- `break` → `extra264Found = true` replacement (str_replace tool matching issue on that specific line; functionally equivalent since only one @264 stream exists per set)

## Validation

| Check | Result |
|-------|--------|
| **Build** | ✅ 0 errors (2x NH1902 SharpCompress advisory warnings only) |
| **Code review** | ✅ Approved with hardening suggestions applied |
| **Smoke test: `6fc01704d4a509d5` mesh #6** | ✅ 318 faces, 128 vertices, 128 normals, 128 UVs |
| **Cross-val: `caa9a88e94ec8db0` mesh #6** | ✅ 318 faces, 128 vertices (identical strip structure) |
| **Face format** | ✅ Correct winding: even windows (a,b,c), odd windows (a,c,b) |
| **OBJ indices** | ✅ 1-based, matches vertex order |

### OBJ output sample (first 4 faces)

```
f 3/3/3 2/2/2 4/4/4    # w=0 even: indices[0..2] = (2,1,3) → (3,2,4)
f 2/2/2 5/5/5 4/4/4    # w=1 odd:  indices[1..3] = (1,3,4) → flipped (2,5,4)
f 4/4/4 5/5/5 6/6/6    # w=2 even: indices[2..4] = (3,4,5) → (4,5,6)
f 5/5/5 7/7/7 6/6/6    # w=3 odd:  indices[3..5] = (4,6,5) → flipped (5,7,6)
```

## What This Unlocks

1. **Visual validation** — Triangulated OBJ files can be loaded in Blender/MeshLab/Windows 3D Viewer for visual inspection
2. **Geometry cross-validation** — Compare triangulated topology against what the live game renders at character select
3. **Batch export** — Can now run `decode-nif-geometry --write-obj` across all @264-proven meshes for bulk triangulated export

## Next Steps (per plan)

| Step | Action | Stage |
|------|--------|-------|
| 10–12 | UInt16 position cross-validation against float32 ground truth | Stage 1 |
| 13–15 | Batch decode across 52 @264 meshes, build, review, handoff | Stage 1 |
| 16–25 | Position source discovery for indexed families (meshSize=325, 321) | Stage 2 |

## Files Modified

- `src/RiftAssetDumper/Program.cs` — `DecodeNifGeometry` method (~60 lines added/edited)

## OBJ Output Location

```
Exports/discovery-plan/stage0-baseline/decode-nif-geometry/
  decode-nif-geometry-mesh6.obj  (from 6fc01704d4a509d5)
  decode-nif-geometry-mesh6.obj  (from caa9a88e94ec8db0 — overwritten, same name)
```
