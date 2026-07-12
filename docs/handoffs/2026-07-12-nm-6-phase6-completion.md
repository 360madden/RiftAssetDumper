# NM-6 Phase 6 Completion — 2026-07-12

## Outcome

NM-6 M6.1-M6.4 are implemented and validated in the Assets repo.

| Milestone | Result |
|---|---|
| M6.1 hardening | Selected runs use `navmesh-index.selected.json` by default; full/selected scope and SHA-256 input provenance are recorded; Draft-07 instance validation is active; 29/29 M6.1 tests pass |
| M6.1 full batch | 4 eligible, 4 built, 0 failed, 10 skipped; source freshness check passes |
| M6.2 adjacency | 4 built nodes, 2 symmetric navmesh-vertex-proximity edges; graph schema validated |
| M6.3 cross-zone routing | Weighted A* plus Detour projection and per-zone segment concatenation; route schema validated |
| M6.4 validation | 3 reachable pairs pass below 1 ms; 3 disconnected nature-cohort pairs are explicitly reported; synthetic six-zone routes pass |

Housing initially produced zero polygons because normalized local geometry used
a world-scale 0.54 agent radius. The bounded `normalized_small` adaptive profile
uses a 0.05 radius and now produces 9 validated polygons.

## Durable files

- `scripts/build_all_navmeshes.py`
- `scripts/build_zone_connection_graph.py`
- `scripts/cross_zone_pathfind.py`
- `scripts/validate_multi_zone_navigation.py`
- `scripts/navmesh_pathfind.py`
- `docs/schemas/navmesh-index-v1.schema.json`
- `docs/schemas/zone-connection-graph-v1.schema.json`
- `docs/schemas/navmesh-cross-zone-route-v1.schema.json`
- `scripts/export_navigation_debug_obj.py`
- `.github/workflows/ci.yml` (full `pytest tests/` gate)

Generated evidence remains gitignored under `Exports/navmesh-phase6/`.

## Validation

- `ruff check .` — clean
- `mypy scripts --no-error-summary` — clean
- `pytest -q` — 1241 passed + 3 subtests passed
- `dotnet test RiftAssetDumper.slnx --no-restore` — 56 passed
- `dotnet format RiftAssetDumper.slnx --verify-no-changes --no-restore` — clean
- `build_all_navmeshes.py check-schema` — 14 zones pass Draft-07 validation
- `validate_multi_zone_navigation.py` — 3 reachable pairs pass; 3 disconnected pairs reported

## Scope boundary

M6.3 provides zone-level A*, projects each transition onto both adjacent Detour
meshes, and concatenates the resulting per-zone path segments. Off-mesh gaps are
bounded by the configured 10-unit connection threshold. It does not claim live
movement control or memory writes.
NM-7 remains optional and requires an explicit safety review.
