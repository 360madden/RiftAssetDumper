# Phase 1 M1.1 — 329 Family ID List for Systematic Probing

**Source**: Exports/post50-mesh329-family-proof.md (23 evidence groups)

## Full List of IDs in the Family (23)

```
0364ea142bc00ce7
04de901531a091ab
066fa520a8ce62e3
07c733b4eee3ed2e
1c4f0a1acdb5e141
35cc1dcce900d723
384fb5a30638d1aa
4eb7745610adf8c7
588211447a07e84a
69b4ce22b1c23887
69da9507d49c42ff
6e3c9ccc3c0389a1
7f3e71246752afb2
812d13ed780bdd64
83df87e22bff4a94
863db700617fe8f8
91ead5caf689a8a5
acccb682df4d4ad8
b57694c1f202ec07
c5a1982e92e15b7b
c74529260da63fb2
c9f03083db63fd81
f2c347fe81a5e3b2
```

## Priority Batch for Initial Probing (Highest vector count + known extra-stream examples)

Recommended first wave (8 IDs) for mesh#7 and mesh#34 probes:

1. **69da9507d49c42ff** — 77 vectors, largest payload (924)
2. **f2c347fe81a5e3b2** — 64 vectors (768)
3. **07c733b4eee3ed2e** — 56 vectors (672)
4. **83df87e22bff4a94** — 52 vectors (624)
5. **0364ea142bc00ce7** — 48 vectors (576) — has prior extra @304 data
6. **4eb7745610adf8c7** — 46 vectors (552)
7. **c5a1982e92e15b7b** — 45 vectors (540)
8. **91ead5caf689a8a5** — 31 vectors (372) — good mid-range sample

**Rationale for this batch**:
- Covers high vector count range.
- Includes previously probed examples for validation.
- Mix of sizes to detect patterns in attribute set behavior and @304 extra stream.

Once this wave is complete, remaining IDs can be run in a second wave if time/resources allow within the milestone.

## Next Step for Prober Agents
Use the Priority Batch above as the first assignment.

All probes must be run with `--skip-build` and results saved under Exports/.

This list is the controlled scope for M1.1. Do not add IDs from other families.