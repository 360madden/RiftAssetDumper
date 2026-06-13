# Repository instructions

- After finishing a task, include a short optional section with practical next steps or improvement ideas.
- Keep next steps brief, relevant, and non-repetitive.
- Always include optional top 10 followups for the next best recommended action.
- When invoking the `suggest_followups` tool, default to 10 followups sorted by priority with the highest-leverage followups for the current workflow first.
- Use emojis and tables when they improve clarity, especially in status reports, milestone summaries, risk summaries, and validation results.
- After major milestones, provide a detailed human-readable summary that explains what changed, why it matters, what was validated, and what remains uncertain.
- Continue autonomously on the next safe, relevant task when the user has opened that lane; keep the pace aggressive but preserve safety boundaries around destructive actions, live game interaction, copied assets, and public/privacy-sensitive output.
- Treat `Source/`, `Extracted/`, and `Exports/` as local/generated data unless the user explicitly says otherwise.
- Do not commit copied RIFT game assets or generated extraction output by accident.
- Redact Windows user-profile paths and account-like local usernames in chat, docs, and generated artifacts unless the user explicitly requests exact local paths; prefer environment-variable placeholders such as `%USERPROFILE%`.
- **Hard rule**: No new PowerShell (`.ps1`, `.psm1`) or significant CMD scripting from this point forward. All new code, tools, launchers, and automation must be written in Python. Existing thin wrappers may be maintained temporarily but should trend toward removal or minimal `.bat`/`.cmd` shims that only invoke Python. When starting Grok sessions in this repo, prefer the Python-based launcher (see `docs/grok-memory-and-context.md`).
- **All work must follow the project roadmap** (`docs/roadmap/project-roadmap.md`). Reference the current phase and milestone in handoffs and major commits. Use `docs/roadmap/current-phase.md` as the living pointer. Anti-drift rules in the roadmap are mandatory.

## Reasoning and task-routing safety policy

- Follow `docs/task-routing-safety-policy.md` for any model/agent/reasoning-effort routing decision.
- Default to high/extra-high reasoning for asset truth, API truth, runtime truth, memory/offset discovery, proof guards, schemas, cross-repo contracts, exporter gates, live game interaction, commit/push review, and architecture decisions.
- Use lower-intelligence/lower-reasoning execution only when safety is practically guaranteed: the task must be reversible, mechanical, bounded, explicitly specified, non-live, non-cross-repo, non-promotional, and reviewed by the main high-reasoning lane before it affects committed truth or guard behavior.
- Never let a lower-intelligence/lower-reasoning pass decide what is durable truth, promote a candidate, weaken a guard, stage generated asset output, or unblock live movement/export.
- If unsure, classify the work as high-risk and keep it on the stronger reasoning path.
