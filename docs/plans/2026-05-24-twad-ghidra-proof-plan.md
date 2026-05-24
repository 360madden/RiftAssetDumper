# TWAD Ghidra proof plan — 2026-05-24

## Execution status

Milestones 1, 2, and 4 are complete:

- `TWAD` compare site inspected in the retained Ghidra project.
- Byte-level archive/header cross-check completed against copied and live archive headers.
- Parser-facing test `TwadArchiveHeader_MatchesClientGhidraProof` added without changing production parser behavior.

Milestone 3 is partially complete through the generic `ghidra-run` workflow command and tracked `scripts/ghidra/FunctionSiteSurvey.java` template. A report summarizer remains optional future workflow hardening.

## Recommended goal

Prove the TWAD Ghidra lead without changing parser behavior: reuse the retained Ghidra project, inspect the compare at `0x1406e905e`, identify the owning function and caller/input path, cross-check against local asset/package bytes, write a hypothesis/proof handoff, add only minimal durable workflow support if needed, run validation and generated-output guard, and commit/push tracked artifacts only.

## Why this goal is first

| Option | Priority | Why |
| --- | ---: | --- |
| Prove `TWAD` lead | 1 | It is the only raw magic/code-path clue from the first Ghidra survey and may unlock archive/package structure. |
| Improve reusable Ghidra workflow | 2 | Useful after we know which Ghidra facts need repeated extraction. |
| Inspect `NiDataStream` / `NiMesh` leads | 3 | Valuable for geometry, but likely downstream of archive/package understanding. |
| Change parser code now | Not yet | Static hints are not parser truth. |

## Milestone 1: TWAD proof packet

**Goal:** determine what the `TWAD` compare is checking.

Use retained generated project:

- `Exports/ghidra-projects/RiftAnchorSurvey`

Focus location:

- probable compare instruction: `0x1406e905e`
- TWAD virtual address clue: `0x1406e9060`
- file offset clue: `0x6e8460`

Deliverable:

- Markdown proof note under `docs/handoffs/` or `docs/research/`
- no parser changes
- no generated output committed

Success condition:

- classify whether `TWAD` is likely archive magic, chunk magic, manifest/table magic, or an unrelated code constant.

## Milestone 2: Cross-check against real bytes

**Goal:** connect Ghidra's code clue to actual local asset/package bytes.

Actions:

- Search local generated/copied data only under ignored paths.
- Look for real `TWAD` occurrences in package/archive files.
- Compare byte layout around real `TWAD` with what the Ghidra function appears to validate.
- Record offsets and structure hypotheses.

Success condition:

- static code clue and real file bytes agree on at least one structure boundary.

Still no parser behavior changes.

## Milestone 3: Durable workflow support

Only after Milestone 1 or 2 proves useful, make tooling durable.

Possible additions:

- tracked Ghidra Java script template
- `rift_workflow.py ghidra-twad-survey`
- report summarizer
- tests for wrapper command construction

Success condition:

- future agents can rerun the same survey without recreating one-off scripts in `Exports/`.

## Milestone 4: Parser test, not parser rewrite

If `TWAD` is proven against real bytes:

- add a small parser-facing test or fixture summary
- assert detected magic/header fields
- keep behavior read-only first
- avoid OBJ/export work

Success condition:

- the parser can identify the proven structure without changing unrelated decode paths.

## Milestone 5: Only then consider parser changes

Parser changes should happen only when:

1. Ghidra code path is understood.
2. Real bytes match the hypothesis.
3. A small test exists.
4. Generated-output guard passes.
5. The change is bounded and reversible.

## Agentic split when practical

| Agent lane | Work |
| --- | --- |
| Main agent | Inspect `TWAD` function and decide truth/hypothesis level. |
| Search agent | Search repo/docs/current parser code for TWAD/archive assumptions. |
| Byte agent | Search ignored local asset/package bytes for matching `TWAD` structures. |
| Reviewer agent | Check no generated outputs are staged; verify proof language is not overstated. |

Avoid multiple agents writing overlapping files at once.

## Safety rules for this plan

- Do not change parser behavior during this goal.
- Do not stage or commit `Source/`, `Extracted/`, `Exports/`, build output, or local assistant/tool history.
- Treat Ghidra function names and addresses as hypotheses unless byte-level proof backs them.
- Commit only tracked plan/proof/tooling/test files after validation.
