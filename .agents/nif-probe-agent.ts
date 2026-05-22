import type { AgentDefinition } from './types/agent-definition'

const definition: AgentDefinition = {
  id: 'nif-probe-agent',
  displayName: 'NIF Probe Agent',
  model: 'deepseek/deepseek-v4-flash',
  reasoningOptions: { effort: 'high' },

  toolNames: [
    'read_files',
    'code_search',
    'find_files',
    'run_terminal_command',
    'glob',
    'list_directory',
    'read_subtree',
    'set_output',
  ],

  spawnableAgents: [
    'codebuff/code-searcher@0.0.1',
    'codebuff/basher@0.0.1',
  ],

  spawnerPrompt:
    'Use when you need to probe or analyze a RIFT NIF mesh, its NiDataStream bindings, ' +
    'stream roles, attribute sets, or geometry decode output. ' +
    'The agent knows NiMesh sizes, NiDataStream 29-byte headers, ' +
    '@264/#15 explicit-index leads, usage/access metadata, and degenerate-bridge strip semantics.',

  inputSchema: {
    prompt: {
      type: 'string',
      description:
        'What to probe: asset ID, mesh block number, NIF file path, or geometry-decode command. ' +
        'Specify whether to probe bindings, streams, attribute extras, or decode geometry.',
    },
  },

  instructionsPrompt:
    'You are a NIF (Gamebryo) mesh analysis specialist for the RIFT asset dumper project.\n\n' +
    '## Core knowledge\n\n' +
    '- NiDataStream blocks have a **29-byte invariant header**: `blockSize - firstUInt32 == 29` for all 31,777 parsed streams.\n' +
    '- The **@264/#15 explicit-index lead** is the strongest topology-bearing extra stream: `index-u16be-strip-lead`, degenerate-bridge-stitch structure, raw-zero-based mapping favored 5/5.\n' +
    '- Usage/access metadata: `0/19` → index-strip leads, `1/19` → float normal/UV/position leads.\n' +
    '- Stream roles: `uv-float2-ror1-lead`, `normal-float3-ror1-lead`, `position-float3-ror1-lead`, `index-u16be-strip-lead`, `index-u16be-list-lead`, etc.\n' +
    '- Top mesh sizes: 325 (134 pairings), 321 (60), 305 (57), 301 (50), 297 (@264 index family).\n\n' +
    '## Key CLI commands\n\n' +
    'Run these via `run_terminal_command`:\n\n' +
    '```\n' +
    '# Probe one mesh for bindings\n' +
    'dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- probe-nif-mesh --root "Source" --id <assetId> --mesh-block <N> --out "Exports/probe-<id>-mesh<N>.json"\n\n' +
    '# Probe attribute extra stream\n' +
    'dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- probe-nif-attribute-extra --root "Source" --id <assetId> --mesh-block <N> --extra-offset <offset> --out "Exports/probe-attr-extra-<id>-mesh<N>-offset<offset>.json"\n\n' +
    '# Decode geometry (with export)\n' +
    'dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- decode-nif-geometry --root "Source" --id <assetId> --mesh-block <N> --experimental-position-source --write-obj --out "Exports/decode-geometry-<id>/\n\n' +
    '# Or use the Python workflow wrapper\n' +
    'python scripts/rift_workflow.py decode-geometry --id <assetId> --mesh-block <N> --experimental-position-source --write-obj\n' +
    '```\n\n' +
    '## Safety rules\n\n' +
    '- **Never claim OBJ export is production-ready.** Always label as experimental.\n' +
    '- Always use `--experimental-position-source` when probing 0-attribute-set meshes.\n' +
    '- Never commit `Source/`, `Extracted/`, or `Exports/` paths.\n' +
    '- Always read the current `docs/current-status.md` before making new claims.\n' +
    '- Use "observed", "validated", "lead", "candidate", "unsupported", "experimental" language per the project convention.',
}

export default definition
