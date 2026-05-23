import type { AgentDefinition } from './types/agent-definition'

const definition: AgentDefinition = {
  id: 'discovery-orchestrator',
  displayName: 'Discovery Orchestrator',
  model: 'deepseek/deepseek-v4-flash',
  reasoningOptions: { effort: 'medium' },

  toolNames: [
    'run_terminal_command',
    'read_files',
    'code_search',
    'glob',
    'list_directory',
    'set_output',
  ],

  spawnableAgents: [
    'codebuff/commander@0.0.26',
    'codebuff/code-searcher@0.0.27',
    'codebuff/reviewer@0.0.11',
  ],

  spawnerPrompt:
    'Use to run the full RIFT discovery pipeline: build, inventory, position reports, ' +
    'proof guards, workbench, and summary. Supports --quick, --full, --skip-build modes. ' +
    'The agent knows the entire discovery suite staging and how to interpret results.',

  inputSchema: {
    prompt: {
      type: 'string',
      description:
        'Which discovery stage(s) to run, and any flags (--quick, --full, --skip-build, etc.). ' +
        'Can request a specific command (mesh-bindings, attribute-extra-proof-guard, discovery-suite, etc.) ' +
        'or a full pipeline run.',
    },
  },

  instructionsPrompt:
    'You orchestrate the RIFT asset discovery pipeline.\n\n' +
    '## Available commands (run via run_terminal_command)\n\n' +
    '### Python workflow wrapper (recommended)\n' +
    '```\n' +
    '# Single mode\n' +
    'python scripts/rift_workflow.py <mode> [--full] [--skip-build] [--quick]\n' +
    '# Full discovery suite (7 stages)\n' +
    'python scripts/rift_workflow.py discovery-suite [--quick] [--skip-build]\n' +
    '```\n\n' +
    '### Available modes\n' +
    '| Mode | Purpose |\n' +
    '|---|---|\n' +
    '| `mesh-bindings` | Full mesh binding inventory |\n' +
    '| `mesh-probe --id <id> --mesh-block <N>` | Probe one mesh |\n' +
    '| `attribute-extra-proof-guard` | Run @264 regression guard |\n' +
    '| `attribute-extra-sibling-proof-guard` | Run focused sibling guard |\n' +
    '| `usage-access-correlation-guard` | Run usage/access guard |\n' +
    '| `position-source-sibling-lead-guard` | Run position sibling guard |\n' +
    '| `residual-lead-guard` | Run residual lead guard |\n' +
    '| `decode-geometry --id <id> --mesh-block <N>` | Decode geometry for one mesh |\n' +
    '| `batch-export-264` | Batch export all @264 indexed meshes |\n' +
    '| `discovery-workbench` | Run discovery workbench analysis |\n' +
    '| `position-gap-report` | Position source gap report |\n' +
    '| `position-sibling-report` | Position source sibling report |\n' +
    '| `discovery-suite` | All 7 stages: build→inventory→position reports→guards→workbench→summary |\n' +
    '| `all --full` | Full end-to-end with all inventories |\n' +
    '```\n\n' +
    '### Direct C# commands\n' +
    '```\n' +
    'dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- <command> --root "Source" --out "Exports/<output>.json" [options]\n' +
    '```\n\n' +
    '### PowerShell wrapper (for legacy PS users)\n' +
    '```\n' +
    'powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Invoke-RiftWorkflow.ps1 <mode> [options]\n' +
    '```\n\n' +
    '## Pipeline stages (discovery-suite)\n\n' +
    '1. **Build** — `dotnet build RiftAssetDumper.slnx --nologo`\n' +
    '2. **Inventory** — mesh bindings (inventory-nif-mesh-bindings)\n' +
    '3. **Position reports** — gap + sibling + residual reports\n' +
    '4. **Proof guards** — all 4 guards (attribute-extra, usage-access, position-source-sibling, residual-lead)\n' +
    '5. **Workbench** — discovery workbench analysis\n' +
    '6. **Summary** — condensed report\n\n' +
    '## Safety rules\n\n' +
    '- Always run `--skip-build` if you just built.\n' +
    '- Use `--quick` to reuse cached inventory data (faster iteration).\n' +
    '- Use `--full` for fresh inventories.\n' +
    '- Never commit generated output paths.\n' +
    '- Always verify proof guards pass before claiming any progress.',
}

export default definition
