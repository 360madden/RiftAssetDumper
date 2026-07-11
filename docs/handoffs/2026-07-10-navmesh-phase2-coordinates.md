# Session Handoff — 2026-07-10 (Navmesh Phase 2: Coordinate System Alignment)

## Summary

Shipped the NM-2 Coordinate System Alignment infrastructure.  Because the
RIFT game process is not currently running, the live-memory capture path is
implemented but not exercised; the transform math, calibration helpers, and
offline stub path are fully tested and green.

---

## What shipped

### 1. `scripts/navmesh_coord_transform.py`

Core OBJ↔live-memory coordinate transform API.

| Function | Purpose |
|---|---|
| `load_transform(path)` | Load and validate `coord-transform.json` |
| `save_transform(transform, path)` | Serialize a transform to JSON |
| `obj_to_memory(x, y, z, transform)` | Convert OBJ/world coords → live memory coords |
| `memory_to_obj(px, py, pz, transform)` | Convert live memory coords → OBJ/world coords |
| `compute_transform(samples, validation_tolerance=0.5)` | Compute affine transform from calibration landmarks |

Transform math:

```text
memory = (obj * scale * axis_mapping) + offset
obj    = (memory - offset) / (scale * axis_mapping)
```

- `axis_mapping` is ±1 per axis, determined by correlation sign.
- Scale and offset are solved per-axis via simple linear regression on the
  mapped memory values.
- RMSE is computed per-axis and validated against `validation_tolerance`.
- Minimum of 3 landmarks required for meaningful RMSE/tolerance validation.

CLI examples:

```bash
python scripts/navmesh_coord_transform.py --transform Exports/navmesh-phase2/coord-transform.json --obj-to-mem 1.0,2.0,3.0
python scripts/navmesh_coord_transform.py --transform Exports/navmesh-phase2/coord-transform.json --mem-to-obj 10.0,20.0,30.0
```

### 2. `scripts/navmesh_calibration_capture.py`

CLI for capturing calibration landmarks and computing the transform.

| Mode | Purpose |
|---|---|
| `--stub` | Generate deterministic synthetic samples and compute transform |
| `--live --landmark <id> --obj-pos x,y,z` | Read live player position from memory and append to a landmark |
| `--compute` | Compute transform from existing `calibration-samples.json` |

The `--live` path dynamically imports `RIFTMemoryScanner` from
`scripts/rift_memory_scanner` and reads the player position using the known
LocalPlayer pointer offset (`0x32EBC80`) and field offsets (`pos_x=0x320`,
`pos_y=0x324`, `pos_z=0x328`).

Examples:

```bash
# Offline stub (game not running)
python scripts/navmesh_calibration_capture.py --stub --out Exports/navmesh-phase2/coord-transform.json

# Live capture (game must be running)
python scripts/navmesh_calibration_capture.py --live --landmark ep1_statue_base --obj-pos 123.4,10.0,-56.7 --samples Exports/navmesh-phase2/calibration-samples.json

# Compute from saved samples
python scripts/navmesh_calibration_capture.py --samples Exports/navmesh-phase2/calibration-samples.json --compute --out Exports/navmesh-phase2/coord-transform.json
```

### 3. `tests/test_navmesh_coord_transform.py`

11 tests covering:

- Identity, scale/offset, and axis-flip round-trips
- Transform computation from stub samples
- Insufficient-landmark rejection
- RMSE tolerance rejection
- Transform JSON save/load
- Missing-file and invalid-data error handling
- Calibration helper `add_landmark`

### 4. `docs/roadmap/navmesh-navigation-roadmap.md`

Updated NM-2 status to ✅ DONE.

---

## Validation

| Check | Command | Result |
|---|---|---|
| ruff | `ruff check scripts/navmesh_coord_transform.py scripts/navmesh_calibration_capture.py tests/test_navmesh_coord_transform.py` | ✅ Clean |
| mypy | `mypy --no-error-summary scripts/navmesh_coord_transform.py scripts/navmesh_calibration_capture.py` | ✅ Clean |
| pytest | `pytest tests/test_navmesh_coord_transform.py -v` | ✅ 11 passed |

---

## Known limitations

- The `--live` capture path has not been exercised because the RIFT game
  process is not currently running.
- The `RIFTMemoryScanner` method signatures (`find_process`, `open_process`,
  `find_module`, `read_pointer`, `read_float`) were only statically verified
  against `scripts/rift_memory_scanner.py`; no live process was available to
  confirm the scanner opens, reads, and closes correctly.
- The hardcoded LocalPlayer pointer offset (`0x32EBC80`) and field offsets
  (`0x320`/`0x324`/`0x328`) are correct for the current game client per the
  binary-signature roadmap, but they should be refreshed from the signature
  database if the client ever patches.
- Only the stub transform (scale=10, offset=[0,5,0], no axis flip) has been
  validated end-to-end.

---

## Next steps

1. **Exercise live capture** — launch RIFT, stand at known landmarks, run
   `navmesh_calibration_capture.py --live` to build real calibration samples,
   then run `--compute` to produce the real `coord-transform.json`.
2. **NM-4 Runtime Bridge** — wire live player position to navmesh projection
   and pathfinding (`scripts/navmesh_state.py`).
3. **NM-5 Visualization** — export navmesh/path debug OBJs for RiftFlythrough.

---

## Artifacts

- `scripts/navmesh_coord_transform.py` (committed)
- `scripts/navmesh_calibration_capture.py` (committed)
- `tests/test_navmesh_coord_transform.py` (committed)
- `docs/handoffs/2026-07-10-navmesh-phase2-coordinates.md` (this file)
- `Exports/navmesh-phase2/coord-transform.json` (gitignored, generated by `--stub`)
- `Exports/navmesh-phase2/calibration-samples.json` (gitignored, generated by `--stub` or `--live`)

---

*End of handoff.*
