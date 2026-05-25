# Handoff — Ghidra FunctionSiteSurvey data-ref byte samples

Date: 2026-05-25

## Goal

Improve the Ghidra static-analysis workflow so descriptor-helper/table follow-up can inspect bounded bytes at memory-backed data references without broad dumps or parser/export changes.

## What changed

- `scripts/ghidra/FunctionSiteSurvey.java` now emits optional `dataRefByteSamples` for unique memory-backed DATA references from the surveyed function.
- Each sample records:
  - referenced address,
  - requested byte count,
  - bytes read,
  - hex bytes,
  - read error when unavailable.
- The sample is bounded to 64 unique DATA refs and 32 bytes each.
- `docs/schemas/ghidra-function-site-survey-v1.schema.json` documents the new optional field.
- `scripts/ghidra_report_summary.py` now summarizes data-ref byte sample counts and rows.
- `scripts/test_ghidra_report_summary.py` covers summary output for sampled bytes.
- Workflow docs now state that new FunctionSiteSurvey runs can capture bounded `dataRefByteSamples`.

## Why it matters

The current `NiDataStream` descriptor lane needs exact evidence for descriptor bytes 1-2. Existing helper/builder reports show static table references such as descriptor helper table offsets, but prior reports did not include the bytes at those data refs. New FunctionSiteSurvey reruns can now capture small, candidate-only byte windows around those references for review.

## Validation

Passed:

```powershell
# Compile FunctionSiteSurvey.java against local Ghidra 12.1 jars into a temp output folder.
<jdk>\bin\javac.exe -cp <all-ghidra-jars> -d <temp> scripts\ghidra\FunctionSiteSurvey.java

python -m py_compile scripts/ghidra_report_summary.py scripts/test_ghidra_report_summary.py
python scripts/test_ghidra_report_summary.py
python scripts/test_schema_registry.py
ruff check scripts/ghidra_report_summary.py scripts/test_ghidra_report_summary.py
mypy scripts/ --no-error-summary
python scripts/test_ghidra_runner.py
python scripts/rift_workflow.py ghidra-function-site-target-guard
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Generated output safety

- No copied RIFT assets or generated extraction/report outputs are intended to be staged.
- The Java compile emitted classes only to a temp folder, which was removed.
- `generated-output-guard` reported 0 tracked and 0 staged generated/copy/build output paths.

## Known blockers

- Existing ignored reports under `Exports/ghidra-reports/` were not rerun in this slice, so they do not yet contain `dataRefByteSamples`.
- Data-ref byte samples remain static/candidate-only evidence and must not be consumed by decode/export paths.
- Parser/export promotion remains locked until exact byte semantics, negative fixtures, and guards are in place.

## Next recommended actions

1. Rerun only the NiDataStream descriptor helper/builder FunctionSiteSurvey targets to refresh ignored reports with `dataRefByteSamples`.
2. Summarize the refreshed reports and compare sampled static-table bytes against the descriptor context review queue.
3. Keep any discovered mapping candidate-only until parser fixtures and promotion guards prove it.
