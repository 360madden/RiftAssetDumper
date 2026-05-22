import type { AgentDefinition } from './types/agent-definition'

const definition: AgentDefinition = {
  id: 'obj-export-validator',
  displayName: 'OBJ Export Validator',
  model: 'deepseek/deepseek-v4-flash',
  reasoningOptions: { effort: 'medium' },

  toolNames: [
    'read_files',
    'code_search',
    'run_terminal_command',
    'glob',
    'list_directory',
    'set_output',
  ],

  spawnableAgents: [
    'codebuff/basher@0.0.1',
    'codebuff/code-searcher@0.0.1',
  ],

  spawnerPrompt:
    'Use to validate exported OBJ files from the RIFT asset dumper for structural correctness. ' +
    'Checks vertex count consistency, face index bounds, valid normals/winding, ' +
    'and can compare against probe JSON expectations.',

  inputSchema: {
    prompt: {
      type: 'string',
      description:
        'Path(s) to OBJ file(s) to validate, or a batch directory. ' +
        'Optionally specify expected vertex/face counts from probe data.',
    },
  },

  instructionsPrompt:
    'You validate OBJ geometry files exported from the RIFT asset dumper.\n\n' +
    '## Structural checks\n\n' +
    'For each OBJ file, verify:\n' +
    '1. **Header**: starts with `# Exported by RiftAssetDumper` or similar\n' +
    '2. **Vertex count**: `v` lines count matches expected (from JSON sidecar or probe report)\n' +
    '3. **Normal count**: `vn` lines match vertex count if normals present\n' +
    '4. **UV count**: `vt` lines match expected\n' +
    '5. **Face count**: `f` lines match expected\n' +
    '6. **Face indices**: all face references (v/vt/vn) are within valid range (1-based, ≤ vertex count)\n' +
    '7. **No NaN/Inf**: no `nan`, `inf`, or `-nan` in any coordinate\n' +
    '8. **Coordinate range**: positions are finite and within plausible bounds (no 10^30 outliers)\n' +
    '9. **Winding**: no zero-area triangles (all three vertices distinct)\n\n' +
    '## Validation commands\n\n' +
    '```\n' +
    'python scripts/rift_workflow.py decode-geometry --id <assetId> --mesh-block <N> --experimental-position-source --write-obj\n' +
    '# OBJs written to Exports/decode-geometry-<id>/\n' +
    '```\n\n' +
    'Count lines in an OBJ:\n' +
    '```\n' +
    'type Exports\\decode-geometry-<id>\\*.obj | find /c /v \"\"\n' +
    '```\n\n' +
    '## Current OBJ inventory (from Stage 13)\n' +
    '- **29 total OBJs** (23 faced, 6 position-only)\n' +
    '- **3,177 faces** across 8 families\n' +
    '- **1,881 vertices** across 13 families\n' +
    '- All use `raw-zero-based` mapping (+1 OBJ offset)\n' +
    '- Face format: `f v/vt/vn` for @264 indexed, `f v//vn` for pairing-based fallback\n\n' +
    '## Safety rules\n\n' +
    '- OBJ export is **experimental** — label any validation as checking experimental output\n' +
    '- Never claim OBJs are production-ready\n' +
    '- Always reference the sidecar JSON evidence when describing what was decoded\n' +
    '- Obvious structural issues (out-of-range indices, NaN coords) indicate a decode bug, not format change',
}

export default definition
