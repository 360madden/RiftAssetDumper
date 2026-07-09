# Memory Scanner Helper Addon

A Lua addon that runs inside RIFT to help us discover memory structures and API functions.

## Installation

1. Copy the `lua_addon/` folder to your RIFT addons directory:

   ```
   Documents\RIFT\Interface\Addons\MemoryScannerHelper\
   ```

2. The folder structure should be:

   ```
   Addons/MemoryScannerHelper/
   ├── Manifest.toc
   └── Core.lua
   ```

3. Launch RIFT and log in

4. The addon will auto-load and print: `[MSC] Loaded! Type /msc help for commands`

## Commands

Type `/msc help` in chat to see all commands.

| Command | Description |
|---------|-------------|
| `/msc help` | Show all commands |
| `/msc api` | List all registered Lua API functions |
| `/msc player` | Show player object data |
| `/msc units` | List all visible units |
| `/msc search <pattern>` | Search for API functions (e.g., `/msc search Unit`) |
| `/msc table <name>` | Dump a table (e.g., `/msc table Inspect`) |
| `/msc export` | Export all data for the memory scanner |

## If Commands Don't Work

You can also use these slash commands directly:

| Command | Description |
|---------|-------------|
| `/script MSC_Help()` | Show help |
| `/script MSC_Api()` | List API functions |
| `/script MSC_Player()` | Show player data |
| `/script MSC_Units()` | List units |
| `/script MSC_Export()` | Export all data |

## Usage with Memory Scanner

1. In RIFT, run: `/msc export`
2. Copy all output from chat
3. The data contains:
   - All registered Lua functions
   - All namespaces
   - Player object fields
   - Unit list with IDs

## What It Exports

### API Functions

```
FUNC:Inspect.Unit.Detail
FUNC:Inspect.Unit.List
...
```

### Namespaces

```
NS:Inspect
NS:Inspect.Unit
NS:Inspect.Item
...
```

### Player Fields

```
FIELD:posX=1234.56
FIELD:posY=5678.90
FIELD:name=MyCharacter
...
```

### Units

```
UNIT:player:MyCharacter:player
UNIT:npc12345:Mob Name:npc
...
```

## Why This Helps

Instead of reverse-engineering memory from scratch, this addon:

1. Shows us exactly what Lua API functions exist
2. Reveals the structure of game objects (what fields they have)
3. Gives us the actual memory layout from the Lua side
4. Helps us validate what we find in memory scanning

## Notes

- The addon uses the standard Rift addon format (Manifest.toc as Lua table)
- Compatible with Rift 4.3+ environment
- No external dependencies required
