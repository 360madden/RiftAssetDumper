# Ghidra pairing review report handoff — 2026-05-24

## Status

Implemented a workflow-level candidate-only report for the Ghidra pairing review findings.

This is an integration/usability slice only. It reads the existing mesh-binding inventory, writes ignored JSON/Markdown reports under `Exports/`, and does not change parser, role-promotion, guard, export, or OBJ behavior.

## What changed

- Added workflow command:

```powershell
python scripts/rift_workflow.py ghidra-pairing-review-report --quick --limit 10
```

- Added `ghidra_pairing_review_report(...)` in `scripts/rift_workflow_reports.py`.
- The report reads `TopGhidraPairingReviewFindings` from `nif-mesh-binding-inventory.json` and emits:
  - `Exports/ghidra-pairing-review-report.json`
  - `Exports/ghidra-pairing-review-report.md`
- Each emitted finding is marked `CandidateOnly=true` and includes:
  - rank, review kind, priority, mesh size, count,
  - legacy and Ghidra role pairs,
  - legacy/Ghidra vertex semantic classes,
  - confidence summary,
  - sample id/mesh block and stream offsets,
  - legacy and Ghidra body first-byte evidence,
  - a ready `mesh-probe` command for the sample.
- Added Python regression coverage for the new report writer.
- Documented the command in README and the AI workflow guide.

## Validation evidence

Commands:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/rift_workflow_reports.py scripts/test_rift_workflow_reports.py
python scripts/test_rift_workflow_reports.py
ruff check scripts/rift_workflow.py scripts/rift_workflow_reports.py scripts/test_rift_workflow_reports.py
mypy scripts/rift_workflow.py scripts/rift_workflow_reports.py scripts/test_rift_workflow_reports.py --no-error-summary
python scripts/rift_workflow.py ghidra-pairing-review-report --quick --limit 10
```

Results:

| Check | Result |
|---|---|
| Python compile | PASS |
| Python report regression test | PASS |
| Ruff targeted check | PASS |
| Mypy targeted check | PASS |
| Workflow command smoke | PASS |
| Generated-output guard | PASS |

Workflow smoke produced ignored outputs only:

- `Exports/ghidra-pairing-review-report.json`
- `Exports/ghidra-pairing-review-report.md`

## Interpretation

The Ghidra review data is now easier to consume in the normal workflow loop. The next reviewer can open a compact Markdown table or consume JSON rows without hand-inspecting the full mesh-binding inventory.

## Remaining unwired pieces

- No export, OBJ, or guard behavior consumes Ghidra pairing review output.
- No single-sample C# probe mode yet compares decoded legacy-vs-Ghidra index/vector stats in detail.
- No promotable whitelist exists for Ghidra semantic transitions.
- Attribute-set logic still uses legacy/default roles.

## Recommended next milestone

Add a focused read-only C# probe enhancement for one review sample:

- include Ghidra sidecar pairings in `probe-nif-mesh`,
- print/index JSON legacy vs Ghidra body first bytes, role stats, and confidence side by side,
- keep the result candidate-only,
- do not touch export behavior.
