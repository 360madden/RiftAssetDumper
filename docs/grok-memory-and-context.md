# Grok Memory & Context Setup (RiftAssetDumper)

This repository uses Grok's cross-session memory system for persistent recall of RIFT discovery work, proof results, naming conventions, parser state, and architectural decisions across many sessions.

## Current Status

- Memory is **enabled globally** for the user (see `~/.grok/config.toml`).
- First-turn memory injection is active.
- Dream consolidation runs automatically in the background.
- Workspace memory is scoped to this git repository (all clones/worktrees share the same memory store).

## How to Start a Session With Memory

From inside this directory (recommended):

```powershell
# Primary (Python)
python grok-here.py

# Or with an initial prompt
python grok-here.py --prompt "Continue the NiDataStream proof work from last session"

# With YOLO (auto-approve) for trusted periods
python grok-here.py --yolo
```

From cmd.exe or Explorer (via minimal shim):

```cmd
grok-here
```

Normal launch also works once memory is enabled in your global config:

```powershell
grok
```

## Key Memory Commands Inside Grok

| Command              | Purpose |
|----------------------|---------|
| `/memory`            | Browse all workspace + global memory files |
| `/flush`             | Immediately save a rich LLM summary of the current session |
| `/dream`             | Consolidate scattered session logs into clean topics |
| `remember ...`       | Save a fact/decision/convention directly |
| `forget ...`         | Remove something from memory |
| `what do you remember?` | Ask Grok to summarize its current knowledge for this workspace |
| `grok memory stats`  | CLI: show index size, chunk counts, etc. |
| `grok memory edit`   | Open the workspace MEMORY.md in your editor |

## Recommended Workflow

1. Start sessions with `.\grok-here.ps1`.
2. At the end of any productive discovery/proof session, run `/flush` before exiting or compacting.
3. Let dream consolidation run (or trigger manually with `/dream`).
4. Use explicit `remember "NiMesh 0x2b has extra position stream at offset 0x..."` when you discover something important.

## Files

- Workspace memory lives at `%USERPROFILE%\.grok\memory\<project-hash>\MEMORY.md`
- Session logs are in the `sessions/` subfolder (auto-summarized).
- Global cross-project facts are in `%USERPROFILE%\.grok\memory\MEMORY.md`

## Disabling (Emergency)

Launch with the override:

```powershell
$env:GROK_MEMORY="0"; grok
```

Or use `.\grok-here.ps1 -NoMemory`.

## See Also

- `~/.grok/docs/user-guide/13-memory.md` (full upstream reference)
- AGENTS.md (repo safety + reasoning policy)
- `docs/current-status.md`
