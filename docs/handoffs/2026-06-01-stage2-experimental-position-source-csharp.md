# Stage 2: ExperimentalPositionSource — C# implementation

**Date:** 2026-06-01  
**Status:** Complete ✅  
**Branch:** `main` (ahead by 1 commit)

---

## Summary

Added a new `--experimental-position-source` flag to `decode-nif-geometry` that enables position decoding from linked NiDataStream blocks when no standard attribute sets are found for a mesh.

This is a fallback path for NIF files where the standard `FindNifMeshAttributeSets` heuristic returns 0 sets — the mesh has bound streams but the position/normal/UV role assignment is non-standard or missing from the NIF metadata.

## What was implemented

### 1. `AppOptions` record — new `ExperimentalPositionSource` flag

Added `bool ExperimentalPositionSource` field to the `AppOptions` record, with:
- Variable declaration `var experimentalPositionSource = false;`
- CLI argument parsing `case "--experimental-position-source"`
- Constructor parameter `ExperimentalPositionSource: experimentalPositionSource`
- Help text in `PrintUsage()`

### 2. `DecodeNifGeometry` — fallback logic

When `attributeSets.Count == 0` and `options.ExperimentalPositionSource` is `true`:

1. **Scan linked streams** via `ScanNifLinkedStreamPositionCandidates()` — reuses the same scanner from `probe-nif-position-source`
2. **Filter float32 candidates** — only float32 position data is decoded (no UInt16)
3. **Decode positions** via `BuildNifAttributeFloatVertexSamples()` using the first float32 candidate
4. **Build OBJ vertex data** when `--write-obj` is set
5. **Generate trivial triangle fan faces** — since no index stream is available in this mode, we generate a fan from vertex 0 to each consecutive pair: `(1,2,3), (1,3,4), (1,4,5)...`

### 3. Variable scoping fix

Hoisted `objVertices`, `objNormals`, `objTexCoords`, `objFaces`, `totalPositions`, `totalNormals`, `totalUvs`, and `objVertexBase` declarations **before** the `if (attributeSets.Count == 0)` check so they're accessible in both the fallback path and the normal attribute-set path. Removed the duplicate declarations that previously existed further down in the function.

### 4. Console output improvements

- The `NIF geometry decode` header now shows `(linked-stream fallback)` label when in fallback mode
- The summary line similarly shows the fallback label instead of misleading "0 attribute sets"
- OBJ file header comments distinguish between "degenerate-bridge UInt16BE strip @264" (normal) and "trivial fan (no index stream available)" (fallback)

## Validated

| Check | Result |
|---|---|
| Build (`dotnet build`) | 0 errors, 2 warnings (pre-existing SharpCompress vulnerability) |
| Tests (`dotnet test`) | 6/6 passed, 0 failed, 0 skipped |
| Code review | Clean — no issues found |

## Usage

```bash
# Decode positions from linked streams when no attribute sets exist:
dotnet run --project src/RiftAssetDumper -- decode-nif-geometry \
  --root Source --id <16hex> --mesh-block <n> \
  --experimental-position-source --write-obj
```

## Known limitations (v1)

1. **Normals not decoded** — The fallback only scans for position candidates. Normal data from linked streams is ignored. Acceptable for v1; normals can be added when linked-stream role assignment improves.

2. **Trivial fan faces only** — No index stream is available in this fallback mode, so faces are generated as a simple triangle fan from vertex 0. This produces a valid OBJ that renders in most viewers, but does not represent the original mesh topology.

3. **Single candidate** — Only the first float32 position candidate is decoded. If multiple linked streams contain valid position data, the rest are skipped.

## Files changed

- `src/RiftAssetDumper/Program.cs` — ExperimentalPositionSource flag + fallback + face gen + console improvements

## Next recommended steps

1. Run `--experimental-position-source --write-obj` on a few target assets and verify OBJ output in a 3D viewer
2. Extend fallback to also decode normals from linked streams
3. Explore index stream candidates in linked streams for proper topology recovery
4. Consider adding `--experimental-position-source` to the Python workflow orchestrator (`rift_workflow.py`)
