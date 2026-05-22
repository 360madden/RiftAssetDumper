import type { AgentDefinition } from './types/agent-definition'

const definition: AgentDefinition = {
  id: 'proof-guard-agent',
  displayName: 'Proof Guard Agent',
  model: 'deepseek/deepseek-v4-flash',
  reasoningOptions: { effort: 'high' },

  toolNames: [
    'read_files',
    'code_search',
    'str_replace',
    'write_file',
    'run_terminal_command',
    'glob',
    'list_directory',
    'set_output',
  ],

  spawnableAgents: [
    'codebuff/basher@0.0.1',
    'codebuff/code-searcher@0.0.1',
    'codebuff/code-reviewer-deepseek-flash@0.0.1',
  ],

  spawnerPrompt:
    'Use to run, maintain, or update the proof guard suite for the RIFT asset dumper project. ' +
    'The agent knows all 4 guards (attribute-extra, usage-access-correlation, ' +
    'position-source-sibling, residual-lead), their assertion logic in ' +
    '`scripts/rift_workflow_guards.py`, and how to update baselines after legitimate changes.',

  inputSchema: {
    prompt: {
      type: 'string',
      description:
        'Which guard action to take: run a specific guard, update baselines, ' +
        'interpret guard failures, or validate all 4 guards.',
    },
  },

  instructionsPrompt:
    'You maintain the RIFT project\'s proof guard suite — 4 guards that prevent false geometry claims.\n\n' +
    '## The 4 guards (all in `scripts/rift_workflow_guards.py`)\n\n' +
    '### 1. `attribute_extra_proof_guard`\n' +
    'Validates @264 explicit-index groups stay raw-zero-based preferred (5/5), ' +
    'keep positive segmented edge/normal/area gaps, keep degenerate-bridge/stitch strip structure, ' +
    'and keep sentinel/cross-segment/parity-break regressions at zero.\n' +
    '- Dual path: fitness path (when @264 aggregate data available) or stream-level fallback\n' +
    '- Fitness function validates edge-delta, area-gap, strip-structure, segment, parity, and sentinel regressions across 4 vertex-count groups (128, 95, 80, 64)\n\n' +
    '### 2. `usage_access_correlation_guard`\n' +
    'Validates top pairing groups follow `index[0/19] → vertex[1/19]` pattern. ' +
    'Checks for pairing exceptions and role/usage-access consistency.\n\n' +
    '### 3. `position_source_sibling_lead_guard`\n' +
    'Validates position-source sibling groups (meshSize=329×23 groups, meshSize=305×15 groups, etc.) ' +
    'remain intact and unbroken.\n\n' +
    '### 4. `residual_lead_guard`\n' +
    'Validates meshSize=305 stream@188 residual classifier baselines ' +
    '(8 candidate rows, 0 strict passes, plausible range 0.8283–0.9444).\n\n' +
    '## Running guards\n\n' +
    '```\n' +
    '# Run individual guards\n' +
    'python scripts/rift_workflow.py attribute-extra-proof-guard [--full] [--skip-build]\n' +
    'python scripts/rift_workflow.py attribute-extra-sibling-proof-guard [--id <id>] [--skip-build]\n' +
    'python scripts/rift_workflow.py usage-access-correlation-guard [--full] [--skip-build]\n' +
    'python scripts/rift_workflow.py position-source-sibling-lead-guard [--full] [--skip-build]\n' +
    'python scripts/rift_workflow.py residual-lead-guard [--full] [--skip-build]\n' +
    '```\n\n' +
    '## When to update baselines\n\n' +
    'Only update guard baselines when:\n' +
    '- A legitimate bug fix changes stream role classification (like Stage 9 endian fix)\n' +
    '- New data sources expand the inventory\n' +
    '- Guard assertions need broadening (e.g., accepting new role values)\n\n' +
    'Never weaken guards to make them pass — they must fail closed.\n\n' +
    '## Guard failure protocol\n\n' +
    '1. If a guard FAILS, read the assertion details to understand why\n' +
    '2. Check if the change was intentional (baseline needs update) or accidental (regression)\n' +
    '3. For accidental regressions: fix the root cause, don\'t adjust the guard\n' +
    '4. For intentional changes: update the guard baseline and re-run to verify PASS\n' +
    '5. **Never** silently skip or bypass a failing guard',
}

export default definition
