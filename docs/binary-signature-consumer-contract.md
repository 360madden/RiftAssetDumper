# Binary Signature Consumer Contract

**Version**: 8.0  
**Date**: 2026-07-09  
**Target**: `rift_x64.exe`  
**ImageBase**: `0x140000000`  
**Schema**: `binary-signatures/v2`  
**Schema File**: `docs/schemas/binary-signatures-v1.schema.json`

---

## Overview

This document describes how to integrate with the Rift binary signature system to read player data at runtime. The pipeline is:

```
String scan → Table locate → Handler resolve → Registry access → Player data read
```

All addresses in this document are **virtual addresses (VA)** relative to the binary's image base of `0x140000000`. At runtime, apply the ASLR delta (see [ASLR Handling](#aslr-handling)).

---

## Step 1: Scan for the API Anchor String

The most stable entry point is the ASCII string `Inspect.Unit.Detail` in the `.rdata` section.

**Signature (hex)**:

```
49 6E 73 70 65 63 74 2E 55 6E 69 74 2E 44 65 74 61 69 6C 00
```

**Known VA**: `0x1426772D8`

**Scan with Reloaded.Memory.Sigscan**:

```csharp
var scanner = new SigScanScanner(process, module.BaseAddress, module.ModuleMemorySize);
scanner.AddPattern("InspectUnitDetail", "49 6E 73 70 65 63 74 2E 55 6E 69 74 2E 44 65 74 61 69 6C 00");
var results = scanner.Scan();
if (results.TryGetValue("InspectUnitDetail", out long address))
{
    // address is the runtime VA of the string
}
```

**Validation**: The 8 bytes at `StringVA - 0x08` should point to `"detail@unit"` (handler name string).

---

## Step 2: Locate the Pointer Table

The string is referenced by a pointer table in `.data`. Each entry is 8 bytes (QWORD).

**Known table structure** (contiguous, starting at `0x142EECD08`):

| Offset | VA | Points to | Role |
|--------|-----|-----------|------|
| +0x00 | `0x142EECD08` | `Inspect.Unit.Detail` | MethodName |
| +0x08 | `0x142EECD10` | `unit` | Category |
| +0x18 | `0x142EECD20` | `units` | Collection |
| +0x28 | `0x142EECD30` | `detail@unit` | Handler |
| +0x38 | `0x142EECD40` | `details@unit` | DetailsHandler |
| +0x48 | `0x142EECD50` | `id` | Field |
| +0x50 | `0x142EECD58` | `name` | Field |
| +0x58 | `0x142EECD60` | `nameSecondary` | Field |
| +0x60 | `0x142EECD68` | `guild` | Field |
| +0x68 | `0x142EECD70` | `titlePrefixName` | Field |
| +0x70 | `0x142EECD78` | `titleSuffixName` | Field |
| +0x78 | `0x142EECD80` | `titlePrefixId` | Field |
| +0x80 | `0x142EECD88` | `titleSuffixId` | Field |
| +0x88 | `0x142EECD90` | `player` | Field |
| +0x90 | `0x142EECD98` | `relation` | Field |
| +0x98 | `0x142EECDA0` | `level` | Field |

---

## Step 3: Resolve the Handler Function

The handler function at `0x140989570` (file offset `0x988570`) processes field lookups for `Inspect.Unit.Detail`.

**Fallback anchor** (if string scan breaks):

| Name | Signature | VA |
|------|-----------|-----|
| `handler-thunk` | `45 33 C0 BA 10 00 00 00 E9` | Variable |
| `vtable-dispatch` | `48 85 D2 74 0A 48 83 C1 10 48 8B 01 FF 50 08` | `0x14129C834` |

**Calling convention**: Microsoft x64 fastcall

| Register | Usage |
|----------|-------|
| RCX | Lua state / inspection context pointer |
| RDX | Field name string pointer (ASCII, null-terminated) |
| R8 | Unit object base pointer |
| R9 | Additional context |
| RAX | Return value (integer/string fields) |
| XMM0 | Return value (float fields) |

---

## Step 4: Access the Unit Registry

**Registry accessor**: `0x140758b10` (file offset `0x757f10`)

**Key instruction**: `MOV RAX, [RCX + RAX * 8 + 0x810]` at `0x140758bd3`

**Registry base**: Loaded via `LEA RCX, [RIP + 0x2ba33b5]` at `0x140758b14`

**Indexing formula**:

```
UnitObject = RegistryBase[RAX * 8 + 0x810]
```

Where `RAX` is the unit index/ID.

---

## Step 5: Read Player Data

### Unit Object Structure

| Offset | Type | Name | Description |
|--------|------|------|-------------|
| `0x120` | DWORD | `player_flag` | 1 = player, 0 = NPC |
| `0x6E0` | QWORD | `details_substructure` | Pointer to name/details sub-struct |
| `0x700` | BYTE | `flag_byte` | Boolean flag |
| `0xF0C` | DWORD | `comparison_field` | Compared with register value |

### Player Identification

```csharp
uint playerFlag = ReadUInt32(unitPtr + 0x120);
bool isPlayer = (playerFlag == 1);
```

### Player Coordinates

These are in a sub-structure, **not** directly in the unit object.

| Offset | Type | Name | ModRM Hits | Confidence |
|--------|------|------|------------|------------|
| `0x304` | float | `turn_rate` | 35 | inferred |
| `0x30C` | float | `facing_x` | 38 | inferred |
| `0x310` | float | `facing_y` | 566 | confirmed |
| `0x314` | float | `facing_z` | 41 | inferred |
| `0x320` | float | `pos_x` | 623 | confirmed |
| `0x324` | float | `pos_y` | 39 | inferred |
| `0x328` | float | `pos_z` | 646 | confirmed |

```csharp
float posX = ReadFloat(subStructPtr + 0x320);
float posY = ReadFloat(subStructPtr + 0x324);
float posZ = ReadFloat(subStructPtr + 0x328);
```

---

## ASLR Handling

All VAs in this database are relative to `ImageBase = 0x140000000`. At runtime:

```
RuntimeVA = DatabaseVA - 0x140000000 + RuntimeModuleBase
```

For RIP-relative instructions:

```
TargetVA = RIP_of_instruction + 4 + sign_extend(disp32)
```

**Example**:

```csharp
long runtimeBase = process.MainModule.BaseAddress;
long delta = runtimeBase - 0x140000000;
long handlerVA = 0x140989570 + delta;  // runtime address of handler
```

---

## Fallback Strategies

| Priority | Scenario | Strategy |
|----------|----------|----------|
| 1 | String `Inspect.Unit.Detail` moves | Scan for `detail@unit` or `details@unit` as secondary anchors |
| 2 | Handler VA changes | Re-trace from string scan; follow the CALL at registration |
| 3 | Registry offset 0x810 changes | Search for `MOV RAX, [RCX+RAX*8+<offset>]` pattern |
| 4 | Player flag offset 0x120 changes | Search for `CMP dword ptr [RAX+<offset>], 1` near handler |
| 5 | All signatures break | Fall back to any `Inspect.Unit.*` string in .rdata |

---

## Complete Integration Checklist

1. [ ] Scan `.rdata` for `Inspect.Unit.Detail\0`
2. [ ] Locate pointer table in `.data`
3. [ ] Resolve handler function `0x140989570`
4. [ ] Find registry accessor `0x140758b10`
5. [ ] Read registry base from `.data`
6. [ ] Index into registry to get unit object
7. [ ] Check `player_flag` at `[UnitPtr+0x120] == 1`
8. [ ] Read coordinates at `[SubStruct+0x320]` (pos_x), `[SubStruct+0x328]` (pos_z)
9. [ ] Apply ASLR delta to all addresses
10. [ ] Validate every pointer before dereferencing

---

## Signature Database

Full signature database (Phase 8 final):

```
Exports/binary-phase8/rift-x64-signature-database.json
```

JSON Schema for validation:

```
docs/schemas/binary-signatures-v1.schema.json
```

Previous phase outputs (reference only):

```
Exports/binary-phase5/rift-x64-signature-database.json
Exports/binary-phase7/integration-contract.json
```

---

## Schema Validation

Validate the signature database against the JSON schema before importing:

```csharp
// Using NJsonSchema or similar library
var schema = await JsonSchema.FromFileAsync("docs/schemas/binary-signatures-v1.schema.json");
var database = await File.ReadAllTextAsync("Exports/binary-phase8/rift-x64-signature-database.json");
var validationErrors = schema.Validate(database);

if (validationErrors.Any())
{
    foreach (var error in validationErrors)
        Console.WriteLine($"Schema error: {error.Kind} - {error.Path}");
    throw new InvalidOperationException("Signature database failed schema validation");
}
```

**Key constraints enforced by the schema**:

| Constraint | Value | Purpose |
|------------|-------|---------|
| `SchemaVersion` | `const "binary-signatures/v2"` | Prevents version drift |
| `additionalProperties` | `false` at all levels | No uncontrolled fields |
| `StabilityTier` | `enum [1, 2, 3]` | Tier classification |
| `Confidence` | `enum [high, medium, low, inferred, confirmed]` | Field confidence levels |
| `SignatureHex` | Pattern `^[0-9A-Fa-f ?]+$` | Valid hex with wildcards |
| Anchor `UniquenessVerified` | Required boolean | Ensures uniqueness was checked |

**If validation fails**: The database may be from an incompatible version or may have been corrupted during transfer. Re-run the Phase 8 extraction pipeline.

---

## Versioning and Updates

### Version Format

The database uses `SchemaVersion: "binary-signatures/v2"`. The schema file is versioned independently as `binary-signatures-v1.schema.json` (schema version 1, data format version 2).

### When to Re-extract

After a game patch, re-extract the database in this order:

1. **Binary metadata** — PE timestamp, file size will change
2. **String anchors** — Check if `Inspect.Unit.Detail` moved in `.rdata`
3. **Handler chain** — Registration → handler → registry accessor VAs
4. **ModRM scan** — Confirm offsets 0x304-0x328 still active
5. **Anchor uniqueness** — Re-verify all 11 anchors against the new binary
6. **Struct layouts** — Confirm field offsets are unchanged

### Breaking vs Non-Breaking Changes

**Breaking** (require schema version bump and consumer update):

- Anchor signature bytes change (not just addresses)
- Struct layout offsets shift
- Registry table offset (0x810) changes
- Calling convention or register usage changes
- New `SchemaVersion` value

**Non-breaking** (require only data update, consumers auto-adapt):

- VAs shift due to recompilation (ASLR handles this)
- New anchors added to the database
- New fields discovered in existing structs
- Updated confidence levels
- Updated `ExtractedAt` timestamp

### Consumer Migration

When `SchemaVersion` changes:

1. Update the schema file (`binary-signatures-v1.schema.json`)
2. Update consumer code to handle the new schema
3. Re-extract the database against the new schema
4. Validate the new database passes the updated schema
5. Deploy updated consumer with new database

---

## Ghidra Corrections (Phase 3-5)

Previous analysis incorrectly attributed player coordinate reads to:

| Function | Actual Role | Why It Was Wrong |
|----------|-------------|------------------|
| `FUN_1408b39d0` | AATree UI dialog handler | 0x320 displacement is a UI struct offset, not pos_x |
| `FUN_140da8870` | PetBar UI handler | 0x328 displacement is a texture path offset, not pos_z |
| `FUN_14078a0d0` | 5,784-instruction property dispatch | Repeatedly calls factory/lookup helpers — NOT coordinate access |

The actual player coordinate access is distributed across 1,337 ModRM `[base+disp32]` instructions found by the byte-scanner, concentrated in functions using RBX/RCX base registers.
