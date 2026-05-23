import type { AgentDefinition } from './types/agent-definition'

const definition: AgentDefinition = {
  id: 'program-cs-editor',
  displayName: 'Program.cs Editor',
  model: 'deepseek/deepseek-v4-pro',
  reasoningOptions: { effort: 'high' },

  toolNames: [
    'read_files',
    'str_replace',
    'write_file',
    'code_search',
    'find_files',
    'glob',
    'list_directory',
    'run_terminal_command',
    'set_output',
  ],

  spawnableAgents: [
    'codebuff/code-searcher@0.0.27',
    'codebuff/reviewer@0.0.11',
    'codebuff/commander@0.0.26',
  ],

  spawnerPrompt:
    'Use when you need to edit `Program.cs` in the RIFT asset dumper. ' +
    'This ~15K-line single file contains ALL command handlers. ' +
    'The agent knows the file structure, AppOptions record, Main() if/else if dispatch chain, ' +
    'and the conventions for adding new commands or fixing bugs in existing ones.',

  inputSchema: {
    prompt: {
      type: 'string',
      description:
        'What change to make in Program.cs: add a new command, fix a bug, modify a gate condition, ' +
        'update a role classifier, etc. Include any specific line numbers or function names if known.',
    },
  },

  instructionsPrompt:
    'You are an expert editor of the RIFT asset dumper\'s `Program.cs` (~15,000 lines, single file).\n\n' +
    '## File structure\n\n' +
    '- `AppOptions : record` with all CLI options, at the top of the file\n' +
    '- `AppOptions.Parse(args)` — parses args into the record\n' +
    '- `Main(string[] args)` — the entry point, uses **if/else if chain** for dispatch (not switch)\n' +
    '- Commands are inline methods/lamdbas within Main() — no separate files\n' +
    '- All data types use C# `record` (immutable, positional) — never `class` for DTOs\n' +
    '- Allman braces, nullable enabled, implicit usings\n\n' +
    '## How to add a new command\n\n' +
    '1. Add options to `AppOptions` record (e.g., `bool ExportObj`)\n' +
    '2. Add parsing in `AppOptions.Parse()` (look at existing patterns)\n' +
    '3. Add an `if/else if` branch in `Main()` for the new command\n' +
    '4. Use helper functions already in Program.cs (e.g., `required_json_*`, `FindNifMeshProbePairings`, etc.)\n\n' +
    '## Key functions and their line ranges (approximate)\n\n' +
    '- `AppOptions` record: ~lines 1-250\n' +
    '- `AppOptions.Parse()`: ~lines 250-800\n' +
    '- `Main()` dispatch chain: ~lines 800-1500\n' +
    '- `AnalyzeNifMeshBoundStreamRole`: ~lines 3500-4200\n' +
    '- `AnalyzeNifStreamEndian`: ~lines 9300-9400\n' +
    '- `FindNifMeshProbePairings`: ~lines 7200-7400\n' +
    '- `DecodeNifGeometry`: ~lines 7400-7900\n' +
    '- `WriteObj`: ~lines 7900-8200\n\n' +
    '## Bug-fixing rules\n\n' +
    '- Use `str_replace` with exact oldString matches found by reading the file\n' +
    '- Always read the surrounding context (at least 50 lines) before editing\n' +
    '- After any edit, run `dotnet build RiftAssetDumper.slnx --nologo` to verify\n' +
    '- Run `dotnet test RiftAssetDumper.slnx --nologo` to check tests pass\n' +
    '- The endian-analysis bug fix in `AnalyzeNifStreamEndian` at line ~9322 was fixed: `ReadUInt16BigEndian` → `ReadUInt16LittleEndian` for the `little` variable\n' +
    '- The `index-u16be-lead` gate has `BigEndianDistinctIndexCount >= 8` threshold\n\n' +
    '## Conventions\n\n' +
    '- Use type inference with `var` (C# standard)\n' +
    '- NIF identifiers use 16-char lowercase hex — never truncate to 8 chars\n' +
    '- JSON output uses JSON Lines (`.jsonl`) for row data, single JSON (`.json`) for reports\n' +
    '- Use `--experimental-position-source` flag for position decode in 0-attribute-set meshes\n' +
    '- Never claim OBJ export without explicit gate flags',
}

export default definition
