# Task Routing Safety Policy 🛡️

Date: 2026-05-07

This project uses aggressive discovery, but not reckless delegation. The default posture is:

```text
Safety > truth integrity > validation > speed > cost savings
```

Lower-intelligence or lower-reasoning execution is allowed only when safety is practically guaranteed. If there is any real chance that a task can change project truth, proof gates, runtime assumptions, cross-repo contracts, live game behavior, generated/copy asset hygiene, or commit safety, keep it on the stronger reasoning path.

## Non-negotiable rule 🚦

> Use lower-intelligence execution only for reversible, mechanical, bounded tasks with explicit inputs and outputs. The main high-reasoning lane must review the result before it affects committed truth, guard behavior, live workflows, or pushed changes.

If unsure, classify the task as high-risk.

## Default routing matrix 🧠

| Work type | Required reasoning | Lower-intelligence allowed? | Reason |
|---|---:|---:|---|
| Asset truth classification | High / extra-high | ❌ No | Mislabeling assets creates false durable truth. |
| API truth classification | High / extra-high | ❌ No | API fields are the strongest current anchors and must stay precise. |
| Runtime memory / offset discovery | High / extra-high | ❌ No | Session addresses, offsets, and stale anchors are easy to over-promote. |
| Truth taxonomy | Extra-high | ❌ No | Bad categories poison future handoffs and guards. |
| Asset-guided reacquisition strategy | Extra-high | ❌ No | This is core project architecture. |
| Shared schemas / packet contracts | Extra-high | ❌ No | Schema mistakes create long-lived migration and interpretation debt. |
| Proof guard design or weakening | High / extra-high | ❌ No | Guards must fail closed and never silently bless false proof. |
| Cross-repo boundaries | High / extra-high | ❌ No | Prevents Assets/RiftScan/RiftReader contamination. |
| Live game interaction | High / extra-high | ❌ No | Live input and process interaction are safety-sensitive. |
| Exporter gates | High / extra-high | ❌ No | Export must stay blocked until proof is strong. |
| Commit/push review | High / extra-high | ❌ No | Prevents generated asset output, private paths, or incoherent milestones from landing. |
| Read-only grep/search | Medium allowed | ✅ Yes, with review | No mutation if scoped. |
| Formatting an approved Markdown table | Low/medium allowed | ✅ Yes | Reversible and mechanical. |
| Copying exact approved schema field descriptions | Low/medium allowed | ✅ Yes, with review | Mechanical if the schema is already approved. |
| Sorting known enum names | Low/medium allowed | ✅ Yes, with tests/review | Mechanical if behavior is unchanged. |
| Summarizing already-validated command output | Low/medium allowed | ✅ Yes, with no new truth claims | The validation already happened elsewhere. |

## Lower-intelligence eligibility checklist ✅

Every item must be true before using lower-intelligence execution:

| # | Requirement |
|---:|---|
| 1 | The task is reversible and does not require destructive operations. |
| 2 | The task is mechanical, not interpretive. |
| 3 | Inputs and expected outputs are explicit. |
| 4 | No live game interaction is involved. |
| 5 | No memory/process scanning is involved. |
| 6 | No exact address, offset, candidate, or proof anchor is being promoted. |
| 7 | No truth taxonomy, schema, guard, or promotion rule is being designed or changed. |
| 8 | No cross-repo edits are involved. |
| 9 | No `Source/`, `Extracted/`, or `Exports/` generated/copied asset output can be staged. |
| 10 | The main high-reasoning lane will review before commit, push, or any truth claim. |

If one item fails, use high/extra-high reasoning.

## Never delegate cheaply 🚫

Do not use lower-intelligence/lower-reasoning execution for:

- deciding whether something is durable truth;
- deciding whether a runtime address/offset is current or restart-stable;
- interpreting API-vs-asset-vs-runtime truth;
- creating or weakening proof guards;
- implementing promotion gates;
- designing shared packet schemas;
- changing cross-repo ownership rules;
- touching live input, target windows, process memory, or movement gates;
- enabling, documenting as ready, or implying readiness of model/OBJ export;
- staging, committing, or pushing without high-reasoning review;
- handling privacy-sensitive paths or account-like local identifiers without review.

## Safe lower-intelligence examples 🟢

These are acceptable only after the checklist passes:

| Task | Why it is safe |
|---|---|
| Reflow a Markdown table with already-approved content | Formatting-only and reversible. |
| Alphabetize a static list of known field names | Mechanical if behavior is unchanged. |
| Run a scoped read-only search and report raw hit counts | No mutation and no interpretation. |
| Generate boilerplate comments from an already-approved schema | Main lane reviews before commit. |
| Summarize a passed validation log without adding new claims | Truth was established by validation, not the summary. |

## High-risk examples 🔴

| Task | Why lower-intelligence is unsafe |
|---|---|
| Rename a runtime artifact from `candidate` to `truth` | Promotes evidence and can mislead future work. |
| Change a guard threshold | Can silently bless bad topology or runtime proof. |
| Interpret a changed memory offset after restart | Requires stale-vs-structural reasoning. |
| Decide whether `@264` is export-ready | Affects unsupported model output claims. |
| Add `Assets ↔ RiftScan ↔ RiftReader` packet contracts | Cross-repo architecture and schema design. |
| Stage a broad path like `.` | Could commit generated/copied game assets. |

## Commit and push gate 📦

Before any commit/push, the main high-reasoning lane must verify:

| Gate | Required check |
|---|---|
| Scope | `git status --short` and staged file list are intentional. |
| Generated data | `Source/`, `Extracted/`, and `Exports/` are not staged. |
| Privacy | No raw Windows user-profile path or account-like username is introduced. |
| Diff hygiene | `git diff --check` and/or `git diff --cached --check` passes. |
| Validation | Relevant build, guard, smoke, or documentation check was attempted. |
| Truth wording | New docs distinguish API truth, asset truth, runtime-session proof, restart-stable structure, and historical anchors where relevant. |

## Project-specific truth routing 🧭

| Truth class | Strong reasoning required? | Notes |
|---|---:|---|
| API contract truth | ✅ Yes | Most durable current live anchor; do not overstate sample values as permanent. |
| Static asset truth | ✅ Yes | Durable until local files or client patch change. |
| Asset-derived schema | ✅ Yes | Treat as hypothesis until enough files corroborate it. |
| Runtime-session proof | ✅ Yes | Valid only for current process/session unless revalidated. |
| Restart-stable structure | ✅ Yes | Requires at least two-session rediscovery logic. |
| Exact runtime address | ✅ Yes | Never durable by itself. |
| Historical handoff/capture | ✅ Yes | Use as lead history, not current truth until refreshed. |

## Routing summary 🧷

Use this short decision rule:

```text
Can this task affect truth, proof, schemas, guards, runtime state, live input, cross-repo boundaries, generated asset hygiene, or pushed history?
  yes -> high/extra-high reasoning
  no  -> lower reasoning may be used only if the checklist passes and main-lane review follows
```

This policy is intentionally conservative. The project is allowed to move fast, but not by letting low-risk formatting rules leak into high-risk discovery decisions.
