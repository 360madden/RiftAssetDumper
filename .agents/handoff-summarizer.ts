import type { AgentDefinition } from './types/agent-definition'

const definition: AgentDefinition = {
  id: 'handoff-summarizer',
  displayName: 'Handoff Summarizer',
  model: 'deepseek/deepseek-v4-flash',
  reasoningOptions: { effort: 'high' },

  toolNames: [
    'read_files',
    'code_search',
    'write_file',
    'glob',
    'list_directory',
    'run_terminal_command',
    'set_output',
  ],

  spawnableAgents: [
    'codebuff/commander@0.0.26',
    'codebuff/code-searcher@0.0.27',
    'codebuff/reviewer@0.0.11',
  ],

  spawnerPrompt:
    'Use to generate structured session handoff documents for the RIFT asset dumper project. ' +
    'The agent reads the current project state (git diff, test results, guard outputs, current-status.md) ' +
    'and writes a timestamped handoff to `docs/handoffs/` with findings, blockers, and next steps.',

  inputSchema: {
    prompt: {
      type: 'string',
      description:
        'Session summary: what was accomplished, what changed, what\'s blocked, and what the next priority is. ' +
        'Optionally specify a custom output file path.',
    },
  },

  instructionsPrompt:
    'You generate structured session handoff documents for the RIFT asset dumper project.\n\n' +
    '## Handoff format\n\n' +
    'Write to `docs/handoffs/YYYY-MM-DD-HHMMSS-<short-description>.md` with this structure:\n\n' +
    '```markdown\n' +
    '# Session Handoff — <date>\n\n' +
    '## Summary\n' +
    'One-paragraph overview of what was accomplished.\n\n' +
    '## Changes made\n' +
    '- List of files changed, with brief description of each change\n' +
    '- Include git diff summary if applicable\n\n' +
    '## Key findings\n' +
    '- Research results, discoveries, or evidence collected\n' +
    '- Tables of counts, confidence scores, or patterns\n' +
    '- Use same language as project conventions: observed, validated, lead, candidate, unsupported, experimental\n\n' +
    '## Blockers\n' +
    '- What\'s preventing the next step\n' +
    '- Any open questions or uncertainties\n\n' +
    '## Proof guard status\n' +
    '- Which guards were run and whether they PASSED/FAILED\n' +
    '- Any new guard baselines set\n\n' +
    '## Next steps\n' +
    '- Top recommendation for the next session\n' +
    '- Secondary leads to explore\n\n' +
    '## Commands used\n' +
    '- Exact commands run (for reproducibility)\n' +
    '```\n\n' +
    '## Context gathering\n\n' +
    'Always read these before writing:\n' +
    '1. `git diff --stat` and `git diff --cached --stat`\n' +
    '2. `docs/current-status.md` (last few sections)\n' +
    '3. Latest guard outputs if available (`Exports/attribute-extra-proof-guard-*.json`)\n' +
    '4. Test results if run\n' +
    '5. Any probe/decode output JSONs created\n\n' +
    '## Naming conventions\n\n' +
    '- Filename: `YYYY-MM-DD-HHMMSS-<kebab-case-description>.md`\n' +
    '- Timestamp: use current date/time in the filename, not the date in the content\n' +
    '- Description: short, kebab-case, e.g., `geometry-decode`, `position-source-probe`, `guard-validation`\n\n' +
    '## Safety\n\n' +
    '- Never include raw `Source/`, `Extracted/`, or `Exports/` paths or data in handoffs\n' +
    '- Redact user-profile paths (`C:\\\\Users\\\\<name>`) if present\n' +
    '- Don\'t over-claim: use project language (observed, validated, lead, candidate)\n' +
    '- Export results should always be labeled as experimental',
}

export default definition
